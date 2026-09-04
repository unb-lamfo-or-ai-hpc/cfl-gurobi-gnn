"""Solver-neutral planning contract for the four-arm TRL-6 MVP.

This module is dependency-free by design: it validates the experiment before
PyTorch, Gurobi, or PySCIPOpt is imported. Derived samples are statistical
descendants of their parent MILPBench instance and always inherit its fold.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.splits.instance_folds import InstanceFold, role_for_fold


SCHEMA_VERSION = 1
SOLVERS = ("gurobi", "scip")
SAMPLING_STRATEGIES = ("original", "incumbent_local_branching")
EXPECTED_ARMS = {
    (solver, sampling_strategy)
    for solver in SOLVERS
    for sampling_strategy in SAMPLING_STRATEGIES
}
ROLES = ("train", "validation", "test")


class ContractError(ValueError):
    """Raised when an MVP configuration or sample violates the protocol."""


def _finite_nonnegative(value: Any, *, field: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ContractError(f"{field} is not numeric") from error
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ContractError(f"{field} must be finite and nonnegative")
    return normalized


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ContractError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ContractError(f"{field} must be a positive integer") from error
    if normalized <= 0 or normalized != value:
        raise ContractError(f"{field} must be a positive integer")
    return normalized


def _required_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")
    return value.strip()


def _required_sha256(value: Any, *, field: str) -> str:
    digest = _required_string(value, field=field)
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ContractError(f"{field} must be a lowercase SHA-256 digest")
    return digest


def _assert_gap_units_match(relative: float, percent: float, *, field: str) -> None:
    if not math.isclose(percent, 100.0 * relative, rel_tol=1e-9, abs_tol=1e-9):
        raise ContractError(f"{field} relative and percentage values disagree")


def _string_tuple(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{field} must be a non-empty list")
    normalized = tuple(_required_string(item, field=field) for item in value)
    if len(set(normalized)) != len(normalized):
        raise ContractError(f"{field} must not contain duplicates")
    return normalized


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


@dataclass(frozen=True, slots=True)
class GapPolicy:
    """Maximum admitted label gap and precommitted sensitivity thresholds."""

    maximum_admissible_relative_gap: float
    sensitivity_thresholds_relative: tuple[float, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GapPolicy":
        maximum = _finite_nonnegative(
            value.get("maximum_admissible_relative_gap"),
            field="maximum_admissible_relative_gap",
        )
        raw_thresholds = value.get("sensitivity_thresholds_relative")
        if not isinstance(raw_thresholds, list) or not raw_thresholds:
            raise ContractError("sensitivity_thresholds_relative must be a list")
        thresholds = tuple(
            _finite_nonnegative(item, field="sensitivity threshold")
            for item in raw_thresholds
        )
        if thresholds != tuple(sorted(set(thresholds))):
            raise ContractError("sensitivity thresholds must be unique and increasing")
        if thresholds[-1] != maximum:
            raise ContractError("the maximum gap must be the last sensitivity threshold")
        if maximum > 0.10:
            raise ContractError("the MVP does not admit labels above 10% MIP gap")
        return cls(maximum, thresholds)

    def accepts(self, relative_gap: float) -> bool:
        gap = _finite_nonnegative(relative_gap, field="label mip gap")
        return gap <= self.maximum_admissible_relative_gap + 1e-12

    def sensitivity_memberships(self, relative_gap: float) -> tuple[str, ...]:
        gap = _finite_nonnegative(relative_gap, field="label mip gap")
        return tuple(
            f"gap_le_{threshold:g}"
            for threshold in self.sensitivity_thresholds_relative
            if gap <= threshold + 1e-12
        )


@dataclass(frozen=True, slots=True)
class ExperimentArm:
    arm_id: str
    solver: str
    sampling_strategy: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExperimentArm":
        arm_id = _required_string(value.get("arm_id"), field="arm_id")
        solver = _required_string(value.get("solver"), field="solver").lower()
        sampling = _required_string(
            value.get("sampling_strategy"), field="sampling_strategy"
        ).lower()
        if solver not in SOLVERS:
            raise ContractError(f"unknown solver in {arm_id}: {solver}")
        if sampling not in SAMPLING_STRATEGIES:
            raise ContractError(f"unknown sampling strategy in {arm_id}: {sampling}")
        return cls(arm_id, solver, sampling)


@dataclass(frozen=True, slots=True)
class AugmentationPolicy:
    operator: str
    binary_variables_only: bool
    radius_fractions: tuple[float, ...]
    minimum_radius: int
    maximum_derived_per_parent: int
    train_only: bool
    inherit_parent_fold: bool
    parent_weighting: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AugmentationPolicy":
        operator = _required_string(value.get("operator"), field="operator")
        if operator != "incumbent_local_branching_v1":
            raise ContractError("the MVP requires incumbent_local_branching_v1")
        radius = value.get("radius_policy")
        if not isinstance(radius, Mapping):
            raise ContractError("radius_policy must be an object")
        if radius.get("mode") != "fraction_of_binary_variables":
            raise ContractError("local-branching radius must be a binary-variable fraction")
        raw_fractions = radius.get("fractions")
        if not isinstance(raw_fractions, list) or not raw_fractions:
            raise ContractError("radius fractions must be a non-empty list")
        fractions = tuple(
            _finite_nonnegative(item, field="radius fraction")
            for item in raw_fractions
        )
        if fractions != tuple(sorted(set(fractions))) or any(
            item <= 0.0 or item > 1.0 for item in fractions
        ):
            raise ContractError("radius fractions must be unique, increasing, and in (0, 1]")
        binary_only = value.get("binary_variables_only")
        train_only = value.get("train_only")
        inherit = value.get("inherit_parent_fold")
        if binary_only is not True or train_only is not True or inherit is not True:
            raise ContractError(
                "augmentation must be binary-only, train-only, and inherit parent folds"
            )
        weighting = _required_string(
            value.get("parent_weighting"), field="parent_weighting"
        )
        if weighting != "equal_parent_mass":
            raise ContractError("the MVP requires equal_parent_mass weighting")
        maximum = _positive_int(
            value.get("maximum_derived_per_parent"),
            field="maximum_derived_per_parent",
        )
        if maximum > len(fractions):
            raise ContractError(
                "maximum_derived_per_parent exceeds the precommitted radius count"
            )
        return cls(
            operator=operator,
            binary_variables_only=True,
            radius_fractions=fractions,
            minimum_radius=_positive_int(
                radius.get("minimum_radius"), field="minimum_radius"
            ),
            maximum_derived_per_parent=maximum,
            train_only=True,
            inherit_parent_fold=True,
            parent_weighting=weighting,
        )


@dataclass(frozen=True, slots=True)
class MvpExperimentConfig:
    experiment_id: str
    development_only: bool
    rotation: int
    objective_sense: str
    gap_policy: GapPolicy
    augmentation: AugmentationPolicy
    arms: tuple[ExperimentArm, ...]
    validation_test_original_only: bool
    test_reference: str
    classification_probability_threshold: float
    optimization_primary_metrics: tuple[str, ...]
    optimization_diagnostic_metrics: tuple[str, ...]
    prediction_secondary_metrics: tuple[str, ...]

    @property
    def contract_sha256(self) -> str:
        return _sha256_payload(self.to_contract())

    def to_contract(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "experiment_id": self.experiment_id,
            "development_only": self.development_only,
            "rotation": self.rotation,
            "objective_sense": self.objective_sense,
            "gap_policy": {
                "maximum_admissible_relative_gap": (
                    self.gap_policy.maximum_admissible_relative_gap
                ),
                "sensitivity_thresholds_relative": list(
                    self.gap_policy.sensitivity_thresholds_relative
                ),
            },
            "augmentation": {
                "operator": self.augmentation.operator,
                "binary_variables_only": self.augmentation.binary_variables_only,
                "radius_policy": {
                    "mode": "fraction_of_binary_variables",
                    "fractions": list(self.augmentation.radius_fractions),
                    "minimum_radius": self.augmentation.minimum_radius,
                },
                "maximum_derived_per_parent": (
                    self.augmentation.maximum_derived_per_parent
                ),
                "train_only": self.augmentation.train_only,
                "inherit_parent_fold": self.augmentation.inherit_parent_fold,
                "parent_weighting": self.augmentation.parent_weighting,
            },
            "arms": [
                {
                    "arm_id": arm.arm_id,
                    "solver": arm.solver,
                    "sampling_strategy": arm.sampling_strategy,
                }
                for arm in self.arms
            ],
            "evaluation": {
                "validation_test_original_only": (
                    self.validation_test_original_only
                ),
                "test_reference": self.test_reference,
                "classification_probability_threshold": (
                    self.classification_probability_threshold
                ),
            },
            "metrics": {
                "optimization_primary": list(self.optimization_primary_metrics),
                "optimization_diagnostic": list(
                    self.optimization_diagnostic_metrics
                ),
                "prediction_secondary": list(self.prediction_secondary_metrics),
            },
            "exploratory_arms": [
                {
                    "solver": "scip",
                    "sampling_strategy": "scip_exact_node_mip",
                    "included_in_factorial_comparison": False,
                }
            ],
        }


@dataclass(frozen=True, slots=True)
class MvpSampleRecord:
    """One graph/label artifact declared by a future dataset-producing sprint."""

    sample_id: str
    parent_instance_id: str
    category: str
    difficulty: str
    fold: int
    solver: str
    sampling_strategy: str
    graph_path: str
    graph_sha256: str
    label_source: str
    label_solution_sha256: str
    label_objective: float
    label_mip_gap_relative: float
    label_mip_gap_percent: float
    label_execution_time_seconds: float
    source_incumbent_id: str | None
    source_incumbent_artifact_sha256: str | None
    source_incumbent_objective: float | None
    source_incumbent_mip_gap_relative: float | None
    source_incumbent_mip_gap_percent: float | None
    source_incumbent_execution_time_seconds: float | None
    local_branching_radius: int | None
    local_branching_radius_fraction: float | None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MvpSampleRecord":
        solver = _required_string(value.get("solver"), field="solver").lower()
        sampling = _required_string(
            value.get("sampling_strategy"), field="sampling_strategy"
        ).lower()
        if solver not in SOLVERS or sampling not in SAMPLING_STRATEGIES:
            raise ContractError("sample has an unknown solver or sampling strategy")
        try:
            fold = int(value.get("fold"))
        except (TypeError, ValueError, OverflowError) as error:
            raise ContractError("sample fold must be an integer") from error
        source_incumbent = value.get("source_incumbent_id")
        source_incumbent_digest = value.get("source_incumbent_artifact_sha256")
        source_incumbent_objective = value.get("source_incumbent_objective")
        source_incumbent_gap = value.get("source_incumbent_mip_gap_relative")
        source_incumbent_gap_percent = value.get("source_incumbent_mip_gap_percent")
        source_incumbent_time = value.get("source_incumbent_execution_time_seconds")
        radius = value.get("local_branching_radius")
        radius_fraction = value.get("local_branching_radius_fraction")
        if sampling == "incumbent_local_branching":
            source_incumbent = _required_string(
                source_incumbent, field="source_incumbent_id"
            )
            radius = _positive_int(radius, field="local_branching_radius")
            radius_fraction = _finite_nonnegative(
                radius_fraction, field="local_branching_radius_fraction"
            )
            if not 0.0 < radius_fraction <= 1.0:
                raise ContractError("local_branching_radius_fraction must be in (0, 1]")
            source_incumbent_digest = _required_sha256(
                source_incumbent_digest, field="source_incumbent_artifact_sha256"
            )
            try:
                source_incumbent_objective = float(source_incumbent_objective)
            except (TypeError, ValueError, OverflowError) as error:
                raise ContractError("source incumbent objective must be numeric") from error
            if not math.isfinite(source_incumbent_objective):
                raise ContractError("source incumbent objective must be finite")
            source_incumbent_gap = _finite_nonnegative(
                source_incumbent_gap, field="source_incumbent_mip_gap_relative"
            )
            source_incumbent_gap_percent = _finite_nonnegative(
                source_incumbent_gap_percent,
                field="source_incumbent_mip_gap_percent",
            )
            _assert_gap_units_match(
                source_incumbent_gap,
                source_incumbent_gap_percent,
                field="source incumbent mip gap",
            )
            source_incumbent_time = _finite_nonnegative(
                source_incumbent_time,
                field="source_incumbent_execution_time_seconds",
            )
        elif any(
            item is not None
            for item in (
                source_incumbent,
                source_incumbent_digest,
                source_incumbent_objective,
                source_incumbent_gap,
                source_incumbent_gap_percent,
                source_incumbent_time,
                radius,
                radius_fraction,
            )
        ):
            raise ContractError("original samples cannot declare derivation fields")
        objective = float(value.get("label_objective"))
        if not math.isfinite(objective):
            raise ContractError("label_objective must be finite")
        digest = _required_sha256(value.get("graph_sha256"), field="graph_sha256")
        label_gap = _finite_nonnegative(
            value.get("label_mip_gap_relative"), field="label_mip_gap_relative"
        )
        label_gap_percent = _finite_nonnegative(
            value.get("label_mip_gap_percent"), field="label_mip_gap_percent"
        )
        _assert_gap_units_match(label_gap, label_gap_percent, field="label mip gap")
        return cls(
            sample_id=_required_string(value.get("sample_id"), field="sample_id"),
            parent_instance_id=_required_string(
                value.get("parent_instance_id"), field="parent_instance_id"
            ),
            category=_required_string(value.get("category"), field="category"),
            difficulty=_required_string(value.get("difficulty"), field="difficulty"),
            fold=fold,
            solver=solver,
            sampling_strategy=sampling,
            graph_path=_required_string(value.get("graph_path"), field="graph_path"),
            graph_sha256=digest,
            label_source=_required_string(
                value.get("label_source"), field="label_source"
            ),
            label_solution_sha256=_required_sha256(
                value.get("label_solution_sha256"), field="label_solution_sha256"
            ),
            label_objective=objective,
            label_mip_gap_relative=label_gap,
            label_mip_gap_percent=label_gap_percent,
            label_execution_time_seconds=_finite_nonnegative(
                value.get("label_execution_time_seconds"),
                field="label_execution_time_seconds",
            ),
            source_incumbent_id=source_incumbent,
            source_incumbent_artifact_sha256=source_incumbent_digest,
            source_incumbent_objective=source_incumbent_objective,
            source_incumbent_mip_gap_relative=source_incumbent_gap,
            source_incumbent_mip_gap_percent=source_incumbent_gap_percent,
            source_incumbent_execution_time_seconds=source_incumbent_time,
            local_branching_radius=radius,
            local_branching_radius_fraction=radius_fraction,
        )


def load_experiment_config(path: str | Path) -> MvpExperimentConfig:
    """Read and validate the complete, precommitted MVP configuration."""
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise ContractError("experiment configuration is unreadable") from error
    if not isinstance(value, Mapping) or value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("unsupported experiment configuration schema")
    raw_arms = value.get("arms")
    if not isinstance(raw_arms, list):
        raise ContractError("arms must be a list")
    arms = tuple(ExperimentArm.from_mapping(item) for item in raw_arms)
    combinations = {(arm.solver, arm.sampling_strategy) for arm in arms}
    if len(arms) != 4 or combinations != EXPECTED_ARMS:
        raise ContractError("the MVP requires exactly the solver x sampling 2x2 arms")
    if len({arm.arm_id for arm in arms}) != len(arms):
        raise ContractError("arm identifiers must be unique")
    evaluation = value.get("evaluation")
    if not isinstance(evaluation, Mapping):
        raise ContractError("evaluation must be an object")
    if evaluation.get("validation_test_original_only") is not True:
        raise ContractError("validation and test must contain original parents only")
    probability_threshold = _finite_nonnegative(
        evaluation.get("classification_probability_threshold"),
        field="classification_probability_threshold",
    )
    if probability_threshold > 1.0:
        raise ContractError("classification_probability_threshold must be in [0, 1]")
    if value.get("development_only") is not True:
        raise ContractError("the partial-inventory MVP must be development_only")
    rotation = value.get("rotation")
    if not isinstance(rotation, int) or not 0 <= rotation < 5:
        raise ContractError("rotation must be an integer in [0, 4]")
    if value.get("objective_sense") != "MINIMIZE":
        raise ContractError("the corrected CFL objective sense must be MINIMIZE")
    gap_policy_value = value.get("gap_policy", {})
    if not isinstance(gap_policy_value, Mapping):
        raise ContractError("gap_policy must be an object")
    if gap_policy_value.get("missing_gap_eligible") is not False:
        raise ContractError("labels with missing MIP gap must fail closed")
    metrics = value.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ContractError("metrics must be an object")
    metric_groups = {
        name: _string_tuple(metrics.get(name), field=name)
        for name in (
            "optimization_primary",
            "optimization_diagnostic",
            "prediction_secondary",
        )
    }
    exploratory = value.get("exploratory_arms")
    expected_exploratory = [
        {
            "included_in_factorial_comparison": False,
            "sampling_strategy": "scip_exact_node_mip",
            "solver": "scip",
        }
    ]
    if exploratory != expected_exploratory:
        raise ContractError("exact SCIP node MIPs must remain exploratory")
    return MvpExperimentConfig(
        experiment_id=_required_string(
            value.get("experiment_id"), field="experiment_id"
        ),
        development_only=True,
        rotation=rotation,
        objective_sense="MINIMIZE",
        gap_policy=GapPolicy.from_mapping(gap_policy_value),
        augmentation=AugmentationPolicy.from_mapping(
            value.get("augmentation", {})
        ),
        arms=arms,
        validation_test_original_only=True,
        test_reference=_required_string(
            evaluation.get("test_reference"), field="test_reference"
        ),
        classification_probability_threshold=probability_threshold,
        optimization_primary_metrics=metric_groups["optimization_primary"],
        optimization_diagnostic_metrics=metric_groups[
            "optimization_diagnostic"
        ],
        prediction_secondary_metrics=metric_groups["prediction_secondary"],
    )


def read_sample_manifest(path: str | Path) -> tuple[MvpSampleRecord, ...]:
    """Read a JSON-lines sample manifest without loading any graph."""
    source = Path(path)
    records: list[MvpSampleRecord] = []
    try:
        with source.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                    if not isinstance(value, Mapping):
                        raise ContractError("record is not an object")
                    records.append(MvpSampleRecord.from_mapping(value))
                except (ValueError, TypeError) as error:
                    raise ContractError(
                        f"invalid sample manifest record at line {line_number}: {error}"
                    ) from error
    except OSError as error:
        raise ContractError("sample manifest is unreadable") from error
    return tuple(records)


def _validate_samples(
    config: MvpExperimentConfig,
    parent_manifest: Sequence[InstanceFold],
    samples: Sequence[MvpSampleRecord],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parents = {entry.source_instance_id: entry for entry in parent_manifest}
    seen_samples: set[str] = set()
    eligible: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    derived_count: Counter[tuple[str, str]] = Counter()

    for sample in samples:
        reasons: list[str] = []
        parent = parents.get(sample.parent_instance_id)
        if sample.sample_id in seen_samples:
            reasons.append("duplicate_sample_id")
        seen_samples.add(sample.sample_id)
        if parent is None:
            reasons.append("unknown_parent")
            role = None
        else:
            role = role_for_fold(parent.fold, config.rotation)
            if (
                sample.fold != parent.fold
                or sample.category != parent.category
                or sample.difficulty != parent.difficulty
            ):
                reasons.append("parent_contract_mismatch")
        if sample.sampling_strategy == "incumbent_local_branching":
            if role != "train":
                reasons.append("derived_sample_outside_train")
            key = (sample.solver, sample.parent_instance_id)
            derived_count[key] += 1
            if derived_count[key] > config.augmentation.maximum_derived_per_parent:
                reasons.append("derived_parent_cap_exceeded")
            if (
                sample.local_branching_radius_fraction
                not in config.augmentation.radius_fractions
            ):
                reasons.append("unplanned_local_branching_radius")
        if not config.gap_policy.accepts(sample.label_mip_gap_relative):
            reasons.append("label_gap_above_maximum")

        item = {
            "sample_id": sample.sample_id,
            "parent_instance_id": sample.parent_instance_id,
            "solver": sample.solver,
            "sampling_strategy": sample.sampling_strategy,
            "fold": sample.fold,
            "role": role,
            "label_mip_gap_relative": sample.label_mip_gap_relative,
            "label_mip_gap_percent": sample.label_mip_gap_percent,
            "label_execution_time_seconds": sample.label_execution_time_seconds,
            "source_incumbent_performance": (
                {
                    "objective": sample.source_incumbent_objective,
                    "mip_gap_relative": sample.source_incumbent_mip_gap_relative,
                    "mip_gap_percent": sample.source_incumbent_mip_gap_percent,
                    "execution_time_seconds": (
                        sample.source_incumbent_execution_time_seconds
                    ),
                }
                if sample.sampling_strategy == "incumbent_local_branching"
                else None
            ),
            "sensitivity_memberships": list(
                config.gap_policy.sensitivity_memberships(
                    sample.label_mip_gap_relative
                )
            ),
        }
        if reasons:
            item["reasons"] = sorted(set(reasons))
            invalid.append(item)
        else:
            eligible.append(item)
    return eligible, invalid


def build_mvp_plan(
    config: MvpExperimentConfig,
    parent_manifest: Sequence[InstanceFold],
    samples: Sequence[MvpSampleRecord] = (),
) -> dict[str, Any]:
    """Validate an inventory and return a path-sanitized execution plan."""
    eligible, invalid = _validate_samples(config, parent_manifest, samples)
    by_arm = defaultdict(lambda: {role: 0 for role in ROLES})
    by_sensitivity: Counter[str] = Counter()
    parents_by_role: dict[str, set[str]] = {role: set() for role in ROLES}
    for item in eligible:
        arm_id = next(
            arm.arm_id
            for arm in config.arms
            if arm.solver == item["solver"]
            and arm.sampling_strategy == item["sampling_strategy"]
        )
        by_arm[arm_id][item["role"]] += 1
        parents_by_role[item["role"]].add(item["parent_instance_id"])
        by_sensitivity.update(item["sensitivity_memberships"])

    cross_role = sorted(
        parent
        for parent in set().union(*parents_by_role.values())
        if sum(parent in values for values in parents_by_role.values()) > 1
    )
    if cross_role:
        invalid.extend(
            {
                "sample_id": None,
                "parent_instance_id": parent,
                "reasons": ["parent_leakage_across_roles"],
            }
            for parent in cross_role
        )
    plan = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": config.experiment_id,
        "contract_sha256": config.contract_sha256,
        "development_only": config.development_only,
        "scientific_reporting_eligible": False,
        "rotation": config.rotation,
        "objective_sense": config.objective_sense,
        "planned_parent_population": len(parent_manifest),
        "samples_declared": len(samples),
        "samples_eligible": len(eligible),
        "samples_invalid": len(invalid),
        "contract_valid": not invalid,
        "gap_policy": {
            "maximum_admissible_relative_gap": (
                config.gap_policy.maximum_admissible_relative_gap
            ),
            "sensitivity_thresholds_relative": list(
                config.gap_policy.sensitivity_thresholds_relative
            ),
            "eligible_by_sensitivity": dict(sorted(by_sensitivity.items())),
        },
        "augmentation": {
            "operator": config.augmentation.operator,
            "train_only": True,
            "parent_weighting": config.augmentation.parent_weighting,
            "maximum_derived_per_parent": (
                config.augmentation.maximum_derived_per_parent
            ),
        },
        "arms": {
            arm.arm_id: {
                "solver": arm.solver,
                "sampling_strategy": arm.sampling_strategy,
                "partitions": dict(by_arm[arm.arm_id]),
            }
            for arm in config.arms
        },
        "evaluation": {
            "validation_test_original_only": True,
            "test_reference": config.test_reference,
            "classification_probability_threshold": (
                config.classification_probability_threshold
            ),
        },
        "metrics": {
            "optimization_primary": list(config.optimization_primary_metrics),
            "optimization_diagnostic": list(
                config.optimization_diagnostic_metrics
            ),
            "prediction_secondary": list(config.prediction_secondary_metrics),
        },
        "invalid_samples": invalid,
        "next_gate": (
            "dataset_generation" if not invalid else "repair_sample_contract"
        ),
    }
    return plan


def write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
