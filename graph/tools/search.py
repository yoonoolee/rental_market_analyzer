import os
import asyncio
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
    def _run_search() -> dict:
        search = GoogleSearch({
            "q": query,
            "api_key": os.getenv("SERPAPI_API_KEY"),
            "num": 3,
        })
        return search.get_dict()

    raw = await asyncio.to_thread(_run_search)
    results = []
    for r in raw.get("organic_results", [])[:3]:
        results.append({
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "link": r.get("link", ""),
        })
    return results
