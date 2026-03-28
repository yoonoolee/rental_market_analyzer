from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from .state import RentalState
from .nodes.elicitation import elicitation_node
from .nodes.planner import planner_node
from .nodes.search import search_node
from .nodes.reducer import reducer_node


def route_after_elicitation(state: RentalState):
    """
    After each Q&A turn, decide whether to keep asking questions or proceed
    to the search pipeline.

    If not ready: return END so Chainlit sends the clarifying question back
    to the user and waits for their next message. The graph re-enters at START
    on the next message (session state is preserved in Chainlit's user_session).

    If ready: proceed to planner → parallel searches → reducer.
    """
    if state.get("ready_to_search"):
        return "planner"
    return END


def fan_out_to_searches(state: RentalState) -> list:
    """
    This is the Map step of map-reduce.

    Each query from the planner becomes an independent search_node invocation
    via LangGraph's Send API. They all run in parallel.

    The search results accumulate in state["search_results"] via operator.add
    (see state.py) - so all results are available when reducer runs.
    """
    queries = state.get("search_queries", [])
    return [
        Send("search_node", {"query": q, "preferences": state.get("preferences", {})})
        for q in queries
    ]


def build_graph():
    builder = StateGraph(RentalState)

    builder.add_node("elicitation", elicitation_node)
    builder.add_node("planner", planner_node)
    builder.add_node("search_node", search_node)
    builder.add_node("reducer", reducer_node)

    builder.add_edge(START, "elicitation")

    # after elicitation: either ask another question (END) or go to search pipeline
    builder.add_conditional_edges(
        "elicitation",
        route_after_elicitation,
        ["planner", END]
    )

    # planner fans out to N parallel search nodes (the Map step)
    builder.add_conditional_edges("planner", fan_out_to_searches, ["search_node"])

    # all search nodes feed into reducer (the Reduce step)
    builder.add_edge("search_node", "reducer")
    builder.add_edge("reducer", END)

    return builder.compile()
