from langchain_core.tools import tool


@tool
async def scrape_listing(url: str) -> dict:
    """
    Scrape a rental listing page and return structured data including
    price, floor, address, pet policy, description, and image URLs.

    TODO: implement actual scraping. Options to evaluate:
    - requests + BeautifulSoup for simpler pages (Craigslist is relatively scrape-friendly)
    - Playwright or Selenium for JS-heavy pages (Zillow, Apartments.com render client-side)
    - Firecrawl or ScrapingBee for a managed solution that handles anti-bot measures
    Note: most major listing sites have anti-scraping protections - test each carefully.
    """
    return {
        "url": url,
        "raw_text": f"[STUB] Scraped content for {url} - implement scraping to populate this",
        "address": None,
        "price": None,
        "floor": None,
        "pet_policy": None,
        "description": "[STUB] listing description not available yet",
        "images": [],
    }
