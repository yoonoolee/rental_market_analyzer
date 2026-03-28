from langchain_core.tools import tool


@tool
async def get_commute_time(origin: str, destination: str, mode: str = "transit") -> str:
    """
    Get estimated commute time from an origin address to a destination.
    Mode can be 'transit', 'driving', or 'walking'.

    TODO: implement using Google Maps Distance Matrix API.
    - pip install googlemaps
    - requires GOOGLE_MAPS_API_KEY in environment
    Example:
        import googlemaps
        gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
        result = gmaps.distance_matrix(origin, destination, mode=mode)
        duration = result["rows"][0]["elements"][0]["duration"]["text"]
    """
    return (
        f"[STUB] Commute from '{origin}' to '{destination}' by {mode}: "
        f"not yet implemented - add GOOGLE_MAPS_API_KEY and implement this tool"
    )
