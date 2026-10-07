"""One explicit recovery of cancelled, never-started job 3481; no CLI prompt.

Reuses the human approval already recorded, preserves the predecessor, and
prepares a fresh source-bound successor. Submission remains a separate action.
SPDX-License-Identifier: MIT
"""

import argparse
import json
import os
import urllib.request

import paired_budget_authorization as previous
import paired_matrix_workflow_v2 as flow

AUTH_SHA = "ad80043db2f5ae46bd4e957f2a68ec6440736386a5ebb6e712b66380e58cfc9c"
OPERATOR_SHA = "2c117f2bc9325673f80a633e185f33709ae90de2faf37b0c020030f913c2971d"
MATRIX_SHA = "89650a62b9fea5fe197bbd4c008a93e5001d33d3e5abecdf5394f96c4b85fd34"
SUBMISSION_SHA = "8e5cd5770a7af34e5079a92d58440d7a6b5c67c46add9ea499299ca0efcbb890"
DIAGNOSTIC_SHA = "c82585b53037d2c68262a3d0a0d630038c7e0487ba05c5e4b20f699b3ec0ef49"
require = flow.require


def review_ci(head):
    url = (
        "https://api.github.com/repos/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/commits/"
        + head
        + "/check-runs?per_page=100"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "pr78-recovery-review",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(1024 * 1024 + 1)
    require(len(raw) <= 1024 * 1024)
    data = json.loads(raw)
    expected = {
        f"verify ({system}-latest, {version})"
        for system in ("ubuntu", "windows")
        for version in ("3.10", "3.12")
    }
    latest = {}
    for check in data["check_runs"]:
        if check["name"] in expected and (
            check["name"] not in latest or check["id"] > latest[check["name"]]["id"]
        ):
            latest[check["name"]] = check
    require(set(latest) == expected)
    require(
        all(
            c["head_sha"] == head
            and c["status"] == "completed"
            and c["conclusion"] == "success"
            and c["app"]["slug"] == "github-actions"
            for c in latest.values()
        )
    )
    return {
        name: {"id": c["id"], "conclusion": c["conclusion"]}
        for name, c in sorted(latest.items())
    }


def cancelled_without_start(text):
    rows = [line.split("|") for line in text.strip().splitlines() if line.strip()]
    require(len(rows) == 1 and len(rows[0]) == 4)
    job, state, elapsed, start = rows[0]
    require(job == "3481" and state.split(" by ", 1)[0] == "CANCELLED")
    require(elapsed == "0" and start in {"None", "Unknown", ""})
    return {
        "job_id": job,
        "state": "CANCELLED",
        "elapsed_seconds": 0,
        "start": None,
        "step_rows": 0,
    }


def predecessor():
    root = flow.matrix.adapter.EVIDENCE_ROOT
    directory = flow.site.location(root / "pr76/operator-ad4800505bae/flow")
    plan = previous.review(directory.parent / "pr76_operator_preparation.json")
    previous.verify_original_source(directory.parent / "source", plan)
    require(flow.digest(directory / "operator_approval.json") == OPERATOR_SHA)
    require(flow.digest(directory / "approval.json") == MATRIX_SHA)
    previous.flow.validate_approval(
        plan, flow.load(directory / "operator_approval.json"), OPERATOR_SHA, MATRIX_SHA
    )
    execution = flow.matrix.load_flow(directory, MATRIX_SHA)
    require(execution["plan_sha256"] == previous.MATRIX_SHA)
    authorization = (
        root / "paired-budget-authorization-locks" / AUTH_SHA / "authorization.json"
    )
    previous.validate_authorization(directory, authorization, AUTH_SHA)
    state = previous.flow.state_for(directory, "easy")
    require(flow.digest(state / "submission.json") == SUBMISSION_SHA)
    submission = flow.load(state / "submission.json")
    require(submission["job_id"] == "3481" and submission["parent"] == "easy")
    require(submission["operator_approval_sha256"] == OPERATOR_SHA)
    for name in (
        "held_profile.json",
        "release.started",
        "released.json",
        "batch.started",
    ):
        require(not (state / name).exists() and not (state / name).is_symlink())
    for path in (
        directory / "easy",
        directory / "medium",
        directory / "operator-state/medium",
        root / "paired-matrix-locks" / MATRIX_SHA,
    ):
        require(not path.exists() and not path.is_symlink())
    old_lock = previous.flow.root_for(OPERATOR_SHA)
    require(flow.load(old_lock / "STOP.json")["code"] == "submission_uncertain")
    require(
        flow.load(old_lock / "binding.json")
        == previous.flow.binding(directory, plan, OPERATOR_SHA, MATRIX_SHA)
    )
    require(flow.load(old_lock / "easy.started") == {"easy_review_sha256": None})
    require(not (old_lock / "medium.started").exists())
    diagnostic_path = root / "pr78/site-job3481-GgvTR0mZ/site-job3481.json"
    require(flow.digest(diagnostic_path) == DIAGNOSTIC_SHA)
    diagnostic = flow.load(diagnostic_path)
    require(diagnostic["job_id"] == "3481")
    accounting = cancelled_without_start(
        flow.site.command(
            [
                "sacct",
                "--noheader",
                "--parsable2",
                "-j",
                "3481",
                "--format=JobIDRaw,State,ElapsedRaw,Start",
            ]
        )
    )
    return accounting


def prepare():
    flow.site.host()
    require(not os.environ.get("SLURM_JOB_ID"))
    head = flow.site.source_head()
    ci = review_ci(head)
    accounting = predecessor()
    site_profile = flow.site_profile()
    root = flow.matrix.adapter.EVIDENCE_ROOT
    stage = flow.site.location(root / "pr78/recovery-job3481-v2")
    require(not stage.exists())
    # Stable claim prevents preparation at another head from creating another retry.
    claim = root / "pr78/job3481-recovery.claim"
    flow.write(claim, {"source_commit": head, "prior_authorization_sha256": AUTH_SHA})
    flow.mkdir(stage)
    directory = stage / "flow"
    plan = flow.prepare(directory)
    execution = flow.matrix.load_flow(directory)
    matrix_approval = flow.matrix.approval_template(execution)
    for flag in (
        "explicit_resource_budget_and_submission_approved",
        "exact_head_four_ci_arms_reviewed",
        "installed_no_solver_fault_probe_reviewed",
    ):
        matrix_approval[flag] = True
    matrix_sha = flow.contract.sha(flow.contract.encoded(matrix_approval))
    flow.matrix.validate_approval(execution, matrix_approval, matrix_sha)
    approval = flow.approval_template(plan)
    approval.update(
        matrix_approval_sha256=matrix_sha,
        explicit_resource_budget_and_submission_approved=True,
        exact_head_four_ci_arms_reviewed=True,
    )
    approval_sha = flow.contract.sha(flow.contract.encoded(approval))
    flow.validate_approval(plan, approval, approval_sha, matrix_sha)
    previous.replace_false_approval(
        directory / "approval.json",
        flow.matrix.approval_template(execution),
        matrix_approval,
    )
    previous.replace_false_approval(
        directory / "operator_approval.json", flow.approval_template(plan), approval
    )
    receipt = {
        "schema_version": 1,
        "source_commit": head,
        "prior_authorization_sha256": AUTH_SHA,
        "predecessor_cancelled_job": "3481",
        "predecessor_no_start_verified": True,
        "predecessor_accounting": accounting,
        "predecessor_submission_sha256": SUBMISSION_SHA,
        "site_diagnostic_sha256": DIAGNOSTIC_SHA,
        "site_profile": site_profile,
        "ci_checks": ci,
        "successor_operator_plan_sha256": plan["operator_plan_sha256"],
        "successor_operator_approval_sha256": approval_sha,
        "successor_matrix_approval_sha256": matrix_sha,
        "historical_submission_ceiling": 3,
        "successor_submission_ceiling": 2,
        "maximum_optimization_calls": 10,
        "maximum_optimization_seconds": 36000,
        "automatic_retry": False,
        "scientific_reporting_eligible": False,
    }
    flow.write(stage / "recovery.json", receipt)
    flow.approved(directory, approval_sha)
    return {
        "directory": str(directory),
        "approval_sha256": approval_sha,
        "recovery_sha256": flow.digest(stage / "recovery.json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "submit-easy", "status", "collect")
    )
    args = parser.parse_args()
    os.umask(0o077)
    stage = flow.matrix.adapter.EVIDENCE_ROOT / "pr78/recovery-job3481-v2"
    directory = stage / "flow"
    if args.action == "prepare":
        result = prepare()
    elif args.action == "submit-easy":
        receipt = flow.load(stage / "recovery.json")
        predecessor()  # Cancellation and original absence of execution remain required.
        result = flow.submit(
            directory, receipt["successor_operator_approval_sha256"], "easy"
        )
    elif args.action == "status":
        result = flow.status(directory, "easy")
        state = flow.state_for(directory, "easy")
        if (state / "submission_failure.json").exists():
            result["submission_failure"] = flow.load(state / "submission_failure.json")
        result["release_recorded"] = (state / "released.json").is_file()
    else:
        result = flow.collect(directory, "easy")
    print(flow.contract.encoded(result).decode(), end="")


if __name__ == "__main__":
    try:
        main()
    except flow.SubmissionError as exc:
        print(flow.contract.encoded(exc.report).decode(), end="")
        raise SystemExit(2) from None
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": "recovery_stopped",
                    "cause_type": type(exc).__name__,
                    "instruction": "preserve_evidence_and_return_output",
                }
            )
        )
        raise SystemExit(2) from None
