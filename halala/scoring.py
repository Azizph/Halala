"""Task-agnostic answer scoring: short answers and multiple choice."""

from __future__ import annotations

import re

from .normalize import for_match, for_model

LETTERS = "ABCDE"
_ARABIC = re.compile(r"[ء-ي]")
_LATIN_OPTION = re.compile(r"(?<![A-Za-z])([A-E])(?![A-Za-z])")
_ARABIC_OPTION = re.compile(r"(?<![ء-ي])([أابجده])(?![ء-ي])")
_ARABIC_TO_LETTER = {"أ": "A", "ا": "A", "ب": "B", "ج": "C", "د": "D", "ه": "E"}
_REFUSAL_WORDS = frozenset(for_match(w) for w in ("عذرا", "آسف", "sorry"))
_REFUSAL_PHRASES = tuple(for_match(p) for p in ("لا أستطيع", "لا يمكنني", "لا أفهم", "I can't", "I cannot",
                                                "unable to"))


def is_refusal(text: str) -> bool:
    norm = for_match(text)
    return any(w in _REFUSAL_WORDS for w in norm.split()) or any(f" {p} " in f" {norm} " for p in _REFUSAL_PHRASES)


def extract_choice(text: str, choices: list[str]) -> str:
    """The option letter a reply picks, or "" if it can't be told.
    Accepts "B", "B. Riyadh", "الخيار ب", or the text of exactly one option."""
    valid = LETTERS[: len(choices)]
    clean = for_model(text)   # drops tatweel, so "هـ" reads as "ه"
    for m in _LATIN_OPTION.finditer(clean):
        if m.group(1) in valid:
            return m.group(1)
    for m in _ARABIC_OPTION.finditer(clean):
        letter = _ARABIC_TO_LETTER[m.group(1)]
        if letter in valid:
            return letter
    norm = for_match(text)
    hits = [valid[i] for i, c in enumerate(choices) if for_match(c) and for_match(c) in norm]
    return hits[0] if len(hits) == 1 else ""


def is_correct(prediction: str, answers: list[str]) -> bool:
    pred = for_match(prediction)
    if not pred:
        return False
    for alias in answers:
        a = for_match(alias)
        if not a:
            continue
        if _ARABIC.search(a):
            # Arabic attaches prefixes (و، ب، ل، ال) to words, so plain containment is the safer test.
            if a in pred:
                return True
        elif re.search(rf"(?<!\w){re.escape(a)}(?!\w)", pred):
            return True
    return False


def score(prediction: str, answers: list[str], choices: list[str] | None = None) -> bool:
    """Correctness for either task type: multiple choice when `choices` is given, short answer otherwise."""
    if choices:
        return extract_choice(prediction, choices) in {a.strip().upper() for a in answers}
    return is_correct(prediction, answers)
