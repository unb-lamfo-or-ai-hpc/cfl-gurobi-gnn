"""Offline review of sealed Sprint B returns; no solver, scheduler or network.

SPDX-License-Identifier: MIT
"""

import argparse
import json
import tarfile
import tempfile
import zipfile
from pathlib import Path

import pr78_medium_workflow as flow

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evidence"
RETURN_SHA = "5141dd4568cf83116d9d8d0d313a0cc4f63f573c60304ea5e578e10a08210e0a"
ARCHIVES = {
    "easy": (
        "pr78/job3491/job3489-public-return.zip",
        "9ad9e582eb947ae89da00bf770929cf357172ec880b8424749b30361bc2937d6",
    ),
    "medium": (
        "pr78/job3491/job3490-public-return.zip",
        "d0b8d349db6d1dc52ac30d45f2d625e4593f85de14a594bda56775444e20e5ff",
    ),
    "return": (
        "pr79-job3494-return.zip",
        "60d2386b98e8d9ea1d75f1f6bb0395ce4d9381b7c9a5c1558bd3b61fae4989f4",
    ),
}


def unpack_public(root, destination):
    """Exact archives/members, bounded reads, no extractall or raw-log export."""
    for kind, (name, sha) in ARCHIVES.items():
        path = Path(root) / name
        flow.require(flow.digest(path) == sha)
        expected = {"public_return.json"} if kind == "return" else flow.previous.PUBLIC
        target = destination if kind == "return" else destination / "predecessor" / kind
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path) as archive:
            flow.require(len(archive.infolist()) == len(expected))
            flow.require(set(archive.namelist()) == expected)
            for member in archive.infolist():
                flow.require(
                    not member.is_dir() and member.file_size <= 32 * 1024 * 1024
                )
                with archive.open(member) as stream:
                    raw = stream.read(32 * 1024 * 1024 + 1)
                flow.require(len(raw) == member.file_size)
                with (target / member.filename).open("xb") as stream:
                    stream.write(raw)
    flow.require(flow.digest(destination / "public_return.json") == RETURN_SHA)


def observed_target(result):
    target = result["stopping_gap_relative"]
    matches = [
        row
        for row in result["first_sampled_gap_observations"]
        if row["target_gap_relative"] == target
    ]
    flow.require(len(matches) == 1)
    return matches[0]


def attempt_row(parent, attempt, receipt):
    child = receipt["child"]
    flow.require(child is not None and child["failure_code"] is None)
    result = child["result"]
    terminal = result["terminal"]
    observed = observed_target(result)
    return {
        "parent": parent,
        "attempt_id": attempt,
        "job_id": receipt["job_id"],
        "threads": child["effective_parameters"]["Threads"],
        "seed": child["effective_parameters"]["Seed"],
        "target_gap_relative": result["stopping_gap_relative"],
        "stop": result["stop"],
        "solver_runtime_seconds": terminal["solver_runtime_seconds"],
        "primal": terminal["primal"],
        "dual": terminal["dual"],
        "gap_relative": terminal["gap_relative"],
        "node_count": terminal["node_count"],
        "observed_target_state": observed["state"],
        "first_observed_target_seconds": observed["solver_runtime_seconds"],
        "observation_end_runtime_seconds": observed.get(
            "observation_end_runtime_seconds"
        ),
        "process_cpu_seconds": child["current_process_cpu_seconds"],
        "worker_peak_rss_bytes": child["peak_rss_bytes"],
        "sampled_cgroup_peak_bytes": receipt["guard"]["sampled_cgroup_peak_bytes"],
        "optimization_calls": child["optimization_calls"],
        "memory_stop": receipt["guard"]["guard_stop"],
        "sample_count": len(result["samples"]),
        "dropped_sample_count": result["dropped_sample_count"],
        "time_limit_overshoot_seconds": result["time_limit_overshoot_seconds"],
        "true_first_crossings_qualified": result["true_first_crossings_qualified"],
        "root_tree_phase_costs_qualified": result["root_tree_phase_costs_qualified"],
    }


def comparison(rows):
    """Only compare successful, observed same-parent/seed/target times."""
    rows = [dict(row) for row in rows]
    baselines = {
        (r["parent"], r["seed"], r["target_gap_relative"]): r
        for r in rows
        if r["threads"] == 1
    }
    for row in rows:
        base = baselines.get((row["parent"], row["seed"], row["target_gap_relative"]))
        t = row["first_observed_target_seconds"]
        baseline = None if base is None else base["first_observed_target_seconds"]
        eligible = (
            base is not None
            and row["stop"] == base["stop"] == "gap_target"
            and t is not None
            and baseline is not None
            and t > 0
            and baseline > 0
        )
        row["observed_target_speedup_vs_1"] = baseline / t if eligible else None
        row["observed_target_efficiency_vs_1"] = (
            baseline / t / row["threads"] if eligible else None
        )
    return rows


def seconds(text):
    days, clock = text.split("-", 1) if "-" in text else ("0", text)
    fields = clock.split(":")
    flow.require(len(fields) in (2, 3))
    if len(fields) == 2:
        fields.insert(0, "0")
    h, m, s = (float(v) for v in fields)
    return int(days) * 86400 + h * 3600 + m * 60 + s


def allocation_rows(accountings):
    """Count each job once. Step RSS stays a separately labelled scope."""
    result = {}
    for value in accountings:
        job = value["job_id"]
        rows = value["rows"]
        parents = [r for r in rows if r["JobID"] == job]
        flow.require(len(parents) == 1)
        row = parents[0]
        record = {
            "job_id": job,
            "state": row["State"],
            "elapsed_seconds": row["ElapsedRaw"],
            "scheduler_total_cpu_seconds": seconds(row["TotalCPU"]),
            "allocated_logical_cpus": row["AllocCPUS"],
            "allocated_logical_cpu_hours": row["AllocCPUS"] * row["ElapsedRaw"] / 3600,
            "requested_physical_core_reservation_hours": 16 * row["ElapsedRaw"] / 3600,
            "step_max_rss": {
                r["JobID"]: r["MaxRSS"] for r in rows if r["JobID"] != job
            },
            "historical_memory_scopes_reconciled": False,
        }
        flow.require(job not in result or result[job] == record)
        result[job] = record
    return sorted(result.values(), key=lambda r: int(r["job_id"]))


def profile(rows):
    """Strict Pareto frontier among target-reaching arms, no tie tolerance."""
    eligible = [
        r
        for r in rows
        if r["stop"] == "gap_target" and r["first_observed_target_seconds"] is not None
    ]
    dimensions = (
        "first_observed_target_seconds",
        "process_cpu_seconds",
        "sampled_cgroup_peak_bytes",
    )
    frontier = []
    for row in eligible:
        dominated = any(
            all(other[k] <= row[k] for k in dimensions)
            and any(other[k] < row[k] for k in dimensions)
            for other in eligible
        )
        if not dominated:
            frontier.append(row)
    # An explicit development choice, not a population-optimal claim:
    # choose the lowest thread cap on the strict frontier, preserving all ties.
    return {
        "eligible_arms": len(eligible),
        "total_arms": len(rows),
        "strict_pareto_threads": sorted(r["threads"] for r in frontier),
        "selected_development_threads": min(
            (r["threads"] for r in frontier), default=None
        ),
        "selection_rule": "lowest_thread_cap_on_target_time_cpu_sampled_memory_strict_frontier",
        "population_generalization_supported": False,
    }


def build_report(evidence=EVIDENCE):
    with tempfile.TemporaryDirectory(prefix="pr79-read-only-") as temp:
        directory = Path(temp).resolve()
        unpack_public(evidence, directory)
        value = flow.validate_public(
            flow.load(directory / "public_return.json"), directory
        )
        flow.require(value["submission"]["job_id"] == "3494")
        flow.require(value["ready_for_independent_review"] and value["complete_parent"])
        easy_dir, old_medium_dir = flow.predecessor_paths(directory)
        # Both predecessor archives and every nested contract were already
        # checked by validate_public -> compile_plan -> review_returns.
        with tarfile.open(easy_dir / "matrix.tar.gz", "r:gz") as archive:
            attempts = {}
            for member in archive:
                if member.name.endswith("/attempt_receipt.json"):
                    raw = archive.extractfile(member).read()
                    attempts[member.name.split("/")[1]] = flow.old.strict_payload(raw)
        rows = [
            attempt_row("easy", name, receipt) for name, receipt in attempts.items()
        ]
        rows += [
            attempt_row("medium", name, payload["receipt"])
            for name, payload in value["attempts"].items()
        ]
        flow.require(
            len(rows) == 10 and sum(r["optimization_calls"] for r in rows) == 10
        )
        flow.require(all(r["memory_stop"] is None for r in rows))
        allocations = allocation_rows(
            [
                flow.load(easy_dir / "accounting.json")["accounting"],
                flow.load(old_medium_dir / "accounting.json")["accounting"],
                value["accounting"],
            ]
        )
    rows = comparison(sorted(rows, key=lambda r: (r["parent"], r["threads"])))
    return {
        "schema_version": 1,
        "protocol_id": "pr79_offline_sprint_b_review_v1",
        "job3494_return_sha256": RETURN_SHA,
        "runtime_source_commit": flow.HISTORICAL_CLI_SOURCE,
        "archive_sha256": {name: sha for name, sha in ARCHIVES.values()},
        "all_ten_nested_attempts_validated": True,
        "comparison_rows": rows,
        "allocation_rows": allocations,
        "cost_scope": "jobs3489_3490_3494_only_not_all_historical_diagnostics",
        "job3490_optimization_calls": None,
        "job3490_status": "interrupted_memory_observation_lost_preserved_not_imputed",
        "profiles": {
            p: profile([r for r in rows if r["parent"] == p])
            for p in ("easy", "medium")
        },
        "optimization_runs_added": 0,
        "scheduler_queries": 0,
        "raw_logs_included": False,
        "sprint_b_technical_acceptance_supported": True,
        "scientific_reporting_eligible": False,
        "limitations": [
            "Two fitting parents, one seed, shared node; descriptive development comparison only.",
            "Easy target 1% and medium target 10%: never pool target times across parents.",
            "Sampled first observations are not true first crossings; sample counts/drops are retained.",
            "Successful early-stop gaps are not quality measured at a common 3600-second horizon.",
            "Time-limit arms are censored, not successful target times or missing-at-random observations.",
            "Worker RSS, sampled hierarchical cgroup RAM and Slurm step MaxRSS have different scopes.",
            "Unknown job3490 call count and failure cause remain unknown; all three allocation costs retained.",
            "Development profile selection is exploratory, not a predeclared held-out statistical conclusion.",
        ],
    }


def markdown(report):
    out = [
        "# Sprint B: reviewed paired CPU pilot",
        "",
        "Offline review of easy3489 and medium3494; interrupted3490 retained.",
        "",
        "| Parent | Threads | Stop | Runtime s | Final gap % | First observed target s | Sampled cgroup GiB |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report["comparison_rows"]:
        target = row["first_observed_target_seconds"]
        display = "censored" if target is None else f"{target:.3f}"
        out.append(
            f"| {row['parent']} | {row['threads']} | {row['stop']} | {row['solver_runtime_seconds']:.3f} | {100 * row['gap_relative']:.5f} | {display} | {row['sampled_cgroup_peak_bytes'] / 2**30:.3f} |"
        )
    out += ["", "## Development profile", ""]
    for parent, decision in report["profiles"].items():
        out.append(
            f"- {parent}: frontier {decision['strict_pareto_threads']}; selected cap {decision['selected_development_threads']}; target-reaching coverage {decision['eligible_arms']}/{decision['total_arms']}."
        )
    out += [
        "",
        "Strict frontier: first observed target time, process CPU and sampled memory. Select the lowest cap on that frontier. This is an exploratory development choice, not a population-wide optimum.",
        "",
        "## Allocation costs (counted once per job)",
        "",
        "| Job | Elapsed s | Scheduler CPU s | Allocated logical CPU h | Requested physical-core h |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report["allocation_rows"]:
        out.append(
            f"| {row['job_id']} | {row['elapsed_seconds']} | {row['scheduler_total_cpu_seconds']:.3f} | {row['allocated_logical_cpu_hours']:.3f} | {row['requested_physical_core_reservation_hours']:.3f} |"
        )
    out += [
        "",
        "Scope: jobs3489/3490/3494, not the entire historical diagnostic campaign. Full values, speedup eligibility and separate RSS scopes are in the accompanying JSON.",
        "",
        "## Limits",
        "",
    ]
    out += ["- " + item for item in report["limitations"]]
    out += [
        "",
        "Technical Sprint B acceptance is supported by these reviewed returns and the scoped development profile. Existing operational scientific-eligibility flags remain false. Final closure requires code review, exact-head CI and authorized merge; no new optimization or budget is implied.",
        "",
    ]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.output_directory:
        args.output_directory.mkdir(parents=True, exist_ok=False)
        (args.output_directory / "pr79-sprint-b-review.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (args.output_directory / "pr79-sprint-b-review.md").write_text(
            markdown(report), encoding="utf-8", newline="\n"
        )
    print(
        json.dumps(
            {
                "validated_attempts": len(report["comparison_rows"]),
                "profiles": report["profiles"],
                "optimization_runs_added": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
