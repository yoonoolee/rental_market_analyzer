import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import RentalState
from prompts.analyzer_prompts import ANALYZER_PROMPT


llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.3)


async def analyzer_node(state: RentalState) -> dict:
    """
    Reviews both qualifying and disqualified listings to surface cross-cutting
    patterns: budget mismatches, common disqualification reasons, commute
    realities, and soft constraint availability.

    Runs after the reducer so it doesn't block recommendation generation.
    Its output is appended to the final response the user sees.
    """
    preferences = state.get("preferences", {})
    listing_profiles = state.get("listing_profiles", [])

    good_profiles = [p for p in listing_profiles if not p.get("disqualified")]
    disqualified_profiles = [p for p in listing_profiles if p.get("disqualified")]

    # not enough data to analyze - skip
    if len(listing_profiles) < 2:
        return {"analysis_insights": ""}

    response = await llm.ainvoke([
        SystemMessage(content=ANALYZER_PROMPT),
        HumanMessage(content=(
            f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
            f"Qualifying listings ({len(good_profiles)}):\n"
            f"{json.dumps(good_profiles, indent=2)}\n\n"
            f"Disqualified listings ({len(disqualified_profiles)}):\n"
            f"{json.dumps(disqualified_profiles, indent=2)}"
        ))
    ])

    return {"analysis_insights": response.content}
