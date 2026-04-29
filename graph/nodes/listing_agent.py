import json
import re
import time
import asyncio
import os
import json_repair
from langchain_core.messages import HumanMessage, SystemMessage
from ..llm import make_base_llm
from langgraph.prebuilt import create_react_agent
from langchain_core.callbacks.manager import adispatch_custom_event
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

llm = make_base_llm("listing_agent")

# Global cap across listing agents to avoid provider rate-limit collisions.
# Raise this when your API tier allows more parallel calls.
_CONCURRENCY = asyncio.Semaphore(int(os.getenv("LISTING_CONCURRENCY", "3")))


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

    short_url = url.split("/")[-2] or url[-40:]
    t_queued = time.monotonic()
    await adispatch_custom_event("timing_log", {"msg": f"QUEUED   {short_url}"})

    async with _CONCURRENCY:
        t_start = time.monotonic()
        wait = t_start - t_queued
        await adispatch_custom_event("timing_log", {"msg": f"START    {short_url}  (queued {wait:.1f}s)"})

        try:
            result = await asyncio.wait_for(agent.ainvoke(
                {
                    "messages": [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=f"Research this listing and return a structured JSON profile: {url}"),
                    ]
                },
                config={"run_name": f"listing_agent:{url[:60]}", "tags": ["listing_agent"], "recursion_limit": 12},
            ), timeout=120)
        except Exception as e:
            await adispatch_custom_event("error_log", {
                "node": "listing_agent",
                "error": f"{type(e).__name__} for {url[:80]}: {str(e)[:300]}",
                "level": "error",
            })
            from langchain_core.messages import AIMessage as LCAIMessage
            result = {
                "messages": [LCAIMessage(content=f'{{"url":"{url}","disqualified":true,"disqualify_reason":"agent invocation failed: {str(e)[:120]}"}}')]
            }

        t_end = time.monotonic()
        await adispatch_custom_event("timing_log", {"msg": f"DONE     {short_url}  (ran {t_end - t_start:.1f}s, total {t_end - t_queued:.1f}s)"})

    # find the last AIMessage (not ToolMessage) with content
    from langchain_core.messages import AIMessage as LCAIMessage, ToolMessage
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

    # If the profile has no meaningful scraped data, force-disqualify here rather
    # than letting an empty shell reach the reducer.
    if not profile.get("disqualified") and not profile.get("price") and not profile.get("address") and not profile.get("units"):
        profile["disqualified"] = True
        profile["disqualify_reason"] = "scrape returned no usable data"

    # Pull raw scrape data from tool messages — used for images and multi-unit expansion.
    scrape_data = {}
    for msg in result["messages"]:
        if isinstance(msg, ToolMessage) and msg.name == "scrape_listing":
            try:
                scrape_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                if not isinstance(scrape_data, dict):
                    scrape_data = {}
            except Exception:
                pass
            break

    # Override images with the full list from scrape — LLM tends to truncate long arrays.
    scraped_images = scrape_data.get("images")
    if scraped_images:
        profile["images"] = [u for u in scraped_images if u][:10]

    # Expand multi-unit buildings: if the scrape returned multiple units, create
    # one profile per unit so each gets individually qualified by the reducer.
    units = scrape_data.get("units") or profile.pop("units", None) or []
    if len(units) > 1:
        # Building-level disqualification that isn't price-based propagates to all units.
        disqualify_reason = profile.get("disqualify_reason", "")
        building_disqualified = profile.get("disqualified") and "price" not in disqualify_reason.lower()

        # Fields shared across all units (commute, places, images, amenities, etc.)
        unit_only_keys = {"price", "bedrooms", "bathrooms", "sqft", "floor_plan", "disqualified", "disqualify_reason", "url"}
        shared = {k: v for k, v in profile.items() if k not in unit_only_keys}

        profiles = []
        for i, unit in enumerate(units):
            if not isinstance(unit, dict):
                continue
            floor_plan = unit.get("floor_plan") or str(i)
            safe_plan = re.sub(r"[^a-z0-9-]", "-", floor_plan.lower())
            p = {**shared, **{k: v for k, v in unit.items() if v is not None}}
            p["url"] = f"{url}#{safe_plan}"
            p["building_url"] = url
            if building_disqualified:
                p["disqualified"] = True
                p["disqualify_reason"] = disqualify_reason
            profiles.append(p)

        return {"listing_profiles": profiles}

    return {"listing_profiles": [profile]}
