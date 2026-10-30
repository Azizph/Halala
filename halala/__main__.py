"""Command line: python -m halala <command> [--config configs/<name>.toml]"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .config import load_config, resolve, run_dir


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="halala")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synth", help="write the synthetic arithmetic set (five variants per question)")
    s.add_argument("--groups", type=int, default=400)
    s.add_argument("--out", default="data/synthetic_arith.jsonl")
    s.add_argument("--seed", type=int, default=13)

    def with_config(name: str, help_text: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--config", default=None, help="TOML layered over configs/default.toml")
        return sp

    c = with_config("collect", "run both tiers over the data once and cache every call")
    c.add_argument("--split", default="all", choices=["all", "train", "calib", "test", "sealed"])
    c.add_argument("--unseal", action="store_true", help="required for --split sealed; each opening is logged")
    with_config("train", "fit the router on train, calibrate thresholds on calib")
    e = with_config("evaluate", "replay every policy on test and write the report")
    e.add_argument("--readme", action="store_true", help="also write the results into README.md")
    e.add_argument("--split", default="test", choices=["test", "dev", "sealed"])
    r = with_config("run", "collect, train and evaluate in one go")
    r.add_argument("--readme", action="store_true")
    with_config("tokens", "token-tax baseline: input tokens per variant vs English")
    pr = with_config("profile", "per-variant accuracy and agreement, plus a page to read every answer")
    pr.add_argument("--split", default="test", choices=["train", "calib", "test", "sealed"])
    se = sub.add_parser("seal", help="split a dataset into a dev file and a sealed test file")
    se.add_argument("--data", required=True, help="JSONL with all your questions")
    se.add_argument("--test-fraction", type=float, default=0.33)
    se.add_argument("--seed", type=int, default=13)
    se.add_argument("--force", action="store_true", help="overwrite an existing sealed file")
    rv = sub.add_parser("review", help="render a dataset as a page to check by hand, flagging mislabelled rows")
    rv.add_argument("--data", required=True)
    mc = sub.add_parser("convert-mcq", help="multiple-choice CSV (e.g. ArabicMMLU) to Halala JSONL")
    mc.add_argument("--csv", required=True)
    mc.add_argument("--out", required=True)
    mc.add_argument("--limit", type=int, default=0)
    fd = sub.add_parser("fetch-dialects", help="sample the public dialect benchmark into a local file")
    fd.add_argument("--out", default="data/external/dialectal_mmlu.jsonl")
    fd.add_argument("--groups", type=int, default=100)
    fd.add_argument("--seed", type=int, default=13)
    da = with_config("dialect-audit", "the Dialect Tax per form and model on the public benchmark")
    da.add_argument("--data", default="data/external/dialectal_mmlu.jsonl")
    dr = with_config("dialect-rewrite", "one attempt at closing the Saudi gap with the word list")
    dr.add_argument("--data", default="data/external/dialectal_mmlu.jsonl")
    with_config("prompt-eval", "compare instructions on the dev questions with Halala's real routing (H8)")
    ms = with_config("measure", "real server time per arm on a sample of dev questions, with no cache")
    ms.add_argument("--arms", default=None, help="comma-separated; all arms by default")
    ms.add_argument("--per-form", type=int, default=12)
    ms.add_argument("--interleaved", action="store_true", help="questions in mixed order, so models really swap")
    rw = with_config("rewrite-eval", "compare ways of handling Arabizi on the dev questions (H5)")
    rw.add_argument("--examples", default="data/arabizi_examples.jsonl")
    a = with_config("ask", "send one question through the live cascade and print the trace")
    a.add_argument("question")
    k = with_config("check", "regression gate: compare test results with the saved baseline")
    k.add_argument("--save", action="store_true", help="save the current results as the baseline")
    k.add_argument("--tol-acc", type=float, default=0.01)
    k.add_argument("--tol-cost", type=float, default=0.02)
    cmp = sub.add_parser("compare", help="ablation table across runs")
    cmp.add_argument("--configs", nargs="+", required=True)
    sm = sub.add_parser("smoke", help="the whole pipeline on mock models")
    sm.add_argument("--groups", type=int, default=400)

    args = p.parse_args(argv)

    from . import pipeline
    from .data import make_synthetic_arith, write_jsonl

    if args.cmd == "synth":
        write_jsonl(resolve(args.out), make_synthetic_arith(args.groups, args.seed))
        print(f"wrote {args.groups * 5} items to {args.out}")
        return 0
    if args.cmd == "seal":
        pipeline.cmd_seal(args.data, args.test_fraction, args.seed, args.force)
        return 0
    if args.cmd == "fetch-dialects":
        from .dialect_audit import cmd_fetch_dialects

        cmd_fetch_dialects(args.out, args.groups, args.seed)
        return 0
    if args.cmd == "review":
        pipeline.cmd_review(args.data)
        return 0
    if args.cmd == "convert-mcq":
        pipeline.cmd_convert_mcq(args.csv, args.out, args.limit)
        return 0
    if args.cmd == "compare":
        from .report import compare_runs

        md = compare_runs([run_dir(load_config(cfg)) for cfg in args.configs])
        out = resolve("runs") / "compare.md"
        out.write_text(md, encoding="utf-8")
        print(md)
        return 0
    if args.cmd == "smoke":
        cfg = load_config()
        data = resolve(cfg["run"]["data"])
        if not data.exists():
            write_jsonl(data, make_synthetic_arith(args.groups, int(cfg["run"]["seed"])))
        pipeline.cmd_collect(cfg)
        pipeline.cmd_train(cfg)
        pipeline.cmd_evaluate(cfg)
        return 0

    cfg = load_config(args.config)
    if args.cmd == "collect":
        pipeline.cmd_collect(cfg, args.split, args.unseal)
    elif args.cmd == "train":
        pipeline.cmd_train(cfg)
    elif args.cmd == "evaluate":
        pipeline.cmd_evaluate(cfg, args.readme, args.split)
    elif args.cmd == "run":
        pipeline.cmd_collect(cfg)
        pipeline.cmd_train(cfg)
        pipeline.cmd_evaluate(cfg, args.readme)
    elif args.cmd == "tokens":
        pipeline.cmd_tokens(cfg)
    elif args.cmd == "profile":
        pipeline.cmd_profile(cfg, args.split)
    elif args.cmd == "dialect-audit":
        from .dialect_audit import cmd_dialect_audit

        cmd_dialect_audit(cfg, args.data)
    elif args.cmd == "dialect-rewrite":
        from .dialect_audit import cmd_dialect_rewrite

        cmd_dialect_rewrite(cfg, args.data)
    elif args.cmd == "prompt-eval":
        from .prompt_eval import cmd_prompt_eval

        cmd_prompt_eval(cfg)
    elif args.cmd == "measure":
        from .measure import ALL_ARMS, cmd_measure

        arms = args.arms.split(",") if args.arms else list(ALL_ARMS)
        cmd_measure(cfg, arms, args.per_form, args.interleaved)
    elif args.cmd == "rewrite-eval":
        from .rewrite_eval import cmd_rewrite_eval

        cmd_rewrite_eval(cfg, args.examples)
    elif args.cmd == "ask":
        pipeline.cmd_ask(cfg, args.question)
    elif args.cmd == "check":
        import json

        from .report import check_regression

        out = run_dir(cfg)
        res = json.loads((out / "results.json").read_text(encoding="utf-8"))
        baseline = out / "baseline.json"
        if args.save:
            baseline.write_text(json.dumps(res["policies"]["halala"], indent=2), encoding="utf-8")
            print(f"saved baseline to {baseline}")
            return 0
        if not baseline.exists():
            print("No baseline yet. Run: python -m halala check --save")
            return 1
        problems = check_regression(res, baseline, args.tol_acc, args.tol_cost)
        for msg in problems:
            print(f"REGRESSION: {msg}")
        print("check passed" if not problems else "check failed")
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
