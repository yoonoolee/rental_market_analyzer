import json
import re
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from ..state import RentalState
from ...prompts.elicitation_prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT


# stop asking questions after this many turns and just run the search with what we have.
# 5 felt right from testing - enough to get commute destinations + key trade-offs
# without making the onboarding feel like an interrogation
MAX_QUESTIONS = 5

# haiku for extraction (cheap, fast, just needs to output clean JSON)
# sonnet for question generation (needs to be more conversational and nuanced)
extraction_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.1)
chat_llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.5)


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
    extraction_response = await extraction_llm.ainvoke([
        SystemMessage(content=EXTRACTION_PROMPT),
        *messages[-4:],
        HumanMessage(content=(
            f"Preferences gathered so far: {json.dumps(preferences)}\n\n"
            "Extract any new preference info from the conversation and return JSON. "
            "Set ready_to_search to true if we have at minimum a city and some "
            "indication of price range or bedroom count."
        ))
    ])

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

    # generate the next clarifying question.
    # we ask the LLM to prioritize commute destinations and trade-off flexibility
    # since those are the hardest things to infer and most impactful for ranking
    question_response = await chat_llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        *messages,
        HumanMessage(content=(
            f"Preferences so far: {json.dumps(updated_prefs)}\n\n"
            "Ask one focused follow-up question. Prioritize uncovering: commute "
            "destinations, and what the user is willing to trade off under what conditions. "
            "Be warm and direct - like a friend who knows the rental market, not a chatbot. "
            "No bullet points or lists."
        ))
    ])

    return {
        "preferences": updated_prefs,
        "questions_asked": questions_asked + 1,
        "ready_to_search": False,
        "messages": [AIMessage(content=question_response.content)],
    }
