import os
from serpapi import GoogleSearch
from ..state import SearchNodeState


def search_node(state: SearchNodeState) -> dict:
    """
    Executes a single SerpAPI search query. This node gets called in parallel
    for each query the planner generated (via LangGraph's Send API in builder.py).

    Returns one result entry which gets appended to the parent state's
    search_results list via operator.add (defined in state.py).

    Note: we're only using Google organic results right now. SerpAPI also has
    google_maps and google_local engines which might give better results for
    commute-specific or amenity-specific queries - worth trying later.

    TODO: for listing searches specifically, consider adding a structured listing
    API (RentCast, Realty Mole via RapidAPI) for more reliable price/bedroom data.
    SerpAPI snippets work for a demo but can be inconsistent for structured fields.
    """
    query = state["query"]

    search = GoogleSearch({
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "num": 5,  # keeping this small to save API credits
    })

    raw = search.get_dict()
    organic = raw.get("organic_results", [])

    # strip down to just what we need - full SerpAPI responses are huge
    # and passing all that to the reducer LLM is wasteful
    results = []
    for r in organic[:5]:
        results.append({
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "snippet": r.get("snippet", ""),
            "source": r.get("source", ""),
        })

    return {
        "search_results": [{
            "query": query,
            "results": results,
        }]
    }
