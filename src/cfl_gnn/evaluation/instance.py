"""Contract-locked evaluation for the Gurobi parent-instance baseline."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.training.instance_plan import (
    InstanceTrainingPlan,
    build_instance_training_plan,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
FIXED_PROBABILITY_THRESHOLD = 0.5


class InstanceEvaluationContractError(ValueError):
    """Raised when evaluation cannot prove the training/test contract."""


def _read_json_object(path: str | Path, *, artifact: str) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file() or source.stat().st_size == 0:
        raise InstanceEvaluationContractError(f"missing or empty {artifact}: {source}")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise InstanceEvaluationContractError(f"unreadable {artifact}: {source}") from error
    if not isinstance(value, dict):
        raise InstanceEvaluationContractError(f"{artifact} must be a JSON object")
    return value


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise InstanceEvaluationContractError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise InstanceEvaluationContractError(
            f"{field} must be a positive integer"
        ) from error
    if normalized <= 0 or normalized != value:
        raise InstanceEvaluationContractError(f"{field} must be a positive integer")
    return normalized


def _positive_finite(value: Any, *, field: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise InstanceEvaluationContractError(
            f"{field} must be positive and finite"
        ) from error
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise InstanceEvaluationContractError(f"{field} must be positive and finite")
    return normalized


@dataclass(frozen=True, slots=True)
class InstanceEvaluationPlan:
    """Validated model configuration and held-out parent membership."""

    training_plan: InstanceTrainingPlan
    experiment_name: str
    hidden_dim: int
    num_layers: int
    pos_weight: float
    checkpoint_sha256: str

    @property
    def contract_sha256(self) -> str:
        return self.training_plan.contract_sha256

    @property
    def test_records(self):
        return self.training_plan.records_for_role("test")

    def to_summary(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_variant": "gurobi_parent_instance",
            "evaluation_protocol": "held_out_parent_instances_fixed_threshold",
            "contract_sha256": self.contract_sha256,
            "experiment_name": self.experiment_name,
            "rotation": self.training_plan.audit.rotation,
            "label_policy": self.training_plan.audit.label_policy,
            "development_only": self.training_plan.development_only,
            "scientific_reporting_eligible": (
                self.training_plan.scientific_reporting_eligible
            ),
            "probability_threshold": FIXED_PROBABILITY_THRESHOLD,
            "threshold_source": "fixed_precommitted_not_test_calibrated",
            "checkpoint_format": "plain_gasse_state_dict",
            "checkpoint_sha256": self.checkpoint_sha256,
            "graph_hashes_verified": self.training_plan.audit.graph_hashes_verified,
            "test_partition_usage": "held_out_evaluation_only",
            "test_instances": [
                record.source_instance_id for record in self.test_records
            ],
            "test_by_difficulty": {
                difficulty: sum(
                    record.difficulty == difficulty for record in self.test_records
                )
                for difficulty in sorted(
                    {record.difficulty for record in self.test_records}
                )
            },
            "model": {
                "hidden_dim": self.hidden_dim,
                "num_layers": self.num_layers,
                "pos_weight": self.pos_weight,
            },
        }


def build_instance_evaluation_plan(
    dataset_root: str | Path,
    manifest_path: str | Path,
    training_plan_path: str | Path,
    experiment_summary_path: str | Path,
    checkpoint_path: str | Path,
) -> InstanceEvaluationPlan:
    """Rebuild the audited split and bind it to the saved training contract."""
    stored_plan = _read_json_object(training_plan_path, artifact="training plan")
    experiment = _read_json_object(
        experiment_summary_path, artifact="experiment summary"
    )
    if stored_plan.get("training_plan_schema_version") != 1:
        raise InstanceEvaluationContractError("unsupported training plan schema")
    if stored_plan.get("dataset_variant") != "gurobi_parent_instance":
        raise InstanceEvaluationContractError("training plan dataset variant mismatch")

    rotation = stored_plan.get("rotation")
    label_policy = stored_plan.get("label_policy")
    development_only = stored_plan.get("development_only")
    if not isinstance(rotation, int) or not 0 <= rotation < 5:
        raise InstanceEvaluationContractError("training plan rotation is invalid")
    if label_policy not in ("optimal_only", "all_available"):
        raise InstanceEvaluationContractError("training plan label policy is invalid")
    if not isinstance(development_only, bool):
        raise InstanceEvaluationContractError(
            "training plan development_only flag is invalid"
        )
    if stored_plan.get("test_partition_usage") != (
        "held_out_not_loaded_during_training"
    ):
        raise InstanceEvaluationContractError(
            "training plan does not prove that the test partition was held out"
        )

    current_plan = build_instance_training_plan(
        dataset_root,
        manifest_path,
        rotation=rotation,
        label_policy=label_policy,
        development_only=development_only,
    )
    expected_contract = current_plan.contract_sha256
    if stored_plan.get("contract_sha256") != expected_contract:
        raise InstanceEvaluationContractError(
            "current graph inventory disagrees with the saved training contract"
        )
    if experiment.get("contract_sha256") != expected_contract:
        raise InstanceEvaluationContractError(
            "experiment summary disagrees with the training contract"
        )
    if experiment.get("dataset_variant") != "gurobi_parent_instance":
        raise InstanceEvaluationContractError("experiment dataset variant mismatch")
    if experiment.get("rotation") != rotation:
        raise InstanceEvaluationContractError("experiment rotation mismatch")
    if experiment.get("label_policy") != label_policy:
        raise InstanceEvaluationContractError("experiment label policy mismatch")
    if experiment.get("development_only") is not development_only:
        raise InstanceEvaluationContractError("experiment development flag mismatch")
    if experiment.get("test_partition_usage") != (
        "held_out_not_loaded_during_training"
    ):
        raise InstanceEvaluationContractError(
            "experiment summary does not prove held-out test usage"
        )

    checkpoint = Path(checkpoint_path)
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        raise InstanceEvaluationContractError(
            f"missing or empty checkpoint: {checkpoint}"
        )
    recorded_checkpoint_digest = experiment.get("checkpoint_sha256")
    if not isinstance(recorded_checkpoint_digest, str) or re.fullmatch(
        r"[0-9a-f]{64}", recorded_checkpoint_digest
    ) is None:
        raise InstanceEvaluationContractError(
            "experiment summary has no valid checkpoint SHA-256"
        )
    current_checkpoint_digest = sha256_file(checkpoint)
    if current_checkpoint_digest != recorded_checkpoint_digest:
        raise InstanceEvaluationContractError(
            "checkpoint SHA-256 disagrees with the experiment summary"
        )

    stored_test = stored_plan.get("partitions", {}).get("test", {}).get("instances")
    current_test = [
        record.source_instance_id
        for record in current_plan.records_for_role("test")
    ]
    if stored_test != current_test:
        raise InstanceEvaluationContractError("saved and current test membership differ")

    hyperparameters = experiment.get("hyperparameters")
    if not isinstance(hyperparameters, Mapping):
        raise InstanceEvaluationContractError("experiment hyperparameters are missing")
    experiment_name = experiment.get("experiment_name")
    if not isinstance(experiment_name, str) or not experiment_name:
        raise InstanceEvaluationContractError("experiment name is missing")
    return InstanceEvaluationPlan(
        training_plan=current_plan,
        experiment_name=experiment_name,
        hidden_dim=_positive_int(
            hyperparameters.get("hidden_dim"), field="hidden_dim"
        ),
        num_layers=_positive_int(
            hyperparameters.get("num_layers"), field="num_layers"
        ),
        pos_weight=_positive_finite(
            hyperparameters.get("pos_weight"), field="pos_weight"
        ),
        checkpoint_sha256=current_checkpoint_digest,
    )


def classification_metrics(tp: int, tn: int, fp: int, fn: int) -> dict[str, float]:
    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a parent-instance Gasse checkpoint exclusively on its "
            "contract-bound held-out test fold."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--base_pyg_dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--training_plan", type=Path)
    parser.add_argument("--experiment_summary", type=Path)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--num_workers", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def _select_device(torch_module, requested: str):
    if requested == "cuda" and not torch_module.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    if requested == "auto":
        requested = "cuda" if torch_module.cuda.is_available() else "cpu"
    return torch_module.device(requested)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_evaluation(
    args: argparse.Namespace,
    plan: InstanceEvaluationPlan,
    output_dir: Path,
) -> None:
    # PyTorch and PyG are imported only after the contract has passed.
    import torch
    import torch.nn.functional as functional
    from torch_geometric.loader import DataLoader

    from cfl_gnn.graph.instance_dataset import ParentInstanceDataset
    from cfl_gnn.models.gasse import GasseGNN

    device = _select_device(torch, args.device)
    state_dict = torch.load(args.checkpoint, map_location=device, weights_only=True)
    test_dataset = ParentInstanceDataset(plan.test_records)
    test_loader = DataLoader(
        test_dataset,
        batch_size=1,
        shuffle=False,
        num_workers=args.num_workers,
    )
    pos_weight = torch.tensor([plan.pos_weight], device=device)
    model = None
    rows: list[dict[str, Any]] = []
    totals = {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "targets": 0, "loss": 0.0}
    by_difficulty: dict[str, dict[str, float | int]] = {}

    for record, batch in zip(plan.test_records, test_loader):
        batch = batch.to(device)
        edge_store = batch["variable", "rev_coef", "constraint"]
        if model is None:
            edge_attr = edge_store.edge_attr
            edge_dim = int(edge_attr.shape[-1]) if edge_attr is not None else 0
            model = GasseGNN(
                var_in_dim=int(batch["variable"].x.shape[-1]),
                cons_in_dim=int(batch["constraint"].x.shape[-1]),
                edge_dim=edge_dim,
                hidden_dim=plan.hidden_dim,
                num_layers=plan.num_layers,
            ).to(device)
            model.load_state_dict(state_dict)
            model.eval()

        mask = batch["variable"].is_discrete.bool()
        if int(mask.sum()) == 0:
            raise InstanceEvaluationContractError(
                f"test graph has no discrete targets: {record.source_instance_id}"
            )
        with torch.no_grad():
            logits = model(
                x_var=batch["variable"].x,
                x_cons=batch["constraint"].x,
                edge_v2c=edge_store.edge_index,
                binary_mask=mask,
                edge_attr=edge_store.edge_attr,
            )
            targets = torch.clamp(batch["variable"].y[mask], min=0.0, max=1.0)
            probabilities = torch.sigmoid(logits)
            predictions = probabilities >= FIXED_PROBABILITY_THRESHOLD
            positives = targets >= 0.5
            loss_sum = functional.binary_cross_entropy_with_logits(
                logits,
                targets,
                pos_weight=pos_weight,
                reduction="sum",
            ).item()

        tp = int((predictions & positives).sum().item())
        tn = int((~predictions & ~positives).sum().item())
        fp = int((predictions & ~positives).sum().item())
        fn = int((~predictions & positives).sum().item())
        n_targets = int(targets.numel())
        metrics = classification_metrics(tp, tn, fp, fn)
        rows.append(
            {
                "source_instance_id": record.source_instance_id,
                "difficulty": record.difficulty,
                "fold": record.fold,
                "n_targets": n_targets,
                "n_positive": int(positives.sum().item()),
                "weighted_bce_per_variable": loss_sum / n_targets,
                "tp": tp,
                "tn": tn,
                "fp": fp,
                "fn": fn,
                **metrics,
            }
        )
        for key, value in (("tp", tp), ("tn", tn), ("fp", fp), ("fn", fn)):
            totals[key] += value
        totals["targets"] += n_targets
        totals["loss"] += loss_sum
        difficulty_totals = by_difficulty.setdefault(
            record.difficulty,
            {"tp": 0, "tn": 0, "fp": 0, "fn": 0, "targets": 0, "loss": 0.0},
        )
        for key, value in (("tp", tp), ("tn", tn), ("fp", fp), ("fn", fn)):
            difficulty_totals[key] += value
        difficulty_totals["targets"] += n_targets
        difficulty_totals["loss"] += loss_sum

    if len(rows) != len(plan.test_records):
        raise InstanceEvaluationContractError(
            "held-out test loader did not yield every contracted instance"
        )
    if model is None or totals["targets"] == 0:
        raise InstanceEvaluationContractError("held-out test partition produced no targets")

    per_difficulty: dict[str, Any] = {}
    for difficulty, values in sorted(by_difficulty.items()):
        per_difficulty[difficulty] = {
            "n_targets": values["targets"],
            "weighted_bce_per_variable": values["loss"] / values["targets"],
            "confusion": {
                key: values[key] for key in ("tp", "tn", "fp", "fn")
            },
            **classification_metrics(
                int(values["tp"]),
                int(values["tn"]),
                int(values["fp"]),
                int(values["fn"]),
            ),
        }
    aggregate = {
        "n_test_instances": len(rows),
        "n_targets": totals["targets"],
        "weighted_bce_per_variable": totals["loss"] / totals["targets"],
        "confusion": {key: totals[key] for key in ("tp", "tn", "fp", "fn")},
        **classification_metrics(
            int(totals["tp"]),
            int(totals["tn"]),
            int(totals["fp"]),
            int(totals["fn"]),
        ),
    }
    summary = plan.to_summary()
    summary.update(
        {
            "aggregate_metrics": aggregate,
            "metrics_by_difficulty": per_difficulty,
            "per_instance_metrics_file": "per_instance_metrics.csv",
        }
    )
    _write_json(output_dir / "instance_evaluation_summary.json", summary)
    with (output_dir / "per_instance_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = build_parser().parse_args(argv)
    if args.num_workers < 0:
        raise ValueError("num_workers must be nonnegative")
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        raise FileNotFoundError(f"missing or empty checkpoint: {checkpoint}")
    args.checkpoint = checkpoint
    run_dir = checkpoint.parent
    training_plan_path = (args.training_plan or run_dir / "instance_training_plan.json")
    experiment_summary_path = (
        args.experiment_summary or run_dir / "experiment_summary.json"
    )
    plan = build_instance_evaluation_plan(
        args.base_pyg_dir,
        args.manifest,
        training_plan_path,
        experiment_summary_path,
        checkpoint,
    )
    output_dir = (args.output_dir or run_dir / "evaluation_fixed_threshold").resolve()
    result_outputs = (
        output_dir / "instance_evaluation_summary.json",
        output_dir / "per_instance_metrics.csv",
    )
    if not args.dry_run and not args.overwrite and any(
        path.exists() for path in result_outputs
    ):
        raise FileExistsError(
            "evaluation output already exists; choose another output directory or "
            "pass --overwrite explicitly"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "instance_evaluation_plan.json", plan.to_summary())
    print(
        "[INFO] "
        f"contract={plan.contract_sha256} | test={len(plan.test_records)} | "
        f"threshold={FIXED_PROBABILITY_THRESHOLD} | "
        f"development_only={plan.training_plan.development_only}"
    )
    print("[INFO] only held-out test graphs are eligible for deserialization")
    print(f"[INFO] Plan: {output_dir / 'instance_evaluation_plan.json'}")
    if args.dry_run:
        return 0
    _run_evaluation(args, plan, output_dir)
    LOGGER.info("held-out evaluation complete: %s", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
