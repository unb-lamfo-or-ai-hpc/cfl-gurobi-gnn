"""Contract tests for the admitted-label to strict-graph/Gasse adapter."""
import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.pipelines import confirmation_training as t
from cfl_gnn.pipelines import confirmation_execution as s
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold
from cfl_gnn.graph.gurobi_graph_artifact import _solution_by_name, GurobiGraphError


def gz(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(value, stream)


@pytest.fixture
def cohort(tmp_path):
    campaign, data, dataset = tmp_path / "campaign", tmp_path / "data", tmp_path / "graphs"
    campaign.mkdir()
    data.mkdir()
    entries = {e.source_instance_id: e for e in read_manifest(t.PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv")}
    tasks, rows = [], []
    for index, identity in enumerate(s.COHORT):
        entry = entries[identity]
        mip = data / f"{identity}.lp"
        mip.write_text(identity)
        task = {"task_index": index, "source_instance_id": identity, "difficulty": entry.difficulty,
                "role": role_for_fold(entry.fold, 0), "fold": entry.fold, "mip": s.descriptor(data, mip)}
        tasks.append(task)
        solution = campaign / "labels" / identity / "confirmation_solution.json.gz"
        gz(solution, {"source_instance_id": identity, "source_mip_sha256": task["mip"]["sha256"],
            "solution_source": "independently_audited_gurobi_confirmation_label", "effective_objective_sense": "MINIMIZE",
            "mathematical_audit": {"valid": True}, "mip_gap_relative": 0., "execution_time_seconds": 10.,
            "solution_objective": 1., "variables": [{"name": "x", "value": 1.}]})
        report_path = solution.parent / s.REPORT
        s.write_json(report_path, {"source_instance_id": identity, "mip_sha256": task["mip"]["sha256"],
            "gate_status": "passed", "label_eligible": True, "solution": s.descriptor(solution.parent, solution)})
        rows.append({**task, "label_eligible": True, "mip_gap_relative": 0.,
                     "solution": s.descriptor(campaign, solution), "report": s.descriptor(campaign, report_path)})
    plan = {"tasks": tasks, "objective_sense": "MINIMIZE", "seed": 42, "epochs": 100,
            "maximum_label_mip_gap_relative": .1, "repair_budgets_seconds": [3600, 14400],
            "implementation_sha256": s.implementation_hashes()}
    plan["contract_sha256"] = s.canonical_sha256(plan)
    s.write_json(campaign / s.PLAN, plan)
    index = campaign / "confirmation_label_index.jsonl"
    index.write_text("".join(json.dumps(row)+"\n" for row in rows))
    s.write_json(campaign / "confirmation_execution_report.json", {"campaign_contract_sha256": plan["contract_sha256"],
        "gate_status": "passed", "label_inventory_ready": True, "label_index": s.descriptor(campaign, index)})
    return campaign, data, dataset


def fake_builds(monkeypatch):
    from cfl_gnn.graph import gurobi_graph_artifact as g
    calls = []
    def root(path, **kwargs):
        calls.append(kwargs)
        return {"relaxation_vector": [.5], "variable_names": ["x"], "capture_method": "first_optimal_root_gurobi_mipnode"}
    def graph(**kwargs):
        path = kwargs["output_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(kwargs["sample_metadata"]["sample_id"])
        return {"graph_sha256": s.sha256_file(path), "roundtrip_readable": True,
                "label_variable_identity_match": True, "root_lp_feature_exactly_encoded": True,
                "independent_label_feasibility": {"valid": True}}
    monkeypatch.setattr(g, "capture_root_relaxation", root)
    monkeypatch.setattr(g, "build_graph_artifact", graph)
    return calls


def test_admitted_import_has_explicit_solver_source():
    payload = {"solution_source": "independently_audited_gurobi_confirmation_label",
               "effective_objective_sense": "MINIMIZE", "mathematical_audit": {"valid": True},
               "variables": [{"name": "x", "value": 1.}]}
    assert _solution_by_name(payload, label_source_solver="gurobi") == {"x": 1.}
    with pytest.raises(GurobiGraphError):
        _solution_by_name(payload, label_source_solver="scip")
    payload["mathematical_audit"]["valid"] = False
    with pytest.raises(GurobiGraphError):
        _solution_by_name(payload, label_source_solver="gurobi")


def test_incomplete_label_gate_blocks_graphs(cohort):
    campaign, _, _ = cohort
    path = campaign / "confirmation_execution_report.json"
    report = s.read_json(path)
    report["label_inventory_ready"] = False
    s.write_json(path, report)
    with pytest.raises(ValueError, match="not complete"):
        t.admitted_sources(campaign)


def test_graph_task_resumes_only_hash_bound_completed_artifacts(cohort, monkeypatch):
    campaign, data, dataset = cohort
    calls = fake_builds(monkeypatch)
    result = t.build_graph(campaign_dir=campaign, data_root=data, dataset_dir=dataset, task_index=0)
    assert calls == [{"expected_mip_sha256": result["mip_sha256"], "time_limit_seconds": 600, "threads": 1, "seed": 42, "presolve": 0}]
    assert t.build_graph(campaign_dir=campaign, data_root=data, dataset_dir=dataset, task_index=0) == result
    assert len(calls) == 1
    s.safe_path(dataset, result["graph"]["relative_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        t.build_graph(campaign_dir=campaign, data_root=data, dataset_dir=dataset, task_index=0)


def test_graph_consolidation_needs_all_42_receipts(cohort, monkeypatch):
    campaign, data, dataset = cohort
    fake_builds(monkeypatch)
    t.build_graph(campaign_dir=campaign, data_root=data, dataset_dir=dataset, task_index=0)
    with pytest.raises(FileNotFoundError):
        t.consolidate(campaign_dir=campaign, dataset_dir=dataset, descriptive_outputs=False)


def test_full_cohort_reuses_gasse_contract_with_fixed_split_and_budget(cohort, monkeypatch):
    campaign, data, dataset = cohort
    fake_builds(monkeypatch)
    for index in range(42):
        t.build_graph(campaign_dir=campaign, data_root=data, dataset_dir=dataset, task_index=index)
    report = t.consolidate(campaign_dir=campaign, dataset_dir=dataset, descriptive_outputs=False)
    assert report["graphs"] == 42
    plan = t.training_plan(campaign_dir=campaign, dataset_dir=dataset)
    t.validate_training_plan(plan)
    assert plan["partition_counts"] == {"train": 24, "validation": 10, "test": 8}
    assert plan["protocol"]["optimization"]["epochs"] == 100
    assert plan["protocol"]["optimization"]["seed"] == 42
    assert not plan["scientific_reporting_eligible"]
    assert all(r["label_source"] == "independently_audited_gurobi_confirmation_label" for r in plan["records"])
    assert str(campaign) not in json.dumps(plan)
    assert all(r["sampling_strategy"] == "original" for r in plan["records"])


def test_resealed_split_leakage_is_rejected(cohort):
    campaign, _, _ = cohort
    path = campaign / "confirmation_label_index.jsonl"
    rows = t.read_jsonl(path)
    rows[0]["role"] = "train"
    path.write_text("".join(json.dumps(r)+"\n" for r in rows))
    report_path = campaign / "confirmation_execution_report.json"
    report = s.read_json(report_path)
    report["label_index"] = s.descriptor(campaign, path)
    s.write_json(report_path, report)
    with pytest.raises(ValueError, match="identity"):
        t.admitted_sources(campaign)


def test_confirmation_training_launchers_are_safe_and_lf_only():
    root = t.PROJECT_ROOT / "scripts/slurm/dasci"
    for name in ("submit_confirmation_graphs.sbs", "submit_confirmation_graph_audit.sbs", "submit_confirmation_training.sbs", "launch_confirmation_training.sh"):
        payload = (root / name).read_bytes()
        assert b"\r" not in payload
        assert b"set -euo pipefail" in payload
        assert b"--overwrite" not in payload
    launch = (root / "launch_confirmation_training.sh").read_text()
    assert "afterany:" in launch and "afterok:" in launch
    assert "--array=0-41%2" in launch
