"""How Halala holds up when typing gets messy: the same Arabizi questions retyped ten ways, with fixed seeds.

Every retyped question goes through ALLaM alone and through Halala, with the frozen rewrite. The rule was set before the first run: a
way of typing holds up if Halala keeps at least two-thirds of the right answers it gets as written, and doesn't fall below ALLaM alone.
"""

from __future__ import annotations

import copy
import math
import random
import re
from collections import Counter
from dataclasses import replace

from .config import resolve
from .data import load_jsonl
from .measure import _models, _row, _save
from .pipeline import SYSTEM_ANSWER

BATCHES = ("data/arabizi_fresh3.jsonl", "data/arabizi_fresh2.jsonl", "data/arabizi_fresh.jsonl")   # the first was unseen at the freeze
SEED = 20261031
KEYS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
LETTER_WORD = re.compile(r"[A-Za-z][A-Za-z0-9']{3,}")
NUMBER_LETTERS = (("3'", "gh"), ("7'", "kh"), ("6'", "z"), ("9'", "d"), ("3", "a"), ("7", "h"), ("5", "kh"), ("2", "a"), ("6", "t"),
                  ("9", "s"), ("8", "g"))


def _neighbours() -> dict[str, list[str]]:
    near = {}
    for r, row in enumerate(KEYS):
        for i, ch in enumerate(row):
            near[ch] = [row[j] for j in (i - 1, i + 1) if 0 <= j < len(row)]
            if r + 1 < len(KEYS):
                near[ch] += [KEYS[r + 1][j] for j in (i - 1, i) if 0 <= j < len(KEYS[r + 1])]
    return near


NEAR = _neighbours()


def _pick(q: str, rng: random.Random) -> re.Match | None:
    words = list(LETTER_WORD.finditer(q))
    return rng.choice(words) if words else None


def typo(q: str, rng: random.Random) -> str:
    """One slip of the finger: a letter becomes a neighbouring key."""
    m = _pick(q, rng)
    if not m:
        return q
    spots = [i for i in range(m.start(), m.end()) if NEAR.get(q[i].lower())]
    if not spots:
        return q
    i = rng.choice(spots)
    return q[:i] + rng.choice(NEAR[q[i].lower()]) + q[i + 1:]


def two_typos(q: str, rng: random.Random) -> str:
    return typo(typo(q, rng), rng)


def swapped(q: str, rng: random.Random) -> str:
    """Two neighbouring letters typed the wrong way round."""
    m = _pick(q, rng)
    if not m:
        return q
    i = rng.randrange(m.start(), m.end() - 1)
    return q[:i] + q[i + 1] + q[i] + q[i + 2:]


def stretched(q: str, rng: random.Random) -> str:
    """Texting emphasis: weeesh, sa3odiyaaa."""
    m = _pick(q, rng)
    if not m:
        return q
    return q[:m.end()] + q[m.end() - 1] * 3 + q[m.end():]


def no_numerals(q: str, rng: random.Random) -> str:
    """For people who never learned the number letters."""
    for src, dst in NUMBER_LETTERS:
        q = re.sub(rf"(?<=[A-Za-z']){re.escape(src)}|{re.escape(src)}(?=[A-Za-z'])", dst, q)
    return q


def no_vowels(q: str, rng: random.Random) -> str:
    """Texting shorthand: vowels dropped from the middle of longer words."""
    def strip(m: re.Match) -> str:
        w = m.group(0)
        return w[0] + re.sub(r"[aeiouAEIOU]", "", w[1:-1]) + w[-1]
    return LETTER_WORD.sub(strip, q)


TYPING = {
    "as written": lambda q, rng: q,
    "first letter capital": lambda q, rng: q[:1].upper() + q[1:],
    "ALL CAPITALS": lambda q, rng: q.upper(),
    "all lower case, no punctuation": lambda q, rng: re.sub(r"[?!.,:;)(]+", " ", q.lower()).strip(),
    "an emoji on the end": lambda q, rng: q + " " + rng.choice(["😂", "🤔", "🙏"]),
    "stretched letters": stretched,
    "one typo": typo,
    "two typos": two_typos,
    "swapped letters": swapped,
    "no number letters": no_numerals,
    "no vowels": no_vowels,
}


def retype(item, kind: str) -> str:
    return TYPING[kind](item.question, random.Random(f"{SEED}|{item.id}|{kind}"))


def holds_up(alone: int, mine: int, as_written: int) -> bool:
    return mine >= math.ceil(2 * as_written / 3) and mine >= alone


def cmd_messy(cfg: dict) -> str:
    one_model = copy.deepcopy(cfg)
    one_model["cascade"]["route_english"] = False
    small, large = _models(one_model, cached=True)
    large.complete(SYSTEM_ANSWER, "مرحبا", 0.0, 0, {})
    batches = [load_jsonl(resolve(path)) for path in BATCHES]
    n = sum(len(items) for items in batches)
    alone, mine, unseen = Counter(), Counter(), Counter()
    for b, items in enumerate(batches):
        for it in items:
            for kind in TYPING:
                typed = replace(it, question=retype(it, kind))
                alone[kind] += _row(typed, small, large, one_model, True)["correct"]
                right = _row(typed, small, large, one_model, False)["correct"]
                mine[kind] += right
                if b == 0:
                    unseen[kind] += right
    lines = [f"{n} Arabizi questions outside the sealed set, each retyped ten ways with fixed seeds. The rewrite is unchanged. The rule was "
             "set before the first run: a way of typing holds up if Halala keeps at least two-thirds of the right answers it gets as "
             f"written, and doesn't fall below ALLaM alone. The last column is the {len(batches[0])} questions unseen when the rewrite was "
             "frozen. The other questions helped build it, so the totals flatter it a little.", "",
             "| Way of typing | ALLaM alone | With Halala | Holds up | With Halala, unseen only |", "|---|---|---|---|---|"]
    for kind in TYPING:
        verdict = "-" if kind == "as written" else "yes" if holds_up(alone[kind], mine[kind], mine["as written"]) else "no"
        lines.append(f"| {kind} | {alone[kind]} of {n} | {mine[kind]} of {n} | {verdict} | {unseen[kind]} of {len(batches[0])} |")
    return _save(cfg, "messy_typing", "\n".join(lines))
