"""
End-to-end smoke test of the LangGraph pipeline (no web UI).
Exercises every intent_router branch and an elicitation → full-search flow.

Usage:
    python -m scripts.smoke_test_graph
"""
import asyncio
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

load_dotenv(override=True)

# Pause between API-heavy turns (classifier + follow-up). Override e.g. SMOKE_THROTTLE_SEC=0 for a quick run.
_SMOKE_THROTTLE = float(os.getenv("SMOKE_THROTTLE_SEC", "2"))


async def invoke(graph, text, thread_id="smoke-test"):
    print(f"\n>>> USER: {text}")
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=text)]},
        config=config,
    )
    intent = result.get("intent", "?")
    print(f"    intent: {intent}")
    if result.get("final_response"):
        print(f"    final_response:  {result['final_response'][:250]}...")
        if result.get("analysis_insights"):
            print(f"    analysis:        {result['analysis_insights'][:150]}...")
    else:
        ai = [m for m in result.get("messages", []) if m.__class__.__name__ == "AIMessage"]
        if ai:
            print(f"    ai_response:     {ai[-1].content[:250]}")
    return result


async def main():
    from graph.builder import build_graph

    # use in-memory checkpointer for the smoke test so we don't pollute rental_state.db
    memory = MemorySaver()
    graph = build_graph(checkpointer=memory)

    # 1. off-topic
    await invoke(graph, "Write me a poem about cats", thread_id="smoke-off-topic")
    await asyncio.sleep(_SMOKE_THROTTLE)

    # 2. conversational
    await invoke(graph, "What's the difference between a studio and a 1BR?", thread_id="smoke-convo")
    await asyncio.sleep(_SMOKE_THROTTLE)

    # 3. tool_call: commute
    await invoke(graph, "How long is the commute from 4521 Telegraph Ave Oakland to UC Berkeley by transit?", thread_id="smoke-tool-commute")
    await asyncio.sleep(_SMOKE_THROTTLE)

    # 4. tool_call: places
    await invoke(graph, "Find grocery stores near 2090 Kittredge St Berkeley", thread_id="smoke-tool-places")
    await asyncio.sleep(_SMOKE_THROTTLE)

    # 5. needs_search (will exercise the full pipeline — expect this to take a few minutes)
    #    Uses a single thread so multi-turn elicitation state is preserved.
    #    Skip with SKIP_PIPELINE=1 to avoid API costs during quick checks.
    if os.getenv("SKIP_PIPELINE") == "1":
        print("\n\n=== FULL PIPELINE TEST SKIPPED (SKIP_PIPELINE=1) ===")
        return
    print("\n\n=== FULL PIPELINE TEST ===")
    print("(this hits SerpAPI + Firecrawl + Google Maps; will take a few minutes)")
    await invoke(graph, "I'm looking for a 1BR in Oakland under $2100, pet-friendly (I have a cat), close to BART because I commute to UC Berkeley Soda Hall.", thread_id="smoke-search")


if __name__ == "__main__":
    asyncio.run(main())
