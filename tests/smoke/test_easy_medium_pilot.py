"""Fail-closed pilot provenance, ranking, audit and diagnostic tests."""
import copy
import json
from pathlib import Path

import pytest

from cfl_gnn.pipelines import easy_medium_pilot as p
from cfl_gnn.graph.label_free_gurobi import prediction_rows
from cfl_gnn.solvers.paired_partial_start import start_evidence


@pytest.fixture
def training(tmp_path):
    root = tmp_path / "training"
    root.mkdir()
    records = [dict(source_instance_id=e.source_instance_id, difficulty="easy", role=p.role_for_fold(e.fold, 0))
               for e in p.read_manifest(p.PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv") if e.difficulty == "easy"]
    protocol = p.read_json(p.PROJECT_ROOT / "configs/training/gasse_easy_transfer_v1.json")
    plan = dict(dataset_variant="easy_only_medium_transfer_v1", records=records, protocol=protocol,
                legacy_gasse_git_blob_sha1=p.git_blob_sha1(p.PROJECT_ROOT / "src/cfl_gnn/models/gasse.py"),
                implementation_sha256={n:p.sha256_file(p.PROJECT_ROOT / "src/cfl_gnn" / n) for n in ("models/gasse_calibrated.py", "models/versioning.py")},
                partition_counts=dict(train=18, validation=6, test=6), medium_records_in_training_plan=0,
                initialization="fresh_seed42_no_pretrained_checkpoint", normalization_scope="easy_training_only", objective_sense="MINIMIZE",
                root_lp_policy="first_optimal_root_gurobi_mipnode_no_zero_fallback")
    plan["contract_sha256"] = p.canonical_sha256(plan)
    p.write_json(root / "gasse_training_plan.json", plan)
    (root / "best_model.pt").write_bytes(b"test-checkpoint-not-a-real-model")
    (root / "training_validation_loss.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (root / "training_epoch_metrics.csv").write_text("epoch,train_loss,validation_loss\n" + "".join(f"{i},0.1,0.2\n" for i in range(1, 101)))
    report = dict(gate_status="passed", epochs_completed=100, test_graphs_loaded=0, model_version="gasse_v2_alternating_prenorm",
                  checkpoint_selection="minimum_validation_weighted_bce", threshold_source="maximum_validation_f1",
                  training_contract_sha256=plan["contract_sha256"], selected_probability_threshold=.9975,
                  outputs={key: dict(file_name=name, sha256=p.sha256_file(root / name)) for key, name in (
                      ("checkpoint", "best_model.pt"), ("training_epoch_metrics.csv", "training_epoch_metrics.csv"),
                      ("training_validation_loss.svg", "training_validation_loss.svg"))})
    p.write_json(root / "gasse_training_report.json", report)
    wrapper = dict(gate_status="passed", medium_graphs_loaded=0, test_graphs_loaded=0, epochs_completed=100,
                   training_contract_sha256=plan["contract_sha256"], training_report_sha256=p.sha256_file(root / "gasse_training_report.json"))
    p.write_json(root / "easy_transfer_training_report.json", wrapper)
    return root


@pytest.fixture
def inputs(training, tmp_path):
    mip_root = tmp_path / "raw"
    for name in p.PARENTS:
        path = mip_root / "CFL_medium_instance/LP" / f"{name}.lp.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    return training, mip_root


def test_plan_pins_complete_source_without_target_labels(inputs):
    plan = p.build_plan(*inputs)
    p.validate_plan(plan)
    assert len(plan["targets"]) == 2
    assert plan["targets"][0]["method_order"] == list(p.METHODS)
    assert plan["targets"][1]["method_order"] == list(reversed(p.METHODS))
    assert plan["threshold"] == .9975
    assert not plan["target_labels_loaded"]
    text = json.dumps(plan)
    assert str(inputs[0]) not in text and str(inputs[1]) not in text


@pytest.mark.parametrize("name", ["best_model.pt", "training_epoch_metrics.csv", "training_validation_loss.svg", "gasse_training_report.json"])
def test_changed_training_artifact_rejected(training, name):
    with (training / name).open("a") as stream:
        stream.write("changed")
    with pytest.raises((ValueError, KeyError)):
        p.load_training(training)


def test_changed_architecture_source_rejected(training, monkeypatch):
    monkeypatch.setattr(p, "git_blob_sha1", lambda _: "changed")
    with pytest.raises(ValueError, match="architecture"):
        p.load_training(training)


@pytest.mark.parametrize("key,value", [("dataset_variant", "approved_39_parent_development_v1"),
    ("normalization_scope", "all_graphs"), ("objective_sense", "MAXIMIZE"), ("medium_records_in_training_plan", 1)])
def test_wrong_training_provenance_rejected(training, key, value):
    path = training / "gasse_training_plan.json"
    plan = p.read_json(path)
    plan[key] = value
    plan["contract_sha256"] = p.canonical_sha256({k:v for k,v in plan.items() if k != "contract_sha256"})
    p.write_json(path, plan)
    with pytest.raises(ValueError):
        p.load_training(training)


def test_missing_target_is_not_silently_dropped(inputs):
    training, root = inputs
    (root / "CFL_medium_instance/LP/CFL_medium_instance_0.lp.gz").unlink()
    with pytest.raises(ValueError, match="missing"):
        p.build_plan(training, root)


def test_plan_mutation_and_implementation_change_rejected(inputs, monkeypatch):
    plan = p.build_plan(*inputs)
    modified = copy.deepcopy(plan)
    modified["threshold"] = .5
    with pytest.raises(ValueError):
        p.validate_plan(modified)
    monkeypatch.setattr(p, "implementation_hashes", lambda: {})
    with pytest.raises(ValueError):
        p.validate_plan(plan)


def test_partial_output_cannot_be_overwritten(inputs, tmp_path):
    plan_dir, runs = tmp_path / "plan", tmp_path / "runs"
    plan_dir.mkdir()
    p.write_json(plan_dir / p.PLAN, p.build_plan(*inputs))
    (runs / p.PARENTS[0]).mkdir(parents=True)
    with pytest.raises(FileExistsError):
        p.run_pair(plan_dir, *inputs, runs, 0, "cpu")


def test_failed_or_missing_pairs_keep_denominator(inputs, tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    p.write_json(plan_dir / p.PLAN, p.build_plan(*inputs))
    report = p.audit(plan_dir, tmp_path / "missing", tmp_path / "audit")
    assert report["gate_status"] == "failed"
    assert report["summary"] == dict(planned_parents=2, planned_method_runs=4, valid_pairs=0, valid_method_runs=0)
    assert len(report["failures"]) == 2


def test_prediction_threshold_and_deterministic_coverage():
    from cfl_gnn.experiments.neural_guidance_policy import guidance_directives
    rows = prediction_rows([f"x{i:02}" for i in range(20)], [.99]*20, .9975)
    assert all(r["predicted_value"] == 0 for r in rows)
    assert guidance_directives(list(reversed(rows)), method="partial_mip_start", fraction=.1)["assignments"] == guidance_directives(rows, method="partial_mip_start", fraction=.1)["assignments"]
    assert len(guidance_directives(rows, method="partial_mip_start", fraction=.1)["assignments"]) == 2


@pytest.mark.parametrize("names,values,threshold", [(["x", "x"], [.5,.5], .5), (["x"], [], .5),
    (["x"], [float("nan")], .5), (["x"], [1.1], .5), (["x"], [.5], float("nan"))])
def test_bad_predictions_rejected(names, values, threshold):
    with pytest.raises(ValueError):
        prediction_rows(names, values, threshold)


def test_start_messages_do_not_certify_infeasibility():
    evidence = start_evidence(["User MIP start did not produce a new incumbent solution"], True)
    assert evidence["status"] == "no_new_incumbent" and evidence["completed"] is None
    assert start_evidence([], True)["accepted"] is None
    assert start_evidence(["Loaded user MIP start with objective 1"], True)["accepted"] is True
    assert start_evidence([], False)["status"] == "not_submitted"


def test_censored_comparison_does_not_fabricate_speedup():
    control = {"solve": dict(terminal_mip_gap_relative=.2, solve_status_code=9),
               "timing": dict(model_optimize_wall_time_seconds=3600., total_wall_time_seconds=3602.)}
    guided = copy.deepcopy(control)
    guided["solve"]["terminal_mip_gap_relative"] = .3
    result = p.paired_effect(control, guided, 20.)
    assert result["gap_difference_guided_minus_control"] == pytest.approx(.1)
    assert result["time_to_optimal_speedup"] is None
    assert result["guided_cold_total_seconds"] == 3622.


def test_launchers_are_lf_only_fresh_process_and_bounded_pilot():
    for name in ("submit_easy_medium_pilot.sbs", "submit_easy_medium_pilot_audit.sbs"):
        content = (p.PROJECT_ROOT / "scripts/slurm/dasci" / name).read_bytes()
        assert b"\r" not in content
        assert b"SLURM_SUBMIT_DIR" in content and b"set -euo pipefail" in content
        assert b"--overwrite" not in content and b"sbatch" not in content
    content = (p.PROJECT_ROOT / "scripts/slurm/dasci/submit_easy_medium_pilot.sbs").read_text()
    assert "--array=0-1%1" in content and "--mem=64G" in content


@pytest.fixture
def completed_pilot(inputs, tmp_path):
    plan_dir, runs = tmp_path / "plan", tmp_path / "runs"
    plan_dir.mkdir()
    plan = p.build_plan(*inputs)
    p.write_json(plan_dir / p.PLAN, plan)
    for target in plan["targets"]:
        folder = runs / target["source_instance_id"]
        folder.mkdir(parents=True)
        for name in ("root_features.json.gz", "label_free_graph.pt"):
            (folder / name).write_bytes(b"fixture")
        p.write_gzip(folder / "predictions.json.gz", dict(contract_sha256=plan["contract_sha256"],
            source_instance_id=target["source_instance_id"], mip_sha256=target["mip"]["sha256"],
            checkpoint_sha256=plan["checkpoint"]["sha256"], threshold=plan["threshold"], target_labels_loaded=False,
            binary_order_sha256=p.canonical_sha256(["x"]), predictions=prediction_rows(["x"], [.9], plan["threshold"])))
        p.write_json(folder / "preparation.json", dict(gate_status="passed", contract_sha256=plan["contract_sha256"],
            source_instance_id=target["source_instance_id"], timing=dict(preparation_wall_time_seconds=10.),
            artifacts={n: p.descriptor(folder, folder/n) for n in ("root_features.json.gz", "label_free_graph.pt", "predictions.json.gz")}))
        for method in p.METHODS:
            p.write_json(folder / f"{method}.json", dict(gate_status="passed", contract_sha256=plan["contract_sha256"],
                source_instance_id=target["source_instance_id"], mip_sha256=target["mip"]["sha256"], method=method,
                parameters={"TimeLimit":3600}, solver_version=[13,0,1], mathematical_signature_sha256="same",
                solve=dict(feasible_solution=False, terminal_mip_gap_relative=None, solve_status_code=9),
                start=dict(status="no_new_incumbent" if method == p.METHODS[1] else "not_submitted"),
                timing=dict(total_wall_time_seconds=3604., data_read_wall_time_seconds=1., model_build_wall_time_seconds=1.,
                    model_optimize_wall_time_seconds=3600., independent_audit_wall_time_seconds=1., other_wall_time_seconds=1.)))
        p.write_json(folder / "pair_receipt.json", dict(contract_sha256=plan["contract_sha256"],
            source_instance_id=target["source_instance_id"],
            workers=[dict(method=m, returncode=0, process_wall_time_seconds=3605.) for m in target["method_order"]],
            artifacts={f.name: p.descriptor(folder, f) for f in folder.iterdir()}))
    return plan_dir, runs


def test_integrity_gate_does_not_require_improvement_or_feasible_solution(completed_pilot, tmp_path):
    report = p.audit(*completed_pilot, tmp_path / "audit")
    assert report["gate_status"] == "passed"
    assert report["summary"]["valid_pairs"] == 2 and not report["improvement_required_for_gate"]
    effects = p.read_json(tmp_path / "audit/paired_effects.json")["records"]
    assert all(r["gap_difference_guided_minus_control"] is None for r in effects)
    assert effects[0]["guided_cold_total_seconds"] == 3615.


def test_failed_guidance_retains_control_and_all_denominators(completed_pilot, tmp_path):
    plan_dir, runs = completed_pilot
    folder = runs / p.PARENTS[0]
    method_path = folder / "partial_mip_start.json"
    p.write_json(method_path, dict(gate_status="failed"))
    receipt = p.read_json(folder / "pair_receipt.json")
    receipt["artifacts"][method_path.name] = p.descriptor(folder, method_path)
    p.write_json(folder / "pair_receipt.json", receipt)
    report = p.audit(plan_dir, runs, tmp_path / "audit")
    assert report["gate_status"] == "failed"
    assert report["summary"]["valid_method_runs"] == 3
    assert report["summary"]["valid_pairs"] == 1
    statuses = p.read_json(tmp_path / "audit/per_method_status.json")["records"]
    assert len(statuses) == 4 and sum(s["artifact_valid"] for s in statuses) == 3


def test_prediction_artifact_tampering_fails_closed(completed_pilot, tmp_path):
    (completed_pilot[1] / p.PARENTS[0] / "predictions.json.gz").write_bytes(b"changed")
    report = p.audit(*completed_pilot, tmp_path / "audit")
    assert report["gate_status"] == "failed" and report["summary"]["valid_pairs"] == 1


def test_omitted_method_hash_cannot_pass(completed_pilot, tmp_path):
    folder = completed_pilot[1] / p.PARENTS[0]
    receipt = p.read_json(folder / "pair_receipt.json")
    del receipt["artifacts"]["partial_mip_start.json"]
    p.write_json(folder / "pair_receipt.json", receipt)
    report = p.audit(*completed_pilot, tmp_path / "audit")
    assert report["gate_status"] == "failed" and report["summary"]["valid_method_runs"] == 3


def test_absent_root_callback_still_fails_closed(tmp_path, monkeypatch):
    """Negative control: no event must never become a fabricated root vector."""
    import sys
    from types import SimpleNamespace
    from cfl_gnn.graph.gurobi_graph_artifact import capture_root_relaxation, GurobiGraphError

    class NoRootEventModel:
        ModelSense = -1
        Params = SimpleNamespace()
        disposed = False

        def update(self):
            pass

        def getVars(self):
            return [SimpleNamespace(VarName="x")]

        def optimize(self, observer):
            pass

        def dispose(self):
            self.disposed = True

    model = NoRootEventModel()
    fake = SimpleNamespace(read=lambda _: model, GRB=SimpleNamespace(MINIMIZE=1))
    monkeypatch.setitem(sys.modules, "gurobipy", fake)
    path = tmp_path / "no_root.lp"
    path.write_bytes(b"fixture")
    with pytest.raises(GurobiGraphError, match="no optimal root MIPNODE"):
        capture_root_relaxation(path, expected_mip_sha256=p.sha256_file(path))
    assert model.disposed
