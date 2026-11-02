"""Redraw frozen historical appendix records; never refit PCA or run research.

SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2] / "manuscript"
INPUT_NAMES = {
    "source_evidence", "confirmation_final", "graph_statistics", "graph_clustering",
    "graph_clustering_report", "training_epoch_metrics", "per_parent_metrics",
    "per_difficulty_metrics", "calibration_curve",
}
TABLE_NAMES = (
    "cohort", "rejections", "times", "structure", "descriptors", "instances",
    "quality", "pca", "clusters", "epochs", "predictive", "baselines", "distributions",
    "per_parent", "calibration",
)
FIGURE_NAMES = (
    "admission", "source_gap", "time_regions", "structure_pca", "distributions",
    "training", "prediction",
)
CLAIM_IDS = {
    "history39_cohort", "history39_pca", "history39_selection",
    "history39_targets", "history39_f1", "history39_rank",
}
DESCRIPTORS = (
    ("density", "Nonzeros divided by variables times rows"),
    ("discrete_fraction", "Fraction selected by the stored discrete-variable mask"),
    ("constraint_variable_ratio", "Rows divided by variables"),
    ("objective_log_mean", "Mean encoded objective channel"),
    ("objective_log_std", "Population SD of encoded objective channel"),
    ("rhs_log_mean", "Mean encoded right-hand-side channel"),
    ("rhs_log_std", "Population SD of encoded right-hand-side channel"),
    ("coefficient_log_mean", "Mean encoded coefficient-edge channel"),
    ("coefficient_log_std", "Population SD of encoded coefficient-edge channel"),
    ("lower_bound_log_mean", "Mean encoded lower-bound channel"),
    ("upper_bound_log_mean", "Mean encoded upper-bound channel"),
    ("fixed_domain_fraction", "Encoded bounds equal within absolute tolerance 1e-9"),
    ("variable_degree_std", "Population SD of variable-node degrees"),
    ("constraint_degree_std", "Population SD of constraint-node degrees"),
    ("root_lp_mean", "Mean stored root-LP channel over variables"),
    ("root_lp_std", "Population SD of that root-LP channel"),
    ("binary_lp_fractionality", "Mean distance to nearest integer over the discrete mask"),
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_sources(root: Path = ROOT) -> tuple[dict, dict]:
    manifest = json.loads((root / "supplement/historical-appendix-manifest.json").read_text(encoding="utf-8"))
    if (manifest["schema_version"] != 1
            or manifest["kind"] != "historical_appendix_restoration_not_new_experiment"
            or any(manifest[key] is not False for key in (
                "current_cohort_replaced", "research_execution_performed",
                "projection_refitted", "learned_embeddings_extracted"))
            or {s["id"] for s in manifest["sources"]} != INPUT_NAMES
            or len(manifest["sources"]) != len(INPUT_NAMES)
            or {c["id"] for c in manifest["claims"]} != CLAIM_IDS):
        raise ValueError("historical_manifest_scope")
    sources = {}
    for record in manifest["sources"]:
        suffix = ".csv" if record["format"] == "csv" else ".json"
        expected = "manuscript/results/" + record["id"] + suffix
        if record["path"] != expected:
            raise ValueError("historical_source_path")
        path = root / "results" / (record["id"] + suffix)
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("historical_source_path")
        raw = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if digest(raw) != record["sha256"] or blob != record["git_blob_sha1"]:
            raise ValueError("historical_source_hash:" + record["id"])
        sources[record["id"]] = (
            list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))
            if record["format"] == "csv" else json.loads(raw)
        )
    stats, points = sources["graph_statistics"], sources["graph_clustering"]
    final, projection = sources["confirmation_final"], sources["graph_clustering_report"]
    cohort = {"parents": 39, "easy": 30, "medium": 9, "hard": 0,
              "train": 23, "validation": 8, "test": 8}
    if (final["cohort"] != cohort or len(stats) != 39 or len(points) != 39
            or Counter(r["difficulty"] for r in stats) != {"easy": 30, "medium": 9}
            or len({r["sample_id"] for r in stats}) != 39
            or {r["sample_id"] for r in stats} != {r["sample_id"] for r in points}
            or any(r["sample_id"] != r["source_instance_id"] for r in stats)
            or any(r["right_censored"] != "" for r in stats)):
        raise ValueError("historical_population_or_missing_censoring")
    method = projection["methodology"]
    if (projection["summary"]["graphs"] != 39
            or method["features"] != [key for key, _ in DESCRIPTORS]
            or method["outcomes_used_as_projection_inputs"] is not False
            or method["umap_status"] != "not_requested"
            or projection["eligibility"]["inferential_cluster_claims_allowed"] is not False):
        raise ValueError("historical_projection_scope")
    for row in points:
        if int(row["cluster_id"]) not in (0, 1, 2) or any(
                not math.isfinite(float(row[key])) for key in ("pca_component_1", "pca_component_2")):
            raise ValueError("historical_projection_coordinates")
    epochs = sources["training_epoch_metrics"]
    parents, bins = sources["per_parent_metrics"], sources["calibration_curve"]
    target_count = final["evaluation"]["aggregate_metrics"]["n_targets"]
    if ([int(r["epoch"]) for r in epochs] != list(range(1, 101))
            or len(parents) != 8 or len(bins) != 10
            or sum(int(r["n_targets"]) for r in parents) != target_count
            or sum(int(r["count"]) for r in bins) != target_count
            or len({r["parent_instance_id"] for r in parents}) != 8):
        raise ValueError("historical_predictive_population")
    return manifest, sources


def expected_claim(claim: dict, sources: dict) -> str:
    values = {}
    for name, metric in claim["metrics"].items():
        value = sources[metric["source"]]
        for part in metric["pointer"].lstrip("/").split("/"):
            value = value[int(part)] if isinstance(value, list) else value[part]
        if isinstance(value, bool) or not math.isfinite(float(value)):
            raise ValueError("historical_metric")
        spec, scale = metric["format"], metric.get("scale", 1)
        if spec not in {".0f", ".2f", ".4f", ",.0f"} or scale not in {1, 100}:
            raise ValueError("historical_metric_format")
        values[name] = format(float(value) * scale, spec)
    return claim["template"].format(**values)


def check_source(root: Path = ROOT) -> list[str]:
    try:
        manifest, sources = load_sources(root)
        text = (root / "supplement/extended-results.md").read_text(encoding="utf-8")
        failures = []
        for claim in manifest["claims"]:
            heading = re.search(r"(?m)^#{1,6} [^\n]*\{#" + re.escape(claim["section"]) + r"\}", text)
            if heading is None:
                raise ValueError("historical_claim_section")
            remaining = text[heading.end():]
            following = re.search(r"(?m)^#{1,6} ", remaining)
            section = remaining[:following.start()] if following else remaining
            if " ".join(expected_claim(claim, sources).split()) not in " ".join(section.split()):
                failures.append("historical_claim_mismatch:" + claim["id"])
        return failures
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, IndexError) as error:
        return ["historical_appendix_invalid:" + str(error)]


def check_outputs(root: Path = ROOT, rendered: Path | None = None) -> list[str]:
    target = rendered if rendered is not None else root
    try:
        receipt = json.loads((target / "tables/historical_appendix_assets.json").read_text(encoding="utf-8"))
        if (receipt["research_execution_performed"] is not False
                or receipt["projection_refitted"] is not False
                or receipt["learned_embeddings_extracted"] is not False
                or receipt["inputs"] != json.loads((root / "supplement/historical-appendix-manifest.json").read_text())["sources"]):
            return ["historical_asset_scope"]
        wanted = {"tables/history39_" + n + ".qmd" for n in TABLE_NAMES}
        wanted |= {"figures/figure_history39_" + n + "." + ext
                   for n in FIGURE_NAMES for ext in ("pdf", "svg", "png")}
        if {item["path"] for item in receipt["outputs"]} != wanted:
            return ["historical_asset_coverage"]
        for item in receipt["outputs"]:
            path = target / item["path"]
            if (path.is_symlink() or not path.resolve().is_relative_to(target.resolve())
                    or digest(path.read_bytes()) != item["sha256"]):
                return ["historical_asset_hash:" + item["path"]]
        return []
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return ["historical_assets_invalid"]


def label(row: dict, key: str = "source_instance_id") -> str:
    identity = row[key]
    return ("E" if "_easy_" in identity else "M") + identity.rsplit("_", 1)[1]


def sorted_instances(rows: list[dict], key: str = "source_instance_id") -> list[dict]:
    return sorted(rows, key=lambda r: ("_medium_" in r[key], int(r[key].rsplit("_", 1)[1])))


def build(root: Path = ROOT) -> None:
    errors = check_source(root)
    if errors:
        raise ValueError(errors)
    manifest, data = load_sources(root)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter

    figures, tables = root / "figures", root / "tables"
    figures.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    outputs = []
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "cfl-history39-static-appendix-v1"})

    def save(fig, stem):
        for extension in ("pdf", "svg", "png"):
            path = figures / ("figure_history39_" + stem + "." + extension)
            metadata = ({"CreationDate": None, "ModDate": None} if extension == "pdf"
                        else {"Date": None} if extension == "svg" else {})
            fig.savefig(path, dpi=220, bbox_inches="tight", metadata=metadata)
            outputs.append(path)
        plt.close(fig)

    def table(stem, headers, rows, caption, note=""):
        text = "| " + " | ".join(headers) + " |\n"
        text += "|" + "|".join(":--" for _ in headers) + "|\n"
        text += "".join("| " + " | ".join(str(x) for x in row) + " |\n" for row in rows)
        text += "\n: " + caption + " {#tbl-history39-" + stem.replace("_", "-") + "}\n"
        if note:
            text += "\n" + note + "\n"
        path = tables / ("history39_" + stem + ".qmd")
        path.write_text(text, encoding="utf-8", newline="\n")
        outputs.append(path)

    original, final = data["source_evidence"], data["confirmation_final"]
    stats = sorted_instances(data["graph_statistics"])
    points = sorted_instances(data["graph_clustering"])
    epochs = data["training_epoch_metrics"]
    parents = sorted_instances(data["per_parent_metrics"], "parent_instance_id")
    bins = data["calibration_curve"]
    before, after = original["cohort"]["initial_roles"], original["cohort"]["revised_roles"]
    table("cohort", ["Role", "Planned", "Excluded", "Admitted"],
          [(r.title(), before[r], before[r] - after[r], after[r]) for r in ("train", "validation", "test")]
          + [("Total", 42, 3, 39)], "Admission and original-instance roles in the earlier development cohort.")
    rejected = [{**run, "source_instance_id": parent["source_instance_id"], "role": parent["role"]}
                for parent in original["rejected"] for run in parent["repairs"]]
    table("rejections", ["Instance", "Role", "Budget (s)", "Primal", "Dual", "Gap (%)", "Censored"],
          [(label(r), r["role"], r["budget_seconds"], f'{r["solution_objective"]:.5f}',
            f'{r["best_bound"]:.5f}', f'{100*r["mip_gap_relative"]:.4f}',
            "Yes" if r["right_censored"] else "No") for r in rejected],
          "All six archived acquisition attempts for excluded medium instances.")
    clocks = ("data_read_wall_time_seconds", "model_build_wall_time_seconds",
              "model_optimize_wall_time_seconds", "total_wall_time_seconds")
    table("times", ["Instance", "Budget (s)", "Read (s)", "Build (s)", "Optimize (s)", "Total (s)"],
          [(label(r), r["budget_seconds"], *(f'{r["time_regions"][k]:.3f}' for k in clocks)) for r in rejected],
          "Four observed wall-time regions in the historical acquisition records.")
    summary_rows = []
    for difficulty in ("easy", "medium"):
        group = [r for r in stats if r["difficulty"] == difficulty]
        summary_rows.append((difficulty.title(), len(group), f'{int(group[0]["variables"]):,}',
                             f'{int(group[0]["constraints"]):,}', f'{int(group[0]["nonzeros"]):,}',
                             f'{100*float(group[0]["density"]):.5f}'))
        if any((r["variables"], r["constraints"], r["nonzeros"]) !=
               (group[0]["variables"], group[0]["constraints"], group[0]["nonzeros"]) for r in group):
            raise ValueError("historical_size_not_constant_within_difficulty")
    table("structure", ["Difficulty", "Instances", "Variables", "Rows", "Nonzeros", "Density (%)"],
          summary_rows, "Original graph topology in the archived 39-instance cohort.",
          "Sizes are constant within each difficulty class; coefficients and labels need not be.")
    def quantile(values, fraction):
        values = sorted(values)
        position = (len(values)-1)*fraction
        lo = int(position)
        hi = min(lo+1, len(values)-1)
        return values[lo] + (values[hi]-values[lo])*(position-lo)
    distribution_rows = []
    for difficulty in ("easy", "medium"):
        group = [r for r in stats if r["difficulty"] == difficulty]
        for key, title, factor in (
            ("discrete_fraction", "Discrete (%)", 100),
            ("positive_label_fraction", "Positive (%)", 100),
            ("mip_gap_relative", "Source gap (%)", 100),
            ("execution_time_seconds", "Source time (s)", 1),
            ("root_lp_nonzero_fraction", "Root nonzero (%)", 100),
        ):
            values = [factor*float(r[key]) for r in group]
            distribution_rows.append((difficulty.title(), title,
                                      *(f"{quantile(values, q):.5f}" for q in (0, .25, .5, .75, 1))))
    table("distributions", ["Difficulty", "Descriptor", "Min", "Q1", "Median", "Q3", "Max"],
          distribution_rows, "Instance-level descriptive distributions in the earlier cohort.",
          "Quartiles use linear interpolation at (N-1)q. No inferential intervals are calculated. "
          "Source time is not time to optimality, and censoring remains unavailable.")
    table("descriptors", ["Stored descriptor", "Definition before standardization"],
          [(key.replace("_", r"\_"), meaning) for key, meaning in DESCRIPTORS],
          "All 17 inputs to the archived descriptor PCA.",
          "Channel moments are computed from encoded features, not untransformed coefficients. "
          "SD means population standard deviation. Outcomes and label prevalence are excluded.")
    table("instances", ["Instance", "Variables", "Rows", "Nonzeros", "Discrete (%)", "Positive (%)"],
          [(label(r), f'{int(r["variables"]):,}', r["constraints"], f'{int(r["nonzeros"]):,}',
            f'{100*float(r["discrete_fraction"]):.4f}', f'{100*float(r["positive_label_fraction"]):.5f}') for r in stats],
          "Complete original-instance graph inventory, with archived domain and label fractions.",
          "Positive prevalence uses labels selected by the graph's stored discrete-variable mask.")
    table("quality", ["Instance", "Source gap (%)", "Source time (s)", "Root nonzero (%)", "Censoring"],
          [(label(r), f'{100*float(r["mip_gap_relative"]):.5f}', f'{float(r["execution_time_seconds"]):.3f}',
            f'{100*float(r["root_lp_nonzero_fraction"]):.5f}', "Unavailable") for r in stats],
          "Historical source quality, execution and root-vector descriptors for all 39 instances.",
          "Every censoring field is missing. Source time is not an observed time to optimality.")
    table("pca", ["Instance", "Difficulty", "PC1", "PC2", "Group"],
          [(label(r), r["difficulty"], f'{float(r["pca_component_1"]):.6f}',
            f'{float(r["pca_component_2"]):.6f}', int(r["cluster_id"])+1) for r in points],
          "All archived PCA coordinates and fixed descriptive group assignments.",
          "Group labels are display identifiers, not learned difficulty classes.")
    counts = Counter((int(r["cluster_id"]), r["difficulty"]) for r in points)
    table("clusters", ["Group", "Easy", "Medium", "Total"],
          [(c+1, counts[c, "easy"], counts[c, "medium"], counts[c, "easy"]+counts[c, "medium"]) for c in range(3)],
          "Composition of the three archived descriptive groups.")
    selected = min(epochs, key=lambda r: float(r["validation_loss"]))
    table("epochs", ["Epoch", "Training weighted BCE", "Validation weighted BCE"],
          [(r["epoch"], f'{float(r["train_loss"]):.6f}', f'{float(r["validation_loss"]):.6f}')
           for r in (epochs[0], selected, epochs[-1])],
          "First, minimum-validation and final epochs in the earlier training history.")
    ev = final["evaluation"]
    summaries = [("Pooled", 8, ev["aggregate_metrics"]), ("Instance macro", 8, ev["parent_macro_classification"])]
    summaries += [(r["difficulty"].title()+" pooled", 6 if r["difficulty"]=="easy" else 2, r)
                  for r in data["per_difficulty_metrics"]]
    table("predictive", ["Summary", "Instances", "Precision", "Recall", "F1"],
          [(name, n, *(f'{float(row[k]):.4f}' for k in ("precision", "recall", "f1_score")))
           for name, n, row in summaries], "Archived classification summaries for the earlier eight-instance test.")
    score_rows = [("GNN", ev["score_diagnostics"]),
                  ("Clipped root LP", ev["baseline_diagnostics"]["root_lp_clipped_to_binary_domain"]),
                  ("Constant zero", ev["baseline_diagnostics"]["constant_zero"])]
    table("baselines", ["Score source", "AP", "Unweighted BCE", "Brier", "ECE"],
          [(name, *(f'{float(row[k]):.5f}' for k in ("average_precision", "binary_cross_entropy",
                                                   "brier_score", "expected_calibration_error")))
           for name, row in score_rows], "Archived score diagnostics and reference baselines.",
          f'Recorded scalar ROC-AUC is {ev["roc_auc"]:.6f}; trapezoidal PR-AUC is '
          f'{ev["precision_recall_auc"]:.6f}. AP is a different summary; full ROC/PR coordinates are unavailable.')
    table("per_parent", ["Instance", "Targets", "Positives", "TP", "FP", "FN", "F1"],
          [(label(r, "parent_instance_id"), f'{int(r["n_targets"]):,}', f'{int(r["n_positive"]):,}',
            r["tp"], r["fp"], r["fn"], f'{float(r["f1_score"]):.4f}') for r in parents],
          "Every earlier predictive-test instance and its archived classification counts.",
          "TN equals targets minus TP, FP and FN; the source CSV retains TN and all original metrics.")
    table("calibration", ["Bin", "Score interval", "Targets", "Mean score", "Positive fraction"],
          [(r["bin_index"], f'{float(r["lower_bound"]):.1f}-{float(r["upper_bound"]):.1f}',
            f'{int(r["count"]):,}', f'{float(r["mean_probability"]):.6f}',
            f'{float(r["positive_fraction"]):.8f}') for r in bins],
          "All ten archived score bins for the earlier predictive test.")

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.6), layout="constrained")
    for ax, labels, old, new in (
        (axes[0], ("Easy", "Medium", "Hard"), (30, 12, 0), (30, 9, 0)),
        (axes[1], ("Train", "Validation", "Test"), (24, 10, 8), (23, 8, 8)),
    ):
        for offset, values, color, legend in ((-.19, old, ".72", "Planned"), (.19, new, ".25", "Admitted")):
            bars = ax.bar([i+offset for i in range(3)], values, .36, color=color, label=legend)
            ax.bar_label(bars, padding=2, fontsize=8)
        ax.set_xticks(range(3), labels)
        ax.set(ylabel="Original instances", ylim=(0, 35))
    axes[0].legend(frameon=False, fontsize=8)
    save(fig, "admission")

    fig, ax = plt.subplots(figsize=(7.1, 2.5), layout="constrained")
    for offset, budget, color in ((-.19, 3600, ".7"), (.19, 14400, ".25")):
        values = [100*r["mip_gap_relative"] for r in rejected if r["budget_seconds"] == budget]
        bars = ax.bar([i+offset for i in range(3)], values, .36, color=color, label=f"{budget:,} s")
        ax.bar_label(bars, fmt="%.2f", padding=2, fontsize=8)
    ax.axhline(10, color="black", linestyle="--", label="10% admission ceiling")
    ax.set_xticks(range(3), ("M3 (train)", "M5 (validation)", "M6 (validation)"))
    ax.set(ylabel="Reported terminal gap (%)", ylim=(0, 23))
    ax.legend(frameon=False, ncols=3, fontsize=8, loc="upper center")
    save(fig, "source_gap")

    fig, axes = plt.subplots(2, 2, figsize=(7.4, 4.3), layout="constrained")
    for ax, key, title in zip(axes.flat, clocks, ("Data reading", "Model construction", "Optimization", "Total")):
        ax.bar(range(6), [r["time_regions"][key] for r in rejected], color=[".7", ".25"]*3)
        ax.set_xticks(range(6), [label(r)+"/"+str(r["budget_seconds"]//3600)+"h" for r in rejected],
                      rotation=30, fontsize=7)
        ax.set(title=title, ylabel="Wall time (s)")
        ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    save(fig, "time_regions")

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3), layout="constrained")
    for difficulty, color in (("easy", ".6"), ("medium", ".15")):
        group = [r for r in stats if r["difficulty"] == difficulty]
        axes[0].scatter([float(r["variables"])/1e6 for r in group],
                        [float(r["nonzeros"])/1e6 for r in group], color=color, label=difficulty.title(), s=32)
        for cluster, marker in enumerate(("o", "s", "^")):
            group = [r for r in points if r["difficulty"] == difficulty and int(r["cluster_id"]) == cluster]
            if group:
                axes[1].scatter([float(r["pca_component_1"]) for r in group],
                                [float(r["pca_component_2"]) for r in group],
                                color=color, marker=marker, s=28, label=difficulty.title()+f", group {cluster+1}")
    axes[0].set(xlabel="Variables (millions)", ylabel="Nonzeros (millions)")
    axes[1].set(xlabel="PC1 (85.78%)", ylabel="PC2 (7.74%)")
    for ax in axes:
        ax.legend(frameon=False, fontsize=7)
    save(fig, "structure_pca")

    fig, axes = plt.subplots(2, 2, figsize=(7.4, 4.6), layout="constrained")
    for ax, key, factor, title in zip(axes.flat,
        ("density", "discrete_fraction", "positive_label_fraction", "execution_time_seconds"),
        (100, 100, 100, 1), ("Density (%)", "Discrete variables (%)", "Positive labels (%)", "Source time (s)")):
        values = [[factor*float(r[key]) for r in stats if r["difficulty"] == d] for d in ("easy", "medium")]
        ax.boxplot(values, tick_labels=("Easy", "Medium"), showfliers=False,
                   medianprops={"color": "black"}, boxprops={"color": ".3"})
        for i, group in enumerate(values):
            ax.scatter([i+1]*len(group), group, color=".35", s=12, alpha=.6)
        ax.set_ylabel(title)
    save(fig, "distributions")

    fig, ax = plt.subplots(figsize=(7.2, 2.9), layout="constrained")
    for key, name, color, style in (("train_loss", "Training", ".2", "-"),
                                    ("validation_loss", "Validation", ".55", "--")):
        ax.plot([int(r["epoch"]) for r in epochs], [float(r[key]) for r in epochs],
                color=color, linestyle=style, linewidth=1.1, label=name)
    ax.axvline(int(selected["epoch"]), color=".3", linestyle=":", label="Minimum validation: epoch "+selected["epoch"])
    ax.set(xlabel="Epoch", ylabel="Weighted BCE", xlim=(1, 100), ylim=(0, None))
    ax.legend(frameon=False, fontsize=8)
    save(fig, "training")

    fig, axes = plt.subplots(1, 3, figsize=(8.2, 2.7), layout="constrained")
    axes[0].bar(range(8), [float(r["f1_score"]) for r in parents], color=".35")
    axes[0].set_xticks(range(8), [label(r, "parent_instance_id") for r in parents], rotation=40, fontsize=7)
    axes[0].set(ylabel="F1", ylim=(0, 1), xlabel="Earlier test instance")
    axes[1].plot([0, 1], [0, 1], color=".7", linestyle="--")
    axes[1].plot([float(r["mean_probability"]) for r in bins],
                 [float(r["positive_fraction"]) for r in bins], "o-", color=".2", markersize=3)
    axes[1].set(xlabel="Mean score", ylabel="Observed positive fraction", xlim=(0, 1), ylim=(0, 1))
    axes[2].bar(range(10), [int(r["count"]) for r in bins], color=".35")
    axes[2].set(xlabel="Score bin", ylabel="Target count", yscale="log")
    axes[2].set_xticks((0, 3, 6, 9))
    save(fig, "prediction")

    receipt = {"schema_version": 1, "scope": "static_historical_appendix_restoration",
               "research_execution_performed": False, "projection_refitted": False,
               "learned_embeddings_extracted": False, "inputs": manifest["sources"],
               "outputs": [{"path": p.relative_to(root).as_posix(), "sha256": digest(p.read_bytes())}
                           for p in outputs]}
    (tables / "historical_appendix_assets.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    build()
