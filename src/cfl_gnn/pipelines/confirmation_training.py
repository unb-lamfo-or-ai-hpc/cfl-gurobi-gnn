"""Strict graph consolidation of a complete or explicitly revised source cohort.

This adapter preserves imported-label provenance. It reuses the versioned Gasse
backend, not a new trainer, and never manufactures parent solve reports.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path

from cfl_gnn.pipelines.confirmation_execution import (
    PLAN, COHORT, read_json, checked, descriptor, safe_path, validate_plan, eligible_gap)
from cfl_gnn.training.gasse_reconnected import (
    canonical_sha256, write_json, read_jsonl, load_protocol, git_blob_sha1,
    LEGACY_GASSE_GIT_BLOB_SHA1, validate_training_plan, TRAINING_PLAN_NAME,
    TRAINING_REPORT_NAME, TRAINING_HISTORY_NAME, run_serial_training)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT


def admitted_sources(campaign_dir, cohort_revision_dir=None):
    if cohort_revision_dir is not None:
        from cfl_gnn.pipelines.confirmation_revision import load
        _, plan, report, rows = load(campaign_dir, cohort_revision_dir)
        return plan, report, {r["source_instance_id"]: r for r in rows}
    campaign = Path(campaign_dir).resolve()
    plan = read_json(campaign / PLAN)
    validate_plan(plan)
    report = read_json(campaign / "confirmation_execution_report.json")
    if (report.get("campaign_contract_sha256") != plan["contract_sha256"]
            or report.get("gate_status") != "passed" or report.get("label_inventory_ready") is not True):
        raise ValueError("42-parent independent source gate is not complete")
    index_path = checked(campaign, report["label_index"])
    rows = read_jsonl(index_path)
    if len(rows) != 42 or {r["source_instance_id"] for r in rows} != set(COHORT):
        raise ValueError("label index differs from the frozen 42-parent cohort")
    tasks = {t["source_instance_id"]: t for t in plan["tasks"]}
    for row in rows:
        task = tasks[row["source_instance_id"]]
        if (row["mip"] != task["mip"] or row["role"] != task["role"] or row["fold"] != task["fold"]
                or row.get("label_eligible") is not True or not eligible_gap(row["mip_gap_relative"])):
            raise ValueError("label index identity or eligibility mismatch")
    return plan, report, {r["source_instance_id"]: r for r in rows}


def graph_contract(campaign_dir, cohort_revision_dir=None):
    from cfl_gnn.graph import gurobi_graph_artifact
    plan, report, rows = admitted_sources(campaign_dir, cohort_revision_dir)
    contract = {"schema_version": 1, "source_contract_sha256": plan["contract_sha256"],
                "source_report_sha256": sha256_file(Path(campaign_dir) / "confirmation_execution_report.json"),
                "label_index_sha256": report["label_index"]["sha256"],
                "root_policy": "first_optimal_root_gurobi_mipnode", "root_time_limit_seconds": 600,
                "graph_authority": "gurobi", "objective_sense": "MINIMIZE", "seed": 42,
                "zero_fallback_allowed": False, "cohort": list(rows),
                "implementation_sha256": {"adapter": sha256_file(Path(__file__)),
                    "graph_builder": sha256_file(Path(gurobi_graph_artifact.__file__))}}
    if cohort_revision_dir is not None:
        from cfl_gnn.pipelines.confirmation_revision import load
        revision, _, _, _ = load(campaign_dir, cohort_revision_dir)
        contract["cohort_revision"] = revision
    return {**contract, "contract_sha256": canonical_sha256(contract)}, plan, rows


def checked_label(campaign, row, task):
    path = checked(campaign, row["solution"])
    report_path = checked(campaign, row["report"])
    report = read_json(report_path)
    if (report.get("gate_status") != "passed" or report.get("label_eligible") is not True
            or report.get("mip_sha256") != task["mip"]["sha256"]
            or report.get("source_instance_id") != task["source_instance_id"]
            or report.get("solution", {}).get("sha256") != row["solution"]["sha256"]):
        raise ValueError("source report does not certify the indexed label")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        label = json.load(stream)
    if (label.get("source_mip_sha256") != task["mip"]["sha256"]
            or label.get("solution_source") != "independently_audited_gurobi_confirmation_label"
            or label.get("mathematical_audit", {}).get("valid") is not True
            or label.get("mip_gap_relative") != row["mip_gap_relative"]):
        raise ValueError("imported label provenance differs from the index")
    return path, label


def build_graph(*, campaign_dir, data_root, dataset_dir, task_index, cohort_revision_dir=None):
    from cfl_gnn.graph.gurobi_graph_artifact import capture_root_relaxation, write_root_artifact, build_graph_artifact
    campaign, output = Path(campaign_dir).resolve(), Path(dataset_dir).resolve()
    contract, source_plan, sources = graph_contract(campaign, cohort_revision_dir)
    tasks = [t for t in source_plan["tasks"] if t["source_instance_id"] in sources]
    if not 0 <= task_index < len(tasks):
        raise ValueError("graph task outside frozen cohort")
    task = tasks[task_index]
    identity = task["source_instance_id"]
    row = sources[identity]
    mip = checked(data_root, task["mip"])
    label_path, _ = checked_label(campaign, row, task)
    receipt_path = output / "receipts" / f"{identity}.json"
    if receipt_path.is_file():
        previous = read_json(receipt_path)
        if previous.get("contract_sha256") != contract["contract_sha256"]:
            raise ValueError("existing graph receipt belongs to another contract")
        for name in ("graph", "root"):
            checked(output, previous[name])
        return previous
    graph_path, root_path = output / "graphs" / f"{identity}.pt", output / "roots" / f"{identity}.json.gz"
    if graph_path.exists() or root_path.exists():
        raise ValueError("uncommitted graph artifacts exist; preserve and inspect them")
    root = capture_root_relaxation(mip, expected_mip_sha256=task["mip"]["sha256"],
                                  time_limit_seconds=600, threads=1, seed=42, presolve=0)
    write_root_artifact(root_path, root)
    metadata = {"sample_id": identity, "source_instance_id": identity,
                "category": identity.rsplit("_", 1)[0], "difficulty": task["difficulty"],
                "fold": task["fold"], "role": task["role"], "sampling_strategy": "original",
                "label_source_solver": "gurobi"}
    audit = build_graph_artifact(mip_path=mip, mip_sha256=task["mip"]["sha256"],
        solution_path=label_path, solution_sha256=row["solution"]["sha256"], root_payload=root,
        output_path=graph_path, sample_metadata=metadata)
    result = {**metadata, "contract_sha256": contract["contract_sha256"],
              "mip_sha256": task["mip"]["sha256"], "source_label": row["solution"],
              "source_report": row["report"], "graph": descriptor(output, graph_path),
              "root": descriptor(output, root_path), "audit": audit,
              "development_only": True, "scientific_reporting_eligible": False}
    write_json(receipt_path, result)
    return result


def consolidate(*, campaign_dir, dataset_dir, descriptive_outputs=True, cohort_revision_dir=None):
    campaign, output = Path(campaign_dir).resolve(), Path(dataset_dir).resolve()
    contract, plan, sources = graph_contract(campaign, cohort_revision_dir)
    records = []
    for task in plan["tasks"]:
        identity = task["source_instance_id"]
        if identity not in sources:
            continue
        receipt_path = output / "receipts" / f"{identity}.json"
        receipt = read_json(receipt_path)
        if (receipt["contract_sha256"] != contract["contract_sha256"] or receipt["source_instance_id"] != identity
                or receipt["role"] != task["role"] or receipt["fold"] != task["fold"]
                or receipt["source_label"] != sources[identity]["solution"]
                or receipt["source_report"] != sources[identity]["report"]
                or receipt["mip_sha256"] != task["mip"]["sha256"]):
            raise ValueError("graph receipt identity mismatch")
        audit = receipt["audit"]
        if not all(audit.get(k) is True for k in ("roundtrip_readable", "label_variable_identity_match", "root_lp_feature_exactly_encoded")):
            raise ValueError("strict graph audit did not pass")
        if audit.get("independent_label_feasibility", {}).get("valid") is not True:
            raise ValueError("graph label is not independently feasible")
        checked(output, receipt["graph"])
        checked(output, receipt["root"])
        label_path, label = checked_label(campaign, sources[identity], task)
        records.append({"sample_id": identity, "source_instance_id": identity, "parent_instance_id": identity,
            "category": identity.rsplit("_", 1)[0], "difficulty": task["difficulty"],
            "fold": task["fold"], "role": task["role"], "sampling_strategy": "original", "graph_authority": "gurobi",
            "mip_sha256": task["mip"]["sha256"], "graph_relative_path": receipt["graph"]["relative_path"],
            "graph_sha256": receipt["graph"]["sha256"], "root_relative_path": receipt["root"]["relative_path"],
            "root_sha256": receipt["root"]["sha256"], "label_solver": "gurobi",
            "label_source": label["solution_source"], "label_contract_sha256": plan["contract_sha256"],
            "label_run_relative_path": label_path.parent.relative_to(campaign).as_posix(),
            "label_file_name": label_path.name, "label_sha256": sources[identity]["solution"]["sha256"],
            "label_mip_gap_relative": label["mip_gap_relative"], "label_objective": label["solution_objective"],
            "label_execution_time_seconds": label["execution_time_seconds"],
            "receipt": descriptor(output, receipt_path)})
    if len({r["mip_sha256"] for r in records}) != len(sources):
        raise ValueError("duplicate parent formulation in frozen cohort")
    manifest = output / "confirmation_graph_manifest.jsonl"
    manifest.write_text("".join(json.dumps(r, sort_keys=True, allow_nan=False)+"\n" for r in records), encoding="utf-8")
    analyses = {}
    if descriptive_outputs:
        from cfl_gnn.analysis.graph_statistics import analyze_graph_manifest
        from cfl_gnn.analysis.graph_clustering import cluster_graph_manifest
        for name, function in (("statistics", analyze_graph_manifest), ("clustering", cluster_graph_manifest)):
            analyses[name] = function(manifest_path=manifest, graph_root=output, output_dir=output / "analysis" / name, overwrite=True)
        if not all(r["gate_status"] == "passed" for r in analyses.values()):
            raise ValueError("graph descriptive analysis failed")
    report = {"contract": contract, "gate_status": "passed", "graphs": len(sources),
              "manifest": descriptor(output, manifest), "analyses": analyses,
              "descriptive_outputs_complete": descriptive_outputs,
              "development_only": True, "scientific_reporting_eligible": False}
    write_json(output / "confirmation_graph_report.json", report)
    return report


def training_plan(*, campaign_dir, dataset_dir, cohort_revision_dir=None):
    output = Path(dataset_dir).resolve()
    contract, source_plan, sources = graph_contract(campaign_dir, cohort_revision_dir)
    report = read_json(output / "confirmation_graph_report.json")
    if report.get("gate_status") != "passed" or report.get("contract") != contract or report.get("graphs") != len(sources):
        raise ValueError("strict approved-cohort graph dataset is not ready")
    records = read_jsonl(checked(output, report["manifest"]))
    if len(records) != len(sources) or {r["sample_id"] for r in records} != set(sources):
        raise ValueError("training inventory changed")
    tasks = {t["source_instance_id"]: t for t in source_plan["tasks"]}
    for record in records:
        task = tasks[record["sample_id"]]
        if (record["role"] != task["role"] or record["fold"] != task["fold"]
                or record["sampling_strategy"] != "original" or record["mip_sha256"] != task["mip"]["sha256"]
                or not eligible_gap(record["label_mip_gap_relative"])):
            raise ValueError("training split or sample identity changed")
        checked(output, {"relative_path": record["graph_relative_path"], "sha256": record["graph_sha256"]})
        checked(output, {"relative_path": record["root_relative_path"], "sha256": record["root_sha256"]})
        checked(campaign_dir, {"relative_path": record["label_run_relative_path"]+"/"+record["label_file_name"], "sha256": record["label_sha256"]})
    protocol_path = PROJECT_ROOT / "configs/training" / (
        "gasse_development_39_v1.json" if cohort_revision_dir is not None else "gasse_confirmation_v2.json")
    protocol = load_protocol(protocol_path)
    if protocol["optimization"]["epochs"] != 100 or protocol["optimization"]["patience"] != 100 or protocol["optimization"]["seed"] != 42:
        raise ValueError("confirmation requires 100 full epochs and seed 42")
    if protocol["sampling"]["maximum_label_mip_gap_relative"] != .1:
        raise ValueError("confirmation label admission ceiling must remain ten percent")
    model_path = PROJECT_ROOT / "src/cfl_gnn/models/gasse.py"
    if git_blob_sha1(model_path) != LEGACY_GASSE_GIT_BLOB_SHA1:
        raise ValueError("preserved Gasse model changed")
    counts = {role: sum(r["role"] == role for r in records) for role in ("train", "validation", "test")}
    expected_counts = contract.get("cohort_revision", {}).get("partition_counts", {"train": 24, "validation": 10, "test": 8})
    if counts != expected_counts:
        raise ValueError("confirmation partition counts changed")
    payload = {"schema_version": 1, "dataset_variant": "independently_admitted_confirmation_v1",
        "graph_dataset_contract_sha256": contract["contract_sha256"],
        "source_collection_contract_sha256": source_plan["contract_sha256"],
        "graph_report_sha256": sha256_file(output / "confirmation_graph_report.json"),
        "graph_authority": "gurobi", "label_solver": "gurobi", "protocol": protocol,
        "protocol_sha256": canonical_sha256(protocol), "legacy_gasse_git_blob_sha1": LEGACY_GASSE_GIT_BLOB_SHA1,
        "implementation_sha256": {name: sha256_file(PROJECT_ROOT / "src/cfl_gnn" / name) for name in (
            "models/gasse_calibrated.py", "training/gasse_reconnected.py", "training/serial.py",
            "training/figures.py", "evaluation/gasse_reconnected.py")},
        "records": records, "partition_counts": counts,
        "test_partition_usage": "held_out_not_loaded_during_training",
        "development_only": True, "scientific_reporting_eligible": False}
    if cohort_revision_dir is not None:
        payload["dataset_variant"] = "approved_39_parent_development_v1"
        payload["cohort_revision"] = contract["cohort_revision"]
    return {**payload, "contract_sha256": canonical_sha256(payload), "contract_valid": True,
            "training_ready": True, "engineering_smoke_ready": True, "held_out_evaluation_ready": True}


def validate_training_receipt(report, output):
    """Require a complete finite learning curve before accessing held-out graphs."""
    if (report.get("gate_status") != "passed" or report.get("epochs_completed") != 100
            or report.get("test_graphs_loaded") != 0
            or report.get("checkpoint_selection") != "minimum_validation_weighted_bce"
            or report.get("threshold_source") != "maximum_validation_f1"):
        raise ValueError("100-epoch training or validation-only selection contract failed")
    for key in ("checkpoint", TRAINING_HISTORY_NAME, "training_validation_loss.svg"):
        item = report["outputs"][key]
        checked(output, {"relative_path": item.get("file_name", key), "sha256": item["sha256"]})
    with (Path(output) / TRAINING_HISTORY_NAME).open(encoding="utf-8", newline="") as stream:
        history = list(csv.DictReader(stream))
    if ([int(row["epoch"]) for row in history] != list(range(1, 101))
            or any(not math.isfinite(float(row[key])) or float(row[key]) < 0
                   for row in history for key in ("train_loss", "validation_loss"))):
        raise ValueError("training and validation curves must contain 100 finite epochs")


def train_and_evaluate(*, campaign_dir, dataset_dir, output_dir, device="cuda", cohort_revision_dir=None):
    from cfl_gnn.evaluation.gasse_reconnected import build_evaluation_plan, execute_evaluation
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("use a new training output directory")
    plan = training_plan(campaign_dir=campaign_dir, dataset_dir=dataset_dir, cohort_revision_dir=cohort_revision_dir)
    graph_report = read_json(Path(dataset_dir) / "confirmation_graph_report.json")
    if graph_report.get("descriptive_outputs_complete") is not True:
        raise ValueError("graph descriptive outputs must pass before training")
    validate_training_plan(plan)
    write_json(output / TRAINING_PLAN_NAME, plan)
    report = run_serial_training(plan, graph_root=dataset_dir, label_root=campaign_dir,
                                 output_dir=output, device_name=device)
    validate_training_receipt(report, output)
    evaluation = build_evaluation_plan(training_plan_path=output / TRAINING_PLAN_NAME,
        training_report_path=output / TRAINING_REPORT_NAME, checkpoint_path=output / "best_model.pt")
    write_json(output / "evaluation/gasse_evaluation_plan.json", evaluation)
    result = execute_evaluation(evaluation, graph_root=dataset_dir, label_root=campaign_dir,
        checkpoint_path=output / "best_model.pt", output_dir=output / "evaluation", device_name=device)
    if (result.get("gate_status") != "passed" or result.get("test_graphs_loaded") != 8
            or result.get("test_partition_usage") != "held_out_evaluation_only"):
        raise ValueError("eight-parent held-out evaluation contract failed")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("revise", "preflight", "graph", "consolidate", "dry-run", "train"))
    p.add_argument("--campaign_dir", type=Path, required=True)
    p.add_argument("--dataset_dir", type=Path, required=True)
    p.add_argument("--cohort_revision_dir", type=Path)
    p.add_argument("--data_root", type=Path)
    p.add_argument("--task_index", type=int)
    p.add_argument("--output_dir", type=Path)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = p.parse_args(argv)
    revision_args = {"cohort_revision_dir": args.cohort_revision_dir}
    if args.command == "revise":
        if args.cohort_revision_dir is None:
            p.error("revise requires cohort_revision_dir")
        from cfl_gnn.pipelines.confirmation_revision import prepare
        result = prepare(args.campaign_dir, args.cohort_revision_dir)
    elif args.command == "preflight":
        result, _, _ = graph_contract(args.campaign_dir, **revision_args)
    elif args.command == "graph":
        if args.data_root is None or args.task_index is None:
            p.error("graph requires data_root and task_index")
        result = build_graph(campaign_dir=args.campaign_dir, data_root=args.data_root,
                             dataset_dir=args.dataset_dir, task_index=args.task_index, **revision_args)
    elif args.command == "consolidate":
        result = consolidate(campaign_dir=args.campaign_dir, dataset_dir=args.dataset_dir, **revision_args)
    elif args.command == "dry-run":
        result = training_plan(campaign_dir=args.campaign_dir, dataset_dir=args.dataset_dir, **revision_args)
    else:
        if args.output_dir is None:
            p.error("train requires output_dir")
        result = train_and_evaluate(campaign_dir=args.campaign_dir, dataset_dir=args.dataset_dir,
                                   output_dir=args.output_dir, device=args.device, **revision_args)
    if args.command in {"revise", "preflight"}:
        print(json.dumps({"contract_sha256": result["contract_sha256"], "cohort_size": len(result["cohort"]),
                          "cohort_revision": result.get("cohort_revision", {}).get("revision_id", result.get("revision_id")),
                          "development_only": True}, sort_keys=True))
    print(f"[INFO] confirmation stage={args.command} completed | development_only=true")
    return 0
