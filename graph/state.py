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


class RentalState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    preferences: PreferenceState
    search_queries: list[str]

    # operator.add here is what makes map-reduce work:
    # each parallel search_node appends its result to this list,
    # and LangGraph merges them all before reducer runs
    search_results: Annotated[list[dict], operator.add]

    questions_asked: int
    ready_to_search: bool
    final_response: str
