"""Validation-only qualification of class-aware GNN partial MIP starts.

The held-out test parent set is frozen in the plan but is never executed or
read by this stage. Each optimization method receives a fresh Gurobi model.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from cfl_gnn.experiments.pr58_guidance import (
    METHODS,
    class_aware_gnn_assignments,
    matched_root_lp_assignments,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.pipelines.confirmation_execution import (
    checked,
    descriptor,
    error_reason,
    read_json,
    safe_path,
)
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold
from cfl_gnn.training.gasse_reconnected import (
    canonical_sha256,
    git_blob_sha1,
    validate_training_plan,
    write_json,
)


CONFIG = PROJECT_ROOT / "configs/experiments/pr58_validation_guidance_v1.json"
SPLIT = PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv"
PLAN_NAME = "pr58_validation_guidance_plan.json"
REPORT_NAME = "pr58_validation_guidance_report.json"
EXPECTED_TRAINING_CONTRACT = "432a42dab9f49f01a31d7b28f658bd14f7c50450ac2d83d1ae3102bcc12f0d40"
EXPECTED_CHECKPOINT_SHA = "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028"
EXPECTED_THRESHOLD = 0.9991843104362488
TRAINING_FILES = (
    "gasse_training_plan.json",
    "gasse_training_report.json",
    "training_epoch_metrics.csv",
    "best_model.pt",
    "pr57_54_training_audit.json",
    "evaluation_recovery/gasse_evaluation_plan.json",
    "evaluation_recovery/gasse_evaluation_report.json",
)
IMPLEMENTATIONS = (
    "experiments/pr58_guidance.py",
    "pipelines/pr58_validation_guidance.py",
    "graph/label_free_gurobi.py",
    "graph/gurobi_graph_artifact.py",
    "solvers/paired_partial_start.py",
    "models/gasse.py",
    "models/gasse_calibrated.py",
    "models/versioning.py",
    "validation/mathematical.py",
)


def implementation_hashes() -> dict[str, str]:
    return {
        name: sha256_file(PROJECT_ROOT / "src/cfl_gnn" / name)
        for name in IMPLEMENTATIONS
    }


def _read_policy() -> dict:
    policy = read_json(CONFIG)
    if (
        policy.get("protocol_id") != "pr58_validation_only_class_aware_partial_start_v1"
        or tuple(policy.get("methods", ())) != METHODS
        or policy.get("objective_sense") != "MINIMIZE"
        or policy.get("seed") != 42
        or policy.get("threads_per_run") != 1
        or policy.get("optimization_time_limit_seconds") != 3600
        or policy.get("coverage_fraction") != 0.1
        or policy.get("absolute_support_cap") != 20000
        or policy.get("qualification_partition") != "validation"
        or policy.get("test_outcomes_available_to_qualification") is not False
        or policy.get("target_labels_or_incumbents_allowed_as_guidance_input") is not False
        or policy.get("development_only") is not True
        or policy.get("scientific_reporting_eligible") is not False
    ):
        raise ValueError("PR58 policy contract changed")
    return policy


def _validate_training(training_dir: Path) -> tuple[dict, dict, dict]:
    plan = read_json(training_dir / "gasse_training_plan.json")
    report = read_json(training_dir / "gasse_training_report.json")
    audit = read_json(training_dir / "pr57_54_training_audit.json")
    validate_training_plan(plan)
    if (
        plan.get("contract_sha256") != EXPECTED_TRAINING_CONTRACT
        or plan.get("partition_counts") != {"train": 34, "validation": 10, "test": 10}
        or report.get("training_contract_sha256") != EXPECTED_TRAINING_CONTRACT
        or report.get("gate_status") != "passed"
        or report.get("epochs_completed") != 100
        or report.get("test_graphs_loaded") != 0
        or report.get("selected_probability_threshold") != EXPECTED_THRESHOLD
        or report.get("threshold_source") != "maximum_validation_f1"
        or report.get("outputs", {}).get("checkpoint", {}).get("sha256")
        != EXPECTED_CHECKPOINT_SHA
        or audit.get("gate_status") != "passed"
        or audit.get("failures") != []
        or not audit.get("checks")
        or not all(value is True for value in audit["checks"].values())
        or audit.get("summary", {}).get("checkpoint_sha256") != EXPECTED_CHECKPOINT_SHA
        or audit.get("summary", {}).get("training_contract_sha256")
        != EXPECTED_TRAINING_CONTRACT
    ):
        raise ValueError("frozen PR57 training/evaluation evidence is invalid")
    for name in TRAINING_FILES:
        path = training_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing frozen training input: {name}")
    if sha256_file(training_dir / "best_model.pt") != EXPECTED_CHECKPOINT_SHA:
        raise ValueError("frozen checkpoint SHA-256 changed")
    if (
        report.get("legacy_gasse_git_blob_sha1")
        != git_blob_sha1(PROJECT_ROOT / "src/cfl_gnn/models/gasse.py")
    ):
        raise ValueError("checkpoint model implementation changed")
    return plan, report, audit


def _split_sets() -> tuple[list[str], list[str]]:
    records = [record for record in read_manifest(SPLIT) if record.difficulty == "medium"]
    validation = sorted(
        record.source_instance_id
        for record in records
        if role_for_fold(record.fold, 0) == "validation"
    )
    test = sorted(
        record.source_instance_id
        for record in records
        if role_for_fold(record.fold, 0) == "test"
    )
    return validation, test


def build_plan(training_dir: str | Path, mip_root: str | Path) -> dict:
    training_root = Path(training_dir).resolve()
    source_root = Path(mip_root).resolve()
    training_plan, training_report, _ = _validate_training(training_root)
    policy = _read_policy()
    validation, test = _split_sets()
    if validation != sorted(policy["qualification_parent_ids"]):
        raise ValueError("qualification set is not the complete medium validation fold")
    if test != sorted(policy["frozen_test_parent_ids"]):
        raise ValueError("frozen test set is not the complete medium test fold")
    records = {row["parent_instance_id"]: row for row in training_plan["records"]}
    targets = []
    for task_index, identity in enumerate(policy["qualification_parent_ids"]):
        relative = f"CFL_medium_instance/LP/{identity}.lp.gz"
        mip = safe_path(source_root, relative)
        if not mip.is_file():
            raise ValueError(f"missing validation MIP: {identity}")
        trained_record = records.get(identity)
        targets.append(
            {
                "task_index": task_index,
                "source_instance_id": identity,
                "role": "validation",
                "was_present_in_training_plan": trained_record is not None,
                "was_used_for_gradient_updates": False,
                "method_order": [METHODS[(task_index + offset) % len(METHODS)] for offset in range(len(METHODS))],
                "mip": descriptor(source_root, mip),
            }
        )
    frozen_test = []
    for identity in policy["frozen_test_parent_ids"]:
        mip = safe_path(source_root, f"CFL_medium_instance/LP/{identity}.lp.gz")
        if not mip.is_file():
            raise ValueError(f"missing frozen test MIP: {identity}")
        frozen_test.append(
            {
                "source_instance_id": identity,
                "role": "test",
                "not_executed_in_pr58": True,
                "mip": descriptor(source_root, mip),
            }
        )
    payload = {
        "schema_version": 1,
        "stage": "validation_only_native_guidance_qualification",
        "policy": policy,
        "policy_sha256": sha256_file(CONFIG),
        "split_sha256": sha256_file(SPLIT),
        "implementation_sha256": implementation_hashes(),
        "training_contract_sha256": EXPECTED_TRAINING_CONTRACT,
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "probability_threshold": EXPECTED_THRESHOLD,
        "architecture": training_plan["protocol"]["architecture"],
        "training_inputs": {
            name: descriptor(training_root, training_root / name) for name in TRAINING_FILES
        },
        "targets": targets,
        "frozen_test_targets": frozen_test,
        "target_labels_loaded": False,
        "test_outcomes_loaded": False,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {**payload, "contract_sha256": canonical_sha256(payload), "contract_valid": True}


def validate_plan(plan: dict) -> None:
    payload = {key: value for key, value in plan.items() if key not in {"contract_sha256", "contract_valid"}}
    if (
        plan.get("contract_valid") is not True
        or canonical_sha256(payload) != plan.get("contract_sha256")
        or plan.get("policy_sha256") != sha256_file(CONFIG)
        or plan.get("split_sha256") != sha256_file(SPLIT)
        or plan.get("implementation_sha256") != implementation_hashes()
        or any(target.get("role") != "validation" for target in plan.get("targets", []))
        or any(target.get("not_executed_in_pr58") is not True for target in plan.get("frozen_test_targets", []))
    ):
        raise ValueError("PR58 plan, implementation, or split changed")


def load_plan(plan_dir: str | Path) -> dict:
    plan = read_json(Path(plan_dir) / PLAN_NAME)
    validate_plan(plan)
    return plan


def _write_gzip(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            stream.write(json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8"))


def _read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def prepare_parent(plan: dict, target: dict, training_dir: Path, mip_root: Path, parent_dir: Path, device: str) -> dict:
    import torch

    from cfl_gnn.graph.gurobi_graph_artifact import capture_root_relaxation, write_root_artifact
    from cfl_gnn.graph.label_free_gurobi import build_features, predict

    started = perf_counter()
    for item in plan["training_inputs"].values():
        checked(training_dir, item)
    checkpoint = checked(training_dir, plan["training_inputs"]["best_model.pt"])
    mip = checked(mip_root, target["mip"])
    root = capture_root_relaxation(
        mip,
        expected_mip_sha256=target["mip"]["sha256"],
        time_limit_seconds=plan["policy"]["root_capture_time_limit_seconds"],
        threads=1,
        seed=42,
        presolve=0,
    )
    graph, binary_order, feature_audit = build_features(mip, target["mip"]["sha256"], root)
    predictions = predict(
        graph,
        binary_order,
        checkpoint,
        plan["architecture"],
        plan["probability_threshold"],
        device,
    )
    gnn = class_aware_gnn_assignments(
        predictions,
        fraction=plan["policy"]["coverage_fraction"],
        absolute_cap=plan["policy"]["absolute_support_cap"],
        abstain_without_positive=plan["policy"]["abstain_without_gnn_positive"],
    )
    indices = {name: index for index, name in enumerate(root["variable_names"])}
    root_binary_values = [root["relaxation_vector"][indices[name]] for name in binary_order]
    baseline = matched_root_lp_assignments(
        binary_order,
        root_binary_values,
        support=gnn["selected_support"],
        positive_assignments=gnn["positive_assignments"],
    )
    write_root_artifact(parent_dir / "root_features.json.gz", root)
    torch.save(graph, parent_dir / "label_free_graph.pt")
    prediction_payload = {
        "schema_version": 1,
        "contract_sha256": plan["contract_sha256"],
        "source_instance_id": target["source_instance_id"],
        "role": target["role"],
        "target_labels_loaded": False,
        "test_outcomes_loaded": False,
        "checkpoint_sha256": plan["checkpoint_sha256"],
        "probability_threshold": plan["probability_threshold"],
        "binary_order_sha256": feature_audit["binary_order_sha256"],
        "predictions": predictions,
    }
    _write_gzip(parent_dir / "predictions.json.gz", prediction_payload)
    for name, selection in ((METHODS[1], baseline), (METHODS[2], gnn)):
        _write_gzip(
            parent_dir / f"{name}.assignments.json.gz",
            {
                "schema_version": 1,
                "contract_sha256": plan["contract_sha256"],
                "source_instance_id": target["source_instance_id"],
                "method": name,
                "target_labels_loaded": False,
                **selection,
            },
        )
    artifacts = {
        path.name: descriptor(parent_dir, path)
        for path in sorted(parent_dir.iterdir())
        if path.is_file()
    }
    result = {
        "gate_status": "passed" if not gnn["abstained"] else "inconclusive",
        "reason_code": gnn["reason_code"],
        "contract_sha256": plan["contract_sha256"],
        "source_instance_id": target["source_instance_id"],
        "role": target["role"],
        "feature_audit": feature_audit,
        "gnn_selection": {key: value for key, value in gnn.items() if key != "assignments"},
        "root_lp_selection": {key: value for key, value in baseline.items() if key != "assignments"},
        "artifacts": artifacts,
        "preparation_wall_time_seconds": perf_counter() - started,
    }
    write_json(parent_dir / "preparation.json", result)
    return result


def _load_assignments(parent_dir: Path, plan: dict, target: dict, method: str) -> list[dict]:
    preparation = read_json(parent_dir / "preparation.json")
    name = f"{method}.assignments.json.gz"
    artifact = checked(parent_dir, preparation["artifacts"][name])
    payload = _read_gzip(artifact)
    assignments = payload.get("assignments")
    if (
        payload.get("contract_sha256") != plan["contract_sha256"]
        or payload.get("source_instance_id") != target["source_instance_id"]
        or payload.get("method") != method
        or payload.get("target_labels_loaded") is not False
        or not isinstance(assignments, list)
        or canonical_sha256(assignments) != payload.get("assignment_sha256")
    ):
        raise ValueError("partial-start assignment artifact changed")
    return assignments


def worker(plan_dir: Path, mip_root: Path, run_root: Path, task_index: int, method: str) -> bool:
    from cfl_gnn.solvers.paired_partial_start import solve

    plan = load_plan(plan_dir)
    target = plan["targets"][task_index]
    parent_dir = run_root / target["source_instance_id"]
    destination = parent_dir / f"{method}.json"
    if destination.exists():
        raise ValueError("method result already exists; preserve the prior attempt")
    try:
        mip = checked(mip_root, target["mip"])
        if method == METHODS[0]:
            result = solve(
                mip,
                target["mip"]["sha256"],
                [],
                "unguided_control",
                budget=plan["policy"]["optimization_time_limit_seconds"],
                solution_path=parent_dir / f"{method}.solution.json.gz",
            )
        else:
            assignments = _load_assignments(parent_dir, plan, target, method)
            result = solve(
                mip,
                target["mip"]["sha256"],
                [],
                "partial_mip_start",
                budget=plan["policy"]["optimization_time_limit_seconds"],
                solution_path=parent_dir / f"{method}.solution.json.gz",
                preselected_assignments=assignments,
                reported_method=method,
            )
        result.update(
            contract_sha256=plan["contract_sha256"],
            source_instance_id=target["source_instance_id"],
            role=target["role"],
        )
    except Exception as error:
        result = {
            "gate_status": "failed",
            "reason_code": "method_execution_failed",
            "error_type": type(error).__name__,
            "reason_detail": error_reason(error),
            "contract_sha256": plan["contract_sha256"],
            "source_instance_id": target["source_instance_id"],
            "role": target["role"],
            "method": method,
        }
    write_json(destination, result)
    return result["gate_status"] == "passed"


def run_parent(plan_dir: Path, training_dir: Path, mip_root: Path, run_root: Path, task_index: int, device: str) -> bool:
    plan = load_plan(plan_dir)
    if build_plan(training_dir, mip_root) != plan:
        raise ValueError("PR58 source inputs differ from the frozen plan")
    target = plan["targets"][task_index]
    parent_dir = run_root / target["source_instance_id"]
    parent_dir.mkdir(parents=True, exist_ok=False)
    try:
        preparation = prepare_parent(plan, target, training_dir, mip_root, parent_dir, device)
    except Exception as error:
        write_json(
            parent_dir / "preparation_failure.json",
            {
                "gate_status": "failed",
                "contract_sha256": plan["contract_sha256"],
                "source_instance_id": target["source_instance_id"],
                "error_type": type(error).__name__,
                "reason_detail": error_reason(error),
            },
        )
        return False
    if preparation["gate_status"] != "passed":
        return False
    workers = []
    for method in target["method_order"]:
        started = perf_counter()
        command = [
            sys.executable,
            "-m",
            "cfl_gnn.cli.run_pr58_validation_guidance",
            "worker",
            "--plan_dir",
            str(plan_dir),
            "--mip_root",
            str(mip_root),
            "--run_root",
            str(run_root),
            "--task_index",
            str(task_index),
            "--method",
            method,
        ]
        with (parent_dir / f"{method}.log").open("wb") as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        workers.append(
            {
                "method": method,
                "returncode": process.returncode,
                "process_wall_time_seconds": perf_counter() - started,
            }
        )
    receipt = {
        "contract_sha256": plan["contract_sha256"],
        "source_instance_id": target["source_instance_id"],
        "role": "validation",
        "method_order": target["method_order"],
        "workers": workers,
        "artifacts": {
            path.name: descriptor(parent_dir, path)
            for path in sorted(parent_dir.iterdir())
            if path.is_file() and path.suffix != ".log"
        },
    }
    write_json(parent_dir / "parent_receipt.json", receipt)
    return all(item["returncode"] == 0 for item in workers)


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def audit(plan_dir: Path, run_root: Path, output_dir: Path) -> dict:
    plan = load_plan(plan_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    outcomes: list[dict] = []
    effects: list[dict] = []
    statuses: list[dict] = []
    failures: list[dict] = []
    nonabstained = 0
    for target in plan["targets"]:
        identity = target["source_instance_id"]
        parent_dir = run_root / identity
        try:
            receipt = read_json(parent_dir / "parent_receipt.json")
            preparation = read_json(parent_dir / "preparation.json")
            if (
                receipt.get("contract_sha256") != plan["contract_sha256"]
                or receipt.get("source_instance_id") != identity
                or receipt.get("role") != "validation"
                or receipt.get("method_order") != target["method_order"]
                or [item["method"] for item in receipt.get("workers", [])] != target["method_order"]
                or any(item.get("returncode") != 0 for item in receipt.get("workers", []))
            ):
                raise ValueError("parent execution receipt changed or contains a failed worker")
            for item in receipt.get("artifacts", {}).values():
                checked(parent_dir, item)
            if preparation.get("gnn_selection", {}).get("abstained") is not False:
                raise ValueError("GNN selection abstained on this validation parent")
            nonabstained += 1
            if (
                preparation["gnn_selection"]["selected_support"]
                != preparation["root_lp_selection"]["selected_support"]
                or preparation["gnn_selection"]["positive_assignments"]
                != preparation["root_lp_selection"]["positive_assignments"]
            ):
                raise ValueError("root-LP baseline is not support/class matched")
            results = {}
            for method in METHODS:
                status = {
                    "source_instance_id": identity,
                    "role": "validation",
                    "method": method,
                    "artifact_valid": False,
                }
                statuses.append(status)
                result = read_json(parent_dir / f"{method}.json")
                if (
                    result.get("gate_status") != "passed"
                    or result.get("contract_sha256") != plan["contract_sha256"]
                    or result.get("source_instance_id") != identity
                    or result.get("role") != "validation"
                    or result.get("method") != method
                    or result.get("mip_sha256") != target["mip"]["sha256"]
                    or result.get("mathematical_model_unchanged") is not True
                    or result.get("fresh_model") is not True
                ):
                    raise ValueError(f"invalid method result: {method}")
                timing = result["timing"]
                if any(
                    not math.isfinite(float(timing[name])) or float(timing[name]) < -1e-6
                    for name in (
                        "total_wall_time_seconds",
                        "data_read_wall_time_seconds",
                        "model_build_wall_time_seconds",
                        "model_optimize_wall_time_seconds",
                    )
                ):
                    raise ValueError(f"invalid timing evidence: {method}")
                if method == METHODS[0] and result["start"]["submitted_assignments"] != 0:
                    raise ValueError("unguided control received a start")
                if method != METHODS[0] and result["start"]["submitted_assignments"] <= 0:
                    raise ValueError("guided method received no partial start")
                solve = result["solve"]
                if solve["feasible_solution"]:
                    solution = result.get("solution_artifact")
                    if (
                        not isinstance(solution, dict)
                        or sha256_file(parent_dir / solution["file_name"]) != solution["sha256"]
                        or result.get("independent_feasibility", {}).get("valid") is not True
                    ):
                        raise ValueError(f"solution evidence mismatch: {method}")
                outcomes.append(
                    {
                        "source_instance_id": identity,
                        "role": "validation",
                        "method": method,
                        "solve_status_code": solve["solve_status_code"],
                        "right_censored": solve["right_censored"],
                        "feasible_solution": solve["feasible_solution"],
                        "primal": solve["primal"],
                        "dual": solve["dual"],
                        "terminal_mip_gap_relative": solve["terminal_mip_gap_relative"],
                        "first_observed_gap_le_0.1_seconds": solve["first_observed_gap_times_seconds"]["0.1"],
                        "model_optimize_wall_time_seconds": timing["model_optimize_wall_time_seconds"],
                        "total_wall_time_seconds": timing["total_wall_time_seconds"],
                        "submitted_assignments": result["start"]["submitted_assignments"],
                        "positive_assignments": result["start"]["positive_assignments"],
                        "start_status": result["start"]["status"],
                    }
                )
                results[method] = result
                status["artifact_valid"] = True
            control = results[METHODS[0]]
            if any(
                results[method]["parameters"] != control["parameters"]
                or results[method]["solver_version"] != control["solver_version"]
                or results[method]["mathematical_signature_sha256"]
                != control["mathematical_signature_sha256"]
                for method in METHODS[1:]
            ):
                raise ValueError("paired solver controls differ")
            control_gap = control["solve"]["terminal_mip_gap_relative"]
            for method in METHODS[1:]:
                guided_gap = results[method]["solve"]["terminal_mip_gap_relative"]
                effects.append(
                    {
                        "source_instance_id": identity,
                        "role": "validation",
                        "method": method,
                        "terminal_gap_difference_guided_minus_control": (
                            None if control_gap is None or guided_gap is None else guided_gap - control_gap
                        ),
                        "optimize_time_difference_guided_minus_control": (
                            results[method]["timing"]["model_optimize_wall_time_seconds"]
                            - control["timing"]["model_optimize_wall_time_seconds"]
                        ),
                        "control_first_gap_le_0.1_seconds": control["solve"]["first_observed_gap_times_seconds"]["0.1"],
                        "guided_first_gap_le_0.1_seconds": results[method]["solve"]["first_observed_gap_times_seconds"]["0.1"],
                    }
                )
        except Exception as error:
            failures.append(
                {
                    "source_instance_id": identity,
                    "role": "validation",
                    "error_type": type(error).__name__,
                    "reason_detail": error_reason(error),
                }
            )
    gnn_effects = [row for row in effects if row["method"] == METHODS[2]]
    gap_differences = [
        row["terminal_gap_difference_guided_minus_control"]
        for row in gnn_effects
        if row["terminal_gap_difference_guided_minus_control"] is not None
    ]
    gate = plan["policy"]["qualification_gate"]
    gap_wins = sum(value < 0.0 for value in gap_differences)
    large_regressions = sum(value > gate["large_regression_relative_gap"] for value in gap_differences)
    median_gap = _median(gap_differences)
    qualification_checks = {
        "all_six_validation_parents_valid": len(gnn_effects) >= gate["minimum_valid_parents"] and not failures,
        "all_six_gnn_starts_nonabstained": nonabstained >= gate["minimum_nonabstained_parents"],
        "minimum_four_terminal_gap_wins": gap_wins >= gate["minimum_gap_wins_vs_control"],
        "median_terminal_gap_not_worse": median_gap is not None
        and median_gap <= gate["maximum_median_gap_difference_guided_minus_control"],
        "at_most_one_large_gap_regression": large_regressions <= gate["maximum_large_regressions"],
        "test_outcomes_not_loaded": plan["test_outcomes_loaded"] is False,
    }
    authorized = all(qualification_checks.values())
    for filename, rows in (
        ("per_method_outcomes.json", outcomes),
        ("paired_effects.json", effects),
        ("per_method_status.json", statuses),
    ):
        write_json(output_dir / filename, {"records": rows})
    for filename, rows in (("per_method_outcomes.csv", outcomes), ("paired_effects.csv", effects)):
        with (output_dir / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["source_instance_id"])
            writer.writeheader()
            writer.writerows(rows)
    report = {
        "schema_version": 1,
        "contract_sha256": plan["contract_sha256"],
        "gate_status": "passed" if len(outcomes) == 18 and not failures else "failed",
        "probe_completed": True,
        "summary": {
            "planned_validation_parents": 6,
            "valid_validation_parents": len(gnn_effects),
            "planned_method_runs": 18,
            "valid_method_runs": len(outcomes),
            "gnn_gap_wins_vs_control": gap_wins,
            "gnn_large_gap_regressions": large_regressions,
            "gnn_median_gap_difference_guided_minus_control": median_gap,
        },
        "qualification_checks": qualification_checks,
        "failures": failures,
        "eligibility": {
            "test_benchmark_authorized": authorized,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "next_gate": "held_out_six_medium_paired_benchmark" if authorized else "report_negative_validation_qualification",
            "test_parent_ids": plan["policy"]["frozen_test_parent_ids"],
        },
        "outputs": {
            path.name: descriptor(output_dir, path)
            for path in sorted(output_dir.iterdir())
            if path.is_file()
        },
    }
    write_json(output_dir / REPORT_NAME, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "parent", "worker", "audit"))
    parser.add_argument("--training_dir", type=Path)
    parser.add_argument("--mip_root", type=Path)
    parser.add_argument("--plan_dir", type=Path, required=True)
    parser.add_argument("--run_root", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--task_index", type=int, choices=range(6))
    parser.add_argument("--method", choices=METHODS)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = parser.parse_args(argv)
    required = {
        "plan": ("training_dir", "mip_root"),
        "parent": ("training_dir", "mip_root", "run_root", "task_index"),
        "worker": ("mip_root", "run_root", "task_index", "method"),
        "audit": ("run_root", "output_dir"),
    }
    if any(getattr(args, name) is None for name in required[args.command]):
        parser.error("required command-specific argument missing")
    try:
        if args.command == "plan":
            plan = build_plan(args.training_dir, args.mip_root)
            args.plan_dir.mkdir(parents=True, exist_ok=False)
            write_json(args.plan_dir / PLAN_NAME, plan)
            print(
                f"[INFO] contract={plan['contract_sha256']} | validation_parents=6 | "
                "test_parents_frozen=6 | solver_runs=0"
            )
            ok = True
        elif args.command == "parent":
            ok = run_parent(
                args.plan_dir,
                args.training_dir,
                args.mip_root,
                args.run_root,
                args.task_index,
                args.device,
            )
        elif args.command == "worker":
            ok = worker(
                args.plan_dir,
                args.mip_root,
                args.run_root,
                args.task_index,
                args.method,
            )
        else:
            report = audit(args.plan_dir, args.run_root, args.output_dir)
            print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
            ok = report["gate_status"] == "passed"
        return 0 if ok else 1
    except Exception as error:
        print(f"[ERROR] {type(error).__name__}: {error_reason(error)}; preserve outputs for review")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
