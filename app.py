import os
import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from graph.builder import build_graph
from graph.state import RentalState
from dotenv import load_dotenv

load_dotenv()

# LangSmith tracing is enabled automatically when LANGCHAIN_TRACING_V2=true.
# The env vars (LANGCHAIN_API_KEY, LANGCHAIN_PROJECT) are read by LangChain at
# import time, so load_dotenv() must run before any langchain imports.
TRACING_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

# build the graph once at startup - no need to rebuild per message
graph = build_graph()

WELCOME_MESSAGE = """Hey! I'm here to help you find your next apartment.

Tell me what you're looking for - city, budget, vibe, anything. The more context
you share (especially commute destinations and what you're willing to trade off),
the more useful I can be.

What are you looking for?"""


@cl.on_chat_start
async def start():
    # fresh state for each new chat session
    initial_state: RentalState = {
        "messages": [],
        "preferences": {},
        "search_queries": [],
        "all_search_queries": [],
        "search_results": [],
        "pending_urls": [],
        "searched_urls": [],
        "listing_profiles": [],
        "search_attempts": 0,
        "questions_asked": 0,
        "ready_to_search": False,
        "final_response": "",
        "analysis_insights": "",
    }
    cl.user_session.set("state", initial_state)
    await cl.Message(content=WELCOME_MESSAGE).send()


@cl.on_message
async def on_message(message: cl.Message):
    state = cl.user_session.get("state")

    # append the new user message before invoking the graph
    state["messages"].append(HumanMessage(content=message.content))

    # if we already returned results in a previous turn, reset the search state
    # so a follow-up message triggers a fresh search with updated preferences.
    # TODO: handle follow-ups more gracefully - right now re-running the full pipeline
    # is wasteful if the user just wants to ask about a specific listing from the results.
    # could add a "clarification" branch that skips elicitation if prefs are already set.
    if state.get("final_response"):
        state["ready_to_search"] = False
        state["search_queries"] = []
        state["all_search_queries"] = []
        state["search_results"] = []
        state["pending_urls"] = []
        state["searched_urls"] = []
        state["listing_profiles"] = []
        state["search_attempts"] = 0
        state["final_response"] = ""
        state["analysis_insights"] = ""

    # show a thinking indicator while the graph runs
    async with cl.Step(name="searching...") as step:
        result = await graph.ainvoke(
            state,
            config={
                "run_name": "rental-market-analyzer",
                "metadata": {
                    "session_id": cl.user_session.get("id"),
                    "questions_asked": state.get("questions_asked", 0),
                    "ready_to_search": state.get("ready_to_search", False),
                },
            },
        )
        step.output = "done"

    # persist updated state for the next turn
    cl.user_session.set("state", result)

    # final_response means the full pipeline ran and we have ranked recommendations.
    # otherwise it's a clarifying question from the elicitation node.
    if result.get("final_response"):
        response = result["final_response"]
        if result.get("analysis_insights"):
            response += "\n\n---\n\n### Market Insights\n\n" + result["analysis_insights"]
        await cl.Message(content=response).send()
    else:
        ai_messages = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
        if ai_messages:
            await cl.Message(content=ai_messages[-1].content).send()
