import os
import math
import asyncio
import httpx
import googlemaps
from langchain_core.tools import tool


_gmaps_client = None


def _get_gmaps_client():
    global _gmaps_client
    if _gmaps_client is None:
        _gmaps_client = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
    return _gmaps_client


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
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    normalized_type = _normalize_place_type(place_type)
    try:
        geo = _get_gmaps_client().geocode(address)
        if not geo:
            return {"error": f"Could not geocode address: {address}", "query_type": place_type, "address": address}

        loc = geo[0]["geometry"]["location"]
        origin_lat, origin_lng = loc["lat"], loc["lng"]

        resp = httpx.post(
            "https://places.googleapis.com/v1/places:searchNearby",
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.location",
            },
            json={
                "includedTypes": [normalized_type],
                "maxResultCount": 5,
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": origin_lat, "longitude": origin_lng},
                        "radius": float(radius),
                    }
                },
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for place in data.get("places", []):
            ploc = place.get("location", {})
            dist = _haversine_distance(origin_lat, origin_lng, ploc.get("latitude", 0), ploc.get("longitude", 0))
            results.append({
                "name": place.get("displayName", {}).get("text", ""),
                "address": place.get("formattedAddress", ""),
                "rating": place.get("rating"),
                "total_ratings": place.get("userRatingCount", 0),
                "distance_meters": round(dist),
            })

        return {
            "query_type": place_type,
            "resolved_type": normalized_type,
            "address": address,
            "radius_meters": radius,
            "results_count": len(results),
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
