import os
import asyncio
from firecrawl import AsyncFirecrawl
from langchain_core.tools import tool

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
        result = await asyncio.wait_for(app.scrape(url, formats=[_JSON_FORMAT]), timeout=30)
        data = dict(result.json or {})
        data["url"] = url
        return data
    except Exception as e:
        return {"url": url, "error": str(e)}
