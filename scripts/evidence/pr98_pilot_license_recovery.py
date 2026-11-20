"""One explicitly approved replacement of H25 job 3891 after license refusal."""

import os
import subprocess
from pathlib import Path

import pr98_hard_inputs as inputs

LICENSE_PATH = Path("/raid/vrcelestino/data/cfl-gurobi-gnn/secrets/gurobi.lic")
LICENSE_SHA256 = "50c98fadf9d6fdcb03ea4233019731e942a620c4827783b90873e2f085a63810"
PARENT_STAGE = inputs.EVIDENCE / "pr98-hard.xwo48uPi"
PARENT_SOURCE = "ecf2cf257f462555537f3c270d11d712ce64ee78"
PARENT_PREFLIGHT = "ff20f7524de8e8a5a6335101b9c69220af3ad145992e0a87898a1db174ff7bdc"
PARENT_INPUTS = "3922d7d27f6076bc3e2b2e60f28d7b0837947576e7f9ce65c4a92055ff32f687"
PARENT_JOB = "3891"
RECOVERY_CLAIM = "pr98-h25-license-recovery-3891.claim.json"
MARKER = "license-recovery.json"
need = inputs.require


def license_binding():
    need(
        os.environ.get("GRB_LICENSE_FILE") == str(LICENSE_PATH),
        "canonical_license_path",
    )
    need(LICENSE_PATH.is_file(), "canonical_license_missing")
    need(inputs.digest(LICENSE_PATH) == LICENSE_SHA256, "canonical_license_bytes")
    return {"path": str(LICENSE_PATH), "sha256": LICENSE_SHA256}


def parent_snapshot(fresh_accounting=False):
    import pr98_hard_pilot as pilot

    parent = PARENT_STAGE
    need(parent.is_dir() and not parent.is_symlink(), "preserve_parent_stage")
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    head = subprocess.check_output(
        ["git", "-C", str(parent / "source"), "rev-parse", "HEAD"],
        text=True,
        timeout=30,
        env=env,
    ).strip()
    need(head == PARENT_SOURCE, "parent_source")
    status = subprocess.check_output(
        [
            "git",
            "-C",
            str(parent / "source"),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        text=True,
        timeout=30,
        env=env,
    ).strip()
    need(not status, "parent_source_changed")
    need(
        inputs.digest(parent / "preflight.json") == PARENT_PREFLIGHT, "parent_preflight"
    )
    need(
        inputs.digest(parent / "inputs.private.json") == PARENT_INPUTS, "parent_inputs"
    )
    original = inputs.read(parent / "pilot-approval.json")
    need(
        original
        == inputs.read(inputs.EVIDENCE / "pr98-h25-technical-pilot.claim.json"),
        "parent_claim",
    )
    need(
        original["budget"] == pilot.BUDGET
        and original["preflight_sha256"] == PARENT_PREFLIGHT,
        "same_pilot_budget",
    )
    need(
        inputs.read(parent / "pilot-submission.json")
        == {
            "job_id": PARENT_JOB,
            "preflight_sha256": PARENT_PREFLIGHT,
            "scope": pilot.PILOT_SCOPE,
        },
        "parent_submission",
    )
    folder = parent / "run/pilot"
    need(
        inputs.read(folder / "preparation/root.intent.json") == {"maximum_calls": 1},
        "parent_root_intent",
    )
    for name in (
        "complete.json",
        "preparation/forward.intent.json",
        "preparation/artifact-receipt.json",
        *("preparation/" + value for value in pilot.ARTIFACTS.values()),
    ):
        need(not (folder / name).exists(), "parent_unexpected_scientific_artifact")
    for concurrent in pilot.PROFILES:
        for method in pilot.ORDER:
            trial = folder / f"c{concurrent}-{method}"
            need(not trial.exists(), "parent_evaluation_activity")
    log = folder / "preparation.console.private.log"
    need(log.stat().st_size <= 1024 * 1024, "bounded_parent_log")
    text = log.read_text(encoding="utf-8", errors="replace")
    need(
        "Model too large for size-limited license" in text
        and "model.optimize(observer)" in text,
        "parent_license_refusal",
    )
    supervision = inputs.read(folder / "preparation.supervision.private.json")
    need(
        supervision["child_exit_code"] == 1 and supervision["guard_stop"] is None,
        "parent_failure_disposition",
    )
    names = (
        "preflight.json",
        "inputs.private.json",
        "pilot-approval.json",
        "pilot-submission.json",
        "pilot-held-profile.private.json",
        "pilot-3891.private.err",
        "pilot-3891.private.out",
        "run/pilot/batch.json",
        "run/pilot/preparation/root.intent.json",
        "run/pilot/preparation.console.private.log",
        "run/pilot/preparation.supervision.private.json",
        "run/pilot/preparation/gurobi.private.log",
    )
    hashes = {}
    for name in names:
        path = parent / name
        if name.endswith("preparation/gurobi.private.log") and not path.exists():
            hashes[name] = None
        else:
            need(path.is_file() and not path.is_symlink(), "regular_parent_evidence")
            hashes[name] = inputs.digest(path)
    if fresh_accounting:
        from pr94_isolated_preparation import accounting

        job = accounting(parent, "pilot")
        need(job["job_id"] == PARENT_JOB and job["terminal"], "parent_not_terminal")
        rows = {row["JobID"]: row for row in job["rows"]}
        for name in (PARENT_JOB, PARENT_JOB + ".batch"):
            need(
                rows[name]["State"] == "FAILED" and rows[name]["ExitCode"] == "1:0",
                "parent_accounting_disposition",
            )
        need(
            rows[PARENT_JOB + ".extern"]["State"] == "COMPLETED",
            "parent_extern_accounting",
        )
    return {
        "stage": str(parent),
        "job_id": PARENT_JOB,
        "source_commit": PARENT_SOURCE,
        "original_claim_sha256": inputs.digest(
            inputs.EVIDENCE / "pr98-h25-technical-pilot.claim.json"
        ),
        "files_sha256": hashes,
    }


def approve(stage, accepted, decision):
    import pr98_hard_pilot as pilot

    need(decision.strip(), "explicit_recovery_decision")
    need(stage.resolve() != PARENT_STAGE.resolve(), "new_isolated_stage_required")
    pilot.admitted(stage, accepted)
    need(
        inputs.digest(stage / "inputs.private.json") == PARENT_INPUTS,
        "unchanged_inputs",
    )
    license_record = license_binding()
    parent = parent_snapshot(fresh_accounting=True)
    inputs.write_once(
        stage / MARKER,
        {
            "schema_version": 1,
            "parent": parent,
            "preflight_sha256": accepted,
            "license": license_record,
            "budget": pilot.BUDGET,
            "decision": decision,
            "scope": pilot.PILOT_SCOPE,
        },
    )


def claim_path(stage, fresh_accounting=False):
    import pr98_hard_pilot as pilot

    marker = stage / MARKER
    if not marker.exists():
        return inputs.EVIDENCE / "pr98-h25-technical-pilot.claim.json"
    record = inputs.read(marker)
    need(
        record["schema_version"] == 1 and record["scope"] == pilot.PILOT_SCOPE,
        "recovery_schema",
    )
    need(
        record["budget"] == pilot.BUDGET and record["decision"].strip(),
        "recovery_budget_and_decision",
    )
    need(record["license"] == license_binding(), "recovery_license")
    need(
        record["parent"] == parent_snapshot(fresh_accounting), "parent_evidence_changed"
    )
    need(
        record["preflight_sha256"] == inputs.digest(stage / "preflight.json"),
        "recovery_preflight",
    )
    need(
        inputs.digest(stage / "inputs.private.json") == PARENT_INPUTS, "recovery_inputs"
    )
    need(stage.resolve() != PARENT_STAGE.resolve(), "new_isolated_stage_required")
    return inputs.EVIDENCE / RECOVERY_CLAIM
