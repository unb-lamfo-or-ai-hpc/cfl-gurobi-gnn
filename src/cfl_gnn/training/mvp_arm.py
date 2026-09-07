"""Dependency-free contracts for loading the four MVP training arms.

The dataset composition stage stores one manifest per arm.  This module checks
those manifests before PyTorch is imported, applies a precommitted label-gap
threshold, intersects the eligible training parents across all four arms, and
constructs a deterministic schedule with exactly equal draws per parent.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.experiments.mvp_contract import (
    MvpExperimentConfig,
    MvpSampleRecord,
    load_experiment_config,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.splits.instance_folds import role_for_fold


SCHEMA_VERSION = 1
POLICY_SCHEMA_VERSION = 1
PLAN_NAME = "mvp_training_data_plan.json"
AUDIT_NAME = "mvp_training_data_audit.json"
COMPOSITION_PLAN_NAME = "mvp_dataset_composition_plan.json"
COMPOSITION_REPORT_NAME = "mvp_dataset_composition_report.json"
UNIFIED_MANIFEST_NAME = "mvp_sample_manifest.jsonl"
REFERENCE_MANIFEST_NAME = "evaluation_reference_manifest.jsonl"
ARM_DIR_NAME = "arms"
ROLES = ("train", "validation", "test")


class MvpTrainingDataError(ValueError):
    """Raised when a four-arm training-data contract fails closed."""


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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise MvpTrainingDataError(f"unreadable JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise MvpTrainingDataError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    line_number = 0
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise TypeError("record is not an object")
                result.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise MvpTrainingDataError(
            f"unreadable JSONL artifact: {path.name}:{line_number}"
        ) from error
    return result


def _finite_nonnegative(value: Any, *, field: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise MvpTrainingDataError(f"{field} must be numeric") from error
    if not math.isfinite(normalized) or normalized < 0.0:
        raise MvpTrainingDataError(f"{field} must be finite and nonnegative")
    return normalized


def _finite(value: Any, *, field: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise MvpTrainingDataError(f"{field} must be numeric") from error
    if not math.isfinite(normalized):
        raise MvpTrainingDataError(f"{field} must be finite")
    return normalized


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise MvpTrainingDataError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise MvpTrainingDataError(f"{field} must be a positive integer") from error
    if normalized <= 0 or normalized != value:
        raise MvpTrainingDataError(f"{field} must be a positive integer")
    return normalized


def _required_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MvpTrainingDataError(f"{field} must be a non-empty string")
    return value.strip()


def _required_sha256(value: Any, *, field: str) -> str:
    digest = _required_string(value, field=field)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise MvpTrainingDataError(f"{field} must be a lowercase SHA-256 digest")
    return digest


def _safe_artifact(dataset_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise MvpTrainingDataError("graph path is not relative to the dataset root")
    root = dataset_root.resolve()
    resolved = (root / relative).resolve()
    if resolved == root or root not in resolved.parents:
        raise MvpTrainingDataError("graph path escapes the dataset root")
    if not resolved.is_file():
        raise MvpTrainingDataError(f"missing graph artifact: {relative.as_posix()}")
    return resolved


@dataclass(frozen=True, slots=True)
class MvpLoaderPolicy:
    """Precommitted data-selection and parent-balancing policy."""

    policy_id: str
    gap_threshold_relative: float
    sampler: str
    seed: int
    draws_per_parent_per_epoch: int
    training_parent_set: str
    validation_reference: str
    test_access_policy: str

    @property
    def contract_payload(self) -> dict[str, Any]:
        return {
            "schema_version": POLICY_SCHEMA_VERSION,
            "policy_id": self.policy_id,
            "gap_threshold_relative": self.gap_threshold_relative,
            "sampler": self.sampler,
            "seed": self.seed,
            "draws_per_parent_per_epoch": self.draws_per_parent_per_epoch,
            "training_parent_set": self.training_parent_set,
            "validation_reference": self.validation_reference,
            "test_access_policy": self.test_access_policy,
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MvpLoaderPolicy":
        if value.get("schema_version") != POLICY_SCHEMA_VERSION:
            raise MvpTrainingDataError("unsupported loader-policy schema")
        gap = _finite_nonnegative(
            value.get("gap_threshold_relative"), field="gap_threshold_relative"
        )
        if gap > 0.10:
            raise MvpTrainingDataError("the loader cannot admit labels above 10% gap")
        if value.get("sampler") != "deterministic_parent_balanced_cycle_v1":
            raise MvpTrainingDataError("unsupported parent-balancing sampler")
        if value.get("training_parent_set") != "intersection_across_all_four_arms":
            raise MvpTrainingDataError(
                "training parents must be intersected across arms"
            )
        if value.get("validation_reference") != (
            "best_known_across_valid_gurobi_and_scip_artifacts"
        ):
            raise MvpTrainingDataError(
                "validation must use the common best-known reference"
            )
        if value.get("test_access_policy") != "held_out_not_loaded_during_training":
            raise MvpTrainingDataError("the test partition must remain held out")
        raw_seed = value.get("seed")
        if isinstance(raw_seed, bool):
            raise MvpTrainingDataError("seed must be an integer")
        try:
            seed = int(raw_seed)
        except (TypeError, ValueError, OverflowError) as error:
            raise MvpTrainingDataError("seed must be an integer") from error
        if seed != raw_seed:
            raise MvpTrainingDataError("seed must be an integer")
        return cls(
            policy_id=_required_string(value.get("policy_id"), field="policy_id"),
            gap_threshold_relative=gap,
            sampler=str(value["sampler"]),
            seed=seed,
            draws_per_parent_per_epoch=_positive_int(
                value.get("draws_per_parent_per_epoch"),
                field="draws_per_parent_per_epoch",
            ),
            training_parent_set=str(value["training_parent_set"]),
            validation_reference=str(value["validation_reference"]),
            test_access_policy=str(value["test_access_policy"]),
        )


def load_loader_policy(path: str | Path) -> MvpLoaderPolicy:
    """Read a versioned loader policy without importing the ML stack."""
    return MvpLoaderPolicy.from_mapping(_read_json(Path(path)))


@dataclass(frozen=True, slots=True)
class ArmSample:
    """One validated arm-manifest row."""

    sample: MvpSampleRecord
    arm_id: str
    role: str
    stored_sample_weight: float

    @property
    def sample_id(self) -> str:
        return self.sample.sample_id

    @property
    def parent_instance_id(self) -> str:
        return self.sample.parent_instance_id

    def selected_payload(
        self, *, common_parent_count: int, eligible_siblings: int
    ) -> dict[str, Any]:
        return {
            "sample_id": self.sample.sample_id,
            "parent_instance_id": self.sample.parent_instance_id,
            "category": self.sample.category,
            "difficulty": self.sample.difficulty,
            "fold": self.sample.fold,
            "role": self.role,
            "solver": self.sample.solver,
            "sampling_strategy": self.sample.sampling_strategy,
            "graph_path": self.sample.graph_path,
            "graph_sha256": self.sample.graph_sha256,
            "label_solution_sha256": self.sample.label_solution_sha256,
            "label_mip_gap_relative": self.sample.label_mip_gap_relative,
            "label_mip_gap_percent": self.sample.label_mip_gap_percent,
            "label_objective": self.sample.label_objective,
            "label_execution_time_seconds": self.sample.label_execution_time_seconds,
            "stored_sample_weight": self.stored_sample_weight,
            "effective_within_parent_weight": 1.0 / eligible_siblings,
            "effective_sampling_probability": (
                1.0 / (common_parent_count * eligible_siblings)
            ),
        }


def _arm_sample(
    value: Mapping[str, Any], *, arm_id: str, config: MvpExperimentConfig
) -> ArmSample:
    sample = MvpSampleRecord.from_mapping(value)
    declared_arm = _required_string(value.get("arm_id"), field="arm_id")
    if declared_arm != arm_id:
        raise MvpTrainingDataError("arm manifest contains a foreign arm identifier")
    role = _required_string(value.get("role"), field="role")
    if role not in ROLES or role != role_for_fold(sample.fold, config.rotation):
        raise MvpTrainingDataError("arm role does not match the canonical parent fold")
    if value.get("weighting_policy") != "equal_parent_mass":
        raise MvpTrainingDataError("arm row does not declare equal_parent_mass")
    weight = _finite_nonnegative(value.get("sample_weight"), field="sample_weight")
    if weight <= 0.0:
        raise MvpTrainingDataError("sample_weight must be positive")
    return ArmSample(sample, arm_id, role, weight)


def _validate_stored_parent_mass(records: Sequence[ArmSample]) -> None:
    mass: dict[tuple[str, str], float] = defaultdict(float)
    for record in records:
        mass[(record.role, record.parent_instance_id)] += record.stored_sample_weight
        if record.role != "train" and record.sample.sampling_strategy != "original":
            raise MvpTrainingDataError("validation/test contains a derived sample")
    if any(not math.isclose(value, 1.0, abs_tol=1e-12) for value in mass.values()):
        raise MvpTrainingDataError("stored arm weights do not sum to one per parent")


def _load_reference_records(
    raw_references: Sequence[Mapping[str, Any]],
    unified: Mapping[str, MvpSampleRecord],
    *,
    config: MvpExperimentConfig,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    seen: set[str] = set()
    for reference in raw_references:
        parent_id = _required_string(
            reference.get("parent_instance_id"), field="reference parent_instance_id"
        )
        if parent_id in seen:
            raise MvpTrainingDataError("duplicate parent in evaluation reference")
        seen.add(parent_id)
        role = _required_string(reference.get("role"), field="reference role")
        solver = _required_string(
            reference.get("selected_solver"), field="selected_solver"
        ).lower()
        candidates = [
            sample
            for sample in unified.values()
            if sample.parent_instance_id == parent_id
            and sample.solver == solver
            and sample.sampling_strategy == "original"
        ]
        if len(candidates) != 1:
            raise MvpTrainingDataError("reference does not select one original graph")
        selected = candidates[0]
        canonical_role = role_for_fold(selected.fold, config.rotation)
        if role != canonical_role or role not in ROLES:
            raise MvpTrainingDataError("reference role does not match the parent fold")
        digest = _required_sha256(
            reference.get("label_solution_sha256"),
            field="reference label_solution_sha256",
        )
        if digest != selected.label_solution_sha256:
            raise MvpTrainingDataError(
                "reference solution hash does not match the graph label"
            )
        if reference.get("selection_policy") != (
            "minimum_objective_then_gap_time_solver"
        ):
            raise MvpTrainingDataError(
                "unexpected evaluation-reference selection policy"
            )
        reference_metrics = (
            ("label_objective", selected.label_objective),
            ("label_mip_gap_relative", selected.label_mip_gap_relative),
            ("label_execution_time_seconds", selected.label_execution_time_seconds),
        )
        for field, expected in reference_metrics:
            observed = _finite(reference.get(field), field=field)
            if not math.isclose(observed, expected, rel_tol=1e-9, abs_tol=1e-9):
                raise MvpTrainingDataError(
                    f"evaluation reference disagrees with selected label: {field}"
                )
        if reference.get("candidate_count") != 2:
            raise MvpTrainingDataError(
                "evaluation reference must compare the two solver labels"
            )
        result[role].append(
            {
                "sample_id": selected.sample_id,
                "parent_instance_id": parent_id,
                "category": selected.category,
                "difficulty": selected.difficulty,
                "fold": selected.fold,
                "role": role,
                "selected_solver": solver,
                "graph_path": selected.graph_path,
                "graph_sha256": selected.graph_sha256,
                "label_solution_sha256": selected.label_solution_sha256,
                "label_objective": selected.label_objective,
                "label_mip_gap_relative": selected.label_mip_gap_relative,
                "label_execution_time_seconds": selected.label_execution_time_seconds,
                "selection_policy": str(reference["selection_policy"]),
            }
        )
    return {
        role: sorted(records, key=lambda item: item["parent_instance_id"])
        for role, records in result.items()
    }


def _arm_expectations(config: MvpExperimentConfig) -> dict[str, tuple[str, str]]:
    return {
        arm.arm_id: (arm.solver, arm.sampling_strategy) for arm in config.arms
    }


def _validate_arm_membership(
    arm_id: str,
    records: Sequence[ArmSample],
    *,
    solver: str,
    sampling_strategy: str,
) -> None:
    if not records:
        raise MvpTrainingDataError(f"empty arm manifest: {arm_id}")
    ids = [record.sample_id for record in records]
    if len(ids) != len(set(ids)):
        raise MvpTrainingDataError(f"duplicate sample in arm: {arm_id}")
    for record in records:
        if record.sample.solver != solver:
            raise MvpTrainingDataError(f"arm {arm_id} contains another solver")
        if sampling_strategy == "original":
            allowed = {"original"}
        else:
            allowed = {"original", "incumbent_local_branching"}
        if record.sample.sampling_strategy not in allowed:
            raise MvpTrainingDataError(
                f"arm {arm_id} contains an invalid sampling strategy"
            )


def build_training_data_plan(
    dataset_dir: str | Path,
    *,
    experiment_config_path: str | Path,
    loader_policy_path: str | Path,
    verify_graph_hashes: bool = True,
) -> dict[str, Any]:
    """Validate the four arms and return a path-sanitized training-data plan."""
    root = Path(dataset_dir).resolve()
    config = load_experiment_config(experiment_config_path)
    policy = load_loader_policy(loader_policy_path)
    if not any(
        math.isclose(policy.gap_threshold_relative, threshold, abs_tol=1e-12)
        for threshold in config.gap_policy.sensitivity_thresholds_relative
    ):
        raise MvpTrainingDataError("loader gap threshold is not precommitted")

    composition_plan = _read_json(root / COMPOSITION_PLAN_NAME)
    composition_report = _read_json(root / COMPOSITION_REPORT_NAME)
    dataset_contract = _required_sha256(
        composition_report.get("contract_sha256"), field="dataset contract"
    )
    if composition_plan.get("contract_sha256") != dataset_contract:
        raise MvpTrainingDataError("composition plan/report contract mismatch")
    if composition_plan.get("experiment_contract_sha256") != config.contract_sha256:
        raise MvpTrainingDataError("dataset uses another MVP experiment contract")
    if (
        composition_report.get("gate_status") != "passed"
        or composition_report.get("eligibility", {}).get("dataset_eligible") is not True
        or composition_report.get("eligibility", {}).get("development_only") is not True
        or composition_report.get("eligibility", {}).get(
            "scientific_reporting_eligible"
        )
        is not False
    ):
        raise MvpTrainingDataError(
            "composition report is not an eligible development dataset"
        )

    output_contracts = composition_report.get("outputs", {})
    unified_path = root / UNIFIED_MANIFEST_NAME
    reference_path = root / REFERENCE_MANIFEST_NAME
    if sha256_file(unified_path) != output_contracts.get("sample_manifest_sha256"):
        raise MvpTrainingDataError("unified sample manifest hash mismatch")
    if sha256_file(reference_path) != output_contracts.get(
        "evaluation_reference_manifest_sha256"
    ):
        raise MvpTrainingDataError("evaluation-reference manifest hash mismatch")

    unified_values = _read_jsonl(unified_path)
    unified_records = [MvpSampleRecord.from_mapping(value) for value in unified_values]
    unified = {record.sample_id: record for record in unified_records}
    if len(unified) != len(unified_records):
        raise MvpTrainingDataError("duplicate sample in unified manifest")

    arm_expectations = _arm_expectations(config)
    arm_records: dict[str, list[ArmSample]] = {}
    arm_manifest_hashes: dict[str, str] = {}
    parents_by_arm_role: dict[str, dict[str, set[str]]] = {}
    for arm_id, (solver, sampling_strategy) in sorted(arm_expectations.items()):
        path = root / ARM_DIR_NAME / f"{arm_id}.jsonl"
        digest = sha256_file(path)
        if digest != composition_report.get("arms", {}).get(arm_id, {}).get("sha256"):
            raise MvpTrainingDataError(f"arm manifest hash mismatch: {arm_id}")
        records = [
            _arm_sample(value, arm_id=arm_id, config=config)
            for value in _read_jsonl(path)
        ]
        _validate_arm_membership(
            arm_id,
            records,
            solver=solver,
            sampling_strategy=sampling_strategy,
        )
        _validate_stored_parent_mass(records)
        for record in records:
            expected = unified.get(record.sample_id)
            if expected is None or expected != record.sample:
                raise MvpTrainingDataError(
                    f"arm row disagrees with inventory: {record.sample_id}"
                )
        arm_records[arm_id] = records
        arm_manifest_hashes[arm_id] = digest
        parents_by_arm_role[arm_id] = {
            role: {
                record.parent_instance_id for record in records if record.role == role
            }
            for role in ROLES
        }

    for role in ROLES:
        role_sets = [values[role] for values in parents_by_arm_role.values()]
        if any(parent_set != role_sets[0] for parent_set in role_sets[1:]):
            raise MvpTrainingDataError(
                f"parent population differs across arms for {role}"
            )

    reference_records = _load_reference_records(
        _read_jsonl(reference_path), unified, config=config
    )
    for role in ROLES:
        expected_parents = next(iter(parents_by_arm_role.values()))[role]
        actual_parents = {
            item["parent_instance_id"] for item in reference_records[role]
        }
        if actual_parents != expected_parents:
            raise MvpTrainingDataError(
                f"common reference population differs for {role}"
            )

    eligible_by_arm: dict[str, dict[str, list[ArmSample]]] = {}
    for arm_id, records in arm_records.items():
        by_parent: dict[str, list[ArmSample]] = defaultdict(list)
        for record in records:
            if record.role == "train" and (
                record.sample.label_mip_gap_relative
                <= policy.gap_threshold_relative + 1e-12
            ):
                by_parent[record.parent_instance_id].append(record)
        eligible_by_arm[arm_id] = by_parent
    common_training_parents = set.intersection(
        *(set(values) for values in eligible_by_arm.values())
    )
    common_training_parent_ids = sorted(common_training_parents)

    selected_arms: dict[str, Any] = {}
    all_graphs: dict[str, str] = {}
    for record in unified_records:
        previous_digest = all_graphs.get(record.graph_path)
        if previous_digest is not None and previous_digest != record.graph_sha256:
            raise MvpTrainingDataError("one graph path declares multiple hashes")
        all_graphs[record.graph_path] = record.graph_sha256
    for relative_path, expected_digest in sorted(all_graphs.items()):
        artifact = _safe_artifact(root, relative_path)
        if verify_graph_hashes:
            if sha256_file(artifact) != expected_digest:
                raise MvpTrainingDataError(f"graph SHA-256 mismatch: {relative_path}")

    common_count = len(common_training_parent_ids)
    for arm_id, by_parent in sorted(eligible_by_arm.items()):
        selected: list[dict[str, Any]] = []
        for parent_id in common_training_parent_ids:
            siblings = sorted(by_parent[parent_id], key=lambda item: item.sample_id)
            selected.extend(
                item.selected_payload(
                    common_parent_count=common_count,
                    eligible_siblings=len(siblings),
                )
                for item in siblings
            )
        source_train = [item for item in arm_records[arm_id] if item.role == "train"]
        excluded_gap = sum(
            item.sample.label_mip_gap_relative
            > policy.gap_threshold_relative + 1e-12
            for item in source_train
        )
        selected_arms[arm_id] = {
            "arm_manifest": f"{ARM_DIR_NAME}/{arm_id}.jsonl",
            "arm_manifest_sha256": arm_manifest_hashes[arm_id],
            "eligible_training_records": selected,
            "eligible_training_record_count": len(selected),
            "eligible_training_parent_count": common_count,
            "source_training_record_count": len(source_train),
            "excluded_by_gap_count": excluded_gap,
            "excluded_by_common_parent_intersection_count": sum(
                item.parent_instance_id not in common_training_parents
                and item.sample.label_mip_gap_relative
                <= policy.gap_threshold_relative + 1e-12
                for item in source_train
            ),
            "draws_per_epoch": common_count * policy.draws_per_parent_per_epoch,
            "parent_mass_min": 1.0 if common_count else None,
            "parent_mass_max": 1.0 if common_count else None,
        }

    validation_count = len(reference_records["validation"])
    test_count = len(reference_records["test"])
    training_ready = common_count > 0 and validation_count > 0
    held_out_evaluation_ready = test_count > 0
    warnings: list[str] = []
    if common_count == 0:
        warnings.append("no_common_gap_eligible_training_parent")
    if validation_count == 0:
        warnings.append("validation_partition_missing")
    if test_count == 0:
        warnings.append("held_out_test_partition_missing")
    if len(unified_records) < 90 * 2:
        warnings.append("development_partial_parent_population")

    contract_payload = {
        "schema_version": SCHEMA_VERSION,
        "experiment_stage": "mvp_four_arm_training_data",
        "dataset_contract_sha256": dataset_contract,
        "experiment_contract_sha256": config.contract_sha256,
        "loader_policy": policy.contract_payload,
        "loader_policy_sha256": policy.contract_sha256,
        "unified_manifest": {
            "file_name": UNIFIED_MANIFEST_NAME,
            "sha256": sha256_file(unified_path),
        },
        "common_reference_manifest": {
            "file_name": REFERENCE_MANIFEST_NAME,
            "sha256": sha256_file(reference_path),
        },
        "common_training_parent_ids": common_training_parent_ids,
        "arms": selected_arms,
        "common_reference_partitions": reference_records,
        "test_partition_usage": "held_out_not_loaded_during_training",
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **contract_payload,
        "contract_sha256": _canonical_sha256(contract_payload),
        "contract_valid": True,
        "graph_hash_verification": (
            "all_unified_graphs_verified" if verify_graph_hashes else "not_requested"
        ),
        "partition_summary": {
            "common_training_parents": common_count,
            "common_validation_parents": validation_count,
            "common_test_parents": test_count,
        },
        "training_ready": training_ready,
        "held_out_evaluation_ready": held_out_evaluation_ready,
        "mvp_execution_ready": training_ready and held_out_evaluation_ready,
        "warnings": warnings,
        "next_gate": (
            "four_arm_training"
            if training_ready and held_out_evaluation_ready
            else "complete_train_validation_test_vertical_slice"
        ),
    }


def build_parent_balanced_epoch_indices(
    records: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    epoch: int,
    draws_per_parent: int,
) -> tuple[int, ...]:
    """Return a deterministic schedule with exactly equal draws per parent."""
    if epoch < 0:
        raise MvpTrainingDataError("epoch must be nonnegative")
    draws_per_parent = _positive_int(draws_per_parent, field="draws_per_parent")
    by_parent: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        parent_id = _required_string(
            record.get("parent_instance_id"), field="parent_instance_id"
        )
        by_parent[parent_id].append(index)
    if not by_parent:
        return ()
    scheduled: list[int] = []
    for parent_id, indices in sorted(by_parent.items()):
        parent_seed = int.from_bytes(
            hashlib.sha256(f"{seed}:{epoch}:{parent_id}".encode("utf-8")).digest()[:8],
            byteorder="big",
        )
        parent_rng = random.Random(parent_seed)
        selected: list[int] = []
        cycle = 0
        while len(selected) < draws_per_parent:
            order = list(indices)
            cycle_rng = random.Random(parent_rng.getrandbits(64) ^ cycle)
            cycle_rng.shuffle(order)
            selected.extend(order)
            cycle += 1
        scheduled.extend(selected[:draws_per_parent])
    global_seed = int.from_bytes(
        hashlib.sha256(f"{seed}:{epoch}:global".encode("utf-8")).digest()[:8],
        byteorder="big",
    )
    random.Random(global_seed).shuffle(scheduled)
    return tuple(scheduled)


class DeterministicParentBalancedSampler:
    """PyTorch-compatible sampler without importing PyTorch at planning time."""

    def __init__(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        seed: int,
        draws_per_parent: int,
    ) -> None:
        self.records = tuple(records)
        self.seed = int(seed)
        self.draws_per_parent = _positive_int(
            draws_per_parent, field="draws_per_parent"
        )
        self.epoch = 0
        self._parent_count = len(
            {str(record["parent_instance_id"]) for record in self.records}
        )

    def set_epoch(self, epoch: int) -> None:
        if epoch < 0:
            raise MvpTrainingDataError("epoch must be nonnegative")
        self.epoch = int(epoch)

    def __iter__(self) -> Iterable[int]:
        return iter(
            build_parent_balanced_epoch_indices(
                self.records,
                seed=self.seed,
                epoch=self.epoch,
                draws_per_parent=self.draws_per_parent,
            )
        )

    def __len__(self) -> int:
        return self._parent_count * self.draws_per_parent


def write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    """Atomically write a JSON contract."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def sampler_parent_counts(
    records: Sequence[Mapping[str, Any]], indices: Sequence[int]
) -> dict[str, int]:
    """Summarize an epoch schedule for audits and dependency-free tests."""
    counts: Counter[str] = Counter()
    for index in indices:
        counts[str(records[index]["parent_instance_id"])] += 1
    return dict(sorted(counts.items()))

