"""Command line: python -m halala <command> [--config configs/local_gemma.toml]"""

from __future__ import annotations

import argparse
import sys

from .config import load_config


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="halala")
    sub = p.add_subparsers(dest="cmd", required=True)

    def with_config(name: str, help_text: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--config", default=None, help="TOML layered over configs/default.toml")
        return sp

    a = with_config("ask", "send one question through Halala and print each step")
    a.add_argument("question")
    with_config("dialect-tax", "real seconds per correct answer by form, before and after each fix")
    f = with_config("fresh", "Arabizi on unseen text, from questions nobody tuned on")
    f.add_argument("--data", default="data/arabizi_fresh.jsonl")
    k = with_config("check", "regression gate on the dialect-tax table")
    k.add_argument("--save", action="store_true", help="save the current table as the baseline")
    m = with_config("measure", "Halala on mixed traffic, in real seconds")
    m.add_argument("--per-form", type=int, default=12)
    da = with_config("dialect-audit", "the Dialect Tax per form and model on the public benchmark")
    da.add_argument("--data", default="data/external/dialectal_mmlu.jsonl")
    u = with_config("sealed", "the one run on the sealed test set")
    u.add_argument("--unseal", action="store_true", help="required; each opening is logged")
    fd = sub.add_parser("fetch-dialects", help="sample the public dialect benchmark into a local file")
    fd.add_argument("--out", default="data/external/dialectal_mmlu.jsonl")
    fd.add_argument("--groups", type=int, default=100)
    fd.add_argument("--seed", type=int, default=13)
    se = sub.add_parser("seal", help="split a dataset into a dev file and a sealed test file")
    se.add_argument("--data", required=True, help="JSONL with all your questions")
    se.add_argument("--test-fraction", type=float, default=0.33)
    se.add_argument("--seed", type=int, default=13)
    se.add_argument("--force", action="store_true", help="overwrite an existing sealed file")
    args = p.parse_args(argv)

    from . import dialect_audit, measure, pipeline

    if args.cmd == "seal":
        pipeline.cmd_seal(args.data, args.test_fraction, args.seed, args.force)
    elif args.cmd == "fetch-dialects":
        dialect_audit.cmd_fetch_dialects(args.out, args.groups, args.seed)
    else:
        cfg = load_config(args.config)
        if args.cmd == "ask":
            pipeline.cmd_ask(cfg, args.question)
        elif args.cmd == "dialect-tax":
            measure.cmd_tax(cfg)
        elif args.cmd == "fresh":
            measure.cmd_fresh(cfg, args.data)
        elif args.cmd == "check":
            return measure.cmd_check(cfg, args.save)
        elif args.cmd == "measure":
            measure.cmd_measure(cfg, args.per_form)
        elif args.cmd == "dialect-audit":
            dialect_audit.cmd_dialect_audit(cfg, args.data)
        elif args.cmd == "sealed":
            measure.cmd_sealed(cfg, args.unseal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
