from typing import TypedDict, Annotated
import operator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# PreferenceState is the core data structure we build up during Q&A.
#
# Design note: trade_off_rules stores natural language conditional preferences
# instead of numeric weights. This lets the reducer LLM reason about them
# holistically rather than doing brittle math. Examples:
#   "willing to pay +$300/mo if commute to work is under 10 minutes"
#   "don't need in-unit gym if there's one within 5 min walk"
#   "noise level matters more since I work from home"
#
# soft_constraints are also intentionally not flat - "quiet" matters more if the
# user works from home, "walkable" matters more if they don't have a car, etc.
# The reducer handles this reasoning, we just collect the raw signals here.
class PreferenceState(TypedDict, total=False):
    city: str
    bedrooms: int                    # 0 = studio, 1 = 1BR, 2 = 2BR, etc.
    max_price: int
    min_price: int                   # optional lower bound (some users have this)
    soft_constraints: list[str]      # e.g. ["quiet", "walkable", "near grocery stores"]
    trade_off_rules: list[str]       # conditional prefs in plain english (see above)
    commute_destinations: list[str]  # e.g. ["UC Berkeley campus", "Downtown Oakland gym"]
    lifestyle_notes: str             # pets, parking, lease length, anything else
    raw_query: str                   # original user message - useful context for the planner


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
    # generating duplicate queries
    all_search_queries: Annotated[list[str], operator.add]

    # raw URL results from search nodes - operator.add lets parallel search nodes
    # each append their results before supervisor processes them
    search_results: Annotated[list[dict], operator.add]

    # URLs queued for listing agent processing this round (replaced each supervisor run)
    pending_urls: list[str]

    # all URLs ever sent to a listing agent - used by supervisor to avoid
    # re-processing the same listing on retry rounds
    searched_urls: Annotated[list[str], operator.add]

    # structured per-listing profiles returned by listing agents.
    # operator.add lets all parallel listing agents append their profile.
    # each profile is either a full data object or {disqualified: true, reason: ...}
    listing_profiles: Annotated[list[dict], operator.add]

    # how many full search + listing cycles have completed.
    # supervisor_check increments this and uses it to cap retries at MAX_SEARCH_ATTEMPTS.
    search_attempts: int

    questions_asked: int
    ready_to_search: bool
    final_response: str
    analysis_insights: str
