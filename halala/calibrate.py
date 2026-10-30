"""Pick escalation thresholds with a finite-sample guarantee on accuracy loss.

Policy: keep the small model's answer when the router score is >= t, otherwise escalate.
Loss on an item: 1 if we kept the small answer, it was wrong, and the large model was right; else 0.
That upper-bounds the accuracy drop compared with always using the large model.

Thresholds are tested from strictest to loosest (fixed-sequence testing, as in Learn-then-Test,
Angelopoulos et al., 2021). We keep loosening while a one-sided binomial test rejects "risk > epsilon"
at level delta, and return the loosest certified threshold. With probability at least 1 - delta over
the calibration draw, its true risk is at most epsilon, assuming calibration and test data are exchangeable.

Per-variant calibration uses one item per question. Global calibration pools the five variants of each
question, which are correlated, so its guarantee is weaker than it looks.
"""

from __future__ import annotations

import math

import numpy as np

from .features import DETECTED_VARIANTS

NEVER_KEEP = math.inf


def binom_cdf(k: int, n: int, p: float) -> float:
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    lp, lq, ln_n = math.log(p), math.log1p(-p), math.lgamma(n + 1)
    total = sum(math.exp(ln_n - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
                for i in range(k + 1))
    return min(total, 1.0)


def losses_if_kept(records: list[dict]) -> np.ndarray:
    """1 where keeping the small answer loses to escalating. Escalation is what the large model does with any
    rewrite, not the raw baseline: otherwise a variant the baseline fails on looks safe to fail on cheaply."""
    return np.array([float(r.get("large_rescued_correct", r["large_correct"]) and not r["majority_correct"])
                     for r in records])


def certify(scores: np.ndarray, losses: np.ndarray, epsilon: float, delta: float, grid=None) -> float:
    n = len(scores)
    if n == 0:
        return NEVER_KEEP
    grid = np.linspace(1.0, 0.0, 101) if grid is None else grid
    best = NEVER_KEEP
    for t in grid:   # strictest first; the order is fixed in advance, so no multiplicity correction is needed
        k = int(losses[scores >= t].sum())
        if binom_cdf(k, n, epsilon) > delta:
            break
        best = float(t)
    return best


def calibrate(records: list[dict], scores: np.ndarray, cfg: dict) -> dict:
    c = cfg["calibrate"]
    eps, delta = float(c["epsilon"]), float(c["delta"])
    min_n, small_policy = int(c["min_group_size"]), c.get("small_group_policy", "escalate")
    losses = losses_if_kept(records)
    overall = certify(scores, losses, eps, delta)
    variants = np.array([r["detected_variant"] for r in records])
    per, sizes = {}, {}
    for v in DETECTED_VARIANTS:
        idx = np.flatnonzero(variants == v)
        sizes[v] = int(len(idx))
        if len(idx) >= min_n:
            per[v] = certify(scores[idx], losses[idx], eps, delta)
        else:
            per[v] = NEVER_KEEP if small_policy == "escalate" else overall

    def out(t: float) -> float | None:
        return None if math.isinf(t) else t

    return {
        "global": out(overall),
        "per_variant": {v: out(t) for v, t in per.items()},
        "group_sizes": sizes,
        "epsilon": eps,
        "delta": delta,
        "n": len(records),
    }


def threshold(thresholds: dict, variant: str, per_variant: bool = True) -> float:
    """Threshold for one item; infinity means always escalate. Unknown variants always escalate."""
    t = thresholds["per_variant"].get(variant) if per_variant else thresholds["global"]
    return NEVER_KEEP if t is None else t
