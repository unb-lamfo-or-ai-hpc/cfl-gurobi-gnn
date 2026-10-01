"""Execute the frozen PR59 held-out medium guidance benchmark.

PR58 selected and qualified the intervention exclusively on validation
parents. This stage evaluates the unchanged intervention once on the frozen
test parents. Benchmark completion depends on artifact and pairing integrity,
never on whether the learned intervention improves an outcome.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from cfl_gnn.experiments.pr58_guidance import METHODS
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.pipelines.confirmation_execution import (
    checked,
    descriptor,
    error_reason,
    read_json,
    safe_path,
)
from cfl_gnn.pipelines.pr58_validation_guidance import (
    _load_assignments,
    _split_sets,
    _validate_training,
    prepare_parent,
)
from cfl_gnn.training.gasse_reconnected import canonical_sha256, write_json


CONFIG = PROJECT_ROOT / "configs/experiments/pr59_heldout_guidance_v1.json"
SPLIT = PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv"
PLAN_NAME = "pr59_heldout_guidance_plan.json"
REPORT_NAME = "pr59_heldout_guidance_report.json"
AUDIT_OUTPUT_NAMES = (
    "paired_effects.csv",
    "paired_effects.json",
    "per_method_outcomes.csv",
    "per_method_outcomes.json",
    "per_method_status.json",
)
EXPECTED_VALIDATION_CONTRACT = (
    "6b37643a6364e9d25c272b04b96575de9ee29a17c54d55e14153e376e1cd7758"
)
EXPECTED_VALIDATION_OUTPUTS = {
    "paired_effects.csv": "63c668dbfdcaab8705b865014b17c1f72f30b0a4785d4f6f5ba214e8c14e7800",
    "paired_effects.json": "a09ebee9546b9012377e3c33a0c4e98e920b5a01bbc31f1838ccb0dcd6090d9c",
    "per_method_outcomes.csv": "f239bbce99e668eeb281b1c48efb58b0ae799eb3ce77138b1d47f0270481749e",
    "per_method_outcomes.json": "44b91d0d9d48318b8ae38f30375e00927f3fce0a38f8cf6999a0edf3ae3496be",
    "per_method_status.json": "2a8eebef1c191d16dfb004deb421885c1599de158652993df10f53c879e2d85e",
}
EXPECTED_VALIDATION_PARENTS = {
    "CFL_medium_instance_5",
    "CFL_medium_instance_6",
    "CFL_medium_instance_11",
    "CFL_medium_instance_14",
    "CFL_medium_instance_17",
    "CFL_medium_instance_19",
}
EXPECTED_TEST_PARENTS = {
    "CFL_medium_instance_0",
    "CFL_medium_instance_4",
    "CFL_medium_instance_7",
    "CFL_medium_instance_9",
    "CFL_medium_instance_12",
    "CFL_medium_instance_20",
}
IMPLEMENTATIONS = (
    "experiments/pr58_guidance.py",
    "pipelines/pr58_validation_guidance.py",
    "pipelines/pr59_heldout_guidance.py",
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
    analysis = policy.get("analysis_policy", {})
    if (
        policy.get("protocol_id")
        != "pr59_frozen_heldout_class_aware_partial_start_v1"
        or tuple(policy.get("methods", ())) != METHODS
        or policy.get("objective_sense") != "MINIMIZE"
        or policy.get("seed") != 42
        or policy.get("threads_per_run") != 1
        or policy.get("optimization_time_limit_seconds") != 3600
        or policy.get("root_capture_time_limit_seconds") != 600
        or policy.get("coverage_fraction") != 0.1
        or policy.get("absolute_support_cap") != 20000
        or policy.get("benchmark_partition") != "test"
        or set(policy.get("benchmark_parent_ids", ())) != EXPECTED_TEST_PARENTS
        or set(policy.get("qualification_parent_ids", ()))
        != EXPECTED_VALIDATION_PARENTS
        or policy.get("policy_locked_before_test_execution") is not True
        or policy.get("test_outcomes_may_select_or_modify_policy") is not False
        or policy.get("target_labels_or_incumbents_allowed_as_guidance_input")
        is not False
        or analysis.get("completion_gate_depends_only_on_execution_integrity")
        is not True
        or analysis.get("favorable_outcome_required_for_completion") is not False
        or analysis.get("policy_reselection_after_test") is not False
        or policy.get("development_only") is not True
        or policy.get("scientific_reporting_eligible") is not False
    ):
        raise ValueError("PR59 held-out policy contract changed")
    return policy


def _validation_authorization(validation_dir: Path) -> tuple[dict, dict[str, dict]]:
    report_path = validation_dir / "pr58_validation_guidance_report.json"
    report = read_json(report_path)
    checks = report.get("qualification_checks", {})
    decision = report.get("decision", {})
    eligibility = report.get("eligibility", {})
    summary = report.get("summary", {})
    if (
        report.get("contract_sha256") != EXPECTED_VALIDATION_CONTRACT
        or report.get("gate_status") != "passed"
        or report.get("probe_completed") is not True
        or report.get("failures") != []
        or not checks
        or not all(value is True for value in checks.values())
        or eligibility.get("test_benchmark_authorized") is not True
        or eligibility.get("development_only") is not True
        or eligibility.get("scientific_reporting_eligible") is not False
        or decision.get("next_gate") != "held_out_six_medium_paired_benchmark"
        or set(decision.get("test_parent_ids", ())) != EXPECTED_TEST_PARENTS
        or summary.get("planned_validation_parents") != 6
        or summary.get("valid_validation_parents") != 6
        or summary.get("planned_method_runs") != 18
        or summary.get("valid_method_runs") != 18
        or summary.get("gnn_gap_wins_vs_control") != 4
        or summary.get("gnn_large_gap_regressions") != 1
        or not math.isclose(
            float(summary.get("gnn_median_gap_difference_guided_minus_control")),
            -0.012235269305291743,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
    ):
        raise ValueError("PR58 validation did not authorize the frozen test benchmark")
    descriptors = {
        "pr58_validation_guidance_report.json": descriptor(
            validation_dir, report_path
        )
    }
    declared = report.get("outputs", {})
    for name, expected_sha in EXPECTED_VALIDATION_OUTPUTS.items():
        path = validation_dir / name
        if (
            declared.get(name, {}).get("relative_path") != name
            or declared.get(name, {}).get("sha256") != expected_sha
            or sha256_file(path) != expected_sha
        ):
            raise ValueError(f"PR58 validation output changed: {name}")
        descriptors[name] = descriptor(validation_dir, path)
    outcomes = read_json(validation_dir / "per_method_outcomes.json").get("records", [])
    if (
        len(outcomes) != 18
        or {row.get("source_instance_id") for row in outcomes}
        != EXPECTED_VALIDATION_PARENTS
        or any(row.get("role") != "validation" for row in outcomes)
    ):
        raise ValueError("PR58 validation cohort or cardinality changed")
    return report, descriptors


def build_plan(
    training_dir: str | Path,
    validation_audit_dir: str | Path,
    mip_root: str | Path,
) -> dict:
    training_root = Path(training_dir).resolve()
    validation_root = Path(validation_audit_dir).resolve()
    source_root = Path(mip_root).resolve()
    training_plan, training_report, _ = _validate_training(training_root)
    validation_report, authorization_inputs = _validation_authorization(validation_root)
    policy = _read_policy()
    validation, test = _split_sets()
    if set(validation) != EXPECTED_VALIDATION_PARENTS:
        raise ValueError("validation population changed after policy qualification")
    if test != sorted(policy["benchmark_parent_ids"]):
        raise ValueError("held-out benchmark is not the complete medium test fold")
    records = {row["parent_instance_id"]: row for row in training_plan["records"]}
    targets = []
    for task_index, identity in enumerate(policy["benchmark_parent_ids"]):
        relative = f"CFL_medium_instance/LP/{identity}.lp.gz"
        mip = safe_path(source_root, relative)
        if not mip.is_file():
            raise ValueError(f"missing held-out test MIP: {identity}")
        trained_record = records.get(identity)
        if trained_record is None or trained_record.get("role") != "test":
            raise ValueError(f"training plan does not freeze test membership: {identity}")
        targets.append(
            {
                "task_index": task_index,
                "source_instance_id": identity,
                "role": "test",
                "was_present_in_training_plan": True,
                "was_used_for_gradient_updates": False,
                "was_used_for_policy_qualification": False,
                "method_order": [
                    METHODS[(task_index + offset) % len(METHODS)]
                    for offset in range(len(METHODS))
                ],
                "mip": descriptor(source_root, mip),
            }
        )
    payload = {
        "schema_version": 1,
        "stage": "frozen_held_out_native_guidance_benchmark",
        "policy": policy,
        "policy_sha256": sha256_file(CONFIG),
        "split_sha256": sha256_file(SPLIT),
        "implementation_sha256": implementation_hashes(),
        "training_contract_sha256": training_plan["contract_sha256"],
        "checkpoint_sha256": training_report["outputs"]["checkpoint"]["sha256"],
        "probability_threshold": training_report["selected_probability_threshold"],
        "architecture": training_plan["protocol"]["architecture"],
        "validation_authorization_contract_sha256": validation_report[
            "contract_sha256"
        ],
        "validation_authorization_inputs": authorization_inputs,
        "targets": targets,
        "target_labels_loaded": False,
        "source_incumbents_loaded": False,
        "policy_locked_before_test_execution": True,
        "test_outcomes_used_for_policy_selection": False,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **payload,
        "contract_sha256": canonical_sha256(payload),
        "contract_valid": True,
    }


def validate_plan(plan: dict) -> None:
    payload = {
        key: value
        for key, value in plan.items()
        if key not in {"contract_sha256", "contract_valid"}
    }
    identities = {target.get("source_instance_id") for target in plan.get("targets", [])}
    if (
        plan.get("contract_valid") is not True
        or canonical_sha256(payload) != plan.get("contract_sha256")
        or plan.get("policy_sha256") != sha256_file(CONFIG)
        or plan.get("split_sha256") != sha256_file(SPLIT)
        or plan.get("implementation_sha256") != implementation_hashes()
        or plan.get("validation_authorization_contract_sha256")
        != EXPECTED_VALIDATION_CONTRACT
        or identities != EXPECTED_TEST_PARENTS
        or len(plan.get("targets", [])) != 6
        or any(target.get("role") != "test" for target in plan.get("targets", []))
        or plan.get("policy_locked_before_test_execution") is not True
        or plan.get("test_outcomes_used_for_policy_selection") is not False
    ):
        raise ValueError("PR59 plan, implementation, split, or frozen cohort changed")


def load_plan(plan_dir: str | Path) -> dict:
    plan = read_json(Path(plan_dir) / PLAN_NAME)
    validate_plan(plan)
    return plan


def worker(
    plan_dir: Path,
    mip_root: Path,
    run_root: Path,
    task_index: int,
    method: str,
) -> bool:
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
            role="test",
        )
    except Exception as error:
        result = {
            "gate_status": "failed",
            "reason_code": "method_execution_failed",
            "error_type": type(error).__name__,
            "reason_detail": error_reason(error),
            "contract_sha256": plan["contract_sha256"],
            "source_instance_id": target["source_instance_id"],
            "role": "test",
            "method": method,
        }
    write_json(destination, result)
    return result["gate_status"] == "passed"


def run_parent(
    plan_dir: Path,
    training_dir: Path,
    validation_audit_dir: Path,
    mip_root: Path,
    run_root: Path,
    task_index: int,
    device: str,
) -> bool:
    plan = load_plan(plan_dir)
    if build_plan(training_dir, validation_audit_dir, mip_root) != plan:
        raise ValueError("PR59 source inputs differ from the frozen plan")
    target = plan["targets"][task_index]
    parent_dir = run_root / target["source_instance_id"]
    parent_dir.mkdir(parents=True, exist_ok=False)
    try:
        preparation = prepare_parent(
            plan, target, training_dir, mip_root, parent_dir, device
        )
    except Exception as error:
        write_json(
            parent_dir / "preparation_failure.json",
            {
                "gate_status": "failed",
                "contract_sha256": plan["contract_sha256"],
                "source_instance_id": target["source_instance_id"],
                "role": "test",
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
            "cfl_gnn.cli.run_pr59_heldout_guidance",
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
            process = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
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
        "role": "test",
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


def _finite_timing(result: dict) -> None:
    timing = result["timing"]
    for name in (
        "total_wall_time_seconds",
        "data_read_wall_time_seconds",
        "model_build_wall_time_seconds",
        "model_optimize_wall_time_seconds",
    ):
        value = float(timing[name])
        if not math.isfinite(value) or value < -1e-6:
            raise ValueError(f"invalid timing evidence: {name}")


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


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
    matched_support_parents = 0
    paired_control_parents = 0
    for target in plan["targets"]:
        identity = target["source_instance_id"]
        parent_dir = run_root / identity
        try:
            receipt = read_json(parent_dir / "parent_receipt.json")
            preparation = read_json(parent_dir / "preparation.json")
            if (
                receipt.get("contract_sha256") != plan["contract_sha256"]
                or receipt.get("source_instance_id") != identity
                or receipt.get("role") != "test"
                or receipt.get("method_order") != target["method_order"]
                or [item["method"] for item in receipt.get("workers", [])]
                != target["method_order"]
                or any(
                    item.get("returncode") != 0
                    for item in receipt.get("workers", [])
                )
            ):
                raise ValueError("parent receipt changed or contains a failed worker")
            for item in receipt.get("artifacts", {}).values():
                checked(parent_dir, item)
            if preparation.get("gnn_selection", {}).get("abstained") is not False:
                raise ValueError("GNN selection abstained on a frozen test parent")
            nonabstained += 1
            if (
                preparation["gnn_selection"]["selected_support"]
                != preparation["root_lp_selection"]["selected_support"]
                or preparation["gnn_selection"]["positive_assignments"]
                != preparation["root_lp_selection"]["positive_assignments"]
            ):
                raise ValueError("root-LP baseline is not support/class matched")
            matched_support_parents += 1
            results = {}
            for method in METHODS:
                status = {
                    "source_instance_id": identity,
                    "role": "test",
                    "method": method,
                    "artifact_valid": False,
                }
                statuses.append(status)
                result = read_json(parent_dir / f"{method}.json")
                if (
                    result.get("gate_status") != "passed"
                    or result.get("contract_sha256") != plan["contract_sha256"]
                    or result.get("source_instance_id") != identity
                    or result.get("role") != "test"
                    or result.get("method") != method
                    or result.get("mip_sha256") != target["mip"]["sha256"]
                    or result.get("mathematical_model_unchanged") is not True
                    or result.get("fresh_model") is not True
                ):
                    raise ValueError(f"invalid method result: {method}")
                _finite_timing(result)
                if method == METHODS[0] and result["start"]["submitted_assignments"] != 0:
                    raise ValueError("unguided control received a partial start")
                if method != METHODS[0] and result["start"]["submitted_assignments"] <= 0:
                    raise ValueError("guided method received no partial start")
                solve = result["solve"]
                if solve["feasible_solution"]:
                    solution = result.get("solution_artifact")
                    if (
                        not isinstance(solution, dict)
                        or sha256_file(parent_dir / solution["file_name"])
                        != solution["sha256"]
                        or result.get("independent_feasibility", {}).get("valid")
                        is not True
                    ):
                        raise ValueError(f"solution evidence mismatch: {method}")
                outcomes.append(
                    {
                        "source_instance_id": identity,
                        "role": "test",
                        "method": method,
                        "solve_status_code": solve["solve_status_code"],
                        "right_censored": solve["right_censored"],
                        "feasible_solution": solve["feasible_solution"],
                        "primal": solve["primal"],
                        "dual": solve["dual"],
                        "terminal_mip_gap_relative": solve[
                            "terminal_mip_gap_relative"
                        ],
                        "first_observed_gap_le_0.1_seconds": solve[
                            "first_observed_gap_times_seconds"
                        ]["0.1"],
                        "model_optimize_wall_time_seconds": result["timing"][
                            "model_optimize_wall_time_seconds"
                        ],
                        "total_wall_time_seconds": result["timing"][
                            "total_wall_time_seconds"
                        ],
                        "submitted_assignments": result["start"][
                            "submitted_assignments"
                        ],
                        "positive_assignments": result["start"][
                            "positive_assignments"
                        ],
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
            paired_control_parents += 1
            control_gap = control["solve"]["terminal_mip_gap_relative"]
            for method in METHODS[1:]:
                guided_gap = results[method]["solve"]["terminal_mip_gap_relative"]
                effects.append(
                    {
                        "source_instance_id": identity,
                        "role": "test",
                        "method": method,
                        "terminal_gap_difference_guided_minus_control": (
                            None
                            if control_gap is None or guided_gap is None
                            else guided_gap - control_gap
                        ),
                        "optimize_time_difference_guided_minus_control": (
                            results[method]["timing"][
                                "model_optimize_wall_time_seconds"
                            ]
                            - control["timing"]["model_optimize_wall_time_seconds"]
                        ),
                        "control_first_gap_le_0.1_seconds": control["solve"][
                            "first_observed_gap_times_seconds"
                        ]["0.1"],
                        "guided_first_gap_le_0.1_seconds": results[method]["solve"][
                            "first_observed_gap_times_seconds"
                        ]["0.1"],
                    }
                )
        except Exception as error:
            failures.append(
                {
                    "source_instance_id": identity,
                    "role": "test",
                    "error_type": type(error).__name__,
                    "reason_detail": error_reason(error),
                }
            )
    gnn_effects = [row for row in effects if row["method"] == METHODS[2]]
    root_effects = [row for row in effects if row["method"] == METHODS[1]]
    gnn_gap = [
        float(row["terminal_gap_difference_guided_minus_control"])
        for row in gnn_effects
        if row["terminal_gap_difference_guided_minus_control"] is not None
    ]
    root_gap = [
        float(row["terminal_gap_difference_guided_minus_control"])
        for row in root_effects
        if row["terminal_gap_difference_guided_minus_control"] is not None
    ]
    integrity_checks = {
        "all_six_test_parents_valid": len(gnn_effects) == 6 and not failures,
        "all_eighteen_method_runs_valid": len(outcomes) == 18,
        "all_six_gnn_starts_nonabstained": nonabstained == 6,
        "all_six_root_lp_starts_support_and_class_matched": matched_support_parents
        == 6,
        "all_six_method_triplets_paired": paired_control_parents == 6,
        "frozen_policy_authorized_by_pr58": plan[
            "validation_authorization_contract_sha256"
        ]
        == EXPECTED_VALIDATION_CONTRACT,
        "validation_parents_not_executed": {
            target["source_instance_id"] for target in plan["targets"]
        }.isdisjoint(EXPECTED_VALIDATION_PARENTS),
        "test_outcomes_not_used_for_policy_selection": plan[
            "test_outcomes_used_for_policy_selection"
        ]
        is False,
    }
    complete = all(integrity_checks.values())
    for filename, rows in (
        ("per_method_outcomes.json", outcomes),
        ("paired_effects.json", effects),
        ("per_method_status.json", statuses),
    ):
        write_json(output_dir / filename, {"records": rows})
    for filename, rows in (
        ("per_method_outcomes.csv", outcomes),
        ("paired_effects.csv", effects),
    ):
        with (output_dir / filename).open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=list(rows[0]) if rows else ["source_instance_id"],
            )
            writer.writeheader()
            writer.writerows(rows)
    report = {
        "schema_version": 1,
        "contract_sha256": plan["contract_sha256"],
        "validation_authorization_contract_sha256": EXPECTED_VALIDATION_CONTRACT,
        "gate_status": "passed" if complete else "failed",
        "probe_completed": True,
        "integrity_checks": integrity_checks,
        "summary": {
            "planned_test_parents": 6,
            "valid_test_parents": len(gnn_effects),
            "planned_method_runs": 18,
            "valid_method_runs": len(outcomes),
            "gnn_gap_wins_vs_control": sum(value < 0.0 for value in gnn_gap),
            "gnn_gap_ties_vs_control": sum(value == 0.0 for value in gnn_gap),
            "gnn_gap_losses_vs_control": sum(value > 0.0 for value in gnn_gap),
            "gnn_mean_gap_difference_guided_minus_control": _mean(gnn_gap),
            "gnn_median_gap_difference_guided_minus_control": _median(gnn_gap),
            "root_lp_gap_wins_vs_control": sum(value < 0.0 for value in root_gap),
            "root_lp_mean_gap_difference_minus_control": _mean(root_gap),
            "root_lp_median_gap_difference_minus_control": _median(root_gap),
            "right_censored_runs_by_method": {
                method: sum(
                    row["right_censored"]
                    for row in outcomes
                    if row["method"] == method
                )
                for method in METHODS
            },
            "gap_le_0.1_observed_by_method": {
                method: sum(
                    row["first_observed_gap_le_0.1_seconds"] is not None
                    for row in outcomes
                    if row["method"] == method
                )
                for method in METHODS
            },
        },
        "failures": failures,
        "interpretation_policy": {
            "paired_effects_are_descriptive": True,
            "favorable_outcome_required_for_completion": False,
            "policy_reselection_after_test": False,
            "right_censoring_retained": True,
            "confirmatory_significance_claim_allowed": False,
        },
        "eligibility": {
            "held_out_benchmark_complete": complete,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "next_gate": (
                "interpret_held_out_benchmark_without_policy_reselection"
                if complete
                else "review_held_out_execution_integrity_failures"
            ),
            "policy_change_authorized_by_test_outcomes": False,
        },
        "outputs": {
            path.name: descriptor(output_dir, path)
            for path in sorted(output_dir.iterdir())
            if path.is_file()
        },
    }
    write_json(output_dir / REPORT_NAME, report)
    return report


def verify_audit(output_dir: Path) -> dict:
    report_path = output_dir / REPORT_NAME
    report = read_json(report_path)
    checks = report.get("integrity_checks", {})
    summary = report.get("summary", {})
    eligibility = report.get("eligibility", {})
    decision = report.get("decision", {})
    if (
        report.get("gate_status") != "passed"
        or report.get("probe_completed") is not True
        or report.get("validation_authorization_contract_sha256")
        != EXPECTED_VALIDATION_CONTRACT
        or not checks
        or not all(value is True for value in checks.values())
        or summary.get("planned_test_parents") != 6
        or summary.get("valid_test_parents") != 6
        or summary.get("planned_method_runs") != 18
        or summary.get("valid_method_runs") != 18
        or report.get("failures") != []
        or eligibility.get("held_out_benchmark_complete") is not True
        or eligibility.get("development_only") is not True
        or eligibility.get("scientific_reporting_eligible") is not False
        or decision.get("next_gate")
        != "interpret_held_out_benchmark_without_policy_reselection"
        or decision.get("policy_change_authorized_by_test_outcomes") is not False
    ):
        raise ValueError("PR59 held-out benchmark report gate failed")
    declared = report.get("outputs", {})
    if set(declared) != set(AUDIT_OUTPUT_NAMES):
        raise ValueError("PR59 declared audit output inventory changed")
    for name in AUDIT_OUTPUT_NAMES:
        checked(output_dir, declared[name])
    unsafe_tokens = ("/raid/", "/home/", "gurobi.lic", "WLSAccessID", "WLSSecret")
    text_files = [report_path, *(output_dir / name for name in AUDIT_OUTPUT_NAMES)]
    for path in text_files:
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in unsafe_tokens):
            raise ValueError(f"sanitization failed in {path.name}")
    return {
        "report_gate_valid": True,
        "declared_output_hashes_valid": True,
        "declared_text_sanitization_valid": True,
        "declared_outputs_verified": len(AUDIT_OUTPUT_NAMES),
        "text_artifacts_scanned": len(text_files),
        "scope": "development_only_frozen_held_out_benchmark",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("plan", "parent", "worker", "audit", "verify")
    )
    parser.add_argument("--training_dir", type=Path)
    parser.add_argument("--validation_audit_dir", type=Path)
    parser.add_argument("--mip_root", type=Path)
    parser.add_argument("--plan_dir", type=Path)
    parser.add_argument("--run_root", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--task_index", type=int, choices=range(6))
    parser.add_argument("--method", choices=METHODS)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = parser.parse_args(argv)
    required = {
        "plan": ("plan_dir", "training_dir", "validation_audit_dir", "mip_root"),
        "parent": (
            "plan_dir",
            "training_dir",
            "validation_audit_dir",
            "mip_root",
            "run_root",
            "task_index",
        ),
        "worker": ("plan_dir", "mip_root", "run_root", "task_index", "method"),
        "audit": ("plan_dir", "run_root", "output_dir"),
        "verify": ("output_dir",),
    }
    if any(getattr(args, name) is None for name in required[args.command]):
        parser.error("required command-specific argument missing")
    try:
        if args.command == "plan":
            plan = build_plan(
                args.training_dir,
                args.validation_audit_dir,
                args.mip_root,
            )
            args.plan_dir.mkdir(parents=True, exist_ok=False)
            write_json(args.plan_dir / PLAN_NAME, plan)
            print(
                f"[INFO] contract={plan['contract_sha256']} | test_parents=6 | "
                "methods=3 | policy=frozen_by_PR58 | solver_runs=0"
            )
            ok = True
        elif args.command == "parent":
            ok = run_parent(
                args.plan_dir,
                args.training_dir,
                args.validation_audit_dir,
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
        elif args.command == "audit":
            report = audit(args.plan_dir, args.run_root, args.output_dir)
            print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
            ok = report["gate_status"] == "passed"
        else:
            verification = verify_audit(args.output_dir)
            print(json.dumps(verification, indent=2, sort_keys=True))
            print("PR59_REPORT_OK")
            print("PR59_OUTPUT_HASHES_OK")
            print("PR59_DECLARED_TEXT_SANITIZATION_OK")
            ok = True
        return 0 if ok else 1
    except Exception as error:
        print(
            f"[ERROR] {type(error).__name__}: {error_reason(error)}; "
            "preserve outputs for review"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
