"""Pinned jobs3562..3567 and a 75-cell descriptive ledger; no solver."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import review_pr86_f0 as f0
import review_pr86_wave13 as prior

q = prior.q
SHA = "003a856fec2b9dd81d5ba18bf944389b5f99a2f007827e8cf11bb3535d7886a3"
COMMIT = "3cfc6d35a81d07461771111f9f4e78363188cbe6"
PLAN = "3bfbea0a28f4b2dfeb85502c74ca5a314ea2815a0e1b2bdf00562a41bfe76fde"
DEST = q.ROOT / "docs/evidence/pr86/jobs3562-3567"


def review_wave(raw):
    # The original validator passed before edits. Never rebuild historical pins.
    q.require(q.digest(raw) == SHA, "wave19_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(frozen["source_commit"] == COMMIT, "wave19_source")
    q.require(
        value["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "wave19_plan"
    )
    original, cells = q.first.executor.proposal.build()
    q.require(len(frozen["groups"]) == 6, "six_groups")
    for group, expected in zip(frozen["groups"], original["groups"][19:25]):
        q.require(group["group"] == expected, "manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == expected["group_id"]],
            "manifest_cells",
        )
    policy = SimpleNamespace(
        protocol="pr86_frozen_groups19_24_v1", plan=lambda _: frozen
    )
    q.require(
        q.validate_return(raw, policy)["ready_for_independent_review"], "incomplete"
    )
    q.require(
        [r["accounting"]["job_id"] for r in value["returns"]]
        == [str(j) for j in range(3562, 3568)],
        "wave19_jobs",
    )
    return value


def review(raw):
    rows, previous = prior.review(q.read(prior.DEST / "public_return.json"))
    wave = review_wave(raw)
    rows += f0.rows_from_returns(
        wave["returns"], {str(j): SHA for j in range(3562, 3568)}
    )
    original, cells = q.first.executor.proposal.build()
    groups = {g["group_id"] for g in original["groups"][:25]}
    expected = {c["cell_id"] for c in cells if c["group_id"] in groups}
    q.require(
        len(rows) == len(expected) == 75 and {r["cell_id"] for r in rows} == expected,
        "prefix75",
    )
    return rows, {
        "protocol_id": "pr86_twentyfive_group_descriptive_review_v1",
        "input_return_sha256": previous["input_return_sha256"] + [SHA],
        "completed_cells": 75,
        "completed_groups": 25,
        "remaining_cells": 135,
        "remaining_groups": 45,
        "distinct_historically_exposed_parents": 4,
        "complete_five_cap_parents": ["F0", "F3", "F6"],
        "F14_pending_caps": [4, 8, 16],
        "wave_scheduler_elapsed_sum_seconds": sum(
            r["accounting"]["rows"][0]["ElapsedRaw"] for r in wave["returns"]
        ),
        "all_observed_target_gaps_met": all(
            not r["right_censored"] and r["gap_fraction"] <= 1e-4 for r in rows
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
        "f6_cpu.svg": f0.figure([r for r in rows if r["alias"] == "F6"], "F6"),
        "f14_cpu_partial.svg": f0.figure(
            [r for r in rows if r["alias"] == "F14"],
            "F14",
            (1, 2),
            "Serie parcial: 4, 8 y 16 hilos pendientes. Sin generalización ni coste de preparación.",
        ),
    }
    outputs["manifest.json"] = q.encoded(
        {
            "inputs": summary["input_return_sha256"],
            "outputs": {k: q.digest(v) for k, v in outputs.items()},
        }
    )
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
