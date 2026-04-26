import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from ..llm import make_llm
from ..state import RentalState
from prompts.planner_prompts import PLANNER_PROMPT
from ..nodes.supervisor import TRUSTED_DOMAINS


llm = make_llm(model="claude-sonnet-4-6", temperature=0.2)


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

    retry_context = ""
    if search_attempts > 0 and past_queries:
        retry_context = (
            f"\n\nThis is retry round {search_attempts}. The following queries were already run "
            f"- do not repeat them. Target different neighborhoods or features:\n"
            + "\n".join(f"- {q}" for q in past_queries)
        )

    response = await llm.ainvoke([
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=(
            f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
            f"Allowed site: operators (use only these): {', '.join(sorted(TRUSTED_DOMAINS))}\n\n"
            "Return JSON with key 'search_queries' as a list of strings. Exactly 3 queries."
            + retry_context
        ))
    ])

    try:
        parsed = _extract_json(response.content)
        queries = parsed.get("search_queries", [])
    except (json.JSONDecodeError, AttributeError, ValueError):
        queries = [f"apartment for rent site:{d}" for d in sorted(TRUSTED_DOMAINS)][:3]

    return {
        "search_queries": queries,
        # accumulate all queries ever run so subsequent planner calls can avoid them
        "all_search_queries": queries,
    }
