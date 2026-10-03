"""Equal-budget Gurobi/SCIP Neural Diving engineering experiment."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


EXPECTED_ARMS = (
    "gurobi_original",
    "gurobi_incumbent_augmented",
    "scip_original",
    "scip_incumbent_augmented",
)
TARGET_SOLVERS = ("gurobi", "scip")
PLAN_NAME = "mvp_neural_diving_plan.json"
REPORT_NAME = "mvp_neural_diving_report.json"
RUN_METRICS_NAME = "per_run_solver_metrics.csv"
COMPARISONS_NAME = "paired_solver_comparisons.jsonl"
EVALUATION_PLAN_NAME = "mvp_four_arm_evaluation_plan.json"
EVALUATION_REPORT_NAME = "mvp_four_arm_evaluation_report.json"
DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "experiments"
    / "mvp_neural_diving_equal_budget_v1.json"
)


class MvpNeuralDivingError(RuntimeError):
    """Raised when a benchmark contract or artifact fails closed."""


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise MvpNeuralDivingError(f"JSON object required: {Path(path).name}")
    return payload


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    temporary.replace(destination)


def _safe_relative(value: Any, *, field: str) -> Path:
    path = Path(str(value))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise MvpNeuralDivingError(f"unsafe {field}")
    return path


def _required_sha256(value: Any, *, field: str) -> str:
    normalized = str(value).lower()
    if len(normalized) != 64 or any(
        char not in "0123456789abcdef" for char in normalized
    ):
        raise MvpNeuralDivingError(f"invalid {field}")
    return normalized


def _finite(value: Any, *, field: str, minimum: float | None = None) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise MvpNeuralDivingError(f"invalid {field}") from error
    if not math.isfinite(normalized) or (
        minimum is not None and normalized < minimum
    ):
        raise MvpNeuralDivingError(f"invalid {field}")
    return normalized


def _finite_or_none(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(normalized) or abs(normalized) >= 1e100:
        return None
    return normalized


def _gap(objective: Any, bound: Any) -> float | None:
    primal = _finite_or_none(objective)
    dual = _finite_or_none(bound)
    if primal is None or dual is None:
        return None
    return abs(primal - dual) / max(abs(primal), 1e-10)


def _read_hint_rows(
    path: Path,
    *,
    expected_sha256: str,
    expected_semantic_sha256: str,
) -> list[dict[str, Any]]:
    if sha256_file(path) != expected_sha256:
        raise MvpNeuralDivingError("hint artifact SHA-256 mismatch")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if not rows or canonical_sha256(rows) != expected_semantic_sha256:
        raise MvpNeuralDivingError("hint semantic SHA-256 mismatch")
    forbidden = {"target", "label", "ground_truth"}
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or forbidden.intersection(row):
            raise MvpNeuralDivingError("hint contains test labels")
        name = str(row.get("variable_name", ""))
        probability = _finite(row.get("probability"), field="probability")
        confidence = _finite(row.get("confidence"), field="confidence")
        priority = int(row.get("priority", -1))
        prediction = row.get("predicted_value")
        if (
            not name
            or name in names
            or not 0.0 <= probability <= 1.0
            or not 0.0 <= confidence <= 1.0
            or not 0 <= priority <= 100
            or prediction not in (0, 1)
        ):
            raise MvpNeuralDivingError("invalid solver-neutral hint row")
        names.add(name)
    return rows


def select_fixings(
    rows: Sequence[Mapping[str, Any]], fixing_fraction: float
) -> list[dict[str, Any]]:
    """Select the same top-confidence domain fixings for either solver."""
    fraction = _finite(fixing_fraction, field="fixing fraction", minimum=0.0)
    if not 0.0 < fraction <= 1.0 or not rows:
        raise MvpNeuralDivingError("fixing fraction must be in (0, 1]")
    count = max(1, int(math.floor(len(rows) * fraction)))
    ordered = sorted(
        rows,
        key=lambda row: (
            -int(row["priority"]),
            -float(row["confidence"]),
            str(row["variable_name"]),
        ),
    )
    return [
        {
            "variable_name": str(row["variable_name"]),
            "value": int(row["predicted_value"]),
            "priority": int(row["priority"]),
            "confidence": float(row["confidence"]),
        }
        for row in ordered[:count]
    ]


def _plan_contract(plan: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {"contract_sha256", "contract_valid", "task_count", "next_gate"}
    return {key: value for key, value in plan.items() if key not in excluded}


def validate_plan(plan: Mapping[str, Any]) -> None:
    expected = canonical_sha256(_plan_contract(plan))
    if (
        plan.get("contract_valid") is not True
        or plan.get("contract_sha256") != expected
    ):
        raise MvpNeuralDivingError("benchmark plan contract mismatch")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or plan.get("task_count") != len(tasks):
        raise MvpNeuralDivingError("benchmark task inventory mismatch")
    if len({task.get("task_index") for task in tasks}) != len(tasks):
        raise MvpNeuralDivingError("duplicate benchmark task index")


def build_plan(
    evaluation_dir: str | Path,
    base_source_dir: str | Path,
    *,
    time_limit_seconds: int,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Verify PR #36 artifacts and precommit the full factorial run plan."""
    evaluation_root = Path(evaluation_dir).resolve()
    source_root = Path(base_source_dir).resolve()
    evaluation_plan_path = evaluation_root / EVALUATION_PLAN_NAME
    evaluation_report_path = evaluation_root / EVALUATION_REPORT_NAME
    evaluation_plan = load_json(evaluation_plan_path)
    evaluation_report = load_json(evaluation_report_path)
    config = load_json(config_path)
    budget = config.get("time_budget", {})
    minimum = int(budget.get("minimum_seconds", 0))
    maximum = int(budget.get("maximum_seconds", 0))
    requested = int(time_limit_seconds)
    if not minimum <= requested <= maximum:
        raise MvpNeuralDivingError(
            f"time limit must be between {minimum} and {maximum} seconds"
        )
    if (
        evaluation_report.get("gate_status") != "passed"
        or evaluation_report.get("evaluation_contract_sha256")
        != evaluation_plan.get("contract_sha256")
        or evaluation_report.get("arm_selection", {}).get("performed") is not False
        or set(evaluation_report.get("arm_selection", {}).get("forwarded_arms", []))
        != set(EXPECTED_ARMS)
        or not all(evaluation_report.get("common_controls", {}).values())
        or evaluation_report.get("eligibility", {}).get(
            "solver_neutral_hints_eligible_for_engineering_smoke"
        )
        is not True
    ):
        raise MvpNeuralDivingError("PR #36 evaluation contract is not admissible")
    test_records = evaluation_plan.get("test_records")
    if not isinstance(test_records, list) or not test_records:
        raise MvpNeuralDivingError("held-out test inventory is empty")
    parent_records: list[dict[str, Any]] = []
    for record in test_records:
        parent_id = str(record.get("parent_instance_id", ""))
        parent_relative = _safe_relative(
            record.get("parent_mip_relative_path"), field="parent MIP path"
        )
        parent_sha256 = _required_sha256(
            record.get("parent_mip_sha256"), field="parent MIP SHA-256"
        )
        if not parent_id or sha256_file(source_root / parent_relative) != parent_sha256:
            raise MvpNeuralDivingError("held-out parent MIP identity mismatch")
        parent_records.append(
            {
                "parent_instance_id": parent_id,
                "difficulty": str(record.get("difficulty")),
                "fold": int(record.get("fold")),
                "parent_mip_relative_path": parent_relative.as_posix(),
                "parent_mip_sha256": parent_sha256,
            }
        )
    arm_hints: dict[str, dict[str, dict[str, Any]]] = {}
    for arm_id in EXPECTED_ARMS:
        arm = evaluation_report.get("arms", {}).get(arm_id)
        if not isinstance(arm, dict) or arm.get("arm_id") != arm_id:
            raise MvpNeuralDivingError(f"missing PR #36 arm: {arm_id}")
        artifacts = arm.get("hint_artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != len(parent_records):
            raise MvpNeuralDivingError(f"hint inventory mismatch: {arm_id}")
        by_parent: dict[str, dict[str, Any]] = {}
        for artifact in artifacts:
            parent_id = str(artifact.get("parent_instance_id", ""))
            relative = _safe_relative(
                artifact.get("relative_path"), field="hint artifact path"
            )
            compressed_sha = _required_sha256(
                artifact.get("sha256"), field="hint artifact SHA-256"
            )
            semantic_sha = _required_sha256(
                artifact.get("semantic_sha256"), field="hint semantic SHA-256"
            )
            rows = _read_hint_rows(
                evaluation_root / relative,
                expected_sha256=compressed_sha,
                expected_semantic_sha256=semantic_sha,
            )
            if parent_id in by_parent or int(artifact.get("hints", -1)) != len(rows):
                raise MvpNeuralDivingError(f"invalid hint artifact: {arm_id}")
            by_parent[parent_id] = {
                "relative_path": relative.as_posix(),
                "sha256": compressed_sha,
                "semantic_sha256": semantic_sha,
                "hint_count": len(rows),
            }
        if set(by_parent) != {item["parent_instance_id"] for item in parent_records}:
            raise MvpNeuralDivingError(f"hint parents mismatch: {arm_id}")
        arm_hints[arm_id] = by_parent
    fixing_fraction = _finite(
        config.get("neural_diving_operator", {}).get("fixing_fraction"),
        field="fixing fraction",
        minimum=0.0,
    )
    tasks: list[dict[str, Any]] = []
    for parent in parent_records:
        parent_id = parent["parent_instance_id"]
        for target_solver in TARGET_SOLVERS:
            run_specs: list[tuple[str, dict[str, Any] | None]] = [
                ("unguided_control", None)
            ]
            run_specs.extend(
                (arm_id, arm_hints[arm_id][parent_id])
                for arm_id in EXPECTED_ARMS
            )
            for arm_id, hint in run_specs:
                task_index = len(tasks)
                task_payload = {
                    "task_index": task_index,
                    "run_id": f"{target_solver}__{arm_id}__{parent_id}",
                    "run_kind": "control" if hint is None else "guided",
                    "gnn_arm_id": None if hint is None else arm_id,
                    "target_solver": target_solver,
                    **parent,
                    "hint_artifact": hint,
                    "time_limit_seconds": requested,
                    "threads": int(config["threads_per_run"]),
                    "seed": int(config["seed"]),
                    "output_relative_path": (
                        Path("runs")
                        / f"{task_index:03d}_{target_solver}_{arm_id}_{parent_id}.json"
                    ).as_posix(),
                }
                tasks.append(
                    {
                        **task_payload,
                        "task_contract_sha256": canonical_sha256(task_payload),
                    }
                )
    protocol = {
        "schema_version": 1,
        "experiment_stage": "engineering_equal_budget_neural_diving",
        "source_evaluation_plan_sha256": sha256_file(evaluation_plan_path),
        "source_evaluation_report_sha256": sha256_file(evaluation_report_path),
        "source_evaluation_contract_sha256": evaluation_plan["contract_sha256"],
        "experiment_config": config,
        "experiment_config_sha256": sha256_file(config_path),
        "time_limit_seconds": requested,
        "same_time_limit_for_every_task": True,
        "objective_sense_required": "MINIMIZE",
        "fixing_fraction": fixing_fraction,
        "fixing_operator": "top_confidence_domain_fixing_v1",
        "held_out_parents": parent_records,
        "arms": list(EXPECTED_ARMS),
        "target_solvers": list(TARGET_SOLVERS),
        "controls": [f"{solver}_unguided" for solver in TARGET_SOLVERS],
        "tasks": tasks,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **protocol,
        "contract_sha256": canonical_sha256(protocol),
        "contract_valid": True,
        "task_count": len(tasks),
        "next_gate": "fresh_process_solver_task_execution",
    }


def _hardware_fingerprint() -> dict[str, Any]:
    cpu_model = platform.processor().strip()
    cpuinfo = Path("/proc/cpuinfo")
    if not cpu_model and cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                cpu_model = line.split(":", 1)[1].strip()
                break
    payload = {
        "machine": platform.machine(),
        "cpu_model": cpu_model or "unavailable",
        "logical_cpu_count": os.cpu_count(),
    }
    return {**payload, "sha256": canonical_sha256(payload)}


def _gurobi_status(status: int, grb: Any) -> str:
    names = {
        getattr(grb, name): name.lower()
        for name in (
            "OPTIMAL",
            "INFEASIBLE",
            "INF_OR_UNBD",
            "UNBOUNDED",
            "TIME_LIMIT",
            "NODE_LIMIT",
            "INTERRUPTED",
            "NUMERIC",
            "SUBOPTIMAL",
        )
        if hasattr(grb, name)
    }
    return names.get(int(status), f"status_{int(status)}")


def _run_gurobi(
    model_path: Path,
    task: Mapping[str, Any],
    fixings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    build_start = time.perf_counter()
    import gurobipy as gp
    from gurobipy import GRB

    model = gp.read(str(model_path))
    try:
        original_sense = (
            "MINIMIZE" if int(model.ModelSense) == int(GRB.MINIMIZE) else "MAXIMIZE"
        )
        model.ModelSense = GRB.MINIMIZE
        model.Params.OutputFlag = 0
        model.Params.TimeLimit = float(task["time_limit_seconds"])
        model.Params.Threads = int(task["threads"])
        model.Params.Seed = int(task["seed"])
        variables = {str(variable.VarName): variable for variable in model.getVars()}
        for fixing in fixings:
            variable = variables.get(str(fixing["variable_name"]))
            if variable is None or variable.VType not in (GRB.BINARY, GRB.INTEGER):
                raise MvpNeuralDivingError("Gurobi fixing variable mismatch")
            value = float(fixing["value"])
            if value < float(variable.LB) - 1e-9 or value > float(variable.UB) + 1e-9:
                raise MvpNeuralDivingError("Gurobi fixing violates original domain")
            variable.LB = value
            variable.UB = value
        model.update()
        build_time = time.perf_counter() - build_start
        optimize_start = time.perf_counter()
        model.optimize()
        optimize_time = time.perf_counter() - optimize_start
        post_start = time.perf_counter()
        solution_count = int(model.SolCount)
        objective = _finite_or_none(model.ObjVal) if solution_count else None
        bound = _finite_or_none(model.ObjBound)
        relative_gap = (
            _finite_or_none(model.MIPGap) if solution_count else _gap(objective, bound)
        )
        status = _gurobi_status(int(model.Status), GRB)
        outcome = {
            "solver_versions": {
                "gurobi": ".".join(str(item) for item in gp.gurobi.version()),
                "gurobipy": str(getattr(gp, "__version__", "unknown")),
            },
            "original_objective_sense": original_sense,
            "effective_objective_sense": "MINIMIZE",
            "solve_status": status,
            "right_censored": status in {"time_limit", "node_limit"},
            "solution_count": solution_count,
            "best_objective": objective,
            "best_bound": bound,
            "terminal_mip_gap_relative": relative_gap,
            "terminal_mip_gap_percent": (
                None if relative_gap is None else 100.0 * relative_gap
            ),
            "solver_reported_optimize_time_seconds": _finite_or_none(model.Runtime),
            "nodes": int(model.NodeCount),
            "work_units": _finite_or_none(model.Work),
            "model_signature": {
                "variables": int(model.NumVars),
                "constraints": int(model.NumConstrs),
                "nonzeros": int(model.NumNZs),
            },
        }
        post_time = time.perf_counter() - post_start
        return {
            "outcome": outcome,
            "model_build_wall_time_seconds": build_time,
            "model_optimize_wall_time_seconds": optimize_time,
            "post_optimize_extraction_wall_time_seconds": post_time,
        }
    finally:
        model.dispose()


def _run_scip(
    model_path: Path,
    task: Mapping[str, Any],
    fixings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    build_start = time.perf_counter()
    import pyscipopt
    from pyscipopt import Model

    model = Model()
    try:
        model.hideOutput(True)
        model.readProblem(str(model_path))
        original_sense = str(model.getObjectiveSense()).upper()
        model.setMinimize()
        model.setParam("limits/time", float(task["time_limit_seconds"]))
        model.setParam("parallel/maxnthreads", int(task["threads"]))
        model.setParam("randomization/randomseedshift", int(task["seed"]))
        model.setParam("display/verblevel", 0)
        variables = {
            str(variable.name): variable
            for variable in model.getVars(transformed=False)
        }
        for fixing in fixings:
            variable = variables.get(str(fixing["variable_name"]))
            if variable is None or str(variable.vtype()).upper() not in {
                "BINARY",
                "INTEGER",
                "IMPLINT",
            }:
                raise MvpNeuralDivingError("SCIP fixing variable mismatch")
            infeasible, fixed = model.fixVar(variable, float(fixing["value"]))
            if infeasible or not fixed:
                raise MvpNeuralDivingError("SCIP could not apply domain fixing")
        build_time = time.perf_counter() - build_start
        optimize_start = time.perf_counter()
        model.optimize()
        optimize_time = time.perf_counter() - optimize_start
        post_start = time.perf_counter()
        status = str(model.getStatus()).lower()
        solution_count = int(model.getNSols())
        objective = _finite_or_none(model.getObjVal()) if solution_count else None
        bound = _finite_or_none(model.getDualbound())
        relative_gap = _finite_or_none(model.getGap()) if solution_count else None
        outcome = {
            "solver_versions": {
                "scip": ".".join(
                    str(item)
                    for item in (
                        model.getMajorVersion(),
                        model.getMinorVersion(),
                        model.getTechVersion(),
                    )
                ),
                "pyscipopt": str(getattr(pyscipopt, "__version__", "unknown")),
            },
            "original_objective_sense": original_sense,
            "effective_objective_sense": "MINIMIZE",
            "solve_status": status,
            "right_censored": status in {"timelimit", "nodelimit"},
            "solution_count": solution_count,
            "best_objective": objective,
            "best_bound": bound,
            "terminal_mip_gap_relative": relative_gap,
            "terminal_mip_gap_percent": (
                None if relative_gap is None else 100.0 * relative_gap
            ),
            "solver_reported_optimize_time_seconds": _finite_or_none(
                model.getSolvingTime()
            ),
            "nodes": int(model.getNNodes()),
            "nodes_total": int(model.getNTotalNodes()),
            "model_signature": {
                "variables": int(model.getNVars()),
                "constraints": int(model.getNConss()),
            },
        }
        post_time = time.perf_counter() - post_start
        return {
            "outcome": outcome,
            "model_build_wall_time_seconds": build_time,
            "model_optimize_wall_time_seconds": optimize_time,
            "post_optimize_extraction_wall_time_seconds": post_time,
        }
    finally:
        try:
            model.freeProb()
        except Exception:
            pass


Adapter = Callable[
    [Path, Mapping[str, Any], Sequence[Mapping[str, Any]]], dict[str, Any]
]


def run_task(
    plan_path: str | Path,
    evaluation_dir: str | Path,
    base_source_dir: str | Path,
    output_dir: str | Path,
    *,
    task_index: int,
    overwrite: bool = False,
    adapters: Mapping[str, Adapter] | None = None,
) -> dict[str, Any]:
    """Execute exactly one solver run; intended for a fresh Slurm process."""
    total_start = time.perf_counter()
    read_start = time.perf_counter()
    plan = load_json(plan_path)
    validate_plan(plan)
    try:
        task = plan["tasks"][int(task_index)]
    except (IndexError, TypeError) as error:
        raise MvpNeuralDivingError("task index is outside the plan") from error
    if task.get("task_index") != int(task_index):
        raise MvpNeuralDivingError("task index contract mismatch")
    task_payload = {
        key: value for key, value in task.items() if key != "task_contract_sha256"
    }
    if canonical_sha256(task_payload) != task.get("task_contract_sha256"):
        raise MvpNeuralDivingError("task contract SHA-256 mismatch")
    evaluation_root = Path(evaluation_dir).resolve()
    source_root = Path(base_source_dir).resolve()
    output_root = Path(output_dir).resolve()
    output_relative = _safe_relative(
        task.get("output_relative_path"), field="task output path"
    )
    output_path = output_root / output_relative
    if output_path.exists() and not overwrite:
        raise MvpNeuralDivingError("task output exists; use --overwrite")
    evaluation_plan_path = evaluation_root / EVALUATION_PLAN_NAME
    evaluation_report_path = evaluation_root / EVALUATION_REPORT_NAME
    if (
        sha256_file(evaluation_plan_path)
        != plan["source_evaluation_plan_sha256"]
        or sha256_file(evaluation_report_path)
        != plan["source_evaluation_report_sha256"]
    ):
        raise MvpNeuralDivingError("PR #36 artifact identity changed")
    model_relative = _safe_relative(
        task.get("parent_mip_relative_path"), field="parent MIP path"
    )
    model_path = source_root / model_relative
    if sha256_file(model_path) != task.get("parent_mip_sha256"):
        raise MvpNeuralDivingError("held-out MIP SHA-256 mismatch")
    rows: list[dict[str, Any]] = []
    fixings: list[dict[str, Any]] = []
    hint = task.get("hint_artifact")
    if hint is not None:
        hint_relative = _safe_relative(
            hint.get("relative_path"), field="hint artifact path"
        )
        rows = _read_hint_rows(
            evaluation_root / hint_relative,
            expected_sha256=_required_sha256(
                hint.get("sha256"), field="hint artifact SHA-256"
            ),
            expected_semantic_sha256=_required_sha256(
                hint.get("semantic_sha256"), field="hint semantic SHA-256"
            ),
        )
        if len(rows) != int(hint.get("hint_count", -1)):
            raise MvpNeuralDivingError("hint count changed")
        fixings = select_fixings(rows, float(plan["fixing_fraction"]))
    data_read_time = time.perf_counter() - read_start
    selected_fixings_sha256 = canonical_sha256(fixings)
    runner_map: Mapping[str, Adapter] = adapters or {
        "gurobi": _run_gurobi,
        "scip": _run_scip,
    }
    solver = str(task["target_solver"])
    if solver not in runner_map:
        raise MvpNeuralDivingError("target solver adapter is unavailable")
    adapter_result = runner_map[solver](model_path, task, fixings)
    total_time = time.perf_counter() - total_start
    build_time = _finite(
        adapter_result.get("model_build_wall_time_seconds"),
        field="model build time",
        minimum=0.0,
    )
    optimize_time = _finite(
        adapter_result.get("model_optimize_wall_time_seconds"),
        field="model optimize time",
        minimum=0.0,
    )
    post_time = _finite(
        adapter_result.get("post_optimize_extraction_wall_time_seconds"),
        field="post optimize time",
        minimum=0.0,
    )
    accounted = data_read_time + build_time + optimize_time + post_time
    unattributed = max(0.0, total_time - accounted)
    outcome = adapter_result.get("outcome")
    if not isinstance(outcome, dict):
        raise MvpNeuralDivingError("solver adapter returned no outcome")
    report = {
        "schema_version": 1,
        "benchmark_contract_sha256": plan["contract_sha256"],
        "task_contract_sha256": task["task_contract_sha256"],
        "task_index": int(task_index),
        "run_id": task["run_id"],
        "run_kind": task["run_kind"],
        "gnn_arm_id": task["gnn_arm_id"],
        "target_solver": solver,
        "parent_instance_id": task["parent_instance_id"],
        "probe_completed": True,
        "gate_status": "passed",
        "fresh_process_required": True,
        "objective_sense_required": "MINIMIZE",
        "time_budget": {
            "time_limit_seconds": int(task["time_limit_seconds"]),
            "threads": int(task["threads"]),
            "seed": int(task["seed"]),
        },
        "time_regions": {
            "total_wall_time_seconds": total_time,
            "data_read_wall_time_seconds": data_read_time,
            "model_build_wall_time_seconds": build_time,
            "model_optimize_wall_time_seconds": optimize_time,
            "post_optimize_extraction_wall_time_seconds": post_time,
            "unattributed_overhead_wall_time_seconds": unattributed,
        },
        "neural_diving": {
            "operator": plan["fixing_operator"],
            "fixing_fraction": plan["fixing_fraction"],
            "available_hint_count": len(rows),
            "fixed_variable_count": len(fixings),
            "selected_fixings_sha256": selected_fixings_sha256,
            "test_labels_consumed": False,
            "native_advisory_hint_used": False,
        },
        "hardware": _hardware_fingerprint(),
        "outcome": outcome,
        "eligibility": {
            "technical_execution_valid": True,
            "primary_outcomes_complete": (
                outcome.get("terminal_mip_gap_relative") is not None
                and outcome.get("solver_reported_optimize_time_seconds") is not None
            ),
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
    }
    write_json(output_path, report)
    return report


def _timing_valid(record: Mapping[str, Any]) -> bool:
    regions = record.get("time_regions", {})
    required = (
        "total_wall_time_seconds",
        "data_read_wall_time_seconds",
        "model_build_wall_time_seconds",
        "model_optimize_wall_time_seconds",
    )
    try:
        values = {key: float(regions[key]) for key in required}
    except (KeyError, TypeError, ValueError):
        return False
    if any(not math.isfinite(value) or value < 0.0 for value in values.values()):
        return False
    internal = sum(values[key] for key in required if key != "total_wall_time_seconds")
    return values["total_wall_time_seconds"] + 1e-6 >= internal


def _solver_runtime_consistent(record: Mapping[str, Any]) -> bool:
    external = _finite_or_none(
        record.get("time_regions", {}).get("model_optimize_wall_time_seconds")
    )
    reported = _finite_or_none(
        record.get("outcome", {}).get("solver_reported_optimize_time_seconds")
    )
    if external is None or reported is None:
        return False
    tolerance = max(2.0, 0.05 * max(external, reported))
    return abs(external - reported) <= tolerance


def _metric_delta(
    candidate: Mapping[str, Any], reference: Mapping[str, Any]
) -> dict[str, Any]:
    candidate_outcome = candidate["outcome"]
    reference_outcome = reference["outcome"]
    return {
        "terminal_mip_gap_relative_delta": (
            float(candidate_outcome["terminal_mip_gap_relative"])
            - float(reference_outcome["terminal_mip_gap_relative"])
        ),
        "model_optimize_wall_time_seconds_delta": (
            float(candidate["time_regions"]["model_optimize_wall_time_seconds"])
            - float(reference["time_regions"]["model_optimize_wall_time_seconds"])
        ),
    }


def audit_run(
    plan_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Aggregate all fresh-process tasks and apply fail-closed gates."""
    plan = load_json(plan_path)
    validate_plan(plan)
    output_root = Path(output_dir).resolve()
    records: list[dict[str, Any]] = []
    missing: list[int] = []
    for task in plan["tasks"]:
        relative = _safe_relative(
            task.get("output_relative_path"), field="task output path"
        )
        path = output_root / relative
        if not path.is_file():
            missing.append(int(task["task_index"]))
            continue
        record = load_json(path)
        if (
            record.get("benchmark_contract_sha256") != plan["contract_sha256"]
            or record.get("task_contract_sha256") != task["task_contract_sha256"]
            or record.get("gate_status") != "passed"
        ):
            raise MvpNeuralDivingError("task result contract mismatch")
        records.append(record)
    if missing:
        raise MvpNeuralDivingError(f"missing task results: {missing}")
    by_key = {
        (
            record["parent_instance_id"],
            record["target_solver"],
            record["gnn_arm_id"],
        ): record
        for record in records
    }
    controls = all(
        by_key.get((parent["parent_instance_id"], solver, None), {}).get(
            "run_kind"
        )
        == "control"
        for parent in plan["held_out_parents"]
        for solver in TARGET_SOLVERS
    )
    full_factorial = all(
        (parent["parent_instance_id"], solver, arm_id) in by_key
        for parent in plan["held_out_parents"]
        for solver in TARGET_SOLVERS
        for arm_id in EXPECTED_ARMS
    )
    fixing_pairs: dict[tuple[str, str], set[str]] = {}
    for record in records:
        arm_id = record.get("gnn_arm_id")
        if arm_id is None:
            continue
        key = (record["parent_instance_id"], str(arm_id))
        fixing_pairs.setdefault(key, set()).add(
            record["neural_diving"]["selected_fixings_sha256"]
        )
    common_controls = {
        "all_tasks_completed": len(records) == len(plan["tasks"]),
        "same_time_limit_all_tasks": len(
            {record["time_budget"]["time_limit_seconds"] for record in records}
        )
        == 1,
        "same_threads_all_tasks": len(
            {record["time_budget"]["threads"] for record in records}
        )
        == 1,
        "same_seed_all_tasks": len(
            {record["time_budget"]["seed"] for record in records}
        )
        == 1,
        "same_hardware_class_all_tasks": len(
            {record["hardware"]["sha256"] for record in records}
        )
        == 1,
        "effective_objective_minimize_all_tasks": all(
            record["outcome"].get("effective_objective_sense") == "MINIMIZE"
            for record in records
        ),
        "four_time_regions_valid_all_tasks": all(
            _timing_valid(record) for record in records
        ),
        "terminal_gap_observed_all_tasks": all(
            record["outcome"].get("terminal_mip_gap_relative") is not None
            for record in records
        ),
        "solver_runtime_observed_all_tasks": all(
            record["outcome"].get("solver_reported_optimize_time_seconds") is not None
            for record in records
        ),
        "external_and_solver_optimize_times_consistent": all(
            _solver_runtime_consistent(record) for record in records
        ),
        "unguided_control_present_per_solver": controls,
        "four_by_two_guided_factorial_complete": full_factorial,
        "identical_fixings_across_target_solvers": all(
            len(hashes) == 1 for hashes in fixing_pairs.values()
        ),
        "test_labels_absent_from_neural_diving": all(
            record["neural_diving"].get("test_labels_consumed") is False
            for record in records
        ),
    }
    comparisons: list[dict[str, Any]] = []
    if all(record["eligibility"]["primary_outcomes_complete"] for record in records):
        for parent in plan["held_out_parents"]:
            parent_id = parent["parent_instance_id"]
            for solver in TARGET_SOLVERS:
                control = by_key[(parent_id, solver, None)]
                for arm_id in EXPECTED_ARMS:
                    guided = by_key[(parent_id, solver, arm_id)]
                    comparisons.append(
                        {
                            "comparison": "guided_minus_unguided_control",
                            "parent_instance_id": parent_id,
                            "target_solver": solver,
                            "candidate_arm": arm_id,
                            "reference_arm": None,
                            **_metric_delta(guided, control),
                        }
                    )
                for source_solver in TARGET_SOLVERS:
                    original_id = f"{source_solver}_original"
                    augmented_id = f"{source_solver}_incumbent_augmented"
                    comparisons.append(
                        {
                            "comparison": "augmented_minus_original_training",
                            "parent_instance_id": parent_id,
                            "target_solver": solver,
                            "candidate_arm": augmented_id,
                            "reference_arm": original_id,
                            **_metric_delta(
                                by_key[(parent_id, solver, augmented_id)],
                                by_key[(parent_id, solver, original_id)],
                            ),
                        }
                    )
            for arm_id in EXPECTED_ARMS:
                comparisons.append(
                    {
                        "comparison": "scip_minus_gurobi_target_solver",
                        "parent_instance_id": parent_id,
                        "target_solver": "cross_solver",
                        "candidate_arm": arm_id,
                        "reference_arm": arm_id,
                        **_metric_delta(
                            by_key[(parent_id, "scip", arm_id)],
                            by_key[(parent_id, "gurobi", arm_id)],
                        ),
                    }
                )
    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / RUN_METRICS_NAME).open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        fields = [
            "task_index",
            "run_id",
            "run_kind",
            "gnn_arm_id",
            "target_solver",
            "parent_instance_id",
            "solve_status",
            "right_censored",
            "terminal_mip_gap_relative",
            "terminal_mip_gap_percent",
            "total_wall_time_seconds",
            "data_read_wall_time_seconds",
            "model_build_wall_time_seconds",
            "model_optimize_wall_time_seconds",
            "fixed_variable_count",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    **{key: record.get(key) for key in fields},
                    "solve_status": record["outcome"]["solve_status"],
                    "right_censored": record["outcome"]["right_censored"],
                    "terminal_mip_gap_relative": record["outcome"][
                        "terminal_mip_gap_relative"
                    ],
                    "terminal_mip_gap_percent": record["outcome"][
                        "terminal_mip_gap_percent"
                    ],
                    **{
                        key: record["time_regions"][key]
                        for key in (
                            "total_wall_time_seconds",
                            "data_read_wall_time_seconds",
                            "model_build_wall_time_seconds",
                            "model_optimize_wall_time_seconds",
                        )
                    },
                    "fixed_variable_count": record["neural_diving"][
                        "fixed_variable_count"
                    ],
                }
            )
    with (output_root / COMPARISONS_NAME).open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        for comparison in comparisons:
            stream.write(json.dumps(comparison, sort_keys=True, allow_nan=False) + "\n")
    gate_passed = all(common_controls.values())
    report = {
        "schema_version": 1,
        "benchmark_contract_sha256": plan["contract_sha256"],
        "probe_completed": True,
        "gate_status": "passed" if gate_passed else "failed",
        "experiment_stage": "engineering_equal_budget_neural_diving",
        "execution": {
            "planned_runs": len(plan["tasks"]),
            "completed_runs": len(records),
            "held_out_parents": len(plan["held_out_parents"]),
            "guided_runs": sum(record["run_kind"] == "guided" for record in records),
            "control_runs": sum(record["run_kind"] == "control" for record in records),
        },
        "time_budget": {
            "selected_seconds": plan["time_limit_seconds"],
            "permitted_minimum_seconds": plan["experiment_config"]["time_budget"][
                "minimum_seconds"
            ],
            "permitted_maximum_seconds": plan["experiment_config"]["time_budget"][
                "maximum_seconds"
            ],
            "same_for_every_run": common_controls["same_time_limit_all_tasks"],
        },
        "time_region_semantics": plan["experiment_config"]["time_regions"],
        "primary_outcomes": [
            "terminal_mip_gap_relative",
            "model_optimize_wall_time_seconds",
        ],
        "common_controls": common_controls,
        "summary_by_target_solver": {
            solver: {
                "runs": sum(record["target_solver"] == solver for record in records),
                "right_censored_runs": sum(
                    record["target_solver"] == solver
                    and record["outcome"]["right_censored"]
                    for record in records
                ),
            }
            for solver in TARGET_SOLVERS
        },
        "outputs": {
            "per_run_metrics": RUN_METRICS_NAME,
            "per_run_metrics_sha256": sha256_file(output_root / RUN_METRICS_NAME),
            "paired_comparisons": COMPARISONS_NAME,
            "paired_comparisons_sha256": sha256_file(
                output_root / COMPARISONS_NAME
            ),
        },
        "eligibility": {
            "engineering_comparison_eligible": gate_passed,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": (
                "equal_budget_neural_diving_smoke_completed"
                if gate_passed
                else "equal_budget_neural_diving_gate_failed"
            ),
            "next_gate": (
                "mvp_four_arm_comparison_and_reproducibility_review"
                if gate_passed
                else "review_failed_solver_runs"
            ),
        },
    }
    write_json(output_root / REPORT_NAME, report)
    return report
