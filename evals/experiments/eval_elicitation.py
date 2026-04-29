"""
Experiment: Preference Elicitation Node Quality

Variants compared:
  - haiku_sonnet  : Haiku extraction + Sonnet questions  (current production)
  - haiku_haiku   : Haiku for both
  - sonnet_sonnet : Sonnet for both

Held constant:
  - 10 simulated conversation test cases (datasets/preferences.json)
  - MAX_QUESTIONS = 5
  - Extraction prompt template (from prompts/elicitation_prompts.py)
  - System prompt for question generation

Metrics:
  - extraction_f1         : field-level F1 between extracted preferences and ground truth
  - completeness_score    : % of non-null expected fields correctly populated
  - turns_to_ready        : Q&A turns needed to reach ready_to_search=True (lower is better)
  - question_quality_score: LLM-judge score (1-10) on follow-up question naturalness/relevance
  - latency_ms_per_turn   : avg wall-clock time per elicitation turn
  - total_tokens_per_session: total token count for one full elicitation session
"""
import json
import os
from anthropic import Anthropic

from evals.config import RESULTS_DIR, ELICITATION_VARIANTS, DATASETS_DIR
from evals.metrics.nlp import LatencyTimer, field_f1
from evals.metrics.llm_judge import LLMJudge

EXTRACTION_SYSTEM = """Extract apartment search preferences from the conversation.
Return ONLY valid JSON with these fields (use null if not mentioned):
{
  "city": <string|null>,
  "bedrooms": <int|null>,
  "max_price": <int|null>,
  "min_price": <int|null>,
  "pet_friendly": <bool|null>,
  "commute_destinations": <list of strings>,
  "soft_constraints": <list of strings>,
  "trade_off_rules": <list of strings>,
  "lifestyle_notes": <string|null>
}"""

CHAT_SYSTEM = """You are a warm, friendly apartment-hunting assistant helping someone find their next home.
Ask concise, natural follow-up questions to learn about their priorities.
Focus on: commute locations, budget flexibility, lifestyle needs, and trade-offs they're willing to make.
Ask one question at a time. Be conversational, not like a form."""


def extract_preferences(messages: list[dict], model: str, client: Anthropic) -> tuple[dict, dict]:
    """Run preference extraction and return (preferences_dict, usage_stats)."""
    context = messages[-4:] if len(messages) > 4 else messages
    convo_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in context)

    with LatencyTimer() as timer:
        resp = client.messages.create(
            model=model,
            max_tokens=512,
            system=EXTRACTION_SYSTEM,
            messages=[{"role": "user", "content": f"Conversation:\n{convo_text}"}],
        )
    raw = resp.content[0].text.strip()
    import re
    try:
        # Standard load
        prefs = json.loads(raw)
    except json.JSONDecodeError:
        # Robust extraction: find { ... } and strip trailing commas
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            clean_json = match.group(0)
            # Strip trailing commas before } or ]
            clean_json = re.sub(r',\s*([}\]])', r'\1', clean_json)
            try:
                prefs = json.loads(clean_json)
            except:
                prefs = {}
        else:
            prefs = {}

    return prefs, {"latency_ms": timer.elapsed_ms, "tokens": resp.usage.input_tokens + resp.usage.output_tokens}


def generate_question(messages: list[dict], preferences: dict, model: str, client: Anthropic) -> tuple[str, dict]:
    """Generate the next follow-up question."""
    # Format conversation as text so the API always receives a valid user-last message list
    context_str = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages[-6:])
    prompt = (
        f"Conversation so far:\n{context_str}\n\n"
        f"Extracted preferences: {json.dumps(preferences)}\n\n"
        "What is the single most important follow-up question to ask next? "
        "Reply with just the question, nothing else."
    )
    with LatencyTimer() as timer:
        resp = client.messages.create(
            model=model,
            max_tokens=256,
            system=CHAT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    question = resp.content[0].text.strip()
    return question, {"latency_ms": timer.elapsed_ms, "tokens": resp.usage.input_tokens + resp.usage.output_tokens}


def is_ready_to_search(preferences: dict) -> bool:
    """Mirrors graph/nodes/elicitation.py: ready when city + (price or bedrooms) are set."""
    return bool(preferences.get("city")) and bool(
        preferences.get("max_price") or preferences.get("bedrooms")
    )


def simulate_elicitation_session(
    test_case: dict,
    extraction_model: str,
    chat_model: str,
    client: Anthropic,
    judge: LLMJudge,
    max_questions: int = 5,
) -> dict:
    """
    Simulate a full elicitation session:
    1. Start with user's initial messages
    2. Run extract → question → [user replies with next turn] loop
    3. Stop when ready_to_search=True or max_questions reached
    """
    messages = list(test_case["conversation"])
    total_tokens = 0
    total_latency = 0.0
    question_scores = []
    turns = 0

    final_preferences = {}
    ready = False

    for turn in range(max_questions):
        # Extract preferences from current conversation
        prefs, extr_usage = extract_preferences(messages, extraction_model, client)
        total_tokens += extr_usage["tokens"]
        total_latency += extr_usage["latency_ms"]
        final_preferences = prefs

        if is_ready_to_search(prefs):
            ready = True
            turns = turn + 1
            break

        # Generate follow-up question
        question, gen_usage = generate_question(messages, prefs, chat_model, client)
        total_tokens += gen_usage["tokens"]
        total_latency += gen_usage["latency_ms"]

        # Judge question quality
        q_score = judge.question_quality(question, messages)
        question_scores.append(q_score.get("score", 0))

        # Simulate user not providing more info (worst case — tests max turns).
        # Append a neutral user reply so the conversation maintains proper user/assistant
        # alternation; without it, consecutive assistant turns confuse subsequent extractions.
        messages.append({"role": "assistant", "content": question})
        messages.append({"role": "user", "content": "I'm not sure, can you help me figure that out?"})
        turns = turn + 1

    if not ready:
        # Final extraction after all turns
        final_preferences, extr_usage = extract_preferences(messages, extraction_model, client)
        total_tokens += extr_usage["tokens"]
        total_latency += extr_usage["latency_ms"]

    return {
        "test_id": test_case["id"],
        "final_preferences": final_preferences,
        "turns_to_ready": turns if ready else max_questions,
        "reached_ready": ready,
        "mean_question_quality": round(sum(question_scores) / len(question_scores), 2) if question_scores else None,
        "total_tokens": total_tokens,
        "total_latency_ms": round(total_latency, 1),
    }


def evaluate_variant(variant_name: str, config: dict, test_cases: list[dict], judge: LLMJudge) -> dict:
    client = Anthropic()
    per_case_metrics = []

    for tc in test_cases:
        session = simulate_elicitation_session(
            tc, config["extraction_model"], config["chat_model"], client, judge
        )

        # Field-level F1
        expected = tc["expected_preferences"]
        f1_result = field_f1(session["final_preferences"], expected)

        # Completeness: % non-null expected fields correctly populated
        non_null_fields = {k: v for k, v in expected.items() if v not in (None, [], "")}
        completeness = (
            sum(
                1 for k in non_null_fields
                if session["final_preferences"].get(k) not in (None, [], "")
            ) / len(non_null_fields)
            if non_null_fields else 1.0
        )

        per_case_metrics.append({
            **session,
            "extraction_micro_f1": f1_result["micro_f1"],
            "per_field_f1": f1_result["per_field"],
            "completeness_score": round(completeness, 3),
        })

    n = len(per_case_metrics)
    return {
        "variant": variant_name,
        "config": config,
        "per_case": per_case_metrics,
        "aggregate": {
            "mean_extraction_f1": round(sum(m["extraction_micro_f1"] for m in per_case_metrics) / n, 3),
            "mean_completeness": round(sum(m["completeness_score"] for m in per_case_metrics) / n, 3),
            "mean_turns_to_ready": round(sum(m["turns_to_ready"] for m in per_case_metrics) / n, 2),
            "ready_rate": round(sum(1 for m in per_case_metrics if m["reached_ready"]) / n, 3),
            "mean_question_quality": round(
                sum(m["mean_question_quality"] or 0 for m in per_case_metrics) / n, 2
            ),
            "mean_total_tokens": round(sum(m["total_tokens"] for m in per_case_metrics) / n),
            "mean_latency_ms": round(sum(m["total_latency_ms"] for m in per_case_metrics) / n, 1),
        },
    }


def run(variants: list[str] | None = None) -> dict:
    dataset = json.loads((DATASETS_DIR / "preferences.json").read_text())
    
    # SLIM MODE: only use 2 preferences
    if os.environ.get("EVAL_SLIM") == "true":
        dataset = dataset[:2]

    judge = LLMJudge()
    targets = variants or list(ELICITATION_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = ELICITATION_VARIANTS[name]
        print(f"  Running elicitation variant: {name}")
        all_results[name] = evaluate_variant(name, config, dataset, judge)

    output_path = RESULTS_DIR / "elicitation_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
