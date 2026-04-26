# Real Estate AIgent: Personalized Apartment Search

**New here?** Start with [SETUP.md](SETUP.md) for install + run + test instructions.

A conversational apartment-hunting agent built as part of INFO 290: Generative AI at UC Berkeley. The idea came from a pretty universal pain point - searching for a rental is tedious, results are scattered across a dozen sites, and standard search filters don't capture the nuance of what people actually care about (commute time, noise level, whether there's a good gym nearby, etc.).

This project explores what a better version of that experience could look like when you combine a conversational LLM with real-time web search, parallel multi-agent research, and structured preference reasoning.

---

## What It Does

The system talks with you first. Rather than making you fill out a form, it asks a few targeted questions to understand your priorities - budget, location, commute destinations, lifestyle preferences, and importantly, how you'd trade those off against each other. Once it has enough to go on, it finds candidate listings, then spins up a research agent per listing that decides what tools to call based on your specific situation. Someone with a dog gets pet policy checked immediately. Someone who cares about a bar scene gets a places lookup for that. Someone who didn't mention grocery stores doesn't waste an API call on it.

The result is a ranked recommendation list built from real data - actual commute times, actual nearby places, actual listing details - not inferred from search snippets. After ranking, an analyzer node reviews both the recommended and disqualified listings to surface cross-cutting market patterns: whether your budget is realistic for the area, what's actually eliminating options, and concrete suggestions for adjusting the search.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI + React UI                          │  [Human in the Loop]
│              + AsyncSqliteSaver checkpointer                    │  [Persistence]
└───────────────────────────┬─────────────────────────────────────┘
                            │ user message (thread_id scoped)
                            ▼
                    ┌───────────────┐
                    │ Intent Router │  Claude Haiku (classify intent) — IMPLEMENTED
                    │     Node      │  [Routing]
                    └───────┬───────┘
        ┌──────────┬────────┴───────────┬──────────┐
        │          │                    │          │
        ▼          ▼                    ▼          ▼
 off_topic  conversational      get recommendations  tool_call
 decline &  answer directly             │          run commute/places
 END        from context → END          │          directly → END
                                        ▼
                                ┌───────────────┐
                                │  Elicitation  │  Claude Haiku (extract prefs)
                                │     Node      │  Claude Sonnet (generate question)  [Human in the Loop]
                                └───────┬───────┘
                                        │ ready_to_search = True
                                        ▼
                                ┌───────────────┐
                                │    Planner    │◄──────────────────────┐  [Plan + Execute]  generates listing-discovery queries only
                                │     Node      │                       │  retry-aware: avoids previously run queries
                                └───────┬───────┘                       │
                                        │ search queries                │
                                        ▼                               │
                        ┌──────────────────────────────┐               │
                        │     Parallel Search Nodes    │  SerpAPI      │  [Map Reduce: map / fan-out]
                        │  [q1] [q2] ... [up to q30]   │               │
                        └──────────────┬───────────────┘               │
                                        │ candidate URLs                │
                                        ▼                               │
                                ┌───────────────┐                       │
                                │   Supervisor  │                       │  [Hierarchical] [Multi-agent orchestration]
                                │     Node      │                       │
                                └───────┬───────┘                       │
                                        │ spawns one agent per unique URL │
                                        ▼                               │
                ┌───────────────────────────────────────────────────┐       │
                │              Parallel ReAct Listing Agents        │       │  [ReAct] [Map Reduce: map]
                │                                                   │       │
                │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │       │
                │  │  Agent A    │  │   Agent B   │  │  Agent C  │  │       │
                │  │             │  │             │  │           │  │       │
                │  │ tools used  │  │ disqualified│  │tools used │  │       │
                │  │ based on    │  │ early (e.g. │  │based on   │  │       │
                │  │ user prefs  │  │ no pets)    │  │user prefs │  │       │
                │  └──────┬──────┘  └─────────────┘  └─────┬─────┘  │       │
                │         │                                │        │       │
                │    ┌────┴────────────────────────────────┴────┐   │       │
                │    │              Available Tools             │   │       │
                │    │  scrape_listing  │  get_commute_time     │   │       │
                │    │  find_nearby_places  │  search_web       │   │       │
                │    │  analyze_listing_photos                  │   │       │
                │    └──────────────────────────────────────────┘   │       │
                └───────────────────────┬───────────────────────────┘       │
                                        │ structured profiles               │
                                        ▼                                   │
                                ┌───────────────┐                           │
                                │ Results Check │  counts good results      │  [Routing]
                                │     Node      ├──── < 10 good? ───────────┘
                                │               │     retry with new queries
                                └───────┬───────┘
                                        │ >= 10 good results (or max attempts hit)
                                        ▼
                                ┌───────────────┐
                                │    Reducer    │  ranks with real structured data  [Map Reduce: reduce]
                                │     Node      │  applies trade-off rules against actual numbers
                                └───────┬───────┘
                                        │ final profiles + disqualified profiles
                                        ▼
                                ┌───────────────┐
                                │    Analyzer   │  surfaces patterns across all results  [Reflection]
                                │     Node      │  e.g. budget too low, neighborhood commute mismatch
                                └───────┬───────┘
                                        │
                                        ▼
                        ranked recommendations
                        with links + images + insights
```


## How the Listing Agents Work

Each listing agent is a ReAct (Reason + Act) agent. It has a set of tools and decides which ones to call based on what it finds and what the user cares about - not a fixed pipeline.

Example for a user with a dog who wants bars nearby:

```
scrape_listing(url)
  finds: price, floor, description, no pet policy listed

user has a dog - need to verify pet policy before going further
  search_web("pet policy 4521 Telegraph Ave Oakland")
  result: "pets allowed with $500 deposit"

commute check - user listed UC Berkeley as a destination
  get_commute_time("4521 Telegraph Ave", "UC Berkeley", mode="transit")
  result: "14 min BART"

user mentioned bars in soft_constraints
  find_nearby_places("4521 Telegraph Ave", "bars")
  result: "Temescal strip 0.1mi"

user didn't mention grocery stores - skip that lookup
done, returning profile
```

A different user with different preferences triggers a completely different set of tool calls.

---

## Search Strategy

The planner generates 3 queries (limited for testing; increase as API credits allow). Each query explores one trade-off scenario from the user's preferences — hard requirements appear in every query, and what varies per query is driven by the trade-off being explored (e.g. one query targets gym proximity for the 1-bed scenario, another targets grocery proximity for the 2-bed scenario). This ensures each query surfaces a distinct slice of the market.

Active listing site: Apartments.com (others commented out for testing). Each query returns 1 SerpAPI result to conserve credits.

The supervisor deduplicates URLs across all query results before spawning listing agents, so the same listing surfaced by multiple queries is only researched once. Filtering is done at the URL level (trusted domain + individual listing page heuristic — including apartments.com's 2-segment alphanumeric ID pattern). The final response surfaces the top ranked results from however many listings were researched.

`scrape_listing` now uses Firecrawl's structured JSON extraction instead of raw markdown, returning clean fields (price, address, amenities, images, etc.) directly — works generically across any listing site.

---

## Tools

The listing agents have access to five tools. Which ones get called depends on the user's preferences — not every agent uses every tool.

| Tool | API | Status |
|---|---|---|
| `scrape_listing` | Firecrawl | Implemented |
| `search_web` | SerpAPI (Google) | Implemented |
| `analyze_listing_photos` | Claude Sonnet 4.6 (vision) | Implemented |
| `get_commute_time` | Google Maps Distance Matrix API | Implemented |
| `find_nearby_places` | Google Places API (New) + Geocoding | Implemented |

---

## Example Listing Profile

Each ReAct listing agent returns a structured JSON profile with fields selected based on the user's preferences. Example for a user with a dog who cares about commute and wants bars nearby:

```json
{
  "url": "https://sfbay.craigslist.org/eby/apa/d/oakland-temescal-2br",
  "disqualified": false,
  "disqualify_reason": null,
  "price": 2350,
  "floor": 1,
  "address": "4521 Telegraph Ave, Temescal, Oakland, CA",
  "views": false,
  "pet_friendly": true,
  "pet_deposit": 400,
  "furnishing": "unfurnished",
  "images": [
    "https://images.craigslist.org/00A0A_ex1_600x450.jpg",
    "https://images.craigslist.org/00D0D_ex2_600x450.jpg"
  ],
  "commute_times": {
    "UC Berkeley, Soda Hall": "13 min BART",
    "Downtown Oakland": "10 min BART"
  },
  "nearby_places": {
    "bars": "Temescal strip 0.1mi",
    "coffee shop": "Bicycle Coffee 0.1mi"
  },
  "modern_finishes": false,
  "natural_light": true,
  "spacious": true,
  "condition": "good",
  "notes": "Classic bungalow with a small yard, walkable to Temescal restaurants",
  "description": "2BR Temescal bungalow, yard, pet-friendly"
}
```

Note how only preference-relevant fields are populated. A user who didn't mention bars or commute would receive a profile without `commute_times` or the "bars" `nearby_places` entry — the agent skips unnecessary API calls.

---

## Evaluation

The evaluation suite lives in [`evals/`](evals/) and covers six component-level experiments plus one end-to-end pipeline experiment:

| Experiment | Scope |
|---|---|
| `elicitation` | Preference extraction accuracy + question quality |
| `planner`     | Search query format, diversity, retry novelty |
| `search`      | SerpAPI result precision, yield, relevance |
| `listing_agent` | Field extraction F1, disqualification accuracy, tool efficiency |
| `image`       | Photo analysis accuracy vs. human labels, consistency |
| `reducer`     | Ranking accuracy, trade-off application, ROUGE-L vs reference |
| `end_to_end`  | Full-pipeline Kendall tau vs human gold rankings on a static 30-listing corpus |

**Reproducibility:** the end-to-end experiment runs against [`evals/datasets/static_listings.json`](evals/datasets/static_listings.json) (30 fixed apartment profiles across SF/Oakland/Chicago) with [`evals/datasets/preference_rankings.json`](evals/datasets/preference_rankings.json) providing human-labeled gold orderings. This pins every external API response so results are comparable across runs.

**Dataset split:** [`evals/datasets/preferences.json`](evals/datasets/preferences.json) explicitly marks each row `"split": "validation"` (rows 1–5, for prompt tuning) or `"split": "test"` (rows 6–10, for final reporting).

**LLM-as-judge:** all judges run on `claude-sonnet-4-6`. Rubrics live in [`evals/metrics/llm_judge.py`](evals/metrics/llm_judge.py).

Run with `python -m evals.run_evals`. See [`evals/README.md`](evals/README.md) for full documentation.

---

## TODO

- ~~Intent Router node~~ — **done.** Haiku classifier in [`graph/nodes/intent_router.py`](graph/nodes/intent_router.py) routes every message to one of: `needs_search` (→ elicitation), `conversational` (answer from context), `tool_call` (direct commute/places lookup), or `off_topic` (polite decline).
- ~~`find_nearby_places` tool~~ — **done.** Geocodes + Places Nearby Search (new API), maps natural-language types, returns structured results with distances.
- ~~`get_commute_time` tool~~ — **done.** Distance Matrix across transit/driving/bicycling/walking.
- ~~LangSmith observability~~ — **done.** Per-node run names tagged; enable via `LANGCHAIN_TRACING_V2=true` in `.env`.
- ~~Evals datasets~~ — **done.** 30-listing static corpus, 10 preferences (5 validation / 5 test), 5 human-ranked preference-to-listing sets, end-to-end experiment registered.
- ~~Data persistence~~ — **done.** `AsyncSqliteSaver` checkpointer wired into `build_graph()` with `thread_id` per session. Session ID persisted in `localStorage`; full conversation history + final search results replayed on reconnect from SQLite.
- Photo analysis token cost — `analyze_listing_photos` currently passes all available images to Claude vision. This gives the best analysis quality (no relevant photos get cut) but cost scales linearly with listing photo count — Zillow/Apartments.com listings commonly have 30–50 images. A few options worth considering:
  - **Hard cap with relevance ranking**: do a cheap first-pass call to categorize/label all images, then pass only the top-N most relevant to `focus_areas` for the full analysis. Better quality than a naive slice, but adds a round-trip.
  - **Single-pass expanded**: pass all images in one call but prompt the model to weight its analysis toward images most relevant to `focus_areas`. One call, higher token cost, no extra latency.
  - **Naive cap (original)**: `image_urls[:N]` — cheapest but misses relevant photos that appear later in the listing's sequence.
  Current choice favors analysis quality; revisit if per-listing API cost becomes a concern.
- Scale static corpus to 50–100 — framework supports it; current 30 is the MVP.
- Error handling — errors throughout the codebase currently surface raw to the user. Should catch and return friendly messages instead. Leaving raw for now to make errors visible during testing.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | React (Vite + TypeScript + Tailwind) |
| Backend | FastAPI + WebSockets |
| Graph / Orchestration | LangGraph |
| LLM | Claude Haiku 4.5, Claude Sonnet 4.6 (Anthropic) |
| Search | SerpAPI (Google) |
| Scraping | Firecrawl |
| Location / Commute | Google Maps Platform (Distance Matrix, Places API New, Geocoding) |
| LLM framework | LangChain |
| Observability | LangSmith (per-node run names) |
| Persistence | LangGraph AsyncSqliteSaver (thread-scoped checkpointer) |
