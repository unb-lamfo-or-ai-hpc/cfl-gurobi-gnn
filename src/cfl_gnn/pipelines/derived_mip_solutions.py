"""Independently solve local-branching MIPs for one MVP solver arm."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.experiments.mvp_contract import load_experiment_config
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.solvers.pyscipopt_solution import sha256_file


SCHEMA_VERSION = 1
DATASET_VARIANT = "mvp_independent_derived_mip_labels"
PLAN_NAME = "derived_mip_solution_plan.json"
REPORT_NAME = "derived_mip_solution_report.json"
PER_CANDIDATE_NAME = "per_candidate_derived_metrics.jsonl"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
SOLVERS = ("gurobi", "scip")


class DerivedMipSolveError(RuntimeError):
    """Raised when a derived-MIP solve contract is invalid."""


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise DerivedMipSolveError(f"expected JSON object: {path.name}")
    return loaded


def _read_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        loaded = json.load(stream)
    if not isinstance(loaded, dict):
        raise DerivedMipSolveError(f"expected compressed JSON object: {path.name}")
    return loaded


def _positive(value: Any, *, field: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{field} must be positive and finite")
    return normalized


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    normalized = int(value)
    if normalized != value or normalized <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return normalized


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    path: Path
    provenance_path: Path
    sha256: str
    provenance_sha256: str
    parent_instance_id: str
    category: str
    difficulty: str
    fold: int
    radius: int
    radius_fraction: float
    operator_contract_sha256: str
    source_incumbent_id: str
    source_incumbent_artifact_sha256: str

    @property
    def stem(self) -> str:
        return self.path.stem

    def contract_payload(self) -> dict[str, Any]:
        return {
            "file_name": self.path.name,
            "sha256": self.sha256,
            "provenance_file_name": self.provenance_path.name,
            "provenance_sha256": self.provenance_sha256,
            "parent_instance_id": self.parent_instance_id,
            "category": self.category,
            "difficulty": self.difficulty,
            "fold": self.fold,
            "role": "train",
            "radius": self.radius,
            "radius_fraction": self.radius_fraction,
            "operator_contract_sha256": self.operator_contract_sha256,
            "source_incumbent_id": self.source_incumbent_id,
            "source_incumbent_artifact_sha256": (
                self.source_incumbent_artifact_sha256
            ),
        }


@dataclass(frozen=True, slots=True)
class DerivedSolvePlan:
    solver: str
    candidate_dir: Path
    output_dir: Path
    experiment_contract_sha256: str
    maximum_admissible_relative_gap: float
    sensitivity_thresholds_relative: tuple[float, ...]
    candidates: tuple[CandidateSpec, ...]
    time_limit: float
    node_limit: int
    threads_per_candidate: int
    seed: int
    max_parallel: int

    @property
    def contract_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": DATASET_VARIANT,
            "experiment_contract_sha256": self.experiment_contract_sha256,
            "experiment_stage": "engineering_label_generation",
            "solver": self.solver,
            "sampling_strategy": "incumbent_local_branching",
            "candidates": [item.contract_payload() for item in self.candidates],
            "solve_contract": {
                "fresh_process_per_candidate": True,
                "warm_start_supplied": False,
                "parent_incumbent_consumed": False,
                "objective_sense": "MINIMIZE",
                "solver_profile": "default",
                "time_limit_seconds_per_candidate": self.time_limit,
                "node_limit_per_candidate": self.node_limit,
                "threads_per_candidate": self.threads_per_candidate,
                "seed": self.seed,
                "max_parallel_candidates": self.max_parallel,
                "online_incumbent_vectors": True,
            },
            "gap_policy": {
                "maximum_admissible_relative_gap": (
                    self.maximum_admissible_relative_gap
                ),
                "sensitivity_thresholds_relative": list(
                    self.sensitivity_thresholds_relative
                ),
            },
            "metric_semantics": {
                "mip_gap": "terminal_solver_relative_gap",
                "execution_time": "solver_wall_time_seconds",
                "right_censoring": "time_or_node_limit",
                "comparative_use": (
                    "label_generation_provenance_only_not_final_solver_benchmark"
                ),
            },
            "eligibility": {
                "dataset_eligible": False,
                "scientific_reporting_eligible": False,
            },
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    def to_summary(self) -> dict[str, Any]:
        return {
            **self.contract_payload,
            "contract_sha256": self.contract_sha256,
            "candidate_count": len(self.candidates),
            "outputs": {
                "report": REPORT_NAME,
                "per_candidate_metrics": PER_CANDIDATE_NAME,
                "solutions_dir": "solutions",
                "incumbents_dir": "incumbents",
                "variable_orders_dir": "variable_orders",
            },
        }


def _candidate_from_provenance(
    path: Path,
    provenance_path: Path,
    *,
    solver: str,
    experiment_contract_sha256: str,
) -> CandidateSpec:
    provenance = _read_json(provenance_path)
    output = provenance.get("output", {})
    source_incumbent = provenance.get("source_incumbent", {})
    local_branching = provenance.get("local_branching", {})
    checks = {
        "solver": provenance.get("solver") == solver,
        "sampling_strategy": (
            provenance.get("sampling_strategy") == "incumbent_local_branching"
        ),
        "role": provenance.get("role") == "train",
        "experiment_contract": (
            provenance.get("experiment_contract_sha256")
            == experiment_contract_sha256
        ),
        "output_file": output.get("file_name") == path.name,
        "output_sha256": output.get("sha256") == sha256_file(path),
        "unlabelled_status": (
            provenance.get("sample_status") == "derived_mip_unlabelled"
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise DerivedMipSolveError(
            f"invalid provenance for {path.name}: {','.join(failed)}"
        )
    return CandidateSpec(
        path=path.resolve(),
        provenance_path=provenance_path.resolve(),
        sha256=sha256_file(path),
        provenance_sha256=sha256_file(provenance_path),
        parent_instance_id=str(provenance["parent_instance_id"]),
        category=str(provenance["category"]),
        difficulty=str(provenance["difficulty"]),
        fold=int(provenance["fold"]),
        radius=int(local_branching["radius"]),
        radius_fraction=float(local_branching["radius_fraction"]),
        operator_contract_sha256=str(provenance["operator_contract_sha256"]),
        source_incumbent_id=str(source_incumbent["incumbent_id"]),
        source_incumbent_artifact_sha256=str(
            source_incumbent["artifact_sha256"]
        ),
    )


def build_plan(
    *,
    solver: str,
    candidate_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path,
    time_limit: float,
    node_limit: int,
    threads_per_candidate: int,
    seed: int,
    max_parallel: int,
    expected_candidates: int | None = None,
) -> DerivedSolvePlan:
    if solver not in SOLVERS:
        raise ValueError("solver must be gurobi or scip")
    source_dir = Path(candidate_dir).resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"missing candidate directory: {source_dir}")
    config = load_experiment_config(config_path)
    paths = sorted(source_dir.glob(f"*__{solver}__lb_r*.lp"), key=lambda p: p.name)
    required = (
        config.augmentation.maximum_derived_per_parent
        if expected_candidates is None
        else _positive_int(expected_candidates, field="expected_candidates")
    )
    if len(paths) != required:
        raise DerivedMipSolveError(
            f"expected {required} {solver} candidate MIPs, found {len(paths)}"
        )
    candidates = tuple(
        _candidate_from_provenance(
            path,
            path.with_suffix(".provenance.json"),
            solver=solver,
            experiment_contract_sha256=config.contract_sha256,
        )
        for path in paths
    )
    parent_ids = {item.parent_instance_id for item in candidates}
    operator_hashes = {item.operator_contract_sha256 for item in candidates}
    folds = {item.fold for item in candidates}
    if len(parent_ids) != 1 or len(operator_hashes) != 1 or len(folds) != 1:
        raise DerivedMipSolveError(
            "candidate cohort must share parent, operator contract, and fold"
        )
    return DerivedSolvePlan(
        solver=solver,
        candidate_dir=source_dir,
        output_dir=Path(output_dir).resolve(),
        experiment_contract_sha256=config.contract_sha256,
        maximum_admissible_relative_gap=(
            config.gap_policy.maximum_admissible_relative_gap
        ),
        sensitivity_thresholds_relative=(
            config.gap_policy.sensitivity_thresholds_relative
        ),
        candidates=candidates,
        time_limit=_positive(time_limit, field="time_limit"),
        node_limit=_positive_int(node_limit, field="node_limit"),
        threads_per_candidate=_positive_int(
            threads_per_candidate, field="threads_per_candidate"
        ),
        seed=int(seed),
        max_parallel=min(
            _positive_int(max_parallel, field="max_parallel"), len(candidates)
        ),
    )


def _artifact_paths(plan: DerivedSolvePlan, candidate: CandidateSpec) -> dict[str, Path]:
    return {
        "solution": plan.output_dir / "solutions" / f"{candidate.stem}.solution.json.gz",
        "incumbents": (
            plan.output_dir / "incumbents" / f"{candidate.stem}.incumbents.parquet"
        ),
        "variable_order": (
            plan.output_dir
            / "variable_orders"
            / f"{candidate.stem}.variable_order.json.gz"
        ),
    }


def worker_request(
    plan: DerivedSolvePlan,
    candidate: CandidateSpec,
) -> dict[str, Any]:
    artifacts = _artifact_paths(plan, candidate)
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "solver": plan.solver,
        "candidate_path": str(candidate.path),
        "candidate_file_name": candidate.path.name,
        "candidate_sha256": candidate.sha256,
        "solution_path": str(artifacts["solution"]),
        "incumbent_stream_path": str(artifacts["incumbents"]),
        "variable_order_path": str(artifacts["variable_order"]),
        "capture_incumbent_vectors": True,
        "force_minimize": True,
        "time_limit": plan.time_limit,
        "node_limit": plan.node_limit,
        "threads": plan.threads_per_candidate,
        "seed": plan.seed,
        "solver_profile": "default",
    }


def _run_worker_process(request_path: Path, result_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "cfl_gnn.cli.solve_derived_mips",
            "--_worker_request",
            str(request_path),
            "--_worker_result",
            str(result_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _sensitivity_memberships(
    gap: float | None,
    thresholds: Sequence[float],
) -> list[str]:
    if gap is None or not math.isfinite(float(gap)) or float(gap) < 0.0:
        return []
    return [
        f"gap_le_{threshold:g}"
        for threshold in thresholds
        if float(gap) <= threshold + 1e-12
    ]


def evaluate_candidate(
    plan: DerivedSolvePlan,
    candidate: CandidateSpec,
    payload: Mapping[str, Any],
    *,
    reused: bool,
) -> dict[str, Any]:
    online = payload.get("online_incumbent_capture", {})
    trace_audit = payload.get("incumbent_trace_audit", {})
    events = int(online.get("events_recorded", 0))
    vectors = int(online.get("vectors_streamed", 0))
    solution_count = int(payload.get("solution_count", 0))
    has_solution = solution_count > 0 and payload.get("solution_objective") is not None
    artifacts = _artifact_paths(plan, candidate)
    gap_raw = payload.get("mip_gap_relative")
    gap = float(gap_raw) if gap_raw is not None else None
    gap_finite = gap is not None and math.isfinite(gap) and gap >= 0.0
    expected_source = f"independent_{plan.solver}_optimization"
    execution_checks = {
        "candidate_sha256_match": payload.get("candidate_sha256") == candidate.sha256,
        "solution_source_match": payload.get("solution_source") == expected_source,
        "fresh_process": payload.get("fresh_process") is True,
        "zero_pre_solve_solutions": payload.get("pre_solve_solution_count") == 0,
        "no_warm_start": payload.get("warm_start_supplied") is False,
        "no_parent_incumbent": payload.get("parent_incumbent_consumed") is False,
        "objective_minimize": payload.get("objective_sense") == "minimize",
        "callback_errors_absent": online.get("capture_error_count") == 0,
    }
    solution_checks = {
        "solution_present": has_solution,
        "solver_feasibility_check": payload.get("solver_feasibility_check") is True,
        "named_solution_present": bool(payload.get("variables")),
        "online_incumbent_observed": events > 0,
        "incumbent_vectors_match_events": vectors == events and events > 0,
        "incumbent_stream_committed": online.get("stream_committed") is True,
        "incumbent_trace_consistent": (
            trace_audit.get("incumbent_trace_consistent") is True
        ),
        "terminal_gap_finite": gap_finite,
        "solution_artifact_present": artifacts["solution"].is_file(),
        "incumbent_artifact_present": artifacts["incumbents"].is_file(),
        "variable_order_artifact_present": artifacts["variable_order"].is_file(),
    }
    execution_valid = all(execution_checks.values())
    solution_valid = all(solution_checks.values())
    gap_eligible = (
        gap_finite
        and gap is not None
        and gap <= plan.maximum_admissible_relative_gap + 1e-12
    )
    label_eligible = execution_valid and solution_valid and gap_eligible
    status = str(payload.get("solve_status", "unknown"))
    if label_eligible:
        gate_status = "passed"
        reason_code = "independent_derived_label_admissible"
    elif not execution_valid or (has_solution and not solution_valid):
        gate_status = "failed"
        reason_code = "independent_derived_solve_evidence_failed"
    elif not has_solution:
        gate_status = "inconclusive"
        reason_code = f"no_feasible_solution_{status}"
    else:
        gate_status = "inconclusive"
        reason_code = "terminal_gap_above_label_policy"
    def artifact_record(name: str) -> dict[str, Any] | None:
        path = artifacts[name]
        if not path.is_file() or path.stat().st_size == 0:
            return None
        return {"file_name": path.name, "sha256": sha256_file(path)}

    memberships = (
        _sensitivity_memberships(gap, plan.sensitivity_thresholds_relative)
        if execution_valid and solution_valid
        else []
    )
    return {
        "sample_id": candidate.stem,
        "solver": plan.solver,
        "sampling_strategy": "incumbent_local_branching",
        "parent_instance_id": candidate.parent_instance_id,
        "category": candidate.category,
        "difficulty": candidate.difficulty,
        "fold": candidate.fold,
        "role": "train",
        "candidate": candidate.contract_payload(),
        "execution": {"fresh_process": True, "reused": reused},
        "solve": {
            key: payload.get(key)
            for key in (
                "solver_versions",
                "solver_parameter_sha256",
                "original_objective_sense",
                "objective_sense",
                "solve_status",
                "solution_count",
                "solution_objective",
                "best_bound",
                "mip_gap_relative",
                "mip_gap_percent",
                "execution_time_seconds",
                "work_units",
                "best_incumbent_discovery_time_seconds",
                "nodes_current_run",
                "nodes_total",
            )
        },
        "online_incumbent_capture": dict(online),
        "incumbent_trace_audit": dict(trace_audit),
        "checks": {**execution_checks, **solution_checks},
        "gap_sensitivity_memberships": memberships,
        "artifacts": {
            "solution": artifact_record("solution"),
            "incumbents": artifact_record("incumbents"),
            "variable_order": artifact_record("variable_order"),
        },
        "gate_status": gate_status,
        "eligibility": {
            "label_eligible": label_eligible,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": reason_code,
            "next_gate": (
                "derived_graph_generation"
                if label_eligible
                else "increase_budget_or_repair_solve_evidence"
            ),
        },
    }


def _failed_worker_record(
    plan: DerivedSolvePlan,
    candidate: CandidateSpec,
    *,
    returncode: int,
) -> dict[str, Any]:
    return {
        "sample_id": candidate.stem,
        "solver": plan.solver,
        "sampling_strategy": "incumbent_local_branching",
        "parent_instance_id": candidate.parent_instance_id,
        "category": candidate.category,
        "difficulty": candidate.difficulty,
        "fold": candidate.fold,
        "role": "train",
        "candidate": candidate.contract_payload(),
        "execution": {
            "fresh_process": True,
            "reused": False,
            "worker_returncode": returncode,
        },
        "gate_status": "failed",
        "checks": {"worker_completed": False},
        "gap_sensitivity_memberships": [],
        "artifacts": {"solution": None, "incumbents": None, "variable_order": None},
        "eligibility": {
            "label_eligible": False,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": "fresh_solver_worker_failed",
            "next_gate": "repair_worker_and_repeat_candidate",
        },
    }


def _solve_candidate(
    plan: DerivedSolvePlan,
    candidate: CandidateSpec,
    *,
    resume: bool,
) -> dict[str, Any]:
    artifacts = _artifact_paths(plan, candidate)
    solution_path = artifacts["solution"]
    if resume and solution_path.is_file():
        payload = _read_gzip_json(solution_path)
        if (
            payload.get("contract_sha256") == plan.contract_sha256
            and payload.get("candidate_sha256") == candidate.sha256
        ):
            return evaluate_candidate(plan, candidate, payload, reused=True)
    worker_dir = plan.output_dir / ".workers"
    request_path = worker_dir / f"{candidate.stem}.request.json"
    result_path = worker_dir / f"{candidate.stem}.result.json"
    for path in artifacts.values():
        path.unlink(missing_ok=True)
    _write_json(request_path, worker_request(plan, candidate))
    completed = _run_worker_process(request_path, result_path)
    try:
        if completed.returncode != 0 or not result_path.is_file():
            return _failed_worker_record(
                plan, candidate, returncode=completed.returncode
            )
        result = _read_json(result_path)
        if result.get("worker_status") != "completed":
            return _failed_worker_record(plan, candidate, returncode=1)
        return evaluate_candidate(
            plan,
            candidate,
            _read_gzip_json(solution_path),
            reused=False,
        )
    finally:
        request_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)


def run(plan: DerivedSolvePlan, *, resume: bool) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=plan.max_parallel) as executor:
        futures = {
            executor.submit(_solve_candidate, plan, candidate, resume=resume): candidate
            for candidate in plan.candidates
        }
        for future in as_completed(futures):
            candidate = futures[future]
            try:
                records.append(future.result())
            except Exception:
                records.append(_failed_worker_record(plan, candidate, returncode=1))
    records.sort(key=lambda item: str(item["sample_id"]))
    statuses = Counter(str(item["gate_status"]) for item in records)
    eligible = sum(
        bool(item["eligibility"]["label_eligible"]) for item in records
    )
    if statuses["failed"]:
        gate_status = "failed"
        reason_code = "one_or_more_derived_solve_workers_failed"
    elif eligible == len(records):
        gate_status = "passed"
        reason_code = "all_independent_derived_labels_admissible"
    else:
        gate_status = "inconclusive"
        reason_code = "one_or_more_derived_labels_need_additional_budget"
    sensitivity = {
        f"gap_le_{threshold:g}": sum(
            f"gap_le_{threshold:g}" in item["gap_sensitivity_memberships"]
            for item in records
        )
        for threshold in plan.sensitivity_thresholds_relative
    }
    _write_jsonl(plan.output_dir / PER_CANDIDATE_NAME, records)
    return {
        **plan.to_summary(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "execution": {
            "mode": "parallel_fresh_processes",
            "planned_candidates": len(plan.candidates),
            "completed_records": len(records),
            "workers_used": plan.max_parallel,
            "reused_records": sum(item["execution"]["reused"] for item in records),
        },
        "summary": {
            "candidate_count": len(records),
            "label_eligible_count": eligible,
            "passed": statuses["passed"],
            "inconclusive": statuses["inconclusive"],
            "failed": statuses["failed"],
            "eligible_by_gap_sensitivity": sensitivity,
        },
        "gate_status": gate_status,
        "eligibility": {
            "all_labels_eligible": eligible == len(records),
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": reason_code,
            "next_gate": (
                "derived_graph_generation_and_manifest"
                if gate_status == "passed"
                else "review_per_candidate_metrics"
            ),
        },
    }


def _solve_worker(request: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("solver") == "gurobi":
        from cfl_gnn.solvers.gurobi_solution import solve_named_mip
    elif request.get("solver") == "scip":
        from cfl_gnn.solvers.pyscipopt_solution import solve_named_mip
    else:
        raise ValueError("worker solver must be gurobi or scip")
    return solve_named_mip(request)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independently solve one arm of local-branching MIPs."
    )
    parser.add_argument("--solver", choices=SOLVERS)
    parser.add_argument("--candidate_dir", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--time_limit", type=float, default=3600.0)
    parser.add_argument("--node_limit", type=int, default=1_000_000)
    parser.add_argument("--threads_per_candidate", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_parallel", type=int, default=3)
    parser.add_argument("--expected_candidates", type=int)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--_worker_request", help=argparse.SUPPRESS)
    parser.add_argument("--_worker_result", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args._worker_request or args._worker_result:
        if not args._worker_request or not args._worker_result:
            raise ValueError("worker request and result must be supplied together")
        result = _solve_worker(_read_json(Path(args._worker_request)))
        _write_json(Path(args._worker_result), result)
        return 0
    required = {
        "solver": args.solver,
        "candidate_dir": args.candidate_dir,
        "output_dir": args.output_dir,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        print("[ERROR] missing required arguments: " + ", ".join(missing))
        return 2
    if args.resume and args.overwrite:
        print("[ERROR] --resume and --overwrite are mutually exclusive")
        return 2
    try:
        plan = build_plan(
            solver=args.solver,
            candidate_dir=args.candidate_dir,
            output_dir=args.output_dir,
            config_path=args.config,
            time_limit=args.time_limit,
            node_limit=args.node_limit,
            threads_per_candidate=args.threads_per_candidate,
            seed=args.seed,
            max_parallel=args.max_parallel,
            expected_candidates=args.expected_candidates,
        )
        plan.output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan.output_dir / PLAN_NAME
        report_path = plan.output_dir / REPORT_NAME
        if not args.overwrite and not args.resume and (
            plan_path.exists() or report_path.exists()
        ):
            raise FileExistsError(
                "output exists; use another directory, --resume, or --overwrite"
            )
        _write_json(plan_path, plan.to_summary())
        print(
            f"[INFO] solver={plan.solver} | candidates={len(plan.candidates)} | "
            f"contract={plan.contract_sha256} | budget={plan.time_limit}s each"
        )
        print("[INFO] workers are fresh, independent, and receive no warm start")
        print(f"[INFO] Plan: {plan_path}")
        if args.dry_run:
            return 0
        report = run(plan, resume=args.resume)
        _write_json(report_path, report)
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"eligible={report['summary']['label_eligible_count']}/"
            f"{report['summary']['candidate_count']}"
        )
        print(f"[INFO] Report: {report_path}")
        return 1 if report["gate_status"] == "failed" else 0
    except (DerivedMipSolveError, OSError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

