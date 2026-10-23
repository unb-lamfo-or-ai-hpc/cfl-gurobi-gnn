"""Derive seed42 views and unapproved CPU budget; no solver, training or scheduler."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/evidence/pr86/final-210/campaign_results.csv"
SOURCE_SHA = "e5fc92d75f2d26620a51a4e4d9b1d1f63befd7ec2680ad7a3b2c34cd781390b8"
DEST = ROOT / "docs/evidence/methodology-20261019"
CAPS = (1, 2, 4, 8, 16)
METHODS = ("M0", "M1", "M2")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def csv_bytes(rows, columns=None):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=columns or list(rows[0]), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def json_bytes(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def observed_rows(raw):
    require(digest(raw) == SOURCE_SHA, "historical_source_hash")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    require(
        len(rows) == 210 and len({r["cell_id"] for r in rows}) == 210,
        "historical_cells",
    )
    selected = [r for r in rows if r["seed"] == "42"]
    require(len(selected) == 150, "main_seed42_count")
    require(
        Counter(r["method"] for r in selected) == {m: 50 for m in METHODS}, "methods"
    )
    require(len({r["parent"] for r in selected}) == 10, "parent_unit")
    require(sum(r["right_censored"] == "True" for r in selected) == 53, "censoring")
    return rows, selected


def qualified(row):
    # Terminal solver times are comparable only at the same terminal criterion.
    # This scoped eligibility does not turn a floating-point result into exact proof.
    return row["right_censored"] == "False" and row["alias"] not in {"M4", "M12"}


def comparisons(rows):
    lookup = {(r["parent"], r["threads"], r["method"]): r for r in rows}
    result, scaling = [], []
    for row in rows:
        for baseline in ("M0", "M1") if row["method"] == "M2" else ():
            other = lookup[(row["parent"], row["threads"], baseline)]
            eligible = qualified(row) and qualified(other)
            result.append(
                {
                    "parent": row["parent"],
                    "alias": row["alias"],
                    "threads": row["threads"],
                    "seed": 42,
                    "comparison": "M2_vs_" + baseline,
                    "speedup_baseline_over_M2": float(other["solver_seconds"])
                    / float(row["solver_seconds"])
                    if eligible
                    else "",
                    "eligible_common_terminal_target": eligible,
                    "reason": "scoped_tolerance_review_not_exact_certificate"
                    if eligible
                    else "censored_or_numerically_sensitive",
                }
            )
        base = lookup[(row["parent"], "1", row["method"])]
        eligible = qualified(row) and qualified(base)
        speedup = (
            float(base["solver_seconds"]) / float(row["solver_seconds"])
            if eligible
            else None
        )
        scaling.append(
            {
                "parent": row["parent"],
                "alias": row["alias"],
                "method": row["method"],
                "seed": 42,
                "threads": row["threads"],
                "same_method_cpu_speedup": speedup if eligible else "",
                "same_method_cpu_efficiency": speedup / int(row["threads"])
                if eligible
                else "",
                "eligible_common_terminal_target": eligible,
            }
        )
    return result, scaling


def cpu_package():
    matrix = []
    _, principal = observed_rows(SOURCE.read_bytes())
    for parent in (0, 4, 7, 12):
        # Preserve the original seed42 method order, not a new outcome-driven order.
        for cap in CAPS:
            order = [
                r["method"]
                for r in sorted(
                    (
                        r
                        for r in principal
                        if r["alias"] == f"M{parent}" and r["threads"] == str(cap)
                    ),
                    key=lambda r: int(r["method_order_position"]),
                )
            ]
            for position, method in enumerate(order, 1):
                matrix.append(
                    {
                        "sequence": len(matrix) + 1,
                        "parent": f"CFL_medium_instance_{parent}",
                        "alias": f"M{parent}",
                        "method": method,
                        "threads": cap,
                        "seed": 42,
                        "method_order_position": position,
                        "solver_limit_seconds": 43200,
                        "wall_seconds": 46800,
                        "memory_mib": 65536,
                        "gpus": 0,
                        "nodes": 1,
                        "tasks": 1,
                        "execution_authorized": False,
                    }
                )
    return matrix, {
        "package_id": "pr88_cpu_medium12h_seed42_proposal_v1",
        "execution_authorized": False,
        "resource_budget_approved": False,
        "scheduler_feasibility_verified": False,
        "source_campaign_sha256": SOURCE_SHA,
        "seed": 42,
        "methods": list(METHODS),
        "thread_caps": list(CAPS),
        "objective_sense": "MINIMIZE",
        "mip_gap_fraction": 0.0001,
        "maximum_jobs": 60,
        "maximum_optimization_calls": 60,
        "solver_hours_ceiling": 720,
        "physical_cap_solver_core_hours_ceiling": 4464,
        "sequential_reserved_hours_ceiling": 780,
        "physical_reserved_core_hours_ceiling": 4836,
        "memory_mib_per_job": 65536,
        "solver_soft_memory_decimal_gb": 48,
        "sampled_stop_gib": 56,
        "kernel_ram_gib": 64,
        "wall_seconds_per_job": 46800,
        "solver_seconds_per_call": 43200,
        "gpus": 0,
        "maximum_concurrent_jobs": 1,
        "partition": "batch",
        "nodes_per_job": "1-1",
        "tasks_per_job": 1,
        "exclusive": False,
        "requeue": False,
        "automatic_retry": False,
        "resume": False,
        "new_preparation_or_training_admitted": False,
        "targets_gap_fraction": [0.1, 0.05, 0.01, 0.0001],
        "horizons_seconds": [3600, 14400, 28800, 43200],
        "numerical_sensitivity_preserved": ["M4", "M12"],
        "gates_pending": [
            "partition_wall",
            "physical_affinity",
            "memory_guards",
            "numerical_scope",
            "artifact_integrity",
            "total_budget",
            "calendar",
            "environment_permissions",
        ],
        "scientific_reporting_eligible": False,
    }


def products(raw):
    historical, main = observed_rows(raw)
    pairs, scaling = comparisons(main)
    matrix, cpu = cpu_package()
    require(len(matrix) == 60, "cpu_matrix_count")
    require(
        sum(r["solver_limit_seconds"] for r in matrix) / 3600 == 720, "solver_budget"
    )
    require(
        sum(r["threads"] * r["solver_limit_seconds"] for r in matrix) / 3600 == 4464,
        "solver_core_budget",
    )
    require(
        sum(r["threads"] * r["wall_seconds"] for r in matrix) / 3600 == 4836,
        "reserved_budget",
    )
    output = {
        "seed42_main.csv": csv_bytes(main),
        "seed42_paired_speedups.csv": csv_bytes(pairs),
        "seed42_cpu_scaling.csv": csv_bytes(scaling),
        "cpu_60_jobs_proposed.csv": csv_bytes(matrix),
        "cpu_authorization_package.json": json_bytes(cpu),
        "summary.json": json_bytes(
            {
                "historical_rows_preserved": len(historical),
                "main_seed42_rows": len(main),
                "historical_only_seed43_44_rows": 60,
                "experimental_units": 10,
                "easy_main_rows": 90,
                "medium_main_rows": 60,
                "solver_reported_terminal_target": 97,
                "right_censored_terminal_target": 53,
                "numerically_sensitive_main_rows": 30,
                "solver_hours_seed42_measured": sum(
                    float(r["solver_seconds"]) for r in main
                )
                / 3600,
                "exact_optimality_claimed": False,
                "new_jobs": 0,
                "new_optimization_calls": 0,
                "new_training_runs": 0,
                "execution_authorized": False,
            }
        ),
    }
    # Reuse qualified preparation components, changing only the scenario denominator.
    # Historical /7 values stay in the original source, never relabelled as /5.
    costs = []
    for row in main:
        costs.append(
            {
                "cell_id": row["cell_id"],
                "method": row["method"],
                "seed": 42,
                "supervised_attempt_seconds": row["supervised_attempt_seconds"],
                "preparation_seconds": row["scoped_preparation_seconds"],
                "cold_scoped_scenario_seconds": row[
                    "scoped_cold_cost_scenario_seconds"
                ],
                "amortization_uses": 5,
                "amortized_scoped_scenario_seconds": float(
                    row["supervised_attempt_seconds"]
                )
                + float(row["scoped_preparation_seconds"]) / 5,
                "scope": "derived_reuse_scenario_not_independent_end_to_end_measurement",
            }
        )
    output["seed42_cost_scenarios.csv"] = csv_bytes(costs)
    output["manifest.json"] = json_bytes(
        {
            "source": "docs/evidence/pr86/final-210/campaign_results.csv",
            "source_sha256": SOURCE_SHA,
            "outputs": {name: digest(value) for name, value in sorted(output.items())},
            "historical_files_modified": False,
            "execution_authorized": False,
        }
    )
    return output


def build(directory=DEST, check=False):
    output = products(SOURCE.read_bytes())
    if not check:
        directory.mkdir(parents=True, exist_ok=True)
    for name, raw in output.items():
        target = directory / name
        if check or target.exists():
            require(target.read_bytes() == raw, "derived_output_changed:" + name)
        else:
            with target.open("xb") as stream:
                stream.write(raw)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps({"files_verified": len(build(check=args.check)), "new_jobs": 0}))
