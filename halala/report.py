"""Results table, charts, README injection, cross-run comparison and the regression gate."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .config import ROOT  # noqa: E402

VARIANT_LABELS = {"en": "English", "msa": "MSA", "najdi": "Najdi", "arabizi": "Arabizi", "mixed": "Mixed",
                  "dialect": "Dialect"}
COST_LABELS = {"tokens": "tokens", "flops": "estimated FLOPs", "usd": "US dollars", "latency_s": "seconds"}
TABLE_POLICIES = ("always_small", "always_large", "agreement_global", "router_global", "halala_full", "halala",
                  "halala_cache")

# Reference palette (dataviz skill): light surface, ink tokens, categorical slots 1-3 in fixed order.
SURFACE, INK, INK_2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1", "#b9b7b0"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")


def _pct(x: float, digits: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.{digits}f}%"


def _pts(x: float) -> str:
    if math.isnan(x):
        return "n/a"
    value = round(100 * x, 1)
    return "0.0 pts" if value == 0 else f"{value:+.1f} pts"


def _english_cost(res: dict) -> float | None:
    """Always-large's cost per success on English, or overall if the data has no English variant."""
    large = res["policies"]["always_large"]
    return large["per_variant"].get("en", {}).get("cost_per_success") or large["cost_per_success"]


def _times(value: float | None, base: float | None) -> str:
    return "no successes" if value is None or not base else f"{value / base:.1f}x"


def render_markdown(res: dict, image_prefix: str = "") -> str:
    split = {"sealed": "sealed test set", "dev": "all dev questions"}.get(res.get("split"), "test split")
    lines = [f"### Run `{res['run']}`: {split}, {res['n_test']} items",
             "",
             f"Small model `{res['models']['small']}`, large model `{res['models']['large']}`. "
             f"Cost is {COST_LABELS[res['primary']]}, shown relative to always using the large model.",
             ""]
    if res["mock"]:
        lines += ["**Mock models.** These numbers only check that the pipeline works. They are not results.", ""]
    if res.get("split") == "dev":
        lines += ["The router and thresholds were fitted on most of these questions, so their rows are optimistic. "
                  "Halala has no trained parts.", ""]
    floors = res.get("floors", {})
    lines += [f"Floors: every variant at {_pct(floors.get('min_variant_success', 0), 0)} success or better, and a task "
              f"only succeeds if answered within {floors.get('latency_limit_s') or 'any'} seconds.", "",
              "| Policy | Accuracy | Worst variant vs always-large | Cost per success vs always-large | "
              "Cost vs always-large | Sent to large model | p95 latency | Meets floors |",
              "|---|---|---|---|---|---|---|---|"]
    for key in TABLE_POLICIES:
        p = res["policies"].get(key)
        if not p:
            continue
        worst = VARIANT_LABELS.get(p["worst_variant"], p["worst_variant"])
        lines.append(f"| {p['label']} | {_pct(p['accuracy'])} | {_pts(-p['worst_gap'])} ({worst}) | "
                     f"{_pct(p['relative_cost_per_success'], 0)} | {_pct(p['relative_cost'], 0)} | "
                     f"{_pct(p['escalation_rate'], 0)} | {p['p95_latency_s']:.1f}s | "
                     f"{'yes' if p['meets_floors'] else 'no'} |")

    shown = [k for k in ("always_small", "always_large", "router_global", "halala_full", "halala")
             if k in res["policies"]]
    lines += ["", "#### Accuracy by variant", "",
              "| Variant | " + " | ".join(res["policies"][k]["label"] for k in shown) + " | Halala: sent to large |",
              "|---|" + "---|" * (len(shown) + 1)]
    for v in res["variants"]:
        cells = [_pct(res["policies"][k]["per_variant"][v]["accuracy"]) for k in shown]
        esc = _pct(res["policies"]["halala"]["per_variant"][v]["escalation_rate"], 0)
        lines.append(f"| {VARIANT_LABELS.get(v, v)} | " + " | ".join(cells) + f" | {esc} |")

    base = _english_cost(res)
    lines += ["", "#### Cost per successful task, by variant", "",
              "1.0x is always-large on English. Failed tasks still count as spend, so a variant that fails often "
              "costs more per success.", "",
              "| Variant | " + " | ".join(res["policies"][k]["label"] for k in shown) + " |",
              "|---|" + "---|" * len(shown)]
    for v in res["variants"]:
        cells = [_times(res["policies"][k]["per_variant"][v]["cost_per_success"], base) for k in shown]
        lines.append(f"| {VARIANT_LABELS.get(v, v)} | " + " | ".join(cells) + " |")

    lines += ["", f"#### Full pipeline guarantee check (epsilon = {res['epsilon']}, delta = {res['delta']})", "",
              "Loss is the share of questions it got wrong that the large model got right. Thresholds are set "
              "per detected variant; this table groups by the dataset's variant labels.", "",
              "| Variant | Loss on test | Within epsilon |", "|---|---|---|"]
    for v, g in res["guarantee"].items():
        lines.append(f"| {VARIANT_LABELS.get(v, v)} | {_pct(g['loss_rate'])} | {'yes' if g['within_epsilon'] else 'no'} |")

    lines += ["", f"![Cost per success by variant]({image_prefix}cost_per_success.png)", "",
              f"![Compute vs accuracy]({image_prefix}pareto.png)", "",
              f"![Accuracy by variant]({image_prefix}variants.png)", ""]
    return "\n".join(lines)


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_pareto(res: dict, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharex=True, sharey=True, facecolor=SURFACE)
    sweeps = (("router", "Router, one threshold"), ("agreement", "Agreement, one threshold"))
    points = (("always_small", "Always small"), ("always_large", "Always large"), ("halala", "Halala"))
    for ax, key, title in zip(axes, ("accuracy", "worst_accuracy"), ("Overall accuracy", "Worst-variant accuracy")):
        _style(ax)
        for (name, label), color in zip(sweeps, SERIES):
            pts = sorted(res["sweeps"][name], key=lambda p: p["relative_cost"])
            ax.plot([100 * p["relative_cost"] for p in pts], [100 * p[key] for p in pts],
                    color=color, linewidth=2, label=label)
        for pkey, text in points:
            p = res["policies"][pkey]
            x, y = 100 * p["relative_cost"], 100 * p[key]
            ax.plot(x, y, marker="o", markersize=8, color=INK, markeredgecolor=SURFACE, markeredgewidth=2,
                    linestyle="none", zorder=5)
            ax.annotate(text, (x, y), xytext=(7, -13), textcoords="offset points", fontsize=9, color=INK)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xlabel("Compute per question (% of always-large)", color=INK_2, fontsize=9)
    axes[0].set_ylabel("Accuracy (%)", color=INK_2, fontsize=9)
    axes[0].legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_variants(res: dict, path: Path) -> None:
    series = (("always_large", "Always large"), ("router_global", "Router, one threshold"), ("halala", "Halala"))
    variants = res["variants"]
    x, width = np.arange(len(variants)), 0.27
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="x", visible=False)
    for i, ((key, label), color) in enumerate(zip(series, SERIES)):
        values = [100 * res["policies"][key]["per_variant"][v]["accuracy"] for v in variants]
        ax.bar(x + (i - 1) * width, values, width, color=color, edgecolor=SURFACE, linewidth=1.5, label=label)
    ax.set_xticks(x, [VARIANT_LABELS.get(v, v) for v in variants])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Accuracy (%)", color=INK_2, fontsize=9)
    ax.set_title("Accuracy by variant", loc="left", fontsize=11, color=INK, pad=26)
    ax.legend(frameon=False, fontsize=9, ncols=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_cost_per_success(res: dict, path: Path) -> None:
    series = (("always_large", "Always large"), ("router_global", "Router, one threshold"), ("halala", "Halala"))
    variants, base = res["variants"], _english_cost(res)
    x, width = np.arange(len(variants)), 0.27
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="x", visible=False)
    for i, ((key, label), color) in enumerate(zip(series, SERIES)):
        costs = [res["policies"][key]["per_variant"][v]["cost_per_success"] for v in variants]
        values = [c / base if c is not None and base else 0.0 for c in costs]
        positions = x + (i - 1) * width
        ax.bar(positions, values, width, color=color, edgecolor=SURFACE, linewidth=1.5, label=label)
        for pos, c in zip(positions, costs):
            if c is None:   # no bar to draw: nothing succeeded, so the cost per success has no value
                ax.text(pos, 0.02, "no successes", rotation=90, ha="center", va="bottom", fontsize=8,
                        color=INK_2, transform=ax.get_xaxis_transform())
    ax.set_xticks(x, [VARIANT_LABELS.get(v, v) for v in variants])
    ax.set_ylabel("Cost per success (1 = always-large on English)", color=INK_2, fontsize=9)
    ax.set_title("Cost per successful task", loc="left", fontsize=11, color=INK, pad=26)
    ax.legend(frameon=False, fontsize=9, ncols=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def write_report(res: dict, out_dir: Path, readme: bool = False) -> str:
    with open(out_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    plot_cost_per_success(res, out_dir / "cost_per_success.png")
    plot_pareto(res, out_dir / "pareto.png")
    plot_variants(res, out_dir / "variants.png")
    md = render_markdown(res)
    (out_dir / "results.md").write_text(md, encoding="utf-8")
    if readme:
        prefix = out_dir.resolve().relative_to(ROOT).as_posix() + "/"
        inject_readme(render_markdown(res, image_prefix=prefix))
    return md


def inject_readme(block: str, readme: Path = ROOT / "README.md") -> None:
    text = readme.read_text(encoding="utf-8")
    new = re.sub(r"(<!-- results:start -->).*?(<!-- results:end -->)",
                 lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", text, flags=re.S)
    readme.write_text(new, encoding="utf-8")


def compare_runs(run_dirs: list[Path]) -> str:
    """One row per run for the Halala policy: the ablation table."""
    lines = ["| Run | Accuracy | Worst variant vs always-large | Cost per success vs always-large | "
             "Cost vs always-large | Sent to large | Arabizi sent to large |",
             "|---|---|---|---|---|---|---|"]
    for d in run_dirs:
        res = json.loads((d / "results.json").read_text(encoding="utf-8"))
        p = res["policies"]["halala"]
        arabizi = p["per_variant"].get("arabizi", {}).get("escalation_rate", float("nan"))
        lines.append(f"| {res['run']} | {_pct(p['accuracy'])} | {_pts(-p['worst_gap'])} | "
                     f"{_pct(p['relative_cost_per_success'], 0)} | {_pct(p['relative_cost'], 0)} | "
                     f"{_pct(p['escalation_rate'], 0)} | {_pct(arabizi, 0)} |")
    return "\n".join(lines)


def check_regression(res: dict, baseline_path: Path, tol_acc: float, tol_cost: float) -> list[str]:
    """Problems compared with the saved baseline; an empty list means the gate passes."""
    base = json.loads(baseline_path.read_text(encoding="utf-8"))
    now = res["policies"]["halala"]
    problems = []
    if now["accuracy"] < base["accuracy"] - tol_acc:
        problems.append(f"accuracy fell {_pct(base['accuracy'])} -> {_pct(now['accuracy'])}")
    if now["worst_gap"] > base["worst_gap"] + tol_acc:
        problems.append(f"worst-variant gap grew {_pts(base['worst_gap'])} -> {_pts(now['worst_gap'])}")
    if now["relative_cost"] > base["relative_cost"] + tol_cost:
        problems.append(f"cost rose {_pct(base['relative_cost'], 0)} -> {_pct(now['relative_cost'], 0)}")
    before, after = base.get("relative_cost_per_success"), now["relative_cost_per_success"]
    if before is not None and after > before + tol_cost:
        problems.append(f"cost per success rose {_pct(before, 0)} -> {_pct(after, 0)}")
    return problems
