"""
Experiment: End-to-End Pipeline Evaluation on Static Corpus

Addresses the professor's feedback on reproducibility: live Firecrawl/SerpAPI/Google
Maps responses change daily and break comparison across runs. This experiment pins
every external call to static_listings.json so results are reproducible.

Approach:
  - For each preference in preferences.json, select candidate listings from
    static_listings.json that match the user's city (this mimics what the search
    + supervisor + listing_agent stages would surface in production).
  - Run the real reducer_node + analyzer_node (the "reduce" phase of the DAG) on
    those candidate profiles.
  - Score the output against preference_rankings.json (human-labeled gold) using:
      * ranking_alignment — normalized Kendall tau between predicted top-N order
        and human-ranked order (higher = better).
      * top1_accuracy — did the #1 ideal listing appear first in the response?
      * hard_constraint_violations — count of disqualified-by-ground-truth listings
        that were surfaced as recommendations.
      * recommendation_quality / trade_off_adherence — LLM-as-judge.
      * latency_ms, cost_usd — per-session wall time and token cost.

Variants:
  - baseline    : temperature=0.4 on reducer, analyzer enabled
  - low_temp    : temperature=0.1 on reducer
  - no_analyzer : skip analyzer stage (measures its marginal contribution)

Held constant:
  - Static listing corpus (evals/datasets/static_listings.json)
  - Human rankings (evals/datasets/preference_rankings.json)
  - Test preferences (evals/datasets/preferences.json — uses rows that have a ranking)
  - Reducer + analyzer prompts
  - Judge model: claude-sonnet-4-6
"""
import json
import itertools
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from evals.config import RESULTS_DIR, DATASETS_DIR, SONNET_MODEL, END_TO_END_VARIANTS
from evals.metrics.nlp import LatencyTimer
from evals.metrics.llm_judge import LLMJudge
from prompts.reducer_prompts import REDUCER_PROMPT
from prompts.analyzer_prompts import ANALYZER_PROMPT


COST_PER_M_INPUT = {SONNET_MODEL: 3.00}
COST_PER_M_OUTPUT = {SONNET_MODEL: 15.00}


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for block in content:
            if isinstance(block, dict):
                chunks.append(str(block.get("text", "")))
            else:
                chunks.append(str(block))
        return " ".join(chunks).strip()
    return str(content)


def _kendall_tau(predicted: list[str], gold: list[str]) -> float:
    """
    Normalized Kendall tau distance between two rankings.
    Only considers items present in `gold`. Returns a value in [-1, 1]; 1 is a
    perfect match, -1 is reversed. Items missing from `predicted` are treated
    as ranked after all predicted items.
    """
    if len(gold) < 2:
        return 1.0 if predicted[:1] == gold[:1] else 0.0

    # restrict predicted to items that exist in gold, preserving predicted order
    pred_restricted = [p for p in predicted if p in gold]
    # append any gold items missing from predicted to the end (penalty)
    for g in gold:
        if g not in pred_restricted:
            pred_restricted.append(g)

    pos_pred = {item: i for i, item in enumerate(pred_restricted)}
    pos_gold = {item: i for i, item in enumerate(gold)}

    concordant = discordant = 0
    for a, b in itertools.combinations(gold, 2):
        pred_order = pos_pred[a] - pos_pred[b]
        gold_order = pos_gold[a] - pos_gold[b]
        if pred_order * gold_order > 0:
            concordant += 1
        elif pred_order * gold_order < 0:
            discordant += 1
    total = concordant + discordant
    if total == 0:
        return 1.0
    return (concordant - discordant) / total


def _extract_listing_ids_from_response(response: str, listing_id_to_url: dict[str, str]) -> list[str]:
    """
    Scan the reducer response for listing URLs and return the corresponding IDs
    in the order they first appear. This is how we infer predicted ranking.
    """
    found = []
    for lid, url in listing_id_to_url.items():
        pos = response.find(url)
        if pos >= 0 and lid not in found:
            found.append((pos, lid))
    found.sort(key=lambda x: x[0])
    return [lid for _, lid in found]


def _select_candidate_profiles(
    preference: dict,
    static_listings: list[dict],
) -> list[dict]:
    """
    Mimic what the listing_agent stage would produce for this preference.
    Select listings matching city (loose match), with disqualified flag intact so
    the reducer receives a realistic mix of qualifying + disqualified profiles.
    """
    target_city = (preference.get("city") or "").lower()
    candidates = []
    for listing in static_listings:
        if listing.get("city", "").lower() == target_city:
            # Strip meta fields the reducer doesn't need / shouldn't see
            profile = {k: v for k, v in listing.items() if k not in ("id", "city")}
            candidates.append(profile)
    return candidates


async def _run_reducer_stage(
    preference: dict,
    candidate_profiles: list[dict],
    temperature: float,
) -> tuple[str, dict]:
    llm = ChatAnthropic(model=SONNET_MODEL, temperature=temperature)

    good = [p for p in candidate_profiles if not p.get("disqualified")]
    bad = [p for p in candidate_profiles if p.get("disqualified")]

    with LatencyTimer() as timer:
        resp = await llm.ainvoke([
            SystemMessage(content=REDUCER_PROMPT),
            HumanMessage(content=(
                f"User preferences:\n{json.dumps(preference, indent=2)}\n\n"
                f"Qualifying listings ({len(good)}):\n{json.dumps(good, indent=2)}\n\n"
                f"Disqualified listings ({len(bad)}):\n{json.dumps(bad, indent=2)}"
            )),
        ])

    input_t = getattr(resp, "usage_metadata", {}).get("input_tokens", 0)
    output_t = getattr(resp, "usage_metadata", {}).get("output_tokens", 0)
    cost = (
        input_t / 1_000_000 * COST_PER_M_INPUT[SONNET_MODEL]
        + output_t / 1_000_000 * COST_PER_M_OUTPUT[SONNET_MODEL]
    )
    return _content_to_text(resp.content), {
        "latency_ms": timer.elapsed_ms,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "cost_usd": round(cost, 6),
    }


async def _run_analyzer_stage(
    preference: dict,
    candidate_profiles: list[dict],
) -> tuple[str, dict]:
    llm = ChatAnthropic(model=SONNET_MODEL, temperature=0.3)
    good = [p for p in candidate_profiles if not p.get("disqualified")]
    bad = [p for p in candidate_profiles if p.get("disqualified")]

    with LatencyTimer() as timer:
        resp = await llm.ainvoke([
            SystemMessage(content=ANALYZER_PROMPT),
            HumanMessage(content=(
                f"User preferences:\n{json.dumps(preference, indent=2)}\n\n"
                f"Qualifying listings ({len(good)}):\n{json.dumps(good, indent=2)}\n\n"
                f"Disqualified listings ({len(bad)}):\n{json.dumps(bad, indent=2)}"
            )),
        ])

    input_t = getattr(resp, "usage_metadata", {}).get("input_tokens", 0)
    output_t = getattr(resp, "usage_metadata", {}).get("output_tokens", 0)
    cost = (
        input_t / 1_000_000 * COST_PER_M_INPUT[SONNET_MODEL]
        + output_t / 1_000_000 * COST_PER_M_OUTPUT[SONNET_MODEL]
    )
    return _content_to_text(resp.content), {
        "latency_ms": timer.elapsed_ms,
        "cost_usd": round(cost, 6),
    }


async def evaluate_variant_async(
    variant_name: str,
    config: dict,
    rankings: list[dict],
    preferences: list[dict],
    static_listings: list[dict],
    judge: LLMJudge,
) -> dict:
    prefs_by_id = {p["id"]: p for p in preferences}
    listing_by_id = {l["id"]: l for l in static_listings}
    id_to_url = {l["id"]: l["url"] for l in static_listings}

    per_case_metrics = []

    for ranking in rankings:
        pref_id = ranking["preference_id"]
        pref_row = prefs_by_id.get(pref_id)
        if not pref_row:
            continue
        preference = pref_row["expected_preferences"]
        gold_ranking = ranking["ranked_listing_ids"]
        gold_disqualified = set(ranking.get("disqualified_listing_ids", []))

        candidates = _select_candidate_profiles(preference, static_listings)

        reducer_response, reducer_usage = await _run_reducer_stage(
            preference, candidates, config["reducer_temperature"]
        )

        analyzer_response = ""
        analyzer_usage = {"latency_ms": 0, "cost_usd": 0.0}
        if config["analyzer_enabled"]:
            analyzer_response, analyzer_usage = await _run_analyzer_stage(preference, candidates)

        # Ranking alignment
        predicted_order = _extract_listing_ids_from_response(reducer_response, id_to_url)
        tau = _kendall_tau(predicted_order, gold_ranking)
        top1_correct = bool(predicted_order) and predicted_order[0] == gold_ranking[0]

        # Hard-constraint violations: did we recommend a ground-truth disqualified listing?
        violations = [lid for lid in predicted_order if lid in gold_disqualified]

        # LLM-as-judge quality and trade-off adherence
        rec_quality = judge.recommendation_quality(reducer_response, preference, candidates)
        trade_off_rules = preference.get("trade_off_rules", []) or []
        trade_off_score = (
            judge.trade_off_adherence(reducer_response, trade_off_rules, candidates)
            if trade_off_rules
            else {"score": None, "rationale": "No trade-off rules for this preference"}
        )

        per_case_metrics.append({
            "preference_id": pref_id,
            "predicted_order": predicted_order,
            "gold_order": gold_ranking,
            "kendall_tau": round(tau, 4),
            "top1_accuracy": top1_correct,
            "hard_constraint_violations": violations,
            "num_violations": len(violations),
            "recommendation_quality": rec_quality.get("score"),
            "rec_quality_rationale": rec_quality.get("rationale"),
            "trade_off_adherence": trade_off_score.get("score"),
            "trade_off_rationale": trade_off_score.get("rationale"),
            "reducer_latency_ms": reducer_usage["latency_ms"],
            "analyzer_latency_ms": analyzer_usage["latency_ms"],
            "total_latency_ms": round(reducer_usage["latency_ms"] + analyzer_usage["latency_ms"], 1),
            "total_cost_usd": round(reducer_usage["cost_usd"] + analyzer_usage["cost_usd"], 6),
            "response_preview": reducer_response[:400],
        })

    n = len(per_case_metrics)
    if n == 0:
        return {"variant": variant_name, "config": config, "per_case": [], "aggregate": {}}

    def mean(key):
        vals = [m[key] for m in per_case_metrics if m.get(key) is not None]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    return {
        "variant": variant_name,
        "config": config,
        "per_case": per_case_metrics,
        "aggregate": {
            "mean_kendall_tau": mean("kendall_tau"),
            "top1_accuracy_rate": round(sum(1 for m in per_case_metrics if m["top1_accuracy"]) / n, 3),
            "mean_hard_constraint_violations": round(sum(m["num_violations"] for m in per_case_metrics) / n, 3),
            "mean_recommendation_quality": mean("recommendation_quality"),
            "mean_trade_off_adherence": mean("trade_off_adherence"),
            "mean_latency_ms": round(sum(m["total_latency_ms"] for m in per_case_metrics) / n, 1),
            "mean_cost_usd": round(sum(m["total_cost_usd"] for m in per_case_metrics) / n, 6),
        },
    }


def run(variants: list[str] | None = None) -> dict:
    import asyncio

    preferences = json.loads((DATASETS_DIR / "preferences.json").read_text())
    static_listings = json.loads((DATASETS_DIR / "static_listings.json").read_text())
    rankings_file = json.loads((DATASETS_DIR / "preference_rankings.json").read_text())
    rankings = rankings_file["rankings"]

    judge = LLMJudge()
    targets = variants or list(END_TO_END_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = END_TO_END_VARIANTS[name]
        print(f"  Running end-to-end variant: {name} (temp={config['reducer_temperature']}, analyzer={config['analyzer_enabled']})")
        all_results[name] = asyncio.run(
            evaluate_variant_async(name, config, rankings, preferences, static_listings, judge)
        )

    output_path = RESULTS_DIR / "end_to_end_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
