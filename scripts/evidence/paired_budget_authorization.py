"""Review installed PR76 and record a separately authorized frozen budget.

No scheduler, solver, license, model, approval inference or retry interface.
SPDX-License-Identifier: MIT
"""

import argparse
import os
import sys
from pathlib import Path

import paired_matrix_workflow as flow

require, contract, old = flow.require, flow.contract, flow.old
HEAD = "ad4800505bae78032e8fdbaa449a7afd2f12a080"
RECEIPT_SHA = "0249a1de5cb6d06422932d7ffa5568a2077ceb0c6f51099a5675a6f33fdeca14"
OPERATOR_SHA = "c7f5aa69c775088e7d383a942d9ee66f2b053dfe656e5d123e80e546692f70a2"
MATRIX_SHA = "b24dbe0924a2c6f03f7f162cf2f85bfd327f4a0bd99048b98200b6f22e5a575b"
ARCHIVE = "docs/evidence/pr76/operator-ad4800505bae/pr76_operator_preparation.json"
PROTOCOL = "explicit_paired_matrix_budget_authorization_v1"


def expected_receipt(plan):
    return {
        "schema_version": 1,
        "source_commit": HEAD,
        "tests_run": 28,
        "errors": 0,
        "failures": 0,
        "skipped": 0,
        "passed_no_solver_operator_probe": True,
        "operator_plan_sha256": OPERATOR_SHA,
        "matrix_plan_sha256": MATRIX_SHA,
        "dependency_sha256": plan["dependency_sha256"],
        "installed_executor_probe_sha256": flow.PROBE_SHA,
        "resource_budget_approved": False,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "scheduler_queries": 0,
        "higher_budget_memory_safety_qualified": False,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
    }


def review(receipt=None):
    flow.reviewed_probe()
    flow.matrix.reviewed_evidence()
    plan = flow.plan_for(HEAD)
    require(plan["operator_plan_sha256"] == OPERATOR_SHA)
    require(plan["matrix_plan_sha256"] == MATRIX_SHA)
    require(len(plan["dependency_sha256"]) == 13)
    raw = old.read_bytes(receipt or flow.SOURCE / ARCHIVE)
    require(contract.sha(raw) == RECEIPT_SHA)
    old.strict_payload(raw)
    require(raw == contract.encoded(expected_receipt(plan)))
    return plan


def template(directory):
    directory = Path(directory).absolute()
    require(directory.resolve() == directory and not directory.is_symlink())
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "authorization_source": "explicit_human_cli",
        "source_commit": HEAD,
        "operator_plan_sha256": OPERATOR_SHA,
        "matrix_plan_sha256": MATRIX_SHA,
        "installed_operator_receipt_sha256": RECEIPT_SHA,
        "flow_directory_sha256": contract.sha(str(directory).encode()),
        "maximum_submissions": 2,
        "maximum_optimization_calls": 10,
        "maximum_optimization_seconds": 36000,
        "maximum_parent_wall_seconds": 19800,
        "physical_cores": 16,
        "scheduler_memory_mib": 65536,
        "gpus": 0,
        "exclusive": False,
        "requeue": False,
        "automatic_retry": False,
        "independent_easy_review_before_medium_required": True,
        "actual_kernel_memory_gate_before_model_read_required": True,
        "explicit_resource_budget_and_submission_approved": False,
        "exact_head_four_ci_arms_reviewed": False,
        "installed_no_solver_probes_reviewed": False,
        "higher_budget_memory_safety_qualified": False,
        "scientific_reporting_eligible": False,
    }


def validate_authorization(directory, path, expected_sha):
    old.hexadecimal(expected_sha)
    path = Path(path).absolute()
    require(
        path.resolve() == path
        and path.is_relative_to(flow.matrix.adapter.EVIDENCE_ROOT)
    )
    raw = old.read_bytes(path)
    require(contract.sha(raw) == expected_sha)
    old.strict_payload(raw)
    value = template(directory)
    for name in (
        "explicit_resource_budget_and_submission_approved",
        "exact_head_four_ci_arms_reviewed",
        "installed_no_solver_probes_reviewed",
    ):
        value[name] = True
    require(raw == contract.encoded(value))
    return value


def verify_original_source(source, plan):
    require(source.resolve() == source and source.is_dir())
    command = ["git", "-c", "safe.directory=" + str(source), "-C", str(source)]
    require(flow.site.command([*command, "rev-parse", "HEAD"]).strip() == HEAD)
    require(
        not flow.site.command(
            [*command, "status", "--porcelain", "--untracked-files=all"]
        )
    )
    require(not (source / "gurobi.env").exists())
    for name, sha in plan["dependency_sha256"].items():
        path = (
            source / name
            if name.startswith("scripts/")
            else source / "scripts/evidence" / name
        )
        require(flow.digest(path) == sha)


def frozen_flow(directory):
    flow.site.host()
    require(not os.environ.get("SLURM_JOB_ID"))
    directory = flow.site.location(directory)
    require(
        directory
        == flow.matrix.adapter.EVIDENCE_ROOT / "pr76/operator-ad4800505bae/flow"
    )
    plan = review(directory.parent / "pr76_operator_preparation.json")
    require(old.read_bytes(directory / "operator_plan.json") == contract.encoded(plan))
    execution = flow.matrix.plan_for(HEAD)
    require(old.read_bytes(directory / "plan.json") == contract.encoded(execution))
    require(
        old.read_bytes(directory / "approval.json")
        == contract.encoded(flow.matrix.approval_template(execution))
    )
    require(
        old.read_bytes(directory / "operator_approval.json")
        == contract.encoded(flow.approval_template(plan))
    )
    require(not (directory / "operator-state").exists())
    require(not any((directory / name).exists() for name in flow.matrix.PARENTS))
    verify_original_source(directory.parent / "source", plan)
    return directory, plan, execution


def approved_records(plan, execution):
    matrix_approval = flow.matrix.approval_template(execution)
    for name in (
        "explicit_resource_budget_and_submission_approved",
        "exact_head_four_ci_arms_reviewed",
        "installed_no_solver_fault_probe_reviewed",
    ):
        matrix_approval[name] = True
    matrix_sha = contract.sha(contract.encoded(matrix_approval))
    operator_approval = flow.approval_template(plan)
    operator_approval.update(
        matrix_approval_sha256=matrix_sha,
        explicit_resource_budget_and_submission_approved=True,
        exact_head_four_ci_arms_reviewed=True,
    )
    operator_sha = contract.sha(contract.encoded(operator_approval))
    flow.matrix.validate_approval(execution, matrix_approval, matrix_sha)
    flow.validate_approval(plan, operator_approval, operator_sha, matrix_sha)
    return matrix_approval, matrix_sha, operator_approval, operator_sha


def replace_false_approval(path, false_value, approved_value):
    require(old.read_bytes(path) == contract.encoded(false_value))
    pending = path.with_name(path.name + ".authorized.pending")
    flow.write(pending, approved_value)
    # Each replacement is atomic. The two-file recording is NOT a transaction.
    # Interrupted recordings retain their exclusive claim for manual review.
    os.replace(pending, path)
    flow.sync_dir(path.parent)


def record(directory, authorization, authorization_sha):
    directory, plan, execution = frozen_flow(directory)
    value = validate_authorization(directory, authorization, authorization_sha)
    matrix_approval, matrix_sha, operator_approval, operator_sha = approved_records(
        plan, execution
    )
    require(
        old.read_bytes(directory / "approval.json")
        == contract.encoded(flow.matrix.approval_template(execution))
    )
    require(
        old.read_bytes(directory / "operator_approval.json")
        == contract.encoded(flow.approval_template(plan))
    )
    for path in (
        flow.root_for(operator_sha),
        flow.matrix.adapter.EVIDENCE_ROOT / "paired-matrix-locks" / matrix_sha,
    ):
        require(path.resolve() == path and not path.exists())
    root = (
        flow.matrix.adapter.EVIDENCE_ROOT
        / "paired-budget-authorization-locks"
        / authorization_sha
    )
    require(root.resolve() == root)
    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(root.parent.resolve() == root.parent)
    flow.sync_dir(root.parent.parent)
    flow.mkdir(root)
    flow.write(root / "authorization.json", value)
    flow.write(
        root / "matrix_approval.before.json", flow.matrix.approval_template(execution)
    )
    flow.write(root / "operator_approval.before.json", flow.approval_template(plan))
    replace_false_approval(
        directory / "approval.json",
        flow.matrix.approval_template(execution),
        matrix_approval,
    )
    replace_false_approval(
        directory / "operator_approval.json",
        flow.approval_template(plan),
        operator_approval,
    )
    require(flow.digest(directory / "approval.json") == matrix_sha)
    require(flow.digest(directory / "operator_approval.json") == operator_sha)
    result = {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "authorization_sha256": authorization_sha,
        "operator_plan_sha256": OPERATOR_SHA,
        "matrix_plan_sha256": MATRIX_SHA,
        "matrix_approval_sha256": matrix_sha,
        "operator_approval_sha256": operator_sha,
        "recorded_separate_explicit_budget": True,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "scheduler_queries": 0,
        "automatic_retry": False,
        "higher_budget_memory_safety_qualified": False,
        "scientific_reporting_eligible": False,
    }
    flow.write(root / "recording.completed.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("review", "preview", "record"))
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--authorization-sha")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "review":
        require(
            args.directory is None
            and args.authorization is None
            and args.authorization_sha is None
        )
        plan = review()
        result = {
            "receipt_sha256": RECEIPT_SHA,
            "operator_plan_sha256": plan["operator_plan_sha256"],
            "matrix_plan_sha256": plan["matrix_plan_sha256"],
            "reviewed_dependency_count": 13,
            "installed_tests_reported": 28,
            "resource_budget_approved": False,
            "scientific_reporting_eligible": False,
        }
    elif args.action == "preview":
        require(
            args.directory is not None
            and args.authorization is None
            and args.authorization_sha is None
        )
        directory, _, _ = frozen_flow(args.directory)
        result = template(directory)
    else:
        require(
            args.directory is not None
            and args.authorization is not None
            and args.authorization_sha is not None
        )
        result = record(args.directory, args.authorization, args.authorization_sha)
    print(contract.encoded(result).decode(), end="")


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt):
        print(
            "PAIRED_BUDGET_STOP_PRESERVE_CLAIM_AND_EVIDENCE_NO_RETRY", file=sys.stderr
        )
        sys.exit(2)
