"""The Dialect Tax on a public benchmark: the same questions asked in different forms of Arabic, on each model.

The source is MBZUAI/Dialectal-Arabic-MMLU (CC BY 4.0, Oct 2025), with English, MSA, Saudi, Emirati, Syrian, Egyptian
and Moroccan. It is outside data nobody on this project wrote, so it answers the worry that we tested ourselves. It is
separate from the sealed set and from anything used to build the rewrite.
"""

from __future__ import annotations

import html
import math
import time
from collections import defaultdict

from .collect import SYSTEM_MC, format_mc
from .config import resolve, run_dir
from .data import Item, _unit, load_jsonl, write_jsonl
from .models import build_models
from .normalize import dialect_to_formal
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


def sign_test(wins: int, losses: int) -> float:
    """Two-sided chance of a split at least this lopsided if neither side were really better."""
    n = wins + losses
    return min(1.0, sum(math.comb(n, i) for i in range(min(wins, losses) + 1)) / 2 ** (n - 1)) if n else 1.0


def cmd_dialect_audit(cfg: dict, data: str) -> str:
    items = load_jsonl(resolve(data))
    small, large, cache = build_models(cfg)
    results: dict[str, dict[str, list[dict]]] = {}
    try:
        for tier, model in (("large", large), ("small", small)):   # one model at a time, so it never swaps
            print(f"{model.name}: {len(items)} questions", flush=True)
            per_form: dict[str, list[dict]] = defaultdict(list)
            for item in items:
                c = model.complete(SYSTEM_MC, format_mc(item.question, item.choices), 0.0, 0,
                                   {"answer": item.answers[0]})
                per_form[item.variant].append({"correct": score(c.text, item.answers, item.choices),
                                               "tokens": c.tokens_in + c.tokens_out})
            results[model.name] = per_form
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


REWRITE_RULE = ("Rule fixed before the run: adopt the word list if it gains at least 5 more questions than it loses, and "
                "the dev Najdi and mixed scores don't fall.")


def cmd_dialect_rewrite(cfg: dict, data: str) -> str:
    """One attempt at closing the Saudi gap with the word list, on questions it was written without seeing. A second
    attempt belongs on benchmark questions outside this sample, never on these. The dev check uses no instruction."""
    items = load_jsonl(resolve(data))
    saudi = [it for it in items if it.variant == "KSA"]
    rewritten = [(dialect_to_formal(it.question), [dialect_to_formal(c) for c in it.choices]) for it in saudi]
    dev = [it for it in load_jsonl(resolve(cfg["run"]["data"])) if it.variant in ("najdi", "mixed")]
    _, large, cache = build_models(cfg)

    def mc(item: Item, question: str, choices: list[str]) -> dict:
        c = large.complete(SYSTEM_MC, format_mc(question, choices), 0.0, 0, {"answer": item.answers[0]})
        return {"text": c.text, "correct": score(c.text, item.answers, choices), "tokens": c.tokens_in + c.tokens_out}

    def plain(item: Item, question: str) -> bool:
        c = large.complete("", question, 0.0, 0, {"answer": item.answers[0]})
        return score(c.text, item.answers, item.choices)

    try:
        print(f"{large.name}: {len(saudi)} Saudi questions, then {len(dev)} dev questions", flush=True)
        before = [mc(it, it.question, it.choices) for it in saudi]
        after = [mc(it, q, c) for it, (q, c) in zip(saudi, rewritten)]
        english = [mc(it, it.question, it.choices) for it in items if it.variant == "ENG"]
        formal = [mc(it, it.question, it.choices) for it in items if it.variant == "MSA"]
        dev_rows = [(it.variant, plain(it, it.question), plain(it, dialect_to_formal(it.question))) for it in dev]
    finally:
        if cache is not None:
            cache.close()

    def per_correct(rows: list[dict]) -> float:
        return sum(r["tokens"] for r in rows) / max(1, sum(r["correct"] for r in rows))

    base = per_correct(english)
    gained = sum(a["correct"] and not b["correct"] for b, a in zip(before, after))
    lost = sum(b["correct"] and not a["correct"] for b, a in zip(before, after))
    changed = sum(it.question != q or it.choices != c for it, (q, c) in zip(saudi, rewritten))
    falls = [v for v in ("najdi", "mixed") if sum(r[2] for r in dev_rows if r[0] == v) < sum(r[1] for r in dev_rows if r[0] == v)]
    passed = gained - lost >= 5 and not falls
    lines = [f"Source: {SOURCE}. One attempt on {len(saudi)} sampled questions, with a word list written before anyone "
             "read their Saudi text. No model call is added.", "",
             "| Form | Correct | Tokens per correct | Tax vs English |", "|---|---|---|---|"]
    for label, rows in (("English", english), ("Formal Arabic", formal), ("Saudi, as written", before),
                        ("Saudi, rewritten", after)):
        wins, cost = sum(r["correct"] for r in rows), per_correct(rows)
        lines.append(f"| {label} | {wins} of {len(rows)} | {cost:.0f} | {cost / base:.2f}x |")
    lines += ["", f"The word list changed {changed} of {len(saudi)} questions. It gained {gained} and lost {lost} "
              f"(chance of a split this lopsided: {sign_test(gained, lost):.3f}).", ""]
    for variant in ("najdi", "mixed"):
        rows = [r for r in dev_rows if r[0] == variant]
        lines.append(f"Dev {variant}, no instruction: {sum(r[1] for r in rows)} to {sum(r[2] for r in rows)} of {len(rows)}.")
    lines += ["", REWRITE_RULE, f"Result: {'passed' if passed else 'failed'}."]
    md = "\n".join(lines)
    out = run_dir(cfg)
    (out / "dialect_rewrite.md").write_text(md, encoding="utf-8")
    (out / "dialect_rewrite.html").write_text(_rewrite_page(saudi, rewritten, before, after), encoding="utf-8")
    print(md)
    return md


def _rewrite_page(saudi: list[Item], rewritten: list[tuple], before: list[dict], after: list[dict]) -> str:
    def cell(text) -> str:
        return f"<td dir='auto'>{html.escape(str(text))}</td>"

    def result(b: dict, a: dict) -> str:
        return "gained" if a["correct"] > b["correct"] else "lost" if a["correct"] < b["correct"] else ""

    body = "".join("<tr>" + cell(it.question) + cell(q) + cell(b["text"]) + cell(a["text"]) + cell(it.answers[0])
                   + cell(result(b, a)) + "</tr>"
                   for it, (q, _), b, a in zip(saudi, rewritten, before, after) if it.question != q)
    return ("<!doctype html><meta charset='utf-8'><title>Halala Saudi rewrite</title>"
            "<style>body{font:14px system-ui,sans-serif;margin:24px;background:#fcfcfb;color:#0b0b0b}"
            "table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e6e5e1;padding:6px 10px;"
            "vertical-align:top;text-align:start}th{color:#52514e;font-weight:500}td{unicode-bidi:plaintext}</style>"
            "<table><tr><th>Saudi</th><th>Rewritten</th><th>Answer before</th><th>Answer after</th><th>Correct</th>"
            f"<th>Result</th></tr>{body}</table>")
