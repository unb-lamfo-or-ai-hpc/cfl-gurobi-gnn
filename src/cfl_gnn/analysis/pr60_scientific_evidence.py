"""Build a path-sanitized evidence package from the frozen PR57--PR59 stages.

This stage performs no training, inference, or solver execution. It validates
the immutable upstream contracts, preserves censoring, and generates only
descriptive tables and figures suitable for development-MVP review.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.pipelines import pr59_heldout_guidance as pr59
from cfl_gnn.pipelines.pr58_validation_guidance import (
    EXPECTED_TRAINING_CONTRACT,
    _validate_training,
)
from cfl_gnn.training.figures import write_training_validation_loss_figure
from cfl_gnn.training.gasse_reconnected import canonical_sha256, write_json


CONFIG = PROJECT_ROOT / "configs/evaluation/pr60_scientific_evidence_v1.json"
PLAN_NAME = "pr60_scientific_evidence_plan.json"
REPORT_NAME = "pr60_scientific_evidence_report.json"
MANIFEST_NAME = "pr60_scientific_evidence_manifest.json"
TABLE_TRAINING = "table_training_epoch_metrics.csv"
TABLE_PREDICTIVE = "table_predictive_metrics.csv"
TABLE_OUTCOMES = "table_solver_outcomes.csv"
TABLE_EFFECTS = "table_paired_gap_effects.csv"
TABLE_CENSORING = "table_censoring_summary.csv"
TABLE_INFLUENCE = "table_heldout_influence_analysis.csv"
FIGURE_PIPELINE = "figure_offline_online_pipeline.svg"
FIGURE_TRAINING = "figure_training_validation_loss.svg"
FIGURE_PREDICTIVE = "figure_predictive_quality.svg"
FIGURE_EFFECTS = "figure_validation_test_gap_effects.svg"
FIGURE_TIME = "figure_time_to_ten_percent_gap.svg"
TABLES = (
    TABLE_TRAINING,
    TABLE_PREDICTIVE,
    TABLE_OUTCOMES,
    TABLE_EFFECTS,
    TABLE_CENSORING,
    TABLE_INFLUENCE,
)
FIGURES = (
    FIGURE_PIPELINE,
    FIGURE_TRAINING,
    FIGURE_PREDICTIVE,
    FIGURE_EFFECTS,
    FIGURE_TIME,
)
SOURCE_FILES = {
    "training_plan": "gasse_training_plan.json",
    "training_report": "gasse_training_report.json",
    "training_history": "training_epoch_metrics.csv",
    "training_audit": "pr57_54_training_audit.json",
    "evaluation_report": "evaluation_recovery/gasse_evaluation_report.json",
    "validation_report": "pr58_validation_guidance_report.json",
    "validation_outcomes": "per_method_outcomes.json",
    "validation_effects": "paired_effects.json",
    "heldout_report": "pr59_heldout_guidance_report.json",
    "heldout_outcomes": "per_method_outcomes.json",
    "heldout_effects": "paired_effects.json",
}
UNSAFE_TOKENS = ("/raid/", "/home/", "gurobi.lic", "WLSAccessID", "WLSSecret")


class ScientificEvidenceError(RuntimeError):
    """Raised when frozen evidence or a generated publication artifact fails."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ScientificEvidenceError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ScientificEvidenceError(f"JSON artifact is not an object: {path.name}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except (OSError, csv.Error) as error:
        raise ScientificEvidenceError(f"unreadable CSV artifact: {path.name}") from error
    if not rows:
        raise ScientificEvidenceError(f"empty CSV artifact: {path.name}")
    return rows


def _records(path: Path) -> list[dict[str, Any]]:
    value = _read_json(path).get("records")
    if not isinstance(value, list) or not value or not all(isinstance(row, dict) for row in value):
        raise ScientificEvidenceError(f"invalid record artifact: {path.name}")
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ScientificEvidenceError(f"cannot write empty table: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _descriptor(root: Path, path: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved_root not in resolved.parents or not resolved.is_file():
        raise ScientificEvidenceError(f"unsafe or missing artifact: {path.name}")
    return {
        "relative_path": resolved.relative_to(resolved_root).as_posix(),
        "sha256": sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _checked(root: Path, descriptor: Mapping[str, Any]) -> Path:
    relative = Path(str(descriptor.get("relative_path", "")))
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or resolved_root not in candidate.parents
        or not candidate.is_file()
        or sha256_file(candidate) != descriptor.get("sha256")
        or candidate.stat().st_size != descriptor.get("size_bytes")
    ):
        raise ScientificEvidenceError("source descriptor validation failed")
    return candidate


def _config() -> dict[str, Any]:
    value = _read_json(CONFIG)
    if (
        value.get("protocol_id") != "pr60_pr57_pr59_scientific_evidence_v1"
        or value.get("seed") != 42
        or value.get("objective_sense") != "MINIMIZE"
        or value.get("training_contract_sha256") != EXPECTED_TRAINING_CONTRACT
        or value.get("validation_contract_sha256") != pr59.EXPECTED_VALIDATION_CONTRACT
        or value.get("heldout_contract_sha256")
        != "94abd94ba3eb5d4023b95fc3009330073aad02f9232d018149af2498cf62a670"
        or tuple(value.get("optimization_methods", ())) != pr59.METHODS
        or value.get("confirmatory_significance_claim_allowed") is not False
        or value.get("policy_reselection_after_test") is not False
        or value.get("development_only") is not True
        or value.get("scientific_reporting_eligible") is not False
    ):
        raise ScientificEvidenceError("PR60 evidence policy changed")
    return value


def _validate_sources(training: Path, validation: Path, heldout: Path) -> dict[str, Any]:
    training_plan, training_report, training_audit = _validate_training(training)
    validation_report, _ = pr59._validation_authorization(validation)
    heldout_verification = pr59.verify_audit(heldout)
    heldout_report = _read_json(heldout / SOURCE_FILES["heldout_report"])
    if heldout_report.get("contract_sha256") != _config()["heldout_contract_sha256"]:
        raise ScientificEvidenceError("held-out PR59 contract changed")
    evaluation = _read_json(training / SOURCE_FILES["evaluation_report"])
    if (
        evaluation.get("gate_status") != "passed"
        or evaluation.get("test_partition_usage") != "held_out_evaluation_only"
        or evaluation.get("eligibility", {}).get("development_only") is not True
        or evaluation.get("eligibility", {}).get("scientific_reporting_eligible") is not False
    ):
        raise ScientificEvidenceError("PR57 predictive evaluation is invalid")
    return {
        "training_plan": training_plan,
        "training_report": training_report,
        "training_audit": training_audit,
        "evaluation_report": evaluation,
        "validation_report": validation_report,
        "heldout_report": heldout_report,
        "heldout_verification": heldout_verification,
    }


def build_plan(training_dir: Path, validation_dir: Path, heldout_dir: Path) -> dict[str, Any]:
    training = training_dir.resolve()
    validation = validation_dir.resolve()
    heldout = heldout_dir.resolve()
    evidence = _validate_sources(training, validation, heldout)
    roots = {"training": training, "validation": validation, "heldout": heldout}
    source_inputs: dict[str, dict[str, Any]] = {}
    for key, relative in SOURCE_FILES.items():
        source = "training" if key.startswith("training") or key == "evaluation_report" else (
            "validation" if key.startswith("validation") else "heldout"
        )
        source_inputs[key] = {"source": source, **_descriptor(roots[source], roots[source] / relative)}
    payload = {
        "schema_version": 1,
        "stage": "development_scientific_evidence_synthesis",
        "policy": _config(),
        "policy_sha256": sha256_file(CONFIG),
        "source_inputs": source_inputs,
        "source_contracts": {
            "training": evidence["training_plan"]["contract_sha256"],
            "validation": evidence["validation_report"]["contract_sha256"],
            "heldout": evidence["heldout_report"]["contract_sha256"],
        },
        "solver_runs_executed": 0,
        "training_runs_executed": 0,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {**payload, "contract_sha256": canonical_sha256(payload), "contract_valid": True}


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ScientificEvidenceError(f"invalid numeric value: {name}") from error
    if not math.isfinite(result):
        raise ScientificEvidenceError(f"non-finite numeric value: {name}")
    return result


def _history_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in _read_csv(path):
        rows.append(
            {
                "epoch": int(row["epoch"]),
                "training_weighted_bce": _finite(row["train_loss"], "train_loss"),
                "validation_weighted_bce": _finite(row["validation_loss"], "validation_loss"),
                "accuracy": _finite(row["accuracy"], "accuracy"),
                "precision": _finite(row["precision"], "precision"),
                "recall": _finite(row["recall"], "recall"),
                "f1_score": _finite(row["f1_score"], "f1_score"),
            }
        )
    if [row["epoch"] for row in rows] != list(range(1, 101)):
        raise ScientificEvidenceError("training history is not the full 100-epoch sequence")
    return rows


def _predictive_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    aggregate = report["aggregate_metrics"]
    score = report["score_diagnostics"]
    macro = report["parent_macro_score_diagnostics"]
    return [
        {
            "scope": "micro_all_test_variables",
            "targets": aggregate["n_targets"],
            "positives": aggregate["n_positive"],
            "accuracy": aggregate["accuracy"],
            "precision": aggregate["precision"],
            "recall": aggregate["recall"],
            "f1_score": aggregate["f1_score"],
            "roc_auc": report["roc_auc"],
            "average_precision": score["average_precision"],
            "brier_score": score["brier_score"],
            "expected_calibration_error": score["expected_calibration_error"],
        },
        {
            "scope": "parent_macro",
            "targets": "",
            "positives": "",
            "accuracy": report["parent_macro_classification"]["accuracy"],
            "precision": report["parent_macro_classification"]["precision"],
            "recall": report["parent_macro_classification"]["recall"],
            "f1_score": report["parent_macro_classification"]["f1_score"],
            "roc_auc": "",
            "average_precision": macro["average_precision"],
            "brier_score": macro["brier_score"],
            "expected_calibration_error": macro["expected_calibration_error"],
        },
    ]


def _outcome_rows(validation: Sequence[Mapping[str, Any]], heldout: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for partition, records in (("validation", validation), ("test", heldout)):
        for row in records:
            rows.append({"partition": partition, **row})
    return rows


def _effect_rows(validation: Sequence[Mapping[str, Any]], heldout: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for partition, records in (("validation", validation), ("test", heldout)):
        for row in records:
            rows.append({"partition": partition, **row})
    return rows


def _censoring_rows(outcomes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for partition in ("validation", "test"):
        for method in pr59.METHODS:
            selected = [row for row in outcomes if row["partition"] == partition and row["method"] == method]
            rows.append(
                {
                    "partition": partition,
                    "method": method,
                    "runs": len(selected),
                    "right_censored_runs": sum(bool(row["right_censored"]) for row in selected),
                    "gap_le_0.1_observed_runs": sum(row["first_observed_gap_le_0.1_seconds"] is not None for row in selected),
                }
            )
    return rows


def _influence_rows(effects: Sequence[Mapping[str, Any]], exclusions: Sequence[Sequence[str]]) -> list[dict[str, Any]]:
    learned = [row for row in effects if row["partition"] == "test" and row["method"] == pr59.METHODS[2]]
    rows = []
    for excluded in exclusions:
        values = [
            _finite(row["terminal_gap_difference_guided_minus_control"], "gap difference")
            for row in learned
            if row["source_instance_id"] not in excluded
        ]
        rows.append(
            {
                "analysis": "all_heldout" if not excluded else "exclude_" + "_and_".join(excluded),
                "excluded_parent_ids": ";".join(excluded),
                "included_parents": len(values),
                "gnn_gap_wins": sum(value < 0.0 for value in values),
                "mean_gap_difference_guided_minus_control": statistics.fmean(values),
                "median_gap_difference_guided_minus_control": statistics.median(values),
            }
        )
    return rows


def _svg_document(title: str, subtitle: str, body: Iterable[str], *, height: int = 720) -> str:
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            f'<text x="60" y="55" font-family="Arial" font-size="26" font-weight="bold">{html.escape(title)}</text>',
            f'<text x="60" y="84" font-family="Arial" font-size="15" fill="#4B5563">{html.escape(subtitle)}</text>',
            *body,
            '<text x="60" y="700" font-family="Arial" font-size="13" fill="#991B1B">Development-only descriptive evidence; no confirmatory significance claim.</text>',
            "</svg>",
            "",
        ]
    )


def _pipeline_svg() -> str:
    boxes = [
        (60, "Gurobi-authoritative\nbipartite graphs"),
        (300, "Offline GNN training\n34 train / 10 validation"),
        (540, "Frozen checkpoint\nand class-aware selector"),
        (780, "Fresh Gurobi models\n3 paired methods"),
        (1020, "Held-out outcomes\ngap, time, censoring"),
    ]
    body = []
    for index, (x, label) in enumerate(boxes):
        body.append(f'<rect x="{x}" y="245" width="170" height="115" rx="10" fill="#EFF6FF" stroke="#2563EB" stroke-width="2"/>')
        for line_index, line in enumerate(label.split("\n")):
            body.append(f'<text x="{x + 85}" y="{292 + 24 * line_index}" text-anchor="middle" font-family="Arial" font-size="15">{html.escape(line)}</text>')
        if index < len(boxes) - 1:
            body.append(f'<line x1="{x + 170}" y1="302" x2="{x + 230}" y2="302" stroke="#111827" stroke-width="2" marker-end="url(#arrow)"/>')
    body.insert(0, '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#111827"/></marker></defs>')
    body.extend(
        [
            '<text x="300" y="205" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold" fill="#0F766E">OFFLINE</text>',
            '<text x="900" y="205" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold" fill="#7C3AED">ONLINE SOLVER APPLICATION</text>',
            '<line x1="660" y1="155" x2="660" y2="475" stroke="#9CA3AF" stroke-dasharray="7 5"/>',
        ]
    )
    return _svg_document("CFL-GNN evidence pipeline", "The held-out test outcomes cannot alter the frozen checkpoint or guidance policy.", body)


def _predictive_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    micro = rows[0]
    metrics = [
        ("ROC AUC", float(micro["roc_auc"])),
        ("Average precision", float(micro["average_precision"])),
        ("F1 score", float(micro["f1_score"])),
        ("Recall", float(micro["recall"])),
    ]
    body = []
    for index, (label, value) in enumerate(metrics):
        y = 150 + index * 105
        body.extend(
            [
                f'<text x="60" y="{y + 25}" font-family="Arial" font-size="16">{html.escape(label)}</text>',
                f'<rect x="260" y="{y}" width="{800 * value:.2f}" height="36" fill="#0D9488"/>',
                f'<text x="{275 + 800 * value:.2f}" y="{y + 25}" font-family="Arial" font-size="15">{value:.4f}</text>',
            ]
        )
    return _svg_document("Held-out predictive quality", "Variable-level metrics from the untouched graph test partition.", body)


def _effects_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    learned = [row for row in rows if row["method"] == pr59.METHODS[2]]
    values = [_finite(row["terminal_gap_difference_guided_minus_control"], "gap effect") for row in learned]
    scale = 1150.0
    zero = 600
    body = [f'<line x1="{zero}" y1="120" x2="{zero}" y2="625" stroke="#111827" stroke-width="2"/>']
    for index, (row, value) in enumerate(zip(learned, values)):
        y = 145 + index * 38
        x = zero + value * scale
        color = "#0D9488" if value < 0 else "#DC2626"
        body.extend(
            [
                f'<text x="55" y="{y + 5}" font-family="Arial" font-size="12">{html.escape(row["partition"] + ":" + row["source_instance_id"].replace("CFL_medium_instance_", "m"))}</text>',
                f'<line x1="{zero}" y1="{y}" x2="{x:.2f}" y2="{y}" stroke="{color}" stroke-width="7"/>',
                f'<circle cx="{x:.2f}" cy="{y}" r="5" fill="{color}"/>',
            ]
        )
    return _svg_document("Learned-start terminal-gap effects", "Negative values favor the GNN start; validation and held-out test effects are both shown.", body)


def _time_svg(outcomes: Sequence[Mapping[str, Any]]) -> str:
    selected = [row for row in outcomes if row["partition"] == "test"]
    body = []
    for index, row in enumerate(selected):
        parent = row["source_instance_id"].replace("CFL_medium_instance_", "m")
        method = {pr59.METHODS[0]: "Control", pr59.METHODS[1]: "Root-LP", pr59.METHODS[2]: "GNN"}[row["method"]]
        y = 125 + index * 29
        observed = row["first_observed_gap_le_0.1_seconds"]
        value = 3600.0 if observed is None else float(observed)
        color = "#9CA3AF" if observed is None else ("#0D9488" if method == "GNN" else "#2563EB")
        body.extend(
            [
                f'<text x="55" y="{y + 4}" font-family="Arial" font-size="11">{html.escape(parent + " " + method)}</text>',
                f'<rect x="210" y="{y - 10}" width="{value / 3600 * 850:.2f}" height="14" fill="{color}"/>',
                f'<text x="1070" y="{y + 4}" font-family="Arial" font-size="11">{"censored" if observed is None else f"{value:.0f} s"}</text>',
            ]
        )
    return _svg_document("First observed time to relative MIP gap <= 10%", "Bars reaching 3,600 s in gray are right-censored, not observed hitting times.", body)


def generate(plan: Mapping[str, Any], roots: Mapping[str, Path], output_dir: Path) -> dict[str, Any]:
    payload = {key: value for key, value in plan.items() if key not in {"contract_sha256", "contract_valid"}}
    if plan.get("contract_valid") is not True or canonical_sha256(payload) != plan.get("contract_sha256"):
        raise ScientificEvidenceError("PR60 plan contract mismatch")
    source_paths = {
        key: _checked(roots[value["source"]], value)
        for key, value in plan["source_inputs"].items()
    }
    _validate_sources(roots["training"], roots["validation"], roots["heldout"])
    output_dir.mkdir(parents=True, exist_ok=False)
    history = _history_rows(source_paths["training_history"])
    evaluation = _read_json(source_paths["evaluation_report"])
    predictive = _predictive_rows(evaluation)
    validation_outcomes = _records(source_paths["validation_outcomes"])
    heldout_outcomes = _records(source_paths["heldout_outcomes"])
    validation_effects = _records(source_paths["validation_effects"])
    heldout_effects = _records(source_paths["heldout_effects"])
    outcomes = _outcome_rows(validation_outcomes, heldout_outcomes)
    effects = _effect_rows(validation_effects, heldout_effects)
    censoring = _censoring_rows(outcomes)
    influence = _influence_rows(effects, plan["policy"]["influence_exclusions"])
    _write_csv(output_dir / TABLE_TRAINING, history)
    _write_csv(output_dir / TABLE_PREDICTIVE, predictive)
    _write_csv(output_dir / TABLE_OUTCOMES, outcomes)
    _write_csv(output_dir / TABLE_EFFECTS, effects)
    _write_csv(output_dir / TABLE_CENSORING, censoring)
    _write_csv(output_dir / TABLE_INFLUENCE, influence)
    loss_history = [
        {"epoch": row["epoch"], "train_loss": row["training_weighted_bce"], "validation_loss": row["validation_weighted_bce"]}
        for row in history
    ]
    write_training_validation_loss_figure(loss_history, output_dir / FIGURE_TRAINING, title="Training and validation weighted BCE (54-parent cohort)")
    (output_dir / FIGURE_PIPELINE).write_text(_pipeline_svg(), encoding="utf-8", newline="\n")
    (output_dir / FIGURE_PREDICTIVE).write_text(_predictive_svg(predictive), encoding="utf-8", newline="\n")
    (output_dir / FIGURE_EFFECTS).write_text(_effects_svg(effects), encoding="utf-8", newline="\n")
    (output_dir / FIGURE_TIME).write_text(_time_svg(outcomes), encoding="utf-8", newline="\n")
    generated = [*(output_dir / name for name in TABLES), *(output_dir / name for name in FIGURES)]
    manifest = {
        "schema_version": 1,
        "contract_sha256": plan["contract_sha256"],
        "artifacts": {path.name: _descriptor(output_dir, path) for path in generated},
    }
    write_json(output_dir / MANIFEST_NAME, manifest)
    test_learned = [row for row in effects if row["partition"] == "test" and row["method"] == pr59.METHODS[2]]
    report = {
        "schema_version": 1,
        "contract_sha256": plan["contract_sha256"],
        "gate_status": "passed",
        "source_contracts": plan["source_contracts"],
        "summary": {
            "training_epochs": len(history),
            "training_parents": 34,
            "validation_parents": 10,
            "graph_test_parents": 10,
            "solver_validation_parents": 6,
            "solver_test_parents": 6,
            "solver_method_runs": len(outcomes),
            "heldout_gnn_gap_wins_vs_control": sum(float(row["terminal_gap_difference_guided_minus_control"]) < 0 for row in test_learned),
            "heldout_gnn_mean_gap_difference_guided_minus_control": influence[0]["mean_gap_difference_guided_minus_control"],
            "heldout_gnn_median_gap_difference_guided_minus_control": influence[0]["median_gap_difference_guided_minus_control"],
            "predictive_roc_auc": evaluation["roc_auc"],
            "predictive_average_precision": evaluation["score_diagnostics"]["average_precision"],
        },
        "interpretation": {
            "heldout_generalization_evidence": "favorable_descriptive",
            "mean_effect_influence_sensitive": True,
            "right_censoring_retained": True,
            "confirmatory_significance_claim_allowed": False,
            "policy_reselection_after_test": False,
        },
        "eligibility": {
            "publication_artifacts_ready_for_development_review": True,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {"next_gate": "repository_documentation_and_manuscript_revision"},
        "outputs": {MANIFEST_NAME: _descriptor(output_dir, output_dir / MANIFEST_NAME)},
    }
    write_json(output_dir / REPORT_NAME, report)
    return report


def verify(output_dir: Path) -> dict[str, Any]:
    report = _read_json(output_dir / REPORT_NAME)
    manifest = _read_json(output_dir / MANIFEST_NAME)
    if (
        report.get("gate_status") != "passed"
        or report.get("contract_sha256") != manifest.get("contract_sha256")
        or report.get("eligibility", {}).get("development_only") is not True
        or report.get("eligibility", {}).get("scientific_reporting_eligible") is not False
        or report.get("interpretation", {}).get("confirmatory_significance_claim_allowed") is not False
        or set(manifest.get("artifacts", {})) != set((*TABLES, *FIGURES))
    ):
        raise ScientificEvidenceError("PR60 report or manifest gate failed")
    checked = 0
    for descriptor in manifest["artifacts"].values():
        _checked(output_dir, descriptor)
        checked += 1
    text_paths = [output_dir / REPORT_NAME, output_dir / MANIFEST_NAME, *(output_dir / name for name in (*TABLES, *FIGURES))]
    for path in text_paths:
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in UNSAFE_TOKENS):
            raise ScientificEvidenceError(f"sanitization failed in {path.name}")
    return {"artifacts_verified": checked, "text_artifacts_scanned": len(text_paths), "development_only": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "build", "verify"))
    parser.add_argument("--training_dir", type=Path)
    parser.add_argument("--validation_dir", type=Path)
    parser.add_argument("--heldout_dir", type=Path)
    parser.add_argument("--plan_dir", type=Path)
    parser.add_argument("--output_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            if None in (args.training_dir, args.validation_dir, args.heldout_dir, args.plan_dir):
                parser.error("plan requires all source directories and --plan_dir")
            plan = build_plan(args.training_dir, args.validation_dir, args.heldout_dir)
            args.plan_dir.mkdir(parents=True, exist_ok=False)
            write_json(args.plan_dir / PLAN_NAME, plan)
            print(f"[INFO] contract={plan['contract_sha256']} | solver_runs=0 | training_runs=0")
        elif args.command == "build":
            if None in (args.training_dir, args.validation_dir, args.heldout_dir, args.plan_dir, args.output_dir):
                parser.error("build requires all source, plan, and output directories")
            plan = _read_json(args.plan_dir / PLAN_NAME)
            report = generate(
                plan,
                {"training": args.training_dir.resolve(), "validation": args.validation_dir.resolve(), "heldout": args.heldout_dir.resolve()},
                args.output_dir,
            )
            print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
        else:
            if args.output_dir is None:
                parser.error("verify requires --output_dir")
            result = verify(args.output_dir)
            print(json.dumps(result, indent=2, sort_keys=True))
            print("PR60_REPORT_OK")
            print("PR60_OUTPUT_HASHES_OK")
            print("PR60_DECLARED_TEXT_SANITIZATION_OK")
        return 0
    except Exception as error:
        print(f"[ERROR] {type(error).__name__}: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
