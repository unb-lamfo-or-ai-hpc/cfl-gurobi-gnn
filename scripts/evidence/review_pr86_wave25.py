"""Pinned jobs3572..3577 and a 93-cell descriptive ledger; no solver."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import review_pr86_f0 as f0
import review_pr86_wave19 as prior

q = prior.q
SHA = "a54d71775afcff941d496236bfb18f92569a0cc15b8ffadac68978c33c700968"
COMMIT = "99d9b33cd49016dc561c1c8580a3013df298effc"
PLAN = "453f42c948cfd39503e326010227afb848346439b3bedba6b63426eefd4ecfc3"
DEST = q.ROOT / "docs/evidence/pr86/jobs3572-3577"


def review_wave(raw):
    # The original validator passed before edits. Never rebuild historical pins.
    q.require(q.digest(raw) == SHA, "wave25_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(frozen["source_commit"] == COMMIT, "wave25_source")
    q.require(
        value["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "wave25_plan"
    )
    original, cells = q.first.executor.proposal.build()
    q.require(len(frozen["groups"]) == 6, "six_groups")
    for group, expected in zip(frozen["groups"], original["groups"][25:31]):
        q.require(group["group"] == expected, "manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == expected["group_id"]],
            "manifest_cells",
        )
    policy = SimpleNamespace(
        protocol="pr86_frozen_groups25_30_v1", plan=lambda _: frozen
    )
    q.require(
        q.validate_return(raw, policy)["ready_for_independent_review"], "incomplete"
    )
    q.require(
        [r["accounting"]["job_id"] for r in value["returns"]]
        == [str(j) for j in range(3572, 3578)],
        "wave25_jobs",
    )
    return value


def review(raw):
    rows, previous = prior.review(q.read(prior.DEST / "public_return.json"))
    wave = review_wave(raw)
    rows += f0.rows_from_returns(
        wave["returns"], {str(j): SHA for j in range(3572, 3578)}
    )
    original, cells = q.first.executor.proposal.build()
    groups = {g["group_id"] for g in original["groups"][:31]}
    expected = {c["cell_id"] for c in cells if c["group_id"] in groups}
    q.require(
        len(rows) == len(expected) == 93 and {r["cell_id"] for r in rows} == expected,
        "prefix93",
    )
    return rows, {
        "protocol_id": "pr86_thirtyone_group_descriptive_review_v1",
        "input_return_sha256": previous["input_return_sha256"] + [SHA],
        "completed_cells": 93,
        "completed_groups": 31,
        "remaining_cells": 117,
        "remaining_groups": 39,
        "distinct_historically_exposed_parents": 5,
        "complete_five_cap_parents": ["F0", "F3", "F6", "F14"],
        "F27_pending_caps": [2, 4, 8, 16],
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
        "f14_cpu.svg": f0.figure([r for r in rows if r["alias"] == "F14"], "F14"),
        "f27_cpu_partial.svg": f0.figure(
            [r for r in rows if r["alias"] == "F27"],
            "F27",
            (1,),
            "Serie parcial: 2, 4, 8 y 16 hilos pendientes. Sin generalización ni coste de preparación.",
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
