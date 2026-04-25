import os
from firecrawl import AsyncFirecrawl
from langchain_core.tools import tool


@tool
async def scrape_listing(url: str) -> dict:
    """
    Scrape a rental listing page using Firecrawl and return the raw markdown content
    along with the URL. The listing agent is responsible for extracting structured
    fields (price, address, pet policy, etc.) from the returned markdown.

    Returns {url, raw_text} on success, or {url, error} if the site is unsupported
    or the scrape fails. The listing agent should check for the 'error' key and
    disqualify the listing if scraping is not possible.
    """
    try:
        app = AsyncFirecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))
        result = await app.scrape(url, formats=["markdown"])
        return {"url": url, "raw_text": result.markdown}
    except Exception as e:
        return {"url": url, "error": str(e)}
