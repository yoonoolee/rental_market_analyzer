import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from graph.builder import build_graph
from graph.state import RentalState
from dotenv import load_dotenv

load_dotenv()

# build the graph once at startup - no need to rebuild per message
graph = build_graph()

WELCOME_MESSAGE = """Hey! I'm here to help you find your next apartment.

Tell me what you're looking for — city, budget, vibe, anything. The more context
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
        "search_results": [],
        "questions_asked": 0,
        "ready_to_search": False,
        "final_response": "",
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
    # TODO: handle follow-ups more gracefully - right now re-running the full search
    # is wasteful if the user is just asking about a specific listing from the results.
    # could add a "clarification" branch that skips elicitation if prefs are already set.
    if state.get("final_response"):
        state["ready_to_search"] = False
        state["search_queries"] = []
        state["search_results"] = []
        state["final_response"] = ""

    # show a thinking indicator while the graph runs
    async with cl.Step(name="searching...") as step:
        result = await graph.ainvoke(state)
        step.output = "done"

    # persist updated state for the next turn
    cl.user_session.set("state", result)

    # figure out what to send back to the user.
    # final_response means the full search pipeline ran and we have results.
    # otherwise it's a clarifying question from the elicitation node.
    if result.get("final_response"):
        await cl.Message(content=result["final_response"]).send()
    else:
        ai_messages = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
        if ai_messages:
            await cl.Message(content=ai_messages[-1].content).send()
