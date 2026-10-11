"""Reconcile existing timing coverage, not new comparison or HPC execution."""

import argparse
import csv
import io
from pathlib import Path

import bind_pr86_existing_starts as binding
import pr86_cost_accounting as costs
import review_e0_job3506 as historical


def build():
    raw = historical.SOURCE.read_bytes()
    historical.flow.require(
        historical.flow.digest(raw) == historical.SHA, "job3506_hash"
    )
    value = historical.flow.review.flow.meta.strict_json(raw)
    historical.audit(value)
    mapping = dict(zip(historical.flow.METHODS, ("M0", "M1", "M2")))
    rows = []
    for attempt in value["matrix"]["attempts"]:
        child = attempt["child"]
        disjoint = costs.execution_costs(child["result"]["timing"])
        estimate = costs.end_to_end(mapping[child["method"]], {}, disjoint)
        rows.append(
            {
                "parent": child["parent"],
                "method": estimate["method"],
                "historical_job_id": "3506",
                "source_return_sha256": historical.SHA,
                **{k + "_seconds": v for k, v in disjoint.items()},
                "execution_seconds": estimate["execution_seconds"],
                "execution_scope": "solver_function_only_not_whole_worker_or_job",
                "worker_overhead_seconds": None,
                "preparation_seconds": estimate["preparation_seconds"],
                "cold_end_to_end_seconds": estimate["cold_end_to_end_seconds"],
                "amortized_end_to_end_seconds": estimate[
                    "amortized_end_to_end_seconds"
                ],
                "missing_preparation_regions": ";".join(
                    estimate["missing_preparation_regions"]
                ),
                "prospective_pr86_result": False,
            }
        )
    return rows


def produce(output):
    rows = build()
    output.mkdir(parents=True, exist_ok=False)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (output / "historical_cost_coverage.csv").write_bytes(stream.getvalue().encode())
    report = {
        "protocol_id": "pr86_historical_cost_coverage_v1",
        "historical_rows": 18,
        "baseline_pr85_merge_commit": binding.MERGED_PR85,
        "original_proposal_unchanged": True,
        "historical_guided_preparation_qualified": False,
        "prospective_instrumentation_integrated_and_installed": False,
        "ten_private_bindings_installed_and_reviewed": False,
        "source_formulation_mapping_accepted": False,
        "resource_budget_approved": False,
        "solver_execution_admitted": False,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "note": "Merged documentary audit is not scientific or resource authorization.",
    }
    (output / "readiness.json").write_bytes(binding.proposal.encoded(report))
    manifest = {
        "files": {
            p.name: binding.proposal.digest(p.read_bytes())
            for p in sorted(output.iterdir())
        },
        "historical_return_sha256": historical.SHA,
        "new_experiments": 0,
    }
    (output / "manifest.json").write_bytes(binding.proposal.encoded(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    produce(parser.parse_args().output)
