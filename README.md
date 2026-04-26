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
                    │ Intent Router │  Llama 3.1 8B (classify intent)
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
                                │  Elicitation  │  Llama 3.1 8B (extract prefs)
                                │     Node      │  Llama 3.3 70B (generate question)  [Human in the Loop]
                                └───────┬───────┘
                                        │ ready_to_search = True
                                        ▼
                                ┌───────────────┐
                                │    Planner    │◄──────────────────────┐  [Plan + Execute]
                                │     Node      │                       │  generates 8 search queries
                                └───────┬───────┘                       │  retry-aware: avoids past queries
                                        │ search queries                │
                                        ▼                               │
                        ┌──────────────────────────────┐               │
                        │     Parallel Search Nodes    │  SerpAPI      │  [Map Reduce: fan-out]
                        │   [q1] [q2] ... [up to q8]   │  10 URLs/query│
                        └──────────────┬───────────────┘               │
                                        │ candidate URLs (up to 80)     │
                                        ▼                               │
                                ┌───────────────┐                       │
                                │   Supervisor  │                       │  [Hierarchical]
                                │     Node      │                       │  deduplicates + filters valid listing URLs
                                └───────┬───────┘                       │
                                        │ spawns one agent per unique URL│
                                        ▼                               │
                ┌───────────────────────────────────────────────────┐   │
                │          Parallel ReAct Listing Agents            │   │  [ReAct] [Map Reduce: map]
                │         (unlimited concurrency, all at once)      │   │
                │                                                   │   │
                │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
                │  │  Agent A    │  │   Agent B   │  │  Agent C  │  │   │
                │  │ tools based │  │ disqualified│  │tools based│  │   │
                │  │ on prefs    │  │ early       │  │on prefs   │  │   │
                │  └──────┬──────┘  └─────────────┘  └─────┬─────┘  │   │
                │    ┌────┴────────────────────────────────┴────┐   │   │
                │    │              Available Tools             │   │   │
                │    │  scrape_listing  │  get_commute_time     │   │   │
                │    │  find_nearby_places  │  search_web       │   │   │
                │    │  analyze_listing_photos (GPT-4o-mini)    │   │   │
                │    └──────────────────────────────────────────┘   │   │
                └───────────────────────┬───────────────────────────┘   │
                                        │ structured profiles            │
                                        ▼                               │
                                ┌───────────────┐                       │
                                │ Results Check │  counts good results  │  [Routing]
                                │     Node      ├──── < 20 good? ───────┘
                                │               │     retry with new queries
                                └───────┬───────┘
                                        │ >= 20 good results (or max attempts hit)
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
                        with links + images + map
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

The planner generates 8 queries per round. Each query explores one trade-off scenario from the user's preferences — hard requirements appear in every query, and what varies per query is driven by the trade-off being explored (e.g. one query targets gym proximity for the 1-bed scenario, another targets grocery proximity for the 2-bed scenario). Each query fetches up to 10 URLs from SerpAPI, giving a theoretical maximum of 80 candidate listing URLs per round.

Active listing sites: **Zillow** and **Apartments.com** (others commented out). The supervisor deduplicates URLs across all query results before spawning listing agents, so the same listing surfaced by multiple queries is only researched once. Filtering is done at the URL level (trusted domain + individual listing page heuristic — including Zillow's `/homedetails/` prefix and apartments.com's 2-segment alphanumeric ID pattern).

`scrape_listing` uses Firecrawl's structured JSON extraction, returning clean fields (price, address, amenities, images, etc.) directly — works generically across any listing site.

---

## Tools

The listing agents have access to five tools. Which ones get called depends on the user's preferences — not every agent uses every tool.

| Tool | API | Status |
|---|---|---|
| `scrape_listing` | Firecrawl | Implemented |
| `search_web` | SerpAPI (Google) | Implemented |
| `analyze_listing_photos` | GPT-4o-mini (vision) | Implemented |
| `get_commute_time` | Google Maps Distance Matrix API | Implemented |
| `find_nearby_places` | Google Places API (New) + Geocoding | Implemented |

---

## Example Listing Profile

Each ReAct listing agent returns a structured JSON profile with fields selected based on the user's preferences. Example for a user with a dog who cares about commute and wants bars nearby:

```json
{
  "url": "https://www.apartments.com/the-temescal-oakland-ca/abc123/",
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
    "https://images.apartments.com/...",
    "https://images.apartments.com/..."
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

- ~~Intent Router node~~ — **done.** Llama 3.1 8B classifier in [`graph/nodes/intent_router.py`](graph/nodes/intent_router.py) routes every message to one of: `needs_search` (→ elicitation), `conversational` (answer from context), `tool_call` (direct commute/places lookup), or `off_topic` (polite decline).
- ~~`find_nearby_places` tool~~ — **done.** Geocodes + Places Nearby Search (new API), maps natural-language types, returns structured results with distances.
- ~~`get_commute_time` tool~~ — **done.** Distance Matrix across transit/driving/bicycling/walking.
- ~~LangSmith observability~~ — **done.** Per-node run names tagged; enable via `LANGCHAIN_TRACING_V2=true` in `.env`.
- ~~Evals datasets~~ — **done.** 30-listing static corpus, 10 preferences (5 validation / 5 test), 5 human-ranked preference-to-listing sets, end-to-end experiment registered.
- ~~Data persistence~~ — **done.** `AsyncSqliteSaver` checkpointer wired into `build_graph()` with `thread_id` per session. Session ID persisted in `localStorage`; full conversation history + final search results replayed on reconnect from SQLite.
- ~~Photo analysis~~ — **done.** `analyze_listing_photos` uses GPT-4o-mini vision, capped to `MAX_PHOTOS` (default 12). Images proxied through `/imgproxy` backend endpoint to bypass hotlink restrictions.
- ~~Rate limit bottleneck~~ — **done.** Text nodes on Groq (Llama 3.1/3.3), listing agents and photo analysis on OpenAI (GPT-4o-mini). Concurrency is unlimited by default (env-tunable via `LISTING_CONCURRENCY`). UI surfaces rate-limit waits + run aborts.
- ~~Search scale~~ — **done.** 8 queries × 10 URLs = up to 80 candidate listings per round (was 3 × 1 = 3).
- ~~WebSocket reconnect~~ — **done.** Auto-reconnects with exponential backoff on disconnect; immediately reconnects when tab becomes visible again.
- ~~Map rendering~~ — **done.** Google Maps with geocoded pins; requires `VITE_GOOGLE_MAPS_KEY` in `frontend/.env`.
- Scale static corpus to 50–100 — framework supports it; current 30 is the MVP.
- Error handling — errors throughout the codebase currently surface raw to the user. Should catch and return friendly messages instead. Leaving raw for now to make errors visible during testing.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | React (Vite + TypeScript + Tailwind) |
| Backend | FastAPI + WebSockets |
| Graph / Orchestration | LangGraph |
| LLM (text nodes) | Groq — Llama 3.1 8B (classify/extract) + Llama 3.3 70B (generate) |
| LLM (listing agents + vision) | OpenAI — GPT-4o-mini |
| Search | SerpAPI (Google) |
| Scraping | Firecrawl |
| Location / Commute | Google Maps Platform (Distance Matrix, Places API New, Geocoding) |
| LLM framework | LangChain |
| Observability | LangSmith (per-node run names) |
| Persistence | LangGraph AsyncSqliteSaver (thread-scoped checkpointer) |
