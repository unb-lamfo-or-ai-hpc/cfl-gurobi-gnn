"""Compile the prospective full PR94 matrix; standard library, no execution."""

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

CHECKPOINT = "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028"
PREPARATION_SOURCE = "c623fe858f62d8fa2a70eebf6f3aeee5692e8f90"
PREPARATION_PLAN = "b41953a81f48a91d73c8112bb6794ccce78e72c41ce6ddef7a28ff7e4c098a77"
PARENTS = {
    "easy": (0, 3, 6, 14, 27, 29),
    "medium": (0, 4, 7, 12, 5, 6, 9, 13, 20, 26),
}
METHODS = ("M0", "M1", "M2")
SEEDS = (42, 43, 44)
NEW = {"M5", "M6", "M9", "M13", "M20", "M26"}
FIELDS = (
    "cell_id",
    "group_id",
    "parent",
    "alias",
    "difficulty",
    "seed",
    "method",
    "presentation",
    "order_in_group",
    "lane",
    "threads",
    "time_limit_seconds",
    "model_sha256",
    "checkpoint_sha256",
    "effective_objective_sense",
    "new_solve",
    "scientific_reporting_eligible",
    "assigned_job_id",
)


def require(value, code):
    if not value:
        raise ValueError(code)


def encoded(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def compile_plan(cohort, historical_bindings):
    """Validate the frozen identities and derive groups without reading outcomes."""
    expected = {
        f"CFL_{difficulty}_instance_{number}": ("F" if difficulty == "easy" else "M")
        + str(number)
        for difficulty, numbers in PARENTS.items()
        for number in numbers
    }
    require(len(cohort) == 16, "cohort_count")
    rows = {row["parent"]: row for row in cohort}
    require(len(rows) == 16 and set(rows) == set(expected), "cohort_identity")
    historical = {row["parent"]: row for row in historical_bindings["parents"]}
    require(len(historical) == 10, "historical_binding_count")
    for parent, alias in expected.items():
        row = rows[parent]
        require(row["alias"] == alias, "alias")
        require(re.fullmatch(r"[0-9a-f]{64}", row["model_sha256"]), "model_hash")
        require(
            row["independent_untouched_generalization_claim"] == "false", "exposure"
        )
        if alias not in NEW:
            require(parent in historical, "historical_parent")
            binding = historical[parent]
            require(binding["model_sha256"] == row["model_sha256"], "historical_model")
            require(binding["checkpoint_sha256"] == CHECKPOINT, "checkpoint")
            for key in (
                "M1_assignment_sha256",
                "M2_assignment_sha256",
                "root_sha256",
                "graph_sha256",
                "private_starts_sha256",
            ):
                require(re.fullmatch(r"[0-9a-f]{64}", binding[key]), "artifact_hash")
    groups, cells = [], []
    parents = list(expected)
    for seed_index, seed in enumerate(SEEDS):
        for parent_index, parent in enumerate(parents):
            row = rows[parent]
            index = len(groups)
            lane = index % 4
            rotation = (parent_index + seed_index) % 3
            methods = METHODS[rotation:] + METHODS[:rotation]
            group_id = f"pr94-full-v2--{row['alias']}-t1-s{seed}"
            previous = groups[index - 4]["group_id"] if index >= 4 else None
            group = {
                "group_id": group_id,
                "parent": parent,
                "seed": seed,
                "lane": lane,
                "predecessor_group_id": previous,
                "dependency": "afterok_and_closed_predecessor_receipt",
                "methods": list(methods),
                "cells": [],
                "assigned_job_id": None,
                "new_preparation_required": row["alias"] in NEW,
            }
            for order, method in enumerate(methods):
                cell = {
                    "cell_id": group_id + "-" + method,
                    "group_id": group_id,
                    "parent": parent,
                    "alias": row["alias"],
                    "difficulty": row["difficulty"],
                    "seed": seed,
                    "method": method,
                    "presentation": {"M0": "B", "M1": "R", "M2": "G"}[method],
                    "order_in_group": order,
                    "lane": lane,
                    "threads": 1,
                    "time_limit_seconds": 3600,
                    "model_sha256": row["model_sha256"],
                    "checkpoint_sha256": CHECKPOINT,
                    "effective_objective_sense": "MINIMIZE",
                    "new_solve": True,
                    "scientific_reporting_eligible": False,
                    "assigned_job_id": None,
                }
                cells.append(cell)
                group["cells"].append(cell["cell_id"])
            groups.append(group)
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(cells)
    csv_bytes = text.getvalue().encode()
    plan = {
        "protocol_id": "pr94_full_matrix_v2_prospective",
        "author_direction_date": "2026-11-02",
        "design_decision": "fresh_144_replaces_conditional_90_reuse_plus_54_new",
        "cohort_sha256": hashlib.sha256(encoded(cohort)).hexdigest(),
        "historical_bindings_sha256": hashlib.sha256(
            encoded(historical_bindings)
        ).hexdigest(),
        "cells_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "parents": 16,
        "easy": 6,
        "medium": 10,
        "new_evaluations": 144,
        "historical_rows_counted_as_new": 0,
        "groups": groups,
        "learning": {
            "parents": 54,
            "split": [34, 10, 10],
            "checkpoint_sha256": CHECKPOINT,
            "training_calls": 0,
            "threshold": "0.9991843104362488",
        },
        "preparation": {
            "source": PREPARATION_SOURCE,
            "plan_sha256": PREPARATION_PLAN,
            "new_roots_maximum": 6,
            "new_forwards_maximum": 6,
            "installed_source_modified": False,
        },
        "resources": {
            "roots_jobs": 1,
            "roots_job_hours": 2,
            "guidance_jobs": 1,
            "guidance_job_hours": 1,
            "evaluation_jobs": 48,
            "evaluation_job_hours_each": 4,
            "total_jobs": 50,
            "optimizer_calls_maximum": 150,
            "optimizer_hours_ceiling": 145,
            "summed_reserved_job_hours": 195,
            "physical_core_hours_ceiling": 198,
            "reserved_V100_GPU_hours": 1,
            "RAM_GiB_each": 64,
            "RAM_GiB_hours": 12480,
            "evaluation_concurrency_ceiling": 4,
            "evaluation_RAM_GiB_peak_ceiling": 256,
            "evaluation_physical_core_peak_ceiling": 4,
            "evaluation_ideal_packed_hours_excluding_queue_and_reviews": 48,
            "evaluation_child_deadline_seconds": 3780,
            "storage_GiB_admission_floor": 80,
            "previous_working_storage_allowance_GiB": 64,
            "full_matrix_storage_bound_verified": False,
        },
        "execution_released": False,
        "dispatcher_implemented": False,
        "all_16_current_private_byte_preflights_received": False,
        "all_Start_bindings_reviewed": False,
        "assigned_job_ids": [],
        "no_automatic_retry_or_cancel": True,
        "M7_retained": True,
        "M4_M12_numerical_restrictions_retained": True,
        "reporting_eligible": False,
    }
    return plan, csv_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with (args.package / "cohort.csv").open(encoding="utf-8", newline="") as stream:
        cohort = list(csv.DictReader(stream))
    bindings = json.loads(
        (args.package / "historical-artifact-bindings.json").read_text()
    )
    plan, cells = compile_plan(cohort, bindings)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "planned-cells.csv").write_bytes(cells)
    (args.output / "plan.json").write_bytes(encoded(plan))


if __name__ == "__main__":
    main()
