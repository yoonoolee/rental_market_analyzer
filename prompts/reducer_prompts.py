# Prompt for the reducer node.
#
# The reducer now receives structured listing profiles from the ReAct listing agents,
# not raw search snippets. Each profile contains real data (price, floor, commute times,
# nearby places, pet policy, images) gathered from actual tool calls - so the reducer
# should reason from facts, not infer from fragments.
#
# Key responsibility: apply the user's trade-off rules to real numbers.
# "willing to pay $200 more if commute < 15 min" should be evaluated against
# actual commute times in the profiles, not estimated from neighborhood context.
#
# TODO: consider adding chain-of-thought reasoning (ask LLM to reason step by step
# before giving final rankings) - might improve quality for complex trade-off sets


REDUCER_PROMPT = """You rank apartment listings and write a short, plain summary for the user.

Data in each profile is real — scraped from the listing, commute times from Maps API, places from Places API. Use it directly.

Return JSON in exactly this format:
{
  "ranked_urls": ["url1", "url2", ...],
  "response": "..."
}

ranked_urls: best-first, URLs only, max MAX_SHOWN.

response rules — write clean, scannable markdown:
- Start with one short sentence (what you found, or why options are limited)
- For each recommended listing, a small header with address and price, then 2–3 tight bullet points covering only what matters for this user (commute, pet policy, key amenity, trade-off applied). Skip nulls.
- If any listings were disqualified, one line at the end: "X listings didn't make the cut — [main reason]."
- Close with one short follow-up question (max 10 words).

Tone: direct, no filler words, no "Great news!" or "I found". Write like a text from a friend who just checked the listings."""
