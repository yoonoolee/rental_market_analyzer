import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from ..llm import make_llm
from ..state import RentalState
from prompts.planner_prompts import PLANNER_PROMPT


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

    city = preferences.get("city", "")
    bedrooms = preferences.get("bedrooms")
    max_price = preferences.get("max_price")
    min_price = preferences.get("min_price")

    price_str = ""
    if min_price and max_price:
        price_str = f"${min_price}–${max_price}"
    elif max_price:
        price_str = f"under ${max_price}"
    elif min_price:
        price_str = f"over ${min_price}"

    br_str = ""
    if bedrooms is not None:
        br_str = "studio" if bedrooms == 0 else f"{bedrooms} bedroom"

    hard_requirements = f"City: {city}" + (f" | Bedrooms: {br_str}" if br_str else "") + (f" | Price: {price_str}" if price_str else "")

    response = await llm.ainvoke([
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=(
            f"Hard requirements (must appear in every query): {hard_requirements}\n\n"
            f"Full preferences (use soft constraints to vary queries):\n{json.dumps(preferences, indent=2)}\n\n"
            "Generate search queries where the hard requirements are locked in every query, "
            "but each query targets a different neighborhood or feature (e.g. pet-friendly, modern, near a landmark). "
            "Return JSON with key 'search_queries' as a list of strings. Up to 30 queries."
            + retry_context
        ))
    ])

    try:
        parsed = _extract_json(response.content)
        queries = parsed.get("search_queries", [])
    except (json.JSONDecodeError, AttributeError, ValueError):
        # fallback if the LLM returns something unparseable
        # TODO: retry with a stricter prompt before falling back
        city = preferences.get("city", "")
        bedrooms = preferences.get("bedrooms", 1)
        max_price = preferences.get("max_price", 2500)
        br_label = "studio" if bedrooms == 0 else f"{bedrooms} bedroom"
        queries = [
            f"{br_label} apartment for rent {city} under ${max_price} site:zillow.com",
            f"{br_label} apartment {city} under ${max_price} site:apartments.com",
            f"{br_label} apartment {city} ${max_price} site:trulia.com",
        ]

    return {
        "search_queries": queries,
        # accumulate all queries ever run so subsequent planner calls can avoid them
        "all_search_queries": queries,
    }
