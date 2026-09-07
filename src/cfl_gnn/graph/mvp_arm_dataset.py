"""Lazy PyG dataset adapter for a validated MVP training-data plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.training.mvp_arm import MvpTrainingDataError


def _resolve_graph(dataset_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    root = dataset_root.resolve()
    if relative.is_absolute() or ".." in relative.parts:
        raise MvpTrainingDataError("unsafe graph path in training plan")
    resolved = (root / relative).resolve()
    if root not in resolved.parents or not resolved.is_file():
        raise MvpTrainingDataError("training graph is missing or outside the dataset")
    return resolved


class MvpArmDataset:
    """Load only the records explicitly selected by the training-data plan."""

    def __init__(
        self,
        dataset_root: str | Path,
        records: Sequence[Mapping[str, Any]],
        *,
        verify_hash_on_load: bool = False,
    ) -> None:
        self.dataset_root = Path(dataset_root).resolve()
        self.records = tuple(dict(record) for record in records)
        self.verify_hash_on_load = verify_hash_on_load

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        import torch

        record = self.records[index]
        path = _resolve_graph(self.dataset_root, str(record["graph_path"]))
        if self.verify_hash_on_load and sha256_file(path) != record["graph_sha256"]:
            raise MvpTrainingDataError("graph changed after training planning")
        graph = torch.load(path, weights_only=False)
        graph.sample_id = str(record["sample_id"])
        graph.parent_instance_id = str(record["parent_instance_id"])
        graph.role = str(record["role"])
        graph.sample_weight = float(
            record.get("effective_within_parent_weight", 1.0)
        )
        return graph


def selected_records_for_arm(
    plan: Mapping[str, Any], arm_id: str
) -> tuple[dict[str, Any], ...]:
    """Return training rows for one arm without exposing held-out records."""
    try:
        records = plan["arms"][arm_id]["eligible_training_records"]
    except (KeyError, TypeError) as error:
        raise MvpTrainingDataError(f"unknown or malformed arm: {arm_id}") from error
    if not isinstance(records, list):
        raise MvpTrainingDataError("eligible_training_records must be a list")
    return tuple(dict(record) for record in records)


def selected_common_reference_records(
    plan: Mapping[str, Any], role: str
) -> tuple[dict[str, Any], ...]:
    """Return validation records; test access must be requested explicitly."""
    if role not in ("validation", "test"):
        raise MvpTrainingDataError("common reference role must be validation or test")
    if role == "test" and plan.get("test_partition_usage") != (
        "held_out_not_loaded_during_training"
    ):
        raise MvpTrainingDataError("test access policy is not held out")
    records = plan.get("common_reference_partitions", {}).get(role)
    if not isinstance(records, list):
        raise MvpTrainingDataError(f"malformed common {role} reference")
    return tuple(dict(record) for record in records)

