from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.training import mvp_four_arm as training


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (
    PROJECT_ROOT
    / "configs"
    / "training"
    / "mvp_four_arm_training_smoke_v1.json"
)


def _record(arm_id: str, index: int = 0) -> dict[str, object]:
    solver = arm_id.split("_", 1)[0]
    sampling = (
        "original" if arm_id.endswith("_original") else "incumbent_local_branching"
    )
    return {
        "sample_id": f"easy-2__{solver}__{sampling}__{index}",
        "parent_instance_id": "CFL_easy_instance_2",
        "role": "train",
        "solver": solver,
        "sampling_strategy": sampling,
        "graph_path": f"graphs/{arm_id}/{index}.pt",
        "graph_sha256": f"{index + 1:064x}",
    }


def _data_plan() -> dict[str, object]:
    arms: dict[str, object] = {}
    for arm_id in training.EXPECTED_ARMS:
        records = [_record(arm_id)]
        if "incumbent_augmented" in arm_id:
            records = [_record(arm_id, index) for index in range(4)]
        arms[arm_id] = {
            "eligible_training_records": records,
            "eligible_training_parent_count": 1,
            "draws_per_epoch": 4,
        }
    validation = {
        "sample_id": "CFL_easy_instance_1__common",
        "parent_instance_id": "CFL_easy_instance_1",
        "role": "validation",
        "graph_path": "graphs/validation.pt",
        "graph_sha256": "a" * 64,
        "label_solution_sha256": "1" * 64,
    }
    test = {
        "sample_id": "CFL_easy_instance_0__common",
        "parent_instance_id": "CFL_easy_instance_0",
        "role": "test",
        "graph_path": "graphs/test.pt",
        "graph_sha256": "b" * 64,
        "label_solution_sha256": "2" * 64,
    }
    return {
        "dataset_contract_sha256": "c" * 64,
        "contract_sha256": "d" * 64,
        "mvp_execution_ready": True,
        "loader_policy": {"draws_per_parent_per_epoch": 4},
        "arms": arms,
        "common_reference_partitions": {
            "validation": [validation],
            "test": [test],
        },
    }


def test_training_protocol_precommits_paired_controls() -> None:
    protocol = training.load_training_protocol(PROTOCOL)
    payload = protocol.contract_payload
    assert protocol.experiment_stage == "engineering_smoke"
    assert protocol.epochs == 2
    assert payload["comparison_controls"] == {
        "independent_model_per_arm": True,
        "initialization_seed_restarted_per_arm": True,
        "equal_optimizer_steps_per_epoch": True,
        "prenorm_policy": (
            "solver_original_reference_reused_within_solver_pair"
        ),
        "pos_weight_policy": (
            "solver_original_training_labels_reused_within_solver_pair"
        ),
        "validation_policy": "common_reference_shared_across_all_arms",
        "test_access_policy": "held_out_not_loaded_during_training",
    }


def test_run_plan_is_ready_and_excludes_test_graph_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(training, "build_training_data_plan", lambda *a, **k: _data_plan())
    plan = training.build_training_run_plan(
        tmp_path / "dataset",
        experiment_config_path=tmp_path / "experiment.json",
        loader_policy_path=tmp_path / "loader.json",
        training_protocol_path=PROTOCOL,
    )
    assert plan["contract_valid"] is True
    assert plan["mvp_execution_ready"] is True
    assert plan["optimizer_steps_per_arm_per_epoch"] == 4
    assert plan["held_out_test_contract"] == {
        "record_count": 1,
        "parent_instance_ids": ["CFL_easy_instance_0"],
        "graph_sha256": ["b" * 64],
        "access_policy": "not_deserialized_during_training",
    }
    assert "graphs/test.pt" not in json.dumps(plan)
    for solver in ("gurobi", "scip"):
        assert plan["solver_pair_references"][solver]["pos_weight_source_arm"] == (
            f"{solver}_original"
        )


def test_run_plan_rejects_unequal_optimizer_step_budgets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_plan = _data_plan()
    data_plan["arms"]["scip_original"]["draws_per_epoch"] = 3
    monkeypatch.setattr(
        training, "build_training_data_plan", lambda *a, **k: data_plan
    )
    with pytest.raises(training.MvpFourArmTrainingError, match="step budget"):
        training.build_training_run_plan(
            tmp_path / "dataset",
            experiment_config_path=tmp_path / "experiment.json",
            loader_policy_path=tmp_path / "loader.json",
            training_protocol_path=PROTOCOL,
        )


def test_four_arm_orchestration_preserves_pairing_and_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(training, "build_training_data_plan", lambda *a, **k: _data_plan())
    plan = training.build_training_run_plan(
        tmp_path / "dataset",
        experiment_config_path=tmp_path / "experiment.json",
        loader_policy_path=tmp_path / "loader.json",
        training_protocol_path=PROTOCOL,
    )

    def fake_runner(**kwargs):
        arm_id = kwargs["arm_id"]
        solver = kwargs["arm"]["solver"]
        return {
            "arm_id": arm_id,
            "solver": solver,
            "epochs_completed": 2,
            "optimizer_steps_per_epoch": 4,
            "optimizer_steps_completed": 8,
            "training_record_count": kwargs["arm"]["record_count"],
            "training_parent_count": 1,
            "validation_record_count": 1,
            "validation_reference_sha256": plan["validation_reference_sha256"],
            "initialization_seed": 42,
            "initial_model_state_sha256": "9" * 64,
            "prenorm_reference_sample_id": plan["solver_pair_references"][solver][
                "sample_id"
            ],
            "pos_weight": 300.0 if solver == "gurobi" else 310.0,
            "pos_weight_source_arm": f"{solver}_original",
            "device_effective": "cpu",
            "best_epoch": 2,
            "best_validation_metrics": {"f1_score": 0.1},
            "checkpoint": {"file_name": "best_model.pt", "sha256": "e" * 64},
            "history": {"file_name": "training_history.csv", "sha256": "f" * 64},
            "test_graphs_loaded": 0,
        }

    output = tmp_path / "output"
    report = training.run_four_arm_training(
        plan,
        dataset_dir=tmp_path / "dataset",
        output_dir=output,
        arm_runner=fake_runner,
    )
    assert report["gate_status"] == "passed"
    assert report["execution"]["arms_completed"] == 4
    assert all(report["paired_controls"].values())
    assert report["eligibility"] == {
        "training_smoke_eligible": True,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    serialized = (output / training.RUN_REPORT_NAME).read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized


def test_four_arm_orchestration_rejects_unpaired_pos_weight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(training, "build_training_data_plan", lambda *a, **k: _data_plan())
    plan = training.build_training_run_plan(
        tmp_path / "dataset",
        experiment_config_path=tmp_path / "experiment.json",
        loader_policy_path=tmp_path / "loader.json",
        training_protocol_path=PROTOCOL,
    )

    def mismatched_runner(**kwargs):
        arm_id = kwargs["arm_id"]
        solver = kwargs["arm"]["solver"]
        return {
            "arm_id": arm_id,
            "solver": solver,
            "optimizer_steps_per_epoch": 4,
            "optimizer_steps_completed": 8,
            "validation_record_count": 1,
            "validation_reference_sha256": plan["validation_reference_sha256"],
            "initialization_seed": 42,
            "initial_model_state_sha256": "9" * 64,
            "prenorm_reference_sample_id": plan["solver_pair_references"][solver][
                "sample_id"
            ],
            "pos_weight": 1.0 if arm_id.endswith("_original") else 2.0,
            "device_effective": "cpu",
            "test_graphs_loaded": 0,
        }

    with pytest.raises(training.MvpFourArmTrainingError, match="paired"):
        training.run_four_arm_training(
            plan,
            dataset_dir=tmp_path / "dataset",
            output_dir=tmp_path / "output",
            arm_runner=mismatched_runner,
        )


def test_dasci_launcher_is_lf_only_and_uses_cuda() -> None:
    launcher = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_mvp_four_arm_training_smoke.sbs"
    )
    payload = launcher.read_bytes()
    assert b"\r" not in payload
    text = payload.decode("utf-8")
    assert "SLURM_SUBMIT_DIR" in text
    assert "--device cuda" in text
    assert "--gres=gpu:1" in text
