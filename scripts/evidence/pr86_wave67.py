"""Final frozen M12 groups67..69: three serial jobs, no retry or extra calls."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pr86_wave61 as previous
import review_pr86_m12_numeric as reviewed

q = reviewed.q
START, STOP = 67, 70


def predecessor(wave_raw, numeric_raw):
    _, summary = reviewed.campaign(wave_raw, numeric_raw)
    q.require(
        summary["final_original_nine_continuation_review_passed"],
        "m12_continuation_not_approved",
    )
    return {
        k: summary[k]
        for k in (
            "input_return_sha256",
            "completed_cells",
            "completed_groups",
            "completed_counts_scope",
            "scoped_review_non_M4_M12_cells",
            "M4_sensitive_cells",
            "M12_sensitive_cells",
            "numeric_audits_sha256",
            "author_decisions",
        )
    }


def plan(commit):
    groups = [q.first.plan_for_group(commit, i) for i in range(START, STOP)]
    prior = predecessor(
        q.read(reviewed.audit.review.DEST / "public_return.json"),
        q.read(reviewed.DEST / "numeric_audit.json"),
    )
    q.require(prior["completed_groups"] == START, "collected_prefix")
    return {
        "protocol_id": "pr86_final_frozen_groups67_69_m12_limitation_v1",
        "source_commit": commit,
        "first_review": prior,
        "groups": groups,
        "maximum_submissions": 3,
        "maximum_optimization_calls": 9,
        "maximum_serial_reservation_seconds": 43200,
        "maximum_physical_core_hours": sum(g["group"]["threads"] * 4 for g in groups),
        "maximum_solver_seconds": 32400,
        "campaign_completed_calls_before_this_wave": 201,
        "campaign_calls_ceiling": 210,
        "automatic_retry": False,
        "scientific_reporting_eligible": False,
        "dispatch_after_this_wave": False,
    }


def installed_review():
    previous.installed_review()
    return predecessor(
        q.read(reviewed.audit.STAGE / "public_return.json"),
        q.read(
            q.BASE / ("numeric-m12-" + reviewed.COLLECTOR[:12]) / "numeric_audit.json"
        ),
    )


POLICY = SimpleNamespace(
    plan=plan,
    prefix="next-67-",
    protocol="pr86_final_frozen_groups67_69_m12_limitation_v1",
    claim=q.BASE / "main-comparison-groups67-69.claim",
    operator="operate_pr86_wave67.sh",
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
    q.first.private_inputs(frozen["groups"][0])
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
