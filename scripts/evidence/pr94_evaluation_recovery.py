"""One explicitly authorized replacement of the closed PR94 entry failure.

Only metadata and provenance are handled here. Scientific preparation is reused;
the original claim is never removed, renamed or overwritten.
"""

import argparse
import datetime as dt
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence")
PARENT = EVIDENCE / "pr94-evaluation-10fd1af20ff4"
PARENT_SOURCE = "10fd1af20ff40c43147331e7321adf10c151a6f5"
PARENT_PLAN = "44b443a127af5ec4795e454b534aca8274c8e9a3d3d0ddb91fd67bb4cd4a9600"
ARCHIVE = EVIDENCE / (
    "pr94-closed-entry-attempt-4e8c18291c3444ec815b4872a437ca39.private.zip"
)
ARCHIVE_SHA = "e8755224290ad952846689701b1513a1d4f9d845aa53d8f9703d7830f48b7e89"
CLOSURE_SHA = "70739cff41968a551fcc507af8339aafad168176053527f9dfaa03510536a3ea"
ENTRY_SHA = "9eb631ee51d90c2e95a405c5725cde51b32aaba7706a9be2ae08dfa90c46ffe9"
ORIGINAL_CLAIM = EVIDENCE / "pr94-full-v2-evaluations.claim.json"
CLAIM = EVIDENCE / "pr94-full-v2-entry-recovery-1.claim.json"
IDS = tuple(str(i) for i in range(3785, 3833))
DOCS = "docs/research/solver-seed-extension-v2/"
ALLOWED_SOURCE_CHANGES = {
    "scripts/evidence/operate_pr94_evaluation.sh",
    "scripts/evidence/pr94_evaluation_workflow.py",
    "scripts/evidence/pr94_evaluation_recovery.py",
    DOCS + "README.md",
    DOCS + "evaluation-runbook.md",
    DOCS + "roots-author-snapshot-20261102.json",
    DOCS + "evaluation-entry-10fd1af.sh.txt",
    DOCS + "entry-recovery-approval-20261102.json",
    DOCS + "recovery-launch.template.sh",
}


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(
        b, sort_keys=True, allow_nan=False
    )


def read_small(path, limit=4 * 1024**2):
    need(path.is_file() and not path.is_symlink(), "recovery_regular_file")
    need(path.stat().st_size <= limit, "recovery_file_size")
    return path.read_bytes()


def closed_rows(rows):
    need(len(rows) == 48, "recovery_accounting_count")
    index = {r["JobIDRaw"]: r for r in rows}
    need(len(index) == 48 and set(index) == set(IDS), "recovery_accounting_ids")
    for i, job in enumerate(IDS):
        row = index[job]
        need(row["User"] == "vrcelestino", "recovery_accounting_owner")
        need(
            row["State"].split()[0].rstrip("+") == ("FAILED" if i < 4 else "CANCELLED"),
            "recovery_parent_not_closed",
        )
        need(row["ElapsedRaw"] == "0", "recovery_parent_elapsed")
        if i < 4:
            need(row["ExitCode"] == "2:0", "recovery_head_exit")


def receipt():
    need(sha(read_small(ARCHIVE)) == ARCHIVE_SHA, "recovery_archive_sha256")
    expected = {
        "original-plan.private.json",
        "original-submission.json",
        "original-approval.json",
        "original-global-claim.json",
        "closure-review.json",
        *{
            f"terminal-logs/evaluation-{job}.private.{ext}"
            for job in IDS[:4]
            for ext in ("err", "out")
        },
    }
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = archive.namelist()
        need(
            len(names) == len(set(names)) == len(expected) + 1
            and set(names) == expected | {"manifest.json"},
            "recovery_archive_members",
        )
        need(
            all(i.file_size <= 4 * 1024**2 for i in archive.infolist()),
            "recovery_member_size",
        )
        need(archive.testzip() is None, "recovery_archive_crc")
        members = {name: archive.read(name) for name in expected}
        manifest = json.loads(archive.read("manifest.json"))
    need(
        manifest == {"sha256": {k: sha(v) for k, v in members.items()}},
        "recovery_manifest",
    )
    need(sha(members["original-plan.private.json"]) == PARENT_PLAN, "recovery_plan_sha")
    need(sha(members["closure-review.json"]) == CLOSURE_SHA, "recovery_closure_sha")
    plan = json.loads(members["original-plan.private.json"])
    need(plan["source"]["commit"] == PARENT_SOURCE, "recovery_parent_source")
    expected_claim = {
        "plan_sha256": PARENT_PLAN,
        "source_commit": PARENT_SOURCE,
        "maximum_evaluations": 144,
        "maximum_submissions": 48,
        "concurrency_ceiling": 4,
        "automatic_retry": False,
        "explicit_author_CLI": True,
    }
    for name in ("original-approval.json", "original-global-claim.json"):
        need(json.loads(members[name]) == expected_claim, "recovery_original_claim")
    submission = json.loads(members["original-submission.json"])
    need(submission["plan_sha256"] == PARENT_PLAN, "recovery_submission_plan")
    need(
        tuple(r["job_id"] for r in submission["jobs"]) == IDS, "recovery_submission_ids"
    )
    closure = json.loads(members["closure-review.json"])
    closed_rows(closure["accounting"])
    need(
        closure["all_48_terminal"] is True
        and closure["failure_before_python_worker"] is True
        and closure["durable_optimize_intents"] == []
        and closure["run_file_names"] == []
        and closure["source_commit"] == PARENT_SOURCE
        and closure["plan_sha256"] == PARENT_PLAN
        and closure["entry_sha256"] == ENTRY_SHA,
        "recovery_closure_evidence",
    )
    for job in IDS[:4]:
        for ext in ("err", "out"):
            value = members[f"terminal-logs/evaluation-{job}.private.{ext}"]
            need(
                value == (b"PR94_EVALUATION_INVALID_STAGE\n" if ext == "err" else b""),
                "recovery_head_log",
            )
    return plan, members


def record():
    receipt()
    return {
        "attempt": "entry-recovery-1",
        "human_decision_date": "2026-11-02",
        "human_decision": "Autorizar a recuperação técnica descrita",
        "parent_source_commit": PARENT_SOURCE,
        "parent_plan_sha256": PARENT_PLAN,
        "parent_archive_sha256": ARCHIVE_SHA,
        "parent_closure_sha256": CLOSURE_SHA,
        "parent_jobs": list(IDS),
        "original_claim_preserved": True,
        "scientific_cells_changed": False,
        "automatic_retry": False,
    }


def validate_current(command):
    _, members = receipt()
    current = {
        "original-plan.private.json": PARENT / "plan.json",
        "original-submission.json": PARENT / "submission.json",
        "original-approval.json": PARENT / "approval.json",
        "original-global-claim.json": ORIGINAL_CLAIM,
    }
    for name, path in current.items():
        need(read_small(path) == members[name], "recovery_original_bytes_changed")
    for job in IDS[:4]:
        for ext in ("err", "out"):
            name = f"evaluation-{job}.private.{ext}"
            need(
                read_small(PARENT / name) == members["terminal-logs/" + name],
                "recovery_current_log",
            )
    need(
        sha(read_small(PARENT / "source/scripts/evidence/operate_pr94_evaluation.sh"))
        == ENTRY_SHA,
        "recovery_current_entry",
    )
    need(
        command(["git", "-C", str(PARENT / "source"), "rev-parse", "HEAD"])
        == PARENT_SOURCE,
        "recovery_current_source",
    )
    need(
        not list((PARENT / "claims").glob("*.optimize.json")),
        "recovery_unexpected_intent",
    )
    need(
        not any(p.is_file() for p in (PARENT / "run").rglob("*")),
        "recovery_unexpected_worker",
    )
    raw = command(
        [
            "sacct",
            "--allocations",
            "--noheader",
            "--parsable2",
            "-j",
            ",".join(IDS),
            "--format=JobIDRaw%40,User%40,State%80,ExitCode,ElapsedRaw",
        ]
    )
    rows = []
    for line in raw.splitlines():
        values = [v.strip() for v in line.split("|")]
        if len(values) == 6 and values[-1] == "":
            values.pop()
        need(len(values) == 5, "recovery_current_accounting_columns")
        rows.append(
            dict(zip(("JobIDRaw", "User", "State", "ExitCode", "ElapsedRaw"), values))
        )
    closed_rows(rows)
    return {
        "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "FAILED": 4,
        "CANCELLED": 44,
        "original_bytes_unchanged": True,
        "worker_evidence_absent": True,
    }


def equivalence(plan):
    """Review every semantic field against the exact previously accepted plan."""
    parent, _ = receipt()
    extra = {"recovery_record", "recovery_validation"}
    need(set(plan) == set(parent) | extra, "recovery_plan_keys")
    variable = {"source", "site", "storage"}
    for key in set(parent) - variable:
        need(
            same(plan[key], parent[key]),
            "recovery_scientific_or_resource_change_" + key,
        )
    need(same(plan["recovery_record"], record()), "recovery_record_changed")
    need(set(plan["source"]) == set(parent["source"]), "recovery_source_keys")
    need(
        re.fullmatch("[0-9a-f]{40}", plan["source"]["commit"]) is not None,
        "recovery_new_commit",
    )
    old, new = parent["source"]["sha256_lf"], plan["source"]["sha256_lf"]
    changes = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    need(
        changes <= ALLOWED_SOURCE_CHANGES and set(old) <= set(new),
        "recovery_unreviewed_source_change",
    )
    need(
        {k: v for k, v in plan["site"].items() if k != "query_utc"}
        == {k: v for k, v in parent["site"].items() if k != "query_utc"},
        "recovery_site_policy_changed",
    )
    need(set(plan["storage"]) == set(parent["storage"]), "recovery_storage_keys")
    for key in set(parent["storage"]) - {"workspace_bytes"}:
        need(
            plan["storage"][key] == parent["storage"][key],
            "recovery_storage_policy_changed",
        )
    need(
        type(plan["storage"]["workspace_bytes"]) is int
        and 0 <= plan["storage"]["workspace_bytes"] <= 256 * 1024**3,
        "recovery_workspace",
    )
    need(
        plan["recovery_validation"]["FAILED"] == 4
        and plan["recovery_validation"]["CANCELLED"] == 44
        and plan["recovery_validation"]["original_bytes_unchanged"] is True
        and plan["recovery_validation"]["worker_evidence_absent"] is True,
        "recovery_validation",
    )
    return {
        "parent_plan_sha256": PARENT_PLAN,
        "same_scientific_and_resource_fields": True,
        "source_changes": sorted(changes),
        "private_inputs_sha256": plan["private_inputs_sha256"],
        "automatic_retry": False,
    }


def review(stage, plan, write, encoded):
    report = equivalence(plan)
    report.update(
        plan_sha256=sha((stage / "plan.json").read_bytes()),
        source_commit=plan["source"]["commit"],
        review_kind="strict_equivalence_to_previously_reviewed_plan",
        scientific_reporting_eligible=False,
    )
    write(stage / "recovery-plan-review.json", report)
    return report


def require_review(stage, plan):
    report = json.loads(read_small(stage / "recovery-plan-review.json"))
    expected = {
        **equivalence(plan),
        "plan_sha256": sha((stage / "plan.json").read_bytes()),
        "source_commit": plan["source"]["commit"],
        "review_kind": "strict_equivalence_to_previously_reviewed_plan",
        "scientific_reporting_eligible": False,
    }
    need(report == expected, "recovery_plan_review_missing_or_changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    args = parser.parse_args()
    import pr94_evaluation_workflow as flow

    stage = flow.stage_path(args.stage)
    plan = flow.load(stage)
    if (stage / "submission.json").exists():
        print(json.dumps(flow.accounting(stage), indent=2))
        return
    need(not CLAIM.exists(), "recovery_claim_exists_preserve_diagnose")
    report = review(stage, plan, flow.write, flow.encoded)
    print("PR94_RECOVERY_REVIEWED_PLAN_SHA256=" + report["plan_sha256"], flush=True)
    result = flow.submit(stage, report["plan_sha256"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
