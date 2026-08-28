"""Dependency-free tests for the instance-level partitioning contract."""

from collections import Counter, defaultdict
from pathlib import Path

from cfl_gnn.splits.instance_folds import (
    CATEGORIES,
    DEFAULT_REQUIRED_ARTIFACTS,
    audit_inventory,
    build_planned_manifest,
    read_manifest,
    role_for_fold,
    validate_manifest,
    write_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_MANIFEST = (
    PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
)


def test_canonical_plan_is_exactly_balanced() -> None:
    entries = build_planned_manifest()
    assert len(entries) == 90
    assert len({entry.source_instance_id for entry in entries}) == 90
    for category in CATEGORIES:
        category_entries = [entry for entry in entries if entry.category == category]
        assert len(category_entries) == 30
        assert Counter(entry.fold for entry in category_entries) == {
            fold: 6 for fold in range(5)
        }


def test_five_rotations_have_no_leakage_and_complete_role_coverage() -> None:
    entries = build_planned_manifest()
    roles_by_instance = defaultdict(list)

    for rotation in range(5):
        for category in CATEGORIES:
            counts = Counter(
                role_for_fold(entry.fold, rotation)
                for entry in entries
                if entry.category == category
            )
            assert counts == {"train": 18, "validation": 6, "test": 6}

        for entry in entries:
            roles_by_instance[entry.source_instance_id].append(
                role_for_fold(entry.fold, rotation)
            )

    for roles in roles_by_instance.values():
        assert Counter(roles) == {"train": 3, "validation": 1, "test": 1}


def test_assignment_is_reproducible_and_seed_sensitive() -> None:
    first = build_planned_manifest(seed=42)
    second = build_planned_manifest(seed=42)
    alternative = build_planned_manifest(seed=43)
    assert first == second
    assert [entry.fold for entry in first] != [entry.fold for entry in alternative]


def test_partial_inventory_keeps_canonical_assignments(tmp_path: Path) -> None:
    entries = build_planned_manifest()
    selected = entries[:3] + entries[30:32]
    for entry in selected:
        instance_dir = tmp_path / entry.category / entry.source_instance_id
        instance_dir.mkdir(parents=True)
        for artifact in DEFAULT_REQUIRED_ARTIFACTS:
            (instance_dir / artifact).write_bytes(b"fixture")

    incomplete = entries[60]
    incomplete_dir = tmp_path / incomplete.category / incomplete.source_instance_id
    incomplete_dir.mkdir(parents=True)
    (incomplete_dir / DEFAULT_REQUIRED_ARTIFACTS[0]).write_bytes(b"fixture")

    records = audit_inventory(tmp_path, entries)
    available = [record.entry for record in records if record.available]
    assert available == selected
    assert {entry.fold for entry in available} == {entry.fold for entry in selected}

    incomplete_record = next(
        record
        for record in records
        if record.entry.source_instance_id == incomplete.source_instance_id
    )
    assert set(incomplete_record.missing_artifacts) == set(
        DEFAULT_REQUIRED_ARTIFACTS[1:]
    )


def test_manifest_round_trip_and_committed_plan(tmp_path: Path) -> None:
    generated = build_planned_manifest()
    output = tmp_path / "folds.csv"
    write_manifest(
        output,
        generated,
        rotation=0,
        population_status="development_partial",
    )
    loaded = read_manifest(output)
    validate_manifest(loaded)
    assert loaded == generated
    assert "population_status" in output.read_text(encoding="utf-8").splitlines()[0]

    committed = read_manifest(CANONICAL_MANIFEST)
    validate_manifest(committed)
    assert committed == generated
