"""Descriptive and reproducible review of the MVP Neural Diving benchmark."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.experiments.mvp_neural_diving import (
    COMPARISONS_NAME,
    EXPECTED_ARMS,
    PLAN_NAME as BENCHMARK_PLAN_NAME,
    REPORT_NAME as BENCHMARK_REPORT_NAME,
    RUN_METRICS_NAME as BENCHMARK_METRICS_NAME,
    TARGET_SOLVERS,
    canonical_sha256,
    load_json,
    sha256_file,
    validate_plan as validate_benchmark_plan,
    write_json,
)


PLAN_NAME = "mvp_neural_diving_comparison_plan.json"
REPORT_NAME = "mvp_neural_diving_comparison_report.json"
RUN_TABLE_NAME = "per_run_descriptive_metrics.csv"
ARM_TABLE_NAME = "per_arm_descriptive_summary.csv"
EFFECT_TABLE_NAME = "paired_descriptive_effects.csv"
MANIFEST_NAME = "reproducibility_manifest.json"
DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "evaluation"
    / "mvp_neural_diving_comparison_v1.json"
)


class MvpComparisonError(RuntimeError):
    """Raised when the comparison contract cannot be verified."""


def _safe_relative(value: Any, *, field: str) -> Path:
    path = Path(str(value))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise MvpComparisonError(f"unsafe {field}")
    return path


def _finite(value: Any, *, field: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as error:
        raise MvpComparisonError(f"invalid {field}") from error
    if not math.isfinite(normalized):
        raise MvpComparisonError(f"non-finite {field}")
    return normalized


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise MvpComparisonError(
                    f"JSON object required at {path.name}:{line_number}"
                )
            records.append(payload)
    return records


def _write_csv(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
    temporary.replace(path)


def _plan_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in plan.items()
        if key not in {"contract_sha256", "contract_valid", "next_gate"}
    }


def validate_plan(plan: Mapping[str, Any]) -> None:
    expected = canonical_sha256(_plan_payload(plan))
    if (
        plan.get("contract_valid") is not True
        or plan.get("contract_sha256") != expected
    ):
        raise MvpComparisonError("comparison plan contract mismatch")


def _source_paths(root: Path) -> dict[str, Path]:
    return {
        "benchmark_plan": root / BENCHMARK_PLAN_NAME,
        "benchmark_report": root / BENCHMARK_REPORT_NAME,
        "per_run_metrics": root / BENCHMARK_METRICS_NAME,
        "paired_comparisons": root / COMPARISONS_NAME,
    }


def _load_source(root: Path) -> dict[str, Any]:
    paths = _source_paths(root)
    for path in paths.values():
        if not path.is_file():
            raise MvpComparisonError(f"missing source artifact: {path.name}")
    plan = load_json(paths["benchmark_plan"])
    validate_benchmark_plan(plan)
    report = load_json(paths["benchmark_report"])
    if report.get("gate_status") != "passed":
        raise MvpComparisonError("source benchmark gate did not pass")
    if report.get("benchmark_contract_sha256") != plan.get("contract_sha256"):
        raise MvpComparisonError("source benchmark contract mismatch")
    outputs = report.get("outputs", {})
    if outputs.get("per_run_metrics_sha256") != sha256_file(
        paths["per_run_metrics"]
    ):
        raise MvpComparisonError("source per-run metrics SHA-256 mismatch")
    if outputs.get("paired_comparisons_sha256") != sha256_file(
        paths["paired_comparisons"]
    ):
        raise MvpComparisonError("source comparisons SHA-256 mismatch")
    controls = report.get("common_controls", {})
    if not controls or not all(value is True for value in controls.values()):
        raise MvpComparisonError("source common controls did not pass")
    records: list[dict[str, Any]] = []
    task_files: list[dict[str, Any]] = []
    for task in plan.get("tasks", []):
        relative = _safe_relative(
            task.get("output_relative_path"), field="task result path"
        )
        path = root / relative
        if not path.is_file():
            raise MvpComparisonError(f"missing task result: {relative.as_posix()}")
        record = load_json(path)
        if (
            record.get("gate_status") != "passed"
            or record.get("benchmark_contract_sha256") != plan["contract_sha256"]
            or record.get("task_contract_sha256") != task.get("task_contract_sha256")
        ):
            raise MvpComparisonError("task result contract mismatch")
        records.append(record)
        task_files.append(
            {
                "relative_path": relative.as_posix(),
                "sha256": sha256_file(path),
            }
        )
    raw_comparisons = _read_jsonl(paths["paired_comparisons"])
    return {
        "paths": paths,
        "plan": plan,
        "report": report,
        "records": records,
        "task_files": task_files,
        "raw_comparisons": raw_comparisons,
    }


def build_plan(
    benchmark_dir: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Verify the source benchmark and precommit a descriptive review."""
    root = Path(benchmark_dir).resolve()
    source = _load_source(root)
    config_file = Path(config_path).resolve()
    config = load_json(config_file)
    expected_arms = list(config.get("expected_arms", []))
    expected_solvers = list(config.get("expected_target_solvers", []))
    if expected_arms != list(EXPECTED_ARMS):
        raise MvpComparisonError("comparison arm contract mismatch")
    if expected_solvers != list(TARGET_SOLVERS):
        raise MvpComparisonError("comparison solver contract mismatch")
    plan: dict[str, Any] = {
        "schema_version": 1,
        "analysis_stage": config["analysis_stage"],
        "source_benchmark_contract_sha256": source["plan"]["contract_sha256"],
        "source_artifacts": {
            key: {
                "file_name": path.name,
                "sha256": sha256_file(path),
            }
            for key, path in source["paths"].items()
        },
        "source_task_results": source["task_files"],
        "configuration": config,
        "configuration_sha256": sha256_file(config_file),
        "planned_runs": len(source["records"]),
        "planned_parents": len(source["plan"].get("held_out_parents", [])),
        "development_only": True,
        "scientific_reporting_eligible": False,
        "arm_selection_performed": False,
    }
    plan["contract_sha256"] = canonical_sha256(plan)
    plan["contract_valid"] = True
    plan["next_gate"] = "descriptive_comparison_execution"
    return plan


def _timing_valid(record: Mapping[str, Any], required: Sequence[str]) -> bool:
    regions = record.get("time_regions", {})
    try:
        values = [_finite(regions[name], field=name) for name in required]
    except (KeyError, MvpComparisonError):
        return False
    if any(value < 0.0 for value in values):
        return False
    total = _finite(regions.get("total_wall_time_seconds"), field="total time")
    accounted = sum(
        _finite(regions.get(name), field=name)
        for name in (
            "data_read_wall_time_seconds",
            "model_build_wall_time_seconds",
            "model_optimize_wall_time_seconds",
            "post_optimize_extraction_wall_time_seconds",
            "unattributed_overhead_wall_time_seconds",
        )
    )
    return abs(total - accounted) <= max(1e-6, total * 1e-6)


def _run_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: int(item["task_index"])):
        outcome = record["outcome"]
        timing = record["time_regions"]
        rows.append(
            {
                "task_index": record["task_index"],
                "run_id": record["run_id"],
                "parent_instance_id": record["parent_instance_id"],
                "target_solver": record["target_solver"],
                "arm_id": record.get("gnn_arm_id") or "unguided_control",
                "run_kind": record["run_kind"],
                "solve_status": outcome["solve_status"],
                "right_censored": outcome["right_censored"],
                "terminal_mip_gap_relative": outcome["terminal_mip_gap_relative"],
                "terminal_mip_gap_percent": outcome["terminal_mip_gap_percent"],
                "best_objective": outcome.get("best_objective"),
                "best_bound": outcome.get("best_bound"),
                "nodes": outcome.get("nodes"),
                "solution_count": outcome.get("solution_count"),
                "total_wall_time_seconds": timing["total_wall_time_seconds"],
                "data_read_wall_time_seconds": timing[
                    "data_read_wall_time_seconds"
                ],
                "model_build_wall_time_seconds": timing[
                    "model_build_wall_time_seconds"
                ],
                "model_optimize_wall_time_seconds": timing[
                    "model_optimize_wall_time_seconds"
                ],
                "post_optimize_extraction_wall_time_seconds": timing.get(
                    "post_optimize_extraction_wall_time_seconds"
                ),
                "unattributed_overhead_wall_time_seconds": timing.get(
                    "unattributed_overhead_wall_time_seconds"
                ),
                "solver_reported_optimize_time_seconds": outcome.get(
                    "solver_reported_optimize_time_seconds"
                ),
                "fixed_variable_count": record["neural_diving"][
                    "fixed_variable_count"
                ],
            }
        )
    return rows


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values)


def _arm_rows(
    run_rows: Sequence[Mapping[str, Any]], thresholds: Sequence[float]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in run_rows:
        key = (str(row["target_solver"]), str(row["arm_id"]), str(row["run_kind"]))
        groups[key].append(row)
    summaries: list[dict[str, Any]] = []
    for (solver, arm_id, run_kind), rows in sorted(groups.items()):
        gaps = [_finite(row["terminal_mip_gap_relative"], field="gap") for row in rows]
        optimize = [
            _finite(row["model_optimize_wall_time_seconds"], field="optimize time")
            for row in rows
        ]
        summary: dict[str, Any] = {
            "target_solver": solver,
            "arm_id": arm_id,
            "run_kind": run_kind,
            "runs": len(rows),
            "parents": len({row["parent_instance_id"] for row in rows}),
            "right_censored_runs": sum(bool(row["right_censored"]) for row in rows),
            "mean_terminal_mip_gap_relative": _mean(gaps),
            "median_terminal_mip_gap_relative": statistics.median(gaps),
            "mean_model_optimize_wall_time_seconds": _mean(optimize),
            "median_model_optimize_wall_time_seconds": statistics.median(optimize),
        }
        for name in (
            "total_wall_time_seconds",
            "data_read_wall_time_seconds",
            "model_build_wall_time_seconds",
        ):
            values = [_finite(row[name], field=name) for row in rows]
            summary[f"median_{name}"] = statistics.median(values)
        for threshold in thresholds:
            label = str(threshold).replace(".", "_")
            summary[f"runs_gap_le_{label}"] = sum(gap <= threshold for gap in gaps)
        summaries.append(summary)
    return summaries


def _effect_class(gap_delta: float, time_delta: float) -> str:
    gap_better = gap_delta < 0.0
    gap_worse = gap_delta > 0.0
    time_better = time_delta < 0.0
    time_worse = time_delta > 0.0
    if (gap_better or time_better) and not (gap_worse or time_worse):
        return "descriptively_dominates_reference"
    if (gap_worse or time_worse) and not (gap_better or time_better):
        return "descriptively_dominated_by_reference"
    if not any((gap_better, gap_worse, time_better, time_worse)):
        return "descriptively_equal"
    return "descriptive_tradeoff"


def _effect_rows(
    raw: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_key = {
        (
            record["parent_instance_id"],
            record["target_solver"],
            record.get("gnn_arm_id"),
        ): record
        for record in records
    }
    rows: list[dict[str, Any]] = []
    for comparison in raw:
        parent = comparison["parent_instance_id"]
        solver = comparison["target_solver"]
        candidate_arm = comparison.get("candidate_arm")
        reference_arm = comparison.get("reference_arm")
        if comparison["comparison"] == "scip_minus_gurobi_target_solver":
            candidate = by_key[(parent, "scip", candidate_arm)]
            reference = by_key[(parent, "gurobi", reference_arm)]
        else:
            candidate = by_key[(parent, solver, candidate_arm)]
            reference = by_key[(parent, solver, reference_arm)]
        gap_delta = _finite(
            comparison["terminal_mip_gap_relative_delta"], field="gap delta"
        )
        time_delta = _finite(
            comparison["model_optimize_wall_time_seconds_delta"],
            field="optimize-time delta",
        )
        expected_gap_delta = _finite(
            candidate["outcome"]["terminal_mip_gap_relative"],
            field="candidate gap",
        ) - _finite(
            reference["outcome"]["terminal_mip_gap_relative"],
            field="reference gap",
        )
        expected_time_delta = _finite(
            candidate["time_regions"]["model_optimize_wall_time_seconds"],
            field="candidate optimize time",
        ) - _finite(
            reference["time_regions"]["model_optimize_wall_time_seconds"],
            field="reference optimize time",
        )
        if not math.isclose(gap_delta, expected_gap_delta, abs_tol=1e-12):
            raise MvpComparisonError("source paired gap delta mismatch")
        if not math.isclose(time_delta, expected_time_delta, abs_tol=1e-9):
            raise MvpComparisonError("source paired optimize-time delta mismatch")
        censored = bool(candidate["outcome"]["right_censored"]) or bool(
            reference["outcome"]["right_censored"]
        )
        rows.append(
            {
                **comparison,
                "terminal_mip_gap_relative_improvement": -gap_delta,
                "model_optimize_wall_time_seconds_improvement": -time_delta,
                "descriptive_joint_class": _effect_class(gap_delta, time_delta),
                "censoring_interpretation": (
                    "right_censored_descriptive_only"
                    if censored
                    else "uncensored_descriptive"
                ),
            }
        )
    return rows


def run_review(
    benchmark_dir: str | Path,
    output_dir: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create comparison tables, audit controls, and a reproducibility manifest."""
    source_root = Path(benchmark_dir).resolve()
    output_root = Path(output_dir).resolve()
    outputs = [
        PLAN_NAME,
        REPORT_NAME,
        RUN_TABLE_NAME,
        ARM_TABLE_NAME,
        EFFECT_TABLE_NAME,
    ]
    if not overwrite and any((output_root / name).exists() for name in outputs):
        raise MvpComparisonError("comparison output exists; use --overwrite")
    plan = build_plan(source_root, config_path=config_path)
    validate_plan(plan)
    source = _load_source(source_root)
    config = plan["configuration"]
    required_time_regions = list(config["required_time_regions"])
    records = source["records"]
    raw_comparisons = source["raw_comparisons"]
    run_rows = _run_rows(records)
    thresholds = [
        _finite(value, field="gap sensitivity threshold")
        for value in config["gap_sensitivity_thresholds_relative"]
    ]
    arm_rows = _arm_rows(run_rows, thresholds)
    effect_rows = _effect_rows(raw_comparisons, records)
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / PLAN_NAME, plan)
    run_fields = list(run_rows[0])
    arm_fields = list(arm_rows[0])
    effect_fields = list(effect_rows[0])
    _write_csv(output_root / RUN_TABLE_NAME, run_fields, run_rows)
    _write_csv(output_root / ARM_TABLE_NAME, arm_fields, arm_rows)
    _write_csv(output_root / EFFECT_TABLE_NAME, effect_fields, effect_rows)
    expected_runs = len(source["plan"]["held_out_parents"]) * 10
    expected_effects = len(source["plan"]["held_out_parents"]) * 16
    common_controls = {
        "source_benchmark_gate_passed": source["report"]["gate_status"] == "passed",
        "source_contract_matches": (
            source["report"]["benchmark_contract_sha256"]
            == source["plan"]["contract_sha256"]
        ),
        "source_common_controls_passed": all(
            value is True for value in source["report"]["common_controls"].values()
        ),
        "expected_run_count": len(records) == expected_runs,
        "unique_run_ids": len({record["run_id"] for record in records})
        == len(records),
        "all_task_gates_passed": all(
            record["gate_status"] == "passed" for record in records
        ),
        "primary_outcomes_finite": all(
            math.isfinite(float(row["terminal_mip_gap_relative"]))
            and math.isfinite(float(row["model_optimize_wall_time_seconds"]))
            for row in run_rows
        ),
        "four_time_regions_reconciled": all(
            _timing_valid(record, required_time_regions) for record in records
        ),
        "paired_effect_count": len(effect_rows) == expected_effects,
        "arm_selection_absent": plan["arm_selection_performed"] is False,
        "scientific_reporting_disabled": (
            plan["scientific_reporting_eligible"] is False
        ),
    }
    gate_passed = all(common_controls.values())
    analysis_outputs = {
        name: {
            "file_name": name,
            "sha256": sha256_file(output_root / name),
        }
        for name in (RUN_TABLE_NAME, ARM_TABLE_NAME, EFFECT_TABLE_NAME)
    }
    manifest = {
        "schema_version": 1,
        "comparison_contract_sha256": plan["contract_sha256"],
        "source_benchmark_contract_sha256": plan[
            "source_benchmark_contract_sha256"
        ],
        "source_artifacts": plan["source_artifacts"],
        "source_task_results": plan["source_task_results"],
        "analysis_outputs": analysis_outputs,
        "analysis_policy": {
            "selection_policy": config["selection_policy"],
            "inference_policy": config["inference_policy"],
            "censoring_policy": config["censoring_policy"],
        },
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    write_json(output_root / MANIFEST_NAME, manifest)
    report = {
        "schema_version": 1,
        "comparison_contract_sha256": plan["contract_sha256"],
        "source_benchmark_contract_sha256": plan[
            "source_benchmark_contract_sha256"
        ],
        "gate_status": "passed" if gate_passed else "failed",
        "analysis_stage": config["analysis_stage"],
        "execution": {
            "parents": len(source["plan"]["held_out_parents"]),
            "runs": len(records),
            "guided_runs": sum(record["run_kind"] == "guided" for record in records),
            "control_runs": sum(record["run_kind"] == "control" for record in records),
            "paired_descriptive_effects": len(effect_rows),
        },
        "primary_outcomes": config["primary_outcomes"],
        "gap_sensitivity_thresholds_relative": thresholds,
        "censoring": {
            "policy": config["censoring_policy"],
            "right_censored_runs": sum(bool(row["right_censored"]) for row in run_rows),
        },
        "common_controls": common_controls,
        "outputs": {
            **analysis_outputs,
            "reproducibility_manifest": {
                "file_name": MANIFEST_NAME,
                "sha256": sha256_file(output_root / MANIFEST_NAME),
            },
        },
        "deferred_publication_outputs": config["deferred_publication_outputs"],
        "eligibility": {
            "descriptive_mvp_review_eligible": gate_passed,
            "arm_selection_eligible": False,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": (
                "descriptive_four_arm_review_completed"
                if gate_passed
                else "descriptive_four_arm_review_gate_failed"
            ),
            "next_gate": (
                "mvp_pipeline_reproducibility_and_publication_outputs"
                if gate_passed
                else "review_comparison_contract_failures"
            ),
        },
    }
    write_json(output_root / REPORT_NAME, report)
    return report
