"""
Experiment: Planner Node — Search Query Generation

Variants compared:
  - baseline : temperature=0.2, no few-shot  (current production)
  - low_temp : temperature=0.0, no few-shot
  - few_shot  : temperature=0.2, with few-shot examples

Held constant:
  - Input preference sets (from datasets/preferences.json, pref_001 and pref_005)
  - Model: Claude Sonnet 4.6
  - Required output format: JSON {"search_queries": [...]}
  - Site operators: craigslist, zillow, apartments, trulia, hotpads

Metrics:
  - format_validity       : % queries containing site:, location, bedrooms, price (rule-based + LLM judge)
  - query_diversity       : avg pairwise embedding distance within one batch (higher = less redundant)
  - no_repetition_on_retry: % of retry queries that are genuinely new vs. first-round queries
  - parse_success_rate    : % of LLM outputs that produce valid JSON without fallback
  - latency_ms            : wall-clock time per planner call
  - token_cost            : input+output tokens per call
"""
import json
import re
import itertools
from pathlib import Path
from anthropic import Anthropic

from evals.config import RESULTS_DIR, PLANNER_VARIANTS, DATASETS_DIR, SONNET_MODEL
from evals.metrics.nlp import LatencyTimer, embedding_similarity
from evals.metrics.llm_judge import LLMJudge

REQUIRED_SITE_OPERATORS = [
    "craigslist.org", "zillow.com", "apartments.com", "trulia.com", "hotpads.com"
]

FEW_SHOT_EXAMPLES = """
Example 1 — Chicago, 2br, $1800-$2400:
{"search_queries": [
  "2 bedroom apartment Chicago $1800 $2400 site:craigslist.org",
  "2br apartment Chicago under $2400 site:zillow.com inurl:homedetails",
  "2 bedroom apartment Chicago Wicker Park Logan Square site:apartments.com",
  "2 bedroom Chicago $2000 $2400 transit site:trulia.com",
  "2br Chicago Lincoln Park Lakeview $1800 $2400 site:hotpads.com"
]}

Example 2 — Seattle, 2br, under $2200:
{"search_queries": [
  "2 bedroom apartment Seattle under $2200 site:craigslist.org",
  "2br Seattle Capitol Hill Queen Anne $2200 site:zillow.com inurl:homedetails",
  "2 bedroom apartment Seattle with parking under $2200 site:apartments.com",
  "2br Seattle $1800 $2200 near downtown site:trulia.com",
  "2 bedroom Seattle Fremont Ballard under $2200 site:hotpads.com"
]}
"""

BASE_PLANNER_PROMPT = """Generate search queries to find rental listing URLs matching these preferences.
Target these sites with site: operators: craigslist.org, zillow.com, apartments.com, trulia.com, hotpads.com.

RULES:
- Include bedroom count, price range, and city in every query
- Use site: operator in every query
- Generate 5-8 diverse queries covering different neighborhoods and sites
- Return ONLY valid JSON: {{"search_queries": [...]}}

User preferences:
{preferences}
{few_shot_block}
Previous queries (avoid repeating these):
{previous_queries}"""


def build_planner_prompt(preferences: dict, use_few_shot: bool, previous_queries: list[str]) -> str:
    few_shot_block = f"\n\nExamples of good queries:\n{FEW_SHOT_EXAMPLES}" if use_few_shot else ""
    prev = json.dumps(previous_queries) if previous_queries else "[]"
    return BASE_PLANNER_PROMPT.format(
        preferences=json.dumps(preferences, indent=2),
        few_shot_block=few_shot_block,
        previous_queries=prev,
    )


def run_planner(
    preferences: dict,
    temperature: float,
    use_few_shot: bool,
    previous_queries: list[str],
    client: Anthropic,
) -> tuple[list[str], dict]:
    prompt = build_planner_prompt(preferences, use_few_shot, previous_queries)

    with LatencyTimer() as timer:
        resp = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=1024,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

    raw = resp.content[0].text.strip()
    parse_success = True
    try:
        parsed = json.loads(raw)
        queries = parsed.get("search_queries", [])
    except json.JSONDecodeError:
        parse_success = False
        # Fallback: extract quoted strings
        queries = re.findall(r'"([^"]+site:[^"]+)"', raw)
        if not queries:
            city = preferences.get("city", "city")
            beds = preferences.get("bedrooms", 1)
            price = preferences.get("max_price", 3000)
            queries = [f"{beds} bedroom apartment {city} under ${price} site:craigslist.org"]

    usage = {
        "latency_ms": timer.elapsed_ms,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "parse_success": parse_success,
    }
    return queries, usage


def check_format_validity(query: str, preferences: dict) -> dict:
    """Rule-based format check (fast, no API call)."""
    has_site = any(op in query for op in REQUIRED_SITE_OPERATORS)
    city = (preferences.get("city") or "").lower()
    city_words = city.split()
    has_location = any(w in query.lower() for w in city_words) if city_words else False
    has_bedrooms = bool(re.search(r'\d\s*(br|bed|bedroom)', query, re.I))
    has_price = bool(re.search(r'\$[\d,]+|\d{3,4}\s*\$?/mo', query, re.I))
    score = sum([has_site, has_location, has_bedrooms, has_price]) / 4
    return {
        "has_site_operator": has_site,
        "has_location": has_location,
        "has_bedrooms": has_bedrooms,
        "has_price": has_price,
        "validity_score": round(score, 2),
    }


def pairwise_diversity(queries: list[str]) -> float:
    """Average pairwise embedding distance (1 - cosine_sim). Higher = more diverse."""
    if len(queries) < 2:
        return 0.0
    pairs = list(itertools.combinations(queries, 2))
    distances = [1.0 - embedding_similarity(a, b) for a, b in pairs]
    return round(sum(distances) / len(distances), 4)


def evaluate_variant(
    variant_name: str, config: dict, test_preferences: list[dict], judge: LLMJudge
) -> dict:
    client = Anthropic()
    per_pref_metrics = []

    for prefs in test_preferences:
        # Round 1: fresh queries
        queries_r1, usage_r1 = run_planner(
            prefs, config["temperature"], config["use_few_shot"], [], client
        )

        # Round 2: retry (simulate retrying after insufficient results)
        queries_r2, usage_r2 = run_planner(
            prefs, config["temperature"], config["use_few_shot"], queries_r1, client
        )

        # Format validity for all round-1 queries
        validity_results = [check_format_validity(q, prefs) for q in queries_r1]
        mean_validity = sum(r["validity_score"] for r in validity_results) / len(validity_results) if validity_results else 0

        # Query diversity within round 1
        diversity = pairwise_diversity(queries_r1)

        # No-repetition on retry: % of r2 queries not in r1
        r1_lower = set(q.lower() for q in queries_r1)
        no_repeat_rate = (
            sum(1 for q in queries_r2 if q.lower() not in r1_lower) / len(queries_r2)
            if queries_r2 else 0.0
        )

        # LLM judge format validity for a sample query
        sample_query = queries_r1[0] if queries_r1 else ""
        judge_validity = judge.query_format_validity(sample_query, prefs)

        per_pref_metrics.append({
            "preferences_id": prefs.get("id", "unknown"),
            "num_queries_r1": len(queries_r1),
            "mean_format_validity": round(mean_validity, 3),
            "query_diversity": diversity,
            "no_repetition_rate": round(no_repeat_rate, 3),
            "parse_success_r1": usage_r1["parse_success"],
            "parse_success_r2": usage_r2["parse_success"],
            "judge_validity_score": judge_validity.get("score"),
            "latency_ms_r1": usage_r1["latency_ms"],
            "total_tokens_r1": usage_r1["input_tokens"] + usage_r1["output_tokens"],
            "sample_queries_r1": queries_r1[:3],
            "sample_queries_r2": queries_r2[:3],
        })

    n = len(per_pref_metrics)
    return {
        "variant": variant_name,
        "config": config,
        "per_preference": per_pref_metrics,
        "aggregate": {
            "mean_format_validity": round(sum(m["mean_format_validity"] for m in per_pref_metrics) / n, 3),
            "mean_query_diversity": round(sum(m["query_diversity"] for m in per_pref_metrics) / n, 4),
            "mean_no_repetition_rate": round(sum(m["no_repetition_rate"] for m in per_pref_metrics) / n, 3),
            "parse_success_rate": round(sum(1 for m in per_pref_metrics if m["parse_success_r1"]) / n, 3),
            "mean_latency_ms": round(sum(m["latency_ms_r1"] for m in per_pref_metrics) / n, 1),
            "mean_tokens": round(sum(m["total_tokens_r1"] for m in per_pref_metrics) / n),
        },
    }


def run(variants: list[str] | None = None) -> dict:
    all_prefs = json.loads((DATASETS_DIR / "preferences.json").read_text())
    # Use a subset with clear requirements for planner eval
    test_prefs = [p for p in all_prefs if p["id"] in ("pref_001", "pref_005")]
    judge = LLMJudge()
    targets = variants or list(PLANNER_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = PLANNER_VARIANTS[name]
        print(f"  Running planner variant: {name} (temp={config['temperature']}, few_shot={config['use_few_shot']})")
        all_results[name] = evaluate_variant(name, config, test_prefs, judge)

    output_path = RESULTS_DIR / "planner_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
