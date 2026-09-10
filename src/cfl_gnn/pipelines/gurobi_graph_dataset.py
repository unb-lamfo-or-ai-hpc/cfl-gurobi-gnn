"""Build one Gurobi-authoritative graph per original parent MIP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.analysis.graph_clustering import cluster_graph_manifest
from cfl_gnn.analysis.graph_statistics import analyze_graph_manifest
from cfl_gnn.graph.gurobi_graph_artifact import (
    GurobiGraphError,
    build_graph_artifact,
    canonical_sha256,
    capture_root_relaxation,
    compare_root_relaxations,
    load_legacy_root_vector,
    write_root_artifact,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.parent_collection_task import validate_campaign_plan
from cfl_gnn.pipelines.parent_population import PLAN_NAME
from cfl_gnn.pipelines.parent_solutions import report_name


SCHEMA_VERSION = 1
GRAPH_PLAN_NAME = "gurobi_graph_dataset_plan.json"
GRAPH_REPORT_NAME = "gurobi_graph_dataset_report.json"
GRAPH_MANIFEST_NAME = "gurobi_graph_manifest.jsonl"
GRAPH_AUDIT_NAME = "per_graph_audit.jsonl"
GRAPH_CONTRACT_FIELDS = (
    "schema_version",
    "dataset_variant",
    "parent_collection_contract_sha256",
    "graph_identity",
    "incumbent_role",
    "graph_authority",
    "scip_graph_construction_allowed",
    "objective_sense",
    "implementation_sha256",
    "root_lp_contract",
    "specifications",
)


class GurobiGraphDatasetError(RuntimeError):
    """Raised when the graph-dataset contract is missing or inconsistent."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise GurobiGraphDatasetError(
            f"unreadable JSON artifact: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise GurobiGraphDatasetError(f"expected JSON object: {path.name}")
    return value


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
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def _select_tasks(
    plan: Mapping[str, Any], instances: Sequence[str] | None
) -> list[dict[str, Any]]:
    requested = set(instances or [])
    tasks = [
        dict(task)
        for task in plan.get("tasks", [])
        if task.get("solver") == "gurobi"
    ]
    if requested:
        known = {str(task["source_instance_id"]) for task in tasks}
        unknown = sorted(requested - known)
        if unknown:
            raise GurobiGraphDatasetError(
                "requested parents are absent from the Gurobi task manifest: "
                + ",".join(unknown)
            )
        tasks = [task for task in tasks if task["source_instance_id"] in requested]
    if not tasks:
        raise GurobiGraphDatasetError("no Gurobi parent task was selected")
    return sorted(tasks, key=lambda item: str(item["source_instance_id"]))


def build_graph_plan(
    *,
    parent_collection_plan_dir: str | Path,
    parent_collection_run_root: str | Path,
    base_source_dir: str | Path,
    output_dir: str | Path,
    legacy_intermediate_dir: str | Path | None = None,
    instances: Sequence[str] | None = None,
    require_legacy_parity: bool = False,
    parity_tolerance: float = 1e-8,
    root_time_limit_seconds: float = 600.0,
) -> dict[str, Any]:
    """Resolve hash-bound Gurobi graph specifications without running Gurobi."""
    plan_root = Path(parent_collection_plan_dir).resolve()
    run_root = Path(parent_collection_run_root).resolve()
    source_root = Path(base_source_dir).resolve()
    legacy_root = (
        Path(legacy_intermediate_dir).resolve() if legacy_intermediate_dir else None
    )
    parent_plan = _read_json(plan_root / PLAN_NAME)
    try:
        validate_campaign_plan(parent_plan)
    except Exception as error:
        raise GurobiGraphDatasetError(
            "parent collection contract is invalid"
        ) from error
    specifications: list[dict[str, Any]] = []
    mip_hashes: set[str] = set()
    for task in _select_tasks(parent_plan, instances):
        instance_id = str(task["source_instance_id"])
        source = source_root / str(task["parent_mip_relative_path"])
        if not source.is_file() or sha256_file(source) != task["parent_mip_sha256"]:
            raise GurobiGraphDatasetError(
                f"parent MIP is missing or changed: {instance_id}"
            )
        if task["parent_mip_sha256"] in mip_hashes:
            raise GurobiGraphDatasetError("duplicate mathematical MIP in graph plan")
        mip_hashes.add(str(task["parent_mip_sha256"]))
        run_relative = Path(str(task["run_dir_relative_path"]))
        report_path = run_root / run_relative / report_name("gurobi")
        report = _read_json(report_path)
        if (
            report.get("gate_status") not in {"passed", "inconclusive"}
            or report.get("eligibility", {}).get("label_eligible") is not True
            or report.get("parent", {}).get("sha256") != task["parent_mip_sha256"]
        ):
            raise GurobiGraphDatasetError(
                f"ineligible Gurobi parent label: {instance_id}"
            )
        solution_descriptor = report.get("artifacts", {}).get("solution", {})
        solution_path = (
            run_root
            / run_relative
            / str(solution_descriptor.get("file_name", ""))
        )
        solution_sha256 = str(solution_descriptor.get("sha256", ""))
        if not solution_path.is_file() or sha256_file(solution_path) != solution_sha256:
            raise GurobiGraphDatasetError(
                f"Gurobi solution artifact changed: {instance_id}"
            )
        legacy_relative = None
        legacy_sha256 = None
        if legacy_root is not None:
            candidate = (
                legacy_root
                / str(task["category"])
                / instance_id
                / "node_relaxations.parquet"
            )
            if candidate.is_file() and candidate.stat().st_size > 0:
                legacy_relative = candidate.relative_to(legacy_root).as_posix()
                legacy_sha256 = sha256_file(candidate)
        if require_legacy_parity and legacy_relative is None:
            raise GurobiGraphDatasetError(
                f"legacy root parity artifact is required: {instance_id}"
            )
        specifications.append(
            {
                "sample_id": instance_id,
                "source_instance_id": instance_id,
                "category": str(task["category"]),
                "difficulty": str(task["difficulty"]),
                "fold": int(task["fold"]),
                "role": str(task["role"]),
                "sampling_strategy": "original",
                "graph_authority": "gurobi",
                "label_source_solver": "gurobi",
                "mip_relative_path": str(task["parent_mip_relative_path"]),
                "mip_sha256": str(task["parent_mip_sha256"]),
                "solution_run_relative_path": run_relative.as_posix(),
                "solution_file_name": solution_path.name,
                "solution_sha256": solution_sha256,
                "parent_solve_contract_sha256": str(report["contract_sha256"]),
                "legacy_root_relative_path": legacy_relative,
                "legacy_root_sha256": legacy_sha256,
                "graph_relative_path": (
                    Path("graphs") / str(task["category"]) / f"{instance_id}.pt"
                ).as_posix(),
                "root_relative_path": (
                    Path("root_relaxations") / str(task["category"])
                    / f"{instance_id}.root.json.gz"
                ).as_posix(),
                "provenance_relative_path": (
                    Path("provenance") / str(task["category"])
                    / f"{instance_id}.provenance.json"
                ).as_posix(),
            }
        )
    contract_payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_variant": "gurobi_authoritative_parent_graphs_v1",
        "parent_collection_contract_sha256": parent_plan["contract_sha256"],
        "graph_identity": "one_graph_per_mathematical_mip",
        "incumbent_role": "label_and_provenance_only",
        "graph_authority": "gurobi",
        "scip_graph_construction_allowed": False,
        "objective_sense": "MINIMIZE",
        "implementation_sha256": {
            "graph_builder": sha256_file(
                Path(__file__).resolve().parents[1]
                / "graph"
                / "gurobi_graph_artifact.py"
            ),
            "graph_statistics": sha256_file(
                Path(__file__).resolve().parents[1]
                / "analysis"
                / "graph_statistics.py"
            ),
            "graph_clustering": sha256_file(
                Path(__file__).resolve().parents[1]
                / "analysis"
                / "graph_clustering.py"
            ),
        },
        "root_lp_contract": {
            "method": "first_optimal_root_gurobi_mipnode",
            "zero_fallback_allowed": False,
            "continuous_relaxation_fallback_allowed": False,
            "presolve": 0,
            "threads": 1,
            "seed": 42,
            "node_limit": 1,
            "time_limit_seconds": float(root_time_limit_seconds),
            "legacy_parity_required": bool(require_legacy_parity),
            "legacy_parity_tolerance": float(parity_tolerance),
        },
        "specifications": specifications,
    }
    return {
        **contract_payload,
        "contract_sha256": canonical_sha256(contract_payload),
        "summary": {
            "graphs_planned": len(specifications),
            "unique_mip_sha256": len(mip_hashes),
            "legacy_parity_artifacts": sum(
                item["legacy_root_relative_path"] is not None
                for item in specifications
            ),
        },
        "eligibility": {
            "execution_ready": True,
            "development_only": parent_plan["eligibility"]["development_only"],
            "scientific_reporting_eligible": False,
        },
    }


def validate_graph_plan(plan: Mapping[str, Any]) -> None:
    """Fail closed when a persisted graph plan was modified after planning."""
    try:
        contract_payload = {field: plan[field] for field in GRAPH_CONTRACT_FIELDS}
    except (KeyError, TypeError) as error:
        raise GurobiGraphDatasetError("graph plan contract is incomplete") from error
    if canonical_sha256(contract_payload) != plan.get("contract_sha256"):
        raise GurobiGraphDatasetError("graph plan contract hash mismatch")


def execute_graph_plan(
    plan: Mapping[str, Any],
    *,
    parent_collection_run_root: str | Path,
    base_source_dir: str | Path,
    output_dir: str | Path,
    legacy_intermediate_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Execute an in-memory graph plan and run statistics plus clustering."""
    validate_graph_plan(plan)
    run_root = Path(parent_collection_run_root).resolve()
    source_root = Path(base_source_dir).resolve()
    output = Path(output_dir).resolve()
    legacy_root = (
        Path(legacy_intermediate_dir).resolve() if legacy_intermediate_dir else None
    )
    manifest: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for specification in plan["specifications"]:
        source = source_root / specification["mip_relative_path"]
        solution = (
            run_root
            / specification["solution_run_relative_path"]
            / specification["solution_file_name"]
        )
        root_payload = capture_root_relaxation(
            source,
            expected_mip_sha256=specification["mip_sha256"],
            time_limit_seconds=plan["root_lp_contract"]["time_limit_seconds"],
            threads=plan["root_lp_contract"]["threads"],
            seed=plan["root_lp_contract"]["seed"],
            presolve=plan["root_lp_contract"]["presolve"],
        )
        parity = {
            "status": "not_available",
            "reason_code": "legacy_root_relaxation_not_available",
        }
        if specification["legacy_root_relative_path"] is not None:
            legacy_path = legacy_root / specification["legacy_root_relative_path"]
            if sha256_file(legacy_path) != specification["legacy_root_sha256"]:
                raise GurobiGraphDatasetError("legacy parity artifact changed")
            legacy, legacy_provenance = load_legacy_root_vector(
                legacy_path,
                expected_variables=root_payload["variable_count"],
            )
            parity = {
                **compare_root_relaxations(
                    root_payload["relaxation_vector"],
                    legacy,
                    tolerance=plan["root_lp_contract"]["legacy_parity_tolerance"],
                ),
                **legacy_provenance,
            }
        if (
            plan["root_lp_contract"]["legacy_parity_required"]
            and parity["status"] != "passed"
        ):
            raise GurobiGraphDatasetError("required legacy root parity failed")
        root_payload = {**root_payload, "legacy_parity": parity}
        root_path = output / specification["root_relative_path"]
        root_sha256 = write_root_artifact(root_path, root_payload)
        graph_path = output / specification["graph_relative_path"]
        graph_audit = build_graph_artifact(
            mip_path=source,
            mip_sha256=specification["mip_sha256"],
            solution_path=solution,
            solution_sha256=specification["solution_sha256"],
            root_payload=root_payload,
            output_path=graph_path,
            sample_metadata=specification,
        )
        provenance = {
            "schema_version": SCHEMA_VERSION,
            "graph_dataset_contract_sha256": plan["contract_sha256"],
            **specification,
            "root_artifact_sha256": root_sha256,
            "root_capture_method": root_payload["capture_method"],
            "root_vector_sha256": root_payload["vector_sha256"],
            "legacy_parity": parity,
            "graph_audit": graph_audit,
        }
        provenance_path = output / specification["provenance_relative_path"]
        _write_json(provenance_path, provenance)
        record = {
            "schema_version": SCHEMA_VERSION,
            "sample_id": specification["sample_id"],
            "source_instance_id": specification["source_instance_id"],
            "category": specification["category"],
            "difficulty": specification["difficulty"],
            "fold": specification["fold"],
            "role": specification["role"],
            "sampling_strategy": specification["sampling_strategy"],
            "graph_authority": "gurobi",
            "label_source_solver": "gurobi",
            "mip_sha256": specification["mip_sha256"],
            "graph_relative_path": specification["graph_relative_path"],
            "graph_sha256": graph_audit["graph_sha256"],
            "root_relative_path": specification["root_relative_path"],
            "root_sha256": root_sha256,
            "root_vector_sha256": root_payload["vector_sha256"],
            "provenance_relative_path": specification["provenance_relative_path"],
            "provenance_sha256": sha256_file(provenance_path),
        }
        manifest.append(record)
        audits.append(
            {
                "sample_id": specification["sample_id"],
                **graph_audit,
                "legacy_parity": parity,
            }
        )
    manifest_path = output / GRAPH_MANIFEST_NAME
    audit_path = output / GRAPH_AUDIT_NAME
    _write_jsonl(manifest_path, manifest)
    _write_jsonl(audit_path, audits)
    analysis_dir = output / "analysis"
    statistics_report = analyze_graph_manifest(
        manifest_path=manifest_path,
        graph_root=output,
        output_dir=analysis_dir / "statistics",
        overwrite=True,
    )
    clustering_report = cluster_graph_manifest(
        manifest_path=manifest_path,
        graph_root=output,
        output_dir=analysis_dir / "clustering",
        overwrite=True,
    )
    parity_required = plan["root_lp_contract"]["legacy_parity_required"]
    parity_passed = all(
        record["legacy_parity"]["status"] == "passed" for record in audits
    )
    gate_passed = (
        len(manifest) == plan["summary"]["graphs_planned"]
        and len({record["mip_sha256"] for record in manifest}) == len(manifest)
        and all(record["root_lp_feature_exactly_encoded"] for record in audits)
        and (not parity_required or parity_passed)
        and statistics_report["gate_status"] == "passed"
        and clustering_report["gate_status"] == "passed"
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan["contract_sha256"],
        "gate_status": "passed" if gate_passed else "failed",
        "graph_contract": {
            "identity": "one_graph_per_mathematical_mip",
            "authority": "gurobi",
            "label_source_solver": "gurobi",
            "root_lp_relaxation": "first_optimal_root_gurobi_mipnode",
            "zero_fallback_allowed": False,
        },
        "summary": {
            "graphs_planned": plan["summary"]["graphs_planned"],
            "graphs_written": len(manifest),
            "unique_mip_sha256": len({record["mip_sha256"] for record in manifest}),
            "root_features_exactly_encoded": sum(
                record["root_lp_feature_exactly_encoded"] for record in audits
            ),
            "legacy_parity_passed": sum(
                record["legacy_parity"]["status"] == "passed" for record in audits
            ),
        },
        "outputs": {
            GRAPH_MANIFEST_NAME: {"sha256": sha256_file(manifest_path)},
            GRAPH_AUDIT_NAME: {"sha256": sha256_file(audit_path)},
            "statistics_report": statistics_report,
            "clustering_report": clustering_report,
        },
        "eligibility": {
            "dataset_eligible": gate_passed,
            "development_only": plan["eligibility"]["development_only"],
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": (
                "gurobi_root_graph_pipeline_audited"
                if gate_passed
                else "gurobi_root_graph_pipeline_failed"
            ),
            "next_gate": (
                "gasse_training_pipeline_reconnection"
                if gate_passed
                else "repair_gurobi_root_graph_pipeline"
            ),
        },
    }
    _write_json(output / GRAPH_REPORT_NAME, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build one Gurobi-authoritative graph per parent MIP."
    )
    parser.add_argument("--parent_collection_plan_dir", type=Path, required=True)
    parser.add_argument("--parent_collection_run_root", type=Path, required=True)
    parser.add_argument("--base_source_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--legacy_intermediate_dir", type=Path)
    parser.add_argument("--instances", nargs="*")
    parser.add_argument("--require_legacy_parity", action="store_true")
    parser.add_argument("--parity_tolerance", type=float, default=1e-8)
    parser.add_argument("--root_time_limit", type=float, default=600.0)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output_dir.resolve()
    plan_path = output / GRAPH_PLAN_NAME
    report_path = output / GRAPH_REPORT_NAME
    try:
        if not args.overwrite and (
            plan_path.exists() or (not args.dry_run and report_path.exists())
        ):
            raise GurobiGraphDatasetError("output exists; use --overwrite")
        plan = build_graph_plan(
            parent_collection_plan_dir=args.parent_collection_plan_dir,
            parent_collection_run_root=args.parent_collection_run_root,
            base_source_dir=args.base_source_dir,
            output_dir=output,
            legacy_intermediate_dir=args.legacy_intermediate_dir,
            instances=args.instances,
            require_legacy_parity=args.require_legacy_parity,
            parity_tolerance=args.parity_tolerance,
            root_time_limit_seconds=args.root_time_limit,
        )
        _write_json(plan_path, plan)
        print(
            f"[INFO] contract={plan['contract_sha256']} | "
            f"graphs={plan['summary']['graphs_planned']} | authority=gurobi"
        )
        print("[INFO] root_lp=first_optimal_root_gurobi_mipnode | zero_fallback=false")
        print(f"[INFO] Plan: {plan_path}")
        if args.dry_run:
            return 0
        report = execute_graph_plan(
            plan,
            parent_collection_run_root=args.parent_collection_run_root,
            base_source_dir=args.base_source_dir,
            output_dir=output,
            legacy_intermediate_dir=args.legacy_intermediate_dir,
        )
    except (
        OSError,
        TypeError,
        ValueError,
        GurobiGraphError,
        GurobiGraphDatasetError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2
    print(
        f"[INFO] gate={report['gate_status']} | "
        f"graphs={report['summary']['graphs_written']}"
    )
    print(f"[INFO] Report: {report_path}")
    return 0 if report["gate_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
