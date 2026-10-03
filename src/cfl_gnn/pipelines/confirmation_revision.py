"""Explicitly approved 39-parent development cohort; the 42-parent gate is immutable."""
from pathlib import Path

from cfl_gnn.pipelines import confirmation_execution as c
from cfl_gnn.training.gasse_reconnected import read_jsonl

NAME = "confirmation_cohort_revision.json"
EXCLUDED = ("CFL_medium_instance_3", "CFL_medium_instance_5", "CFL_medium_instance_6")
COHORT = tuple(identity for identity in c.COHORT if identity not in EXCLUDED)
COUNTS = {"train": 23, "validation": 8, "test": 8}
POLICY = {
    "revision_id": "approved_39_parent_development_v1",
    "approval_date": "2026-09-13", "approval_basis": "explicit_maintainer_approval",
    "original_cohort": list(c.COHORT), "cohort": list(COHORT),
    "excluded_parents": list(EXCLUDED), "partition_counts": COUNTS,
    "exclusion_reason": "terminal_gap_above_10_percent_after_14400_seconds",
    "selection_bias": "conditions_on_solver_label_admissibility_not_representative_of_all_42",
    "seed": 42, "epochs": 100, "maximum_label_mip_gap_relative": .1,
    "original_campaign_remains_incomplete": True, "development_only": True,
    "scientific_reporting_eligible": False,
}


def source_snapshot(campaign_dir):
    campaign = Path(campaign_dir).resolve()
    plan = c.read_json(campaign / c.PLAN)
    c.validate_plan(plan)
    path = campaign / "confirmation_execution_report.json"
    report = c.read_json(path)
    if (report.get("campaign_contract_sha256") != plan["contract_sha256"]
            or report.get("gate_status") != "incomplete"
            or report.get("label_inventory_ready") is not False
            or report.get("independently_admissible_parents") != 39):
        raise ValueError("revision requires the incomplete 39-of-42 source receipt")
    statuses = report["records"]
    if ([r["source_instance_id"] for r in statuses] != list(c.COHORT)
            or [r["source_instance_id"] for r in statuses if r.get("label_eligible") is True] != list(COHORT)):
        raise ValueError("source exclusions differ from the approved revision")
    index_path = c.checked(campaign, report["label_index"])
    rows = read_jsonl(index_path)
    if [r["source_instance_id"] for r in rows] != list(COHORT):
        raise ValueError("revision label index differs from approved cohort")
    tasks = {t["source_instance_id"]: t for t in plan["tasks"]}
    from cfl_gnn.paths import PROJECT_ROOT
    from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold
    folds = {e.source_instance_id: e for e in read_manifest(PROJECT_ROOT / "configs/splits/cfl_90_seed42_folds.csv")}
    for row in rows:
        task, entry = tasks[row["source_instance_id"]], folds[row["source_instance_id"]]
        if (row["mip"] != task["mip"] or row["fold"] != task["fold"] or row["fold"] != entry.fold
                or row["role"] != task["role"] or row["role"] != role_for_fold(entry.fold, 0)
                or row.get("label_eligible") is not True or not c.eligible_gap(row["mip_gap_relative"])):
            raise ValueError("revision label identity or admission mismatch")
    if {role: sum(r["role"] == role for r in rows) for role in COUNTS} != COUNTS:
        raise ValueError("revision partition counts changed")
    snapshot = {"source_campaign_contract_sha256": plan["contract_sha256"],
                "source_plan": c.descriptor(campaign, campaign / c.PLAN),
                "source_report": c.descriptor(campaign, path),
                "label_index": c.descriptor(campaign, index_path)}
    return snapshot, plan, report, rows


def prepare(campaign_dir, revision_dir):
    from cfl_gnn.pipelines.confirmation_diagnostics import diagnose
    output, campaign = Path(revision_dir).resolve(), Path(campaign_dir).resolve()
    if output == campaign or output.is_relative_to(campaign) or campaign.is_relative_to(output):
        raise ValueError("revision must be separate from the original campaign")
    if output.exists() and any(output.iterdir()):
        raise ValueError("use a new revision directory")
    snapshot, _, _, _ = source_snapshot(campaign)
    diagnostic = diagnose(campaign)
    for pending in diagnostic["pending"]:
        evidence = next(r for r in pending["repairs"] if r["budget_seconds"] == 14400)
        if (evidence["status"] != "gap_above_policy_or_invalid"
                or evidence.get("recorded_report_hash_match") is not True
                or evidence.get("solve_status") != "timelimit"
                or evidence.get("mip_gap_relative") is None or evidence["mip_gap_relative"] <= .1):
            raise ValueError("revision exclusion evidence does not match approved rationale")
    evidence_path = output / "source_rejection_evidence.json"
    c.write_json(evidence_path, diagnostic)
    payload = {"schema_version": 1, **POLICY, **snapshot,
               "exclusion_evidence": c.descriptor(output, evidence_path)}
    result = {**payload, "contract_sha256": c.canonical_sha256(payload)}
    c.write_json(output / NAME, result)
    return result


def load(campaign_dir, revision_dir):
    output = Path(revision_dir).resolve()
    revision = c.read_json(output / NAME)
    payload = {k: v for k, v in revision.items() if k != "contract_sha256"}
    if c.canonical_sha256(payload) != revision.get("contract_sha256") or any(revision.get(k) != v for k, v in POLICY.items()):
        raise ValueError("cohort revision contract or approved policy changed")
    snapshot, plan, report, rows = source_snapshot(campaign_dir)
    if any(revision.get(k) != v for k, v in snapshot.items()):
        raise ValueError("original source campaign changed after revision")
    c.checked(output, revision["exclusion_evidence"])
    return revision, plan, report, rows
