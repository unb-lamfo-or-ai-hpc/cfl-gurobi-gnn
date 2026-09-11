"""Held-out evaluation for the manifest-driven Gasse baseline."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.training.gasse_reconnected import (
    GasseLabelViewDataset,
    GasseTrainingError,
    LEGACY_GASSE_GIT_BLOB_SHA1,
    canonical_sha256,
    classification_metrics,
    git_blob_sha1,
    read_json,
    validate_training_plan,
    write_json,
)


SCHEMA_VERSION = 1
EVALUATION_PLAN_NAME = "gasse_evaluation_plan.json"
EVALUATION_REPORT_NAME = "gasse_evaluation_report.json"
PER_PARENT_NAME = "per_parent_metrics.csv"
PER_DIFFICULTY_NAME = "per_difficulty_metrics.csv"
CALIBRATION_NAME = "calibration_curve.csv"
ROC_NAME = "roc_curve.csv"
PR_NAME = "precision_recall_curve.csv"


class GasseEvaluationError(RuntimeError):
    """Raised when held-out evaluation would violate the training contract."""


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise GasseEvaluationError(f"cannot write empty evaluation table: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_evaluation_plan(
    *,
    training_plan_path: str | Path,
    training_report_path: str | Path,
    checkpoint_path: str | Path,
) -> dict[str, Any]:
    """Bind a checkpoint to the untouched test partition and fixed threshold."""
    plan_path = Path(training_plan_path)
    report_path = Path(training_report_path)
    checkpoint = Path(checkpoint_path)
    training_plan = read_json(plan_path)
    validate_training_plan(training_plan)
    training_report = read_json(report_path)
    if not training_plan.get("training_ready"):
        raise GasseEvaluationError(
            "held-out evaluation requires train, validation, and test partitions"
        )
    if (
        training_report.get("gate_status") != "passed"
        or training_report.get("training_contract_sha256")
        != training_plan["contract_sha256"]
        or training_report.get("test_graphs_loaded") != 0
    ):
        raise GasseEvaluationError("training report violates the held-out contract")
    if training_report.get("threshold_source") != "maximum_validation_f1":
        raise GasseEvaluationError(
            "the decision threshold was not selected on validation"
        )
    checkpoint_descriptor = training_report.get("outputs", {}).get("checkpoint", {})
    if (
        not checkpoint.is_file()
        or sha256_file(checkpoint) != checkpoint_descriptor.get("sha256")
    ):
        raise GasseEvaluationError("checkpoint SHA-256 mismatch")
    threshold = float(training_report.get("selected_probability_threshold"))
    if not math.isfinite(threshold) or threshold < 0.0 or threshold > 1.0:
        raise GasseEvaluationError("invalid validation-selected threshold")
    test_records = [
        record for record in training_plan["records"] if record["role"] == "test"
    ]
    if not test_records:
        raise GasseEvaluationError("held-out test partition is empty")
    contract = {
        "schema_version": SCHEMA_VERSION,
        "training_contract_sha256": training_plan["contract_sha256"],
        "training_plan_sha256": sha256_file(plan_path),
        "training_report_sha256": sha256_file(report_path),
        "checkpoint_sha256": sha256_file(checkpoint),
        "legacy_gasse_git_blob_sha1": LEGACY_GASSE_GIT_BLOB_SHA1,
        "architecture": training_plan["protocol"]["architecture"],
        "probability_threshold": threshold,
        "threshold_source": "maximum_validation_f1",
        "test_partition_usage": "held_out_evaluation_only",
        "test_records": test_records,
        "diagnostics": {
            "aggregate_classification": True,
            "per_parent": True,
            "per_difficulty": True,
            "roc_auc": True,
            "precision_recall_auc": True,
            "calibration_bins": int(
                training_plan["protocol"]["evaluation"]["calibration_bins"]
            ),
        },
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "contract_valid": True,
        "next_gate": "held_out_gasse_evaluation_execution",
    }


def validate_evaluation_plan(plan: Mapping[str, Any]) -> None:
    payload = {
        key: value
        for key, value in plan.items()
        if key not in {"contract_sha256", "contract_valid", "next_gate"}
    }
    if canonical_sha256(payload) != plan.get("contract_sha256"):
        raise GasseEvaluationError("evaluation plan contract hash mismatch")


def confusion_counts(
    targets: Sequence[float], probabilities: Sequence[float], threshold: float
) -> tuple[int, int, int, int]:
    if len(targets) != len(probabilities):
        raise GasseEvaluationError("target and probability lengths differ")
    tp = tn = fp = fn = 0
    for target, probability in zip(targets, probabilities):
        truth = float(target) >= 0.5
        predicted = float(probability) >= threshold
        if truth and predicted:
            tp += 1
        elif not truth and not predicted:
            tn += 1
        elif predicted:
            fp += 1
        else:
            fn += 1
    return tp, tn, fp, fn


def binary_curve_rows(
    targets: Sequence[float], probabilities: Sequence[float]
) -> tuple[list[dict[str, float]], list[dict[str, float]], float | None, float | None]:
    """Return exact ROC and PR points plus trapezoidal AUC values."""
    import numpy as np

    truth = np.asarray(targets, dtype=np.float64) >= 0.5
    scores = np.asarray(probabilities, dtype=np.float64)
    if truth.size == 0 or truth.shape != scores.shape:
        raise GasseEvaluationError("empty or malformed prediction vectors")
    thresholds = np.concatenate(([np.inf], np.unique(scores)[::-1], [-np.inf]))
    positives = int(truth.sum())
    negatives = int((~truth).sum())
    roc_rows: list[dict[str, float]] = []
    pr_rows: list[dict[str, float]] = []
    for threshold in thresholds:
        predicted = scores >= threshold
        tp = int((predicted & truth).sum())
        fp = int((predicted & ~truth).sum())
        recall = tp / positives if positives else 0.0
        false_positive_rate = fp / negatives if negatives else 0.0
        precision = tp / (tp + fp) if tp + fp else 1.0
        serialized_threshold = (
            float(threshold)
            if np.isfinite(threshold)
            else (1.0 if threshold > 0 else 0.0)
        )
        roc_rows.append(
            {
                "threshold": serialized_threshold,
                "false_positive_rate": false_positive_rate,
                "true_positive_rate": recall,
            }
        )
        pr_rows.append(
            {
                "threshold": serialized_threshold,
                "recall": recall,
                "precision": precision,
            }
        )
    roc_auc = None
    if positives and negatives:
        roc_auc = float(
            np.trapz(
                [row["true_positive_rate"] for row in roc_rows],
                [row["false_positive_rate"] for row in roc_rows],
            )
        )
    pr_auc = None
    if positives:
        ordered = sorted(pr_rows, key=lambda row: row["recall"])
        pr_auc = float(
            np.trapz(
                [row["precision"] for row in ordered],
                [row["recall"] for row in ordered],
            )
        )
    return roc_rows, pr_rows, roc_auc, pr_auc


def calibration_rows(
    targets: Sequence[float], probabilities: Sequence[float], bins: int
) -> list[dict[str, Any]]:
    if bins <= 0:
        raise GasseEvaluationError("calibration bin count must be positive")
    grouped: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for target, probability in zip(targets, probabilities):
        score = min(1.0, max(0.0, float(probability)))
        index = min(bins - 1, int(score * bins))
        grouped[index].append((float(target), score))
    rows: list[dict[str, Any]] = []
    for index, values in enumerate(grouped):
        count = len(values)
        rows.append(
            {
                "bin_index": index,
                "lower_bound": index / bins,
                "upper_bound": (index + 1) / bins,
                "count": count,
                "mean_probability": (
                    sum(item[1] for item in values) / count if count else None
                ),
                "positive_fraction": (
                    sum(item[0] >= 0.5 for item in values) / count if count else None
                ),
            }
        )
    return rows


def _metric_row(
    key: str,
    value: str,
    targets: Sequence[float],
    probabilities: Sequence[float],
    threshold: float,
) -> dict[str, Any]:
    tp, tn, fp, fn = confusion_counts(targets, probabilities, threshold)
    return {
        key: value,
        "n_targets": len(targets),
        "n_positive": sum(float(target) >= 0.5 for target in targets),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        **classification_metrics(tp, tn, fp, fn),
    }


def execute_evaluation(
    plan: Mapping[str, Any],
    *,
    graph_root: str | Path,
    label_root: str | Path,
    checkpoint_path: str | Path,
    output_dir: str | Path,
    device_name: str = "auto",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Deserialize only test graphs and emit full held-out diagnostics."""
    validate_evaluation_plan(plan)
    import torch
    import torch.nn as nn
    from torch_geometric.loader import DataLoader

    from cfl_gnn.models.versioning import model_class
    from cfl_gnn.training.binary_contract import binary_targets

    output = Path(output_dir).resolve()
    report_path = output / EVALUATION_REPORT_NAME
    if report_path.exists() and not overwrite:
        raise GasseEvaluationError("evaluation output exists; use --overwrite")
    output.mkdir(parents=True, exist_ok=True)
    if device_name == "cuda" and not torch.cuda.is_available():
        raise GasseEvaluationError("CUDA was requested but is unavailable")
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device_name)
    records = list(plan["test_records"])
    dataset = GasseLabelViewDataset(
        records, graph_root=graph_root, label_root=label_root
    )
    first = dataset[0].to(device)
    edge = first["variable", "rev_coef", "constraint"]
    architecture = plan["architecture"]
    model = model_class(architecture.get("model_version", "legacy"))(
        var_in_dim=int(first["variable"].x.shape[-1]),
        cons_in_dim=int(first["constraint"].x.shape[-1]),
        edge_dim=int(edge.edge_attr.shape[-1]) if edge.edge_attr is not None else 0,
        hidden_dim=int(architecture["hidden_dim"]),
        num_layers=int(architecture["num_layers"]),
    ).to(device)
    state = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(
        {key.removeprefix("module."): value for key, value in state.items()}
    )
    model.eval()
    loss_fn = nn.BCEWithLogitsLoss(reduction="sum")
    all_targets: list[float] = []
    all_probabilities: list[float] = []
    per_parent_raw: dict[str, tuple[list[float], list[float]]] = {}
    baseline_scores = []
    prediction_outputs = {}
    total_loss = 0.0
    with torch.no_grad():
        loader = DataLoader(dataset, batch_size=1, shuffle=False)
        for record, graph in zip(records, loader):
            from time import perf_counter
            graph = graph.to(device)
            mask = graph["variable"].is_discrete.bool()
            graph_edge = graph["variable", "rev_coef", "constraint"]
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            inference_started = perf_counter()
            logits = model(
                x_var=graph["variable"].x,
                x_cons=graph["constraint"].x,
                edge_v2c=graph_edge.edge_index,
                binary_mask=mask,
                edge_attr=graph_edge.edge_attr,
            )
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            inference_seconds = perf_counter()-inference_started
            mask, targets = binary_targets(graph)
            probabilities = torch.sigmoid(logits)
            total_loss += float(loss_fn(logits, targets).item())
            local_targets = targets.cpu().tolist()
            local_probabilities = probabilities.cpu().tolist()
            all_targets.extend(local_targets)
            all_probabilities.extend(local_probabilities)
            baseline_scores.extend(graph["variable"].x[mask, 6].clamp(0, 1).cpu().tolist())
            # Export only model predictions, never target labels, for solver execution.
            import gzip
            names = graph.variable_names
            if len(names) == 1 and isinstance(names[0], list):
                names = names[0]  # PyG batch size one.
            indices = torch.where(mask)[0].cpu().tolist()
            prediction_name = f"predictions/{record['parent_instance_id']}.json.gz"
            prediction_path = output / prediction_name
            prediction_path.parent.mkdir(parents=True, exist_ok=True)
            prediction_payload = {
                "schema_version": 1, "role": "test", "sampling_strategy": "original",
                "source_instance_id": record["parent_instance_id"],
                "mip_sha256": record["mip_sha256"],
                "checkpoint_sha256": sha256_file(checkpoint_path),
                "model_inference_wall_time_seconds": inference_seconds,
                "root_graph_precomputation_included": False,
                "evaluation_contract_sha256": plan["contract_sha256"],
                "probability_threshold": float(plan["probability_threshold"]),
                "predictions": [{"variable_name": names[i], "predicted_value": int(p >= float(plan["probability_threshold"])),
                                 "probability": p, "confidence": abs(p-.5)*2,
                                 "priority": int(abs(p-.5)*200)} for i,p in zip(indices, local_probabilities)]}
            with prediction_path.open("wb") as raw:
                with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
                    stream.write(json.dumps(prediction_payload, allow_nan=False).encode("utf-8"))
            prediction_outputs[prediction_name] = {"sha256": sha256_file(prediction_path), "records": len(indices)}
            per_parent_raw[str(record["parent_instance_id"])] = (
                local_targets,
                local_probabilities,
            )
    threshold = float(plan["probability_threshold"])
    aggregate = _metric_row(
        "scope", "aggregate", all_targets, all_probabilities, threshold
    )
    aggregate["bce_per_target"] = total_loss / len(all_targets)
    per_parent = [
        _metric_row("parent_instance_id", parent, targets, probabilities, threshold)
        for parent, (targets, probabilities) in sorted(per_parent_raw.items())
    ]
    by_difficulty: dict[str, tuple[list[float], list[float]]] = defaultdict(
        lambda: ([], [])
    )
    difficulty_by_parent = {
        str(record["parent_instance_id"]): str(record["difficulty"])
        for record in records
    }
    for parent, (targets, probabilities) in per_parent_raw.items():
        target_bucket, probability_bucket = by_difficulty[difficulty_by_parent[parent]]
        target_bucket.extend(targets)
        probability_bucket.extend(probabilities)
    per_difficulty = [
        _metric_row("difficulty", difficulty, targets, probabilities, threshold)
        for difficulty, (targets, probabilities) in sorted(by_difficulty.items())
    ]
    roc_rows, pr_rows, roc_auc, pr_auc = binary_curve_rows(
        all_targets, all_probabilities
    )
    calibration = calibration_rows(
        all_targets,
        all_probabilities,
        int(plan["diagnostics"]["calibration_bins"]),
    )
    artifacts = {
        PER_PARENT_NAME: per_parent,
        PER_DIFFICULTY_NAME: per_difficulty,
        CALIBRATION_NAME: calibration,
        ROC_NAME: roc_rows,
        PR_NAME: pr_rows,
    }
    outputs: dict[str, Any] = dict(prediction_outputs)
    for name, rows in artifacts.items():
        path = output / name
        _write_csv(path, rows)
        outputs[name] = {"sha256": sha256_file(path), "records": len(rows)}
    from cfl_gnn.evaluation.binary_quality import score_quality
    parent_quality = [score_quality(y, p) for y, p in per_parent_raw.values()]
    report = {
        "model_version": architecture.get("model_version", "legacy"),
        "score_diagnostics": score_quality(all_targets, all_probabilities),
        "baseline_diagnostics": {
            "constant_zero": score_quality(all_targets, [0.] * len(all_targets)),
            "root_lp_clipped_to_binary_domain": score_quality(all_targets, baseline_scores),
        },
        "parent_macro_score_diagnostics": {
            key: (sum(value[key] for value in parent_quality if value[key] is not None)
                  / sum(value[key] is not None for value in parent_quality)
                  if any(value[key] is not None for value in parent_quality) else None)
            for key in ("average_precision", "brier_score", "expected_calibration_error", "binary_cross_entropy")
        },
        "parent_macro_classification": {
            key: sum(row[key] for row in per_parent) / len(per_parent)
            for key in ("accuracy", "precision", "recall", "f1_score")
        },
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan["contract_sha256"],
        "gate_status": "passed",
        "legacy_gasse_git_blob_sha1": git_blob_sha1(
            Path(__file__).resolve().parents[1] / "models" / "gasse.py"
        ),
        "probability_threshold": threshold,
        "threshold_source": plan["threshold_source"],
        "test_partition_usage": "held_out_evaluation_only",
        "test_graphs_loaded": len(records),
        "aggregate_metrics": aggregate,
        "roc_auc": roc_auc,
        "precision_recall_auc": pr_auc,
        "outputs": outputs,
        "eligibility": {
            "held_out_evaluation_complete": True,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {"next_gate": "native_neural_diving_guidance_reconnection"},
    }
    write_json(report_path, report)
    return report
