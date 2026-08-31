"""Reproducible dataset partitioning contracts."""

from .instance_folds import (
    CATEGORIES,
    DEFAULT_REQUIRED_ARTIFACTS,
    InstanceFold,
    InventoryRecord,
    audit_inventory,
    build_planned_manifest,
    read_manifest,
    role_for_fold,
    validate_manifest,
    write_manifest,
)
from .instance_partitions import (
    LABEL_POLICIES,
    ROLES,
    ExcludedInstance,
    InstanceDatasetAudit,
    InstanceDatasetContractError,
    InstanceGraphRecord,
    InvalidInstance,
    assert_no_partition_leakage,
    audit_instance_dataset,
)

__all__ = [
    "CATEGORIES",
    "DEFAULT_REQUIRED_ARTIFACTS",
    "InstanceFold",
    "InventoryRecord",
    "audit_inventory",
    "build_planned_manifest",
    "read_manifest",
    "role_for_fold",
    "validate_manifest",
    "write_manifest",
    "LABEL_POLICIES",
    "ROLES",
    "ExcludedInstance",
    "InstanceDatasetAudit",
    "InstanceDatasetContractError",
    "InstanceGraphRecord",
    "InvalidInstance",
    "assert_no_partition_leakage",
    "audit_instance_dataset",
]
