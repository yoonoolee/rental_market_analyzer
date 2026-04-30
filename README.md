<div align="center">

# 🏠 Real Estate AIgent

**A conversational apartment-hunting agent powered by LangGraph, Claude, and GPT-4o**

*Searches real listings · Researches them in parallel · Returns recommendations grounded in your actual preferences*

---

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3A5E?style=flat)](https://langchain-ai.github.io/langgraph/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-WebSockets-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

Built for **INFO 290: Generative AI** at UC Berkeley

[**Quick Start →**](SETUP.md) · [**Architecture**](#architecture) · [**Features**](#features) · [**Evals**](#evaluation)

</div>

---

## The Problem

Standard rental search is broken. Filters don't capture what people actually care about — commute to a specific building, whether the building is pet-friendly, or how they'd trade a shorter commute for more space. Results are scattered across a dozen sites, and ranking is just price-sorted ad placement.

**Real Estate AIgent** takes a different approach:

1. **Talks with you first** — learns your real priorities, budget, commute destinations, and trade-offs
2. **Dispatches parallel research agents** — one per candidate listing, each calling real APIs to verify real data
3. **Returns ranked recommendations** built from verified commute times, actual nearby places, and real listing details — not keyword matches

---

## Features

<table>
<tr>
<td width="50%">

### 🤖 Conversational Search
- Asks targeted questions to surface priorities, not just keywords
- Skips elicitation when you've been specific enough upfront
- Full conversation history persists across page refreshes (SQLite)

### 🔬 Parallel Multi-Agent Research
- One ReAct agent per candidate listing, all running concurrently
- Each agent picks its own tools based on your preferences — a user with a dog gets pet policy checked first; no wasted API calls on irrelevant data
- Up to 80 candidate listings researched per round

### 📊 Ranked Results + Market Analysis
- Reducer ranks listings against your actual trade-off rules
- Analyzer surfaces cross-cutting patterns: budget gaps, neighborhood trends, what's eliminating options

</td>
<td width="50%">

### 🎨 Professional UI
- **Match score badges** — scored per listing with expandable "why?" breakdown
- **Compare drawer** — side-by-side table for up to 3 listings
- **Interactive map** — price-bubble pins synced to card hover
- **Sort + filter** — by price, commute, sqft, saved, pet-friendly
- **Photo lightbox** — keyboard-navigable fullscreen gallery
- **Agent's take** — inline research notes per listing
- **Live process panel** — progress bar, per-agent status, timing
- **Keyboard shortcuts** — J/K nav, F favorite, C compare, ⌘K new search
- **CSV export** + clipboard share

</td>
</tr>
</table>

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                   FastAPI + React UI (port 8000)                 │
│               AsyncSqliteSaver — thread-scoped persistence       │
└────────────────────────────┬─────────────────────────────────────┘
                             │ WebSocket · user message
                             ▼
                     ┌───────────────┐
                     │ Intent Router │  Llama 3.1 8B — classify
                     └───────┬───────┘
         ┌───────────┬───────┴──────────┬───────────┐
         ▼           ▼                  ▼           ▼
    off_topic   conversational    needs_search   tool_call
    → decline   → answer direct        │         → commute/places
                                       ▼
                               ┌───────────────┐
                               │  Elicitation  │  extract prefs · ask questions
                               └───────┬───────┘
                                       │ ready_to_search
                                       ▼
                               ┌───────────────┐     retry with
                               │    Planner    │◄────new queries
                               └───────┬───────┘
                                       │ 8 search queries
                                       ▼
                       ┌───────────────────────────┐
                       │   Parallel Search Nodes   │  SerpAPI · 10 URLs each
                       │   [q1] [q2] ... [q8]      │  up to 80 candidates
                       └──────────────┬────────────┘
                                      │
                                      ▼
                               ┌───────────────┐
                               │   Supervisor  │  deduplicate URLs
                               └───────┬───────┘
                                       │ one agent per unique URL
                                       ▼
               ┌───────────────────────────────────────────────┐
               │        Parallel ReAct Listing Agents          │
               │           (all running concurrently)          │
               │                                               │
               │  scrape_listing  ·  search_web               │
               │  get_commute_time  ·  find_nearby_places      │
               │  analyze_listing_photos  (GPT-4o-mini vision) │
               └───────────────────────┬───────────────────────┘
                                       │ structured profiles
                                       ▼
                               ┌───────────────┐
                               │ Results Check │  < 20 good? → retry
                               └───────┬───────┘
                                       │ ≥ 20 results
                                       ▼
                               ┌───────────────┐
                               │    Reducer    │  rank · apply trade-offs
                               └───────┬───────┘
                                       ▼
                               ┌───────────────┐
                               │    Analyzer   │  market patterns · budget gaps
                               └───────┬───────┘
                                       ▼
                      ranked recommendations + market analysis
```

---

## How Listing Agents Work

Each agent is a [ReAct](https://arxiv.org/abs/2210.03629) (Reason + Act) loop. It receives one listing URL and your full preference profile, then decides its own tool sequence — there's no fixed pipeline.

**Example** — user has a dog, wants bars nearby, commutes to UC Berkeley:

```
→ scrape_listing(url)
  price and floor found; no pet policy listed

→ user has dog — need to verify before continuing
  search_web("pet policy 4521 Telegraph Ave Oakland")
  result: "pets allowed with $500 deposit"

→ user listed UC Berkeley as commute destination
  get_commute_time("4521 Telegraph Ave", "UC Berkeley", mode="transit")
  result: "14 min BART"

→ user mentioned bars in soft_constraints
  find_nearby_places("4521 Telegraph Ave", "bars")
  result: "Temescal strip 0.1mi"

→ user didn't mention grocery stores — skip that lookup
→ return structured profile
```

A user who didn't mention pets or bars triggers a completely different sequence of tool calls.

---

## Tools

| Tool | API | What it does |
|---|---|---|
| `scrape_listing` | Firecrawl | Structured JSON extraction — price, address, amenities, images |
| `search_web` | SerpAPI + Serpex fallback | Pet policies, additional listing details |
| `analyze_listing_photos` | OpenAI GPT-4o-mini | Vision analysis of listing photos against user preferences |
| `get_commute_time` | Google Distance Matrix | Transit, driving, cycling, walking times to named destinations |
| `find_nearby_places` | Google Places API (New) | Geocoded proximity search for any place type |

---

## LLM Models

| Pipeline Step | Provider | Model | Fallback |
|---|---|---|---|
| Intent classification | Groq | Llama 3.1 8B Instant | OpenAI gpt-4o-mini |
| Intent chat response | Groq | Llama 3.3 70B Versatile | OpenAI gpt-4o |
| Preference extraction | Groq | Llama 3.1 8B Instant | OpenAI gpt-4o-mini |
| Preference chat | Groq | Llama 3.3 70B Versatile | OpenAI gpt-4o |
| Search planning | Groq | Llama 3.3 70B Versatile | OpenAI gpt-4o-mini |
| Listing agent (ReAct) | OpenAI | gpt-4o-mini | — pinned |
| Result reduction | Anthropic | Claude Sonnet 4.6 | OpenAI gpt-4o-mini |
| Market analysis | Anthropic | Claude Sonnet 4.6 | OpenAI gpt-4o-mini |
| Photo vision | OpenAI | gpt-4o-mini | — pinned |

Model selection is centralized in [`graph/llm.py`](graph/llm.py). Override per-role via `RENTAL_MODELS` or globally via `LLM_PROVIDER`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19 · TypeScript · Tailwind CSS v4 · Vite |
| **Backend** | FastAPI · WebSockets |
| **Orchestration** | LangGraph (multi-agent graph) |
| **LLMs** | Groq (Llama) · Anthropic (Claude) · OpenAI (GPT-4o-mini) |
| **Web search** | SerpAPI · Serpex (fallback) |
| **Scraping** | Firecrawl |
| **Maps** | Google Maps Platform — Distance Matrix · Places API · Geocoding |
| **LLM framework** | LangChain |
| **Observability** | LangSmith |
| **Persistence** | LangGraph AsyncSqliteSaver |

---

## Example Listing Profile

Each ReAct agent returns a structured JSON profile. Only preference-relevant fields are populated — no wasted API calls.

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
  "commute_times": { "UC Berkeley, Soda Hall": "13 min BART" },
  "nearby_places": {
    "bars": "Temescal strip 0.1mi",
    "coffee shop": "Bicycle Coffee 0.1mi"
  },
  "natural_light": true,
  "spacious": true,
  "condition": "good",
  "notes": "Classic bungalow with a small yard, walkable to Temescal restaurants"
}
```

---

## Evaluation

The evaluation suite in [`evals/`](evals/) covers 6 component experiments and 1 end-to-end pipeline experiment.

| Experiment | What it measures |
|---|---|
| `elicitation` | Preference extraction accuracy · question quality |
| `planner` | Query format · diversity · retry novelty |
| `search` | SerpAPI result precision · yield · relevance |
| `listing_agent` | Field extraction F1 · disqualification accuracy · tool efficiency |
| `image` | Photo analysis accuracy vs. human labels |
| `reducer` | Ranking accuracy · trade-off application |
| `end_to_end` | Kendall τ vs. human gold rankings on 30-listing static corpus |

All LLM judges use Claude Sonnet 4.6. The end-to-end experiment runs against a fixed 30-listing corpus with human-labeled rankings for reproducibility.

```bash
python -m evals.run_evals                                    # all experiments
python -m evals.run_evals --experiments end_to_end           # just end-to-end
```

See [`evals/README.md`](evals/README.md) for full documentation.

---

## Project Structure

```
rental_market_analyzer/
├── server.py                    # FastAPI app, WebSocket handler, session management
├── graph/
│   ├── builder.py               # LangGraph graph definition and compilation
│   ├── state.py                 # RentalState, PreferenceState, ListingProfile TypedDicts
│   ├── llm.py                   # Centralized model/provider resolution with fallbacks
│   ├── nodes/
│   │   ├── intent_router.py     # Classify → route to elicitation/chat/tool/off-topic
│   │   ├── elicitation.py       # Extract preferences, generate follow-up questions
│   │   ├── planner.py           # Generate diverse search queries from preferences
│   │   ├── search_node.py       # SerpAPI search, URL filtering per listing site
│   │   ├── supervisor.py        # Deduplicate URLs, spawn agents via Send()
│   │   ├── listing_agent.py     # ReAct agent — one per listing URL
│   │   ├── results_check.py     # Gate: enough results? retry or proceed
│   │   ├── reducer.py           # Rank and filter final listing profiles
│   │   └── analyzer.py          # Market pattern analysis across all results
│   └── tools/
│       ├── scraper.py           # Firecrawl structured extraction
│       ├── search.py            # SerpAPI + Serpex web search
│       ├── commute.py           # Google Distance Matrix API
│       ├── places.py            # Google Places API (New)
│       └── photos.py            # GPT-4o-mini vision analysis
├── frontend/src/
│   ├── App.tsx                  # Layout, sort/filter pipeline, match scoring, shortcuts
│   ├── hooks/
│   │   ├── useChat.ts           # WebSocket client, session state, message handling
│   │   ├── useListingPrefs.ts   # Favorites + compare list via localStorage
│   │   └── useToast.tsx         # Toast notification context
│   └── components/
│       ├── ListingCard.tsx      # Card: photo lightbox, match score, agent's take
│       ├── ListingMap.tsx       # Google Maps: price-bubble pins, hover sync
│       ├── ListingControls.tsx  # Sort dropdown, filter pills, CSV export
│       ├── CompareDrawer.tsx    # Side-by-side comparison table (up to 3 listings)
│       ├── ProcessSteps.tsx     # Live pipeline progress: agents, progress bar, timing
│       ├── Sidebar.tsx          # Session history, click-to-toggle
│       └── KeyboardShortcuts.tsx
├── evals/                       # 7-experiment evaluation suite
├── scripts/                     # Smoke tests (tools, graph, end-to-end)
└── SETUP.md                     # Full setup, API keys, and run instructions
```

---

## Quick Start

```bash
# 1. Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env   # then fill in your keys

# 3. Build frontend and start
cd frontend && npm install && npm run build && cd ..
uvicorn server:app --reload --port 8000
```

Open **http://localhost:8000** → type what you're looking for → get results.

Full setup guide with API key instructions, smoke tests, and eval commands: **[SETUP.md](SETUP.md)**
