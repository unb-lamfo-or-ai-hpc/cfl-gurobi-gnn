from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.evaluation import mvp_four_arm as evaluation
from cfl_gnn.graph.instance_provenance import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_PROTOCOL = (
    PROJECT_ROOT / "configs" / "evaluation" / "mvp_four_arm_held_out_v1.json"
)


def _record() -> dict[str, object]:
    return {
        "sample_id": "CFL_easy_instance_0__scip__original",
        "parent_instance_id": "CFL_easy_instance_0",
        "category": "CFL_easy_instance",
        "difficulty": "easy",
        "fold": 0,
        "role": "test",
        "selected_solver": "scip",
        "graph_path": "graphs/original/scip/test.pt",
        "graph_sha256": "a" * 64,
        "label_solution_sha256": "b" * 64,
    }


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dataset = tmp_path / "dataset"
    training_run = tmp_path / "training"
    source = tmp_path / "source"
    record = _record()
    graph = dataset / str(record["graph_path"])
    graph.parent.mkdir(parents=True)
    graph.write_bytes(b"graph")
    record["graph_sha256"] = sha256_file(graph)
    parent = source / "CFL_easy_instance" / "LP" / "CFL_easy_instance_0.lp.gz"
    parent.parent.mkdir(parents=True)
    parent.write_bytes(b"parent")
    provenance = (
        dataset
        / "provenance"
        / "original"
        / "scip"
        / "CFL_easy_instance_0__scip__original.provenance.json"
    )
    provenance.parent.mkdir(parents=True)
    provenance.write_text(
        json.dumps(
            {
                "sample": {
                    "sample_id": record["sample_id"],
                    "parent_instance_id": record["parent_instance_id"],
                    "graph_sha256": record["graph_sha256"],
                    "label_solution_sha256": record["label_solution_sha256"],
                },
                "parent_mip_sha256": sha256_file(parent),
                "graph_generation_contract_sha256": "9" * 64,
                "graph_audit": {
                    "roundtrip_readable": True,
                    "label_variable_identity_match": True,
                },
                "eligibility": {"dataset_eligible": True},
            }
        ),
        encoding="utf-8",
    )
    training_plan = {
        "contract_sha256": "c" * 64,
        "dataset_contract_sha256": "d" * 64,
        "training_data_contract_sha256": "e" * 64,
        "training_protocol_sha256": "f" * 64,
        "training_protocol": {"model": {"hidden_dim": 32, "num_layers": 2}},
        "held_out_test_contract": {
            "record_count": 1,
            "parent_instance_ids": ["CFL_easy_instance_0"],
            "graph_sha256": [record["graph_sha256"]],
        },
    }
    training_run.mkdir(parents=True)
    (training_run / evaluation.TRAINING_PLAN_NAME).write_text(
        json.dumps(training_plan), encoding="utf-8"
    )
    report_arms = {}
    for arm_id in evaluation.EXPECTED_ARMS:
        arm_root = training_run / "arms" / arm_id
        arm_root.mkdir(parents=True)
        checkpoint = arm_root / evaluation.CHECKPOINT_NAME
        checkpoint.write_bytes(arm_id.encode())
        summary_payload = {
            "arm_id": arm_id,
            "checkpoint": {"sha256": sha256_file(checkpoint)},
            "test_graphs_loaded": 0,
        }
        summary = arm_root / evaluation.ARM_SUMMARY_NAME
        summary.write_text(json.dumps(summary_payload), encoding="utf-8")
        report_arms[arm_id] = {
            "arm_id": arm_id,
            "solver": arm_id.split("_", 1)[0],
            "checkpoint": {
                "file_name": checkpoint.name,
                "sha256": sha256_file(checkpoint),
            },
            "summary_sha256": sha256_file(summary),
        }
    training_report = {
        "gate_status": "passed",
        "training_run_contract_sha256": training_plan["contract_sha256"],
        "paired_controls": {"paired": True},
        "eligibility": {
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "arms": report_arms,
    }
    (training_run / evaluation.TRAINING_REPORT_NAME).write_text(
        json.dumps(training_report), encoding="utf-8"
    )
    data_plan = {
        "contract_sha256": training_plan["training_data_contract_sha256"],
        "common_reference_partitions": {"test": [record]},
    }
    monkeypatch.setattr(
        evaluation, "build_training_run_plan", lambda *args, **kwargs: training_plan
    )
    monkeypatch.setattr(
        evaluation, "build_training_data_plan", lambda *args, **kwargs: data_plan
    )
    return dataset, training_run, source


def _plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dataset, training_run, source = _fixture(tmp_path, monkeypatch)
    plan = evaluation.build_evaluation_plan(
        dataset,
        training_run,
        source,
        experiment_config_path=tmp_path / "experiment.json",
        loader_policy_path=tmp_path / "loader.json",
        training_protocol_path=tmp_path / "training.json",
        evaluation_protocol_path=EVALUATION_PROTOCOL,
    )
    return plan, dataset, training_run, source


def test_evaluation_protocol_precommits_no_test_selection() -> None:
    protocol = evaluation.load_evaluation_protocol(EVALUATION_PROTOCOL)
    assert protocol.probability_threshold == 0.5
    assert protocol.contract_payload["arm_selection_policy"] == (
        "all_four_arms_forwarded_without_test_selection"
    )
    assert protocol.contract_payload["hint_policy"][
        "include_all_discrete_variables"
    ]


def test_plan_binds_four_checkpoints_and_one_test_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _, _, _ = _plan(tmp_path, monkeypatch)
    assert plan["contract_valid"] is True
    assert set(plan["arms"]) == set(evaluation.EXPECTED_ARMS)
    assert len(plan["test_records"]) == 1
    assert plan["arm_selection_performed"] is False
    assert plan["all_four_arms_forwarded"] is True
    assert str(tmp_path) not in json.dumps(plan)


def test_plan_rejects_tampered_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset, training_run, source = _fixture(tmp_path, monkeypatch)
    checkpoint = training_run / "arms" / "gurobi_original" / evaluation.CHECKPOINT_NAME
    checkpoint.write_bytes(b"tampered")
    with pytest.raises(evaluation.MvpFourArmEvaluationError, match="changed"):
        evaluation.build_evaluation_plan(
            dataset,
            training_run,
            source,
            experiment_config_path=tmp_path / "experiment.json",
            loader_policy_path=tmp_path / "loader.json",
            training_protocol_path=tmp_path / "training.json",
            evaluation_protocol_path=EVALUATION_PROTOCOL,
        )


def test_hint_writer_is_deterministic_and_contains_no_labels(tmp_path: Path) -> None:
    rows = [
        {
            "variable_name": "x1",
            "predicted_value": 1,
            "probability": 0.9,
            "confidence": 0.8,
            "priority": 80,
        }
    ]
    first = tmp_path / "first.jsonl.gz"
    second = tmp_path / "second.jsonl.gz"
    first_report = evaluation._write_hint_rows(first, rows)
    second_report = evaluation._write_hint_rows(second, rows)
    assert first.read_bytes() == second.read_bytes()
    assert first_report["semantic_sha256"] == second_report["semantic_sha256"]
    with gzip.open(first, "rt", encoding="utf-8") as stream:
        assert json.loads(stream.readline()) == rows[0]
    with pytest.raises(evaluation.MvpFourArmEvaluationError, match="labels"):
        evaluation._write_hint_rows(tmp_path / "bad.gz", [{"label": 1}])


def test_orchestration_forwards_all_arms_without_selecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, dataset, training_run, source = _plan(tmp_path, monkeypatch)

    def fake_evaluator(**kwargs):
        arm_id = kwargs["arm_id"]
        solver = kwargs["arm"]["solver"]
        hint_path = kwargs["output_dir"] / "hints" / "test.jsonl.gz"
        hint = evaluation._write_hint_rows(
            hint_path,
            [
                {
                    "variable_name": "x1",
                    "predicted_value": 1,
                    "probability": 0.9,
                    "confidence": 0.8,
                    "priority": 80,
                },
                {
                    "variable_name": "x2",
                    "predicted_value": 0,
                    "probability": 0.1,
                    "confidence": 0.8,
                    "priority": 80,
                },
            ],
        )
        return {
            "arm_id": arm_id,
            "solver": solver,
            "checkpoint_sha256": kwargs["arm"]["checkpoint_sha256"],
            "device_effective": "cpu",
            "probability_threshold": 0.5,
            "threshold_source": "fixed_precommitted_not_test_calibrated",
            "test_reference_sha256": plan["test_reference_sha256"],
            "test_graphs_loaded": 1,
            "metrics_by_parent": [],
            "aggregate_metrics": {
                "n_test_parents": 1,
                "n_targets": 2,
                "unweighted_bce_per_variable": 0.5,
                "accuracy": 0.5,
                "precision": 0.5,
                "recall": 0.5,
                "f1_score": 0.5,
            },
            "hint_artifacts": [
                {
                    "parent_instance_id": "CFL_easy_instance_0",
                    "relative_path": (
                        Path("arms") / arm_id / "hints" / hint_path.name
                    ).as_posix(),
                    **hint,
                }
            ],
            "hint_policy": plan["evaluation_protocol"]["hint_policy"],
            "test_labels_in_hint_artifacts": False,
        }

    output = tmp_path / "evaluation"
    report = evaluation.run_evaluation(
        plan,
        dataset_dir=dataset,
        training_run_dir=training_run,
        base_source_dir=source,
        output_dir=output,
        arm_evaluator=fake_evaluator,
    )
    assert report["gate_status"] == "passed"
    assert all(report["common_controls"].values())
    assert report["arm_selection"]["performed"] is False
    assert report["arm_selection"]["forwarded_arms"] == list(
        evaluation.EXPECTED_ARMS
    )
    assert report["eligibility"]["scientific_reporting_eligible"] is False
    assert str(tmp_path) not in (output / evaluation.REPORT_NAME).read_text()


def test_dasci_launcher_is_lf_only_and_uses_cuda() -> None:
    launcher = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_mvp_four_arm_evaluation.sbs"
    )
    payload = launcher.read_bytes()
    assert b"\r" not in payload
    text = payload.decode("utf-8")
    assert "SLURM_SUBMIT_DIR" in text
    assert "--device cuda" in text
    assert "--gres=gpu:1" in text
