"""Build demo/examples.js from demo/comparisons.json and the recorded runs. No model is called.

Recorded answers go through `run_question` in demo/server.py, the same steps as live mode, so replay and live can't
drift apart. Run from anywhere: python demo/build_examples.py
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
from pathlib import Path

import server   # demo/server.py, which also puts the repo on sys.path

from halala.models import Completion

DEMO = Path(__file__).resolve().parent
RUN = "runs/local_gemma"
SPLITS = ("collect_train", "collect_calib", "collect_test")


class Recorded:
    """Stands in for a model and answers from the recorded calls, keyed by the text the model was sent."""

    def __init__(self, name: str, calls: dict[str, dict]):
        self.name = name
        self.calls = calls

    def complete(self, system: str, user: str, temperature: float = 0.0, sample: int = 0,
                 hint: dict | None = None) -> Completion:
        if user not in self.calls:
            raise SystemExit(f"nothing recorded for {user!r}: the run no longer matches the Halala path")
        return Completion(**self.calls[user])


def load_records(run: Path) -> dict[str, tuple[str, dict]]:
    records = {}
    for split in SPLITS:
        path = run / f"{split}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            records[row["id"]] = (f"{RUN}/{path.name}", row)
    return records


def replay(row: dict, cfg: dict) -> list[dict]:
    """The recorded answers to one question, as the events live mode would send."""
    calls = row["calls"]
    small = Recorded(cfg["models"]["small"]["name"], {row["prompt"]: calls["small"][0]})
    large = Recorded(cfg["models"]["large"]["name"], {row["prompt"]: calls["large_rescued"][0],
                                                      row["question"]: calls["large"][0]})
    events = list(server.run_question(row["question"], row["answers"], server.PATHS, small, large, cfg))
    for event in events:
        if "seconds" in event:   # the rewrite is timed here, and the file shouldn't change on every build
            event["seconds"] = round(event["seconds"], 3)
    return events


def side(records: dict, group: str, form: str, cfg: dict) -> dict:
    source, row = records[f"{group}-{form}"]
    return {"form": form, "question": row["question"], "answers": row["answers"], "source": source,
            "events": replay(row, cfg)}


def outcome(events: list[dict], step: str) -> bool | None:
    return next(event["correct"] for event in reversed(events) if event["step"] == step)


def check(comparison: dict, example: dict) -> None:
    """Stop if a rebuilt example no longer shows what its comparison says it shows."""
    expect = comparison.get("expect", {})
    seen = {"left": outcome(example["left"]["events"], "direct"), "right": outcome(example["right"]["events"], "direct"),
            "fixed": outcome(example["right"]["events"], "answer")}
    wrong = [key for key, value in expect.items() if seen[key] != value]
    if wrong:
        raise SystemExit(f"{example['id']} no longer shows the expected result for: {', '.join(wrong)}")


def build(spec: dict, cfg: dict, records: dict) -> dict:
    comparisons = []
    for comparison in spec["comparisons"]:
        examples = []
        for chosen in comparison["examples"]:
            group = chosen["group"]
            example = {"id": group, "label": chosen["label"],
                       "left": side(records, group, comparison["left"]["form"], cfg),
                       "right": side(records, group, comparison["right"]["form"], cfg)}
            check(comparison, example)
            # The glosses are hand translations of these exact replies, so a different live reply gets none.
            example["glosses"] = {}
            if chosen.get("gloss_raw"):
                example["glosses"][next(e["text"] for e in example["right"]["events"]
                                        if e["step"] == "direct")] = chosen["gloss_raw"]
            if chosen.get("gloss_fixed"):
                example["glosses"][next(e["text"] for e in example["right"]["events"]
                                        if e["step"] == "answer")] = chosen["gloss_fixed"]
            examples.append(example)
        comparisons.append({**comparison, "examples": examples})
    picks = [{"label": pick["label"], **side(records, pick["group"], pick["form"], cfg)} for pick in spec["picks"]]
    recorded = {tier: {"name": cfg["models"][tier]["name"], "params_b": cfg["models"][tier].get("params_b", 0)}
                for tier in server.TIERS}
    return {"recorded": recorded, "comparisons": comparisons, "picks": picks}


def main() -> None:
    spec = json.loads((DEMO / "comparisons.json").read_text(encoding="utf-8"))
    run = DEMO.parent / RUN
    cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
    data = build(spec, cfg, load_records(run))
    body = json.dumps(data, ensure_ascii=False, indent=1)
    (DEMO / "examples.js").write_text(
        "// Generated by demo/build_examples.py from demo/comparisons.json and recorded runs. Do not edit by hand.\n"
        f"window.HALALA_EXAMPLES = {body};\n", encoding="utf-8")
    count = sum(len(c["examples"]) for c in data["comparisons"])
    print(f"wrote {count} examples and {len(data['picks'])} picks to demo/examples.js")


if __name__ == "__main__":
    main()
