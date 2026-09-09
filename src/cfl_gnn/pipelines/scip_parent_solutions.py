"""Shared original-parent solve pipeline for Gurobi and PySCIPOpt.

The historical module name is retained for import compatibility.  New code
should import :mod:`cfl_gnn.pipelines.parent_solutions`.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.experiments.mvp_contract import load_experiment_config
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.solvers.pyscipopt_solution import sha256_file, solve_named_mip
from cfl_gnn.splits.instance_folds import role_for_fold


SCHEMA_VERSION = 1
PLAN_NAME = "scip_parent_solve_plan.json"
REPORT_NAME = "scip_parent_solve_report.json"
SOLUTION_NAME = "parent_solution.json.gz"
INCUMBENTS_NAME = "incumbents.parquet"
VARIABLE_ORDER_NAME = "incumbent_variable_order.json.gz"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"


class ScipParentSolveError(RuntimeError):
    """Backward-compatible parent-solve contract error."""


ParentSolveError = ScipParentSolveError


def plan_name(solver: str) -> str:
    """Return the solver-specific parent plan artifact name."""
    if solver not in {"gurobi", "scip"}:
        raise ValueError("solver must be gurobi or scip")
    return f"{solver}_parent_solve_plan.json"


def report_name(solver: str) -> str:
    """Return the solver-specific parent report artifact name."""
    if solver not in {"gurobi", "scip"}:
        raise ValueError("solver must be gurobi or scip")
    return f"{solver}_parent_solve_report.json"


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


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ScipParentSolveError("worker result must be a JSON object")
    return value


def _read_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ScipParentSolveError("solution artifact must be a JSON object")
    return value


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
class ParentSolvePlan:
    solver: str
    parent_mip: Path
    output_dir: Path
    parent_instance_id: str
    category: str
    difficulty: str
    fold: int
    role: str
    experiment_contract_sha256: str
    maximum_admissible_relative_gap: float
    time_limit: float
    node_limit: int
    seed: int
    threads: int
    solver_profile: str

    @property
    def parent_sha256(self) -> str:
        return sha256_file(self.parent_mip)

    @property
    def contract_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": f"{self.solver}_original_parent_solution",
            "experiment_contract_sha256": self.experiment_contract_sha256,
            "parent": {
                "source_instance_id": self.parent_instance_id,
                "category": self.category,
                "difficulty": self.difficulty,
                "fold": self.fold,
                "role": self.role,
                "file_name": self.parent_mip.name,
                "sha256": self.parent_sha256,
            },
            "solver_contract": {
                "solver": self.solver,
                "interface": (
                    "gurobipy" if self.solver == "gurobi" else "pyscipopt"
                ),
                "solver_profile": self.solver_profile,
                "force_minimize": True,
                "time_limit_seconds": self.time_limit,
                "node_limit": self.node_limit,
                "threads": self.threads,
                "seed": self.seed,
                "fresh_process": True,
                "warm_start_supplied": False,
                "event_handler": (
                    "MIPSOL" if self.solver == "gurobi" else "BESTSOLFOUND"
                ),
                "event_handler_api": (
                    "gurobipy_Model.optimize_callback"
                    if self.solver == "gurobi"
                    else "Model.attachEventHandlerCallback"
                ),
                "incumbent_vectors": "streamed_float64_parquet",
            },
            "gap_policy": {
                "maximum_admissible_relative_gap": (
                    self.maximum_admissible_relative_gap
                )
            },
            "eligibility": {
                "label_eligible": False,
                "augmentation_source_eligible": False,
                "dataset_eligible": False,
                "scientific_reporting_eligible": False,
            },
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    def to_summary(self) -> dict[str, Any]:
        outputs = {
            "solution": SOLUTION_NAME,
            "incumbents": INCUMBENTS_NAME,
            "variable_order": VARIABLE_ORDER_NAME,
            "plan": plan_name(self.solver),
            "report": report_name(self.solver),
        }
        if self.solver == "gurobi":
            outputs["legacy_plan_alias"] = PLAN_NAME
            outputs["legacy_report_alias"] = REPORT_NAME
        return {
            **self.contract_payload,
            "contract_sha256": self.contract_sha256,
            "outputs": outputs,
        }


def _time_regions_valid(payload: Mapping[str, Any]) -> bool:
    regions = payload.get("time_regions")
    if not isinstance(regions, Mapping):
        return False
    required = (
        "total_wall_time_seconds",
        "data_read_wall_time_seconds",
        "model_build_wall_time_seconds",
        "model_optimize_wall_time_seconds",
    )
    try:
        values = {key: float(regions[key]) for key in required}
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    if not all(math.isfinite(value) and value >= 0.0 for value in values.values()):
        return False
    component_total = sum(values[key] for key in required if key != required[0])
    return values[required[0]] + 1e-6 >= component_total


def build_plan(
    *,
    parent_mip: str | Path,
    output_dir: str | Path,
    parent_instance_id: str,
    category: str,
    difficulty: str,
    fold: int,
    config_path: str | Path,
    time_limit: float,
    node_limit: int,
    seed: int,
    threads: int,
    solver_profile: str,
    solver: str = "scip",
) -> ParentSolvePlan:
    source = Path(parent_mip).resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise FileNotFoundError(f"missing parent MIP: {source}")
    config = load_experiment_config(config_path)
    if difficulty not in {"easy", "medium", "hard"}:
        raise ValueError("difficulty must be easy, medium, or hard")
    if solver_profile != "default":
        raise ValueError("the parent MVP solve is precommitted to the default profile")
    if solver not in {"gurobi", "scip"}:
        raise ValueError("solver must be gurobi or scip")
    role = role_for_fold(int(fold), config.rotation)
    return ParentSolvePlan(
        solver=solver,
        parent_mip=source,
        output_dir=Path(output_dir).resolve(),
        parent_instance_id=str(parent_instance_id),
        category=str(category),
        difficulty=difficulty,
        fold=int(fold),
        role=role,
        experiment_contract_sha256=config.contract_sha256,
        maximum_admissible_relative_gap=(
            config.gap_policy.maximum_admissible_relative_gap
        ),
        time_limit=_positive(time_limit, field="time_limit"),
        node_limit=_positive_int(node_limit, field="node_limit"),
        seed=int(seed),
        threads=_positive_int(threads, field="threads"),
        solver_profile=solver_profile,
    )


def worker_request(plan: ParentSolvePlan) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "candidate_path": str(plan.parent_mip),
        "candidate_file_name": plan.parent_mip.name,
        "candidate_sha256": plan.parent_sha256,
        "solution_path": str(plan.output_dir / SOLUTION_NAME),
        "incumbent_stream_path": str(plan.output_dir / INCUMBENTS_NAME),
        "variable_order_path": str(plan.output_dir / VARIABLE_ORDER_NAME),
        "capture_incumbent_vectors": True,
        "force_minimize": True,
        "time_limit": plan.time_limit,
        "node_limit": plan.node_limit,
        "threads": plan.threads,
        "seed": plan.seed,
        "solver_profile": plan.solver_profile,
    }


def _run_fresh_worker(plan: ParentSolvePlan) -> None:
    request_path = plan.output_dir / ".worker_request.json"
    result_path = plan.output_dir / ".worker_result.json"
    _write_json(request_path, worker_request(plan))
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            f"cfl_gnn.cli.collect_{plan.solver}_parent_solution",
            "--_worker_request",
            str(request_path),
            "--_worker_result",
            str(result_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        if completed.returncode != 0:
            raise ScipParentSolveError(
                f"fresh {plan.solver} parent worker failed: "
                + completed.stderr.strip()[-500:]
            )
        result = _read_json(result_path)
        if result.get("worker_status") != "completed":
            raise ScipParentSolveError(
                f"fresh {plan.solver} parent worker did not complete"
            )
    finally:
        request_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)


def evaluate_solution(plan: ParentSolvePlan, payload: Mapping[str, Any]) -> dict[str, Any]:
    online = payload.get("online_incumbent_capture", {})
    trace_audit = payload.get("incumbent_trace_audit", {})
    gap = payload.get("mip_gap_relative")
    feasible = (
        payload.get("solver_feasibility_check") is True
        and int(payload.get("solution_count", 0)) > 0
        and payload.get("solution_objective") is not None
    )
    gap_valid = (
        gap is not None
        and math.isfinite(float(gap))
        and 0.0 <= float(gap) <= plan.maximum_admissible_relative_gap + 1e-12
    )
    events = int(online.get("events_recorded", 0))
    streamed = int(online.get("vectors_streamed", 0))
    checks = {
        "parent_sha256_match": payload.get("candidate_sha256") == plan.parent_sha256,
        "solution_source_match": payload.get("solution_source")
        == f"independent_{'gurobi' if plan.solver == 'gurobi' else 'pyscipopt'}_optimization",
        "solver_feasibility_check_space": payload.get(
            "solver_feasibility_check_space"
        )
        == (
            "original_model_solution_quality"
            if plan.solver == "gurobi"
            else "original_problem"
        ),
        "fresh_process": payload.get("fresh_process") is True,
        "zero_pre_solve_solutions": payload.get("pre_solve_solution_count") == 0,
        "no_warm_start": payload.get("warm_start_supplied") is False,
        "objective_minimize": payload.get("objective_sense") == "minimize",
        "feasible_solution": feasible,
        "online_incumbent_observed": events > 0,
        "callback_errors_absent": online.get("capture_error_count") == 0,
        "stream_matches_events": events == streamed,
        "stream_committed": online.get("stream_committed") is True,
        "trace_consistent": trace_audit.get("incumbent_trace_consistent") is True,
        "named_solution_present": bool(payload.get("variables")),
        "terminal_gap_finite": gap is not None and math.isfinite(float(gap)),
        "four_time_regions_valid": _time_regions_valid(payload),
    }
    instrumentation_valid = all(checks.values())
    label_eligible = instrumentation_valid and gap_valid
    augmentation_eligible = label_eligible and plan.role == "train"
    if augmentation_eligible:
        gate_status = "passed"
        reason_code = f"{plan.solver}_parent_incumbent_eligible_for_local_branching"
    elif instrumentation_valid:
        gate_status = "inconclusive"
        reason_code = (
            "parent_not_in_training_partition"
            if plan.role != "train"
            else "terminal_gap_above_augmentation_policy"
        )
    else:
        gate_status = "failed"
        reason_code = f"{plan.solver}_parent_solution_instrumentation_failed"
    solution_path = plan.output_dir / SOLUTION_NAME
    incumbent_path = plan.output_dir / INCUMBENTS_NAME
    order_path = plan.output_dir / VARIABLE_ORDER_NAME
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "gate_status": gate_status,
        "parent": plan.contract_payload["parent"],
        "solve": {
            key: payload.get(key)
            for key in (
                "original_objective_sense",
                "objective_sense",
                "solve_status",
                "solution_count",
                "solution_objective",
                "best_bound",
                "mip_gap_relative",
                "mip_gap_percent",
                "execution_time_seconds",
                "best_incumbent_discovery_time_seconds",
                "nodes_current_run",
                "nodes_total",
            )
        },
        "time_regions": dict(payload.get("time_regions", {})),
        "time_region_semantics": dict(payload.get("time_region_semantics", {})),
        "performance_feature_tags": dict(
            payload.get("performance_feature_tags", {})
        ),
        "solver_versions": dict(payload.get("solver_versions", {})),
        "solver_parameter_map": dict(payload.get("solver_parameter_map", {})),
        "solver_parameter_sha256": payload.get("solver_parameter_sha256"),
        "online_incumbent_capture": dict(online),
        "incumbent_trace_audit": dict(trace_audit),
        "checks": checks,
        "artifacts": {
            "solution": {
                "file_name": solution_path.name,
                "sha256": sha256_file(solution_path),
            },
            "incumbents": {
                "file_name": incumbent_path.name,
                "sha256": sha256_file(incumbent_path),
                "records": streamed,
            },
            "variable_order": {
                "file_name": order_path.name,
                "sha256": sha256_file(order_path),
            },
        },
        "eligibility": {
            "label_eligible": label_eligible,
            "augmentation_source_eligible": augmentation_eligible,
            "dataset_eligible": False,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": reason_code,
            "next_gate": (
                f"{plan.solver}_original_parent_local_branching_generation"
                if augmentation_eligible
                else "increase_budget_or_repair_instrumentation"
            ),
        },
    }


def run(plan: ParentSolvePlan) -> dict[str, Any]:
    _run_fresh_worker(plan)
    payload = _read_gzip_json(plan.output_dir / SOLUTION_NAME)
    return evaluate_solution(plan, payload)


def build_parser(*, solver: str = "scip") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Solve one original CFL parent with online {solver} incumbents."
    )
    parser.add_argument("--parent_mip", type=Path)
    parser.add_argument("--parent_instance_id")
    parser.add_argument("--category")
    parser.add_argument("--difficulty", choices=("easy", "medium", "hard"))
    parser.add_argument("--fold", type=int, choices=range(5))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--time_limit", type=float, default=3600.0)
    parser.add_argument("--node_limit", type=int, default=1_000_000)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--solver_profile", default="default")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--_worker_request", help=argparse.SUPPRESS)
    parser.add_argument("--_worker_result", help=argparse.SUPPRESS)
    return parser


def main(
    argv: Sequence[str] | None = None, *, solver: str = "scip"
) -> int:
    args = build_parser(solver=solver).parse_args(argv)
    if args._worker_request or args._worker_result:
        if not args._worker_request or not args._worker_result:
            raise ValueError("worker request and result must be supplied together")
        if solver == "gurobi":
            from cfl_gnn.solvers.gurobi_solution import solve_named_mip as solve
        else:
            solve = solve_named_mip
        result = solve(_read_json(Path(args._worker_request)))
        _write_json(Path(args._worker_result), result)
        return 0
    required = {
        "parent_mip": args.parent_mip,
        "parent_instance_id": args.parent_instance_id,
        "category": args.category,
        "difficulty": args.difficulty,
        "fold": args.fold,
        "output_dir": args.output_dir,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        print("[ERROR] missing required arguments: " + ", ".join(missing))
        return 2
    try:
        plan = build_plan(
            parent_mip=args.parent_mip,
            output_dir=args.output_dir,
            parent_instance_id=args.parent_instance_id,
            category=args.category,
            difficulty=args.difficulty,
            fold=args.fold,
            config_path=args.config,
            time_limit=args.time_limit,
            node_limit=args.node_limit,
            seed=args.seed,
            threads=args.threads,
            solver_profile=args.solver_profile,
            solver=solver,
        )
        plan.output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan.output_dir / plan_name(solver)
        report_path = plan.output_dir / report_name(solver)
        if not args.overwrite and (
            report_path.exists() or (args.dry_run and plan_path.exists())
        ):
            raise FileExistsError("output exists; choose another directory or use --overwrite")
        _write_json(plan_path, plan.to_summary())
        if solver == "gurobi":
            _write_json(plan.output_dir / PLAN_NAME, plan.to_summary())
        print(
            f"[INFO] parent={plan.parent_instance_id} | fold={plan.fold} | "
            f"role={plan.role} | contract={plan.contract_sha256}"
        )
        callback = "MIPSOL" if solver == "gurobi" else "BESTSOLFOUND"
        print(f"[INFO] solver={solver} | callback={callback} | passive=true | vectors=streamed")
        print(f"[INFO] Plan: {plan_path}")
        if args.dry_run:
            return 0
        report = run(plan)
        _write_json(report_path, report)
        if solver == "gurobi":
            _write_json(plan.output_dir / REPORT_NAME, report)
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"events={report['online_incumbent_capture']['events_recorded']} | "
            f"gap={report['solve']['mip_gap_percent']}% | "
            f"augmentation_eligible="
            f"{str(report['eligibility']['augmentation_source_eligible']).lower()}"
        )
        print(f"[INFO] Report: {report_path}")
        return 1 if report["gate_status"] == "failed" else 0
    except (OSError, ValueError, ScipParentSolveError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
