"""Reproduce frozen-model descriptive results from the immutable job3505 return."""

import argparse
import json
import statistics as stats
from pathlib import Path

import e0_frozen_inference as flow

SHA = "8f8f0b3c9dc350422f7a36bdb6c46d338186274ebf629d14acb88ea0ecbf9c40"
SOURCE = flow.c1.ROOT / "docs/evidence/e0/job3505-return.json"
EASY = tuple(p for p in flow.CASES if "_easy_" in p)


def reviewed():
    data = SOURCE.read_bytes()
    rows = flow.validate_return(data, SHA)
    value = flow.meta.strict_json(data)
    flow.c1.require(value["job_id"] == "3505", "job_identity")
    flow.c1.require(
        value["source_commit"] == "d6e7b20c1dfd25a9aa628b0ca6315351a2635d45",
        "source_commit",
    )
    return value, rows


def summarize(rows):
    result = []
    for difficulty in ("easy", "medium"):
        for cohort in ("easy", "mixed"):
            group = [
                r
                for r in rows
                if r["cohort"] == cohort and f"_{difficulty}_" in r["parent"]
            ]
            positives = sum(r["n_positive"] for r in group)
            total = sum(r["n_targets"] for r in group)
            result.append(
                {
                    "difficulty": difficulty,
                    "cohort": cohort,
                    "parents": len(group),
                    "positive_fraction": positives / total,
                    "all_zero_accuracy": 1 - positives / total,
                    **{
                        f"macro_{m}": stats.mean(r[m] for r in group)
                        for m in (
                            "f1_score",
                            "precision",
                            "recall",
                            "pr_auc",
                            "roc_auc",
                            "accuracy",
                        )
                    },
                    "median_forward_seconds": stats.median(
                        r["forward_seconds"] for r in group
                    ),
                    "median_case_seconds": stats.median(
                        r["case_wall_seconds"] for r in group
                    ),
                    "max_torch_allocated_gib": max(
                        r["gpu_peak_allocated_bytes"] for r in group
                    )
                    / 1024**3,
                }
            )
    effects = []
    for parent in flow.CASES:
        pair = {r["cohort"]: r for r in rows if r["parent"] == parent}
        effects.append(
            {
                "parent": parent,
                **{
                    f"mixed_minus_easy_{m}": pair["mixed"][m] - pair["easy"][m]
                    for m in (
                        "f1_score",
                        "pr_auc",
                        "recall",
                        "forward_seconds",
                        "case_wall_seconds",
                    )
                },
            }
        )
    return result, effects


def proposal():
    # Historical mixed-model completion was specified before observing job3505.
    return {
        "protocol_id": "e0_six_easy_missing_coverage_proposal_v1",
        "inference_return_sha256": SHA,
        "parents": list(EASY),
        "cohort": "mixed",
        "seed": 42,
        "threads": 1,
        "methods": [
            "unguided_control",
            "root_lp_matched_partial_start",
            "gnn_class_aware_partial_start",
        ],
        "maximum_main_solves": 18,
        "time_limit_per_main_solve_seconds": 3600,
        "maximum_main_solver_seconds": 64800,
        "new_root_solves": 0,
        "source_objective_sense_must_be_recorded": True,
        "effective_objective_sense": "MINIMIZE",
        "root_precomputation_cost_available": False,
        "model_choice_reason": "complete_historical_mixed_protocol_not_test_winner_selection",
        "remaining_label_excluded_parents": [
            "CFL_medium_instance_13",
            "CFL_medium_instance_26",
        ],
        "solver_execution_admitted": False,
        "resource_budget_approved": False,
        "automatic_retry": False,
        "training_runs_added": 0,
    }


def produce(output, figures=False):
    value, rows = reviewed()
    summary, effects = summarize(rows)
    output.mkdir(parents=True, exist_ok=False)
    for name, items in (
        ("per_parent.csv", rows),
        ("summary.csv", summary),
        ("paired_effects.csv", effects),
    ):
        flow.c1.write_csv(output / name, items)
    flow.legacy.write(output / "next_solve_proposal.json", proposal())
    flow.legacy.write(
        output / "review.json",
        {
            "job_id": value["job_id"],
            "source_return_sha256": SHA,
            "forwards": 20,
            "mixed_f1_wins": sum(r["mixed_minus_easy_f1_score"] > 0 for r in effects),
            "mixed_pr_auc_wins": sum(r["mixed_minus_easy_pr_auc"] > 0 for r in effects),
            "confusion_metrics_independently_recomputed": True,
            "auc_private_rescoring_performed": False,
            "solver_acceptance_qualified": False,
            "fresh_holdout_claimed": False,
            "causal_training_cohort_effect_claimed": False,
            "gpu_scaling_claimed": False,
            "optimization_runs_added": 0,
        },
    )
    if figures:
        import matplotlib.pyplot as plt

        plt.rcParams.update({"font.size": 10, "svg.hashsalt": "e0-job3505"})
        labels = [
            p.replace("CFL_easy_instance_", "F").replace("CFL_medium_instance_", "M")
            for p in flow.CASES
        ]
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        for cohort, label, color, marker in (
            ("easy", "Modelo solo fáciles", "#cd7f32", "s"),
            ("mixed", "Modelo mixto", "#176f85", "o"),
        ):
            group = {r["parent"]: r for r in rows if r["cohort"] == cohort}
            for ax, metric in zip(axes, ("f1_score", "pr_auc")):
                ax.plot(
                    range(10),
                    [group[p][metric] for p in flow.CASES],
                    marker=marker,
                    color=color,
                    label=label,
                )
                ax.set_xticks(range(10), labels)
                ax.axvline(5.5, linestyle="--", color="0.6")
                ax.set_ylim(0, 1)
                ax.set_title(
                    "F1 con umbral congelado"
                    if metric == "f1_score"
                    else "Área bajo la curva precisión–recobrado"
                )
                ax.grid(axis="y", alpha=0.2)
        axes[0].legend(loc="lower left")
        fig.suptitle(
            "E0: evaluación de dos modelos existentes en diez padres de prueba"
        )
        fig.text(
            0.02,
            0.02,
            "Una evaluación por modelo y padre. Partición histórica; sin nuevo entrenamiento.\nF1 reconciliado con la matriz de confusión; AUC registrada, sin recálculo de predicciones privadas.",
            fontsize=9,
        )
        fig.tight_layout(rect=(0, 0.10, 1, 0.94))
        for ext in ("svg", "pdf", "png"):
            fig.savefig(output / f"predictive_comparison.{ext}", dpi=160)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
        for cohort, label, color, marker in (
            ("easy", "Modelo solo fáciles", "#cd7f32", "s"),
            ("mixed", "Modelo mixto", "#176f85", "o"),
        ):
            group = {r["parent"]: r for r in rows if r["cohort"] == cohort}
            for ax, metric in zip(axes, ("forward_seconds", "case_wall_seconds")):
                ax.scatter(
                    range(10),
                    [group[p][metric] for p in flow.CASES],
                    marker=marker,
                    color=color,
                    label=label,
                )
                ax.set_xticks(range(10), labels)
                ax.set_yscale("log")
                ax.set_ylabel("Segundos (escala logarítmica)")
                ax.set_title(
                    "Paso de inferencia en GPU"
                    if metric == "forward_seconds"
                    else "Caso: carga, inferencia, selección y evaluación"
                )
                ax.grid(axis="y", alpha=0.2)
        axes[0].legend(fontsize=8)
        fig.suptitle("Costes observados con una Tesla V100 de 32 GB")
        fig.text(
            0.02,
            0.02,
            "Job3505: 179 s. Una medición por caso; orden fijo, sin ensayo de aceleración.\nEl tiempo por caso excluye el cálculo previo de la relajación y no incluye una resolución MILP.",
            fontsize=9,
        )
        fig.tight_layout(rect=(0, 0.10, 1, 0.94))
        for ext in ("svg", "pdf", "png"):
            fig.savefig(output / f"inference_cost.{ext}", dpi=160)
        plt.close(fig)
    manifest = {
        p.name: flow.meta.digest(p.read_bytes())
        for p in sorted(output.iterdir())
        if p.is_file()
    }
    flow.legacy.write(
        output / "asset_hashes.json", {"source_return_sha256": SHA, "files": manifest}
    )
    print(json.dumps({"source_sha256": SHA, "summary": summary}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figures", action="store_true")
    args = parser.parse_args()
    produce(args.output, args.figures)
