"""Dependency-free training contract for the parent-instance baseline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cfl_gnn.splits.instance_folds import CATEGORIES, read_manifest
from cfl_gnn.splits.instance_partitions import (
    InstanceDatasetAudit,
    InstanceGraphRecord,
    assert_no_partition_leakage,
    audit_instance_dataset,
)


class InstanceTrainingPlanError(ValueError):
    """Raised when an audited inventory is unsafe for the requested run."""


@dataclass(frozen=True, slots=True)
class InstanceTrainingPlan:
    """Immutable, path-free description of one serial training run."""

    audit: InstanceDatasetAudit
    development_only: bool

    def records_for_role(self, role: str) -> tuple[InstanceGraphRecord, ...]:
        return self.audit.records_for_role(role)

    def _contract_payload(self) -> dict[str, Any]:
        partitions: dict[str, list[dict[str, Any]]] = {}
        for role in ("train", "validation", "test"):
            partitions[role] = [
                {
                    "source_instance_id": record.source_instance_id,
                    "difficulty": record.difficulty,
                    "fold": record.fold,
                    "label_source": record.label_source,
                    "mip_gap": record.mip_gap,
                    "mip_gap_band": record.mip_gap_band,
                }
                for record in self.records_for_role(role)
            ]
        return {
            "schema_version": 1,
            "dataset_variant": "gurobi_parent_instance",
            "rotation": self.audit.rotation,
            "label_policy": self.audit.label_policy,
            "development_only": self.development_only,
            "partitions": partitions,
        }

    @property
    def contract_sha256(self) -> str:
        encoded = json.dumps(
            self._contract_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def scientific_reporting_eligible(self) -> bool:
        return (
            not self.development_only
            and self.audit.discovered_graphs == self.audit.manifest_size
            and len(self.audit.eligible) == self.audit.manifest_size
            and not self.audit.excluded
            and not self.audit.invalid
        )

    def to_summary(self) -> dict[str, Any]:
        """Return a JSON-safe report with no machine-specific paths."""
        summary = self.audit.to_summary()
        warnings = list(summary["warnings"])
        if self.development_only:
            warnings.append("development_only_training")
        summary.update(
            {
                "training_plan_schema_version": 1,
                "contract_sha256": self.contract_sha256,
                "development_only": self.development_only,
                "scientific_reporting_eligible": self.scientific_reporting_eligible,
                "test_partition_usage": "held_out_not_loaded_during_training",
                "warnings": warnings,
            }
        )
        return summary


def validate_instance_training_audit(
    audit: InstanceDatasetAudit,
    *,
    development_only: bool,
) -> InstanceTrainingPlan:
    """Promote a dataset audit to a training plan or fail closed."""
    if audit.invalid:
        first = audit.invalid[0]
        raise InstanceTrainingPlanError(
            f"invalid graph contract for {first.source_instance_id}: {first.reason}"
        )
    if not audit.contract_valid:
        raise InstanceTrainingPlanError(
            "every run requires non-empty train, validation, and test partitions"
        )
    if audit.label_policy != "optimal_only" and not development_only:
        raise InstanceTrainingPlanError(
            "non-optimal labels require an explicit development-only run"
        )

    assert_no_partition_leakage(audit.eligible)
    ids_by_role = {
        role: {record.source_instance_id for record in audit.records_for_role(role)}
        for role in ("train", "validation", "test")
    }
    if (
        ids_by_role["train"] & ids_by_role["validation"]
        or ids_by_role["train"] & ids_by_role["test"]
        or ids_by_role["validation"] & ids_by_role["test"]
    ):
        raise InstanceTrainingPlanError("parent-instance leakage across partitions")

    if not development_only:
        if audit.discovered_graphs != audit.manifest_size or audit.missing:
            raise InstanceTrainingPlanError(
                "partial inventory requires an explicit development-only run"
            )
        if audit.excluded or len(audit.eligible) != audit.manifest_size:
            raise InstanceTrainingPlanError(
                "the scientific run requires an eligible label for every parent"
            )
        present_difficulties = {record.difficulty for record in audit.eligible}
        required_difficulties = set(CATEGORIES.values())
        if present_difficulties != required_difficulties:
            raise InstanceTrainingPlanError(
                "the scientific run requires easy, medium, and hard instances"
            )

    return InstanceTrainingPlan(
        audit=audit,
        development_only=development_only,
    )


def build_instance_training_plan(
    dataset_root: str | Path,
    manifest_path: str | Path,
    *,
    rotation: int,
    label_policy: str = "optimal_only",
    development_only: bool = False,
) -> InstanceTrainingPlan:
    """Audit hashes and provenance, then construct one immutable run plan."""
    manifest = read_manifest(manifest_path)
    audit = audit_instance_dataset(
        dataset_root,
        manifest,
        rotation=rotation,
        label_policy=label_policy,
        verify_graph_hashes=True,
    )
    return validate_instance_training_audit(
        audit,
        development_only=development_only,
    )


def write_instance_training_plan(
    output_path: str | Path,
    plan: InstanceTrainingPlan,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan.to_summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

