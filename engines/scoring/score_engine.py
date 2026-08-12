"""
engines/scoring/score_engine.py — Continuous scoring engine.
Replaces binary gate chain with weighted, explainable 0–100 scoring.
Factor groups are scored independently. Hard vetoes bypass scoring entirely.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

QUALITY_CLASSES = [
    ("A+", config.SCORE_THRESHOLDS["A+"]),
    ("A",  config.SCORE_THRESHOLDS["A"]),
    ("B+", config.SCORE_THRESHOLDS["B+"]),
    ("B",  config.SCORE_THRESHOLDS["B"]),
    ("C",  0),
]

def quality_class(score: float) -> str:
    """Map continuous score to quality class."""
    for label, threshold in QUALITY_CLASSES:
        if score >= threshold:
            return label
    return "C"

def normalize_score(raw: float, max_raw: float) -> float:
    """Normalize a raw sub-score to its configured maximum."""
    if max_raw <= 0:
        return 0.0
    return min(raw, max_raw)

def build_stock_score(breakdown: dict) -> dict:
    """
    Build final stock composite score from factor group breakdown.

    breakdown: dict keyed by factor group name, each value is:
        {"raw": float, "max": float, "details": dict}

    Returns: {"total": float, "quality_class": str, "breakdown": dict,
              "factor_pct": dict}
    """
    weights = config.STOCK_SCORE_WEIGHTS
    total = 0.0
    result_breakdown = {}

    for group, weight in weights.items():
        if group in breakdown:
            raw = breakdown[group].get("raw", 0.0)
            score = normalize_score(raw, weight)
        else:
            score = 0.0
        result_breakdown[group] = {
            "score": round(score, 2),
            "max":   weight,
            "pct":   round(score / weight * 100, 1) if weight > 0 else 0,
            "details": breakdown.get(group, {}).get("details", {}),
        }
        total += score

    total = round(min(total, 100), 2)
    return {
        "total":         total,
        "quality_class": quality_class(total),
        "breakdown":     result_breakdown,
        "factor_pct":    {k: v["pct"] for k, v in result_breakdown.items()},
    }

def build_crypto_score(breakdown: dict) -> dict:
    """
    Build final crypto composite score from factor group breakdown.
    Same logic as build_stock_score but uses CRYPTO_SCORE_WEIGHTS.
    """
    weights = config.CRYPTO_SCORE_WEIGHTS
    total = 0.0
    result_breakdown = {}

    for group, weight in weights.items():
        if group in breakdown:
            raw = breakdown[group].get("raw", 0.0)
            score = normalize_score(raw, weight)
        else:
            score = 0.0
        result_breakdown[group] = {
            "score": round(score, 2),
            "max":   weight,
            "pct":   round(score / weight * 100, 1) if weight > 0 else 0,
            "details": breakdown.get(group, {}).get("details", {}),
        }
        total += score

    total = round(min(total, 100), 2)
    return {
        "total":         total,
        "quality_class": quality_class(total),
        "breakdown":     result_breakdown,
        "factor_pct":    {k: v["pct"] for k, v in result_breakdown.items()},
    }

def extract_top_reasons(breakdown: dict, n: int = 4) -> list[str]:
    """
    Extract top N reasons from breakdown for Telegram message.
    Returns human-readable strings sorted by score contribution.
    """
    reasons = []
    for group, data in breakdown.items():
        pct  = data.get("pct", 0)
        dets = data.get("details", {})
        if pct >= 50:    # Only mention factors that fired meaningfully
            detail_str = ", ".join(f"{k}={v}" for k, v in dets.items()
                                   if not isinstance(v, dict))[:80]
            reasons.append((pct, f"{group.replace('_',' ').title()}: {detail_str}"))

    reasons.sort(reverse=True)
    return [r[1] for r in reasons[:n]]

def should_alert(score: float) -> bool:
    """Send B grade and above to Telegram. User manages risk manually."""
    return score >= config.SCORE_THRESHOLDS["B"]   # 40+
