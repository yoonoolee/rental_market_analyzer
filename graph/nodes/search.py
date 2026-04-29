import os
import asyncio
import httpx
from serpapi import GoogleSearch
from langchain_core.callbacks.manager import adispatch_custom_event
from ..state import SearchNodeState


def _serpapi_search(query: str) -> list[dict]:
    search = GoogleSearch({
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "num": 10,
    })
    raw = search.get_dict()
    if "error" in raw:
        raise RuntimeError(raw["error"])
    results = []
    for r in raw.get("organic_results", [])[:10]:
        results.append({
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "snippet": r.get("snippet", ""),
            "source": r.get("source", ""),
        })
    return results


async def _serpex_search(query: str) -> list[dict]:
    key = os.getenv("SERPEX_API_KEY", "").strip()
    if not key:
        raise RuntimeError("SERPEX_API_KEY not set")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            "https://api.serpex.dev/api/search",
            params={"q": query, "engine": "google", "category": "web"},
            headers={"Authorization": f"Bearer {key}"},
        )
        r.raise_for_status()
        data = r.json()
    results = []
    for r in data.get("results", [])[:10]:
        results.append({
            "title": r.get("title", ""),
            "link": r.get("url", ""),
            "snippet": r.get("snippet", ""),
            "source": r.get("engine", ""),
        })
    return results


async def search_node(state: SearchNodeState) -> dict:
    """
    Executes a single search query. Tries SerpAPI first, falls back to Serpex
    if SerpAPI returns an error (e.g. credit limit exhausted).
    """
    query = state["query"]
    provider = "serpapi"

    try:
        results = await asyncio.to_thread(_serpapi_search, query)
    except Exception as e:
        serpapi_err = str(e)
        await adispatch_custom_event("error_log", {
            "node": "search",
            "error": f"SerpAPI failed ('{serpapi_err[:80]}'), falling back to Serpex",
            "level": "warn",
        })
        try:
            results = await _serpex_search(query)
            provider = "serpex"
        except Exception as e2:
            await adispatch_custom_event("error_log", {
                "node": "search",
                "error": f"Serpex also failed: {str(e2)[:200]}",
                "level": "error",
            })
            return {"search_results": [{"query": query, "results": [], "error": f"serpapi: {serpapi_err[:80]} | serpex: {str(e2)[:80]}"}]}

    links = [r["link"] for r in results if r.get("link")]
    await adispatch_custom_event("error_log", {
        "node": "search",
        "error": f"[{provider}] query '{query[:80]}' → {len(links)} results: {links[:5]}",
        "level": "warn",
    })

    return {"search_results": [{"query": query, "results": results}]}
