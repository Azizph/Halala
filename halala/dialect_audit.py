"""The Dialect Tax on a public benchmark: the same questions asked in different forms of Arabic, on each model.

The source is MBZUAI/Dialectal-Arabic-MMLU (CC BY 4.0, Oct 2025), with English, MSA, Saudi, Emirati, Syrian, Egyptian
and Moroccan. It is outside data nobody on this project wrote, so it answers the worry that we tested ourselves. It is
separate from the sealed set and from anything used to build the rewrite.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict

from .config import resolve, run_dir
from .data import Item, _unit, load_jsonl, write_jsonl
from .models import Completion, build_models
from .pipeline import SYSTEM_MC, format_mc
from .scoring import LETTERS, score

SOURCE = "MBZUAI/Dialectal-Arabic-MMLU"
ROWS_URL = "https://datasets-server.huggingface.co/rows"
FORMS = ("ENG", "MSA", "KSA", "UAE", "SYR", "EGY", "MAG")
FORM_NAMES = {"ENG": "English", "MSA": "Formal Arabic", "KSA": "Saudi", "UAE": "Emirati", "SYR": "Syrian",
              "EGY": "Egyptian", "MAG": "Moroccan"}


def fetch(groups: int, seed: int, max_chars: int = 400) -> list[Item]:
    """Pull the benchmark and sample questions that exist in every form and are short enough to run on a laptop."""
    import requests

    rows: list[dict] = []
    while True:
        for wait in (0, 5, 15, 30, 60, 120):   # the public API rate-limits, so back off rather than fail
            time.sleep(wait or 0.7)
            r = requests.get(ROWS_URL, timeout=60, params={"dataset": SOURCE, "config": "default", "split": "test",
                                                           "offset": len(rows), "length": 100})
            if r.status_code != 429:
                break
        r.raise_for_status()
        page = r.json()
        rows += [x["row"] for x in page["rows"]]
        if not page["rows"] or len(rows) >= page["num_rows_total"]:
            break
    by_group: dict[tuple, dict] = defaultdict(dict)
    for row in rows:
        by_group[(row["domain"], row["qid"])][row["dialect"]] = row
    # A group only counts if every form exists and agrees on the correct option's position.
    usable = [key for key, forms in by_group.items()
              if all(f in forms for f in FORMS)
              and len({forms[f]["answer"] for f in FORMS}) == 1
              and all(len(forms[f]["question"]) <= max_chars and len(forms[f]["choices"]) >= 2 for f in FORMS)]
    print(f"{len(rows)} rows, {len(by_group)} groups, {len(usable)} usable in all {len(FORMS)} forms")
    chosen = sorted(usable, key=lambda key: _unit(f"{key[0]}-{key[1]}", seed))[:groups]
    items = []
    for domain, qid in chosen:
        for form in FORMS:
            row = by_group[(domain, qid)][form]
            items.append(Item(id=f"dmmlu-{domain}-{qid}-{form}", group_id=f"dmmlu-{domain}-{qid}", variant=form,
                              question=row["question"], answers=[LETTERS[int(row["answer"])]],
                              choices=[str(c) for c in row["choices"]], meta={"source": SOURCE, "domain": domain}))
    return items


def cmd_fetch_dialects(out: str, groups: int, seed: int) -> None:
    items = fetch(groups, seed)
    write_jsonl(resolve(out), items)
    print(f"wrote {len(items)} items ({len(items) // len(FORMS)} questions in {len(FORMS)} forms) to {out}")


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a share, which behaves properly at small counts."""
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def ask_item(model, item: Item) -> tuple[Completion, bool]:
    """One benchmark question and whether the reply is right. The scorecard and the demo share this call, so the prompt and
    the marking are the same, though a reply can still move between runs (runs/local_gemma/live_replay.md). It skips `steps`
    on purpose: Halala's rewrite plays no part here, and `for_model` would change the prompt."""
    c = model.complete(SYSTEM_MC, format_mc(item.question, item.choices), 0.0, 0, {"answer": item.answers[0]})
    return c, score(c.text, item.answers, item.choices)


def _audit(model, items: list[Item]) -> dict[str, list[dict]]:
    """Every question through one model, grouped by form. One model at a time, so it never swaps."""
    print(f"{model.name}: {len(items)} questions", flush=True)
    per_form: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        c, correct = ask_item(model, item)
        per_form[item.variant].append({"correct": correct, "tokens": c.tokens_in + c.tokens_out})
    return per_form


def cmd_scorecard(cfg: dict, data: str, names: list[str]) -> str:
    """The same audit across models, so anyone can read a model's Dialect Tax beside the others. Tokenizers differ between models,
    so each tax is against that model's own English, and only right answers compare directly."""
    items = load_jsonl(resolve(data))
    small, large, cache = build_models(cfg)
    known = {large.name: large, small.name: small}
    results: dict[str, dict[str, list[dict]]] = {}
    try:
        for name in names:
            spec = {**small.cfg, "name": name, **({"think": False} if name.startswith("qwen3") else {})}
            results[name] = _audit(known.get(name) or type(small)(spec, cache), items)
    finally:
        if cache is not None:
            cache.close()
    forms = [f for f in FORMS if any(f in per for per in results.values())]
    head, rule = " | ".join(FORM_NAMES.get(f, f) for f in forms), "|---|" + "---|" * len(forms)
    n = len(next(iter(results.values()))[forms[0]])
    right = [f"| {name} | " + " | ".join(str(sum(r["correct"] for r in per[f])) for f in forms) + " |" for name, per in results.items()]
    taxes = []
    for name, per in results.items():
        cost = {f: sum(r["tokens"] for r in per[f]) / max(1, sum(r["correct"] for r in per[f])) for f in forms}
        taxes.append(f"| {name} | " + " | ".join(f"{cost[f] / cost[forms[0]]:.1f}x" for f in forms) + " |")
    md = "\n".join([f"Source: {SOURCE} (CC BY 4.0), {n} questions asked in every form, with the same instruction for every model. "
                    "Chance is 25%. Run after the sealed test, and Halala's rewrite plays no part.",
                    "", f"Right answers out of {n}:", "", f"| Model | {head} |", rule, *right, "",
                    "The Dialect Tax: tokens per right answer, as a multiple of the same model on English:", "",
                    f"| Model | {head} |", rule, *taxes])
    (run_dir(cfg) / "scorecard.md").write_text(md, encoding="utf-8")
    print(md)
    return md


def cmd_dialect_audit(cfg: dict, data: str) -> str:
    items = load_jsonl(resolve(data))
    small, large, cache = build_models(cfg)
    results: dict[str, dict[str, list[dict]]] = {}
    try:
        for model in (large, small):
            results[model.name] = _audit(model, items)
    finally:
        if cache is not None:
            cache.close()
    forms = [f for f in FORMS if any(f in per for per in results.values())]
    lines = [f"Source: {SOURCE} (CC BY 4.0), sampled questions asked in every form. Chance is 25%. Brackets are 95% "
             "intervals. Tax is tokens per correct answer, as a multiple of the same model on English."]
    for name, per_form in results.items():
        base_rows = per_form[forms[0]]
        base = sum(r["tokens"] for r in base_rows) / max(1, sum(r["correct"] for r in base_rows))
        lines += ["", f"**{name}**", "", "| Form | Correct | Tax vs English |", "|---|---|---|"]
        for form in forms:
            rows = per_form[form]
            wins, n = sum(r["correct"] for r in rows), len(rows)
            low, high = wilson(wins, n)
            tax = f"{sum(r['tokens'] for r in rows) / wins / base:.1f}x" if wins else "no correct answers"
            lines.append(f"| {FORM_NAMES.get(form, form)} | {wins} of {n} ({low * 100:.0f} to {high * 100:.0f}%) | {tax} |")
    md = "\n".join(lines)
    (run_dir(cfg) / "dialect_audit.md").write_text(md, encoding="utf-8")
    print(md)
    return md
