"""Preserve and review the installed ten-parent receipt and existing cost data."""

import argparse
import csv
import io
import json
from pathlib import Path

import bind_pr86_existing_starts as binding
import pr86_supervised_costs as costs
import review_e0_job3506 as historical

SHA = "45eab23962f8427b28de1a86557cb03f251f4ecf49d62f23001f54a3215198b2"
SOURCE_COMMIT = "46802675ff996bc2da26e0e0638543e1aa270f6e"
DESTINATION = binding.proposal.ROOT / "docs/evidence/pr86/bindings-45eab23962f8"


def review(raw):
    value = binding.validate(raw, SHA)
    binding.require(value["source_commit"] == SOURCE_COMMIT, "installed_source")
    rows = []
    for parent in value["parents"]:
        n, k = parent["binary_variables"], parent["selected_support"]
        binding.require(k == min(n, 20000, max(1, n // 10)), "support_rule")
        rows.append(
            {
                "parent": parent["parent"],
                "alias": binding.proposal.review.alias(parent["parent"]),
                "difficulty": parent["parent"].split("_")[1],
                "role": parent["role"],
                "historically_exposed": True,
                "binary_variables": n,
                "selected_support_per_guided_method": k,
                "positive_assignments_per_guided_method": parent[
                    "positive_assignments"
                ],
                "zero_assignments_per_guided_method": k
                - parent["positive_assignments"],
                "coverage_fraction": k / n,
                "binary_identity_verified": True,
                "full_solution_feasibility_qualified": False,
                "solver_acceptance_observed": False,
                "source_receipt_sha256": SHA,
                "gnn_assignment_sha256": parent["gnn_assignment_sha256"],
                "lp_assignment_sha256": parent["lp_assignment_sha256"],
            }
        )
    return rows


def historical_cost_rows():
    raw = historical.SOURCE.read_bytes()
    binding.require(binding.proposal.digest(raw) == historical.SHA, "historical_hash")
    value = binding.existing.flow.meta.strict_json(raw)
    historical.audit(value)
    mapping = dict(zip(historical.flow.METHODS, ("M0", "M1", "M2")))
    rows = []
    for attempt in value["matrix"]["attempts"]:
        child = attempt["child"]
        method = mapping[child["method"]]
        measured = costs.reconcile(attempt["supervision"], child["result"], method)
        binding.require(measured["complete_attempt"], "historical_attempt_incomplete")
        rows.append(
            {
                "parent": child["parent"],
                "method": method,
                "job_id": "3506",
                "source_return_sha256": historical.SHA,
                **{
                    k: v
                    for k, v in measured.items()
                    if k != "execution_regions_seconds"
                },
                **{
                    k + "_seconds": v
                    for k, v in measured["execution_regions_seconds"].items()
                },
                "prospective_pr86_result": False,
            }
        )
    return rows


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def produce(receipt, output):
    raw = receipt.read_bytes()
    rows, costs_rows = review(raw), historical_cost_rows()
    output.mkdir(parents=True, exist_ok=False)
    # Artifact generation deliberately copies exact bytes, never re-serializes
    # the HPC receipt. All publication files are under -text Git attributes.
    (output / "binding.json").write_bytes(raw)
    (output / "start_coverage.csv").write_bytes(csv_bytes(rows))
    (output / "historical_attempt_costs.csv").write_bytes(csv_bytes(costs_rows))
    report = {
        "protocol_id": "pr86_installed_binding_review_v1",
        "binding_sha256": SHA,
        "binding_source_commit": SOURCE_COMMIT,
        "parents": 10,
        "easy_parents": 6,
        "medium_parents": 4,
        "ten_historical_start_bindings_reviewed": True,
        "public_review_reopens_private_artifacts": False,
        "full_solution_feasibility_qualified": False,
        "solver_start_acceptance_qualified": False,
        "historical_attempt_timings_reconciled": len(costs_rows),
        "historical_guided_preparation_costs_qualified": False,
        "whole_job_end_to_end_qualified": False,
        "source_formulation_mapping_accepted": False,
        "prospective_executor_installed_and_qualified": False,
        "resource_budget_approved": False,
        "solver_execution_admitted": False,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
        "forwards_added": 0,
        "training_runs_added": 0,
        "submissions_added": 0,
    }
    (output / "review.json").write_bytes(binding.proposal.encoded(report))
    manifest = {
        "files": {
            p.name: binding.proposal.digest(p.read_bytes())
            for p in sorted(output.iterdir())
        },
        "historical_return_sha256": historical.SHA,
        "source_binding_sha256": SHA,
        "original_receipt_bytes_preserved": True,
    }
    (output / "manifest.json").write_bytes(binding.proposal.encoded(manifest))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(args.receipt, args.output), sort_keys=True))
