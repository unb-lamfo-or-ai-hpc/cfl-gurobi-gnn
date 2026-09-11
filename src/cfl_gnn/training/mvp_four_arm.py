"""Paired serial training for the four development-only MVP arms."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.training.gasse_reconnected import git_blob_sha1
from cfl_gnn.training.mvp_arm import (
    DeterministicParentBalancedSampler,
    MvpTrainingDataError,
    build_training_data_plan,
    write_json,
)


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1
RUN_PLAN_NAME = "mvp_four_arm_training_plan.json"
RUN_REPORT_NAME = "mvp_four_arm_training_report.json"
ARM_SUMMARY_NAME = "arm_training_summary.json"
HISTORY_NAME = "training_history.csv"
CHECKPOINT_NAME = "best_model.pt"
EXPECTED_ARMS = (
    "gurobi_original",
    "gurobi_incumbent_augmented",
    "scip_original",
    "scip_incumbent_augmented",
)


class MvpFourArmTrainingError(RuntimeError):
    """Raised when the paired four-arm training contract fails closed."""


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _reference_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    """Fingerprint a reference population without retaining filesystem paths."""
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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise MvpFourArmTrainingError(
            f"unreadable JSON artifact: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise MvpFourArmTrainingError(f"expected JSON object: {path.name}")
    return value


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise MvpFourArmTrainingError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise MvpFourArmTrainingError(
            f"{field} must be a positive integer"
        ) from error
    if normalized <= 0 or normalized != value:
        raise MvpFourArmTrainingError(f"{field} must be a positive integer")
    return normalized


def _finite_positive(value: Any, *, field: str, allow_zero: bool = False) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise MvpFourArmTrainingError(f"{field} must be numeric") from error
    lower_bound_valid = normalized >= 0.0 if allow_zero else normalized > 0.0
    if not math.isfinite(normalized) or not lower_bound_valid:
        qualifier = "nonnegative" if allow_zero else "positive"
        raise MvpFourArmTrainingError(f"{field} must be finite and {qualifier}")
    return normalized


@dataclass(frozen=True, slots=True)
class TrainingProtocol:
    """Versioned hyperparameters and nuisance-variable controls."""

    schema_version: int
    protocol_id: str
    experiment_stage: str
    hidden_dim: int
    num_layers: int
    learning_rate: float
    gradient_clip: float
    epochs: int
    patience: int
    seed: int
    num_workers: int
    probability_threshold: float | None
    checkpoint_selection_metric: str
    threshold_selection_method: str
    legacy_gasse_git_blob_sha1: str | None

    @property
    def contract_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "protocol_id": self.protocol_id,
            "experiment_stage": self.experiment_stage,
            "arms": list(EXPECTED_ARMS),
            "model": {
                "model_class": "GasseGNN",
                "hidden_dim": self.hidden_dim,
                "num_layers": self.num_layers,
            },
            "optimization": {
                "batch_size": 1,
                "learning_rate": self.learning_rate,
                "gradient_clip": self.gradient_clip,
                "epochs": self.epochs,
                "patience": self.patience,
                "seed": self.seed,
                "num_workers": self.num_workers,
            },
            "comparison_controls": {
                "independent_model_per_arm": True,
                "initialization_seed_restarted_per_arm": True,
                "equal_optimizer_steps_per_epoch": True,
                "prenorm_policy": (
                    "solver_original_reference_reused_within_solver_pair"
                ),
                "pos_weight_policy": (
                    "solver_original_training_labels_reused_within_solver_pair"
                ),
                "validation_policy": "common_reference_shared_across_all_arms",
                "test_access_policy": "held_out_not_loaded_during_training",
            },
            "development_only": True,
            "scientific_reporting_eligible": False,
        }
        if self.schema_version == 1:
            payload["optimization"]["probability_threshold"] = (
                self.probability_threshold
            )
        else:
            payload["model"]["legacy_gasse_git_blob_sha1"] = (
                self.legacy_gasse_git_blob_sha1
            )
            payload["checkpoint_selection"] = {
                "metric": self.checkpoint_selection_metric,
                "mode": "minimum",
                "test_partition_access": "held_out_evaluation_only",
            }
            payload["threshold_selection"] = {
                "method": self.threshold_selection_method,
                "population": "common_validation_only",
                "tie_break": "closest_to_0.5_then_lower",
                "test_partition_access": "held_out_evaluation_only",
            }
            payload["comparison_controls"]["threshold_selection_policy"] = (
                "per_arm_common_validation_only"
            )
        return payload

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TrainingProtocol":
        schema_version = value.get("schema_version")
        if schema_version not in (1, 2):
            raise MvpFourArmTrainingError("unsupported training protocol schema")
        if value.get("arms") != list(EXPECTED_ARMS):
            raise MvpFourArmTrainingError("training protocol requires four fixed arms")
        expected_stage = (
            "engineering_smoke"
            if schema_version == 1
            else "development_four_arm_training"
        )
        if value.get("experiment_stage") != expected_stage:
            raise MvpFourArmTrainingError("unsupported four-arm experiment stage")
        if value.get("development_only") is not True or value.get(
            "scientific_reporting_eligible"
        ) is not False:
            raise MvpFourArmTrainingError(
                "four-arm smoke must remain development-only"
            )
        model = value.get("model")
        optimization = value.get("optimization")
        controls = value.get("comparison_controls")
        if not isinstance(model, Mapping) or model.get("model_class") != "GasseGNN":
            raise MvpFourArmTrainingError("unsupported four-arm model")
        if not isinstance(optimization, Mapping) or not isinstance(
            controls, Mapping
        ):
            raise MvpFourArmTrainingError("training protocol sections are missing")
        expected_controls = {
            "independent_model_per_arm": True,
            "initialization_seed_restarted_per_arm": True,
            "equal_optimizer_steps_per_epoch": True,
            "prenorm_policy": (
                "solver_original_reference_reused_within_solver_pair"
            ),
            "pos_weight_policy": (
                "solver_original_training_labels_reused_within_solver_pair"
            ),
            "validation_policy": "common_reference_shared_across_all_arms",
            "test_access_policy": "held_out_not_loaded_during_training",
        }
        if schema_version == 2:
            expected_controls["threshold_selection_policy"] = (
                "per_arm_common_validation_only"
            )
        if dict(controls) != expected_controls:
            raise MvpFourArmTrainingError("comparison controls are not precommitted")
        if optimization.get("batch_size") != 1:
            raise MvpFourArmTrainingError("four-arm training requires batch size one")
        raw_seed = optimization.get("seed")
        raw_workers = optimization.get("num_workers")
        if isinstance(raw_seed, bool) or not isinstance(raw_seed, int):
            raise MvpFourArmTrainingError("seed must be an integer")
        if isinstance(raw_workers, bool) or not isinstance(raw_workers, int):
            raise MvpFourArmTrainingError("num_workers must be an integer")
        if raw_workers < 0:
            raise MvpFourArmTrainingError("num_workers must be nonnegative")
        threshold: float | None = None
        checkpoint_metric = "validation_weighted_bce"
        threshold_method = "fixed_precommitted"
        legacy_gasse_git_blob_sha1: str | None = None
        if schema_version == 1:
            threshold = _finite_positive(
                optimization.get("probability_threshold"),
                field="probability_threshold",
                allow_zero=True,
            )
            if threshold != 0.5:
                raise MvpFourArmTrainingError(
                    "the engineering smoke uses the fixed logit threshold 0.5"
                )
        else:
            legacy_gasse_git_blob_sha1 = model.get(
                "legacy_gasse_git_blob_sha1"
            )
            if legacy_gasse_git_blob_sha1 != (
                "e2937ebcca149f8a99ec437c3c8e7fd31e49438b"
            ):
                raise MvpFourArmTrainingError(
                    "training protocol does not pin the preserved Gasse model"
                )
            checkpoint = value.get("checkpoint_selection")
            threshold_selection = value.get("threshold_selection")
            if checkpoint != {
                "metric": "validation_weighted_bce",
                "mode": "minimum",
                "test_partition_access": "held_out_evaluation_only",
            }:
                raise MvpFourArmTrainingError(
                    "checkpoint selection must use validation weighted BCE"
                )
            expected_threshold = {
                "method": "maximum_validation_f1",
                "population": "common_validation_only",
                "tie_break": "closest_to_0.5_then_lower",
                "test_partition_access": "held_out_evaluation_only",
            }
            if threshold_selection != expected_threshold:
                raise MvpFourArmTrainingError(
                    "threshold selection must use only common validation labels"
                )
            threshold_method = "maximum_validation_f1"
        protocol_id = value.get("protocol_id")
        if not isinstance(protocol_id, str) or not protocol_id.strip():
            raise MvpFourArmTrainingError("protocol_id must be a non-empty string")
        epochs = _positive_int(optimization.get("epochs"), field="epochs")
        patience = _positive_int(optimization.get("patience"), field="patience")
        if patience < epochs:
            raise MvpFourArmTrainingError(
                "patience must cover all epochs to preserve the paired step budget"
            )
        return cls(
            schema_version=int(schema_version),
            protocol_id=protocol_id.strip(),
            experiment_stage=expected_stage,
            hidden_dim=_positive_int(model.get("hidden_dim"), field="hidden_dim"),
            num_layers=_positive_int(model.get("num_layers"), field="num_layers"),
            learning_rate=_finite_positive(
                optimization.get("learning_rate"), field="learning_rate"
            ),
            gradient_clip=_finite_positive(
                optimization.get("gradient_clip"),
                field="gradient_clip",
                allow_zero=True,
            ),
            epochs=epochs,
            patience=patience,
            seed=raw_seed,
            num_workers=raw_workers,
            probability_threshold=threshold,
            checkpoint_selection_metric=checkpoint_metric,
            threshold_selection_method=threshold_method,
            legacy_gasse_git_blob_sha1=legacy_gasse_git_blob_sha1,
        )


def load_training_protocol(path: str | Path) -> TrainingProtocol:
    """Read and validate the immutable four-arm smoke protocol."""
    return TrainingProtocol.from_mapping(_read_json(Path(path)))


def build_training_run_plan(
    dataset_dir: str | Path,
    *,
    experiment_config_path: str | Path,
    loader_policy_path: str | Path,
    training_protocol_path: str | Path,
) -> dict[str, Any]:
    """Compose the loader and training contracts without importing PyTorch."""
    data_plan = build_training_data_plan(
        dataset_dir,
        experiment_config_path=experiment_config_path,
        loader_policy_path=loader_policy_path,
        verify_graph_hashes=True,
    )
    protocol = load_training_protocol(training_protocol_path)
    current_gasse_blob = git_blob_sha1(
        PROJECT_ROOT / "src" / "cfl_gnn" / "models" / "gasse.py"
    )
    if (
        protocol.schema_version == 2
        and current_gasse_blob != protocol.legacy_gasse_git_blob_sha1
    ):
        raise MvpFourArmTrainingError("preserved Gasse model implementation changed")
    if not data_plan.get("mvp_execution_ready"):
        raise MvpFourArmTrainingError("four-arm dataset is not execution-ready")
    arms = data_plan.get("arms")
    if not isinstance(arms, Mapping) or tuple(sorted(arms)) != tuple(
        sorted(EXPECTED_ARMS)
    ):
        raise MvpFourArmTrainingError("loader plan does not expose four arms")
    draws = {int(arms[arm]["draws_per_epoch"]) for arm in EXPECTED_ARMS}
    if len(draws) != 1 or next(iter(draws)) <= 0:
        raise MvpFourArmTrainingError("optimizer-step budget differs across arms")
    validation = data_plan.get("common_reference_partitions", {}).get(
        "validation"
    )
    held_out = data_plan.get("common_reference_partitions", {}).get("test")
    if not isinstance(validation, list) or not validation:
        raise MvpFourArmTrainingError("common validation reference is missing")
    if not isinstance(held_out, list) or not held_out:
        raise MvpFourArmTrainingError("held-out test reference is missing")
    arm_payload: dict[str, Any] = {}
    for arm_id in EXPECTED_ARMS:
        solver = arm_id.split("_", 1)[0]
        records = arms[arm_id].get("eligible_training_records")
        if not isinstance(records, list) or not records:
            raise MvpFourArmTrainingError(f"empty training arm: {arm_id}")
        if any(record.get("role") != "train" for record in records):
            raise MvpFourArmTrainingError("training arm contains a held-out record")
        arm_payload[arm_id] = {
            "solver": solver,
            "records": records,
            "record_count": len(records),
            "parent_count": arms[arm_id]["eligible_training_parent_count"],
            "draws_per_parent": data_plan["loader_policy"][
                "draws_per_parent_per_epoch"
            ],
            "draws_per_epoch": arms[arm_id]["draws_per_epoch"],
        }
    reference_by_solver: dict[str, dict[str, Any]] = {}
    for solver in ("gurobi", "scip"):
        original_id = f"{solver}_original"
        original_records = arm_payload[original_id]["records"]
        reference = sorted(
            original_records,
            key=lambda record: (
                str(record["parent_instance_id"]),
                str(record["sample_id"]),
            ),
        )[0]
        if reference.get("sampling_strategy") != "original":
            raise MvpFourArmTrainingError("prenorm reference is not original")
        reference_by_solver[solver] = {
            "sample_id": reference["sample_id"],
            "graph_path": reference["graph_path"],
            "graph_sha256": reference["graph_sha256"],
            "pos_weight_source_arm": original_id,
        }
    contract_payload = {
        "schema_version": SCHEMA_VERSION,
        "experiment_stage": "mvp_four_arm_training_smoke",
        "dataset_contract_sha256": data_plan["dataset_contract_sha256"],
        "training_data_contract_sha256": data_plan["contract_sha256"],
        "training_protocol": protocol.contract_payload,
        "training_protocol_sha256": protocol.contract_sha256,
        "legacy_gasse_git_blob_sha1": current_gasse_blob,
        "arms": arm_payload,
        "solver_pair_references": reference_by_solver,
        "validation_records": validation,
        "validation_reference_sha256": _reference_sha256(validation),
        "held_out_test_contract": {
            "record_count": len(held_out),
            "parent_instance_ids": sorted(
                str(record["parent_instance_id"]) for record in held_out
            ),
            "graph_sha256": sorted(str(record["graph_sha256"]) for record in held_out),
            "access_policy": "not_deserialized_during_training",
        },
        "optimizer_steps_per_arm_per_epoch": next(iter(draws)),
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **contract_payload,
        "contract_sha256": _canonical_sha256(contract_payload),
        "contract_valid": True,
        "mvp_execution_ready": True,
        "test_graphs_loaded": 0,
        "next_gate": "four_arm_training_execution",
    }


def _select_device(torch_module: Any, requested: str) -> Any:
    if requested == "cuda" and not torch_module.cuda.is_available():
        raise MvpFourArmTrainingError("CUDA was requested but is unavailable")
    if requested == "auto":
        requested = "cuda" if torch_module.cuda.is_available() else "cpu"
    return torch_module.device(requested)


def _atomic_torch_save(torch_module: Any, value: Any, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch_module.save(value, temporary)
    temporary.replace(path)


def _torch_state_sha256(model: Any) -> str:
    """Fingerprint initial tensors so equal seeded initialization is auditable."""
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        normalized = tensor.detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(normalized.dtype).encode("ascii"))
        digest.update(str(tuple(normalized.shape)).encode("ascii"))
        digest.update(normalized.numpy().tobytes())
    return digest.hexdigest()


def select_validation_threshold(
    targets: Sequence[float], probabilities: Sequence[float]
) -> dict[str, Any]:
    """Select the exact maximum-F1 threshold from validation predictions.

    The implementation sorts predictions once, so calibration remains practical
    for CFL graphs with hundreds of thousands of binary targets. Ties prefer the
    threshold nearest 0.5 and then the lower threshold. Test labels are never an
    input to this function.
    """
    import numpy as np

    truth = np.asarray(targets, dtype=np.float64) >= 0.5
    scores = np.asarray(probabilities, dtype=np.float64)
    if truth.size == 0 or scores.shape != truth.shape:
        raise MvpFourArmTrainingError(
            "validation predictions are empty or malformed"
        )
    if not np.isfinite(scores).all() or ((scores < 0.0) | (scores > 1.0)).any():
        raise MvpFourArmTrainingError("validation probabilities are invalid")

    order = np.argsort(-scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_truth = truth[order]
    cumulative_tp = np.cumsum(sorted_truth, dtype=np.int64)
    cumulative_fp = np.cumsum(~sorted_truth, dtype=np.int64)
    boundaries = np.flatnonzero(
        np.r_[sorted_scores[1:] != sorted_scores[:-1], True]
    )
    total_positive = int(truth.sum())
    candidates: list[tuple[float, int, int]] = []
    for index in boundaries.tolist():
        candidates.append(
            (
                float(sorted_scores[index]),
                int(cumulative_tp[index]),
                int(cumulative_fp[index]),
            )
        )
    for threshold in (0.0, 0.5, 1.0):
        predicted = scores >= threshold
        candidates.append(
            (
                threshold,
                int((predicted & truth).sum()),
                int((predicted & ~truth).sum()),
            )
        )

    best_key: tuple[float, float, float] | None = None
    best_payload: dict[str, Any] | None = None
    for threshold, tp, fp in candidates:
        fn = total_positive - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_score = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        key = (f1_score, -abs(threshold - 0.5), -threshold)
        if best_key is None or key > best_key:
            best_key = key
            best_payload = {
                "probability_threshold": threshold,
                "f1_score": f1_score,
                "precision": precision,
                "recall": recall,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
    assert best_payload is not None
    best_payload["candidates_evaluated"] = len(candidates)
    return best_payload


def _validation_predictions(
    model: Any, loader: Any, device: Any, *, clear_cache: bool
) -> tuple[list[float], list[float]]:
    """Collect validation targets and probabilities from the chosen checkpoint."""
    import torch

    model.eval()
    targets: list[float] = []
    probabilities: list[float] = []
    with torch.no_grad():
        for graph in loader:
            graph = graph.to(device)
            mask = graph["variable"].is_discrete.bool()
            edge = graph["variable", "rev_coef", "constraint"]
            logits = model(
                x_var=graph["variable"].x,
                x_cons=graph["constraint"].x,
                edge_v2c=edge.edge_index,
                binary_mask=mask,
                edge_attr=edge.edge_attr,
            )
            probabilities.extend(torch.sigmoid(logits).detach().cpu().tolist())
            targets.extend(
                torch.clamp(graph["variable"].y[mask], 0.0, 1.0)
                .detach()
                .cpu()
                .tolist()
            )
            if clear_cache:
                del graph, logits
                torch.cuda.empty_cache()
    return targets, probabilities


class _OptimizerStepCounter:
    """Count actual optimizer updates while preserving the existing train loop."""

    def __init__(self, optimizer: Any) -> None:
        self.optimizer = optimizer
        self.steps = 0

    def zero_grad(self) -> None:
        self.optimizer.zero_grad()

    def step(self) -> Any:
        result = self.optimizer.step()
        self.steps += 1
        return result


def _production_arm_runner(
    *,
    arm_id: str,
    arm: Mapping[str, Any],
    plan: Mapping[str, Any],
    protocol: TrainingProtocol,
    dataset_root: Path,
    output_dir: Path,
    device_name: str,
    clear_cache: bool,
) -> dict[str, Any]:
    """Train one arm; heavy ML imports stay behind the contract gate."""
    import torch
    import torch.nn as nn
    from torch_geometric.loader import DataLoader

    from cfl_gnn.graph.mvp_arm_dataset import MvpArmDataset
    from cfl_gnn.models.gasse import GasseGNN
    from cfl_gnn.training.serial import (
        calc_metrics,
        compute_pos_weight,
        eval_loop,
        set_global_seed,
        train_loop,
    )

    solver = str(arm["solver"])
    original_records = plan["arms"][f"{solver}_original"]["records"]
    training_records = arm["records"]
    validation_records = plan["validation_records"]
    device = _select_device(torch, device_name)
    original_dataset = MvpArmDataset(
        dataset_root, original_records, verify_hash_on_load=True
    )
    original_loader = DataLoader(
        original_dataset,
        batch_size=1,
        shuffle=False,
        num_workers=protocol.num_workers,
    )
    pos_weight = compute_pos_weight(original_loader, device)

    training_dataset = MvpArmDataset(
        dataset_root, training_records, verify_hash_on_load=True
    )
    sampler = DeterministicParentBalancedSampler(
        training_records,
        seed=protocol.seed,
        draws_per_parent=int(arm["draws_per_parent"]),
    )
    training_loader = DataLoader(
        training_dataset,
        batch_size=1,
        sampler=sampler,
        num_workers=protocol.num_workers,
    )
    validation_loader = DataLoader(
        MvpArmDataset(
            dataset_root, validation_records, verify_hash_on_load=True
        ),
        batch_size=1,
        shuffle=False,
        num_workers=protocol.num_workers,
    )

    reference_id = plan["solver_pair_references"][solver]["sample_id"]
    reference_index = next(
        index
        for index, record in enumerate(original_records)
        if record["sample_id"] == reference_id
    )
    representative = original_dataset[reference_index].to(device)
    edge_store = representative["variable", "rev_coef", "constraint"]
    edge_attr = edge_store.edge_attr
    edge_dim = int(edge_attr.shape[-1]) if edge_attr is not None else 0
    set_global_seed(protocol.seed)
    model = GasseGNN(
        var_in_dim=int(representative["variable"].x.shape[-1]),
        cons_in_dim=int(representative["constraint"].x.shape[-1]),
        edge_dim=edge_dim,
        hidden_dim=protocol.hidden_dim,
        num_layers=protocol.num_layers,
    ).to(device)
    initial_model_state_sha256 = _torch_state_sha256(model)
    model.fit_prenorm(
        x_var=representative["variable"].x,
        x_cons=representative["constraint"].x,
        edge_v2c=edge_store.edge_index,
        edge_attr=edge_attr,
    )
    del representative

    optimizer = _OptimizerStepCounter(
        torch.optim.Adam(model.parameters(), lr=protocol.learning_rate)
    )
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    loop_args = type(
        "LoopArguments",
        (),
        {"grad_clip": protocol.gradient_clip, "clear_cache": clear_cache},
    )()
    history: list[dict[str, Any]] = []
    best_loss = float("inf")
    best_epoch = 0
    patience_counter = 0
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / CHECKPOINT_NAME
    for epoch in range(protocol.epochs):
        steps_before_epoch = optimizer.steps
        sampler.set_epoch(epoch)
        train_loss = train_loop(
            model, training_loader, optimizer, loss_fn, device, loop_args
        )
        validation_loss, tp, tn, fp, fn = eval_loop(
            model, validation_loader, loss_fn, device, loop_args
        )
        accuracy, precision, recall, f1 = calc_metrics(tp, tn, fp, fn)
        row = {
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "validation_loss": validation_loss,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "optimizer_steps": optimizer.steps - steps_before_epoch,
        }
        if row["optimizer_steps"] != arm["draws_per_epoch"]:
            raise MvpFourArmTrainingError(
                f"actual optimizer-step budget failed for {arm_id}"
            )
        history.append(row)
        LOGGER.info(
            "arm=%s epoch=%d train_loss=%.6f validation_loss=%.6f f1=%.6f",
            arm_id,
            epoch + 1,
            train_loss,
            validation_loss,
            f1,
        )
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_epoch = epoch + 1
            patience_counter = 0
            _atomic_torch_save(torch, model.state_dict(), checkpoint)
        else:
            patience_counter += 1
        if patience_counter >= protocol.patience:
            break

    history_path = output_dir / HISTORY_NAME
    with history_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    if best_epoch == 0 or not checkpoint.is_file():
        raise MvpFourArmTrainingError(
            f"no finite validation checkpoint was produced for {arm_id}"
        )
    best = next(row for row in history if row["epoch"] == best_epoch)
    model.load_state_dict(
        torch.load(checkpoint, map_location=device, weights_only=True)
    )
    if protocol.threshold_selection_method == "maximum_validation_f1":
        validation_targets, validation_probabilities = _validation_predictions(
            model, validation_loader, device, clear_cache=clear_cache
        )
        threshold_selection = select_validation_threshold(
            validation_targets, validation_probabilities
        )
        threshold_source = "maximum_validation_f1"
    else:
        threshold_selection = {
            "probability_threshold": protocol.probability_threshold,
            "f1_score": best["f1_score"],
            "precision": best["precision"],
            "recall": best["recall"],
            "candidates_evaluated": 1,
        }
        threshold_source = "fixed_precommitted_not_test_calibrated"
    result = {
        "arm_id": arm_id,
        "solver": solver,
        "epochs_completed": len(history),
        "optimizer_steps_per_epoch": arm["draws_per_epoch"],
        "optimizer_steps_completed": optimizer.steps,
        "training_record_count": arm["record_count"],
        "training_parent_count": arm["parent_count"],
        "validation_record_count": len(validation_records),
        "validation_reference_sha256": plan["validation_reference_sha256"],
        "initialization_seed": protocol.seed,
        "initial_model_state_sha256": initial_model_state_sha256,
        "prenorm_reference_sample_id": reference_id,
        "pos_weight": float(pos_weight.item()),
        "pos_weight_source_arm": f"{solver}_original",
        "device_effective": str(device),
        "best_epoch": best_epoch,
        "best_validation_metrics": best,
        "selected_probability_threshold": threshold_selection[
            "probability_threshold"
        ],
        "threshold_source": threshold_source,
        "threshold_selection": threshold_selection,
        "checkpoint": {
            "file_name": CHECKPOINT_NAME,
            "sha256": sha256_file(checkpoint),
        },
        "history": {
            "file_name": HISTORY_NAME,
            "sha256": sha256_file(history_path),
        },
        "test_graphs_loaded": 0,
    }
    write_json(output_dir / ARM_SUMMARY_NAME, result)
    result["summary_sha256"] = sha256_file(output_dir / ARM_SUMMARY_NAME)
    return result


ArmRunner = Callable[..., dict[str, Any]]


def run_four_arm_training(
    plan: Mapping[str, Any],
    *,
    dataset_dir: str | Path,
    output_dir: str | Path,
    device: str = "auto",
    clear_cache: bool = False,
    overwrite: bool = False,
    arm_runner: ArmRunner = _production_arm_runner,
) -> dict[str, Any]:
    """Execute four independent arms and emit a path-sanitized aggregate report."""
    if plan.get("contract_valid") is not True or plan.get(
        "mvp_execution_ready"
    ) is not True:
        raise MvpFourArmTrainingError("training run plan is not executable")
    protocol = TrainingProtocol.from_mapping(plan["training_protocol"])
    if protocol.contract_sha256 != plan.get("training_protocol_sha256"):
        raise MvpFourArmTrainingError("training protocol changed after planning")
    output = Path(output_dir).resolve()
    expected_outputs = [output / RUN_REPORT_NAME] + [
        output / "arms" / arm_id / CHECKPOINT_NAME for arm_id in EXPECTED_ARMS
    ]
    if not overwrite and any(path.exists() for path in expected_outputs):
        raise FileExistsError("training output exists; use --overwrite")
    results: list[dict[str, Any]] = []
    for arm_id in EXPECTED_ARMS:
        result = arm_runner(
            arm_id=arm_id,
            arm=plan["arms"][arm_id],
            plan=plan,
            protocol=protocol,
            dataset_root=Path(dataset_dir).resolve(),
            output_dir=output / "arms" / arm_id,
            device_name=device,
            clear_cache=clear_cache,
        )
        if protocol.schema_version == 1:
            result.setdefault(
                "selected_probability_threshold", protocol.probability_threshold
            )
            result.setdefault(
                "threshold_source", "fixed_precommitted_not_test_calibrated"
            )
        if (
            result.get("arm_id") != arm_id
            or result.get("test_graphs_loaded") != 0
            or result.get("initialization_seed") != protocol.seed
            or result.get("optimizer_steps_per_epoch")
            != plan["optimizer_steps_per_arm_per_epoch"]
            or result.get("validation_reference_sha256")
            != plan["validation_reference_sha256"]
            or not 0.0
            <= float(result.get("selected_probability_threshold", -1.0))
            <= 1.0
            or result.get("threshold_source")
            != (
                "maximum_validation_f1"
                if protocol.threshold_selection_method
                == "maximum_validation_f1"
                else "fixed_precommitted_not_test_calibrated"
            )
        ):
            raise MvpFourArmTrainingError(f"arm execution audit failed: {arm_id}")
        results.append(result)
    by_solver: dict[str, list[dict[str, Any]]] = {
        solver: [item for item in results if item["solver"] == solver]
        for solver in ("gurobi", "scip")
    }
    paired_controls = {
        "same_initialization_seed_all_arms": len(
            {item["initialization_seed"] for item in results}
        )
        == 1,
        "same_initial_model_state_all_arms": len(
            {item["initial_model_state_sha256"] for item in results}
        )
        == 1,
        "same_optimizer_steps_all_arms": len(
            {item["optimizer_steps_per_epoch"] for item in results}
        )
        == 1,
        "same_total_optimizer_steps_all_arms": len(
            {item["optimizer_steps_completed"] for item in results}
        )
        == 1,
        "same_validation_population_all_arms": all(
            item["validation_reference_sha256"]
            == plan["validation_reference_sha256"]
            for item in results
        ),
        "validation_only_threshold_selection_all_arms": all(
            item["threshold_source"]
            == (
                "maximum_validation_f1"
                if protocol.threshold_selection_method
                == "maximum_validation_f1"
                else "fixed_precommitted_not_test_calibrated"
            )
            for item in results
        ),
        "solver_pair_pos_weight_match": all(
            len({item["pos_weight"] for item in records}) == 1
            for records in by_solver.values()
        ),
        "solver_pair_prenorm_reference_match": all(
            len({item["prenorm_reference_sample_id"] for item in records}) == 1
            for records in by_solver.values()
        ),
        "test_graphs_loaded_zero": all(
            item["test_graphs_loaded"] == 0 for item in results
        ),
        "same_effective_device_all_arms": len(
            {item["device_effective"] for item in results}
        )
        == 1,
    }
    if not all(paired_controls.values()):
        raise MvpFourArmTrainingError("paired four-arm controls were not preserved")
    eligibility = {
        "training_smoke_eligible": True,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    if protocol.schema_version == 2:
        eligibility["held_out_evaluation_ready"] = True
    report = {
        "schema_version": SCHEMA_VERSION,
        "training_run_contract_sha256": plan["contract_sha256"],
        "training_data_contract_sha256": plan["training_data_contract_sha256"],
        "training_protocol_sha256": plan["training_protocol_sha256"],
        "probe_completed": True,
        "gate_status": "passed",
        "experiment_stage": protocol.experiment_stage,
        "execution": {
            "mode": "serial_independent_models",
            "arms_planned": 4,
            "arms_completed": len(results),
            "device_request": device,
        },
        "paired_controls": paired_controls,
        "arms": {item["arm_id"]: item for item in results},
        "held_out_test_contract": plan["held_out_test_contract"],
        "eligibility": eligibility,
        "decision": {
            "reason_code": (
                "four_arm_validation_selected_training_completed"
                if protocol.threshold_selection_method
                == "maximum_validation_f1"
                else "four_arm_training_smoke_completed"
            ),
            "next_gate": "common_held_out_evaluation_and_hint_solver_comparison",
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / RUN_REPORT_NAME, report)
    return report


def write_training_run_plan(path: str | Path, plan: Mapping[str, Any]) -> None:
    """Write the path-sanitized training-run contract."""
    write_json(path, plan)

