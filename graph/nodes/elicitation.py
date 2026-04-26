import json
import re
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from ..llm import make_llm
from ..state import RentalState
from prompts.elicitation_prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT


# stop asking questions after this many turns and just run the search with what we have.
# 5 felt right from testing - enough to get commute destinations + key trade-offs
# without making the onboarding feel like an interrogation
MAX_QUESTIONS = 5

# haiku for extraction (cheap, fast, just needs to output clean JSON)
# sonnet for question generation (needs to be more conversational and nuanced)
extraction_llm = make_llm("elicitation_extract")
chat_llm = make_llm("elicitation_chat")


def _heuristic_pref_parse(latest: str) -> dict:
    text = latest.lower()
    parsed = {"new_preferences": {}, "ready_to_search": False}
    prefs = parsed["new_preferences"]

    for city in ("oakland", "berkeley", "san francisco", "chicago", "austin", "seattle"):
        if city in text:
            prefs["city"] = city.title() if city != "san francisco" else "San Francisco"
            break

    bed = re.search(r"(\d+)\s*(?:br|bed|bedroom)", text)
    if bed:
        prefs["bedrooms"] = int(bed.group(1))

    price = re.search(r"(?:under|max(?:imum)?|budget)\s*\$?\s*([0-9][0-9,]{2,})", text)
    if price:
        prefs["max_price"] = int(price.group(1).replace(",", ""))

    if "cat" in text or "dog" in text or "pet" in text:
        prefs["pet_friendly"] = True

    commute = re.search(r"commute to ([^.,;]+)", latest, re.I)
    if commute:
        prefs["commute_destinations"] = [commute.group(1).strip()]

    soft = []
    if "bart" in text:
        soft.append("close to BART")
    if soft:
        prefs["soft_constraints"] = soft

    parsed["ready_to_search"] = bool(prefs.get("city")) and bool(prefs.get("max_price") or prefs.get("bedrooms"))
    return parsed


def _extract_json(text) -> dict:
    """Pull JSON out of LLM response, handles markdown code blocks and content block lists."""
    if isinstance(text, list):
        text = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in text)
    # LLMs love wrapping output in ```json blocks even when you ask them not to
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())


def _has_enough(prefs: dict) -> bool:
    return bool(prefs.get("city")) and bool(prefs.get("max_price") or prefs.get("bedrooms"))


def _fallback_question(prefs: dict) -> tuple[str, list[str]]:
    """Return a context-aware question + options based on what's still missing."""
    if not prefs.get("city"):
        return (
            "Which city or neighborhood are you looking in?",
            ["Oakland", "Berkeley", "San Francisco", "Flexible"],
        )
    if not prefs.get("max_price"):
        return (
            "What's your monthly budget?",
            ["Under $1800", "$1800–$2200", "$2200–$2800", "Over $2800"],
        )
    if not prefs.get("bedrooms"):
        return (
            "How many bedrooms do you need?",
            ["Studio", "1 bedroom", "2 bedrooms", "3+ bedrooms"],
        )
    return (
        "Any must-haves I should know about?",
        ["Pet-friendly", "Parking", "In-unit laundry", "Near transit"],
    )


async def elicitation_node(state: RentalState) -> dict:
    messages = state.get("messages", [])
    preferences = state.get("preferences", {})
    questions_asked = state.get("questions_asked", 0)

    latest = messages[-1].content if messages and hasattr(messages[-1], "content") else ""

    # Always run the heuristic on the latest message and merge with accumulated preferences.
    # This handles well-formed initial messages (e.g. "1BR Oakland under $2500") without
    # any LLM call, and also correctly merges chip answers into existing state.
    heuristic = _heuristic_pref_parse(latest)
    merged_prefs = {**preferences, **heuristic.get("new_preferences", {})}

    # Fast path: if heuristic + accumulated prefs already have city + price/beds, go search.
    if _has_enough(merged_prefs) or questions_asked >= MAX_QUESTIONS:
        # Run a quick LLM extraction to catch anything the heuristic missed (best-effort).
        try:
            extraction_response = await asyncio.wait_for(extraction_llm.ainvoke(
                [
                    SystemMessage(content=EXTRACTION_PROMPT),
                    *messages[-4:],
                    HumanMessage(content=(
                        f"Preferences gathered so far: {json.dumps(merged_prefs)}\n\n"
                        "Extract any additional preference info and return JSON. "
                        "Set ready_to_search to true."
                    ))
                ],
                config={"run_name": "elicitation:extract", "tags": ["elicitation"]},
            ), timeout=8)
            extra = _extract_json(extraction_response.content)
            merged_prefs = {**merged_prefs, **extra.get("new_preferences", {})}
        except Exception:
            pass
        return {"preferences": merged_prefs, "ready_to_search": True}

    # Need more info — try LLM extraction to find anything the heuristic missed.
    try:
        extraction_response = await asyncio.wait_for(extraction_llm.ainvoke(
            [
                SystemMessage(content=EXTRACTION_PROMPT),
                *messages[-4:],
                HumanMessage(content=(
                    f"Preferences gathered so far: {json.dumps(merged_prefs)}\n\n"
                    "Extract any new preference info from the conversation and return JSON. "
                    "Set ready_to_search to true if we have at minimum a city and some "
                    "indication of price range or bedroom count."
                ))
            ],
            config={"run_name": "elicitation:extract", "tags": ["elicitation"]},
        ), timeout=12)
        parsed = _extract_json(extraction_response.content)
        merged_prefs = {**merged_prefs, **parsed.get("new_preferences", {})}
        if parsed.get("ready_to_search") or _has_enough(merged_prefs):
            return {"preferences": merged_prefs, "ready_to_search": True}
    except Exception:
        pass

    # Still not ready — generate a clarifying question.
    try:
        question_response = await asyncio.wait_for(chat_llm.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                *messages,
                HumanMessage(content=(
                    f"Preferences so far: {json.dumps(merged_prefs)}\n\n"
                    "Ask one focused follow-up question with 3-5 short answer options the user can tap. "
                    "Prioritize uncovering: commute destinations, budget, and trade-off flexibility. "
                    "Be warm and direct. Return ONLY valid JSON in this exact format:\n"
                    '{"question": "...", "options": ["option1", "option2", "option3"]}\n'
                    "Options should be short (2-5 words max)."
                ))
            ],
            config={"run_name": "elicitation:ask_question", "tags": ["elicitation"]},
        ), timeout=12)
        parsed_q = _extract_json(question_response.content)
        question_text = parsed_q["question"]
        options = parsed_q.get("options", [])
    except Exception:
        question_text, options = _fallback_question(merged_prefs)

    return {
        "preferences": merged_prefs,
        "questions_asked": questions_asked + 1,
        "ready_to_search": False,
        "messages": [AIMessage(content=question_text)],
        "elicitation_options": options,
    }
