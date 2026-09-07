"""Dependency-light tests for the four-arm MVP training-data contract."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from cfl_gnn.cli.plan_mvp_training import main
from cfl_gnn.experiments.mvp_contract import load_experiment_config
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.graph.mvp_arm_dataset import (
    selected_common_reference_records,
    selected_records_for_arm,
)
from cfl_gnn.training.mvp_arm import (
    MvpTrainingDataError,
    build_parent_balanced_epoch_indices,
    build_training_data_plan,
    load_loader_policy,
    sampler_parent_counts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
LOADER_POLICY = (
    PROJECT_ROOT / "configs" / "training" / "mvp_four_arm_loader_v1.json"
)
ARM_IDS = (
    "gurobi_original",
    "gurobi_incumbent_augmented",
    "scip_original",
    "scip_incumbent_augmented",
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def _sample(
    root: Path,
    *,
    parent: str,
    fold: int,
    role: str,
    solver: str,
    derived: bool = False,
    gap: float = 0.0,
) -> dict[str, object]:
    suffix = "lb_r1" if derived else "original"
    sample_id = f"{parent}__{solver}__{suffix}"
    relative = Path("graphs") / ("derived" if derived else "original") / solver
    relative /= f"{sample_id}.pt"
    artifact = root / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(f"graph:{sample_id}".encode("utf-8"))
    record: dict[str, object] = {
        "sample_id": sample_id,
        "parent_instance_id": parent,
        "category": "CFL_easy_instance",
        "difficulty": "easy",
        "fold": fold,
        "solver": solver,
        "sampling_strategy": (
            "incumbent_local_branching" if derived else "original"
        ),
        "graph_path": relative.as_posix(),
        "graph_sha256": sha256_file(artifact),
        "label_source": f"{sample_id}.solution.json.gz",
        "label_solution_sha256": _digest(f"solution:{sample_id}"),
        "label_objective": 6.0 + fold / 10.0,
        "label_mip_gap_relative": gap,
        "label_mip_gap_percent": 100.0 * gap,
        "label_execution_time_seconds": 10.0 + fold,
        "source_incumbent_id": None,
        "source_incumbent_artifact_sha256": None,
        "source_incumbent_objective": None,
        "source_incumbent_mip_gap_relative": None,
        "source_incumbent_mip_gap_percent": None,
        "source_incumbent_execution_time_seconds": None,
        "local_branching_radius": None,
        "local_branching_radius_fraction": None,
    }
    if derived:
        record.update(
            {
                "source_incumbent_id": f"{solver}:incumbent",
                "source_incumbent_artifact_sha256": _digest(
                    f"incumbent:{solver}:{parent}"
                ),
                "source_incumbent_objective": 6.5,
                "source_incumbent_mip_gap_relative": 0.05,
                "source_incumbent_mip_gap_percent": 5.0,
                "source_incumbent_execution_time_seconds": 30.0,
                "local_branching_radius": 1,
                "local_branching_radius_fraction": 0.001,
            }
        )
    record["_role"] = role
    return record


def _without_test_role(record: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if key != "_role"}


def _build_dataset(root: Path, *, derived_gap: float = 0.08) -> Path:
    config = load_experiment_config(EXPERIMENT_CONFIG)
    parents = (
        ("parent_train", 2, "train"),
        ("parent_val", 1, "validation"),
        ("parent_test", 0, "test"),
    )
    originals: dict[tuple[str, str], dict[str, object]] = {}
    derived: dict[str, dict[str, object]] = {}
    for solver in ("gurobi", "scip"):
        for parent, fold, role in parents:
            originals[(solver, parent)] = _sample(
                root,
                parent=parent,
                fold=fold,
                role=role,
                solver=solver,
            )
        derived[solver] = _sample(
            root,
            parent="parent_train",
            fold=2,
            role="train",
            solver=solver,
            derived=True,
            gap=derived_gap,
        )
    unified = [
        _without_test_role(value)
        for value in sorted(
            [*originals.values(), *derived.values()],
            key=lambda item: str(item["sample_id"]),
        )
    ]
    unified_path = root / "mvp_sample_manifest.jsonl"
    _write_jsonl(unified_path, unified)

    arm_hashes: dict[str, str] = {}
    for solver in ("gurobi", "scip"):
        solver_originals = [
            originals[(solver, parent)] for parent, _, _ in parents
        ]
        for augmented in (False, True):
            arm_id = f"{solver}_{'incumbent_augmented' if augmented else 'original'}"
            members = solver_originals + ([derived[solver]] if augmented else [])
            sibling_counts = Counter(
                str(value["parent_instance_id"]) for value in members
            )
            arm_records: list[dict[str, object]] = []
            for value in members:
                role = str(value["_role"])
                arm_records.append(
                    {
                        **_without_test_role(value),
                        "arm_id": arm_id,
                        "role": role,
                        "sample_weight": (
                            1.0 / sibling_counts[str(value["parent_instance_id"])]
                            if role == "train"
                            else 1.0
                        ),
                        "weighting_policy": "equal_parent_mass",
                    }
                )
            path = root / "arms" / f"{arm_id}.jsonl"
            _write_jsonl(path, arm_records)
            arm_hashes[arm_id] = sha256_file(path)

    references: list[dict[str, object]] = []
    for parent, _, role in parents:
        selected = originals[("gurobi", parent)]
        references.append(
            {
                "parent_instance_id": parent,
                "role": role,
                "selection_policy": "minimum_objective_then_gap_time_solver",
                "selected_solver": "gurobi",
                "label_objective": selected["label_objective"],
                "label_mip_gap_relative": selected["label_mip_gap_relative"],
                "label_execution_time_seconds": selected[
                    "label_execution_time_seconds"
                ],
                "label_solution_sha256": selected["label_solution_sha256"],
                "candidate_count": 2,
            }
        )
    reference_path = root / "evaluation_reference_manifest.jsonl"
    _write_jsonl(reference_path, references)
    dataset_contract = "a" * 64
    _write_json(
        root / "mvp_dataset_composition_plan.json",
        {
            "contract_sha256": dataset_contract,
            "experiment_contract_sha256": config.contract_sha256,
        },
    )
    _write_json(
        root / "mvp_dataset_composition_report.json",
        {
            "contract_sha256": dataset_contract,
            "gate_status": "passed",
            "arms": {
                arm_id: {"sha256": digest} for arm_id, digest in arm_hashes.items()
            },
            "outputs": {
                "sample_manifest_sha256": sha256_file(unified_path),
                "evaluation_reference_manifest_sha256": sha256_file(reference_path),
            },
            "eligibility": {
                "dataset_eligible": True,
                "development_only": True,
                "scientific_reporting_eligible": False,
            },
        },
    )
    return root


def _retain_training_parent_only(dataset: Path) -> None:
    for path in [
        dataset / "mvp_sample_manifest.jsonl",
        dataset / "evaluation_reference_manifest.jsonl",
        *(dataset / "arms").glob("*.jsonl"),
    ]:
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        _write_jsonl(
            path,
            [
                record
                for record in records
                if record["parent_instance_id"] == "parent_train"
            ],
        )
    report_path = dataset / "mvp_dataset_composition_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["outputs"]["sample_manifest_sha256"] = sha256_file(
        dataset / "mvp_sample_manifest.jsonl"
    )
    report["outputs"]["evaluation_reference_manifest_sha256"] = sha256_file(
        dataset / "evaluation_reference_manifest.jsonl"
    )
    for arm_id in ARM_IDS:
        report["arms"][arm_id]["sha256"] = sha256_file(
            dataset / "arms" / f"{arm_id}.jsonl"
        )
    _write_json(report_path, report)


def test_default_loader_policy_is_precommitted() -> None:
    policy = load_loader_policy(LOADER_POLICY)
    assert policy.gap_threshold_relative == 0.10
    assert policy.draws_per_parent_per_epoch == 4
    assert policy.contract_sha256


def test_four_arm_plan_uses_common_parents_and_references(tmp_path: Path) -> None:
    dataset = _build_dataset(tmp_path / "dataset")
    plan = build_training_data_plan(
        dataset,
        experiment_config_path=EXPERIMENT_CONFIG,
        loader_policy_path=LOADER_POLICY,
    )
    assert plan["contract_valid"] is True
    assert plan["training_ready"] is True
    assert plan["held_out_evaluation_ready"] is True
    assert plan["mvp_execution_ready"] is True
    assert plan["partition_summary"] == {
        "common_training_parents": 1,
        "common_validation_parents": 1,
        "common_test_parents": 1,
    }
    assert plan["common_training_parent_ids"] == ["parent_train"]
    for arm_id in ARM_IDS:
        arm = plan["arms"][arm_id]
        assert arm["draws_per_epoch"] == 4
        assert arm["eligible_training_parent_count"] == 1
        assert all(
            record["effective_sampling_probability"]
            == record["effective_within_parent_weight"]
            for record in arm["eligible_training_records"]
        )
    assert len(plan["arms"]["gurobi_original"]["eligible_training_records"]) == 1
    assert (
        len(
            plan["arms"]["gurobi_incumbent_augmented"][
                "eligible_training_records"
            ]
        )
        == 2
    )
    assert {
        record["selected_solver"]
        for record in plan["common_reference_partitions"]["validation"]
    } == {"gurobi"}


def test_gap_filter_recomputes_augmented_parent_weight(tmp_path: Path) -> None:
    dataset = _build_dataset(tmp_path / "dataset", derived_gap=0.08)
    raw_policy = json.loads(LOADER_POLICY.read_text(encoding="utf-8"))
    raw_policy["gap_threshold_relative"] = 0.05
    policy_path = tmp_path / "policy.json"
    _write_json(policy_path, raw_policy)
    plan = build_training_data_plan(
        dataset,
        experiment_config_path=EXPERIMENT_CONFIG,
        loader_policy_path=policy_path,
    )
    for arm_id in ARM_IDS:
        records = plan["arms"][arm_id]["eligible_training_records"]
        assert len(records) == 1
        assert records[0]["effective_within_parent_weight"] == 1.0
    assert plan["arms"]["scip_incumbent_augmented"]["excluded_by_gap_count"] == 1


def test_one_parent_smoke_is_valid_but_not_training_ready(tmp_path: Path) -> None:
    dataset = _build_dataset(tmp_path / "dataset")
    _retain_training_parent_only(dataset)
    plan = build_training_data_plan(
        dataset,
        experiment_config_path=EXPERIMENT_CONFIG,
        loader_policy_path=LOADER_POLICY,
    )
    assert plan["contract_valid"] is True
    assert plan["partition_summary"]["common_training_parents"] == 1
    assert plan["training_ready"] is False
    assert plan["held_out_evaluation_ready"] is False
    assert plan["next_gate"] == "complete_train_validation_test_vertical_slice"
    assert "validation_partition_missing" in plan["warnings"]
    assert "held_out_test_partition_missing" in plan["warnings"]


def test_parent_balanced_schedule_is_exact_and_replayable() -> None:
    records = [
        {"parent_instance_id": "a"},
        {"parent_instance_id": "a"},
        {"parent_instance_id": "a"},
        {"parent_instance_id": "b"},
    ]
    first = build_parent_balanced_epoch_indices(
        records, seed=42, epoch=0, draws_per_parent=4
    )
    replay = build_parent_balanced_epoch_indices(
        records, seed=42, epoch=0, draws_per_parent=4
    )
    second_epoch = build_parent_balanced_epoch_indices(
        records, seed=42, epoch=1, draws_per_parent=4
    )
    assert first == replay
    assert first != second_epoch
    assert sampler_parent_counts(records, first) == {"a": 4, "b": 4}


def test_tampered_graph_fails_closed(tmp_path: Path) -> None:
    dataset = _build_dataset(tmp_path / "dataset")
    graph = next((dataset / "graphs").rglob("*.pt"))
    graph.write_bytes(b"tampered")
    with pytest.raises(MvpTrainingDataError, match="graph SHA-256 mismatch"):
        build_training_data_plan(
            dataset,
            experiment_config_path=EXPERIMENT_CONFIG,
            loader_policy_path=LOADER_POLICY,
        )


def test_dataset_accessors_do_not_mix_training_and_reference(tmp_path: Path) -> None:
    dataset = _build_dataset(tmp_path / "dataset")
    plan = build_training_data_plan(
        dataset,
        experiment_config_path=EXPERIMENT_CONFIG,
        loader_policy_path=LOADER_POLICY,
    )
    train = selected_records_for_arm(plan, "scip_incumbent_augmented")
    validation = selected_common_reference_records(plan, "validation")
    test = selected_common_reference_records(plan, "test")
    assert {record["role"] for record in train} == {"train"}
    assert {record["role"] for record in validation} == {"validation"}
    assert {record["role"] for record in test} == {"test"}


def test_cli_writes_sanitized_plan_and_audit(tmp_path: Path) -> None:
    dataset = _build_dataset(tmp_path / "dataset")
    output = tmp_path / "output"
    arguments = [
        "--dataset_dir",
        str(dataset),
        "--output_dir",
        str(output),
        "--experiment_config",
        str(EXPERIMENT_CONFIG),
        "--loader_policy",
        str(LOADER_POLICY),
    ]
    assert main(arguments) == 0
    plan = json.loads((output / "mvp_training_data_plan.json").read_text())
    audit = json.loads((output / "mvp_training_data_audit.json").read_text())
    assert plan["mvp_execution_ready"] is True
    assert audit["sampler_gate_status"] == "passed"
    assert audit["graph_load_smoke"]["status"] == "not_requested"
    serialized = json.dumps({"plan": plan, "audit": audit})
    assert str(tmp_path) not in serialized
    assert main(arguments) == 2

