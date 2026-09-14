"""Unlicensed regression tests for immutable expansion and outcome semantics."""
import gzip
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from scipy.sparse import csr_matrix

from cfl_gnn.pipelines import gurobi_expansion as g


def zipped(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream)


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    data = tmp_path / "data"
    source, rev = data / "analysis/old_campaign", data / "analysis/old_revision"
    approved = {"contract_sha256": "approved"}
    g.c.write_json(rev / g.revision.NAME, approved)
    rows = []
    for e in g.build_planned_manifest():
        path = data / f"raw/MILPBench/CFL/{e.category}/LP/{e.source_instance_id}.lp.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(e.source_instance_id.encode())
        if e.source_instance_id not in g.revision.COHORT:
            continue
        solution = source / e.source_instance_id / "solution.json.gz"
        report = source / e.source_instance_id / "report.json"
        mip = g.c.descriptor(data, path)
        zipped(solution, {"source_instance_id": e.source_instance_id,
            "source_mip_sha256": mip["sha256"],
            "solution_source": "independently_audited_gurobi_confirmation_label",
            "effective_objective_sense": "MINIMIZE", "mip_gap_relative": 0.,
            "mathematical_audit": {"valid": True}})
        g.c.write_json(report, {"label_eligible": True})
        rows.append({"source_instance_id": e.source_instance_id, "mip": mip,
                     "solution": g.c.descriptor(source, solution), "report": g.c.descriptor(source, report)})
    monkeypatch.setattr(g.revision, "load", lambda *a: (approved, {}, {}, rows))
    plan_dir = data / "analysis/gurobi_expansion/pilot_plan"
    run_root = data / "intermediate/gurobi_expansion/pilot"
    plan = g.prepare(data, source, rev, plan_dir)
    return data, plan_dir, run_root, plan


def test_inventory_preserves_39_plans_only_two_and_records_51(campaign):
    data, folder, _, plan = campaign
    assert len(plan["inventory"]) == 90
    assert len(plan["preserved"]) == 39
    assert sum(r["disposition"] == "pending" for r in plan["inventory"]) == 51
    assert [t["source_instance_id"] for t in plan["tasks"]] == list(g.PILOT)
    assert plan["time_limit_seconds"] == 28800 and plan["seed"] == 42
    assert plan["objective_sense"] == "MINIMIZE" and plan["solver"] == "gurobi"
    assert str(data) not in (folder / g.PLAN).read_text()
    assert g.load_plan(folder) == plan


def test_changed_preserved_artifact_blocks_work(campaign):
    data, folder, root, plan = campaign
    g.c.safe_path(data, plan["preserved"][0]["solution"]["relative_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        g.execute(data, folder, root, 0)
    assert not root.exists()


def test_plan_hash_and_implementation_changes_rejected(campaign, monkeypatch):
    _, folder, _, plan = campaign
    monkeypatch.setattr(g, "implementations", lambda: {})
    with pytest.raises(ValueError, match="implementation"):
        g.load_plan(folder)
    plan["time_limit_seconds"] = 14400
    g.c.write_json(folder / g.PLAN, plan)
    with pytest.raises(ValueError):
        g.load_plan(folder)


@pytest.mark.parametrize("bad", ["../raw", "/tmp/out", "C:\\out"])
def test_safe_paths_reject_escape(tmp_path, bad):
    with pytest.raises(ValueError):
        g.c.safe_path(tmp_path, bad)


def test_output_may_not_touch_old_data(campaign):
    data, folder, _, _ = campaign
    with pytest.raises(ValueError, match="dedicated"):
        g.execute(data, folder, data / "raw/MILPBench/CFL", 0)


class Model:
    NumQConstrs = NumGenConstrs = NumQNZs = 0
    ObjCon = 0.
    def __init__(self):
        self.ModelSense = -1
    def getVars(self): return [SimpleNamespace(VarName="x", VType="B", LB=0., UB=1., Obj=2.)]
    def getConstrs(self): return [SimpleNamespace(Sense=">", RHS=1.)]
    def getA(self): return csr_matrix([[1.]])
    def update(self): assert self.ModelSense == 1
    def __enter__(self): return self
    def __exit__(self, *args): pass


class Env:
    def __init__(self, **kwargs): pass
    def setParam(self, *args): pass
    def start(self): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


def mock_solver(monkeypatch, gap=0., status="optimal", value=1.):
    monkeypatch.setitem(sys.modules, "gurobipy", SimpleNamespace(
        Env=Env, read=lambda *a, **k: Model(), GRB=SimpleNamespace(MINIMIZE=1)))
    calls = []
    def run(solve):
        calls.append(solve)
        request = g.parent.worker_request(solve)
        assert request["time_limit"] == 28800 and request["force_minimize"] is True
        assert request["seed"] == 42 and request["threads"] == 1
        payload = {"candidate_sha256": solve.parent_sha256,
            "contract_sha256": solve.contract_sha256,
            "solution_source": "independent_gurobi_optimization",
            "solver_feasibility_check_space": "original_model_solution_quality",
            "fresh_process": True, "warm_start_supplied": False, "pre_solve_solution_count": 0,
            "objective_sense": "minimize", "original_objective_sense": "maximize",
            "solver_feasibility_check": True, "solution_count": 1,
            "solution_objective": 2., "best_bound": 2 * (1-gap), "mip_gap_relative": gap,
            "execution_time_seconds": 10., "solve_status": status,
            "variables": [{"name": "x", "value": value}],
            "runtime_environment": dict(hostname="test", platform="test", machine="test", logical_cpu_count=1),
            "solver_versions": {"gurobi": "test"},
            "solver_parameter_map": {"TimeLimit": 28800, "NodeLimit": 1000000, "Threads": 1, "Seed": 42, "ModelSense": 1},
            "time_regions": dict(zip(g.REGIONS, [13., 1., 1., 10.])),
            "online_incumbent_capture": {"events_recorded": 1, "vectors_streamed": 1,
                                         "capture_error_count": 0, "stream_committed": True},
            "incumbent_trace_audit": {"incumbent_trace_consistent": True}}
        payload["solver_parameter_sha256"] = g.c.canonical_sha256(payload["solver_parameter_map"])
        zipped(solve.output_dir / g.parent.SOLUTION_NAME, payload)
        for name in (g.parent.INCUMBENTS_NAME, g.parent.VARIABLE_ORDER_NAME):
            (solve.output_dir / name).write_bytes(b"mock artifact")
        return g.parent.evaluate_solution(solve, payload)
    monkeypatch.setattr(g.parent, "run", run)
    return calls


@pytest.mark.parametrize("gap,admitted", [(0., True), (.1, True), (.10001, False), (.3, False)])
def test_valid_time_limit_is_not_technical_failure_and_resume_never_resolves(campaign, monkeypatch, gap, admitted):
    data, folder, root, _ = campaign
    calls = mock_solver(monkeypatch, gap=gap, status="timelimit")
    result = g.execute(data, folder, root, 0)
    assert result["execution_valid"] is True and result["right_censored"] is True
    assert result["label_eligible"] is admitted
    assert result["mathematical_audit"]["valid"] is True
    assert result["historical_cumulative_runtime_seconds"] is None
    assert g.execute(data, folder, root, 0) == result
    assert len(calls) == 1


def test_invalid_vector_rejected_despite_zero_gap(campaign, monkeypatch):
    data, folder, root, _ = campaign
    mock_solver(monkeypatch, value=0.)
    result = g.execute(data, folder, root, 0)
    assert result["execution_valid"] is False and result["label_eligible"] is False
    with pytest.raises(ValueError, match="failed attempt"):
        g.execute(data, folder, root, 0)


def test_no_incumbent_is_not_an_infeasibility_claim():
    skipped = ("feasible_solution", "online_incumbent_observed", "trace_consistent",
               "named_solution_present", "terminal_gap_finite")
    report = {"checks": {**{k: False for k in skipped}, "parent_sha256_match": True,
                         "callback_errors_absent": True}}
    result = g.classify(report, {"solution_count": 0, "solve_status": "timelimit", "variables": []}, {})
    assert result["execution_valid"] is True and result["label_eligible"] is False
    assert result["reason_code"] == "no_feasible_solution_observed"
    report["checks"]["callback_errors_absent"] = False
    assert g.classify(report, {"solution_count": 0, "solve_status": "timelimit"}, {})["execution_valid"] is False


def test_partial_directory_and_artifact_corruption_never_overwritten(campaign, monkeypatch):
    data, folder, root, plan = campaign
    calls = mock_solver(monkeypatch)
    output = g.c.safe_path(root, plan["tasks"][0]["run_relative_path"])
    output.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        g.execute(data, folder, root, 0)
    assert calls == []
    g.execute(data, folder, root, 1)
    output = g.c.safe_path(root, plan["tasks"][1]["run_relative_path"])
    (output / g.parent.INCUMBENTS_NAME).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="changed"):
        g.execute(data, folder, root, 1)
    assert len(calls) == 1


def test_error_receipt_sanitized_and_retained(campaign, monkeypatch):
    data, folder, root, _ = campaign
    def fail(*args): raise RuntimeError("/home/user/secrets/gurobi.lic sensitive text")
    monkeypatch.setattr(g.parent, "run", fail)
    result = g.execute(data, folder, root, 0)
    assert result["error_type"] == "RuntimeError" and result["execution_valid"] is False
    assert "/home" not in json.dumps(result) and "sensitive" not in json.dumps(result)


def test_aggregate_and_hash_gates(campaign, monkeypatch):
    data, folder, root, _ = campaign
    mock_solver(monkeypatch, gap=.2, status="timelimit")
    for i in (0, 1): g.execute(data, folder, root, i)
    output = data / "analysis/gurobi_expansion/audit"
    result = g.audit(data, folder, root, output)
    assert result["gate_status"] == "passed"
    assert result["summary"]["new_labels_admitted"] == 0
    assert result["summary"]["unresolved_population"] == 51
    assert result["summary"]["right_censored_tasks"] == 2
    assert result["eligibility"]["dataset_eligible"] is False
    for artifact in result["outputs"].values(): g.c.checked(output, artifact)
    with pytest.raises(FileExistsError): g.audit(data, folder, root, output)


def test_missing_receipts_fail_audit(campaign):
    data, folder, root, _ = campaign
    result = g.audit(data, folder, root, data / "analysis/gurobi_expansion/missing_audit")
    assert result["gate_status"] == "failed"
    assert result["summary"]["failed_or_missing_tasks"] == 2


def test_launchers_use_lf_no_gpu_no_scip_and_correct_budget():
    root = g.PROJECT_ROOT / "scripts/slurm/dasci"
    for name in ("submit_gurobi_expansion_pilot.sbs", "submit_gurobi_expansion_audit.sbs"):
        payload = (root / name).read_bytes()
        assert b"\r" not in payload
        assert b"SLURM_SUBMIT_DIR" in payload and b"dirname" not in payload
        assert b"--gres" not in payload and b"qos1" not in payload
        assert b"collect_scip" not in payload
    payload = (root / "submit_gurobi_expansion_pilot.sbs").read_text()
    assert "12:00:00" in payload and "GRB_LICENSE_FILE" in payload and "--mem=64G" in payload
