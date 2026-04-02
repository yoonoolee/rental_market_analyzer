"""
NLP-based metrics: ROUGE, embedding cosine similarity, field-level F1.
"""
import re
import time
import statistics
from typing import Any
from anthropic import Anthropic

# ── ROUGE-L ───────────────────────────────────────────────────────────────────

def _lcs_length(a: list, b: list) -> int:
    """Longest common subsequence length (token lists)."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]


def rouge_l(hypothesis: str, reference: str) -> dict[str, float]:
    """Return ROUGE-L precision, recall, and F1 between two strings."""
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()
    if not hyp_tokens or not ref_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    lcs = _lcs_length(hyp_tokens, ref_tokens)
    precision = lcs / len(hyp_tokens)
    recall = lcs / len(ref_tokens)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


# ── Embedding Cosine Similarity ───────────────────────────────────────────────

def embedding_similarity(text_a: str, text_b: str, client: Anthropic | None = None) -> float:
    """
    Cosine similarity via sentence-transformers (local, free).
    Falls back to a simple token-overlap Jaccard if the library isn't installed.
    """
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer("all-MiniLM-L6-v2")
        vecs = model.encode([text_a, text_b])
        cos = float(
            np.dot(vecs[0], vecs[1])
            / (np.linalg.norm(vecs[0]) * np.linalg.norm(vecs[1]) + 1e-9)
        )
        return round(cos, 4)
    except ImportError:
        # Jaccard fallback
        a_set = set(text_a.lower().split())
        b_set = set(text_b.lower().split())
        if not a_set and not b_set:
            return 1.0
        return round(len(a_set & b_set) / len(a_set | b_set), 4)


# ── Field-level F1 (for structured preference / listing extraction) ───────────

def field_f1(predicted: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """
    Token-level F1 per field, plus micro-averaged F1 across all fields.

    Numeric fields use exact match (within 5% tolerance).
    String fields use token overlap F1.
    Boolean / None fields use exact match.
    """
    field_scores: dict[str, float] = {}
    for key, expected_val in expected.items():
        pred_val = predicted.get(key)
        if expected_val is None:
            field_scores[key] = 1.0 if pred_val is None else 0.0
            continue
        if isinstance(expected_val, bool):
            field_scores[key] = 1.0 if pred_val == expected_val else 0.0
        elif isinstance(expected_val, (int, float)):
            if pred_val is None:
                field_scores[key] = 0.0
            else:
                try:
                    tol = abs(expected_val) * 0.05 or 1
                    field_scores[key] = 1.0 if abs(float(pred_val) - float(expected_val)) <= tol else 0.0
                except (TypeError, ValueError):
                    field_scores[key] = 0.0
        elif isinstance(expected_val, str):
            field_scores[key] = rouge_l(str(pred_val) if pred_val else "", expected_val)["f1"]
        elif isinstance(expected_val, list):
            exp_str = " ".join(str(v) for v in expected_val)
            pred_str = " ".join(str(v) for v in (pred_val or []))
            field_scores[key] = rouge_l(pred_str, exp_str)["f1"]
        else:
            field_scores[key] = 1.0 if pred_val == expected_val else 0.0

    micro_f1 = statistics.mean(field_scores.values()) if field_scores else 0.0
    return {"per_field": field_scores, "micro_f1": round(micro_f1, 4)}


# ── Latency helper ────────────────────────────────────────────────────────────

class LatencyTimer:
    def __init__(self):
        self._start: float | None = None
        self.elapsed_ms: float | None = None

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 1)
