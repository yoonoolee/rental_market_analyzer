import json
import re
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from ..llm import make_base_llm
from langgraph.prebuilt import create_react_agent
from ..state import ListingAgentState
from ..tools.scraper import scrape_listing
from ..tools.commute import get_commute_time
from ..tools.places import find_nearby_places
from ..tools.search import search_web
from ..tools.photos import analyze_listing_photos
from prompts.listing_agent_prompts import build_listing_agent_prompt


# all tools available to listing agents.
# each agent decides which ones to call based on the user's preferences -
# not every agent will use every tool.
LISTING_AGENT_TOOLS = [scrape_listing, get_commute_time, find_nearby_places, search_web, analyze_listing_photos]

llm = make_base_llm(model="claude-haiku-4-5-20251001", temperature=0.1)

# cap concurrent Claude calls across all listing agents to avoid rate limit collisions.
# raise this when on a higher API tier.
_CONCURRENCY = asyncio.Semaphore(2)


def _extract_json(text) -> dict:
    """Pull JSON out of agent response, handles markdown code blocks and content block lists."""
    if isinstance(text, list):
        text = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in text)
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1).strip())
    return json.loads(text.strip())


async def listing_agent_node(state: ListingAgentState) -> dict:
    """
    ReAct agent that researches a single apartment listing end-to-end.

    The agent receives the listing URL and the user's full preference profile.
    It reasons about which tools to call based on what the user actually cares about:
    - Has a pet? Check pet policy immediately, disqualify early if not allowed.
    - Has commute destinations? Call get_commute_time for each.
    - Mentioned bars? Call find_nearby_places for bars. Didn't mention grocery? Skip it.
    - Info missing from listing page? Fall back to search_web.

    This means tool usage varies per user and per listing - which is the point.
    A fixed pipeline would either over-call (wasting API credits) or under-call
    (missing info the user actually needs).

    Returns one structured listing profile which accumulates in
    state["listing_profiles"] via operator.add (see state.py).
    """
    url = state["url"]
    preferences = state["preferences"]

    agent = create_react_agent(model=llm, tools=LISTING_AGENT_TOOLS)
    system_prompt = build_listing_agent_prompt(url, preferences)

    async with _CONCURRENCY:
        result = await agent.ainvoke(
            {
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Research this listing and return a structured JSON profile: {url}"),
                ]
            },
            config={"run_name": f"listing_agent:{url[:60]}", "tags": ["listing_agent"]},
        )

    # last message from the agent should be the JSON profile
    final_content = result["messages"][-1].content

    try:
        profile = _extract_json(final_content)
        profile["url"] = url  # always ensure URL is set even if agent omitted it
    except (json.JSONDecodeError, ValueError):
        profile = {
            "url": url,
            "disqualified": True,
            "disqualify_reason": "Agent failed to return a parseable JSON profile",
        }

    return {"listing_profiles": [profile]}
