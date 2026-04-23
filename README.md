# Rental Recommendation Agent: Personalized Apartment Search

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
│                         Chainlit UI                             │  [Human in the Loop]
└───────────────────────────┬─────────────────────────────────────┘
                            │ user message
                            ▼
                    ┌───────────────┐
                    │ Intent Router │  Claude Haiku (classify intent)
                    │     Node      │  [Routing]
                    └───────┬───────┘
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
 conversational     get recommendations       tool_call
 answer directly            │               run specific
 from context → END         │                tool → END
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
             │  [query1] [query2] [query3]  │               │
             └──────────────┬───────────────┘               │
                            │ candidate URLs                │
                            ▼                               │
                    ┌───────────────┐                       │
                    │   Supervisor  │                       │  [Hierarchical] [Multi-agent orchestration]
                    │     Node      │                       │
                    └───────┬───────┘                       │
                            │ spawns one agent per new URL  │
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

## Tools

The listing agents have access to five tools. Which ones get called depends on the user's preferences — not every agent uses every tool.

| Tool | API | Status |
|---|---|---|
| `scrape_listing` | Firecrawl | Implemented |
| `search_web` | SerpAPI (Google) | Implemented |
| `analyze_listing_photos` | Claude Sonnet 4.6 (vision) | Implemented |
| `get_commute_time` | Google Maps Distance Matrix API | API tested, prototype ready |
| `find_nearby_places` | Google Places API (+ Geocoding) | API tested, prototype ready |

---

## TODO

- Intent Router node - currently every message goes straight to elicitation regardless of what the user is asking. A lightweight Haiku classifier should run first on every message and route to one of three paths: `needs_search` (user wants to find apartments → elicitation if prefs incomplete, planner if ready), `conversational` (general question, follow-up about results, etc. → answer directly from context), or `tool_call` (specific data request like commute time or nearby places for a known address → call the relevant tool directly and return). Examples of each: "find me a 2br in SF under $3k" → needs_search; "what's the difference between a studio and 1br?" → conversational; "how long is the commute from 123 Main St to UC Berkeley by transit?" → tool_call. Currently the app resets and reruns the full search pipeline on every follow-up message regardless of intent, which is wasteful and breaks simple conversational exchanges.
- `find_nearby_places` tool - API tested and prototype implementation ready in `notebooks/google_maps_places_api_test.ipynb`; needs to be wired into the stub at `graph/tools/places.py` (geocodes address internally, returns structured dict with nearby place details). Uses `GOOGLE_MAPS_API_KEY` — single key covers Places + Geocoding + Distance Matrix.
- `get_commute_time` tool - API tested and prototype implementation ready in `notebooks/google_maps_places_api_test.ipynb`; needs to be wired into the stub at `graph/tools/commute.py` (supports driving, transit, bicycling, walking modes; returns structured dict). Uses same `GOOGLE_MAPS_API_KEY`.
- LangSmith observability - add tracing across graph traces (node inputs/outputs, latency, token usage)
- Evals - framework implemented in `evals/` with 6 experiments covering all major nodes (elicitation, planner, search, listing agent, reducer, image analysis). Run with `python -m evals.run_evals` or type `/evals` in the Chainlit UI. Metrics include ROUGE-L, embedding similarity, F1, LLM-as-judge, latency, and cost per session. Results saved to `evals/results/`. Outstanding: fill in test datasets (`evals/datasets/preferences.json`, `listings.json`, `images.json`) with real examples.
- Photo analysis token cost - `analyze_listing_photos` currently passes all available images to Claude vision. This gives the best analysis quality (no relevant photos get cut) but cost scales linearly with listing photo count — Zillow/Apartments.com listings commonly have 30–50 images. A few options worth considering:
  - **Hard cap with relevance ranking**: do a cheap first-pass call to categorize/label all images, then pass only the top-N most relevant to `focus_areas` for the full analysis. Better quality than a naive slice, but adds a round-trip.
  - **Single-pass expanded**: pass all images in one call but prompt the model to weight its analysis toward images most relevant to `focus_areas`. One call, higher token cost, no extra latency.
  - **Naive cap (original)**: `image_urls[:N]` — cheapest but misses relevant photos that appear later in the listing's sequence.
  Current choice favors analysis quality; revisit if per-listing API cost becomes a concern.
- Data persistence - state is in-memory only (`cl.user_session`), so a page refresh or server restart loses all chat history and LLM context. Two things needed to fix this:
  - **LLM context** - wire a LangGraph checkpointer (e.g. `SqliteSaver`) into `build_graph()` and pass a `thread_id` per user in the invoke config; the graph will automatically reload prior state on resume
  - **Visual chat history** - configure Chainlit's data layer (LiteralAI or a custom adapter) so the UI replays past messages on reload; without this the page appears blank even if the LLM has context

---

## Tech Stack

| Layer | Tool |
|---|---|
| Chat UI | Chainlit |
| Graph / Orchestration | LangGraph |
| LLM | Claude Haiku 4.5, Claude Sonnet 4.6 (Anthropic) |
| Search | SerpAPI (Google) |
| Scraping | Firecrawl |
| Location / Commute | Google Maps Platform (Distance Matrix, Places, Geocoding) |
| LLM framework | LangChain |
| Observability | LangSmith (planned) |
