"""
Experiment: Claude Image Analysis (analyze_listing_photos tool)

Variants compared:
  - sonnet_5img : Claude Sonnet 4.6, up to 5 images  (current production)
  - haiku_5img  : Claude Haiku 4.5, up to 5 images
  - sonnet_3img : Claude Sonnet 4.6, up to 3 images

Held constant:
  - Image datasets (datasets/images.json — same URLs + human labels)
  - User preferences per image set
  - Prompt template (replicates graph/tools/photos.py logic)
  - 3 repetitions per image set to measure consistency

Metrics:
  - field_accuracy    : exact match per boolean field vs human labels (precision/recall/F1)
  - consistency_score : LLM-judge score (1-10) comparing run1 vs run2 of same images
  - judge_quality     : LLM-judge score (1-10) for analysis accuracy & usefulness
  - latency_ms        : wall-clock time per image set
  - input_tokens      : Claude API input tokens used
  - cost_usd          : estimated cost (based on published token prices)
"""
import json
import os
import base64
import urllib.request

from anthropic import Anthropic

from evals.config import RESULTS_DIR, IMAGE_VARIANTS, DATASETS_DIR
from evals.metrics.nlp import LatencyTimer, field_f1
from evals.metrics.llm_judge import LLMJudge

# Token cost per million (as of 2026-04 — update as needed)
COST_PER_M_INPUT = {
    "claude-sonnet-4-6": 3.00,
    "claude-haiku-4-5-20251001": 0.80,
}
COST_PER_M_OUTPUT = {
    "claude-sonnet-4-6": 15.00,
    "claude-haiku-4-5-20251001": 4.00,
}

ANALYSIS_SYSTEM_PROMPT = """You are analyzing apartment listing photos.
Return ONLY valid JSON with exactly these fields:
{
  "modern_finishes": <true|false>,
  "natural_light": <true|false>,
  "spacious": <true|false>,
  "condition": <"excellent"|"good"|"dated"|"poor">,
  "notes": "<concise 1-2 sentence summary>"
}
Do not include any text outside the JSON object."""


def fetch_image_as_base64(url: str) -> tuple[str, str]:
    """Fetch image URL, return (base64_data, media_type)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    return base64.b64encode(data).decode(), content_type


def build_image_content(image_urls: list[str], max_images: int) -> list[dict]:
    """Build Anthropic message content blocks for images."""
    content = []
    for url in image_urls[:max_images]:
        try:
            b64, media_type = fetch_image_as_base64(url)
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            })
        except Exception as e:
            print(f"    Warning: could not fetch image {url}: {e}")
    content.append({"type": "text", "text": "Analyze these apartment photos as instructed."})
    return content


def analyze_photos(
    image_urls: list[str],
    model: str,
    max_images: int,
    client: Anthropic,
) -> tuple[dict, dict]:
    """Run photo analysis. Returns (parsed_result, usage_stats)."""
    content = build_image_content(image_urls, max_images)

    with LatencyTimer() as timer:
        resp = client.messages.create(
            model=model,
            max_tokens=512,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

    raw = resp.content[0].text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}") + 1
        parsed = json.loads(raw[start:end]) if start != -1 and end > start else {}

    input_tokens = resp.usage.input_tokens
    output_tokens = resp.usage.output_tokens
    cost = (
        input_tokens / 1_000_000 * COST_PER_M_INPUT.get(model, 3.0)
        + output_tokens / 1_000_000 * COST_PER_M_OUTPUT.get(model, 15.0)
    )

    return parsed, {
        "latency_ms": timer.elapsed_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
    }


def evaluate_variant(variant_name: str, config: dict, image_sets: list[dict], judge: LLMJudge) -> dict:
    model = config["model"]
    max_images = config["max_images"]
    client = Anthropic()

    per_set_metrics = []
    for img_set in image_sets:
        set_id = img_set["id"]
        urls = img_set["image_urls"]
        human_labels = img_set["human_labels"]
        focus_areas = img_set.get("focus_areas", [])
        preferences = {"focus_areas": focus_areas}

        # Run 3 times to measure consistency
        runs = []
        all_usage = []
        for _ in range(3):
            result, usage = analyze_photos(urls, model, max_images, client)
            runs.append(result)
            all_usage.append(usage)

        # field_accuracy: compare run[0] to human labels (boolean fields only)
        boolean_fields = {
            k: v for k, v in human_labels.items()
            if isinstance(v, bool)
        }
        f1_result = field_f1(runs[0], boolean_fields)

        # condition accuracy (string exact match)
        condition_correct = runs[0].get("condition") == human_labels.get("condition")

        # consistency: judge run[0] vs run[1]
        consistency = judge.photo_analysis_consistency(runs[0], runs[1])

        # judge_quality: judge run[0] against human labels
        quality = judge.photo_analysis_quality(runs[0], urls, preferences)

        # avg usage
        avg_latency = sum(u["latency_ms"] for u in all_usage) / len(all_usage)
        avg_tokens = sum(u["input_tokens"] for u in all_usage) / len(all_usage)
        avg_cost = sum(u["cost_usd"] for u in all_usage) / len(all_usage)

        per_set_metrics.append({
            "set_id": set_id,
            "field_accuracy_f1": f1_result["micro_f1"],
            "per_field_f1": f1_result["per_field"],
            "condition_correct": condition_correct,
            "consistency_score": consistency.get("score"),
            "consistency_rationale": consistency.get("rationale"),
            "quality_score": quality.get("score"),
            "quality_rationale": quality.get("rationale"),
            "avg_latency_ms": round(avg_latency, 1),
            "avg_input_tokens": round(avg_tokens),
            "avg_cost_usd": round(avg_cost, 6),
            "runs": runs,
        })

    n = len(per_set_metrics)
    return {
        "variant": variant_name,
        "config": config,
        "per_set": per_set_metrics,
        "aggregate": {
            "mean_field_accuracy_f1": round(sum(m["field_accuracy_f1"] for m in per_set_metrics) / n, 3),
            "condition_accuracy": round(sum(1 for m in per_set_metrics if m["condition_correct"]) / n, 3),
            "mean_consistency_score": round(sum(m["consistency_score"] or 0 for m in per_set_metrics) / n, 2),
            "mean_quality_score": round(sum(m["quality_score"] or 0 for m in per_set_metrics) / n, 2),
            "mean_latency_ms": round(sum(m["avg_latency_ms"] for m in per_set_metrics) / n, 1),
            "mean_cost_usd": round(sum(m["avg_cost_usd"] for m in per_set_metrics) / n, 6),
        },
    }


def run(variants: list[str] | None = None) -> dict:
    """
    Run image analysis eval.

    NOTE: The image URLs in datasets/images.json are placeholders.
    Replace them with real Zillow/Craigslist photo URLs before running.
    """
    dataset = json.loads((DATASETS_DIR / "images.json").read_text())
    
    # SLIM MODE: only use 1 image set
    if os.environ.get("EVAL_SLIM") == "true":
        dataset = dataset[:1]

    judge = LLMJudge()
    targets = variants or list(IMAGE_VARIANTS.keys())

    all_results = {}
    for name in targets:
        config = IMAGE_VARIANTS[name]
        print(f"  Running image analysis variant: {name} (model={config['model']}, max_images={config['max_images']})")
        all_results[name] = evaluate_variant(name, config, dataset, judge)

    output_path = RESULTS_DIR / "image_analysis_eval.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"  Results saved → {output_path}")
    return all_results


if __name__ == "__main__":
    run()
