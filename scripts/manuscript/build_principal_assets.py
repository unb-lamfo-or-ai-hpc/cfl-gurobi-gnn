"""Render existing seed42 CPU evidence; never train, infer, optimize or submit.

SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUTS = (
    "docs/evidence/methodology-20261019/seed42_main.csv",
    "docs/evidence/methodology-20261019/seed42_cpu_scaling.csv",
    "docs/evidence/pr86/final-210/paired_uncertainty.csv",
)
METHODS = {"M0": "B", "M1": "R", "M2": "G"}
CAPS = (1, 2, 4, 8, 16)
EASY = ("F0", "F3", "F6", "F14", "F27", "F29")
MEDIUM = ("M0", "M4", "M7", "M12")


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def fixed_inputs(repository=ROOT):
    manifest = json.loads(
        (repository / "manuscript/supplement/claim-evidence.json").read_text(
            encoding="utf-8"
        )
    )
    records = {record["path"]: record for record in manifest["sources"]}
    for name in INPUTS:
        raw = (repository / name).read_bytes()
        if name not in records or hashlib.sha256(raw).hexdigest() != records[name]["sha256"]:
            raise ValueError("principal input hash mismatch: " + name)
    rows = read_csv(repository / INPUTS[0])
    identities = {(r["alias"], int(r["threads"]), r["method"], r["seed"]) for r in rows}
    expected = {(p, c, m, "42") for p in EASY + MEDIUM for c in CAPS for m in METHODS}
    if len(rows) != 150 or identities != expected:
        raise ValueError("principal population or cell identity mismatch")
    if any(r["right_censored"] != "False" for r in rows if r["alias"] in EASY):
        raise ValueError("easy target no longer attained")
    return rows, read_csv(repository / INPUTS[1]), read_csv(repository / INPUTS[2])


def summary_row(summaries, cap, numerator, denominator, metric):
    matches = [r for r in summaries if
               r["seed_scope"] == "seed42" and int(r["threads"]) == cap
               and r["numerator"] == numerator and r["denominator"] == denominator
               and r["metric"] == metric and r["parents"] == "6"]
    if len(matches) != 1:
        raise ValueError("ambiguous principal aggregate")
    return matches[0]


def write_table(path, columns, values, caption, identity, note):
    lines = ["| " + " | ".join(columns) + " |",
             "| " + " | ".join([":--"] * len(columns)) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in values]
    path.write_text("\n".join(lines) + f"\n\n: {caption} {{#{identity}}}\n\n{note}\n",
                    encoding="utf-8", newline="\n")


def build(repository=ROOT):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows, scaling, summaries = fixed_inputs(repository)
    root = repository / "manuscript"
    figures, tables = root / "figures", root / "tables"
    figures.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    outputs = []
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "svg.hashsalt": "cfl-pr93-reader-results-v1",
    })

    def save(fig, name):
        for suffix in ("pdf", "svg", "png"):
            path = figures / f"{name}.{suffix}"
            metadata = {"CreationDate": None, "ModDate": None} if suffix == "pdf" else (
                {"Date": None} if suffix == "svg" else {}
            )
            fig.savefig(path, dpi=180, bbox_inches="tight", metadata=metadata)
            outputs.append(path)
        plt.close(fig)

    indexed = {(r["alias"], int(r["threads"]), r["method"]): r for r in rows}
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.4), layout="constrained")
    for comparison, denominator, color, marker, delta in (
        ("G/B", "M0", "#222222", "o", -.12),
        ("G/R", "M1", "#777777", "s", .12),
    ):
        for i, cap in enumerate(CAPS):
            for j, parent in enumerate(EASY):
                g = float(indexed[parent, cap, "M2"]["solver_seconds"])
                control = float(indexed[parent, cap, denominator]["solver_seconds"])
                axes[0].plot(i + delta + (j - 2.5) * .025, g / control,
                             marker, color=color, alpha=.28, markersize=3)
        means = [float(summary_row(summaries, c, "M2", denominator, "solver_seconds")[
            "geometric_mean_ratio"]) for c in CAPS]
        axes[0].plot([i + delta for i in range(5)], means, marker=marker,
                     color=color, linewidth=1.4, label=comparison + " geometric mean")
    axes[0].axhline(1, color="#999999", linestyle=":", linewidth=1)
    axes[0].set_xticks(range(5), CAPS)
    axes[0].set(xlabel="Thread cap", ylabel="Solver-time ratio (lower favours G)",
                yscale="log", title="Between-method effects")
    axes[0].legend(fontsize=8, frameon=False)
    for method, color, marker in (
        ("M0", "#aaaaaa", "o"), ("M1", "#777777", "s"), ("M2", "#222222", "^")
    ):
        means = []
        for cap in CAPS:
            selected = [float(r["same_method_cpu_speedup"]) for r in scaling
                        if r["alias"] in EASY and r["method"] == method
                        and int(r["threads"]) == cap and r["seed"] == "42"
                        and r["eligible_common_terminal_target"] == "True"]
            if len(selected) != 6:
                raise ValueError("scaling population drift")
            means.append(math.exp(sum(map(math.log, selected)) / 6))
        axes[1].plot(range(5), means, color=color, marker=marker,
                     label=METHODS[method], linewidth=1.4)
    axes[1].axhline(1, color="#999999", linestyle=":", linewidth=1)
    axes[1].set_xticks(range(5), CAPS)
    axes[1].set(xlabel="Thread cap", ylabel="Own one-thread time / current time",
                title="Within-method CPU scaling")
    axes[1].legend(title="Method", fontsize=8, frameon=False)
    save(fig, "figure_principal_time_scaling")

    fig, axes = plt.subplots(2, 2, figsize=(7.4, 5.0), layout="constrained")
    for ax, parent in zip(axes.flat, MEDIUM):
        restricted = parent in {"M4", "M12"}
        if restricted:
            ax.set_facecolor("#f1f1f1")
        for method, color, marker in (
            ("M0", "#aaaaaa", "o"), ("M1", "#777777", "s"), ("M2", "#222222", "^")
        ):
            group = [indexed[parent, c, method] for c in CAPS]
            values = [100 * float(r["gap_fraction"]) for r in group]
            ax.plot(range(5), values, color=color, linewidth=1, label=METHODS[method])
            for i, (r, value) in enumerate(zip(group, values)):
                ax.plot(i, value, marker=marker, color=color, markersize=5,
                        markerfacecolor="white" if r["right_censored"] == "True" else color)
        ax.set_xticks(range(5), CAPS)
        maximum_gap = max(100 * float(indexed[parent, c, m]["gap_fraction"])
                          for c in CAPS for m in METHODS)
        ax.set_ylim(bottom=-max(.01, maximum_gap * .025))
        ax.set(title=parent + (" — numerical restrictions" if restricted else ""),
               xlabel="Thread cap", ylabel="Terminal reported gap (%)")
        ax.tick_params(labelsize=9)
    axes[0, 0].legend(title="Method", fontsize=8, frameon=False)
    save(fig, "figure_principal_medium_gap")

    values = []
    for cap in CAPS:
        ratios = [float(summary_row(summaries, cap, n, d, "solver_seconds")[
            "geometric_mean_ratio"]) for n, d in (("M1", "M0"), ("M2", "M0"), ("M2", "M1"))]
        values.append([str(cap)] + [f"{v:.4f}" for v in ratios])
    write_table(tables / "principal_ratios.qmd",
                ["Threads", "R/B time", "G/B time", "G/R time"], values,
                "Geometric-mean solver-time ratios on six easy instances, seed42.",
                "tbl-principal-ratios",
                "Each ratio gives equal weight to the six original instances. Lower values "
                "favour the numerator. All pairs attain the reported terminal target under "
                "tolerances; these are descriptive ratios, not exact certificates or "
                "confirmatory significance tests.")
    scopes = (
        ("Solver Runtime", "solver_seconds"),
        ("Execution + delimited cold preparation", "scoped_cold_cost_scenario_seconds"),
        ("Execution + broader cold allocation", "allocated_cold_scenario_seconds"),
        ("Execution + delimited preparation / 7 uses", "scoped_amortized_cost_scenario_seconds"),
        ("Execution + broader preparation / 7 uses", "allocated_amortized_scenario_seconds"),
    )
    values = [[label, f"{float(summary_row(summaries, 16, 'M2', 'M0', metric)['geometric_mean_ratio']):.4f}"]
              for label, metric in scopes]
    write_table(tables / "principal_costs.qmd", ["Accounting boundary", "G/B ratio"],
                values, "Scope-dependent time ratios: six easy instances, sixteen threads, seed42.",
                "tbl-principal-costs",
                "Execution is the supervised attempt interval. Preparation scopes and "
                "seven-use allocations are recorded scenarios, not independently measured "
                "complete applications. Lower ratios favour G.")
    values = []
    for parent in EASY:
        for cap in CAPS:
            values.append([parent, str(cap)] + [
                f"{float(indexed[parent, cap, m]['solver_seconds']):.3f}" for m in METHODS
            ])
    write_table(tables / "principal_easy_times.qmd",
                ["Instance", "Threads", "B (s)", "R (s)", "G (s)"], values,
                "Solver runtimes for the principal easy-instance conditions.",
                "tbl-easy-times",
                "All rows attain the reported terminal target under the stated tolerances. "
                "Times exclude neural preparation and supervised-attempt overhead.")
    values = []
    for parent in MEDIUM:
        for cap in CAPS:
            for method in METHODS:
                r = indexed[parent, cap, method]
                def number(field):
                    v = float(r[field])
                    return f"{v:.6f}" if math.isfinite(v) else "Unavailable"
                values.append([
                    parent + ("*" if parent in {"M4", "M12"} else ""), str(cap),
                    METHODS[method], number("primal"), number("dual"),
                    f"{100 * float(r['gap_fraction']):.4f}",
                    "Censored" if r["right_censored"] == "True" else "Reported target",
                ])
    write_table(tables / "principal_medium_quality.qmd",
                ["Instance", "Threads", "Method", "Primal", "Dual", "Gap (%)", "Target"], values,
                "Terminal reported medium-instance quality and target disposition.",
                "tbl-medium-quality",
                "An asterisk marks M4/M12's numerical restrictions. Target disposition "
                "is distinct from an earlier threshold crossing; Reported target does not "
                "mean exact optimality. Raw values and actual follow-up remain in the "
                "versioned source table.")
    outputs += [tables / name for name in (
        "principal_ratios.qmd", "principal_costs.qmd",
        "principal_easy_times.qmd", "principal_medium_quality.qmd",
    )]
    receipt = {
        "schema_version": 1, "scope": "existing_seed42_publication_assets",
        "source_files": {name: hashlib.sha256((repository / name).read_bytes()).hexdigest()
                         for name in INPUTS},
        "experimental_units": 10, "principal_rows": 150,
        "research_execution_performed": False, "scientific_reporting_eligible": False,
        "outputs": [{"relative_path": p.relative_to(root).as_posix(),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in outputs],
    }
    (tables / "principal_assets.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print("PR93_EXISTING_CPU_ASSETS_OK")


if __name__ == "__main__":
    build()
