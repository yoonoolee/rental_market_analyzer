# Rental Market Analyzer Evaluations

This directory contains the evaluation suite for the Rental Market Analyzer agent. It mixes **component-level experiments** (one per major node) with an **end-to-end experiment** on a static corpus for reproducibility.

## Overview

The evaluation suite tests individual nodes and the full pipeline. Available experiments:

- `search`       — SerpAPI URL discovery and search query logic
- `image`        — vision analysis of listing photos
- `elicitation`  — preference extraction and clarifying-question quality
- `planner`      — search query generation
- `listing_agent`— ReAct agents that research specific listings (tool selection + extraction)
- `reducer`      — final ranking and trade-off analysis
- `end_to_end`   — **full-pipeline evaluation on a static corpus** (reproducible across runs)

## Dataset split (validation / test)

`datasets/preferences.json` is explicitly split via a `"split"` field on each row:

- **Validation** (5 rows: `pref_001` … `pref_005`) — used during prompt tuning. Shape decisions about prompts/models should be based on these.
- **Test** (5 rows: `pref_006` … `pref_010`) — held out for final reporting. Avoid iterating against these to prevent overfitting.

`datasets/static_listings.json` is a fixed snapshot of 30 apartment profiles across SF, Oakland, and Chicago. Every field matches what a production `listing_agent_node` would return (price, bedrooms, address, pet policy, commute_times, nearby_places, photo-analysis fields, disqualified flag, etc.). This corpus is the reason the end-to-end experiment is reproducible — live Firecrawl/SerpAPI/Google Maps responses change daily and would otherwise break comparison across runs.

`datasets/preference_rankings.json` contains human-ranked ideal orderings for 5 preference-to-listing sets. Used by the end-to-end experiment for ranking alignment metrics.

## LLM-as-judge model and rubric

All judges run on **`claude-sonnet-4-6`** (defined as `JUDGE_MODEL` in `config.py`). Every judge rubric lives in `metrics/llm_judge.py` — each method has a system prompt that defines scoring criteria (score range, what earns high vs low). Scores are always `{score: 0-1 or 1-10, rationale: str}`.

## How the evals validate the system

1. **Adherence to constraints** — planner and listing agents respect hard constraints (budget caps, pet policy, etc.).
2. **Preference extraction accuracy** — elicitation correctly parses hard + soft constraints from raw text (field-level F1).
3. **Tool selection accuracy** — listing agent invokes expensive APIs only when warranted.
4. **Ranking quality** — reducer applies trade-offs, disqualifies dealbreakers, boosts soft-constraint matches. Measured via ROUGE-L, top-1 accuracy, and LLM judge.
5. **End-to-end pipeline** — the full graph produces rankings aligned with human gold-standard rankings (Kendall tau), doesn't surface disqualified listings (hard-constraint violation rate), and stays within reasonable latency and cost.
6. **Efficiency** — tokens and latency tracked across variants to catch prompt/architecture regressions.

## Running evaluations

Ensure `.env` has valid API keys (`ANTHROPIC_API_KEY`, `SERPAPI_API_KEY`, `FIRECRAWL_API_KEY`, `GOOGLE_MAPS_API_KEY` for live tools — the end-to-end experiment only needs `ANTHROPIC_API_KEY` since it uses the static corpus).

### Terminal

```bash
# Run everything
python -m evals.run_evals

# Run one experiment (the end-to-end pipeline eval)
python -m evals.run_evals --experiments end_to_end

# Specific variants across selected experiments
python -m evals.run_evals --experiments reducer --variants baseline low_temp
python -m evals.run_evals --experiments end_to_end --variants baseline
```

### Chainlit front-end

With the app running (`chainlit run app.py -w`), type `/evals` in the chat. The full suite runs in the background; a markdown summary renders when complete.

## Results

- Per-experiment: `results/<experiment>_eval.json`
- Combined summary: `results/summary.json`

## End-to-end experiment details

`eval_end_to_end.py` is the experiment that addresses reproducibility directly:

1. For each preference in `preferences.json` that has a gold ranking in `preference_rankings.json`, candidate listings are selected from `static_listings.json` by city match.
2. The real `reducer_node` and `analyzer_node` are run against these profiles (no live APIs).
3. Metrics:
   - **Kendall tau** — normalized rank correlation against human-labeled order.
   - **Top-1 accuracy** — did the #1 gold listing appear first?
   - **Hard-constraint violations** — recommending a ground-truth-disqualified listing.
   - **LLM-judge** recommendation quality and trade-off adherence.
   - Latency and cost per session.

Variants compared: `baseline` (temp=0.4, analyzer on), `low_temp` (temp=0.1), `no_analyzer` (measures analyzer's marginal contribution).

### Example summary

```json
{
  "end_to_end": {
    "baseline": {
      "aggregate": {
        "mean_kendall_tau": 0.67,
        "top1_accuracy_rate": 0.8,
        "mean_hard_constraint_violations": 0.0,
        "mean_recommendation_quality": 8.2,
        "mean_trade_off_adherence": 7.8
      }
    }
  }
}
```
