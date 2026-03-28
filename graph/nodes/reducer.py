import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from ..state import RentalState
from ...prompts.reducer_prompts import REDUCER_PROMPT


llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.4)


async def reducer_node(state: RentalState) -> dict:
    """
    This is the Reduce step. Takes all parallel search results + the full
    preference state and synthesizes a ranked recommendation response.

    Key thing this needs to do well: apply interdependent trade-off rules.
    Not just "here are apartments under $2500" but "this one is $2700 but
    it's 8 min walk to BART so given your trade-off rule it's worth considering."

    The prompt (reducer_prompts.py) handles most of the reasoning instructions.
    """
    preferences = state.get("preferences", {})
    search_results = state.get("search_results", [])

    # format search results in a readable way for the LLM
    # keeping the query alongside results so it knows what each result is for
    formatted_results = ""
    for item in search_results:
        formatted_results += f"\n### Query: {item['query']}\n"
        for r in item.get("results", []):
            formatted_results += (
                f"- **{r['title']}** ({r.get('source', '')})\n"
                f"  {r.get('snippet', '')}\n"
                f"  {r.get('link', '')}\n"
            )

    response = await llm.ainvoke([
        SystemMessage(content=REDUCER_PROMPT),
        HumanMessage(content=(
            f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
            f"Search results:\n{formatted_results}\n\n"
            "Synthesize these into ranked apartment recommendations. Apply the user's "
            "trade-off rules explicitly - if something costs more but satisfies a condition "
            "they said they'd pay for, call that out. Include links to listings. "
            "Be specific about neighborhoods and commute implications."
        ))
    ])

    return {
        "final_response": response.content,
        "messages": [AIMessage(content=response.content)],
    }
