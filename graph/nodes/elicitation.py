import json
import re
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
extraction_llm = make_llm(model="claude-haiku-4-5-20251001", temperature=0.1)
chat_llm = make_llm(model="claude-sonnet-4-6", temperature=0.5)


def _extract_json(text: str) -> dict:
    """Pull JSON out of LLM response, handles markdown code blocks."""
    # LLMs love wrapping output in ```json blocks even when you ask them not to
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())


async def elicitation_node(state: RentalState) -> dict:
    messages = state.get("messages", [])
    preferences = state.get("preferences", {})
    questions_asked = state.get("questions_asked", 0)

    # first, extract any structured preference info from the latest message.
    # we only send the last 4 messages to keep token count reasonable -
    # the preferences dict already captures everything important from earlier turns
    extraction_response = await extraction_llm.ainvoke(
        [
            SystemMessage(content=EXTRACTION_PROMPT),
            *messages[-4:],
            HumanMessage(content=(
                f"Preferences gathered so far: {json.dumps(preferences)}\n\n"
                "Extract any new preference info from the conversation and return JSON. "
                "Set ready_to_search to true if we have at minimum a city and some "
                "indication of price range or bedroom count."
            ))
        ],
        config={"run_name": "elicitation:extract", "tags": ["elicitation"]},
    )

    try:
        parsed = _extract_json(extraction_response.content)
    except (json.JSONDecodeError, AttributeError, ValueError):
        # if JSON parsing fails just move on with existing preferences
        # TODO: add a retry here with a stricter prompt before giving up
        parsed = {}

    updated_prefs = {**preferences, **parsed.get("new_preferences", {})}
    is_ready = parsed.get("ready_to_search", False) or questions_asked >= MAX_QUESTIONS

    if is_ready:
        return {
            "preferences": updated_prefs,
            "ready_to_search": True,
        }

    # generate the next clarifying question with selectable options.
    # structured output: {question, options[]} so the UI can render chips.
    question_response = await chat_llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            *messages,
            HumanMessage(content=(
                f"Preferences so far: {json.dumps(updated_prefs)}\n\n"
                "Ask one focused follow-up question with 3-5 short answer options the user can tap. "
                "Prioritize uncovering: commute destinations, budget, and trade-off flexibility. "
                "Be warm and direct. Return ONLY valid JSON in this exact format:\n"
                '{"question": "...", "options": ["option1", "option2", "option3"]}\n'
                "Options should be short (2-5 words max)."
            ))
        ],
        config={"run_name": "elicitation:ask_question", "tags": ["elicitation"]},
    )

    try:
        parsed_q = _extract_json(question_response.content)
        question_text = parsed_q["question"]
        options = parsed_q.get("options", [])
    except (json.JSONDecodeError, KeyError, ValueError):
        question_text = question_response.content
        options = []

    return {
        "preferences": updated_prefs,
        "questions_asked": questions_asked + 1,
        "ready_to_search": False,
        "messages": [AIMessage(content=question_text)],
        "elicitation_options": options,
    }
