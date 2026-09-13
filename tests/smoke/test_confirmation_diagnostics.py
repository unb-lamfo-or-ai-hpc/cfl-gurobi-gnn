"""Rejection triage must preserve evidence and never promote partial cohorts."""
import json

import pytest

from cfl_gnn.pipelines import confirmation_diagnostics as d
from cfl_gnn.pipelines import confirmation_execution as c


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def campaign(tmp_path):
    tasks = [{"source_instance_id": name, "role": "train", "fold": 2,
              "task_index": i, "mip": {"sha256": "parent"}}
             for i, name in enumerate(c.COHORT)]
    plan = {"tasks": tasks, "objective_sense": "MINIMIZE", "seed": 42, "epochs": 100,
            "maximum_label_mip_gap_relative": .1, "repair_budgets_seconds": [3600, 14400],
            "implementation_sha256": c.implementation_hashes(), "repair_plans": {}}
    for budget in (3600, 14400):
        repair = {"tasks": [{**t, "solver": "gurobi",
                   "run_dir_relative_path": f"{budget}/{t['source_instance_id']}"} for t in tasks]}
        path = tmp_path / f"repair_{budget}s/parent_collection_plan.json"
        write(path, repair)
        plan["repair_plans"][str(budget)] = c.descriptor(tmp_path, path)
    plan["contract_sha256"] = c.canonical_sha256(plan)
    write(tmp_path / c.PLAN, plan)
    index = tmp_path / "confirmation_label_index.jsonl"
    index.write_text("", encoding="utf-8")
    write(tmp_path / "confirmation_execution_report.json", {
        "campaign_contract_sha256": plan["contract_sha256"], "independently_admissible_parents": 0,
        "label_index": c.descriptor(tmp_path, index),
        "records": [{"source_instance_id": t["source_instance_id"], "role": t["role"],
                     "label_eligible": False} for t in tasks]})
    return plan


def repair(tmp_path, plan, *, gap=.2, failed=False):
    task = plan["tasks"][0]
    root = tmp_path / "repair_runs/14400" / task["source_instance_id"]
    artifacts = {}
    for key in ("solution", "incumbents", "variable_order"):
        path = root / f"{key}.json"
        write(path, {"not_deserialized": True})
        artifacts[key] = {"file_name": path.name, "sha256": c.sha256_file(path)}
    checks = {k: True for k in d.CHECKS}
    checks["trace_consistent"] = not failed
    path = root / "gurobi_parent_solve_report.json"
    write(path, {"parent": {"source_instance_id": task["source_instance_id"], "sha256": "parent"},
        "solve": {"mip_gap_relative": gap, "execution_time_seconds": 14401., "solve_status": "timelimit"},
        "checks": checks, "artifacts": artifacts, "runtime_environment": {"secret": "/home/private"}})
    return path


def test_read_only_missing_reports_are_not_budget_failures(tmp_path):
    campaign(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = d.diagnose(tmp_path)
    assert result["pending_parents"] == 42
    assert result["solver_runs_executed"] == 0 and not result["training_authorized"]
    assert result["pending"][0]["repairs"][0]["status"] == "missing_or_invalid_evidence"
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("gap,failed,expected", [
    (.2, False, "gap_above_policy_or_invalid"),
    (0., True, "collector_checks_require_review"),
    (0., False, "review_independent_admission"),
])
def test_gap_and_instrumentation_are_separate(tmp_path, gap, failed, expected):
    plan = campaign(tmp_path)
    repair(tmp_path, plan, gap=gap, failed=failed)
    result = d.diagnose(tmp_path)
    evidence = result["pending"][0]["repairs"][1]
    assert evidence["status"] == expected
    assert evidence["right_censored"] is True
    assert evidence["execution_time_seconds"] == 14401.
    assert not result["automatic_retry_authorized"]
    assert "/home/private" not in json.dumps(result)


def test_corrupt_artifact_is_not_a_solver_quality_failure(tmp_path):
    plan = campaign(tmp_path)
    path = repair(tmp_path, plan)
    (path.parent / "solution.json").write_bytes(b"changed")
    assert d.diagnose(tmp_path)["pending"][0]["repairs"][1]["status"] == "artifact_hash_or_presence_failure"


def test_report_hash_is_bound_to_recorded_attempt(tmp_path):
    plan = campaign(tmp_path)
    repair(tmp_path, plan)
    task = plan["tasks"][0]
    write(tmp_path / "labels" / task["source_instance_id"] / c.REPORT, {
        "campaign_contract_sha256": plan["contract_sha256"], **task, "mip_sha256": "parent",
        "repair_outcomes": [{"budget_seconds": 14400, "report_sha256": "wrong"}],
        "source_errors": [{"reason": "secret /raid/private/gurobi.lic"}]})
    result = d.diagnose(tmp_path)
    assert result["pending"][0]["repairs"][1]["recorded_report_hash_match"] is False
    assert result["pending"][0]["repairs"][1]["status"] == "missing_or_invalid_evidence"
    assert "gurobi.lic" not in json.dumps(result)


def test_label_index_hash_mismatch_blocks_diagnostic(tmp_path):
    campaign(tmp_path)
    (tmp_path / "confirmation_label_index.jsonl").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        d.diagnose(tmp_path)


def test_accepted_receipts_are_checked_without_reading_vectors(tmp_path):
    plan = campaign(tmp_path)
    task = plan["tasks"][0]
    for name in ("accepted_solution.gz", "accepted_report.json"):
        (tmp_path / name).write_bytes(b"hash checked, never deserialized")
    index = tmp_path / "confirmation_label_index.jsonl"
    entry = {"source_instance_id": task["source_instance_id"],
             "solution": c.descriptor(tmp_path, tmp_path / "accepted_solution.gz"),
             "report": c.descriptor(tmp_path, tmp_path / "accepted_report.json")}
    index.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    path = tmp_path / "confirmation_execution_report.json"
    aggregate = c.read_json(path)
    aggregate["records"][0]["label_eligible"] = True
    aggregate["independently_admissible_parents"] = 1
    aggregate["label_index"] = c.descriptor(tmp_path, index)
    write(path, aggregate)
    result = d.diagnose(tmp_path)
    assert result["admitted_parents"] == 1 and result["pending_parents"] == 41
    assert result["admitted_by_role"] == {"train": 1}
    (tmp_path / "accepted_solution.gz").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="changed"):
        d.diagnose(tmp_path)
