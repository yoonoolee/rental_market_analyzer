from typing import TypedDict, Annotated
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


def append_or_reset(existing: list, new: list | None) -> list:
    """
    Custom reducer for list-typed state fields that need both accumulate and reset semantics.
    - Passing a list: appends to existing (like operator.add)
    - Passing None: resets to [] (used by intent_router when starting a new search session
      after the user already has prior ranked results)
    """
    if new is None:
        return []
    return (existing or []) + list(new)


class PreferenceState(TypedDict, total=False):
    hard_requirements: list[str]     # non-negotiables e.g. ["Berkeley or East Bay", "under $2000", "1-2 bedrooms"]
    soft_constraints: list[str]      # unconditional nice-to-haves e.g. ["walkable", "modern finishes", "has a dog"]
    trade_off_rules: list[str]       # conditional preferences e.g. ["1 bed $1000 if gym nearby, 2 bed $2000 if grocery"]
    commute_destinations: list[str]  # specific places for commute tool calls e.g. ["South Hall UC Berkeley"]
    raw_query: str                   # original user message


# SearchNodeState is the input to each individual search node.
# We use a separate TypedDict here because LangGraph's Send API passes this
# dict directly to the search node instead of the full RentalState.
class SearchNodeState(TypedDict):
    query: str
    preferences: PreferenceState


# ListingAgentState is the input to each ReAct listing agent.
# Each agent receives one URL and the full user preference profile.
# The agent then decides which tools to call based on what the user cares about -
# someone with a pet triggers a pet policy check first; someone who didn't mention
# grocery stores won't trigger a places lookup for them.
class ListingAgentState(TypedDict):
    url: str
    preferences: PreferenceState


class RentalState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    preferences: PreferenceState

    # current round's queries - replaced each time planner runs
    search_queries: list[str]

    # all queries ever run across all rounds - used by planner on retry to avoid
    # generating duplicate queries. Pass None to reset for a new search session.
    all_search_queries: Annotated[list[str], append_or_reset]

    # raw URL results from search nodes. Parallel search nodes append here;
    # intent_router resets by passing None when starting a new search.
    search_results: Annotated[list[dict], append_or_reset]

    # URLs queued for listing agent processing this round (replaced each supervisor run)
    pending_urls: list[str]

    # all URLs ever sent to a listing agent - used by supervisor to avoid
    # re-processing the same listing on retry rounds. Reset on new search.
    searched_urls: Annotated[list[str], append_or_reset]

    # structured per-listing profiles returned by listing agents.
    # Parallel listing agents append here; intent_router resets on new search.
    listing_profiles: Annotated[list[dict], append_or_reset]

    # how many full search + listing cycles have completed.
    # supervisor_check increments this and uses it to cap retries at MAX_SEARCH_ATTEMPTS.
    search_attempts: int

    questions_asked: int
    ready_to_search: bool
    final_response: str
    ranked_listings: list[dict]
    analysis_insights: str
    elicitation_options: list[str]

    # set by the intent_router node on every message: one of
    # "needs_search", "conversational", "tool_call", "off_topic".
    # Only "needs_search" proceeds through elicitation → planner → ...; the
    # other intents short-circuit with a direct response.
    intent: str
