import os
import math
import asyncio
import googlemaps
from langchain_core.tools import tool


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
    return _client


# Natural-language to Google Places type mapping. Listing agents often pass
# user phrasing like "grocery store" or "coffee shop"; Places API expects
# canonical type strings. Anything not in the map is passed through unchanged.
_PLACE_TYPE_MAP = {
    "grocery store": "supermarket",
    "grocery": "supermarket",
    "supermarket": "supermarket",
    "coffee shop": "cafe",
    "coffee": "cafe",
    "cafe": "cafe",
    "bar": "bar",
    "bars": "bar",
    "gym": "gym",
    "gyms": "gym",
    "park": "park",
    "parks": "park",
    "restaurant": "restaurant",
    "restaurants": "restaurant",
    "pharmacy": "pharmacy",
    "school": "school",
}


def _normalize_place_type(place_type: str) -> str:
    return _PLACE_TYPE_MAP.get(place_type.strip().lower(), place_type.strip().lower())


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in meters between two lat/lng points."""
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _places_sync(address: str, place_type: str, radius: int) -> dict:
    client = _get_client()
    normalized_type = _normalize_place_type(place_type)
    try:
        geo = client.geocode(address)
        if not geo:
            return {
                "error": f"Could not geocode address: {address}",
                "query_type": place_type,
                "address": address,
            }

        loc = geo[0]["geometry"]["location"]
        origin_lat, origin_lng = loc["lat"], loc["lng"]

        places = client.places_nearby(
            location=(origin_lat, origin_lng),
            radius=radius,
            type=normalized_type,
        )

        results = []
        for place in places.get("results", [])[:5]:
            ploc = place["geometry"]["location"]
            dist = _haversine_distance(origin_lat, origin_lng, ploc["lat"], ploc["lng"])
            results.append({
                "name": place["name"],
                "address": place.get("vicinity", ""),
                "rating": place.get("rating"),
                "total_ratings": place.get("user_ratings_total", 0),
                "distance_meters": round(dist),
            })

        return {
            "query_type": place_type,
            "resolved_type": normalized_type,
            "address": address,
            "radius_meters": radius,
            "results_count": len(places.get("results", [])),
            "results": results,
        }
    except Exception as e:
        return {"error": str(e), "query_type": place_type, "address": address}


@tool
async def find_nearby_places(address: str, place_type: str, radius: int = 1000) -> dict:
    """
    Find places of a given type near an address using Google Places API (Nearby Search).

    Geocodes the address first, then searches within `radius` meters (default 1000m).
    `place_type` accepts natural-language terms like 'grocery store', 'coffee shop',
    'bar', 'gym', 'park', 'restaurant' — mapped internally to Google Places types.

    Returns {query_type, address, radius_meters, results_count, results: [...]}
    where each result has {name, address, rating, total_ratings, distance_meters}.
    Returns {error, ...} on failure.
    """
    return await asyncio.to_thread(_places_sync, address, place_type, radius)
