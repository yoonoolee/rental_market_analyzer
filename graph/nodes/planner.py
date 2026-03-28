import json
import re
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import RentalState
from prompts.planner_prompts import PLANNER_PROMPT


llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.2)


def _extract_json(text: str) -> dict:
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())


async def planner_node(state: RentalState) -> dict:
    """
    This is the Map step. The LLM looks at the user's full preference state
    and generates a list of specific SerpAPI queries to run in parallel.

    The planner decides what to search for - listings, commute times, neighborhood
    context, nearby amenities, etc. This is what makes the system feel intelligent:
    instead of us hardcoding "always search for X", the LLM figures out what's
    relevant for this specific user.
    """
    preferences = state.get("preferences", {})

    response = await llm.ainvoke([
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=(
            f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
            "Generate specific SerpAPI search queries to find relevant listings and context. "
            "Return JSON with key 'search_queries' as a list of strings.\n\n"
            "Cover:\n"
            "- Apartment listings (target craigslist, zillow, apartments.com)\n"
            "- Commute times for each destination the user mentioned\n"
            "- Neighborhood signals they care about (safety, walkability, noise, etc.)\n"
            "- Specific amenities (gyms, grocery stores, etc.) if mentioned\n\n"
            "5-8 queries max. Be specific with locations and price ranges."
        ))
    ])

    try:
        parsed = _extract_json(response.content)
        queries = parsed.get("search_queries", [])
    except (json.JSONDecodeError, AttributeError, ValueError):
        # fallback if the LLM returns something unparseable
        # TODO: improve fallback - maybe retry with a stricter prompt
        city = preferences.get("city", "")
        bedrooms = preferences.get("bedrooms", 1)
        max_price = preferences.get("max_price", 2500)
        br_label = "studio" if bedrooms == 0 else f"{bedrooms} bedroom"
        queries = [
            f"{br_label} apartment under ${max_price} {city} site:craigslist.org",
            f"{br_label} apartment for rent {city} zillow {max_price}",
            f"neighborhoods in {city} safe walkable affordable 2024",
        ]

    return {"search_queries": queries}
