"""Replay routing policies over collected records (no model calls) and score them."""

from __future__ import annotations

import math
import re
from collections import defaultdict

import numpy as np

from .calibrate import threshold
from .data import VARIANTS
from .normalize import for_match
from .scoring import is_refusal, score

COST_KEYS = ("tokens", "flops", "usd", "latency_s")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
LABELS = {
    "always_small": "Always small",
    "always_large": "Always large",
    "agreement_global": "Agreement, one threshold",
    "router_global": "Router, one threshold",
    "halala": "Halala: router, per-variant thresholds",
    "halala_cache": "Halala + answer cache",
}


def call_cost(call: dict, model_cfg: dict, prefill: bool = True) -> dict:
    """prefill=False counts only generated tokens, for samples that reuse an earlier sample's prompt pass."""
    t_in, t_out = (call["tokens_in"] if prefill else 0), call["tokens_out"]
    return {
        "tokens": t_in + t_out,
        "flops": 2.0 * float(model_cfg.get("params_b", 0)) * 1e9 * (t_in + t_out),
        "usd": (t_in * float(model_cfg.get("usd_per_mtok_in", 0))
                + t_out * float(model_cfg.get("usd_per_mtok_out", 0))) / 1e6,
        "latency_s": call["latency_s"],   # samples are summed, as if run one after another
    }


def _total(calls: list[dict], model_cfg: dict, start: dict | None = None, shared_prefill: bool = False) -> dict:
    total = dict(start) if start else dict.fromkeys(COST_KEYS, 0.0)
    for i, call in enumerate(calls):
        for k, v in call_cost(call, model_cfg, prefill=not (shared_prefill and i > 0)).items():
            total[k] += v
    return total


def tier_costs(record: dict, cfg: dict) -> dict[str, dict]:
    small, large = cfg["models"]["small"], cfg["models"]["large"]
    shared = bool(cfg["cascade"].get("shared_prefill", True))
    rescue = _total(record["calls"]["translit"], small)
    rescued = record["calls"].get("large_rescued") or record["calls"]["large"]
    return {
        "greedy": _total(record["calls"]["small"][:1], small, rescue),
        "samples": _total(record["calls"]["small"], small, rescue, shared_prefill=shared),
        "large": _total(record["calls"]["large"], large),           # the baseline: raw question
        "escalated": _total(rescued, large),                        # the large model, given any rewrite
        "direct": _total(rescued, large, rescue),                   # straight to large, paying for the rewrite
    }


def nearest_prior(records: list[dict]) -> list[tuple[int, float]]:
    """For each item, the most similar earlier question (character 3-gram cosine) and its similarity.
    Only questions containing the same numbers can match: "12 plus 34" and "12 plus 43" look almost
    identical as text but are different questions (without this guard the cache cost 8 points on the smoke run)."""
    from sklearn.feature_extraction.text import HashingVectorizer

    texts = [for_match(r["question"]) for r in records]
    vec = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 3), alternate_sign=False, norm="l2")
    X = vec.transform(texts)
    by_numbers: dict[tuple, list[int]] = defaultdict(list)
    out = []
    for i, text in enumerate(texts):
        prior = by_numbers[tuple(_NUMBER.findall(text))]
        if prior:
            sims = (X[prior] @ X[i].T).toarray().ravel()
            k = int(np.argmax(sims))
            out.append((prior[k], float(sims[k])))
        else:
            out.append((-1, 0.0))
        prior.append(i)
    return out


def simulate(records: list[dict], cfg: dict, mode: str, keep: list[bool] | None = None,
             use_cache: bool = False, direct: list[bool] | None = None) -> list[dict]:
    """mode: small (always small, greedy), large (always large), cascade (keep[i] decides).
    direct[i] sends a cascade item straight to the large model, skipping the small tier's cost."""
    near = nearest_prior(records) if use_cache else None
    tau = float(cfg["cascade"].get("cache_similarity", 0.92))
    limit = float(cfg.get("floors", {}).get("latency_limit_s", 0))
    outcomes: list[dict] = []
    for i, r in enumerate(records):
        costs = tier_costs(r, cfg)
        if near and near[i][1] >= tau:
            text, tier, cost = outcomes[near[i][0]]["text"], "cache", dict.fromkeys(COST_KEYS, 0.0)
        elif mode == "small":
            text, tier, cost = r["greedy_text"], "small", costs["greedy"]
        elif mode == "large":
            text, tier, cost = r["large_text"], "large", costs["large"]
        elif direct and direct[i]:
            text, tier, cost = r.get("large_rescued_text", r["large_text"]), "large", costs["direct"]
        elif keep[i]:
            text, tier, cost = r["majority_text"], "small", costs["samples"]
        else:
            text, tier = r.get("large_rescued_text", r["large_text"]), "large"
            cost = {k: costs["samples"][k] + costs["escalated"][k] for k in COST_KEYS}
        correct = score(text, r["answers"], r.get("choices"))
        outcomes.append({
            "variant": r["variant"],
            "tier": tier,
            "text": text,
            "correct": correct,
            "success": correct and (not limit or cost["latency_s"] <= limit),   # right, and in time
            "cost": cost,
        })
    return outcomes


def drop_unprofitable(thresholds: dict, records: list[dict], scores: np.ndarray, cfg: dict) -> dict:
    """Keep a variant on the small tier only if it earns it, on the calibration split. Two tests:
    - Savings: with keep rate k, small-tier cost s and large cost L, the cascade beats going straight to the large
      model only when k * L > s.
    - Floor: the answers it would keep must themselves be right at least min_variant_success of the time. The
      guarantee only limits loss against the large model, so it can't see a variant both tiers do badly on.
    Thresholds that fail are cleared, so those variants skip the small tier."""
    primary = cfg["cost"]["primary"]
    floor = float(cfg.get("floors", {}).get("min_variant_success", 0))
    costs = [tier_costs(r, cfg) for r in records]
    for v, t in thresholds["per_variant"].items():
        idx = [i for i, r in enumerate(records) if r["detected_variant"] == v]
        if t is None or not idx:
            continue
        kept = [i for i in idx if scores[i] >= t]
        keep_rate = len(kept) / len(idx)
        small = _mean(costs[i]["samples"][primary] for i in idx)
        large = _mean(costs[i]["large"][primary] for i in idx)
        kept_accuracy = _mean(records[i]["majority_correct"] for i in kept) if kept else 0.0
        if keep_rate * large <= small or kept_accuracy < floor:
            thresholds["per_variant"][v] = None
    return thresholds


def _mean(xs) -> float:
    xs = list(xs)
    return float(np.mean(xs)) if xs else float("nan")


def cost_per_success(outcomes: list[dict], primary: str) -> float | None:
    """Total spend over the tasks that succeeded: failed runs still burn compute. None if nothing succeeded."""
    wins = sum(o["success"] for o in outcomes)
    return sum(o["cost"][primary] for o in outcomes) / wins if wins else None


def summarize(outcomes: list[dict], reference: list[dict], primary: str, variants: list[str]) -> dict:
    per = {}
    for v in variants:
        idx = [i for i, o in enumerate(outcomes) if o["variant"] == v]
        acc = _mean(outcomes[i]["correct"] for i in idx)
        ref = _mean(reference[i]["correct"] for i in idx)
        per[v] = {
            "n": len(idx),
            "accuracy": acc,
            "reference_accuracy": ref,
            "gap": ref - acc,
            "loss_rate": _mean(reference[i]["correct"] and not outcomes[i]["correct"] for i in idx),
            "escalation_rate": _mean(outcomes[i]["tier"] == "large" for i in idx),
            "cost": _mean(outcomes[i]["cost"][primary] for i in idx),
            "success_rate": _mean(outcomes[i]["success"] for i in idx),
            "cost_per_success": cost_per_success([outcomes[i] for i in idx], primary),
        }
    cost = {k: _mean(o["cost"][k] for o in outcomes) for k in COST_KEYS}
    ref_cost = _mean(o["cost"][primary] for o in reference)
    cps, ref_cps = cost_per_success(outcomes, primary), cost_per_success(reference, primary)
    worst = max(variants, key=lambda v: per[v]["gap"]) if variants else None
    return {
        "accuracy": _mean(o["correct"] for o in outcomes),
        "success_rate": _mean(o["success"] for o in outcomes),
        "worst_success_rate": min(per[v]["success_rate"] for v in variants) if variants else float("nan"),
        "cost_per_success": cps,
        "relative_cost_per_success": cps / ref_cps if cps is not None and ref_cps else float("nan"),
        "p95_latency_s": float(np.percentile([o["cost"]["latency_s"] for o in outcomes], 95)) if outcomes else float("nan"),
        "worst_accuracy": min(per[v]["accuracy"] for v in variants) if variants else float("nan"),
        "worst_gap": per[worst]["gap"] if worst else float("nan"),
        "worst_variant": worst,
        "escalation_rate": _mean(o["tier"] == "large" for o in outcomes),
        "cache_rate": _mean(o["tier"] == "cache" for o in outcomes),
        "cost": cost,
        "relative_cost": cost[primary] / ref_cost if ref_cost else float("nan"),
        "per_variant": per,
    }


def evaluate(test: list[dict], router, thresholds: dict, cfg: dict) -> dict:
    primary = cfg["cost"]["primary"]
    present = {r["variant"] for r in test}
    variants = [v for v in VARIANTS if v in present] + sorted(present - set(VARIANTS))
    detected = [r["detected_variant"] for r in test]
    scores = {"router": router.score(test), "agreement": np.array([r["agreement"] for r in test], dtype=float)}
    # An empty answer or a refusal is never kept, however much the samples agree.
    answered = np.array([bool(r["majority_text"].strip()) and not is_refusal(r["majority_text"]) for r in test])

    def keep(name: str, per_variant: bool) -> list[bool]:
        th = thresholds[name]
        return [bool(s >= threshold(th, v, per_variant) and ok)
                for s, v, ok in zip(scores[name], detected, answered)]

    def direct(name: str, per_variant: bool) -> list[bool]:
        """Variants with no certified threshold always escalate, so they skip the small tier's cost."""
        return [math.isinf(threshold(thresholds[name], v, per_variant)) for v in detected]

    runs = {
        "always_small": simulate(test, cfg, "small"),
        "always_large": simulate(test, cfg, "large"),
        "agreement_global": simulate(test, cfg, "cascade", keep("agreement", False), direct=direct("agreement", False)),
        "router_global": simulate(test, cfg, "cascade", keep("router", False), direct=direct("router", False)),
        "halala": simulate(test, cfg, "cascade", keep("router", True), direct=direct("router", True)),
    }
    if cfg["cascade"].get("cache"):
        runs["halala_cache"] = simulate(test, cfg, "cascade", keep("router", True), use_cache=True,
                                        direct=direct("router", True))
    reference = runs["always_large"]
    policies = {k: {"label": LABELS[k], **summarize(o, reference, primary, variants)} for k, o in runs.items()}
    floors = cfg.get("floors", {})
    for p in policies.values():
        p["meets_floors"] = bool(p["worst_success_rate"] >= float(floors.get("min_variant_success", 0)))

    sweeps = {}
    for name, s in scores.items():
        points = []
        for t in np.linspace(1.0, 0.0, 41):
            summary = summarize(simulate(test, cfg, "cascade", list((s >= t) & answered)), reference, primary, variants)
            points.append({"threshold": float(t), **{k: summary[k] for k in
                           ("relative_cost", "accuracy", "worst_accuracy", "worst_gap")}})
        sweeps[name] = points

    eps = thresholds["router"]["epsilon"]
    guarantee = {v: {"loss_rate": policies["halala"]["per_variant"][v]["loss_rate"],
                     "within_epsilon": policies["halala"]["per_variant"][v]["loss_rate"] <= eps}
                 for v in variants}
    return {
        "run": cfg["run"]["name"],
        "primary": primary,
        "mock": any(cfg["models"][t]["backend"] == "mock" for t in ("small", "large")),
        "models": {t: cfg["models"][t]["name"] for t in ("small", "large")},
        "n_test": len(test),
        "variants": variants,
        "epsilon": eps,
        "delta": thresholds["router"]["delta"],
        "floors": floors,
        "policies": policies,
        "sweeps": sweeps,
        "thresholds": thresholds,
        "guarantee": guarantee,
    }
