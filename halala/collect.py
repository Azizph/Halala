"""One pass over the data: both tiers answer every item, and everything needed to replay any routing
policy offline is saved. Policies, threshold sweeps and ablations then cost no model calls."""

from __future__ import annotations

import functools
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from . import normalize
from .config import resolve
from .data import Item, load_examples, write_jsonl
from .features import ARABIC_LETTER, LATIN_LETTER, detect_variant, question_features
from .models import Completion, Model
from .scoring import LETTERS, cluster_answers, is_refusal, score

SYSTEM_ANSWER = "Answer the question. Reply with only the short final answer, with no explanation."
SYSTEM_MC = "Answer the multiple-choice question. Reply with only the letter of the correct option."
SYSTEM_TRANSLIT = (
    "The user's text is Arabic written in Latin letters and digits (Arabizi). Rewrite it in Arabic script, "
    "keeping the dialect and meaning. Reply with only the rewritten text."
)

_CHAT_TOKEN = re.compile(r"<\|[^>]*>|\|>")


def format_mc(question: str, choices: list[str]) -> str:
    return question + "\n" + "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(choices))


def check_rewrite(original: str, rewrite: str) -> str:
    """Why a model's Arabizi rewrite can't be used, or "" if it can. Catches format failures only
    (seen with ALLaM 7B on 2026-10-30): a fluent rewrite that changes the meaning still gets through."""
    text = rewrite.strip()
    if not text:
        return "empty"
    if _CHAT_TOKEN.search(text):
        return "chat token"
    if is_refusal(text):
        return "refusal"
    if len(text) > 2 * len(original) + 20:
        return "too long"
    if len(ARABIC_LETTER.findall(text)) <= len(LATIN_LETTER.findall(text)):
        return "not Arabic script"
    return ""


@functools.lru_cache(maxsize=8)
def _examples_block(path: str) -> str:
    rows = load_examples(resolve(path))
    return "\n\nExamples:\n" + "\n".join(f"Arabizi: {r['arabizi']}\nArabic: {r['arabic']}" for r in rows)


def rewrite_system(cascade: dict) -> str:
    path = cascade.get("arabizi_examples", "")
    return SYSTEM_TRANSLIT + (_examples_block(path) if path else "")


def prepare_prompt(question: str, cascade: dict, small: Model) -> tuple[str, list[dict], dict]:
    """The cheap rescue step: what the small model sees. The large model always gets the raw question.
    Returns the prompt, the rewrite calls (for cost), and what happened to the rewrite."""
    text, calls, rewrite = question, [], {}
    if cascade.get("normalize", True):
        text = normalize.for_model(text)
    mode = cascade.get("arabizi", "none")
    if mode != "none" and detect_variant(question) == "arabizi":
        if mode == "rules":
            text = normalize.arabizi_to_arabic(text)
            rewrite = {"text": text, "rejected": ""}
        elif mode == "model":
            c = small.complete(rewrite_system(cascade), text, 0.0, 0, {"task": "transliterate"})
            calls.append(asdict(c))
            reason = check_rewrite(text, c.text)
            rewrite = {"text": c.text, "rejected": reason}
            if not reason:   # otherwise fall back to the cleaned original
                text = c.text.strip()
        else:
            raise ValueError(f"unknown arabizi mode: {mode}")
    return text, calls, rewrite


def small_samples(small: Model, system: str, prompt: str, cascade: dict, hint: dict) -> list[Completion]:
    k = max(1, int(cascade.get("samples", 5)))
    temperature = float(cascade.get("temperature", 0.7))
    return [small.complete(system, prompt, 0.0 if i == 0 else temperature, i, hint) for i in range(k)]


def summarize_samples(samples: list[Completion], choices: list[str] | None = None) -> dict:
    texts = [s.text for s in samples]
    ids = cluster_answers(texts, choices)
    counts = Counter(ids)
    majority, top = counts.most_common(1)[0]   # ties go to the greedy sample's answer
    if majority == -1:   # most samples were empty or picked no option
        top = 0
    members = [t for t, i in zip(texts, ids) if i == majority]
    return {
        "small_texts": texts,
        "greedy_text": texts[0],
        "majority_text": min(members, key=len) if majority != -1 else "",   # the most concise wording
        "agreement": top / len(samples),
        "n_distinct": len(counts),
        "greedy_in_majority": ids[0] == majority,
    }


def collect_item(item: Item, small: Model, large: Model, cascade: dict) -> dict:
    hint = {"answer": item.answers[0] if item.answers else ""}
    system = SYSTEM_MC if item.choices else SYSTEM_ANSWER
    prompt, rewrite_calls, rewrite = prepare_prompt(item.question, cascade, small)
    if item.choices:
        options = [normalize.for_model(c) for c in item.choices] if cascade.get("normalize", True) else item.choices
        prompt = format_mc(prompt, options)
    samples = small_samples(small, system, prompt, cascade, hint)
    raw = format_mc(item.question, item.choices) if item.choices else item.question
    big = large.complete(system, raw, 0.0, 0, hint)
    # The always-large baseline answers the raw question, but when Halala escalates a rewritten question
    # the large model should get the rewrite too: raw Arabizi is what it struggles with.
    rewritten = bool(rewrite.get("text")) and not rewrite.get("rejected")
    rescued = large.complete(system, prompt, 0.0, 0, hint) if rewritten else big
    rec = {
        "id": item.id,
        "group_id": item.group_id,
        "variant": item.variant,
        "question": item.question,
        "choices": item.choices,
        "answers": item.answers,
        "prompt": prompt,
        "rewrite": rewrite,
        "rewrite_rejected": bool(rewrite.get("rejected")),
        "detected_variant": detect_variant(item.question),
        "features": question_features(item.question),
        **summarize_samples(samples, item.choices),
        "large_text": big.text,
        "large_rescued_text": rescued.text,
    }
    rec["greedy_correct"] = score(rec["greedy_text"], item.answers, item.choices)
    rec["majority_correct"] = score(rec["majority_text"], item.answers, item.choices)
    rec["large_correct"] = score(big.text, item.answers, item.choices)
    rec["large_rescued_correct"] = score(rescued.text, item.answers, item.choices)
    rec["calls"] = {"translit": rewrite_calls, "small": [asdict(s) for s in samples], "large": [asdict(big)],
                    "large_rescued": [asdict(rescued)]}
    return rec


def collect(items: list[Item], small: Model, large: Model, cfg: dict, out_path: Path) -> list[dict]:
    cascade = cfg["cascade"]
    workers = max(1, int(cfg["run"].get("workers", 1)))
    records = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, rec in enumerate(pool.map(lambda it: collect_item(it, small, large, cascade), items), 1):
            records.append(rec)
            if i % max(1, len(items) // 20) == 0 or i == len(items):
                print(f"  {i}/{len(items)}", file=sys.stderr)
    write_jsonl(out_path, records)
    return records
