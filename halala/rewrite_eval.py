"""H5: which way of handling Arabizi keeps the meaning, and at what cost?

Every arm prepares the question differently, then the large model answers it. Two arms bound the rest:
"raw" sends the Arabizi as typed, and "reference" sends the hand-checked Najdi version of the same question,
which is the best any rewrite could do. Dev data only: the sealed set is never read here.
"""

from __future__ import annotations

import html
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

from .collect import SYSTEM_ANSWER, SYSTEM_TRANSLIT, check_rewrite, rewrite_system
from .config import resolve, run_dir
from .data import load_examples, load_jsonl
from .models import build_models
from .normalize import arabizi_kit, arabizi_to_arabic, for_match, for_model
from .pipeline import _guard_leaks
from .policies import call_cost
from .scoring import score

SYSTEM_SPELL = (
    "The user's text is a Saudi Arabic sentence spelled phonetically, with wrong letters and extra vowels. "
    "Rewrite it with correct Arabic spelling, keeping the dialect and meaning. Reply with only the corrected text."
)
ARMS = ("raw", "rules_nolex", "rules", "rules_both", "kit", "kit_large", "small", "small_examples", "large",
        "large_examples", "large_nearest", "reference")
LABELS = {
    "raw": "Raw Arabizi (no rewrite)",
    "rules_nolex": "Rules, no word list",
    "rules": "Rules + word list",
    "rules_both": "Rules + word list, plus the raw text",
    "kit": "ArabiziKit (no model call)",
    "kit_large": "ArabiziKit + large model spelling fix",
    "small": "Small model rewrite",
    "small_examples": "Small model rewrite + examples",
    "large": "Large model rewrite",
    "large_examples": "Large model rewrite + examples",
    "large_nearest": "Large model rewrite + 4 nearest examples",
    "reference": "Hand-checked Najdi (upper bound)",
}
NEAREST_K = 4


def similarity(a: str, b: str) -> float:
    """Overlap of character 3-grams (Jaccard). A rough stand-in for "says the same thing"."""
    def grams(text: str) -> set[str]:
        t = f" {for_match(text)} "
        return {t[i:i + 3] for i in range(len(t) - 2)}

    x, y = grams(a), grams(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def nearest_system(question: str, examples: str, k: int = NEAREST_K) -> str:
    """The rewrite prompt with only the examples closest to this question, so context earns its tokens."""
    rows = sorted(load_examples(resolve(examples)), key=lambda r: -similarity(r["arabizi"], question))[:k]
    return SYSTEM_TRANSLIT + "\n\nExamples:\n" + "\n".join(f"Arabizi: {r['arabizi']}\nArabic: {r['arabic']}" for r in rows)


def _run_arm(arm: str, item, reference, small, large, cfg: dict, examples: str) -> dict:
    question = for_model(item.question)
    system = SYSTEM_TRANSLIT
    if arm.endswith("_examples"):
        system = rewrite_system({"arabizi_examples": examples})
    elif arm == "large_nearest":
        system = nearest_system(question, examples)
    text, calls, rejected = question, [], ""
    if arm == "rules":
        text = arabizi_to_arabic(question)
    elif arm == "rules_nolex":
        text = arabizi_to_arabic(question, lexicon=False)
    elif arm == "rules_both":
        text = f"{arabizi_to_arabic(question)}\n({question})"
    elif arm == "reference":
        text = reference.question
    elif arm == "kit":
        text = arabizi_kit(question)
    elif arm == "kit_large":
        draft = arabizi_kit(question)
        c = large.complete(SYSTEM_SPELL, draft, 0.0, 0, {"task": "transliterate"})
        calls.append(("large", asdict(c)))
        rejected = check_rewrite(draft, c.text)
        text = c.text.strip() if not rejected else draft
    elif arm != "raw":
        tier, model = ("small", small) if arm.startswith("small") else ("large", large)
        c = model.complete(system, question, 0.0, 0, {"task": "transliterate"})
        calls.append((tier, asdict(c)))
        rejected = check_rewrite(question, c.text)
        text = c.text.strip() if not rejected else question
    answer = large.complete(SYSTEM_ANSWER, text, 0.0, 0, {"answer": item.answers[0]})
    calls.append(("large", asdict(answer)))
    return {
        "group_id": item.group_id,
        "question": item.question,
        "reference": reference.question,
        "text": text,
        "rejected": rejected,
        "similarity": similarity(text, reference.question),
        "answer": answer.text,
        "correct": score(answer.text, item.answers),
        "cost": sum(call_cost(c, cfg["models"][tier])[cfg["cost"]["primary"]] for tier, c in calls),
    }


def cmd_rewrite_eval(cfg: dict, examples: str) -> str:
    items = load_jsonl(resolve(cfg["run"]["data"]))
    _guard_leaks({**cfg, "cascade": {**cfg["cascade"], "arabizi_examples": examples}}, items)
    references = {it.group_id: it for it in items if it.variant == "najdi"}
    arabizi = [it for it in items if it.variant == "arabizi" and it.group_id in references]
    small, large, cache = build_models(cfg)
    results: dict[str, list[dict]] = {}
    try:
        for arm in ARMS:
            print(f"arm {arm}: {len(arabizi)} questions", flush=True)
            with ThreadPoolExecutor(max_workers=max(1, int(cfg["run"].get("workers", 1)))) as pool:
                results[arm] = list(pool.map(
                    lambda it: _run_arm(arm, it, references[it.group_id], small, large, cfg, examples), arabizi))
    finally:
        if cache is not None:
            cache.close()

    def per_success(rows: list[dict]) -> float | None:
        wins = sum(r["correct"] for r in rows)
        return sum(r["cost"] for r in rows) / wins if wins else None

    base = per_success(results["reference"])
    n = len(arabizi)
    lines = [f"{n} dev Arabizi questions. The large model answers in every arm. Cost per correct answer is relative "
             "to the upper bound.", "",
             "| Arm | Correct | Rewrites rejected | Similarity to Najdi | Cost per correct answer |",
             "|---|---|---|---|---|"]
    for arm in ARMS:
        rows = results[arm]
        cost = per_success(rows)
        lines.append(f"| {LABELS[arm]} | {sum(r['correct'] for r in rows)} of {n} | "
                     f"{sum(bool(r['rejected']) for r in rows)} | {sum(r['similarity'] for r in rows) / n:.2f} | "
                     f"{'no correct answers' if cost is None else f'{cost / base:.1f}x' if base else f'{cost:.0f}'} |")
    md = "\n".join(lines)
    out = run_dir(cfg)
    (out / "rewrite_eval.md").write_text(md, encoding="utf-8")
    (out / "rewrite_eval.html").write_text(_page(results), encoding="utf-8")
    print(md)
    print(f"\nread every rewrite: {out / 'rewrite_eval.html'}")
    return md


def _page(results: dict[str, list[dict]]) -> str:
    def cell(text: str) -> str:
        return f"<td dir='auto'>{html.escape(str(text))}</td>"

    sections = []
    for arm, rows in results.items():
        body = "".join(
            "<tr>" + cell(r["question"]) + cell(r["reference"]) + cell(r["text"])
            + cell(r["answer"]) + cell("✓" if r["correct"] else "✗") + cell(r["rejected"]) + "</tr>"
            for r in rows
        )
        sections.append(f"<h2>{html.escape(LABELS[arm])}</h2><table><tr><th>Arabizi</th><th>Najdi</th><th>Sent to model"
                        f"</th><th>Answer</th><th></th><th>Rejected</th></tr>{body}</table>")
    return ("<!doctype html><meta charset='utf-8'><title>Halala rewrite comparison</title>"
            "<style>body{font:14px system-ui,sans-serif;margin:24px;background:#fcfcfb;color:#0b0b0b}"
            "table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e6e5e1;padding:6px 10px;"
            "vertical-align:top;text-align:start}th{color:#52514e;font-weight:500}td{unicode-bidi:plaintext}"
            "h2{font-size:16px;margin-top:28px}</style>" + "".join(sections))
