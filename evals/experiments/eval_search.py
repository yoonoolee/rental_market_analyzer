"""
Experiment: Internet Search (SerpAPI) Quality

Variants compared:
  - baseline_5:  5 results per query  (current production)
  - reduced_3:   3 results per query
  - expanded_10: 10 results per query

Held constant:
  - Query set (generated from pref_001 preferences)
  - SerpAPI GoogleSearch engine
  - site: operators (craigslist, zillow, apartments, trulia, hotpads)

Metrics:
  - listing_precision   : % of returned URLs that are valid rental listings (LLM-as-judge)
  - query_relevance     : LLM judge score (1-10) for result relevance to query
  - embedding_similarity: cosine similarity between query and aggregated snippet text
  - yield_rate          : % of queries returning >= 1 valid listing URL
  - latency_ms          : wall-clock time per query
  - api_credits_used    : estimated SerpAPI credits (1 per query, tracked manually)
"""
import json
import time
from pathlib import Path

from evals.config import SERPAPI_KEY, RESULTS_DIR, SEARCH_VARIANTS
from evals.metrics.nlp import LatencyTimer, embedding_similarity
from evals.metrics.llm_judge import LLMJudge

# Representative queries derived from pref_001 preferences
TEST_QUERIES = [
    "2 bedroom apartment for rent San Francisco under $3000 site:craigslist.org",
    "2br apartment San Francisco $2000-$3000 site:zillow.com inurl:homedetails",
    "2 bedroom pet friendly apartment San Francisco max $3000 site:apartments.com",
    "2 bedroom apartment near Salesforce Tower San Francisco site:trulia.com",
    "2br flat San Francisco SOMA Mission $2500 $3000 site:hotpads.com",
]


def run_single_query(query: str, num_results: int) -> dict:
    """Execute one SerpAPI query and return stripped results + metadata."""
    from serpapi import GoogleSearch  # google-search-results package

    with LatencyTimer() as timer:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": num_results,
            "engine": "google",
        }
        results_raw = GoogleSearch(params).get_dict()

    organic = results_raw.get("organic_results", [])[:num_results]
    stripped = [
        {"title": r.get("title", ""), "link": r.get("link", ""), "snippet": r.get("snippet", "")}
        for r in organic
    ]
    return {"query": query, "results": stripped, "latency_ms": timer.elapsed_ms}


def evaluate_variant(variant_name: str, config: dict, judge: LLMJudge) -> dict:
    """Run all test queries for a single variant and aggregate metrics."""
    num_results = config["num_results"]
    city = "San Francisco"

    per_query_metrics = []
    for query in TEST_QUERIES:
        result = run_single_query(query, num_results)
        urls_with_snippets = result["results"]

        # --- listing_precision (LLM-as-judge per URL) ---
        precision_scores = []
        for item in urls_with_snippets:
            j = judge.is_valid_listing_url(item["link"], city, item["snippet"])
            precision_scores.append(j.get("score", 0))
        listing_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0.0

        # --- query_relevance (LLM judge, 1-10) ---
        results_text = "\n".join(
            f"- {r['title']}: {r['snippet']}" for r in urls_with_snippets
        )
        relevance_judge = judge.query_relevance(query, results_text)
        query_relevance = relevance_judge.get("score", 0)

        # --- embedding_similarity (query vs. aggregated snippets) ---
        all_snippets = " ".join(r["snippet"] for r in urls_with_snippets)
        emb_sim = embedding_similarity(query, all_snippets) if all_snippets else 0.0

        # --- yield_rate (>= 1 valid listing URL) ---
        has_valid = any(s == 1 for s in precision_scores)

        per_query_metrics.append({
            "query": query,
            "num_returned": len(urls_with_snippets),
            "listing_precision": round(listing_precision, 3),
            "query_relevance": query_relevance,
            "embedding_similarity": emb_sim,
            "has_valid_listing": has_valid,
            "latency_ms": result["latency_ms"],
        })

    # --- aggregate ---
    n = len(per_query_metrics)
    return {
        "variant": variant_name,
        "config": config,
        "per_query": per_query_metrics,
        "aggregate": {
            "mean_listing_precision": round(sum(m["listing_precision"] for m in per_query_metrics) / n, 3),
            "mean_query_relevance": round(sum(m["query_relevance"] for m in per_query_metrics) / n, 2),
            "mean_embedding_similarity": round(sum(m["embedding_similarity"] for m in per_query_metrics) / n, 4),
            "yield_rate": round(sum(1 for m in per_query_metrics if m["has_valid_listing"]) / n, 3),
            "mean_latency_ms": round(sum(m["latency_ms"] for m in per_query_metrics) / n, 1),
            "estimated_api_credits": n,  # 1 credit per query
        },
    }


def run(variants: list[str] | None = None) -> dict:
    """
    Run search eval across specified variants (default: all).
    Returns aggregated results dict and saves to results/search_eval.json.
    """
    judge = LLMJudge()
    targets = variants or list(SEARCH_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = SEARCH_VARIANTS[name]
        print(f"  Running search variant: {name} (num_results={config['num_results']})")
        all_results[name] = evaluate_variant(name, config, judge)

    output_path = RESULTS_DIR / "search_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
