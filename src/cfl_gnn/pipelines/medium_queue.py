"""Queue the remaining original medium batches behind independently verified audits.

Preparation tolerates the earlier batch being in progress. Each future worker
must verify its predecessor audit before calling the unchanged PR54 executor.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cfl_gnn.pipelines import medium_continuation as previous

campaign, c, pilot = previous.campaign, previous.c, previous.pilot
PLAN = "remaining_medium_queue_plan.json"
POLICY = dict(schema_version=1, protocol="remaining_medium_queue_v1", solver="gurobi",
              objective_sense="MINIMIZE", seed=42, time_limit_seconds=28800,
              threads=1, memory_gib=64, concurrency=1, batches=[2, 3],
              warm_start=False, hard_jobs=0, rescue_jobs=0, training_jobs=0,
              development_only=True, scientific_reporting_eligible=False)


def prepare(data_root, campaign_dir, run_root, reviewed_preflight, predecessor_audit_dir, output_dir):
    data = Path(data_root).resolve()
    root = pilot.scoped(data, run_root, "intermediate/gurobi_expansion_campaign")
    output = pilot.scoped(data, output_dir, "analysis/medium_queue")
    predecessor = pilot.scoped(data, predecessor_audit_dir, "analysis/gurobi_expansion_campaign")
    plan = campaign.load_plan(campaign_dir)
    campaign.verify_sources(data, plan)
    reviewed_path = Path(reviewed_preflight).resolve()
    reviewed = c.read_json(reviewed_path)
    body = {k: v for k, v in reviewed.items() if k != "contract_sha256"}
    expected = [t for t in plan["tasks"] if t["phase"] == "medium" and t["batch_index"] == 1]
    if (c.canonical_sha256(body) != reviewed.get("contract_sha256")
            or reviewed.get("gate_status") != "passed"
            or reviewed.get("source_campaign_contract_sha256") != plan["contract_sha256"]
            or reviewed.get("original_campaign_batch") != 1
            or reviewed.get("selected_tasks") != expected
            or reviewed.get("preserved_labels") != 42
            or reviewed.get("implementation_sha256") != c.sha256_file(Path(previous.__file__))):
        raise ValueError("verified first continuation preflight required")
    sources = [c.descriptor(data, reviewed_path), c.descriptor(data, Path(campaign_dir) / campaign.PLAN),
               reviewed["source_reconciliation"], *reviewed["source_outputs"]]
    for item in sources:
        c.checked(data, item)
    index_paths = [c.checked(data, item) for item in reviewed["source_outputs"]
                   if Path(item["relative_path"]).name == "preserved_label_index.jsonl"]
    if len(index_paths) != 1:
        raise ValueError("preserved label index required")
    import json
    preserved = [json.loads(line) for line in index_paths[0].read_text().splitlines() if line.strip()]
    if len(preserved) != 42 or len({r["source_instance_id"] for r in preserved}) != 42:
        raise ValueError("forty two distinct admitted parents required")
    for row in preserved:
        for key in ("mip", "solution", "report"):
            c.checked(data, row[key])
            sources.append(row[key])
    selected = [t for t in plan["tasks"] if t["phase"] == "medium" and t["batch_index"] in (2, 3)]
    if [t["task_index"] for t in selected] != list(range(10, 20)):
        raise ValueError("remaining original task indices changed")
    for task in selected:
        c.checked(data, task["mip"])
        if c.safe_path(root, task["run_relative_path"]).exists():
            raise ValueError("remaining target already started; reconcile before a new queue")
    audits = {str(b): f"analysis/gurobi_expansion_campaign/{output.name}_batch{b}_audit" for b in (2, 3)}
    if any(c.safe_path(data, p).exists() for p in audits.values()):
        raise FileExistsError("queue audit output already exists")
    payload = {**POLICY, "campaign_dir": Path(campaign_dir).resolve().relative_to(data).as_posix(),
        "run_root": root.relative_to(data).as_posix(),
        "predecessor_audit_dir": predecessor.relative_to(data).as_posix(),
        "campaign_contract_sha256": plan["contract_sha256"], "preserved_labels": 42,
        "implementation_sha256": c.sha256_file(Path(__file__)),
        "sources": sources, "tasks": selected, "audit_dirs": audits,
        "solver_runs_executed": 0, "gate_status": "passed"}
    result = {**payload, "contract_sha256": c.canonical_sha256(payload)}
    pilot.new_directory(output)
    c.write_json(output / PLAN, result)
    return result


def load(data_root, queue_dir):
    data = Path(data_root).resolve()
    queue = c.read_json(pilot.scoped(data, queue_dir, "analysis/medium_queue") / PLAN)
    body = {k: v for k, v in queue.items() if k != "contract_sha256"}
    if (c.canonical_sha256(body) != queue.get("contract_sha256")
            or any(queue.get(k) != v for k, v in POLICY.items())
            or queue.get("implementation_sha256") != c.sha256_file(Path(__file__))):
        raise ValueError("queue contract or implementation changed")
    plan = campaign.load_plan(c.safe_path(data, queue["campaign_dir"]))
    if (queue["campaign_contract_sha256"] != plan["contract_sha256"]
            or queue["tasks"] != [t for t in plan["tasks"] if t["phase"] == "medium" and t["batch_index"] in (2, 3)]):
        raise ValueError("queue differs from the original medium campaign")
    campaign.verify_sources(data, plan)
    for descriptor in queue["sources"]:
        c.checked(data, descriptor)
    return data, queue, plan


def verify_predecessor(data, queue, plan, batch):
    """Verify output bytes and actual receipts; a scheduler exit code is insufficient."""
    directory = c.safe_path(data, queue["predecessor_audit_dir"] if batch == 2 else queue["audit_dirs"]["2"])
    report = c.read_json(directory / campaign.REPORT)
    if (report.get("gate_status") != "passed" or report.get("requested_medium_batch") != batch - 1
            or report.get("contract_sha256") != plan["contract_sha256"]
            or set(report.get("outputs", {})) != {"campaign_task_metrics.json", "campaign_runtime_outcomes.csv", "admitted_parent_label_index.jsonl"}):
        raise ValueError("passed matching predecessor audit required before solving")
    for item in report["outputs"].values():
        c.checked(directory, item)
    rows = c.read_json(c.checked(directory, report["outputs"]["campaign_task_metrics.json"]))["records"]
    root = c.safe_path(data, queue["run_root"])
    for task in plan["tasks"]:
        if task["phase"] != "hard" and task["batch_index"] != batch - 1:
            continue
        taskdir = c.safe_path(root, task["run_relative_path"])
        receipt = campaign.verify_receipt(taskdir, plan, task)
        matches = [r for r in rows if r["phase"] == task["phase"] and r["task_index"] == task["task_index"]]
        if (len(matches) != 1 or receipt.get("execution_valid") is not True
                or matches[0].get("task_receipt") != c.descriptor(data, taskdir / campaign.TASK_REPORT)
                or any(matches[0].get(k) != v for k, v in receipt.items() if k != "task")
                or any(matches[0].get(k) != v for k, v in task.items())):
            raise ValueError("predecessor audit does not match valid source receipts")
    # Existing high-gap hard evidence is verified, never rerun or admitted here.


def execute(data_root, queue_dir, task_index):
    data, queue, plan = load(data_root, queue_dir)
    selected = [t for t in queue["tasks"] if t["task_index"] == task_index]
    if len(selected) != 1:
        raise ValueError("task is not in the remaining medium queue")
    verify_predecessor(data, queue, plan, selected[0]["batch_index"])
    return campaign.execute(data, c.safe_path(data, queue["campaign_dir"]),
                            c.safe_path(data, queue["run_root"]), "medium", task_index)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    for key in ("data_root", "campaign_dir", "run_root", "reviewed_preflight", "predecessor_audit_dir", "output_dir"):
        p.add_argument("--" + key, type=Path, required=True)
    p = commands.add_parser("task")
    for key in ("data_root", "queue_dir"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--task_index", type=int, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        result = prepare(**args) if command == "prepare" else execute(**args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"[ERROR] {c.error_reason(error)} ({type(error).__name__})")
        return 2
    if command == "prepare":
        print("[INFO] PR57_REMAINING_QUEUE_OK | tasks=10 | batches=2,3 | preserved=42 | solver_runs=0")
        return 0
    print(f"[INFO] execution_valid={result['execution_valid']} | label_eligible={result['label_eligible']}")
    return 0 if result["execution_valid"] else 1
