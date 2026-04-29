import re
import os
import asyncio
from urllib.parse import urlparse
from firecrawl import AsyncFirecrawl
from langchain_core.callbacks.manager import adispatch_custom_event
from ..state import RentalState

TRUSTED_DOMAINS = {
    "zillow.com",
    "apartments.com",
    # "trulia.com",  # scraping auth issues
    # "realtor.com",
    # "rent.com",
    # "zumper.com",
    # "padmapper.com",
}

# how many good (non-disqualified) listing profiles we want before proceeding to reducer
MIN_GOOD_RESULTS = 3

# cap on how many search + listing cycles we'll run before giving up and going to reducer
MAX_SEARCH_ATTEMPTS = int(os.getenv("MAX_SEARCH_ATTEMPTS", "2"))

# per-round URL budget to bound end-to-end latency and API spend.
MAX_URLS_PER_ROUND = int(os.getenv("MAX_URLS_PER_ROUND", "9"))

# max category pages to scrape per round
MAX_CATEGORY_PAGES = int(os.getenv("MAX_CATEGORY_PAGES", "10"))


def _is_valid_listing(url: str) -> bool:
    """
    Keep only individual listing pages from trusted rental sites.
    - Zillow: must start with /homedetails/
    - apartments.com: 2 segments where the last is a short alphanumeric listing ID
    - Others: 3+ segments (heuristic for detail pages vs search pages)
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if not any(hostname == d or hostname.endswith("." + d) for d in TRUSTED_DOMAINS):
            return False
        if parsed.query:
            return False
        segments = [s for s in parsed.path.split("/") if s]

        if "zillow.com" in hostname:
            return len(segments) >= 2 and segments[0] == "homedetails"

        if "apartments.com" in hostname:
            if len(segments) != 2:
                return False
            slug, listing_id = segments
            if not re.match(r'^[a-z0-9]{6,9}$', listing_id):
                return False
            # Property slug must be a street address (starts with digit) or a long property name (>30 chars)
            return slug[0].isdigit() or len(slug) > 30

        return len(segments) >= 3
    except Exception:
        return False


def _is_category_page(url: str) -> bool:
    """
    Return True if the URL is a trusted domain search/browse results page
    (not an individual listing, but a page that likely contains listing links).
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if not any(hostname == d or hostname.endswith("." + d) for d in TRUSTED_DOMAINS):
            return False
        if parsed.query:
            return False
        if _is_valid_listing(url):
            return False
        segments = [s for s in parsed.path.split("/") if s]
        return 1 <= len(segments) <= 4
    except Exception:
        return False


async def _scrape_category_page(url: str) -> list[str]:
    """
    Use Firecrawl to render a category/search page and extract individual listing URLs.
    Returns a deduplicated list of URLs that pass _is_valid_listing().
    """
    try:
        app = AsyncFirecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))
        result = await asyncio.wait_for(app.scrape(url, formats=["links"]), timeout=30)
        links = result.links or []
        found = []
        seen = set()
        for href in links:
            href = href.split("?")[0].split("#")[0]
            if href not in seen and _is_valid_listing(href):
                seen.add(href)
                found.append(href)
        return found
    except Exception as e:
        await adispatch_custom_event("error_log", {
            "node": "supervisor:expand",
            "error": f"{type(e).__name__} scraping {url[:80]}: {str(e)[:200]}",
            "level": "error",
        })
        return []


async def supervisor_node(state: RentalState) -> dict:
    all_search_results = state.get("search_results", [])
    already_searched = set(state.get("searched_urls", []))

    # collect all raw URLs from search results
    raw_urls = []
    for result_batch in all_search_results:
        for r in result_batch.get("results", []):
            link = r.get("link", "")
            if link:
                raw_urls.append(link)

    # bucket into individual listings vs category pages, skipping already-seen URLs
    seen = set(already_searched)
    direct_listings = []
    category_pages = []

    for url in raw_urls:
        if url in seen:
            continue
        seen.add(url)
        if _is_valid_listing(url):
            direct_listings.append(url)
        elif _is_category_page(url):
            category_pages.append(url)

    # scrape category pages in parallel to extract individual listing URLs
    extracted_listings = []
    if category_pages:
        pages_to_scrape = category_pages[:MAX_CATEGORY_PAGES]
        scrape_results = await asyncio.gather(*[_scrape_category_page(u) for u in pages_to_scrape])
        for batch in scrape_results:
            for url in batch:
                if url not in seen:
                    seen.add(url)
                    extracted_listings.append(url)

        console_msg = (
            f"Scraped {len(pages_to_scrape)} category pages → "
            f"{len(extracted_listings)} additional listings found"
        )
        await adispatch_custom_event("error_log", {
            "node": "supervisor",
            "error": console_msg,
            "level": "warn",
        })

        # emit a UI process step if we found anything from category pages
        if extracted_listings:
            await adispatch_custom_event("supervisor_expand", {
                "category_count": len(pages_to_scrape),
                "extracted_count": len(extracted_listings),
                "detail": extracted_listings,
            })

    # combine: direct first (higher confidence), then extracted — deduplicated by `seen` above
    all_new_urls = (direct_listings + extracted_listings)[:MAX_URLS_PER_ROUND]

    await adispatch_custom_event("error_log", {
        "node": "supervisor",
        "error": (
            f"Final queue: {len(direct_listings)} direct + {len(extracted_listings)} extracted "
            f"= {len(all_new_urls)} total (cap {MAX_URLS_PER_ROUND})"
        ),
        "level": "warn",
    })

    return {
        "pending_urls": all_new_urls,
        # track both individual URLs and category pages so retry rounds skip them
        "searched_urls": all_new_urls + category_pages,
    }


async def results_check_node(state: RentalState) -> dict:
    return {"search_attempts": state.get("search_attempts", 0) + 1}


def route_after_results_check(state: RentalState) -> str:
    good_profiles = [
        p for p in state.get("listing_profiles", [])
        if not p.get("disqualified")
    ]
    attempts = state.get("search_attempts", 0)

    if len(good_profiles) >= MIN_GOOD_RESULTS or attempts >= MAX_SEARCH_ATTEMPTS:
        return "reducer"

    return "planner"
