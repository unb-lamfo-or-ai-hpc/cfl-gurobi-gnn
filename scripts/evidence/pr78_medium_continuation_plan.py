"""Read-only continuation proposal; never authorize, claim, submit or optimize.

The historical operator validator remains frozen. Both exact downloaded returns
must pass its nested contract before a proposal can be emitted. No original
approval can be used as an authorization for this proposal.
SPDX-License-Identifier: MIT
"""

import argparse
import sys
from pathlib import Path

import paired_matrix_executor_v3 as successor
import paired_matrix_workflow_v3 as historical

old, contract, require = historical.old, historical.contract, historical.require
PROTOCOL = "pr78_medium_only_continuation_proposal_v1"
SCOPES = ("unattempted-only", "full-medium")
SOURCE = historical.SOURCE
PRIOR_HEAD = "2a538fd7cc048eb988d44a529cc5ee5c9faf96bf"
RETURNS = {
    "easy": "06502e632c5ad0806cb5a7c331d72887b9298866a2b59e7b28bde97b1f51e329",
    "medium": "4068bb9824bcd4dbd49c2327806d9e2a22980053c9a9ddb5e0e245c8e6436227",
}
PACKAGES = {
    "easy": "a35ef35d687d66c7b6f0d1c0e9b1e2c5bc7dc538c933981a6dcc9b67420cb571",
    "medium": "b9d86015d24b56de316bfea5cea11207a0cc416e14916c14a651343f1460a7e5",
}
MATRIX_APPROVAL = "de16f405335cb2df7876ea0b244efc5740220020e093ed4ef61b749a75955ce2"
OPERATOR_APPROVAL = "f5e2f5bf8d348be46a80ef769cf3b76e174bfe7713117493fa0422561f176147"
OPERATOR_PLAN = "2d59e104cd896d1f9dcec067fdd3d507f2e6c4d69085deefca4da2fa8e0a609e"
EASY_REVIEW = "a7b8acca50978b0a522be345bac3f80aac19f95d36adc0475941f8e5bcf75966"
INTERRUPTED = "medium-seed42-threads16"


def review_returns(easy_directory, medium_directory):
    """Validate public bytes locally; no scheduler, private log or LP reads."""
    values = {}
    for parent, directory, job in (
        ("easy", easy_directory, "3489"),
        ("medium", medium_directory, "3490"),
    ):
        value = historical.validate_return(directory, RETURNS[parent])
        require(value["parent"] == parent and value["accounting"]["job_id"] == job)
        require(value["operator_plan_sha256"] == OPERATOR_PLAN)
        require(value["operator_approval_sha256"] == OPERATOR_APPROVAL)
        require(value["matrix_approval_sha256"] == MATRIX_APPROVAL)
        require(value["matrix_package_sha256"] == PACKAGES[parent])
        require(historical.clean_accounting(value["accounting"]))
        require(value["parent_evidence_state"] == "validated")
        require(value["raw_logs_included"] is False)
        require(value["scientific_reporting_eligible"] is False)
        values[parent] = value
    easy, medium = values["easy"], values["medium"]
    require(easy["complete_parent"] is True)
    require(easy["exact_optimization_call_count"] == 5)
    require(easy["ready_for_independent_review"] is True)
    require(easy["pause_remaining_matrix"] is False)
    require(medium["complete_parent"] is False)
    require(medium["completed_attempts_observed"] == 1)
    require(medium["exact_optimization_call_count"] is None)
    require(medium["ready_for_independent_review"] is False)
    require(medium["pause_remaining_matrix"] is True)
    require(medium["workflow_stop_present"] is True)
    record = historical.load(Path(medium_directory) / "submission.json")
    require(record["easy_review_sha256"] == EASY_REVIEW)
    report = historical.matrix.validate_package(
        Path(medium_directory) / "matrix.tar.gz", PACKAGES["medium"]
    )
    require(list(report["attempt_receipt_sha256"]) == [INTERRUPTED])
    require(report["stop_code"] == "memory_observation_lost")
    # Exact pinned return hashes bind the original source, approvals and bytes.
    return {
        "source_commit": PRIOR_HEAD,
        "return_manifest_sha256": dict(RETURNS),
        "matrix_package_sha256": dict(PACKAGES),
        "operator_plan_sha256": OPERATOR_PLAN,
        "operator_approval_sha256": OPERATOR_APPROVAL,
        "matrix_approval_sha256": MATRIX_APPROVAL,
        "easy_review_sha256": EASY_REVIEW,
        "easy_job_id": "3489",
        "easy_exact_optimization_calls": 5,
        "easy_preserved_without_rerun": True,
        "medium_job_id": "3490",
        "medium_interrupted_attempt": INTERRUPTED,
        "medium_exact_optimization_calls": None,
        "medium_reserved_optimization_slots": 1,
        "reservation_is_not_a_measured_call_count": True,
        "historical_stop_preserved": True,
        "historical_failure_cause_proven": False,
        "scientific_reporting_eligible": False,
    }


def dependency_hashes():
    return {
        **historical.plan_for(PRIOR_HEAD)["dependency_sha256"],
        **successor.pins(),
        "pr78_medium_continuation_plan.py": historical.digest(Path(__file__)),
    }


def compile_plan(head, easy_directory, medium_directory, scope):
    old.hexadecimal(head, 40)
    require(scope in SCOPES)
    predecessor = review_returns(easy_directory, medium_directory)
    successor.reviewed_evidence()
    proposal = contract.compile_proposal()
    medium = [
        row for row in proposal["attempts"] if row["attempt_id"].startswith("medium-")
    ]
    require([row["threads"] for row in medium] == [16, 8, 2, 1, 4])
    rows = medium[1:] if scope == "unattempted-only" else medium
    count = len(rows)
    budget = {
        "scope": "successor_campaign_jobs3489_3490_and_proposed_continuation_only",
        "earlier_diagnostic_and_recovery_jobs_included": False,
        "original_maximum_submissions": 2,
        "original_maximum_optimization_calls": 10,
        "original_maximum_solver_seconds": 36000,
        "prior_submissions_consumed": 2,
        "prior_optimization_slots_conservatively_reserved": 6,
        "prior_solver_seconds_conservatively_reserved": 21600,
        "prior_runtime_is_measured_by_this_ledger": False,
        "remaining_original_submission_slots": 0,
        "remaining_original_optimization_slots": 4,
        "proposed_new_submissions": 1,
        "proposed_new_optimization_calls": count,
        "proposed_new_solver_seconds": count * 3600,
        "proposed_new_wall_seconds": count * 3780 + 900,
        "proposed_cumulative_submission_ceiling": 3,
        "proposed_cumulative_optimization_slot_ceiling": 6 + count,
        "proposed_cumulative_solver_seconds_ceiling": (6 + count) * 3600,
        "additional_submission_slots_required": 1,
        "additional_optimization_slots_required": max(0, 6 + count - 10),
        "additional_solver_seconds_required": max(0, (6 + count) * 3600 - 36000),
        "fresh_explicit_authorization_required": True,
        "old_approvals_are_not_continuation_authorization": True,
    }
    value = {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "source_commit": head,
        "dependency_sha256": dependency_hashes(),
        "installed_qualification_sha256": successor.evidence.QUALIFICATION_SHA,
        "runtime_protocol": successor.PROTOCOL,
        "memory_gate_protocol": successor.memory.PROTOCOL,
        "memory_policy": dict(successor.memory.POLICY),
        "original_comparison_proposal_sha256": proposal["proposal_sha256"],
        "predecessor": predecessor,
        "scope": scope,
        "parent": "medium",
        "attempts": rows,
        "original_within_parent_order_preserved": True,
        "interrupted_attempt_reexecution_proposed": scope == "full-medium",
        "matrix_complete_if_all_new_attempts_validate": scope == "full-medium",
        "unresolved_attempts_after_success": [INTERRUPTED]
        if scope == "unattempted-only"
        else [],
        "budget": budget,
        "scheduler": {
            **historical.PROFILE,
            "wall_seconds": budget["proposed_new_wall_seconds"],
        },
        "child_deadline_seconds": 3780,
        "concurrent_attempts": 1,
        "execution_enabled": False,
        "scheduler_adapter_implemented": False,
        "resource_budget_approved": False,
        "exact_head_ci_reviewed": False,
        "automatic_retry": False,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "scheduler_queries": 0,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
    }
    value["continuation_plan_sha256"] = contract.sha(contract.encoded(value))
    old.strict_payload(contract.encoded(value))
    return value


def validate_plan(value, easy_directory, medium_directory):
    require(isinstance(value, dict))
    expected = compile_plan(
        value["source_commit"], easy_directory, medium_directory, value["scope"]
    )
    # Canonical byte equality rejects True == 1 and floating-point substitutions.
    require(contract.encoded(value) == contract.encoded(expected))
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "validate"))
    parser.add_argument("--easy-return", required=True)
    parser.add_argument("--medium-return", required=True)
    parser.add_argument("--scope", choices=SCOPES)
    parser.add_argument("--plan")
    args = parser.parse_args(argv)
    if args.action == "preview":
        require(args.scope is not None and args.plan is None)
        # Local clean Git source only. No network or scheduler calls.
        head = historical.site.source_head()
        result = compile_plan(head, args.easy_return, args.medium_return, args.scope)
    else:
        require(args.plan is not None and args.scope is None)
        result = validate_plan(
            historical.load(args.plan), args.easy_return, args.medium_return
        )
    print(contract.encoded(result).decode(), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never expose filesystem paths or exception text from receipt parsing.
        print("PR78_CONTINUATION_PLAN_REJECTED_NO_SUBMISSION", file=sys.stderr)
        raise SystemExit(2) from None
