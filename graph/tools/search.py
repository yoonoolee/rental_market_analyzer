import os
from serpapi import GoogleSearch
from langchain_core.tools import tool


@tool
async def search_web(query: str) -> list[dict]:
    """
    Run a Google web search and return the top results as a list of
    {title, snippet, link} dicts.

    Used by listing agents as a fallback when other tools can't find
    specific information - e.g. pet policy not stated on the listing page,
    building address is ambiguous, or floor/view details need verification.
    """
    search = GoogleSearch({
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "num": 3,
    })
    raw = search.get_dict()
    results = []
    for r in raw.get("organic_results", [])[:3]:
        results.append({
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "link": r.get("link", ""),
        })
    return results
