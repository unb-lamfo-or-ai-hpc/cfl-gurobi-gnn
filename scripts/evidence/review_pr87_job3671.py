"""Preserve and inspect the failed PR87 return, never submit or execute training."""

import argparse
import json
from pathlib import Path

import pr87_contract as c
import pr87_workflow as workflow

SHA = "e65676eb6f84fe515de766f11b467ba5a2b2ba25715425bf813b1f4eea7cf033"
SOURCE = "f4b226476c8c7520b88560319ec53bba5d2dfb4e"
DEST = c.REPO / "docs/evidence/pr87/job3671"


def products(raw):
    c.require(c.sha(raw) == SHA, "job3671_receipt_hash")
    value = json.loads(raw)
    c.require(value["plan"]["source_commit"] == SOURCE, "historical_source")
    c.require(
        [r["job_id"] for r in value["accounting"]["jobs"]] == ["3671", "3672"],
        "historical_job_ids",
    )
    result = workflow.inspect_return(value)
    c.require(
        result["result_reports_present"] == result["supervisor_reports_present"] == 0,
        "historical_absence_scope",
    )
    return {
        "public_return.json": raw,
        "review.json": (
            json.dumps(
                {
                    "source_return_sha256": SHA,
                    "source_commit": SOURCE,
                    **result,
                    "transfer_failed": False,
                    "spooled_entry_location_defect_identified_in_source": True,
                    "historical_failure_gate_proven": False,
                    "optimization_calls_added": 0,
                    "training_runs_added": 0,
                    "submissions_added": 0,
                    "retry_authorized": False,
                    "raw_logs_included": False,
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = products(args.receipt.read_bytes())
    DEST.mkdir(parents=True, exist_ok=True)
    for name, raw in result.items():
        target = DEST / name
        if target.exists():
            c.require(target.read_bytes() == raw, "preserve_failed_receipt")
        else:
            with target.open("xb") as stream:
                stream.write(raw)
    print(result["review.json"].decode())


if __name__ == "__main__":
    main()
