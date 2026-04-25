"""
Experiment: Listing Agent (ReAct) — Data Extraction & Tool Selection

Variants compared:
  - sonnet_conditional : Sonnet 4.6, preference-driven tool use  (current production)
  - haiku_conditional  : Haiku 4.5, preference-driven tool use
  - sonnet_all_tools   : Sonnet 4.6, always call every available tool

Held constant:
  - Listing URLs and preferences (from datasets/listings.json)
  - Tool prompt template (replicated from prompts/listing_agent_prompts.py)
  - Available tools: scraper, analyze_listing_photos, search_web
    (commute and places tools are stubs — excluded from this eval)
  - Structured JSON output format

Metrics:
  - field_accuracy          : F1 for price, bedrooms, address vs ground truth
  - disqualification_accuracy: correct disqualification decision (precision, recall, F1)
  - tool_efficiency         : avg # tool calls per listing
  - profile_completeness    : % non-null fields in returned profile
  - judge_quality_score     : LLM judge (1-10) on profile accuracy and usefulness
  - latency_ms              : wall-clock time per listing agent run
  - cost_usd                : estimated token cost per listing
"""
import json
from anthropic import Anthropic

from evals.config import RESULTS_DIR, LISTING_AGENT_VARIANTS, DATASETS_DIR, SONNET_MODEL, HAIKU_MODEL
from evals.metrics.nlp import LatencyTimer, field_f1
from evals.metrics.llm_judge import LLMJudge

COST_PER_M_INPUT = {SONNET_MODEL: 3.00, HAIKU_MODEL: 0.80}
COST_PER_M_OUTPUT = {SONNET_MODEL: 15.00, HAIKU_MODEL: 4.00}

# Simplified listing agent prompt (mirrors listing_agent_prompts.py)
LISTING_AGENT_SYSTEM = """You are researching a rental listing. Your job:
1. Scrape the listing page (always do this first)
2. Check hard requirements immediately and disqualify if violated
3. Only call optional tools if the user explicitly needs them:
   - analyze_listing_photos: only if user wants photo analysis
   - search_web: fallback for critical missing data

Return ONLY valid JSON with these fields (null if unknown):
{{
  "url": "<string>",
  "disqualified": <true|false>,
  "disqualify_reason": <string|null>,
  "price": <int|null>,
  "bedrooms": <int|null>,
  "address": <string|null>,
  "pet_friendly": <bool|null>,
  "pet_deposit": <int|null>,
  "furnishing": <string|null>,
  "images": <list of urls>,
  "modern_finishes": <bool|null>,
  "natural_light": <bool|null>,
  "spacious": <bool|null>,
  "condition": <string|null>,
  "notes": <string|null>
}}

User preferences: {preferences}
URL to research: {url}

IMPORTANT: You do not have real tool access in this eval.
Based on the preferences and URL provided, reason through what data you would extract
and simulate a realistic profile output. Make the output consistent with what a
Firecrawl scrape of a real listing would return."""


def simulate_listing_agent(
    url: str,
    preferences: dict,
    ground_truth: dict,
    model: str,
    always_use_all_tools: bool,
    client: Anthropic,
) -> tuple[dict, dict]:
    """
    Run the listing agent (simulated — uses Claude to reason about what the agent would return).

    In production, swap this for the actual graph/nodes/listing_agent.py invocation.
    """
    tool_hint = ""
    if always_use_all_tools:
        tool_hint = "\nUse all available tools regardless of user preferences."
    else:
        # Add conditional tool hints based on preferences
        if preferences.get("pet_friendly"):
            tool_hint += "\nCheck pet policy (user has pets — hard requirement)."
        if preferences.get("commute_destinations"):
            tool_hint += "\nCalculate commute times for: " + ", ".join(preferences["commute_destinations"])
        tool_hint += "\nAnalyze listing photos for: natural_light, modern_finishes."

    prompt = LISTING_AGENT_SYSTEM.format(
        preferences=json.dumps(preferences, indent=2),
        url=url,
    ) + tool_hint

    with LatencyTimer() as timer:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

    raw = resp.content[0].text.strip()
    try:
        profile = json.loads(raw)
    except json.JSONDecodeError:
        s, e = raw.find("{"), raw.rfind("}") + 1
        profile = json.loads(raw[s:e]) if s != -1 and e > s else {"url": url, "disqualified": False}

    # Estimate tool calls (heuristic based on model output fields populated)
    tool_calls = 1  # always scrapes
    if profile.get("modern_finishes") is not None:
        tool_calls += 1  # photo analysis
    if profile.get("commute_times"):
        tool_calls += len(profile.get("commute_times", {}))
    if always_use_all_tools:
        tool_calls = 4  # forced maximum

    input_t = resp.usage.input_tokens
    output_t = resp.usage.output_tokens
    cost = (
        input_t / 1_000_000 * COST_PER_M_INPUT.get(model, 3.0)
        + output_t / 1_000_000 * COST_PER_M_OUTPUT.get(model, 15.0)
    )

    usage = {
        "latency_ms": timer.elapsed_ms,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "cost_usd": round(cost, 6),
        "estimated_tool_calls": tool_calls,
    }
    return profile, usage


def profile_completeness(profile: dict) -> float:
    """% of non-null fields in profile (excluding url)."""
    fields = [k for k in profile if k != "url"]
    if not fields:
        return 0.0
    non_null = sum(1 for k in fields if profile[k] is not None)
    return round(non_null / len(fields), 3)


def disqualification_metrics(profiles_and_truths: list[tuple[dict, bool]]) -> dict:
    """Precision, recall, F1 for disqualification decisions."""
    tp = fp = tn = fn = 0
    for profile, gt_disq in profiles_and_truths:
        pred_disq = profile.get("disqualified", False)
        if pred_disq and gt_disq:
            tp += 1
        elif pred_disq and not gt_disq:
            fp += 1
        elif not pred_disq and gt_disq:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }


def evaluate_variant(
    variant_name: str,
    config: dict,
    listings: list[dict],
    all_preferences: list[dict],
    judge: LLMJudge,
) -> dict:
    client = Anthropic()
    prefs_by_id = {p["id"]: p["expected_preferences"] for p in all_preferences}

    per_listing_metrics = []
    disq_pairs = []

    for listing in listings:
        url = listing["url"]
        gt = listing["ground_truth"]
        pref_id = listing["preferences_used"]
        prefs = prefs_by_id.get(pref_id, {})

        profile, usage = simulate_listing_agent(
            url, prefs, gt, config["model"], config["always_use_all_tools"], client
        )

        # Field-level F1 for extractable fields
        extractable_gt = {k: v for k, v in gt.items() if k in ("price", "bedrooms", "address", "pet_friendly")}
        f1_result = field_f1(profile, extractable_gt)

        # Disqualification tracking
        disq_pairs.append((profile, gt.get("disqualified", False)))

        # Judge quality
        quality = judge.listing_profile_quality(profile, prefs)

        completeness = profile_completeness(profile)

        per_listing_metrics.append({
            "listing_id": listing["id"],
            "url": url,
            "field_accuracy_f1": f1_result["micro_f1"],
            "per_field_f1": f1_result["per_field"],
            "profile_completeness": completeness,
            "judge_quality_score": quality.get("score"),
            "judge_rationale": quality.get("rationale"),
            "estimated_tool_calls": usage["estimated_tool_calls"],
            "latency_ms": usage["latency_ms"],
            "cost_usd": usage["cost_usd"],
            "predicted_disqualified": profile.get("disqualified"),
            "ground_truth_disqualified": gt.get("disqualified"),
        })

    disq_metrics = disqualification_metrics(disq_pairs)
    n = len(per_listing_metrics)

    return {
        "variant": variant_name,
        "config": config,
        "per_listing": per_listing_metrics,
        "disqualification": disq_metrics,
        "aggregate": {
            "mean_field_accuracy_f1": round(sum(m["field_accuracy_f1"] for m in per_listing_metrics) / n, 3),
            "mean_profile_completeness": round(sum(m["profile_completeness"] for m in per_listing_metrics) / n, 3),
            "mean_judge_quality": round(sum(m["judge_quality_score"] or 0 for m in per_listing_metrics) / n, 2),
            "mean_tool_calls": round(sum(m["estimated_tool_calls"] for m in per_listing_metrics) / n, 2),
            "mean_latency_ms": round(sum(m["latency_ms"] for m in per_listing_metrics) / n, 1),
            "mean_cost_usd": round(sum(m["cost_usd"] for m in per_listing_metrics) / n, 6),
            "disqualification_f1": disq_metrics["f1"],
        },
    }


def run(variants: list[str] | None = None) -> dict:
    listings = json.loads((DATASETS_DIR / "listings.json").read_text())
    all_prefs = json.loads((DATASETS_DIR / "preferences.json").read_text())
    judge = LLMJudge()
    targets = variants or list(LISTING_AGENT_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = LISTING_AGENT_VARIANTS[name]
        print(f"  Running listing agent variant: {name} (model={config['model']}, all_tools={config['always_use_all_tools']})")
        all_results[name] = evaluate_variant(name, config, listings, all_prefs, judge)

    output_path = RESULTS_DIR / "listing_agent_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
