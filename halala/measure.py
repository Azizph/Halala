"""What a correct answer really costs, by how the question was written: the Dialect Tax, in real seconds and tokens.

`dialect-tax` shows the tax in each form before and after each fix, and `check` guards that table against regressions.
`measure` shows what Halala does to mixed traffic. `sealed` is the one run on unseen questions. Seconds are the server's own
evaluation time, so failed attempts count as spend and nothing is estimated.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import replace
from pathlib import Path

from .config import resolve, run_dir
from .data import VARIANTS, load_jsonl
from .features import detect_variant
from .models import build_models
from .pipeline import SYSTEM_ANSWER, answer, load_dev, open_sealed, prepare
from .scoring import score

NOISE = "Identical runs vary by up to about 20%, so small differences mean little."


def _models(cfg: dict, cached: bool = False) -> tuple:
    small, large, cache = build_models(cfg)
    if not cached:   # a cached call replays its old seconds, and these numbers must be real calls
        if cache is not None:
            cache.close()
        small.cache = large.cache = None
    return small, large


def _row(item, small, large, cfg: dict, alone: bool) -> dict:
    """One question, either unaided on the large model or through Halala."""
    hint = {"answer": item.answers[0]}
    if alone:
        c = large.complete(SYSTEM_ANSWER, item.question, 0.0, 0, hint)
        result = {"text": c.text, "calls": [vars(c)]}
    else:
        result = answer(item.question, small, large, cfg, hint=hint)
    calls = result["calls"]
    return {
        "variant": item.variant,
        "correct": score(result["text"], item.answers, item.choices),
        "tokens_in": sum(c["tokens_in"] for c in calls),
        "tokens_out": sum(c["tokens_out"] for c in calls),
        "seconds": sum(c["latency_s"] for c in calls),
        "active_s": sum(c["active_s"] for c in calls),
        "load_s": sum(c["load_s"] for c in calls),
    }


def _per_correct(rows: list[dict]) -> float:
    return sum(r["active_s"] for r in rows) / max(1, sum(r["correct"] for r in rows))


def _tokens_per_correct(rows: list[dict]) -> float:
    """Tokens read and written per correct answer. They repeat exactly between runs, but they aren't compute: writing a token
    costs far more than reading one, so the seconds stay beside them."""
    return sum(r["tokens_in"] + r["tokens_out"] for r in rows) / max(1, sum(r["correct"] for r in rows))


def _by_form(rows: list[dict]) -> dict:
    """Correct answers in each form, and the tax: real seconds per correct answer as a multiple of English, then the same in tokens."""
    base = _per_correct([r for r in rows if r["variant"] == "en"]) or 1.0
    token_base = _tokens_per_correct([r for r in rows if r["variant"] == "en"]) or 1.0
    forms = {}
    for variant in VARIANTS:
        group = [r for r in rows if r["variant"] == variant]
        if group:
            forms[variant] = {"correct": sum(r["correct"] for r in group), "n": len(group),
                              "seconds_per_correct": round(_per_correct(group), 3),
                              "tax": round(_per_correct(group) / base, 2),
                              "tokens_per_correct": round(_tokens_per_correct(group), 1),
                              "token_tax": round(_tokens_per_correct(group) / token_base, 2)}
    return forms


def _tax_table(results: dict[str, list[dict]], intro: str) -> tuple[str, dict]:
    summary = {label: {"correct": sum(r["correct"] for r in rows), "n": len(rows),
                       "seconds_per_correct": round(_per_correct(rows), 3),
                       "tokens": sum(r["tokens_in"] + r["tokens_out"] for r in rows),
                       "tokens_per_correct": round(_tokens_per_correct(rows), 1), "forms": _by_form(rows)}
               for label, rows in results.items()}
    forms = list(next(iter(summary.values()))["forms"])
    lines = [f"{intro} Each form shows correct answers, then the tax: real seconds per correct answer as a multiple of "
             f"English on the same row. {NOISE}", "",
             "| Design | Correct | Seconds per correct | " + " | ".join(forms) + " |", "|---|---|---|" + "---|" * len(forms)]
    for label, row in summary.items():
        cells = [f"{row['forms'][f]['correct']}, {row['forms'][f]['tax']:.2f}x" for f in forms]
        lines.append(f"| {label} | {row['correct']} of {row['n']} | {row['seconds_per_correct']:.2f} | " + " | ".join(cells) + " |")
    lines += ["", "The same runs in tokens read and written. Each form shows correct answers, then tokens per correct answer.", "",
              "| Design | Correct | Tokens per correct | " + " | ".join(forms) + " |", "|---|---|---|" + "---|" * len(forms)]
    for label, row in summary.items():
        cells = [f"{row['forms'][f]['correct']}, {row['forms'][f]['tokens_per_correct']:.0f}" for f in forms]
        lines.append(f"| {label} | {row['correct']} of {row['n']} | {row['tokens_per_correct']:.0f} | " + " | ".join(cells) + " |")
    return "\n".join(lines), summary


def _save(cfg: dict, name: str, md: str, summary: dict | None = None) -> str:
    out = run_dir(cfg)
    (out / f"{name}.md").write_text(md, encoding="utf-8")
    if summary is not None:
        (out / f"{name}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md)
    return md


def _two_ways(items: list, small, large, cfg: dict) -> dict[str, list[dict]]:
    """Every question through ALLaM alone and through Halala."""
    results = {}
    for label, alone in (("ALLaM alone", True), ("With Halala", False)):
        print(f"{label}: {len(items)} questions", flush=True)
        results[label] = [_row(it, small, large, cfg, alone) for it in items]
    return results


def cmd_tax(cfg: dict) -> str:
    """The Dialect Tax before and after Halala, on the large model only, so a form's tax comes from the form."""
    items = load_dev(cfg)
    one_model = copy.deepcopy(cfg)
    one_model["cascade"]["route_english"] = False
    small, large = _models(one_model)
    large.complete(SYSTEM_ANSWER, "مرحبا", 0.0, 0, {})   # load the model first, so the first row isn't charged for it
    md, summary = _tax_table(_two_ways(items, small, large, one_model), f"{len(items)} dev questions in mixed order, with no cache.")
    return _save(cfg, "dialect_tax", md, summary)


def cmd_fresh(cfg: dict, data: str) -> str:
    """Arabizi on unseen text: questions written by an agent that never saw the word list, the rules or the dev questions."""
    items = load_jsonl(resolve(data))
    one_model = copy.deepcopy(cfg)
    one_model["cascade"]["route_english"] = False
    small, large = _models(one_model)
    large.complete(SYSTEM_ANSWER, "مرحبا", 0.0, 0, {})
    results = _two_ways(items, small, large, one_model)
    control = [_row(replace(it, question=it.meta["arabic"]), small, large, one_model, True) for it in items if "arabic" in it.meta]
    detected = sum(detect_variant(it.question) == "arabizi" for it in items)
    lines = [f"{len(items)} fresh Arabizi questions, written by a separate agent from published examples. Read by Halala as "
             f"Arabizi: {detected} of {len(items)}. {NOISE}", "", "| Design | Correct | Seconds per correct | Tokens per correct |",
             "|---|---|---|---|"]
    for label, rows in {**results, "ALLaM alone, the same questions in proper Arabic": control}.items():
        if rows:
            lines.append(f"| {label} | {sum(r['correct'] for r in rows)} of {len(rows)} | {_per_correct(rows):.2f} | {_tokens_per_correct(rows):.0f} |")
    lines += ["", "| Question | Rewrite | ALLaM alone | With Halala |", "|---|---|---|---|"]
    for it, before, after in zip(items, *results.values()):
        lines.append(f"| {it.question} | {prepare(it.question)[0]} | {'right' if before['correct'] else 'wrong'} | "
                     f"{'right' if after['correct'] else 'wrong'} |")
    return _save(cfg, Path(data).stem, "\n".join(lines))


def cmd_check(cfg: dict, save: bool, tolerance: int = 1) -> int:
    """Regression gate: no form's correct answers may fall below the saved baseline, on the last design measured."""
    out = run_dir(cfg)
    path, baseline = out / "dialect_tax.json", out / "baseline.json"
    if not path.exists():
        raise SystemExit("Nothing measured yet. Run: python -m halala dialect-tax")
    current = list(json.loads(path.read_text(encoding="utf-8")).values())[-1]["forms"]
    if save:
        baseline.write_text(json.dumps(current, indent=2), encoding="utf-8")
        print(f"saved baseline to {baseline}")
        return 0
    if not baseline.exists():
        raise SystemExit("No baseline yet. Run: python -m halala check --save")
    saved = json.loads(baseline.read_text(encoding="utf-8"))
    problems = [f"{form}: {saved[form]['correct']} to {current[form]['correct']}" for form in saved
                if current[form]["correct"] < saved[form]["correct"] - tolerance]
    for problem in problems:
        print(f"REGRESSION {problem}")
    print("check failed" if problems else "check passed")
    return 1 if problems else 0


def cmd_measure(cfg: dict, per_form: int, seed: int = 13) -> str:
    """Halala on mixed traffic, in the order questions really arrive, so any model swaps are paid for."""
    items, rng = load_dev(cfg), random.Random(seed)
    chosen = [q for variant in VARIANTS for q in rng.sample([it for it in items if it.variant == variant], per_form)]
    rng.shuffle(chosen)
    small, large = _models(cfg)
    lines = [f"{len(chosen)} dev questions in mixed order, with no cache. English goes to the small model: "
             f"{cfg['cascade']['route_english']}. Active seconds are evaluation time, load seconds are model loading, and "
             f"wall seconds are what a user waits. {NOISE}", "",
             "| Design | Correct | Active seconds per correct | Active | Load | Wall |", "|---|---|---|---|---|---|"]
    for label, alone in (("ALLaM alone", True), ("With Halala", False)):
        print(f"{label}: {len(chosen)} questions", flush=True)
        rows = [_row(it, small, large, cfg, alone) for it in chosen]
        lines.append(f"| {label} | {sum(r['correct'] for r in rows)} of {len(rows)} | {_per_correct(rows):.2f} | "
                     f"{sum(r['active_s'] for r in rows):.0f} | {sum(r['load_s'] for r in rows):.0f} | "
                     f"{sum(r['seconds'] for r in rows):.0f} |")
    return _save(cfg, "measure", "\n".join(lines))


def cmd_sealed(cfg: dict, unseal: bool) -> str:
    """The one run on unseen questions. Calls are cached, so a crash doesn't need a second opening to redo them."""
    if not unseal:
        raise SystemExit("The sealed test set is for the final evaluation only. Add --unseal if this is that run; each "
                         "opening is logged.")
    items = open_sealed(cfg)
    small, large = _models(cfg, cached=True)
    md, summary = _tax_table(_two_ways(items, small, large, cfg), f"{len(items)} sealed questions, seen by nobody until this run.")
    return _save(cfg, "sealed", md, summary)
