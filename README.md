# Rental Market Analyzer

A conversational apartment-hunting agent built as part of INFO 290: Generative AI at UC Berkeley. The idea came from a pretty universal pain point - searching for a rental is tedious, results are scattered across a dozen sites, and standard search filters don't capture the nuance of what people actually care about (commute time, noise level, whether there's a good gym nearby, etc.).

This project explores what a better version of that experience could look like when you combine a conversational LLM with real-time web search, parallel multi-agent research, and structured preference reasoning.

---

## What It Does

The system talks with you first. Rather than making you fill out a form, it asks a few targeted questions to understand your priorities - budget, location, commute destinations, lifestyle preferences, and importantly, how you'd trade those off against each other. Once it has enough to go on, it finds candidate listings, then spins up a research agent per listing that decides what tools to call based on your specific situation. Someone with a dog gets pet policy checked immediately. Someone who cares about a bar scene gets a places lookup for that. Someone who didn't mention grocery stores doesn't waste an API call on it.

The result is a ranked recommendation list built from real data - actual commute times, actual nearby places, actual listing details - not inferred from search snippets.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Chainlit UI                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ user message
                            ▼
                    ┌───────────────┐
                    │  Elicitation  │  Claude Haiku (extract prefs)
                    │     Node      │  Claude Sonnet (generate question)
                    └───────┬───────┘
                            │ ready_to_search = True
                            ▼
                    ┌───────────────┐
                    │    Planner    │  generates listing-discovery queries only
                    │     Node      │  retry-aware: avoids previously run queries
                    └───────┬───────┘
                            │ search queries
                            ▼
             ┌──────────────────────────────┐
             │     Parallel Search Nodes    │  SerpAPI - finds listing URLs
             │  [query1] [query2] [query3]  │
             └──────────────┬───────────────┘
                            │ candidate URLs
                            ▼
                    ┌───────────────┐
                    │   Supervisor  │◄──────────────────────┐
                    │     Node      │                       │
                    └───────┬───────┘                       │
                            │ spawns one agent per new URL  │
                            ▼                               │
┌───────────────────────────────────────────────────┐       │
│              Parallel ReAct Listing Agents        │       │
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
                │ Results Check │  counts good results      │
                │     Node      ├──── < 10 good? ───────────┘
                │               │     retry with new queries
                └───────┬───────┘
                        │ >= 10 good results (or max attempts hit)
                        ▼
                ┌───────────────┐
                │    Reducer    │  ranks with real structured data
                │     Node      │  applies trade-off rules against actual numbers
                └───────┬───────┘
                        │ final profiles + disqualified profiles
                        ▼
                ┌───────────────┐
                │    Analyzer   │  surfaces patterns across all results
                │     Agent     │  e.g. budget too low, neighborhood commute mismatch
                └───────┬───────┘
                        │
                        ▼
             ranked recommendations
             with links + images + insights
```

---

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

## TODO

- Analyzer agent - after the reducer runs, a separate agent reviews both the final ranked listings and the disqualified ones to surface patterns that might be useful to the user (e.g. most listings in their budget don't allow pets, commute times are consistently longer than expected in their target neighborhood, disqualified listings were mostly due to price - maybe the budget needs adjusting)
- `find_nearby_places` tool - currently a stub; implement using Google Places API (nearbysearch endpoint) with a geocode step to convert address to lat/lng first (requires `GOOGLE_PLACES_API_KEY`)
- `get_commute_time` tool - currently a stub; implement using Google Maps Distance Matrix API via the `googlemaps` SDK (requires `GOOGLE_MAPS_API_KEY`)
- LangSmith observability - add tracing across graph traces (node inputs/outputs, latency, token usage)
- Evals - approach TBD, still deciding what "good" looks like (preference adherence, ranking quality, etc.)
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
| LLM framework | LangChain |
| Observability | LangSmith (planned) |
