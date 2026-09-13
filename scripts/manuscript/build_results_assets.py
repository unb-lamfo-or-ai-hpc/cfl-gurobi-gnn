"""Render only the reviewed source-diagnostic extract; never execute research jobs.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2] / "manuscript"


def build(root: Path = ROOT) -> None:
    evidence = json.loads((root / "results/source_evidence.json").read_text())
    figures = root / "figures"
    tables = root / "tables"
    figures.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "cfl-pr52-source-evidence-v1"})

    def save(fig, name):
        fig.savefig(figures / f"{name}.png", dpi=220, bbox_inches="tight")
        fig.savefig(figures / f"{name}.svg", bbox_inches="tight", metadata={"Date": None})
        plt.close(fig)

    cohort = evidence["cohort"]
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 2.7), layout="constrained")
    groups = [("Easy", "Medium", "Hard"), ("Train", "Validation", "Test")]
    counts = [([cohort[f"planned_{d}"] for d in ("easy", "medium", "hard")],
               [cohort[f"admitted_{d}"] for d in ("easy", "medium", "hard")]),
              ([cohort["initial_roles"][r] for r in ("train", "validation", "test")],
               [cohort["revised_roles"][r] for r in ("train", "validation", "test")])]
    assert sum(cohort["revised_roles"].values()) == cohort["admitted"] == 39
    for ax, names, (planned, admitted) in zip(axes, groups, counts):
        xs = list(range(3))
        for delta, values, color, label in [(-.19, planned, "#a5b4c2", "Original cohort"),
                                             (.19, admitted, "#176b87", "Admitted revision")]:
            bars = ax.bar([x + delta for x in xs], values, .36, label=label, color=color)
            ax.bar_label(bars, padding=3, fontsize=9)
        ax.set_xticks(xs, names)
        ax.set_ylabel("Original parents (count)")
        ax.set_ylim(0, 35)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    save(fig, "figure_cohort_admission")

    rows = []
    for parent in evidence["rejected"]:
        for run in parent["repairs"]:
            rows.append({"source_instance_id": parent["source_instance_id"],
                         "role": parent["role"], "budget_seconds": run["budget_seconds"],
                         "mip_gap_relative": run["mip_gap_relative"],
                         "solution_objective": run["solution_objective"],
                         "best_bound": run["best_bound"],
                         "right_censored": run["right_censored"],
                         **run["time_regions"], "source_report_sha256": run["report"]["sha256"]})
    with (tables / "table_source_rejection_outcomes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    fig, ax = plt.subplots(figsize=(7.5, 2.7), layout="constrained")
    xs = list(range(3))
    for delta, budget, color, label in [(-.18, 3600, "#667c91", "3,600 s"),
                                       (.18, 14400, "#176b87", "14,400 s")]:
        values = [100 * r["mip_gap_relative"] for r in rows if r["budget_seconds"] == budget]
        bars = ax.bar([x + delta for x in xs], values, .34, color=color, label=label)
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
    ax.axhline(10, color="#a14d23", ls="--", label="Admission ceiling (10%)")
    ax.set_xticks(xs, ["Medium 3 (train)", "Medium 5 (validation)", "Medium 6 (validation)"])
    ax.set_ylabel("Terminal MIP gap (%)")
    ax.set_ylim(0, 23)
    ax.legend(frameon=False, ncols=3, fontsize=8, loc="upper center")
    save(fig, "figure_source_gap")

    fig, axes = plt.subplots(2, 2, figsize=(8.0, 4.8), layout="constrained")
    keys = ["total_wall_time_seconds", "data_read_wall_time_seconds",
            "model_build_wall_time_seconds", "model_optimize_wall_time_seconds"]
    titles = ["Total", "Data reading", "Model construction", "Optimization"]
    labels = [f"M{r['source_instance_id'].rsplit('_', 1)[1]} / {r['budget_seconds']//3600}h" for r in rows]
    for ax, key, title in zip(axes.flat, keys, titles):
        ax.bar(range(6), [r[key] for r in rows], color=["#667c91", "#176b87"] * 3)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("Wall time (s)")
        ax.set_xticks(range(6), labels, rotation=35, ha="right", fontsize=8)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    save(fig, "figure_source_time_regions")
    outputs = [*sorted(figures.glob("figure_*.png")), *sorted(figures.glob("figure_*.svg")),
               tables / "table_source_rejection_outcomes.csv"]
    receipt = {"schema_version": 1, "license": "MIT",
               "source_sha256": hashlib.sha256((root / "results/source_evidence.json").read_bytes()).hexdigest(),
               "scope": "supplied_diagnostic_visualization_not_research_certification",
               "scientific_reporting_eligible": False,
               "outputs": [{"relative_path": p.relative_to(root).as_posix(),
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in outputs]}
    (tables / "rendered_assets.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
