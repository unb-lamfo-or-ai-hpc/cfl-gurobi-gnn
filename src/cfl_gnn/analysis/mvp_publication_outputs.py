"""Deterministic tables and vector figures for the development-only MVP."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.analysis.mvp_neural_diving_comparison import (
    ARM_TABLE_NAME as SOURCE_ARM_TABLE,
    EFFECT_TABLE_NAME as SOURCE_EFFECT_TABLE,
    REPORT_NAME as COMPARISON_REPORT_NAME,
    RUN_TABLE_NAME as SOURCE_RUN_TABLE,
)
from cfl_gnn.analysis.mvp_pipeline_reproducibility import (
    LEDGER_NAME as REPRODUCIBILITY_LEDGER_NAME,
    MANIFEST_NAME as REPRODUCIBILITY_MANIFEST_NAME,
    PLAN_NAME as REPRODUCIBILITY_PLAN_NAME,
    REPORT_NAME as REPRODUCIBILITY_REPORT_NAME,
    canonical_sha256,
    validate_plan as validate_reproducibility_plan,
)
from cfl_gnn.evaluation.mvp_four_arm import (
    METRICS_NAME as SOURCE_GNN_METRICS,
    REPORT_NAME as EVALUATION_REPORT_NAME,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.training.mvp_four_arm import (
    EXPECTED_ARMS,
    HISTORY_NAME,
    RUN_REPORT_NAME as TRAINING_REPORT_NAME,
)


SCHEMA_VERSION = 1
PLAN_NAME = "mvp_publication_outputs_plan.json"
REPORT_NAME = "mvp_publication_outputs_report.json"
MANIFEST_NAME = "mvp_publication_outputs_manifest.json"
TABLE_TRAINING = "table_training_epoch_metrics.csv"
TABLE_GNN = "table_gnn_test_metrics.csv"
TABLE_SOLVER = "table_solver_run_outcomes.csv"
TABLE_TIMING = "table_solver_time_regions.csv"
TABLE_EFFECTS = "table_paired_descriptive_effects.csv"
TABLE_SENSITIVITY = "table_gap_sensitivity.csv"
FIGURE_TRAINING = "figure_training_curves.svg"
FIGURE_GNN = "figure_gnn_quality.svg"
FIGURE_GAP = "figure_solver_mip_gap.svg"
FIGURE_TIMING = "figure_solver_time_regions.svg"
FIGURE_EFFECTS = "figure_paired_effects.svg"
FIGURE_SENSITIVITY = "figure_gap_sensitivity.svg"
TABLES = (
    TABLE_TRAINING,
    TABLE_GNN,
    TABLE_SOLVER,
    TABLE_TIMING,
    TABLE_EFFECTS,
    TABLE_SENSITIVITY,
)
FIGURES = (
    FIGURE_TRAINING,
    FIGURE_GNN,
    FIGURE_GAP,
    FIGURE_TIMING,
    FIGURE_EFFECTS,
    FIGURE_SENSITIVITY,
)
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "evaluation" / "mvp_publication_outputs_v1.json"
)
PALETTE = {
    "unguided_control": "#4B5563",
    "gurobi_original": "#2563EB",
    "gurobi_incumbent_augmented": "#0D9488",
    "scip_original": "#D97706",
    "scip_incumbent_augmented": "#DC2626",
}


class MvpPublicationOutputsError(RuntimeError):
    """Raised when source evidence or a publication artifact fails closed."""


def _read_json(path: Path, *, artifact: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise MvpPublicationOutputsError(f"unreadable {artifact}") from error
    if not isinstance(value, dict):
        raise MvpPublicationOutputsError(f"{artifact} must be a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _read_csv(path: Path, *, artifact: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            records = list(csv.DictReader(stream))
    except (OSError, csv.Error) as error:
        raise MvpPublicationOutputsError(f"unreadable {artifact}") from error
    if not records:
        raise MvpPublicationOutputsError(f"empty {artifact}")
    return records


def _write_csv(
    path: Path, fields: Sequence[str], records: Iterable[Mapping[str, Any]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields))
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field) for field in fields})


def _finite(value: Any, *, field: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as error:
        raise MvpPublicationOutputsError(f"invalid {field}") from error
    if not math.isfinite(normalized):
        raise MvpPublicationOutputsError(f"non-finite {field}")
    return normalized


def _integer(value: Any, *, field: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise MvpPublicationOutputsError(f"invalid {field}") from error
    normalized = int(numeric)
    if not math.isfinite(numeric) or normalized != numeric:
        raise MvpPublicationOutputsError(f"non-integral {field}")
    return normalized


def _optional_finite(value: Any, *, field: str) -> float | None:
    if value in (None, "", "None", "null"):
        return None
    return _finite(value, field=field)


def _optional_integer(value: Any, *, field: str) -> int | None:
    if value in (None, "", "None", "null"):
        return None
    return _integer(value, field=field)


def _boolean(value: Any, *, field: str) -> bool:
    if value in (True, "True", "true", "1", 1):
        return True
    if value in (False, "False", "false", "0", 0):
        return False
    raise MvpPublicationOutputsError(f"invalid {field}")


def _safe_file(root: Path, relative_value: Any, *, artifact: str) -> Path:
    relative = Path(str(relative_value))
    resolved_root = root.resolve()
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise MvpPublicationOutputsError(f"unsafe {artifact} path")
    resolved = (resolved_root / relative).resolve()
    if resolved_root not in resolved.parents or not resolved.is_file():
        raise MvpPublicationOutputsError(f"missing or unsafe {artifact}")
    return resolved


def _read_jsonl(path: Path, *, artifact: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise MvpPublicationOutputsError(
                        f"non-object {artifact} record {line_number}"
                    )
                records.append(value)
    except (OSError, ValueError) as error:
        raise MvpPublicationOutputsError(f"unreadable {artifact}") from error
    if not records:
        raise MvpPublicationOutputsError(f"empty {artifact}")
    return records


def _validate_config(config: Mapping[str, Any]) -> None:
    if (
        config.get("schema_version") != SCHEMA_VERSION
        or config.get("expected_arms") != list(EXPECTED_ARMS)
        or config.get("expected_target_solvers") != ["gurobi", "scip"]
        or config.get("gap_sensitivity_thresholds_relative")
        != [0.01, 0.05, 0.1]
        or config.get("selection_policy") != "no_arm_ranking_or_selection"
        or config.get("development_only") is not True
        or config.get("scientific_reporting_eligible") is not False
    ):
        raise MvpPublicationOutputsError(
            "publication configuration is not the precommitted policy"
        )


def _load_reproducibility(root: Path) -> dict[str, Any]:
    paths = {
        "plan": _safe_file(
            root, REPRODUCIBILITY_PLAN_NAME, artifact="reproducibility plan"
        ),
        "report": _safe_file(
            root, REPRODUCIBILITY_REPORT_NAME, artifact="reproducibility report"
        ),
        "manifest": _safe_file(
            root,
            REPRODUCIBILITY_MANIFEST_NAME,
            artifact="reproducibility manifest",
        ),
        "ledger": _safe_file(
            root, REPRODUCIBILITY_LEDGER_NAME, artifact="reproducibility ledger"
        ),
    }
    plan = _read_json(paths["plan"], artifact="reproducibility plan")
    validate_reproducibility_plan(plan)
    report = _read_json(paths["report"], artifact="reproducibility report")
    manifest = _read_json(paths["manifest"], artifact="reproducibility manifest")
    ledger = _read_jsonl(paths["ledger"], artifact="reproducibility ledger")
    controls = report.get("common_controls", {})
    contract = plan["contract_sha256"]
    if (
        report.get("gate_status") != "passed"
        or report.get("reproducibility_contract_sha256") != contract
        or manifest.get("reproducibility_contract_sha256") != contract
        or not controls
        or not all(value is True for value in controls.values())
        or report.get("eligibility", {}).get("publication_output_layer_ready")
        is not True
        or report.get("eligibility", {}).get("scientific_reporting_eligible")
        is not False
    ):
        raise MvpPublicationOutputsError("reproducibility gate is not admissible")
    if (
        report["outputs"]["artifact_ledger"]["sha256"]
        != sha256_file(paths["ledger"])
        or report["outputs"]["reproducibility_manifest"]["sha256"]
        != sha256_file(paths["manifest"])
        or manifest["artifact_ledger"]["sha256"]
        != sha256_file(paths["ledger"])
    ):
        raise MvpPublicationOutputsError("reproducibility output SHA-256 mismatch")
    index = {
        (record["stage"], record["relative_path"]): record for record in ledger
    }
    if len(index) != len(ledger):
        raise MvpPublicationOutputsError("duplicate reproducibility ledger key")
    return {
        "paths": paths,
        "plan": plan,
        "report": report,
        "manifest": manifest,
        "ledger": ledger,
        "index": index,
    }


def _verified_source(
    evidence: Mapping[str, Any],
    *,
    stage: str,
    root: Path,
    relative_path: str | Path,
    artifact: str,
) -> Path:
    relative = Path(relative_path).as_posix()
    try:
        expected = evidence["index"][(stage, relative)]["sha256"]
    except KeyError as error:
        raise MvpPublicationOutputsError(
            f"{artifact} is absent from the reproducibility ledger"
        ) from error
    path = _safe_file(root, relative, artifact=artifact)
    if sha256_file(path) != expected:
        raise MvpPublicationOutputsError(f"{artifact} SHA-256 mismatch")
    return path


def _load_sources(
    *,
    training_dir: str | Path,
    evaluation_dir: str | Path,
    comparison_dir: str | Path,
    reproducibility_dir: str | Path,
) -> dict[str, Any]:
    roots = {
        "training": Path(training_dir).resolve(),
        "evaluation": Path(evaluation_dir).resolve(),
        "comparison": Path(comparison_dir).resolve(),
        "reproducibility": Path(reproducibility_dir).resolve(),
    }
    evidence = _load_reproducibility(roots["reproducibility"])
    reports = {}
    for stage, file_name in (
        ("training", TRAINING_REPORT_NAME),
        ("evaluation", EVALUATION_REPORT_NAME),
        ("comparison", COMPARISON_REPORT_NAME),
    ):
        path = _verified_source(
            evidence,
            stage=stage,
            root=roots[stage],
            relative_path=file_name,
            artifact=f"{stage} report",
        )
        reports[stage] = _read_json(path, artifact=f"{stage} report")
    if any(report.get("gate_status") != "passed" for report in reports.values()):
        raise MvpPublicationOutputsError("an upstream report gate did not pass")
    if any(
        report.get("eligibility", {}).get("scientific_reporting_eligible")
        is not False
        for report in reports.values()
    ):
        raise MvpPublicationOutputsError("upstream scientific boundary changed")

    histories = {}
    for arm_id in EXPECTED_ARMS:
        relative = Path("arms") / arm_id / HISTORY_NAME
        histories[arm_id] = _verified_source(
            evidence,
            stage="training",
            root=roots["training"],
            relative_path=relative,
            artifact=f"{arm_id} training history",
        )
    source_files = {
        "gnn_metrics": _verified_source(
            evidence,
            stage="evaluation",
            root=roots["evaluation"],
            relative_path=SOURCE_GNN_METRICS,
            artifact="GNN test metrics",
        ),
        "run_table": _verified_source(
            evidence,
            stage="comparison",
            root=roots["comparison"],
            relative_path=SOURCE_RUN_TABLE,
            artifact="solver run table",
        ),
        "arm_table": _verified_source(
            evidence,
            stage="comparison",
            root=roots["comparison"],
            relative_path=SOURCE_ARM_TABLE,
            artifact="solver arm table",
        ),
        "effect_table": _verified_source(
            evidence,
            stage="comparison",
            root=roots["comparison"],
            relative_path=SOURCE_EFFECT_TABLE,
            artifact="paired effect table",
        ),
    }
    return {
        "roots": roots,
        "evidence": evidence,
        "reports": reports,
        "histories": histories,
        "source_files": source_files,
    }


def build_plan(
    *,
    training_dir: str | Path,
    evaluation_dir: str | Path,
    comparison_dir: str | Path,
    reproducibility_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Verify all inputs and precommit a path-sanitized output contract."""
    config_file = Path(config_path).resolve()
    config = _read_json(config_file, artifact="publication configuration")
    _validate_config(config)
    source = _load_sources(
        training_dir=training_dir,
        evaluation_dir=evaluation_dir,
        comparison_dir=comparison_dir,
        reproducibility_dir=reproducibility_dir,
    )
    input_artifacts = {
        "training_histories": {
            arm_id: {
                "relative_path": (Path("arms") / arm_id / HISTORY_NAME).as_posix(),
                "sha256": sha256_file(path),
            }
            for arm_id, path in source["histories"].items()
        },
        **{
            name: {"file_name": path.name, "sha256": sha256_file(path)}
            for name, path in source["source_files"].items()
        },
    }
    evidence = source["evidence"]
    reproducibility_artifacts = {
        name: {"file_name": path.name, "sha256": sha256_file(path)}
        for name, path in evidence["paths"].items()
    }
    contract = {
        "schema_version": SCHEMA_VERSION,
        "analysis_stage": "mvp_publication_tables_and_figures",
        "source_reproducibility_contract_sha256": evidence["plan"][
            "contract_sha256"
        ],
        "source_reproducibility_artifacts": reproducibility_artifacts,
        "source_inputs": input_artifacts,
        "configuration": config,
        "configuration_sha256": sha256_file(config_file),
        "planned_tables": list(TABLES),
        "planned_figures": list(FIGURES),
        "development_only": True,
        "scientific_reporting_eligible": False,
        "arm_selection_performed": False,
    }
    return {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "contract_valid": True,
        "next_gate": "mvp_publication_output_generation",
    }


def validate_plan(plan: Mapping[str, Any]) -> None:
    excluded = {"contract_sha256", "contract_valid", "next_gate"}
    payload = {key: value for key, value in plan.items() if key not in excluded}
    if (
        plan.get("contract_valid") is not True
        or plan.get("contract_sha256") != canonical_sha256(payload)
    ):
        raise MvpPublicationOutputsError("publication plan contract mismatch")


def _normalized_tables(source: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    training: list[dict[str, Any]] = []
    for arm_id in EXPECTED_ARMS:
        rows = _read_csv(
            source["histories"][arm_id], artifact=f"{arm_id} training history"
        )
        previous_epoch = 0
        for row in rows:
            epoch = _integer(row.get("epoch"), field="training epoch")
            if epoch <= previous_epoch:
                raise MvpPublicationOutputsError("training epochs are not ordered")
            previous_epoch = epoch
            training.append(
                {
                    "arm_id": arm_id,
                    "epoch": epoch,
                    "train_loss": _finite(row.get("train_loss"), field="train loss"),
                    "validation_loss": _finite(
                        row.get("validation_loss"), field="validation loss"
                    ),
                    "accuracy": _finite(row.get("accuracy"), field="accuracy"),
                    "precision": _finite(row.get("precision"), field="precision"),
                    "recall": _finite(row.get("recall"), field="recall"),
                    "f1_score": _finite(row.get("f1_score"), field="F1 score"),
                }
            )

    gnn = _read_csv(source["source_files"]["gnn_metrics"], artifact="GNN metrics")
    if {row.get("arm_id") for row in gnn} != set(EXPECTED_ARMS):
        raise MvpPublicationOutputsError("GNN metric arm inventory mismatch")
    gnn_rows = [
        {
            "arm_id": row["arm_id"],
            "n_test_parents": _integer(
                row.get("n_test_parents"), field="test parents"
            ),
            "n_targets": _integer(row.get("n_targets"), field="targets"),
            "unweighted_bce_per_variable": _finite(
                row.get("unweighted_bce_per_variable"), field="test BCE"
            ),
            "accuracy": _finite(row.get("accuracy"), field="test accuracy"),
            "precision": _finite(row.get("precision"), field="test precision"),
            "recall": _finite(row.get("recall"), field="test recall"),
            "f1_score": _finite(row.get("f1_score"), field="test F1"),
        }
        for row in gnn
    ]

    source_runs = _read_csv(
        source["source_files"]["run_table"], artifact="solver runs"
    )
    run_rows: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []
    for row in source_runs:
        common = {
            "run_id": row["run_id"],
            "parent_instance_id": row["parent_instance_id"],
            "target_solver": row["target_solver"],
            "arm_id": row["arm_id"],
            "run_kind": row["run_kind"],
            "solve_status": row["solve_status"],
            "right_censored": _boolean(
                row.get("right_censored"), field="right censoring"
            ),
        }
        run_rows.append(
            {
                **common,
                "terminal_mip_gap_relative": _finite(
                    row.get("terminal_mip_gap_relative"), field="terminal gap"
                ),
                "terminal_mip_gap_percent": _finite(
                    row.get("terminal_mip_gap_percent"), field="terminal gap percent"
                ),
                "best_objective": _optional_finite(
                    row.get("best_objective"), field="best objective"
                ),
                "best_bound": _optional_finite(
                    row.get("best_bound"), field="best bound"
                ),
                "nodes": _optional_integer(row.get("nodes"), field="nodes"),
                "solution_count": _integer(
                    row.get("solution_count"), field="solution count"
                ),
                "fixed_variable_count": _integer(
                    row.get("fixed_variable_count"), field="fixed variables"
                ),
            }
        )
        timing_rows.append(
            {
                **common,
                **{
                    name: _finite(row.get(name), field=name)
                    for name in (
                        "total_wall_time_seconds",
                        "data_read_wall_time_seconds",
                        "model_build_wall_time_seconds",
                        "model_optimize_wall_time_seconds",
                    )
                },
            }
        )

    effects = _read_csv(
        source["source_files"]["effect_table"], artifact="paired effects"
    )
    effect_rows = [dict(row) for row in effects]
    for row in effect_rows:
        row["terminal_mip_gap_relative_improvement"] = _finite(
            row.get("terminal_mip_gap_relative_improvement"),
            field="paired gap improvement",
        )
        row["model_optimize_wall_time_seconds_improvement"] = _finite(
            row.get("model_optimize_wall_time_seconds_improvement"),
            field="paired optimize-time improvement",
        )

    thresholds = source["config"]["gap_sensitivity_thresholds_relative"]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in run_rows:
        grouped[(row["target_solver"], row["arm_id"])].append(row)
    sensitivity: list[dict[str, Any]] = []
    for (solver, arm_id), rows in sorted(grouped.items()):
        for threshold in thresholds:
            eligible = sum(
                row["terminal_mip_gap_relative"] <= threshold for row in rows
            )
            sensitivity.append(
                {
                    "target_solver": solver,
                    "arm_id": arm_id,
                    "threshold_relative": threshold,
                    "threshold_percent": 100.0 * threshold,
                    "runs": len(rows),
                    "runs_at_or_below_threshold": eligible,
                    "proportion_at_or_below_threshold": eligible / len(rows),
                    "right_censored_runs": sum(
                        row["right_censored"] for row in rows
                    ),
                }
            )
    return {
        TABLE_TRAINING: training,
        TABLE_GNN: sorted(gnn_rows, key=lambda row: EXPECTED_ARMS.index(row["arm_id"])),
        TABLE_SOLVER: run_rows,
        TABLE_TIMING: timing_rows,
        TABLE_EFFECTS: effect_rows,
        TABLE_SENSITIVITY: sensitivity,
    }


def _svg_text(x: float, y: float, value: Any, **attributes: Any) -> str:
    def attribute_name(key: str) -> str:
        return "class" if key == "class_" else key.replace("_", "-")

    attrs = " ".join(
        f'{attribute_name(key)}="{html.escape(str(item))}"'
        for key, item in attributes.items()
    )
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" {attrs}>'
        f"{html.escape(str(value))}</text>"
    )


def _svg_document(title: str, subtitle: str, body: Sequence[str]) -> str:
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" '
        'viewBox="0 0 1200 720" role="img">',
        f"<title>{html.escape(title)}</title>",
        f"<desc>{html.escape(subtitle)}</desc>",
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#111827}",
        ".title{font-size:24px;font-weight:700}",
        ".subtitle{font-size:14px;fill:#4B5563}",
        ".axis{stroke:#374151;stroke-width:1}",
        ".grid{stroke:#E5E7EB;stroke-width:1}",
        ".tick{font-size:11px;fill:#4B5563}",
        ".legend{font-size:12px}",
        "</style>",
        '<rect width="1200" height="720" fill="#FFFFFF"/>',
        _svg_text(60, 42, title, class_="title"),
        _svg_text(60, 66, subtitle, class_="subtitle"),
        *body,
        _svg_text(
            60,
            700,
            "Development-only descriptive MVP; no arm selection or inference.",
            class_="subtitle",
        ),
        "</svg>",
    ]
    return "\n".join(elements) + "\n"


def _label(value: str) -> str:
    return value.replace("_incumbent_augmented", "+aug").replace(
        "_original", "+orig"
    )


def _short_label(value: str) -> str:
    labels = {
        "unguided_control": "CTL",
        "gurobi_original": "G-orig",
        "gurobi_incumbent_augmented": "G-aug",
        "scip_original": "S-orig",
        "scip_incumbent_augmented": "S-aug",
    }
    return labels[value]


def _bar_figure(
    *,
    title: str,
    subtitle: str,
    categories: Sequence[str],
    series: Sequence[tuple[str, str, Sequence[float]]],
    transform=lambda value: value,
    value_label=lambda value: f"{value:.3g}",
) -> str:
    left, top, width, height = 90.0, 110.0, 1040.0, 470.0
    transformed = [transform(value) for _, _, values in series for value in values]
    maximum = max(transformed + [1e-12]) * 1.12
    body = [
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" '
        f'y2="{top + height}"/>',
        f'<line class="axis" x1="{left}" y1="{top + height}" '
        f'x2="{left + width}" y2="{top + height}"/>',
    ]
    for tick in range(6):
        y = top + height - height * tick / 5
        body.append(
            f'<line class="grid" x1="{left}" y1="{y:.2f}" '
            f'x2="{left + width}" y2="{y:.2f}"/>'
        )
        body.append(_svg_text(left - 10, y + 4, f"{maximum * tick / 5:.2g}",
                              class_="tick", text_anchor="end"))
    group_width = width / len(categories)
    bar_width = min(28.0, group_width * 0.72 / len(series))
    for category_index, category in enumerate(categories):
        center = left + group_width * (category_index + 0.5)
        total_width = bar_width * len(series)
        for series_index, (_, color, values) in enumerate(series):
            value = values[category_index]
            scaled = transform(value)
            bar_height = height * scaled / maximum
            x = center - total_width / 2 + series_index * bar_width
            y = top + height - bar_height
            body.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width - 2:.2f}" '
                f'height="{bar_height:.2f}" fill="{color}" opacity="0.88"/>'
            )
            body.append(
                _svg_text(
                    x + (bar_width - 2) / 2,
                    max(top + 12, y - 5),
                    value_label(value),
                    class_="tick",
                    text_anchor="middle",
                )
            )
        body.append(
            _svg_text(
                center,
                top + height + 20,
                category,
                class_="tick",
                text_anchor="middle",
            )
        )
    legend_x = 90.0
    for name, color, _ in series:
        body.append(
            f'<rect x="{legend_x:.2f}" y="620" width="14" height="14" '
            f'fill="{color}"/>'
        )
        body.append(_svg_text(legend_x + 20, 632, name, class_="legend"))
        legend_x += 205
    return _svg_document(title, subtitle, body)


def _training_figure(records: Sequence[Mapping[str, Any]]) -> str:
    by_arm: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_arm[str(record["arm_id"])].append(record)
    body: list[str] = []
    panels = (
        (70.0, "train_loss", "Training loss"),
        (630.0, "validation_loss", "Validation loss"),
    )
    for left, field, label in panels:
        top, width, height = 125.0, 490.0, 440.0
        values = [_finite(row[field], field=field) for row in records]
        maximum = max(values) * 1.08
        minimum = min(values) * 0.92
        span = max(maximum - minimum, 1e-12)
        body.extend(
            [
                _svg_text(left, 105, label, font_size="16", font_weight="700"),
                f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" '
                f'y2="{top + height}"/>',
                f'<line class="axis" x1="{left}" y1="{top + height}" '
                f'x2="{left + width}" y2="{top + height}"/>',
            ]
        )
        max_epoch = max(int(row["epoch"]) for row in records)
        for arm_id in EXPECTED_ARMS:
            rows = sorted(by_arm[arm_id], key=lambda row: int(row["epoch"]))
            points = []
            for row in rows:
                x = left + width * (int(row["epoch"]) - 1) / max(max_epoch - 1, 1)
                y = top + height * (maximum - float(row[field])) / span
                points.append(f"{x:.2f},{y:.2f}")
                body.append(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" '
                    f'fill="{PALETTE[arm_id]}"/>'
                )
            body.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{PALETTE[arm_id]}" stroke-width="2.5"/>'
            )
        for epoch in range(1, max_epoch + 1):
            x = left + width * (epoch - 1) / max(max_epoch - 1, 1)
            body.append(
                _svg_text(x, top + height + 20, epoch, class_="tick",
                          text_anchor="middle")
            )
    legend_x = 80.0
    for arm_id in EXPECTED_ARMS:
        body.append(
            f'<line x1="{legend_x}" y1="620" x2="{legend_x + 22}" y2="620" '
            f'stroke="{PALETTE[arm_id]}" stroke-width="3"/>'
        )
        body.append(_svg_text(legend_x + 28, 624, _label(arm_id), class_="legend"))
        legend_x += 270
    return _svg_document(
        "GNN training and validation trajectories",
        "Epoch-wise loss for four independently trained arms.",
        body,
    )


def _effects_figure(records: Sequence[Mapping[str, Any]]) -> str:
    gap = [float(row["terminal_mip_gap_relative_improvement"]) for row in records]
    timing = [
        float(row["model_optimize_wall_time_seconds_improvement"])
        for row in records
    ]
    max_x = max(max(abs(value) for value in timing), 1e-12) * 1.1
    max_y = max(max(abs(value) for value in gap), 1e-12) * 1.1
    left, top, width, height = 100.0, 110.0, 1000.0, 480.0
    center_x = left + width / 2
    center_y = top + height / 2
    body = [
        f'<line class="axis" x1="{left}" y1="{center_y}" '
        f'x2="{left + width}" y2="{center_y}"/>',
        f'<line class="axis" x1="{center_x}" y1="{top}" '
        f'x2="{center_x}" y2="{top + height}"/>',
        _svg_text(center_x, top + height + 35, "Optimization-time improvement (s)",
                  class_="legend", text_anchor="middle"),
        _svg_text(25, center_y, "Gap improvement", class_="legend",
                  transform=f"rotate(-90 25 {center_y})", text_anchor="middle"),
    ]
    for row in records:
        x_value = float(row["model_optimize_wall_time_seconds_improvement"])
        y_value = float(row["terminal_mip_gap_relative_improvement"])
        x = center_x + x_value / max_x * width / 2
        y = center_y - y_value / max_y * height / 2
        censored = row.get("censoring_interpretation") == (
            "right_censored_descriptive_only"
        )
        body.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" '
            f'fill="{"#FFFFFF" if censored else "#2563EB"}" '
            f'stroke="#2563EB" stroke-width="2"/>'
        )
    body.append(_svg_text(100, 625, "Filled: uncensored", class_="legend"))
    body.append(_svg_text(270, 625, "Open: right-censored", class_="legend"))
    return _svg_document(
        "Paired descriptive Neural Diving effects",
        "Positive coordinates indicate lower gap and shorter optimization time.",
        body,
    )


def _figure_payloads(
    tables: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, str]:
    gnn = tables[TABLE_GNN]
    gnn_categories = [_short_label(str(row["arm_id"])) for row in gnn]
    gnn_figure = _bar_figure(
        title="Held-out GNN classification quality",
        subtitle="Precision, recall, and F1 at the precommitted threshold.",
        categories=gnn_categories,
        series=(
            ("Precision", "#2563EB", [float(row["precision"]) for row in gnn]),
            ("Recall", "#0D9488", [float(row["recall"]) for row in gnn]),
            ("F1", "#DC2626", [float(row["f1_score"]) for row in gnn]),
        ),
    )
    runs = tables[TABLE_SOLVER]
    run_categories = [
        f"{str(row['target_solver'])[0].upper()}:{_short_label(str(row['arm_id']))}"
        for row in runs
    ]
    gap_figure = _bar_figure(
        title="Terminal MIP gap by Neural Diving run",
        subtitle="Right-censored runs are retained; exact values remain in the table.",
        categories=run_categories,
        series=(("MIP gap (%)", "#7C3AED", [
            float(row["terminal_mip_gap_percent"]) for row in runs
        ]),),
        value_label=lambda value: f"{value:.2f}%",
    )
    timings = tables[TABLE_TIMING]
    timing_figure = _bar_figure(
        title="Four-region execution-time audit",
        subtitle="Axis uses log10(1 + seconds); the CSV retains exact wall times.",
        categories=run_categories,
        series=(
            ("Total", "#111827", [float(row["total_wall_time_seconds"])
                                    for row in timings]),
            ("Read", "#2563EB", [float(row["data_read_wall_time_seconds"])
                                   for row in timings]),
            ("Build", "#D97706", [float(row["model_build_wall_time_seconds"])
                                    for row in timings]),
            ("Optimize", "#DC2626", [
                float(row["model_optimize_wall_time_seconds"]) for row in timings
            ]),
        ),
        transform=lambda value: math.log10(1.0 + value),
        value_label=lambda value: f"{value:.1f}s",
    )
    sensitivity = tables[TABLE_SENSITIVITY]
    sensitivity_groups: dict[float, list[float]] = defaultdict(list)
    ordered_groups = sorted({
        (str(row["target_solver"]), str(row["arm_id"])) for row in sensitivity
    })
    for threshold in (0.01, 0.05, 0.1):
        by_group = {
            (str(row["target_solver"]), str(row["arm_id"])): float(
                row["proportion_at_or_below_threshold"]
            )
            for row in sensitivity
            if math.isclose(float(row["threshold_relative"]), threshold)
        }
        sensitivity_groups[threshold] = [by_group[group] for group in ordered_groups]
    sensitivity_figure = _bar_figure(
        title="MIP-gap sensitivity",
        subtitle="Proportion of runs at or below each precommitted gap threshold.",
        categories=[f"{solver[0].upper()}:{_short_label(arm)}"
                    for solver, arm in ordered_groups],
        series=(
            ("<=1%", "#2563EB", sensitivity_groups[0.01]),
            ("<=5%", "#0D9488", sensitivity_groups[0.05]),
            ("<=10%", "#D97706", sensitivity_groups[0.1]),
        ),
        value_label=lambda value: f"{100 * value:.0f}%",
    )
    return {
        FIGURE_TRAINING: _training_figure(tables[TABLE_TRAINING]),
        FIGURE_GNN: gnn_figure,
        FIGURE_GAP: gap_figure,
        FIGURE_TIMING: timing_figure,
        FIGURE_EFFECTS: _effects_figure(tables[TABLE_EFFECTS]),
        FIGURE_SENSITIVITY: sensitivity_figure,
    }


def run_generation(
    *,
    training_dir: str | Path,
    evaluation_dir: str | Path,
    comparison_dir: str | Path,
    reproducibility_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate contract-bound CSV tables and deterministic SVG figures."""
    output = Path(output_dir).resolve()
    expected = [output / PLAN_NAME, output / REPORT_NAME, *(
        output / name for name in (*TABLES, *FIGURES)
    )]
    if not overwrite and any(path.exists() for path in expected):
        raise FileExistsError("publication output exists; use --overwrite")
    plan = build_plan(
        training_dir=training_dir,
        evaluation_dir=evaluation_dir,
        comparison_dir=comparison_dir,
        reproducibility_dir=reproducibility_dir,
        config_path=config_path,
    )
    validate_plan(plan)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / PLAN_NAME, plan)
    if dry_run:
        return plan
    source = _load_sources(
        training_dir=training_dir,
        evaluation_dir=evaluation_dir,
        comparison_dir=comparison_dir,
        reproducibility_dir=reproducibility_dir,
    )
    source["config"] = plan["configuration"]
    tables = _normalized_tables(source)
    for name, records in tables.items():
        if not records:
            raise MvpPublicationOutputsError(f"empty normalized table: {name}")
        _write_csv(output / name, list(records[0]), records)
    figures = _figure_payloads(tables)
    for name, payload in figures.items():
        (output / name).write_text(payload, encoding="utf-8", newline="\n")
    artifacts = {
        name: {
            "file_name": name,
            "sha256": sha256_file(output / name),
            "size_bytes": (output / name).stat().st_size,
        }
        for name in (*TABLES, *FIGURES)
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "publication_contract_sha256": plan["contract_sha256"],
        "source_reproducibility_contract_sha256": plan[
            "source_reproducibility_contract_sha256"
        ],
        "source_inputs": plan["source_inputs"],
        "artifacts": artifacts,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    _write_json(output / MANIFEST_NAME, manifest)
    report = {
        "schema_version": SCHEMA_VERSION,
        "publication_contract_sha256": plan["contract_sha256"],
        "probe_completed": True,
        "gate_status": "passed",
        "summary": {
            "tables_written": len(TABLES),
            "figures_written": len(FIGURES),
            "training_epoch_records": len(tables[TABLE_TRAINING]),
            "gnn_metric_records": len(tables[TABLE_GNN]),
            "solver_run_records": len(tables[TABLE_SOLVER]),
            "paired_effect_records": len(tables[TABLE_EFFECTS]),
            "gap_sensitivity_records": len(tables[TABLE_SENSITIVITY]),
        },
        "common_controls": {
            "source_reproducibility_gate_passed": True,
            "source_artifact_hashes_match": True,
            "four_training_arms_present": len({
                row["arm_id"] for row in tables[TABLE_TRAINING]
            }) == 4,
            "four_gnn_metric_arms_present": len(tables[TABLE_GNN]) == 4,
            "training_epoch_inventory_matches": len(tables[TABLE_TRAINING])
            == sum(
                int(arm["epochs_completed"])
                for arm in source["reports"]["training"]["arms"].values()
            ),
            "solver_run_inventory_matches": len(tables[TABLE_SOLVER])
            == int(source["reports"]["comparison"]["execution"]["runs"]),
            "paired_effect_inventory_matches": len(tables[TABLE_EFFECTS])
            == int(
                source["reports"]["comparison"]["execution"][
                    "paired_descriptive_effects"
                ]
            ),
            "primary_solver_outcomes_preserved": all(
                math.isfinite(float(row["terminal_mip_gap_relative"]))
                for row in tables[TABLE_SOLVER]
            ),
            "four_time_regions_preserved": all(
                all(float(row[field]) >= 0.0 for field in (
                    "total_wall_time_seconds",
                    "data_read_wall_time_seconds",
                    "model_build_wall_time_seconds",
                    "model_optimize_wall_time_seconds",
                ))
                for row in tables[TABLE_TIMING]
            ),
            "right_censoring_preserved": sum(
                bool(row["right_censored"]) for row in tables[TABLE_SOLVER]
            )
            == int(
                source["reports"]["comparison"]["censoring"][
                    "right_censored_runs"
                ]
            ),
            "gap_sensitivity_precommitted": sorted({
                float(row["threshold_relative"])
                for row in tables[TABLE_SENSITIVITY]
            }) == [0.01, 0.05, 0.1],
            "arm_selection_absent": source["reports"]["comparison"][
                "eligibility"
            ].get("arm_selection_eligible") is False,
            "scientific_reporting_disabled": all(
                report["eligibility"]["scientific_reporting_eligible"] is False
                for report in source["reports"].values()
            ),
        },
        "outputs": {
            "manifest": {
                "file_name": MANIFEST_NAME,
                "sha256": sha256_file(output / MANIFEST_NAME),
            },
            "artifacts": artifacts,
        },
        "eligibility": {
            "publication_assets_ready_for_mvp_review": True,
            "manuscript_claims_eligible": False,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": "development_publication_assets_generated",
            "next_gate": "english_repository_documentation_and_dependency_audit",
        },
    }
    if not all(report["common_controls"].values()):
        raise MvpPublicationOutputsError("publication common controls failed")
    _write_json(output / REPORT_NAME, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate reproducible development-only MVP result assets."
    )
    parser.add_argument("--training_dir", required=True)
    parser.add_argument("--evaluation_dir", required=True)
    parser.add_argument("--comparison_dir", required=True)
    parser.add_argument("--reproducibility_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_generation(
            training_dir=args.training_dir,
            evaluation_dir=args.evaluation_dir,
            comparison_dir=args.comparison_dir,
            reproducibility_dir=args.reproducibility_dir,
            output_dir=args.output_dir,
            config_path=args.config,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
    except (MvpPublicationOutputsError, FileExistsError) as error:
        print(f"[ERROR] {error}")
        return 1
    if args.dry_run:
        print(
            f"[INFO] contract={result['contract_sha256']} | "
            f"tables={len(TABLES)} | figures={len(FIGURES)} | dry_run=true"
        )
        print(f"[INFO] Plan: {Path(args.output_dir).resolve() / PLAN_NAME}")
    else:
        print(
            f"[INFO] gate={result['gate_status']} | "
            f"tables={result['summary']['tables_written']} | "
            f"figures={result['summary']['figures_written']}"
        )
        print(f"[INFO] Report: {Path(args.output_dir).resolve() / REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
