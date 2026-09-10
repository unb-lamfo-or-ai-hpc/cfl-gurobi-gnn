"""CLI for the Gurobi-authoritative derived Gasse dataset."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from cfl_gnn.graph.gurobi_graph_artifact import GurobiGraphError
from cfl_gnn.pipelines.derived_graphs import DerivedGraphError, SourceInput
from cfl_gnn.pipelines.gurobi_derived_training_dataset import (
    GurobiDerivedTrainingError,
    PLAN_NAME,
    REPORT_NAME,
    execute_dataset,
    prepare_dataset,
)
from cfl_gnn.training.gasse_reconnected import GasseTrainingError, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build Gurobi-authoritative graphs and four Gasse training views "
            "for independently labelled local-branching MIPs."
        )
    )
    parser.add_argument(
        "--source",
        nargs=3,
        action="append",
        metavar=("SOLVER", "CANDIDATE_DIR", "SOLVE_DIR"),
        required=True,
    )
    parser.add_argument("--parent_graph_dataset_dir", type=Path, required=True)
    parser.add_argument("--parent_collection_plan_dir", type=Path, required=True)
    parser.add_argument("--parent_collection_run_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument(
        "--experiment_config",
        type=Path,
        default=Path("configs/experiments/mvp_partial_v1.json"),
    )
    parser.add_argument(
        "--parent_manifest",
        type=Path,
        default=Path("configs/splits/cfl_90_seed42_folds.csv"),
    )
    parser.add_argument(
        "--training_protocol",
        type=Path,
        default=Path("configs/training/gasse_reconnected_v1.json"),
    )
    parser.add_argument("--root_time_limit", type=float, default=600.0)
    parser.add_argument("--allow_partial_smoke", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        sources = tuple(
            SourceInput(
                solver=str(raw[0]).lower(),
                candidate_dir=Path(raw[1]).resolve(),
                solve_dir=Path(raw[2]).resolve(),
            )
            for raw in args.source
        )
        prepared = prepare_dataset(
            sources=sources,
            output_dir=args.output_dir,
            experiment_config_path=args.experiment_config,
            parent_manifest_path=args.parent_manifest,
            parent_graph_dataset_dir=args.parent_graph_dataset_dir,
            parent_collection_plan_dir=args.parent_collection_plan_dir,
            parent_collection_run_root=args.parent_collection_run_root,
            training_protocol_path=args.training_protocol,
            allow_partial_smoke=args.allow_partial_smoke,
            root_time_limit_seconds=args.root_time_limit,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(args.output_dir / PLAN_NAME, prepared.plan)
        print(
            f"[INFO] contract={prepared.plan['contract_sha256']} | "
            f"derived={prepared.plan['summary']['derived_graphs_planned']} | "
            "authority=gurobi"
        )
        print("[INFO] root_lp=real_gurobi_mipnode | zero_fallback=false")
        print(f"[INFO] Plan: {args.output_dir / PLAN_NAME}")
        if args.dry_run:
            return 0
        report = execute_dataset(
            prepared,
            parent_graph_dataset_dir=args.parent_graph_dataset_dir,
            parent_collection_run_root=args.parent_collection_run_root,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except (
        DerivedGraphError,
        GasseTrainingError,
        GurobiDerivedTrainingError,
        GurobiGraphError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2
    print(
        f"[INFO] gate={report['gate_status']} | "
        f"derived={report['summary']['derived_graphs_written']} | arms=4"
    )
    print(f"[INFO] Report: {args.output_dir / REPORT_NAME}")
    return 0 if report["gate_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
