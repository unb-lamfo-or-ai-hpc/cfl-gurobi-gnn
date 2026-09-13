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
    assert '--array="0-$((COHORT_SIZE-1))%2"' in launch
    assert "--development39" in launch and "graph_contract" in launch


@pytest.fixture
def revised_cohort(cohort):
    from cfl_gnn.pipelines import confirmation_revision as r
    from cfl_gnn.pipelines.confirmation_diagnostics import CHECKS
    campaign, data, dataset = cohort
    plan = s.read_json(campaign / s.PLAN)
    plan["repair_plans"] = {}
    for budget in (3600, 14400):
        tasks = [{**task, "solver": "gurobi", "run_dir_relative_path": f"{budget}/{task['source_instance_id']}"}
                 for task in plan["tasks"]]
        path = campaign / f"repair_{budget}s/parent_collection_plan.json"
        s.write_json(path, {"tasks": tasks})
        plan["repair_plans"][str(budget)] = s.descriptor(campaign, path)
    plan["contract_sha256"] = s.canonical_sha256({k: v for k, v in plan.items() if k != "contract_sha256"})
    s.write_json(campaign / s.PLAN, plan)
    for task in plan["tasks"]:
        identity = task["source_instance_id"]
        if identity not in r.EXCLUDED:
            continue
        outcomes = []
        for budget in (3600, 14400):
            root = campaign / f"repair_runs/{budget}/{identity}"
            artifacts = {}
            for key in ("solution", "incumbents", "variable_order"):
                path = root / (key + ".json")
                s.write_json(path, {"fixture": key})
                artifacts[key] = {"file_name": path.name, "sha256": s.sha256_file(path)}
            path = root / "gurobi_parent_solve_report.json"
            s.write_json(path, {"parent": {"source_instance_id": identity, "sha256": task["mip"]["sha256"]},
                "solve": {"mip_gap_relative": .13, "execution_time_seconds": budget, "solve_status": "timelimit"},
                "checks": dict.fromkeys(CHECKS, True), "artifacts": artifacts, "eligibility": {"label_eligible": False}})
            outcomes.append({"budget_seconds": budget, "report_sha256": s.sha256_file(path)})
        s.write_json(campaign / "labels" / identity / s.REPORT, {
            "campaign_contract_sha256": plan["contract_sha256"], **task, "mip_sha256": task["mip"]["sha256"],
            "label_eligible": False, "repair_outcomes": outcomes, "source_errors": []})
    index = campaign / "confirmation_label_index.jsonl"
    rows = [row for row in t.read_jsonl(index) if row["source_instance_id"] in r.COHORT]
    index.write_text("".join(json.dumps(row)+"\n" for row in rows))
    s.write_json(campaign / "confirmation_execution_report.json", {
        "campaign_contract_sha256": plan["contract_sha256"], "gate_status": "incomplete", "label_inventory_ready": False,
        "independently_admissible_parents": 39, "label_index": s.descriptor(campaign, index),
        "records": [{"source_instance_id": task["source_instance_id"], "role": task["role"],
                     "label_eligible": task["source_instance_id"] in r.COHORT} for task in plan["tasks"]]})
    return campaign, data, dataset, campaign.parent / "revision"


def test_revised_39_requires_explicit_contract_and_preserves_sources(revised_cohort):
    from cfl_gnn.pipelines import confirmation_revision as r
    campaign, _, _, revision = revised_cohort
    before = {p: p.read_bytes() for p in campaign.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="not complete"):
        t.admitted_sources(campaign)
    result = r.prepare(campaign, revision)
    assert result["partition_counts"] == {"train": 23, "validation": 8, "test": 8}
    assert result["original_campaign_remains_incomplete"] is True
    assert len(t.admitted_sources(campaign, revision)[2]) == 39
    assert before == {p: p.read_bytes() for p in campaign.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="new revision"):
        r.prepare(campaign, revision)


def test_39_graphs_and_training_use_the_approved_model_split_and_protocol(revised_cohort, monkeypatch):
    from cfl_gnn.pipelines import confirmation_revision as r
    campaign, data, dataset, revision = revised_cohort
    r.prepare(campaign, revision)
    fake_builds(monkeypatch)
    for i in range(39):
        t.build_graph(campaign_dir=campaign, data_root=data, dataset_dir=dataset, task_index=i, cohort_revision_dir=revision)
    with pytest.raises(ValueError, match="outside"):
        t.build_graph(campaign_dir=campaign, data_root=data, dataset_dir=dataset, task_index=39, cohort_revision_dir=revision)
    report = t.consolidate(campaign_dir=campaign, dataset_dir=dataset, cohort_revision_dir=revision, descriptive_outputs=False)
    assert report["graphs"] == 39
    plan = t.training_plan(campaign_dir=campaign, dataset_dir=dataset, cohort_revision_dir=revision)
    t.validate_training_plan(plan)
    assert plan["dataset_variant"] == "approved_39_parent_development_v1"
    assert plan["partition_counts"] == r.COUNTS
    assert {row["sample_id"] for row in plan["records"]} == set(r.COHORT)
    assert plan["protocol"]["protocol_id"] == "gasse_39_parent_development_v1"
    assert plan["protocol"]["optimization"]["epochs"] == plan["protocol"]["optimization"]["patience"] == 100
    assert plan["protocol"]["optimization"]["seed"] == 42
    assert plan["protocol"]["sampling"]["maximum_label_mip_gap_relative"] == .1
    assert str(campaign) not in json.dumps(plan)
    assert not plan["scientific_reporting_eligible"]
    with pytest.raises(ValueError, match="descriptive"):
        t.train_and_evaluate(campaign_dir=campaign, dataset_dir=dataset, output_dir=dataset / "train", cohort_revision_dir=revision)


@pytest.mark.parametrize("key,value", [("seed", 43), ("epochs", 1), ("maximum_label_mip_gap_relative", .15),
                                      ("excluded_parents", ["CFL_medium_instance_2"])])
def test_resealed_policy_changes_cannot_expand_revision(revised_cohort, key, value):
    from cfl_gnn.pipelines import confirmation_revision as r
    campaign, _, _, revision = revised_cohort
    result = r.prepare(campaign, revision)
    result[key] = value
    result["contract_sha256"] = s.canonical_sha256({k: v for k, v in result.items() if k != "contract_sha256"})
    s.write_json(revision / r.NAME, result)
    with pytest.raises(ValueError, match="policy"):
        r.load(campaign, revision)


def test_revision_rejects_changed_source_receipt(revised_cohort):
    from cfl_gnn.pipelines import confirmation_revision as r
    campaign, _, _, revision = revised_cohort
    r.prepare(campaign, revision)
    path = campaign / "confirmation_execution_report.json"
    result = s.read_json(path)
    result["changed"] = True
    s.write_json(path, result)
    with pytest.raises(ValueError, match="source campaign changed"):
        r.load(campaign, revision)


def test_revision_never_writes_inside_source_campaign(revised_cohort):
    from cfl_gnn.pipelines import confirmation_revision as r
    campaign, _, _, _ = revised_cohort
    with pytest.raises(ValueError, match="separate"):
        r.prepare(campaign, campaign / "revision")


@pytest.mark.parametrize("loss,accepted", [("0.2", True), ("nan", False), ("inf", False), ("-0.2", False)])
def test_heldout_access_requires_100_finite_training_and_validation_epochs(tmp_path, loss, accepted):
    history = tmp_path / t.TRAINING_HISTORY_NAME
    history.write_text("epoch,train_loss,validation_loss\n" + "".join(f"{i},0.3,{loss}\n" for i in range(1, 101)))
    (tmp_path / "best_model.pt").write_bytes(b"checkpoint fixture")
    (tmp_path / "training_validation_loss.svg").write_text("<svg/>")
    report = {"gate_status": "passed", "epochs_completed": 100, "test_graphs_loaded": 0,
              "checkpoint_selection": "minimum_validation_weighted_bce", "threshold_source": "maximum_validation_f1",
              "outputs": {key: {"file_name": name, "sha256": s.sha256_file(tmp_path / name)}
                          for key, name in (("checkpoint", "best_model.pt"), (t.TRAINING_HISTORY_NAME, t.TRAINING_HISTORY_NAME),
                                            ("training_validation_loss.svg", "training_validation_loss.svg"))}}
    if accepted:
        t.validate_training_receipt(report, tmp_path)
        report["test_graphs_loaded"] = 1
        with pytest.raises(ValueError, match="selection contract"):
            t.validate_training_receipt(report, tmp_path)
    else:
        with pytest.raises(ValueError, match="finite epochs"):
            t.validate_training_receipt(report, tmp_path)
