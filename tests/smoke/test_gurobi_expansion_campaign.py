"""PR54 preserves pilot evidence and isolates medium/hard budgets."""
import json
import sys
from types import SimpleNamespace

import pytest

from cfl_gnn.pipelines import gurobi_expansion_campaign as m
from test_gurobi_expansion import campaign, mock_solver, zipped, Model, Env


@pytest.fixture
def prepared(campaign, monkeypatch):
    data, pilot_dir, pilot_root, old = campaign
    mock_solver(monkeypatch, gap=.08, status="timelimit")
    m.pilot.execute(data, pilot_dir, pilot_root, 0)
    mock_solver(monkeypatch, gap=.64, status="timelimit")
    m.pilot.execute(data, pilot_dir, pilot_root, 1)
    old_audit = data / "analysis/gurobi_expansion/pilot_audit"
    m.pilot.audit(data, pilot_dir, pilot_root, old_audit)
    folder = data / "analysis/gurobi_expansion_campaign/plan"
    root = data / "intermediate/gurobi_expansion_campaign/runs"
    plan = m.prepare(data, pilot_dir, pilot_root, old_audit, folder)
    return data, folder, root, plan, pilot_root


def flexible_solver(monkeypatch, *, gap=.08, value=1., wrong_budget=False):
    monkeypatch.setitem(sys.modules, "gurobipy", SimpleNamespace(Env=Env,
        read=lambda *a, **k: Model(), GRB=SimpleNamespace(MINIMIZE=1)))
    calls = []
    def run(solve):
        calls.append(solve)
        req = m.parent.worker_request(solve)
        assert req["force_minimize"] is True and req["seed"] == 42 and req["threads"] == 1
        parameters = {**m.PARAMETERS, "TimeLimit": 123 if wrong_budget else solve.time_limit}
        payload = {"candidate_sha256": solve.parent_sha256, "contract_sha256": solve.contract_sha256,
            "solution_source": "independent_gurobi_optimization",
            "solver_feasibility_check_space": "original_model_solution_quality",
            "fresh_process": True, "pre_solve_solution_count": 0, "warm_start_supplied": False,
            "objective_sense": "minimize", "original_objective_sense": "maximize",
            "solver_feasibility_check": True, "solution_count": 1,
            "solution_objective": 2., "best_bound": 2*(1-gap), "mip_gap_relative": gap,
            "execution_time_seconds": 10., "solve_status": "timelimit",
            "variables": [{"name": "x", "value": value}],
            "solver_parameter_map": parameters, "solver_parameter_sha256": m.c.canonical_sha256(parameters),
            "runtime_environment": dict(hostname="test", platform="test", machine="test", logical_cpu_count=1),
            "solver_versions": {"gurobi": "test"},
            "time_regions": dict(zip(m.pilot.REGIONS, [13., 1., 1., 10.])),
            "online_incumbent_capture": {"events_recorded": 1, "vectors_streamed": 1,
                "capture_error_count": 0, "stream_committed": True},
            "incumbent_trace_audit": {"incumbent_trace_consistent": True}}
        zipped(solve.output_dir / m.parent.SOLUTION_NAME, payload)
        for name in (m.parent.INCUMBENTS_NAME, m.parent.VARIABLE_ORDER_NAME):
            (solve.output_dir / name).write_bytes(b"mock artifact")
        return m.parent.evaluate_solution(solve, payload)
    monkeypatch.setattr(m.parent, "run", run)
    return calls


def test_preserves_forty_and_freezes_all_pending_batches(prepared):
    data, folder, _, plan, _ = prepared
    assert len(plan["preserved"]) == 40 and len(plan["tasks"]) == 21 and len(plan["deferred"]) == 29
    assert [r["source_instance_id"] for r in plan["tasks"][:5]] == [f"CFL_medium_instance_{i}" for i in range(5, 10)]
    assert all(sum(t["batch_index"] == i for t in plan["tasks"]) == 5 for i in range(4))
    assert plan["tasks"][-1]["source_instance_id"] == "CFL_hard_instance_1"
    assert plan["tasks"][-1]["time_limit_seconds"] == 57600
    assert any(r["source_instance_id"] == "CFL_hard_instance_0" for r in plan["deferred"])
    assert [r["label_eligible"] for r in plan["historical_pilot_attempts"]] == [True, False]
    assert m.load_plan(folder) == plan
    assert str(data) not in (folder / m.PLAN).read_text()
    assert len((folder / "preserved_parent_label_index.jsonl").read_text().splitlines()) == 40


@pytest.mark.parametrize("phase,index,budget", [("medium", 0, 28800), ("medium", 19, 28800), ("hard", 0, 57600)])
def test_effective_budget_and_independent_validation(prepared, monkeypatch, phase, index, budget):
    data, folder, root, _, _ = prepared
    calls = flexible_solver(monkeypatch)
    result = m.execute(data, folder, root, phase, index)
    assert result["execution_valid"] and result["label_eligible"]
    assert result["right_censored"] and result["mathematical_audit"]["valid"]
    assert calls[0].time_limit == budget and result["task"]["time_limit_seconds"] == budget
    assert m.execute(data, folder, root, phase, index) == result
    assert len(calls) == 1


def test_wrong_effective_budget_is_not_accepted(prepared, monkeypatch):
    data, folder, root, _, _ = prepared
    flexible_solver(monkeypatch, wrong_budget=True)
    result = m.execute(data, folder, root, "hard", 0)
    assert not result["execution_valid"] and not result["label_eligible"]
    assert result["checks"]["effective_budget_matches"] is False


def test_invalid_mathematics_blocks_even_small_gap(prepared, monkeypatch):
    data, folder, root, _, _ = prepared
    flexible_solver(monkeypatch, gap=0., value=0.)
    result = m.execute(data, folder, root, "medium", 0)
    assert not result["execution_valid"] and not result["label_eligible"]
    with pytest.raises(ValueError, match="failed attempt"):
        m.execute(data, folder, root, "medium", 0)


def test_censored_unadmitted_attempt_resumes_without_resolve(prepared, monkeypatch):
    data, folder, root, _, _ = prepared
    calls = flexible_solver(monkeypatch, gap=.64)
    result = m.execute(data, folder, root, "hard", 0)
    assert result["execution_valid"] and not result["label_eligible"]
    assert m.execute(data, folder, root, "hard", 0) == result
    assert len(calls) == 1


def test_source_hard_negative_evidence_cannot_change(prepared, monkeypatch):
    data, folder, root, plan, _ = prepared
    evidence = m.c.checked(data, plan["historical_pilot_attempts"][1]["receipt"])
    evidence.write_bytes(b"changed")
    calls = flexible_solver(monkeypatch)
    with pytest.raises(ValueError, match="changed"):
        m.execute(data, folder, root, "medium", 0)
    assert not calls and not root.exists()


def test_partial_folder_and_corrupt_resume_protected(prepared, monkeypatch):
    data, folder, root, plan, _ = prepared
    task = m.select_task(plan, "medium", 0)
    m.c.safe_path(root, task["run_relative_path"]).mkdir(parents=True)
    calls = flexible_solver(monkeypatch)
    with pytest.raises(FileExistsError): m.execute(data, folder, root, "medium", 0)
    assert not calls
    m.execute(data, folder, root, "hard", 0)
    output = m.c.safe_path(root, m.select_task(plan, "hard", 0)["run_relative_path"])
    (output / m.parent.INCUMBENTS_NAME).write_bytes(b"broken")
    with pytest.raises(ValueError): m.execute(data, folder, root, "hard", 0)
    assert len(calls) == 1


def test_selected_batch_passes_without_claiming_unstarted_tasks_failed(prepared, monkeypatch):
    data, folder, root, _, _ = prepared
    flexible_solver(monkeypatch)
    for i in range(5): m.execute(data, folder, root, "medium", i)
    flexible_solver(monkeypatch, gap=.64)
    m.execute(data, folder, root, "hard", 0)
    out = data / "analysis/gurobi_expansion_campaign/audit"
    result = m.audit(data, folder, root, out, 0)
    assert result["gate_status"] == "passed"
    assert result["summary"]["not_started_tasks"] == 15
    assert result["summary"]["failed_tasks"] == 0
    assert result["summary"]["admitted_population"] == 45
    assert result["summary"]["unresolved_population"] == 45
    assert result["cost_accounting"]["known_expansion_optimize_wall_seconds"] == 80
    assert result["cost_accounting"]["pre_pilot_and_other_attempts_cumulative_seconds"] is None
    assert not result["decision"]["all_planned_tasks_valid"]
    assert not result["eligibility"]["dataset_eligible"]
    for descriptor in result["outputs"].values(): m.c.checked(out, descriptor)
    with pytest.raises(FileExistsError): m.audit(data, folder, root, out, 0)


def test_missing_selected_tasks_and_no_receipt_are_not_certified(prepared):
    data, folder, root, plan, _ = prepared
    task = m.select_task(plan, "medium", 0)
    m.c.safe_path(root, task["run_relative_path"]).mkdir(parents=True)
    result = m.audit(data, folder, root, data / "analysis/gurobi_expansion_campaign/missing", 0)
    assert result["gate_status"] == "failed"
    assert result["summary"]["incomplete_tasks"] == 1 and result["summary"]["not_started_tasks"] == 20
    assert result["summary"]["admitted_population"] == 40


@pytest.mark.parametrize("phase,index", [("medium", -1), ("medium", 20), ("hard", 1), ("scip", 0)])
def test_out_of_scope_tasks_rejected(prepared, phase, index):
    data, folder, root, _, _ = prepared
    with pytest.raises(ValueError): m.execute(data, folder, root, phase, index)


def test_resigned_tampered_batch_or_budget_is_rejected(prepared):
    _, folder, _, plan, _ = prepared
    plan["tasks"][0]["time_limit_seconds"] = 57600
    plan["contract_sha256"] = m.c.canonical_sha256({k: v for k, v in plan.items() if k != "contract_sha256"})
    m.c.write_json(folder / m.PLAN, plan)
    with pytest.raises(ValueError, match="budget"): m.load_plan(folder)


def test_failed_receipt_cannot_claim_label_admission(prepared, monkeypatch):
    data, folder, root, plan, _ = prepared
    flexible_solver(monkeypatch, wrong_budget=True)
    result = m.execute(data, folder, root, "medium", 0)
    task = m.select_task(plan, "medium", 0)
    result["label_eligible"] = True
    result.pop("receipt_sha256")
    directory = m.c.safe_path(root, task["run_relative_path"])
    m.c.write_json(directory / m.TASK_REPORT, m.pilot.seal(result))
    with pytest.raises(ValueError, match="cannot admit"):
        m.verify_receipt(directory, plan, task)


def test_launchers_have_separate_wall_budgets_lf_and_no_gpu():
    scripts = m.pilot.PROJECT_ROOT / "scripts/slurm/dasci"
    expected = {"submit_gurobi_medium_batch.sbs": "12:00:00",
                "submit_gurobi_hard_16h.sbs": "24:00:00",
                "submit_gurobi_expansion_batch_audit.sbs": "00:30:00"}
    for name, limit in expected.items():
        raw = (scripts / name).read_bytes()
        assert b"\r" not in raw and limit.encode() in raw
        assert b"SLURM_SUBMIT_DIR" in raw and b"--gres" not in raw
        if "audit" not in name: assert b"--mem=64G" in raw and b"--cpus-per-task=1" in raw
    raw = (scripts / "run_gurobi_expansion_campaign.sh").read_bytes()
    assert b"\r" not in raw and b"GRB_LICENSE_FILE" in raw
