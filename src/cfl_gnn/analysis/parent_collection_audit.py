"""Audit Gurobi-first parent collection and produce Phase 1 EDA artifacts."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.parent_collection_task import validate_campaign_plan
from cfl_gnn.pipelines.parent_population import (
    PLAN_NAME,
    SOLVER_ORDER,
    ParentPopulationError,
)
from cfl_gnn.pipelines.parent_solutions import report_name


SCHEMA_VERSION = 1
REPORT_NAME = "parent_collection_audit_report.json"
METRICS_NAME = "parent_solve_metrics.csv"
TRAJECTORY_NAME = "incumbent_trajectory.csv"
PAIRED_NAME = "paired_parent_metrics.csv"
GAP_SENSITIVITY_NAME = "parent_gap_sensitivity.csv"
GAP_FIGURE_NAME = "figure_parent_terminal_mip_gap.svg"
TIME_FIGURE_NAME = "figure_parent_time_regions.svg"
TRAJECTORY_FIGURE_NAME = "figure_parent_incumbent_trajectories.svg"


class ParentCollectionAuditError(RuntimeError):
    """Raised when collected parent artifacts violate the campaign contract."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise ParentCollectionAuditError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ParentCollectionAuditError(f"expected JSON object: {path.name}")
    return value


def _read_gzip_json(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, TypeError, ValueError) as error:
        raise ParentCollectionAuditError(
            f"unreadable compressed JSON artifact: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise ParentCollectionAuditError(f"expected JSON object: {path.name}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _finite(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return normalized if math.isfinite(normalized) else None


def _median(values: Iterable[Any]) -> float | None:
    finite = [number for value in values if (number := _finite(value)) is not None]
    return statistics.median(finite) if finite else None


def _time_regions_valid(regions: Any) -> bool:
    if not isinstance(regions, dict):
        return False
    required = (
        "total_wall_time_seconds",
        "data_read_wall_time_seconds",
        "model_build_wall_time_seconds",
        "model_optimize_wall_time_seconds",
    )
    values = [_finite(regions.get(key)) for key in required]
    if any(value is None or value < 0 for value in values):
        return False
    assert all(value is not None for value in values)
    return values[0] + 1e-6 >= sum(values[1:])


def _artifact_set_valid(run_dir: Path, report: Mapping[str, Any]) -> bool:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        return False
    for descriptor in artifacts.values():
        if not isinstance(descriptor, dict):
            return False
        path = run_dir / str(descriptor.get("file_name", ""))
        if not path.is_file() or sha256_file(path) != descriptor.get("sha256"):
            return False
    return True


def _format_number(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.4g}"


def _bar_svg(
    *,
    title: str,
    ylabel: str,
    groups: Sequence[tuple[str, Sequence[float]]],
    series_labels: Sequence[str] = (),
) -> str:
    width, height = 860, 480
    left, right, top, bottom = 90, 30, 65, 90
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [value for _, group in groups for value in group]
    maximum = max(values, default=1.0)
    maximum = maximum if maximum > 0 else 1.0
    colors = ("#2563EB", "#D97706", "#059669", "#7C3AED")
    group_width = plot_width / max(len(groups), 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="20">{html.escape(title)}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#111827"/>',
        f'<text x="20" y="{top + plot_height / 2}" transform="rotate(-90 20 {top + plot_height / 2})" text-anchor="middle" font-family="sans-serif" font-size="13">{html.escape(ylabel)}</text>',
    ]
    for group_index, (label, group) in enumerate(groups):
        count = max(len(group), 1)
        bar_width = min(70.0, group_width / (count + 1))
        start = left + group_index * group_width + (group_width - count * bar_width) / 2
        for value_index, value in enumerate(group):
            bar_height = plot_height * value / maximum
            x = start + value_index * bar_width
            y = top + plot_height - bar_height
            parts.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width * 0.78:.2f}" height="{bar_height:.2f}" fill="{colors[value_index % len(colors)]}"/>'
            )
            parts.append(
                f'<text x="{x + bar_width * 0.39:.2f}" y="{max(y - 5, 50):.2f}" text-anchor="middle" font-family="sans-serif" font-size="11">{html.escape(_format_number(value))}</text>'
            )
        parts.append(
            f'<text x="{left + (group_index + 0.5) * group_width:.2f}" y="{top + plot_height + 28}" text-anchor="middle" font-family="sans-serif" font-size="13">{html.escape(label)}</text>'
        )
    for index, label in enumerate(series_labels):
        legend_x = left + index * 165
        parts.append(
            f'<rect x="{legend_x}" y="{height - 35}" width="11" height="11" fill="{colors[index % len(colors)]}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 17}" y="{height - 25}" font-family="sans-serif" font-size="11">{html.escape(label)}</text>'
        )
    parts.append('</svg>\n')
    return "".join(parts)


def _trajectory_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    width, height = 860, 480
    left, right, top, bottom = 90, 30, 65, 75
    plot_width = width - left - right
    plot_height = height - top - bottom
    finite_rows = [
        row
        for row in rows
        if _finite(row.get("incumbent_discovery_time_seconds")) is not None
        and _finite(row.get("incumbent_objective")) is not None
    ]
    max_x = max(
        (_finite(row["incumbent_discovery_time_seconds"]) or 0.0 for row in finite_rows),
        default=1.0,
    )
    objectives = [_finite(row["incumbent_objective"]) or 0.0 for row in finite_rows]
    min_y, max_y = (min(objectives), max(objectives)) if objectives else (0.0, 1.0)
    if math.isclose(min_y, max_y):
        max_y = min_y + 1.0
    max_x = max(max_x, 1e-12)
    colors = {"gurobi": "#2563EB", "scip": "#D97706"}
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in finite_rows:
        grouped[(str(row["solver"]), str(row["source_instance_id"]))].append(row)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="20">Incumbent objective trajectories</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#111827"/>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#111827"/>',
        f'<text x="{left + plot_width / 2}" y="{height - 22}" text-anchor="middle" font-family="sans-serif" font-size="13">Incumbent discovery time (seconds)</text>',
        f'<text x="20" y="{top + plot_height / 2}" transform="rotate(-90 20 {top + plot_height / 2})" text-anchor="middle" font-family="sans-serif" font-size="13">Objective (MINIMIZE)</text>',
    ]
    for (solver, _), group in sorted(grouped.items()):
        points = []
        for row in sorted(group, key=lambda item: float(item["incumbent_discovery_time_seconds"])):
            x_value = float(row["incumbent_discovery_time_seconds"])
            y_value = float(row["incumbent_objective"])
            x = left + plot_width * x_value / max_x
            y = top + plot_height * (max_y - y_value) / (max_y - min_y)
            points.append(f"{x:.2f},{y:.2f}")
        if points:
            parts.append(
                f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors.get(solver, "#374151")}" stroke-width="1.5" opacity="0.65"/>'
            )
    parts.extend(
        [
            '<rect x="650" y="48" width="12" height="12" fill="#2563EB"/><text x="668" y="59" font-family="sans-serif" font-size="12">Gurobi</text>',
            '<rect x="740" y="48" width="12" height="12" fill="#D97706"/><text x="758" y="59" font-family="sans-serif" font-size="12">SCIP</text>',
            '</svg>\n',
        ]
    )
    return "".join(parts)


def audit_parent_collection(
    *, plan_dir: str | Path, run_root: str | Path, output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    plan_root = Path(plan_dir).resolve()
    runs = Path(run_root).resolve()
    output = Path(output_dir).resolve()
    plan = _read_json(plan_root / PLAN_NAME)
    try:
        validate_campaign_plan(plan)
    except (OSError, ValueError, ParentPopulationError) as error:
        raise ParentCollectionAuditError(str(error)) from error
    output_names = (
        REPORT_NAME, METRICS_NAME, TRAJECTORY_NAME, PAIRED_NAME,
        GAP_SENSITIVITY_NAME, GAP_FIGURE_NAME, TIME_FIGURE_NAME,
        TRAJECTORY_FIGURE_NAME,
    )
    if not overwrite and any((output / name).exists() for name in output_names):
        raise ParentCollectionAuditError("audit output exists; use --overwrite")
    output.mkdir(parents=True, exist_ok=True)

    metrics: list[dict[str, Any]] = []
    trajectories: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    valid_by_parent: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for task in plan["tasks"]:
        solver = str(task["solver"])
        instance_id = str(task["source_instance_id"])
        run_dir = runs / str(task["run_dir_relative_path"])
        report_path = run_dir / report_name(solver)
        if not report_path.is_file():
            failures.append(
                {"solver": solver, "source_instance_id": instance_id,
                 "reason_code": "parent_solve_report_missing"}
            )
            continue
        try:
            report = _read_json(report_path)
            artifact_valid = _artifact_set_valid(run_dir, report)
            solution_descriptor = report.get("artifacts", {}).get("solution", {})
            solution_path = run_dir / str(solution_descriptor.get("file_name", ""))
            solution = _read_gzip_json(solution_path)
            solve = report.get("solve", {})
            regions = report.get("time_regions", {})
            runtime_context = report.get("runtime_environment", {})
            checks = {
                "parent_identity_match": (
                    report.get("parent", {}).get("source_instance_id") == instance_id
                ),
                "parent_sha256_match": (
                    report.get("parent", {}).get("sha256")
                    == task["parent_mip_sha256"]
                ),
                "objective_minimize": solve.get("objective_sense") == "minimize",
                "terminal_gap_finite": _finite(solve.get("mip_gap_relative")) is not None,
                "four_time_regions_valid": _time_regions_valid(regions),
                "artifact_hashes_valid": artifact_valid,
                "solution_contract_match": (
                    solution.get("contract_sha256") == report.get("contract_sha256")
                ),
                "solution_candidate_sha256_match": (
                    solution.get("candidate_sha256") == task["parent_mip_sha256"]
                ),
                "runtime_environment_recorded": (
                    isinstance(runtime_context, dict)
                    and all(
                        runtime_context.get(key) is not None
                        for key in (
                            "hostname", "platform", "machine", "logical_cpu_count"
                        )
                    )
                ),
                "solver_parameter_contract_recorded": bool(
                    report.get("solver_parameter_sha256")
                ),
            }
            if not all(checks.values()):
                raise ParentCollectionAuditError("parent solve audit checks failed")
            trace = solution.get("incumbent_trace", [])
            if not isinstance(trace, list):
                raise ParentCollectionAuditError("incumbent trace is not a list")
            row = {
                "source_instance_id": instance_id,
                "category": task["category"],
                "difficulty": task["difficulty"],
                "fold": task["fold"],
                "role": task["role"],
                "solver": solver,
                "solve_status": solve.get("solve_status"),
                "solution_objective": solve.get("solution_objective"),
                "best_bound": solve.get("best_bound"),
                "terminal_mip_gap_relative": solve.get("mip_gap_relative"),
                "terminal_mip_gap_percent": solve.get("mip_gap_percent"),
                "solver_execution_time_seconds": solve.get("execution_time_seconds"),
                "total_wall_time_seconds": regions.get("total_wall_time_seconds"),
                "data_read_wall_time_seconds": regions.get("data_read_wall_time_seconds"),
                "model_build_wall_time_seconds": regions.get("model_build_wall_time_seconds"),
                "model_optimize_wall_time_seconds": regions.get("model_optimize_wall_time_seconds"),
                "incumbent_count": len(trace),
                "time_to_first_incumbent_seconds": (
                    trace[0].get("incumbent_discovery_time_seconds") if trace else None
                ),
                "time_to_best_incumbent_seconds": solve.get(
                    "best_incumbent_discovery_time_seconds"
                ),
                "nodes_current_run": solve.get("nodes_current_run"),
                "nodes_total": solve.get("nodes_total"),
                "right_censored": solve.get("solve_status") != "optimal",
                "label_eligible": report.get("eligibility", {}).get("label_eligible"),
                "augmentation_source_eligible": report.get("eligibility", {}).get(
                    "augmentation_source_eligible"
                ),
                "solver_parameter_sha256": report.get("solver_parameter_sha256"),
                "parent_solve_contract_sha256": report.get("contract_sha256"),
                "hostname": runtime_context.get("hostname"),
                "platform": runtime_context.get("platform"),
                "machine": runtime_context.get("machine"),
                "processor": runtime_context.get("processor"),
                "logical_cpu_count": runtime_context.get("logical_cpu_count"),
                "slurm_partition": runtime_context.get("slurm", {}).get(
                    "slurm_job_partition"
                ),
            }
            metrics.append(row)
            valid_by_parent[instance_id][solver] = row
            for incumbent_index, incumbent in enumerate(trace):
                trajectories.append(
                    {
                        "source_instance_id": instance_id,
                        "difficulty": task["difficulty"],
                        "role": task["role"],
                        "solver": solver,
                        "incumbent_index": incumbent_index,
                        "incumbent_discovery_time_seconds": incumbent.get(
                            "incumbent_discovery_time_seconds"
                        ),
                        "incumbent_objective": incumbent.get("incumbent_objective"),
                        "best_bound_at_discovery": incumbent.get(
                            "incumbent_best_bound_at_discovery"
                        ),
                        "mip_gap_relative_at_discovery": incumbent.get(
                            "incumbent_mip_gap_relative_at_discovery"
                        ),
                        "node_count_at_discovery": incumbent.get(
                            "node_count_at_discovery"
                        ),
                    }
                )
        except (OSError, TypeError, ValueError, ParentCollectionAuditError) as error:
            failures.append(
                {"solver": solver, "source_instance_id": instance_id,
                 "reason_code": "parent_solve_artifact_invalid",
                 "error_type": type(error).__name__}
            )

    paired: list[dict[str, Any]] = []
    for instance_id, by_solver in sorted(valid_by_parent.items()):
        if set(by_solver) != set(SOLVER_ORDER):
            continue
        gurobi = by_solver["gurobi"]
        scip = by_solver["scip"]
        paired.append(
            {
                "source_instance_id": instance_id,
                "difficulty": gurobi["difficulty"],
                "role": gurobi["role"],
                "gurobi_terminal_mip_gap_relative": gurobi["terminal_mip_gap_relative"],
                "scip_terminal_mip_gap_relative": scip["terminal_mip_gap_relative"],
                "scip_minus_gurobi_terminal_mip_gap_relative": (
                    float(scip["terminal_mip_gap_relative"])
                    - float(gurobi["terminal_mip_gap_relative"])
                ),
                "gurobi_model_optimize_wall_time_seconds": gurobi[
                    "model_optimize_wall_time_seconds"
                ],
                "scip_model_optimize_wall_time_seconds": scip[
                    "model_optimize_wall_time_seconds"
                ],
                "scip_minus_gurobi_model_optimize_wall_time_seconds": (
                    float(scip["model_optimize_wall_time_seconds"])
                    - float(gurobi["model_optimize_wall_time_seconds"])
                ),
            }
        )

    thresholds = [float(value) for value in plan["gap_sensitivity_thresholds_relative"]]
    sensitivity: list[dict[str, Any]] = []
    for solver in SOLVER_ORDER:
        solver_rows = [row for row in metrics if row["solver"] == solver]
        for threshold in thresholds:
            count = sum(
                float(row["terminal_mip_gap_relative"]) <= threshold + 1e-12
                for row in solver_rows
            )
            sensitivity.append(
                {"solver": solver, "threshold_relative": threshold,
                 "eligible_count": count, "observed_count": len(solver_rows),
                 "eligible_fraction": count / len(solver_rows) if solver_rows else None}
            )

    metric_fields = (
        "source_instance_id", "category", "difficulty", "fold", "role", "solver",
        "solve_status", "solution_objective", "best_bound",
        "terminal_mip_gap_relative", "terminal_mip_gap_percent",
        "solver_execution_time_seconds", "total_wall_time_seconds",
        "data_read_wall_time_seconds", "model_build_wall_time_seconds",
        "model_optimize_wall_time_seconds", "incumbent_count",
        "time_to_first_incumbent_seconds", "time_to_best_incumbent_seconds",
        "nodes_current_run", "nodes_total", "right_censored", "label_eligible",
        "augmentation_source_eligible", "solver_parameter_sha256",
        "parent_solve_contract_sha256", "hostname", "platform", "machine",
        "processor", "logical_cpu_count", "slurm_partition",
    )
    trajectory_fields = (
        "source_instance_id", "difficulty", "role", "solver", "incumbent_index",
        "incumbent_discovery_time_seconds", "incumbent_objective",
        "best_bound_at_discovery", "mip_gap_relative_at_discovery",
        "node_count_at_discovery",
    )
    paired_fields = (
        "source_instance_id", "difficulty", "role",
        "gurobi_terminal_mip_gap_relative", "scip_terminal_mip_gap_relative",
        "scip_minus_gurobi_terminal_mip_gap_relative",
        "gurobi_model_optimize_wall_time_seconds",
        "scip_model_optimize_wall_time_seconds",
        "scip_minus_gurobi_model_optimize_wall_time_seconds",
    )
    _write_csv(output / METRICS_NAME, metrics, metric_fields)
    _write_csv(output / TRAJECTORY_NAME, trajectories, trajectory_fields)
    _write_csv(output / PAIRED_NAME, paired, paired_fields)
    _write_csv(
        output / GAP_SENSITIVITY_NAME,
        sensitivity,
        ("solver", "threshold_relative", "eligible_count", "observed_count", "eligible_fraction"),
    )

    gap_groups = [
        (
            solver.capitalize(),
            [100.0 * (_median(
                row["terminal_mip_gap_relative"] for row in metrics
                if row["solver"] == solver
            ) or 0.0)],
        )
        for solver in SOLVER_ORDER
    ]
    (output / GAP_FIGURE_NAME).write_text(
        _bar_svg(title="Median terminal MIP gap", ylabel="MIP gap (%)", groups=gap_groups),
        encoding="utf-8",
    )
    time_groups = []
    for solver in SOLVER_ORDER:
        solver_rows = [row for row in metrics if row["solver"] == solver]
        time_groups.append(
            (solver.capitalize(), [
                _median(row["total_wall_time_seconds"] for row in solver_rows) or 0.0,
                _median(row["data_read_wall_time_seconds"] for row in solver_rows) or 0.0,
                _median(row["model_build_wall_time_seconds"] for row in solver_rows) or 0.0,
                _median(row["model_optimize_wall_time_seconds"] for row in solver_rows) or 0.0,
            ])
        )
    (output / TIME_FIGURE_NAME).write_text(
        _bar_svg(
            title="Median parent-solve time regions",
            ylabel="Wall time (seconds)",
            groups=time_groups,
            series_labels=("Total", "Data read", "Model build", "Optimize"),
        ),
        encoding="utf-8",
    )
    (output / TRAJECTORY_FIGURE_NAME).write_text(
        _trajectory_svg(trajectories), encoding="utf-8"
    )

    expected_tasks = len(plan["tasks"])
    expected_pairs = int(plan["available_parent_population"])
    gate_passed = len(metrics) == expected_tasks and not failures and len(paired) == expected_pairs
    by_solver = {}
    for solver in SOLVER_ORDER:
        solver_rows = [row for row in metrics if row["solver"] == solver]
        by_solver[solver] = {
            "observed_parents": len(solver_rows),
            "right_censored_parents": sum(bool(row["right_censored"]) for row in solver_rows),
            "label_eligible_parents": sum(row["label_eligible"] is True for row in solver_rows),
            "median_terminal_mip_gap_relative": _median(
                row["terminal_mip_gap_relative"] for row in solver_rows
            ),
            "median_model_optimize_wall_time_seconds": _median(
                row["model_optimize_wall_time_seconds"] for row in solver_rows
            ),
            "median_incumbent_count": _median(row["incumbent_count"] for row in solver_rows),
        }
    outputs = {}
    for name in output_names[1:]:
        outputs[name] = {"sha256": sha256_file(output / name)}
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "parent_collection_contract_sha256": plan["contract_sha256"],
        "gate_status": "passed" if gate_passed else "failed",
        "probe_completed": True,
        "methodology": {
            "priority_solver": "gurobi",
            "scip_role": "matched_comparison_only",
            "objective_sense": "MINIMIZE",
            "primary_metrics": [
                "terminal_mip_gap_relative",
                "model_optimize_wall_time_seconds",
            ],
            "time_regions": [
                "total_wall_time_seconds", "data_read_wall_time_seconds",
                "model_build_wall_time_seconds", "model_optimize_wall_time_seconds",
            ],
            "censoring_policy": "retain_and_flag_no_naive_inference",
        },
        "summary": {
            "planned_parent_population": plan["planned_parent_population"],
            "available_parent_population": plan["available_parent_population"],
            "expected_tasks": expected_tasks,
            "valid_tasks": len(metrics),
            "failed_tasks": len(failures),
            "paired_parents": len(paired),
            "incumbent_observations": len(trajectories),
            "by_solver": by_solver,
            "gap_sensitivity": sensitivity,
        },
        "failures": failures,
        "outputs": outputs,
        "eligibility": {
            "phase1_descriptive_audit_complete": gate_passed,
            "gurobi_graph_authority_ready_for_next_gate": gate_passed,
            "development_only": plan["eligibility"]["development_only"],
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": (
                "paired_parent_collection_audited"
                if gate_passed else "parent_collection_incomplete_or_invalid"
            ),
            "next_gate": (
                "gurobi_root_relaxation_graph_contract"
                if gate_passed else "resume_or_repair_parent_collection"
            ),
        },
    }
    report["contract_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"generated_at_utc"}},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    _write_json(output / REPORT_NAME, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit original-parent solves and generate Phase 1 EDA outputs."
    )
    parser.add_argument("--plan_dir", type=Path, required=True)
    parser.add_argument("--run_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_parent_collection(
            plan_dir=args.plan_dir,
            run_root=args.run_root,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError, ParentCollectionAuditError) as error:
        print(f"[ERROR] {error}")
        return 2
    print(
        f"[INFO] gate={report['gate_status']} | "
        f"valid={report['summary']['valid_tasks']}/"
        f"{report['summary']['expected_tasks']} | "
        f"paired={report['summary']['paired_parents']}"
    )
    print(f"[INFO] Report: {Path(args.output_dir).resolve() / REPORT_NAME}")
    return 0 if report["gate_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
