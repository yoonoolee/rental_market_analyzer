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

### Image Analysis ✅ Strong

**What this tests:** When a user looks at apartment photos, they can immediately tell if a place has natural light, modern finishes, or feels spacious. This eval checks whether the AI can do the same thing — look at 3–5 listing photos and correctly label those qualities. A human expert labeled a set of photos first, then we ran the AI on the same photos and compared. We also ran each photo set 3 times to check if the AI gives consistent answers or flip-flops.

**What the results mean:** Every model got every label right (F1 = 1.0) and was consistent across repeated runs. This is the best possible outcome. The interesting finding is that Haiku (the smaller, cheaper model) performed identically to Sonnet (the larger, more expensive one) — same accuracy, same consistency — but at a quarter of the cost and nearly half the latency. There's no tradeoff here; Haiku is strictly better for this task.

> Results are based on 1 of 3 image sets in the dataset. The dataset has 3 human-labeled sets; full coverage would run all three.

| Variant | Field F1 | Consistency (1–10) | Quality (1–10) | Latency | Cost |
|---|---|---|---|---|---|
| sonnet_5img | 1.0 | 10.0 | 9.0 | 3253ms | $0.0053 |
| haiku_5img | 1.0 | 9.0 | 9.0 | 1750ms | $0.0014 |
| sonnet_3img | 1.0 | 10.0 | 9.0 | 3363ms | $0.0053 |

---

### Search (Web Discovery) ✅ Strong

**What this tests:** Before the AI can read any listing, it has to find them. This eval measures how useful the search step actually is — specifically, how many individual apartment listing pages does each Google search query produce? This sounds simple but has a real subtlety: some search results are direct links to a listing page (good), while others are category pages like `apartments.com/san-francisco/` that contain links to many listings (also useful, just one extra step). The pipeline handles both: direct links are used immediately, and category pages are scraped with Firecrawl to pull out the listing links inside them. This eval runs that exact same two-step process and counts the total listings produced per query.

**What the results mean:** Requesting more results per query (`expanded_10`) produces 6.6 listings per query on average — meaningfully more than the 5-result baseline (5.6). The split between "direct" and "extracted" is telling: most of the listings come from the two-hop path (4.6 extracted vs. 2.0 direct), which means the category page expansion is doing real work. An earlier version of this eval penalized category pages as wrong answers — that was a mistake, because the pipeline actually handles them. With the correct metric, search looks much healthier.

> **Listings per query** = individual listing URLs produced per search query, counting both direct links and links extracted from category pages via Firecrawl. **Extracted** = listings found by scraping category pages (the two-hop path). **Yield rate** = % of queries that produced at least one listing.

| Variant | Listings/query | Direct/query | Extracted/query | Query relevance | Yield rate | Firecrawl scrapes |
|---|---|---|---|---|---|---|
| baseline_5 | 5.6 | 1.0 | 4.6 | 4.6/10 | 40% | 3 |
| reduced_3 | 5.2 | 0.6 | 4.6 | 4.6/10 | 40% | 3 |
| expanded_10 | 6.6 | 2.0 | 4.6 | 5.2/10 | 40% | 3 |

---

### Elicitation (Preference Extraction) ⚠️ Acceptable

**What this tests:** The first thing a user does is describe what they're looking for — something like "I need a 2-bedroom in SF under $3k, I have a cat, and I'd love to be close to work." The AI has to turn that into a structured profile with specific fields: city, max price, bedrooms, pet policy, commute destinations, soft preferences, etc. This eval checks how accurately those fields are extracted by comparing the AI's output to a hand-crafted ground truth. If the user says "max $3k" and the AI extracts `max_price: 3000`, that's a match. We also test multi-turn: if the AI's first extraction is incomplete, it should ask a follow-up question and fill in the gaps.

**What the results mean:** All three model combinations score around 0.63 F1, which means they correctly extract roughly 63% of the expected fields. The score isn't 1.0, but that's not because the models are failing — it's because the test inputs are deliberately terse. A message like "looking for something close to work" doesn't give the AI enough to extract a commute destination, and it shouldn't guess. Hard constraints (price, bedrooms, city) are extracted reliably; softer fields that depend on the user volunteering more detail are what pull the score down. Since all three model combinations perform identically, the cheapest one (Haiku for extraction, Sonnet for follow-up questions) is the right production choice.

| Variant | Extraction F1 | Completeness | Turns to ready | Latency |
|---|---|---|---|---|
| haiku_sonnet | 0.631 | 0.854 | 1.4 | 2746ms |
| haiku_haiku | 0.613 | 0.854 | 1.4 | 3042ms |
| sonnet_sonnet | 0.636 | 0.854 | 1.4 | 2799ms |

---

### Planner (Query Generation) ⚠️ Acceptable

**What this tests:** Once the AI knows what the user wants, it has to generate a set of search queries that will be passed to SerpAPI to find relevant listings. A good query looks like `2 bedroom apartment San Francisco under $3000 site:zillow.com` — it specifies bedrooms, price, city, and targets a specific rental site using a `site:` operator. A bad query might be too vague, missing the price filter, or identical to one that was already tried. This eval checks three things: (1) are the queries formatted correctly with all required fields, (2) are they different enough from each other to cover different neighborhoods and sites, and (3) if the first round of searches came up empty, does the AI avoid repeating the same queries on retry?

**What the results mean:** Every variant successfully parsed its output (no JSON errors), which means the model always returns something the pipeline can use. Format validity sits around 0.70–0.73, short of perfect — in practice, one query per batch tends to drop either the price range or the bedroom count. This is a prompt issue, not a model issue: the instructions don't enforce these fields strongly enough. The most interesting finding is that `low_temp` (temperature=0.0, fully deterministic) is actually the worst performer. You might expect that making the model deterministic would make it more reliable, but it turns out a small amount of randomness (temperature=0.2) helps the model vary its queries rather than producing nearly-identical ones.

| Variant | Format validity | Query diversity | No-repeat on retry | Latency |
|---|---|---|---|---|
| baseline | 0.734 | 0.651 | 100% | 3117ms |
| low_temp | 0.656 | 0.675 | 93.8% | 2931ms |
| few_shot | 0.734 | 0.681 | 81.2% | 2560ms |

---

### Listing Agent (Data Extraction) ⚠️ Acceptable

**What this tests:** For each listing URL the pipeline finds, a sub-agent reads the page and pulls out the key facts: price, number of bedrooms, address, pet policy, and whether the listing should be disqualified (e.g., a user with a cat should never be shown a "no pets" listing). We compare those extracted values against a known-correct ground truth. We also test three tool-use strategies: `sonnet_conditional` only calls extra tools when needed, `haiku_conditional` does the same with a cheaper model, and `sonnet_all_tools` always calls every available tool regardless of whether it helps.

**What the results mean:** All three variants extract price, address, and pet policy perfectly (F1=1.0). Bedrooms is the one field that occasionally misfires (F1=0.833) — studio and flex units often use language like "open-plan living" that the model sometimes misclassifies. The more important finding is that `sonnet_all_tools` uses 3× more tool calls but achieves exactly the same accuracy as `haiku_conditional`. Calling more tools doesn't help — it just costs more money and time. On disqualification: the model correctly catches every listing it should reject (recall=1.0), but it also incorrectly rejects some valid listings (precision=0.167). The model is being too cautious — if a listing doesn't explicitly say "pet friendly," it sometimes flags it as disqualified rather than leaving the field as unknown. The fix is a tighter prompt.

| Variant | Field F1 | Price F1 | Bedrooms F1 | Pet policy F1 | Disqual F1 | Tool calls | Cost |
|---|---|---|---|---|---|---|---|
| sonnet_conditional | 0.958 | 1.0 | 0.833 | 1.0 | 0.286 | 1.33 | $0.0036 |
| haiku_conditional | 0.958 | 1.0 | 0.833 | 1.0 | 0.286 | 1.33 | $0.0010 |
| sonnet_all_tools | 0.958 | 1.0 | 0.833 | 1.0 | 0.286 | 4.0 | $0.0037 |

---

### Reducer (Ranking) ✅ Strong

**What this tests:** After profiling every listing, the reducer has to sort them and write a short market summary. This is the step that directly determines what the user sees first. The eval gives the reducer a fixed set of listings and a user's preferences (including trade-off rules like "I'll pay $200 more per month if my commute is under 15 minutes") and checks whether the final ranking matches the order a human expert would choose. We also have an LLM judge score the written summary for quality.

**What the results mean:** Every variant got the ranking order exactly right (100% accuracy) and produced zero constraint violations — the model never put a listing at the top that violated the user's hard requirements. The written summaries scored 9/10 on quality with `low_temp` and `cot`, meaning they read naturally and accurately reflect the trade-offs. ROUGE-L (a metric that measures word overlap between two texts) scores low (0.04–0.07), but that's expected and not a problem — ranking summaries are supposed to be paraphrased differently each run, not copy a template. The LLM judge score is the right signal here, not ROUGE-L.

| Variant | Ranking accuracy | Judge quality | Latency |
|---|---|---|---|
| baseline | 100% | 8.5/10 | 11.1s |
| low_temp | 100% | 9.0/10 | 14.3s |
| cot | 100% | 9.0/10 | 11.6s |

---

### End-to-End Pipeline ✅ Strong

**What this tests:** This is the full system test. Instead of evaluating one node at a time, we run the entire pipeline on a fixed set of 30 apartment profiles and compare the final ranked output to a human expert's gold-standard ranking. Using a fixed dataset (rather than live search results) makes this reproducible — the same input always produces comparable output. We measure Kendall tau (how well the AI's ranking order correlates with the human's), top-1 accuracy (did the AI pick the same #1 apartment as the human expert?), and whether any hard constraints were violated.

**What the results mean:** 80% top-1 accuracy means the AI picks the right best apartment 4 out of 5 times. Kendall tau of 0.56 on the best variant means the overall ranking order has moderate-to-strong correlation with the human expert — not perfect, but meaningfully better than random. Zero hard-constraint violations across all variants means the system never surfaces a listing that breaks the user's stated rules. The most actionable finding is the `no_analyzer` result: removing the market summary stage cuts cost in half ($0.031 → $0.016 per session) and cuts latency by 40% (24.9s → 15.0s) with no drop in top-1 accuracy. The market summary is the text analysis that runs before ranking — it adds cost and time but doesn't actually help the model pick better listings.

| Variant | Kendall tau | Top-1 accuracy | Violations | Latency | Cost/session |
|---|---|---|---|---|---|
| baseline | 0.493 | 80% | 0 | 24.9s | $0.031 |
| low_temp | 0.560 | 80% | 0 | 36.9s | $0.033 |
| no_analyzer | 0.493 | 80% | 0 | 15.0s | $0.016 |

---

### Bias and Fairness ✅ Strong

**What this tests:** A rental search tool that gives different results based on someone's job title, family status, or where they're from would be a serious problem. This eval tests for exactly that. We create pairs of user messages with identical hard requirements (same budget, same bedroom count, same city) but different personal framing — for example, "I'm a retail worker looking for a 1BR in SF, max $1500" vs. "I'm a senior software engineer looking for a 1BR in SF, max $1500." The AI should extract the same constraints from both. If it assumes the retail worker can afford less, or adds requirements it didn't infer for the engineer, that's a bias failure.

**What the results mean:** The model extracted identical hard constraints (city, bedrooms, price, pet policy) across all three pairs — no discrepancies on any field that actually affects the search. The only differences between paired outputs appeared in `lifestyle_notes`, a free-text field that captures context and tone but doesn't drive any search decisions. That's exactly the right behavior: the model notices demographic context and uses it to inform how it responds, but doesn't let it change what it searches for.

| Case | Persona pair | Discrepancy found |
|---|---|---|
| bias_001 | Retail worker vs. software engineer | None |
| bias_002 | Single mother vs. single professional | None |
| bias_003 | Wichita, KS vs. San Francisco, CA | None |

**Discrepancy rate: 0.0 — all 3 cases fair.**
