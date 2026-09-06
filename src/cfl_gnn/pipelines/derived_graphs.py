"""Build audited PyG graphs and the MVP manifest for derived MILPs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
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
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold


SCHEMA_VERSION = 1
DATASET_VARIANT = "mvp_independently_labelled_derived_graphs"
PLAN_NAME = "mvp_derived_graph_plan.json"
REPORT_NAME = "mvp_derived_graph_report.json"
MANIFEST_NAME = "mvp_sample_manifest.jsonl"
PER_GRAPH_AUDIT_NAME = "per_derived_graph_audit.jsonl"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
DEFAULT_PARENT_MANIFEST = (
    PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
)
SOLVERS = ("gurobi", "scip")
GRAPH_FEATURE_SCHEMA = {
    "variable": [
        "objective_log",
        "lower_bound_log",
        "upper_bound_log",
        "is_continuous",
        "is_binary",
        "is_integer",
        "root_lp_relaxation",
    ],
    "constraint": [
        "rhs_log",
        "sense_le",
        "sense_eq",
        "sense_ge",
        "constant_one",
    ],
    "edge": ["coefficient_log"],
}


class DerivedGraphError(RuntimeError):
    """Raised when graph or manifest evidence fails closed."""


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
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
        raise DerivedGraphError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise DerivedGraphError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise TypeError("record is not an object")
                records.append(value)
    except (OSError, ValueError, TypeError) as error:
        raise DerivedGraphError(
            f"invalid JSONL artifact {path.name}: {error}"
        ) from error
    return records


def _read_gzip_json(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError, TypeError) as error:
        raise DerivedGraphError(f"unreadable solution artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise DerivedGraphError(f"expected solution object: {path.name}")
    return value


def _finite(value: Any, *, field: str, nonnegative: bool = False) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise DerivedGraphError(f"{field} must be numeric") from error
    if not math.isfinite(normalized) or (nonnegative and normalized < 0.0):
        raise DerivedGraphError(f"{field} must be finite")
    return normalized


@dataclass(frozen=True, slots=True)
class SourceInput:
    solver: str
    candidate_dir: Path
    solve_dir: Path


@dataclass(frozen=True, slots=True)
class DerivedGraphSpec:
    solver: str
    sample_id: str
    parent_instance_id: str
    category: str
    difficulty: str
    fold: int
    candidate_path: Path
    candidate_sha256: str
    provenance_path: Path
    provenance_sha256: str
    solution_path: Path
    solution_sha256: str
    experiment_contract_sha256: str
    derived_solve_contract_sha256: str
    operator_contract_sha256: str
    label_objective: float
    label_mip_gap_relative: float
    label_mip_gap_percent: float
    label_execution_time_seconds: float
    gap_sensitivity_memberships: tuple[str, ...]
    source_incumbent_id: str
    source_incumbent_artifact_sha256: str
    source_incumbent_objective: float
    source_incumbent_mip_gap_relative: float
    source_incumbent_mip_gap_percent: float
    source_incumbent_execution_time_seconds: float
    radius: int
    radius_fraction: float

    @property
    def arm_id(self) -> str:
        return f"{self.solver}_incumbent_augmented"

    def contract_payload(self) -> dict[str, Any]:
        return {
            "solver": self.solver,
            "sample_id": self.sample_id,
            "parent_instance_id": self.parent_instance_id,
            "category": self.category,
            "difficulty": self.difficulty,
            "fold": self.fold,
            "role": "train",
            "candidate": {
                "file_name": self.candidate_path.name,
                "sha256": self.candidate_sha256,
                "provenance_file_name": self.provenance_path.name,
                "provenance_sha256": self.provenance_sha256,
            },
            "solution": {
                "file_name": self.solution_path.name,
                "sha256": self.solution_sha256,
            },
            "experiment_contract_sha256": self.experiment_contract_sha256,
            "derived_solve_contract_sha256": self.derived_solve_contract_sha256,
            "operator_contract_sha256": self.operator_contract_sha256,
            "label": {
                "objective": self.label_objective,
                "mip_gap_relative": self.label_mip_gap_relative,
                "mip_gap_percent": self.label_mip_gap_percent,
                "execution_time_seconds": self.label_execution_time_seconds,
                "gap_sensitivity_memberships": list(
                    self.gap_sensitivity_memberships
                ),
            },
            "source_incumbent": {
                "incumbent_id": self.source_incumbent_id,
                "artifact_sha256": self.source_incumbent_artifact_sha256,
                "objective": self.source_incumbent_objective,
                "mip_gap_relative": self.source_incumbent_mip_gap_relative,
                "mip_gap_percent": self.source_incumbent_mip_gap_percent,
                "execution_time_seconds": (
                    self.source_incumbent_execution_time_seconds
                ),
            },
            "local_branching": {
                "radius": self.radius,
                "radius_fraction": self.radius_fraction,
            },
        }


@dataclass(frozen=True, slots=True)
class DerivedGraphPlan:
    output_dir: Path
    experiment_contract_sha256: str
    samples: tuple[DerivedGraphSpec, ...]

    @property
    def contract_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": DATASET_VARIANT,
            "experiment_contract_sha256": self.experiment_contract_sha256,
            "experiment_stage": "engineering_derived_graph_generation",
            "objective_sense": "MINIMIZE",
            "graph_builder": "cfl_gnn.graph.build_dataset.build_heterodata",
            "graph_feature_schema": GRAPH_FEATURE_SCHEMA,
            "root_lp_relaxation_policy": (
                "zero_ablation_for_all_mvp_derived_graphs"
            ),
            "samples": [sample.contract_payload() for sample in self.samples],
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
            "sample_count": len(self.samples),
        }


def _require_sha(path: Path, expected: Any, *, field: str) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        raise DerivedGraphError(f"missing {field}: {path.name}")
    digest = sha256_file(path)
    if digest != expected:
        raise DerivedGraphError(f"{field} SHA-256 mismatch: {path.name}")
    return digest


def _safe_child(root: Path, name: Any, *, field: str) -> Path:
    raw = str(name)
    relative = Path(raw)
    if not raw or relative.is_absolute() or relative.name != raw:
        raise DerivedGraphError(f"unsafe {field} file name")
    return root / relative


def _source_incumbent_fields(
    provenance: Mapping[str, Any],
) -> tuple[str, str, float, float, float, float]:
    source = provenance.get("source_incumbent", {})
    if not isinstance(source, Mapping):
        raise DerivedGraphError("source_incumbent provenance is missing")
    tags = source.get("performance_feature_tags", {})
    if not isinstance(tags, Mapping):
        raise DerivedGraphError("source-incumbent performance tags are missing")
    gap = _finite(
        tags.get("admission_mip_gap_relative"),
        field="source incumbent mip gap",
        nonnegative=True,
    )
    gap_percent = _finite(
        tags.get("admission_mip_gap_percent"),
        field="source incumbent mip gap percent",
        nonnegative=True,
    )
    if not math.isclose(gap_percent, 100.0 * gap, rel_tol=1e-9, abs_tol=1e-8):
        raise DerivedGraphError("source-incumbent MIP-gap units disagree")
    return (
        str(source["incumbent_id"]),
        str(source["artifact_sha256"]),
        _finite(tags.get("incumbent_objective"), field="source incumbent objective"),
        gap,
        gap_percent,
        _finite(
            tags.get("execution_time_seconds"),
            field="source incumbent execution time",
            nonnegative=True,
        ),
    )


def _load_source(
    source: SourceInput,
    *,
    experiment_contract_sha256: str,
    parent_roles: Mapping[str, tuple[str, int, str, str]],
) -> list[DerivedGraphSpec]:
    report = _read_json(source.solve_dir / "derived_mip_solution_report.json")
    solve_plan = _read_json(source.solve_dir / "derived_mip_solution_plan.json")
    metrics = _read_jsonl(
        source.solve_dir / "per_candidate_derived_metrics.jsonl"
    )
    if report.get("gate_status") != "passed" or report.get("solver") != source.solver:
        raise DerivedGraphError(f"{source.solver} derived-label gate is not passed")
    if report.get("eligibility", {}).get("all_labels_eligible") is not True:
        raise DerivedGraphError(f"{source.solver} labels are not all eligible")
    if report.get("contract_sha256") != solve_plan.get("contract_sha256"):
        raise DerivedGraphError(f"{source.solver} solve plan/report contract mismatch")
    if report.get("experiment_contract_sha256") != experiment_contract_sha256:
        raise DerivedGraphError(f"{source.solver} experiment contract mismatch")
    if len(metrics) != int(report.get("summary", {}).get("candidate_count", -1)):
        raise DerivedGraphError(f"{source.solver} metric count mismatch")

    results: list[DerivedGraphSpec] = []
    for metric in metrics:
        if (
            metric.get("gate_status") != "passed"
            or metric.get("eligibility", {}).get("label_eligible") is not True
            or metric.get("solver") != source.solver
            or metric.get("sampling_strategy") != "incumbent_local_branching"
            or metric.get("role") != "train"
        ):
            raise DerivedGraphError("one or more derived labels are not admissible")
        candidate = metric.get("candidate", {})
        if not isinstance(candidate, Mapping):
            raise DerivedGraphError("candidate contract is missing")
        sample_id = str(metric["sample_id"])
        candidate_path = _safe_child(
            source.candidate_dir, candidate["file_name"], field="candidate"
        )
        provenance_path = _safe_child(
            source.candidate_dir,
            candidate["provenance_file_name"],
            field="candidate provenance",
        )
        _require_sha(candidate_path, candidate.get("sha256"), field="candidate MIP")
        _require_sha(
            provenance_path,
            candidate.get("provenance_sha256"),
            field="candidate provenance",
        )
        provenance = _read_json(provenance_path)
        output = provenance.get("output", {})
        if (
            provenance.get("solver") != source.solver
            or provenance.get("parent_instance_id") != metric.get("parent_instance_id")
            or provenance.get("role") != "train"
            or provenance.get("experiment_contract_sha256")
            != experiment_contract_sha256
            or provenance.get("operator_contract_sha256")
            != candidate.get("operator_contract_sha256")
            or output.get("file_name") != candidate_path.name
            or output.get("sha256") != candidate.get("sha256")
            or candidate_path.stem != sample_id
        ):
            raise DerivedGraphError("candidate provenance linkage mismatch")
        solution_artifact = metric.get("artifacts", {}).get("solution")
        if not isinstance(solution_artifact, Mapping):
            raise DerivedGraphError("eligible metric has no solution artifact")
        solution_path = _safe_child(
            source.solve_dir / "solutions",
            solution_artifact["file_name"],
            field="solution",
        )
        _require_sha(
            solution_path,
            solution_artifact.get("sha256"),
            field="solution artifact",
        )
        parent_id = str(metric["parent_instance_id"])
        try:
            role, parent_fold, parent_category, parent_difficulty = parent_roles[
                parent_id
            ]
        except KeyError as error:
            raise DerivedGraphError(f"unknown parent: {parent_id}") from error
        if (
            role != "train"
            or int(metric["fold"]) != parent_fold
            or metric.get("category") != parent_category
            or metric.get("difficulty") != parent_difficulty
        ):
            raise DerivedGraphError("derived sample violates its parent fold contract")
        solve = metric.get("solve", {})
        local_branching = provenance.get("local_branching", {})
        if (
            int(local_branching.get("radius", -1)) != int(candidate.get("radius", -2))
            or float(local_branching.get("radius_fraction", -1.0))
            != float(candidate.get("radius_fraction", -2.0))
            or provenance.get("source_incumbent", {}).get("incumbent_id")
            != candidate.get("source_incumbent_id")
            or provenance.get("source_incumbent", {}).get("artifact_sha256")
            != candidate.get("source_incumbent_artifact_sha256")
        ):
            raise DerivedGraphError("operator or source-incumbent linkage mismatch")
        incumbent = _source_incumbent_fields(provenance)
        gap = _finite(
            solve.get("mip_gap_relative"), field="label MIP gap", nonnegative=True
        )
        gap_percent = _finite(
            solve.get("mip_gap_percent"),
            field="label MIP gap percent",
            nonnegative=True,
        )
        if not math.isclose(
            gap_percent, 100.0 * gap, rel_tol=1e-9, abs_tol=1e-8
        ):
            raise DerivedGraphError("label MIP-gap units disagree")
        results.append(
            DerivedGraphSpec(
                solver=source.solver,
                sample_id=sample_id,
                parent_instance_id=parent_id,
                category=str(metric["category"]),
                difficulty=str(metric["difficulty"]),
                fold=int(metric["fold"]),
                candidate_path=candidate_path,
                candidate_sha256=str(candidate["sha256"]),
                provenance_path=provenance_path,
                provenance_sha256=str(candidate["provenance_sha256"]),
                solution_path=solution_path,
                solution_sha256=str(solution_artifact["sha256"]),
                experiment_contract_sha256=experiment_contract_sha256,
                derived_solve_contract_sha256=str(report["contract_sha256"]),
                operator_contract_sha256=str(
                    candidate["operator_contract_sha256"]
                ),
                label_objective=_finite(
                    solve.get("solution_objective"), field="label objective"
                ),
                label_mip_gap_relative=gap,
                label_mip_gap_percent=gap_percent,
                label_execution_time_seconds=_finite(
                    solve.get("execution_time_seconds"),
                    field="label execution time",
                    nonnegative=True,
                ),
                gap_sensitivity_memberships=tuple(
                    str(item)
                    for item in metric.get("gap_sensitivity_memberships", [])
                ),
                source_incumbent_id=incumbent[0],
                source_incumbent_artifact_sha256=incumbent[1],
                source_incumbent_objective=incumbent[2],
                source_incumbent_mip_gap_relative=incumbent[3],
                source_incumbent_mip_gap_percent=incumbent[4],
                source_incumbent_execution_time_seconds=incumbent[5],
                radius=int(local_branching["radius"]),
                radius_fraction=float(local_branching["radius_fraction"]),
            )
        )
    return results


def build_plan(
    *,
    sources: Sequence[SourceInput],
    output_dir: Path,
    config_path: Path,
    parent_manifest_path: Path,
) -> DerivedGraphPlan:
    config = load_experiment_config(config_path)
    if {source.solver for source in sources} != set(SOLVERS) or len(sources) != 2:
        raise DerivedGraphError("exactly one Gurobi and one SCIP source are required")
    parent_manifest = read_manifest(parent_manifest_path)
    parent_roles = {
        entry.source_instance_id: (
            role_for_fold(entry.fold, config.rotation),
            entry.fold,
            entry.category,
            entry.difficulty,
        )
        for entry in parent_manifest
    }
    samples: list[DerivedGraphSpec] = []
    for source in sorted(sources, key=lambda item: item.solver):
        samples.extend(
            _load_source(
                source,
                experiment_contract_sha256=config.contract_sha256,
                parent_roles=parent_roles,
            )
        )
    samples.sort(key=lambda item: (item.solver, item.parent_instance_id, item.radius))
    if not samples or len({sample.sample_id for sample in samples}) != len(samples):
        raise DerivedGraphError("sample identifiers must be non-empty and unique")
    counts = Counter((item.solver, item.parent_instance_id) for item in samples)
    if any(count > config.augmentation.maximum_derived_per_parent for count in counts.values()):
        raise DerivedGraphError("maximum derived samples per parent exceeded")
    if any(
        sample.label_mip_gap_relative
        > config.gap_policy.maximum_admissible_relative_gap + 1e-12
        for sample in samples
    ):
        raise DerivedGraphError("an admitted label exceeds the gap policy")
    return DerivedGraphPlan(
        output_dir=output_dir.resolve(),
        experiment_contract_sha256=config.contract_sha256,
        samples=tuple(samples),
    )


def _canonical_variable_type(raw: Any, lower: float, upper: float) -> str:
    normalized = str(raw).strip().upper()
    if normalized in {"B", "BINARY"} or (
        normalized in {"I", "INTEGER"}
        and lower >= -1e-9
        and upper <= 1.0 + 1e-9
    ):
        return "B"
    if normalized in {"I", "INTEGER", "IMPLINT", "IMPLICIT_INTEGER"}:
        return "I"
    if normalized in {"C", "CONTINUOUS"}:
        return "C"
    raise DerivedGraphError(f"unsupported variable type: {raw!r}")


def _linear_constraint_data(
    model: Any, constraint: Any
) -> tuple[str, float, list[Any], list[float]]:
    variables = list(model.getConsVars(constraint))
    coefficients = [float(value) for value in model.getConsVals(constraint)]
    lhs = float(model.getLhs(constraint))
    rhs = float(model.getRhs(constraint))
    lhs_finite = math.isfinite(lhs) and lhs > -1e19
    rhs_finite = math.isfinite(rhs) and rhs < 1e19
    tolerance = 1e-9 * max(
        1.0,
        abs(lhs) if lhs_finite else 0.0,
        abs(rhs) if rhs_finite else 0.0,
    )
    if lhs_finite and rhs_finite and abs(lhs - rhs) <= tolerance:
        return "=", rhs, variables, coefficients
    if lhs_finite and not rhs_finite:
        return ">", lhs, variables, coefficients
    if rhs_finite and not lhs_finite:
        return "<", rhs, variables, coefficients
    raise DerivedGraphError(f"unsupported ranged constraint: {constraint.name}")


def _solution_by_name(spec: DerivedGraphSpec) -> dict[str, float]:
    payload = _read_gzip_json(spec.solution_path)
    if payload.get("candidate_sha256") != spec.candidate_sha256:
        raise DerivedGraphError("solution is linked to a different candidate MIP")
    values: dict[str, float] = {}
    for item in payload.get("variables", []):
        if not isinstance(item, Mapping) or item.get("name") is None:
            raise DerivedGraphError("solution contains an unnamed variable")
        name = str(item["name"])
        if name in values:
            raise DerivedGraphError(f"duplicate solution variable: {name}")
        values[name] = _finite(item.get("value"), field=f"solution[{name}]")
    if not values:
        raise DerivedGraphError("solution variable vector is empty")
    return values


def _tensor_sha256(array: Any) -> str:
    import numpy as np

    normalized = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(normalized.dtype).encode("ascii"))
    digest.update(str(tuple(normalized.shape)).encode("ascii"))
    digest.update(normalized.tobytes(order="C"))
    return digest.hexdigest()


def build_graph_artifact(spec: DerivedGraphSpec, output_path: Path) -> dict[str, Any]:
    """Build one graph through a common PySCIPOpt LP reader and production encoder."""
    import numpy as np
    import torch
    from pyscipopt import Model

    from cfl_gnn.artifacts.schemas import (
        ConstraintFeatures,
        ModelFeatures,
        VariableFeatures,
    )
    from cfl_gnn.graph.build_dataset import build_heterodata

    solution = _solution_by_name(spec)
    model = Model()
    try:
        model.hideOutput(True)
        model.readProblem(str(spec.candidate_path))
        if str(model.getObjectiveSense()).lower() != "minimize":
            raise DerivedGraphError("derived candidate objective is not minimize")
        variables = sorted(
            model.getVars(transformed=False), key=lambda variable: str(variable.name)
        )
        constraints = sorted(
            model.getConss(transformed=False),
            key=lambda constraint: str(constraint.name),
        )
        variable_names = [str(variable.name) for variable in variables]
        if len(set(variable_names)) != len(variable_names):
            raise DerivedGraphError("candidate has duplicate variable names")
        if set(solution) != set(variable_names):
            raise DerivedGraphError("solution and candidate variable identities differ")
        variable_index = {name: index for index, name in enumerate(variable_names)}
        lower_bounds = np.asarray(
            [float(variable.getLbOriginal()) for variable in variables],
            dtype=np.float64,
        )
        upper_bounds = np.asarray(
            [float(variable.getUbOriginal()) for variable in variables],
            dtype=np.float64,
        )
        variable_types = np.asarray(
            [
                _canonical_variable_type(variable.vtype(), lower, upper)
                for variable, lower, upper in zip(
                    variables, lower_bounds, upper_bounds
                )
            ],
            dtype="<U1",
        )
        objective = np.asarray(
            [float(variable.getObj()) for variable in variables], dtype=np.float64
        )
        senses: list[str] = []
        rhs_values: list[float] = []
        row_norms: list[float] = []
        constraint_indices: list[int] = []
        variable_indices: list[int] = []
        edge_coefficients: list[float] = []
        constraint_records: list[Any] = []
        for constraint_index, constraint in enumerate(constraints):
            sense, rhs, row_variables, coefficients = _linear_constraint_data(
                model, constraint
            )
            senses.append(sense)
            rhs_values.append(rhs)
            row_norms.append(float(np.linalg.norm(coefficients)))
            terms: list[list[Any]] = []
            for variable, coefficient in zip(row_variables, coefficients):
                name = str(variable.name)
                if name not in variable_index:
                    raise DerivedGraphError(f"constraint references unknown variable: {name}")
                constraint_indices.append(constraint_index)
                variable_indices.append(variable_index[name])
                edge_coefficients.append(coefficient)
                terms.append([name, coefficient])
            constraint_records.append(
                [str(constraint.name), sense, rhs, sorted(terms)]
            )
        labels = np.asarray([solution[name] for name in variable_names], dtype=np.float64)
        graph = build_heterodata(
            ModelFeatures(
                num_vars=len(variables),
                num_constrs=len(constraints),
                num_binary=int(np.sum(variable_types == "B")),
                num_integer=int(np.sum(variable_types == "I")),
                num_continuous=int(np.sum(variable_types == "C")),
                obj_sense="MINIMIZE",
                obj_offset=0.0,
            ),
            VariableFeatures(
                types=variable_types,
                lower_bounds=lower_bounds,
                upper_bounds=upper_bounds,
                obj_coeffs=objective,
            ),
            ConstraintFeatures(
                senses=np.asarray(senses, dtype="<U1"),
                rhs_values=np.asarray(rhs_values, dtype=np.float64),
                row_norms=np.asarray(row_norms, dtype=np.float64),
            ),
            np.asarray([constraint_indices, variable_indices], dtype=np.int64),
            np.asarray(edge_coefficients, dtype=np.float64),
            labels,
            np.zeros(len(variables), dtype=np.float64),
            spec.label_mip_gap_relative,
            spec.label_execution_time_seconds,
            spec.label_mip_gap_relative <= 1e-4,
            -1,
            spec.sample_id,
            {"complexity_class": spec.difficulty},
        )
        if graph is None:
            raise DerivedGraphError("production graph builder returned no graph")
        graph.sample_id = spec.sample_id
        graph.source_instance_id = spec.parent_instance_id
        graph.parent_instance_id = spec.parent_instance_id
        graph.instance_fold = spec.fold
        graph.role = "train"
        graph.solver = spec.solver
        graph.arm_id = spec.arm_id
        graph.sampling_strategy = "incumbent_local_branching"
        graph.objective_sense = "MINIMIZE"
        graph.root_lp_relaxation_mode = "zero_ablation_for_mvp_derived_graphs"
        graph.label_source = spec.solution_path.name
        graph.label_solution_sha256 = spec.solution_sha256
        graph.label_objective = spec.label_objective
        graph.source_incumbent_id = spec.source_incumbent_id
        graph.source_incumbent_artifact_sha256 = (
            spec.source_incumbent_artifact_sha256
        )
        graph.local_branching_radius = spec.radius
        graph.local_branching_radius_fraction = spec.radius_fraction
        graph.derived_solve_contract_sha256 = spec.derived_solve_contract_sha256
        graph.experiment_contract_sha256 = spec.experiment_contract_sha256
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        torch.save(graph, temporary)
        temporary.replace(output_path)
        reloaded = torch.load(output_path, map_location="cpu", weights_only=False)
        if (
            getattr(reloaded, "sample_id", None) != spec.sample_id
            or int(reloaded["variable"].x.shape[0]) != len(variables)
            or int(reloaded["constraint"].x.shape[0]) != len(constraints)
            or int(reloaded["variable"].y.shape[0]) != len(variables)
        ):
            raise DerivedGraphError("serialized graph failed its round-trip audit")
        structural_sha256 = _canonical_sha256(
            {
                "variable_names": variable_names,
                "variable_types": variable_types.tolist(),
                "lower_bounds": _tensor_sha256(lower_bounds),
                "upper_bounds": _tensor_sha256(upper_bounds),
                "objective": _tensor_sha256(objective),
                "constraints": constraint_records,
            }
        )
        graph_content_sha256 = _canonical_sha256(
            {
                "structure": structural_sha256,
                "label": _tensor_sha256(labels),
                "mip_gap_relative": spec.label_mip_gap_relative,
                "execution_time_seconds": spec.label_execution_time_seconds,
            }
        )
        return {
            "graph_sha256": sha256_file(output_path),
            "structural_graph_sha256": structural_sha256,
            "graph_content_sha256": graph_content_sha256,
            "variables": len(variables),
            "constraints": len(constraints),
            "nonzeros": len(edge_coefficients),
            "binary_variables": int(np.sum(variable_types == "B")),
            "integer_variables": int(np.sum(variable_types == "I")),
            "continuous_variables": int(np.sum(variable_types == "C")),
            "roundtrip_readable": True,
            "label_variable_identity_match": True,
        }
    finally:
        try:
            model.freeProb()
        except Exception:
            pass


def _manifest_record(
    plan: DerivedGraphPlan,
    spec: DerivedGraphSpec,
    output_path: Path,
    graph_audit: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "sample_id": spec.sample_id,
        "parent_instance_id": spec.parent_instance_id,
        "category": spec.category,
        "difficulty": spec.difficulty,
        "fold": spec.fold,
        "solver": spec.solver,
        "sampling_strategy": "incumbent_local_branching",
        "graph_path": output_path.relative_to(plan.output_dir).as_posix(),
        "graph_sha256": graph_audit["graph_sha256"],
        "label_source": spec.solution_path.name,
        "label_solution_sha256": spec.solution_sha256,
        "label_objective": spec.label_objective,
        "label_mip_gap_relative": spec.label_mip_gap_relative,
        "label_mip_gap_percent": spec.label_mip_gap_percent,
        "label_execution_time_seconds": spec.label_execution_time_seconds,
        "source_incumbent_id": spec.source_incumbent_id,
        "source_incumbent_artifact_sha256": (
            spec.source_incumbent_artifact_sha256
        ),
        "source_incumbent_objective": spec.source_incumbent_objective,
        "source_incumbent_mip_gap_relative": (
            spec.source_incumbent_mip_gap_relative
        ),
        "source_incumbent_mip_gap_percent": (
            spec.source_incumbent_mip_gap_percent
        ),
        "source_incumbent_execution_time_seconds": (
            spec.source_incumbent_execution_time_seconds
        ),
        "local_branching_radius": spec.radius,
        "local_branching_radius_fraction": spec.radius_fraction,
    }


def run_generation(
    plan: DerivedGraphPlan,
    *,
    config_path: Path,
    parent_manifest_path: Path,
    overwrite: bool,
    graph_builder: Callable[[DerivedGraphSpec, Path], Mapping[str, Any]] = (
        build_graph_artifact
    ),
) -> dict[str, Any]:
    graph_records: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for spec in plan.samples:
        output_path = plan.output_dir / "graphs" / spec.solver / f"{spec.sample_id}.pt"
        provenance_path = (
            plan.output_dir
            / "provenance"
            / spec.solver
            / f"{spec.sample_id}.provenance.json"
        )
        if not overwrite and (output_path.exists() or provenance_path.exists()):
            raise FileExistsError(f"output exists: {output_path.name}")
        graph_audit = dict(graph_builder(spec, output_path))
        required_checks = (
            graph_audit.get("roundtrip_readable") is True
            and graph_audit.get("label_variable_identity_match") is True
            and graph_audit.get("graph_sha256") == sha256_file(output_path)
        )
        if not required_checks:
            raise DerivedGraphError(f"graph audit failed: {spec.sample_id}")
        record = _manifest_record(plan, spec, output_path, graph_audit)
        manifest.append(record)
        graph_records.append(
            {
                "sample_id": spec.sample_id,
                "solver": spec.solver,
                "parent_instance_id": spec.parent_instance_id,
                "graph_path": record["graph_path"],
                "provenance_path": provenance_path.relative_to(
                    plan.output_dir
                ).as_posix(),
                **graph_audit,
            }
        )

    within_parent = defaultdict(list)
    for item in graph_records:
        within_parent[(item["solver"], item["parent_instance_id"])].append(
            item["structural_graph_sha256"]
        )
    collisions = [
        {"solver": key[0], "parent_instance_id": key[1]}
        for key, digests in within_parent.items()
        if len(digests) != len(set(digests))
    ]
    if collisions:
        raise DerivedGraphError("duplicate derived graph structure within a parent arm")

    _write_jsonl(plan.output_dir / PER_GRAPH_AUDIT_NAME, graph_records)
    manifest.sort(key=lambda item: item["sample_id"])
    _write_jsonl(plan.output_dir / MANIFEST_NAME, manifest)
    parsed_manifest = read_sample_manifest(plan.output_dir / MANIFEST_NAME)
    mvp_plan = build_mvp_plan(
        load_experiment_config(config_path),
        read_manifest(parent_manifest_path),
        parsed_manifest,
    )
    manifest_valid = (
        mvp_plan["contract_valid"] is True
        and mvp_plan["samples_eligible"] == len(manifest)
        and mvp_plan["samples_invalid"] == 0
    )
    if not manifest_valid:
        raise DerivedGraphError("generated sample manifest failed the MVP contract")

    manifest_by_sample = {item["sample_id"]: item for item in manifest}
    graph_by_sample = {item["sample_id"]: item for item in graph_records}
    for spec in plan.samples:
        item = manifest_by_sample[spec.sample_id]
        graph_audit = graph_by_sample[spec.sample_id]
        provenance_path = plan.output_dir / graph_audit["provenance_path"]
        _write_json(
            provenance_path,
            {
                "schema_version": SCHEMA_VERSION,
                "dataset_variant": DATASET_VARIANT,
                "graph_generation_contract_sha256": plan.contract_sha256,
                "experiment_contract_sha256": plan.experiment_contract_sha256,
                "sample": spec.contract_payload(),
                "graph": graph_audit,
                "manifest_record_sha256": _canonical_sha256(item),
                "root_lp_relaxation_policy": (
                    "zero_ablation_for_all_mvp_derived_graphs"
                ),
                "eligibility": {
                    "dataset_eligible": True,
                    "development_only": True,
                    "scientific_reporting_eligible": False,
                },
            },
        )

    by_solver = Counter(item["solver"] for item in manifest)
    return {
        **plan.to_summary(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "probe_completed": True,
        "gate_status": "passed",
        "outputs": {
            "sample_manifest": MANIFEST_NAME,
            "sample_manifest_sha256": sha256_file(plan.output_dir / MANIFEST_NAME),
            "per_graph_audit": PER_GRAPH_AUDIT_NAME,
            "per_graph_audit_sha256": sha256_file(
                plan.output_dir / PER_GRAPH_AUDIT_NAME
            ),
            "graphs_root": "graphs",
            "provenance_root": "provenance",
        },
        "summary": {
            "samples_planned": len(plan.samples),
            "graphs_written": len(graph_records),
            "manifest_records": len(manifest),
            "graphs_by_solver": dict(sorted(by_solver.items())),
            "within_parent_structural_collisions": 0,
            "manifest_contract_valid": True,
        },
        "eligibility": {
            "dataset_eligible": True,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": "derived_graphs_and_manifest_admissible",
            "next_gate": "original_solver_datasets_and_manifest_composition",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build audited MVP graphs from independently labelled derived MIPs."
    )
    parser.add_argument(
        "--source",
        nargs=3,
        action="append",
        metavar=("SOLVER", "CANDIDATE_DIR", "SOLVE_DIR"),
        required=True,
        help="Repeat once for gurobi and once for scip.",
    )
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--parent_manifest", type=Path, default=DEFAULT_PARENT_MANIFEST
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan: DerivedGraphPlan | None = None
    try:
        sources = tuple(
            SourceInput(
                solver=str(raw[0]).lower(),
                candidate_dir=Path(raw[1]).resolve(),
                solve_dir=Path(raw[2]).resolve(),
            )
            for raw in args.source
        )
        if any(source.solver not in SOLVERS for source in sources):
            raise DerivedGraphError("solver must be gurobi or scip")
        plan = build_plan(
            sources=sources,
            output_dir=args.output_dir,
            config_path=args.config,
            parent_manifest_path=args.parent_manifest,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = args.output_dir / PLAN_NAME
        report_path = args.output_dir / REPORT_NAME
        if not args.overwrite and (
            report_path.exists() or (args.dry_run and plan_path.exists())
        ):
            raise FileExistsError(
                "output exists; choose another directory or use --overwrite"
            )
        _write_json(plan_path, plan.to_summary())
        print(
            f"[INFO] contract={plan.contract_sha256} | "
            f"samples={len(plan.samples)} | solvers=gurobi,scip"
        )
        print("[INFO] derived samples are train-only and inherit the parent fold")
        print(f"[INFO] Plan: {plan_path}")
        if args.dry_run:
            return 0
        report = run_generation(
            plan,
            config_path=args.config,
            parent_manifest_path=args.parent_manifest,
            overwrite=args.overwrite,
        )
        _write_json(report_path, report)
        print(
            f"[INFO] gate=passed | graphs={report['summary']['graphs_written']} | "
            "dataset_eligible=true | scientific_reporting_eligible=false"
        )
        print(f"[INFO] Report: {report_path}")
        return 0
    except (
        DerivedGraphError,
        FileExistsError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        if plan is not None:
            _write_json(
                plan.output_dir / REPORT_NAME,
                {
                    **plan.to_summary(),
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "probe_completed": False,
                    "gate_status": "failed",
                    "failure": {
                        "error_type": type(error).__name__,
                        "reason_code": "derived_graph_generation_failed",
                    },
                    "eligibility": {
                        "dataset_eligible": False,
                        "development_only": True,
                        "scientific_reporting_eligible": False,
                    },
                    "decision": {
                        "reason_code": "stop_or_correct_derived_graph_generation",
                        "next_gate": "repeat_derived_graph_generation",
                    },
                },
            )
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
