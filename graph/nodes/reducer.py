import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from ..llm import make_llm
from ..state import RentalState
from ..nodes.supervisor import MIN_GOOD_RESULTS, MAX_SEARCH_ATTEMPTS, MAX_SHOWN
from prompts.reducer_prompts import REDUCER_PROMPT


llm = make_llm(model="claude-sonnet-4-6", temperature=0.4)


async def reducer_node(state: RentalState) -> dict:
    """
    Synthesizes structured listing profiles into ranked recommendations.

    The key difference from the old approach: the reducer now receives real data
    gathered by listing agents (actual prices, commute times from the Maps API,
    nearby places from Places API, pet policy from the listing page). It reasons
    from facts, not snippets.

    Trade-off rules are applied against real numbers - "willing to pay $200 more
    if commute < 15 min" is evaluated against the actual commute_times in each profile.
    """
    preferences = state.get("preferences", {})
    listing_profiles = state.get("listing_profiles", [])
    search_attempts = state.get("search_attempts", 0)

    good_profiles = [p for p in listing_profiles if not p.get("disqualified")]
    disqualified_profiles = [p for p in listing_profiles if p.get("disqualified")]

    # surface a note if we ran out of retries without hitting the target result count
    context_note = ""
    if search_attempts >= MAX_SEARCH_ATTEMPTS and len(good_profiles) < MIN_GOOD_RESULTS:
        context_note = (
            f"\n\nNote: searched {search_attempts} rounds and found only {len(good_profiles)} "
            f"listings matching the user's requirements (target was {MIN_GOOD_RESULTS}). "
            f"The market may be thin for these criteria. Mention this honestly in your response."
        )

    response = await llm.ainvoke([
        SystemMessage(content=REDUCER_PROMPT.replace("MAX_SHOWN", str(MAX_SHOWN))),
        HumanMessage(content=(
            f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
            f"Qualifying listings ({len(good_profiles)}):\n"
            f"{json.dumps(good_profiles, indent=2)}\n\n"
            f"Disqualified listings ({len(disqualified_profiles)}):\n"
            f"{json.dumps(disqualified_profiles, indent=2)}"
            + context_note
        ))
    ])

    content = response.content
    if isinstance(content, list):
        content = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)

    ranked_urls = []
    final_response = content
    try:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        parsed = json.loads(match.group(1).strip() if match else content.strip())
        ranked_urls = parsed.get("ranked_urls", [])
        final_response = parsed.get("response", content)
    except (json.JSONDecodeError, AttributeError, ValueError):
        pass

    profile_by_url = {p.get("url"): p for p in good_profiles}
    ranked_listings = [profile_by_url[u] for u in ranked_urls if u in profile_by_url]
    if not ranked_listings:
        ranked_listings = good_profiles[:MAX_SHOWN]

    return {
        "final_response": final_response,
        "ranked_listings": ranked_listings,
    }
