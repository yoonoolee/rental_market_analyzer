import os
import asyncio
import json
import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from graph.builder import build_graph
from dotenv import load_dotenv

load_dotenv()

# LangSmith tracing is enabled automatically when LANGCHAIN_TRACING_V2=true.
# The env vars (LANGCHAIN_API_KEY, LANGCHAIN_PROJECT) are read by LangChain at
# import time, so load_dotenv() must run before any langchain imports.
TRACING_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

# SqliteSaver persists conversation state across Chainlit sessions.
# Each user session gets its own thread_id; the checkpointer reloads prior state
# automatically on graph.ainvoke(..., config={"configurable": {"thread_id": ...}}).
_CHECKPOINT_DB = os.getenv("RENTAL_CHECKPOINT_DB", "rental_state.db")
_checkpoint_ctx = AsyncSqliteSaver.from_conn_string(_CHECKPOINT_DB)
checkpointer = None
graph = None


async def _ensure_graph():
    global graph, checkpointer
    if graph is None:
        checkpointer = await _checkpoint_ctx.__aenter__()
        graph = build_graph(checkpointer=checkpointer)
    return graph


WELCOME_MESSAGE = """Hey! I'm here to help you find your next apartment.

Tell me what you're looking for - city, budget, vibe, anything. The more context
you share (especially commute destinations and what you're willing to trade off),
the more useful I can be.

What are you looking for?"""


@cl.on_chat_start
async def start():
    await _ensure_graph()
    await cl.Message(content=WELCOME_MESSAGE).send()


@cl.on_message
async def on_message(message: cl.Message):
    if message.content.strip().lower() == "/evals":
        async with cl.Step(name="Running Evals (this may take a few minutes)...") as step:
            process = await asyncio.create_subprocess_exec(
                "python3", "-m", "evals.run_evals",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                step.output = stdout.decode("utf-8")

                summary_path = "evals/results/summary.json"
                if os.path.exists(summary_path):
                    with open(summary_path, "r") as f:
                        summary_data = json.load(f)

                    md = "### Eval Summary\n\n"
                    for exp_name, results in summary_data.items():
                        md += f"**{exp_name.upper().replace('_', ' ')}**\n"
                        for variant, data in results.items():
                            agg = data.get("aggregate", {})
                            metrics_str = " | ".join(f"{k}: {v}" for k, v in agg.items())
                            md += f"- `{variant}`: {metrics_str}\n"
                        md += "\n"

                    await cl.Message(content=md).send()
                else:
                    await cl.Message(content="Evals ran successfully, but no summary file was found.").send()
            else:
                step.output = stderr.decode("utf-8")
                await cl.Message(content="Evals failed. See steps for details.").send()
        return

    g = await _ensure_graph()

    # thread_id scopes the checkpointer to this user session, so state reloads
    # automatically across page refreshes / server restarts
    thread_id = cl.user_session.get("id")
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "rental-market-analyzer",
        "metadata": {"session_id": thread_id},
    }

    # count of AI messages before invoking — used to find only the NEW ones after.
    # Without this, the fallback path would keep re-sending the last historical AI
    # message on every turn once the checkpointer accumulates history.
    prior_state = await g.aget_state(config)
    prior_ai_count = sum(
        1 for m in (prior_state.values.get("messages", []) if prior_state else [])
        if isinstance(m, AIMessage)
    )

    # send only the newest user message; checkpointer merges with prior state
    input_state = {"messages": [HumanMessage(content=message.content)]}

    async with cl.Step(name="searching..."):
        result = await g.ainvoke(input_state, config=config)

    # final_response means the full search pipeline ran and we have recommendations.
    # Otherwise an AI message was appended by intent_router or elicitation — send only
    # the newly-added AI messages (those beyond prior_ai_count).
    if result.get("final_response"):
        response = result["final_response"]
        if result.get("analysis_insights"):
            response += "\n\n---\n\n### Market Insights\n\n" + result["analysis_insights"]
        await cl.Message(content=response).send()
    else:
        ai_messages = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
        new_ai_messages = ai_messages[prior_ai_count:]
        for m in new_ai_messages:
            await cl.Message(content=m.content).send()
