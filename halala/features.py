"""Detect how a question was written, with no model call: script, Arabizi markers and dialect cue words."""

from __future__ import annotations

import re

from .normalize import for_match

ARABIC_LETTER = re.compile(r"[ء-يٱ-ۓ]")
LATIN_LETTER = re.compile(r"[A-Za-z]")
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
# Everyday English words. Two outweigh any Arabizi marker ("What is CO2?"), and with no marker one is enough.
ENGLISH_WORDS = frozenset(
    "a an the of in on at to for from by with and or not is are was were be do does did has have had can could will "
    "would should what which who whom whose when where why how many much this that these those it its".split()
)
ENGLISH_DIGIT_WORD = re.compile(r"^\d+(?:st|nd|rd|th)$|[A-Z]\d|\d[A-Z]")   # 3rd, CO2, H2O, 5G


def _cues(words: str) -> frozenset[str]:
    return frozenset(for_match(w) for w in words.split())


GULF_CUES = _cues("وش ايش ابي ابغى يبي تبي ودي زين مره حيل الحين هالحين كذا شلون وشلون اللي يطلع ليش مب عشان وين دقايق")
OTHER_DIALECT_CUES = _cues("ازاي عايز دلوقتي كده ايه شو هلق بدي هيك منيح")
MSA_CUES = _cues("ماذا لماذا الذي التي هل سوف أريد الآن ناتج")
MSA_PHRASES = tuple(for_match(p) for p in ("ما هو", "ما هي"))

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


def _english_words(text: str) -> int:
    return sum(w in ENGLISH_WORDS for w in re.findall(r"[a-z0-9']+", text.lower()))


def _looks_arabizi(text: str) -> bool:
    if _english_words(text) >= 2:
        return False
    tokens = re.findall(r"[A-Za-z0-9']+", text)
    if any(ARABIZI_DIGIT_IN_WORD.search(t) and not ENGLISH_DIGIT_WORD.search(t) for t in tokens):
        return True
    words = [t.lower() for t in tokens]
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
        if _looks_arabizi(text):
            return "arabizi"
        # Unsure Latin text takes the mixed path, as typed to the large model: doubt costs compute, never accuracy.
        return "en" if _english_words(text) else "mixed"
    if arabic_words:
        gulf, other, msa = dialect_scores(text)
        return "dialect" if gulf + other > msa else "msa"
    return "en"
