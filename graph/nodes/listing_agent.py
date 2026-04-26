import json
import re
import asyncio
import json_repair
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

llm = make_base_llm(model="claude-sonnet-4-6", temperature=0.1)

# cap concurrent Claude calls across all listing agents to avoid rate limit collisions.
# raise this when on a higher API tier.
_CONCURRENCY = asyncio.Semaphore(1)


def _extract_json(text) -> dict:
    """Pull JSON out of agent response, tries multiple strategies including repair."""
    if isinstance(text, list):
        text = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in text)
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(json_repair.repair_json(match.group(1).strip()))
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(json_repair.repair_json(match.group(0)))
    raise ValueError(f"no JSON found: {text[:200]}")


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

    # find the last AIMessage (not ToolMessage) with content
    from langchain_core.messages import AIMessage as LCAIMessage
    ai_messages = [m for m in result["messages"] if isinstance(m, LCAIMessage) and m.content]
    final_content = ai_messages[-1].content if ai_messages else ""

    try:
        profile = _extract_json(final_content)
        profile["url"] = url
    except (json.JSONDecodeError, ValueError) as e:
        profile = {
            "url": url,
            "disqualified": True,
            "disqualify_reason": f"Parse failed ({str(e)[:100]}). Last AI msg: {str(final_content)[:150]}",
        }

    return {"listing_profiles": [profile]}
