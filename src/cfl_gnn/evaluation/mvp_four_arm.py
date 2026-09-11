"""Common held-out evaluation and solver-neutral hints for the four MVP arms."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.training.mvp_arm import (
    MvpTrainingDataError,
    build_training_data_plan,
    write_json,
)
from cfl_gnn.training.mvp_four_arm import (
    ARM_SUMMARY_NAME,
    CHECKPOINT_NAME,
    EXPECTED_ARMS,
    RUN_PLAN_NAME as TRAINING_PLAN_NAME,
    RUN_REPORT_NAME as TRAINING_REPORT_NAME,
    MvpFourArmTrainingError,
    build_training_run_plan,
)


SCHEMA_VERSION = 1
PLAN_NAME = "mvp_four_arm_evaluation_plan.json"
REPORT_NAME = "mvp_four_arm_evaluation_report.json"
METRICS_NAME = "per_arm_test_metrics.csv"
DEFAULT_EXPERIMENT_CONFIG = (
    PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
)
DEFAULT_LOADER_POLICY = (
    PROJECT_ROOT / "configs" / "training" / "mvp_four_arm_loader_v1.json"
)
DEFAULT_TRAINING_PROTOCOL = (
    PROJECT_ROOT / "configs" / "training" / "mvp_four_arm_training_smoke_v1.json"
)
DEFAULT_EVALUATION_PROTOCOL = (
    PROJECT_ROOT / "configs" / "evaluation" / "mvp_four_arm_held_out_v1.json"
)


class MvpFourArmEvaluationError(RuntimeError):
    """Raised when held-out evaluation provenance or pairing fails closed."""


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path, *, artifact: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise MvpFourArmEvaluationError(f"unreadable {artifact}") from error
    if not isinstance(value, dict):
        raise MvpFourArmEvaluationError(f"{artifact} must be a JSON object")
    return value


def _safe_file(root: Path, relative_value: Any, *, artifact: str) -> Path:
    relative = Path(str(relative_value))
    resolved_root = root.resolve()
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise MvpFourArmEvaluationError(f"unsafe {artifact} path")
    resolved = (resolved_root / relative).resolve()
    if resolved_root not in resolved.parents or not resolved.is_file():
        raise MvpFourArmEvaluationError(f"missing or unsafe {artifact}")
    return resolved


def _required_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise MvpFourArmEvaluationError(f"{field} is not a SHA-256 digest")
    return value


def _reference_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    return _canonical_sha256(
        [
            {
                "sample_id": str(record["sample_id"]),
                "parent_instance_id": str(record["parent_instance_id"]),
                "graph_sha256": str(record["graph_sha256"]),
                "label_solution_sha256": str(record["label_solution_sha256"]),
            }
            for record in records
        ]
    )


@dataclass(frozen=True, slots=True)
class EvaluationProtocol:
    """Immutable threshold, hint, metric, and eligibility policy."""

    schema_version: int
    protocol_id: str
    probability_threshold: float | None
    threshold_source: str
    maximum_priority: int

    @property
    def contract_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "protocol_id": self.protocol_id,
            "experiment_stage": (
                "engineering_held_out_evaluation"
                if self.schema_version == 1
                else "development_four_arm_held_out_evaluation"
            ),
            "threshold_source": self.threshold_source,
            "hint_policy": {
                "solver_neutral": True,
                "include_all_discrete_variables": True,
                "maximum_priority": self.maximum_priority,
                "priority_formula": (
                    "floor_absolute_probability_distance_from_half_times_200"
                ),
            },
            "arm_selection_policy": (
                "all_four_arms_forwarded_without_test_selection"
            ),
            "metrics": {
                "secondary_gnn_diagnostics": [
                    "unweighted_bce_per_variable",
                    "f1_score",
                    "precision",
                    "recall",
                ],
                "research_primary_outcomes_reserved_for_solver_gate": [
                    "mip_gap_relative",
                    "execution_time_seconds",
                ],
            },
            "development_only": True,
            "scientific_reporting_eligible": False,
        }
        if self.schema_version == 1:
            payload["probability_threshold"] = self.probability_threshold
        return payload

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvaluationProtocol":
        schema_version = value.get("schema_version")
        if schema_version not in (1, 2):
            raise MvpFourArmEvaluationError("unsupported evaluation schema")
        try:
            maximum_priority = int(value.get("hint_policy", {}).get(
                "maximum_priority"
            ))
        except (TypeError, ValueError, OverflowError) as error:
            raise MvpFourArmEvaluationError(
                "invalid evaluation threshold or priority"
            ) from error
        threshold: float | None = None
        threshold_source = str(value.get("threshold_source", ""))
        if schema_version == 1:
            threshold = float(value.get("probability_threshold"))
        if maximum_priority != 100 or (
            schema_version == 1
            and (
                threshold != 0.5
                or threshold_source
                != "fixed_precommitted_not_test_calibrated"
            )
        ):
            raise MvpFourArmEvaluationError(
                "held-out threshold and priority scale are fixed"
            )
        if schema_version == 2 and threshold_source != (
            "per_arm_maximum_validation_f1_from_training_report"
        ):
            raise MvpFourArmEvaluationError(
                "evaluation thresholds must originate from validation"
            )
        protocol_id = value.get("protocol_id")
        if not isinstance(protocol_id, str) or not protocol_id:
            raise MvpFourArmEvaluationError("evaluation protocol id is missing")
        protocol = cls(
            int(schema_version),
            protocol_id,
            threshold,
            threshold_source,
            maximum_priority,
        )
        if dict(value) != protocol.contract_payload:
            raise MvpFourArmEvaluationError(
                "evaluation protocol is not the precommitted contract"
            )
        return protocol


def load_evaluation_protocol(path: str | Path) -> EvaluationProtocol:
    return EvaluationProtocol.from_mapping(
        _read_json(Path(path), artifact="evaluation protocol")
    )


def _verified_training_artifacts(
    training_root: Path,
    report: Mapping[str, Any],
    protocol: EvaluationProtocol,
) -> dict[str, dict[str, Any]]:
    report_arms = report.get("arms")
    if not isinstance(report_arms, Mapping) or set(report_arms) != set(EXPECTED_ARMS):
        raise MvpFourArmEvaluationError("training report does not contain four arms")
    result: dict[str, dict[str, Any]] = {}
    for arm_id in EXPECTED_ARMS:
        arm = report_arms[arm_id]
        if not isinstance(arm, Mapping) or arm.get("arm_id") != arm_id:
            raise MvpFourArmEvaluationError("malformed training arm report")
        arm_root = training_root / "arms" / arm_id
        checkpoint = _safe_file(
            arm_root,
            arm.get("checkpoint", {}).get("file_name"),
            artifact=f"{arm_id} checkpoint",
        )
        if checkpoint.name != CHECKPOINT_NAME:
            raise MvpFourArmEvaluationError("unexpected checkpoint file name")
        summary = _safe_file(
            arm_root, ARM_SUMMARY_NAME, artifact=f"{arm_id} summary"
        )
        checkpoint_sha256 = _required_sha256(
            arm.get("checkpoint", {}).get("sha256"),
            field=f"{arm_id} checkpoint sha256",
        )
        summary_sha256 = _required_sha256(
            arm.get("summary_sha256"), field=f"{arm_id} summary sha256"
        )
        if sha256_file(checkpoint) != checkpoint_sha256:
            raise MvpFourArmEvaluationError(f"{arm_id} checkpoint changed")
        if sha256_file(summary) != summary_sha256:
            raise MvpFourArmEvaluationError(f"{arm_id} summary changed")
        stored_summary = _read_json(summary, artifact=f"{arm_id} summary")
        if (
            stored_summary.get("arm_id") != arm_id
            or stored_summary.get("checkpoint", {}).get("sha256")
            != checkpoint_sha256
            or stored_summary.get("test_graphs_loaded") != 0
        ):
            raise MvpFourArmEvaluationError(
                f"{arm_id} summary disagrees with the training report"
            )
        if protocol.schema_version == 2:
            threshold = stored_summary.get("selected_probability_threshold")
            threshold_source = stored_summary.get("threshold_source")
            try:
                threshold = float(threshold)
            except (TypeError, ValueError, OverflowError) as error:
                raise MvpFourArmEvaluationError(
                    f"{arm_id} validation threshold is invalid"
                ) from error
            if (
                not 0.0 <= threshold <= 1.0
                or threshold_source != "maximum_validation_f1"
                or arm.get("selected_probability_threshold") != threshold
                or arm.get("threshold_source") != threshold_source
            ):
                raise MvpFourArmEvaluationError(
                    f"{arm_id} validation threshold provenance failed"
                )
        else:
            threshold = protocol.probability_threshold
            threshold_source = protocol.threshold_source
        result[arm_id] = {
            "solver": str(arm["solver"]),
            "checkpoint_relative_path": (
                Path("arms") / arm_id / checkpoint.name
            ).as_posix(),
            "checkpoint_sha256": checkpoint_sha256,
            "training_summary_sha256": summary_sha256,
            "probability_threshold": threshold,
            "threshold_source": threshold_source,
        }
    return result


def build_evaluation_plan(
    dataset_dir: str | Path,
    training_run_dir: str | Path,
    base_source_dir: str | Path,
    *,
    experiment_config_path: str | Path,
    loader_policy_path: str | Path,
    training_protocol_path: str | Path,
    evaluation_protocol_path: str | Path,
) -> dict[str, Any]:
    """Bind four checkpoints to one rebuilt, immutable held-out population."""
    dataset_root = Path(dataset_dir).resolve()
    training_root = Path(training_run_dir).resolve()
    source_root = Path(base_source_dir).resolve()
    stored_plan_path = training_root / TRAINING_PLAN_NAME
    stored_report_path = training_root / TRAINING_REPORT_NAME
    stored_plan = _read_json(stored_plan_path, artifact="training plan")
    training_report = _read_json(stored_report_path, artifact="training report")
    current_plan = build_training_run_plan(
        dataset_root,
        experiment_config_path=experiment_config_path,
        loader_policy_path=loader_policy_path,
        training_protocol_path=training_protocol_path,
    )
    if stored_plan.get("contract_sha256") != current_plan["contract_sha256"]:
        raise MvpFourArmEvaluationError("training plan no longer reproduces")
    controls = training_report.get("paired_controls")
    if (
        training_report.get("gate_status") != "passed"
        or training_report.get("training_run_contract_sha256")
        != current_plan["contract_sha256"]
        or not isinstance(controls, Mapping)
        or not controls
        or not all(value is True for value in controls.values())
        or training_report.get("eligibility", {}).get("development_only") is not True
        or training_report.get("eligibility", {}).get(
            "scientific_reporting_eligible"
        )
        is not False
    ):
        raise MvpFourArmEvaluationError("training gate is not admissible")
    protocol = load_evaluation_protocol(evaluation_protocol_path)
    checkpoints = _verified_training_artifacts(
        training_root, training_report, protocol
    )
    data_plan = build_training_data_plan(
        dataset_root,
        experiment_config_path=experiment_config_path,
        loader_policy_path=loader_policy_path,
        verify_graph_hashes=True,
    )
    if data_plan.get("contract_sha256") != current_plan.get(
        "training_data_contract_sha256"
    ):
        raise MvpFourArmEvaluationError("training-data contract changed")
    test_records = data_plan.get("common_reference_partitions", {}).get("test")
    if not isinstance(test_records, list) or not test_records:
        raise MvpFourArmEvaluationError("held-out test reference is missing")
    held_out = current_plan.get("held_out_test_contract", {})
    if (
        held_out.get("record_count") != len(test_records)
        or held_out.get("parent_instance_ids")
        != sorted(str(record["parent_instance_id"]) for record in test_records)
        or held_out.get("graph_sha256")
        != sorted(str(record["graph_sha256"]) for record in test_records)
    ):
        raise MvpFourArmEvaluationError("held-out population changed after training")
    planned_test: list[dict[str, Any]] = []
    for record in test_records:
        sample_id = str(record["sample_id"])
        solver = str(record["selected_solver"])
        provenance_relative = (
            Path("provenance")
            / "original"
            / solver
            / f"{sample_id}.provenance.json"
        )
        provenance_path = _safe_file(
            dataset_root, provenance_relative, artifact="test provenance"
        )
        provenance = _read_json(provenance_path, artifact="test provenance")
        candidate_relative = (
            Path(str(record["category"]))
            / "LP"
            / f"{record['parent_instance_id']}.lp.gz"
        )
        candidate = _safe_file(
            source_root, candidate_relative, artifact="test parent MIP"
        )
        parent_sha256 = _required_sha256(
            provenance.get("parent_mip_sha256"), field="parent MIP sha256"
        )
        provenance_sample = provenance.get("sample", {})
        graph_audit = provenance.get("graph_audit", {})
        if (
            not isinstance(provenance_sample, Mapping)
            or provenance_sample.get("sample_id") != sample_id
            or provenance_sample.get("parent_instance_id")
            != record["parent_instance_id"]
            or provenance_sample.get("graph_sha256") != record["graph_sha256"]
            or provenance_sample.get("label_solution_sha256")
            != record["label_solution_sha256"]
            or not isinstance(graph_audit, Mapping)
            or graph_audit.get("roundtrip_readable") is not True
            or graph_audit.get("label_variable_identity_match") is not True
            or provenance.get("eligibility", {}).get("dataset_eligible") is not True
            or sha256_file(candidate) != parent_sha256
        ):
            raise MvpFourArmEvaluationError("test graph/source provenance mismatch")
        planned_test.append(
            {
                **dict(record),
                "parent_mip_relative_path": candidate_relative.as_posix(),
                "parent_mip_sha256": parent_sha256,
                "provenance_relative_path": provenance_relative.as_posix(),
                "graph_generation_contract_sha256": _required_sha256(
                    provenance.get("graph_generation_contract_sha256"),
                    field="graph generation contract sha256",
                ),
            }
        )
    contract = {
        "schema_version": SCHEMA_VERSION,
        "experiment_stage": "mvp_four_arm_common_held_out_evaluation",
        "dataset_contract_sha256": current_plan["dataset_contract_sha256"],
        "training_data_contract_sha256": current_plan[
            "training_data_contract_sha256"
        ],
        "training_run_contract_sha256": current_plan["contract_sha256"],
        "training_protocol_sha256": current_plan["training_protocol_sha256"],
        "training_plan_sha256": sha256_file(stored_plan_path),
        "training_report_sha256": sha256_file(stored_report_path),
        "model": dict(current_plan["training_protocol"]["model"]),
        "evaluation_protocol": protocol.contract_payload,
        "evaluation_protocol_sha256": protocol.contract_sha256,
        "arms": checkpoints,
        "test_records": planned_test,
        "test_reference_sha256": _reference_sha256(test_records),
        "test_access_policy": "held_out_evaluation_only",
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **contract,
        "contract_sha256": _canonical_sha256(contract),
        "contract_valid": True,
        "arm_selection_performed": False,
        "all_four_arms_forwarded": True,
        "next_gate": "four_arm_held_out_evaluation_execution",
    }


def classification_metrics(tp: int, tn: int, fp: int, fn: int) -> dict[str, float]:
    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
    }


def _write_hint_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    forbidden = {"target", "label", "ground_truth"}
    if not rows or any(forbidden.intersection(row) for row in rows):
        raise MvpFourArmEvaluationError("hint artifact is empty or contains labels")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    semantic_sha256 = _canonical_sha256(list(rows))
    with temporary.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="\n") as text:
                for row in rows:
                    text.write(json.dumps(row, sort_keys=True) + "\n")
    temporary.replace(path)
    return {
        "file_name": path.name,
        "sha256": sha256_file(path),
        "semantic_sha256": semantic_sha256,
        "hints": len(rows),
        "contains_test_labels": False,
    }


def _variable_names(candidate_path: Path) -> list[str]:
    from pyscipopt import Model

    model = Model()
    try:
        model.hideOutput(True)
        model.readProblem(str(candidate_path))
        return sorted(
            str(variable.name) for variable in model.getVars(transformed=False)
        )
    finally:
        model.freeProb()


def _select_device(torch_module: Any, requested: str) -> Any:
    if requested == "cuda" and not torch_module.cuda.is_available():
        raise MvpFourArmEvaluationError("CUDA was requested but is unavailable")
    if requested == "auto":
        requested = "cuda" if torch_module.cuda.is_available() else "cpu"
    return torch_module.device(requested)


def _production_arm_evaluator(
    *,
    arm_id: str,
    arm: Mapping[str, Any],
    plan: Mapping[str, Any],
    dataset_root: Path,
    training_root: Path,
    source_root: Path,
    output_dir: Path,
    device_name: str,
    clear_cache: bool,
) -> dict[str, Any]:
    import torch
    import torch.nn.functional as functional

    from cfl_gnn.graph.mvp_arm_dataset import MvpArmDataset
    from cfl_gnn.models.gasse import GasseGNN

    device = _select_device(torch, device_name)
    protocol = plan["evaluation_protocol"]
    threshold = float(arm["probability_threshold"])
    maximum_priority = int(protocol["hint_policy"]["maximum_priority"])
    checkpoint = _safe_file(
        training_root, arm["checkpoint_relative_path"], artifact="checkpoint"
    )
    state_dict = torch.load(checkpoint, map_location=device, weights_only=True)
    rows: list[dict[str, Any]] = []
    hint_artifacts: list[dict[str, Any]] = []
    totals = {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "targets": 0, "loss": 0.0}
    model = None
    for record in plan["test_records"]:
        graph = MvpArmDataset(
            dataset_root, [record], verify_hash_on_load=True
        )[0].to(device)
        names = _variable_names(
            _safe_file(
                source_root,
                record["parent_mip_relative_path"],
                artifact="test parent MIP",
            )
        )
        if len(names) != int(graph["variable"].x.shape[0]):
            raise MvpFourArmEvaluationError("graph/source variable count mismatch")
        edge_store = graph["variable", "rev_coef", "constraint"]
        if model is None:
            edge_attr = edge_store.edge_attr
            edge_dim = int(edge_attr.shape[-1]) if edge_attr is not None else 0
            model = GasseGNN(
                var_in_dim=int(graph["variable"].x.shape[-1]),
                cons_in_dim=int(graph["constraint"].x.shape[-1]),
                edge_dim=edge_dim,
                hidden_dim=int(plan["model"]["hidden_dim"]),
                num_layers=int(plan["model"]["num_layers"]),
            ).to(device)
            model.load_state_dict(state_dict)
            model.eval()
        mask = graph["variable"].is_discrete.bool()
        if int(mask.sum().item()) == 0:
            raise MvpFourArmEvaluationError("test graph has no discrete variables")
        with torch.no_grad():
            logits = model(
                x_var=graph["variable"].x,
                x_cons=graph["constraint"].x,
                edge_v2c=edge_store.edge_index,
                binary_mask=mask,
                edge_attr=edge_store.edge_attr,
            )
            targets = torch.clamp(graph["variable"].y[mask], 0.0, 1.0)
            probabilities = torch.sigmoid(logits)
            predictions = probabilities >= threshold
            positives = targets >= 0.5
            loss_sum = float(
                functional.binary_cross_entropy_with_logits(
                    logits, targets, reduction="sum"
                ).item()
            )
        tp = int((predictions & positives).sum().item())
        tn = int((~predictions & ~positives).sum().item())
        fp = int((predictions & ~positives).sum().item())
        fn = int((~predictions & positives).sum().item())
        target_indices = torch.where(mask)[0].detach().cpu().tolist()
        probability_values = probabilities.detach().cpu().tolist()
        hint_rows: list[dict[str, Any]] = []
        for index, probability in zip(target_indices, probability_values):
            normalized = float(probability)
            if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
                raise MvpFourArmEvaluationError("non-finite model probability")
            hint_rows.append(
                {
                    "variable_name": names[index],
                    "predicted_value": int(normalized >= threshold),
                    "probability": normalized,
                    "confidence": abs(normalized - 0.5) * 2.0,
                    "priority": int(
                        abs(normalized - 0.5) * 2.0 * maximum_priority
                    ),
                }
            )
        hint_path = output_dir / "hints" / f"{record['parent_instance_id']}.jsonl.gz"
        hint = _write_hint_rows(hint_path, hint_rows)
        hint_artifacts.append(
            {
                "parent_instance_id": record["parent_instance_id"],
                "relative_path": (
                    Path("arms") / arm_id / "hints" / hint_path.name
                ).as_posix(),
                **hint,
            }
        )
        n_targets = int(targets.numel())
        metric = {
            "parent_instance_id": record["parent_instance_id"],
            "difficulty": record["difficulty"],
            "fold": record["fold"],
            "n_targets": n_targets,
            "n_positive": int(positives.sum().item()),
            "unweighted_bce_per_variable": loss_sum / n_targets,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            **classification_metrics(tp, tn, fp, fn),
        }
        rows.append(metric)
        for key, value in (("tp", tp), ("tn", tn), ("fp", fp), ("fn", fn)):
            totals[key] += value
        totals["targets"] += n_targets
        totals["loss"] += loss_sum
        if clear_cache:
            del graph, logits, targets, probabilities
            torch.cuda.empty_cache()
    aggregate = {
        "n_test_parents": len(rows),
        "n_targets": totals["targets"],
        "unweighted_bce_per_variable": totals["loss"] / totals["targets"],
        "confusion": {key: totals[key] for key in ("tp", "tn", "fp", "fn")},
        **classification_metrics(
            int(totals["tp"]),
            int(totals["tn"]),
            int(totals["fp"]),
            int(totals["fn"]),
        ),
    }
    return {
        "arm_id": arm_id,
        "solver": arm["solver"],
        "checkpoint_sha256": arm["checkpoint_sha256"],
        "device_effective": str(device),
        "probability_threshold": threshold,
        "threshold_source": arm["threshold_source"],
        "test_reference_sha256": plan["test_reference_sha256"],
        "test_graphs_loaded": len(rows),
        "metrics_by_parent": rows,
        "aggregate_metrics": aggregate,
        "hint_artifacts": hint_artifacts,
        "hint_policy": protocol["hint_policy"],
        "test_labels_in_hint_artifacts": False,
    }


ArmEvaluator = Callable[..., dict[str, Any]]


def _validate_hint_artifacts(
    output_root: Path,
    arm_id: str,
    artifacts: Any,
) -> None:
    if not isinstance(artifacts, list) or not artifacts:
        raise MvpFourArmEvaluationError(f"missing hint artifacts: {arm_id}")
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise MvpFourArmEvaluationError("malformed hint artifact record")
        relative = str(artifact.get("relative_path", ""))
        expected_prefix = f"arms/{arm_id}/hints/"
        if not relative.startswith(expected_prefix):
            raise MvpFourArmEvaluationError("hint artifact has a foreign path")
        path = _safe_file(output_root, relative, artifact="hint artifact")
        expected_sha256 = _required_sha256(
            artifact.get("sha256"), field="hint artifact sha256"
        )
        _required_sha256(
            artifact.get("semantic_sha256"), field="hint semantic sha256"
        )
        if (
            sha256_file(path) != expected_sha256
            or artifact.get("contains_test_labels") is not False
            or not isinstance(artifact.get("hints"), int)
            or artifact["hints"] <= 0
        ):
            raise MvpFourArmEvaluationError("hint artifact audit failed")


def run_evaluation(
    plan: Mapping[str, Any],
    *,
    dataset_dir: str | Path,
    training_run_dir: str | Path,
    base_source_dir: str | Path,
    output_dir: str | Path,
    device: str = "auto",
    clear_cache: bool = False,
    overwrite: bool = False,
    arm_evaluator: ArmEvaluator = _production_arm_evaluator,
) -> dict[str, Any]:
    if plan.get("contract_valid") is not True:
        raise MvpFourArmEvaluationError("evaluation plan is not executable")
    output = Path(output_dir).resolve()
    report_path = output / REPORT_NAME
    if report_path.exists() and not overwrite:
        raise FileExistsError("evaluation output exists; use --overwrite")
    results: list[dict[str, Any]] = []
    for arm_id in EXPECTED_ARMS:
        result = arm_evaluator(
            arm_id=arm_id,
            arm=plan["arms"][arm_id],
            plan=plan,
            dataset_root=Path(dataset_dir).resolve(),
            training_root=Path(training_run_dir).resolve(),
            source_root=Path(base_source_dir).resolve(),
            output_dir=output / "arms" / arm_id,
            device_name=device,
            clear_cache=clear_cache,
        )
        if (
            result.get("arm_id") != arm_id
            or result.get("solver") != plan["arms"][arm_id]["solver"]
            or result.get("checkpoint_sha256")
            != plan["arms"][arm_id]["checkpoint_sha256"]
            or result.get("test_reference_sha256")
            != plan["test_reference_sha256"]
            or result.get("test_graphs_loaded") != len(plan["test_records"])
            or result.get("probability_threshold")
            != plan["arms"][arm_id]["probability_threshold"]
            or result.get("threshold_source")
            != plan["arms"][arm_id]["threshold_source"]
            or result.get("test_labels_in_hint_artifacts") is not False
        ):
            raise MvpFourArmEvaluationError(f"evaluation audit failed: {arm_id}")
        _validate_hint_artifacts(output, arm_id, result.get("hint_artifacts"))
        results.append(result)
    common_controls = {
        "same_test_reference_all_arms": len(
            {item["test_reference_sha256"] for item in results}
        )
        == 1,
        "threshold_contract_valid_all_arms": all(
            item["probability_threshold"]
            == plan["arms"][item["arm_id"]]["probability_threshold"]
            and item["threshold_source"]
            == plan["arms"][item["arm_id"]]["threshold_source"]
            for item in results
        ),
        "same_effective_device_all_arms": len(
            {item["device_effective"] for item in results}
        )
        == 1,
        "all_test_graphs_loaded_exactly_once_per_arm": all(
            item["test_graphs_loaded"] == len(plan["test_records"])
            for item in results
        ),
        "all_hint_artifacts_exclude_test_labels": all(
            item["test_labels_in_hint_artifacts"] is False for item in results
        ),
        "all_discrete_variables_forwarded_as_hints": all(
            sum(hint["hints"] for hint in item["hint_artifacts"])
            == item["aggregate_metrics"]["n_targets"]
            for item in results
        ),
    }
    if not all(common_controls.values()):
        raise MvpFourArmEvaluationError("common held-out controls failed")
    result_by_arm = {item["arm_id"]: item for item in results}
    paired_deltas: dict[str, Any] = {}
    for solver in ("gurobi", "scip"):
        original = result_by_arm[f"{solver}_original"]["aggregate_metrics"]
        augmented = result_by_arm[f"{solver}_incumbent_augmented"][
            "aggregate_metrics"
        ]
        paired_deltas[solver] = {
            "augmented_minus_original": {
                metric: augmented[metric] - original[metric]
                for metric in (
                    "unweighted_bce_per_variable",
                    "f1_score",
                    "precision",
                    "recall",
                )
            },
            "interpretation": "descriptive_engineering_diagnostic_only",
        }
    output.mkdir(parents=True, exist_ok=True)
    with (output / METRICS_NAME).open("w", encoding="utf-8", newline="") as stream:
        metric_rows = [
            {"arm_id": item["arm_id"], **item["aggregate_metrics"]}
            for item in results
        ]
        fieldnames = [
            "arm_id",
            "n_test_parents",
            "n_targets",
            "unweighted_bce_per_variable",
            "accuracy",
            "precision",
            "recall",
            "f1_score",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(metric_rows)
    report = {
        "schema_version": SCHEMA_VERSION,
        "evaluation_contract_sha256": plan["contract_sha256"],
        "training_run_contract_sha256": plan["training_run_contract_sha256"],
        "evaluation_protocol_sha256": plan["evaluation_protocol_sha256"],
        "probe_completed": True,
        "gate_status": "passed",
        "experiment_stage": "engineering_held_out_evaluation",
        "execution": {
            "arms_planned": 4,
            "arms_completed": len(results),
            "device_request": device,
        },
        "common_controls": common_controls,
        "test_contract": {
            "record_count": len(plan["test_records"]),
            "reference_sha256": plan["test_reference_sha256"],
            "access_policy": "held_out_evaluation_only",
        },
        "arms": result_by_arm,
        "paired_deltas": paired_deltas,
        "arm_selection": {
            "performed": False,
            "policy": "all_four_arms_forwarded_without_test_selection",
            "forwarded_arms": list(EXPECTED_ARMS),
        },
        "threshold_selection": {
            "source": plan["evaluation_protocol"]["threshold_source"],
            "test_labels_used": False,
            "per_arm_thresholds": {
                item["arm_id"]: item["probability_threshold"]
                for item in results
            },
        },
        "primary_research_metrics": [
            "mip_gap_relative",
            "execution_time_seconds",
        ],
        "outputs": {
            "per_arm_metrics": METRICS_NAME,
            "per_arm_metrics_sha256": sha256_file(output / METRICS_NAME),
        },
        "eligibility": {
            "held_out_evaluation_eligible": True,
            "solver_neutral_hints_eligible_for_engineering_smoke": True,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": "four_arm_common_held_out_evaluation_completed",
            "next_gate": "equal_budget_gurobi_scip_neural_diving_smoke",
        },
    }
    write_json(report_path, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate all four MVP checkpoints on one held-out reference."
    )
    parser.add_argument("--dataset_dir", type=Path, required=True)
    parser.add_argument("--training_run_dir", type=Path, required=True)
    parser.add_argument("--base_source_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument(
        "--experiment_config", type=Path, default=DEFAULT_EXPERIMENT_CONFIG
    )
    parser.add_argument("--loader_policy", type=Path, default=DEFAULT_LOADER_POLICY)
    parser.add_argument(
        "--training_protocol", type=Path, default=DEFAULT_TRAINING_PROTOCOL
    )
    parser.add_argument(
        "--evaluation_protocol", type=Path, default=DEFAULT_EVALUATION_PROTOCOL
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--clear_cache", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = build_evaluation_plan(
            args.dataset_dir,
            args.training_run_dir,
            args.base_source_dir,
            experiment_config_path=args.experiment_config,
            loader_policy_path=args.loader_policy,
            training_protocol_path=args.training_protocol,
            evaluation_protocol_path=args.evaluation_protocol,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / PLAN_NAME, plan)
        print(
            f"[INFO] contract={plan['contract_sha256']} | arms=4 | "
            f"test={len(plan['test_records'])} | "
            f"threshold_source={plan['evaluation_protocol']['threshold_source']}"
        )
        print("[INFO] no threshold calibration or arm selection uses test labels")
        print(f"[INFO] Plan: {args.output_dir / PLAN_NAME}")
        if args.dry_run:
            return 0
        report = run_evaluation(
            plan,
            dataset_dir=args.dataset_dir,
            training_run_dir=args.training_run_dir,
            base_source_dir=args.base_source_dir,
            output_dir=args.output_dir,
            device=args.device,
            clear_cache=args.clear_cache,
            overwrite=args.overwrite,
        )
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"completed={report['execution']['arms_completed']}/4"
        )
        print(f"[INFO] Report: {args.output_dir / REPORT_NAME}")
        return 0
    except (
        FileExistsError,
        OSError,
        TypeError,
        ValueError,
        MvpTrainingDataError,
        MvpFourArmTrainingError,
        MvpFourArmEvaluationError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

