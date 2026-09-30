"""Reconciliation preserves evidence; selection qualification does not solve."""
import gzip
import json
import math
from pathlib import Path

import pytest

from cfl_gnn.experiments import assignment_selection as selection
from cfl_gnn.pipelines import medium_reconciliation as m
from test_gurobi_expansion import campaign, mock_solver  # noqa: F401
from test_gurobi_expansion_campaign import prepared, flexible_solver  # noqa: F401


@pytest.mark.parametrize("q,w,expected", [(.99, 99, .5), (.5, 1, .5), (0, 100, 0), (1, 100, 1)])
def test_weight_correction_is_algebra_not_calibration(q, w, expected):
    assert selection.undo_positive_weight(q, w) == pytest.approx(expected)


@pytest.mark.parametrize("p", [-.01, 1.01, math.nan, math.inf])
def test_invalid_probabilities_rejected(p):
    with pytest.raises(ValueError): selection.assignment_confidence(p, 0)


def test_assignment_confidence_matches_submitted_value_not_max_score():
    assert selection.assignment_confidence(.99, 0) == pytest.approx(.01)
    assert selection.assignment_confidence(.99, 1) == pytest.approx(.99)
    assert selection.select_calibrated(["x"], [.99], threshold=.9975,
        minimum_confidence=.9, coverage_fraction=1, maximum_assignments=1) == []


def test_identity_permutation_caps_and_ties():
    args = dict(threshold=.5, minimum_confidence=.8, coverage_fraction=.75, maximum_assignments=2)
    a = selection.select_calibrated(["d", "a", "b", "c"], [.99, .99, .9, .5], **args)
    b = selection.select_calibrated(["c", "b", "a", "d"], [.5, .9, .99, .99], **args)
    assert a == b and [r["variable_name"] for r in a] == ["a", "d"]
    assert selection.select_calibrated(["a"], [.99], **args) == []  # floor prevents exceeding fractional cap
    with pytest.raises(ValueError): selection.select_calibrated(["a", "a"], [.1, .9], **args)


@pytest.mark.parametrize("role,strategy", [("test", "original"), ("train", "original"), ("validation", "incumbent_local_branching")])
def test_calibration_partition_rejects_leakage(role, strategy):
    with pytest.raises(ValueError):
        selection.validate_calibration_partition([dict(parent_instance_id="p", role=role, sampling_strategy=strategy)])


def test_calibration_unique_parents():
    row = dict(parent_instance_id="p", role="validation", sampling_strategy="original")
    assert selection.validate_calibration_partition([row]) == {"p"}
    with pytest.raises(ValueError): selection.validate_calibration_partition([row, row])


def test_version_caps_are_not_silent_upgrades():
    assert not selection.completion_capabilities([12, 0, 3])["start_time_limit_available"]
    assert selection.completion_capabilities([13, 0, 0])["start_work_limit_available"]
    assert not selection.completion_capabilities([13, 0, 0])["budget_selected"]
    assert not selection.completion_capabilities([12, 0, 3])["node_limit_is_wall_time_cap"]


def predictions(name):
    rows = [dict(variable_name=n, probability=p, predicted_value=0,
                 confidence=max(p, 1-p), priority=round(100*max(p, 1-p)))
            for n, p in [("a", .99), ("b", .5), ("c", .1)]]
    return dict(source_instance_id=name, predictions=rows, threshold=.9975,
                target_labels_loaded=False, binary_order_sha256=m.c.canonical_sha256(["a", "b", "c"]))


def test_prediction_diagnostics_does_not_claim_calibration():
    row = m.prediction_diagnostics(predictions("p"), "p")
    assert row["selected_assignments"] == 1 and row["selected_negative"] == 1
    assert row["selected_high_score_assigned_zero"] == 1
    assert sum(row["raw_score_decile_counts"]) == 3
    assert not row["calibration_estimated"] and not row["corrected_starts_generated"]


def test_prediction_identity_and_rule_corruption_rejected():
    payload = predictions("p")
    payload["binary_order_sha256"] = "bad"
    with pytest.raises(ValueError): m.prediction_diagnostics(payload, "p")
    payload = predictions("p")
    payload["predictions"][0]["confidence"] = .01
    with pytest.raises(ValueError): m.prediction_diagnostics(payload, "p")


@pytest.fixture
def pr56_sources(tmp_path):
    data = tmp_path / "data"
    audit, runs = data / "audit", data / "runs"
    audit.mkdir(parents=True)
    inventory, ledger = {}, []
    for number in range(2):
        name = f"CFL_medium_instance_{number}"
        directory = runs / name
        directory.mkdir(parents=True)
        inventory[name] = dict(mip={"sha256": str(number)}, role="test", fold=0)
        for method in ("unguided_control", "partial_mip_start"):
            m.c.write_json(directory / f"{method}.json", dict(contract_sha256=m.PR56_CONTRACT,
                source_instance_id=name, method=method, gate_status="passed", mip_sha256=str(number),
                effective_objective_sense="MINIMIZE", mathematical_model_unchanged=True, fresh_model=True,
                parameters={"Seed": 42}, mathematical_signature_sha256="same",
                independent_feasibility={"valid": True}, solve=dict(feasible_solution=True, terminal_mip_gap_relative=.08),
                start=dict(submitted_assignments=int(method == "partial_mip_start"), positive_assignments=0, negative_assignments=1), solver_version=[12, 0, 3]))
        with gzip.open(directory / "predictions.json.gz", "wt", encoding="utf-8") as stream:
            json.dump({**predictions(name), "contract_sha256": m.PR56_CONTRACT, "mip_sha256": str(number)}, stream)
        artifacts = {p.name: m.c.descriptor(directory, p) for p in directory.iterdir()}
        m.c.write_json(directory / "pair_receipt.json", dict(source_instance_id=name, contract_sha256=m.PR56_CONTRACT, artifacts=artifacts,
            workers=[dict(method=k, returncode=0) for k in ("unguided_control", "partial_mip_start")]))
        ledger.append(m.c.descriptor(runs, directory / "pair_receipt.json"))
    m.c.write_json(audit / "source_ledger.json", {"records": ledger})
    for name in ("per_method_outcomes.json", "per_method_outcomes.csv", "paired_effects.json", "paired_effects.csv", "per_method_status.json"):
        m.c.write_json(audit / name, {"fixture": True})
    outputs = {p.name: m.c.descriptor(audit, p) for p in audit.iterdir()}
    m.c.write_json(audit / "easy_medium_pilot_report.json", dict(contract_sha256=m.PR56_CONTRACT,
        gate_status="passed", failures=[], development_only=True, scientific_reporting_eligible=False,
        summary={"valid_pairs": 2}, outputs=outputs))
    return data, audit, runs, inventory


def test_pr56_sources_preserve_roles_without_promoting_labels(pr56_sources):
    controls, diagnostics, _ = m.inspect_pr56(*pr56_sources)
    assert len(controls) == len(diagnostics) == 2
    assert all(r["role"] == "test" and r["label_candidate"] for r in controls)
    assert all(r["promotion_status"] == "review_required_no_automatic_admission" for r in controls)


def test_pr56_corrupt_artifact_rejected(pr56_sources):
    (pr56_sources[2] / "CFL_medium_instance_0" / "predictions.json.gz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"): m.inspect_pr56(*pr56_sources)


def test_reconciles42_without_relaunching_or_admitting_hard(prepared, monkeypatch):
    data, folder, root, plan, _ = prepared
    for index, gap in enumerate([.12, .105, .03, .02, .116]):
        flexible_solver(monkeypatch, gap=gap)
        m.campaign.execute(data, folder, root, "medium", index)
    flexible_solver(monkeypatch, gap=.81)
    m.campaign.execute(data, folder, root, "hard", 0)
    monkeypatch.setattr(m, "inspect_pr56", lambda *args: ([], [], []))
    monkeypatch.setattr(m.campaign, "execute", lambda *args: pytest.fail("reconciliation must not solve"))
    output = data / "analysis/medium_reconciliation/new"
    report = m.reconcile(data, folder, root, data, data, output)
    assert report["gate_status"] == "passed"
    assert report["summary"]["admitted_parents"] == 42
    assert report["summary"]["medium_unstarted_tasks"] == 15
    assert report["summary"]["medium_review_tasks"] == 3
    assert report["decision"]["solver_runs_executed"] == 0
    assert not any(report["eligibility"][key] for key in ("training_ready", "calibration_qualified", "automatic_submission_authorized"))
    for item in report["outputs"].values(): m.c.checked(output, item)
    assert str(data) not in (output / m.REPORT).read_text()
    pending = [json.loads(line) for line in (output / "medium_continuation_tasks.jsonl").read_text().splitlines()]
    assert len(pending) == 15 and {r["continuation_batch"] for r in pending} == {0, 1, 2}
    assert all(r["phase"] == "medium" and r["proposed_time_limit_seconds"] == 28800 for r in pending)
    with pytest.raises(FileExistsError): m.reconcile(data, folder, root, data, data, output)


def test_incomplete_evidence_blocks_gate(prepared, monkeypatch):
    data, folder, root, plan, _ = prepared
    m.c.safe_path(root, plan["tasks"][0]["run_relative_path"]).mkdir(parents=True)
    monkeypatch.setattr(m, "inspect_pr56", lambda *args: ([], [], []))
    report = m.reconcile(data, folder, root, data, data, data / "analysis/medium_reconciliation/incomplete")
    assert report["gate_status"] == "failed" and report["failures"][0]["reason_code"] == "incomplete"


def test_launcher_is_audit_only_lf():
    path = Path(__file__).parents[2] / "scripts/slurm/dasci/submit_medium_reconciliation.sbs"
    raw = path.read_bytes()
    assert b"\r" not in raw and b"--mem=8G" in raw
    assert b"reconcile_medium_sources" in raw and b"--gres" not in raw
