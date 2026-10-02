"""Render manuscript tables and vector figures from frozen publication CSVs.

No training, inference, or optimization is performed. Derived illustrations
never replace the imported originals or their hashes.
SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from import_pr60_evidence import ARTIFACTS, MANIFEST, REPORT, verify_payload

ROOT = Path(__file__).resolve().parents[2] / "manuscript"
METHODS = ("unguided_control", "root_lp_matched_partial_start", "gnn_class_aware_partial_start")
LABELS = dict(zip(METHODS, ("Control", "Root-LP", "GNN")))
COLORS = dict(zip(METHODS, ("#526779", "#bd7b27", "#007f78")))


def rows(root: Path, name: str) -> list[dict[str, str]]:
    with (root / "results/current" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def table(path: Path, headings: list[str], values: list[list[str]], caption: str, identity: str) -> None:
    text = ["| " + " | ".join(headings) + " |", "| " + " | ".join([":--"] * len(headings)) + " |"]
    text += ["| " + " | ".join(record) + " |" for record in values]
    path.write_text("\n".join(text) + f"\n\n: {caption} {{#{identity}}}\n", encoding="utf-8", newline="\n")


def build(root: Path = ROOT) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    current = root / "results/current"
    verify_payload({name: (current / name).read_bytes() for name in (*ARTIFACTS, MANIFEST, REPORT)})
    figures, tables = root / "figures", root / "tables"
    figures.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    history = rows(root, "table_training_epoch_metrics.csv")
    if [int(r["epoch"]) for r in history] != list(range(1, 101)):
        raise ValueError("training history is not exactly 100 ordered epochs")
    best = min(history, key=lambda r: float(r["validation_weighted_bce"]))
    outcomes = rows(root, "table_solver_outcomes.csv")
    effects = rows(root, "table_paired_gap_effects.csv")
    predictive = rows(root, "table_predictive_metrics.csv")
    influence = rows(root, "table_heldout_influence_analysis.csv")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "cfl-cor-evidence-v1"})
    generated = []

    def save(fig, name):
        for suffix in ("pdf", "svg", "png"):
            path = figures / f"{name}.{suffix}"
            metadata = {"CreationDate": None, "ModDate": None} if suffix == "pdf" else ({"Date": None} if suffix == "svg" else {})
            fig.savefig(path, dpi=200, bbox_inches="tight", metadata=metadata)
            generated.append(path)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.set(xlim=(0, 10), ylim=(0, 4.6))
    ax.axis("off")
    box_rows = ((3.0, "OFFLINE", ("Original CFL models\nMINIMIZE + checked labels", "Bipartite graphs\nreal root-LP features", "GNN: 34 train / 10 val\n100 epochs; freeze model")),
                (0.9, "ONLINE", ("New medium model\nlabel-free graph + scores", "Class-aware partial start\nno domain restrictions", "Fresh Gurobi solve\ngap / time / feasibility")))
    for y, title, texts in box_rows:
        ax.text(.1, y+1.1, title, color="#007f78", weight="bold", fontsize=11)
        for index, label in enumerate(texts):
            x = .1 + index * 3.35
            ax.add_patch(FancyBboxPatch((x, y), 2.9, .88, boxstyle="round,pad=.06", facecolor="#edf5f7", edgecolor="#526779"))
            ax.text(x+1.45, y+.44, label, ha="center", va="center", fontsize=9)
            if index < 2:
                ax.annotate("", xy=(x+3.28, y+.44), xytext=(x+2.98, y+.44), arrowprops={"arrowstyle": "->", "color": "#526779"})
    ax.annotate("", xy=(4.9, 1.9), xytext=(8.1, 2.94), arrowprops={"arrowstyle": "->", "connectionstyle": "arc3,rad=-.12", "color": "#526779"})
    ax.text(6.5, 2.3, "Frozen checkpoint\nand validation-qualified policy", ha="center", va="center",
            fontsize=8, bbox={"facecolor": "white", "edgecolor": "none", "pad": 2})
    ax.text(.1, .25, "Test outcomes do not select model, threshold, support, or ordering.", fontsize=9)
    save(fig, "figure_pipeline")

    fig, ax = plt.subplots(figsize=(8, 3.0), layout="constrained")
    for key, label, color in (("training_weighted_bce", "Training", "#007f78"), ("validation_weighted_bce", "Validation", "#ad542f")):
        ax.plot([int(r["epoch"]) for r in history], [float(r[key]) for r in history], label=label, color=color, lw=1.4)
    ax.axvline(int(best["epoch"]), ls="--", color="#526779", lw=.9, label=f"Minimum validation BCE: epoch {best['epoch']}")
    ax.set(xlabel="Epoch", ylabel="Weighted BCE", xlim=(1, 100), ylim=(0, None))
    ax.legend(frameon=False, fontsize=8)
    save(fig, "figure_training_validation_loss")

    fig, axes = plt.subplots(1, 2, figsize=(8, 3.3), layout="constrained", sharex=True)
    for ax, partition in zip(axes, ("validation", "test")):
        selected = sorted((r for r in effects if r["partition"] == partition and r["method"] == METHODS[2]), key=lambda r: int(r["source_instance_id"].rsplit("_", 1)[1]))
        values = [100*float(r["terminal_gap_difference_guided_minus_control"]) for r in selected]
        ax.barh(range(len(selected)), values, color=["#007f78" if v<0 else "#ad542f" for v in values])
        ax.set_yticks(range(len(selected)), ["M"+r["source_instance_id"].rsplit("_", 1)[1] for r in selected])
        ax.invert_yaxis()
        ax.axvline(0, color="#526779", lw=.8)
        ax.set(xlabel="GNN minus control gap (percentage points)", title=partition.capitalize())
    save(fig, "figure_validation_test_gap_effects")

    tests = [r for r in outcomes if r["partition"] == "test"]
    parents = sorted({r["source_instance_id"] for r in tests}, key=lambda n: int(n.rsplit("_", 1)[1]))
    fig, axes = plt.subplots(2, 3, figsize=(8.5, 4.8), layout="constrained", sharex=True)
    for ax, parent in zip(axes.flat, parents):
        selected = {r["method"]: r for r in tests if r["source_instance_id"] == parent}
        for index, method in enumerate(METHODS):
            raw = selected[method]["first_observed_gap_le_0.1_seconds"]
            value = float(raw) if raw else 3600
            ax.barh(index, value, color=COLORS[method] if raw else "#dddddd", hatch=None if raw else "//")
            ax.text(value+45, index, f"{value:.0f}" if raw else "censored", va="center", fontsize=7)
        ax.set_yticks(range(3), [LABELS[m] for m in METHODS])
        ax.invert_yaxis()
        ax.set(title="Medium "+parent.rsplit("_", 1)[1], xlim=(0, 4550))
        ax.set_xlabel("First observed crossing (s)")
    save(fig, "figure_time_to_ten_percent_gap")

    table(tables / "current_predictive.qmd", ["Aggregation", "Precision", "Recall", "F1", "AP", "Brier", "ECE"],
          [["Variable-pooled" if r["scope"].startswith("micro") else "Parent-macro", *[f"{float(r[k]):.4f}" for k in ("precision", "recall", "f1_score", "average_precision", "brier_score", "expected_calibration_error")]] for r in predictive],
          "Predictive test metrics. AP is average precision, not trapezoidal PR-AUC; weighted scores are not assumed calibrated.", "tbl-predictive")
    effect_by_parent = {r["source_instance_id"]: r for r in effects if r["partition"] == "test" and r["method"] == METHODS[2]}
    values = []
    for parent in parents:
        pair = {r["method"]: r for r in tests if r["source_instance_id"] == parent}
        crossing = [f"{float(pair[m]['first_observed_gap_le_0.1_seconds']):.1f}" if pair[m]["first_observed_gap_le_0.1_seconds"] else "Censored" for m in (METHODS[0], METHODS[2])]
        values.append([parent.rsplit("_", 1)[1], f"{100*float(pair[METHODS[0]]['terminal_mip_gap_relative']):.3f}", f"{100*float(pair[METHODS[2]]['terminal_mip_gap_relative']):.3f}", f"{100*float(effect_by_parent[parent]['terminal_gap_difference_guided_minus_control']):+.3f}", *crossing])
    table(tables / "current_heldout.qmd", ["Medium", "Control gap (%)", "GNN gap (%)", "Difference (points)", "Control crossing (s)", "GNN crossing (s)"], values,
          "All six frozen optimization-test parents. Crossing refers to first observed gap at most 10 percent, not exact hitting time.", "tbl-heldout")
    table(tables / "current_influence.qmd", ["Excluded parents", "Included", "Wins", "Mean (points)", "Median (points)"],
          [[r["excluded_parent_ids"].replace("CFL_medium_instance_", "M").replace(";", ", ") or "None", r["included_parents"], r["gnn_gap_wins"], f"{100*float(r['mean_gap_difference_guided_minus_control']):.3f}", f"{100*float(r['median_gap_difference_guided_minus_control']):.3f}"] for r in influence],
          "Post-analysis influence diagnostics, not alternative test cohorts or policy selection.", "tbl-influence")
    values = []
    for parent in parents:
        pair = {r["method"]: r for r in tests if r["source_instance_id"] == parent}
        values.append([parent.rsplit("_", 1)[1], *[f"{float(pair[m]['model_optimize_wall_time_seconds']):.1f}" for m in METHODS],
                       f"{float(pair[METHODS[2]]['total_wall_time_seconds']):.1f}"])
    table(tables / "current_timing.qmd", ["Medium", "Control optimize (s)", "Root-LP optimize (s)", "GNN optimize (s)", "GNN worker total (s)"], values,
          "Measured worker times, excluding feature preparation, inference, and parent orchestration. Budget-limited runs do not establish speedups. The source summary does not include reading/build/preparation components; these remain available only in upstream receipts until separately transferred.", "tbl-times")
    for path in sorted(tables.glob("current_*.qmd")):
        generated.append(path)
    receipt = {"schema_version": 1, "source_contract_sha256": json.loads((current / REPORT).read_text())["contract_sha256"],
               "validation_minimum_epoch": int(best["epoch"]), "training_epochs": len(history),
               "source_files": {n: hashlib.sha256((current / n).read_bytes()).hexdigest() for n in (*ARTIFACTS, MANIFEST, REPORT)},
               "outputs": [{"relative_path": p.relative_to(root).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in generated],
               "research_execution_performed": False, "development_only": True, "scientific_reporting_eligible": False}
    (tables / "rendered_assets.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8", newline="\n")
    print("PR62_CURRENT_TABLES_AND_FIGURES_OK")


if __name__ == "__main__":
    build()
