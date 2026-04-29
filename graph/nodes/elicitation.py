import json
import re
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from ..llm import make_llm
from ..state import RentalState
from prompts.elicitation_prompts import ELICITATION_PROMPT


MAX_ITERATIONS = 1
MAX_QUESTIONS_PER_BATCH = 3

llm = make_llm("elicitation_chat")


def _extract_json(text) -> dict:
    if isinstance(text, list):
        text = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in text)
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())


async def elicitation_node(state: RentalState) -> dict:
    messages = state.get("messages", [])
    preferences = state.get("preferences", {})
    elicitation_iteration = state.get("elicitation_iteration", 0)

    if elicitation_iteration >= MAX_ITERATIONS:
        return {"preferences": preferences, "ready_to_search": True}

    # Capture the raw query from the first user message
    raw_query = preferences.get("raw_query", "")
    if not raw_query and messages:
        for m in messages:
            if hasattr(m, "type") and m.type == "human":
                raw_query = m.content[:500]
                break

    try:
        response = await asyncio.wait_for(llm.ainvoke([
            SystemMessage(content=ELICITATION_PROMPT),
            *messages,
            HumanMessage(content=(
                f"Preferences extracted so far: {json.dumps(preferences)}\n"
                f"Question round {elicitation_iteration + 1} of {MAX_ITERATIONS}."
            ))
        ]), timeout=15)
        parsed = _extract_json(response.content)
    except Exception as e:
        await adispatch_custom_event("error_log", {
            "node": "elicitation",
            "error": f"{type(e).__name__}: {str(e)[:300]}",
            "level": "error",
        })
        return {"preferences": preferences, "ready_to_search": True}

    new_prefs = {
        "hard_requirements": parsed.get("hard_requirements") or preferences.get("hard_requirements", []),
        "soft_constraints": parsed.get("soft_constraints") or preferences.get("soft_constraints", []),
        "trade_off_rules": parsed.get("trade_off_rules") or preferences.get("trade_off_rules", []),
        "commute_destinations": parsed.get("commute_destinations") or preferences.get("commute_destinations", []),
        "raw_query": raw_query,
    }

    if parsed.get("ready_to_search"):
        return {"preferences": new_prefs, "ready_to_search": True}

    questions = [
        q for q in parsed.get("questions", [])
        if isinstance(q, dict) and q.get("question")
    ][:MAX_QUESTIONS_PER_BATCH]

    if not questions:
        return {"preferences": new_prefs, "ready_to_search": True}

    return {
        "preferences": new_prefs,
        "ready_to_search": False,
        "elicitation_iteration": elicitation_iteration + 1,
        "elicitation_batch": questions,
    }
