"""Build the multi-parent Gurobi-authoritative four-arm graph dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from cfl_gnn.analysis.scalable_graph_dataset import (
    ScalableGraphDatasetError,
    audit_scalable_graph_dataset,
)
from cfl_gnn.graph.gurobi_graph_artifact import GurobiGraphError
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.derived_graphs import DerivedGraphError, SourceInput
from cfl_gnn.pipelines.gurobi_derived_training_dataset import (
    GurobiDerivedTrainingError,
    PLAN_NAME,
    execute_dataset,
    prepare_dataset,
)
from cfl_gnn.training.gasse_reconnected import GasseTrainingError, write_json


class ScalableDatasetBuildError(RuntimeError):
    """Raised when the augmentation audit cannot authorize graph building."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ScalableDatasetBuildError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ScalableDatasetBuildError("source index record is invalid")
                records.append(value)
    return records


def _safe_child(root: Path, value: Any) -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts:
        raise ScalableDatasetBuildError("source index contains an unsafe path")
    return root / relative


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build multi-parent Gurobi-authoritative graphs from an audited "
            "paired augmentation campaign."
        )
    )
    parser.add_argument("--augmentation_audit_dir", type=Path, required=True)
    parser.add_argument("--augmentation_run_root", type=Path, required=True)
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
        audit_root = args.augmentation_audit_dir.resolve()
        run_root = args.augmentation_run_root.resolve()
        audit = _read_json(audit_root / "scalable_augmentation_audit_report.json")
        source_index = audit_root / "derived_source_index.jsonl"
        if (
            audit.get("gate_status") != "passed"
            or audit.get("eligibility", {}).get(
                "gurobi_authoritative_graph_build_ready"
            )
            is not True
            or audit.get("source_index_sha256") != sha256_file(source_index)
        ):
            raise ScalableDatasetBuildError("augmentation audit is not admissible")
        records = _read_jsonl(source_index)
        sources = tuple(
            SourceInput(
                solver=str(record["solver"]),
                candidate_dir=_safe_child(
                    run_root, record["candidate_dir_relative_path"]
                ),
                solve_dir=_safe_child(run_root, record["solve_dir_relative_path"]),
            )
            for record in records
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
        print(f"[INFO] Plan: {args.output_dir / PLAN_NAME}")
        if args.dry_run:
            return 0
        dataset_report = execute_dataset(
            prepared,
            parent_graph_dataset_dir=args.parent_graph_dataset_dir,
            parent_collection_run_root=args.parent_collection_run_root,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
        if dataset_report.get("gate_status") != "passed":
            return 1
        analysis_report = audit_scalable_graph_dataset(
            dataset_dir=args.output_dir,
            output_dir=args.output_dir / "descriptive_analysis",
            overwrite=args.overwrite,
        )
    except (
        DerivedGraphError,
        GasseTrainingError,
        GurobiDerivedTrainingError,
        GurobiGraphError,
        OSError,
        ScalableDatasetBuildError,
        ScalableGraphDatasetError,
        TypeError,
        ValueError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2
    print(
        f"[INFO] dataset_gate=passed | analysis_gate="
        f"{analysis_report['gate_status']} | "
        f"graphs={analysis_report['summary']['structural_graphs']}"
    )
    return 0 if analysis_report["gate_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
