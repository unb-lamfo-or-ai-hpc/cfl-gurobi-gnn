"""One operator-invoked continuation after verified pre-executor failure.

No prompt or automatic retry. Old approvals, claims, sources and logs remain
untouched. A fresh successor is bound to job3485 and the recorded budget.
"""

import argparse
import json
import os

import paired_budget_authorization as budget
import paired_matrix_workflow_v2 as predecessor_flow
import paired_matrix_workflow_v3 as flow
import recover_pr78_job3481 as previous

AUTH_SHA = previous.AUTH_SHA
OLD_HEAD = "173b63d62658731678357772fa2d3bba48f9bc81"
OLD_MATRIX_SHA = "d17184004a1d22b425452d70d76d04722642914377bd002cbd2a6cbd9c449519"
OLD_OPERATOR_SHA = "6b81cd2d9ec6459e85e9da257883653c64d7ff8c2fb29fb3b32cffe55f6c8313"
RETURN_SHA = "c66cf6b3d10df04a443f371f070432c98edb4a5f10bef6ace5f8c9260bd7ac22"
require = flow.require


def absent(path):
    require(not path.exists() and not path.is_symlink())


def predecessor():
    root = flow.matrix.adapter.EVIDENCE_ROOT
    directory = flow.site.location(root / "pr78/recovery-job3481-v2/flow")
    source = flow.site.location(root / "pr78/recovery-source-173b63d62658")
    git = ["git", "-c", "safe.directory=" + str(source), "-C", str(source)]
    require(flow.site.command([*git, "rev-parse", "HEAD"]).strip() == OLD_HEAD)
    require(
        not flow.site.command([*git, "status", "--porcelain", "--untracked-files=all"])
    )
    plan = predecessor_flow.validate_plan(flow.load(directory / "operator_plan.json"))
    require(plan["source_commit"] == OLD_HEAD)
    for name, sha in plan["dependency_sha256"].items():
        path = (
            source / name
            if name.startswith("scripts/")
            else source / "scripts/evidence" / name
        )
        require(flow.digest(path) == sha)
    require(flow.digest(directory / "approval.json") == OLD_MATRIX_SHA)
    require(flow.digest(directory / "operator_approval.json") == OLD_OPERATOR_SHA)
    result = predecessor_flow.validate_return(directory / "return-easy", RETURN_SHA)
    require(result["accounting"]["job_id"] == "3482")
    require(result["parent_evidence_state"] == "unavailable")
    require(result["pause_remaining_matrix"] is True)
    require(result["matrix_approval_sha256"] == OLD_MATRIX_SHA)
    require(result["operator_approval_sha256"] == OLD_OPERATOR_SHA)
    state = predecessor_flow.state_for(directory, "easy")
    for marker in ("batch.started", "release.started", "released.json"):
        require(flow.load(state / marker) == {"job_id": "3482"})
    for name, sha in {
        "slurm-3482.private.err": "3e3cab03da3895bb5a1ee8cd28d7ebd3a164ccedf85809ac8d4620436d5f79e2",
        "slurm-3482.private.out": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }.items():
        require(
            flow.digest(state / name) == sha
        )  # Fingerprints only, never print text.
    for path in (
        directory / "easy",
        directory / "medium",
        directory / "operator-state/medium",
        root / "paired-matrix-locks" / OLD_MATRIX_SHA,
        predecessor_flow.root_for(OLD_OPERATOR_SHA) / "medium.started",
    ):
        absent(path)
    require(
        flow.load(predecessor_flow.root_for(OLD_OPERATOR_SHA) / "STOP.json")["code"]
        == "batch_failed"
    )
    prior_recovery = flow.load(directory.parent / "recovery.json")
    require(prior_recovery["prior_authorization_sha256"] == AUTH_SHA)
    require(prior_recovery["successor_operator_approval_sha256"] == OLD_OPERATOR_SHA)
    require(prior_recovery["successor_matrix_approval_sha256"] == OLD_MATRIX_SHA)
    auth = root / "paired-budget-authorization-locks" / AUTH_SHA / "authorization.json"
    require(flow.digest(auth) == AUTH_SHA)
    qualification = root / "pr78/hierarchical-memory-job3484-v1/qualification.json"
    require(flow.digest(qualification) == flow.matrix.evidence.QUALIFICATION_SHA)
    flow.matrix.evidence.review(flow.SOURCE)
    accounting = flow.site.parse_accounting(
        flow.site.command(
            [
                "sacct",
                "--noheader",
                "--parsable2",
                "-j",
                "3482",
                "--format=" + flow.site.FIELDS,
            ]
        ),
        "3482",
    )
    flow.validate_accounting(accounting)
    by_id = {r["JobID"]: r for r in accounting["rows"]}
    require(set(by_id) == {"3482", "3482.batch", "3482.extern", "3482.0"})
    for name in ("3482", "3482.batch", "3482.0"):
        require(by_id[name]["State"] == "FAILED" and by_id[name]["ExitCode"] == "2:0")
        require(by_id[name]["ElapsedRaw"] <= 1)
    require(by_id["3482.extern"]["State"] == "COMPLETED")
    require(by_id["3482.extern"]["ExitCode"] == "0:0")
    # Frozen run_parent obtains a matrix claim before creating attempts or
    # invoking any solver. Absence is rechecked; do not relabel old accounting.
    return accounting


def stage_path():
    return flow.matrix.adapter.EVIDENCE_ROOT / "pr78/recovery-job3482-v3"


def prepare():
    flow.site.host()
    require(not os.environ.get("SLURM_JOB_ID"))
    head = flow.site.source_head()
    ci = previous.review_ci(head)
    accounting = predecessor()
    profile = flow.site_profile()
    root = flow.matrix.adapter.EVIDENCE_ROOT
    stage = flow.site.location(stage_path())
    absent(stage)
    flow.write(
        root / "pr78/job3482-recovery.claim",
        {"source_commit": head, "prior_authorization_sha256": AUTH_SHA},
    )
    flow.mkdir(stage)
    directory = stage / "flow"
    plan = flow.prepare(directory)
    execution = flow.matrix.load_flow(directory)
    approval = flow.matrix.approval_template(execution)
    for flag in (
        "explicit_resource_budget_and_submission_approved",
        "exact_head_four_ci_arms_reviewed",
        "installed_no_solver_fault_probe_reviewed",
    ):
        approval[flag] = True
    matrix_sha = flow.contract.sha(flow.contract.encoded(approval))
    flow.matrix.validate_approval(execution, approval, matrix_sha)
    operator = flow.approval_template(plan)
    operator.update(
        matrix_approval_sha256=matrix_sha,
        explicit_resource_budget_and_submission_approved=True,
        exact_head_four_ci_arms_reviewed=True,
    )
    operator_sha = flow.contract.sha(flow.contract.encoded(operator))
    flow.validate_approval(plan, operator, operator_sha, matrix_sha)
    budget.replace_false_approval(
        directory / "approval.json", flow.matrix.approval_template(execution), approval
    )
    budget.replace_false_approval(
        directory / "operator_approval.json", flow.approval_template(plan), operator
    )
    receipt = {
        "schema_version": 1,
        "source_commit": head,
        "prior_authorization_sha256": AUTH_SHA,
        "predecessor_failed_job": "3482",
        "predecessor_runtime_not_entered_verified": True,
        "predecessor_return_sha256": RETURN_SHA,
        "predecessor_accounting": accounting,
        "installed_hierarchical_qualification_sha256": flow.matrix.evidence.QUALIFICATION_SHA,
        "site_profile": profile,
        "ci_checks": ci,
        "successor_operator_plan_sha256": plan["operator_plan_sha256"],
        "successor_operator_approval_sha256": operator_sha,
        "successor_matrix_approval_sha256": matrix_sha,
        "historical_matrix_submission_ceiling": 4,
        "successor_submission_ceiling": 2,
        "maximum_optimization_calls": 10,
        "maximum_optimization_seconds": 36000,
        "automatic_retry": False,
        "scientific_reporting_eligible": False,
    }
    flow.write(stage / "recovery.json", receipt)
    flow.approved(directory, operator_sha)
    return {
        "directory": str(directory),
        "approval_sha256": operator_sha,
        "recovery_sha256": flow.digest(stage / "recovery.json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "submit-easy", "status", "collect")
    )
    args = parser.parse_args()
    os.umask(0o077)
    stage = stage_path()
    directory = stage / "flow"
    if args.action == "prepare":
        result = prepare()
    elif args.action == "submit-easy":
        receipt = flow.load(stage / "recovery.json")
        predecessor()
        previous.review_ci(flow.site.source_head())
        result = flow.submit(
            directory, receipt["successor_operator_approval_sha256"], "easy"
        )
    elif args.action == "status":
        result = flow.status(directory, "easy")
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
                    "instruction": "preserve_evidence_and_return_output_no_retry",
                }
            )
        )
        raise SystemExit(2) from None
