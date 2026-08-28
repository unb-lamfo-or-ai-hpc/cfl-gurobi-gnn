"""Deterministic, instance-grouped folds for the CFL baseline.

The canonical study contains 30 parent instances in each MILPBench CFL
category.  Fold assignment is made from the parent instance identifier, never
from a generated graph.  Future incumbents or search-tree subproblems must
therefore inherit their parent's ``source_instance_id`` and fold.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


CATEGORIES = {
    "CFL_easy_instance": "easy",
    "CFL_medium_instance": "medium",
    "CFL_hard_instance": "hard",
}

DEFAULT_REQUIRED_ARTIFACTS = (
    "original_features.pickle.gz",
    "incumbents.parquet",
    "metadata.json",
)


@dataclass(frozen=True, slots=True)
class InstanceFold:
    """Fold assignment for one original MILPBench parent instance."""

    source_instance_id: str
    category: str
    difficulty: str
    fold: int


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    """Availability of the artifacts required for one planned instance."""

    entry: InstanceFold
    missing_artifacts: tuple[str, ...]

    @property
    def available(self) -> bool:
        return not self.missing_artifacts


def _rank(seed: int, source_instance_id: str) -> bytes:
    """Return a stable pseudo-random rank independent of Python hash state."""
    payload = f"cfl-instance-folds-v1|{seed}|{source_instance_id}".encode("utf-8")
    return hashlib.sha256(payload).digest()


def build_planned_manifest(
    *, seed: int = 42, n_splits: int = 5, instances_per_category: int = 30
) -> list[InstanceFold]:
    """Build the canonical balanced fold plan for all expected instances."""
    if n_splits < 3:
        raise ValueError("n_splits must be at least 3 (train, validation, test)")
    if instances_per_category <= 0:
        raise ValueError("instances_per_category must be positive")
    if instances_per_category % n_splits:
        raise ValueError(
            "instances_per_category must be divisible by n_splits for exact balance"
        )

    entries: list[InstanceFold] = []
    for category, difficulty in CATEGORIES.items():
        instance_ids = [f"{category}_{index}" for index in range(instances_per_category)]
        ranked_ids = sorted(instance_ids, key=lambda item: (_rank(seed, item), item))
        fold_by_id = {
            source_instance_id: position % n_splits
            for position, source_instance_id in enumerate(ranked_ids)
        }
        entries.extend(
            InstanceFold(
                source_instance_id=source_instance_id,
                category=category,
                difficulty=difficulty,
                fold=fold_by_id[source_instance_id],
            )
            for source_instance_id in instance_ids
        )

    validate_manifest(
        entries,
        n_splits=n_splits,
        instances_per_category=instances_per_category,
        require_complete=True,
    )
    return entries


def validate_manifest(
    entries: Sequence[InstanceFold],
    *,
    n_splits: int = 5,
    instances_per_category: int = 30,
    require_complete: bool = True,
) -> None:
    """Validate identifiers, categories, folds, uniqueness, and exact balance."""
    seen: set[str] = set()
    for entry in entries:
        if entry.source_instance_id in seen:
            raise ValueError(f"duplicate source_instance_id: {entry.source_instance_id}")
        seen.add(entry.source_instance_id)

        expected_difficulty = CATEGORIES.get(entry.category)
        if expected_difficulty is None:
            raise ValueError(f"unknown category: {entry.category}")
        if entry.difficulty != expected_difficulty:
            raise ValueError(
                f"difficulty mismatch for {entry.source_instance_id}: "
                f"{entry.difficulty} != {expected_difficulty}"
            )
        if not 0 <= entry.fold < n_splits:
            raise ValueError(f"fold out of range for {entry.source_instance_id}")
        if not entry.source_instance_id.startswith(f"{entry.category}_"):
            raise ValueError(f"instance/category mismatch: {entry.source_instance_id}")

    if not require_complete:
        return

    expected_ids = {
        f"{category}_{index}"
        for category in CATEGORIES
        for index in range(instances_per_category)
    }
    if seen != expected_ids:
        missing = sorted(expected_ids - seen)
        unexpected = sorted(seen - expected_ids)
        raise ValueError(
            f"manifest population mismatch; missing={missing}, unexpected={unexpected}"
        )

    expected_per_fold = instances_per_category // n_splits
    for category in CATEGORIES:
        fold_counts = Counter(
            entry.fold for entry in entries if entry.category == category
        )
        expected = {fold: expected_per_fold for fold in range(n_splits)}
        if dict(fold_counts) != expected:
            raise ValueError(f"unbalanced folds for {category}: {dict(fold_counts)}")


def role_for_fold(fold: int, rotation: int, *, n_splits: int = 5) -> str:
    """Map one assigned fold to train/validation/test for a rotation."""
    if not 0 <= fold < n_splits:
        raise ValueError("fold is outside the configured range")
    if not 0 <= rotation < n_splits:
        raise ValueError("rotation is outside the configured range")
    if fold == rotation:
        return "test"
    if fold == (rotation + 1) % n_splits:
        return "validation"
    return "train"


def audit_inventory(
    inventory_root: str | Path,
    entries: Iterable[InstanceFold],
    *,
    required_artifacts: Sequence[str] = DEFAULT_REQUIRED_ARTIFACTS,
) -> list[InventoryRecord]:
    """Check which planned parent instances currently have usable artifacts."""
    root = Path(inventory_root)
    records: list[InventoryRecord] = []

    for entry in entries:
        instance_dir = root / entry.category / entry.source_instance_id
        if not instance_dir.is_dir():
            missing = ("<instance-directory>",)
        else:
            missing = tuple(
                artifact
                for artifact in required_artifacts
                if not (instance_dir / artifact).is_file()
                or (instance_dir / artifact).stat().st_size == 0
            )
        records.append(InventoryRecord(entry=entry, missing_artifacts=missing))

    return records


def write_manifest(
    output_path: str | Path,
    entries: Iterable[InstanceFold],
    *,
    rotation: int | None = None,
    n_splits: int = 5,
    population_status: str | None = None,
) -> None:
    """Write canonical fold assignments, optionally including one rotation role."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source_instance_id", "category", "difficulty", "fold"]
    if rotation is not None:
        fieldnames.append("role")
    if population_status is not None:
        fieldnames.append("population_status")

    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            row: dict[str, str | int] = {
                "source_instance_id": entry.source_instance_id,
                "category": entry.category,
                "difficulty": entry.difficulty,
                "fold": entry.fold,
            }
            if rotation is not None:
                row["role"] = role_for_fold(
                    entry.fold, rotation, n_splits=n_splits
                )
            if population_status is not None:
                row["population_status"] = population_status
            writer.writerow(row)


def read_manifest(input_path: str | Path) -> list[InstanceFold]:
    """Read a fold manifest; an optional derived ``role`` column is ignored."""
    path = Path(input_path)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"source_instance_id", "category", "difficulty", "fold"}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError(f"manifest is missing required columns: {sorted(required)}")
        return [
            InstanceFold(
                source_instance_id=row["source_instance_id"],
                category=row["category"],
                difficulty=row["difficulty"],
                fold=int(row["fold"]),
            )
            for row in reader
        ]
