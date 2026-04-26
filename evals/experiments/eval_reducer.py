"""
Experiment: Reducer Node — Final Ranking & Recommendation Quality

Variants compared:
  - baseline : Sonnet 4.6, temperature=0.4             (current production)
  - low_temp : Sonnet 4.6, temperature=0.1
  - cot      : Sonnet 4.6, temperature=0.4, chain-of-thought reasoning block

Held constant:
  - Input listing profiles (from datasets/static_listings.json, subset for pref_001 + pref_005)
  - User preferences (from datasets/preferences.json, pref_001 and pref_005)
  - Reducer prompt structure (mirrors prompts/reducer_prompts.py)

Metrics:
  - recommendation_quality : LLM judge (1-10) — preference alignment, actionability, tone
  - trade_off_adherence    : LLM judge (1-10) — explicit trade-off rules correctly applied
  - ranking_accuracy       : does best listing appear as #1? (binary, vs curated ideal ranking)
  - rouge_l                : ROUGE-L F1 vs a reference recommendation for each preference set
  - latency_ms             : wall-clock time per reducer call
  - cost_usd               : token cost per call
"""
import json
from anthropic import Anthropic

from evals.config import RESULTS_DIR, REDUCER_VARIANTS, SONNET_MODEL, DATASETS_DIR
from evals.metrics.nlp import LatencyTimer, rouge_l
from evals.metrics.llm_judge import LLMJudge

COST_PER_M_INPUT = {SONNET_MODEL: 3.00}
COST_PER_M_OUTPUT = {SONNET_MODEL: 15.00}

REDUCER_SYSTEM = """You are a knowledgeable apartment-hunting advisor.
Given a user's preferences and a set of researched listing profiles, produce conversational
rental recommendations that:
1. Rank the top 2-4 qualified listings by how well they match the user's stated preferences
2. Apply any explicit trade-off rules to actual data (not guesses)
3. Include clickable links and key data points
4. Acknowledge disqualified listings briefly
5. Are honest about null/unknown fields — do not infer or hallucinate data
6. Sound like advice from a knowledgeable friend, not a chatbot

{cot_instruction}"""

COT_INSTRUCTION = """Before writing your recommendation, briefly reason through your ranking:
<thinking>
- List each qualified listing and its score vs user priorities
- Apply trade-off rules to actual numbers
- Select top 2-4 by priority alignment
</thinking>

Then write the conversational recommendation."""


def _build_reference_response(listings_by_id: dict, ranked_ids: list[str], disqualified_ids: list[str]) -> str:
    lines = ["Top recommendations:"]
    for idx, lid in enumerate(ranked_ids[:3], start=1):
        listing = listings_by_id.get(lid, {})
        lines.append(
            f"{idx}. {listing.get('address', lid)} — ${listing.get('price', 'N/A')}/mo ({listing.get('url', '')})"
        )
    if disqualified_ids:
        lines.append(f"Excluded listings: {', '.join(disqualified_ids)}")
    return "\n".join(lines)


def _build_test_cases() -> list[dict]:
    prefs = json.loads((DATASETS_DIR / "preferences.json").read_text())
    rankings_file = json.loads((DATASETS_DIR / "preference_rankings.json").read_text())
    listings = json.loads((DATASETS_DIR / "static_listings.json").read_text())

    prefs_by_id = {p["id"]: p["expected_preferences"] for p in prefs}
    listings_by_id = {l["id"]: l for l in listings}
    target_pref_ids = {"pref_001", "pref_005"}

    test_cases = []
    for row in rankings_file["rankings"]:
        pref_id = row["preference_id"]
        if pref_id not in target_pref_ids or pref_id not in prefs_by_id:
            continue

        ranked_ids = row["ranked_listing_ids"]
        disqualified_ids = row.get("disqualified_listing_ids", [])
        case_listing_ids = ranked_ids + disqualified_ids
        profiles = [
            {k: v for k, v in listings_by_id[lid].items() if k not in ("id", "city")}
            for lid in case_listing_ids
            if lid in listings_by_id
        ]
        ideal_ranking_urls = [listings_by_id[lid]["url"] for lid in ranked_ids if lid in listings_by_id]
        reference = _build_reference_response(listings_by_id, ranked_ids, disqualified_ids)

        test_cases.append({
            "id": f"tc_{pref_id}",
            "preferences_id": pref_id,
            "preferences": prefs_by_id[pref_id],
            "listing_profiles": profiles,
            "ideal_ranking": ideal_ranking_urls,
            "reference_response": reference,
        })
    return test_cases


def run_reducer(
    preferences: dict,
    listing_profiles: list[dict],
    temperature: float,
    chain_of_thought: bool,
    client: Anthropic,
) -> tuple[str, dict]:
    qualified = [p for p in listing_profiles if not p.get("disqualified")]
    disqualified = [p for p in listing_profiles if p.get("disqualified")]

    cot_instr = COT_INSTRUCTION if chain_of_thought else ""
    system = REDUCER_SYSTEM.format(cot_instruction=cot_instr)

    prompt = (
        f"User preferences:\n{json.dumps(preferences, indent=2)}\n\n"
        f"Qualified listings ({len(qualified)}):\n{json.dumps(qualified, indent=2)}\n\n"
        f"Disqualified listings ({len(disqualified)}):\n"
        + "\n".join(f"- {p.get('address', p['url'])}: {p.get('disqualify_reason', 'disqualified')}" for p in disqualified)
    )

    with LatencyTimer() as timer:
        resp = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=1500,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

    response_text = resp.content[0].text.strip()
    # Strip <thinking> block for final output measurement
    if chain_of_thought and "<thinking>" in response_text:
        end_think = response_text.find("</thinking>")
        response_text_clean = response_text[end_think + len("</thinking>"):].strip() if end_think != -1 else response_text
    else:
        response_text_clean = response_text

    input_t = resp.usage.input_tokens
    output_t = resp.usage.output_tokens
    cost = (
        input_t / 1_000_000 * COST_PER_M_INPUT.get(SONNET_MODEL, 3.0)
        + output_t / 1_000_000 * COST_PER_M_OUTPUT.get(SONNET_MODEL, 15.0)
    )

    usage = {
        "latency_ms": timer.elapsed_ms,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "cost_usd": round(cost, 6),
    }
    return response_text_clean, usage


def check_ranking_accuracy(response: str, ideal_ranking: list[str]) -> bool:
    """Does the #1 ideal listing appear before the others in the response?"""
    if not ideal_ranking:
        return False
    positions = []
    for url in ideal_ranking:
        pos = response.find(url)
        positions.append(pos if pos != -1 else len(response) + 1)
    return positions[0] < min(positions[1:]) if len(positions) > 1 else positions[0] != len(response) + 1


def evaluate_variant(variant_name: str, config: dict, judge: LLMJudge, test_cases: list[dict]) -> dict:
    client = Anthropic()
    per_case_metrics = []

    for tc in test_cases:
        response, usage = run_reducer(
            tc["preferences"],
            tc["listing_profiles"],
            config["temperature"],
            config["chain_of_thought"],
            client,
        )

        # ROUGE-L vs reference
        rl = rouge_l(response, tc["reference_response"])

        # Ranking accuracy
        ranking_correct = check_ranking_accuracy(response, tc["ideal_ranking"])

        # LLM judges
        rec_quality = judge.recommendation_quality(response, tc["preferences"], tc["listing_profiles"])
        trade_off_rules = tc["preferences"].get("trade_off_rules", [])
        trade_off_score = (
            judge.trade_off_adherence(response, trade_off_rules, tc["listing_profiles"])
            if trade_off_rules
            else {"score": None, "rationale": "No trade-off rules in this test case"}
        )

        per_case_metrics.append({
            "test_id": tc["id"],
            "rouge_l_f1": rl["f1"],
            "ranking_accuracy": ranking_correct,
            "recommendation_quality": rec_quality.get("score"),
            "rec_quality_rationale": rec_quality.get("rationale"),
            "trade_off_adherence": trade_off_score.get("score"),
            "trade_off_rationale": trade_off_score.get("rationale"),
            "latency_ms": usage["latency_ms"],
            "cost_usd": usage["cost_usd"],
            "response_preview": response[:300],
        })

    n = len(per_case_metrics)
    return {
        "variant": variant_name,
        "config": config,
        "per_case": per_case_metrics,
        "aggregate": {
            "mean_rouge_l_f1": round(sum(m["rouge_l_f1"] for m in per_case_metrics) / n, 4),
            "ranking_accuracy_rate": round(sum(1 for m in per_case_metrics if m["ranking_accuracy"]) / n, 3),
            "mean_recommendation_quality": round(sum(m["recommendation_quality"] or 0 for m in per_case_metrics) / n, 2),
            "mean_latency_ms": round(sum(m["latency_ms"] for m in per_case_metrics) / n, 1),
            "mean_cost_usd": round(sum(m["cost_usd"] for m in per_case_metrics) / n, 6),
        },
    }


def run(variants: list[str] | None = None) -> dict:
    judge = LLMJudge()
    test_cases = _build_test_cases()
    targets = variants or list(REDUCER_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = REDUCER_VARIANTS[name]
        print(f"  Running reducer variant: {name} (temp={config['temperature']}, cot={config['chain_of_thought']})")
        all_results[name] = evaluate_variant(name, config, judge, test_cases)

    output_path = RESULTS_DIR / "reducer_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
