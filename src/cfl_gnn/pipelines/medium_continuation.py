"""Verify one unstarted medium batch without modifying the frozen PR54 solver."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from cfl_gnn.pipelines import medium_reconciliation as reconciliation

campaign, c, pilot = reconciliation.campaign, reconciliation.c, reconciliation.pilot
PLAN = "medium_continuation_preflight.json"
OUTPUTS = {
    "preserved_label_index.jsonl", "medium_continuation_tasks.jsonl",
    "medium_rescue_review.jsonl", "source_task_states.jsonl",
    "pr56_control_reuse_review.jsonl", "historical_prediction_diagnostics.jsonl",
}


def prepare(data_root, campaign_dir, run_root, reconciliation_dir, output_dir, continuation_batch=0):
    """Recheck source bytes and live task states before a single operator submission."""
    if type(continuation_batch) is not int or continuation_batch not in range(3):
        raise ValueError("continuation batch must be zero through two")
    data = Path(data_root).resolve()
    root = pilot.scoped(data, run_root, "intermediate/gurobi_expansion_campaign")
    source = pilot.scoped(data, reconciliation_dir, "analysis/medium_reconciliation")
    output = pilot.scoped(data, output_dir, "analysis/medium_continuation")
    plan = campaign.load_plan(campaign_dir)
    campaign.verify_sources(data, plan)
    report_path = source / reconciliation.REPORT
    report = c.read_json(report_path)
    keys = ("schema_version", "protocol", "seed", "source_campaign_contract_sha256", "sources",
            "implementation_sha256", "selection_implementation_sha256")
    if (report.get("gate_status") != "passed" or report.get("failures") != []
            or report.get("schema_version") != 1 or report.get("seed") != 42
            or report.get("protocol") != "medium_reconciliation_and_start_qualification_v1"
            or report.get("source_campaign_contract_sha256") != plan["contract_sha256"]
            or c.canonical_sha256({k: report[k] for k in keys}) != report.get("contract_sha256")
            or set(report.get("outputs", {})) != OUTPUTS):
        raise ValueError("passed, hash-bound reconciliation required")
    paths = [report_path]
    rows = {}
    for name in sorted(OUTPUTS):
        path = c.checked(source, report["outputs"][name])
        if path != source / name:
            raise ValueError("reconciliation output identity changed")
        paths.append(path)
        rows[name] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for path in paths:
        if re.search(r"/raid/|/home/|[A-Za-z]:\\|secrets/|gurobi\.lic", path.read_text(encoding="utf-8"), re.I):
            raise ValueError("declared reconciliation text failed sanitization")
    for descriptor in report["sources"]:
        c.checked(data, descriptor)

    admitted = list(plan["preserved"])
    pending = []
    for task in plan["tasks"]:
        c.checked(data, task["mip"])
        directory = c.safe_path(root, task["run_relative_path"])
        if directory.exists():
            receipt = campaign.verify_receipt(directory, plan, task)
            if receipt.get("execution_valid") is not True:
                raise ValueError("failed existing task requires review")
            if receipt["label_eligible"]:
                admitted.append({**campaign.identity(task), "label_format": "gurobi_parent_solution_json",
                    "solution": c.descriptor(data, c.checked(directory, receipt["artifacts"][campaign.parent.SOLUTION_NAME])),
                    "report": c.descriptor(data, directory / campaign.TASK_REPORT),
                    "mip_gap_relative": receipt["solve"]["mip_gap_relative"],
                    "execution_time_seconds": receipt["solve"]["execution_time_seconds"]})
        elif task["phase"] == "medium":
            pending.append(task)
    if rows["preserved_label_index.jsonl"] != admitted:
        raise ValueError("admitted inventory changed; regenerate reconciliation without replacing labels")
    proposed = rows["medium_continuation_tasks.jsonl"]
    pending_ids = [t["source_instance_id"] for t in pending]
    if len(proposed) != len(pending) or [r["source_instance_id"] for r in proposed] != pending_ids:
        raise ValueError("unstarted inventory changed; regenerate reconciliation")
    for index, (row, task) in enumerate(zip(proposed, pending)):
        if (any(row[k] != task[k] for k in ("source_instance_id", "phase", "task_index", "role", "fold"))
                or row["state"] != "not_started" or row["proposed_time_limit_seconds"] != 28800
                or row["continuation_batch"] != index // 5
                or row["next_action"] != "original_PR54_task_after_preflight"
                or row["automatic_submission_authorized"] is not False):
            raise ValueError("continuation identity, role, state, or budget changed")
    selected = [t for t, r in zip(pending, proposed) if r["continuation_batch"] == continuation_batch]
    original_batch = {t["batch_index"] for t in selected}
    if len(selected) != 5 or len(original_batch) != 1:
        raise ValueError("exactly one complete original five-task medium batch required")
    indices = [t["task_index"] for t in selected]
    if any(t["phase"] != "medium" or t["time_limit_seconds"] != 28800 for t in selected):
        raise ValueError("rescue and hard tasks cannot enter this submission")
    payload = dict(schema_version=1, protocol="reviewed_medium_continuation_v1", seed=42,
        objective_sense="MINIMIZE", solver="gurobi", time_limit_seconds=28800,
        threads=1, memory_gib=64, max_parallel_tasks=1, slurm_wall_hours=12,
        source_campaign_contract_sha256=plan["contract_sha256"],
        source_reconciliation=c.descriptor(data, report_path),
        implementation_sha256=c.sha256_file(Path(__file__)),
        source_outputs=[c.descriptor(data, p) for p in paths[1:]],
        preserved_labels=len(admitted), preserved_by_difficulty=dict(Counter(r["difficulty"] for r in admitted)),
        continuation_batch=continuation_batch, original_campaign_batch=next(iter(original_batch)),
        selected_tasks=selected, slurm_array=",".join(map(str, indices))+"%1",
        gate_status="passed", declared_text_sanitization="passed", solver_runs_executed=0,
        hard_campaign_authorized=False, automatic_submission_authorized=False,
        development_only=True, scientific_reporting_eligible=False)
    result = {**payload, "contract_sha256": c.canonical_sha256(payload)}
    pilot.new_directory(output)
    c.write_json(output / PLAN, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("data_root", "campaign_dir", "run_root", "reconciliation_dir", "output_dir"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--continuation_batch", type=int, default=0)
    try:
        result = prepare(**vars(parser.parse_args(argv)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"[ERROR] {c.error_reason(error)} ({type(error).__name__})")
        return 2
    print(f"[INFO] PR57_CONTINUATION_PREFLIGHT_OK | preserved={result['preserved_labels']} | "
          f"array={result['slurm_array']} | PR54_batch={result['original_campaign_batch']} | solver_runs=0")
    return 0
