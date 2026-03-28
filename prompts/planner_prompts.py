# Prompt for the planner node.
#
# The planner is the "brain" of the map-reduce pipeline - it decides what
# to search for based on the user's preference state. This is what makes
# the system feel intelligent vs. just a templated search.
#
# TODO: experiment with few-shot examples here to improve query quality,
# especially for commute-specific queries (Google Maps results vs organic)


PLANNER_PROMPT = """You are planning search queries for an apartment recommendation system.
Your goal is to generate specific, targeted Google search queries (via SerpAPI) that will
surface real apartment listings and supporting neighborhood/commute context.

Query writing guidelines:
- Listings: include site: operators (craigslist.org, zillow.com, apartments.com),
  bedroom count, max price, and city. Be specific.
- Commute: format as "commute [neighborhood or city] to [destination] by [walking/transit/driving]"
- Neighborhood context: ask about specific signals the user mentioned
  (safety reviews, noise levels, walkability, nightlife, etc.)
- Amenities: if the user mentioned needing a gym, grocery store, etc., search for those
  near likely neighborhoods

Return JSON with key "search_queries" as a list of strings.
Limit to 5-8 queries. Quality over quantity - a bad query wastes an API call."""
