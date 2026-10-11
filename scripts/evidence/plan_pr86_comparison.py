"""Generate the unapproved PR86 comparison manifest offline; never submit jobs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import audit_sprint_c_numeric as numeric
import e0_frozen_inference as frozen
import review_pr80_job3503 as review

ROOT = review.ROOT
PROTOCOL = "pr86_controlled_comparison_proposal_v1"
THREADS = (1, 2, 4, 8, 16)
METHODS = ("M0", "M1", "M2")
CHECKPOINT = "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028"
SOURCE_INFERENCE_SHA = (
    "8f8f0b3c9dc350422f7a36bdb6c46d338186274ebf629d14acb88ea0ecbf9c40"
)


def encoded(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def build():
    original = frozen.plan()
    model = original["models"]["mixed"]
    review.require(model["checkpoint_sha256"] == CHECKPOINT, "mixed_checkpoint_binding")
    review.require(
        model["checkpoint_selection"] == "minimum_validation_weighted_bce"
        and model["threshold_source"] == "maximum_validation_f1",
        "validation_selection_binding",
    )
    frozen.validate_return(
        (ROOT / "docs/evidence/e0/job3505-return.json").read_bytes(),
        SOURCE_INFERENCE_SHA,
    )
    selected = numeric.selected_parents(numeric.source_receipt())
    cells, groups, parents = [], [], []
    for parent_index, parent in enumerate(frozen.CASES):
        item = selected[parent]
        review.require(item["role"] == "test", "exposed_test_parent")
        alias = review.alias(parent)
        parents.append(
            {
                "parent": parent,
                "alias": alias,
                "role": "test",
                "historically_exposed": True,
                "model_sha256": item["mip_sha256_declared"],
                **{
                    key + "_sha256": item[key]["sha256"]
                    for key in ("graph", "root", "label")
                },
            }
        )
        for cap_index, threads in enumerate(THREADS):
            for seed in (42, 43, 44) if threads == 1 else (42,):
                group_id = f"{alias}-threads{threads}-seed{seed}"
                shift = (parent_index + cap_index + seed - 42) % 3
                order = list(METHODS[shift:] + METHODS[:shift])
                groups.append(
                    {
                        "group_id": group_id,
                        "parent": parent,
                        "threads": threads,
                        "seed": seed,
                        "method_order": order,
                        "physical_cores_requested": threads,
                        "job_wall_seconds": 14400,
                        "child_deadline_seconds": 3780,
                    }
                )
                for position, method in enumerate(order, start=1):
                    cells.append(
                        {
                            "cell_id": f"{group_id}-{method}",
                            "group_id": group_id,
                            "parent": parent,
                            "alias": alias,
                            "difficulty": parent.split("_")[1],
                            "method": method,
                            "threads": threads,
                            "seed": seed,
                            "method_order_position": position,
                            "time_limit_seconds": 3600,
                            "mip_gap_fraction": 1e-4,
                            "effective_objective_sense": "MINIMIZE",
                            "checkpoint_sha256": CHECKPOINT if method != "M0" else "",
                            "model_sha256": item["mip_sha256_declared"],
                            "state": "planned_not_executed",
                        }
                    )
    main_seconds = len(cells) * 3600
    main_core_seconds = sum(c["threads"] * 3600 for c in cells)
    reserved_main = sum(g["job_wall_seconds"] * g["threads"] for g in groups)
    budget = {
        "classification": "proposal_not_approval_or_duration_prediction",
        "main_solver_calls": len(cells),
        "root_preparation_calls_maximum": 10,
        "total_optimization_calls_maximum": len(cells) + 10,
        "main_solver_seconds_maximum": main_seconds,
        "root_solver_seconds_maximum": 6000,
        "main_solver_capacity_physical_core_seconds": main_core_seconds,
        "main_group_jobs_maximum": len(groups),
        "root_jobs_maximum": 10,
        "inference_jobs_maximum": 1,
        "total_jobs_maximum": len(groups) + 11,
        "root_job_wall_seconds_each": 1200,
        "inference_job_wall_seconds": 2400,
        "inference_gpus": 1,
        "inference_physical_cores": 4,
        "inference_forwards_maximum": 10,
        "total_sequential_job_wall_seconds_maximum": len(groups) * 14400 + 12000 + 2400,
        "main_reserved_physical_core_seconds_maximum": reserved_main,
        "total_reserved_physical_core_seconds_maximum": reserved_main
        + 12000
        + 4 * 2400,
        "reserved_gpu_seconds_maximum": 2400,
        "queues_included": False,
        "measured_resource_usage": False,
        "training_jobs": 0,
        "automatic_retries": 0,
    }
    plan = {
        "protocol_id": PROTOCOL,
        "state": "proposal_execution_blocked",
        "source_numeric_receipt_sha256": review.RETURN_SHA,
        "source_inference_receipt_sha256": SOURCE_INFERENCE_SHA,
        "parents": parents,
        "checkpoint": model,
        "checkpoint_choice": "mixed_cohort_scope_and_validation_provenance_not_solver_test_speed",
        "historically_untouched_test_claimed": False,
        "thread_caps": list(THREADS),
        "main_seed": 42,
        "repeat_seeds_at_one_thread_only": [43, 44],
        "method_semantics": {
            "M0": "unguided_control",
            "M1": "root_lp_matched_partial_start",
            "M2": "gnn_class_aware_partial_start",
        },
        "lp_matching": "same_support_cardinality_positive_count_not_same_variable_ids",
        "support": {
            "fraction": 0.1,
            "maximum": 20000,
            "unspecified_variables": "undefined_not_fixed",
            "no_positive_gnn": "abstain_follow_existing_policy",
        },
        "parameters": {"TimeLimit": 3600, "MIPGap": 1e-4, "SoftMemLimit": 48},
        "root_capture": {
            "seed": 42,
            "Threads": 1,
            "Presolve": 0,
            "NodeLimit": 1,
            "TimeLimit": 600,
            "policy": "first_optimal_root_MIPNODE_not_model_relax",
            "reuse": "one_fixed_preparation_per_parent_across_all_seeds_caps",
        },
        "scheduler": {
            "partition": "batch",
            "nodes": 1,
            "tasks": 1,
            "memory_mib": 65536,
            "exclusive": False,
            "requeue": False,
            "main_solver_gpus": 0,
            "root_gpus": 0,
            "affinity": "one_logical_cpu_per_requested_physical_core",
            "concurrent_jobs_maximum": 1,
        },
        "memory": {
            "solver_soft_decimal_gb": 48,
            "sampled_stop_bytes": 56 * 1024**3,
            "kernel_ram_cap_bytes_maximum": 64 * 1024**3,
            "loss_of_job_scoped_observation": "stop_preserve_pause_no_retry",
        },
        "groups": groups,
        "budget": budget,
        "resource_budget_approved": False,
        "solver_execution_admitted": False,
        "training_admitted": False,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "submissions_added": 0,
        "execution_gates": {
            "PR85_documentary_review_merged": False,
            "source_formulation_mapping_accepted": False,
            "all_ten_partial_start_bindings_qualified": False,
            "prospective_cost_instrumentation_qualified": False,
            "exact_installed_environment_parameters_bound": False,
            "exact_budget_explicitly_approved": False,
        },
        "execution_interface_included": False,
        "required_outputs": [
            "solver_cells.csv",
            "parent_paired_effects.csv",
            "preparation_costs.csv",
            "cpu_scaling.svg",
            "quality_at_horizon.svg",
            "cold_vs_amortized_cost.svg",
            "memory_by_method.svg",
            "claim_evidence_index.json",
        ],
    }
    review.require(len(cells) == 210 and len(groups) == 70, "matrix_cardinality")
    return plan, cells


def produce(output):
    plan, cells = build()
    output.mkdir(parents=True, exist_ok=False)
    (output / "plan.json").write_bytes(encoded(plan))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(cells[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(cells)
    (output / "planned_cells.csv").write_bytes(stream.getvalue().encode())
    manifest = {
        "protocol_id": PROTOCOL,
        "files": {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())},
        "planner_source_sha256_lf": digest(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ),
        "execution_authorized": False,
    }
    (output / "manifest.json").write_bytes(encoded(manifest))
    print(
        json.dumps(
            {
                "planned_cells": len(cells),
                "planned_main_groups": 70,
                "resource_budget_approved": False,
                "submissions_added": 0,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    produce(parser.parse_args().output)


if __name__ == "__main__":
    main()
