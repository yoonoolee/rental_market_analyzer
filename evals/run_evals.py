"""
Master eval runner.

Usage:
    python -m evals.run_evals                     # run all experiments
    python -m evals.run_evals --experiments search image
    python -m evals.run_evals --variants baseline low_temp
    python -m evals.run_evals --experiments search --variants baseline_5 expanded_10

Results are saved to evals/results/<experiment>_eval.json and a summary to
evals/results/summary.json.
"""
import argparse
import json
import time

from evals.config import RESULTS_DIR

EXPERIMENT_REGISTRY = {
    "search":       ("evals.experiments.eval_search",        "run"),
    "image":        ("evals.experiments.eval_image_analysis","run"),
    "elicitation":  ("evals.experiments.eval_elicitation",   "run"),
    "planner":      ("evals.experiments.eval_planner",       "run"),
    "listing_agent":("evals.experiments.eval_listing_agent", "run"),
    "reducer":      ("evals.experiments.eval_reducer",       "run"),
    "end_to_end":   ("evals.experiments.eval_end_to_end",    "run"),
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
        for variant_name, data in results.items():
            agg = data.get("aggregate", {})
            metrics_str = "  ".join(f"{k}={v}" for k, v in agg.items())
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
    args = parser.parse_args()

    experiments = ALL_EXPERIMENTS if "all" in args.experiments else args.experiments

    print(f"Running evals: {experiments}")
    if args.variants:
        print(f"Filtering variants: {args.variants}")
    print()

    all_results = {}
    start = time.time()

    for exp in experiments:
        print(f"▶ {exp}")
        try:
            results = run_experiment(exp, args.variants)
            all_results[exp] = results
            print(f"  ✓ done\n")
        except Exception as e:
            print(f"  ✗ FAILED: {e}\n")
            all_results[exp] = {"error": str(e)}

    elapsed = round(time.time() - start, 1)
    print(f"Total time: {elapsed}s")

    # Save combined summary
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2))
    print(f"Summary saved → {summary_path}")

    print_summary(all_results)


if __name__ == "__main__":
    main()
