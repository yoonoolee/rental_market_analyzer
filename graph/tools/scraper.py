import os
from firecrawl import Firecrawl
from langchain_core.tools import tool


@tool
async def scrape_listing(url: str) -> dict:
    """
    Scrape a rental listing page using Firecrawl and return the raw markdown content
    along with the URL. The listing agent is responsible for extracting structured
    fields (price, address, pet policy, etc.) from the returned markdown.
    """
    app = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))
    result = app.scrape(url, formats=["markdown"])

    return {
        "url": url,
        "raw_text": result.markdown,
    }
