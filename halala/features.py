"""Cheap, model-free signals about a question: script, Arabizi, dialect cues.

The cue lists are a v0 heuristic. If time allows, replace detect_variant with a small trained
dialect classifier and keep the same labels.
"""

from __future__ import annotations

import re

from .normalize import for_match

DETECTED_VARIANTS = ("en", "msa", "dialect", "arabizi", "mixed")

ARABIC_LETTER = re.compile(r"[ء-يٱ-ۓ]")
LATIN_LETTER = re.compile(r"[A-Za-z]")
ARABIC_INDIC_DIGIT = re.compile(r"[٠-٩۰-۹]")
DIACRITIC = re.compile(r"[ً-ٰٟ]")
ARABIZI_DIGIT_IN_WORD = re.compile(r"[A-Za-z][2356789]|[2356789][A-Za-z]")

# Strong markers: one is enough, because they are not English words.
ARABIZI_STRONG = {
    "wesh", "wish", "shlon", "shlonak", "ya3ni", "mafi", "wallah", "inshallah", "abgha", "zain",
    "laish", "leish", "al7een", "hal7een", "wain", "wein", "ytla3", "shu", "keef", "kaif",
}
# Weak markers: Arabic function words that also occur in English ("el", "min", "fi"), so two are needed.
ARABIZI_WEAK = {
    "el", "al", "il", "bil", "lil", "fi", "fee", "min", "ma3", "3ala", "3la", "ila", "law", "kam",
    "ay", "bi", "ana", "enta", "inta", "enti", "hatha", "hathi", "elly", "illi", "3ashan", "3shan",
    "yom", "sana", "shahar", "sa3a", "madina", "akbar", "awwal", "nos", "7ag", "7agg", "wala",
}


def _cues(words: str) -> frozenset[str]:
    return frozenset(for_match(w) for w in words.split())


GULF_CUES = _cues("وش ايش ابي ابغى يبي تبي ودي زين مره حيل الحين هالحين كذا شلون وشلون اللي يطلع ليش مب عشان وين دقايق")
OTHER_DIALECT_CUES = _cues("ازاي عايز دلوقتي كده ايه شو هلق بدي هيك منيح")
MSA_CUES = _cues("ماذا لماذا الذي التي هل سوف أريد الآن ناتج")
MSA_PHRASES = tuple(for_match(p) for p in ("ما هو", "ما هي"))

QUESTION_FEATURES = (
    "len_chars", "n_words", "frac_arabic", "frac_latin", "arabic_words", "latin_words",
    "arabizi_digit", "arabic_indic_digits", "diacritics", "cue_gulf", "cue_other", "cue_msa",
) + tuple(f"is_{v}" for v in DETECTED_VARIANTS)


def _letter_counts(text: str) -> tuple[int, int]:
    return len(ARABIC_LETTER.findall(text)), len(LATIN_LETTER.findall(text))


def _script_word_counts(text: str) -> tuple[int, int]:
    """Words written in each script. Counting words, not letters, is what catches code-switching:
    one English word inside a long Arabic sentence is still a mix, but only about 7% of its letters."""
    arabic = latin = 0
    for word in text.split():
        if ARABIC_LETTER.search(word):
            arabic += 1
        elif LATIN_LETTER.search(word):
            latin += 1
    return arabic, latin


def _looks_arabizi(text: str) -> bool:
    if ARABIZI_DIGIT_IN_WORD.search(text):
        return True
    words = [w for w in re.findall(r"[a-z0-9']+", text.lower())]
    if any(w in ARABIZI_STRONG for w in words):
        return True
    return sum(w in ARABIZI_WEAK for w in words) >= 2


def dialect_scores(text: str) -> tuple[int, int, int]:
    norm = for_match(text)
    words = norm.split()
    gulf = sum(w in GULF_CUES for w in words)
    other = sum(w in OTHER_DIALECT_CUES for w in words)
    msa = sum(w in MSA_CUES for w in words) + sum(p in norm for p in MSA_PHRASES)
    return gulf, other, msa


def detect_variant(text: str) -> str:
    arabic_words, latin_words = _script_word_counts(text)
    if arabic_words and latin_words:
        return "mixed"
    if latin_words:
        return "arabizi" if _looks_arabizi(text) else "en"
    if arabic_words:
        gulf, other, msa = dialect_scores(text)
        return "dialect" if gulf + other > msa else "msa"
    return "en"


def question_features(text: str) -> dict[str, float]:
    n_ar, n_lat = _letter_counts(text)
    total = n_ar + n_lat
    arabic_words, latin_words = _script_word_counts(text)
    gulf, other, msa = dialect_scores(text)
    variant = detect_variant(text)
    feats = {
        "len_chars": len(text),
        "n_words": len(text.split()),
        "frac_arabic": n_ar / total if total else 0.0,
        "frac_latin": n_lat / total if total else 0.0,
        "arabic_words": arabic_words,
        "latin_words": latin_words,
        "arabizi_digit": float(bool(ARABIZI_DIGIT_IN_WORD.search(text))),
        "arabic_indic_digits": float(bool(ARABIC_INDIC_DIGIT.search(text))),
        "diacritics": len(DIACRITIC.findall(text)),
        "cue_gulf": gulf,
        "cue_other": other,
        "cue_msa": msa,
    }
    for v in DETECTED_VARIANTS:
        feats[f"is_{v}"] = float(variant == v)
    return {name: float(feats[name]) for name in QUESTION_FEATURES}
