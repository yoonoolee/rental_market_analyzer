import os
import json
import anthropic
from langchain_core.tools import tool


_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


@tool
async def analyze_listing_photos(image_urls: list[str], focus_areas: str) -> dict:
    """
    Analyze rental listing photos using Claude vision.

    Always returns fixed quality signals: condition, natural_light, modern_finishes, spacious, notes.
    Also checks anything in focus_areas (comma-separated string), which the listing agent
    should populate based on what the user mentioned — e.g. "views, outdoor space, balcony".

    Returns a dict with bool/string fields for each checked attribute.
    Fields not applicable or not visible in photos are returned as null.
    """
    if not image_urls:
        return {"error": "no images provided"}

    focus_list = [f.strip() for f in focus_areas.split(",") if f.strip()]

    focus_instructions = ""
    if focus_list:
        focus_instructions = "\n\nAlso check these user-specific areas and add them as fields:\n"
        for area in focus_list:
            focus_instructions += f'- "{area}" (true/false/null)\n'
        focus_instructions += (
            'For outdoor space, check for any of: balcony, patio, backyard, yard, rooftop deck.\n'
            'Return a single "outdoor_space" field (true/false/null) regardless of the specific type.\n'
        )

    content = [
        *[
            {"type": "image", "source": {"type": "url", "url": url}}
            for url in image_urls
        ],
        {
            "type": "text",
            "text": f"""Analyze these rental listing photos and return a JSON object.

Always include these fixed fields:
- "modern_finishes" (true/false/null): updated kitchen/bath, stainless appliances, hardwood or quality floors
- "natural_light" (true/false/null): rooms look bright and well-lit
- "spacious" (true/false/null): rooms look reasonably sized, not cramped
- "condition" (string): "excellent", "good", "fair", or "poor" based on overall upkeep
- "notes" (string): one sentence on the most notable positive or negative visible in the photos
{focus_instructions}
Return only valid JSON. Use null for anything not visible or not determinable from the photos."""
        }
    ]

    client = _get_client()
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": content}]
        )
    except anthropic.BadRequestError:
        return {"error": "images could not be downloaded (URL may be auth-protected)"}

    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)
