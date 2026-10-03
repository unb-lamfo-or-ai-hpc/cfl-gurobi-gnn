"""Run a precommitted, paired SCIP emphasis-profile experiment."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.analysis import scip_derived_label_audit as label_audit
from cfl_gnn.graph.instance_provenance import sha256_file


SCHEMA_VERSION = 1
DATASET_VARIANT = "scip_controlled_convergence_experiment"
PLAN_NAME = "scip_convergence_experiment_plan.json"
REPORT_NAME = "scip_convergence_experiment_report.json"
PER_RUN_NAME = "per_profile_candidate_metrics.jsonl"
PAIRED_NAME = "paired_profile_comparison.jsonl"
SOLUTION_DIR_NAME = "profile_solutions"
PROFILE_IDS = label_audit.SUPPORTED_SOLVER_PROFILES
PROFILE_CONTRACT = {
    "default": {
        "emphasis": None,
        "purpose": "locked_pr21_control",
    },
    "feasibility": {
        "emphasis": "SCIP_PARAMEMPHASIS.FEASIBILITY",
        "purpose": "primal_incumbent_progress",
    },
    "optimality": {
        "emphasis": "SCIP_PARAMEMPHASIS.OPTIMALITY",
        "purpose": "dual_bound_and_proof_progress",
    },
}
EXPERIMENT_STAGES = ("engineering_smoke", "equal_budget_pilot")


class ConvergenceExperimentError(RuntimeError):
    """Raised when the controlled experiment fails closed."""


@dataclass(frozen=True, slots=True)
class ConvergencePlan:
    parent_instance_id: str
    root_mip: Path
    node_mips: tuple[Path, ...]
    graph_audit_report: Path
    baseline_plan: Path
    baseline_report: Path
    output_dir: Path
    root_sha256: str
    node_sha256: tuple[str, ...]
    graph_audit_report_sha256: str
    baseline_plan_sha256: str
    baseline_report_sha256: str
    baseline_contract_sha256: str
    experiment_stage: str
    hardware_class: str
    time_limit: float
    node_limit: int
    seed: int
    max_parallel: int
    feasibility_tolerance: float
    optimality_tolerance: float

    @property
    def contract_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": DATASET_VARIANT,
            "parent_instance_id": self.parent_instance_id,
            "experiment_stage": self.experiment_stage,
            "hardware_class": self.hardware_class,
            "root_mip": {
                "file_name": self.root_mip.name,
                "sha256": self.root_sha256,
            },
            "node_mips": [
                {"file_name": path.name, "sha256": digest}
                for path, digest in zip(self.node_mips, self.node_sha256)
            ],
            "upstream": {
                "graph_audit_report": {
                    "file_name": self.graph_audit_report.name,
                    "sha256": self.graph_audit_report_sha256,
                },
                "schema_v3_label_plan": {
                    "file_name": self.baseline_plan.name,
                    "sha256": self.baseline_plan_sha256,
                    "contract_sha256": self.baseline_contract_sha256,
                },
                "schema_v3_label_report": {
                    "file_name": self.baseline_report.name,
                    "sha256": self.baseline_report_sha256,
                    "contract_sha256": self.baseline_contract_sha256,
                },
            },
            "profiles": [
                {"profile_id": profile_id, **PROFILE_CONTRACT[profile_id]}
                for profile_id in PROFILE_IDS
            ],
            "scheduling": {
                "submission_order": "profile_major_then_candidate_file_name",
                "result_order": "profile_major_then_candidate_file_name",
            },
            "locked_controls": {
                "objective_sense": "MINIMIZE",
                "fresh_process_per_run": True,
                "threads_per_scip": 1,
                "time_limit_seconds": self.time_limit,
                "node_limit": self.node_limit,
                "seed": self.seed,
                "max_parallel_runs": self.max_parallel,
                "warm_start_supplied": False,
                "parent_incumbent_consumed": False,
                "individual_parameter_tuning": False,
                "feasibility_tolerance": self.feasibility_tolerance,
                "optimality_tolerance": self.optimality_tolerance,
            },
            "endpoints": {
                "co_primary": [
                    "terminal_mip_gap_relative_at_common_budget",
                    "execution_time_seconds_to_proven_optimality_right_censored",
                ],
                "diagnostic": [
                    "terminal_primal_objective",
                    "terminal_dual_bound",
                    "best_incumbent_objective",
                    "best_incumbent_discovery_time_seconds",
                ],
            },
            "eligibility": {
                "dataset_eligible": False,
                "scientific_reporting_eligible": False,
                "profile_selection_eligible": False,
            },
        }

    @property
    def contract_sha256(self) -> str:
        return label_audit._canonical_sha256(self.contract_payload)

    def to_summary(self) -> dict[str, Any]:
        return {**self.contract_payload, "contract_sha256": self.contract_sha256}


def _read_json_object(path: str | Path, name: str) -> tuple[Path, dict[str, Any]]:
    resolved = Path(path).resolve()
    if not resolved.is_file() or resolved.stat().st_size == 0:
        raise FileNotFoundError(f"missing or empty {name}: {resolved}")
    loaded = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ConvergenceExperimentError(f"{name} must contain a JSON object")
    return resolved, loaded


def _validate_parent_instance_id(value: str) -> str:
    normalized = value.strip()
    if not normalized or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
        for character in normalized
    ):
        raise ValueError("parent_instance_id must be a path-free identifier")
    return normalized


def build_experiment_plan(
    *,
    parent_instance_id: str,
    root_mip: str | Path,
    node_mips: Sequence[str | Path],
    graph_audit_report: str | Path,
    baseline_plan: str | Path,
    baseline_report: str | Path,
    output_dir: str | Path,
    experiment_stage: str = "engineering_smoke",
    hardware_class: str = "dasci_dgx",
    time_limit: float = 300.0,
    node_limit: int = 1_000_000,
    seed: int = 42,
    max_parallel: int = 4,
    feasibility_tolerance: float = 1e-6,
    optimality_tolerance: float = 1e-8,
) -> ConvergencePlan:
    if experiment_stage not in EXPERIMENT_STAGES:
        raise ValueError(f"unsupported experiment_stage: {experiment_stage}")
    graph_path, _ = _read_json_object(graph_audit_report, "graph_audit_report")
    baseline_plan_path, baseline_plan_payload = _read_json_object(
        baseline_plan, "baseline_plan"
    )
    baseline_report_path, baseline_report_payload = _read_json_object(
        baseline_report, "baseline_report"
    )
    if baseline_plan_payload.get("schema_version") != label_audit.SCHEMA_VERSION:
        raise ConvergenceExperimentError("baseline plan is not schema v3")
    if baseline_report_payload.get("schema_version") != label_audit.SCHEMA_VERSION:
        raise ConvergenceExperimentError("baseline report is not schema v3")
    baseline_contract = str(baseline_plan_payload.get("contract_sha256", ""))
    if (
        len(baseline_contract) != 64
        or baseline_report_payload.get("contract_sha256") != baseline_contract
    ):
        raise ConvergenceExperimentError("baseline plan/report contract mismatch")
    if baseline_report_payload.get("probe_completed") is not True or baseline_report_payload.get(
        "execution", {}
    ).get("status") != "completed":
        raise ConvergenceExperimentError("baseline schema-v3 execution did not complete")
    if baseline_report_payload.get("gate_status") not in {"passed", "inconclusive"}:
        raise ConvergenceExperimentError("baseline schema-v3 evidence is invalid")
    if baseline_report_payload.get("summary", {}).get("all_feasible") is not True:
        raise ConvergenceExperimentError("baseline schema-v3 solutions are not all feasible")

    validation_plan = label_audit.build_audit_plan(
        root_mip=root_mip,
        node_mips=node_mips,
        graph_audit_report=graph_path,
        output_dir=output_dir,
        time_limit=time_limit,
        node_limit=node_limit,
        seed=seed,
        max_parallel=max_parallel,
        feasibility_tolerance=feasibility_tolerance,
        optimality_tolerance=optimality_tolerance,
    )
    current = validation_plan.to_summary()
    for key in ("root_mip", "node_mips"):
        if baseline_plan_payload.get(key) != current.get(key):
            raise ConvergenceExperimentError(
                f"current {key} does not match the schema-v3 baseline plan"
            )
    upstream = baseline_plan_payload.get("upstream_graph_audit", {})
    if upstream.get("sha256") != sha256_file(graph_path):
        raise ConvergenceExperimentError(
            "graph audit report does not match the schema-v3 baseline plan"
        )

    return ConvergencePlan(
        parent_instance_id=_validate_parent_instance_id(parent_instance_id),
        root_mip=validation_plan.root_mip,
        node_mips=validation_plan.node_mips,
        graph_audit_report=graph_path,
        baseline_plan=baseline_plan_path,
        baseline_report=baseline_report_path,
        output_dir=Path(output_dir).resolve(),
        root_sha256=validation_plan.root_sha256,
        node_sha256=validation_plan.node_sha256,
        graph_audit_report_sha256=sha256_file(graph_path),
        baseline_plan_sha256=sha256_file(baseline_plan_path),
        baseline_report_sha256=sha256_file(baseline_report_path),
        baseline_contract_sha256=baseline_contract,
        experiment_stage=experiment_stage,
        hardware_class=_validate_parent_instance_id(hardware_class),
        time_limit=validation_plan.time_limit,
        node_limit=validation_plan.node_limit,
        seed=validation_plan.seed,
        max_parallel=validation_plan.max_parallel,
        feasibility_tolerance=validation_plan.feasibility_tolerance,
        optimality_tolerance=validation_plan.optimality_tolerance,
    )


def _solution_path(plan: ConvergencePlan, profile_id: str, candidate: Path) -> Path:
    return (
        plan.output_dir
        / SOLUTION_DIR_NAME
        / profile_id
        / f"{candidate.stem}.solution.json.gz"
    )


def _worker_request(
    plan: ConvergencePlan,
    profile_id: str,
    candidate: Path,
    solution_path: Path,
) -> dict[str, Any]:
    return {
        "contract_sha256": plan.contract_sha256,
        "candidate_path": str(candidate),
        "candidate_file_name": candidate.name,
        "candidate_sha256": sha256_file(candidate),
        "solution_path": str(solution_path),
        "solver_profile": profile_id,
        "time_limit": plan.time_limit,
        "node_limit": plan.node_limit,
        "seed": plan.seed,
    }


def _load_reusable_payload(
    path: Path,
    plan: ConvergencePlan,
    profile_id: str,
    candidate: Path,
) -> dict[str, Any] | None:
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        payload = label_audit._read_gzip_json(path)
    except (OSError, json.JSONDecodeError, label_audit.DerivedLabelAuditError):
        return None
    expected = {
        "schema_version": label_audit.SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "candidate_file_name": candidate.name,
        "candidate_sha256": sha256_file(candidate),
        "solver_profile": profile_id,
        "fresh_process": True,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        return None
    return payload


def _solve_one(
    task_index: int,
    profile_id: str,
    candidate: Path,
    root_domains: Sequence[Mapping[str, Any]],
    plan: ConvergencePlan,
    *,
    reuse_existing: bool,
) -> tuple[int, dict[str, Any]]:
    solution_path = _solution_path(plan, profile_id, candidate)
    solution_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        _load_reusable_payload(
            solution_path, plan, profile_id, candidate
        )
        if reuse_existing
        else None
    )
    reused = payload is not None
    if payload is None:
        request_path = plan.output_dir / f".profile_request_{task_index:03d}.json"
        result_path = plan.output_dir / f".profile_result_{task_index:03d}.json"
        label_audit._write_json(
            request_path,
            _worker_request(plan, profile_id, candidate, solution_path),
        )
        try:
            label_audit._run_worker(request_path, result_path)
            result = label_audit._read_json(result_path)
            if result.get("worker_status") != "completed":
                raise ConvergenceExperimentError("profile worker did not complete")
            payload = label_audit._read_gzip_json(solution_path)
        finally:
            request_path.unlink(missing_ok=True)
            result_path.unlink(missing_ok=True)

    variables = payload.get("variables")
    if not isinstance(variables, list):
        raise ConvergenceExperimentError("profile worker omitted solution vector")
    domain_audit = label_audit.validate_solution_vector(
        root_domains,
        variables,
        tolerance=plan.feasibility_tolerance,
    )
    parameter_map = payload.get("solver_parameter_map")
    parameter_sha = payload.get("solver_parameter_sha256")
    parameter_integrity = isinstance(parameter_map, Mapping) and parameter_sha == (
        label_audit._canonical_sha256(parameter_map)
        if isinstance(parameter_map, Mapping)
        else None
    )
    payload["canonical_type_policy"] = "root_bounded_integer_0_1_as_binary"
    label_audit._write_gzip_json(solution_path, payload)
    record = label_audit.evaluate_candidate_label(
        payload,
        domain_audit,
        solution_file_name=solution_path.name,
        solution_sha256=sha256_file(solution_path),
        optimality_tolerance=plan.optimality_tolerance,
    )
    record["profile_id"] = profile_id
    record["parent_instance_id"] = plan.parent_instance_id
    record["seed"] = plan.seed
    record["solver_versions"] = payload.get("solver_versions")
    record["solver_parameter_sha256"] = parameter_sha
    record["checks"]["solver_parameter_fingerprint"] = parameter_integrity
    record["worker_result_reused"] = reused
    solved = record["checks"].get("optimal_status") is True
    record["censoring"] = {
        "right_censored": not solved,
        "time_to_proven_optimality_seconds": (
            record["solve"].get("execution_time_seconds") if solved else None
        ),
        "censoring_time_limit_seconds": None if solved else plan.time_limit,
    }
    if not parameter_integrity:
        record.update(
            {
                "gate_status": "failed",
                "label_eligible": False,
                "feasible_solution_evidence": False,
                "reason_code": "solver_parameter_fingerprint_invalid",
            }
        )
    return task_index, record


def _finite_number(value: Any) -> float | None:
    if value is None:
        return None
    converted = float(value)
    return converted if math.isfinite(converted) else None


def paired_comparisons(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_candidate_profile = {
        (str(record["candidate_file_name"]), str(record["profile_id"])): record
        for record in records
    }
    candidates = sorted({str(record["candidate_file_name"]) for record in records})
    comparisons: list[dict[str, Any]] = []
    for candidate in candidates:
        control = by_candidate_profile[(candidate, "default")]
        control_gap = _finite_number(control["solve"].get("mip_gap_relative"))
        control_objective = _finite_number(control["solve"].get("objective"))
        control_bound = _finite_number(control["solve"].get("best_bound"))
        for profile_id in PROFILE_IDS[1:]:
            treatment = by_candidate_profile[(candidate, profile_id)]
            treatment_gap = _finite_number(
                treatment["solve"].get("mip_gap_relative")
            )
            treatment_objective = _finite_number(
                treatment["solve"].get("objective")
            )
            treatment_bound = _finite_number(
                treatment["solve"].get("best_bound")
            )
            comparisons.append(
                {
                    "parent_instance_id": control["parent_instance_id"],
                    "candidate_file_name": candidate,
                    "seed": control["seed"],
                    "control_profile_id": "default",
                    "treatment_profile_id": profile_id,
                    "control_terminal_gap_relative": control_gap,
                    "treatment_terminal_gap_relative": treatment_gap,
                    "terminal_gap_difference": (
                        treatment_gap - control_gap
                        if treatment_gap is not None and control_gap is not None
                        else None
                    ),
                    "terminal_gap_ratio": (
                        treatment_gap / control_gap
                        if treatment_gap is not None
                        and control_gap is not None
                        and control_gap > 0
                        else None
                    ),
                    "primal_objective_difference": (
                        treatment_objective - control_objective
                        if treatment_objective is not None
                        and control_objective is not None
                        else None
                    ),
                    "dual_bound_difference": (
                        treatment_bound - control_bound
                        if treatment_bound is not None and control_bound is not None
                        else None
                    ),
                    "control_right_censored": control["censoring"][
                        "right_censored"
                    ],
                    "treatment_right_censored": treatment["censoring"][
                        "right_censored"
                    ],
                    "time_to_optimality_difference_seconds": (
                        treatment["censoring"][
                            "time_to_proven_optimality_seconds"
                        ]
                        - control["censoring"][
                            "time_to_proven_optimality_seconds"
                        ]
                        if not treatment["censoring"]["right_censored"]
                        and not control["censoring"]["right_censored"]
                        else None
                    ),
                }
            )
    return comparisons


def summarize_profiles(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for profile_id in PROFILE_IDS:
        profile_records = [
            record for record in records if record.get("profile_id") == profile_id
        ]
        gaps = [
            float(record["solve"]["mip_gap_relative"])
            for record in profile_records
            if record.get("solve", {}).get("mip_gap_relative") is not None
        ]
        result[profile_id] = {
            "runs": len(profile_records),
            "feasible_runs": sum(
                record.get("feasible_solution_evidence") is True
                for record in profile_records
            ),
            "optimal_runs": sum(
                record.get("label_eligible") is True for record in profile_records
            ),
            "right_censored_runs": sum(
                record.get("censoring", {}).get("right_censored") is True
                for record in profile_records
            ),
            "median_terminal_mip_gap_relative": (
                statistics.median(gaps) if gaps else None
            ),
            "median_terminal_mip_gap_percent": (
                100.0 * statistics.median(gaps) if gaps else None
            ),
            "solver_parameter_sha256": sorted(
                {
                    str(record.get("solver_parameter_sha256"))
                    for record in profile_records
                }
            ),
        }
    return result


def run_experiment(
    plan: ConvergencePlan,
    *,
    reuse_existing: bool = True,
) -> dict[str, Any]:
    root_domains = label_audit._model_domain_records(plan.root_mip)
    tasks = [
        (profile_id, candidate)
        for profile_id in PROFILE_IDS
        for candidate in plan.node_mips
    ]
    workers = min(plan.max_parallel, len(tasks))
    records_by_index: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _solve_one,
                index,
                profile_id,
                candidate,
                root_domains,
                plan,
                reuse_existing=reuse_existing,
            ): index
            for index, (profile_id, candidate) in enumerate(tasks)
        }
        for future in as_completed(futures):
            index, record = future.result()
            records_by_index[index] = record
            partial = [records_by_index[key] for key in sorted(records_by_index)]
            label_audit._write_jsonl(plan.output_dir / PER_RUN_NAME, partial)

    records = [records_by_index[index] for index in range(len(tasks))]
    comparisons = paired_comparisons(records)
    label_audit._write_jsonl(plan.output_dir / PER_RUN_NAME, records)
    label_audit._write_jsonl(plan.output_dir / PAIRED_NAME, comparisons)
    profile_summary = summarize_profiles(records)
    expected_runs = len(PROFILE_IDS) * len(plan.node_mips)
    parameter_maps_consistent = all(
        len(profile_summary[profile_id]["solver_parameter_sha256"]) == 1
        for profile_id in PROFILE_IDS
    )
    profile_parameter_hashes = {
        profile_summary[profile_id]["solver_parameter_sha256"][0]
        for profile_id in PROFILE_IDS
        if len(profile_summary[profile_id]["solver_parameter_sha256"]) == 1
    }
    parameter_maps_distinct = len(profile_parameter_hashes) == len(PROFILE_IDS)
    engineering_gate_passed = (
        len(records) == expected_runs
        and all(record.get("gate_status") in {"passed", "inconclusive"} for record in records)
        and all(
            record.get("checks", {}).get("solver_parameter_fingerprint") is True
            for record in records
        )
        and parameter_maps_consistent
        and parameter_maps_distinct
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "experiment_stage": plan.experiment_stage,
        "gate_status": "passed" if engineering_gate_passed else "failed",
        "execution": {
            "status": "completed",
            "mode": "parallel_fresh_processes",
            "planned_runs": expected_runs,
            "completed_runs": len(records),
            "max_parallel_runs": plan.max_parallel,
            "workers_used": workers,
            "worker_results_reused": sum(
                record["worker_result_reused"] for record in records
            ),
            "worker_results_executed": sum(
                not record["worker_result_reused"] for record in records
            ),
        },
        "profile_summary": profile_summary,
        "paired_comparisons": len(comparisons),
        "checks": {
            "expected_run_count": len(records) == expected_runs,
            "all_runs_valid_or_censored": all(
                record.get("gate_status") in {"passed", "inconclusive"}
                for record in records
            ),
            "parameter_fingerprints_valid": all(
                record.get("checks", {}).get("solver_parameter_fingerprint") is True
                for record in records
            ),
            "parameter_maps_consistent_within_profile": parameter_maps_consistent,
            "parameter_maps_distinct_across_profiles": parameter_maps_distinct,
        },
        "eligibility": {
            "independently_optimal_run_count": sum(
                record.get("label_eligible") is True for record in records
            ),
            "profile_selection_eligible": False,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "engineering_smoke_validated": engineering_gate_passed,
            "profile_selected": False,
            "reason_code": (
                "controlled_profile_experiment_completed_pending_review"
                if engineering_gate_passed
                else "controlled_profile_experiment_failed"
            ),
            "next_gate": (
                "equal_budget_pilot_review"
                if engineering_gate_passed
                and plan.experiment_stage == "engineering_smoke"
                else "parent_grouped_replication_or_stop"
                if engineering_gate_passed
                else "correct_experiment_before_continuing"
            ),
        },
    }


def failure_report(plan: ConvergencePlan, error: Exception) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": False,
        "gate_status": "failed",
        "failure": {
            "error_type": type(error).__name__,
            "reason_code": "controlled_convergence_experiment_execution_failed",
        },
        "eligibility": {
            "profile_selection_eligible": False,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare precommitted SCIP emphasis profiles under equal budgets."
    )
    parser.add_argument("--parent_instance_id")
    parser.add_argument("--root_mip")
    parser.add_argument("--node_mips", nargs="+")
    parser.add_argument("--graph_audit_report")
    parser.add_argument("--baseline_plan")
    parser.add_argument("--baseline_report")
    parser.add_argument("--output_dir")
    parser.add_argument(
        "--experiment_stage",
        choices=EXPERIMENT_STAGES,
        default="engineering_smoke",
    )
    parser.add_argument("--hardware_class", default="dasci_dgx")
    parser.add_argument("--time_limit", type=float, default=300.0)
    parser.add_argument("--node_limit", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_parallel", type=int, default=4)
    parser.add_argument("--feasibility_tolerance", type=float, default=1e-6)
    parser.add_argument("--optimality_tolerance", type=float, default=1e-8)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    required = {
        name: getattr(args, name)
        for name in (
            "parent_instance_id",
            "root_mip",
            "node_mips",
            "graph_audit_report",
            "baseline_plan",
            "baseline_report",
            "output_dir",
        )
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("missing required arguments: " + ", ".join(missing))
    plan = build_experiment_plan(
        parent_instance_id=args.parent_instance_id,
        root_mip=args.root_mip,
        node_mips=args.node_mips,
        graph_audit_report=args.graph_audit_report,
        baseline_plan=args.baseline_plan,
        baseline_report=args.baseline_report,
        output_dir=args.output_dir,
        experiment_stage=args.experiment_stage,
        hardware_class=args.hardware_class,
        time_limit=args.time_limit,
        node_limit=args.node_limit,
        seed=args.seed,
        max_parallel=args.max_parallel,
        feasibility_tolerance=args.feasibility_tolerance,
        optimality_tolerance=args.optimality_tolerance,
    )
    plan_path = plan.output_dir / PLAN_NAME
    report_path = plan.output_dir / REPORT_NAME
    if not args.overwrite and (
        report_path.exists() or (args.dry_run and plan_path.exists())
    ):
        raise FileExistsError("output exists; choose another directory or use --overwrite")
    label_audit._write_json(plan_path, plan.to_summary())
    print(
        "[INFO] "
        f"contract={plan.contract_sha256} | profiles={len(PROFILE_IDS)} | "
        f"candidates={len(plan.node_mips)} | stage={plan.experiment_stage}"
    )
    print(f"[INFO] Plan: {plan_path}")
    if args.dry_run:
        return 0
    try:
        report = run_experiment(plan, reuse_existing=not args.overwrite)
    except Exception as error:
        report = failure_report(plan, error)
        label_audit._write_json(report_path, report)
        print(f"[INFO] Failure report: {report_path}")
        raise
    label_audit._write_json(report_path, report)
    print(
        "[INFO] "
        f"gate={report['gate_status']} | "
        f"completed={report['execution']['completed_runs']}/"
        f"{report['execution']['planned_runs']} | profile_selected=false"
    )
    print(f"[INFO] Report: {report_path}")
    if report["gate_status"] != "passed":
        raise ConvergenceExperimentError(
            "controlled convergence experiment failed; inspect per-run metrics"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
