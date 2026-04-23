# Rental Market Analyzer Evaluations

This directory contains the evaluation suite for the Rental Market Analyzer agent. The evals are designed to test the performance, reasoning, and adherence to preferences across different components of the architecture.

## Overview

The evaluation suite tests individual nodes (e.g., elicitation, planner, search) to ensure they produce high-quality and expected outputs. 

The available experiments are:
- `search`: Evaluates the URL discovery and search query logic.
- `image`: Evaluates the vision analysis of listing photos.
- `elicitation`: Evaluates how well the agent extracts preferences and asks clarifying questions.
- `planner`: Evaluates the generation of search strategies based on user constraints.
- `listing_agent`: Evaluates the ReAct agents that research specific listings.
- `reducer`: Evaluates the final ranking and trade-off analysis.

## How the Evals Validate the System

Because this agent pipeline involves open-ended LLM outputs, the evaluation framework validates the system using a combination of **LLM-as-a-Judge** heuristics and **deterministic checks** over predefined test datasets. 

For each module, the framework injects mocked inputs (such as synthetic user preferences, candidate listings, or simulated chats) and measures key metrics to ensure reliability:
1. **Adherence to Constraints**: Verifies if the planner and search nodes generate queries that strictly respect the user's hard constraints (e.g., budget caps, commute limits).
2. **Preference Extraction Accuracy**: Checks if the `elicitation` node correctly parses out both hard and soft constraints from raw conversational text.
3. **Tool Selection Accuracy**: Evaluates the `listing_agent` to ensure it invokes the correct APIs (like the Google Maps or Places API) *only* when the user's preferences warrant it, preventing wasteful API calls.
4. **Ranking Quality**: The `reducer` eval scores whether the final ranked output logically applies trade-offs, successfully disqualifying listings that fail dealbreakers while appropriately boosting those that hit soft constraints.
5. **Efficiency Metrics**: Tracks token usage and latency across variants to ensure prompt or architecture changes don't degrade the system's speed or cost.

## Running Evaluations

You can run the evaluations from the terminal or directly from the front-end chat interface.

> **Important**: Ensure your `.env` file is properly configured with valid API keys (`ANTHROPIC_API_KEY`, etc.), or the evals will fail with an authentication error.

### 1. Via the Terminal

Run the master eval script from the project root:

```bash
# Run all experiments
python -m evals.run_evals

# Run specific experiments
python -m evals.run_evals --experiments search image

# Run specific variants (e.g., baseline vs. low temperature)
python -m evals.run_evals --variants baseline low_temp

# Combine both
python -m evals.run_evals --experiments search --variants baseline_5 expanded_10
```

### 2. Via the Chainlit Front-end

If the app is running (`chainlit run app.py -w`), you can simply type the following command into the chat box:

```text
/evals
```

The server will asynchronously run the full suite in the background and print a nicely formatted markdown summary directly in the chat window once it's finished.

## Results

Evaluation results are automatically saved to the `evals/results/` directory:
- **Individual Reports**: `evals/results/<experiment>_eval.json`
- **Aggregate Summary**: `evals/results/summary.json`

If an evaluation encounters an error (like missing API keys), the error message will be recorded in the summary file for easy debugging.

### Example Run

Here is an example of what an evaluation summary (`evals/results/summary.json`) looks like after a successful run:

```json
{
  "search": {
    "baseline": {
      "aggregate": {
        "precision": 0.85,
        "recall": 0.92,
        "latency_ms": 1250,
        "token_usage": 1400
      }
    }
  },
  "elicitation": {
    "baseline": {
      "aggregate": {
        "questions_asked": 3.2,
        "preference_extraction_accuracy": 0.95
      }
    }
  }
}
```

When run through the Chainlit front-end using `/evals`, the agent automatically formats this raw data and renders a clean, human-readable summary in the chat:

**SEARCH**
- `baseline`: precision: 0.85 | recall: 0.92 | latency_ms: 1250 | token_usage: 1400

**ELICITATION**
- `baseline`: questions_asked: 3.2 | preference_extraction_accuracy: 0.95
