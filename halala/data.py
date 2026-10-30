"""Dataset items and the sealed test split."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .features import detect_variant

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


def write_jsonl(path: str | Path, rows: list) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(asdict(row) if isinstance(row, Item) else row, ensure_ascii=False) + "\n")


def _unit(text: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / 16**12
