import os
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from graph.builder import build_graph

_CHECKPOINT_DB = os.getenv("RENTAL_CHECKPOINT_DB", "rental_state.db")
graph = None


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


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    config = {
        "configurable": {"thread_id": session_id},
        "run_name": "rental-market-analyzer",
        "metadata": {"session_id": session_id},
    }

    # Replay existing history for returning sessions; new sessions get no server message
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

            fresh_state = await graph.aget_state(config)
            prior_ai_count = sum(
                1 for m in (fresh_state.values.get("messages", []) if fresh_state else [])
                if isinstance(m, AIMessage)
            )

            await websocket.send_json({"type": "step_start", "name": "Searching..."})

            try:
                result = await graph.ainvoke({"messages": [HumanMessage(content=user_message)]}, config=config)
            except Exception as e:
                await websocket.send_json({"type": "step_end"})
                await websocket.send_json({"type": "error", "content": str(e)})
                continue

            await websocket.send_json({"type": "step_end"})

            if result.get("final_response"):
                response = result["final_response"]
                if result.get("analysis_insights"):
                    response += "\n\n---\n\n### Market Insights\n\n" + result["analysis_insights"]
                await websocket.send_json({"type": "message", "role": "assistant", "content": response})
            else:
                ai_messages = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
                for m in ai_messages[prior_ai_count:]:
                    await websocket.send_json({"type": "message", "role": "assistant", "content": m.content})

    except WebSocketDisconnect:
        pass


# Serve built React frontend in production
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
