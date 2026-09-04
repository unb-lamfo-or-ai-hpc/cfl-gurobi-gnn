"""Generate solver-symmetric local-branching MILP variants.

The mathematical operator is kept independent from Gurobi and PySCIPOpt.
Solver adapters only inspect the parent model and serialize one added linear
constraint. No generated variant is a dataset sample until a later stage has
independently solved, labelled, and converted it to a graph.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.experiments.mvp_contract import load_experiment_config
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.splits.instance_folds import role_for_fold


SCHEMA_VERSION = 1
PLAN_NAME = "local_branching_generation_plan.json"
REPORT_NAME = "local_branching_generation_report.json"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
VALUE_TOLERANCE = 1e-6


class AugmentationError(ValueError):
    """Raised when an incumbent cannot safely define a derived MILP."""


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: Any, *, field: str, nonnegative: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise AugmentationError(f"{field} is not numeric") from error
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        qualifier = "finite and nonnegative" if nonnegative else "finite"
        raise AugmentationError(f"{field} must be {qualifier}")
    return result


@dataclass(frozen=True, slots=True)
class VariableDomain:
    name: str
    canonical_type: str
    lower_bound: float
    upper_bound: float

    @property
    def is_binary(self) -> bool:
        return self.canonical_type == "BINARY"


@dataclass(frozen=True, slots=True)
class IncumbentRecord:
    source_solver: str
    source_format: str
    source_artifact: str
    source_artifact_sha256: str
    source_model_sha256: str | None
    source_index: int | None
    incumbent_id: str
    objective: float
    admission_mip_gap_relative: float
    admission_mip_gap_percent: float
    admission_mip_gap_measurement: str
    terminal_mip_gap_relative: float | None
    terminal_mip_gap_percent: float | None
    execution_time_seconds: float
    discovery_time_seconds: float | None
    discovery_mip_gap_relative: float | None
    discovery_mip_gap_percent: float | None
    values_by_name: Mapping[str, float]

    def performance_tags(self) -> dict[str, Any]:
        return {
            "source_solver": self.source_solver,
            "incumbent_objective": self.objective,
            "execution_time_seconds": self.execution_time_seconds,
            "admission_mip_gap_relative": self.admission_mip_gap_relative,
            "admission_mip_gap_percent": self.admission_mip_gap_percent,
            "admission_mip_gap_measurement": self.admission_mip_gap_measurement,
            "terminal_mip_gap_relative": self.terminal_mip_gap_relative,
            "terminal_mip_gap_percent": self.terminal_mip_gap_percent,
            "incumbent_discovery_time_seconds": self.discovery_time_seconds,
            "incumbent_mip_gap_relative_at_discovery": (
                self.discovery_mip_gap_relative
            ),
            "incumbent_mip_gap_percent_at_discovery": (
                self.discovery_mip_gap_percent
            ),
        }


@dataclass(frozen=True, slots=True)
class LocalBranchingConstraint:
    radius_fraction: float
    radius: int
    binary_variable_count: int
    incumbent_zero_count: int
    incumbent_one_count: int
    coefficients: Mapping[str, int]
    rhs: int
    constraint_sha256: str

    def contract_payload(self) -> dict[str, Any]:
        return {
            "radius_fraction": self.radius_fraction,
            "radius": self.radius,
            "binary_variable_count": self.binary_variable_count,
            "incumbent_zero_count": self.incumbent_zero_count,
            "incumbent_one_count": self.incumbent_one_count,
            "coefficients": dict(sorted(self.coefficients.items())),
            "rhs": self.rhs,
        }

    def provenance_payload(self) -> dict[str, Any]:
        """Return bounded-size evidence without repeating 148k coefficients."""
        return {
            "radius_fraction": self.radius_fraction,
            "radius": self.radius,
            "binary_variable_count": self.binary_variable_count,
            "incumbent_zero_count": self.incumbent_zero_count,
            "incumbent_one_count": self.incumbent_one_count,
            "canonical_linear_form": (
                "+x when incumbent=0; -x when incumbent=1; "
                "rhs=radius-incumbent_one_count"
            ),
            "rhs": self.rhs,
            "constraint_sha256": self.constraint_sha256,
        }


def operator_contract_payload(config: Any) -> dict[str, Any]:
    policy = config.augmentation
    return {
        "operator": policy.operator,
        "binary_variables_only": policy.binary_variables_only,
        "mathematical_form": (
            "sum(x_j:x*_j=0)+sum(1-x_j:x*_j=1)<=radius"
        ),
        "radius_mode": "ceil_fraction_of_binary_variables_with_minimum",
        "radius_fractions": list(policy.radius_fractions),
        "minimum_radius": policy.minimum_radius,
        "maximum_derived_per_parent": policy.maximum_derived_per_parent,
    }


def build_local_branching_constraints(
    variables: Sequence[VariableDomain],
    incumbent: IncumbentRecord,
    *,
    radius_fractions: Sequence[float],
    minimum_radius: int,
    maximum_derived: int,
    tolerance: float = VALUE_TOLERANCE,
) -> tuple[LocalBranchingConstraint, ...]:
    """Create canonical linear forms, deduplicating equal integer radii."""
    binary = [variable for variable in variables if variable.is_binary]
    if not binary:
        raise AugmentationError("parent model has no canonical binary variables")
    missing = [v.name for v in binary if v.name not in incumbent.values_by_name]
    if missing:
        raise AugmentationError(
            f"incumbent is missing {len(missing)} binary variable values"
        )

    coefficients: dict[str, int] = {}
    zeros = 0
    ones = 0
    for variable in binary:
        value = _finite(
            incumbent.values_by_name[variable.name],
            field=f"incumbent value for {variable.name}",
        )
        if abs(value) <= tolerance:
            coefficients[variable.name] = 1
            zeros += 1
        elif abs(value - 1.0) <= tolerance:
            coefficients[variable.name] = -1
            ones += 1
        else:
            raise AugmentationError(
                f"binary incumbent value for {variable.name} is fractional"
            )

    constraints: list[LocalBranchingConstraint] = []
    seen_radii: set[int] = set()
    for fraction in radius_fractions:
        normalized_fraction = _finite(
            fraction, field="radius fraction", nonnegative=True
        )
        radius = max(minimum_radius, math.ceil(normalized_fraction * len(binary)))
        radius = min(radius, len(binary))
        if radius in seen_radii:
            continue
        seen_radii.add(radius)
        payload = {
            "radius_fraction": normalized_fraction,
            "radius": radius,
            "binary_variable_count": len(binary),
            "incumbent_zero_count": zeros,
            "incumbent_one_count": ones,
            "coefficients": dict(sorted(coefficients.items())),
            "rhs": radius - ones,
        }
        constraints.append(
            LocalBranchingConstraint(
                **payload,
                constraint_sha256=_canonical_sha256(payload),
            )
        )
        if len(constraints) >= maximum_derived:
            break
    return tuple(constraints)


def _read_json(path: Path) -> Mapping[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else Path.open
    try:
        with opener(path, "rt", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError, TypeError) as error:
        raise AugmentationError("incumbent JSON is unreadable") from error
    if not isinstance(value, Mapping):
        raise AugmentationError("incumbent JSON must contain an object")
    return value


def _gap_pair(relative: Any, percent: Any) -> tuple[float, float]:
    relative_value = _finite(relative, field="terminal MIP gap", nonnegative=True)
    percent_value = (
        100.0 * relative_value
        if percent is None
        else _finite(percent, field="terminal MIP gap percent", nonnegative=True)
    )
    if not math.isclose(
        percent_value, 100.0 * relative_value, rel_tol=1e-8, abs_tol=1e-8
    ):
        raise AugmentationError("relative and percentage MIP gaps disagree")
    return relative_value, percent_value


def load_pyscipopt_solution(path: str | Path) -> IncumbentRecord:
    source = Path(path).resolve()
    value = _read_json(source)
    raw_variables = value.get("variables")
    if not isinstance(raw_variables, list) or not raw_variables:
        raise AugmentationError("PySCIPOpt solution has no named variable vector")
    values_by_name: dict[str, float] = {}
    for variable in raw_variables:
        if not isinstance(variable, Mapping) or not variable.get("name"):
            raise AugmentationError("PySCIPOpt solution has an invalid variable record")
        name = str(variable["name"])
        if name in values_by_name:
            raise AugmentationError(f"duplicate incumbent variable: {name}")
        values_by_name[name] = _finite(variable.get("value"), field=f"value for {name}")
    gap, gap_percent = _gap_pair(
        value.get("mip_gap_relative"), value.get("mip_gap_percent")
    )
    trace = value.get("incumbent_trace")
    best_trace = trace[-1] if isinstance(trace, list) and trace else {}
    discovery_gap = best_trace.get("incumbent_mip_gap_relative_at_discovery")
    discovery_gap_percent = best_trace.get(
        "incumbent_mip_gap_percent_at_discovery"
    )
    digest = sha256_file(source)
    return IncumbentRecord(
        source_solver="scip",
        source_format="pyscipopt_solution_json",
        source_artifact=str(source),
        source_artifact_sha256=digest,
        source_model_sha256=(
            None
            if value.get("candidate_sha256") is None
            else str(value["candidate_sha256"])
        ),
        source_index=None,
        incumbent_id=f"scip:{digest[:16]}",
        objective=_finite(
            value.get("solution_objective", value.get("objective")),
            field="incumbent objective",
        ),
        admission_mip_gap_relative=gap,
        admission_mip_gap_percent=gap_percent,
        admission_mip_gap_measurement="terminal_solver_gap",
        terminal_mip_gap_relative=gap,
        terminal_mip_gap_percent=gap_percent,
        execution_time_seconds=_finite(
            value.get("execution_time_seconds"),
            field="execution time",
            nonnegative=True,
        ),
        discovery_time_seconds=(
            None
            if value.get("best_incumbent_discovery_time_seconds") is None
            else _finite(
                value["best_incumbent_discovery_time_seconds"],
                field="incumbent discovery time",
                nonnegative=True,
            )
        ),
        discovery_mip_gap_relative=(
            None
            if discovery_gap is None
            else _finite(discovery_gap, field="discovery MIP gap", nonnegative=True)
        ),
        discovery_mip_gap_percent=(
            None
            if discovery_gap_percent is None
            else _finite(
                discovery_gap_percent,
                field="discovery MIP gap percent",
                nonnegative=True,
            )
        ),
        values_by_name=values_by_name,
    )


def _parquet_cell_to_values(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        raise AugmentationError("Gurobi solution_vector is not an array")
    return [_finite(item, field="Gurobi incumbent value") for item in value]


def incumbent_from_gurobi_record(
    record: Mapping[str, Any],
    variable_names: Sequence[str],
    *,
    artifact: str | Path,
    artifact_sha256: str,
    source_index: int,
) -> IncumbentRecord:
    vector = _parquet_cell_to_values(record.get("solution_vector"))
    if len(vector) != len(variable_names):
        raise AugmentationError(
            "Gurobi incumbent length does not match the parent model variable order"
        )
    gap, gap_percent = _gap_pair(record.get("mip_gap"), None)
    source = Path(artifact).resolve()
    return IncumbentRecord(
        source_solver="gurobi",
        source_format="gurobi_incumbents_parquet",
        source_artifact=str(source),
        source_artifact_sha256=artifact_sha256,
        source_model_sha256=None,
        source_index=source_index,
        incumbent_id=f"gurobi:{artifact_sha256[:16]}:{source_index}",
        objective=_finite(record.get("objective"), field="incumbent objective"),
        admission_mip_gap_relative=gap,
        admission_mip_gap_percent=gap_percent,
        admission_mip_gap_measurement="callback_at_incumbent_discovery",
        terminal_mip_gap_relative=None,
        terminal_mip_gap_percent=None,
        execution_time_seconds=_finite(
            record.get("time"), field="incumbent time", nonnegative=True
        ),
        discovery_time_seconds=_finite(
            record.get("time"), field="incumbent time", nonnegative=True
        ),
        discovery_mip_gap_relative=gap,
        discovery_mip_gap_percent=gap_percent,
        values_by_name=dict(zip(variable_names, vector, strict=True)),
    )


def load_gurobi_parquet(
    path: str | Path,
    variable_names: Sequence[str],
    *,
    maximum_gap: float,
    incumbent_index: int | None,
) -> IncumbentRecord:
    try:
        import pandas as pd
    except ImportError as error:
        raise AugmentationError("pandas/pyarrow is required for Gurobi Parquet") from error
    source = Path(path).resolve()
    try:
        frame = pd.read_parquet(source)
    except Exception as error:
        raise AugmentationError("Gurobi incumbent Parquet is unreadable") from error
    required = {"objective", "mip_gap", "time", "solution_vector"}
    if frame.empty or not required.issubset(frame.columns):
        raise AugmentationError("Gurobi incumbent Parquet lacks required columns")
    rows = frame.reset_index(drop=True)
    if incumbent_index is None:
        candidates = []
        for index, row in rows.iterrows():
            gap = _finite(row["mip_gap"], field="MIP gap", nonnegative=True)
            if gap <= maximum_gap + 1e-12:
                candidates.append(
                    (
                        _finite(row["objective"], field="objective"),
                        gap,
                        _finite(row["time"], field="time", nonnegative=True),
                        int(index),
                    )
                )
        if not candidates:
            raise AugmentationError("no Gurobi incumbent satisfies the MIP-gap policy")
        incumbent_index = min(candidates)[-1]
    if incumbent_index < 0 or incumbent_index >= len(rows):
        raise AugmentationError("Gurobi incumbent index is out of range")
    record = rows.iloc[incumbent_index].to_dict()
    if _finite(record["mip_gap"], field="MIP gap", nonnegative=True) > maximum_gap + 1e-12:
        raise AugmentationError("selected Gurobi incumbent exceeds the MIP-gap policy")
    return incumbent_from_gurobi_record(
        record,
        variable_names,
        artifact=source,
        artifact_sha256=sha256_file(source),
        source_index=incumbent_index,
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _backend(name: str) -> Any:
    from cfl_gnn.augmentation.solver_backends import GurobiBackend, PyScipOptBackend

    return GurobiBackend() if name == "gurobi" else PyScipOptBackend()


def _slug(value: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
    return normalized.strip("_") or "instance"


def build_generation_plan(args: argparse.Namespace, config: Any) -> dict[str, Any]:
    operator_payload = operator_contract_payload(config)
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_contract_sha256": config.contract_sha256,
        "operator_contract": operator_payload,
        "operator_contract_sha256": _canonical_sha256(operator_payload),
        "solver": args.solver,
        "parent_instance_id": args.parent_instance_id,
        "category": args.category,
        "difficulty": args.difficulty,
        "fold": args.fold,
        "role": role_for_fold(args.fold, config.rotation),
        "parent_mip": str(args.parent_mip.resolve()),
        "parent_mip_sha256": sha256_file(args.parent_mip),
        "incumbent_artifact": str(args.incumbent_artifact.resolve()),
        "incumbent_artifact_sha256": sha256_file(args.incumbent_artifact),
        "incumbent_format": args.incumbent_format,
        "incumbent_index": args.incumbent_index,
        "objective_sense_required": "MINIMIZE",
        "maximum_admissible_relative_gap": (
            config.gap_policy.maximum_admissible_relative_gap
        ),
        "output_dir": str(args.output_dir.resolve()),
        "eligibility": {
            "dataset_eligible": False,
            "label_eligible": False,
            "scientific_reporting_eligible": False,
        },
    }


def run_generation(args: argparse.Namespace, config: Any) -> dict[str, Any]:
    backend = _backend(args.solver)
    inspection = backend.inspect(args.parent_mip)
    names = [variable.name for variable in inspection.variables]
    if args.incumbent_format == "gurobi_parquet":
        incumbent = load_gurobi_parquet(
            args.incumbent_artifact,
            names,
            maximum_gap=config.gap_policy.maximum_admissible_relative_gap,
            incumbent_index=args.incumbent_index,
        )
    else:
        incumbent = load_pyscipopt_solution(args.incumbent_artifact)
    if incumbent.source_solver != args.solver:
        raise AugmentationError("incumbent source solver and generation arm disagree")
    parent_sha256 = plan_parent_sha256 = sha256_file(args.parent_mip)
    if (
        incumbent.source_model_sha256 is not None
        and incumbent.source_model_sha256 != parent_sha256
    ):
        raise AugmentationError(
            "incumbent artifact is linked to a different parent MILP SHA-256"
        )
    if (
        incumbent.admission_mip_gap_relative
        > config.gap_policy.maximum_admissible_relative_gap + 1e-12
    ):
        raise AugmentationError("selected incumbent exceeds the MIP-gap policy")

    constraints = build_local_branching_constraints(
        inspection.variables,
        incumbent,
        radius_fractions=config.augmentation.radius_fractions,
        minimum_radius=config.augmentation.minimum_radius,
        maximum_derived=config.augmentation.maximum_derived_per_parent,
    )
    plan = build_generation_plan(args, config)
    if plan["parent_mip_sha256"] != plan_parent_sha256:
        raise AugmentationError("parent MILP changed while building the generation plan")
    outputs: list[dict[str, Any]] = []
    for constraint in constraints:
        stem = (
            f"{_slug(args.parent_instance_id)}__{args.solver}__"
            f"lb_r{constraint.radius}"
        )
        output = args.output_dir / f"{stem}.lp"
        provenance_path = args.output_dir / f"{stem}.provenance.json"
        if not args.overwrite and (output.exists() or provenance_path.exists()):
            raise FileExistsError(f"output exists: {output}")
        writer = backend.write_variant(args.parent_mip, output, constraint)
        provenance = {
            "schema_version": SCHEMA_VERSION,
            "experiment_contract_sha256": config.contract_sha256,
            "operator_contract_sha256": plan["operator_contract_sha256"],
            "constraint_sha256": constraint.constraint_sha256,
            "sample_status": "derived_mip_unlabelled",
            "solver": args.solver,
            "sampling_strategy": "incumbent_local_branching",
            "parent_instance_id": args.parent_instance_id,
            "category": args.category,
            "difficulty": args.difficulty,
            "fold": args.fold,
            "role": "train",
            "parent_mip": {
                "file_name": args.parent_mip.name,
                "sha256": plan["parent_mip_sha256"],
                "original_objective_sense": inspection.original_objective_sense,
                "effective_objective_sense": "MINIMIZE",
            },
            "source_incumbent": {
                "incumbent_id": incumbent.incumbent_id,
                "artifact_file_name": args.incumbent_artifact.name,
                "artifact_sha256": incumbent.source_artifact_sha256,
                "source_format": incumbent.source_format,
                "source_index": incumbent.source_index,
                "parent_linkage": (
                    "embedded_parent_sha256_match"
                    if incumbent.source_model_sha256 is not None
                    else "gurobi_positional_vector_and_parent_variable_order"
                ),
                "performance_feature_tags": incumbent.performance_tags(),
            },
            "local_branching": {
                **constraint.provenance_payload(),
            },
            "output": {
                "file_name": output.name,
                "sha256": sha256_file(output),
                **writer,
            },
            "parent_weighting": "equal_parent_mass",
            "eligibility": plan["eligibility"],
            "next_gate": "independent_derived_mip_solution_and_graph_generation",
        }
        _write_json(provenance_path, provenance)
        outputs.append(
            {
                "file_name": output.name,
                "sha256": provenance["output"]["sha256"],
                "provenance_file_name": provenance_path.name,
                "radius": constraint.radius,
                "radius_fraction": constraint.radius_fraction,
                "constraint_sha256": constraint.constraint_sha256,
            }
        )
    return {
        **plan,
        "probe_completed": True,
        "gate_status": "passed",
        "parent_model": {
            "original_objective_sense": inspection.original_objective_sense,
            "effective_objective_sense": "MINIMIZE",
            "variables": len(inspection.variables),
            "binary_variables": sum(v.is_binary for v in inspection.variables),
        },
        "source_incumbent": {
            "incumbent_id": incumbent.incumbent_id,
            "source_solver": incumbent.source_solver,
            "performance_feature_tags": incumbent.performance_tags(),
        },
        "summary": {
            "requested_radius_fractions": len(config.augmentation.radius_fractions),
            "distinct_integer_radii": len(constraints),
            "variants_written": len(outputs),
        },
        "outputs": outputs,
        "decision": {
            "operator_materialized": True,
            "solver_arm_consistent": True,
            "dataset_eligible": False,
            "label_eligible": False,
            "reason_code": "local_branching_variants_written_pending_independent_labels",
            "next_gate": "independent_derived_mip_solution_and_graph_generation",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate unlabelled local-branching MILPs for one solver arm."
    )
    parser.add_argument("--solver", choices=("gurobi", "scip"), required=True)
    parser.add_argument("--parent_mip", type=Path, required=True)
    parser.add_argument("--incumbent_artifact", type=Path, required=True)
    parser.add_argument(
        "--incumbent_format",
        choices=("gurobi_parquet", "pyscipopt_solution_json"),
        required=True,
    )
    parser.add_argument("--incumbent_index", type=int)
    parser.add_argument("--parent_instance_id", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--difficulty", choices=("easy", "medium", "hard"), required=True)
    parser.add_argument("--fold", type=int, choices=range(5), required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_experiment_config(args.config)
        if not args.parent_mip.is_file() or not args.incumbent_artifact.is_file():
            raise AugmentationError("parent MILP and incumbent artifact must exist")
        if (args.solver == "gurobi") != (args.incumbent_format == "gurobi_parquet"):
            raise AugmentationError("incumbent format must match the solver arm")
        role = role_for_fold(args.fold, config.rotation)
        if role != "train":
            raise AugmentationError(
                f"derived samples are train-only; fold {args.fold} is {role} "
                f"for rotation {config.rotation}"
            )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        plan = build_generation_plan(args, config)
        _write_json(args.output_dir / PLAN_NAME, plan)
        print(
            f"[INFO] solver={args.solver} | parent={args.parent_instance_id} | "
            f"operator={plan['operator_contract_sha256']} | dataset_eligible=false"
        )
        print(f"[INFO] Plan: {(args.output_dir / PLAN_NAME).resolve()}")
        if args.dry_run:
            return 0
        report = run_generation(args, config)
        _write_json(args.output_dir / REPORT_NAME, report)
        print(
            f"[INFO] gate=passed | variants={report['summary']['variants_written']} | "
            "labels=pending"
        )
        print(f"[INFO] Report: {(args.output_dir / REPORT_NAME).resolve()}")
        return 0
    except (AugmentationError, OSError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
