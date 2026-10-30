"""Halala: a thin layer in front of the model.

A question comes in and is cleaned up, then Halala detects its form. Arabizi is rewritten into Arabic script by rules and word
lists, with no model call. Arabic goes to the large model. English can go to the small model when the hardware has room for
both. A free check catches empty or refused answers, and every call's real cost is recorded.

`steps` is the one path: the command line, the measurements, the sealed test and the demo all go through it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime

from .config import resolve
from .data import file_sha256, load_jsonl, seal
from .features import detect_variant
from .models import Model, build_models
from .normalize import arabizi_to_arabic, for_match, for_model
from .scoring import LETTERS, is_refusal

SYSTEM_ANSWER = "Answer the question. Reply with only the short final answer, with no explanation."
SYSTEM_MC = "Answer the multiple-choice question. Reply with only the letter of the correct option."


def format_mc(question: str, choices: list[str]) -> str:
    return question + "\n" + "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(choices))


def usable_answer(text: str) -> bool:
    """The one free check: an empty answer or a refusal is never accepted."""
    return bool(text.strip()) and not is_refusal(text)


def prepare(question: str) -> tuple[str, bool]:
    """What the model sees, and whether Halala rewrote it. This costs no model call."""
    text = for_model(question)
    if detect_variant(question) == "arabizi":
        return arabizi_to_arabic(text), True
    return text, False


def _ask(tier: str, model: Model, prompt: str, system: str, hint: dict | None) -> Iterator[dict]:
    yield {"step": "asking", "tier": tier, "model": model.name}
    c = model.complete(system, prompt, 0.0, 0, hint or {})
    return {"step": "answer", "tier": tier, "model": model.name, "prompt": prompt, **asdict(c)}


def steps(question: str, small: Model, large: Model, cfg: dict, system: str = SYSTEM_ANSWER,
          hint: dict | None = None) -> Iterator[dict]:
    """Everything Halala does for one question, one event per step, so the demo can show it as it happens."""
    form = detect_variant(question)
    yield {"step": "form", "form": form}
    prompt, rewritten = prepare(question)
    yield {"step": "rewrite", "rewritten": rewritten, "prompt": prompt}
    to_small = form == "en" and cfg["cascade"]["route_english"]
    tier, model = ("small", small) if to_small else ("large", large)
    yield {"step": "route", "route": tier, "tier": tier, "model": model.name}
    call = yield from _ask(tier, model, prompt, system, hint)
    yield call
    if to_small and not usable_answer(call["text"]):
        yield {"step": "route", "route": "fallback", "tier": "large", "model": large.name}
        call = yield from _ask("large", large, question, system, hint)
        yield call


def answer(question: str, small: Model, large: Model, cfg: dict, system: str = SYSTEM_ANSWER,
           hint: dict | None = None) -> dict:
    """One question through Halala. The last call's text is the answer, and every call is paid for."""
    calls = [event for event in steps(question, small, large, cfg, system, hint) if event["step"] == "answer"]
    return {"text": calls[-1]["text"], "calls": calls}


def load_dev(cfg: dict) -> list:
    """The working questions, refusing any overlap with the sealed test set."""
    items = load_jsonl(resolve(cfg["run"]["data"]))
    sealed = resolve(cfg["run"]["sealed"]) if cfg["run"].get("sealed") else None
    if sealed and sealed.exists():
        test = load_jsonl(sealed)
        shared_groups = {it.group_id for it in items} & {it.group_id for it in test}
        shared_text = {for_match(it.question) for it in items} & {for_match(it.question) for it in test}
        if shared_groups or shared_text:
            raise SystemExit(f"Working data overlaps the sealed test set ({len(shared_groups)} groups, "
                             f"{len(shared_text)} questions). Point [run] data at the .dev.jsonl file from `seal`.")
    return items


def open_sealed(cfg: dict) -> list:
    """Open the sealed test set: check it is unchanged since sealing, and log the opening in its manifest."""
    path = resolve(cfg["run"]["sealed"]) if cfg["run"].get("sealed") else None
    if not path or not path.exists():
        raise SystemExit("No sealed test set. Run `python -m halala seal --data <file>` and set [run] sealed.")
    manifest_path = path.with_suffix(".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if file_sha256(path) != manifest["sha256"]:
        raise SystemExit(f"{path.name} has changed since it was sealed on {manifest['created']}. Restore it first.")
    manifest["unsealed"].append({"at": datetime.now().isoformat(timespec="seconds"), "config": cfg["run"]["name"]})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"unsealed {path.name} (opening #{len(manifest['unsealed'])}, logged in {manifest_path.name})")
    return load_jsonl(path)


def cmd_seal(source: str, test_fraction: float, seed: int, force: bool) -> dict:
    info = seal(resolve(source), resolve("data/sealed"), test_fraction, seed, force)
    print(f"dev:    {info['dev_path']}  ({info['dev_items']} items) - work on this one")
    print(f"sealed: {info['test_path']}  ({info['test_items']} items, {info['test_groups']} question groups)")
    return info


def cmd_ask(cfg: dict, question: str) -> None:
    """One question through Halala, printing each step."""
    small, large, cache = build_models(cfg)
    try:
        for event in steps(question, small, large, cfg):
            if event["step"] != "asking":
                print(event)
    finally:
        if cache is not None:
            cache.close()
