"""
Experiment: Internet Search (SerpAPI) Quality

Variants compared:
  - baseline_5:  5 results per query  (current production)
  - reduced_3:   3 results per query
  - expanded_10: 10 results per query

Held constant:
  - Query set (generated from pref_001 preferences)
  - SerpAPI GoogleSearch engine
  - site: operators (craigslist, zillow, apartments, trulia)
    apartments.com included: category pages are followed by _scrape_category_page,
    so they still yield individual listing URLs via the two-hop path
    hotpads.com excluded: returns 0-1 usable results consistently across all variants

Metrics:
  - listings_per_query  : avg individual listing URLs produced per query, after following
                          category pages (Firecrawl scrape). This is the true signal —
                          it counts the same way the production supervisor_node does.
  - direct_per_query    : listings found directly (no category page hop needed)
  - extracted_per_query : listings found by scraping category pages
  - query_relevance     : LLM judge score (1-10) for result relevance to query
  - yield_rate          : % of queries producing >= 1 listing (direct or extracted)
  - latency_ms          : wall-clock time per query (search + category scrape)
  - api_credits_used    : SerpAPI credits (1 per query) + Firecrawl scrapes
"""
import json
import os
import asyncio

from firecrawl import AsyncFirecrawl

from evals.config import SERPAPI_KEY, RESULTS_DIR, SEARCH_VARIANTS
from evals.metrics.nlp import LatencyTimer
from evals.metrics.llm_judge import LLMJudge

# Import the production URL classifiers directly — same logic the pipeline uses.
# _scrape_category_page is NOT imported because it calls adispatch_custom_event
# which requires a LangChain run context. We use _scrape_category_page_eval below
# which is identical minus the event dispatch.
from graph.nodes.supervisor import _is_valid_listing, _is_category_page


async def _scrape_category_page_eval(url: str) -> list[str]:
    """Same as supervisor._scrape_category_page but without adispatch_custom_event,
    which requires a LangChain run context unavailable in the eval runner."""
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
    except Exception:
        return []

# Representative queries derived from pref_001 preferences.
# apartments.com is included — its category pages are handled by the supervisor's
# _scrape_category_page step, so they still produce individual listing URLs.
# hotpads.com remains excluded — returns 0-1 results total, not worth a SerpAPI credit.
# zillow inurl:homedetails forces individual unit pages instead of search result pages.
TEST_QUERIES = [
    "2 bedroom apartment for rent San Francisco under $3000 site:craigslist.org",
    "2br apartment San Francisco $2000-$3000 site:zillow.com inurl:homedetails",
    "2 bedroom pet friendly apartment San Francisco SOMA Mission under $3000 site:apartments.com",
    "2 bedroom apartment near Salesforce Tower San Francisco site:trulia.com",
    "2br flat San Francisco Noe Valley Castro $2500 $3000 site:trulia.com",
]

MAX_CATEGORY_PAGES_PER_QUERY = 3  # cap to bound Firecrawl cost in eval


def run_single_query(query: str, num_results: int) -> dict:
    """Execute one SerpAPI query and return stripped results + metadata."""
    from serpapi import GoogleSearch

    with LatencyTimer() as timer:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": num_results,
            "engine": "google",
        }
        results_raw = GoogleSearch(params).get_dict()

    organic = results_raw.get("organic_results", [])[:num_results]
    stripped = [
        {"title": r.get("title", ""), "link": r.get("link", ""), "snippet": r.get("snippet", "")}
        for r in organic
    ]
    return {"query": query, "results": stripped, "latency_ms": timer.elapsed_ms}


async def expand_query_results(urls_with_snippets: list[dict]) -> dict:
    """
    Mirror the production supervisor_node logic:
    - Direct listing URLs are kept as-is
    - Category pages are scraped with Firecrawl to extract individual listing links
    Returns counts and the final listing URL list.
    """
    direct = []
    category_pages = []
    seen = set()

    for item in urls_with_snippets:
        url = item["link"]
        if url in seen:
            continue
        seen.add(url)
        if _is_valid_listing(url):
            direct.append(url)
        elif _is_category_page(url):
            category_pages.append(url)

    # Scrape category pages in parallel, capped to control eval cost
    extracted = []
    pages_to_scrape = category_pages[:MAX_CATEGORY_PAGES_PER_QUERY]
    if pages_to_scrape:
        scrape_results = await asyncio.gather(*[_scrape_category_page_eval(u) for u in pages_to_scrape])
        for batch in scrape_results:
            for url in batch:
                if url not in seen:
                    seen.add(url)
                    extracted.append(url)

    return {
        "direct": direct,
        "extracted": extracted,
        "all_listings": direct + extracted,
        "category_pages_scraped": len(pages_to_scrape),
    }


async def evaluate_variant_async(variant_name: str, config: dict, judge: LLMJudge) -> dict:
    num_results = config["num_results"]
    per_query_metrics = []

    for query in TEST_QUERIES:
        with LatencyTimer() as total_timer:
            search_result = run_single_query(query, num_results)
            urls_with_snippets = search_result["results"]
            expansion = await expand_query_results(urls_with_snippets)

        results_text = "\n".join(
            f"- {r['title']}: {r['snippet']}" for r in urls_with_snippets
        )
        relevance_judge = judge.query_relevance(query, results_text)
        query_relevance = relevance_judge.get("score", 0)

        per_query_metrics.append({
            "query": query,
            "num_search_returned": len(urls_with_snippets),
            "direct_listings": len(expansion["direct"]),
            "extracted_listings": len(expansion["extracted"]),
            "total_listings": len(expansion["all_listings"]),
            "category_pages_scraped": expansion["category_pages_scraped"],
            "query_relevance": query_relevance,
            "has_any_listing": len(expansion["all_listings"]) > 0,
            "latency_ms": total_timer.elapsed_ms,
        })

    n = len(per_query_metrics)
    total_firecrawl_scrapes = sum(m["category_pages_scraped"] for m in per_query_metrics)

    return {
        "variant": variant_name,
        "config": config,
        "per_query": per_query_metrics,
        "aggregate": {
            "mean_listings_per_query": round(sum(m["total_listings"] for m in per_query_metrics) / n, 2),
            "mean_direct_per_query": round(sum(m["direct_listings"] for m in per_query_metrics) / n, 2),
            "mean_extracted_per_query": round(sum(m["extracted_listings"] for m in per_query_metrics) / n, 2),
            "mean_query_relevance": round(sum(m["query_relevance"] for m in per_query_metrics) / n, 2),
            "yield_rate": round(sum(1 for m in per_query_metrics if m["has_any_listing"]) / n, 3),
            "mean_latency_ms": round(sum(m["latency_ms"] for m in per_query_metrics) / n, 1),
            "estimated_serpapi_credits": n,
            "estimated_firecrawl_scrapes": total_firecrawl_scrapes,
        },
    }


def evaluate_variant(variant_name: str, config: dict, judge: LLMJudge) -> dict:
    return asyncio.run(evaluate_variant_async(variant_name, config, judge))


def run(variants: list[str] | None = None) -> dict:
    judge = LLMJudge()
    targets = variants or list(SEARCH_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = SEARCH_VARIANTS[name]
        print(f"  Running search variant: {name} (num_results={config['num_results']})")
        all_results[name] = evaluate_variant(name, config, judge)

    output_path = RESULTS_DIR / "search_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
