"""Two-parent, label-free easy-to-medium Gurobi partial-start pilot.

Each method runs in a fresh child process. A successful audit certifies paired
execution integrity, not positive effects or scientific generalization.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.confirmation_execution import checked, descriptor, read_json, safe_path, error_reason
from cfl_gnn.pipelines.confirmation_training import validate_training_receipt
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold
from cfl_gnn.training.gasse_reconnected import canonical_sha256, validate_training_plan, write_json, git_blob_sha1

CONFIG = PROJECT_ROOT / "configs/experiments/easy_medium_partial_start_v1.json"
PLAN = "easy_medium_pilot_plan.json"
REPORT = "easy_medium_pilot_report.json"
METHODS = ("unguided_control", "partial_mip_start")
PARENTS = ("CFL_medium_instance_0", "CFL_medium_instance_1")
IMPLEMENTATIONS = (
    "pipelines/easy_medium_pilot.py", "graph/label_free_gurobi.py", "solvers/paired_partial_start.py",
    "solvers/neural_guidance.py", "experiments/neural_guidance_policy.py", "graph/gurobi_graph_artifact.py",
    "graph/build_dataset.py", "models/gasse.py", "models/gasse_calibrated.py", "models/versioning.py",
    "validation/mathematical.py")


def implementation_hashes():
    return {name: sha256_file(PROJECT_ROOT / "src/cfl_gnn" / name) for name in IMPLEMENTATIONS}


def load_training(directory):
    directory = Path(directory)
    plan = read_json(directory / "gasse_training_plan.json")
    report = read_json(directory / "gasse_training_report.json")
    wrapper = read_json(directory / "easy_transfer_training_report.json")
    validate_training_plan(plan)
    validate_training_receipt(report, directory)
    if (plan.get("legacy_gasse_git_blob_sha1") != git_blob_sha1(PROJECT_ROOT / "src/cfl_gnn/models/gasse.py")
            or any(plan.get("implementation_sha256", {}).get(name) != sha256_file(PROJECT_ROOT / "src/cfl_gnn" / name)
                   for name in ("models/gasse_calibrated.py", "models/versioning.py"))):
        raise ValueError("checkpoint architecture implementation changed since training")
    expected = {r.source_instance_id: r for r in read_manifest(PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv") if r.difficulty == "easy"}
    records = plan["records"]
    if (plan.get("dataset_variant") != "easy_only_medium_transfer_v1"
            or len(records) != 30 or {r["source_instance_id"] for r in records} != set(expected)
            or any(r["difficulty"] != "easy" or r["role"] != role_for_fold(expected[r["source_instance_id"]].fold, 0) for r in records)
            or plan.get("partition_counts") != {"train": 18, "validation": 6, "test": 6}
            or plan.get("medium_records_in_training_plan") != 0
            or plan.get("initialization") != "fresh_seed42_no_pretrained_checkpoint"
            or plan.get("normalization_scope") != "easy_training_only"
            or plan.get("objective_sense") != "MINIMIZE"
            or plan.get("root_lp_policy") != "first_optimal_root_gurobi_mipnode_no_zero_fallback"
            or plan["protocol"]["optimization"]["seed"] != 42
            or plan["protocol"]["optimization"]["epochs"] != 100
            or plan["protocol"]["architecture"]["model_version"] != "gasse_v2_alternating_prenorm"):
        raise ValueError("only the complete fresh PR55 easy-only training is admissible")
    if (wrapper.get("gate_status") != "passed" or wrapper.get("medium_graphs_loaded") != 0
            or wrapper.get("test_graphs_loaded") != 0 or wrapper.get("epochs_completed") != 100
            or wrapper.get("training_contract_sha256") != plan["contract_sha256"]
            or report.get("training_contract_sha256") != plan["contract_sha256"]
            or report.get("model_version") != plan["protocol"]["architecture"]["model_version"]
            or wrapper.get("training_report_sha256") != sha256_file(directory / "gasse_training_report.json")):
        raise ValueError("PR55 training report identity mismatch")
    threshold = report["selected_probability_threshold"]
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("invalid validation-selected threshold")
    return plan, report


def build_plan(training_dir, mip_root):
    training_dir, mip_root = Path(training_dir), Path(mip_root)
    training, report = load_training(training_dir)
    policy = read_json(CONFIG)
    if (policy["methods"] != list(METHODS) or policy["pilot_parent_ids"] != list(PARENTS)
            or policy["coverage_fraction"] != .1 or policy["optimization_time_limit_seconds"] != 3600
            or policy["threads_per_run"] != 1 or policy["seed"] != 42
            or policy["root_capture_time_limit_seconds"] != 600
            or policy["target_labels_or_incumbents_allowed_as_input"] is not False
            or policy["binding_interventions_allowed"] is not False):
        raise ValueError("fixed pilot policy changed")
    targets = []
    for i, name in enumerate(PARENTS):
        relative = f"CFL_medium_instance/LP/{name}.lp.gz"
        mip = safe_path(mip_root, relative)
        if not mip.is_file():
            raise ValueError("required medium input is missing")
        targets.append({"task_index": i, "source_instance_id": name, "mip": descriptor(mip_root, mip),
                        "method_order": list(METHODS if i % 2 == 0 else reversed(METHODS))})
    checkpoint = report["outputs"]["checkpoint"]
    payload = dict(schema_version=1, stage="two_medium_engineering_pilot", policy=policy,
        policy_sha256=sha256_file(CONFIG), implementation_sha256=implementation_hashes(),
        training_contract_sha256=training["contract_sha256"],
        training_inputs={name: descriptor(training_dir, training_dir / name) for name in (
            "gasse_training_plan.json", "gasse_training_report.json", "easy_transfer_training_report.json",
            "training_epoch_metrics.csv", "training_validation_loss.svg")},
        checkpoint={"relative_path": checkpoint["file_name"], "sha256": checkpoint["sha256"]},
        architecture=training["protocol"]["architecture"], threshold=report["selected_probability_threshold"],
        targets=targets, target_labels_loaded=False, development_only=True, scientific_reporting_eligible=False)
    return {**payload, "contract_sha256": canonical_sha256(payload)}


def validate_plan(plan):
    payload = {k: v for k, v in plan.items() if k != "contract_sha256"}
    if (canonical_sha256(payload) != plan.get("contract_sha256")
            or plan.get("implementation_sha256") != implementation_hashes()
            or plan.get("policy_sha256") != sha256_file(CONFIG)
            or [t["source_instance_id"] for t in plan["targets"]] != list(PARENTS)):
        raise ValueError("pilot plan or implementation changed")


def load_plan(directory):
    plan = read_json(Path(directory) / PLAN)
    validate_plan(plan)
    return plan


def write_gzip(path, payload):
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, allow_nan=False)


def read_gzip(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def prepare(plan, target, training_dir, mip_root, pair_dir, device):
    start = perf_counter()
    import torch
    from cfl_gnn.graph.gurobi_graph_artifact import capture_root_relaxation, write_root_artifact
    from cfl_gnn.graph.label_free_gurobi import build_features, predict
    for item in plan["training_inputs"].values():
        checked(training_dir, item)
    checkpoint = checked(training_dir, plan["checkpoint"])
    mip = checked(mip_root, target["mip"])
    verify_seconds = perf_counter()-start
    t = perf_counter()
    root = capture_root_relaxation(mip, expected_mip_sha256=target["mip"]["sha256"],
                                  time_limit_seconds=600, threads=1, seed=42, presolve=0)
    root_seconds = perf_counter()-t
    t = perf_counter()
    graph, order, audit = build_features(mip, target["mip"]["sha256"], root)
    graph_seconds = perf_counter()-t
    t = perf_counter()
    write_root_artifact(pair_dir / "root_features.json.gz", root)
    torch.save(graph, pair_dir / "label_free_graph.pt")
    feature_write_seconds = perf_counter()-t
    t = perf_counter()
    rows = predict(graph, order, checkpoint, plan["architecture"], plan["threshold"], device)
    inference_seconds = perf_counter()-t
    t = perf_counter()
    payload = dict(schema_version=1, contract_sha256=plan["contract_sha256"],
                   source_instance_id=target["source_instance_id"], mip_sha256=target["mip"]["sha256"],
                   checkpoint_sha256=plan["checkpoint"]["sha256"], threshold=plan["threshold"],
                   binary_order_sha256=audit["binary_order_sha256"], target_labels_loaded=False, predictions=rows)
    write_gzip(pair_dir / "predictions.json.gz", payload)
    artifacts = {name: descriptor(pair_dir, pair_dir / name) for name in (
        "root_features.json.gz", "label_free_graph.pt", "predictions.json.gz")}
    artifact_seconds = feature_write_seconds + perf_counter()-t
    result = dict(gate_status="passed", contract_sha256=plan["contract_sha256"],
                  source_instance_id=target["source_instance_id"], artifacts=artifacts, feature_audit=audit,
                  device=device, torch_version=str(torch.__version__), cuda_version=torch.version.cuda,
                  timing=dict(preparation_wall_time_seconds=perf_counter()-start,
                              verification_wall_time_seconds=verify_seconds, root_capture_wall_time_seconds=root_seconds,
                              graph_build_wall_time_seconds=graph_seconds, model_load_and_inference_wall_time_seconds=inference_seconds,
                              artifact_export_and_hash_wall_time_seconds=artifact_seconds))
    write_json(pair_dir / "preparation.json", result)
    return result


def load_predictions(pair_dir, plan, target):
    preparation = read_json(pair_dir / "preparation.json")
    if (preparation.get("gate_status") != "passed" or preparation.get("contract_sha256") != plan["contract_sha256"]
            or preparation.get("source_instance_id") != target["source_instance_id"]
            or set(preparation.get("artifacts", {})) != {"root_features.json.gz", "label_free_graph.pt", "predictions.json.gz"}):
        raise ValueError("prediction preparation failed or changed")
    for item in preparation["artifacts"].values():
        checked(pair_dir, item)
    payload = read_gzip(checked(pair_dir, preparation["artifacts"]["predictions.json.gz"]))
    if (payload.get("contract_sha256") != plan["contract_sha256"]
            or payload.get("mip_sha256") != target["mip"]["sha256"]
            or payload.get("source_instance_id") != target["source_instance_id"]
            or payload.get("checkpoint_sha256") != plan["checkpoint"]["sha256"]
            or payload.get("threshold") != plan["threshold"] or payload.get("target_labels_loaded") is not False):
        raise ValueError("prediction identity mismatch")
    from cfl_gnn.graph.label_free_gurobi import prediction_rows
    rows = payload["predictions"]
    if rows != prediction_rows([r["variable_name"] for r in rows], [r["probability"] for r in rows], plan["threshold"]):
        raise ValueError("prediction assignments or ranking changed")
    if canonical_sha256([r["variable_name"] for r in rows]) != payload["binary_order_sha256"]:
        raise ValueError("prediction order changed")
    return rows


def worker(plan_dir, mip_root, run_root, task_index, method):
    from cfl_gnn.solvers.paired_partial_start import solve
    plan = load_plan(plan_dir)
    target = plan["targets"][task_index]
    pair_dir = Path(run_root) / target["source_instance_id"]
    destination = pair_dir / f"{method}.json"
    if destination.exists():
        raise ValueError("method result exists; preserve it")
    try:
        mip = checked(mip_root, target["mip"])
        rows = load_predictions(pair_dir, plan, target) if method == METHODS[1] else []
        result = solve(mip, target["mip"]["sha256"], rows, method,
                       solution_path=pair_dir / f"{method}.solution.json.gz")
        result.update(contract_sha256=plan["contract_sha256"], source_instance_id=target["source_instance_id"])
    except Exception as error:
        result = dict(gate_status="failed", reason_code="method_execution_failed", error_type=type(error).__name__,
                      reason_detail=error_reason(error), contract_sha256=plan["contract_sha256"], source_instance_id=target["source_instance_id"], method=method)
    write_json(destination, result)
    return result["gate_status"] == "passed"


def run_pair(plan_dir, training_dir, mip_root, run_root, task_index, device):
    plan = load_plan(plan_dir)
    if build_plan(training_dir, mip_root) != plan:
        raise ValueError("pilot inputs no longer match preflight")
    if task_index not in (0, 1):
        raise ValueError("only the two-parent pilot is implemented")
    target = plan["targets"][task_index]
    pair_dir = Path(run_root) / target["source_instance_id"]
    # Never overwrite or quietly rerun partial attempts. A reviewed retry needs
    # a new run root; earlier negative results remain retained.
    pair_dir.mkdir(parents=True, exist_ok=False)
    start = perf_counter()
    try:
        prepare(plan, target, training_dir, mip_root, pair_dir, device)
    except Exception as error:
        write_json(pair_dir / "preparation_failure.json", dict(gate_status="failed", error_type=type(error).__name__,
                   reason_code="label_free_preparation_failed", reason_detail=error_reason(error),
                   contract_sha256=plan["contract_sha256"]))
    workers = []
    for method in target["method_order"]:
        t = perf_counter()
        command = [sys.executable, "-m", "cfl_gnn.cli.run_easy_medium_pilot", "worker",
                   "--plan_dir", str(plan_dir), "--mip_root", str(mip_root), "--run_root", str(run_root),
                   "--task_index", str(task_index), "--method", method]
        with (pair_dir / f"{method}.log").open("wb") as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        workers.append(dict(method=method, returncode=process.returncode, process_wall_time_seconds=perf_counter()-t))
    receipt = dict(contract_sha256=plan["contract_sha256"], source_instance_id=target["source_instance_id"],
                   workers=workers, pair_wall_time_seconds=perf_counter()-start,
                   artifacts={p.name: descriptor(pair_dir, p) for p in sorted(pair_dir.iterdir()) if p.is_file() and p.suffix != ".log"})
    write_json(pair_dir / "pair_receipt.json", receipt)
    return all(w["returncode"] == 0 for w in workers)


def paired_effect(control, guided, prep_seconds, worker_seconds=None):
    """Negative differences favour guidance; do not invent censored speedups."""
    c, g = control["solve"], guided["solve"]
    cg, gg = c["terminal_mip_gap_relative"], g["terminal_mip_gap_relative"]
    ct, gt = control["timing"]["model_optimize_wall_time_seconds"], guided["timing"]["model_optimize_wall_time_seconds"]
    comparable_optimal = c["solve_status_code"] == g["solve_status_code"] == 2
    control_total = control["timing"]["total_wall_time_seconds"] if worker_seconds is None else worker_seconds[METHODS[0]]
    guided_total = guided["timing"]["total_wall_time_seconds"] if worker_seconds is None else worker_seconds[METHODS[1]]
    return dict(gap_difference_guided_minus_control=None if cg is None or gg is None else gg-cg,
        optimize_time_difference_guided_minus_control=gt-ct,
        time_to_optimal_speedup=ct/gt if comparable_optimal and gt > 0 else None,
        time_to_optimal_speedup_reason="both_optimal" if comparable_optimal else "censored_or_nonoptimal_no_speedup_claim",
        guided_cold_total_seconds=prep_seconds+guided_total,
        guided_reusable_artifact_total_seconds=guided_total, control_total_seconds=control_total)


def audit(plan_dir, run_root, output_dir):
    plan = load_plan(plan_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    records, pairs, failures, ledger, statuses = [], [], [], [], []
    for target in plan["targets"]:
        name = target["source_instance_id"]
        pair_dir = Path(run_root) / name
        try:
            receipt_path = pair_dir / "pair_receipt.json"
            receipt = read_json(receipt_path)
            if receipt["contract_sha256"] != plan["contract_sha256"] or receipt["source_instance_id"] != name:
                raise ValueError("pair receipt identity mismatch")
            for artifact in receipt["artifacts"].values():
                checked(pair_dir, artifact)
            ledger.append(descriptor(run_root, receipt_path))
            results = {}
            for method in METHODS:
                status = dict(source_instance_id=name, method=method, artifact_valid=False)
                statuses.append(status)
                try:
                    result = read_json(checked(pair_dir, receipt["artifacts"][f"{method}.json"]))
                    if result.get("gate_status") != "passed" or result.get("contract_sha256") != plan["contract_sha256"] or result.get("method") != method or result.get("source_instance_id") != name or result.get("mip_sha256") != target["mip"]["sha256"]:
                        raise ValueError("method failed or identity changed")
                    if result["solve"]["feasible_solution"]:
                        solution = result["solution_artifact"]
                        item = receipt["artifacts"][solution["file_name"]]
                        if item["sha256"] != solution["sha256"] or result["independent_feasibility"]["valid"] is not True:
                            raise ValueError("solution evidence mismatch")
                        checked(pair_dir, item)
                    timing = result["timing"]
                    fields = ["data_read_wall_time_seconds", "model_build_wall_time_seconds", "model_optimize_wall_time_seconds",
                              "independent_audit_wall_time_seconds", "other_wall_time_seconds"]
                    if any(not math.isfinite(timing[k]) or timing[k] < -1e-6 for k in [*fields, "total_wall_time_seconds"]):
                        raise ValueError("invalid timing measurement")
                    if not math.isclose(sum(timing[k] for k in fields), timing["total_wall_time_seconds"], abs_tol=1e-6):
                        raise ValueError("timing does not reconcile")
                    records.append(dict(source_instance_id=name, method=method, **result["solve"],
                                        **{k: timing[k] for k in [*fields, "total_wall_time_seconds"]}, start_status=result["start"]["status"]))
                    results[method] = result
                    status["artifact_valid"] = True
                except Exception as error:
                    status.update(error_type=type(error).__name__, reason_detail=error_reason(error))
            if len(results) != 2:
                raise ValueError("one or more method results invalid; retained in status ledger")
            preparation = read_json(checked(pair_dir, receipt["artifacts"]["preparation.json"]))
            load_predictions(pair_dir, plan, target)
            control, guided = [results[m] for m in METHODS]
            if (control["parameters"] != guided["parameters"] or control["solver_version"] != guided["solver_version"]
                    or control["mathematical_signature_sha256"] != guided["mathematical_signature_sha256"]
                    or [w["method"] for w in receipt["workers"]] != target["method_order"]
                    or any(w["returncode"] != 0 for w in receipt["workers"])):
                raise ValueError("paired execution controls differ")
            if any(not math.isfinite(w["process_wall_time_seconds"]) or w["process_wall_time_seconds"] < 0 for w in receipt["workers"]):
                raise ValueError("invalid worker process timing")
            if not math.isfinite(preparation["timing"]["preparation_wall_time_seconds"]) or preparation["timing"]["preparation_wall_time_seconds"] < 0:
                raise ValueError("invalid preparation timing")
            pairs.append(dict(source_instance_id=name, **paired_effect(control, guided, preparation["timing"]["preparation_wall_time_seconds"],
                {w["method"]: w["process_wall_time_seconds"] for w in receipt["workers"]})))
        except Exception as error:
            failures.append(dict(source_instance_id=name, error_type=type(error).__name__, reason_code="pair_incomplete_or_invalid", reason_detail=error_reason(error)))
        for method in METHODS:
            if not any(s["source_instance_id"] == name and s["method"] == method for s in statuses):
                statuses.append(dict(source_instance_id=name, method=method, artifact_valid=False, reason_detail="missing_or_unverified_pair_receipt"))
    # Failure-only runs still produce explicit reports with the full denominator.
    for filename, rows in (("per_method_outcomes.json", records), ("paired_effects.json", pairs), ("source_ledger.json", ledger), ("per_method_status.json", statuses)):
        write_json(output / filename, {"records": rows})
    for filename, rows in (("per_method_outcomes.csv", records), ("paired_effects.csv", pairs)):
        with (output / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["source_instance_id"])
            writer.writeheader()
            writer.writerows(rows)
    result = dict(schema_version=1, contract_sha256=plan["contract_sha256"], probe_completed=True,
                  gate_status="passed" if len(pairs) == 2 and not failures else "failed",
                  summary=dict(planned_parents=2, planned_method_runs=4, valid_pairs=len(pairs), valid_method_runs=len(records)),
                  failures=failures, improvement_required_for_gate=False, development_only=True, scientific_reporting_eligible=False,
                  timing_semantics={"cold_guided": "feature_preparation_plus_measured_worker_process",
                      "reusable_guided": "measured_worker_process_including_prediction_artifact_verification",
                      "excluded_from_comparative_totals": "offline_training_plan_audit_scheduler_queue_and_pair_orchestration",
                      "first_gap_times": "first_observed_not_exact_hitting_times"},
                  decision=dict(next_gate="review_medium_pilot_before_expansion", thirty_medium_campaign_authorized=False),
                  outputs={p.name: descriptor(output, p) for p in sorted(output.iterdir())})
    write_json(output / REPORT, result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("plan", "pair", "worker", "audit"))
    p.add_argument("--training_dir", type=Path)
    p.add_argument("--mip_root", type=Path)
    p.add_argument("--plan_dir", type=Path, required=True)
    p.add_argument("--run_root", type=Path)
    p.add_argument("--output_dir", type=Path)
    p.add_argument("--task_index", type=int, choices=(0, 1))
    p.add_argument("--method", choices=METHODS)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = p.parse_args(argv)
    required = {"plan": ("training_dir", "mip_root"), "pair": ("training_dir", "mip_root", "run_root", "task_index"),
                "worker": ("mip_root", "run_root", "task_index", "method"), "audit": ("run_root", "output_dir")}
    if any(getattr(args, name) is None for name in required[args.command]):
        p.error("required command-specific argument missing")
    try:
        if args.command == "plan":
            plan = build_plan(args.training_dir, args.mip_root)
            args.plan_dir.mkdir(parents=True, exist_ok=False)
            write_json(args.plan_dir / PLAN, plan)
            print(f"[INFO] contract={plan['contract_sha256']} | parents=2 | solves=4 | seed=42 | MINIMIZE")
            ok = True
        elif args.command == "pair":
            ok = run_pair(args.plan_dir, args.training_dir, args.mip_root, args.run_root, args.task_index, args.device)
        elif args.command == "worker":
            ok = worker(args.plan_dir, args.mip_root, args.run_root, args.task_index, args.method)
        else:
            report = audit(args.plan_dir, args.run_root, args.output_dir)
            print(json.dumps(report, indent=2))
            ok = report["gate_status"] == "passed"
        return 0 if ok else 1
    except Exception as error:
        print(f"[ERROR] {type(error).__name__}: {error_reason(error)}; preserve outputs for review")
        return 2
