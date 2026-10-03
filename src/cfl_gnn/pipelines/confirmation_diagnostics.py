"""Read-only triage of frozen-cohort rejections; never solve or admit labels.

This separate reader leaves the implementation fingerprint of an existing
confirmation campaign unchanged. Output is a diagnostic, not an admission gate.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from cfl_gnn.pipelines import confirmation_execution as c

CHECKS = (
    "parent_sha256_match", "solution_source_match", "solver_feasibility_check_space",
    "fresh_process", "zero_pre_solve_solutions", "no_warm_start", "objective_minimize",
    "feasible_solution", "online_incumbent_observed", "callback_errors_absent",
    "stream_matches_events", "stream_committed", "trace_consistent",
    "named_solution_present", "terminal_gap_finite", "four_time_regions_valid",
    "runtime_environment_recorded", "solver_parameter_contract_recorded",
)
REASONS = {
    "independent mathematical validation failed",
    "terminal gap is inconsistent with primal and dual bounds",
    "minimization dual bound exceeds the primal objective",
    "artifact unreadable or schema invalid",
    "legacy label failed independent original-MIP validation",
    "artifact missing or changed since planning", "parent identity mismatch",
    "solution source or objective policy mismatch", "duplicate variable name",
}
TIMES = ("total_wall_time_seconds", "data_read_wall_time_seconds",
         "model_build_wall_time_seconds", "model_optimize_wall_time_seconds")


def number(value):
    return value if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) else None


def repair_evidence(campaign, plan, task, budget, outcomes):
    row = {"budget_seconds": budget, "status": "missing_or_invalid_evidence"}
    try:
        repair = c.read_json(c.checked(campaign, plan["repair_plans"][str(budget)]))
        matches = [t for t in repair["tasks"] if t["solver"] == "gurobi"
                   and t["source_instance_id"] == task["source_instance_id"]]
        if len(matches) != 1:
            raise ValueError("repair task identity mismatch")
        relative = matches[0]["run_dir_relative_path"]
        c.safe_path(campaign, relative)
        root = c.safe_path(campaign, "repair_runs/" + relative)
        path = root / "gurobi_parent_solve_report.json"
        report = c.read_json(path)
        if (report["parent"]["source_instance_id"] != task["source_instance_id"]
                or report["parent"]["sha256"] != task["mip"]["sha256"]):
            raise ValueError("parent identity mismatch")
        row["report"] = c.descriptor(campaign, path)
        recorded = [o["report_sha256"] for o in outcomes if o.get("budget_seconds") == budget]
        row["recorded_report_hash_match"] = (
            row["report"]["sha256"] in recorded if recorded else None)
        if recorded and row["recorded_report_hash_match"] is not True:
            raise ValueError("repair report changed")
        solve = report.get("solve", {})
        raw_status = solve.get("solve_status")
        row["solve_status"] = raw_status if raw_status in {
            "optimal", "timelimit", "nodelimit", "infeasible", "unbounded",
            "inforunbd", "interrupted", "numeric", "suboptimal"} else "unknown"
        row["right_censored"] = row["solve_status"] in {"timelimit", "nodelimit"}
        for key in ("mip_gap_relative", "execution_time_seconds", "solution_objective", "best_bound"):
            row[key] = number(solve.get(key))
        row["time_regions"] = {key: number(report.get("time_regions", {}).get(key)) for key in TIMES}
        checks = report.get("checks", {})
        row["failed_checks"] = [key for key in CHECKS if key in checks and checks[key] is not True]
        row["missing_checks"] = [key for key in CHECKS if key not in checks]
        row["reported_label_eligible"] = report.get("eligibility", {}).get("label_eligible") is True
        artifacts = report.get("artifacts", {})
        artifact_checks = {}
        for key in ("solution", "incumbents", "variable_order"):
            try:
                item = artifacts[key]
                c.checked(root, {"relative_path": item["file_name"], "sha256": item["sha256"]})
                artifact_checks[key] = True
            except (OSError, ValueError, KeyError, TypeError):
                artifact_checks[key] = False
        row["artifact_hashes"] = artifact_checks
        if not all(artifact_checks.values()):
            row["status"] = "artifact_hash_or_presence_failure"
        elif row["failed_checks"] or row["missing_checks"]:
            row["status"] = "collector_checks_require_review"
        elif not c.eligible_gap(row["mip_gap_relative"]):
            row["status"] = "gap_above_policy_or_invalid"
        else:
            row["status"] = "review_independent_admission"
    except (OSError, ValueError, KeyError, TypeError):
        # Raw exceptions and arbitrary metadata can contain paths or credentials.
        row["evidence_error"] = "missing_changed_or_invalid_repair_evidence"
    return row


def diagnose(campaign_dir):
    campaign = Path(campaign_dir).resolve()
    plan = c.read_json(campaign / c.PLAN)
    c.validate_plan(plan)
    aggregate_path = campaign / "confirmation_execution_report.json"
    aggregate = c.read_json(aggregate_path)
    if aggregate.get("campaign_contract_sha256") != plan["contract_sha256"]:
        raise ValueError("aggregate belongs to another campaign")
    rows = aggregate["records"]
    if [r["source_instance_id"] for r in rows] != list(c.COHORT):
        raise ValueError("aggregate cohort differs from frozen plan")
    index_path = c.checked(campaign, aggregate["label_index"])
    index = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    admitted = [r["source_instance_id"] for r in rows if r.get("label_eligible") is True]
    if ([r["source_instance_id"] for r in index] != admitted
            or len(index) != aggregate["independently_admissible_parents"]):
        raise ValueError("label index disagrees with aggregate")
    # Check accepted receipts without deserializing vectors or calling a solver.
    for entry in index:
        c.checked(campaign, entry["solution"])
        c.checked(campaign, entry["report"])
    pending = []
    for task, status in zip(plan["tasks"], rows):
        if status["role"] != task["role"]:
            raise ValueError("aggregate role differs from plan")
        if status.get("label_eligible") is True:
            continue
        row = {"source_instance_id": task["source_instance_id"], "task_index": task["task_index"],
               "role": task["role"], "source_report_status": "missing_or_invalid", "source_errors": []}
        outcomes = []
        try:
            path = campaign / "labels" / task["source_instance_id"] / c.REPORT
            source = c.read_json(path)
            if (source["campaign_contract_sha256"] != plan["contract_sha256"]
                    or source["source_instance_id"] != task["source_instance_id"]
                    or source["mip_sha256"] != task["mip"]["sha256"]
                    or source["role"] != task["role"] or source["fold"] != task["fold"]):
                raise ValueError("source identity mismatch")
            row["source_report"] = c.descriptor(campaign, path)
            row["source_report_status"] = "present"
            row["reported_label_eligible"] = source.get("label_eligible") is True
            outcomes = source.get("repair_outcomes", [])
            row["source_errors"] = [
                {"budget_seconds": number(e.get("budget_seconds")),
                 "reason": e.get("reason") if e.get("reason") in REASONS else "redacted_unclassified_source_error"}
                for e in source.get("source_errors", [])]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        row["repairs"] = [repair_evidence(campaign, plan, task, budget, outcomes)
                          for budget in plan["repair_budgets_seconds"]]
        pending.append(row)
    return {"schema_version": 1, "campaign_contract_sha256": plan["contract_sha256"],
            "source_aggregate": c.descriptor(campaign, aggregate_path),
            "label_index": c.descriptor(campaign, index_path),
            "diagnostic_completed": True, "accepted_artifact_hashes_valid": True,
            "admitted_parents": len(admitted), "pending_parents": len(pending),
            "admitted_by_role": dict(Counter(r["role"] for r in rows if r.get("label_eligible") is True)),
            "pending": pending, "solver_runs_executed": 0, "source_artifacts_modified": False,
            "automatic_retry_authorized": False, "training_authorized": False,
            "development_only": True, "scientific_reporting_eligible": False,
            "next_gate": "review_source_rejection_evidence"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign_dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = diagnose(args.campaign_dir)
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"diagnostic_completed": False, "reason": "campaign_or_artifact_validation_failed"}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 0
