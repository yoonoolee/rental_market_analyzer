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

Generate 3-4 queries per allowed site, each targeting a different neighborhood or feature
angle so each query returns a different set of listings.

Good example (neighborhood/feature varies per query, not just the site):
- "site:apartments.com 1 bed Elmwood Berkeley $1500"
- "site:apartments.com 1 bed North Berkeley $1500 modern"
- "site:apartments.com 1 bed Southside Berkeley $1500 near campus"
- "site:apartments.com 1 bed Telegraph Berkeley $1500 pet friendly"
... and so on for each allowed site

Bad example (only the site: changes — do NOT do this):
- "site:zillow.com 1BR Berkeley CA under $1500"
- "site:apartments.com 1BR Berkeley CA under $1500"
- "site:trulia.com 1BR Berkeley CA under $1500"

Return JSON with key "search_queries" as a list of strings. Generate 3-5 queries."""
