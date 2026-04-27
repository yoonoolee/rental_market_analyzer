import json
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from ..llm import make_llm
from ..state import RentalState
from prompts.analyzer_prompts import ANALYZER_PROMPT


llm = make_llm("analyzer")


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

    try:
        response = await asyncio.wait_for(llm.ainvoke([
            SystemMessage(content=ANALYZER_PROMPT),
            HumanMessage(content=(
                f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
                f"Qualifying listings ({len(good_profiles)}):\n"
                f"{json.dumps(good_profiles, indent=2)}\n\n"
                f"Disqualified listings ({len(disqualified_profiles)}):\n"
                f"{json.dumps(disqualified_profiles, indent=2)}"
            ))
        ]), timeout=20)
    except Exception as e:
        await adispatch_custom_event("error_log", {
            "node": "analyzer",
            "error": f"{type(e).__name__}: {str(e)[:300]}",
            "level": "error",
        })
        return {"analysis_insights": ""}

    insights = response.content if isinstance(response.content, str) else ""
    return {
        "analysis_insights": insights,
        "messages": [AIMessage(content=insights)] if insights else [],
    }
