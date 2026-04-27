import os
import asyncio
from firecrawl import AsyncFirecrawl
from langchain_core.tools import tool
from langchain_core.callbacks.manager import adispatch_custom_event

_JSON_FORMAT = {
    "type": "json",
    "prompt": "Extract apartment listing details from this page. Return all fields you can find, null for anything not present.",
    "schema": {
        "type": "object",
        "properties": {
            "price":        {"type": ["number", "null"]},
            "address":      {"type": ["string", "null"]},
            "bedrooms":     {"type": ["number", "null"]},
            "bathrooms":    {"type": ["number", "null"]},
            "sqft":         {"type": ["number", "null"]},
            "floor":        {"type": ["number", "null"]},
            "pet_friendly": {"type": ["boolean", "null"]},
            "pet_deposit":  {"type": ["number", "null"]},
            "furnishing":   {"type": ["string", "null"]},
            "amenities":    {"type": "array", "items": {"type": "string"}},
            "images":       {"type": "array", "items": {"type": "string"}},
            "description":  {"type": ["string", "null"]},
        }
    }
}


@tool
async def scrape_listing(url: str) -> dict:
    """
    Scrape a rental listing page using Firecrawl's structured extraction.
    Returns clean structured fields (price, address, images, amenities, etc.)
    directly — works generically across any listing site.

    Returns the extracted fields on success, or {url, error} if scraping fails.
    The listing agent should check for the 'error' key and disqualify if present.
    """
    try:
        app = AsyncFirecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))
        result = await asyncio.wait_for(app.scrape(url, formats=[_JSON_FORMAT]), timeout=50)
        data = dict(result.json or {})
        data["url"] = url
        return data
    except Exception as e:
        err_str = str(e)
        err_lower = err_str.lower()
        if any(x in err_lower for x in ("credit", "billing", "quota", "payment", "402", "insufficient")):
            level, label = "error", "FirecrawlCreditsError"
        elif "429" in err_str or "rate limit" in err_lower:
            level, label = "warn", "FirecrawlRateLimit"
        elif "401" in err_str or "unauthorized" in err_lower or "invalid api key" in err_lower:
            level, label = "error", "FirecrawlAuthError"
        else:
            level, label = "error", f"FirecrawlError({type(e).__name__})"
        await adispatch_custom_event("error_log", {
            "node": "scraper",
            "error": f"{label} for {url[:80]}: {err_str[:200]}",
            "level": level,
        })
        return {"url": url, "error": err_str}
