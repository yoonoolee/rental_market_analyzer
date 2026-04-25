import json
import re
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from ..llm import make_llm
from ..state import RentalState
from ..tools.commute import get_commute_time
from ..tools.places import find_nearby_places
from prompts.intent_router_prompts import (
    CLASSIFIER_PROMPT,
    CONVERSATIONAL_PROMPT,
    OFF_TOPIC_RESPONSE,
)


classifier_llm = make_llm(model="claude-haiku-4-5-20251001", temperature=0.0)
chat_llm = make_llm(model="claude-sonnet-4-6", temperature=0.4)


def _extract_json(text: str) -> dict:
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())


def _format_commute(result: dict) -> str:
    if "error" in result:
        return f"Couldn't get a commute time — {result['error']}."
    return (
        f"From {result['origin']} to {result['destination']} by {result['mode']}: "
        f"{result['duration_text']} ({result['distance_text']})."
    )


def _format_places(result: dict) -> str:
    if "error" in result:
        return f"Couldn't find nearby places — {result['error']}."
    places = result.get("results", [])
    if not places:
        return f"No {result['query_type']} found within {result['radius_meters']}m of {result['address']}."
    lines = [f"Nearby {result['query_type']} around {result['address']}:"]
    for p in places[:5]:
        rating = f"{p['rating']}★ ({p['total_ratings']})" if p.get("rating") else "no rating"
        lines.append(f"- {p['name']} — {p['distance_meters']}m, {rating}")
    return "\n".join(lines)


async def intent_router_node(state: RentalState) -> dict:
    """
    First node on every message. Classifies the user's message into one of four
    intents and handles non-search intents directly. Only `needs_search` falls
    through to the elicitation pipeline.
    """
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "needs_search"}

    latest = messages[-1].content if hasattr(messages[-1], "content") else ""
    preferences = state.get("preferences", {})
    has_prior_results = bool(state.get("final_response"))

    context_block = (
        f"Current preferences gathered: {json.dumps(preferences)}\n"
        f"User has prior ranked results in this session: {has_prior_results}\n\n"
        f"User message: {latest}"
    )

    response = await classifier_llm.ainvoke(
        [
            SystemMessage(content=CLASSIFIER_PROMPT),
            HumanMessage(content=context_block),
        ],
        config={"run_name": "intent_router:classify", "tags": ["intent_router"]},
    )

    try:
        parsed = _extract_json(response.content)
    except (json.JSONDecodeError, ValueError):
        parsed = {"intent": "needs_search"}

    intent = parsed.get("intent", "needs_search")

    if intent == "off_topic":
        return {
            "intent": intent,
            "messages": [AIMessage(content=OFF_TOPIC_RESPONSE)],
        }

    if intent == "conversational":
        answer = await chat_llm.ainvoke(
            [SystemMessage(content=CONVERSATIONAL_PROMPT), *messages],
            config={"run_name": "intent_router:conversational", "tags": ["intent_router"]},
        )
        return {
            "intent": intent,
            "messages": [AIMessage(content=answer.content)],
        }

    if intent == "tool_call":
        tool_name = parsed.get("tool")
        params = parsed.get("params", {}) or {}
        try:
            if tool_name == "commute":
                result = await get_commute_time.ainvoke({
                    "origin": params.get("origin", ""),
                    "destination": params.get("destination", ""),
                    "mode": params.get("mode", "transit"),
                })
                reply = _format_commute(result)
            elif tool_name == "places":
                result = await find_nearby_places.ainvoke({
                    "address": params.get("address", ""),
                    "place_type": params.get("place_type", ""),
                })
                reply = _format_places(result)
            else:
                reply = "I couldn't figure out which tool to run. Could you rephrase?"
        except Exception as e:
            reply = f"Tool call failed: {e}"

        return {
            "intent": intent,
            "messages": [AIMessage(content=reply)],
        }

    # needs_search — reset search state for a fresh pipeline run if there are prior results.
    # For the accumulated list fields (operator.add-style reducers), we pass None via the
    # append_or_reset reducer to clear them; plain fields can be assigned directly.
    if has_prior_results:
        return {
            "intent": intent,
            "ready_to_search": False,
            "search_queries": [],
            "pending_urls": [],
            "search_attempts": 0,
            "final_response": "",
            "analysis_insights": "",
            # None triggers append_or_reset to clear:
            "all_search_queries": None,
            "search_results": None,
            "searched_urls": None,
            "listing_profiles": None,
        }

    return {"intent": intent}


def route_after_intent_router(state: RentalState) -> str:
    """Route based on classified intent. Only needs_search proceeds to elicitation."""
    from langgraph.graph import END
    intent = state.get("intent", "needs_search")
    if intent == "needs_search":
        return "elicitation"
    return END
