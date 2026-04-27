# Rental Market Analyzer — Evaluation Suite

This directory contains the evaluation suite for the Rental Market Analyzer agent. It mixes **component-level experiments** (one per major pipeline node) with an **end-to-end experiment** on a static corpus for reproducibility.

## Experiments

Eight experiments cover the full pipeline, each targeting one node:

- **`elicitation`** — Does the intake agent correctly extract hard and soft constraints (budget, pet policy, commute destinations) from a chatty user message?
- **`planner`** — Are the generated search queries diverse, correctly formatted, and free of repetition across retry rounds?
- **`search`** — Do the Google search results actually point to real apartment listings rather than blog posts or homepages?
- **`listing_agent`** — Can the sub-agent correctly extract rent, bedrooms, commute times, and pet policy from a scraped listing page, and does it disqualify listings that violate hard constraints?
- **`image`** — Does the agent correctly identify apartment features (modern finishes, natural light, spaciousness) from listing photos?
- **`reducer`** — Does the agent rank listings in the right order given the user's preferences and trade-off rules?
- **`bias`** — Does the system treat different demographics identically, or does it hallucinate different constraints for different persona types?
- **`end_to_end`** — Does the full pipeline produce rankings that align with a human expert's gold-standard ordering?

## Datasets

**`datasets/preferences.json`** contains 10 preference sets with a `"split"` field:

- **Validation** (`pref_001`–`pref_005`) — used during prompt tuning. Base all prompt and model decisions on these.
- **Test** (`pref_006`–`pref_010`) — held out for final reporting. Do not iterate against these to avoid overfitting.

**`datasets/static_listings.json`** is a fixed snapshot of 30 apartment profiles across SF, Oakland, and Chicago. Every field matches what a production `listing_agent_node` returns (price, bedrooms, pet policy, commute times, nearby places, photo-analysis flags, disqualified flag). Pinning to a static corpus is what makes the end-to-end experiment reproducible — live Firecrawl/SerpAPI responses change daily.

**`datasets/preference_rankings.json`** contains human-ranked ideal orderings for 5 preference sets, used as gold labels for the end-to-end ranking metrics.

**`datasets/bias_personas.json`** contains 3 counterfactual persona pairs (e.g. retail worker vs. software engineer) with identical hard constraints, used to test for demographic bias in preference extraction.

## LLM-as-judge

All judges use `claude-sonnet-4-6` (defined as `JUDGE_MODEL` in `config.py`). Every rubric lives in `metrics/llm_judge.py`. Each judge returns a `{score, rationale}` pair.

## Reducer ranking priority

When ranking listings, the reducer applies preferences in this order:

1. **Hard constraints** — exclude any listing that is disqualified or violates budget, bedroom count, or pet policy
2. **Soft constraints** — listings that satisfy more of the user's soft constraints rank higher
3. **Trade-off rules** — apply explicit user trade-offs against real numbers in the profiles (e.g. "willing to pay $200 more if commute < 15 min")
4. **Commute tiebreaker** — when soft constraints are tied, prefer shorter total commute to stated destinations
5. **Price** — last resort tiebreaker only

## Running evaluations

Ensure `.env` has valid API keys (`ANTHROPIC_API_KEY`, `SERPAPI_API_KEY`, `FIRECRAWL_API_KEY`, `GOOGLE_MAPS_API_KEY`). The end-to-end experiment only needs `ANTHROPIC_API_KEY` since it uses the static corpus.

```bash
# Run everything
python -m evals.run_evals

# Run a single experiment
python -m evals.run_evals --experiments end_to_end

# Run specific variants within an experiment
python -m evals.run_evals --experiments reducer --variants baseline low_temp

# Slim mode — fewer samples, useful for smoke-testing
python -m evals.run_evals --slim
```

Results are saved to `results/<experiment>_eval.json` per experiment, and merged into `results/summary.json`.

## Running evals against real session logs

The static datasets are hand-crafted fixtures designed for reproducibility. To validate against data from actual user sessions, use the log capture pipeline:

**Step 1 — Capture real sessions**

Start the app with `LOG_SESSIONS=true` to write one JSON file per session to `logs/sessions/`:

```bash
LOG_SESSIONS=true uvicorn server:app --reload --port 8000
```

Run a few real searches through the app. Each completed session will be written to `logs/sessions/<session_id>.json` with the full preference profile and listing_agent outputs in their production schema.

**Step 2 — Build eval datasets from logs**

```bash
# Convert all captured sessions
python -m scripts.build_eval_dataset

# Or point at specific session files
python -m scripts.build_eval_dataset --sessions logs/sessions/abc123.json logs/sessions/def456.json

# Custom output paths
python -m scripts.build_eval_dataset \
  --out-listings evals/datasets/real_static_listings.json \
  --out-preferences evals/datasets/real_preferences.json
```

This produces `evals/datasets/real_static_listings.json` and `evals/datasets/real_preferences.json` in the same schema as the static fixtures, so they can be dropped in as replacements.

> **Note:** `logs/` is in `.gitignore`. Real session logs may contain user queries and actual listing URLs — do not commit them.

## Results

### Image analysis

All three variants achieve perfect field accuracy (F1 = 1.0) and condition detection across repeated runs. Haiku at 5 images is 2× faster and 4× cheaper than Sonnet with identical accuracy — preferred for production.

| Variant | Field F1 | Consistency (1–10) | Quality (1–10) | Latency | Cost |
|---|---|---|---|---|---|
| sonnet_5img | 1.0 | 10.0 | 9.0 | 3253ms | $0.0053 |
| haiku_5img | 1.0 | 9.0 | 9.0 | 1750ms | $0.0014 |
| sonnet_3img | 1.0 | 10.0 | 9.0 | 3363ms | $0.0053 |

### Search (web discovery)

`expanded_10` is the strongest variant — highest listing precision (0.44), best query relevance (5.8/10), and paradoxically the lowest latency. The `hotpads.com` site operator consistently returns 0–1 results across all variants and should be removed from the query set.

| Variant | Listing precision | Query relevance | Yield rate | Latency |
|---|---|---|---|---|
| baseline_5 | 0.36 | 4.4/10 | 60% | 1745ms |
| reduced_3 | 0.33 | 4.0/10 | 40% | 313ms |
| expanded_10 | 0.44 | 5.8/10 | 60% | 123ms |

> **Listing precision** = % of returned URLs that are actual apartment listings (not homepages or articles). **Yield rate** = % of queries that returned at least one valid listing.

### Elicitation (preference extraction)

All three model combinations achieve identical extraction F1 (0.651) and completeness (0.916), and every session reaches `ready` in a single turn. The F1 ceiling is caused by `soft_constraints` and `commute_destinations`, which are genuinely hard to infer from terse single-message inputs — not a model quality gap. Haiku+Sonnet is the most cost-efficient configuration.

| Variant | Extraction F1 | Completeness | Turns to ready | Latency |
|---|---|---|---|---|
| haiku_sonnet | 0.651 | 0.916 | 1 | 1867ms |
| haiku_haiku | 0.651 | 0.916 | 1 | 2100ms |
| sonnet_sonnet | 0.651 | 0.916 | 1 | 2218ms |

### Planner (query generation)

All variants parse successfully (100% parse rate). `few_shot` achieves the highest query diversity (0.616) and zero repetition on retry, at the cost of ~50% more tokens and latency. Format validity plateaus at 0.75 across all variants — one query per batch consistently fails the format check, suggesting a structural prompt issue worth investigating.

| Variant | Format validity | Query diversity | No-repeat on retry | Latency |
|---|---|---|---|---|
| baseline | 0.75 | 0.540 | 87.5% | 4421ms |
| low_temp | 0.75 | 0.526 | 100% | 4046ms |
| few_shot | 0.75 | 0.616 | 100% | 6368ms |

### Listing agent (data extraction)

`sonnet_conditional` leads on field accuracy and completeness. `sonnet_all_tools` — which always calls every available tool regardless of need — performs worse on accuracy while using 4× more tool calls, confirming that selective tool use is strictly better. Disqualification F1 of 0.5 is consistent across all variants and represents the clearest area for improvement.

| Variant | Field F1 | Completeness | Judge quality | Avg tool calls | Latency | Cost |
|---|---|---|---|---|---|---|
| sonnet_conditional | 0.703 | 0.875 | 8.5/10 | 1.75 | 9203ms | $0.0093 |
| haiku_conditional | 0.680 | 0.715 | 7.75/10 | 1.5 | 4374ms | $0.0023 |
| sonnet_all_tools | 0.455 | 0.679 | 8.25/10 | 4.0 | 7636ms | $0.0077 |

### Reducer (ranking)

All three variants achieve 100% ranking accuracy and zero hard-constraint violations. `low_temp` and `cot` both score 9.0/10 on judge quality. ROUGE-L scores are low across the board (0.04–0.07), but that metric is a poor fit for ranking tasks where response wording varies freely — the LLM judge quality scores are the relevant signal here.

| Variant | Ranking accuracy | Judge quality | Latency |
|---|---|---|---|
| baseline | 100% | 8.5/10 | 11.1s |
| low_temp | 100% | 9.0/10 | 14.3s |
| cot | 100% | 9.0/10 | 11.6s |

### End-to-end pipeline

Kendall tau of 0.467 reflects moderate rank correlation with human gold rankings across 5 test cases. Top-1 accuracy is 80% (4/5 cases correct). Zero hard-constraint violations across all variants. `no_analyzer` cuts cost and latency in half with only a small tau drop (0.467 → 0.427), suggesting the analyzer stage contributes little to ranking quality and may not be worth its cost.

| Variant | Kendall tau | Top-1 accuracy | Violations | Latency | Cost/session |
|---|---|---|---|---|---|
| baseline | 0.467 | 80% | 0 | 24.5s | $0.031 |
| low_temp | 0.467 | 80% | 0 | 36.0s | $0.031 |
| no_analyzer | 0.427 | 80% | 0 | 14.6s | $0.016 |

### Bias and fairness

The model extracted identical hard constraints (city, bedrooms, price, pet policy, soft constraints) across all three counterfactual persona pairs. Demographic markers appear only in `lifestyle_notes`, which is the correct behavior — they should inform tone, not alter constraint extraction.

| Case | Persona pair | Discrepancy found |
|---|---|---|
| bias_001 | Retail worker vs. software engineer | None |
| bias_002 | Single mother vs. single professional | None |
| bias_003 | Wichita, KS vs. San Francisco, CA | None |

**discrepancy_rate: 0.0 — all 3 cases fair.**
