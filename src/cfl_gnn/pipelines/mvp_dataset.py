"""Build original graphs and compose the four MVP dataset arms.

This stage consumes independently solved original parents from both solvers and
the audited derived-graph fragment produced by PR #28.  It never solves a MIP.
All graph encoding goes through :func:`build_graph_artifact`, so original and
derived samples share the exact feature schema and zero root-LP ablation.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cfl_gnn.experiments.mvp_contract import (
    build_mvp_plan,
    load_experiment_config,
    read_sample_manifest,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.pipelines.derived_graphs import (
    DerivedGraphError,
    GRAPH_FEATURE_SCHEMA,
    build_graph_artifact,
)
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold


SCHEMA_VERSION = 1
DATASET_VARIANT = "mvp_four_arm_partial_dataset"
PLAN_NAME = "mvp_dataset_composition_plan.json"
REPORT_NAME = "mvp_dataset_composition_report.json"
MANIFEST_NAME = "mvp_sample_manifest.jsonl"
AUDIT_NAME = "per_original_graph_audit.jsonl"
REFERENCE_NAME = "evaluation_reference_manifest.jsonl"
ARM_DIR = "arms"
SOLVERS = ("gurobi", "scip")
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
DEFAULT_PARENT_MANIFEST = (
    PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
)


class MvpDatasetError(RuntimeError):
    """Raised when original graph or four-arm lineage fails closed."""


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


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
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise MvpDatasetError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise MvpDatasetError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise TypeError("record is not an object")
                    records.append(item)
    except (OSError, ValueError, TypeError) as error:
        raise MvpDatasetError(f"invalid JSONL artifact: {path.name}") from error
    return records


def _read_gzip_json(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError, TypeError) as error:
        raise MvpDatasetError(f"unreadable solution: {path.name}") from error
    if not isinstance(value, dict):
        raise MvpDatasetError("solution artifact must contain an object")
    return value


def _finite(value: Any, *, field: str, nonnegative: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise MvpDatasetError(f"{field} must be numeric") from error
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        raise MvpDatasetError(f"{field} must be finite")
    return result


def _find_artifact(run_dir: Path, names: Sequence[str], *, field: str) -> Path:
    matches = [
        run_dir / name for name in dict.fromkeys(names) if (run_dir / name).is_file()
    ]
    if len(matches) != 1:
        raise MvpDatasetError(f"expected one {field} in {run_dir.name}")
    return matches[0]


def _safe_child(root: Path, name: Any, *, field: str) -> Path:
    raw = str(name)
    relative = Path(raw)
    if not raw or relative.is_absolute() or relative.name != raw:
        raise MvpDatasetError(f"unsafe {field} file name")
    return root / relative


@dataclass(frozen=True, slots=True)
class ParentRunInput:
    solver: str
    run_dir: Path


@dataclass(frozen=True, slots=True)
class OriginalGraphSpec:
    solver: str
    sample_id: str
    parent_instance_id: str
    category: str
    difficulty: str
    fold: int
    role: str
    candidate_path: Path
    candidate_sha256: str
    solution_path: Path
    solution_sha256: str
    parent_solve_contract_sha256: str
    experiment_contract_sha256: str
    label_objective: float
    label_mip_gap_relative: float
    label_mip_gap_percent: float
    label_execution_time_seconds: float

    @property
    def arm_id(self) -> str:
        return f"{self.solver}_original"

    @property
    def sampling_strategy(self) -> str:
        return "original"

    def contract_payload(self) -> dict[str, Any]:
        return {
            "solver": self.solver,
            "sample_id": self.sample_id,
            "parent_instance_id": self.parent_instance_id,
            "category": self.category,
            "difficulty": self.difficulty,
            "fold": self.fold,
            "role": self.role,
            "parent_mip": {
                "file_name": self.candidate_path.name,
                "sha256": self.candidate_sha256,
            },
            "solution": {
                "file_name": self.solution_path.name,
                "sha256": self.solution_sha256,
            },
            "parent_solve_contract_sha256": self.parent_solve_contract_sha256,
            "label": {
                "objective": self.label_objective,
                "mip_gap_relative": self.label_mip_gap_relative,
                "mip_gap_percent": self.label_mip_gap_percent,
                "execution_time_seconds": self.label_execution_time_seconds,
            },
        }


@dataclass(frozen=True, slots=True)
class DatasetPlan:
    output_dir: Path
    derived_graph_dir: Path
    derived_manifest_sha256: str
    experiment_contract_sha256: str
    originals: tuple[OriginalGraphSpec, ...]
    derived_records: tuple[dict[str, Any], ...]

    @property
    def contract_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": DATASET_VARIANT,
            "experiment_contract_sha256": self.experiment_contract_sha256,
            "experiment_stage": "engineering_four_arm_dataset_composition",
            "objective_sense": "MINIMIZE",
            "graph_builder": "cfl_gnn.graph.build_dataset.build_heterodata",
            "graph_feature_schema": GRAPH_FEATURE_SCHEMA,
            "root_lp_relaxation_policy": "zero_ablation_for_all_mvp_graphs",
            "parent_weighting": "equal_parent_mass",
            "validation_test_original_only": True,
            "originals": [item.contract_payload() for item in self.originals],
            "derived_manifest": {
                "file_name": MANIFEST_NAME,
                "sha256": self.derived_manifest_sha256,
                "records": len(self.derived_records),
            },
            "eligibility": {
                "development_only": True,
                "dataset_eligible": False,
                "scientific_reporting_eligible": False,
            },
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    def to_summary(self) -> dict[str, Any]:
        return {
            **self.contract_payload,
            "contract_sha256": self.contract_sha256,
            "original_count": len(self.originals),
            "derived_count": len(self.derived_records),
        }


def _load_original(
    source: ParentRunInput,
    *,
    base_source_dir: Path,
    experiment_contract_sha256: str,
    parent_index: Mapping[str, tuple[str, int, str, str]],
    maximum_gap: float,
) -> OriginalGraphSpec:
    if source.solver not in SOLVERS:
        raise MvpDatasetError(f"unknown solver: {source.solver}")
    plan_path = _find_artifact(
        source.run_dir,
        (f"{source.solver}_parent_solve_plan.json", "scip_parent_solve_plan.json"),
        field="parent solve plan",
    )
    report_path = _find_artifact(
        source.run_dir,
        (f"{source.solver}_parent_solve_report.json", "scip_parent_solve_report.json"),
        field="parent solve report",
    )
    plan = _read_json(plan_path)
    report = _read_json(report_path)
    if plan.get("contract_sha256") != report.get("contract_sha256"):
        raise MvpDatasetError("parent solve plan/report contract mismatch")
    if plan.get("experiment_contract_sha256") != experiment_contract_sha256:
        raise MvpDatasetError("parent solve uses another experiment contract")
    if report.get("probe_completed") is not True:
        raise MvpDatasetError("parent solve did not complete")
    if report.get("eligibility", {}).get("label_eligible") is not True:
        raise MvpDatasetError("parent label is not eligible")
    if not all(report.get("checks", {}).values()):
        raise MvpDatasetError("parent solve audit contains a failed check")
    solver_contract = plan.get("solver_contract", {})
    if solver_contract.get("solver") != source.solver:
        raise MvpDatasetError("parent solve belongs to another solver arm")
    parent = report.get("parent", {})
    parent_id = str(parent.get("source_instance_id"))
    try:
        role, fold, category, difficulty = parent_index[parent_id]
    except KeyError as error:
        raise MvpDatasetError(f"unknown parent instance: {parent_id}") from error
    if (
        int(parent.get("fold", -1)) != fold
        or parent.get("category") != category
        or parent.get("difficulty") != difficulty
        or parent.get("role") != role
    ):
        raise MvpDatasetError(
            "parent metadata differs from the canonical fold manifest"
        )
    candidate = _safe_child(
        base_source_dir / category / "LP",
        parent.get("file_name"),
        field="parent MIP",
    )
    if not candidate.is_file() or sha256_file(candidate) != parent.get("sha256"):
        raise MvpDatasetError(f"original parent SHA-256 mismatch: {parent_id}")
    solution_info = report.get("artifacts", {}).get("solution", {})
    solution = _safe_child(
        source.run_dir,
        solution_info.get("file_name"),
        field="parent solution",
    )
    if not solution.is_file() or sha256_file(solution) != solution_info.get("sha256"):
        raise MvpDatasetError(f"parent solution SHA-256 mismatch: {parent_id}")
    payload = _read_gzip_json(solution)
    if payload.get("candidate_sha256") != parent.get("sha256"):
        raise MvpDatasetError("parent solution is linked to another model")
    solve = report.get("solve", {})
    if (
        str(solve.get("original_objective_sense")).lower() != "maximize"
        or str(solve.get("objective_sense")).lower() != "minimize"
    ):
        raise MvpDatasetError("parent objective-sense normalization is not auditable")
    gap = _finite(solve.get("mip_gap_relative"), field="label gap", nonnegative=True)
    gap_percent = _finite(
        solve.get("mip_gap_percent"), field="label gap percent", nonnegative=True
    )
    if gap > maximum_gap + 1e-12 or not math.isclose(
        gap_percent, 100.0 * gap, rel_tol=1e-9, abs_tol=1e-8
    ):
        raise MvpDatasetError("parent label violates the gap policy")
    objective = _finite(solve.get("solution_objective"), field="label objective")
    if not math.isclose(
        objective,
        _finite(payload.get("solution_objective"), field="solution objective"),
        rel_tol=1e-8,
        abs_tol=1e-8,
    ):
        raise MvpDatasetError("parent report and solution objectives disagree")
    return OriginalGraphSpec(
        solver=source.solver,
        sample_id=f"{parent_id}__{source.solver}__original",
        parent_instance_id=parent_id,
        category=category,
        difficulty=difficulty,
        fold=fold,
        role=role,
        candidate_path=candidate,
        candidate_sha256=str(parent["sha256"]),
        solution_path=solution,
        solution_sha256=str(solution_info["sha256"]),
        parent_solve_contract_sha256=str(report["contract_sha256"]),
        experiment_contract_sha256=experiment_contract_sha256,
        label_objective=objective,
        label_mip_gap_relative=gap,
        label_mip_gap_percent=gap_percent,
        label_execution_time_seconds=_finite(
            solve.get("execution_time_seconds"),
            field="label execution time",
            nonnegative=True,
        ),
    )


def _safe_derived_graph(root: Path, relative: Any) -> Path:
    path = Path(str(relative))
    if path.is_absolute() or ".." in path.parts:
        raise MvpDatasetError("derived graph path is unsafe")
    resolved_root = root.resolve()
    resolved = (root / path).resolve()
    if resolved_root not in resolved.parents:
        raise MvpDatasetError("derived graph escapes its artifact root")
    return resolved


def build_plan(
    *,
    parent_runs: Sequence[ParentRunInput],
    derived_graph_dir: str | Path,
    base_source_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path,
    parent_manifest_path: str | Path,
) -> DatasetPlan:
    config = load_experiment_config(config_path)
    parents = read_manifest(parent_manifest_path)
    parent_index = {
        item.source_instance_id: (
            role_for_fold(item.fold, config.rotation),
            item.fold,
            item.category,
            item.difficulty,
        )
        for item in parents
    }
    if not parent_runs:
        raise MvpDatasetError("at least one parent run per solver is required")
    originals = tuple(
        _load_original(
            source,
            base_source_dir=Path(base_source_dir),
            experiment_contract_sha256=config.contract_sha256,
            parent_index=parent_index,
            maximum_gap=config.gap_policy.maximum_admissible_relative_gap,
        )
        for source in parent_runs
    )
    keys = [(item.solver, item.parent_instance_id) for item in originals]
    if len(keys) != len(set(keys)):
        raise MvpDatasetError("duplicate original parent run")
    parent_sets = {
        solver: {item.parent_instance_id for item in originals if item.solver == solver}
        for solver in SOLVERS
    }
    if not parent_sets["gurobi"] or parent_sets["gurobi"] != parent_sets["scip"]:
        raise MvpDatasetError("Gurobi and SCIP original parent sets must match")
    derived_root = Path(derived_graph_dir).resolve()
    derived_manifest = derived_root / MANIFEST_NAME
    derived_manifest_sha256 = sha256_file(derived_manifest)
    derived_report = _read_json(derived_root / "mvp_derived_graph_report.json")
    if (
        derived_report.get("gate_status") != "passed"
        or derived_report.get("eligibility", {}).get("dataset_eligible") is not True
        or derived_report.get("experiment_contract_sha256")
        != config.contract_sha256
        or derived_report.get("outputs", {}).get("sample_manifest_sha256")
        != derived_manifest_sha256
    ):
        raise MvpDatasetError("derived graph report is not admissible")
    derived_records = tuple(_read_jsonl(derived_manifest))
    parsed = read_sample_manifest(derived_manifest)
    if len(parsed) != len(derived_records) or not derived_records:
        raise MvpDatasetError("derived manifest is empty or invalid")
    for record in derived_records:
        if record.get("sampling_strategy") != "incumbent_local_branching":
            raise MvpDatasetError("derived manifest contains an original sample")
        sample_id = str(record.get("sample_id"))
        if Path(sample_id).name != sample_id:
            raise MvpDatasetError("derived sample identifier is unsafe")
        graph = _safe_derived_graph(derived_root, record.get("graph_path"))
        if not graph.is_file() or sha256_file(graph) != record.get("graph_sha256"):
            raise MvpDatasetError("derived graph SHA-256 mismatch")
        provenance = (
            derived_root
            / "provenance"
            / str(record.get("solver"))
            / f"{record.get('sample_id')}.provenance.json"
        )
        provenance_payload = _read_json(provenance)
        if (
            provenance_payload.get("eligibility", {}).get("dataset_eligible")
            is not True
            or provenance_payload.get("sample", {}).get("sample_id")
            != record.get("sample_id")
            or provenance_payload.get("graph", {}).get("graph_sha256")
            != record.get("graph_sha256")
        ):
            raise MvpDatasetError("derived graph provenance is not admissible")
        if record.get("parent_instance_id") not in parent_sets[
            str(record.get("solver"))
        ]:
            raise MvpDatasetError("derived graph has no matched original parent")
    return DatasetPlan(
        output_dir=Path(output_dir).resolve(),
        derived_graph_dir=derived_root,
        derived_manifest_sha256=derived_manifest_sha256,
        experiment_contract_sha256=config.contract_sha256,
        originals=tuple(sorted(originals, key=lambda item: item.sample_id)),
        derived_records=tuple(
            sorted(derived_records, key=lambda item: item["sample_id"])
        ),
    )


def _original_manifest_record(
    spec: OriginalGraphSpec, output_path: Path, audit: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "sample_id": spec.sample_id,
        "parent_instance_id": spec.parent_instance_id,
        "category": spec.category,
        "difficulty": spec.difficulty,
        "fold": spec.fold,
        "solver": spec.solver,
        "sampling_strategy": "original",
        "graph_path": output_path.as_posix(),
        "graph_sha256": audit["graph_sha256"],
        "label_source": spec.solution_path.name,
        "label_solution_sha256": spec.solution_sha256,
        "label_objective": spec.label_objective,
        "label_mip_gap_relative": spec.label_mip_gap_relative,
        "label_mip_gap_percent": spec.label_mip_gap_percent,
        "label_execution_time_seconds": spec.label_execution_time_seconds,
        "source_incumbent_id": None,
        "source_incumbent_artifact_sha256": None,
        "source_incumbent_objective": None,
        "source_incumbent_mip_gap_relative": None,
        "source_incumbent_mip_gap_percent": None,
        "source_incumbent_execution_time_seconds": None,
        "local_branching_radius": None,
        "local_branching_radius_fraction": None,
    }


def _materialize_derived_graph(
    source: Path, destination: Path, *, overwrite: bool
) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not overwrite:
            raise FileExistsError(f"output exists: {destination}")
        destination.unlink()
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy_fallback"


def _compose_arm_records(
    inventory: Sequence[dict[str, Any]], parent_roles: Mapping[str, str]
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for solver in SOLVERS:
        originals = [
            item
            for item in inventory
            if item["solver"] == solver and item["sampling_strategy"] == "original"
        ]
        derived = [
            item
            for item in inventory
            if item["solver"] == solver
            and item["sampling_strategy"] == "incumbent_local_branching"
        ]
        for augmented in (False, True):
            arm_id = f"{solver}_{'incumbent_augmented' if augmented else 'original'}"
            members = originals + (derived if augmented else [])
            by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in members:
                by_parent[item["parent_instance_id"]].append(item)
            records: list[dict[str, Any]] = []
            for parent_id, samples in sorted(by_parent.items()):
                role = parent_roles[parent_id]
                if role != "train" and any(
                    item["sampling_strategy"] != "original" for item in samples
                ):
                    raise MvpDatasetError(
                        "validation/test arm contains a derived sample"
                    )
                weight = 1.0 / len(samples) if role == "train" else 1.0
                for item in sorted(samples, key=lambda value: value["sample_id"]):
                    records.append(
                        {
                            **item,
                            "arm_id": arm_id,
                            "role": role,
                            "sample_weight": weight,
                            "weighting_policy": "equal_parent_mass",
                        }
                    )
            result[arm_id] = records
    return result


def run_composition(
    plan: DatasetPlan,
    *,
    config_path: str | Path,
    parent_manifest_path: str | Path,
    overwrite: bool,
    graph_builder: Callable[[Any, Path], dict[str, Any]] = build_graph_artifact,
) -> dict[str, Any]:
    config = load_experiment_config(config_path)
    parents = read_manifest(parent_manifest_path)
    parent_roles = {
        item.source_instance_id: role_for_fold(item.fold, config.rotation)
        for item in parents
    }
    if sha256_file(plan.derived_graph_dir / MANIFEST_NAME) != (
        plan.derived_manifest_sha256
    ):
        raise MvpDatasetError("derived manifest changed after planning")
    existing = (
        [path for path in plan.output_dir.iterdir() if path.name != PLAN_NAME]
        if plan.output_dir.exists()
        else []
    )
    if existing and not overwrite:
        raise FileExistsError("output directory is not empty; use --overwrite")
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    original_records: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    structures: dict[str, dict[str, str]] = defaultdict(dict)
    for spec in plan.originals:
        relative = Path("graphs") / "original" / spec.solver / f"{spec.sample_id}.pt"
        audit = graph_builder(spec, plan.output_dir / relative)
        if (
            audit.get("roundtrip_readable") is not True
            or audit.get("label_variable_identity_match") is not True
            or audit.get("input_objective_sense") != "MAXIMIZE"
            or audit.get("effective_objective_sense") != "MINIMIZE"
            or audit.get("objective_sense_override_applied") is not True
            or audit.get("graph_sha256")
            != sha256_file(plan.output_dir / relative)
        ):
            raise MvpDatasetError(f"original graph audit failed: {spec.sample_id}")
        structures[spec.parent_instance_id][spec.solver] = str(
            audit["structural_graph_sha256"]
        )
        record = _original_manifest_record(spec, relative, audit)
        original_records.append(record)
        sidecar = {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": DATASET_VARIANT,
            "sample": record,
            "parent_mip_sha256": spec.candidate_sha256,
            "parent_solve_contract_sha256": spec.parent_solve_contract_sha256,
            "graph_generation_contract_sha256": plan.contract_sha256,
            "graph_feature_schema": GRAPH_FEATURE_SCHEMA,
            "root_lp_relaxation_policy": "zero_ablation_for_all_mvp_graphs",
            "graph_audit": dict(audit),
            "eligibility": {
                "dataset_eligible": True,
                "development_only": True,
                "scientific_reporting_eligible": False,
            },
        }
        _write_json(
            plan.output_dir
            / "provenance"
            / "original"
            / spec.solver
            / f"{spec.sample_id}.provenance.json",
            sidecar,
        )
        audits.append({"sample_id": spec.sample_id, "solver": spec.solver, **audit})
    if any(
        values.get("gurobi") != values.get("scip") for values in structures.values()
    ):
        raise MvpDatasetError("original graph structure differs between solver arms")

    derived_records: list[dict[str, Any]] = []
    storage_modes: Counter[str] = Counter()
    for record in plan.derived_records:
        source = _safe_derived_graph(plan.derived_graph_dir, record["graph_path"])
        relative = (
            Path("graphs")
            / "derived"
            / str(record["solver"])
            / source.name
        )
        mode = _materialize_derived_graph(
            source, plan.output_dir / relative, overwrite=overwrite
        )
        storage_modes[mode] += 1
        source_provenance = (
            plan.derived_graph_dir
            / "provenance"
            / str(record["solver"])
            / f"{record['sample_id']}.provenance.json"
        )
        _materialize_derived_graph(
            source_provenance,
            plan.output_dir
            / "provenance"
            / "derived"
            / str(record["solver"])
            / source_provenance.name,
            overwrite=overwrite,
        )
        copied = {**record, "graph_path": relative.as_posix()}
        if sha256_file(plan.output_dir / relative) != copied["graph_sha256"]:
            raise MvpDatasetError("materialized derived graph SHA-256 mismatch")
        derived_records.append(copied)

    inventory = sorted(
        original_records + derived_records, key=lambda item: item["sample_id"]
    )
    inventory_path = plan.output_dir / MANIFEST_NAME
    _write_jsonl(inventory_path, inventory)
    parsed = read_sample_manifest(inventory_path)
    mvp_plan = build_mvp_plan(config, parents, parsed)
    if not mvp_plan["contract_valid"]:
        raise MvpDatasetError("composed sample manifest violates the MVP contract")
    arms = _compose_arm_records(inventory, parent_roles)
    arm_summary: dict[str, Any] = {}
    for arm_id, records in arms.items():
        path = plan.output_dir / ARM_DIR / f"{arm_id}.jsonl"
        _write_jsonl(path, records)
        mass: dict[str, float] = defaultdict(float)
        roles: Counter[str] = Counter()
        for record in records:
            roles[record["role"]] += 1
            if record["role"] == "train":
                mass[record["parent_instance_id"]] += record["sample_weight"]
        if any(not math.isclose(value, 1.0, abs_tol=1e-12) for value in mass.values()):
            raise MvpDatasetError("equal-parent-mass invariant failed")
        arm_summary[arm_id] = {
            "records": len(records),
            "partitions": dict(sorted(roles.items())),
            "training_parents": len(mass),
            "training_parent_mass_min": min(mass.values()) if mass else None,
            "training_parent_mass_max": max(mass.values()) if mass else None,
            "sha256": sha256_file(path),
        }

    references: list[dict[str, Any]] = []
    by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in original_records:
        by_parent[record["parent_instance_id"]].append(record)
    for parent_id, candidates in sorted(by_parent.items()):
        selected = min(
            candidates,
            key=lambda item: (
                item["label_objective"],
                item["label_mip_gap_relative"],
                item["label_execution_time_seconds"],
                item["solver"],
            ),
        )
        references.append(
            {
                "parent_instance_id": parent_id,
                "role": parent_roles[parent_id],
                "selection_policy": "minimum_objective_then_gap_time_solver",
                "selected_solver": selected["solver"],
                "label_objective": selected["label_objective"],
                "label_mip_gap_relative": selected["label_mip_gap_relative"],
                "label_execution_time_seconds": selected[
                    "label_execution_time_seconds"
                ],
                "label_solution_sha256": selected["label_solution_sha256"],
                "candidate_count": len(candidates),
            }
        )
    reference_path = plan.output_dir / REFERENCE_NAME
    _write_jsonl(reference_path, references)
    _write_jsonl(plan.output_dir / AUDIT_NAME, audits)
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "gate_status": "passed",
        "dataset_variant": DATASET_VARIANT,
        "root_lp_relaxation_policy": "zero_ablation_for_all_mvp_graphs",
        "summary": {
            "matched_original_parents": len(structures),
            "original_graphs_written": len(original_records),
            "derived_graphs_materialized": len(derived_records),
            "unified_manifest_records": len(inventory),
            "four_arm_manifests_written": len(arms),
            "derived_storage_modes": dict(sorted(storage_modes.items())),
            "manifest_contract_valid": True,
            "original_structures_match_across_solvers": True,
            "equal_parent_mass_valid": True,
            "validation_test_original_only": True,
        },
        "arms": arm_summary,
        "outputs": {
            "sample_manifest": MANIFEST_NAME,
            "sample_manifest_sha256": sha256_file(inventory_path),
            "original_graph_audit": AUDIT_NAME,
            "original_graph_audit_sha256": sha256_file(plan.output_dir / AUDIT_NAME),
            "evaluation_reference_manifest": REFERENCE_NAME,
            "evaluation_reference_manifest_sha256": sha256_file(reference_path),
            "arm_manifest_root": ARM_DIR,
        },
        "eligibility": {
            "dataset_eligible": True,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": "four_arm_partial_dataset_admissible",
            "next_gate": "four_arm_training_loader_and_weighted_sampler",
        },
    }
    _write_json(plan.output_dir / REPORT_NAME, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build original graphs and compose four MVP arm manifests."
    )
    parser.add_argument(
        "--parent_run",
        action="append",
        nargs=2,
        metavar=("SOLVER", "RUN_DIR"),
        required=True,
    )
    parser.add_argument("--derived_graph_dir", type=Path, required=True)
    parser.add_argument("--base_source_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--parent_manifest", type=Path, default=DEFAULT_PARENT_MANIFEST)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = build_plan(
            parent_runs=[
                ParentRunInput(str(solver).lower(), Path(run_dir).resolve())
                for solver, run_dir in args.parent_run
            ],
            derived_graph_dir=args.derived_graph_dir,
            base_source_dir=args.base_source_dir,
            output_dir=args.output_dir,
            config_path=args.config,
            parent_manifest_path=args.parent_manifest,
        )
        plan.output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(plan.output_dir / PLAN_NAME, plan.to_summary())
        print(
            f"[INFO] contract={plan.contract_sha256} | "
            f"originals={len(plan.originals)} | derived={len(plan.derived_records)}"
        )
        print(
            "[INFO] four arms use equal parent mass; "
            "validation/test are original-only"
        )
        print(f"[INFO] Plan: {plan.output_dir / PLAN_NAME}")
        if args.dry_run:
            return 0
        report = run_composition(
            plan,
            config_path=args.config,
            parent_manifest_path=args.parent_manifest,
            overwrite=args.overwrite,
        )
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"original={report['summary']['original_graphs_written']} | "
            f"derived={report['summary']['derived_graphs_materialized']}"
        )
        print(f"[INFO] Report: {plan.output_dir / REPORT_NAME}")
        return 0
    except (OSError, ValueError, DerivedGraphError, MvpDatasetError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

