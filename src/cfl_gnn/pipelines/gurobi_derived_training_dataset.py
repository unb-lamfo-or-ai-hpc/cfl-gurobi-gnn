"""Build Gurobi-authoritative derived graphs and four Gasse training views."""

from __future__ import annotations

import gzip
import json
import os
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.gurobi_graph_artifact import (
    build_graph_artifact,
    capture_root_relaxation,
    write_root_artifact,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.derived_graphs import (
    DerivedGraphPlan,
    SourceInput,
    build_plan as build_source_plan,
)
from cfl_gnn.training.gasse_reconnected import (
    GasseTrainingError,
    ROLES,
    build_gasse_training_plan,
    canonical_sha256,
    read_json,
    write_json,
)


SCHEMA_VERSION = 1
PLAN_NAME = "gurobi_derived_training_dataset_plan.json"
REPORT_NAME = "gurobi_derived_training_dataset_report.json"
MANIFEST_NAME = "gasse_augmented_manifest.jsonl"
GRAPH_AUDIT_NAME = "per_gurobi_derived_graph_audit.jsonl"
ARM_ROOT = "arms"
SOLVERS = ("gurobi", "scip")


class GurobiDerivedTrainingError(RuntimeError):
    """Raised when the authoritative derived-data contract fails closed."""


@dataclass(frozen=True, slots=True)
class PreparedDataset:
    """Path-bearing execution state with a path-neutral persisted contract."""

    plan: dict[str, Any]
    source_plan: DerivedGraphPlan
    original_plans: Mapping[str, Mapping[str, Any]]


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def _read_gzip_json(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, TypeError, ValueError) as error:
        raise GurobiDerivedTrainingError(
            f"unreadable solution artifact: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise GurobiDerivedTrainingError("solution artifact is not an object")
    return value


def _materialize(source: Path, destination: Path, *, overwrite: bool) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not overwrite:
            raise GurobiDerivedTrainingError(
                f"output exists; use --overwrite: {destination.name}"
            )
        destination.unlink()
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy_fallback"


def prepare_dataset(
    *,
    sources: Sequence[SourceInput],
    output_dir: str | Path,
    experiment_config_path: str | Path,
    parent_manifest_path: str | Path,
    parent_graph_dataset_dir: str | Path,
    parent_collection_plan_dir: str | Path,
    parent_collection_run_root: str | Path,
    training_protocol_path: str | Path,
    allow_partial_smoke: bool = False,
    root_time_limit_seconds: float = 600.0,
) -> PreparedDataset:
    """Validate all source labels before Gurobi is imported or executed."""
    output = Path(output_dir).resolve()
    source_plan = build_source_plan(
        sources=sources,
        output_dir=output,
        config_path=Path(experiment_config_path),
        parent_manifest_path=Path(parent_manifest_path),
    )
    original_plans = {
        solver: build_gasse_training_plan(
            graph_dataset_dir=parent_graph_dataset_dir,
            parent_collection_plan_dir=parent_collection_plan_dir,
            parent_collection_run_root=parent_collection_run_root,
            protocol_path=training_protocol_path,
            label_solver=solver,
            allow_partial_smoke=allow_partial_smoke,
        )
        for solver in SOLVERS
    }
    original_mips = {
        solver: {record["mip_sha256"] for record in plan["records"]}
        for solver, plan in original_plans.items()
    }
    if original_mips["gurobi"] != original_mips["scip"]:
        raise GurobiDerivedTrainingError(
            "original solver views do not share the same MIP population"
        )
    original_train_parents = {
        solver: {
            record["parent_instance_id"]
            for record in plan["records"]
            if record["role"] == "train"
        }
        for solver, plan in original_plans.items()
    }
    derived_design = {
        solver: {
            (
                sample.parent_instance_id,
                sample.radius,
                sample.radius_fraction,
            )
            for sample in source_plan.samples
            if sample.solver == solver
        }
        for solver in SOLVERS
    }
    if derived_design["gurobi"] != derived_design["scip"]:
        raise GurobiDerivedTrainingError(
            "Gurobi and SCIP derived designs are not symmetric"
        )
    for solver in SOLVERS:
        derived_parents = {item[0] for item in derived_design[solver]}
        if not derived_parents.issubset(original_train_parents[solver]):
            raise GurobiDerivedTrainingError(
                f"{solver} derived samples lack their original training parents"
            )
    implementation_root = Path(__file__).resolve().parents[1]
    contract = {
        "schema_version": SCHEMA_VERSION,
        "dataset_variant": "gurobi_authoritative_original_and_derived_gasse_v1",
        "graph_authority": "gurobi",
        "scip_graph_construction_allowed": False,
        "graph_identity": "one_graph_per_mathematical_mip",
        "derived_label_policy": "independent_solution_of_same_derived_mip",
        "parent_label_reuse_for_descendants_allowed": False,
        "cross_solver_derived_design": "same_parent_radius_and_fraction",
        "derived_partition_policy": "train_only_inherit_parent_fold",
        "source_validation_contract_sha256": source_plan.contract_sha256,
        "original_training_contracts": {
            solver: original_plans[solver]["contract_sha256"]
            for solver in SOLVERS
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
        },
        "implementation_sha256": {
            "pipeline": sha256_file(Path(__file__)),
            "gurobi_graph_builder": sha256_file(
                implementation_root / "graph" / "gurobi_graph_artifact.py"
            ),
            "gasse_adapter": sha256_file(
                implementation_root / "training" / "gasse_reconnected.py"
            ),
        },
        "derived_samples": [
            sample.contract_payload() for sample in source_plan.samples
        ],
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    plan = {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "contract_valid": True,
        "summary": {
            "derived_graphs_planned": len(source_plan.samples),
            "derived_by_solver": dict(
                sorted(Counter(item.solver for item in source_plan.samples).items())
            ),
            "original_views": sum(
                len(plan["records"]) for plan in original_plans.values()
            ),
            "arms_planned": 4,
        },
        "next_gate": "gurobi_derived_graph_execution_and_training_views",
    }
    return PreparedDataset(plan, source_plan, original_plans)


def validate_plan(plan: Mapping[str, Any]) -> None:
    ignored = {"contract_sha256", "contract_valid", "summary", "next_gate"}
    payload = {key: value for key, value in plan.items() if key not in ignored}
    if canonical_sha256(payload) != plan.get("contract_sha256"):
        raise GurobiDerivedTrainingError("derived dataset contract hash mismatch")


def _pack_original_records(
    prepared: PreparedDataset,
    *,
    parent_graph_root: Path,
    parent_label_root: Path,
    output: Path,
    overwrite: bool,
) -> tuple[dict[str, list[dict[str, Any]]], Counter[str]]:
    storage: Counter[str] = Counter()
    by_solver: dict[str, list[dict[str, Any]]] = {}
    materialized_graphs: set[str] = set()
    materialized_roots: set[str] = set()
    for solver, plan in prepared.original_plans.items():
        records: list[dict[str, Any]] = []
        for source in plan["records"]:
            graph_destination = (
                output / "graphs" / "original" / f"{source['sample_id']}.pt"
            )
            root_destination = (
                output
                / "root_relaxations"
                / "original"
                / f"{source['sample_id']}.root.json.gz"
            )
            if source["sample_id"] not in materialized_graphs:
                storage[_materialize(
                    parent_graph_root / source["graph_relative_path"],
                    graph_destination,
                    overwrite=overwrite,
                )] += 1
                materialized_graphs.add(source["sample_id"])
            if source["sample_id"] not in materialized_roots:
                storage[_materialize(
                    parent_graph_root / source["root_relative_path"],
                    root_destination,
                    overwrite=overwrite,
                )] += 1
                materialized_roots.add(source["sample_id"])
            label_destination = (
                output
                / "labels"
                / "original"
                / solver
                / f"{source['sample_id']}.solution.json.gz"
            )
            storage[_materialize(
                parent_label_root
                / source["label_run_relative_path"]
                / source["label_file_name"],
                label_destination,
                overwrite=overwrite,
            )] += 1
            records.append(
                {
                    **source,
                    "graph_relative_path": graph_destination.relative_to(
                        output
                    ).as_posix(),
                    "root_relative_path": root_destination.relative_to(
                        output
                    ).as_posix(),
                    "label_run_relative_path": label_destination.parent.relative_to(
                        output
                    ).as_posix(),
                    "label_file_name": label_destination.name,
                    "artifact_package": "gurobi_derived_training_dataset",
                }
            )
        by_solver[solver] = records
    return by_solver, storage


def _arm_plan(
    base: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    dataset_contract_sha256: str,
    arm_id: str,
) -> dict[str, Any]:
    normalized = sorted(
        (dict(item) for item in records), key=lambda item: item["sample_id"]
    )
    parents_by_role = {
        role: sorted(
            {
                item["parent_instance_id"]
                for item in normalized
                if item["role"] == role
            }
        )
        for role in ROLES
    }
    counts = {
        role: sum(item["role"] == role for item in normalized) for role in ROLES
    }
    result = {
        **base,
        "dataset_variant": "gurobi_authoritative_original_and_derived_gasse_v1",
        "graph_dataset_contract_sha256": dataset_contract_sha256,
        "augmentation_contract_sha256": dataset_contract_sha256,
        "arm_id": arm_id,
        "records": normalized,
        "excluded_records": [],
        "partition_counts": counts,
        "parent_ids_by_role": parents_by_role,
        "allow_partial_smoke": base["allow_partial_smoke"],
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    ignored = {
        "contract_sha256",
        "contract_valid",
        "training_ready",
        "engineering_smoke_ready",
        "held_out_evaluation_ready",
        "warnings",
        "next_gate",
    }
    result["contract_sha256"] = canonical_sha256(
        {key: value for key, value in result.items() if key not in ignored}
    )
    full_ready = all(counts[role] > 0 for role in ROLES)
    result.update(
        {
            "contract_valid": True,
            "training_ready": full_ready,
            "engineering_smoke_ready": counts["train"] > 0,
            "held_out_evaluation_ready": counts["test"] > 0,
            "warnings": [] if full_ready else [
                "partial_partition_inventory_engineering_smoke_only"
            ],
            "next_gate": (
                "gasse_four_arm_training"
                if full_ready
                else "gasse_four_arm_engineering_smoke"
            ),
        }
    )
    return result


def execute_dataset(
    prepared: PreparedDataset,
    *,
    parent_graph_dataset_dir: str | Path,
    parent_collection_run_root: str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build real-root derived graphs and package four training-plan views."""
    validate_plan(prepared.plan)
    output = Path(output_dir).resolve()
    report_path = output / REPORT_NAME
    if report_path.exists() and not overwrite:
        raise GurobiDerivedTrainingError("output exists; use --overwrite")
    output.mkdir(parents=True, exist_ok=True)
    original, storage = _pack_original_records(
        prepared,
        parent_graph_root=Path(parent_graph_dataset_dir).resolve(),
        parent_label_root=Path(parent_collection_run_root).resolve(),
        output=output,
        overwrite=overwrite,
    )
    derived: dict[str, list[dict[str, Any]]] = {solver: [] for solver in SOLVERS}
    audits: list[dict[str, Any]] = []
    mip_hashes: set[str] = set()
    for specification in prepared.source_plan.samples:
        if sha256_file(specification.candidate_path) != specification.candidate_sha256:
            raise GurobiDerivedTrainingError(
                "derived candidate SHA-256 changed after planning"
            )
        if sha256_file(specification.solution_path) != specification.solution_sha256:
            raise GurobiDerivedTrainingError(
                "derived solution SHA-256 changed after planning"
            )
        solution_payload = _read_gzip_json(specification.solution_path)
        expected_source = {
            "gurobi": "independent_gurobi_optimization",
            "scip": "independent_pyscipopt_optimization",
        }[specification.solver]
        if (
            solution_payload.get("candidate_sha256")
            != specification.candidate_sha256
            or solution_payload.get("solution_source") != expected_source
        ):
            raise GurobiDerivedTrainingError(
                "derived label is not an independent solution of its candidate MIP"
            )
        if specification.candidate_sha256 in mip_hashes:
            raise GurobiDerivedTrainingError("duplicate derived mathematical MIP")
        mip_hashes.add(specification.candidate_sha256)
        root_payload = capture_root_relaxation(
            specification.candidate_path,
            expected_mip_sha256=specification.candidate_sha256,
            time_limit_seconds=prepared.plan["root_lp_contract"][
                "time_limit_seconds"
            ],
            threads=1,
            seed=42,
            presolve=0,
        )
        root_destination = (
            output
            / "root_relaxations"
            / "derived"
            / specification.solver
            / f"{specification.sample_id}.root.json.gz"
        )
        root_sha256 = write_root_artifact(root_destination, root_payload)
        label_destination = (
            output
            / "labels"
            / "derived"
            / specification.solver
            / f"{specification.sample_id}.solution.json.gz"
        )
        storage[_materialize(
            specification.solution_path, label_destination, overwrite=overwrite
        )] += 1
        graph_destination = (
            output
            / "graphs"
            / "derived"
            / specification.solver
            / f"{specification.sample_id}.pt"
        )
        metadata = {
            "sample_id": specification.sample_id,
            "source_instance_id": specification.sample_id,
            "parent_instance_id": specification.parent_instance_id,
            "category": specification.category,
            "difficulty": specification.difficulty,
            "fold": specification.fold,
            "role": "train",
            "sampling_strategy": "incumbent_local_branching",
            "label_source_solver": specification.solver,
        }
        audit = build_graph_artifact(
            mip_path=specification.candidate_path,
            mip_sha256=specification.candidate_sha256,
            solution_path=specification.solution_path,
            solution_sha256=specification.solution_sha256,
            root_payload=root_payload,
            output_path=graph_destination,
            sample_metadata=metadata,
        )
        record = {
            "sample_id": specification.sample_id,
            "parent_instance_id": specification.parent_instance_id,
            "source_instance_id": specification.sample_id,
            "category": specification.category,
            "difficulty": specification.difficulty,
            "fold": specification.fold,
            "role": "train",
            "sampling_strategy": "incumbent_local_branching",
            "mip_sha256": specification.candidate_sha256,
            "graph_relative_path": graph_destination.relative_to(output).as_posix(),
            "graph_sha256": audit["graph_sha256"],
            "root_relative_path": root_destination.relative_to(output).as_posix(),
            "root_sha256": root_sha256,
            "graph_authority": "gurobi",
            "label_solver": specification.solver,
            "label_contract_sha256": specification.derived_solve_contract_sha256,
            "label_run_relative_path": label_destination.parent.relative_to(
                output
            ).as_posix(),
            "label_file_name": label_destination.name,
            "label_sha256": specification.solution_sha256,
            "label_mip_gap_relative": specification.label_mip_gap_relative,
            "label_objective": specification.label_objective,
            "label_execution_time_seconds": (
                specification.label_execution_time_seconds
            ),
            "source_incumbent_id": specification.source_incumbent_id,
            "source_incumbent_artifact_sha256": (
                specification.source_incumbent_artifact_sha256
            ),
            "local_branching_radius": specification.radius,
            "local_branching_radius_fraction": specification.radius_fraction,
            "artifact_package": "gurobi_derived_training_dataset",
        }
        derived[specification.solver].append(record)
        audits.append(
            {
                "sample_id": specification.sample_id,
                "parent_instance_id": specification.parent_instance_id,
                "source_solver": specification.solver,
                "graph_authority": "gurobi",
                "candidate_mip_sha256": specification.candidate_sha256,
                "solution_candidate_sha256": solution_payload["candidate_sha256"],
                "independent_label_source": expected_source,
                "root_lp_capture_method": root_payload["capture_method"],
                "root_lp_zero_fallback_used": False,
                "role": "train",
                **audit,
            }
        )
    arm_plans: dict[str, dict[str, Any]] = {}
    for solver in SOLVERS:
        for augmented in (False, True):
            arm_id = f"{solver}_{'incumbent_augmented' if augmented else 'original'}"
            records = original[solver] + (derived[solver] if augmented else [])
            arm = _arm_plan(
                prepared.original_plans[solver],
                records,
                dataset_contract_sha256=prepared.plan["contract_sha256"],
                arm_id=arm_id,
            )
            arm_path = output / ARM_ROOT / arm_id / "gasse_training_plan.json"
            write_json(arm_path, arm)
            arm_plans[arm_id] = {
                "file_name": arm_path.relative_to(output).as_posix(),
                "sha256": sha256_file(arm_path),
                "records": len(records),
                "training_parents": len(arm["parent_ids_by_role"]["train"]),
            }
    manifest = sorted(
        [record for values in original.values() for record in values]
        + [record for values in derived.values() for record in values],
        key=lambda item: (item["label_solver"], item["sample_id"]),
    )
    manifest_path = output / MANIFEST_NAME
    audit_path = output / GRAPH_AUDIT_NAME
    _write_jsonl(manifest_path, manifest)
    _write_jsonl(audit_path, audits)
    passed = (
        len(audits) == len(prepared.source_plan.samples)
        and all(item["graph_authority"] == "gurobi" for item in audits)
        and all(
            item["root_lp_capture_method"]
            == "first_optimal_root_gurobi_mipnode"
            for item in audits
        )
        and all(item["root_lp_feature_exactly_encoded"] for item in audits)
        and all(item["label_variable_identity_match"] for item in audits)
        and all(item["roundtrip_readable"] for item in audits)
        and all(item["root_lp_zero_fallback_used"] is False for item in audits)
        and all(item["role"] == "train" for item in audits)
        and len(arm_plans) == 4
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": prepared.plan["contract_sha256"],
        "gate_status": "passed" if passed else "failed",
        "graph_contract": {
            "authority": "gurobi",
            "root_lp_relaxation": "first_optimal_root_gurobi_mipnode",
            "zero_fallback_allowed": False,
            "one_graph_per_mathematical_mip": True,
        },
        "label_contract": {
            "derived_solution_matches_candidate_mip_sha256": True,
            "parent_label_reuse_for_descendants": False,
            "maximum_mip_gap_relative": 0.10,
        },
        "summary": {
            "derived_graphs_written": len(audits),
            "derived_by_solver": dict(
                sorted(Counter(item["source_solver"] for item in audits).items())
            ),
            "arm_plans_written": len(arm_plans),
            "manifest_records": len(manifest),
            "storage_modes": dict(sorted(storage.items())),
        },
        "arms": arm_plans,
        "outputs": {
            MANIFEST_NAME: {"sha256": sha256_file(manifest_path)},
            GRAPH_AUDIT_NAME: {"sha256": sha256_file(audit_path)},
        },
        "eligibility": {
            "dataset_eligible": passed,
            "four_arm_training_smoke_ready": passed,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "next_gate": (
                "gasse_augmented_four_arm_training_smoke"
                if passed
                else "repair_gurobi_derived_training_dataset"
            )
        },
    }
    write_json(report_path, report)
    return report
