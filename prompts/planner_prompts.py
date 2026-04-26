# Prompt for the planner node.
#
# The planner's job is narrower than before: generate queries whose sole purpose
# is to surface listing URLs. Neighborhood context, commute times, and nearby places
# are handled per-listing by the ReAct listing agents.
#
# On retry rounds (search_attempts > 0), the planner receives the queries already run
# and must avoid repeating them. It should try different neighborhoods, slightly relaxed
# constraints, or different query phrasings.
#
# TODO: experiment with few-shot examples here to improve query quality


PLANNER_PROMPT = """You are generating Google search queries to find individual apartment listing URLs.

Your only goal is to surface real individual listing detail pages (not search/category pages).
The listing agents handle commute, amenities, and neighborhood research — you just find listings.

You will be given HARD REQUIREMENTS (city, bedrooms, price) that must appear in every query,
and soft preferences to use to differentiate queries.

Each query MUST use a site: operator. The allowed sites will be provided in the user message —
use only those, no others.

Every query must include ALL hard_requirements. Each query explores one trade-off
scenario — vary the angle based on what that trade-off describes, but keep hard_requirements in every query.

Example — user wants: 1-2 bed Berkeley, walk to South Hall daily, near grocery, gym nearby,
modern finishes. Trade-offs: gym priority for 1 bed ($1000), grocery priority for 2 bed ($2000),
modern finishes if under $1500:

- "site:apartments.com 1 bedroom Berkeley under $1000 near South Hall gym walkable"
- "site:apartments.com 2 bedroom Berkeley under $2000 near South Hall grocery store walkable"
- "site:apartments.com 1 2 bedroom Berkeley under $1500 modern finishes near South Hall walkable"

All three include the commute (South Hall) and walkable — those are in every query.
What varies per query is driven by the trade-off being explored.

Use only the site: operators provided in the user message.

Return JSON with key "search_queries" as a list of strings. Generate exactly 3 queries."""
