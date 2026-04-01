from langchain_core.tools import tool


@tool
async def find_nearby_places(address: str, place_type: str) -> str:
    """
    Find places of a given type near an address.
    place_type examples: 'grocery store', 'bar', 'gym', 'park', 'coffee shop'.
    Returns the nearest match with distance if available.

    TODO: implement using Google Places API (GOOGLE_PLACES_API_KEY in .env.example).
    Google Places is purpose-built for this — returns structured name, address, distance,
    rating, and hours. Example using the places-nearby endpoint:
        import requests
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": "{lat},{lng}",  # geocode address first
            "rankby": "distance",
            "keyword": place_type,
            "key": os.getenv("GOOGLE_PLACES_API_KEY"),
        }
        results = requests.get(url, params=params).json()["results"]
    """
    return (
        f"[STUB] {place_type} near '{address}': "
        f"not yet implemented - try SerpAPI google_maps engine first, "
        f"fall back to Google Places API if needed"
    )
