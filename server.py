import os
import json
import asyncio
import traceback
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
load_dotenv(override=True)

_LOG_SESSIONS = os.getenv("LOG_SESSIONS", "").lower() == "true"
_SESSION_LOGS_DIR = Path("logs/sessions")

from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from graph.builder import build_graph
import aiosqlite

_CHECKPOINT_DB = os.getenv("RENTAL_CHECKPOINT_DB", "rental_state.db")
graph = None
ABORT_EVENTS: dict[str, asyncio.Event] = {}
logger = logging.getLogger("uvicorn.error")

TRACKED_NODES = {"planner", "search_node", "supervisor", "listing_agent", "reducer", "analyzer", "elicitation", "intent_router"}


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


@app.post("/abort/{session_id}")
async def abort_session(session_id: str):
    ABORT_EVENTS.setdefault(session_id, asyncio.Event()).set()
    return JSONResponse({"ok": True})


_PROXY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.apartments.com/",
}

@app.get("/imgproxy")
async def image_proxy(url: str = Query(...)):
    """Proxy listing images to bypass hotlink/referrer restrictions."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            r = await client.get(url, headers=_PROXY_HEADERS)
        content_type = r.headers.get("content-type", "image/jpeg")
        return StreamingResponse(iter([r.content]), media_type=content_type)
    except Exception:
        return JSONResponse({"error": "failed"}, status_code=502)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    await websocket.send_json({"type": "connection_state", "state": "connected"})

    config = {
        "configurable": {"thread_id": session_id},
        "run_name": "rental-market-analyzer",
        "metadata": {"session_id": session_id},
    }

    prior_state = await graph.aget_state(config)
    if prior_state and prior_state.values:
        for m in prior_state.values.get("messages", []):
            if isinstance(m, HumanMessage) and m.content:
                if m.content.strip().startswith("Q:") and "\nA:" in m.content:
                    await websocket.send_json({"type": "elicitation_answered", "content": m.content})
                else:
                    await websocket.send_json({"type": "message", "role": "user", "content": m.content})
            elif isinstance(m, AIMessage) and m.content:
                await websocket.send_json({"type": "message", "role": "assistant", "content": m.content})

        # Replay unanswered elicitation batch if session is still mid-elicitation
        if not prior_state.values.get("ready_to_search"):
            batch = prior_state.values.get("elicitation_batch") or []
            if batch:
                await websocket.send_json({"type": "elicitation_batch", "questions": batch})

        ranked_listings = prior_state.values.get("ranked_listings") or []
        if ranked_listings:
            await websocket.send_json({"type": "listings", "listings": ranked_listings})

        analysis_insights = prior_state.values.get("analysis_insights") or ""
        if analysis_insights:
            await websocket.send_json({"type": "message", "role": "assistant", "content": analysis_insights})

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("content", "").strip()
            if not user_message:
                continue

            abort_event = ABORT_EVENTS.setdefault(session_id, asyncio.Event())
            abort_event.clear()
            await websocket.send_json({"type": "process_start"})

            listing_round = 0
            round_done = 0
            round_total = 0
            search_done = 0
            search_total = 0
            agent_run_urls: dict[str, str] = {}  # run_id -> url

            TOOL_LABELS = {
                "scrape_listing": "scraping listing page",
                "get_commute_time": "checking commute",
                "find_nearby_places": "finding nearby places",
                "search_web": "searching web",
                "analyze_listing_photos": "analyzing photos",
            }

            if user_message.startswith("/evals"):
                parts = user_message.split()
                args_to_pass = parts[1:]
                cmd = ["python3", "-u", "-m", "evals.run_evals"] + args_to_pass
                
                await websocket.send_json({
                    "type": "process_step",
                    "node": "evals",
                    "label": f"Running evaluations: {' '.join(args_to_pass) if args_to_pass else 'all'}",
                    "detail": []
                })
                
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            break
                        line_str = line.decode('utf-8').strip()
                        if line_str:
                            await websocket.send_json({
                                "type": "process_step_update",
                                "node": "evals",
                                "label": f"Running evaluations: {', '.join(exps) if exps else 'all'}",
                                "detail_item": line_str
                            })
                    
                    await process.wait()
                    
                    try:
                        with open("evals/results/summary.json", "r") as f:
                            summary = json.load(f)
                        summary_text = "### Evaluation Complete!\n\n"
                        
                        # Determine if we should filter the summary
                        specific_exps = []
                        if "--experiments" in args_to_pass:
                            idx = args_to_pass.index("--experiments")
                            specific_exps = args_to_pass[idx+1:]
                            # stop at next flag
                            specific_exps = [e for e in specific_exps if not e.startswith("-")]

                        for exp_name, res in summary.items():
                            if not specific_exps or exp_name in specific_exps:
                                summary_text += f"**{exp_name.upper()}**\n"
                                if isinstance(res, dict) and "error" in res:
                                    summary_text += f"- *error*: {res['error']}\n\n"
                                    continue
                                for variant, data in res.items():
                                    if isinstance(data, dict):
                                        agg = data.get("aggregate", {})
                                        metrics = " | ".join(f"`{k}`: {v}" for k, v in agg.items())
                                        summary_text += f"- *{variant}*: {metrics}\n"
                                    else:
                                        summary_text += f"- *{variant}*: {data}\n"
                                summary_text += "\n"
                        await websocket.send_json({"type": "message", "role": "assistant", "content": summary_text})
                    except Exception as e:
                        await websocket.send_json({"type": "message", "role": "assistant", "content": f"Could not load summary: {e}"})
                
                except Exception as e:
                    await websocket.send_json({"type": "message", "role": "assistant", "content": f"Failed to run evals: {e}"})
                
                await websocket.send_json({"type": "process_end"})
                continue

            try:
                aborted = False
                async for event in graph.astream_events(
                    {"messages": [HumanMessage(content=user_message)]},
                    config=config,
                    version="v2",
                ):
                    if abort_event.is_set():
                        aborted = True
                        await websocket.send_json({
                            "type": "message",
                            "role": "assistant",
                            "content": "Stopped this run. You can send a new request anytime.",
                        })
                        break

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
                                "round": listing_round,
                                "url": url,
                                "hostname": hostname,
                                "status": "starting…",
                                "finished": False,
                            })
                        continue

                    if kind == "on_custom_event" and name == "timing_log":
                        await websocket.send_json({"type": "debug_log", "msg": event.get("data", {}).get("msg", "")})
                        continue

                    if kind == "on_custom_event" and name == "supervisor_expand":
                        d = event.get("data", {})
                        cat_count = d.get("category_count", 0)
                        extracted_count = d.get("extracted_count", 0)
                        detail = d.get("detail", [])
                        await websocket.send_json({
                            "type": "process_step",
                            "node": "supervisor_expand",
                            "label": f"Expanded {cat_count} search pages → {extracted_count} listings found",
                            "detail": detail,
                        })
                        continue

                    if kind == "on_custom_event" and name == "error_log":
                        d = event.get("data", {})
                        node = d.get("node", "?")
                        msg = d.get("error", "")
                        level = d.get("level", "error")
                        logger.error("[%s] %s", node, msg)
                        await websocket.send_json({"type": "debug_error", "node": node, "msg": msg, "level": level})
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
                                "round": listing_round,
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
                                "round": listing_round,
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
                            search_done = 0
                            search_total = len(queries)
                            await websocket.send_json({
                                "type": "process_step",
                                "node": "planner",
                                "label": f"Generated {len(queries)} search queries",
                                "detail": queries,
                            })
                            await websocket.send_json({
                                "type": "process_step",
                                "node": "search_node",
                                "label": f"Running searches (0/{len(queries)})",
                                "detail": [],
                                "done": 0,
                                "total": len(queries),
                            })
                            logger.info("[planner] %s queries generated", len(queries))

                    elif name == "search_node":
                        search_done += 1
                        query = ((output.get("search_results") or [{}])[0]).get("query", "")
                        await websocket.send_json({
                            "type": "process_step_update",
                            "node": "search_node",
                            "label": f"Running searches ({search_done}/{search_total})",
                            "done": search_done,
                            "total": search_total,
                            "detail_item": query,
                        })
                        if query:
                            logger.info("[search] %s/%s %s", search_done, search_total, query)

                    elif name == "supervisor":
                        urls = output.get("pending_urls", [])
                        listing_round += 1
                        round_done = 0
                        round_total = len(urls)
                        await websocket.send_json({
                            "type": "process_step",
                            "node": "supervisor",
                            "label": f"Found {len(urls)} listings to research",
                            "detail": urls,
                        })
                        logger.info("[supervisor] queued %s listing URLs", len(urls))
                        if urls:
                            await websocket.send_json({
                                "type": "process_step",
                                "node": "listing_agents",
                                "round": listing_round,
                                "label": f"Researching listings (0/{len(urls)})",
                                "detail": [],
                                "done": 0,
                                "total": len(urls),
                            })

                    elif name == "listing_agent":
                        round_done += 1
                        profile = (output.get("listing_profiles") or [{}])[0]
                        url = profile.get("building_url") or profile.get("url", "").split("#")[0]
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
                            "round": listing_round,
                            "url": url,
                            "hostname": hostname,
                            "status": status,
                            "finished": True,
                            "disqualified": disqualified,
                        })
                        await websocket.send_json({
                            "type": "process_step_update",
                            "node": "listing_agents",
                            "round": listing_round,
                            "label": f"Researching listings ({round_done}/{round_total})",
                            "done": round_done,
                            "total": round_total,
                            "detail_item": url,
                        })
                        if url:
                            logger.info("[listing_agent] completed %s", url)

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
                            logger.info("[reducer] returned %s ranked listings", len(ranked))

                    elif name == "analyzer":
                        await websocket.send_json({
                            "type": "process_step",
                            "node": "analyzer",
                            "label": "Analyzing market",
                            "detail": [],
                        })
                        insights = output.get("analysis_insights", "")
                        if insights:
                            await websocket.send_json({"type": "message", "role": "assistant", "content": insights})

                    elif name == "elicitation":
                        ready = output.get("ready_to_search", False)
                        prefs = output.get("preferences", {})
                        if ready:
                            pref_summary = ", ".join(
                                f"{k}: {v}" for k, v in prefs.items()
                                if v not in (None, [], {}, "")
                            )
                            await websocket.send_json({
                                "type": "process_step",
                                "node": "elicitation",
                                "label": "Requirements understood — starting search",
                                "detail": [pref_summary] if pref_summary else [],
                            })
                            if prefs:
                                await websocket.send_json({"type": "preferences", "data": prefs})
                        else:
                            await websocket.send_json({
                                "type": "process_step",
                                "node": "elicitation",
                                "label": "Clarifying your requirements",
                                "detail": [],
                            })
                        batch = output.get("elicitation_batch", [])
                        if batch:
                            await websocket.send_json({"type": "elicitation_batch", "questions": batch})
                        else:
                            messages_out = output.get("messages", [])
                            for m in messages_out:
                                if isinstance(m, AIMessage) and m.content:
                                    await websocket.send_json({"type": "message", "role": "assistant", "content": m.content})

                    elif name == "intent_router":
                        intent = output.get("intent", "")
                        intent_labels = {
                            "off_topic": "Off-topic — responding directly",
                            "conversational": "Answering your question",
                            "tool_call": "Running a quick lookup",
                            "needs_search": "Starting apartment search",
                        }
                        await websocket.send_json({
                            "type": "process_step",
                            "node": "intent_router",
                            "label": intent_labels.get(intent, "Thinking…"),
                            "detail": [],
                        })
                        messages_out = output.get("messages", [])
                        for m in messages_out:
                            if isinstance(m, AIMessage) and m.content:
                                await websocket.send_json({"type": "message", "role": "assistant", "content": m.content})

                if aborted:
                    # Do not emit stale step events after user cancellation.
                    pass
                elif _LOG_SESSIONS:
                    try:
                        final_state = await graph.aget_state(config)
                        vals = final_state.values if final_state else {}
                        _SESSION_LOGS_DIR.mkdir(parents=True, exist_ok=True)
                        log_path = _SESSION_LOGS_DIR / f"{session_id}.json"
                        conversation = [
                            {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                            for m in vals.get("messages", [])
                            if (isinstance(m, (HumanMessage, AIMessage)) and m.content)
                        ]
                        log_path.write_text(json.dumps({
                            "session_id": session_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "preferences": vals.get("preferences"),
                            "listing_profiles": vals.get("listing_profiles", []),
                            "conversation": conversation,
                        }, indent=2))
                    except Exception:
                        pass
            except Exception as e:
                traceback.print_exc()
                err_str = str(e)
                err_lower = err_str.lower()
                if "rate limit" in err_lower or "429" in err_str or "too many requests" in err_lower:
                    err_label = "RateLimitError"
                elif any(x in err_lower for x in ("insufficient_credits", "billing", "quota_exceeded", "payment")):
                    err_label = "CreditsError"
                elif any(x in err_lower for x in ("context_length_exceeded", "maximum context length", "too many tokens", "max_tokens")):
                    err_label = "TokenLimitError"
                elif "401" in err_str or "unauthorized" in err_lower or "invalid api key" in err_lower or "authentication" in err_lower:
                    err_label = "AuthError"
                else:
                    err_label = type(e).__name__
                logger.error("[graph] %s: %s", err_label, err_str)
                await websocket.send_json({"type": "debug_error", "node": "graph", "msg": f"{err_label}: {err_str}", "level": "error"})
                await websocket.send_json({"type": "connection_state", "state": "error"})
                await websocket.send_json({"type": "error", "content": err_str})

            await websocket.send_json({"type": "process_end"})

    except WebSocketDisconnect:
        ABORT_EVENTS.setdefault(session_id, asyncio.Event()).set()


frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
