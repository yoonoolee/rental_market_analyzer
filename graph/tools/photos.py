import os
import json
import base64
import httpx
import anthropic
from langchain_core.tools import tool

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.apartments.com/",
}

def _fetch_image_b64(url: str) -> tuple[str, str] | None:
    """Download an image and return (base64_data, media_type), or None on failure."""
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            return None
        ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not ct.startswith("image/"):
            return None
        return base64.standard_b64encode(r.content).decode(), ct
    except Exception:
        return None


_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


@tool
async def analyze_listing_photos(image_urls: list[str], user_preferences: str) -> dict:
    """
    Analyze rental listing photos in the context of what this specific user cares about.

    user_preferences: plain-text summary of what the user wants (from their preference profile).
    The model decides what to assess based on what actually matters for this user.

    Returns a dict with:
    - "observations": list of short plain-english observations about what's visible
    - "condition": "excellent", "good", "fair", or "poor"
    - "notes": one sentence summary of the most relevant thing visible for this user
    - any other fields the model judges relevant given the user's preferences
    """
    if not image_urls:
        return {"error": "no images provided"}

    image_blocks = []
    for url in image_urls:
        fetched = _fetch_image_b64(url)
        if fetched:
            data, media_type = fetched
            image_blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})

    if not image_blocks:
        return {"error": "images could not be downloaded (auth-protected or unavailable)"}

    content = [
        *image_blocks,
        {
            "type": "text",
            "text": f"""You are analyzing rental listing photos for a specific user. Use their preferences to decide what to look for and assess.

User preferences:
{user_preferences}

Look at the photos and assess what's actually visible and relevant to this user. Don't run through a fixed checklist — focus on what would matter to them specifically based on what they said.

Return a JSON object with:
- "observations": list of short plain-english observations about what you see that's relevant to this user
- "condition": "excellent", "good", "fair", or "poor" based on overall upkeep
- "notes": one sentence on the single most relevant thing visible for this user
- any other boolean or string fields that capture something specific this user cares about that you can see in the photos

Return only valid JSON. Use null for anything not visible."""
        }
    ]

    client = _get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": content}]
    )

    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)
