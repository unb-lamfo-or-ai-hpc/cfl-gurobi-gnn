"""Plan, execute, and audit a resumable paired augmentation campaign.

This module scales the already validated single-parent local-branching and
independent-label pipelines.  Persisted contracts contain only repository- or
run-root-relative paths; absolute execution paths are supplied by the CLI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 1
PLAN_NAME = "scalable_augmentation_plan.json"
TASKS_NAME = "scalable_augmentation_tasks.jsonl"
REPORT_NAME = "scalable_augmentation_audit_report.json"
STATUS_NAME = "scalable_augmentation_task_status.jsonl"
SOURCE_INDEX_NAME = "derived_source_index.jsonl"
SOLVERS = ("gurobi", "scip")


class ScalableAugmentationError(RuntimeError):
    """Raised when a campaign contract or one of its artifacts is invalid."""


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise ScalableAugmentationError(
            f"unreadable JSON artifact: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise ScalableAugmentationError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise TypeError(f"line {line_number} is not an object")
                records.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise ScalableAugmentationError(
            f"unreadable JSONL artifact: {path.name}"
        ) from error
    return records


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(record, sort_keys=True, allow_nan=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def _safe_relative(value: Any, *, field: str) -> Path:
    raw = str(value)
    relative = Path(raw)
    if not raw or relative.is_absolute() or ".." in relative.parts:
        raise ScalableAugmentationError(f"unsafe {field}")
    return relative


def _artifact(
    report: Mapping[str, Any], name: str, run_dir: Path
) -> tuple[str, str]:
    descriptor = report.get("artifacts", {}).get(name)
    if not isinstance(descriptor, Mapping):
        raise ScalableAugmentationError(f"missing parent {name} artifact")
    file_name = str(descriptor.get("file_name", ""))
    if Path(file_name).name != file_name:
        raise ScalableAugmentationError(f"unsafe parent {name} artifact name")
    path = run_dir / file_name
    digest = str(descriptor.get("sha256", ""))
    if not path.is_file() or sha256_file(path) != digest:
        raise ScalableAugmentationError(f"parent {name} artifact SHA-256 mismatch")
    return file_name, digest


def _load_experiment_policy(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    augmentation = value.get("augmentation")
    gap_policy = value.get("gap_policy")
    if not isinstance(augmentation, Mapping) or not isinstance(gap_policy, Mapping):
        raise ScalableAugmentationError("experiment policy is incomplete")
    radius = augmentation.get("radius_policy")
    if not isinstance(radius, Mapping):
        raise ScalableAugmentationError("local-branching radius policy is missing")
    fractions = [float(item) for item in radius.get("fractions", [])]
    maximum = int(augmentation.get("maximum_derived_per_parent", 0))
    if not fractions or maximum <= 0 or maximum != len(fractions):
        raise ScalableAugmentationError("local-branching radius policy is invalid")
    maximum_gap = float(gap_policy.get("maximum_admissible_relative_gap", -1.0))
    if maximum_gap < 0.0 or maximum_gap > 1.0:
        raise ScalableAugmentationError("maximum admissible MIP gap is invalid")
    return {
        "experiment_config_sha256": sha256_file(path),
        "objective_sense": value.get("objective_sense"),
        "rotation": int(value.get("rotation", -1)),
        "operator": augmentation.get("operator"),
        "train_only": augmentation.get("train_only") is True,
        "inherit_parent_fold": augmentation.get("inherit_parent_fold") is True,
        "parent_weighting": augmentation.get("parent_weighting"),
        "maximum_derived_per_parent": maximum,
        "radius_fractions": fractions,
        "minimum_radius": int(radius.get("minimum_radius", 0)),
        "maximum_admissible_relative_gap": maximum_gap,
        "gap_sensitivity_thresholds_relative": [
            float(item)
            for item in gap_policy.get("sensitivity_thresholds_relative", [])
        ],
    }


def _validate_policy(policy: Mapping[str, Any]) -> None:
    checks = (
        policy.get("objective_sense") == "MINIMIZE",
        policy.get("operator") == "incumbent_local_branching_v1",
        policy.get("train_only") is True,
        policy.get("inherit_parent_fold") is True,
        policy.get("parent_weighting") == "equal_parent_mass",
        int(policy.get("minimum_radius", 0)) >= 1,
    )
    if not all(checks):
        raise ScalableAugmentationError("experiment policy violates the MVP contract")


def build_campaign_plan(
    *,
    parent_collection_plan_dir: str | Path,
    parent_collection_progress_dir: str | Path,
    parent_collection_run_root: str | Path,
    base_source_dir: str | Path,
    output_dir: str | Path,
    experiment_config_path: str | Path,
    time_limit_seconds: float = 3600.0,
    node_limit: int = 1_000_000,
    threads_per_candidate: int = 1,
    max_parallel_tasks: int = 2,
    instances: Sequence[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Freeze eligible train-parent pairs into deterministic solver tasks."""
    plan_root = Path(parent_collection_plan_dir).resolve()
    progress_root = Path(parent_collection_progress_dir).resolve()
    run_root = Path(parent_collection_run_root).resolve()
    source_root = Path(base_source_dir).resolve()
    output = Path(output_dir).resolve()
    expected = (output / PLAN_NAME, output / TASKS_NAME)
    if not overwrite and any(path.exists() for path in expected):
        raise ScalableAugmentationError("campaign outputs exist; use --overwrite")
    parent_plan = _read_json(plan_root / "parent_collection_plan.json")
    parent_contract = str(parent_plan.get("contract_sha256", ""))
    if not parent_contract:
        raise ScalableAugmentationError("parent collection contract is missing")
    progress_report_path = progress_root / "parent_collection_progress_report.json"
    progress_report = _read_json(progress_report_path)
    if (
        progress_report.get("gate_status") != "passed"
        or progress_report.get("parent_collection_contract_sha256")
        != parent_contract
    ):
        raise ScalableAugmentationError("parent progress contract is not admissible")
    eligibility_path = progress_root / "paired_parent_eligibility.jsonl"
    if (
        progress_report.get("outputs", {})
        .get("paired_parent_eligibility.jsonl", {})
        .get("sha256")
        != sha256_file(eligibility_path)
    ):
        raise ScalableAugmentationError("paired eligibility SHA-256 mismatch")
    policy = _load_experiment_policy(Path(experiment_config_path).resolve())
    _validate_policy(policy)
    if float(time_limit_seconds) not in {3600.0, 14400.0}:
        raise ScalableAugmentationError(
            "derived solve time limit must be 3600 or 14400 seconds"
        )
    if int(node_limit) <= 0 or int(threads_per_candidate) != 1:
        raise ScalableAugmentationError(
            "derived solve requires a positive node limit and one thread"
        )
    if int(max_parallel_tasks) <= 0:
        raise ScalableAugmentationError("max_parallel_tasks must be positive")
    requested = None if instances is None else set(instances)
    eligibility = _read_jsonl(eligibility_path)
    selected = []
    for record in eligibility:
        parent_id = str(record.get("source_instance_id", ""))
        if requested is not None and parent_id not in requested:
            continue
        if (
            record.get("role") == "train"
            and record.get("paired_label_eligible") is True
            and record.get("paired_augmentation_source_eligible") is True
        ):
            selected.append(record)
    selected.sort(key=lambda item: str(item["source_instance_id"]))
    if requested is not None:
        found = {str(item["source_instance_id"]) for item in selected}
        if found != requested:
            raise ScalableAugmentationError(
                "one or more requested parents are not paired train-eligible"
            )
    if not selected:
        raise ScalableAugmentationError(
            "no paired train parent is augmentation eligible"
        )
    task_lookup = {
        (str(task["source_instance_id"]), str(task["solver"])): task
        for task in parent_plan.get("tasks", [])
    }
    tasks: list[dict[str, Any]] = []
    for pair_index, record in enumerate(selected):
        parent_id = str(record["source_instance_id"])
        pair_tasks = []
        for solver in SOLVERS:
            try:
                parent_task = task_lookup[(parent_id, solver)]
            except KeyError as error:
                raise ScalableAugmentationError(
                    f"missing {solver} parent task for {parent_id}"
                ) from error
            parent_relative = _safe_relative(
                parent_task["parent_mip_relative_path"], field="parent MIP path"
            )
            parent_path = source_root / parent_relative
            if (
                not parent_path.is_file()
                or sha256_file(parent_path) != parent_task.get("parent_mip_sha256")
            ):
                raise ScalableAugmentationError(
                    f"parent MIP is missing or changed: {parent_id}"
                )
            parent_run_relative = _safe_relative(
                parent_task["run_dir_relative_path"], field="parent run path"
            )
            parent_run = run_root / parent_run_relative
            report_name = f"{solver}_parent_solve_report.json"
            report_path = parent_run / report_name
            report = _read_json(report_path)
            checks = report.get("checks")
            if (
                report.get("parent", {}).get("sha256")
                != parent_task.get("parent_mip_sha256")
                or not isinstance(checks, Mapping)
                or not checks
                or not all(checks.values())
                or report.get("eligibility", {}).get(
                    "augmentation_source_eligible"
                )
                is not True
            ):
                raise ScalableAugmentationError(
                    f"inadmissible {solver} parent solution: {parent_id}"
                )
            solution_name, solution_sha = _artifact(report, "solution", parent_run)
            relative_base = Path(solver) / str(parent_task["category"]) / parent_id
            pair_tasks.append(
                {
                    "task_index": len(tasks) + len(pair_tasks),
                    "pair_index": pair_index,
                    "solver": solver,
                    "source_instance_id": parent_id,
                    "category": str(parent_task["category"]),
                    "difficulty": str(parent_task["difficulty"]),
                    "fold": int(parent_task["fold"]),
                    "role": "train",
                    "parent_mip_relative_path": parent_relative.as_posix(),
                    "parent_mip_sha256": str(parent_task["parent_mip_sha256"]),
                    "parent_solution_relative_path": (
                        parent_run_relative / solution_name
                    ).as_posix(),
                    "parent_solution_sha256": solution_sha,
                    "parent_solve_contract_sha256": str(
                        report["contract_sha256"]
                    ),
                    "incumbent_format": (
                        "gurobi_solution_json"
                        if solver == "gurobi"
                        else "pyscipopt_solution_json"
                    ),
                    "variant_run_relative_path": (
                        Path("variants") / relative_base
                    ).as_posix(),
                    "solve_run_relative_path": (
                        Path("derived_solutions") / relative_base
                    ).as_posix(),
                }
            )
        tasks.extend(pair_tasks)
    task_payload_hash = canonical_sha256(tasks)
    contract = {
        "schema_version": SCHEMA_VERSION,
        "dataset_variant": "scalable_paired_local_branching_v1",
        "parent_collection_contract_sha256": parent_contract,
        "parent_collection_progress_report_sha256": sha256_file(
            progress_report_path
        ),
        "paired_parent_eligibility_sha256": sha256_file(eligibility_path),
        "experiment_policy": policy,
        "priority_solver": "gurobi",
        "scip_role": "matched_comparison_only",
        "graph_authority": "gurobi",
        "graph_identity": "one_graph_per_mathematical_mip",
        "derived_partition_policy": "train_only_inherit_parent_fold",
        "solve_contract": {
            "fresh_process_per_candidate": True,
            "warm_start_supplied": False,
            "parent_incumbent_consumed": False,
            "time_limit_seconds_per_candidate": float(time_limit_seconds),
            "node_limit_per_candidate": int(node_limit),
            "threads_per_candidate": int(threads_per_candidate),
            "max_parallel_tasks": int(max_parallel_tasks),
            "seed": 42,
        },
        "eligible_parents": [
            {
                key: record[key]
                for key in (
                    "source_instance_id",
                    "category",
                    "difficulty",
                    "fold",
                    "role",
                )
            }
            for record in selected
        ],
        "tasks_sha256": task_payload_hash,
    }
    plan = {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "summary": {
            "paired_train_parents": len(selected),
            "solver_tasks": len(tasks),
            "planned_derived_mips": (
                len(tasks) * int(policy["maximum_derived_per_parent"])
            ),
            "excluded_non_train_or_ineligible_parents": len(eligibility)
            - len(selected),
        },
        "eligibility": {
            "execution_ready": True,
            "development_only": progress_report.get("eligibility", {}).get(
                "development_only", True
            ),
            "scientific_reporting_eligible": False,
        },
        "decision": {"next_gate": "paired_local_branching_task_execution"},
    }
    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / TASKS_NAME, tasks)
    _write_json(output / PLAN_NAME, plan)
    return plan


def validate_plan(plan: Mapping[str, Any], tasks: Sequence[Mapping[str, Any]]) -> None:
    ignored = {"contract_sha256", "summary", "eligibility", "decision"}
    contract = {key: value for key, value in plan.items() if key not in ignored}
    if canonical_sha256(contract) != plan.get("contract_sha256"):
        raise ScalableAugmentationError("augmentation plan contract hash mismatch")
    if canonical_sha256(list(tasks)) != plan.get("tasks_sha256"):
        raise ScalableAugmentationError("augmentation task manifest hash mismatch")
    if len(tasks) % 2 or {str(item["solver"]) for item in tasks} != set(SOLVERS):
        raise ScalableAugmentationError("augmentation tasks are not solver-paired")


def _generation_valid(
    task: Mapping[str, Any], directory: Path
) -> tuple[bool, list[int]]:
    report_path = directory / "local_branching_generation_report.json"
    if not report_path.is_file():
        return False, []
    report = _read_json(report_path)
    outputs = report.get("outputs")
    if (
        report.get("gate_status") != "passed"
        or report.get("solver") != task.get("solver")
        or report.get("parent_instance_id") != task.get("source_instance_id")
        or report.get("parent_mip_sha256") != task.get("parent_mip_sha256")
        or not isinstance(outputs, list)
        or not outputs
    ):
        return False, []
    radii = []
    for output in outputs:
        candidate = directory / str(output.get("file_name", ""))
        provenance = directory / str(output.get("provenance_file_name", ""))
        if (
            not candidate.is_file()
            or sha256_file(candidate) != output.get("sha256")
            or not provenance.is_file()
        ):
            return False, []
        radii.append(int(output["radius"]))
    return True, sorted(radii)


def _solve_valid(task: Mapping[str, Any], directory: Path) -> bool:
    report_path = directory / "derived_mip_solution_report.json"
    plan_path = directory / "derived_mip_solution_plan.json"
    metrics_path = directory / "per_candidate_derived_metrics.jsonl"
    if not all(path.is_file() for path in (report_path, plan_path, metrics_path)):
        return False
    report = _read_json(report_path)
    solve_plan = _read_json(plan_path)
    metrics = _read_jsonl(metrics_path)
    return bool(
        report.get("gate_status") == "passed"
        and report.get("solver") == task.get("solver")
        and report.get("contract_sha256") == solve_plan.get("contract_sha256")
        and report.get("eligibility", {}).get("all_labels_eligible") is True
        and len(metrics) == report.get("summary", {}).get("candidate_count")
        and all(
            item.get("gate_status") == "passed"
            and item.get("eligibility", {}).get("label_eligible") is True
            and item.get("parent_instance_id") == task.get("source_instance_id")
            for item in metrics
        )
    )


def execute_task(
    *,
    plan_dir: str | Path,
    task_index: int,
    parent_collection_run_root: str | Path,
    base_source_dir: str | Path,
    run_root: str | Path,
    experiment_config_path: str | Path,
    resume: bool = False,
    overwrite: bool = False,
) -> str:
    """Run one solver-parent task through generation and independent solving."""
    plan_root = Path(plan_dir).resolve()
    plan = _read_json(plan_root / PLAN_NAME)
    tasks = _read_jsonl(plan_root / TASKS_NAME)
    validate_plan(plan, tasks)
    if task_index < 0 or task_index >= len(tasks):
        raise ScalableAugmentationError("task index is outside the manifest")
    task = tasks[task_index]
    if int(task["task_index"]) != task_index:
        raise ScalableAugmentationError("task identity mismatch")
    parent = Path(base_source_dir).resolve() / _safe_relative(
        task["parent_mip_relative_path"], field="parent MIP path"
    )
    solution = Path(parent_collection_run_root).resolve() / _safe_relative(
        task["parent_solution_relative_path"], field="parent solution path"
    )
    if not parent.is_file() or sha256_file(parent) != task["parent_mip_sha256"]:
        raise ScalableAugmentationError("parent MIP is missing or changed")
    if (
        not solution.is_file()
        or sha256_file(solution) != task["parent_solution_sha256"]
    ):
        raise ScalableAugmentationError("parent solution is missing or changed")
    root = Path(run_root).resolve()
    variants = root / _safe_relative(
        task["variant_run_relative_path"], field="variant output path"
    )
    solves = root / _safe_relative(
        task["solve_run_relative_path"], field="solve output path"
    )
    generation_ok, _ = _generation_valid(task, variants)
    if not (resume and generation_ok):
        from cfl_gnn.augmentation.local_branching import main as generation_main

        argv = [
            "--solver", str(task["solver"]),
            "--parent_mip", str(parent),
            "--incumbent_artifact", str(solution),
            "--incumbent_format", str(task["incumbent_format"]),
            "--parent_instance_id", str(task["source_instance_id"]),
            "--category", str(task["category"]),
            "--difficulty", str(task["difficulty"]),
            "--fold", str(task["fold"]),
            "--config", str(Path(experiment_config_path).resolve()),
            "--output_dir", str(variants),
        ]
        if overwrite:
            argv.append("--overwrite")
        if generation_main(argv) != 0:
            raise ScalableAugmentationError("local-branching generation failed")
    if resume and _solve_valid(task, solves):
        return "reused"
    from cfl_gnn.pipelines.derived_mip_solutions import main as solve_main

    contract = plan["solve_contract"]
    argv = [
        "--solver", str(task["solver"]),
        "--candidate_dir", str(variants),
        "--output_dir", str(solves),
        "--config", str(Path(experiment_config_path).resolve()),
        "--time_limit", str(contract["time_limit_seconds_per_candidate"]),
        "--node_limit", str(contract["node_limit_per_candidate"]),
        "--threads_per_candidate", str(contract["threads_per_candidate"]),
        "--max_parallel", "1",
        "--seed", str(contract["seed"]),
    ]
    if resume:
        argv.append("--resume")
    if solve_main(argv) != 0:
        raise ScalableAugmentationError("independent derived-MIP solve failed")
    return "executed"


def audit_campaign(
    *,
    plan_dir: str | Path,
    run_root: str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate every solver-parent task and emit graph-builder source records."""
    plan_root = Path(plan_dir).resolve()
    root = Path(run_root).resolve()
    output = Path(output_dir).resolve()
    expected = (output / REPORT_NAME, output / STATUS_NAME, output / SOURCE_INDEX_NAME)
    if not overwrite and any(path.exists() for path in expected):
        raise ScalableAugmentationError("audit outputs exist; use --overwrite")
    plan = _read_json(plan_root / PLAN_NAME)
    tasks = _read_jsonl(plan_root / TASKS_NAME)
    validate_plan(plan, tasks)
    statuses = []
    by_pair: dict[int, list[dict[str, Any]]] = {}
    sources = []
    for task in tasks:
        variants_relative = _safe_relative(
            task["variant_run_relative_path"], field="variant path"
        )
        solves_relative = _safe_relative(
            task["solve_run_relative_path"], field="solve path"
        )
        generation_ok, radii = _generation_valid(task, root / variants_relative)
        solve_ok = _solve_valid(task, root / solves_relative)
        status = {
            "task_index": int(task["task_index"]),
            "pair_index": int(task["pair_index"]),
            "solver": str(task["solver"]),
            "source_instance_id": str(task["source_instance_id"]),
            "role": str(task["role"]),
            "generation_valid": generation_ok,
            "independent_labels_valid": solve_ok,
            "radii": radii,
            "gate_status": "passed" if generation_ok and solve_ok else "failed",
        }
        statuses.append(status)
        by_pair.setdefault(int(task["pair_index"]), []).append(status)
        if generation_ok and solve_ok:
            sources.append(
                {
                    "solver": str(task["solver"]),
                    "source_instance_id": str(task["source_instance_id"]),
                    "candidate_dir_relative_path": variants_relative.as_posix(),
                    "solve_dir_relative_path": solves_relative.as_posix(),
                }
            )
    symmetric_pairs = 0
    for records in by_pair.values():
        if (
            len(records) == 2
            and {item["solver"] for item in records} == set(SOLVERS)
            and len({item["source_instance_id"] for item in records}) == 1
            and len({tuple(item["radii"]) for item in records}) == 1
            and all(item["gate_status"] == "passed" for item in records)
        ):
            symmetric_pairs += 1
    passed = (
        all(item["gate_status"] == "passed" for item in statuses)
        and symmetric_pairs == len(by_pair)
        and len(sources) == len(tasks)
    )
    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / STATUS_NAME, statuses)
    _write_jsonl(output / SOURCE_INDEX_NAME, sources)
    contract = {
        "schema_version": SCHEMA_VERSION,
        "augmentation_contract_sha256": plan["contract_sha256"],
        "task_manifest_sha256": sha256_file(plan_root / TASKS_NAME),
        "status_sha256": sha256_file(output / STATUS_NAME),
        "source_index_sha256": sha256_file(output / SOURCE_INDEX_NAME),
        "graph_authority": "gurobi",
    }
    report = {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "probe_completed": True,
        "gate_status": "passed" if passed else "failed",
        "summary": {
            "paired_train_parents": len(by_pair),
            "symmetric_pairs": symmetric_pairs,
            "solver_tasks": len(tasks),
            "valid_solver_tasks": sum(
                item["gate_status"] == "passed" for item in statuses
            ),
            "derived_sources": len(sources),
            "radii": sorted({radius for item in statuses for radius in item["radii"]}),
            "tasks_by_solver": dict(Counter(item["solver"] for item in statuses)),
        },
        "outputs": {
            STATUS_NAME: {"sha256": contract["status_sha256"]},
            SOURCE_INDEX_NAME: {"sha256": contract["source_index_sha256"]},
        },
        "eligibility": {
            "gurobi_authoritative_graph_build_ready": passed,
            "development_only": plan["eligibility"]["development_only"],
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "next_gate": (
                "gurobi_authoritative_graph_dataset_and_descriptive_analysis"
                if passed
                else "repair_scalable_augmentation_tasks"
            )
        },
    }
    _write_json(output / REPORT_NAME, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or audit the scalable paired augmentation campaign."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--parent_collection_plan_dir", type=Path, required=True)
    plan.add_argument("--parent_collection_progress_dir", type=Path, required=True)
    plan.add_argument("--parent_collection_run_root", type=Path, required=True)
    plan.add_argument("--base_source_dir", type=Path, required=True)
    plan.add_argument("--output_dir", type=Path, required=True)
    plan.add_argument("--experiment_config", type=Path, required=True)
    plan.add_argument("--time_limit", type=float, default=3600.0)
    plan.add_argument("--node_limit", type=int, default=1_000_000)
    plan.add_argument("--threads_per_candidate", type=int, default=1)
    plan.add_argument("--max_parallel_tasks", type=int, default=2)
    plan.add_argument("--instances", nargs="*")
    plan.add_argument("--overwrite", action="store_true")
    task = subparsers.add_parser("run-task")
    task.add_argument("--plan_dir", type=Path, required=True)
    task.add_argument("--task_index", type=int, required=True)
    task.add_argument("--parent_collection_run_root", type=Path, required=True)
    task.add_argument("--base_source_dir", type=Path, required=True)
    task.add_argument("--run_root", type=Path, required=True)
    task.add_argument("--experiment_config", type=Path, required=True)
    task.add_argument("--resume", action="store_true")
    task.add_argument("--overwrite", action="store_true")
    audit = subparsers.add_parser("audit")
    audit.add_argument("--plan_dir", type=Path, required=True)
    audit.add_argument("--run_root", type=Path, required=True)
    audit.add_argument("--output_dir", type=Path, required=True)
    audit.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            result = build_campaign_plan(
                parent_collection_plan_dir=args.parent_collection_plan_dir,
                parent_collection_progress_dir=args.parent_collection_progress_dir,
                parent_collection_run_root=args.parent_collection_run_root,
                base_source_dir=args.base_source_dir,
                output_dir=args.output_dir,
                experiment_config_path=args.experiment_config,
                time_limit_seconds=args.time_limit,
                node_limit=args.node_limit,
                threads_per_candidate=args.threads_per_candidate,
                max_parallel_tasks=args.max_parallel_tasks,
                instances=args.instances,
                overwrite=args.overwrite,
            )
            print(
                f"[INFO] contract={result['contract_sha256']} | "
                f"parents={result['summary']['paired_train_parents']} | "
                f"tasks={result['summary']['solver_tasks']}"
            )
            print(f"[INFO] Plan: {Path(args.output_dir).resolve() / PLAN_NAME}")
            return 0
        if args.command == "run-task":
            status = execute_task(
                plan_dir=args.plan_dir,
                task_index=args.task_index,
                parent_collection_run_root=args.parent_collection_run_root,
                base_source_dir=args.base_source_dir,
                run_root=args.run_root,
                experiment_config_path=args.experiment_config,
                resume=args.resume,
                overwrite=args.overwrite,
            )
            print(f"[INFO] task_status={status}")
            return 0
        result = audit_campaign(
            plan_dir=args.plan_dir,
            run_root=args.run_root,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
        print(
            f"[INFO] gate={result['gate_status']} | "
            f"pairs={result['summary']['symmetric_pairs']}/"
            f"{result['summary']['paired_train_parents']}"
        )
        print(f"[INFO] Report: {Path(args.output_dir).resolve() / REPORT_NAME}")
        return 0 if result["gate_status"] == "passed" else 1
    except (OSError, TypeError, ValueError, ScalableAugmentationError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
