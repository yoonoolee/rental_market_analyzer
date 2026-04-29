import os
import asyncio
import httpx
from serpapi import GoogleSearch
from langchain_core.tools import tool


def _serpapi_search(query: str, num: int = 3) -> list[dict]:
    search = GoogleSearch({
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "num": num,
    })
    raw = search.get_dict()
    if "error" in raw:
        raise RuntimeError(raw["error"])
    results = []
    for r in raw.get("organic_results", [])[:num]:
        results.append({
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "link": r.get("link", ""),
        })
    return results


async def _serpex_search(query: str, num: int = 3) -> list[dict]:
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
    for r in data.get("results", [])[:num]:
        results.append({
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "link": r.get("url", ""),
        })
    return results


@tool
async def search_web(query: str) -> list[dict]:
    """
    Run a Google web search and return the top results as a list of
    {title, snippet, link} dicts. Tries SerpAPI first, falls back to Serpex
    if SerpAPI credits are exhausted.
    """
    try:
        return await asyncio.to_thread(_serpapi_search, query, 3)
    except Exception:
        try:
            return await _serpex_search(query, 3)
        except Exception as e:
            return [{"title": "search failed", "snippet": str(e)[:100], "link": ""}]
