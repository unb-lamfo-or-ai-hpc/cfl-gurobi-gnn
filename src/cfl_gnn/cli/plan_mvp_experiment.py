"""CLI for validating the four-arm MVP contract before solver execution."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cfl_gnn.experiments.mvp_contract import (
    ContractError,
    build_mvp_plan,
    load_experiment_config,
    read_sample_manifest,
    write_json,
)
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.splits.instance_folds import read_manifest, validate_manifest


DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and materialize the solver x augmentation MVP plan without "
            "importing Gurobi, PySCIPOpt, PyTorch, or deserializing graphs."
        )
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--sample_manifest",
        type=Path,
        help=(
            "Optional JSONL inventory emitted by future dataset builders. Omit it "
            "to validate the pre-generation contract."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("mvp_experiment_plan.json"),
    )
    parser.add_argument(
        "--strict_inventory",
        action="store_true",
        help="Fail unless at least one eligible sample exists in every MVP arm.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_experiment_config(args.config)
        parents = read_manifest(args.manifest)
        validate_manifest(parents)
        samples = (
            read_sample_manifest(args.sample_manifest)
            if args.sample_manifest is not None
            else ()
        )
        plan = build_mvp_plan(config, parents, samples)
    except (ContractError, OSError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 2

    write_json(args.output, plan)
    print(
        f"[INFO] contract={plan['contract_sha256']} | "
        f"samples={plan['samples_eligible']}/{plan['samples_declared']} | "
        f"invalid={plan['samples_invalid']}"
    )
    print(
        "[INFO] gap sensitivity="
        + ",".join(
            f"<={100 * value:g}%"
            for value in plan["gap_policy"]["sensitivity_thresholds_relative"]
        )
    )
    print("[INFO] derived samples are train-only and inherit the parent fold")
    print(f"[INFO] Plan: {args.output.resolve()}")

    if not plan["contract_valid"]:
        return 1
    if args.strict_inventory and any(
        sum(arm["partitions"].values()) == 0 for arm in plan["arms"].values()
    ):
        print("[ERROR] strict inventory requires an eligible sample in every arm")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
