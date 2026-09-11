"""Fold-aware inventory contract for the Gurobi parent-instance baseline.

This module deliberately avoids importing PyTorch.  It can therefore audit a
DaSCI graph inventory and construct deterministic train/validation/test record
lists before any graph is deserialized or a GPU process is started.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import (
    mip_gap_band,
    provenance_path,
    sha256_file,
)
from cfl_gnn.splits.instance_folds import (
    CATEGORIES,
    InstanceFold,
    role_for_fold,
    validate_manifest,
)


ROLES = ("train", "validation", "test")
LABEL_POLICIES = ("optimal_only", "gap_le_10pct", "all_available")
KNOWN_GAP_BANDS = (
    "optimal_tolerance",
    "gap_le_10pct",
    "gap_le_40pct",
    "gap_gt_40pct",
)


class InstanceDatasetContractError(ValueError):
    """Raised when a graph or sidecar violates the baseline contract."""


@dataclass(frozen=True, slots=True)
class InstanceGraphRecord:
    """One valid and policy-eligible graph with its canonical role."""

    source_instance_id: str
    category: str
    difficulty: str
    fold: int
    role: str
    graph_path: Path
    provenance_path: Path
    label_source: str
    mip_gap: float | None
    mip_gap_band: str


@dataclass(frozen=True, slots=True)
class ExcludedInstance:
    """A contract-valid graph excluded by the selected label policy."""

    source_instance_id: str
    category: str
    difficulty: str
    fold: int
    role: str
    label_source: str
    mip_gap_band: str
    reason: str


@dataclass(frozen=True, slots=True)
class InvalidInstance:
    """A present graph that is unsafe to expose to training."""

    source_instance_id: str
    relative_graph_path: str
    reason: str


@dataclass(frozen=True, slots=True)
class InstanceDatasetAudit:
    """Complete audit result for one rotation and label policy."""

    dataset_root: Path
    manifest_size: int
    rotation: int
    label_policy: str
    graph_hashes_verified: bool
    discovered_graphs: int
    eligible: tuple[InstanceGraphRecord, ...]
    excluded: tuple[ExcludedInstance, ...]
    missing: tuple[InstanceFold, ...]
    invalid: tuple[InvalidInstance, ...]

    @property
    def valid_graphs(self) -> int:
        return len(self.eligible) + len(self.excluded)

    @property
    def contract_valid(self) -> bool:
        role_counts = Counter(record.role for record in self.eligible)
        return not self.invalid and all(role_counts[role] > 0 for role in ROLES)

    def records_for_role(self, role: str) -> tuple[InstanceGraphRecord, ...]:
        if role not in ROLES:
            raise ValueError(f"unknown partition role: {role}")
        return tuple(record for record in self.eligible if record.role == role)

    def to_summary(self) -> dict[str, Any]:
        """Return a path-sanitized, JSON-serializable audit report."""
        partitions: dict[str, Any] = {}
        for role in ROLES:
            records = self.records_for_role(role)
            partitions[role] = {
                "total": len(records),
                "by_difficulty": dict(
                    sorted(Counter(item.difficulty for item in records).items())
                ),
                "by_fold": {
                    str(key): value
                    for key, value in sorted(
                        Counter(item.fold for item in records).items()
                    )
                },
                "instances": [item.source_instance_id for item in records],
            }

        valid_records = list(self.eligible) + list(self.excluded)
        missing_by_difficulty = Counter(item.difficulty for item in self.missing)
        excluded_by_band = Counter(item.mip_gap_band for item in self.excluded)
        warnings: list[str] = []
        if self.discovered_graphs < self.manifest_size:
            warnings.append("development_partial_inventory")
        absent_difficulties = [
            difficulty
            for difficulty in CATEGORIES.values()
            if not any(item.difficulty == difficulty for item in self.eligible)
        ]
        if absent_difficulties:
            warnings.append(
                "eligible_difficulties_missing:" + ",".join(absent_difficulties)
            )
        if self.label_policy == "all_available" and self.excluded:
            warnings.append("unknown_gap_labels_excluded")
        if self.label_policy != "optimal_only" and any(
            item.mip_gap_band != "optimal_tolerance" for item in self.eligible
        ):
            warnings.append("non_optimal_labels_development_only")
        if self.invalid:
            warnings.append("invalid_graph_contract")

        return {
            "schema_version": 1,
            "dataset_variant": "gurobi_parent_instance",
            "sampling_strategy": "parent_instance_best_available",
            "rotation": self.rotation,
            "label_policy": self.label_policy,
            "graph_hashes_verified": self.graph_hashes_verified,
            "manifest_instances": self.manifest_size,
            "discovered_graphs": self.discovered_graphs,
            "valid_graphs": self.valid_graphs,
            "eligible_graphs": len(self.eligible),
            "excluded_by_label_policy": len(self.excluded),
            "missing_graphs": len(self.missing),
            "invalid_graphs": len(self.invalid),
            "population_status": (
                "complete"
                if self.discovered_graphs == self.manifest_size and not self.invalid
                else "development_partial"
            ),
            "contract_valid": self.contract_valid,
            "partitions": partitions,
            "label_quality": {
                "valid_by_mip_gap_band": dict(
                    sorted(Counter(item.mip_gap_band for item in valid_records).items())
                ),
                "eligible_by_mip_gap_band": dict(
                    sorted(
                        Counter(item.mip_gap_band for item in self.eligible).items()
                    )
                ),
                "excluded_by_mip_gap_band": dict(sorted(excluded_by_band.items())),
                "eligible_by_artifact": dict(
                    sorted(Counter(item.label_source for item in self.eligible).items())
                ),
            },
            "missing_by_difficulty": dict(sorted(missing_by_difficulty.items())),
            "excluded_instances": [
                {
                    "source_instance_id": item.source_instance_id,
                    "difficulty": item.difficulty,
                    "fold": item.fold,
                    "role": item.role,
                    "mip_gap_band": item.mip_gap_band,
                    "reason": item.reason,
                }
                for item in self.excluded
            ],
            "invalid_instances": [
                {
                    "source_instance_id": item.source_instance_id,
                    "relative_graph_path": item.relative_graph_path,
                    "reason": item.reason,
                }
                for item in self.invalid
            ],
            "warnings": warnings,
        }


def _optional_finite_nonnegative(value: Any, *, field: str) -> float | None:
    if value is None:
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise InstanceDatasetContractError(f"{field} is not numeric") from error
    if not math.isfinite(normalized) or normalized < 0.0:
        raise InstanceDatasetContractError(f"{field} is not finite and nonnegative")
    return normalized


def _read_graph_contract(
    graph_path: Path,
    entry: InstanceFold,
    *,
    verify_graph_hash: bool,
) -> tuple[str, float | None, str]:
    sidecar_path = provenance_path(graph_path)
    if not sidecar_path.is_file() or sidecar_path.stat().st_size == 0:
        raise InstanceDatasetContractError("missing provenance sidecar")
    try:
        with sidecar_path.open("r", encoding="utf-8") as stream:
            sidecar = json.load(stream)
    except (OSError, ValueError, TypeError) as error:
        raise InstanceDatasetContractError("unreadable provenance sidecar") from error
    if not isinstance(sidecar, Mapping):
        raise InstanceDatasetContractError("provenance sidecar is not an object")

    expected = {
        "schema_version": 2,
        "instance": entry.source_instance_id,
        "fold": entry.fold,
        "parent_category": entry.category,
        "sampling_strategy": "parent_instance_best_available",
        "objective_sense": "MINIMIZE",
    }
    for field, expected_value in expected.items():
        if sidecar.get(field) != expected_value:
            raise InstanceDatasetContractError(
                f"sidecar {field} mismatch: {sidecar.get(field)!r} != "
                f"{expected_value!r}"
            )

    graph_digest = sidecar.get("graph_sha256")
    if not isinstance(graph_digest, str) or not graph_digest:
        raise InstanceDatasetContractError("sidecar has no graph SHA-256")
    if verify_graph_hash and sha256_file(graph_path) != graph_digest:
        raise InstanceDatasetContractError("graph SHA-256 mismatch")

    label_source = sidecar.get("label_source")
    label = sidecar.get("label_provenance")
    audit = sidecar.get("candidate_audit")
    if not isinstance(label_source, str) or not label_source:
        raise InstanceDatasetContractError("label_source is not explicit")
    if not isinstance(label, Mapping):
        raise InstanceDatasetContractError("label_provenance is missing")
    if not isinstance(audit, Mapping):
        raise InstanceDatasetContractError("candidate_audit is missing")
    if label.get("artifact") != label_source:
        raise InstanceDatasetContractError("label artifact disagrees with label_source")
    if audit.get("selected_artifact") != label_source:
        raise InstanceDatasetContractError(
            "candidate audit disagrees with label_source"
        )

    mip_gap = _optional_finite_nonnegative(
        label.get("mip_gap"), field="label mip_gap"
    )
    recorded_band = label.get("mip_gap_band")
    computed_band = mip_gap_band(mip_gap)
    if recorded_band != computed_band:
        raise InstanceDatasetContractError(
            f"mip-gap band mismatch: {recorded_band!r} != {computed_band!r}"
        )
    return label_source, mip_gap, computed_band


def _policy_accepts(mip_gap_quality: str, label_policy: str) -> bool:
    if label_policy == "optimal_only":
        return mip_gap_quality == "optimal_tolerance"
    if label_policy == "gap_le_10pct":
        return mip_gap_quality in ("optimal_tolerance", "gap_le_10pct")
    return mip_gap_quality in KNOWN_GAP_BANDS


def audit_instance_dataset(
    dataset_root: str | Path,
    manifest: Sequence[InstanceFold],
    *,
    rotation: int,
    label_policy: str = "optimal_only",
    verify_graph_hashes: bool = True,
) -> InstanceDatasetAudit:
    """Audit and partition the current graph inventory without reassigning folds."""
    validate_manifest(manifest)
    if label_policy not in LABEL_POLICIES:
        raise ValueError(f"unknown label policy: {label_policy}")
    role_for_fold(0, rotation)

    root = Path(dataset_root).resolve()
    manifest_by_id = {entry.source_instance_id: entry for entry in manifest}
    expected_paths = {
        (root / entry.category / "processed" / f"{entry.source_instance_id}.pt"):
        entry
        for entry in manifest
    }
    eligible: list[InstanceGraphRecord] = []
    excluded: list[ExcludedInstance] = []
    missing: list[InstanceFold] = []
    invalid: list[InvalidInstance] = []

    actual_graphs = set(root.glob("*/processed/*.pt")) if root.is_dir() else set()
    for unexpected in sorted(actual_graphs - set(expected_paths)):
        invalid.append(
            InvalidInstance(
                source_instance_id=unexpected.stem,
                relative_graph_path=unexpected.relative_to(root).as_posix(),
                reason="graph is not present in the canonical manifest",
            )
        )

    for graph_path, entry in expected_paths.items():
        if not graph_path.is_file() or graph_path.stat().st_size == 0:
            missing.append(entry)
            continue
        role = role_for_fold(entry.fold, rotation)
        try:
            label_source, mip_gap, quality = _read_graph_contract(
                graph_path,
                entry,
                verify_graph_hash=verify_graph_hashes,
            )
        except (InstanceDatasetContractError, OSError) as error:
            invalid.append(
                InvalidInstance(
                    source_instance_id=entry.source_instance_id,
                    relative_graph_path=graph_path.relative_to(root).as_posix(),
                    reason=str(error),
                )
            )
            continue

        if not _policy_accepts(quality, label_policy):
            excluded.append(
                ExcludedInstance(
                    source_instance_id=entry.source_instance_id,
                    category=entry.category,
                    difficulty=entry.difficulty,
                    fold=entry.fold,
                    role=role,
                    label_source=label_source,
                    mip_gap_band=quality,
                    reason=f"label policy {label_policy} rejects {quality}",
                )
            )
            continue
        eligible.append(
            InstanceGraphRecord(
                source_instance_id=entry.source_instance_id,
                category=entry.category,
                difficulty=entry.difficulty,
                fold=entry.fold,
                role=role,
                graph_path=graph_path,
                provenance_path=provenance_path(graph_path),
                label_source=label_source,
                mip_gap=mip_gap,
                mip_gap_band=quality,
            )
        )

    paired_sidecars = {provenance_path(path) for path in actual_graphs}
    actual_sidecars = (
        set(root.glob("*/processed/*.provenance.json")) if root.is_dir() else set()
    )
    for orphan in sorted(actual_sidecars - paired_sidecars):
        instance_id = orphan.name.removesuffix(".provenance.json")
        paired_graph = orphan.parent / f"{instance_id}.pt"
        if instance_id in manifest_by_id and not paired_graph.is_file():
            reason = "orphan provenance sidecar without graph"
        else:
            reason = "provenance sidecar is not paired with a canonical graph"
        invalid.append(
            InvalidInstance(
                source_instance_id=instance_id,
                relative_graph_path=orphan.relative_to(root).as_posix(),
                reason=reason,
            )
        )

    sort_key = lambda item: (item.category, item.source_instance_id)
    return InstanceDatasetAudit(
        dataset_root=root,
        manifest_size=len(manifest),
        rotation=rotation,
        label_policy=label_policy,
        graph_hashes_verified=verify_graph_hashes,
        discovered_graphs=len(actual_graphs),
        eligible=tuple(sorted(eligible, key=sort_key)),
        excluded=tuple(sorted(excluded, key=sort_key)),
        missing=tuple(sorted(missing, key=sort_key)),
        invalid=tuple(
            sorted(invalid, key=lambda item: (item.source_instance_id, item.reason))
        ),
    )


def assert_no_partition_leakage(records: Sequence[InstanceGraphRecord]) -> None:
    """Fail when one parent identifier appears in more than one role."""
    roles_by_instance: dict[str, set[str]] = {}
    for record in records:
        roles_by_instance.setdefault(record.source_instance_id, set()).add(record.role)
    leaked = sorted(
        instance_id
        for instance_id, roles in roles_by_instance.items()
        if len(roles) != 1
    )
    if leaked:
        raise InstanceDatasetContractError(
            "parent-instance leakage across roles: " + ", ".join(leaked)
        )
