"""Read-only source reconciliation and historical prediction audit for Sprint 1.

Only new audit outputs are written. No optimization, training, calibration fit,
source overwrite, automatic label promotion, or scheduler submission occurs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import math
from pathlib import Path

from cfl_gnn.pipelines import gurobi_expansion_campaign as campaign
from cfl_gnn.experiments.assignment_selection import completion_capabilities, probability

c, pilot = campaign.c, campaign.pilot
REPORT = "medium_reconciliation_report.json"
PR56_CONTRACT = "a1baebc1f8f5daadf1231f22ba4c1025d7f33f4727d90ee16754302fdd42ad47"


def prediction_diagnostics(payload, expected_parent):
    if payload.get("source_instance_id") != expected_parent or payload.get("target_labels_loaded") is not False:
        raise ValueError("prediction parent or label-free boundary changed")
    rows = payload["predictions"]
    threshold = probability(payload["threshold"])
    names = [r["variable_name"] for r in rows]
    if (not names or len(set(names)) != len(names) or any(not isinstance(n, str) or not n for n in names)
            or c.canonical_sha256(names) != payload["binary_order_sha256"]):
        raise ValueError("prediction variable identities or order hash changed")
    histogram, disagreement = [0] * 10, 0
    for row in rows:
        p = probability(row["probability"])
        value, score = int(p >= threshold), max(p, 1-p)
        if (row["predicted_value"] != value or row["confidence"] != score
                or row["priority"] != round(100 * score)):
            raise ValueError("historical prediction rule changed")
        histogram[min(9, int(p * 10))] += 1
        disagreement += int(value != int(p >= .5))
    selected = sorted(rows, key=lambda r: (-r["priority"], -r["confidence"], r["variable_name"]))[:math.ceil(.1 * len(rows))]
    positives = sum(r["predicted_value"] for r in selected)
    return dict(source_instance_id=expected_parent, binary_variables=len(rows), threshold=threshold,
        raw_score_decile_counts=histogram, decision_differs_from_half_threshold=disagreement,
        selected_assignments=len(selected), selected_positive=positives,
        selected_negative=len(selected)-positives,
        selected_high_score_assigned_zero=sum(r["predicted_value"] == 0 and r["probability"] > .5 for r in selected),
        calibration_estimated=False, corrected_starts_generated=False,
        interpretation="raw_score_and_assignment_diagnostics_not_calibrated_accuracy")


def inspect_pr56(data, audit_dir, run_root, inventory):
    audit_dir, run_root = Path(audit_dir).resolve(), Path(run_root).resolve()
    report_path = audit_dir / "easy_medium_pilot_report.json"
    report = c.read_json(report_path)
    if (report.get("contract_sha256") != PR56_CONTRACT or report.get("gate_status") != "passed"
            or report.get("failures") != [] or report.get("development_only") is not True
            or report.get("scientific_reporting_eligible") is not False
            or report.get("summary", {}).get("valid_pairs") != 2):
        raise ValueError("passed frozen PR56 audit required")
    if set(report.get("outputs", {})) != {"per_method_outcomes.json", "per_method_outcomes.csv",
            "paired_effects.json", "paired_effects.csv", "per_method_status.json", "source_ledger.json"}:
        raise ValueError("PR56 output inventory changed")
    sources = [c.descriptor(data, report_path)]
    for item in report["outputs"].values():
        sources.append(c.descriptor(data, c.checked(audit_dir, item)))
    ledger = c.read_json(c.checked(audit_dir, report["outputs"]["source_ledger.json"]))["records"]
    if len(ledger) != 2:
        raise ValueError("two PR56 receipts required")
    diagnostics, controls, seen = [], [], set()
    for item in ledger:
        receipt_path = c.checked(run_root, item)
        receipt = c.read_json(receipt_path)
        name = receipt["source_instance_id"]
        if name in seen or name not in {"CFL_medium_instance_0", "CFL_medium_instance_1"} or receipt["contract_sha256"] != PR56_CONTRACT:
            raise ValueError("unexpected PR56 receipt identity")
        seen.add(name)
        workers = receipt.get("workers", [])
        if len(workers) != 2 or {w["method"] for w in workers} != {"unguided_control", "partial_mip_start"} or any(w["returncode"] != 0 for w in workers):
            raise ValueError("PR56 workers incomplete or failed")
        sources.append(c.descriptor(data, receipt_path))
        artifacts = receipt["artifacts"]
        for artifact in artifacts.values():
            c.checked(receipt_path.parent, artifact)
        results = {}
        for method in ("unguided_control", "partial_mip_start"):
            result = c.read_json(c.checked(receipt_path.parent, artifacts[f"{method}.json"]))
            if (result.get("contract_sha256") != PR56_CONTRACT or result.get("source_instance_id") != name
                    or result.get("method") != method or result.get("gate_status") != "passed"
                    or result.get("mip_sha256") != inventory[name]["mip"]["sha256"]
                    or result.get("effective_objective_sense") != "MINIMIZE"
                    or result.get("fresh_model") is not True
                    or result.get("mathematical_model_unchanged") is not True):
                raise ValueError("PR56 method or original model mismatch")
            results[method] = result
        control, guided = results["unguided_control"], results["partial_mip_start"]
        if (control["parameters"] != guided["parameters"] or control["solver_version"] != guided["solver_version"]
                or control["mathematical_signature_sha256"] != guided["mathematical_signature_sha256"]
                or control["start"]["submitted_assignments"] != 0):
            raise ValueError("PR56 paired controls differ")
        controls.append(dict(source_instance_id=name, role=inventory[name]["role"], fold=inventory[name]["fold"],
            label_candidate=control.get("independent_feasibility", {}).get("valid") is True
                and control["solve"].get("feasible_solution") is True
                and c.eligible_gap(control["solve"].get("terminal_mip_gap_relative")),
            gap=control["solve"].get("terminal_mip_gap_relative"),
            promotion_status="review_required_no_automatic_admission",
            guidance_source="unguided_control_only", exposed_development_parent=True))
        with gzip.open(c.checked(receipt_path.parent, artifacts["predictions.json.gz"]), "rt", encoding="utf-8") as stream:
            import json
            payload = json.load(stream)
        if payload.get("contract_sha256") != PR56_CONTRACT or payload.get("mip_sha256") != inventory[name]["mip"]["sha256"]:
            raise ValueError("prediction model identity changed")
        row = prediction_diagnostics(payload, name)
        if (row["selected_assignments"] != guided["start"]["submitted_assignments"]
                or row["selected_positive"] != guided["start"]["positive_assignments"]
                or row["selected_negative"] != guided["start"]["negative_assignments"]):
            raise ValueError("selection diagnostics differ from submitted start")
        row["solver_version"] = guided["solver_version"]
        row["completion_capabilities"] = completion_capabilities(guided["solver_version"])
        diagnostics.append(row)
    return controls, diagnostics, sources


def reconcile(data_root, campaign_dir, run_root, pr56_audit_dir, pr56_run_root, output_dir):
    data = Path(data_root).resolve()
    output = pilot.scoped(data, output_dir, "analysis/medium_reconciliation")
    plan = campaign.load_plan(campaign_dir)
    campaign.verify_sources(data, plan)
    inventory = {r["source_instance_id"]: r for r in plan["preserved"] + plan["tasks"] + plan["deferred"]}
    sources = [c.descriptor(data, Path(campaign_dir) / campaign.PLAN)]
    admitted = list(plan["preserved"])
    states, failures = [], []
    for task in plan["tasks"]:
        c.checked(data, task["mip"])
        directory = c.safe_path(run_root, task["run_relative_path"])
        row = dict(source_instance_id=task["source_instance_id"], phase=task["phase"],
                   task_index=task["task_index"], role=task["role"], fold=task["fold"],
                   state="incomplete" if directory.exists() else "not_started")
        if (directory / campaign.TASK_REPORT).exists():
            try:
                receipt = campaign.verify_receipt(directory, plan, task)
                sources.append(c.descriptor(data, directory / campaign.TASK_REPORT))
                row.update(state="admitted" if receipt["label_eligible"] else "unadmitted" if receipt["execution_valid"] else "failed",
                    gap=receipt.get("solve", {}).get("mip_gap_relative"), right_censored=receipt.get("right_censored"))
                if receipt["label_eligible"]:
                    admitted.append({**campaign.identity(task), "label_format": "gurobi_parent_solution_json",
                        "solution": c.descriptor(data, c.checked(directory, receipt["artifacts"][campaign.parent.SOLUTION_NAME])),
                        "report": c.descriptor(data, directory / campaign.TASK_REPORT),
                        "mip_gap_relative": receipt["solve"]["mip_gap_relative"],
                        "execution_time_seconds": receipt["solve"]["execution_time_seconds"]})
            except (OSError, ValueError, KeyError, TypeError):
                row["state"] = "invalid_receipt"
        if row["state"] in {"failed", "invalid_receipt", "incomplete"}:
            failures.append(dict(source_instance_id=row["source_instance_id"], reason_code=row["state"]))
        states.append(row)
    known = {r["source_instance_id"] for r in admitted}
    if len(known) != len(admitted):
        raise ValueError("duplicate admitted parent")
    controls, diagnostics, prior_sources = inspect_pr56(data, pr56_audit_dir, pr56_run_root, inventory)
    sources += prior_sources
    supplementary = {r["source_instance_id"] for r in controls if r["label_candidate"]}
    pending, rescue = [], []
    for row in states:
        if row["phase"] != "medium" or row["source_instance_id"] in known:
            continue
        item = {**row, "automatic_submission_authorized": False}
        if row["source_instance_id"] in supplementary:
            item["next_action"] = "review_existing_unguided_label_before_resolve"
            rescue.append(item)
        elif row["state"] == "not_started":
            item.update(proposed_time_limit_seconds=28800, next_action="original_PR54_task_after_preflight")
            pending.append(item)
        else:
            item["next_action"] = "review_before_new_rescue_budget"
            rescue.append(item)
    for index, row in enumerate(pending):
        row["continuation_batch"] = index // 5
    payload = dict(schema_version=1, protocol="medium_reconciliation_and_start_qualification_v1", seed=42,
        source_campaign_contract_sha256=plan["contract_sha256"], sources=sources,
        implementation_sha256=c.sha256_file(Path(__file__)),
        selection_implementation_sha256=c.sha256_file(Path(__file__).parents[1] / "experiments/assignment_selection.py"))
    result = {**payload, "contract_sha256": c.canonical_sha256(payload),
        "gate_status": "failed" if failures else "passed", "failures": failures,
        "summary": dict(admitted_parents=len(admitted), admitted_by_difficulty=dict(Counter(r["difficulty"] for r in admitted)),
            medium_unstarted_tasks=len(pending), medium_review_tasks=len(rescue),
            pr56_unguided_candidates=len(supplementary), pr56_candidates_already_admitted=len(supplementary & known)),
        "eligibility": dict(development_only=True, scientific_reporting_eligible=False,
                            calibration_qualified=False, training_ready=False, automatic_submission_authorized=False),
        "decision": dict(next_gate="review_reconciled_medium_queue_and_validation_calibration_inputs",
                         solver_runs_executed=0, hard_campaign_authorized=False)}
    pilot.new_directory(output)
    artifacts = {"preserved_label_index.jsonl": admitted, "medium_continuation_tasks.jsonl": pending,
                 "medium_rescue_review.jsonl": rescue, "source_task_states.jsonl": states,
                 "pr56_control_reuse_review.jsonl": controls, "historical_prediction_diagnostics.jsonl": diagnostics}
    for name, records in artifacts.items():
        campaign.write_jsonl(output / name, records)
    result["outputs"] = {name: c.descriptor(output, output / name) for name in artifacts}
    c.write_json(output / REPORT, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("data_root", "campaign_dir", "run_root", "pr56_audit_dir", "pr56_run_root", "output_dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    try:
        result = reconcile(**vars(parser.parse_args(argv)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"[ERROR] {c.error_reason(error)} ({type(error).__name__})")
        return 2
    print(f"[INFO] gate={result['gate_status']} | preserved={result['summary']['admitted_parents']} | solver_runs=0")
    return 0 if result["gate_status"] == "passed" else 1
