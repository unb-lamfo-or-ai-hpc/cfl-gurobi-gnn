"""Offline review of the immutable ten-root return; no execution authority."""

import argparse
import json
from pathlib import Path

import pr86_root_preparation as roots
from review_pr86_installed_bindings import csv_bytes

SHA = "4b431deb2736b9f780582425c0d77b1e86dbe297abbfffcb48c4027f15549815"
COMMIT = "f58a7b899ab594a7dfac4ed7df4579be9612ab28"
PLAN = "e73107a12affdbb1c4f4cab9a4e61b28cd0be7ca51d4a7c842321de6eca77e52"
DESTINATION = roots.ROOT / "docs/evidence/pr86/job3520"


def review(raw):
    # The original validator was run at the original tree before this review.
    # Do not recompute its whole-source plan hash against a later checkout.
    roots.require(roots.digest(raw) == SHA, "immutable_return_hash")
    value = roots.isolated.existing.review.flow.meta.strict_json(raw)
    roots.require(value["source_commit"] == COMMIT, "source")
    roots.require(value["plan_sha256"] == PLAN, "plan")
    summary, accounting = value["summary"], value["accounting"]
    roots.require(accounting["job_id"] == "3520", "job")
    roots.require(value["ready_for_independent_review"] is True, "incomplete")
    expected = roots.binding.existing.flow.CASES
    roots.require([r["parent"] for r in summary["rows"]] == list(expected), "parents")
    rows = []
    for row in summary["rows"]:
        result, supervision = row["result"], row["supervision"]
        capture = roots.isolated.costs.seconds(result["capture_wall_seconds"])
        export = roots.isolated.costs.seconds(result["root_export_wall_seconds"])
        wall = roots.isolated.costs.seconds(supervision["supervisor_wall_seconds"])
        roots.require(wall >= capture + export, "nested_timing")
        roots.require(row["completed"] and supervision["guard_stop"] is None, "stop")
        roots.require(result["effective_objective_sense"] == "MINIMIZE", "sense")
        rows.append(
            {
                "parent": row["parent"],
                "alias": roots.binding.proposal.review.alias(row["parent"]),
                "variables": result["variable_count"],
                "optimization_calls": result["optimization_calls"],
                "capture_wall_seconds": capture,
                "root_export_wall_seconds": export,
                "supervisor_wall_seconds": wall,
                "residual_supervision_seconds": wall - capture - export,
                "sampled_job_cgroup_peak_bytes": supervision[
                    "sampled_cgroup_peak_bytes"
                ],
                "root_sha256": result["root_sha256"],
                "source_return_sha256": SHA,
            }
        )
    supervised = sum(r["supervisor_wall_seconds"] for r in rows)
    batch = summary["batch_observed_wall_seconds"]
    roots.require(batch >= supervised, "batch_timing")
    report = {
        "protocol_id": "pr86_job3520_public_review_v1",
        "return_sha256": SHA,
        "source_commit": COMMIT,
        "plan_sha256": PLAN,
        "job_id": "3520",
        "completed_roots": len(rows),
        "observed_root_optimization_calls": sum(r["optimization_calls"] for r in rows),
        "capture_wall_seconds_sum": sum(r["capture_wall_seconds"] for r in rows),
        "root_export_wall_seconds_sum": sum(
            r["root_export_wall_seconds"] for r in rows
        ),
        "supervisor_wall_seconds_sum": supervised,
        "batch_observed_wall_seconds": batch,
        "batch_outside_supervision_seconds": batch - supervised,
        "scheduler_elapsed_seconds": accounting["rows"][0]["ElapsedRaw"],
        "sampled_cgroup_peak_bytes": max(
            r["sampled_job_cgroup_peak_bytes"] for r in rows
        ),
        "scope": "root_preparation_identity_and_nested_cost_observations_only",
        "capture_scope": "model_loading_checks_optimize_signature_and_disposal_not_solver_runtime",
        "private_roots_reopened_by_public_review": False,
        "prospective_starts_ready": False,
        "main_comparison_admitted": False,
        "scientific_reporting_eligible": False,
        "optimization_runs_added_by_review": 0,
    }
    return value, rows, report


def produce(receipt, output):
    raw = receipt.read_bytes()
    _, rows, report = review(raw)
    output.mkdir(parents=True, exist_ok=False)
    (output / "public_return.json").write_bytes(raw)
    (output / "root_costs.csv").write_bytes(csv_bytes(rows))
    roots.write(output / "review.json", report)
    roots.write(
        output / "manifest.json",
        {
            "files": {
                p.name: roots.digest(p.read_bytes()) for p in sorted(output.iterdir())
            },
            "original_receipt_bytes_preserved": True,
        },
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(args.receipt, args.output), indent=2))
