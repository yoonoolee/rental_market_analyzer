from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from .state import RentalState
from .nodes.intent_router import intent_router_node, route_after_intent_router
from .nodes.elicitation import elicitation_node
from .nodes.planner import planner_node
from .nodes.search import search_node
from .nodes.reducer import reducer_node
from .nodes.analyzer import analyzer_node
from .nodes.listing_agent import listing_agent_node
from .nodes.supervisor import supervisor_node, results_check_node, route_after_results_check


def route_after_elicitation(state: RentalState):
    """
    After each Q&A turn, decide whether to keep asking questions or proceed
    to the search pipeline.

    If not ready: return END so Chainlit sends the clarifying question back
    to the user and waits for their next message. The graph re-enters at START
    on the next message (session state is preserved in Chainlit's user_session).

    If ready: proceed to planner → parallel searches → supervisor → listing agents → reducer.
    """
    if state.get("ready_to_search"):
        return "planner"
    return END


def fan_out_to_searches(state: RentalState) -> list:
    """
    Map step: each query from the planner becomes an independent search_node
    invocation via LangGraph's Send API. They all run in parallel.

    Results accumulate in state["search_results"] via operator.add (see state.py)
    before supervisor runs.
    """
    queries = state.get("search_queries", [])
    return [
        Send("search_node", {"query": q, "preferences": state.get("preferences", {})})
        for q in queries
    ]


def fan_out_to_listing_agents(state: RentalState) -> list:
    """
    Map step: each URL queued by the supervisor becomes an independent listing_agent
    invocation via LangGraph's Send API. They all run in parallel.

    Each agent researches one listing end-to-end (scrape, commute, places, etc.)
    and returns a structured profile. Profiles accumulate in state["listing_profiles"]
    via operator.add before results_check runs.

    pending_urls is set by supervisor_node each round - it only contains URLs
    not yet processed, so retries don't re-research the same listings.
    """
    urls = state.get("pending_urls", [])
    return [
        Send("listing_agent", {"url": url, "preferences": state.get("preferences", {})})
        for url in urls
    ]


def build_graph(checkpointer=None):
    """
    Build and compile the rental-search graph.

    checkpointer: optional LangGraph checkpointer (e.g. SqliteSaver) for persisting
    state across sessions. When provided, the graph reloads prior state per-thread_id
    on every invocation, so Chainlit page refreshes preserve conversation context.
    """
    builder = StateGraph(RentalState)

    builder.add_node("intent_router", intent_router_node)
    builder.add_node("elicitation", elicitation_node)
    builder.add_node("planner", planner_node)
    builder.add_node("search_node", search_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("listing_agent", listing_agent_node)
    builder.add_node("results_check", results_check_node)
    builder.add_node("reducer", reducer_node)
    builder.add_node("analyzer", analyzer_node)

    builder.add_edge(START, "intent_router")

    # intent_router → elicitation (needs_search) or END (other intents)
    builder.add_conditional_edges(
        "intent_router",
        route_after_intent_router,
        ["elicitation", END]
    )

    # after elicitation: ask another question (END) or kick off search pipeline
    builder.add_conditional_edges(
        "elicitation",
        route_after_elicitation,
        ["planner", END]
    )

    # planner fans out to N parallel search nodes (listing URL discovery)
    builder.add_conditional_edges("planner", fan_out_to_searches, ["search_node"])

    # all search nodes feed into supervisor (which extracts and queues new URLs)
    builder.add_edge("search_node", "supervisor")

    # supervisor fans out to N parallel listing agents (one per new URL)
    builder.add_conditional_edges("supervisor", fan_out_to_listing_agents, ["listing_agent"])

    # all listing agents feed into results_check
    builder.add_edge("listing_agent", "results_check")

    # results_check routes: enough good results → reducer, otherwise retry → planner
    builder.add_conditional_edges(
        "results_check",
        route_after_results_check,
        ["reducer", "planner"]
    )

    builder.add_edge("reducer", "analyzer")
    builder.add_edge("analyzer", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()
