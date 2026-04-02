"""
Experiment: Reducer Node — Final Ranking & Recommendation Quality

Variants compared:
  - baseline : Sonnet 4.6, temperature=0.4             (current production)
  - low_temp : Sonnet 4.6, temperature=0.1
  - cot      : Sonnet 4.6, temperature=0.4, chain-of-thought reasoning block

Held constant:
  - Input listing profiles (curated fixture profiles below)
  - User preferences (from datasets/preferences.json, pref_001 and pref_005)
  - Reducer prompt structure (mirrors prompts/reducer_prompts.py)

Metrics:
  - recommendation_quality : LLM judge (1-10) — preference alignment, actionability, tone
  - trade_off_adherence    : LLM judge (1-10) — explicit trade-off rules correctly applied
  - ranking_accuracy       : does best listing appear as #1? (binary, vs curated ideal ranking)
  - rouge_l                : ROUGE-L F1 vs a reference recommendation for each preference set
  - response_coherence     : LLM judge (1-10) — structure, completeness, no hallucination
  - latency_ms             : wall-clock time per reducer call
  - cost_usd               : token cost per call
"""
import json
from pathlib import Path
from anthropic import Anthropic

from evals.config import RESULTS_DIR, REDUCER_VARIANTS, DATASETS_DIR, SONNET_MODEL
from evals.metrics.nlp import LatencyTimer, rouge_l
from evals.metrics.llm_judge import LLMJudge

COST_PER_M_INPUT = {SONNET_MODEL: 3.00}
COST_PER_M_OUTPUT = {SONNET_MODEL: 15.00}

# ── Fixture listing profiles ──────────────────────────────────────────────────
# These represent what listing_agent_node would produce in production.
# Use pref_001 (SF, 2br, $3000 max, cat, commute to Salesforce Tower).

FIXTURE_PROFILES_PREF001 = [
    {
        "url": "https://sfbay.craigslist.org/sfc/apa/listing1",
        "disqualified": False,
        "price": 2750,
        "bedrooms": 2,
        "address": "South Beach, San Francisco",
        "pet_friendly": True,
        "pet_deposit": 500,
        "commute_times": {"Salesforce Tower": "8 min walk"},
        "modern_finishes": True,
        "natural_light": True,
        "spacious": False,
        "condition": "excellent",
        "notes": "New construction, floor-to-ceiling windows, steps from Salesforce Tower",
    },
    {
        "url": "https://www.zillow.com/homedetails/listing2",
        "disqualified": False,
        "price": 2400,
        "bedrooms": 2,
        "address": "Mission District, San Francisco",
        "pet_friendly": True,
        "pet_deposit": 300,
        "commute_times": {"Salesforce Tower": "22 min Muni"},
        "modern_finishes": False,
        "natural_light": True,
        "spacious": True,
        "condition": "good",
        "notes": "Victorian flat, large rooms, 2 cats welcome, longer commute",
    },
    {
        "url": "https://www.apartments.com/listing3",
        "disqualified": False,
        "price": 2950,
        "bedrooms": 2,
        "address": "SoMa, San Francisco",
        "pet_friendly": True,
        "pet_deposit": 600,
        "commute_times": {"Salesforce Tower": "12 min walk"},
        "modern_finishes": True,
        "natural_light": False,
        "spacious": True,
        "condition": "good",
        "notes": "Updated unit, dark windows face alley, pets ok up to 2",
    },
    {
        "url": "https://sfbay.craigslist.org/sfc/apa/listing4",
        "disqualified": True,
        "disqualify_reason": "No pets allowed",
        "price": 2100,
        "bedrooms": 2,
        "address": "Nob Hill, San Francisco",
        "pet_friendly": False,
    },
]

# Curated ideal ranking for pref_001 (by preference alignment):
# #1: listing1 (best commute, pet-ok, modern, within budget)
# #2: listing3 (close commute, spacious, pet-ok, near budget ceiling)
# #3: listing2 (affordable, spacious, pet-ok, but longer commute)
IDEAL_RANKING_PREF001 = [
    "https://sfbay.craigslist.org/sfc/apa/listing1",
    "https://www.apartments.com/listing3",
    "https://www.zillow.com/homedetails/listing2",
]

# Reference recommendation text (human-written baseline for ROUGE-L)
REFERENCE_RESPONSE_PREF001 = """Here are the top apartments I found for you in San Francisco:

**#1 — South Beach, $2,750/mo** ([listing link](https://sfbay.craigslist.org/sfc/apa/listing1))
Only an 8-minute walk to Salesforce Tower, cats welcome ($500 deposit), new construction with great natural light. Best commute of the bunch.

**#2 — SoMa, $2,950/mo** ([listing link](https://www.apartments.com/listing3))
12-minute walk to your office, spacious layout, pets allowed (up to 2). The windows face an alley so natural light is limited — worth a visit to check in person.

**#3 — Mission District, $2,400/mo** ([listing link](https://www.zillow.com/homedetails/listing2))
Most affordable option with large rooms and great light. The 22-minute Muni commute is the main trade-off here. Good choice if budget is the priority.

One listing in Nob Hill was excluded — no pets allowed.
"""

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


# ── Test cases ────────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "id": "tc_pref001",
        "preferences_id": "pref_001",
        "preferences": {
            "city": "San Francisco", "bedrooms": 2, "max_price": 3000,
            "pet_friendly": True,
            "commute_destinations": ["Salesforce Tower, San Francisco"],
            "soft_constraints": ["pet-friendly", "good commute"],
            "trade_off_rules": [],
        },
        "listing_profiles": FIXTURE_PROFILES_PREF001,
        "ideal_ranking": IDEAL_RANKING_PREF001,
        "reference_response": REFERENCE_RESPONSE_PREF001,
    }
]


def evaluate_variant(variant_name: str, config: dict, judge: LLMJudge) -> dict:
    client = Anthropic()
    per_case_metrics = []

    for tc in TEST_CASES:
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
    targets = variants or list(REDUCER_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = REDUCER_VARIANTS[name]
        print(f"  Running reducer variant: {name} (temp={config['temperature']}, cot={config['chain_of_thought']})")
        all_results[name] = evaluate_variant(name, config, judge)

    output_path = RESULTS_DIR / "reducer_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
