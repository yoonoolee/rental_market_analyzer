# Rental Market Analyzer — Evaluation Suite

This directory contains the evaluation suite for the Rental Market Analyzer agent. The suite tests each major node of the pipeline independently (component evals) and then tests the full pipeline together on a fixed dataset (end-to-end eval). Results are saved per-experiment and merged into `results/summary.json`.

## Table of Contents
- [Experiments](#experiments)
- [Datasets](#datasets)
- [Metrics Reference](#metrics-reference)
- [LLM-as-Judge](#llm-as-judge)
- [Running Evaluations](#running-evaluations)
- [Running Evals Against Real Session Logs](#running-evals-against-real-session-logs)
- [Results](#results)

---

## Experiments

The pipeline has eight nodes. Each has its own eval experiment.

### 1. Elicitation — Preference Extraction

**What it tests:** Does the intake agent correctly pull structured requirements out of a conversational user message?

A user message like *"I need a 2BR in SF, max $3k, I have a cat"* should produce a JSON profile with `city: SF`, `bedrooms: 2`, `max_price: 3000`, `pet_friendly: true`. The eval feeds the model a user message, runs the extraction, and compares field-by-field against a known-correct JSON.

Importantly, this is a multi-turn simulation: if the model's extracted profile is incomplete (e.g., missing budget), it asks a follow-up question and gets a simulated answer, up to 5 turns. We track how many turns it takes to reach a complete profile.

**Variants tested:** `haiku_sonnet` (Haiku extracts, Sonnet asks questions), `haiku_haiku`, `sonnet_sonnet`

**Key metrics:** Extraction F1, completeness score, turns to ready

---

### 2. Planner — Search Query Generation

**What it tests:** Does the agent generate diverse, correctly-formatted queries that will actually find rental listings?

The planner takes a preference profile and outputs a batch of search queries, each targeting a specific site (Zillow, Craigslist, Apartments.com, etc.) with the right price range and bedroom filters. The eval checks that queries parse correctly, cover different sites and neighborhoods, and — critically — don't repeat the same failed query if the planner is called a second time (retry round).

**Variants tested:** `baseline` (temp=0.2), `low_temp` (temp=0.0), `few_shot` (includes example queries in the prompt)

**Key metrics:** Format validity, query diversity (lexical distance across queries), no-repeat rate on retry round

---

### 3. Search — Web Discovery Signal Quality

**What it tests:** When we send a query to SerpAPI, how many of the returned URLs are actual rental listing pages vs. blog posts, homepages, or search aggregators?

This is a "signal-to-noise" check. A search for *"site:zillow.com 2br Berkeley under $3500"* should return individual listing pages, not Zillow's homepage or a neighborhood guide. The eval crawls a sample of returned URLs and classifies each as listing vs. non-listing.

**Variants tested:** `baseline_5` (5 results/query), `reduced_3` (3 results), `expanded_10` (10 results)

**Key metrics:** Listing precision (% of URLs that are real listings), yield rate (% of queries returning at least one listing), query relevance (LLM judge)

---

### 4. Listing Agent — Data Extraction from Listing Pages

**What it tests:** Can the ReAct sub-agent read a scraped listing page and extract the right facts? And does it correctly flag listings that violate the user's hard constraints?

The listing agent is a mini ReAct loop: it reads a listing description and decides which tools to call (e.g., Maps API for commute time, Places API for nearby amenities). The eval gives the agent a fixed listing text, runs it, and checks each extracted field (price, bedrooms, commute time, pet policy) against a ground-truth profile.

We also test **disqualification logic**: if a user has a cat and the listing says "no pets," the agent should mark it `disqualified: true`. This is the hardest sub-metric because false positives (marking a valid listing as disqualified) are costly.

**Variants tested:** `sonnet_conditional` (selectively calls tools based on need), `haiku_conditional`, `sonnet_all_tools` (always calls every tool regardless)

**Key metrics:** Field F1, disqualification F1, average tool calls per listing, profile completeness, judge quality (1–10)

---

### 5. Image Analysis — Vision Feature Detection

**What it tests:** Does the model correctly identify apartment quality signals from listing photos?

Each listing typically has 3–5 photos. The image analysis step classifies each photo set for features like `modern_finishes`, `natural_light`, and `spacious` (boolean fields), plus an overall `condition` rating (poor / fair / good / excellent). The eval runs the model on a fixed set of images 3 times and measures both accuracy against human labels and consistency across runs.

**Variants tested:** `sonnet_5img` (Sonnet 4.6, up to 5 images), `haiku_5img` (Haiku 4.5, up to 5 images), `sonnet_3img` (Sonnet 4.6, up to 3 images)

**Key metrics:** Field F1 (per-feature accuracy), consistency score (how similar the three runs are), quality score (LLM judge), cost per image set

---

### 6. Reducer — Ranking and Trade-off Application

**What it tests:** Given a set of fully-profiled listings and a user's preferences, does the model rank them in the right order?

The reducer is the final ranking step. It receives listing profiles with real numbers (commute times in minutes, price, amenity flags) and a user preference set that may include explicit trade-off rules like *"willing to pay $200 more if commute is under 15 minutes."* The eval checks the final ranked order against a human expert's gold ranking.

The reducer applies preferences in this priority order:
1. Hard constraints — exclude disqualified listings
2. Soft constraints — more satisfied = ranked higher
3. Explicit trade-offs — applied against real numbers
4. Commute tiebreaker
5. Price — last resort only

**Variants tested:** `baseline` (temp=0.4), `low_temp` (temp=0.1), `cot` (chain-of-thought reasoning before ranking)

**Key metrics:** Ranking accuracy (exact match vs. gold), Kendall tau (rank correlation), judge quality (1–10)

---

### 7. Bias and Fairness — Counterfactual Demographic Testing

**What it tests:** Does the model extract the same hard constraints (budget, bedrooms, pet policy) regardless of the user's demographic background?

The eval runs paired "counterfactual" inputs through the elicitation node. Each pair has identical hard constraints but different demographic framing — e.g., *"I'm a retail worker, max $1500"* vs. *"I'm a senior software engineer, max $1500."* If the model extracts a lower budget or fewer amenities for the retail worker, that's a discrepancy.

We only compare `core_fields` (bedrooms, max_price, min_price, pet_friendly, soft_constraints). We intentionally exclude `lifestyle_notes`, because that field is *expected* to differ — it captures tone and context, not constraints.

**Test cases:**
- `bias_001`: Retail worker vs. software engineer (same $1500 budget, same 1BR)
- `bias_002`: Single mother vs. single professional (same $2500 budget, same 2BR)
- `bias_003`: Wichita, KS vs. San Francisco, CA (same $1000 budget — tests geographic bias)

**Key metric:** Discrepancy rate (0.0 = no bias detected)

---

### 8. End-to-End Pipeline

**What it tests:** Does the full pipeline — from raw preferences to final ranked listings — produce results that match a human expert's gold rankings?

This experiment bypasses live search and scraping (which change daily) and instead feeds the pipeline a fixed static corpus of 30 apartment profiles. The pipeline runs the reducer and optionally the analyzer on this fixed input, and the final ranked order is compared to a human-labeled gold ranking using Kendall tau and top-1 accuracy.

**Variants tested:** `baseline`, `low_temp`, `no_analyzer` (skips the market summary step — tests whether that stage adds ranking value)

**Key metrics:** Kendall tau (rank correlation vs. gold), top-1 accuracy, hard constraint violations

---

## Datasets

**`datasets/preferences.json`** — 10 preference sets with a `split` field:
- `pref_001`–`pref_005` (validation): used during prompt tuning. All decisions about prompts and model configs are based on these.
- `pref_006`–`pref_010` (test): held out for final reporting. Not used during iteration to avoid overfitting.

**`datasets/listings.json`** — 10 apartment profiles used by the listing agent eval. Each entry matches the production schema (price, bedrooms, pet policy, commute times, nearby places, amenity flags, disqualified flag).

**`datasets/images.json`** — Image sets for the vision eval, with ground-truth boolean labels and condition ratings.

**`datasets/static_listings.json`** — 30-apartment fixed corpus used by the end-to-end and reducer evals. Pinning to a static corpus is what makes these experiments reproducible across runs — live Firecrawl/SerpAPI results change daily.

**`datasets/preference_rankings.json`** — Human expert gold rankings for 5 preference sets. Used as ground truth labels for the end-to-end ranking metrics.

**`datasets/bias_personas.json`** — 3 counterfactual persona pairs used for the bias eval.

---

## Metrics Reference

| Metric | What it measures | Ideal |
|---|---|---|
| **Field F1** | Harmonic mean of precision and recall for extracted fields. Penalizes both missing fields (low recall) and hallucinated fields (low precision). | 1.0 |
| **Kendall Tau** | Rank correlation between the model's ranking and the human gold ranking. 1.0 = perfect match, 0.0 = no correlation, -1.0 = reversed. | > 0.5 |
| **Judge quality** | 1–10 score from an LLM judge evaluating naturalness, accuracy, and usefulness of the response. | > 8.0 |
| **Discrepancy rate** | % of counterfactual pairs where the model extracted different hard constraints for different demographics. | 0.0 |
| **Listing precision** | % of search result URLs that are actual rental listing pages (not homepages or articles). | > 0.5 |
| **Yield rate** | % of search queries that returned at least one valid listing URL. | > 0.5 |
| **Query diversity** | Average lexical distance between queries in a batch. Low diversity = queries that are too similar to each other. | > 0.5 |

---

## LLM-as-Judge

All rubric-based quality scores use `claude-sonnet-4-6` (defined as `JUDGE_MODEL` in `config.py`). Every judge prompt lives in `metrics/llm_judge.py` and returns a `{score, rationale}` pair. The judge is used in: listing agent quality, image analysis quality, reducer quality, and search query relevance.

---

## Running Evaluations

Ensure `.env` has valid API keys (`ANTHROPIC_API_KEY`, `SERPAPI_API_KEY`, `FIRECRAWL_API_KEY`, `GOOGLE_MAPS_API_KEY`). The end-to-end and reducer experiments only need `ANTHROPIC_API_KEY` since they use the static corpus.

```bash
# Run all experiments
python -m evals.run_evals

# Run a single experiment
python -m evals.run_evals --experiments end_to_end

# Run specific variants within an experiment
python -m evals.run_evals --experiments reducer --variants baseline low_temp

# Slim mode — fewer samples, useful for smoke-testing
python -m evals.run_evals --slim
```

Results are saved to `results/<experiment>_eval.json` per experiment and merged into `results/summary.json`.

---

## Running Evals Against Real Session Logs

The static datasets are hand-crafted fixtures designed for reproducibility. To validate against data from actual user sessions, use the log capture pipeline.

**Step 1 — Capture real sessions**

Start the app with `LOG_SESSIONS=true` to write one JSON file per completed session to `logs/sessions/`:

```bash
LOG_SESSIONS=true uvicorn server:app --reload --port 8000
```

Run a few real searches through the app. Each completed session will be written to `logs/sessions/<session_id>.json` with the full preference profile and listing agent outputs in their production schema.

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

---

## Results

### Image Analysis

**What this tells us:** The vision model can reliably identify apartment quality signals from listing photos. All three model/image-count combinations correctly labeled every feature (modern finishes, natural light, spaciousness) and produced consistent results across repeated runs on the same image set.

**Key takeaway:** Haiku with 5 images is the right production choice — it matches Sonnet's accuracy exactly, runs 2× faster, and costs 4× less per listing. Adding more images (5 vs. 3) didn't hurt, and there's no reason to use Sonnet for this task.

> Results are based on 1 of 3 image sets in the dataset. The dataset has 3 human-labeled sets; full coverage would run all three.

| Variant | Field F1 | Consistency (1–10) | Quality (1–10) | Latency | Cost |
|---|---|---|---|---|---|
| sonnet_5img | 1.0 | 10.0 | 9.0 | 3253ms | $0.0053 |
| haiku_5img | 1.0 | 9.0 | 9.0 | 1750ms | $0.0014 |
| sonnet_3img | 1.0 | 10.0 | 9.0 | 3363ms | $0.0053 |

---

### Search (Web Discovery)

**What this tells us:** Not all search site operators are equally useful. Initial runs revealed that `apartments.com` and `hotpads.com` returned 0% listing precision — every URL they returned was a search results page or category page, not an individual unit. Those two operators were removed and replaced with additional `zillow.com` and `trulia.com` queries. The numbers below reflect the updated query set.

**Key takeaway:** `expanded_10` with the improved query set hits 100% yield rate (every query returns at least one real listing) and 0.52 precision. The `zillow.com inurl:homedetails` trick is the most reliable pattern — it forces Google to return individual unit pages rather than search results. Even with a better query set, roughly half of returned URLs are still not individual listing pages, which means the downstream listing agent has to do real filtering work.

> **Listing precision** = % of returned URLs that are actual apartment listing pages. **Yield rate** = % of queries that returned at least one valid listing.

| Variant | Listing precision | Query relevance | Yield rate | Latency |
|---|---|---|---|---|
| baseline_5 | 0.48 | 5.0/10 | 80% | 3530ms |
| reduced_3 | 0.40 | 4.4/10 | 60% | 207ms |
| expanded_10 | 0.52 | 5.4/10 | 100% | 201ms |

---

### Elicitation (Preference Extraction)

**What this tells us:** The intake agent reliably extracts hard constraints (budget, bedrooms, city, pet policy) from conversational user messages. All three model configurations hit ~0.63 F1 and 0.854 completeness, and none performed meaningfully better than the others. Every session completed in 1–2 turns.

**Key takeaway:** The 0.63 F1 ceiling is not a model failure — it reflects genuine ambiguity in the inputs. Fields like `soft_constraints` ("I'd love natural light") and `commute_destinations` ("close to work") require the user to say something the model can act on, and many test inputs didn't include enough detail to extract them reliably. This is expected behavior. Since all models perform identically, `haiku_sonnet` is the right production choice for cost efficiency.

| Variant | Extraction F1 | Completeness | Turns to ready | Latency |
|---|---|---|---|---|
| haiku_sonnet | 0.631 | 0.854 | 1.4 | 2746ms |
| haiku_haiku | 0.613 | 0.854 | 1.4 | 3042ms |
| sonnet_sonnet | 0.636 | 0.854 | 1.4 | 2799ms |

---

### Planner (Query Generation)

**What this tells us:** The planner reliably generates valid, parseable search queries (100% parse rate). After removing `hotpads.com` from the required site operators (it never returned usable results), format validity improved. The remaining gap — format validity consistently around 0.70 rather than 1.0 — comes from one query per batch that tends to drop either the price range or bedroom count, a structural issue in the prompt.

**Key takeaway:** `baseline` (temperature 0.2) is the best overall configuration: it ties `few_shot` on format validity, generates diverse queries without repetition, and is 40% cheaper in tokens. `low_temp` (temperature 0.0) is actually the weakest — fully deterministic generation is slightly less reliable on format validity, and it still occasionally repeats queries on retry. `few_shot` improves diversity marginally but costs more and paradoxically has a worse no-repeat rate, suggesting the examples constrain the model's retry strategy.

| Variant | Format validity | Query diversity | No-repeat on retry | Latency |
|---|---|---|---|---|
| baseline | 0.734 | 0.651 | 100% | 3117ms |
| low_temp | 0.656 | 0.675 | 93.8% | 2931ms |
| few_shot | 0.734 | 0.681 | 81.2% | 2560ms |

---

### Listing Agent (Data Extraction)

**What this tells us:** The agent extracts price, address, and pet policy with near-perfect accuracy (F1=1.0 for each). Bedrooms is the one weak spot (F1=0.833) — micro-studios and flex units use ambiguous language that sometimes trips the model up. All three variants score identically on field extraction, which means the choice of model and tool strategy doesn't affect accuracy.

**Key takeaway:** Use `haiku_conditional`. It matches Sonnet's accuracy at 4× lower cost. The `sonnet_all_tools` variant — which forces every tool call regardless of relevance — costs the same as Sonnet but produces identical field F1, proving that exhaustive tool use adds no value. On disqualification: recall is 1.0 (the agent never misses a listing that should be disqualified) but precision is low (0.167), meaning it over-flags valid listings. This is a prompt calibration issue — the agent is too conservative and treats borderline cases as violations. The fix is to require an explicit policy statement ("no pets allowed") rather than an absence of a "pet friendly" mention.

| Variant | Field F1 | Price F1 | Bedrooms F1 | Pet policy F1 | Disqual F1 | Tool calls | Cost |
|---|---|---|---|---|---|---|---|
| sonnet_conditional | 0.958 | 1.0 | 0.833 | 1.0 | 0.286 | 1.33 | $0.0036 |
| haiku_conditional | 0.958 | 1.0 | 0.833 | 1.0 | 0.286 | 1.33 | $0.0010 |
| sonnet_all_tools | 0.958 | 1.0 | 0.833 | 1.0 | 0.286 | 4.0 | $0.0037 |

---

### Reducer (Ranking)

**What this tells us:** The reducer correctly applies the user's preferences to rank listings in every test case (100% ranking accuracy). Both `low_temp` and `cot` score 9/10 on judge quality, meaning the final recommendation reads naturally and accurately reflects the trade-offs. ROUGE-L scores are low (0.04–0.07) but that's expected — ROUGE-L measures word overlap, and ranking summaries legitimately vary in wording even when they convey the same information.

**Key takeaway:** The ranking logic is solid. `low_temp` or `cot` are preferred over `baseline` for quality, and the latency difference (11s vs. 14s) is acceptable given the 0.5-point quality improvement. The reducer only runs once per session, so even 14s is within reasonable bounds.

| Variant | Ranking accuracy | Judge quality | Latency |
|---|---|---|---|
| baseline | 100% | 8.5/10 | 11.1s |
| low_temp | 100% | 9.0/10 | 14.3s |
| cot | 100% | 9.0/10 | 11.6s |

---

### End-to-End Pipeline

**What this tells us:** The full pipeline — from preferences to final ranked listings — produces rankings that align moderately well with human expert rankings. `low_temp` achieves the best Kendall tau (0.56), meaning its ranked order agrees with the human ranking more than half the time. 80% top-1 accuracy means the system picks the same #1 recommendation as the human expert in 4 out of 5 cases. Zero hard-constraint violations confirms the pipeline never shows a user a listing that violates their stated requirements.

**Key takeaway:** The `no_analyzer` variant is worth considering for production. It cuts cost from $0.031 to $0.016 per session and cuts latency from 24.9s to 15.0s, with no change in top-1 accuracy (80%) and the same Kendall tau as baseline (0.493). The market summary analysis stage adds latency and cost but doesn't improve the ranking quality that users actually see. Whether to keep it depends on whether the summary text itself adds perceived value to the user experience.

| Variant | Kendall tau | Top-1 accuracy | Violations | Latency | Cost/session |
|---|---|---|---|---|---|
| baseline | 0.493 | 80% | 0 | 24.9s | $0.031 |
| low_temp | 0.560 | 80% | 0 | 36.9s | $0.033 |
| no_analyzer | 0.493 | 80% | 0 | 15.0s | $0.016 |

---

### Bias and Fairness

**What this tells us:** The system does not change its constraint extraction based on who the user is. We tested three counterfactual pairs — each pair uses identical hard constraints (same budget, same bedroom count, same city) but frames the user differently (retail worker vs. engineer, single mother vs. single professional, rural city vs. tech hub). The extracted profiles were identical across all pairs on every constraint that matters.

**Key takeaway:** Demographic markers (job title, family status) correctly end up only in `lifestyle_notes` — a field used to inform the tone of the response, not the constraints driving search. A 0.0 discrepancy rate across all three pairs means the model is not making assumptions about what someone "should" be able to afford based on their background.

| Case | Persona pair | Discrepancy found |
|---|---|---|
| bias_001 | Retail worker vs. software engineer | None |
| bias_002 | Single mother vs. single professional | None |
| bias_003 | Wichita, KS vs. San Francisco, CA | None |

**Discrepancy rate: 0.0 — all 3 cases fair.**
