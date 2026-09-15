"""Controlled medium batches and an additional sixteen-hour hard experiment.

PR53 remains immutable: its implementation hashes and negative evidence are
inputs, not files to update when increasing the budget for a new experiment.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from cfl_gnn.pipelines import gurobi_expansion as pilot

c, parent = pilot.c, pilot.parent
PLAN = "gurobi_expansion_campaign_plan.json"
REPORT = "gurobi_expansion_campaign_report.json"
TASK_REPORT = "gurobi_expansion_campaign_task_report.json"
PARAMETERS = {"NodeLimit": 1000000, "Threads": 1, "Seed": 42, "ModelSense": 1}
POLICY = {"schema_version": 1, "protocol": "gurobi_medium20_hard16h_v1",
          "solver": "gurobi", "objective_sense": "MINIMIZE", "seed": 42,
          "maximum_label_mip_gap_relative": .1, "preserved_parent_population": 40,
          "planned_parent_population": 90, "medium_time_limit_seconds": 28800,
          "hard_time_limit_seconds": 57600, "hard_parent_id": "CFL_hard_instance_1",
          "medium_batch_size": 5, "medium_batch_count": 4,
          "node_limit": 1000000, "threads": 1, "warm_start": False,
          "development_only": True, "scientific_reporting_eligible": False}
ARTIFACT_NAMES = (parent.plan_name("gurobi"), parent.report_name("gurobi"),
                  parent.SOLUTION_NAME, parent.INCUMBENTS_NAME, parent.VARIABLE_ORDER_NAME)


def implementations():
    return {**pilot.implementations(),
            "src/cfl_gnn/pipelines/gurobi_expansion_campaign.py": c.sha256_file(Path(__file__))}


def identity(row):
    return {k: row[k] for k in ("source_instance_id", "category", "difficulty", "fold", "role", "mip")}


def phase_tasks(inventory, preserved_ids):
    medium = [r for r in inventory if r["difficulty"] == "medium" and r["source_instance_id"] not in preserved_ids]
    medium.sort(key=lambda r: int(r["source_instance_id"].rsplit("_", 1)[1]))
    hard = [r for r in inventory if r["source_instance_id"] == POLICY["hard_parent_id"]]
    if len(medium) != 20 or len(hard) != 1 or hard[0]["source_instance_id"] in preserved_ids:
        raise ValueError("campaign requires twenty pending medium and the additional hard parent")
    tasks = []
    for phase, rows, budget in (("medium", medium, 28800), ("hard", hard, 57600)):
        for index, row in enumerate(rows):
            tasks.append({**identity(row), "phase": phase, "task_index": index,
                "batch_index": index // 5 if phase == "medium" else None,
                "time_limit_seconds": budget,
                "run_relative_path": f"budget_{budget}s/gurobi/{row['category']}/{row['source_instance_id']}"})
    return tasks


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def prepare(data_root, pilot_plan_dir, pilot_run_root, pilot_audit_dir, campaign_dir):
    data = Path(data_root).resolve()
    output = pilot.scoped(data, campaign_dir, "analysis/gurobi_expansion_campaign")
    previous = pilot.load_plan(pilot_plan_dir)
    pilot.verify_sources(data, previous)
    audit_dir = Path(pilot_audit_dir).resolve()
    audit_path = audit_dir / pilot.REPORT
    audited = c.read_json(audit_path)
    if audited.get("contract_sha256") != previous["contract_sha256"] or audited.get("gate_status") != "passed":
        raise ValueError("a passed PR53 execution audit is required")
    dependencies = [c.descriptor(data, Path(pilot_plan_dir) / pilot.PLAN),
                    c.descriptor(data, audit_path), previous["source_revision"]]
    for descriptor in audited["outputs"].values():
        dependencies.append(c.descriptor(data, c.checked(audit_dir, descriptor)))
    metrics = c.read_json(c.checked(audit_dir, audited["outputs"]["pilot_task_metrics.json"]))["records"]
    if len(metrics) != 2:
        raise ValueError("pilot task metrics are incomplete")
    inventory = previous["inventory"]
    if [identity(r) for r in inventory] != [{
        "source_instance_id": e.source_instance_id, "category": e.category,
        "difficulty": e.difficulty, "fold": e.fold, "role": pilot.role_for_fold(e.fold, 0),
        "mip": r["mip"]} for e, r in zip(pilot.build_planned_manifest(), inventory)] or len(inventory) != 90:
        raise ValueError("pilot inventory differs from canonical ninety-parent identities")
    for row in inventory:
        c.checked(data, row["mip"])
    preserved = []
    for row in previous["preserved"]:
        payload = pilot.read_solution(c.checked(data, row["solution"]))
        if not payload.get("mathematical_audit", {}).get("valid") or not c.eligible_gap(payload.get("mip_gap_relative")):
            raise ValueError("historical admitted label is no longer verifiable")
        preserved.append({**identity(row), "solution": row["solution"], "report": row["report"],
            "label_format": "confirmation_solution_json", "mip_gap_relative": payload["mip_gap_relative"],
            "execution_time_seconds": payload.get("execution_time_seconds")})
    attempts = []
    for task, metric in zip(previous["tasks"], metrics):
        directory = c.safe_path(pilot_run_root, task["run_relative_path"])
        receipt = pilot.verify_receipt(directory, previous, task)
        descriptor = c.descriptor(data, directory / pilot.TASK_REPORT)
        if (metric != {**receipt, "task_receipt": descriptor}
                or receipt.get("execution_valid") is not True
                or not all(receipt.get("checks", {}).values())
                or receipt.get("mathematical_audit", {}).get("valid") is not True
                or set(receipt.get("artifacts", {})) != set(ARTIFACT_NAMES)):
            raise ValueError("pilot receipt or aggregate lineage differs from source evidence")
        dependencies.append(descriptor)
        for artifact in receipt["artifacts"].values():
            dependencies.append(c.descriptor(data, c.checked(directory, artifact)))
        attempts.append({"source_instance_id": task["source_instance_id"], "receipt": descriptor,
            "label_eligible": receipt["label_eligible"], "solve": receipt["solve"],
            "time_regions": receipt["time_regions"], "right_censored": receipt["right_censored"]})
        if receipt["label_eligible"]:
            if not c.eligible_gap(receipt["solve"]["mip_gap_relative"]):
                raise ValueError("pilot label admission differs from gap policy")
            preserved.append({**identity(task), "label_format": "gurobi_parent_solution_json",
                "solution": c.descriptor(data, c.checked(directory, receipt["artifacts"][parent.SOLUTION_NAME])),
                "report": descriptor, "mip_gap_relative": receipt["solve"]["mip_gap_relative"],
                "execution_time_seconds": receipt["solve"]["execution_time_seconds"]})
    expected_ids = set(pilot.revision.COHORT) | {"CFL_medium_instance_3"}
    if len(preserved) != 40 or {r["source_instance_id"] for r in preserved} != expected_ids:
        raise ValueError("campaign must preserve the approved forty admitted parents")
    if (audited["summary"]["admitted_population"] != 40 or
            audited["summary"]["new_labels_admitted"] != 1):
        raise ValueError("pilot aggregate population disagrees with verified receipts")
    tasks = phase_tasks(inventory, expected_ids)
    selected_ids = {r["source_instance_id"] for r in tasks}
    deferred = [identity(r) for r in inventory if r["source_instance_id"] not in expected_ids | selected_ids]
    payload = {**POLICY, "implementation_sha256": implementations(),
        "source_pilot_contract_sha256": previous["contract_sha256"],
        "source_artifacts": dependencies, "preserved": preserved, "tasks": tasks,
        "deferred": deferred, "historical_pilot_attempts": attempts,
        "time_regions": list(pilot.REGIONS), "dataset_eligible": False,
        "comparison_boundary": "different_hard_parent_and_budget_not_a_paired_time_limit_effect"}
    result = {**payload, "contract_sha256": c.canonical_sha256(payload)}
    pilot.new_directory(output)
    c.write_json(output / PLAN, result)
    write_jsonl(output / "preserved_parent_label_index.jsonl", preserved)
    write_jsonl(output / "medium_tasks.jsonl", [t for t in tasks if t["phase"] == "medium"])
    write_jsonl(output / "hard_tasks.jsonl", [t for t in tasks if t["phase"] == "hard"])
    return result


def load_plan(campaign_dir):
    value = c.read_json(Path(campaign_dir) / PLAN)
    body = {k: v for k, v in value.items() if k != "contract_sha256"}
    if (c.canonical_sha256(body) != value.get("contract_sha256") or
            any(value.get(k) != v for k, v in POLICY.items()) or
            value.get("implementation_sha256") != implementations()):
        raise ValueError("campaign contract or implementation changed")
    known = {r["source_instance_id"] for r in value["preserved"]}
    if len(value["preserved"]) != 40 or known != set(pilot.revision.COHORT) | {"CFL_medium_instance_3"}:
        raise ValueError("preserved cohort changed")
    # Reconstruct expected pending identities from the canonical manifest.
    records = {r["source_instance_id"]: r for r in value["preserved"] + value["tasks"] + value["deferred"]}
    canonical = pilot.build_planned_manifest()
    if len(records) != 90 or len(value["deferred"]) != 29 or len(value["tasks"]) != 21:
        raise ValueError("campaign population accounting changed")
    inventory = []
    for e in canonical:
        row = records[e.source_instance_id]
        expected = {"source_instance_id": e.source_instance_id, "category": e.category,
                    "difficulty": e.difficulty, "fold": e.fold, "role": pilot.role_for_fold(e.fold, 0), "mip": row["mip"]}
        if identity(row) != expected:
            raise ValueError("parent fold or identity changed")
        inventory.append(row)
    if value["tasks"] != phase_tasks(inventory, known):
        raise ValueError("task identity budget or batch changed")
    return value


def verify_sources(data, plan):
    for descriptor in plan["source_artifacts"]:
        c.checked(data, descriptor)
    for row in plan["preserved"]:
        for key in ("mip", "solution", "report"):
            c.checked(data, row[key])


def select_task(plan, phase, task_index):
    matches = [r for r in plan["tasks"] if r["phase"] == phase and r["task_index"] == task_index]
    if len(matches) != 1:
        raise ValueError("phase or task index outside the frozen campaign")
    return matches[0]


def verify_receipt(directory, plan, task):
    value = c.read_json(directory / TASK_REPORT)
    body = {k: v for k, v in value.items() if k != "receipt_sha256"}
    if (c.canonical_sha256(body) != value.get("receipt_sha256")
            or value.get("campaign_contract_sha256") != plan["contract_sha256"]
            or value.get("task") != task):
        raise ValueError("campaign receipt identity budget or hash mismatch")
    if value.get("label_eligible") is True and value.get("execution_valid") is not True:
        raise ValueError("failed execution cannot admit a label")
    if value.get("execution_valid") is True:
        if (set(value.get("artifacts", {})) != set(ARTIFACT_NAMES)
                or not value.get("checks") or not all(v is True for v in value["checks"].values())
                or value.get("label_eligible") is not (value.get("mathematical_audit", {}).get("valid") is True
                    and c.eligible_gap(value.get("solve", {}).get("mip_gap_relative")))):
            raise ValueError("receipt execution or admission evidence is incomplete")
    for descriptor in value.get("artifacts", {}).values():
        c.checked(directory, descriptor)
    return value


def execute(data_root, campaign_dir, run_root, phase, task_index):
    data = Path(data_root).resolve()
    root = pilot.scoped(data, run_root, "intermediate/gurobi_expansion_campaign")
    plan = load_plan(campaign_dir)
    task = select_task(plan, phase, task_index)
    verify_sources(data, plan)
    mip = c.checked(data, task["mip"])
    directory = c.safe_path(root, task["run_relative_path"])
    if (directory / TASK_REPORT).is_file():
        result = verify_receipt(directory, plan, task)
        if result.get("execution_valid") is not True:
            raise ValueError("failed attempt retained; review before using a new run root")
        return result
    solve = parent.build_plan(parent_mip=mip, output_dir=directory,
        parent_instance_id=task["source_instance_id"], category=task["category"],
        difficulty=task["difficulty"], fold=task["fold"], config_path=parent.DEFAULT_CONFIG,
        time_limit=task["time_limit_seconds"], node_limit=plan["node_limit"], seed=42,
        threads=1, solver_profile="default", solver="gurobi")
    if solve.role != task["role"] or solve.maximum_admissible_relative_gap != .1:
        raise ValueError("collector configuration differs from campaign policy")
    pilot.new_directory(directory)
    started = time.perf_counter()
    result = {"schema_version": 1, "campaign_contract_sha256": plan["contract_sha256"],
              "task": task, "dataset_eligible": False, "scientific_reporting_eligible": False}
    artifacts = {}
    try:
        summary = solve.to_summary()
        summary["outputs"].pop("legacy_plan_alias", None)
        summary["outputs"].pop("legacy_report_alias", None)
        c.write_json(directory / parent.plan_name("gurobi"), summary)
        report = parent.run(solve)
        c.write_json(directory / parent.report_name("gurobi"), report)
        artifacts = {name: c.descriptor(directory, directory / name) for name in ARTIFACT_NAMES}
        payload = pilot.read_solution(directory / parent.SOLUTION_NAME)
        parameters = payload.get("solver_parameter_map", {})
        report["checks"]["worker_contract_matches"] = payload.get("contract_sha256") == solve.contract_sha256
        report["checks"]["effective_budget_matches"] = all(parameters.get(k) == v
            for k, v in {**PARAMETERS, "TimeLimit": task["time_limit_seconds"]}.items())
        report["checks"]["parameter_hash_valid"] = payload.get("solver_parameter_sha256") == c.canonical_sha256(parameters)
        mathematical = (pilot.independently_audit(mip, payload) if payload.get("solution_count", 0) > 0
                        else {"valid": None, "reason_code": "no_vector_to_audit"})
        result.update(pilot.classify(report, payload, mathematical))
        result.update(mathematical_audit=mathematical, solve=report["solve"],
            time_regions=report["time_regions"], time_region_semantics=report["time_region_semantics"],
            solver_versions=report["solver_versions"], solver_parameter_sha256=report["solver_parameter_sha256"],
            online_incumbent_capture=report["online_incumbent_capture"])
    except Exception as error:
        result.update(execution_valid=False, label_eligible=False, right_censored=None,
                      reason_code="worker_or_audit_exception", error_type=type(error).__name__)
    result.update(artifacts=artifacts, task_wall_time_seconds=time.perf_counter() - started,
        task_wall_time_semantics="collection_export_and_independent_audit_before_receipt_write")
    result = pilot.seal(result)
    c.write_json(directory / TASK_REPORT, result)
    return result


def audit(data_root, campaign_dir, run_root, output_dir, batch):
    if batch not in range(4):
        raise ValueError("medium batch must be zero through three")
    data = Path(data_root).resolve()
    plan = load_plan(campaign_dir)
    verify_sources(data, plan)
    root = pilot.scoped(data, run_root, "intermediate/gurobi_expansion_campaign")
    output = pilot.scoped(data, output_dir, "analysis/gurobi_expansion_campaign")
    rows, admitted = [], list(plan["preserved"])
    for task in plan["tasks"]:
        c.checked(data, task["mip"])
        directory = c.safe_path(root, task["run_relative_path"])
        row = {**task, "execution_valid": None, "label_eligible": False,
               "state": "not_started" if not directory.exists() else "incomplete"}
        if (directory / TASK_REPORT).is_file():
            try:
                receipt = verify_receipt(directory, plan, task)
                row.update({k: v for k, v in receipt.items() if k != "task"})
                row["task_receipt"] = c.descriptor(data, directory / TASK_REPORT)
                row["state"] = ("completed_admitted" if receipt["label_eligible"] else
                                "completed_unadmitted" if receipt["execution_valid"] else "failed")
                if receipt["label_eligible"]:
                    admitted.append({**identity(task), "label_format": "gurobi_parent_solution_json",
                        "solution": c.descriptor(data, c.checked(directory, receipt["artifacts"][parent.SOLUTION_NAME])),
                        "report": row["task_receipt"], "mip_gap_relative": receipt["solve"]["mip_gap_relative"],
                        "execution_time_seconds": receipt["solve"]["execution_time_seconds"]})
            except (OSError, ValueError, KeyError, TypeError):
                row.update(state="invalid_receipt", execution_valid=False, reason_code="receipt_or_artifact_mismatch")
        rows.append(row)
    selected = [r for r in rows if r["phase"] == "hard" or r["batch_index"] == batch]
    bad = [r for r in rows if r["state"] in {"failed", "invalid_receipt"}]
    passed = all(r["execution_valid"] is True for r in selected) and not bad
    valid = [r for r in rows if r["execution_valid"] is True]
    pilot_cost = sum(r["time_regions"]["model_optimize_wall_time_seconds"] for r in plan["historical_pilot_attempts"])
    measured = [r for r in rows if "model_optimize_wall_time_seconds" in r.get("time_regions", {})]
    current_cost = sum(r["time_regions"]["model_optimize_wall_time_seconds"] for r in measured)
    pilot.new_directory(output)
    c.write_json(output / "campaign_task_metrics.json", {"records": rows})
    write_jsonl(output / "admitted_parent_label_index.jsonl", admitted)
    columns = ["source_instance_id", "phase", "batch_index", "state", "time_limit_seconds",
               "execution_valid", "label_eligible", "right_censored", "reason_code", "mip_gap_relative",
               *pilot.REGIONS, "task_wall_time_seconds"]
    with (output / "campaign_runtime_outcomes.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            flat = {**row, **row.get("solve", {}), **row.get("time_regions", {})}
            writer.writerow({k: flat.get(k) for k in columns})
    result = {"schema_version": 1, "contract_sha256": plan["contract_sha256"],
        "gate_status": "passed" if passed else "failed", "requested_medium_batch": batch,
        "summary": {"preserved_labels": 40, "planned_tasks": 21,
            "selected_tasks": len(selected), "selected_valid_tasks": sum(r["execution_valid"] is True for r in selected),
            "valid_tasks": len(valid), "failed_tasks": len(bad),
            "not_started_tasks": sum(r["state"] == "not_started" for r in rows),
            "incomplete_tasks": sum(r["state"] == "incomplete" for r in rows),
            "new_labels_admitted": len(admitted) - 40, "admitted_population": len(admitted),
            "unresolved_population": 90 - len(admitted), "deferred_hard_parents": 29,
            "right_censored_tasks": sum(r.get("right_censored") is True for r in rows)},
        "cost_accounting": {"prior_pilot_optimize_wall_seconds": pilot_cost,
            "current_run_root_observed_optimize_wall_seconds": current_cost,
            "known_expansion_optimize_wall_seconds": pilot_cost + current_cost,
            "current_tasks_with_optimize_measurements": len(measured),
            "pre_pilot_and_other_attempts_cumulative_seconds": None,
            "scope": "observed_PR53_pilot_and_this_run_root_only_not_full_research_cost"},
        "eligibility": {"dataset_eligible": False, "development_only": True, "scientific_reporting_eligible": False},
        "decision": {"next_gate": "review_next_medium_batch_and_hard_budget_outcome",
                     "all_planned_tasks_valid": len(valid) == 21,
                     "ninety_parent_population_complete": len(admitted) == 90},
        "outputs": {n: c.descriptor(output, output / n) for n in
            ("campaign_task_metrics.json", "campaign_runtime_outcomes.csv", "admitted_parent_label_index.jsonl")}}
    c.write_json(output / REPORT, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "task", "audit"):
        p = commands.add_parser(name)
        p.add_argument("--data_root", required=True, type=Path)
        p.add_argument("--campaign_dir", required=True, type=Path)
        if name == "prepare":
            for field in ("pilot_plan_dir", "pilot_run_root", "pilot_audit_dir"):
                p.add_argument("--" + field, required=True, type=Path)
        else:
            p.add_argument("--run_root", required=True, type=Path)
            if name == "task":
                p.add_argument("--phase", required=True, choices=("medium", "hard"))
                p.add_argument("--task_index", required=True, type=int)
            else:
                p.add_argument("--output_dir", required=True, type=Path)
                p.add_argument("--batch", required=True, type=int)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        result = {"prepare": prepare, "task": execute, "audit": audit}[command](**args)
    except Exception as error:
        print(f"[ERROR] {c.error_reason(error)} ({type(error).__name__})")
        return 2
    if command == "prepare":
        print(f"[INFO] contract={result['contract_sha256']} | preserved=40 | medium=20 at 28800s | hard=1 at 57600s | seed=42 | MINIMIZE")
        return 0
    ok = result.get("execution_valid") is True if command == "task" else result["gate_status"] == "passed"
    print(f"[INFO] {command} | execution_valid={ok} | dataset_eligible=false")
    return 0 if ok else 1
