"""Reproduce the PR80 independent review and descriptive outputs, without HPC.

Tables use stdlib CSV to preserve the repository's machine-readable convention.
Optional static scientific figures require matplotlib; never imported by review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path

import audit_sprint_c_numeric as audit
from verify_sprint_c_artifacts import SELECTION

ROOT = Path(__file__).resolve().parents[2]
RETURN_SHA = "20ed978d7e6a9c0ccc6a284f15cf54c9df6940a0bc5985c1b836db5f69362f60"
SOURCE = "1faa3491b0b5edcd07b4d6a6043bd7cc8b262f22"
MEMBERS = {
    "descriptive_statistics.csv",
    "parent_statistics.csv",
    "numeric/numeric.json",
    "inference.json",
    "integrated.json",
    "runtime.json",
}
FIELDS = (
    "variables",
    "constraints",
    "nonzeros",
    "density",
    "binary_variables",
    "integer_variables",
    "continuous_variables",
    "discrete_targets",
    "positive_discrete_targets",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(left, right):
    return (
        math.isfinite(left)
        and math.isfinite(right)
        and math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-12)
    )


def alias(parent):
    return ("F" if "_easy_" in parent else "M") + parent.rsplit("_", 1)[1]


def quantile(values, q):
    values = sorted(values)
    position = (len(values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def read_package(path):
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == RETURN_SHA, "return hash")
    package = audit.metadata.strict_json(raw)
    require(set(package["members"]) == MEMBERS, "member set")
    for name, member in package["members"].items():
        require(
            audit.metadata.digest(member["text"].encode()) == member["sha256"], name
        )
    return package


def validate(package):
    """Reconcile reports independently; no re-reading private model/prediction bytes."""
    members = package["members"]

    def parse(name):
        return audit.metadata.strict_json(members[name]["text"])

    numeric, integrated, inference = (
        parse(k) for k in ("numeric/numeric.json", "integrated.json", "inference.json")
    )
    require(package["job_id"] == integrated["job_id"] == "3503", "job identity")
    require(package["raw_logs_included"] is False, "raw logs")
    require(integrated["source_commit"] == SOURCE, "source")
    require(integrated["state"] == "complete_pending_independent_review", "state")
    require(integrated["inference"] == inference, "duplicated inference differs")
    require(integrated["runtime"] == parse("runtime.json"), "runtime differs")
    require(integrated["runtime"]["packages_modified"] is False, "environment change")
    require(inference["state"] == "complete", "inference state")
    for obj in (numeric, integrated, inference):
        require(obj["optimization_runs_added"] == 0, "optimization")
        require(obj["scientific_reporting_eligible"] is False, "historical flag")
    require(
        integrated["training_runs_added"] == inference["training_runs_added"] == 0,
        "training",
    )
    parents = audit.selected_parents(audit.source_receipt())
    require(
        set(numeric["parents"]) == set(parents) and len(parents) == 54, "54 parents"
    )
    require(integrated["sample"]["numerically_passed"] == 54, "54 passed")
    require(numeric["source_artifact_receipt_sha256"] == audit.RECEIPT_SHA, "artifacts")
    prior = audit.reuse_reviewed_return(ROOT / "docs/evidence/pr80-job3502-return.json")
    require(set(numeric["reused_parent_observations"]) == set(prior), "39 reused")
    require(numeric["new_parent_attempts"] == 15, "15 attempted")
    require(integrated["reused_numerical_parents"] == 39, "reuse summary")
    require(
        numeric["prior_return_sha256"]
        == integrated["prior_return_sha256"]
        == audit.JOB3502_RETURN_SHA,
        "prior identity",
    )
    for parent, row in prior.items():
        require(numeric["parents"][parent] == row, "reused row changed")
    for cohort, size in (("easy", 30), ("mixed", 54)):
        require(
            numeric["cohorts"][cohort]["numeric_checks_passed"] is True
            and numeric["cohorts"][cohort]["parents"] == size,
            "cohort",
        )
    rows = []
    for parent, record in sorted(parents.items()):
        result = numeric["parents"][parent]
        rep = result["representation"]
        require(result["state"] == "numeric_checks_passed", "unqualified parent")
        require(
            result["parent"] == parent
            and result["role"] == record["role"] == audit.split_for(parent)[1],
            "parent role",
        )
        require(result["model_sha256"] == record["mip_sha256_declared"], "model hash")
        require(
            result["feasibility"]["valid"] is True
            and all(v is True for v in result["feasibility"]["checks"].values()),
            "feasibility",
        )
        require(
            rep["feature_dimensions"] == [7, 5, 1]
            and rep["all_encoded_entries_compared"] is True
            and rep["root_feature_exact_float32"] is True,
            "representation",
        )
        require(
            rep["variables"]
            == sum(
                rep[k]
                for k in (
                    "binary_variables",
                    "integer_variables",
                    "continuous_variables",
                )
            ),
            "variable count",
        )
        require(
            close(
                rep["density"], rep["nonzeros"] / rep["variables"] / rep["constraints"]
            ),
            "density",
        )
        require(
            close(
                result["label_gap_declared_not_resolved"], record["label_gap_declared"]
            ),
            "label gap",
        )
        if parent not in prior:
            require(
                result["label_objective_sense_observed"] == "minimize",
                "installed sense",
            )
        rows.append(
            {
                "parent": parent,
                "alias": alias(parent),
                "difficulty": parent.split("_")[1],
                "role": record["role"],
                **{key: rep[key] for key in FIELDS},
                "positive_prevalence": rep["positive_discrete_targets"]
                / rep["discrete_targets"],
                "label_gap_declared": record["label_gap_declared"],
                "mean_variable_degree": rep["nonzeros"] / rep["variables"],
                "mean_constraint_degree": rep["nonzeros"] / rep["constraints"],
                "clipped_or_infinite_entries": sum(
                    rep["clipped_or_infinite_source_entries"].values()
                ),
            }
        )
    expected_counts = {
        ("easy", "train"): 18,
        ("easy", "validation"): 6,
        ("easy", "test"): 6,
        ("medium", "train"): 16,
        ("medium", "validation"): 4,
        ("medium", "test"): 4,
    }
    require(
        Counter((r["difficulty"], r["role"]) for r in rows) == expected_counts,
        "partitions",
    )
    exported = list(
        csv.DictReader(io.StringIO(members["parent_statistics.csv"]["text"]))
    )
    require(
        len(exported) == 54 and len({r["parent"] for r in exported}) == 54,
        "export rows",
    )
    by_parent = {r["parent"]: r for r in rows}
    for row in exported:
        expected = by_parent[row["parent"]]
        require(row["role"] == expected["role"], "export role")
        for field in (*FIELDS, "positive_prevalence", "label_gap_declared"):
            require(close(float(row[field]), expected[field]), "export value")
    summary = []
    for (difficulty, role), count in sorted(expected_counts.items()):
        group = [r for r in rows if (r["difficulty"], r["role"]) == (difficulty, role)]
        for field in (
            *FIELDS,
            "positive_prevalence",
            "label_gap_declared",
            "mean_variable_degree",
            "mean_constraint_degree",
            "clipped_or_infinite_entries",
        ):
            values = [r[field] for r in group]
            summary.append(
                {
                    "difficulty": difficulty,
                    "role": role,
                    "metric": field,
                    "count": count,
                    "missing": 0,
                    "minimum": min(values),
                    "q1": quantile(values, 0.25),
                    "median": quantile(values, 0.5),
                    "q3": quantile(values, 0.75),
                    "maximum": max(values),
                    "mean": sum(values) / len(values),
                }
            )
    cases = inference["cases"]
    require(
        len(cases) == 4
        and {(c["cohort"], c["parent"]) for c in cases}
        == {
            (cohort, parent)
            for cohort in ("easy", "mixed")
            for parent in ("CFL_easy_instance_1", "CFL_medium_instance_11")
        },
        "four forwards",
    )
    for case in cases:
        metrics = case["metrics"]
        rep = numeric["parents"][case["parent"]]["representation"]
        require(
            case["role"] == audit.split_for(case["parent"])[1] == "validation",
            "case role",
        )
        tp, tn, fp, fn = (metrics[k] for k in ("tp", "tn", "fp", "fn"))
        require(
            tp + tn + fp + fn == metrics["n_targets"] == rep["discrete_targets"],
            "targets",
        )
        require(
            tp + fn == metrics["n_positive"] == rep["positive_discrete_targets"],
            "positives",
        )
        for key, value in {
            "precision": tp / (tp + fp),
            "recall": tp / (tp + fn),
            "f1_score": 2 * tp / (2 * tp + fp + fn),
            "accuracy": (tp + tn) / (tp + tn + fp + fn),
        }.items():
            require(close(metrics[key], value), "confusion-derived metric")
        require(
            case["selected_support"]
            == min(20000, math.floor(0.1 * metrics["n_targets"])),
            "support",
        )
        require(
            case["start_feasibility_or_acceptance_claimed"] is False
            and case["root_precomputation_included"] is False,
            "start claim",
        )
    require(inference["new_threshold_or_prenorm_fit"] is False, "new fit")
    for cohort, model in inference["models"].items():
        require(model["plan_sha256"] == SELECTION[cohort][0], "plan")
        require(model["new_selection_performed"] is False, "selection")
    accounting = list(csv.DictReader(io.StringIO(package["accounting"]), delimiter="|"))
    require(
        any(
            r["JobID"] == "3503"
            and r["State"] == "COMPLETED"
            and r["ExitCode"] == "0:0"
            for r in accounting
        ),
        "accounting",
    )
    return rows, summary, inference


def write_csv(path, rows):
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def produce(destination):
    destination = Path(destination)
    require(not destination.exists(), "use a fresh output directory")
    package = read_package(ROOT / "docs/evidence/pr80-job3503-return.json")
    rows, summary, inference = validate(package)
    sprint_b = json.loads(
        (ROOT / "docs/evidence/pr79-sprint-b-review.json").read_bytes()
    )
    destination.mkdir(parents=True)
    write_csv(destination / "sample_parents.csv", rows)
    write_csv(destination / "sample_summary.csv", summary)
    inference_rows = [
        {
            "cohort": c["cohort"],
            "parent": c["parent"],
            "role": c["role"],
            **{k: v for k, v in c["metrics"].items() if k != "validation_parent"},
            **{
                k: c[k]
                for k in (
                    "pr_auc",
                    "roc_auc",
                    "forward_seconds",
                    "case_wall_seconds",
                    "gpu_peak_allocated_bytes",
                    "gpu_peak_reserved_bytes",
                    "selected_support",
                )
            },
        }
        for c in inference["cases"]
    ]
    write_csv(destination / "inference_metrics.csv", inference_rows)
    write_csv(destination / "sprint_b_cpu.csv", sprint_b["comparison_rows"])
    cost = [
        {
            k: r[k]
            for k in (
                "job_id",
                "elapsed_seconds",
                "scheduler_total_cpu_seconds",
                "allocated_logical_cpu_hours",
                "requested_physical_core_reservation_hours",
            )
        }
        for r in sprint_b["allocation_rows"]
    ]
    write_csv(destination / "sprint_b_allocation_costs.csv", cost)
    historical_path = ROOT / "manuscript/results/current/table_solver_outcomes.csv"
    with historical_path.open(encoding="utf-8", newline="") as stream:
        historical = list(csv.DictReader(stream))
    predictive = {r["parent"] for r in rows if r["role"] == "test"}
    excluded = {f"CFL_medium_instance_{i}" for i in (5, 6, 9, 13, 20, 26)}
    coverage = []
    for parent in sorted(predictive | excluded):
        for method in (
            "unguided_control",
            "root_lp_matched_partial_start",
            "gnn_class_aware_partial_start",
        ):
            found = [
                r
                for r in historical
                if r["source_instance_id"] == parent and r["method"] == method
            ]
            coverage.append(
                {
                    "parent": parent,
                    "role": audit.split_for(parent)[1],
                    "method": method,
                    "published_records": len(found),
                    "scope": "published_MVP1_solver_table_only",
                    "next_action": "compatibility_review_not_new_control"
                    if found
                    else "check_HPC_coverage_before_proposing_solve",
                }
            )
    write_csv(destination / "e0_published_coverage.csv", coverage)
    report = {
        "return_sha256": RETURN_SHA,
        "source_commit": SOURCE,
        "job_id": "3503",
        "numeric_parents_reviewed": 54,
        "reused_observations": 39,
        "new_observations": 15,
        "validation_forwards_reviewed": 4,
        "confusion_metrics_recomputed": True,
        "prediction_vectors_independently_recomputed": False,
        "auc_independently_recomputed": False,
        "historical_receipts_modified": False,
        "training_or_optimization_added": 0,
        "new_execution_authorized": False,
        "sample_admission_supported": True,
        "generalization_or_solver_benefit_established": False,
        "quantiles": "linear_type7",
        "missing_values_are_zero": False,
        "e0_missing_published_method_rows": sum(
            r["published_records"] == 0 for r in coverage
        ),
        "e0_hpc_coverage_complete": False,
        "source_hashes": {
            "sprint_b_review": audit.metadata.digest(
                (ROOT / "docs/evidence/pr79-sprint-b-review.json").read_bytes()
            ),
            "historical_solver_table": audit.metadata.digest(
                historical_path.read_bytes()
            ),
        },
        "table_hashes": {
            p.name: audit.metadata.digest(p.read_bytes())
            for p in sorted(destination.glob("*.csv"))
        },
    }
    (destination / "review.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report, rows, inference, sprint_b


def figures(destination, rows, inference, sprint_b):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.hashsalt": "pr80-job3503",
            "font.family": "DejaVu Sans",
        }
    )
    colors = ("#176B87", "#B85C38")

    def save(fig, name, note):
        fig.text(0.03, 0.015, note, fontsize=9, va="bottom")
        fig.tight_layout(rect=(0, 0.075, 1, 0.94))
        for extension in ("svg", "png", "pdf"):
            metadata = (
                {"Date": None}
                if extension == "svg"
                else (
                    {"CreationDate": None, "ModDate": None}
                    if extension == "pdf"
                    else {}
                )
            )
            fig.savefig(
                Path(destination) / f"{name}.{extension}", dpi=160, metadata=metadata
            )
        plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    fig.suptitle("Muestra auditada: 54 instancias originales", fontsize=16)
    for j, difficulty in enumerate(("easy", "medium")):
        counts = [
            sum(r["difficulty"] == difficulty and r["role"] == role for r in rows)
            for role in ("train", "validation", "test")
        ]
        axes[0, 0].bar(
            [i + j * 0.35 for i in range(3)],
            counts,
            0.35,
            color=colors[j],
            label="Fáciles (30)" if j == 0 else "Medias (24)",
        )
    axes[0, 0].set_xticks(
        [0.175, 1.175, 2.175], ["Entrenamiento", "Validación", "Prueba"]
    )
    axes[0, 0].set_ylabel("Número de padres")
    axes[0, 0].legend(fontsize=8)
    for ax, key, label, factor in zip(
        axes.flat[1:],
        (
            "variables",
            "nonzeros",
            "density",
            "positive_prevalence",
            "label_gap_declared",
        ),
        (
            "Variables (millones)",
            "No ceros (millones)",
            "Densidad (%)",
            "Etiquetas positivas (%)",
            "Brecha declarada (%)",
        ),
        (1e-6, 1e-6, 100, 100, 100),
    ):
        for j, difficulty in enumerate(("easy", "medium")):
            vals = [r[key] * factor for r in rows if r["difficulty"] == difficulty]
            ax.boxplot([vals], positions=[j], widths=0.45, showfliers=False)
            ax.scatter(
                [j + (i % 7 - 3) * 0.018 for i in range(len(vals))],
                vals,
                s=12,
                alpha=0.5,
                color=colors[j],
            )
        ax.set_xticks([0, 1], ["Fáciles", "Medias"])
        ax.set_title(label)
        ax.grid(axis="y", alpha=0.2)
    save(
        fig,
        "figure_sample",
        "Un punto por padre; selección histórica por calidad de etiqueta, no muestra aleatoria.\nBrechas declaradas: no se resolvieron de nuevo los problemas. Cuartiles con interpolación lineal.",
    )

    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    fig.suptitle("Sprint B: efecto del límite de hilos de Gurobi", fontsize=16)
    for i, parent in enumerate(("easy", "medium")):
        group = sorted(
            [r for r in sprint_b["comparison_rows"] if r["parent"] == parent],
            key=lambda r: r["threads"],
        )
        for j, (key, factor, label) in enumerate(
            (
                (
                    "first_observed_target_seconds",
                    1,
                    "Tiempo observado hasta el objetivo (s)",
                ),
                ("gap_relative", 100, "Brecha final (%)"),
                (
                    "sampled_cgroup_peak_bytes",
                    1 / 2**30,
                    "Pico de RAM del grupo del job (GiB)",
                ),
            )
        ):
            ax = axes[i, j]
            valid = [r for r in group if r[key] is not None]
            ax.plot(
                [r["threads"] for r in valid],
                [r[key] * factor for r in valid],
                "o-",
                color=colors[i],
            )
            if j == 0:
                missing = [r for r in group if r[key] is None]
                ax.scatter(
                    [r["threads"] for r in missing],
                    [r["solver_runtime_seconds"] for r in missing],
                    marker="^",
                    facecolors="none",
                    edgecolors=colors[i],
                    s=65,
                    label="Objetivo no alcanzado",
                )
                if missing:
                    ax.legend(fontsize=8)
            ax.set_xscale("log", base=2)
            ax.set_xticks([1, 2, 4, 8, 16], [1, 2, 4, 8, 16])
            ax.set_xlabel("Límite de hilos")
            ax.set_title(label, fontsize=10)
            ax.set_ylabel("F17 (objetivo 1%)" if i == 0 else "M1 (objetivo 10%)")
            ax.grid(alpha=0.2)
    save(
        fig,
        "figure_cpu",
        "Dos padres de desarrollo, semilla 42; no inferencia poblacional. Triángulos: observaciones censuradas.\nLas brechas finales corresponden a paradas distintas; memoria muestreada, no RSS ni máximo exacto.",
    )

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    fig.suptitle("Modelos congelados: dos instancias de validación", fontsize=16)
    for ax, metric, label in zip(
        axes.flat,
        ("f1_score", "precision", "recall", "pr_auc"),
        ("F1", "Precisión", "Sensibilidad", "Área bajo la curva PR"),
    ):
        for j, cohort in enumerate(("easy", "mixed")):
            cases = [c for c in inference["cases"] if c["cohort"] == cohort]
            vals = [
                c["pr_auc"] if metric == "pr_auc" else c["metrics"][metric]
                for c in cases
            ]
            ax.bar(
                [k + j * 0.35 for k in range(2)],
                vals,
                0.35,
                color=colors[j],
                label="Modelo fácil" if j == 0 else "Modelo mixto",
            )
        ax.set_xticks([0.175, 1.175], ["F1", "M11"])
        ax.set_ylim(0, 1)
        ax.set_title(label)
        ax.grid(axis="y", alpha=0.2)
    axes[0, 0].legend(fontsize=8)
    save(
        fig,
        "figure_predictive",
        "Umbrales históricos, sin nuevo ajuste. Validación conocida; no prueba independiente ni mejora del solver.\nMétricas por variable; el padre sigue siendo la unidad independiente.",
    )

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8))
    fig.suptitle("Inferencia en una V100 de 32 GB", fontsize=16)
    for ax, key, factor, title in zip(
        axes,
        ("forward_seconds", "case_wall_seconds", "gpu_peak_allocated_bytes"),
        (1000, 1, 1 / 2**30),
        (
            "Forward sincronizado (ms)",
            "Tiempo del caso (s)",
            "Pico asignado por PyTorch (GiB)",
        ),
    ):
        cases = inference["cases"]
        ax.bar(
            range(4),
            [c[key] * factor for c in cases],
            color=[colors[0], colors[0], colors[1], colors[1]],
        )
        ax.set_xticks(range(4), ["Fácil\nF1", "Fácil\nM11", "Mixto\nF1", "Mixto\nM11"])
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.2)
    save(
        fig,
        "figure_inference_cost",
        "Una pasada por caso, orden fijo, sin calentamiento separado: no comparar velocidades entre modelos.\nNo incluye precálculo de la raíz, entrenamiento ni optimización. No es un estudio de escalabilidad GPU.",
    )
    manifest = {
        "matplotlib": matplotlib.__version__,
        "source_return_sha256": RETURN_SHA,
        "figure_hashes": {
            p.name: audit.metadata.digest(p.read_bytes())
            for p in sorted(Path(destination).glob("figure_*"))
        },
    }
    (Path(destination) / "figures_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--figures", action="store_true")
    args = parser.parse_args()
    result, data, predictions, pilot = produce(args.output_directory)
    if args.figures:
        figures(args.output_directory, data, predictions, pilot)
    print(json.dumps(result, sort_keys=True))
