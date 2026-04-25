# Setup & Run Guide

This guide walks through setting up the project from scratch and testing it end-to-end. Target audience: a grader or teammate who has cloned the repo and never run it.

---

## 1. Prerequisites

- **Python 3.10+** (project was developed against 3.12/3.14; 3.10 is the minimum for the type-hint syntax used).
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

| Env var | Where to get it | Cost notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/ → API Keys | Pay-as-you-go; Haiku/Sonnet pricing on their site |
| `SERPAPI_API_KEY` | https://serpapi.com/manage-api-key | 100 free searches/month; paid plans after |
| `FIRECRAWL_API_KEY` | https://www.firecrawl.dev/app/api-keys | 500 free scrapes/month on the Hobby tier |
| `GOOGLE_MAPS_API_KEY` | https://console.cloud.google.com/ → APIs & Services → Credentials | $200/mo free credit from Google; **must enable Distance Matrix API, Places API, and Geocoding API on that project** |
| `LANGCHAIN_API_KEY` (optional) | https://smith.langchain.com/ → Settings → API Keys | Free personal tier is enough for traces |

### Minimum keys to boot the app

- `ANTHROPIC_API_KEY` — required (every node uses Claude).
- `SERPAPI_API_KEY` — required for the search stage.
- `FIRECRAWL_API_KEY` — required for the scrape stage.
- `GOOGLE_MAPS_API_KEY` — required if users mention commutes or nearby places; otherwise the tool-call intent router path will return errors for those specific queries.

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

## 6. End-to-end smoke test (no Chainlit)

This exercises all four intent-router branches plus one full search pipeline run, using an in-memory checkpointer so nothing persists:

```bash
python -m scripts.smoke_test_graph
```

Expect ~3–5 minutes for the full-pipeline test (it hits SerpAPI + Firecrawl + Google Maps + Claude many times).

---

## 7. Run the Chainlit app

```bash
chainlit run app.py -w
```

`-w` enables auto-reload on file changes. The UI opens at http://localhost:8000.

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

You can also trigger the suite from the Chainlit UI: type `/evals` in the chat.

---

## 9. Common issues

**`ModuleNotFoundError: No module named 'langgraph'`** — your venv isn't activated. Run `source .venv/bin/activate`.

**`anthropic.APIError: Authentication failed`** — `ANTHROPIC_API_KEY` is missing or wrong in `.env`.

**Google Maps returns `REQUEST_DENIED`** — the API key exists but the three required APIs (Distance Matrix, Places, Geocoding) aren't enabled on that Cloud project. Enable them in the Google Cloud console.

**SerpAPI returns no organic results** — you've exhausted the 100 free searches, or the site is blocking the query. Check the dashboard.

**Firecrawl errors on a specific URL** — some listing sites block scrapers. Not every URL will work; the pipeline gracefully skips failed scrapes and marks those listings disqualified.

**`rental_state.db` growing large** — delete it to reset all conversations.

**Chainlit UI shows blank on refresh** — this is expected; the LLM still has full context via the SQLite checkpointer, but visual chat replay requires a Chainlit data layer (see the README TODO).

---

## 10. What to show for the submission

Checklist for a grader to verify everything works:

- [ ] `python -m scripts.smoke_test_tools` → all 5 tools PASS
- [ ] `python -m scripts.print_graph` → 9 nodes listed, matches README diagram
- [ ] `python -m scripts.smoke_test_graph` → all 5 intent branches produce the right response shape
- [ ] `chainlit run app.py -w` → can complete a full search end-to-end
- [ ] `python -m evals.run_evals --experiments end_to_end --variants baseline` → `end_to_end_eval.json` written with non-zero metrics
- [ ] LangSmith dashboard (if enabled) shows traces with per-node names

If you only have time for one command: run **`python -m scripts.smoke_test_graph`** — it exercises the whole architecture.
