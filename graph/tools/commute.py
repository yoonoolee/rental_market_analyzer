import os
import asyncio
import googlemaps
from langchain_core.tools import tool


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
    return _client


def _distance_matrix_sync(origin: str, destination: str, mode: str) -> dict:
    client = _get_client()
    try:
        result = client.distance_matrix(origin, destination, mode=mode)
        element = result["rows"][0]["elements"][0]
        if element["status"] != "OK":
            return {
                "error": f"No route found ({element['status']})",
                "origin": origin,
                "destination": destination,
                "mode": mode,
            }
        return {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "duration_text": element["duration"]["text"],
            "duration_seconds": element["duration"]["value"],
            "distance_text": element["distance"]["text"],
        }
    except Exception as e:
        return {"error": str(e), "origin": origin, "destination": destination, "mode": mode}


@tool
async def get_commute_time(origin: str, destination: str, mode: str = "transit") -> dict:
    """
    Get estimated commute time from an origin address to a destination using the
    Google Maps Distance Matrix API.

    mode: 'transit', 'driving', 'bicycling', or 'walking' (default 'transit').
    Returns {origin, destination, mode, duration_text, duration_seconds, distance_text}
    on success, or {error, origin, destination, mode} on failure.
    """
    # googlemaps client is sync; run in thread to avoid blocking the event loop
    return await asyncio.to_thread(_distance_matrix_sync, origin, destination, mode)
