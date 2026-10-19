"""Frozen groups61..66: finish M7, begin M12; six serial jobs, no retry."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pr86_wave55 as previous
import review_pr86_wave55 as reviewed

q = reviewed.q
START, STOP = 61, 67


def predecessor(raw):
    _, summary = reviewed.review(raw)
    q.require(summary["next_fixed_wave_review_passed"], "new_parent_numeric_conflict")
    return {
        k: summary[k]
        for k in (
            "input_return_sha256",
            "completed_cells",
            "completed_groups",
            "completed_counts_scope",
            "scoped_review_non_M4_cells",
            "numerically_sensitive_cells",
            "numerically_sensitive_parent",
            "numeric_audit_sha256",
            "author_decision",
        )
    }


def plan(commit):
    groups = [q.first.plan_for_group(commit, i) for i in range(START, STOP)]
    prior = predecessor(q.read(reviewed.DEST / "public_return.json"))
    q.require(prior["completed_groups"] == START, "collected_prefix")
    return {
        "protocol_id": "pr86_frozen_groups61_66_numeric_limitation_v1",
        "source_commit": commit,
        "first_review": prior,
        "groups": groups,
        "maximum_submissions": 6,
        "maximum_optimization_calls": 18,
        "maximum_serial_reservation_seconds": 86400,
        "maximum_physical_core_hours": sum(g["group"]["threads"] * 4 for g in groups),
        "maximum_solver_seconds": 64800,
        "campaign_completed_calls_before_this_wave": 183,
        "campaign_calls_ceiling": 210,
        "automatic_retry": False,
        "scientific_reporting_eligible": False,
        "dispatch_after_this_wave": False,
    }


def installed_review():
    previous.installed_review()
    return predecessor(
        q.read(q.BASE / ("next-55-" + reviewed.COMMIT[:12]) / "public_return.json")
    )


POLICY = SimpleNamespace(
    plan=plan,
    prefix="next-61-",
    protocol="pr86_frozen_groups61_66_numeric_limitation_v1",
    claim=q.BASE / "main-comparison-groups61-66.claim",
    operator="operate_pr86_wave61.sh",
    installed_review=installed_review,
)


def prepare(stage):
    q.first.roots.accounting.host()
    frozen = plan(q.first.roots.head())
    q.require(
        stage.resolve() == q.BASE / (POLICY.prefix + frozen["source_commit"][:12]),
        "stage",
    )
    q.require(installed_review() == frozen["first_review"], "predecessor_review")
    parents = set()
    for group in frozen["groups"]:
        if group["group"]["parent"] not in parents:
            q.first.private_inputs(group)
            parents.add(group["group"]["parent"])
    return {"plan_sha256": q.write(stage / "plan.json", frozen), "submissions_added": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "submit", "run", "status", "collect", "review")
    )
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--index", type=int)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.stage)
    elif args.action == "submit":
        result = q.submit(args.stage, args.approved_plan_sha256, POLICY)
    elif args.action == "run":
        return q.run(args.stage, args.index, POLICY)
    elif args.action == "review":
        result = q.validate_return(q.read(args.receipt), POLICY)
    else:
        result = {"status": q.status, "collect": q.collect}[args.action](
            args.stage, POLICY
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
