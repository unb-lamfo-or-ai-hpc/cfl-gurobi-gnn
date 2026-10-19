"""Pinned campaign prefix through job3547; no new optimization or blanket promotion."""

import argparse
import json
from pathlib import Path

import review_pr86_f0 as f0

q = f0.q
SHA = "f526e0fbdff7fe2402fa1d3a3c7a7d264d77c7f1275574e371547994aa5c747c"
COMMIT = "c327d83005ac28fe995efcff618da9d91426b285"
PLAN = "bde874b5be98a5dceae299a15a779c22cbc885137b165222f576a0cba2079cd3"
DEST = q.ROOT / "docs/evidence/pr86/jobs3542-3547"


def review_wave(raw):
    # Original c327d830 validator passed before editing. Keep historical pins fixed.
    q.require(q.digest(raw) == SHA, "f3_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(value["protocol_id"] == "pr86_six_serial_f3_groups_v1", "f3_protocol")
    q.require(frozen["source_commit"] == COMMIT, "f3_source")
    q.require(value["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "f3_plan")
    original, cells = q.first.executor.proposal.build()
    q.require(len(value["returns"]) == len(value["launch"]) == 6, "six_groups")
    for i, (returned, launch) in enumerate(zip(value["returns"], value["launch"])):
        group = frozen["groups"][i]
        q.require(group["group"] == original["groups"][7 + i], "manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == group["group"]["group_id"]],
            "manifest_cells",
        )
        q.require(
            q.first.validate_return(q.encoded(returned), expected_plan=group),
            "f3_incomplete",
        )
        job = str(3542 + i)
        q.require(returned["accounting"]["job_id"] == launch["job_id"] == job, "f3_job")
        held = launch["held_profile"]
        text = " ".join(k + "=" + v for k, v in held["resources"].items())
        if held["dependency"] is not None:
            text += " Dependency=" + held["dependency"]
        q.require(
            q.profile(
                text, job, group["group"]["threads"], str(3541 + i) if i else None
            )
            == held,
            "f3_launch",
        )
    q.require(
        value["raw_logs_included"] is False
        and value["scientific_reporting_eligible"] is False,
        "f3_scope",
    )
    return value


def review(raw):
    prior, _ = f0.review(q.read(f0.DEST / "public_return.json"))
    wave = review_wave(raw)
    rows = f0.rows_from_returns(wave["returns"], {str(3542 + i): SHA for i in range(6)})
    combined = prior + rows
    original, cells = q.first.executor.proposal.build()
    expected_groups = {g["group_id"] for g in original["groups"][:13]}
    expected = {c["cell_id"] for c in cells if c["group_id"] in expected_groups}
    q.require(
        len(combined) == len(expected) == 39
        and {r["cell_id"] for r in combined} == expected,
        "complete_prefix",
    )
    return combined, {
        "protocol_id": "pr86_thirteen_group_descriptive_review_v1",
        "input_return_sha256": [q.FIRST_SHA, f0.SHA, SHA],
        "completed_cells": 39,
        "completed_groups": 13,
        "remaining_cells": 171,
        "remaining_groups": 57,
        "distinct_historically_exposed_parents": 2,
        "complete_five_cap_parents": ["F0"],
        "F3_pending_caps": [16],
        "wave_scheduler_elapsed_sum_seconds": sum(
            r["accounting"]["rows"][0]["ElapsedRaw"] for r in wave["returns"]
        ),
        "all_observed_target_gaps_met": all(
            not r["right_censored"] and r["gap_fraction"] <= 1e-4 for r in combined
        ),
        "qualified_scope": "pinned_descriptive_solver_and_scoped_attempt_measurements",
        "population_speedup_claim": False,
        "whole_job_cold_cost_qualified": False,
        "original_receipts_and_flags_unchanged": True,
        "optimization_runs_added": 0,
    }


def publish(directory):
    rows, summary = review(q.read(DEST / "public_return.json"))
    outputs = {
        "campaign_results.csv": f0.csv_bytes(rows),
        "review.json": q.encoded(summary),
        "f3_cpu_partial.svg": f0.figure(
            [r for r in rows if r["alias"] == "F3"],
            "F3",
            (1, 2, 4, 8),
            "Serie parcial: 16 hilos pendiente. Sin generalización ni coste de preparación.",
        ),
    }
    manifest = {
        "inputs": summary["input_return_sha256"],
        "outputs": {k: q.digest(v) for k, v in outputs.items()},
    }
    outputs["manifest.json"] = q.encoded(manifest)
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        path = directory / name
        if path.exists():
            q.require(q.read(path) == raw, "preserve_output")
        else:
            with path.open("xb") as stream:
                stream.write(raw)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(publish(parser.parse_args().output), indent=2))


if __name__ == "__main__":
    main()
