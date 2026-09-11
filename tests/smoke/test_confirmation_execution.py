"""Frozen-cohort recovery: provenance, independent feasibility and bounded repair."""
import gzip
import json
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from cfl_gnn.artifacts.schemas import ModelFeatures, VariableFeatures, ConstraintFeatures
from cfl_gnn.pipelines import confirmation_execution as c


class Model:
    NumQConstrs = NumGenConstrs = NumQNZs = 0
    ObjCon = 0.
    def __init__(self):
        self.ModelSense = -1
        self.var = SimpleNamespace(VarName="x", VType="B", LB=0., UB=1., Obj=2.)
        self.row = SimpleNamespace(Sense=">", RHS=1.)
    def getVars(self): return [self.var]
    def getConstrs(self): return [self.row]
    def getA(self): return csr_matrix([[1.]])
    def update(self): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


class Env:
    def __init__(self, **kwargs): pass
    def setParam(self, *args): pass
    def start(self): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def compressed(path, value, binary=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        with gzip.open(path, "wb") as stream: pickle.dump(value, stream)
    else:
        with gzip.open(path, "wt", encoding="utf-8") as stream: json.dump(value, stream)


def raw_features():
    return {"model_features": ModelFeatures(1, 1, 1, 0, 0, 1, 0.),
            "variable_features": VariableFeatures(np.array(["B"]), np.array([0.], dtype=np.float32),
                np.array([1.], dtype=np.float32), np.array([2.], dtype=np.float32)),
            "constraint_features": ConstraintFeatures(np.array([">"]), np.array([1.], dtype=np.float32), np.array([1.])),
            "edge_indices": np.array([[0], [0]]), "edge_features": np.array([1.], dtype=np.float32)}


def legacy(tmp_path):
    identity = c.COHORT[0]
    files = {}
    compressed(tmp_path / "original_features.pickle.gz", raw_features(), binary=True)
    compressed(tmp_path / "solutions.pickle.gz", {"solution_pool": [{"objective": 2., "solution_vector": [1.]}]}, binary=True)
    write(tmp_path / "metadata.json", {"instance": identity, "objective_sense_override": "MINIMIZE",
                                       "mip_gap": 0., "best_objective": 2., "runtime": 10.})
    for name in ("original_features.pickle.gz", "solutions.pickle.gz", "metadata.json"):
        files[name] = c.descriptor(tmp_path, tmp_path / name)
    sidecar = {"structure_provenance": {"feature_artifact_sha256": files["original_features.pickle.gz"]["sha256"]},
               "collection_provenance": {"artifact_sha256": files["metadata.json"]["sha256"]},
               "label_provenance": {"artifact": "solutions.pickle.gz", "source_index": 0, "objective": 2., "mip_gap": 0.,
                                    "artifact_sha256": files["solutions.pickle.gz"]["sha256"]}}
    write(tmp_path / "graph.provenance.json", sidecar)
    return {"source_instance_id": identity, "legacy_files": files, "provenance": c.descriptor(tmp_path, tmp_path / "graph.provenance.json")}


def named(tmp_path, *, value=1., gap=0., bound=2., identity=None):
    identity = identity or c.COHORT[0]
    payload = {"solution_source": "independent_gurobi_optimization", "effective_objective_sense": "minimize",
               "mip_gap_relative": gap, "best_bound": bound, "execution_time_seconds": 10.,
               "solution_objective": 2., "variables": [{"name": "x", "value": value}]}
    path = tmp_path / "parent_solution.json.gz"
    compressed(path, payload)
    report = {"parent": {"source_instance_id": identity, "sha256": "mip"},
              "gate_status": "passed", "eligibility": {"label_eligible": True},
              "artifacts": {"solution": {"file_name": path.name, "sha256": c.sha256_file(path)}}}
    write(tmp_path / "gurobi_parent_solve_report.json", report)
    return c.descriptor(tmp_path, tmp_path / "gurobi_parent_solve_report.json")


@pytest.mark.parametrize("relative", ["../escape", "/absolute", "C:/outside", "a\\b", ""])
def test_paths_cannot_escape(tmp_path, relative):
    with pytest.raises(ValueError): c.safe_path(tmp_path, relative)


@pytest.mark.parametrize("gap", [None, float("nan"), float("inf"), -.1, .10001, True])
def test_admission_never_relaxes_ten_percent(gap):
    assert not c.eligible_gap(gap)


def test_legacy_full_precision_label_is_independently_validated(tmp_path):
    task = legacy(tmp_path)
    result = c.legacy_candidate(Model(), tmp_path, task)
    assert result["named"] == {"x": 1.}
    assert result["audit"]["valid"]
    assert result["time_regions"] is None
    assert result["execution_time_seconds"] == 10.
    assert result["time_semantics"] == "terminal_legacy_runtime_not_incumbent_epoch"


def test_legacy_structure_cannot_be_inferred_from_vector_length():
    raw = raw_features()
    raw["edge_features"][0] = 2
    assert not c.legacy_order_matches(Model(), raw)


def test_pool_member_cannot_inherit_best_pool_gap(tmp_path):
    task = legacy(tmp_path)
    compressed(tmp_path / "solutions.pickle.gz", {"solution_pool": [{"objective": 3., "solution_vector": [1.]}]}, binary=True)
    task["legacy_files"]["solutions.pickle.gz"] = c.descriptor(tmp_path, tmp_path / "solutions.pickle.gz")
    sidecar = c.read_json(tmp_path / "graph.provenance.json")
    sidecar["label_provenance"]["artifact_sha256"] = task["legacy_files"]["solutions.pickle.gz"]["sha256"]
    write(tmp_path / "graph.provenance.json", sidecar)
    task["provenance"] = c.descriptor(tmp_path, tmp_path / "graph.provenance.json")
    with pytest.raises(ValueError, match="cannot inherit"):
        c.legacy_candidate(Model(), tmp_path, task)


def test_named_label_requires_original_parent_identity(tmp_path):
    source = named(tmp_path, identity="CFL_easy_instance_28")
    with pytest.raises(ValueError, match="parent identity"):
        c.named_candidate(Model(), tmp_path, {"source_instance_id": c.COHORT[0], "mip": {"sha256": "mip"}}, source)


def test_named_feasible_gap_and_bound_verified(tmp_path):
    source = named(tmp_path)
    task = {"source_instance_id": c.COHORT[0], "mip": {"sha256": "mip"}}
    assert c.named_candidate(Model(), tmp_path, task, source)["audit"]["valid"]
    source = named(tmp_path, value=0.)
    with pytest.raises(ValueError, match="mathematical"):
        c.named_candidate(Model(), tmp_path, task, source)
    source = named(tmp_path, bound=1.)
    with pytest.raises(ValueError, match="inconsistent"):
        c.named_candidate(Model(), tmp_path, task, source)


def test_high_gap_does_not_require_deserializing_bad_variable_vector(tmp_path):
    source = named(tmp_path, gap=.8, value=None)
    task = {"source_instance_id": c.COHORT[0], "mip": {"sha256": "mip"}}
    assert c.named_candidate(Model(), tmp_path, task, source) is None


def execution_plan(tmp_path, monkeypatch):
    task = legacy(tmp_path)
    for name in ("mip.lp.gz", "graph.pt"):
        (tmp_path / name).write_bytes(b"source")
    task.update(task_index=0, mip=c.descriptor(tmp_path, tmp_path / "mip.lp.gz"),
                graph=c.descriptor(tmp_path, tmp_path / "graph.pt"), fold=0, role="test",
                existing_parent_reports=[])
    tasks = [{**task, "source_instance_id": identity, "task_index": i} for i, identity in enumerate(c.COHORT)]
    plan = {"tasks": tasks, "objective_sense": "MINIMIZE", "seed": 42, "epochs": 100,
            "maximum_label_mip_gap_relative": .1, "repair_budgets_seconds": [3600, 14400],
            "implementation_sha256": c.implementation_hashes()}
    plan["contract_sha256"] = c.canonical_sha256(plan)
    write(tmp_path / "campaign" / c.PLAN, plan)
    model = Model()
    monkeypatch.setitem(sys.modules, "gurobipy", SimpleNamespace(Env=Env, read=lambda *a, **k: model, GRB=SimpleNamespace(MINIMIZE=1)))
    return plan, model


def test_reuse_and_resume_do_not_optimize_or_mutate_historical_files(tmp_path, monkeypatch):
    plan, model = execution_plan(tmp_path, monkeypatch)
    before = {p.name: c.sha256_file(p) for p in tmp_path.iterdir() if p.is_file()}
    result = c.execute(campaign_dir=tmp_path / "campaign", data_root=tmp_path, task_index=0, repair=True)
    assert result["label_eligible"] and not result["training_ready"]
    assert result["repair_outcomes"] == []
    assert model.ModelSense == 1
    again = c.execute(campaign_dir=tmp_path / "campaign", data_root=tmp_path, task_index=0, repair=True)
    assert again == result
    assert before == {p.name: c.sha256_file(p) for p in tmp_path.iterdir() if p.is_file()}
    report = c.aggregate(tmp_path / "campaign")
    assert report["independently_admissible_parents"] == 1
    assert not report["training_ready"] and report["gate_status"] == "incomplete"


def test_changed_solution_hash_blocks_resume(tmp_path, monkeypatch):
    execution_plan(tmp_path, monkeypatch)
    c.execute(campaign_dir=tmp_path / "campaign", data_root=tmp_path, task_index=0)
    path = tmp_path / "campaign/labels" / c.COHORT[0] / "confirmation_solution.json.gz"
    path.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="changed"):
        c.execute(campaign_dir=tmp_path / "campaign", data_root=tmp_path, task_index=0)
    assert c.aggregate(tmp_path / "campaign")["independently_admissible_parents"] == 0


def test_cannot_reseal_a_larger_gap_ceiling(tmp_path, monkeypatch):
    plan, _ = execution_plan(tmp_path, monkeypatch)
    plan["maximum_label_mip_gap_relative"] = .9
    plan["contract_sha256"] = c.canonical_sha256({k: v for k, v in plan.items() if k != "contract_sha256"})
    with pytest.raises(ValueError, match="admission policy"):
        c.validate_plan(plan)


def test_invalid_sources_are_reported_without_false_training_readiness(tmp_path, monkeypatch):
    execution_plan(tmp_path, monkeypatch)
    monkeypatch.setattr(c, "legacy_candidate", lambda *a: None)
    result = c.execute(campaign_dir=tmp_path / "campaign", data_root=tmp_path, task_index=0)
    assert result["gate_status"] == "inconclusive" and not result["label_eligible"]


def test_repair_only_escalates_after_inadmissible_first_budget(tmp_path, monkeypatch):
    plan, _ = execution_plan(tmp_path, monkeypatch)
    campaign = tmp_path / "campaign"
    monkeypatch.setattr(c, "legacy_candidate", lambda *a: None)
    calls = []
    from cfl_gnn.pipelines import parent_collection_task
    for budget in (3600, 14400):
        write(campaign / f"repair_{budget}s/parent_collection_plan.json", {"tasks": [{"solver": "gurobi",
            "solver_task_index": 0, "source_instance_id": c.COHORT[0], "run_dir_relative_path": str(budget)}]})
    plan["repair_plans"] = {str(b): c.descriptor(campaign, campaign / f"repair_{b}s/parent_collection_plan.json") for b in (3600, 14400)}
    plan["contract_sha256"] = c.canonical_sha256({k: v for k, v in plan.items() if k != "contract_sha256"})
    write(campaign / c.PLAN, plan)
    def solve(**kwargs):
        budget = int(kwargs["plan_dir"].name.split("_")[1][:-1])
        calls.append(budget)
        root = kwargs["run_root"] / str(budget)
        named(root, gap=.8 if budget == 3600 else 0.)
        report = c.read_json(root / "gurobi_parent_solve_report.json")
        report["parent"]["sha256"] = plan["tasks"][0]["mip"]["sha256"]
        write(root / "gurobi_parent_solve_report.json", report)
    monkeypatch.setattr(parent_collection_task, "execute_parent_collection_task", solve)
    result = c.execute(campaign_dir=campaign, data_root=tmp_path, task_index=0, repair=True)
    assert calls == [3600, 14400]
    assert result["label_eligible"]
    assert result["selected"]["source_root_alias"] == "campaign"
    assert result["repair_outcomes"][0]["label_eligible"] is False
    assert result["repair_outcomes"][1]["label_eligible"] is True


def test_launchers_are_lf_only_and_preserve_submit_directory():
    root = Path(__file__).resolve().parents[2]
    for name in ("submit_confirmation_sources.sbs", "submit_confirmation_sources_audit.sbs", "launch_confirmation_execution.sh"):
        content = (root / "scripts/slurm/dasci" / name).read_bytes()
        assert b"\r" not in content
        assert b"SLURM_SUBMIT_DIR" in content or b'EXEC_DIR="$PWD"' in content
        assert b"dirname" not in content


def test_prepare_freezes_exact_42_and_both_budgets_without_solving(tmp_path):
    from cfl_gnn.pipelines.confirmation_campaign import audit_confirmation
    from cfl_gnn.pipelines.parent_collection_task import validate_campaign_plan
    root = Path(__file__).resolve().parents[2]
    graphs = tmp_path / "bipartite_graphs/instance_baseline_smoke"
    for identity in c.COHORT:
        category = identity.rsplit("_", 1)[0]
        mip = tmp_path / "raw/MILPBench/CFL" / category / "LP" / f"{identity}.lp.gz"
        mip.parent.mkdir(parents=True, exist_ok=True)
        mip.write_bytes(b"never_solved")
        graph = graphs / category / "processed" / f"{identity}.pt"
        graph.parent.mkdir(parents=True, exist_ok=True)
        graph.write_bytes(b"never_deserialized")
        write(graph.with_suffix(".provenance.json"), {
            "graph_sha256": c.sha256_file(graph),
            "structure_provenance": {"raw_instance_sha256": c.sha256_file(mip)},
            "label_provenance": {"mip_gap": .5 if "medium" in identity else 0.},
            "context_provenance": {"mode": "root_node_relaxation"}})
    audit_confirmation(graph_dir=graphs, parent_manifest=root / "configs/splits/cfl_90_seed42_folds.csv", output_dir=tmp_path / "inventory")
    campaign = tmp_path / "campaign"
    plan = c.prepare(inventory_path=tmp_path / "inventory/confirmation_inventory.json", data_root=tmp_path, output_dir=campaign)
    c.validate_plan(plan)
    assert [t["source_instance_id"] for t in plan["tasks"]] == list(c.COHORT)
    assert sum(t["role"] == "train" for t in plan["tasks"]) == 24
    assert sum(t["role"] == "validation" for t in plan["tasks"]) == 10
    assert sum(t["role"] == "test" for t in plan["tasks"]) == 8
    assert str(tmp_path) not in json.dumps(plan)
    for budget in (3600, 14400):
        repair = c.read_json(campaign / f"repair_{budget}s/parent_collection_plan.json")
        validate_campaign_plan(repair)
        assert repair["available_parent_population"] == 42
        assert repair["solve_budget"]["time_limit_seconds"] == budget
    assert not (campaign / "repair_runs").exists()
    with pytest.raises(ValueError, match="new campaign"):
        c.prepare(inventory_path=tmp_path / "inventory/confirmation_inventory.json", data_root=tmp_path, output_dir=campaign)


def test_native_gurobi_legacy_label_validation(tmp_path):
    import os
    gp = pytest.importorskip("gurobipy")
    try:
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()
    except gp.GurobiError:
        if os.environ.get("CFL_REQUIRE_SOLVER_TESTS") == "1":
            pytest.fail("Gurobi license is required by the DGX validation gate")
        pytest.skip("Gurobi license unavailable locally; required on DGX")
    with env, gp.Model(env=env) as model:
        x = model.addVar(vtype=gp.GRB.BINARY, name="x", obj=2.)
        model.addConstr(x >= 1.)
        model.ModelSense = gp.GRB.MINIMIZE
        model.update()
        result = c.legacy_candidate(model, tmp_path, legacy(tmp_path))
        assert result["audit"]["valid"]
        assert model.SolCount == 0  # Audit, not a hidden optimize call.
