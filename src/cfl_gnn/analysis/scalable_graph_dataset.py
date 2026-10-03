"""Audit a scalable Gurobi-authoritative graph dataset descriptively."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.analysis.graph_clustering import (
    REPORT_NAME as CLUSTER_REPORT_NAME,
    GraphClusteringError,
    cluster_graph_manifest,
)
from cfl_gnn.analysis.graph_statistics import (
    REPORT_NAME as STATISTICS_REPORT_NAME,
    GraphStatisticsError,
    analyze_graph_manifest,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.scalable_augmentation import canonical_sha256


SCHEMA_VERSION = 1
STRUCTURAL_MANIFEST_NAME = "gurobi_structural_graph_manifest.jsonl"
REPORT_NAME = "scalable_graph_dataset_audit_report.json"


class ScalableGraphDatasetError(RuntimeError):
    """Raised when the final graph dataset is incomplete or inconsistent."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise ScalableGraphDatasetError(
            f"unreadable JSON artifact: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise ScalableGraphDatasetError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise TypeError("manifest record is not an object")
                    records.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise ScalableGraphDatasetError(
            f"unreadable JSONL artifact: {path.name}"
        ) from error
    return records


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(record, sort_keys=True, allow_nan=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def _structural_records(
    records: Sequence[Mapping[str, Any]], dataset_root: Path
) -> list[dict[str, Any]]:
    """Deduplicate solver-specific label views without losing graph identity."""
    by_mip: dict[str, dict[str, Any]] = {}
    for raw in records:
        record = dict(raw)
        mip_sha = str(record.get("mip_sha256", ""))
        graph_relative = str(record.get("graph_relative_path", ""))
        graph_sha = str(record.get("graph_sha256", ""))
        if not mip_sha or not graph_relative or not graph_sha:
            raise ScalableGraphDatasetError("graph manifest record is incomplete")
        graph_path = dataset_root / graph_relative
        if not graph_path.is_file() or sha256_file(graph_path) != graph_sha:
            raise ScalableGraphDatasetError("graph artifact SHA-256 mismatch")
        previous = by_mip.get(mip_sha)
        if previous is not None:
            if previous["graph_sha256"] != graph_sha:
                raise ScalableGraphDatasetError(
                    "one mathematical MIP maps to conflicting graph artifacts"
                )
            if (
                previous.get("label_solver") != "gurobi"
                and record.get("label_solver") == "gurobi"
            ):
                by_mip[mip_sha] = record
            continue
        by_mip[mip_sha] = record
    result = sorted(by_mip.values(), key=lambda item: str(item["sample_id"]))
    if not result or len({item["sample_id"] for item in result}) != len(result):
        raise ScalableGraphDatasetError("structural graph identities are not unique")
    return result


def audit_scalable_graph_dataset(
    *,
    dataset_dir: str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    dataset = Path(dataset_dir).resolve()
    output = Path(output_dir).resolve()
    report_path = output / REPORT_NAME
    if report_path.exists() and not overwrite:
        raise ScalableGraphDatasetError("audit output exists; use --overwrite")
    dataset_report = _read_json(
        dataset / "gurobi_derived_training_dataset_report.json"
    )
    source_manifest = dataset / "gasse_augmented_manifest.jsonl"
    source_records = _read_jsonl(source_manifest)
    if (
        dataset_report.get("gate_status") != "passed"
        or dataset_report.get("graph_contract", {}).get("authority") != "gurobi"
        or dataset_report.get("eligibility", {}).get("dataset_eligible") is not True
        or dataset_report.get("outputs", {})
        .get("gasse_augmented_manifest.jsonl", {})
        .get("sha256")
        != sha256_file(source_manifest)
    ):
        raise ScalableGraphDatasetError("source graph dataset is not admissible")
    structural = _structural_records(source_records, dataset)
    output.mkdir(parents=True, exist_ok=True)
    structural_path = output / STRUCTURAL_MANIFEST_NAME
    _write_jsonl(structural_path, structural)
    statistics_dir = output / "statistics"
    clustering_dir = output / "clustering"
    try:
        statistics = analyze_graph_manifest(
            manifest_path=structural_path,
            graph_root=dataset,
            output_dir=statistics_dir,
            overwrite=overwrite,
        )
        clustering = cluster_graph_manifest(
            manifest_path=structural_path,
            graph_root=dataset,
            output_dir=clustering_dir,
            overwrite=overwrite,
        )
    except (GraphClusteringError, GraphStatisticsError) as error:
        raise ScalableGraphDatasetError(
            "graph statistics or clustering failed"
        ) from error
    passed = (
        statistics.get("gate_status") == "passed"
        and clustering.get("gate_status") == "passed"
        and statistics.get("summary", {}).get("graphs") == len(structural)
        and clustering.get("summary", {}).get("graphs") == len(structural)
    )
    contract = {
        "schema_version": SCHEMA_VERSION,
        "source_dataset_contract_sha256": dataset_report["contract_sha256"],
        "source_manifest_sha256": sha256_file(source_manifest),
        "structural_manifest_sha256": sha256_file(structural_path),
        "graph_authority": "gurobi",
        "graph_identity": "one_graph_per_mathematical_mip",
        "statistics_report_sha256": sha256_file(
            statistics_dir / STATISTICS_REPORT_NAME
        ),
        "clustering_report_sha256": sha256_file(
            clustering_dir / CLUSTER_REPORT_NAME
        ),
    }
    report = {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "probe_completed": True,
        "gate_status": "passed" if passed else "failed",
        "summary": {
            "label_views": len(source_records),
            "structural_graphs": len(structural),
            "duplicate_label_views_removed": len(source_records) - len(structural),
            "graphs_by_sampling_strategy": dict(
                sorted(
                    Counter(
                        item["sampling_strategy"] for item in structural
                    ).items()
                )
            ),
            "derived_graphs_by_label_solver": dict(
                sorted(
                    Counter(
                        item["label_solver"]
                        for item in structural
                        if item["sampling_strategy"]
                        == "incumbent_local_branching"
                    ).items()
                )
            ),
        },
        "outputs": {
            STRUCTURAL_MANIFEST_NAME: {
                "sha256": contract["structural_manifest_sha256"]
            },
            f"statistics/{STATISTICS_REPORT_NAME}": {
                "sha256": contract["statistics_report_sha256"]
            },
            f"clustering/{CLUSTER_REPORT_NAME}": {
                "sha256": contract["clustering_report_sha256"]
            },
        },
        "eligibility": {
            "descriptive_graph_analysis_complete": passed,
            "development_only": dataset_report.get("eligibility", {}).get(
                "development_only", True
            ),
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "next_gate": (
                "four_arm_gasse_training_and_held_out_evaluation"
                if passed
                else "repair_graph_statistics_or_clustering"
            )
        },
    }
    _write_json(report_path, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit scalable graphs and run statistics plus clustering."
    )
    parser.add_argument("--dataset_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_scalable_graph_dataset(
            dataset_dir=args.dataset_dir,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except (OSError, TypeError, ValueError, ScalableGraphDatasetError) as error:
        print(f"[ERROR] {error}")
        return 2
    print(
        f"[INFO] gate={report['gate_status']} | "
        f"graphs={report['summary']['structural_graphs']}"
    )
    print(f"[INFO] Report: {Path(args.output_dir).resolve() / REPORT_NAME}")
    return 0 if report["gate_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
