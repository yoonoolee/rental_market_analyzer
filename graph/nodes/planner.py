import json
import re
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from ..llm import make_llm
from ..state import RentalState
from prompts.planner_prompts import PLANNER_PROMPT
from ..nodes.supervisor import TRUSTED_DOMAINS


llm = make_llm("planner")


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

    The planner's scope is narrower than before: it only generates queries to find
    listing URLs. Commute times, neighborhood context, and nearby amenities are
    handled per-listing by the ReAct listing agents.

    On retry rounds (search_attempts > 0), the planner receives all previously run
    queries via all_search_queries and must avoid repeating them. It tries different
    listing sites, adjacent neighborhoods, or adjusted price ranges to surface new URLs.
    """
    preferences = state.get("preferences", {})
    search_attempts = state.get("search_attempts", 0)
    past_queries = state.get("all_search_queries", [])
    city = preferences.get("city", "apartment")
    beds = preferences.get("bedrooms", 1)
    max_price = preferences.get("max_price", 2500)

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
                "Return JSON with key 'search_queries' as a list of strings. Exactly 8 queries."
                + retry_context
            ))
        ]), timeout=12)
        parsed = _extract_json(response.content)
        queries = parsed.get("search_queries", [])
    except Exception:
        queries = []

    fallback_queries = [
            f"{beds} bedroom apartment {city} under ${max_price} site:{d}"
            for d in sorted(TRUSTED_DOMAINS)
    ]
    # Keep model output first, then fill with deterministic fallback to guarantee 8.
    deduped = []
    for q in list(queries) + fallback_queries:
        if isinstance(q, str) and q.strip() and q not in deduped:
            deduped.append(q)
    queries = deduped[:8]

    return {
        "search_queries": queries,
        # accumulate all queries ever run so subsequent planner calls can avoid them
        "all_search_queries": queries,
    }
