"""Reproduce descriptive E0 solver results without executing Gurobi or Slurm."""

import argparse
import csv
import json
import math
import statistics as stats
from pathlib import Path

import e0_three_method_executor as flow

SHA = "60260ac77b84538316b725ac0d38033fd3c4afa29b056915085b9455f749cfce"
HEAD = "15da78c928403a27201b831cb1b701cf4e145e8d"
SOURCE = flow.ROOT / "docs/evidence/e0/job3506-return.json"
LABELS = ("Sin inicio", "Inicio LP", "Inicio GNN")
COLORS = ("#555b66", "#c17c18", "#226da8")


def close(a, b, code, absolute=1e-10):
    flow.require(
        math.isfinite(a)
        and math.isfinite(b)
        and math.isclose(a, b, rel_tol=1e-9, abs_tol=absolute),
        code,
    )


def gap(primal, dual):
    if primal is None or dual is None:
        return None
    flow.require(math.isfinite(primal) and math.isfinite(dual), "finite_bounds")
    return abs(primal - dual) / abs(primal) if primal else (0.0 if dual == 0 else None)


def audit(value):
    """Audit recorded numerics; do not claim to reread private solutions/logs."""
    frozen = value["plan"]
    flow.require(
        value["job_id"] == "3506" and frozen["source_commit"] == HEAD, "identity"
    )
    flow.require(value["ready_for_independent_review"] is True, "not_ready")
    flow.require(
        value["scientific_reporting_eligible"] is False
        and value["raw_logs_included"] is False,
        "scope",
    )
    flow.require(frozen["binding_sha256"] == flow.BINDING_SHA, "binding")
    # Freeze the recorded dependency set, not today's growing scripts directory.
    # New analysis scripts must not rewrite the historical plan or require a retry.
    expected = flow.plan(HEAD)
    pins = frozen["source_sha256_lf"]
    expected["source_sha256_lf"] = pins
    flow.require(frozen == expected, "frozen_contract")
    for name, sha in pins.items():
        path = flow.ROOT / name
        flow.require(path.resolve().is_relative_to(flow.ROOT.resolve()), "source_path")
        flow.require(
            flow.digest(path.read_bytes().replace(b"\r\n", b"\n")) == sha,
            "frozen_source_changed",
        )
    matrix = flow.validate_matrix(value["matrix"], frozen)
    flow.require(matrix["job_id"] == "3506" and matrix["complete"], "matrix")
    accounting = list(csv.DictReader(value["accounting"].splitlines(), delimiter="|"))
    flow.require(
        [r["JobID"] for r in accounting] == ["3506", "3506.batch", "3506.extern"],
        "accounting_members",
    )
    flow.require(
        all(r["State"] == "COMPLETED" and r["ExitCode"] == "0:0" for r in accounting),
        "accounting_success",
    )
    flat, trajectory = [], []
    for attempt in matrix["attempts"]:
        child, supervision = attempt["child"], attempt["supervision"]
        result = child["result"]
        solve, timing, start = result["solve"], result["timing"], result["start"]
        flow.require(
            supervision["guard_stop"] is None
            and supervision["child_exit_code"] == 0
            and supervision["memory_failure_diagnostic"] is None,
            "supervision",
        )
        flow.require(
            result["gate_status"] == "passed"
            and not result["callback_errors"]
            and result["fresh_model"] is True,
            "result_gate",
        )
        flow.require(
            solve["solve_status_code"] == 2
            and not solve["right_censored"]
            and solve["feasible_solution"],
            "terminal_status",
        )
        close(
            gap(solve["primal"], solve["dual"]), solve["common_mip_gap_relative"], "gap"
        )
        flow.require(solve["common_mip_gap_relative"] <= 1e-4 + 1e-12, "target")
        feasibility = result["independent_feasibility"]
        flow.require(
            feasibility["valid"] and all(feasibility["checks"].values()), "feasibility"
        )
        close(
            feasibility["recomputed_objective"],
            solve["primal"],
            "audit_objective",
            1e-6,
        )
        for field, tol in (
            ("max_bound_residual", "feasibility_tolerance"),
            ("max_row_residual", "feasibility_tolerance"),
            ("max_integrality_residual", "integrality_tolerance"),
        ):
            flow.require(0 <= feasibility[field] <= feasibility[tol], "audit_residual")
        parameter_bytes = json.dumps(
            result["parameters"], sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        flow.require(
            flow.digest(parameter_bytes) == result["parameter_sha256"], "params_hash"
        )
        flow.require(result["original_objective_sense"] == "MAXIMIZE", "source_sense")
        flow.require(start["unselected_starts_undefined"] is True, "start_semantics")
        close(
            start["actual_coverage"],
            start["submitted_assignments"] / start["binary_variables"],
            "coverage",
        )
        flow.require(
            start["positive_assignments"] + start["negative_assignments"]
            == start["submitted_assignments"],
            "support_counts",
        )
        if attempt["index"] % 3:
            flow.require(
                start["accepted"] is True and start["completed"] is True, "acceptance"
            )
        for seal in (attempt["console_log"], child["gurobi_log"]):
            flow.require(
                seal["private_log_text_included"] is False
                and seal["hash_scope"] == "bytes_after_caller_closed_writer"
                and flow.re.fullmatch(r"[0-9a-f]{64}", seal["log_sha256"]) is not None
                and seal["log_size_bytes"] > 0,
                "log_seal",
            )
        flow.require(
            flow.re.fullmatch(r"[0-9a-f]{64}", child["private_solution_sha256"])
            is not None,
            "solution_hash",
        )
        parts = (
            "data_read_wall_time_seconds",
            "model_build_wall_time_seconds",
            "model_optimize_wall_time_seconds",
            "independent_audit_wall_time_seconds",
            "other_wall_time_seconds",
        )
        close(
            sum(timing[k] for k in parts),
            timing["total_wall_time_seconds"],
            "timing_sum",
            1e-6,
        )
        flow.require(
            all(timing[k] >= 0 for k in parts)
            and timing["solution_export_wall_time_seconds"]
            <= timing["other_wall_time_seconds"],
            "export_is_subset_of_other",
        )
        points = result["trajectory"]
        flow.require(points and points[-1]["event"] == "terminal", "terminal_point")
        close(points[-1]["primal"], solve["primal"], "terminal_primal")
        close(points[-1]["dual"], solve["dual"], "terminal_dual")
        flow.require(
            all(
                0 <= p["seconds"] <= timing["model_optimize_wall_time_seconds"] + 0.1
                for p in points
            )
            and all(a["seconds"] <= b["seconds"] for a, b in zip(points, points[1:])),
            "trajectory_time",
        )
        alias = child["parent"].replace("CFL_easy_instance_", "F")
        for point in points:
            computed = gap(point["primal"], point["dual"])
            if computed is None:
                flow.require(point["common_gap_relative"] is None, "missing_gap")
            else:
                close(computed, point["common_gap_relative"], "trajectory_gap")
            trajectory.append({"parent": alias, "method": child["method"], **point})
        # First-hit callbacks can be omitted by the 30s recording throttle.
        # Thus the public curve supplies an upper bound, not an exact replay.
        for threshold, observed in solve["first_observed_gap_times_seconds"].items():
            eligible = [
                p["seconds"]
                for p in points
                if p["common_gap_relative"] is not None
                and p["common_gap_relative"] <= float(threshold)
            ]
            flow.require(
                observed is not None and 0 <= observed <= min(eligible) + 1e-6,
                "observed_target_bound",
            )
        close(
            solve["first_observed_feasible_seconds"],
            next(p["seconds"] for p in points if p["primal"] is not None),
            "first_feasible",
        )
        flat.append(
            {
                "parent": alias,
                "source_instance_id": child["parent"],
                "method": child["method"],
                "primal": solve["primal"],
                "dual": solve["dual"],
                "gap_fraction": solve["common_mip_gap_relative"],
                "status_code": 2,
                "solver_runtime_seconds": solve["solver_runtime_seconds"],
                "optimize_wall_seconds": timing["model_optimize_wall_time_seconds"],
                "local_pipeline_wall_seconds": timing["total_wall_time_seconds"],
                "load_build_seconds": timing["data_read_wall_time_seconds"]
                + timing["model_build_wall_time_seconds"],
                "audit_seconds": timing["independent_audit_wall_time_seconds"],
                "other_including_export_seconds": timing["other_wall_time_seconds"],
                "export_seconds_subset_of_other": timing[
                    "solution_export_wall_time_seconds"
                ],
                "first_feasible_seconds": solve["first_observed_feasible_seconds"],
                "first_observed_gap_1pct_seconds": solve[
                    "first_observed_gap_times_seconds"
                ]["0.01"],
                "nodes": solve["node_count"],
                "start_accepted_recorded": start["accepted"],
                "selected_support": start["submitted_assignments"],
                "positive_assignments": start["positive_assignments"],
                "sampled_cgroup_peak_gib": supervision["sampled_cgroup_peak_bytes"]
                / 1024**3,
                "root_precomputation_seconds": None,
                "full_end_to_end_seconds": None,
                "gurobi_log_sha256": child["gurobi_log"]["log_sha256"],
                "source_return_sha256": SHA,
            }
        )
    return flat, trajectory, accounting


def reviewed():
    raw = SOURCE.read_bytes()
    flow.require(flow.digest(raw) == SHA, "receipt_bytes")
    value = flow.review.flow.meta.strict_json(raw)
    return value, audit(value)


def summarize(rows):
    effects, summaries = [], []
    for i in range(0, 18, 3):
        control = rows[i]
        for row in rows[i + 1 : i + 3]:
            effects.append(
                {
                    "parent": row["parent"],
                    "method": row["method"],
                    "runtime_ratio_vs_control": row["solver_runtime_seconds"]
                    / control["solver_runtime_seconds"],
                    "runtime_difference_seconds": row["solver_runtime_seconds"]
                    - control["solver_runtime_seconds"],
                    "local_pipeline_ratio_vs_control": row[
                        "local_pipeline_wall_seconds"
                    ]
                    / control["local_pipeline_wall_seconds"],
                    "gap_difference_percentage_points": 100
                    * (row["gap_fraction"] - control["gap_fraction"]),
                    "primal_difference": row["primal"] - control["primal"],
                    "source_return_sha256": SHA,
                }
            )
    for method in flow.METHODS:
        group = [r for r in rows if r["method"] == method]
        paired = [r for r in effects if r["method"] == method]
        summaries.append(
            {
                "method": method,
                "parents": len(group),
                "sum_solver_seconds": sum(r["solver_runtime_seconds"] for r in group),
                "median_solver_seconds": stats.median(
                    r["solver_runtime_seconds"] for r in group
                ),
                "mean_solver_seconds": stats.mean(
                    r["solver_runtime_seconds"] for r in group
                ),
                "max_sampled_cgroup_gib": max(
                    r["sampled_cgroup_peak_gib"] for r in group
                ),
                "faster_than_control_count": sum(
                    r["runtime_ratio_vs_control"] < 1 for r in paired
                )
                if paired
                else None,
                "geometric_mean_runtime_ratio": math.exp(
                    stats.mean(math.log(r["runtime_ratio_vs_control"]) for r in paired)
                )
                if paired
                else None,
                "median_runtime_ratio": stats.median(
                    r["runtime_ratio_vs_control"] for r in paired
                )
                if paired
                else None,
                "source_return_sha256": SHA,
            }
        )
    return summaries, effects


def figures(output, rows, trajectory):
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "svg.hashsalt": "e0-job3506"})
    parents = [r["parent"] for r in rows[::3]]

    def save(fig, name):
        for ext in ("svg", "pdf", "png"):
            metadata = (
                {"CreationDate": None, "ModDate": None}
                if ext == "pdf"
                else ({"Date": None} if ext == "svg" else {})
            )
            fig.savefig(output / f"{name}.{ext}", dpi=160, metadata=metadata)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for j, (method, label, color) in enumerate(zip(flow.METHODS, LABELS, COLORS)):
        group = [r for r in rows if r["method"] == method]
        axes[0].bar(
            [i + (j - 1) * 0.24 for i in range(6)],
            [r["solver_runtime_seconds"] for r in group],
            width=0.23,
            label=label,
            color=color,
        )
        if j:
            axes[1].plot(
                range(6),
                [
                    r["solver_runtime_seconds"] / rows[i * 3]["solver_runtime_seconds"]
                    for i, r in enumerate(group)
                ],
                marker="o" if j == 1 else "s",
                label=label,
                color=color,
            )
    axes[0].set_ylabel("Tiempo del solver (s)")
    axes[0].set_title("18 resoluciones; objetivo de brecha 0,01 %")
    axes[1].axhline(1, color="0.5", linestyle="--")
    axes[1].set_ylabel("Tiempo con inicio / tiempo sin inicio")
    axes[1].set_title("Menor que 1: más rápido que el control")
    for ax in axes:
        ax.set_xticks(range(6), parents)
        ax.grid(axis="y", alpha=0.2)
        ax.legend(fontsize=9)
    fig.suptitle("E0: el efecto del inicio depende de la instancia")
    fig.text(
        0.02,
        0.025,
        "Una ejecución por celda; semilla 42 y un hilo. No es una estimación de aceleración general.\nTiempo del solver: excluye preparación de la guía y auditoría. Job3506; retorno 60260ac77b84.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.13, 1, 0.94))
    save(fig, "solver_comparison")

    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for ax, parent in zip(axes.flat, parents):
        for method, label, color in zip(flow.METHODS, LABELS, COLORS):
            points = [
                p
                for p in trajectory
                if p["parent"] == parent
                and p["method"] == method
                and p["common_gap_relative"] is not None
            ]
            ax.step(
                [p["seconds"] for p in points],
                [100 * p["common_gap_relative"] for p in points],
                where="post",
                color=color,
                label=label,
                linewidth=1.4,
            )
        ax.set_title(parent)
        ax.set_xlabel("Tiempo de pared observado (s)")
        ax.set_ylabel("Brecha (%)")
        ax.set_ylim(-2, 102)
        ax.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Trayectorias registradas de brecha durante la resolución")
    fig.text(
        0.02,
        0.02,
        "Escalones entre observaciones guardadas, no cruces exactos ni interpolación de eventos ausentes.\nLas curvas terminan al finalizar cada método. Fuente: job3506; retorno 60260ac77b84.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.09, 1, 0.95))
    save(fig, "gap_trajectories")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    bottom = [0.0] * 3
    for field, label, color in (
        ("load_build_seconds", "Lectura y construcción", "#9bb9cb"),
        ("optimize_wall_seconds", "Optimización", "#32698d"),
        ("audit_seconds", "Auditoría", "#cb9b53"),
        ("other_including_export_seconds", "Otros, incluida exportación", "#a7a7a7"),
    ):
        values = [
            stats.mean(r[field] for r in rows if r["method"] == method)
            for method in flow.METHODS
        ]
        axes[0].bar(range(3), values, bottom=bottom, color=color, label=label)
        bottom = [a + b for a, b in zip(bottom, values)]
    axes[0].set_xticks(range(3), LABELS)
    axes[0].set_ylabel("Media del tiempo local por caso (s)")
    axes[0].legend(fontsize=8)
    axes[0].set_title("Costes medidos sin sumar dos veces la exportación")
    for j, (method, label, color) in enumerate(zip(flow.METHODS, LABELS, COLORS)):
        axes[1].plot(
            range(6),
            [r["sampled_cgroup_peak_gib"] for r in rows if r["method"] == method],
            color=color,
            marker=("o", "s", "^")[j],
            label=label,
        )
    axes[1].set_xticks(range(6), parents)
    axes[1].set_ylabel("Pico muestreado del cgroup (GiB)")
    axes[1].set_title("Memoria del job; no equivale a MaxRSS")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle("Costes computacionales observados: CPU, un hilo")
    fig.text(
        0.02,
        0.02,
        "Excluye cálculo previo de la relajación, inferencia y materialización de inicios. Coste end-to-end no disponible.\nSin ensayo de escalado CPU/GPU. Fuente: job3506; retorno 60260ac77b84.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.14, 1, 0.94))
    save(fig, "computational_cost")


def produce(output, with_figures=False):
    value, (rows, trajectory, accounting) = reviewed()
    summary, effects = summarize(rows)
    output.mkdir(parents=True, exist_ok=False)
    for name, items in (
        ("per_method.csv", rows),
        ("summary.csv", summary),
        ("paired_effects.csv", effects),
        ("trajectory.csv", trajectory),
        ("accounting.csv", accounting),
    ):
        flow.review.flow.c1.write_csv(output / name, items)
    report = {
        "job_id": "3506",
        "source_return_sha256": SHA,
        "source_commit": HEAD,
        "completed_solves": 18,
        "accepted_starts_recorded": 12,
        "all_recomputed_gaps_within_target": True,
        "private_solution_audits_recorded_passed": 18,
        "private_solution_reaudit_performed_locally": False,
        "private_log_text_reviewed_locally": False,
        "first_crossings_exact": False,
        "affinity_measured_in_return": False,
        "threads_parameter_recorded": 1,
        "scheduler_alloc_cpus": int(accounting[0]["AllocCPUS"]),
        "elapsed_seconds": int(accounting[0]["ElapsedRaw"]),
        "sum_solver_seconds": sum(r["solver_runtime_seconds"] for r in rows),
        "max_sampled_cgroup_gib": max(r["sampled_cgroup_peak_gib"] for r in rows),
        "max_wall_minus_runtime_seconds": max(
            r["optimize_wall_seconds"] - r["solver_runtime_seconds"] for r in rows
        ),
        "root_precomputation_seconds": None,
        "end_to_end_speedup_qualified": False,
        "statistical_significance_claimed": False,
        "optimization_runs_added": 0,
        "scientific_reporting_eligible": False,
        "summary": summary,
    }
    flow.write(output / "review.json", report)
    if with_figures:
        figures(output, rows, trajectory)
    flow.write(
        output / "asset_hashes.json",
        {
            "source_return_sha256": SHA,
            "files": {
                p.name: flow.digest(p.read_bytes())
                for p in sorted(output.iterdir())
                if p.is_file()
            },
        },
    )
    print(flow.encoded(report).decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figures", action="store_true")
    args = parser.parse_args()
    produce(args.output, args.figures)
