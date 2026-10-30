"""Spell Arabizi words as real Arabic words, from a word-frequency list and with no model call.

The rules can't see which vowels are long, so `ensan` comes out as انسن. Here the consonants typed decide which real words are
possible, how well a word lines up with what was typed narrows them down, and how common it is settles the rest.

data/arabic_words.txt merges two public frequency lists, in words per million: subtitles (hermitdave/FrequencyWords, 2018) and
Arabic Wikipedia (IlyaSemenov/wikipedia-word-frequency, 2022-08-29, words seen at least 20 times). Vulgar words are left out.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from itertools import product
from typing import NamedTuple

from .config import ROOT

WORDS = ROOT / "data" / "arabic_words.txt"
INF = math.inf

# What each mismatch costs when lining a typed word up with a real one.
SECOND = 0.5    # a letter's less likely reading: s for ص
SHORT = 0.3     # a vowel typed but not written, which is what a short vowel is
LONG = 1.0      # a long vowel or a w or y typed but not written
MISSING = 0.7   # a long vowel written but not typed
SILENT = 0.0    # a hamza written but not typed, or a final t or h written as ة
COMMON = 0.4    # what ten times the frequency is worth
MAX_FIT = 0.25  # per typed unit: a worse fit than this isn't the same word, so the rules take over
TOP = 200       # real words kept per set of consonants, most common first


class Unit(NamedTuple):
    letters: dict[str, float]   # the Arabic letters it can stand for, and what each costs
    skip: float                 # what writing nothing for it costs


def _unit(first: str, second: str = "", skip: float = INF) -> Unit:
    return Unit(dict.fromkeys(first, 0.0) | dict.fromkeys(second, SECOND), skip)


_A, _E, _I, _U = "اأآإىءة", "يىئةإ", "يىئإ", "وؤ"
_LATIN = {
    "3'": _unit("غ"), "7'": _unit("خ"), "6'": _unit("ظ"), "9'": _unit("ض"), "sh": _unit("ش"), "kh": _unit("خ"),
    "gh": _unit("غ"), "th": _unit("ث", "ذ"), "dh": _unit("ذ", "ضظ"), "ch": _unit("ك", "شج"),
    "3": _unit("ع"), "5": _unit("خ"), "6": _unit("ط"), "7": _unit("ح"), "8": _unit("ق", "غ"), "9": _unit("ص"),
    "b": _unit("ب"), "p": _unit("ب"), "t": _unit("ت", "ط"), "j": _unit("ج"), "d": _unit("د", "ضذ"), "r": _unit("ر"),
    "z": _unit("ز", "ظذ"), "s": _unit("س", "ص"), "f": _unit("ف"), "v": _unit("ف"), "q": _unit("ق", "ك"),
    "g": _unit("ق", "جغ"), "k": _unit("ك", "ق"), "c": _unit("ك"), "l": _unit("ل"), "m": _unit("م"), "n": _unit("ن"),
    "h": _unit("ه", "ح"), "2": _unit("ءأإآؤئا", skip=0.0),
    "aa": _unit(_A, "ع", LONG), "ee": _unit(_I, "ع", LONG), "ii": _unit(_I, "ع", LONG), "oo": _unit(_U, "عأ", LONG),
    "uu": _unit(_U, "عأ", LONG), "ou": _unit(_U, "عأ", LONG), "a": _unit(_A, "ع", SHORT), "e": _unit(_E, "ع", SHORT),
    "i": _unit(_I, "ع", SHORT), "o": _unit(_U, "عأ", SHORT), "u": _unit(_U, "عأ", SHORT), "w": _unit(_U, skip=LONG),
    "y": _unit(_I, skip=LONG),
}
_NOT_TYPED = dict.fromkeys("اوىيعة", MISSING) | dict.fromkeys("ءأآإؤئ", SILENT)
_WEAK = set(_NOT_TYPED) - {"ع"}         # letters with no consonant to match: vowels, hamzas and ة
_STARTS = dict.fromkeys("اأإآ", 0.0)    # any vowel that starts a word is written on an alef
_DIGIT_LETTERS = {"3": "ع", "5": "خ", "6": "ط", "7": "ح", "8": "ق", "9": "ص"}
_REPEAT = re.compile(r"(.)\1+")
_LETTER_THEN_HA = re.compile(r"([td])h(?=(?:a|um|om)$)")   # 3asmetha: ت then ها, not ث


def _skeleton(word: str) -> str:
    return _REPEAT.sub(r"\1", "".join(c for c in word if c not in _WEAK))


@lru_cache(maxsize=1)
def _words() -> dict[str, list[tuple[str, float]]]:
    """Real words by their consonants, most common first."""
    index: dict[str, list[tuple[str, float]]] = {}
    for line in WORDS.read_text(encoding="utf-8").splitlines():
        word, per_million = line.split()
        for skeleton in {_skeleton(word), _skeleton(word.replace("ع", ""))}:   # majmoa: some writers drop the ع
            found = index.setdefault(skeleton, [])
            if len(found) < TOP:
                found.append((word, math.log10(float(per_million))))
    return index


def _units(word: str, digits: str) -> list[Unit]:
    units, i = [], 0
    word = word.replace("x", "ks")
    while i < len(word):
        for size in (2, 1):
            unit = _LATIN.get(word[i:i + size])
            if unit and units and unit is units[-1] and unit.skip == INF:     # doubled, so the vowel before it is short
                if len(units) > 1 and units[-2].skip == SHORT:
                    units[-2] = units[-2]._replace(letters={})
                i += size
                break
            if unit:
                units.append(unit)
                i += size
                break
        else:
            i += 1
    if not units:
        return units
    if units[0].skip == SHORT:      # a word can't open on an unwritten vowel
        units[0] = Unit({**units[0].letters, **_STARTS}, LONG)
    elif units[0].skip == LONG and word[0] in "wy":     # nor can a w or y that opens one go unwritten
        units[0] = units[0]._replace(skip=INF)
    if units[-1].skip == SHORT:     # and a final vowel that's typed is meant
        units[-1] = units[-1]._replace(skip=LONG)
    if len(units) > 1 and units[-2] in (_LATIN["a"], _LATIN["e"]) and units[-1] in (_LATIN["t"], _LATIN["h"]):
        units[-1] = units[-1]._replace(letters={**units[-1].letters, "ة": SILENT})   # 3asmat, 7alqah
    # A writer who types 7 for ح rarely types h for it too, and the same goes for the other digits.
    unlikely = {_DIGIT_LETTERS[d] for d in digits}
    return [u._replace(letters={k: LONG if v and k in unlikely else v for k, v in u.letters.items()}) for u in units]


def _skeletons(units: list[Unit]) -> set[str]:
    choices = [["" if letter in _WEAK else letter for letter in u.letters] for u in units if u.letters.keys() - _WEAK]
    return {_REPEAT.sub(r"\1", "".join(letters)) for letters in product(*choices)}


def _fit(units: list[Unit], word: str) -> float:
    """The cheapest way to line what was typed up with a real word."""
    n, m = len(units), len(word)
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            here = cost[i][j]
            if here == INF:
                continue
            if i < n:
                cost[i + 1][j] = min(cost[i + 1][j], here + units[i].skip)
            if j < m:
                if j and word[j] == word[j - 1] == "ل":     # the article's ل before another, as in اللي
                    unspoken = 0.0
                else:
                    unspoken = LONG if j == 0 and word[j] in _NOT_TYPED else _NOT_TYPED.get(word[j], INF)
                cost[i][j + 1] = min(cost[i][j + 1], here + unspoken)
            if i < n and j < m:
                cost[i + 1][j + 1] = min(cost[i + 1][j + 1], here + units[i].letters.get(word[j], INF))
    return cost[n][m]


@lru_cache(maxsize=None)
def spell(word: str, digits: str = "") -> str | None:
    """The most likely real word for a typed one, or None when nothing fits well enough.

    `digits` are the letter digits this writer used anywhere in the question.
    """
    best, best_score = None, INF
    for reading in {word, _LETTER_THEN_HA.sub(r"\1'h", word)}:
        units = _units(reading, digits)
        for skeleton in _skeletons(units):
            for arabic, frequency in _words().get(skeleton, ()):
                fit = _fit(units, arabic)
                score = fit - COMMON * frequency
                if fit <= MAX_FIT * len(units) and score < best_score:
                    best, best_score = arabic, score
    return best
