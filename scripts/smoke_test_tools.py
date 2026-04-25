"""
Smoke test for all five listing-agent tools. Runs each in turn and prints results.
Requires a fully configured .env with all API keys (see .env.example).

Usage:
    python -m scripts.smoke_test_tools
"""
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()


REQUIRED_KEYS = [
    "ANTHROPIC_API_KEY",
    "SERPAPI_API_KEY",
    "FIRECRAWL_API_KEY",
    "GOOGLE_MAPS_API_KEY",
]


def check_env():
    missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        print(f"Missing env vars: {missing}")
        print("Add them to .env before running the smoke test.")
        return False
    print("All API keys present.")
    return True


async def test_commute():
    from graph.tools.commute import get_commute_time
    print("\n--- get_commute_time (transit) ---")
    result = await get_commute_time.ainvoke({
        "origin": "4521 Telegraph Ave, Oakland, CA",
        "destination": "UC Berkeley, Soda Hall",
        "mode": "transit",
    })
    print(json.dumps(result, indent=2))
    return "duration_text" in result


async def test_places():
    from graph.tools.places import find_nearby_places
    print("\n--- find_nearby_places (gym) ---")
    result = await find_nearby_places.ainvoke({
        "address": "4521 Telegraph Ave, Oakland, CA",
        "place_type": "gym",
    })
    print(json.dumps(result, indent=2)[:1500])
    return bool(result.get("results"))


async def test_search():
    from graph.tools.search import search_web
    print("\n--- search_web ---")
    result = await search_web.ainvoke({"query": "1 bedroom apartment Oakland under 2000 site:craigslist.org"})
    print(json.dumps(result, indent=2)[:1500])
    return len(result) > 0


async def test_scraper():
    from graph.tools.scraper import scrape_listing
    print("\n--- scrape_listing (Zillow) ---")
    # Pick any current Zillow detail URL; the test just verifies the call path works.
    url = "https://www.zillow.com/homedetails/538-3rd-Ave-APT-2-San-Francisco-CA-94118/461374502_zpid/"
    try:
        result = await scrape_listing.ainvoke({"url": url})
        preview = (result.get("raw_text") or "")[:500]
        print(preview)
        return len(preview) > 50
    except Exception as e:
        print(f"scrape_listing failed (may be a dead URL): {e}")
        return False


async def test_photos():
    from graph.tools.photos import analyze_listing_photos
    print("\n--- analyze_listing_photos ---")
    # A public test image that won't require auth
    urls = ["https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"]
    try:
        result = await analyze_listing_photos.ainvoke({
            "image_urls": urls,
            "focus_areas": "natural_light",
        })
        print(json.dumps(result, indent=2))
        return isinstance(result, dict)
    except Exception as e:
        print(f"analyze_listing_photos failed: {e}")
        return False


async def main():
    if not check_env():
        return
    results = {
        "commute":  await test_commute(),
        "places":   await test_places(),
        "search":   await test_search(),
        "scraper":  await test_scraper(),
        "photos":   await test_photos(),
    }
    print("\n\n=== SUMMARY ===")
    for tool, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {tool:10s} {status}")


if __name__ == "__main__":
    asyncio.run(main())
