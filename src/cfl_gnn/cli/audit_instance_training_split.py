"""Audit fold-aware parent-instance partitions without loading PyG graphs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.splits.instance_folds import read_manifest
from cfl_gnn.splits.instance_partitions import (
    LABEL_POLICIES,
    ROLES,
    assert_no_partition_leakage,
    audit_instance_dataset,
)


logger = logging.getLogger(__name__)
DEFAULT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit canonical train/validation/test partitions for the Gurobi "
            "parent-instance graph baseline."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--base_pyg_dir",
        type=Path,
        default=Path(
            "/raid/vrcelestino/data/cfl-gurobi-gnn/data/"
            "bipartite_graphs/instance_baseline"
        ),
    )
    parser.add_argument("--rotation", type=int, choices=range(5), default=0)
    parser.add_argument(
        "--label_policy",
        choices=LABEL_POLICIES,
        default="optimal_only",
    )
    parser.add_argument(
        "--skip_graph_hashes",
        action="store_true",
        help="Skip graph-byte SHA-256 verification for a faster metadata-only audit.",
    )
    parser.add_argument(
        "--strict_inventory",
        action="store_true",
        help="Return nonzero unless all 90 planned graph files are present.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional JSON report path; defaults under --base_pyg_dir.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    manifest = read_manifest(args.manifest)
    audit = audit_instance_dataset(
        args.base_pyg_dir,
        manifest,
        rotation=args.rotation,
        label_policy=args.label_policy,
        verify_graph_hashes=not args.skip_graph_hashes,
    )
    assert_no_partition_leakage(audit.eligible)
    summary = audit.to_summary()

    report_path = args.report or (
        args.base_pyg_dir
        / f"instance_partition_audit_rotation_{args.rotation}_{args.label_policy}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)

    logger.info(
        "inventory=%s/%s | valid=%s | eligible=%s | excluded=%s | invalid=%s",
        audit.discovered_graphs,
        audit.manifest_size,
        audit.valid_graphs,
        len(audit.eligible),
        len(audit.excluded),
        len(audit.invalid),
    )
    for role in ROLES:
        partition = summary["partitions"][role]
        logger.info(
            "%s=%s | by_difficulty=%s",
            role,
            partition["total"],
            partition["by_difficulty"],
        )
    for warning in summary["warnings"]:
        logger.warning(warning)
    logger.info("Report: %s", report_path)

    if audit.invalid or not audit.contract_valid:
        return 1
    if args.strict_inventory and audit.discovered_graphs != audit.manifest_size:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
