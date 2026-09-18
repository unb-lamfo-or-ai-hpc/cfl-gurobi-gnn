"""Remaining batches never consume an unfinished or failed predecessor audit."""
from pathlib import Path

import pytest

from cfl_gnn.pipelines import medium_queue as m
from test_gurobi_expansion import campaign, mock_solver  # noqa: F401
from test_gurobi_expansion_campaign import prepared, flexible_solver  # noqa: F401
from test_medium_continuation import reconciled  # noqa: F401


@pytest.fixture
def queue_inputs(reconciled):
    m.previous.prepare(*reconciled)
    data, folder, root, _, preflight = reconciled
    predecessor = data / "analysis/gurobi_expansion_campaign/batch1_audit"
    output = data / "analysis/medium_queue/remaining"
    return data, folder, root, preflight / m.previous.PLAN, predecessor, output


def test_prepares_ten_without_touching_active_first_batch(queue_inputs, monkeypatch):
    data, folder, root, _, _, output = queue_inputs
    task = m.campaign.select_task(m.campaign.load_plan(folder), "medium", 5)
    directory = m.c.safe_path(root, task["run_relative_path"])
    directory.mkdir(parents=True)
    marker = directory / "active.txt"
    marker.write_text("do not modify")
    monkeypatch.setattr(m.campaign, "execute", lambda *a: pytest.fail("preparation must not solve"))
    result = m.prepare(*queue_inputs)
    assert [t["task_index"] for t in result["tasks"]] == list(range(10, 20))
    assert [t["source_instance_id"] for t in result["tasks"]] == [f"CFL_medium_instance_{i}" for i in range(20, 30)]
    assert all(t["time_limit_seconds"] == 28800 for t in result["tasks"])
    assert result["preserved_labels"] == 42 and result["hard_jobs"] == result["training_jobs"] == 0
    assert result["concurrency"] == 1 and result["memory_gib"] == 64
    assert marker.read_text() == "do not modify"
    assert str(data) not in (output / m.PLAN).read_text()
    assert m.load(data, output)[1] == result
    with pytest.raises(FileExistsError): m.prepare(*queue_inputs)


def test_missing_predecessor_blocks_before_solver(queue_inputs, monkeypatch):
    m.prepare(*queue_inputs)
    monkeypatch.setattr(m.campaign, "execute", lambda *a: pytest.fail("missing audit must block solver"))
    with pytest.raises((OSError, ValueError)):
        m.execute(queue_inputs[0], queue_inputs[-1], 10)


def complete_first_batch(args, monkeypatch):
    data, folder, root, _, audit, _ = args
    flexible_solver(monkeypatch, gap=.15)
    for index in range(5, 10):
        m.campaign.execute(data, folder, root, "medium", index)
    return m.campaign.audit(data, folder, root, audit, 1)


def test_valid_high_gap_predecessor_permits_original_solve_not_label_admission(queue_inputs, monkeypatch):
    m.prepare(*queue_inputs)
    report = complete_first_batch(queue_inputs, monkeypatch)
    assert report["gate_status"] == "passed" and report["summary"]["admitted_population"] == 42
    calls = flexible_solver(monkeypatch, gap=.13)
    result = m.execute(queue_inputs[0], queue_inputs[-1], 10)
    assert result["execution_valid"] and not result["label_eligible"]
    assert len(calls) == 1 and calls[0].time_limit == 28800
    assert m.execute(queue_inputs[0], queue_inputs[-1], 10) == result
    assert len(calls) == 1
    with pytest.raises((OSError, ValueError)): m.execute(queue_inputs[0], queue_inputs[-1], 15)


@pytest.mark.parametrize("change", ["failed", "wrong_batch", "corrupt_metrics"])
def test_bad_predecessor_prevents_solver(queue_inputs, monkeypatch, change):
    m.prepare(*queue_inputs)
    report = complete_first_batch(queue_inputs, monkeypatch)
    if change == "failed":
        report["gate_status"] = "failed"
    elif change == "wrong_batch":
        report["requested_medium_batch"] = 0
    else:
        (queue_inputs[4] / "campaign_task_metrics.json").write_text("{}")
    m.c.write_json(queue_inputs[4] / m.campaign.REPORT, report)
    monkeypatch.setattr(m.campaign, "execute", lambda *a: pytest.fail("bad audit must block solver"))
    with pytest.raises(ValueError): m.execute(queue_inputs[0], queue_inputs[-1], 10)


def test_remaining_attempt_cannot_be_replanned(queue_inputs):
    task = m.campaign.select_task(m.campaign.load_plan(queue_inputs[1]), "medium", 10)
    m.c.safe_path(queue_inputs[2], task["run_relative_path"]).mkdir(parents=True)
    with pytest.raises(ValueError, match="already started"): m.prepare(*queue_inputs)


def test_queue_cannot_select_current_rescue_or_hard_task(queue_inputs, monkeypatch):
    m.prepare(*queue_inputs)
    monkeypatch.setattr(m.campaign, "execute", lambda *a: pytest.fail("wrong task"))
    for index in (0, 5, 20):
        with pytest.raises(ValueError, match="not in"): m.execute(queue_inputs[0], queue_inputs[-1], index)


def test_changed_preserved_solution_blocks(queue_inputs):
    queue = m.prepare(*queue_inputs)
    source = next(r for r in queue["sources"] if r["relative_path"].endswith("solution.json.gz"))
    m.c.safe_path(queue_inputs[0], source["relative_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError): m.load(queue_inputs[0], queue_inputs[-1])


def test_second_remaining_batch_requires_and_accepts_its_own_predecessor(queue_inputs, monkeypatch):
    queue = m.prepare(*queue_inputs)
    complete_first_batch(queue_inputs, monkeypatch)
    flexible_solver(monkeypatch, gap=.15)
    for index in range(10, 15):
        m.execute(queue_inputs[0], queue_inputs[-1], index)
    audit = m.c.safe_path(queue_inputs[0], queue["audit_dirs"]["2"])
    report = m.campaign.audit(*queue_inputs[:3], audit, 2)
    assert report["gate_status"] == "passed"
    calls = flexible_solver(monkeypatch, gap=.07)
    result = m.execute(queue_inputs[0], queue_inputs[-1], 15)
    assert result["label_eligible"] and len(calls) == 1


@pytest.mark.parametrize("change", ["budget", "identity"])
def test_rehashed_modified_policy_cannot_expand_scope(queue_inputs, change):
    queue = m.prepare(*queue_inputs)
    if change == "budget":
        queue["time_limit_seconds"] = 57600
    else:
        queue["tasks"][0]["phase"] = "hard"
    queue["contract_sha256"] = m.c.canonical_sha256({k: v for k, v in queue.items() if k != "contract_sha256"})
    m.c.write_json(queue_inputs[-1] / m.PLAN, queue)
    with pytest.raises(ValueError): m.load(queue_inputs[0], queue_inputs[-1])


def test_scripts_freeze_source_and_audit_before_continuation():
    folder = Path(__file__).parents[2] / "scripts/slurm/dasci"
    submit = (folder / "queue_remaining_medium_batches.sh").read_bytes()
    worker = (folder / "submit_remaining_medium_task.sbs").read_bytes()
    assert b"\r" not in submit + worker
    for token in (b"afterok:", b"afterany:", b"--kill-on-invalid-dep=yes", b"flock -n", b"for BATCH in 2 3", b"submission.txt"):
        assert token in submit
    assert b"--mem=64G" in worker and b"--time=12:00:00" in worker
    assert b"PR57_QUEUE_COMMIT" in worker and b"remaining_medium_queue task" in worker
    assert b"git pull" not in submit + worker and b"git switch" not in submit + worker
