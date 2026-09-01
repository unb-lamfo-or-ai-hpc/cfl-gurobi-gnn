"""Lazy dataset for contract-validated parent-instance PyG graphs."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from cfl_gnn.splits.instance_partitions import InstanceGraphRecord


def validate_loaded_graph(graph: Any, record: InstanceGraphRecord) -> None:
    """Cross-check serialized graph metadata against its audited record."""
    expected = {
        "source_instance_id": record.source_instance_id,
        "instance_fold": record.fold,
        "parent_category": record.category,
        "label_source": record.label_source,
        "label_mip_gap_band": record.mip_gap_band,
    }
    mismatches: list[str] = []
    for field, expected_value in expected.items():
        actual_value = getattr(graph, field, None)
        if actual_value != expected_value:
            mismatches.append(
                f"{field}={actual_value!r}, expected {expected_value!r}"
            )
    if mismatches:
        raise ValueError(
            f"serialized graph contract mismatch for {record.source_instance_id}: "
            + "; ".join(mismatches)
        )


class ParentInstanceDataset(Sequence[Any]):
    """Load only records admitted by an :class:`InstanceDatasetAudit`.

    PyTorch is imported lazily in ``__getitem__`` so inventory and partition
    audits remain runnable on CPU login nodes without the ML environment.
    """

    def __init__(
        self,
        records: Sequence[InstanceGraphRecord],
        *,
        transform: Callable[[Any], Any] | None = None,
    ) -> None:
        self.records = tuple(records)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> Any:
        import torch

        record = self.records[index]
        graph = torch.load(record.graph_path, weights_only=False)
        validate_loaded_graph(graph, record)
        return self.transform(graph) if self.transform is not None else graph

    @property
    def source_instance_ids(self) -> tuple[str, ...]:
        return tuple(record.source_instance_id for record in self.records)
