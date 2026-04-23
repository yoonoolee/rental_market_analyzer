import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from ..state import RentalState
from ..nodes.supervisor import MIN_GOOD_RESULTS, MAX_SEARCH_ATTEMPTS
from prompts.reducer_prompts import REDUCER_PROMPT


llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.4)


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
        SystemMessage(content=REDUCER_PROMPT),
        HumanMessage(content=(
            f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
            f"Qualifying listings ({len(good_profiles)}):\n"
            f"{json.dumps(good_profiles, indent=2)}\n\n"
            f"Disqualified listings ({len(disqualified_profiles)}):\n"
            f"{json.dumps(disqualified_profiles, indent=2)}"
            + context_note
        ))
    ])

    return {
        "final_response": response.content,
    }
