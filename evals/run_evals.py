"""
Master eval runner.

Usage:
    python -m evals.run_evals                     # run all experiments
    python -m evals.run_evals --experiments search image
    python -m evals.run_evals --variants baseline low_temp no_analyzer
    python -m evals.run_evals --experiments search --variants baseline_5 expanded_10

Results are saved to evals/results/<experiment>_eval.json and a summary to
evals/results/summary.json.
"""
import argparse
import json
import time

import os
import openai
import anthropic
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt
from collections import namedtuple

class MockContent:
    def __init__(self, text):
        self.text = text

class MockResponse:
    def __init__(self, text, in_tok, out_tok):
        self.content = [MockContent(text)]
        Usage = namedtuple("Usage", ["input_tokens", "output_tokens"])
        self.usage = Usage(in_tok, out_tok)

def route_to_openai(kwargs):
    client = openai.OpenAI()
    
    model = kwargs.get("model", "")
    o_model = "gpt-4o-mini" # Map everything to mini to avoid strict rate limits on gpt-4o
        
    o_messages = []
    if "system" in kwargs:
        o_messages.append({"role": "system", "content": kwargs["system"]})
        
    for msg in kwargs.get("messages", []):
        if isinstance(msg.get("content"), list):
            o_content = []
            for block in msg["content"]:
                if block.get("type") == "text":
                    o_content.append({"type": "text", "text": block["text"]})
                elif block.get("type") == "image":
                    src = block["source"]
                    o_content.append({
                        "type": "image_url", 
                        "image_url": {"url": f"data:{src['media_type']};base64,{src['data']}"}
                    })
            o_messages.append({"role": msg["role"], "content": o_content})
        else:
            o_messages.append(msg)
            
    resp = client.chat.completions.create(
        model=o_model,
        messages=o_messages,
        max_tokens=kwargs.get("max_tokens", 1024),
        temperature=kwargs.get("temperature", 0.2)
    )
    
    text = resp.choices[0].message.content.strip()
    if text.startswith("```json"):
        text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
    elif text.startswith("```"):
        text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
    text = text.strip()
            
    usage = resp.usage
    return MockResponse(
        text=text,
        in_tok=usage.prompt_tokens if usage else 0,
        out_tok=usage.completion_tokens if usage else 0
    )

original_create = anthropic.resources.Messages.create

@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, openai.RateLimitError)),
    wait=wait_exponential(multiplier=15, min=15, max=60),
    stop=stop_after_attempt(10),
    before_sleep=lambda retry_state: print(f"  [Rate limit hit, pausing for {retry_state.next_action.sleep}s to cool down...]")
)
def rate_limited_create(self, *args, **kwargs):
    provider = os.getenv("EVAL_PROVIDER", "anthropic").strip().lower()
    
    # Force Anthropic for vision/image tasks even if provider is set to OpenAI
    # because user wants higher quality vision analysis
    has_images = False
    for msg in kwargs.get("messages", []):
        if not isinstance(msg, dict): continue
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "image":
                    has_images = True
                    break
        if has_images: break

    if provider == "openai" and not has_images:
        return route_to_openai(kwargs)
    return original_create(self, *args, **kwargs)

anthropic.resources.Messages.create = rate_limited_create

from evals.config import RESULTS_DIR

EXPERIMENT_REGISTRY = {
    "search":       ("evals.experiments.eval_search",        "run"),
    "image":        ("evals.experiments.eval_image_analysis","run"),
    "elicitation":  ("evals.experiments.eval_elicitation",   "run"),
    "planner":      ("evals.experiments.eval_planner",       "run"),
    "listing_agent":("evals.experiments.eval_listing_agent", "run"),
    "reducer":      ("evals.experiments.eval_reducer",       "run"),
    "end_to_end":   ("evals.experiments.eval_end_to_end",    "run"),
    "bias":         ("evals.experiments.eval_bias",          "run"),
}

ALL_EXPERIMENTS = list(EXPERIMENT_REGISTRY.keys())


def run_experiment(name: str, variants: list[str] | None = None) -> dict:
    import importlib
    module_path, fn_name = EXPERIMENT_REGISTRY[name]
    module = importlib.import_module(module_path)
    fn = getattr(module, fn_name)
    return fn(variants=variants)


def print_summary(all_results: dict):
    """Print a comparison table of aggregate metrics per experiment."""
    print("\n" + "=" * 70)
    print("EVAL SUMMARY")
    print("=" * 70)

    for exp_name, results in all_results.items():
        print(f"\n── {exp_name.upper().replace('_', ' ')} ──")
        if isinstance(results, dict) and "error" in results:
            print(f"  [error] {results['error']}")
            continue
        for variant_name, data in results.items():
            if isinstance(data, dict):
                agg = data.get("aggregate", {})
                metrics_str = "  ".join(f"{k}={v}" for k, v in agg.items())
            else:
                metrics_str = str(data)
            print(f"  [{variant_name}] {metrics_str}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Run rental market analyzer evals")
    parser.add_argument(
        "--experiments", nargs="+", choices=ALL_EXPERIMENTS + ["all"],
        default=["all"], help="Which experiments to run"
    )
    parser.add_argument(
        "--variants", nargs="+", default=None,
        help="Which variant names to run (applies to all selected experiments)"
    )
    parser.add_argument(
        "--slim", action="store_true", help="Run in slim mode (fewer samples/listings)"
    )
    args = parser.parse_args()

    # Pass slim flag to environment so experiment scripts can pick it up
    if args.slim:
        os.environ["EVAL_SLIM"] = "true"

    experiments = ALL_EXPERIMENTS if "all" in args.experiments else args.experiments

    print(f"Running evals: {experiments}")
    if args.variants:
        print(f"Filtering variants: {args.variants}")
    if args.slim:
        print("SLIM MODE ENABLED (reduced sample count)")
    print()

    # Load existing summary to merge if it exists
    summary_path = RESULTS_DIR / "summary.json"
    if summary_path.exists():
        try:
            all_results = json.loads(summary_path.read_text())
        except:
            all_results = {}
    else:
        all_results = {}

    start = time.time()

    for exp in experiments:
        print(f"▶ {exp}")
        try:
            results = run_experiment(exp, args.variants)
            all_results[exp] = results
            print(f"  ✓ done\n")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ✗ FAILED: {e}\n")
            all_results[exp] = {"error": str(e)}

    elapsed = round(time.time() - start, 1)
    print(f"Total time: {elapsed}s")

    # Save combined summary
    summary_path.write_text(json.dumps(all_results, indent=2))
    print(f"Summary saved → {summary_path}")

    print_summary(all_results)


if __name__ == "__main__":
    main()
