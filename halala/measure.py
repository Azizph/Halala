"""What the hardware really did, beside the token estimate: fresh calls with no cache, timed by the server's own clock.

Prompt-eval says how accurate each instruction is. This says what each one costs in real seconds, and with --interleaved
what model swaps add when questions arrive in a mixed order. Dev data only: the sealed set is never read here.
"""

from __future__ import annotations

import copy
import random

from .config import resolve, run_dir
from .data import VARIANTS, load_jsonl
from .features import detect_variant
from .models import build_models
from .prompt_eval import ARMS, BASELINES, FIRST_SENTENCE, LABELS, _run

ALL_ARMS = (*BASELINES, *ARMS)


def _sample(cfg: dict, per_form: int, interleaved: bool, seed: int) -> list:
    items, rng, chosen = load_jsonl(resolve(cfg["run"]["data"])), random.Random(seed), []
    for variant in VARIANTS:
        group = [it for it in items if it.variant == variant]
        chosen += rng.sample(group, min(per_form, len(group)))
    if interleaved:
        rng.shuffle(chosen)
    else:
        chosen.sort(key=lambda it: detect_variant(it.question) != "en")   # one model at a time, so nothing swaps
    return chosen


def cmd_measure(cfg: dict, arms: list[str], per_form: int, interleaved: bool, seed: int = 13) -> str:
    items = _sample(cfg, per_form, interleaved, seed)
    small, large, cache = build_models(cfg)
    stopping = copy.deepcopy(cfg)
    for tier in ("small", "large"):
        stopping["models"][tier]["stop"] = FIRST_SENTENCE
    small_first, large_first, cache_first = build_models(stopping)
    for model in (small, large, small_first, large_first):
        model.cache = None   # every call must really run
    results: dict[str, list[dict]] = {}
    try:
        for arm in arms:
            print(f"arm {arm}: {len(items)} questions", flush=True)
            system = BASELINES[arm] if arm in BASELINES else ARMS[arm]
            pair = (small_first, large_first) if arm.endswith("_first") else (small, large)
            results[arm] = [_run(it, system, *pair, cfg, arm in BASELINES) for it in items]
    finally:
        for open_cache in (cache, cache_first):
            if open_cache is not None:
                open_cache.close()

    def active_per_correct(rows: list[dict]) -> float:
        wins = sum(r["correct"] for r in rows)
        return sum(r["active_s"] for r in rows) / wins if wins else float("inf")

    base, n = active_per_correct(results[arms[0]]) or 1.0, len(items)
    order = "in mixed order, so models swap" if interleaved else "one model at a time"
    lines = [f"{n} dev questions {order}, with no cache. Active seconds are the server's own evaluation time. Load seconds "
             "are the time spent loading models. Wall seconds are what a user waits.", "",
             "| Arm | Correct | Active seconds per correct | vs first arm | Active | Load | Wall | Tokens out | "
             "Prompt tokens evaluated |", "|---|---|---|---|---|---|---|---|---|"]
    for arm, rows in results.items():
        evaluated = sum(r["tokens_in"] - r["tokens_cached"] for r in rows)
        lines.append(f"| {LABELS[arm]} | {sum(r['correct'] for r in rows)} of {n} | {active_per_correct(rows):.2f} | "
                     f"{active_per_correct(rows) / base * 100:.0f}% | {sum(r['active_s'] for r in rows):.0f} | "
                     f"{sum(r['load_s'] for r in rows):.0f} | {sum(r['seconds'] for r in rows):.0f} | "
                     f"{sum(r['tokens_out'] for r in rows)} | {evaluated} |")
    md = "\n".join(lines)
    name = "measure_interleaved.md" if interleaved else "measure.md"
    (run_dir(cfg) / name).write_text(md, encoding="utf-8")
    print(md)
    return md
