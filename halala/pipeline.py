"""The commands behind the CLI: collect, train, evaluate, tokens, ask."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import datetime

import numpy as np

from .calibrate import calibrate
from .collect import SYSTEM_ANSWER, collect, prepare_prompt
from .config import resolve, run_dir
from .data import (VARIANTS, convert_mcq_csv, file_sha256, load_examples, load_jsonl, seal, split_items,
                   write_jsonl)
from .features import detect_variant
from .normalize import for_match
from .models import build_models
from .policies import drop_unprofitable, evaluate, tier_costs, usable_answer
from .report import write_report
from .router import Router


def _sealed_path(cfg: dict):
    return resolve(cfg["run"]["sealed"]) if cfg["run"].get("sealed") else None


def _guard_leaks(cfg: dict, items: list) -> None:
    """Stop before any run where the sealed test set or the rewrite examples overlap the questions in use."""
    sealed = _sealed_path(cfg)
    if sealed and sealed.exists():
        test = load_jsonl(sealed)
        shared_groups = {it.group_id for it in items} & {it.group_id for it in test}
        shared_text = {for_match(it.question) for it in items} & {for_match(it.question) for it in test}
        if shared_groups or shared_text:
            raise SystemExit(f"Working data overlaps the sealed test set ({len(shared_groups)} groups, "
                             f"{len(shared_text)} questions). Point [run] data at the .dev.jsonl file from `seal`.")
        items = items + test
    if cfg["cascade"].get("arabizi_examples"):
        questions = {for_match(it.question) for it in items}
        clash = [ex["arabizi"] for ex in load_examples(resolve(cfg["cascade"]["arabizi_examples"]))
                 if for_match(ex["arabizi"]) in questions]
        if clash:
            raise SystemExit(f"Rewrite examples include questions from the data, which would leak answers: {clash}")


def load_splits(cfg: dict) -> dict:
    items = load_jsonl(resolve(cfg["run"]["data"]))
    _guard_leaks(cfg, items)
    r = cfg["run"]
    return split_items(items, r["split_fractions"], int(r["seed"]), int(r.get("limit_groups", 0)))


def _unseal(cfg: dict) -> list:
    """Open the sealed test set: check it is unchanged since sealing, and log the opening in its manifest."""
    path = _sealed_path(cfg)
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


def read_records(cfg: dict, split: str) -> list[dict]:
    path = run_dir(cfg) / f"collect_{split}.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} not found. Run: python -m halala collect --split {split}")
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def cmd_collect(cfg: dict, split: str = "all", unseal: bool = False) -> None:
    if split == "sealed":
        if not unseal:
            raise SystemExit("The sealed test set is for the final evaluation only. "
                             "Add --unseal if this is that run; each opening is logged.")
        splits = {"sealed": _unseal(cfg)}
        names = ["sealed"]
    else:
        splits = load_splits(cfg)
        names = list(splits) if split == "all" else [split]
    out = run_dir(cfg)
    (out / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    small, large, cache = build_models(cfg)
    try:
        for name in names:
            print(f"collect {name}: {len(splits[name])} items", flush=True)
            collect(splits[name], small, large, cfg, out / f"collect_{name}.jsonl")
    finally:
        if cache is not None:
            cache.close()


def cmd_seal(source: str, test_fraction: float, seed: int, force: bool) -> dict:
    info = seal(resolve(source), resolve("data/sealed"), test_fraction, seed, force)
    print(f"dev:    {info['dev_path']}  ({info['dev_items']} items) - work on this one")
    print(f"sealed: {info['test_path']}  ({info['test_items']} items, {info['test_groups']} question groups)")
    print(f"hash recorded in {info['manifest_path'].name}. Set in your config:")
    print(f'  [run] data = "data/{info["dev_file"]}"')
    print(f'        sealed = "data/sealed/{info["sealed_file"]}"')
    return info


EXPECTED_DETECTION = {"en": "en", "msa": "msa", "najdi": "dialect", "arabizi": "arabizi", "mixed": "mixed"}


def cmd_review(data: str) -> Path:
    """Render a dataset as a page a native speaker can read, flagging rows whose text doesn't match its label.
    A flag usually means the wording is not distinctly that variant, which is a question to rewrite."""
    path = resolve(data)
    items = load_jsonl(path)
    rows, flagged = [], 0
    for it in items:
        detected = detect_variant(it.question)
        ok = detected == EXPECTED_DETECTION.get(it.variant, it.variant)
        flagged += not ok
        note = "" if ok else f"reads as {detected}"
        rows.append(f"<tr class='{'' if ok else 'flag'}'><td>{html.escape(it.group_id)}</td>"
                    f"<td>{html.escape(it.variant)}</td><td dir='auto'>{html.escape(it.question)}</td>"
                    f"<td dir='auto'>{html.escape(' / '.join(it.answers))}</td><td>{note}</td></tr>")
    page = path.with_suffix(".review.html")
    page.write_text(
        "<!doctype html><meta charset='utf-8'><title>Halala: review questions</title>"
        "<style>body{font:15px system-ui,sans-serif;margin:24px;background:#fcfcfb;color:#0b0b0b}"
        "table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e6e5e1;padding:7px 10px;"
        "text-align:start;vertical-align:top}th{color:#52514e;font-weight:500}td{unicode-bidi:plaintext}"
        ".flag{background:#fdf0e9}h1{font-size:19px}p{color:#52514e}</style>"
        f"<h1>{html.escape(path.name)}</h1><p>{len(items)} items in {len({i.group_id for i in items})} groups. "
        f"{flagged} flagged: the wording does not read as the variant it is labelled, so rewrite it to be "
        "distinctly that variant.</p>"
        "<table><tr><th>Group</th><th>Variant</th><th>Question</th><th>Answers</th><th>Note</th></tr>"
        + "".join(rows) + "</table>", encoding="utf-8")
    print(f"{len(items)} items, {flagged} flagged\nreview page: {page}")
    return page


def cmd_convert_mcq(csv_path: str, out: str, limit: int) -> None:
    items = convert_mcq_csv(resolve(csv_path), limit)
    write_jsonl(resolve(out), items)
    print(f"wrote {len(items)} multiple-choice items to {out}")


def cmd_train(cfg: dict) -> dict:
    train, calib = read_records(cfg, "train"), read_records(cfg, "calib")
    router = Router(cfg["router"]["model"], int(cfg["run"]["seed"])).fit(train)
    agreement = Router("agreement").fit(train)
    scores = router.score(calib)
    thresholds = {
        "router": drop_unprofitable(calibrate(calib, scores, cfg), calib, scores, cfg),
        "agreement": calibrate(calib, agreement.score(calib), cfg),
    }
    out = run_dir(cfg)
    router.save(out / "router.pkl")
    (out / "thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    th = thresholds["router"]
    print(f"router trained on {len(train)} items; calibrated on {len(calib)}")
    print(f"  global threshold: {th['global']}")
    for v, t in th["per_variant"].items():
        print(f"  {v:<8} n={th['group_sizes'][v]:<5} threshold={'escalate always' if t is None else round(t, 3)}")
    return thresholds


def cmd_evaluate(cfg: dict, readme: bool = False, split: str = "test") -> dict:
    out = run_dir(cfg)
    if not (out / "router.pkl").exists():
        raise SystemExit("No trained router. Run: python -m halala train")
    if split == "dev":   # every non-sealed question, for policies with no trained parts
        test = [r for name in cfg["run"]["split_fractions"] for r in read_records(cfg, name)]
    else:
        test = read_records(cfg, split)
    router = Router.load(out / "router.pkl")
    thresholds = json.loads((out / "thresholds.json").read_text(encoding="utf-8"))
    res = {**evaluate(test, router, thresholds, cfg), "split": split}
    report_dir = out if split == "test" else out / split
    report_dir.mkdir(exist_ok=True)
    print(write_report(res, report_dir, readme=readme))
    return res


def cmd_tokens(cfg: dict) -> str:
    """The token-tax baseline: input tokens per variant, and the extra over the same question in English."""
    records = []
    for split in cfg["run"]["split_fractions"]:
        path = run_dir(cfg) / f"collect_{split}.jsonl"
        if path.exists():
            records += read_records(cfg, split)
    if not records:
        raise SystemExit("Nothing collected yet. Run: python -m halala collect")
    by_group = defaultdict(dict)
    for r in records:
        by_group[r["group_id"]][r["variant"]] = r
    def large_in(r: dict) -> int:
        return r["calls"]["large"][0]["tokens_in"]

    def small_in(r: dict) -> int:   # includes the Arabizi rewrite, which the small model also pays for
        return sum(c["tokens_in"] for c in r["calls"]["translit"]) + r["calls"]["small"][0]["tokens_in"]

    lines = ["| Variant | Large: input tokens | Large: extra vs English | Small: input tokens | Small: extra vs English |",
             "|---|---|---|---|---|"]
    for v in VARIANTS:
        rows = [g[v] for g in by_group.values() if v in g]
        if not rows:
            continue
        pairs = [g for g in by_group.values() if v in g and "en" in g]
        extra_l = [large_in(g[v]) - large_in(g["en"]) for g in pairs]
        extra_s = [small_in(g[v]) - small_in(g["en"]) for g in pairs]
        lines.append(f"| {v} | {np.mean([large_in(r) for r in rows]):.1f} | {np.mean(extra_l):+.1f} | "
                     f"{np.mean([small_in(r) for r in rows]):.1f} | {np.mean(extra_s):+.1f} |")
    md = "Input tokens include the fixed system prompt, which is the same for every variant.\n\n" + "\n".join(lines)
    (run_dir(cfg) / "tokens.md").write_text(md, encoding="utf-8")
    print(md)
    return md


def cmd_profile(cfg: dict, split: str = "test") -> str:
    """Per-variant accuracy and agreement for collected records, plus a page to read every answer."""
    records = read_records(cfg, split)
    lines = ["| Variant | n | Small, greedy | Small, majority of samples | Large, raw question | Mean agreement | "
             "Agreement when majority right | Agreement when wrong |",
             "|---|---|---|---|---|---|---|---|"]
    present = [v for v in VARIANTS if any(r["variant"] == v for r in records)]
    for v in present:
        rows = [r for r in records if r["variant"] == v]
        right = [r["agreement"] for r in rows if r["majority_correct"]]
        wrong = [r["agreement"] for r in rows if not r["majority_correct"]]

        def pct(key: str) -> str:
            return f"{100 * np.mean([r[key] for r in rows]):.0f}%"

        def avg(xs: list) -> str:
            return f"{np.mean(xs):.2f}" if xs else "n/a"

        lines.append(f"| {v} | {len(rows)} | {pct('greedy_correct')} | {pct('majority_correct')} | "
                     f"{pct('large_correct')} | {avg([r['agreement'] for r in rows])} | {avg(right)} | {avg(wrong)} |")
    md = (f"Model `{cfg['models']['small']['name']}`, {len(records)} items. The small tier sees the cleaned "
          "and rewritten prompt; the large tier sees the raw question.\n\n" + "\n".join(lines)
          + "\n\n" + _tokens_per_success(records, present, cfg))
    out = run_dir(cfg)
    (out / "profile.md").write_text(md, encoding="utf-8")
    (out / "profile.html").write_text(_profile_html(records), encoding="utf-8")
    print(md)
    print(f"\nread every answer: {out / 'profile.html'}")
    return md


def _tokens_per_success(records: list[dict], variants: list[str], cfg: dict) -> str:
    """Tokens spent per correct answer for each way of running the model. Failed runs count as spend."""
    setups = (("Plain: one call, raw question", "large", "large_correct"),
              ("Cleanup and rewrite, one call", "greedy", "greedy_correct"),
              ("Cleanup and rewrite, majority of samples", "samples", "majority_correct"))

    def per_success(rows: list[dict], tier: str, flag: str) -> float | None:
        wins = sum(r[flag] for r in rows)
        return sum(tier_costs(r, cfg)[tier]["tokens"] for r in rows) / wins if wins else None

    english = {tier: per_success([r for r in records if r["variant"] == "en"], tier, flag)
               for _, tier, flag in setups}
    out = ["Tokens per correct answer (multiple of English in brackets). Failed runs count as spend.", "",
           "| Variant | " + " | ".join(name for name, _, _ in setups) + " |", "|---|" + "---|" * len(setups)]
    for v in variants:
        rows = [r for r in records if r["variant"] == v]
        cells = []
        for _, tier, flag in setups:
            value, base = per_success(rows, tier, flag), english[tier]
            if value is None:
                cells.append("no correct answers")
            else:
                cells.append(f"{value:.0f} ({value / base:.1f}x)" if base else f"{value:.0f}")
        out.append(f"| {v} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def _profile_html(records: list[dict]) -> str:
    def cell(text: str, ok: bool | None = None) -> str:
        mark = "" if ok is None else (" ✓" if ok else " ✗")
        return f"<td dir='auto'>{html.escape(str(text))}{mark}</td>"

    def rewrite(r: dict) -> str:
        rw = r.get("rewrite") or {}
        return f"rejected ({rw['rejected']}): {rw['text']}" if rw.get("rejected") else rw.get("text", "")

    head = "".join(f"<th>{h}</th>" for h in ("Variant", "Question", "Rewrite", "Small model sees", "Small answers",
                                              "Agreement", "Majority", "Large, raw question"))
    body = "".join(
        "<tr>" + cell(r["variant"]) + cell(r["question"]) + cell(rewrite(r)) + cell(r["prompt"])
        + cell(" | ".join(r["small_texts"]))
        + cell(f"{r['agreement']:.1f}") + cell(r["majority_text"], r["majority_correct"])
        + cell(r["large_text"], r["large_correct"]) + "</tr>"
        for r in records
    )
    return ("<!doctype html><meta charset='utf-8'><title>Halala profile</title>"
            "<style>body{font:14px system-ui,sans-serif;margin:24px;background:#fcfcfb;color:#0b0b0b}"
            "table{border-collapse:collapse}th,td{border-bottom:1px solid #e6e5e1;padding:6px 10px;"
            "vertical-align:top;text-align:start}th{color:#52514e;font-weight:500}td{unicode-bidi:plaintext}</style>"
            f"<table><tr>{head}</tr>{body}</table>")


def cmd_ask(cfg: dict, question: str) -> dict:
    """One question through Halala, with a trace. The seed of the demo."""
    if any(cfg["models"][t]["backend"] == "mock" for t in ("small", "large")):
        print("(mock models: answers are placeholders; use --config configs/local_gemma.toml for real ones)")
    small, large, cache = build_models(cfg)
    variant = detect_variant(question)
    tokens = {"small": 0, "large": 0}
    seconds = 0.0

    def ask(tier: str, model, prompt: str) -> str:
        nonlocal seconds
        c = model.complete(SYSTEM_ANSWER, prompt, 0.0, 0, {})
        tokens[tier] += c.tokens_in + c.tokens_out
        seconds += c.latency_s
        return c.text

    try:
        prompt, rewrite_calls, rewrite = prepare_prompt(question, cfg["cascade"], small)
        tokens["small"] += sum(c["tokens_in"] + c["tokens_out"] for c in rewrite_calls)
        if variant != "en":
            route = "large model, with the rewrite" if rewrite.get("text") else "large model"
            answer = ask("large", large, prompt)
        else:
            route = "small model, once"
            answer = ask("small", small, prompt)
            if not usable_answer(answer):
                route = "small model gave no usable answer, so the large model answered"
                answer = ask("large", large, question)
    finally:
        if cache is not None:
            cache.close()
    return _show_trace(run_dir(cfg), {
        "question": question,
        "detected_variant": variant,
        "rewrite": (f"rejected ({rewrite['rejected']}): {rewrite['text']}" if rewrite.get("rejected")
                    else rewrite.get("text", "not needed")),
        "model_sees": prompt,
        "route": route,
        "answer": answer,
        "tokens": tokens,
        "seconds": round(seconds, 2),
    })


def _show_trace(out, trace: dict) -> dict:
    for k, v in trace.items():
        print(f"{k:>18}: {v}")
    # Terminals on Windows draw Arabic left to right; the browser lays it out properly.
    page = out / "ask.html"
    page.write_text(_trace_html(trace), encoding="utf-8")
    print(f"\nreadable version: {page}")
    return trace


def _trace_html(trace: dict) -> str:
    rows = "".join(
        f"<tr><th>{html.escape(k.replace('_', ' '))}</th><td dir='auto'>{html.escape(str(v))}</td></tr>"
        for k, v in trace.items()
    )
    return ("<!doctype html><meta charset='utf-8'><title>Halala trace</title>"
            "<style>body{font:16px system-ui,sans-serif;margin:24px;background:#fcfcfb;color:#0b0b0b}"
            "th{text-align:left;color:#52514e;font-weight:500;padding:6px 16px 6px 0;vertical-align:top}"
            "td{padding:6px 0;unicode-bidi:plaintext}</style>"
            f"<table>{rows}</table>")
