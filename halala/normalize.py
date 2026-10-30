"""Arabic text normalization and a rule-based Arabizi transliterator.

Two strengths of normalization, because they do different jobs:
- for_model: cleanup that keeps meaning, applied before text goes to a model.
- for_match: aggressive folding for comparing strings (answers, cache keys, cue words).
"""

from __future__ import annotations

import re

from .arabizi_lexicon import LEXICON

_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
# Punctuation, except a decimal point or comma between digits. \w is Unicode-aware, so Arabic letters survive.
_PUNCT = re.compile(r"(?!(?<=\d)[.,](?=\d))[^\w\s]")
_SPACES = re.compile(r"\s+")


def for_model(text: str) -> str:
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    return _SPACES.sub(" ", text.translate(_DIGITS)).strip()


def for_match(text: str) -> str:
    text = for_model(text).translate(_FOLD).lower()
    return _SPACES.sub(" ", _PUNCT.sub(" ", text)).strip()


# Rule-based Arabizi -> Arabic script: letters, word endings, prefixes, and a word list for what rules can't
# recover. It needs no model call. Digit conventions vary by region (8 and 9 especially); these follow Gulf usage.
_MULTI = [
    ("3'", "غ"), ("7'", "خ"), ("sh", "ش"), ("kh", "خ"), ("gh", "غ"), ("th", "ث"), ("dh", "ذ"),
    ("aa", "ا"), ("ee", "ي"), ("ii", "ي"), ("oo", "و"), ("uu", "و"), ("ou", "و"),
]
_SINGLE = {
    "2": "ء", "3": "ع", "5": "خ", "6": "ط", "7": "ح", "8": "ق", "9": "ص",
    "b": "ب", "t": "ت", "j": "ج", "d": "د", "r": "ر", "z": "ز", "s": "س", "f": "ف", "q": "ق",
    "g": "ق", "k": "ك", "l": "ل", "m": "م", "n": "ن", "h": "ه", "w": "و", "y": "ي",
    "p": "ب", "v": "ف", "c": "ك", "x": "كس",
}
_VOWELS = set("aeiou")
_WORD = re.compile(r"[A-Za-z0-9']+")


_DOUBLED = re.compile(r"([bcdfghjklmnpqrstvwxyz])\1")   # Arabic writes a doubled consonant once
_CLITICS = {"el": "ال", "al": "ال", "il": "ال", "bil": "بال", "lil": "لل", "bi": "ب", "w": "و"}
# Word endings the letter-by-letter pass would drop. Arabizi writes them; plain rules lose them.
_ENDINGS = (
    (re.compile(r"(?:iyya|iya|eya|ya)$"), "ية"),
    (re.compile(r"(?<![sktdg])ha$"), "ها"),   # not "sha" or "kha", which are single letters
    (re.compile(r"a$"), "ة"),
    (re.compile(r"i$"), "ي"),
)
_CONSTRUCT = re.compile(r"at$")   # 3omlat el...: "at" before another word is usually ة


def _letters(w: str) -> str:
    out, i = [], 0
    while i < len(w):
        for src, dst in _MULTI:
            if w.startswith(src, i):
                out.append(dst)
                i += len(src)
                break
        else:
            ch = w[i]
            if ch in _VOWELS:
                if i == 0:
                    out.append("ا")
            elif ch in _SINGLE:
                out.append(_SINGLE[ch])
            i += 1
    return "".join(out)


def _translit_word(word: str, followed: bool = False, lexicon: bool = True) -> str:
    if word.isdigit():
        return word
    w = word.lower()
    if w in _CLITICS:
        return _CLITICS[w]
    if lexicon and w in LEXICON:
        return LEXICON[w]
    w = _DOUBLED.sub(r"\1", w)
    endings = _ENDINGS + (((_CONSTRUCT, "ة"),) if followed else ())
    for pattern, arabic in endings:
        m = pattern.search(w)
        if m and m.start() >= 2:
            return _letters(w[: m.start()]) + arabic
    return _letters(w)


_STANDALONE_NUMBER = re.compile(r"(?<![A-Za-z0-9])(\d+)(?![A-Za-z0-9])")


def arabizi_kit(text: str) -> str:
    """ArabiziKit's Arabizi -> Arabic script: no model call, about 2ms a question, and it keeps the question
    recognisable. Standalone numbers are kept away from it, because it reads them as letters ("15" -> "1خ")."""
    from arabizikit import transliterate

    parts = _STANDALONE_NUMBER.split(text)
    out = [p if i % 2 else (transliterate(p).text if p.strip() else p) for i, p in enumerate(parts)]
    return "".join(out).replace("?", "؟")


def arabizi_to_arabic(text: str, lexicon: bool = True) -> str:
    words = list(_WORD.finditer(text))
    last = words[-1].start() if words else -1
    out = _WORD.sub(lambda m: _translit_word(m.group(), m.start() != last, lexicon), text)
    out = re.sub(r"(?<![ء-ي])(ال|بال|لل|ب|و)\s+(?=[ء-ي])", r"\1", out)   # attach prefixes to their word
    return out.replace("?", "؟")
