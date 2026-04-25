import os
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

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("content", "").strip()
            if not user_message:
                continue

            await websocket.send_json({"type": "process_start"})

            listing_total = 0
            listing_done = 0

            try:
                async for event in graph.astream_events(
                    {"messages": [HumanMessage(content=user_message)]},
                    config=config,
                    version="v2",
                ):
                    kind = event["event"]
                    name = event.get("name", "")

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
