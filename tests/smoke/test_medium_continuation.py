"""Continuation is a read-only gate over immutable, independently audited solves."""
import json
from pathlib import Path

import pytest

from cfl_gnn.pipelines import medium_continuation as m
from test_gurobi_expansion import campaign, mock_solver  # noqa: F401
from test_gurobi_expansion_campaign import prepared, flexible_solver  # noqa: F401


@pytest.fixture
def reconciled(prepared, monkeypatch):
    data, folder, root, _, _ = prepared
    for index, gap in enumerate([.12, .105, .03, .02, .116]):
        flexible_solver(monkeypatch, gap=gap)
        m.campaign.execute(data, folder, root, "medium", index)
    flexible_solver(monkeypatch, gap=.81)
    m.campaign.execute(data, folder, root, "hard", 0)
    monkeypatch.setattr(m.reconciliation, "inspect_pr56", lambda *args: ([], [], []))
    source = data / "analysis/medium_reconciliation/new"
    m.reconciliation.reconcile(data, folder, root, data, data, source)
    return data, folder, root, source, data / "analysis/medium_continuation/new"


@pytest.mark.parametrize("batch,indices", [(0, list(range(5, 10))), (1, list(range(10, 15))), (2, list(range(15, 20)))])
def test_five_original_tasks_keep_budget_and_admitted_labels(reconciled, monkeypatch, batch, indices):
    monkeypatch.setattr(m.campaign, "execute", lambda *a: pytest.fail("preflight must not solve"))
    result = m.prepare(*reconciled, continuation_batch=batch)
    assert result["preserved_labels"] == 42
    assert result["preserved_by_difficulty"] == {"easy": 30, "medium": 12}
    assert [t["task_index"] for t in result["selected_tasks"]] == indices
    assert result["original_campaign_batch"] == batch + 1
    assert result["slurm_array"] == ",".join(map(str, indices)) + "%1"
    assert result["memory_gib"] == 64 and result["time_limit_seconds"] == 28800
    assert not result["hard_campaign_authorized"] and not result["automatic_submission_authorized"]
    assert result["solver_runs_executed"] == 0
    assert str(reconciled[0]) not in (reconciled[-1] / m.PLAN).read_text()
    with pytest.raises(FileExistsError): m.prepare(*reconciled, continuation_batch=batch)


def rewrite_output(args, filename, rows):
    source = args[3]
    m.campaign.write_jsonl(source / filename, rows)
    report = m.c.read_json(source / m.reconciliation.REPORT)
    report["outputs"][filename] = m.c.descriptor(source, source / filename)
    m.c.write_json(source / m.reconciliation.REPORT, report)


def test_corrupted_output_hash_blocks(reconciled):
    (reconciled[3] / "medium_continuation_tasks.jsonl").write_bytes(b"changed")
    with pytest.raises(ValueError): m.prepare(*reconciled)
    assert not reconciled[-1].exists()


@pytest.mark.parametrize("key,value", [("role", "test"), ("task_index", 0), ("phase", "hard"),
                                        ("proposed_time_limit_seconds", 57600), ("continuation_batch", 2)])
def test_changed_queue_cannot_launch_wrong_task_even_if_rehashed(reconciled, key, value):
    path = reconciled[3] / "medium_continuation_tasks.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0][key] = value
    rewrite_output(reconciled, path.name, rows)
    with pytest.raises(ValueError, match="continuation identity"): m.prepare(*reconciled)


def test_preserved_label_replacement_rejected(reconciled):
    path = reconciled[3] / "preserved_label_index.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["mip_gap_relative"] = .099
    rewrite_output(reconciled, path.name, rows)
    with pytest.raises(ValueError, match="admitted inventory changed"): m.prepare(*reconciled)


def test_task_started_since_reconciliation_blocks(reconciled, monkeypatch):
    flexible_solver(monkeypatch, gap=.15)
    m.campaign.execute(*reconciled[:3], "medium", 5)
    with pytest.raises(ValueError, match="unstarted inventory changed"): m.prepare(*reconciled)


def test_partial_attempt_is_not_replaced(reconciled):
    task = m.campaign.select_task(m.campaign.load_plan(reconciled[1]), "medium", 5)
    m.c.safe_path(reconciled[2], task["run_relative_path"]).mkdir(parents=True)
    with pytest.raises((OSError, ValueError)): m.prepare(*reconciled)


def test_sanitization_rejects_private_path(reconciled):
    rewrite_output(reconciled, "historical_prediction_diagnostics.jsonl", [{"path": "/home/private/file"}])
    with pytest.raises(ValueError, match="sanitization"): m.prepare(*reconciled)


def test_report_failure_or_contract_mutation_blocks(reconciled):
    path = reconciled[3] / m.reconciliation.REPORT
    report = m.c.read_json(path)
    report["seed"] = 43
    m.c.write_json(path, report)
    with pytest.raises(ValueError, match="hash-bound"): m.prepare(*reconciled)


@pytest.mark.parametrize("batch", [-1, 3, True])
def test_invalid_batch_rejected(reconciled, batch):
    with pytest.raises(ValueError): m.prepare(*reconciled, continuation_batch=batch)


def test_submission_helper_preserves_resources_and_records_before_audit():
    script = Path(__file__).parents[2] / "scripts/slurm/dasci/submit_reviewed_medium_continuation.sh"
    raw = script.read_bytes()
    assert b"\r" not in raw
    text = raw.decode()
    for required in ("flock -n", "squeue -h", "--test-only", "afterany:", "PR57_EXPECTED_COMMIT",
                     "prepare_medium_continuation", "original_campaign_batch", "submission.txt"):
        assert required in text
    assert text.index("MEDIUM_JOB_ID=%s") < text.index('AUDIT_JOB=$(sbatch')
    assert "submit_gurobi_hard" not in text

