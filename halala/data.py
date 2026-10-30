"""Dataset items, deterministic splits, and a synthetic parallel set for pipeline checks."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .features import detect_variant
from .normalize import for_match
from .scoring import LETTERS

VARIANTS = ("en", "msa", "najdi", "arabizi", "mixed")


@dataclass
class Item:
    id: str
    group_id: str      # the same question in every variant shares a group_id
    variant: str
    question: str
    answers: list[str]   # short-answer aliases, or the correct option letter for multiple choice
    choices: list[str] = field(default_factory=list)   # multiple-choice options in order; empty otherwise
    meta: dict = field(default_factory=dict)


def load_jsonl(path: str | Path) -> list[Item]:
    items = []
    # utf-8-sig, because Windows editors and PowerShell write a byte-order mark that plain utf-8 chokes on.
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            items.append(Item(
                id=str(row["id"]),
                group_id=str(row.get("group_id", row["id"])),
                variant=row.get("variant") or detect_variant(row["question"]),
                question=row["question"],
                answers=[str(a) for a in row["answers"]],
                choices=[str(c) for c in row.get("choices", [])],
                meta=row.get("meta", {}),
            ))
    return items


def load_examples(path: str | Path) -> list[dict]:
    """Hand-written pairs for the Arabizi rewrite prompt, one JSON object per line: {"arabizi": ..., "arabic": ...}."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                rows.append({"arabizi": row["arabizi"], "arabic": row["arabic"]})
    return rows


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal(source: Path, sealed_dir: Path, test_fraction: float, seed: int, force: bool = False) -> dict:
    """Split whole question groups into a dev file you work on and a sealed test file you don't open until the
    end. The manifest records the sealed file's hash, so any later edit to it is detectable."""
    items = load_jsonl(source)
    groups = sorted({it.group_id for it in items})
    test_groups = {g for g in groups if _unit(g, seed + 7) < test_fraction}
    test_path = sealed_dir / f"{source.stem}.test.jsonl"
    manifest_path = test_path.with_suffix(".json")
    if test_path.exists() and not force:
        raise SystemExit(f"{test_path} already exists. Resealing would change the test set; pass --force if you mean it.")
    dev_path = source.with_name(f"{source.stem}.dev.jsonl")
    write_jsonl(dev_path, [it for it in items if it.group_id not in test_groups])
    write_jsonl(test_path, [it for it in items if it.group_id in test_groups])
    manifest = {
        "source": source.name,
        "dev_file": dev_path.name,
        "sealed_file": test_path.name,
        "sha256": file_sha256(test_path),
        "test_groups": len(test_groups),
        "test_items": sum(it.group_id in test_groups for it in items),
        "dev_items": sum(it.group_id not in test_groups for it in items),
        "test_fraction": test_fraction,
        "seed": seed,
        "created": datetime.now().isoformat(timespec="seconds"),
        "unsealed": [],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**manifest, "dev_path": dev_path, "test_path": test_path, "manifest_path": manifest_path}


_OPTION_COLUMNS = (list("ABCDE"), [f"Option {i}" for i in range(1, 6)])


def _answer_letter(value: str, choices: list[str]) -> str:
    v = value.strip()
    valid = LETTERS[: len(choices)]
    if v.upper() in valid and len(v) == 1:
        return v.upper()
    if v.isdigit() and 1 <= int(v) <= len(choices):   # 1-based option number
        return valid[int(v) - 1]
    matches = [valid[i] for i, c in enumerate(choices) if for_match(c) == for_match(v)]
    return matches[0] if len(matches) == 1 else ""


def convert_mcq_csv(csv_path: Path, limit: int = 0) -> list[Item]:
    """Multiple-choice CSV (such as ArabicMMLU) to Items. Detects option columns named A-E or Option 1-5, and
    stops with the file's real headers if it doesn't recognise the layout."""
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        q_col = next((c for c in ("Question", "question") if c in headers), None)
        a_col = next((c for c in ("Answer Key", "Answer", "answer") if c in headers), None)
        opt_cols = next(([c for c in cols if c in headers] for cols in _OPTION_COLUMNS if cols[0] in headers), [])
        if not q_col or not a_col or len(opt_cols) < 2:
            raise SystemExit(f"Couldn't find question, option and answer columns in {csv_path.name}. Headers: {headers}")
        ctx_col = "Context" if "Context" in headers else None
        items, skipped = [], 0
        for i, row in enumerate(reader):
            choices = [(row.get(c) or "").strip() for c in opt_cols]
            while choices and not choices[-1]:
                choices.pop()
            question = row[q_col].strip()
            if ctx_col and (row.get(ctx_col) or "").strip():
                question = f"{row[ctx_col].strip()}\n{question}"
            letter = _answer_letter(row[a_col] or "", choices)
            if not letter or len(choices) < 2:
                skipped += 1
                continue
            items.append(Item(id=f"{csv_path.stem}-{i}", group_id=f"{csv_path.stem}-{i}",
                              variant=detect_variant(question), question=question, answers=[letter],
                              choices=choices, meta={"source": csv_path.name}))
            if limit and len(items) >= limit:
                break
    if skipped:
        print(f"skipped {skipped} rows with no usable answer", file=sys.stderr)
    return items


def write_jsonl(path: str | Path, rows: list) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(asdict(row) if isinstance(row, Item) else row, ensure_ascii=False) + "\n")


def _unit(text: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / 16**12


def split_items(items: list[Item], fractions: dict[str, float], seed: int, limit_groups: int = 0) -> dict[str, list[Item]]:
    """Assign whole question groups to splits, so no variant of a test question is seen in training."""
    groups = sorted({it.group_id for it in items}, key=lambda g: _unit(g, seed))
    keep = set(groups[:limit_groups]) if limit_groups else set(groups)
    names = list(fractions)
    out: dict[str, list[Item]] = {name: [] for name in names}
    for it in items:
        if it.group_id not in keep:
            continue
        u, acc = _unit(it.group_id, seed + 1), 0.0
        for name in names:
            acc += fractions[name]
            if u < acc:
                out[name].append(it)
                break
        else:
            out[names[-1]].append(it)
    return out


_ARITH = {
    "plus": {
        "en": "What is {a} plus {b}?",
        "msa": "ما ناتج جمع {a} و{b}؟",
        "najdi": "كم يطلع {a} زايد {b}؟",
        "arabizi": "kam ytla3 {a} zayed {b}?",
        "mixed": "كم {a} plus {b}؟",
    },
    "times": {
        "en": "What is {a} times {b}?",
        "msa": "ما ناتج ضرب {a} في {b}؟",
        "najdi": "كم يطلع {a} ضرب {b}؟",
        "arabizi": "kam ytla3 {a} darb {b}?",
        "mixed": "كم {a} times {b}؟",
    },
}
_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def make_synthetic_arith(n_groups: int, seed: int = 13) -> list[Item]:
    """Arithmetic in five parallel variants. Answers are checkable, so it suits pipeline checks and
    quick live-model sanity runs. It says nothing about real Arabic understanding."""
    rng = random.Random(seed)
    items, seen = [], set()
    g = 0
    while g < n_groups:
        op = rng.choice(sorted(_ARITH))
        digits = rng.choice([1, 2, 2, 3])
        a = rng.randint(10 ** (digits - 1), 10**digits - 1)
        b = rng.randint(2, 10**digits - 1)
        if (op, a, b) in seen:   # a repeated question could land in both train and test
            continue
        seen.add((op, a, b))
        result = a + b if op == "plus" else a * b
        for variant, template in _ARITH[op].items():
            fa, fb = str(a), str(b)
            if variant == "msa":
                fa, fb = fa.translate(_INDIC), fb.translate(_INDIC)
            items.append(Item(
                id=f"arith-{g:04d}-{variant}",
                group_id=f"arith-{g:04d}",
                variant=variant,
                question=template.format(a=fa, b=fb),
                answers=[str(result)],
                meta={"op": op, "digits": digits},
            ))
        g += 1
    return items
