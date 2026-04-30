# Real Estate AIgent

> A conversational apartment-hunting agent that searches real listings, researches them in parallel, and returns ranked recommendations grounded in your actual preferences — commute times, nearby places, pet policies, and more.

Built for [INFO 290: Generative AI](https://www.ischool.berkeley.edu/) at UC Berkeley.

**New here?** Start with [SETUP.md](SETUP.md) for install, configuration, and run instructions.

---

## Overview

Standard rental search is broken. Filters don't capture what people actually care about — commute to a specific building, noise level, whether the neighborhood has good coffee, or how they'd trade a shorter commute for a bigger space. Results are scattered across a dozen sites, and ranking is just price-sorted ad placement.

Real Estate AIgent takes a different approach: it talks with you first, learns your real priorities and trade-offs, then dispatches a fleet of parallel research agents — one per candidate listing — that call real APIs to get real data before anything is ranked. The result is a recommendation list built from verified commute times, actual nearby places, and real listing details, not keyword matches.

---

## Features

### Conversational Search
- Asks targeted questions to understand priorities, budget, location, commute destinations, and how you'd trade them off
- Skips elicitation when you've been specific enough upfront
- Remembers the full conversation across page refreshes via SQLite persistence

### Parallel Multi-Agent Research
- Spawns one ReAct agent per candidate listing — runs all concurrently
- Each agent decides its own tool calls based on your preferences: someone with a dog gets pet policy checked first; someone who didn't mention gyms doesn't waste an API call on one
- Tools: listing scraper, web search, photo analysis (GPT-4o-mini vision), commute time, nearby places

### Ranked Results with Market Analysis
- Reducer node ranks all researched listings against your trade-off rules using real structured data
- Analyzer node surfaces cross-cutting patterns: whether your budget is realistic, what's eliminating options, concrete adjustments to try

### Professional UI
- **Match score badges** on every card — scored against your preferences with an expandable "why?" breakdown
- **Side-by-side compare drawer** for up to 3 listings with best-value highlighting
- **Interactive map** with price-bubble pins that sync with card hover
- **Sort + filter controls**: price, commute, sqft, saved listings, pet-friendly
- **Photo lightbox** with keyboard navigation
- **Agent's take** section on each card with the research agent's own notes
- **Process visualization**: live progress bar, per-listing agent status, elapsed timing
- **Keyboard shortcuts**: J/K navigation, F to favorite, C to compare, ⌘K new search
- **CSV export** and clipboard share

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
                                │     Node      │  Llama 3.3 70B (generate question)
                                └───────┬───────┘
                                        │ ready_to_search = True
                                        ▼
                                ┌───────────────┐
                                │    Planner    │◄──────────────────────┐
                                │     Node      │                       │
                                └───────┬───────┘                       │
                                        │ 8 search queries              │
                                        ▼                               │
                        ┌──────────────────────────────┐               │
                        │     Parallel Search Nodes    │  SerpAPI      │
                        │   [q1] [q2] ... [up to q8]   │  10 URLs each │
                        └──────────────┬───────────────┘               │
                                        │ up to 80 candidate URLs       │
                                        ▼                               │
                                ┌───────────────┐                       │
                                │   Supervisor  │                       │
                                │     Node      │  deduplicates URLs    │
                                └───────┬───────┘                       │
                                        │ one agent per unique URL      │
                                        ▼                               │
                ┌───────────────────────────────────────────────────┐   │
                │          Parallel ReAct Listing Agents            │   │
                │         (unlimited concurrency, all at once)      │   │
                │  ┌──────────────────────────────────────────────┐ │   │
                │  │              Available Tools                  │ │   │
                │  │  scrape_listing  │  search_web               │ │   │
                │  │  get_commute_time  │  find_nearby_places      │ │   │
                │  │  analyze_listing_photos (GPT-4o-mini vision)  │ │   │
                │  └──────────────────────────────────────────────┘ │   │
                └───────────────────────┬───────────────────────────┘   │
                                        │ structured profiles            │
                                        ▼                               │
                                ┌───────────────┐                       │
                                │ Results Check │  < 20 good? ──────────┘
                                │     Node      │  retry with new queries
                                └───────┬───────┘
                                        │ ≥ 20 good results (or max attempts)
                                        ▼
                                ┌───────────────┐
                                │    Reducer    │  ranks with real structured data
                                │     Node      │  applies trade-off rules
                                └───────┬───────┘
                                        │
                                        ▼
                                ┌───────────────┐
                                │    Analyzer   │  surfaces market patterns
                                │     Node      │  budget gaps, neighborhood trends
                                └───────┬───────┘
                                        │
                                        ▼
                        ranked recommendations + market analysis
                        with links, images, map, and match scores
```

---

## LLM Models by Step

| Step | Role | Provider | Model | Fallback |
|---|---|---|---|---|
| Intent classification | `intent_router_classify` | Groq | Llama 3.1 8B Instant | OpenAI gpt-4o-mini |
| Intent chat response | `intent_router_chat` | Groq | Llama 3.3 70B Versatile | OpenAI gpt-4o |
| Preference extraction | `elicitation_extract` | Groq | Llama 3.1 8B Instant | OpenAI gpt-4o-mini |
| Preference chat | `elicitation_chat` | Groq | Llama 3.3 70B Versatile | OpenAI gpt-4o |
| Search planning | `planner` | Groq | Llama 3.3 70B Versatile | OpenAI gpt-4o-mini |
| Listing agent | `listing_agent` | OpenAI | gpt-4o-mini | — (pinned) |
| Result reduction | `reducer` | Anthropic | Claude Sonnet 4.6 | OpenAI gpt-4o-mini |
| Market analysis | `analyzer` | Anthropic | Claude Sonnet 4.6 | OpenAI gpt-4o-mini |
| Photo vision | `photo_vision` | OpenAI | gpt-4o-mini | — (pinned) |

Model selection is centralized in [`graph/llm.py`](graph/llm.py). Override per-role via `RENTAL_MODELS` env var or globally via `LLM_PROVIDER`.

---

## How Listing Agents Work

Each listing agent is a ReAct (Reason + Act) agent. It receives one URL and your full preference profile, then decides its own tool sequence — not a fixed pipeline.

**Example** — user has a dog, wants bars nearby, commutes to UC Berkeley:

```
scrape_listing(url)
→ price, floor, description found; no pet policy listed

user has dog → verify pet policy before continuing
search_web("pet policy 4521 Telegraph Ave Oakland")
→ "pets allowed with $500 deposit"

user listed UC Berkeley as commute destination
get_commute_time("4521 Telegraph Ave", "UC Berkeley", mode="transit")
→ "14 min BART"

user mentioned bars in soft_constraints
find_nearby_places("4521 Telegraph Ave", "bars")
→ "Temescal strip 0.1mi"

user didn't mention grocery stores → skip that lookup
→ return structured profile
```

A user with different preferences triggers a completely different tool sequence.

---

## Tools

| Tool | API | Description |
|---|---|---|
| `scrape_listing` | Firecrawl | Structured JSON extraction — price, address, amenities, images |
| `search_web` | SerpAPI + Serpex fallback | Supplemental web search for pet policies, additional details |
| `analyze_listing_photos` | OpenAI gpt-4o-mini | Vision analysis of listing photos against user preferences |
| `get_commute_time` | Google Distance Matrix | Transit, driving, cycling, walking times to named destinations |
| `find_nearby_places` | Google Places API (New) | Geocoded proximity search for any place type |

---

## Search Strategy

The planner generates 8 queries per round. Hard requirements appear in every query; what varies per query is the trade-off scenario being explored (e.g. gym proximity vs. grocery proximity, 1-bed vs. 2-bed). Each query returns up to 10 URLs from SerpAPI, giving up to 80 candidate listings per round.

Active listing sites: **Zillow** and **Apartments.com**. The supervisor deduplicates URLs across all query results — the same listing surfaced by multiple queries is researched exactly once. If fewer than 20 good profiles come back, the results check node triggers a retry round with the planner generating fresh queries that avoid already-seen URLs.

---

## Example Listing Profile

```json
{
  "url": "https://www.apartments.com/the-temescal-oakland-ca/abc123/",
  "disqualified": false,
  "price": 2350,
  "address": "4521 Telegraph Ave, Temescal, Oakland, CA",
  "bedrooms": 2,
  "bathrooms": 1,
  "sqft": 850,
  "pet_friendly": true,
  "pet_deposit": 400,
  "furnishing": "unfurnished",
  "commute_times": {
    "UC Berkeley, Soda Hall": "13 min BART"
  },
  "nearby_places": {
    "bars": "Temescal strip 0.1mi",
    "coffee shop": "Bicycle Coffee 0.1mi"
  },
  "natural_light": true,
  "spacious": true,
  "condition": "good",
  "notes": "Classic bungalow with a small yard, walkable to Temescal restaurants",
  "images": ["https://images.apartments.com/..."]
}
```

Only preference-relevant fields are populated. A user who didn't mention commute or bars receives a profile without those entries — the agent skips unnecessary API calls.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + TypeScript + Tailwind CSS v4 (Vite) |
| Backend | FastAPI + WebSockets |
| Graph / Orchestration | LangGraph |
| LLM — classify / extract | Groq — Llama 3.1 8B Instant |
| LLM — chat / plan | Groq — Llama 3.3 70B Versatile |
| LLM — reduce / analyze | Anthropic — Claude Sonnet 4.6 |
| LLM — listing agents + vision | OpenAI — GPT-4o-mini |
| Web search | SerpAPI (Google) + Serpex (fallback) |
| Listing scraper | Firecrawl |
| Maps / commute / places | Google Maps Platform (Distance Matrix, Places API New, Geocoding) |
| LLM framework | LangChain |
| Observability | LangSmith |
| Persistence | LangGraph AsyncSqliteSaver |

---

## Evaluation

The evaluation suite in [`evals/`](evals/) covers six component experiments and one end-to-end pipeline experiment:

| Experiment | What it tests |
|---|---|
| `elicitation` | Preference extraction accuracy, question quality |
| `planner` | Search query format, diversity, retry novelty |
| `search` | SerpAPI result precision, yield, relevance |
| `listing_agent` | Field extraction F1, disqualification accuracy, tool efficiency |
| `image` | Photo analysis accuracy vs. human labels |
| `reducer` | Ranking accuracy, trade-off application |
| `end_to_end` | Full pipeline — Kendall τ vs. human gold rankings on 30-listing static corpus |

The end-to-end experiment runs against a fixed 30-listing corpus ([`evals/datasets/static_listings.json`](evals/datasets/static_listings.json)) with human-labeled gold rankings. All LLM judges run on Claude Sonnet 4.6.

```bash
# Run everything
python -m evals.run_evals

# Just the end-to-end experiment
python -m evals.run_evals --experiments end_to_end
```

See [`evals/README.md`](evals/README.md) for full documentation.

---

## Project Structure

```
rental_market_analyzer/
├── server.py                  # FastAPI app, WebSocket handler, session management
├── graph/
│   ├── builder.py             # LangGraph graph definition and compilation
│   ├── state.py               # TypedDicts: RentalState, PreferenceState, ListingProfile
│   ├── llm.py                 # Centralized model/provider resolution
│   └── nodes/
│       ├── intent_router.py   # Classify → route to elicitation/chat/tool/off-topic
│       ├── elicitation.py     # Extract preferences, generate follow-up questions
│       ├── planner.py         # Generate search queries from preferences
│       ├── search_node.py     # SerpAPI search, URL filtering
│       ├── supervisor.py      # Deduplicate URLs, spawn listing agents via Send()
│       ├── listing_agent.py   # ReAct agent per listing
│       ├── results_check.py   # Gate: enough good results? retry or proceed
│       ├── reducer.py         # Rank and filter final profiles
│       └── analyzer.py        # Market pattern analysis
├── graph/tools/
│   ├── scraper.py             # Firecrawl listing extraction
│   ├── search.py              # SerpAPI + Serpex web search
│   ├── commute.py             # Google Distance Matrix
│   ├── places.py              # Google Places API
│   └── photos.py              # GPT-4o-mini vision analysis
├── frontend/src/
│   ├── App.tsx                # Main layout, sort/filter, keyboard shortcuts, match scoring
│   ├── hooks/
│   │   ├── useChat.ts         # WebSocket client, session management, message state
│   │   ├── useListingPrefs.ts # Favorites + compare list (localStorage)
│   │   └── useToast.tsx       # Toast notification system
│   └── components/
│       ├── ListingCard.tsx    # Card with photo lightbox, match score, agent's take
│       ├── ListingMap.tsx     # Google Maps with price-bubble pins, hover sync
│       ├── ListingControls.tsx# Sort dropdown, filter pills, CSV export
│       ├── CompareDrawer.tsx  # Side-by-side comparison table
│       ├── ProcessSteps.tsx   # Live pipeline progress visualization
│       ├── Sidebar.tsx        # Session history, click-to-toggle
│       └── KeyboardShortcuts.tsx
├── evals/                     # Evaluation suite (7 experiments)
├── scripts/                   # Smoke tests, graph printer
└── SETUP.md                   # Full setup and run instructions
```
