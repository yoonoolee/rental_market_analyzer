from langchain_core.tools import tool


@tool
async def find_nearby_places(address: str, place_type: str) -> str:
    """
    Find places of a given type near an address.
    place_type examples: 'grocery store', 'bar', 'gym', 'park', 'coffee shop'.
    Returns the nearest match with distance if available.

    TODO: try SerpAPI google_maps engine first - no extra API key needed,
    uses the existing SERPAPI_API_KEY. Example:
        from serpapi import GoogleSearch
        results = GoogleSearch({
            "engine": "google_maps",
            "q": f"{place_type} near {address}",
            "api_key": os.getenv("SERPAPI_API_KEY"),
        }).get_dict()
    If google_maps results are insufficient (inconsistent distances, missing data),
    fall back to Google Places API which requires a separate GOOGLE_PLACES_API_KEY.
    """
    return (
        f"[STUB] {place_type} near '{address}': "
        f"not yet implemented - try SerpAPI google_maps engine first, "
        f"fall back to Google Places API if needed"
    )
