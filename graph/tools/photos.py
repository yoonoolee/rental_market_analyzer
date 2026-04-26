import os
import json
import base64
import httpx
import asyncio
from langchain_core.tools import tool

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.apartments.com/",
}

async def _fetch_image_b64(client: httpx.AsyncClient, url: str) -> tuple[str, str] | None:
    """Download an image and return (base64_data, media_type), or None on failure."""
    try:
        r = await client.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
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
        import openai
        _client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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

    max_photos = max(1, int(os.getenv("MAX_PHOTOS", "12")))
    urls = image_urls[:max_photos]

    async with httpx.AsyncClient() as http_client:
        fetched_images = await asyncio.gather(*[_fetch_image_b64(http_client, url) for url in urls], return_exceptions=True)

    image_contents = []
    for fetched in fetched_images:
        if isinstance(fetched, Exception) or not fetched:
            continue
        data, media_type = fetched
        image_contents.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{data}", "detail": "low"},
        })

    if not image_contents:
        return {"error": "images could not be downloaded (auth-protected or unavailable)"}

    prompt = f"""You are analyzing rental listing photos for a specific user. Use their preferences to decide what to look for and assess.

User preferences:
{user_preferences}

Look at the photos and assess what's actually visible and relevant to this user. Don't run through a fixed checklist — focus on what would matter to them specifically based on what they said.

Return a JSON object with:
- "observations": list of short plain-english observations about what you see that's relevant to this user
- "condition": "excellent", "good", "fair", or "poor" based on overall upkeep
- "notes": one sentence on the single most relevant thing visible for this user
- any other boolean or string fields that capture something specific this user cares about that you can see in the photos

Return only valid JSON. Use null for anything not visible."""

    messages = [{"role": "user", "content": [*image_contents, {"type": "text", "text": prompt}]}]

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=512,
            messages=messages,
        )
    except Exception as e:
        err = str(e)
        if "401" in err or "invalid_api_key" in err.lower() or "authentication" in err.lower():
            return {"error": "photo analysis unavailable (invalid OpenAI API key)"}
        return {"error": f"photo analysis failed: {err[:80]}"}

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        return {"error": "could not parse photo analysis response"}
