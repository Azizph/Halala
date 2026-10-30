"""Context that earns its tokens: how much of the fixed instruction does each answer really need?

Every arm runs Halala's real routing on the dev questions and changes only the instruction. Always-large arms use the
same instructions, because trimming helps that design too and its saving shouldn't be credited to Halala. English goes
first as one block, because alternating models on a small GPU would reload them on every question. Dev data only: the
sealed set is never read here.
"""

from __future__ import annotations

import copy
import html
from dataclasses import asdict

from .collect import SYSTEM_ANSWER, prepare_prompt
from .config import resolve, run_dir
from .data import VARIANTS, load_jsonl
from .features import detect_variant
from .models import build_models
from .policies import call_cost, usable_answer
from .scoring import score

ARMS = {
    "current": SYSTEM_ANSWER,
    "short_en": "Answer briefly.",
    "short_ar": "أجب باختصار.",
    "none": "",
    "none_first": "",   # as "none", but generation stops at the end of the first sentence
}
BASELINES = {
    "baseline": SYSTEM_ANSWER,
    "baseline_none": "",
    "baseline_first": "",
}
FIRST_SENTENCE = [". ", ".\n", "؟ ", "! ", "\n"]
LABELS = {
    "none_first": "Halala, no instruction, first sentence only",
    "baseline": "Always large, raw question, current instruction",
    "baseline_none": "Always large, raw question, no instruction",
    "baseline_first": "Always large, raw question, no instruction, first sentence only",
    "current": "Halala, current instruction",
    "short_en": 'Halala, "Answer briefly."',
    "short_ar": 'Halala, "أجب باختصار."',
    "none": "Halala, no instruction",
}


def _run(item, system: str, small, large, cfg: dict, baseline: bool) -> dict:
    hint = {"answer": item.answers[0]}
    calls = []

    def ask(tier: str, model, text: str):
        c = model.complete(system, text, 0.0, 0, hint)
        calls.append((tier, asdict(c)))
        return c.text

    if baseline:
        text = item.question
        answer = ask("large", large, text)
    else:
        prompt, _, rewrite = prepare_prompt(item.question, cfg["cascade"], small)
        if detect_variant(item.question) == "en":
            text = prompt
            answer = ask("small", small, text)
            if not usable_answer(answer):
                answer = ask("large", large, item.question)
        else:
            text = prompt if rewrite.get("text") and not rewrite.get("rejected") else item.question
            answer = ask("large", large, text)
    primary = cfg["cost"]["primary"]
    return {
        "variant": item.variant,
        "question": item.question,
        "answer": answer,
        "correct": score(answer, item.answers, item.choices),
        "tokens_in": sum(c["tokens_in"] for _, c in calls),
        "tokens_out": sum(c["tokens_out"] for _, c in calls),
        "tokens_cached": sum(c["cached_in"] for _, c in calls),
        "seconds": sum(c["latency_s"] for _, c in calls),
        "active_s": sum(c["active_s"] for _, c in calls),
        "load_s": sum(c["load_s"] for _, c in calls),
        "cost": sum(call_cost(c, cfg["models"][tier])[primary] for tier, c in calls),
    }


def cmd_prompt_eval(cfg: dict) -> str:
    items = load_jsonl(resolve(cfg["run"]["data"]))
    items.sort(key=lambda it: detect_variant(it.question) != "en")   # one model at a time
    small, large, cache = build_models(cfg)
    stopping = copy.deepcopy(cfg)
    for tier in ("small", "large"):
        stopping["models"][tier]["stop"] = FIRST_SENTENCE
    small_first, large_first, cache_first = build_models(stopping)
    results: dict[str, list[dict]] = {}
    try:
        for arm, system in [*BASELINES.items(), *ARMS.items()]:
            print(f"arm {arm}: {len(items)} questions", flush=True)
            pair = (small_first, large_first) if arm.endswith("_first") else (small, large)
            results[arm] = [_run(it, system, *pair, cfg, arm in BASELINES) for it in items]
    finally:
        for open_cache in (cache, cache_first):
            if open_cache is not None:
                open_cache.close()

    def per_correct(rows: list[dict]) -> float:
        wins = sum(r["correct"] for r in rows)
        return sum(r["cost"] for r in rows) / wins if wins else float("inf")

    base, n = per_correct(results["baseline"]), len(items)
    lines = [f"{n} dev questions. Cost per correct answer is an estimate from tokens, relative to always using the large "
             "model with the current instruction, so compare each Halala arm with the always-large arm on the same "
             "instruction. It counts prompt tokens the server reuses, and treats an output token like an input token. "
             "Times are left out because older cached calls carry a 2-second connection delay: `measure` reports real "
             "compute.", "",
             "| Arm | Correct | Tokens in | Tokens out | Tokens per question | Cost per correct |",
             "|---|---|---|---|---|---|"]
    for arm, rows in results.items():
        tokens_in, tokens_out = sum(r["tokens_in"] for r in rows) / n, sum(r["tokens_out"] for r in rows) / n
        lines.append(f"| {LABELS[arm]} | {sum(r['correct'] for r in rows)} of {n} | {tokens_in:.1f} | {tokens_out:.1f} | "
                     f"{tokens_in + tokens_out:.1f} | {per_correct(rows) / base * 100:.0f}% |")
    lines += ["", "Correct by form:", "", "| Arm | " + " | ".join(VARIANTS) + " |", "|---|" + "---|" * len(VARIANTS)]
    for arm, rows in results.items():
        cells = [str(sum(r["correct"] for r in rows if r["variant"] == v)) for v in VARIANTS]
        lines.append(f"| {LABELS[arm]} | " + " | ".join(cells) + " |")
    md = "\n".join(lines)
    out = run_dir(cfg)
    (out / "prompt_eval.md").write_text(md, encoding="utf-8")
    (out / "prompt_eval.html").write_text(_page(results), encoding="utf-8")
    print(md)
    print(f"\nread every answer: {out / 'prompt_eval.html'}")
    return md


def _page(results: dict[str, list[dict]]) -> str:
    def cell(text) -> str:
        return f"<td dir='auto'>{html.escape(str(text))}</td>"

    sections = []
    for arm, rows in results.items():
        body = "".join("<tr>" + cell(r["variant"]) + cell(r["question"]) + cell(r["answer"])
                       + cell("✓" if r["correct"] else "✗") + "</tr>" for r in rows)
        sections.append(f"<h2>{html.escape(LABELS[arm])}</h2><table><tr><th>Form</th><th>Question</th><th>Answer</th>"
                        f"<th></th></tr>{body}</table>")
    return ("<!doctype html><meta charset='utf-8'><title>Halala prompt comparison</title>"
            "<style>body{font:14px system-ui,sans-serif;margin:24px;background:#fcfcfb;color:#0b0b0b}"
            "table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e6e5e1;padding:6px 10px;"
            "vertical-align:top;text-align:start}th{color:#52514e;font-weight:500}td{unicode-bidi:plaintext}"
            "h2{font-size:16px;margin-top:28px}</style>" + "".join(sections))
