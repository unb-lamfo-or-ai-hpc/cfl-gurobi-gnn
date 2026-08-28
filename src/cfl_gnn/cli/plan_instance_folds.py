"""Plan reproducible CFL folds and audit the currently available inventory."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.splits.instance_folds import (
    CATEGORIES,
    DEFAULT_REQUIRED_ARTIFACTS,
    audit_inventory,
    build_planned_manifest,
    read_manifest,
    role_for_fold,
    write_manifest,
)


DEFAULT_PLAN = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"


def _print_role_counts(entries, rotation: int, n_splits: int) -> None:
    counts = Counter(
        (entry.category, role_for_fold(entry.fold, rotation, n_splits=n_splits))
        for entry in entries
    )
    for category in CATEGORIES:
        print(
            f"  {category}: train={counts[(category, 'train')]} "
            f"validation={counts[(category, 'validation')]} "
            f"test={counts[(category, 'test')]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create the canonical 90-instance fold plan and optionally audit "
            "the subset whose collected artifacts are currently available."
        )
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n_splits", type=int, default=5)
    parser.add_argument("--instances_per_category", type=int, default=30)
    parser.add_argument("--rotation", type=int, default=0)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow replacing an existing plan whose assignments differ.",
    )
    parser.add_argument(
        "--inventory_root",
        type=Path,
        help="Root containing <category>/<source_instance_id>/ artifact folders.",
    )
    parser.add_argument(
        "--required_artifacts",
        nargs="+",
        default=list(DEFAULT_REQUIRED_ARTIFACTS),
    )
    parser.add_argument(
        "--available_output",
        type=Path,
        help="Optional derived CSV containing only currently available instances.",
    )
    parser.add_argument(
        "--strict_inventory",
        action="store_true",
        help="Return a non-zero status unless all planned artifacts are available.",
    )
    args = parser.parse_args(argv)

    if args.available_output and not args.inventory_root:
        parser.error("--available_output requires --inventory_root")
    if not 0 <= args.rotation < args.n_splits:
        parser.error("--rotation must be in [0, n_splits)")

    entries = build_planned_manifest(
        seed=args.seed,
        n_splits=args.n_splits,
        instances_per_category=args.instances_per_category,
    )
    if args.output.exists() and not args.force:
        try:
            existing_entries = read_manifest(args.output)
        except (OSError, ValueError) as error:
            parser.error(f"existing --output is invalid; use --force to replace: {error}")
        if existing_entries != entries:
            parser.error("existing --output differs; choose another path or use --force")
        print(f"Canonical plan verified: {args.output} ({len(entries)} instances)")
    else:
        write_manifest(args.output, entries)
        print(f"Canonical plan written: {args.output} ({len(entries)} instances)")
    print(f"Rotation {args.rotation} planned roles:")
    _print_role_counts(entries, args.rotation, args.n_splits)

    if not args.inventory_root:
        return 0

    records = audit_inventory(
        args.inventory_root,
        entries,
        required_artifacts=args.required_artifacts,
    )
    available = [record.entry for record in records if record.available]
    missing = [record for record in records if not record.available]

    print(
        f"Available inventory: {len(available)}/{len(entries)}; "
        f"missing or incomplete: {len(missing)}"
    )
    print(f"Rotation {args.rotation} available roles (development only):")
    _print_role_counts(available, args.rotation, args.n_splits)

    if missing:
        print("First missing/incomplete instances:")
        for record in missing[:10]:
            reason = ", ".join(record.missing_artifacts)
            print(f"  {record.entry.source_instance_id}: {reason}")

    if args.available_output:
        write_manifest(
            args.available_output,
            available,
            rotation=args.rotation,
            n_splits=args.n_splits,
            population_status="complete" if not missing else "development_partial",
        )
        print(f"Available subset: {args.available_output}")

    return 1 if args.strict_inventory and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
