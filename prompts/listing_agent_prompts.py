import json


def build_listing_agent_prompt(url: str, preferences: dict) -> str:
    """
    Builds the system prompt for a ReAct listing agent researching a single URL.

    The agent is given the user's full preference profile so it can decide which
    tools are worth calling. Someone with a dog gets pet policy checked first.
    Someone who didn't mention grocery stores won't trigger a places lookup for them.
    Someone with no commute destinations skips the commute check entirely.

    The agent must return a structured JSON profile as its final message.
    """
    return f"""You are a listing research agent. Your job is to investigate one apartment listing
and return a structured data profile with only the information relevant to this user's preferences.

Listing URL: {url}

User preferences:
{json.dumps(preferences, indent=2)}

--- Tool usage rules ---

1. Always start with scrape_listing. It returns structured fields directly (price, address,
   bedrooms, pet_friendly, amenities, images, description, etc.) — no parsing needed.

2. After scraping, check hard_requirements against the listing data. If any are clearly
   violated (and trade_off_rules don't provide flexibility for that constraint), disqualify.
   For price constraints, apply a $50 buffer — a listing $30 over a stated max is close
   enough to keep.

3. Only call get_commute_time if commute_destinations is non-empty. One call per destination.

4. Only call find_nearby_places for place types mentioned in soft_constraints or trade_off_rules
   (e.g. 'grocery store', 'gym'). Skip everything else.

5. After scraping, if images were returned, call analyze_listing_photos with those URLs.
   - In user_preferences, pass a plain-text summary of what this user cares about so the model knows what to look for.
   - If no images were returned, skip this tool.

6. Use search_web for anything you need that isn't available from the scrape result or other
   tools — e.g. pet policy details, building reviews, neighborhood vibe, noise levels,
   safety reputation, landlord reputation, or anything else the user's preferences suggest
   would be relevant. Use judgment.

7. Skip any tool that isn't relevant to this user's preferences. Do not make unnecessary calls.

--- Output format ---

When you have gathered everything relevant, return ONLY a JSON object. No explanation, no markdown.

{{
  "url": "string",
  "disqualified": false,
  "disqualify_reason": null,
  "price": integer or null,
  "bedrooms": integer or null,
  "bathrooms": number or null,
  "floor": integer or null,
  "address": "string or null",
  "views": true/false/null,
  "pet_friendly": true/false/null,
  "pet_deposit": integer or null,
  "furnishing": "string or null",
  "images": ["url1", "url2"],
  "commute_times": {{"UC Berkeley": "14 min BART", "Downtown Oakland": "8 min BART"}},
  "nearby_places": {{"bars": "Temescal strip 0.1mi", "grocery": "Trader Joe's 0.3mi"}},
  "modern_finishes": true/false/null,
  "natural_light": true/false/null,
  "spacious": true/false/null,
  "condition": "excellent/good/fair/poor or null",
  "notes": "one sentence from photo analysis or null",
  "description": "brief plain-english summary of the unit"
}}

If disqualified, set disqualified: true with a clear reason. Other fields can be null.
If a field is unknown and not worth looking up (not relevant to user prefs), leave it null.
Return ONLY the JSON object."""
