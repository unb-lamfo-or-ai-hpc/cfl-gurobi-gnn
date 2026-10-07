"""One explicit full-medium continuation; preserve easy and all old stops.

Prepare is solver-free. Approval is a separate CLI action with a bounded budget
flag. Submit, status and collect are one-shot; there is no automatic retry.
SPDX-License-Identifier: MIT
"""

import argparse
import os
import re
import signal
import sys
import time
from pathlib import Path

import pr78_medium_continuation_plan as proposal
import recover_pr78_job3481 as ci

matrix, previous = proposal.successor, proposal.historical
old, contract, require = proposal.old, proposal.contract, proposal.require
site = previous.site
PROTOCOL = "pr78_full_medium_nonblocking_v1"
BATCH = "scripts/slurm/dasci/submit_pr78_medium.sbs"
load, write, digest = previous.load, previous.write, previous.digest


def predecessor_paths(directory):
    return tuple(Path(directory) / "predecessor" / p for p in ("easy", "medium"))


def plan_for(head, directory):
    prepared = proposal.compile_plan(head, *predecessor_paths(directory), "full-medium")
    value = {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "source_commit": head,
        "proposal": prepared,
        "dependency_sha256": {
            **prepared["dependency_sha256"],
            "pr78_medium_workflow.py": digest(Path(__file__)),
            "recover_pr78_job3481.py": digest(
                Path(__file__).with_name("recover_pr78_job3481.py")
            ),
            BATCH: digest(site.SOURCE / BATCH),
        },
        "maximum_submissions": 1,
        "maximum_optimization_calls": 5,
        "resource_budget_approved": False,
        "scientific_reporting_eligible": False,
    }
    value["plan_sha256"] = contract.sha(contract.encoded(value))
    return value


def validate_plan(value, directory):
    expected = plan_for(value["source_commit"], directory)
    require(contract.encoded(value) == contract.encoded(expected))
    return value


def approval_template(plan):
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "plan_sha256": plan["plan_sha256"],
        "source_commit": plan["source_commit"],
        "predecessor_medium_return_sha256": proposal.RETURNS["medium"],
        "maximum_new_submissions": 1,
        "maximum_new_optimization_calls": 5,
        "maximum_new_solver_seconds": 18000,
        "maximum_new_wall_seconds": 19800,
        "successor_campaign_submission_ceiling": 3,
        "successor_campaign_reserved_optimization_ceiling": 11,
        "successor_campaign_reserved_solver_seconds_ceiling": 39600,
        "explicit_additional_medium_budget_approved": False,
        "four_exact_head_ci_arms_reviewed": False,
        "automatic_retry": False,
        "scientific_reporting_eligible": False,
    }


def validate_approval(plan, approval, sha):
    old.hexadecimal(sha)
    expected = approval_template(plan)
    expected["explicit_additional_medium_budget_approved"] = True
    expected["four_exact_head_ci_arms_reviewed"] = True
    require(contract.encoded(approval) == contract.encoded(expected))
    require(contract.sha(contract.encoded(approval)) == sha)


def campaign_root():
    # Source, scope, approval and output changes never create a new entitlement.
    root = (
        matrix.adapter.EVIDENCE_ROOT
        / "pr78-medium-continuation-locks"
        / proposal.RETURNS["medium"]
    )
    require(root.resolve() == root)
    return root


def binding(directory, plan, sha):
    return {
        "plan_sha256": plan["plan_sha256"],
        "approval_sha256": sha,
        "directory_sha256": contract.sha(str(directory).encode()),
        "predecessor_medium_return_sha256": proposal.RETURNS["medium"],
    }


def prepare(directory, easy, medium):
    site.host()
    require(not os.environ.get("SLURM_JOB_ID"))
    directory = site.location(directory)
    require(not directory.exists())
    head = site.source_head()
    proposal.review_returns(easy, medium)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for source, destination in zip((easy, medium), predecessor_paths(directory)):
        destination.mkdir(mode=0o700, parents=True, exist_ok=False)
        for name in sorted(previous.PUBLIC):
            raw = old.read_bytes(Path(source) / name, matrix.MAX_PACKAGE)
            with (destination / name).open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        previous.sync_dir(destination)
    plan = plan_for(head, directory)
    write(directory / "plan.json", plan)
    write(directory / "approval.template.json", approval_template(plan))
    return {
        "plan_sha256": plan["plan_sha256"],
        "resource_budget_approved": False,
        "submissions_added": 0,
    }


def approve(directory, explicit=False):
    site.host()
    require(explicit is True and not os.environ.get("SLURM_JOB_ID"))
    directory = site.location(directory)
    plan = validate_plan(load(directory / "plan.json"), directory)
    require(site.source_head() == plan["source_commit"])
    checks = ci.review_ci(plan["source_commit"])
    approval = approval_template(plan)
    require(load(directory / "approval.template.json") == approval)
    approval.update(
        explicit_additional_medium_budget_approved=True,
        four_exact_head_ci_arms_reviewed=True,
    )
    sha = contract.sha(contract.encoded(approval))
    validate_approval(plan, approval, sha)
    root = campaign_root()
    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(root.parent.resolve() == root.parent)
    previous.mkdir(root)  # Exclusive reservation; crash never silently releases it.
    write(root / "binding.json", binding(directory, plan, sha))
    write(root / "ci.json", checks)
    write(directory / "approval.json", approval)
    return {"approval_sha256": sha, "submissions_added": 0, "automatic_retry": False}


def approved(directory, sha):
    plan = validate_plan(load(directory / "plan.json"), directory)
    validate_approval(plan, load(directory / "approval.json"), sha)
    require(site.source_head() == plan["source_commit"])
    require(load(campaign_root() / "binding.json") == binding(directory, plan, sha))
    return plan


def stop(code):
    require(code in {"submission_uncertain", "batch_failed", "collection_failed"})
    try:
        write(campaign_root() / "STOP.json", {"code": code, "automatic_retry": False})
    except FileExistsError:
        pass


def live():
    require(not (campaign_root() / "STOP.json").exists())


def submit(directory, sha):
    site.host()
    require(not os.environ.get("SLURM_JOB_ID"))
    directory = site.location(directory)
    plan = approved(directory, sha)
    live()
    checks = ci.review_ci(plan["source_commit"])
    profile = previous.site_profile()
    write(campaign_root() / "submit.started", binding(directory, plan, sha))
    job, stage = None, "create_submission_state"
    try:
        write(directory / "submission_preflight.json", {"ci": checks, "site": profile})
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("SBATCH_", "SRUN_", "SLURM_"))
            and k not in {"BASH_ENV", "ENV"}
        }
        stage = "sbatch_held"
        job = site.command(
            [
                "sbatch",
                "--parsable",
                "--hold",
                "--no-requeue",
                "--partition=batch",
                "--nodes=1",
                "--ntasks=1",
                "--cpus-per-task=16",
                "--hint=nomultithread",
                "--mem=64G",
                "--time=05:30:00",
                "--job-name=cfl_medium_cont",
                "--chdir=" + str(site.SOURCE),
                "--output=" + str(directory / "slurm-%j.private.out"),
                "--error=" + str(directory / "slurm-%j.private.err"),
                str(site.SOURCE / BATCH),
                str(directory),
                sha,
            ],
            env=env,
        ).strip()
        require(re.fullmatch(r"[0-9]{1,20}", job) and job not in {"3489", "3490"})
        stage = "persist_job_id"
        write(
            directory / "submission.json",
            {**binding(directory, plan, sha), "job_id": job},
        )
        stage = "validate_held_profile"
        held = previous.held_profile(
            site.command(["scontrol", "show", "job", "--oneliner", job]), job
        )
        write(directory / "held_profile.json", held)
        live()
        write(directory / "release.started", {"job_id": job})
        stage = "release_job"
        site.command(["scontrol", "release", job])
        write(directory / "released.json", {"job_id": job})
        return {
            "job_id": job,
            "parent": "medium",
            "submission": "released",
            "automatic_retry": False,
        }
    except BaseException as exc:
        stop("submission_uncertain")
        safe_job = (
            job if isinstance(job, str) and re.fullmatch(r"[0-9]{1,20}", job) else None
        )
        raise previous.SubmissionError(stage, safe_job, exc) from exc


def submission(directory):
    record = load(directory / "submission.json")
    plan = approved(directory, record["approval_sha256"])
    require(
        re.fullmatch(r"[0-9]{1,20}", record["job_id"])
        and record["job_id"] not in {"3489", "3490"}
    )
    expected = binding(directory, plan, record["approval_sha256"])
    require(record == {**expected, "job_id": record["job_id"]})
    require(load(campaign_root() / "submit.started") == expected)
    return plan, record


def execution_view(plan):
    return {**plan, "attempts": plan["proposal"]["attempts"]}


def request_for(plan, sha, row):
    require(row in plan["proposal"]["attempts"])
    require(row["attempt_id"].startswith("medium-"))
    return matrix.request_for(execution_view(plan), sha, row)


def execution_context(directory):
    plan, record = submission(directory)
    matrix.execution_host(plan, directory)
    require(record["job_id"] == os.environ.get("SLURM_JOB_ID"))
    require(load(directory / "release.started") == {"job_id": record["job_id"]})
    previous.validate_held(load(directory / "held_profile.json"), record["job_id"])
    live()
    return plan, record


def internal_child(output, request_sha):
    output = Path(output)
    directory = site.location(output.parents[1])
    plan, record = execution_context(directory)
    require(load(directory / "batch.started") == {"job_id": record["job_id"]})
    rows = plan["proposal"]["attempts"]
    row = next(row for row in rows if output.name == row["attempt_id"])
    require(output == directory / "medium" / row["attempt_id"])
    request = request_for(plan, record["approval_sha256"], row)
    require(
        digest(output / "request.json")
        == request_sha
        == contract.sha(contract.encoded(request))
    )
    for prior in rows[: row["within_parent_order"]]:
        prior_request = request_for(plan, record["approval_sha256"], prior)
        receipt = load(
            directory / "medium" / prior["attempt_id"] / "attempt_receipt.json"
        )
        matrix.validate_attempt(receipt, prior_request, record["job_id"])
        require(receipt["pause_remaining_matrix"] is False)
    write(output / "child.started", {"request_sha256": request_sha})
    matrix.run_child(request, output, record["job_id"])


def run(directory, sha):
    site.host()
    directory = site.location(directory)
    plan, record = execution_context(directory)
    require(record["approval_sha256"] == sha)
    matrix.memory.MemoryGate(record["job_id"])
    matrix.adapter.screen.qualify_affinity()
    write(directory / "batch.started", {"job_id": record["job_id"]})
    output = directory / "medium"
    previous.mkdir(output)
    started, receipts, reason = time.monotonic(), {}, None
    handler = signal.getsignal(signal.SIGTERM)

    def interrupted(_sig, _frame):
        raise KeyboardInterrupt("batch_termination")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        for row in plan["proposal"]["attempts"]:
            if time.monotonic() - started + 3780 + 20 > 19800:
                reason = "parent_deadline_reserve"
                break
            receipt = matrix.execute_attempt(
                request_for(plan, sha, row),
                output / row["attempt_id"],
                record["job_id"],
                child_module="pr78_medium_workflow",
            )
            receipts[row["attempt_id"]] = contract.sha(contract.encoded(receipt))
            if receipt["pause_remaining_matrix"]:
                reason = receipt["stop_code"]
                break
        report = matrix.parent_report(
            execution_view(plan), sha, "medium", record["job_id"], receipts, reason
        )
        write(output / "parent_receipt.json", report)
        matrix.validate_parent_directory(output, execution_view(plan), sha, "medium")
        if reason is not None:
            stop("batch_failed")
        return report
    except BaseException:
        stop("batch_failed")
        raise
    finally:
        signal.signal(signal.SIGTERM, handler)


def status(directory):
    site.host()
    directory = site.location(directory)
    _, record = submission(directory)
    return site.parse_accounting(
        site.command(
            [
                "sacct",
                "--noheader",
                "--parsable2",
                "-j",
                record["job_id"],
                "--format=" + site.FIELDS,
            ]
        ),
        record["job_id"],
    )


def validate_public(value, directory):
    old.keys(
        value,
        "schema_version protocol_id plan approval submission accounting held_profile release_started released batch_started workflow_stop_present parent_receipt attempts complete_parent ready_for_independent_review pause_remaining_matrix raw_logs_included scientific_reporting_eligible",
    )
    require(
        old.integer(value["schema_version"]) == 1 and value["protocol_id"] == PROTOCOL
    )
    plan = validate_plan(value["plan"], directory)
    approval, record = value["approval"], value["submission"]
    sha = contract.sha(contract.encoded(approval))
    validate_approval(plan, approval, sha)
    old.keys(
        record,
        "plan_sha256 approval_sha256 directory_sha256 predecessor_medium_return_sha256 job_id",
    )
    old.hexadecimal(record["directory_sha256"])
    require(
        record["plan_sha256"] == plan["plan_sha256"]
        and record["approval_sha256"] == sha
        and record["predecessor_medium_return_sha256"] == proposal.RETURNS["medium"]
    )
    job = record["job_id"]
    require(re.fullmatch(r"[0-9]{1,20}", job) and job not in {"3489", "3490"})
    previous.validate_accounting(value["accounting"])
    require(value["accounting"]["job_id"] == job)
    for field in ("release_started", "released", "batch_started"):
        require(value[field] is None or value[field] == {"job_id": job})
    if value["held_profile"] is not None:
        previous.validate_held(value["held_profile"], job)
    report, attempts = value["parent_receipt"], value["attempts"]
    require(isinstance(attempts, dict))
    if report is None:
        require(
            attempts == {}
            and value["complete_parent"] is False
            and value["workflow_stop_present"] is True
        )
    else:
        expected_ids = set(report["attempt_receipt_sha256"])
        require(set(attempts) == expected_ids)
        payloads = {"medium/parent_receipt.json": contract.encoded(report)}
        for attempt, payload in attempts.items():
            old.keys(payload, "request receipt")
            payloads["medium/" + attempt + "/request.json"] = contract.encoded(
                payload["request"]
            )
            payloads["medium/" + attempt + "/attempt_receipt.json"] = contract.encoded(
                payload["receipt"]
            )
        matrix.validate_parent_directory(
            Path("medium"),
            execution_view(plan),
            sha,
            "medium",
            lambda path: payloads[path.as_posix()],
        )
        require(
            report["job_id"] == job
            and value["complete_parent"] is report["complete_parent"]
        )
    for field in (
        "complete_parent",
        "ready_for_independent_review",
        "pause_remaining_matrix",
        "workflow_stop_present",
    ):
        require(type(value[field]) is bool)
    eligible = (
        value["complete_parent"]
        and previous.clean_accounting(value["accounting"])
        and value["held_profile"] is not None
        and all(
            value[k] is not None
            for k in ("release_started", "released", "batch_started")
        )
        and not value["workflow_stop_present"]
    )
    require(
        value["ready_for_independent_review"] is eligible
        and value["pause_remaining_matrix"] is not eligible
    )
    require(
        value["raw_logs_included"] is False
        and value["scientific_reporting_eligible"] is False
    )
    old.strict_payload(contract.encoded(value))
    return value


def collect(directory):
    site.host()
    directory = site.location(directory)
    target = directory / "public_return.json"
    if target.exists():
        value = validate_public(load(target), directory)
    else:
        plan, record = submission(directory)
        accounting = status(directory)
        if not accounting["terminal"]:
            return {"job_id": record["job_id"], "terminal": False, "collected": False}
        write(directory / "collection.started", {"job_id": record["job_id"]})
        try:
            attempts, report = {}, None
            if (directory / "medium/parent_receipt.json").exists():
                report = matrix.validate_parent_directory(
                    directory / "medium",
                    execution_view(plan),
                    record["approval_sha256"],
                    "medium",
                )
                for name in report["attempt_receipt_sha256"]:
                    source = directory / "medium" / name
                    receipt = load(source / "attempt_receipt.json")
                    require(
                        contract.seal_closed_log(source / "console.private.log")
                        == receipt["console_log"]
                    )
                    if (
                        receipt["child"] is not None
                        and receipt["child"]["gurobi_log"] is not None
                    ):
                        require(
                            contract.seal_closed_log(source / "gurobi.private.log")
                            == receipt["child"]["gurobi_log"]
                        )
                    attempts[name] = {
                        "request": load(source / "request.json"),
                        "receipt": receipt,
                    }
            if report is None:
                stop("batch_failed")
            value = {
                "schema_version": 1,
                "protocol_id": PROTOCOL,
                "plan": plan,
                "approval": load(directory / "approval.json"),
                "submission": record,
                "accounting": accounting,
                "held_profile": load(directory / "held_profile.json")
                if (directory / "held_profile.json").exists()
                else None,
                "release_started": load(directory / "release.started")
                if (directory / "release.started").exists()
                else None,
                "released": load(directory / "released.json")
                if (directory / "released.json").exists()
                else None,
                "batch_started": load(directory / "batch.started")
                if (directory / "batch.started").exists()
                else None,
                "workflow_stop_present": (campaign_root() / "STOP.json").exists(),
                "parent_receipt": report,
                "attempts": attempts,
                "complete_parent": report is not None and report["complete_parent"],
                "ready_for_independent_review": False,
                "pause_remaining_matrix": True,
                "raw_logs_included": False,
                "scientific_reporting_eligible": False,
            }
            eligible = (
                value["complete_parent"]
                and previous.clean_accounting(accounting)
                and value["held_profile"] is not None
                and all(
                    value[k] is not None
                    for k in ("release_started", "released", "batch_started")
                )
                and not value["workflow_stop_present"]
            )
            value.update(
                ready_for_independent_review=eligible,
                pause_remaining_matrix=not eligible,
            )
            validate_public(value, directory)
            write(target, value)
        except BaseException:
            stop("collection_failed")
            raise
    return {
        "job_id": value["accounting"]["job_id"],
        "return_sha256": digest(target),
        "ready_for_independent_review": value["ready_for_independent_review"],
        "scientific_reporting_eligible": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare",
            "approve",
            "submit",
            "run",
            "status",
            "collect",
            "validate-return",
        ),
    )
    parser.add_argument("--directory", required=True)
    parser.add_argument("--easy-return")
    parser.add_argument("--medium-return")
    parser.add_argument("--approval-sha")
    parser.add_argument("--approve-additional-medium-budget", action="store_true")
    parser.add_argument("--return-file")
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "prepare":
        result = prepare(args.directory, args.easy_return, args.medium_return)
    elif args.action == "approve":
        result = approve(args.directory, args.approve_additional_medium_budget)
    elif args.action in {"submit", "run"}:
        result = globals()[args.action](args.directory, args.approval_sha)
    elif args.action in {"status", "collect"}:
        result = globals()[args.action](args.directory)
    else:
        old.hexadecimal(args.expected_sha)
        require(digest(args.return_file) == args.expected_sha)
        result = validate_public(load(args.return_file), args.directory)
    print(contract.encoded(result).decode(), end="")


if __name__ == "__main__":
    try:
        main()
    except previous.SubmissionError as exc:
        print(contract.encoded(exc.report).decode(), end="")
        raise SystemExit(2) from None
    except Exception:
        print("PR78_MEDIUM_STOPPED_PRESERVE_STATE_NO_RETRY", file=sys.stderr)
        raise SystemExit(2) from None
