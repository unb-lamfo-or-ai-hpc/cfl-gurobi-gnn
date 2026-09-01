"""Dependency-free tests for held-out parent-instance evaluation."""

import json
from pathlib import Path

import pytest

from cfl_gnn.evaluation import instance as evaluation
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.splits.instance_partitions import InstanceDatasetAudit, InstanceGraphRecord
from cfl_gnn.training.instance_plan import InstanceTrainingPlan


def _record(source_instance_id: str, *, role: str, fold: int) -> InstanceGraphRecord:
    return InstanceGraphRecord(
        source_instance_id=source_instance_id,
        category="CFL_easy_instance",
        difficulty="easy",
        fold=fold,
        role=role,
        graph_path=Path("/private/root") / f"{source_instance_id}.pt",
        provenance_path=(
            Path("/private/root") / f"{source_instance_id}.provenance.json"
        ),
        label_source="solutions.pickle.gz",
        mip_gap=0.0,
        mip_gap_band="optimal_tolerance",
    )


def _training_plan() -> InstanceTrainingPlan:
    audit = InstanceDatasetAudit(
        dataset_root=Path("/private/root"),
        manifest_size=90,
        rotation=0,
        label_policy="optimal_only",
        graph_hashes_verified=True,
        discovered_graphs=3,
        eligible=(
            _record("CFL_easy_instance_0", role="test", fold=0),
            _record("CFL_easy_instance_1", role="validation", fold=1),
            _record("CFL_easy_instance_2", role="train", fold=2),
        ),
        excluded=(),
        missing=(),
        invalid=(),
    )
    return InstanceTrainingPlan(audit=audit, development_only=True)


def _write_contract_files(tmp_path: Path, plan: InstanceTrainingPlan):
    stored_plan = plan.to_summary()
    training_plan_path = tmp_path / "instance_training_plan.json"
    training_plan_path.write_text(json.dumps(stored_plan), encoding="utf-8")
    checkpoint_path = tmp_path / "best_model.pt"
    checkpoint_path.write_bytes(b"plain-state-dict-fixture")
    experiment = {
        "experiment_name": "instance_smoke",
        "dataset_variant": "gurobi_parent_instance",
        "contract_sha256": plan.contract_sha256,
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "rotation": 0,
        "label_policy": "optimal_only",
        "development_only": True,
        "test_partition_usage": "held_out_not_loaded_during_training",
        "hyperparameters": {
            "hidden_dim": 32,
            "num_layers": 2,
            "pos_weight": 388.28,
        },
    }
    experiment_path = tmp_path / "experiment_summary.json"
    experiment_path.write_text(json.dumps(experiment), encoding="utf-8")
    return training_plan_path, experiment_path, checkpoint_path


def test_evaluation_plan_binds_saved_and_current_contracts(
    tmp_path: Path, monkeypatch
) -> None:
    training_plan = _training_plan()
    plan_path, experiment_path, checkpoint_path = _write_contract_files(
        tmp_path, training_plan
    )
    monkeypatch.setattr(
        evaluation,
        "build_instance_training_plan",
        lambda *args, **kwargs: training_plan,
    )

    plan = evaluation.build_instance_evaluation_plan(
        tmp_path / "graphs",
        tmp_path / "manifest.csv",
        plan_path,
        experiment_path,
        checkpoint_path,
    )
    summary = plan.to_summary()
    assert plan.contract_sha256 == training_plan.contract_sha256
    assert summary["test_instances"] == ["CFL_easy_instance_0"]
    assert summary["probability_threshold"] == 0.5
    assert summary["threshold_source"] == "fixed_precommitted_not_test_calibrated"
    assert summary["test_partition_usage"] == "held_out_evaluation_only"
    assert "/private/root" not in json.dumps(summary)


def test_evaluation_rejects_contract_mismatch(tmp_path: Path, monkeypatch) -> None:
    training_plan = _training_plan()
    plan_path, experiment_path, checkpoint_path = _write_contract_files(
        tmp_path, training_plan
    )
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    experiment["contract_sha256"] = "0" * 64
    experiment_path.write_text(json.dumps(experiment), encoding="utf-8")
    monkeypatch.setattr(
        evaluation,
        "build_instance_training_plan",
        lambda *args, **kwargs: training_plan,
    )
    with pytest.raises(
        evaluation.InstanceEvaluationContractError,
        match="experiment summary disagrees",
    ):
        evaluation.build_instance_evaluation_plan(
            tmp_path,
            tmp_path / "manifest.csv",
            plan_path,
            experiment_path,
            checkpoint_path,
        )


def test_evaluation_rejects_test_partition_not_proven_held_out(
    tmp_path: Path, monkeypatch
) -> None:
    training_plan = _training_plan()
    plan_path, experiment_path, checkpoint_path = _write_contract_files(
        tmp_path, training_plan
    )
    stored = json.loads(plan_path.read_text(encoding="utf-8"))
    stored["test_partition_usage"] = "used_during_training"
    plan_path.write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr(
        evaluation,
        "build_instance_training_plan",
        lambda *args, **kwargs: training_plan,
    )
    with pytest.raises(evaluation.InstanceEvaluationContractError, match="held out"):
        evaluation.build_instance_evaluation_plan(
            tmp_path,
            tmp_path / "manifest.csv",
            plan_path,
            experiment_path,
            checkpoint_path,
        )


def test_evaluation_rejects_substituted_checkpoint(tmp_path: Path, monkeypatch) -> None:
    training_plan = _training_plan()
    plan_path, experiment_path, checkpoint_path = _write_contract_files(
        tmp_path, training_plan
    )
    checkpoint_path.write_bytes(b"substituted-model")
    monkeypatch.setattr(
        evaluation,
        "build_instance_training_plan",
        lambda *args, **kwargs: training_plan,
    )
    with pytest.raises(
        evaluation.InstanceEvaluationContractError,
        match="checkpoint SHA-256",
    ):
        evaluation.build_instance_evaluation_plan(
            tmp_path,
            tmp_path / "manifest.csv",
            plan_path,
            experiment_path,
            checkpoint_path,
        )


def test_evaluation_rejects_malformed_checkpoint_digest(
    tmp_path: Path, monkeypatch
) -> None:
    training_plan = _training_plan()
    plan_path, experiment_path, checkpoint_path = _write_contract_files(
        tmp_path, training_plan
    )
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    experiment["checkpoint_sha256"] = "z" * 64
    experiment_path.write_text(json.dumps(experiment), encoding="utf-8")
    monkeypatch.setattr(
        evaluation,
        "build_instance_training_plan",
        lambda *args, **kwargs: training_plan,
    )
    with pytest.raises(
        evaluation.InstanceEvaluationContractError,
        match="valid checkpoint SHA-256",
    ):
        evaluation.build_instance_evaluation_plan(
            tmp_path,
            tmp_path / "manifest.csv",
            plan_path,
            experiment_path,
            checkpoint_path,
        )


def test_classification_metrics_cover_zero_and_nonzero_denominators() -> None:
    assert evaluation.classification_metrics(0, 0, 0, 0) == {
        "accuracy": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "f1_score": 0.0,
    }
    metrics = evaluation.classification_metrics(tp=8, tn=10, fp=2, fn=2)
    assert metrics["accuracy"] == pytest.approx(18 / 22)
    assert metrics["precision"] == pytest.approx(0.8)
    assert metrics["recall"] == pytest.approx(0.8)
    assert metrics["f1_score"] == pytest.approx(0.8)


def test_runtime_source_deserializes_only_test_records() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source = Path(evaluation.__file__).read_text(encoding="utf-8")
    trainer = (
        project_root / "src" / "cfl_gnn" / "training" / "instance_serial.py"
    ).read_text(encoding="utf-8")
    assert "random_split" not in source
    assert "ParentInstanceDataset(plan.test_records)" in source
    assert 'records_for_role("train")' not in source
    assert 'records_for_role("validation")' not in source
    assert "threshold_sweep" not in source
    assert "fixed_precommitted_not_test_calibrated" in source
    assert "PyTorch and PyG are imported only after" in source
    assert '"checkpoint_sha256": sha256_file(checkpoint)' in trainer
