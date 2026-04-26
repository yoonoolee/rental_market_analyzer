"""
Shared configuration for all eval experiments.
Copy .env from the rental_market_analyzer project or set env vars directly.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Models ──────────────────────────────────────────────────────────────────
JUDGE_MODEL = "claude-sonnet-4-6"          # LLM-as-judge
SONNET_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

# ── API Keys ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY")

# ── Paths ────────────────────────────────────────────────────────────────────
EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"
DATASETS_DIR = EVALS_DIR / "datasets"
RESULTS_DIR.mkdir(exist_ok=True)

# ── Experiment Variants ──────────────────────────────────────────────────────

SEARCH_VARIANTS = {
    "baseline_5":  {"num_results": 5},          # current production setting
    "reduced_3":   {"num_results": 3},
    "expanded_10": {"num_results": 10},
}

IMAGE_VARIANTS = {
    "sonnet_5img": {"model": SONNET_MODEL, "max_images": 5},
    "haiku_5img":  {"model": HAIKU_MODEL,  "max_images": 5},
    "sonnet_3img": {"model": SONNET_MODEL, "max_images": 3},
}

ELICITATION_VARIANTS = {
    "haiku_sonnet":  {"extraction_model": HAIKU_MODEL,  "chat_model": SONNET_MODEL},  # current
    "haiku_haiku":   {"extraction_model": HAIKU_MODEL,  "chat_model": HAIKU_MODEL},
    "sonnet_sonnet": {"extraction_model": SONNET_MODEL, "chat_model": SONNET_MODEL},
}

PLANNER_VARIANTS = {
    "baseline":  {"temperature": 0.2, "use_few_shot": False},   # current
    "low_temp":  {"temperature": 0.0, "use_few_shot": False},
    "few_shot":  {"temperature": 0.2, "use_few_shot": True},
}

LISTING_AGENT_VARIANTS = {
    "sonnet_conditional": {"model": SONNET_MODEL, "always_use_all_tools": False},  # current
    "haiku_conditional":  {"model": HAIKU_MODEL,  "always_use_all_tools": False},
    "sonnet_all_tools":   {"model": SONNET_MODEL, "always_use_all_tools": True},
}

REDUCER_VARIANTS = {
    "baseline":  {"temperature": 0.4, "chain_of_thought": False},  # current
    "low_temp":  {"temperature": 0.1, "chain_of_thought": False},
    "cot":       {"temperature": 0.4, "chain_of_thought": True},
}

END_TO_END_VARIANTS = {
    "baseline":    {"reducer_temperature": 0.4, "analyzer_enabled": True},
    "low_temp":    {"reducer_temperature": 0.1, "analyzer_enabled": True},
    "no_analyzer": {"reducer_temperature": 0.4, "analyzer_enabled": False},
}
