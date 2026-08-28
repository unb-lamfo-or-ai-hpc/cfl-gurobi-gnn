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
]
