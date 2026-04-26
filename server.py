import os
from urllib.parse import urlparse
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from graph.builder import build_graph
import aiosqlite

_CHECKPOINT_DB = os.getenv("RENTAL_CHECKPOINT_DB", "rental_state.db")
graph = None

TRACKED_NODES = {"planner", "supervisor", "listing_agent", "reducer", "analyzer", "elicitation", "intent_router"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    async with AsyncSqliteSaver.from_conn_string(_CHECKPOINT_DB) as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    async with aiosqlite.connect(_CHECKPOINT_DB) as db:
        await db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (session_id,))
        await db.execute("DELETE FROM writes WHERE thread_id = ?", (session_id,))
        await db.commit()
    return JSONResponse({"ok": True})


@app.delete("/sessions")
async def delete_all_sessions():
    async with aiosqlite.connect(_CHECKPOINT_DB) as db:
        await db.execute("DELETE FROM checkpoints")
        await db.execute("DELETE FROM writes")
        await db.commit()
    return JSONResponse({"ok": True})


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    config = {
        "configurable": {"thread_id": session_id},
        "run_name": "rental-market-analyzer",
        "metadata": {"session_id": session_id},
    }

    prior_state = await graph.aget_state(config)
    if prior_state and prior_state.values.get("messages"):
        for m in prior_state.values["messages"]:
            if isinstance(m, HumanMessage) and m.content:
                await websocket.send_json({"type": "message", "role": "user", "content": m.content})
            elif isinstance(m, AIMessage) and m.content:
                await websocket.send_json({"type": "message", "role": "assistant", "content": m.content})

        ranked_listings = prior_state.values.get("ranked_listings", [])
        if ranked_listings:
            await websocket.send_json({"type": "listings", "listings": ranked_listings})

        final_response = prior_state.values.get("final_response", "")
        analysis_insights = prior_state.values.get("analysis_insights", "")
        if final_response:
            content = final_response
            if analysis_insights:
                content += "\n\n---\n\n### Market Insights\n\n" + analysis_insights
            await websocket.send_json({"type": "message", "role": "assistant", "content": content})

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("content", "").strip()
            if not user_message:
                continue

            await websocket.send_json({"type": "process_start"})

            listing_total = 0
            listing_done = 0
            agent_run_urls: dict[str, str] = {}  # run_id -> url

            TOOL_LABELS = {
                "scrape_listing": "scraping listing page",
                "get_commute_time": "checking commute",
                "find_nearby_places": "finding nearby places",
                "search_web": "searching web",
                "analyze_listing_photos": "analyzing photos",
            }

            try:
                async for event in graph.astream_events(
                    {"messages": [HumanMessage(content=user_message)]},
                    config=config,
                    version="v2",
                ):
                    kind = event["event"]
                    name = event.get("name", "")

                    # capture run_id → url when a listing agent starts
                    if kind == "on_chain_start" and name == "listing_agent":
                        url = (event.get("data", {}).get("input") or {}).get("url", "")
                        run_id = event.get("run_id", "")
                        if url and run_id:
                            agent_run_urls[run_id] = url
                            hostname = urlparse(url).hostname or url
                            await websocket.send_json({
                                "type": "agent_update",
                                "node": "listing_agents",
                                "url": url,
                                "hostname": hostname,
                                "status": "starting…",
                                "finished": False,
                            })
                        continue

                    # rate limit wait — find which agent triggered it via parent_ids
                    if kind == "on_custom_event" and name == "rate_limit_wait":
                        wait = event.get("data", {}).get("wait", 0)
                        parent_ids = event.get("parent_ids", [])
                        url = next((agent_run_urls[pid] for pid in reversed(parent_ids) if pid in agent_run_urls), "")
                        if url:
                            hostname = urlparse(url).hostname or url
                            await websocket.send_json({
                                "type": "agent_update",
                                "node": "listing_agents",
                                "url": url,
                                "hostname": hostname,
                                "status": "rate limited",
                                "wait_seconds": wait,
                                "finished": False,
                            })
                        continue

                    # stream tool calls within listing agents
                    if kind == "on_tool_start" and name in TOOL_LABELS:
                        parent_ids = event.get("parent_ids", [])
                        url = next((agent_run_urls[pid] for pid in reversed(parent_ids) if pid in agent_run_urls), "")
                        if url:
                            hostname = urlparse(url).hostname or url
                            await websocket.send_json({
                                "type": "agent_update",
                                "node": "listing_agents",
                                "url": url,
                                "hostname": hostname,
                                "status": TOOL_LABELS[name],
                                "finished": False,
                            })
                        continue

                    if kind != "on_chain_end" or name not in TRACKED_NODES:
                        continue

                    output = event.get("data", {}).get("output", {})
                    if not isinstance(output, dict):
                        continue

                    if name == "planner":
                        queries = output.get("search_queries", [])
                        if queries:
                            await websocket.send_json({
                                "type": "process_step",
                                "node": "planner",
                                "label": f"Generated {len(queries)} search queries",
                                "detail": queries,
                            })

                    elif name == "supervisor":
                        urls = output.get("pending_urls", [])
                        listing_total += len(urls)
                        await websocket.send_json({
                            "type": "process_step",
                            "node": "supervisor",
                            "label": f"Found {len(urls)} listings to research",
                            "detail": urls,
                        })
                        if urls:
                            await websocket.send_json({
                                "type": "process_step",
                                "node": "listing_agents",
                                "label": f"Researching listings (0/{len(urls)})",
                                "detail": [],
                                "done": 0,
                                "total": len(urls),
                            })

                    elif name == "listing_agent":
                        listing_done += 1
                        profile = (output.get("listing_profiles") or [{}])[0]
                        url = profile.get("url", "")
                        hostname = urlparse(url).hostname or url
                        disqualified = profile.get("disqualified", False)
                        if disqualified:
                            status = profile.get("disqualify_reason", "disqualified")
                        else:
                            tools_used = []
                            if profile.get("commute_times"): tools_used.append("commute")
                            if profile.get("nearby_places"): tools_used.append("places")
                            if profile.get("pet_friendly") is not None: tools_used.append("pet policy")
                            status = "done" + (f" · {', '.join(tools_used)}" if tools_used else "")
                        await websocket.send_json({
                            "type": "agent_update",
                            "node": "listing_agents",
                            "url": url,
                            "hostname": hostname,
                            "status": status,
                            "finished": True,
                            "disqualified": disqualified,
                        })
                        await websocket.send_json({
                            "type": "process_step_update",
                            "node": "listing_agents",
                            "label": f"Researching listings ({listing_done}/{listing_total})",
                            "done": listing_done,
                            "total": listing_total,
                        })

                    elif name == "reducer":
                        await websocket.send_json({
                            "type": "process_step",
                            "node": "reducer",
                            "label": "Ranking results",
                            "detail": [],
                        })
                        ranked = output.get("ranked_listings", [])
                        if ranked:
                            await websocket.send_json({"type": "listings", "listings": ranked})

                    elif name == "analyzer":
                        await websocket.send_json({
                            "type": "process_step",
                            "node": "analyzer",
                            "label": "Analyzing market",
                            "detail": [],
                        })
                        final_response = output.get("final_response", "")
                        insights = output.get("analysis_insights", "")
                        if final_response:
                            response = final_response
                            if insights:
                                response += "\n\n---\n\n### Market Insights\n\n" + insights
                            await websocket.send_json({"type": "message", "role": "assistant", "content": response})

                    elif name == "elicitation":
                        messages_out = output.get("messages", [])
                        options = output.get("elicitation_options", [])
                        for m in messages_out:
                            if isinstance(m, AIMessage) and m.content:
                                if options:
                                    await websocket.send_json({"type": "options", "content": m.content, "options": options})
                                else:
                                    await websocket.send_json({"type": "message", "role": "assistant", "content": m.content})

                    elif name == "intent_router":
                        messages_out = output.get("messages", [])
                        for m in messages_out:
                            if isinstance(m, AIMessage) and m.content:
                                await websocket.send_json({"type": "message", "role": "assistant", "content": m.content})

            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})

            await websocket.send_json({"type": "process_end"})

    except WebSocketDisconnect:
        pass


frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
