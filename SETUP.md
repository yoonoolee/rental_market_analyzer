# Setup & Run Guide

This guide walks through setting up the project from scratch and testing it end-to-end. Target audience: a grader or teammate who has cloned the repo and never run it.

---

## 1. Prerequisites

- **Python 3.10+** (project was developed against 3.12/3.14; 3.10 is the minimum for the type-hint syntax used).
- **Node.js 20+ and npm** — for the React UI (`frontend/`). Not needed for CLI smoke tests or evals.
- **A shell (bash/zsh)** with `git`, `python3`, and `pip`.

Check:
```bash
python3 --version   # should print Python 3.10+ something
```

---

## 2. Virtual environment

From the project root (`rental_market_analyzer/`):

```bash
# create a venv named .venv in the project folder
python3 -m venv .venv

# activate it (zsh/bash on macOS/Linux)
source .venv/bin/activate

# upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

When activated, your shell prompt shows `(.venv)` at the front. To deactivate later: `deactivate`.

On Windows:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 3. API keys

Copy the template and fill in your keys:

```bash
cp .env.example .env
```

Then open `.env` in a text editor and replace each `your_..._here` placeholder. Never commit `.env` to git (it's already in `.gitignore`).

### Where to get each key

| Env var | Where to get it | Used for |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys | Intent router, elicitation, planner (Llama 3.1/3.3) — free tier |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys | Listing agents + photo analysis (GPT-4o-mini) |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/ → API Keys | Reducer + analyzer (Claude Sonnet 4.6) |
| `SERPAPI_API_KEY` | https://serpapi.com/manage-api-key | Web search — 100 free searches/month |
| `FIRECRAWL_API_KEY` | https://www.firecrawl.dev/app/api-keys | Listing scraper — 500 free scrapes/month |
| `GOOGLE_MAPS_API_KEY` | https://console.cloud.google.com/ → APIs & Services → Credentials | Commute times, nearby places, map geocoding — $200/mo free credit; **enable Distance Matrix API, Places API (New), and Geocoding API** |
| `LANGCHAIN_API_KEY` (optional) | https://smith.langchain.com/ → Settings → API Keys | LangSmith observability traces — free personal tier |

### Minimum keys to run a full search

- `GROQ_API_KEY` — intent router, elicitation, planner
- `OPENAI_API_KEY` — listing agents (reasoning + tool calls) and photo analysis
- `ANTHROPIC_API_KEY` — reducer and analyzer (ranking + market summary)
- `SERPAPI_API_KEY` — search stage
- `FIRECRAWL_API_KEY` — listing scraper
- `GOOGLE_MAPS_API_KEY` — commute times, nearby places, and map pins in the UI

### Runtime tuning knobs (optional)

In `.env`, these defaults are safe for local runs:

```bash
LLM_PROVIDER=groq
LISTING_CONCURRENCY=3
MAX_PHOTOS=12
```

- `LLM_PROVIDER` chooses text-model backend (`groq` default, `anthropic` optional fallback).
- `LISTING_CONCURRENCY` controls max parallel listing-agent runs.
- `MAX_PHOTOS` caps images sent to vision analysis per listing.

### LangSmith (optional but recommended for the submission)

In `.env`, set:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your_langsmith_key>
LANGCHAIN_PROJECT=rental-market-analyzer
```

Then every graph invocation automatically streams a trace to https://smith.langchain.com/. Useful for the final report's observability story.

---

## 4. Smoke-test the tools

Before running the full app, verify each tool works against the live APIs.

```bash
python -m scripts.smoke_test_tools
```

This runs all five tools in sequence (commute, places, search, scraper, photos) and prints a PASS/FAIL summary at the end.

---

## 5. Print the compiled graph

Verify the architecture compiles and looks like the README diagram:

```bash
python -m scripts.print_graph
```

You should see the nine nodes: `intent_router`, `elicitation`, `planner`, `search_node`, `supervisor`, `listing_agent`, `results_check`, `reducer`, `analyzer`.

---

## 6. End-to-end smoke test (no web UI)

This exercises all four intent-router branches plus one full search pipeline run, using an in-memory checkpointer so nothing persists:

```bash
python -m scripts.smoke_test_graph
```

Expect ~3–5 minutes for the full-pipeline test (it hits SerpAPI + Firecrawl + Google Maps + Claude many times).

Optional: slow down between intent-router test turns (defaults to 2s) to reduce API rate issues: `SMOKE_THROTTLE_SEC=0 python -m scripts.smoke_test_graph`

---

## 7. Run the web app (FastAPI + React)

Build the frontend once, then start uvicorn. FastAPI serves the built UI from `frontend/dist` — one process, one port.

```bash
cd frontend && npm install && npm run build && cd ..
uvicorn server:app --reload --port 8000
```

Or use the convenience script:

```bash
./start.sh
```

Open **http://localhost:8000** in the browser.

**Maps in the UI:** add a `frontend/.env` file with your Google Maps key before building:

```bash
echo "VITE_GOOGLE_MAPS_KEY=your_key_here" > frontend/.env
```

Vite bakes this into the built bundle, so it must be set before `npm run build`. Without it, everything works except the map panel.

**After making frontend changes**, rebuild before restarting:

```bash
cd frontend && npm run build && cd ..
uvicorn server:app --reload --port 8000
```

Try these to exercise every path:

| Message | Expected route |
|---|---|
| `Write me a poem about cats` | `off_topic` — polite decline, no pipeline |
| `What's the difference between a studio and a 1BR?` | `conversational` — direct Claude answer |
| `How long from 4521 Telegraph Ave Oakland to UC Berkeley by transit?` | `tool_call` — direct commute lookup |
| `Find gyms near 2090 Kittredge St Berkeley` | `tool_call` — direct places lookup |
| `Looking for 1BR Oakland under $2100, pet-friendly, close to BART` | `needs_search` — full elicitation → ... → recommendations |

Conversation state persists across page refresh via the SQLite checkpointer (`rental_state.db` in the project root).

---

## 8. Run the evaluation suite

The suite has 7 experiments:

```bash
# everything (slow — budget 10–20 minutes + API cost)
python -m evals.run_evals

# just the reproducible end-to-end eval (recommended for submission verification)
python -m evals.run_evals --experiments end_to_end

# one experiment + one variant (fastest)
python -m evals.run_evals --experiments end_to_end --variants baseline
```

Results land in `evals/results/`:
- Per-experiment JSON (`end_to_end_eval.json`, `elicitation_eval.json`, etc.)
- Combined `summary.json`

---

## 9. Common issues

**`ModuleNotFoundError: No module named 'langgraph'`** — your venv isn't activated. Run `source .venv/bin/activate`.

**`anthropic.APIError: Authentication failed`** — `ANTHROPIC_API_KEY` is missing or wrong in `.env`.

**Google Maps returns `REQUEST_DENIED`** — the API key exists but the three required APIs (Distance Matrix, Places, Geocoding) aren't enabled on that Cloud project. Enable them in the Google Cloud console.

**SerpAPI returns no organic results** — you've exhausted the 100 free searches, or the site is blocking the query. Check the dashboard.

**Firecrawl errors on a specific URL** — some listing sites block scrapers. Not every URL will work; the pipeline gracefully skips failed scrapes and marks those listings disqualified.

**`rental_state.db` growing large** — delete it to reset all conversations.

**WebSocket or blank UI in dev** — ensure `uvicorn` is on port 8000 before `npm run dev` (Vite proxies `/ws` to `ws://localhost:8000`). For a single-process setup, use `npm run build` in `frontend/` and open `http://localhost:8000` with only uvicorn running.

---

## 10. What to show for the submission

Checklist for a grader to verify everything works:

- [ ] `python -m scripts.smoke_test_tools` → all 5 tools PASS
- [ ] `python -m scripts.print_graph` → 9 nodes listed, matches README diagram
- [ ] `python -m scripts.smoke_test_graph` → all 5 intent branches produce the right response shape
- [ ] API + Vite dev servers (or built UI + uvicorn) → can complete a full search end-to-end
- [ ] `python -m evals.run_evals --experiments end_to_end --variants baseline` → `end_to_end_eval.json` written with non-zero metrics
- [ ] LangSmith dashboard (if enabled) shows traces with per-node names

If you only have time for one command: run **`python -m scripts.smoke_test_graph`** — it exercises the whole architecture.
