"""
Experiment: Bias and Fairness Evaluation

Variants compared:
  - baseline: Runs extraction on paired counterfactual personas

Held constant:
  - Model: Claude Sonnet 4.6 (Extraction)
  - 3 paired bias test cases (datasets/bias_personas.json)

Metrics:
  - discrepancy_rate: % of pairs where the extracted structured preferences differ (excluding explicit lifestyle notes)
  - hallucinated_constraints: count of instances where the model assumed constraints not present in the text based on demographic markers.
"""
import json
import time
import os
from anthropic import Anthropic

from evals.config import DATASETS_DIR, SONNET_MODEL, RESULTS_DIR
from evals.experiments.eval_elicitation import extract_preferences

def load_bias_datasets():
    path = DATASETS_DIR / "bias_personas.json"
    if not path.exists():
        return []
    with open(path, "r") as f:
        return json.load(f)

def run(variants=None):
    if variants is None:
        variants = ["baseline"]
    
    datasets = load_bias_datasets()
    client = Anthropic()
    
    # SLIM MODE: only use 1 case
    if os.environ.get("EVAL_SLIM") == "true":
        datasets = datasets[:1]
        
    results = {}
    
    for variant in variants:
        discrepancies = 0
        total_pairs = len(datasets)
        details = []
        
        for case in datasets:
            case_id = case["id"]
            keys = list(case["variants"].keys())
            var_A, var_B = keys[0], keys[1]
            
            # Extract for A
            prefs_A, _ = extract_preferences(case["variants"][var_A]["conversation"], SONNET_MODEL, client)
            time.sleep(2) # rate limit
            
            # Extract for B
            prefs_B, _ = extract_preferences(case["variants"][var_B]["conversation"], SONNET_MODEL, client)
            time.sleep(2) # rate limit
            
            # Compare structural fields (ignore lifestyle_notes as those SHOULD differ)
            core_fields = ["bedrooms", "max_price", "min_price", "pet_friendly", "soft_constraints"]
            
            diff_found = False
            field_diffs = {}
            for field in core_fields:
                val_a = prefs_A.get(field)
                val_b = prefs_B.get(field)
                
                # Normalize lists
                if isinstance(val_a, list): val_a = sorted(val_a)
                if isinstance(val_b, list): val_b = sorted(val_b)
                
                if val_a != val_b:
                    diff_found = True
                    field_diffs[field] = {"A": val_a, "B": val_b}
                    
            if diff_found:
                discrepancies += 1
                
            details.append({
                "case": case_id,
                "description": case["description"],
                "discrepancy_found": diff_found,
                "differences": field_diffs,
                "raw_A": prefs_A,
                "raw_B": prefs_B
            })
            
        discrepancy_rate = discrepancies / total_pairs if total_pairs > 0 else 0
        
        results[variant] = {
            "aggregate": {
                "discrepancy_rate": round(discrepancy_rate, 3),
                "fair_cases": total_pairs - discrepancies,
                "total_cases": total_pairs
            },
            "details": details
        }
        
    output_path = RESULTS_DIR / "bias_eval.json"
    output_path.write_text(json.dumps(results, indent=2))
    print(f"  Results saved → {output_path}")
    return results

if __name__ == "__main__":
    print(json.dumps(run(["baseline"]), indent=2))
