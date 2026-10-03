"""CLI entry point for paired serial training of the four MVP arms."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.training.mvp_arm import MvpTrainingDataError
from cfl_gnn.training.mvp_four_arm import (
    RUN_PLAN_NAME,
    MvpFourArmTrainingError,
    build_training_run_plan,
    run_four_arm_training,
    write_training_run_plan,
)


DEFAULT_EXPERIMENT_CONFIG = (
    PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
)
DEFAULT_LOADER_POLICY = (
    PROJECT_ROOT / "configs" / "training" / "mvp_four_arm_loader_v1.json"
)
DEFAULT_TRAINING_PROTOCOL = (
    PROJECT_ROOT
    / "configs"
    / "training"
    / "mvp_four_arm_training_smoke_v1.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train four independent Gasse MVP arms under paired controls."
    )
    parser.add_argument("--dataset_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument(
        "--experiment_config", type=Path, default=DEFAULT_EXPERIMENT_CONFIG
    )
    parser.add_argument("--loader_policy", type=Path, default=DEFAULT_LOADER_POLICY)
    parser.add_argument(
        "--training_protocol", type=Path, default=DEFAULT_TRAINING_PROTOCOL
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--clear_cache", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = build_parser().parse_args(argv)
    try:
        plan = build_training_run_plan(
            args.dataset_dir,
            experiment_config_path=args.experiment_config,
            loader_policy_path=args.loader_policy,
            training_protocol_path=args.training_protocol,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = args.output_dir / RUN_PLAN_NAME
        write_training_run_plan(plan_path, plan)
        print(
            f"[INFO] contract={plan['contract_sha256']} | arms=4 | "
            f"steps_per_epoch={plan['optimizer_steps_per_arm_per_epoch']}"
        )
        print("[INFO] paired initialization, prenorm, pos_weight, and validation")
        print("[INFO] held-out test graphs are not deserialized during training")
        print(f"[INFO] Plan: {plan_path}")
        if args.dry_run:
            return 0
        report = run_four_arm_training(
            plan,
            dataset_dir=args.dataset_dir,
            output_dir=args.output_dir,
            device=args.device,
            clear_cache=args.clear_cache,
            overwrite=args.overwrite,
        )
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"completed={report['execution']['arms_completed']}/4"
        )
        return 0
    except (
        FileExistsError,
        OSError,
        TypeError,
        ValueError,
        MvpTrainingDataError,
        MvpFourArmTrainingError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
