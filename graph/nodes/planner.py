import json
import os
import re
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from ..llm import make_llm
from ..state import RentalState
from prompts.planner_prompts import PLANNER_PROMPT
from ..nodes.supervisor import TRUSTED_DOMAINS


llm = make_llm("planner")
NUM_QUERIES = int(os.getenv("NUM_QUERIES", "8"))


def _extract_json(text) -> dict:
    if isinstance(text, list):
        text = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in text)
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())


async def planner_node(state: RentalState) -> dict:
    """
    Generates listing-discovery search queries for SerpAPI.

    On retry rounds (search_attempts > 0), receives all previously run queries
    and must avoid repeating them — targets different neighborhoods or features.
    """
    preferences = state.get("preferences", {})
    search_attempts = state.get("search_attempts", 0)
    past_queries = state.get("all_search_queries", [])

    retry_context = ""
    if search_attempts > 0 and past_queries:
        retry_context = (
            f"\n\nThis is retry round {search_attempts}. The following queries were already run "
            f"- do not repeat them. Target different neighborhoods or features:\n"
            + "\n".join(f"- {q}" for q in past_queries)
        )

    try:
        response = await asyncio.wait_for(llm.ainvoke([
            SystemMessage(content=PLANNER_PROMPT),
            HumanMessage(content=(
                f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
                f"Allowed site: operators (use only these): {', '.join(sorted(TRUSTED_DOMAINS))}\n\n"
                f"Return JSON with key 'search_queries' as a list of strings. Exactly {NUM_QUERIES} queries."
                + retry_context
            ))
        ]), timeout=12)
        parsed = _extract_json(response.content)
        queries = parsed.get("search_queries", [])
    except Exception as e:
        await adispatch_custom_event("error_log", {
            "node": "planner",
            "error": f"{type(e).__name__}: {str(e)[:300]}",
            "level": "error",
        })
        queries = []

    # Fallback: derive a basic query from hard_requirements or raw_query
    hard_reqs = preferences.get("hard_requirements", [])
    search_hint = " ".join(hard_reqs[:3]) if hard_reqs else preferences.get("raw_query", "apartment rental")
    fallback_queries = [
        f"{search_hint} site:{d}"
        for d in sorted(TRUSTED_DOMAINS)
    ]

    deduped = []
    for q in list(queries) + fallback_queries:
        if isinstance(q, str) and q.strip() and q not in deduped:
            deduped.append(q)
    queries = deduped[:NUM_QUERIES]

    return {
        "search_queries": queries,
        "all_search_queries": queries,
    }
