"""Nonblocking fresh CPU12h operator. Preparation never grants a CPU budget.

No root preparation, inference, training, implicit resume or automatic retry.
The global campaign claim survives changed sources and ambiguous sbatch calls.
"""

import argparse
import importlib.metadata
import json
import os
import platform
import re
import sys
import time
from pathlib import Path

import pr89_cpu_contract as c

previous = c.previous
site = previous.site
accounting = previous.roots.accounting
require, read, parsed, write = c.require, c.read, c.parsed, c.write
BASE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence/pr89")
CLAIM = BASE / "cpu12h-sixty-cells.claim"


class AllocationGate:
    """Keep the selected physical mask observable throughout supervision."""

    def __init__(self, gate):
        self.gate = gate
        self.mask = set(os.sched_getaffinity(0))

    def sample(self):
        require(set(os.sched_getaffinity(0)) == self.mask, "affinity_observation_lost")
        return self.gate.sample()


def source_head():
    return accounting.source_head()


def check_location(stage, commit):
    require(stage.resolve() == BASE / ("cpu12h-" + commit[:12]), "stage_location")
    require(c.ROOT.resolve() == stage / "source", "stage_source_location")


def environment():
    return {
        "python": platform.python_version(),
        **{k: importlib.metadata.version(k) for k in ("numpy", "gurobipy")},
    }


def checkpoint_identity():
    # Metadata/byte verification only: do not call shared_model or torch.load.
    legacy = previous.review.guidance.historical.legacy
    reader = legacy.Reader(
        previous.executor.existing.DATA, seconds=300, max_bytes=1024**3
    )
    reader.scan()
    _, _, _, binding = legacy.discover_model(reader, "mixed")
    require(
        binding["checkpoint_sha256"] == previous.executor.proposal.CHECKPOINT,
        "original_pr86_checkpoint",
    )
    return binding["checkpoint_sha256"]


def wall_seconds(text):
    if text == "UNLIMITED":
        return None
    match = re.fullmatch(r"(?:(\d+)-)?(\d+):(\d{2}):(\d{2})", text)
    require(match is not None, "partition_max_time_unparseable")
    days, hours, minutes, seconds = (int(p or 0) for p in match.groups())
    require(minutes < 60 and seconds < 60, "partition_max_time_units")
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def partition_context(text):
    fields = site.selected_fields(
        text, {"PartitionName", "State", "Nodes", "MaxTime", "TotalNodes"}
    )
    require(
        fields.get("PartitionName") == "batch" and fields.get("State") == "UP",
        "partition_unavailable",
    )
    require(
        fields.get("Nodes") == "dgx-dasci" and fields.get("TotalNodes") == "1",
        "single_node_partition",
    )
    maximum = wall_seconds(fields.get("MaxTime", ""))
    require(maximum is None or maximum >= c.JOB_WALL, "partition_wall_too_short")
    return {
        "partition": "batch",
        "nodes": 1,
        "state": "UP",
        "maximum_wall_seconds": maximum,
        "13h_within_displayed_maximum": True,
        "submission_permission_proven": False,
    }


def prepare(stage):
    accounting.host()
    commit = source_head()
    check_location(stage, commit)
    frozen = c.plan(commit)
    versions = environment()
    require(
        all(p["environment"] == versions for p in frozen["parents"].values()),
        "frozen_tfm_env_versions_changed",
    )
    # Existing reviewed files only. No model deserialization, optimizer or GPU.
    for parent in frozen["parents"].values():
        previous.private_inputs(parent)
    checkpoint_sha = checkpoint_identity()
    context = partition_context(
        accounting.command(["scontrol", "show", "partition", "batch", "--oneliner"])
    )
    plan_sha = write(stage / "plan.json", frozen)
    report = {
        "protocol_id": c.PROTOCOL,
        "source_commit": commit,
        "plan_sha256": plan_sha,
        "environment": versions,
        "partition": context,
        "existing_parent_bindings_verified": 4,
        "existing_root_and_guidance_hashes_verified": True,
        "original_checkpoint_bytes_sha256": checkpoint_sha,
        "new_preparation_calls": 0,
        "optimization_calls_added": 0,
        "training_runs_added": 0,
        "submissions_added": 0,
        "resource_budget_approved": False,
        "launch_only_gates": [
            "held_scheduler_profile_and_permission",
            "allocation_physical_affinity",
            "job_scoped_memory",
            "license_model_loading",
            "predecessor_artifacts",
        ],
        "scientific_reporting_eligible": False,
    }
    sha = write(stage / "preflight.json", report)
    return {
        "preflight_sha256": sha,
        "plan_sha256": plan_sha,
        "output": str(stage / "preflight.json"),
        "submissions_added": 0,
    }


def load(stage):
    accounting.host()
    commit = source_head()
    check_location(stage, commit)
    frozen = parsed(stage / "plan.json")
    require(frozen == c.plan(commit), "source_or_plan_changed")
    require(
        all(p["environment"] == environment() for p in frozen["parents"].values()),
        "environment_changed",
    )
    return frozen


def authorize(stage, approved_sha, decision):
    frozen = load(stage)
    require(c.digest(read(stage / "plan.json")) == approved_sha, "approved_plan_sha256")
    preflight = parsed(stage / "preflight.json")
    require(
        preflight["plan_sha256"] == approved_sha
        and preflight["source_commit"] == frozen["source_commit"]
        and preflight["existing_parent_bindings_verified"] == 4
        and preflight["original_checkpoint_bytes_sha256"]
        == previous.executor.proposal.CHECKPOINT
        and preflight["environment"] == environment()
        and preflight["resource_budget_approved"] is False,
        "installed_preflight_before_authorization",
    )
    # This action is released only after a specific human budget decision.
    value = c.authorization(frozen, decision)
    return {
        "authorization_sha256": write(stage / "authorization.json", value),
        "submissions_added": 0,
    }


def admitted(stage, frozen):
    approval = parsed(stage / "authorization.json")
    c.validate_authorization(frozen, approval)
    require(
        parsed(CLAIM / "claim.json")
        == {
            "plan_sha256": c.digest(c.encoded(frozen)),
            "authorization_sha256": c.digest(read(stage / "authorization.json")),
        },
        "global_campaign_claim",
    )


def folder(stage, index):
    require(type(index) is int and 0 <= index < 60, "cell_index")
    return stage / "runs" / str(index)


def held(text, job, threads, predecessor):
    # Only the new13h field differs. Reuse the complete reviewed resource parser.
    require("TimeLimit=13:00:00" in text, "held_wall_limit")
    old = re.sub(r"(?<!\S)TimeLimit=13:00:00(?=\s|$)", "TimeLimit=04:00:00", text)
    resources = previous.held_profile(old, job, threads)
    resources["TimeLimit"] = "13:00:00"
    dependency = site.selected_fields(text, {"Dependency"}).get("Dependency")
    require(
        dependency
        in (
            (None, "(null)", "None")
            if predecessor is None
            else (f"afterok:{predecessor}", f"afterok:{predecessor}(unfulfilled)")
        ),
        "serial_dependency",
    )
    return {"resources": resources, "dependency": dependency}


def submitted(stage):
    values = []
    for index in range(60):
        path = folder(stage, index) / "submission.json"
        if path.exists():
            require(len(values) == index, "noncontiguous_submissions")
            value = parsed(path)
            require(re.fullmatch(r"[0-9]{1,20}", value["job_id"]), "job_id")
            values.append(value)
    require(len({v["job_id"] for v in values}) == len(values), "duplicate_job_id")
    return values


def submit(stage, approved_sha, count):
    frozen = load(stage)
    require(
        c.digest(read(stage / "authorization.json")) == approved_sha,
        "authorization_sha256",
    )
    c.validate_authorization(frozen, parsed(stage / "authorization.json"))
    partition_context(
        accounting.command(["scontrol", "show", "partition", "batch", "--oneliner"])
    )
    old = submitted(stage)
    start = len(old)
    require(type(count) is int and 1 <= count <= 60 - start, "submission_count")
    # Claims are never erased to resume/retry a partially submitted wave.
    if start == 0:
        CLAIM.mkdir(exist_ok=False)
        write(
            CLAIM / "claim.json",
            {
                "plan_sha256": c.digest(c.encoded(frozen)),
                "authorization_sha256": approved_sha,
            },
        )
    else:
        admitted(stage, frozen)
        require(
            parsed(stage / f"wave-{start - 1}.released.json")["end"] == start,
            "prior_wave_fully_released",
        )
        checked(stage, frozen, start - 1)
    write(stage / f"wave-{start}.intent.json", {"start": start, "count": count})
    for parent in frozen["parents"].values():
        previous.private_inputs(parent)
    checkpoint_identity()
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_", "SRUN_"))
        and k not in ("PYTHONHOME", "PYTHONPATH")
    }
    jobs = [v["job_id"] for v in old]
    for index in range(start, start + count):
        directory = folder(stage, index)
        directory.mkdir(parents=True, exist_ok=False)
        before = jobs[-1] if jobs else None
        write(
            directory / "submission.intent.json",
            {"index": index, "predecessor": before},
        )
        args = [
            "sbatch",
            "--parsable",
            "--hold",
            "--partition=batch",
            "--nodes=1-1",
            "--ntasks=1",
            f"--cpus-per-task={frozen['cells'][index]['threads']}",
            "--hint=nomultithread",
            "--mem=64G",
            "--time=13:00:00",
            "--no-requeue",
            "--kill-on-invalid-dep=yes",
            "--job-name=cfl_cpu12h",
            "--chdir=" + str(c.ROOT),
            "--output=" + str(directory / "batch-%j.private.out"),
            "--error=" + str(directory / "batch-%j.private.err"),
        ]
        if before:
            args += ["--dependency=afterok:" + before]
        args += [
            str(c.ROOT / "scripts/evidence/operate_pr89_cpu.sh"),
            "batch",
            str(stage),
            str(index),
        ]
        job = accounting.command(args, env=env, timeout=30).strip()
        require(
            re.fullmatch(r"[0-9]{1,20}", job) and job not in jobs,
            "ambiguous_sbatch_preserve_claim",
        )
        write(
            directory / "submission.json",
            {"job_id": job, "index": index, "plan_sha256": c.digest(c.encoded(frozen))},
        )
        profile = held(
            accounting.command(["scontrol", "show", "job", job, "--oneliner"]),
            job,
            frozen["cells"][index]["threads"],
            before,
        )
        write(directory / "held_profile.json", profile)
        jobs.append(job)
    # Tail-first release. An ambiguous/failed submission leaves durable held evidence.
    for index in reversed(range(start, start + count)):
        directory = folder(stage, index)
        write(directory / "release.intent.json", {"job_id": jobs[index]})
        accounting.command(["scontrol", "release", jobs[index]])
        write(directory / "released.json", {"job_id": jobs[index]})
    write(stage / f"wave-{start + count - 1}.released.json", {"end": start + count})
    return {
        "job_ids": jobs[start:],
        "submission": "serial_jobs_released",
        "automatic_retry": False,
        "remaining_unsubmitted": 60 - len(jobs),
    }


def validate_child(stage, frozen, index):
    directory = folder(stage, index)
    value = parsed(directory / "child.json")
    cell = frozen["cells"][index]
    require(
        value["plan_sha256"] == c.digest(c.encoded(frozen)) and value["cell"] == cell,
        "child_identity",
    )
    require(
        parsed(directory / "optimize.intent.json")
        == {"cell_sha256": c.digest(c.encoded(cell)), "maximum_calls": 1},
        "optimize_intent",
    )
    c.validate_result(cell, value["result"])
    result = value["result"]
    require(
        value["gurobi_log"]
        == previous.executor.logs.seal_closed_log(directory / "gurobi.private.log"),
        "solver_log_changed",
    )
    start = result["start"]
    binding = frozen["parents"][cell["parent"]]["start_binding"]
    if cell["method"] == "M0":
        require(
            start["submitted_assignments"] == 0 and start["status"] == "not_submitted",
            "control_start",
        )
    else:
        require(
            start["assignment_sha256"] == binding[cell["method"] + "_assignment_sha256"]
            and start["submitted_assignments"] == binding["selected_support"]
            and start["positive_assignments"] == binding["positive_assignments"],
            "start_binding",
        )
    return value


def checked(stage, frozen, index):
    directory = folder(stage, index)
    value = validate_child(stage, frozen, index)
    supervisor = parsed(directory / "supervision.json")
    require(
        supervisor["observation"]["guard_stop"] is None
        and supervisor["observation"]["child_exit_code"] == 0,
        "supervised_stop",
    )
    require(
        supervisor["console_log"]
        == previous.executor.logs.seal_closed_log(directory / "console.private.log"),
        "console_changed",
    )
    require(
        supervisor["job_id"] == parsed(directory / "submission.json")["job_id"],
        "supervisor_job",
    )
    require(
        parsed(directory / "costs.json")
        == attempt_costs(frozen, index, value, supervisor),
        "attempt_cost_binding",
    )
    if index:
        prior = parsed(folder(stage, index - 1) / "child.json")["result"]
        old_cell = frozen["cells"][index - 1]
        if old_cell["parent"] == value["cell"]["parent"]:
            require(
                prior["mathematical_signature_sha256"]
                == value["result"]["mathematical_signature_sha256"],
                "paired_model_signature",
            )
    return {
        "plan_sha256": c.digest(c.encoded(frozen)),
        "index": index,
        "child_sha256": c.digest(read(directory / "child.json")),
        "supervision_sha256": c.digest(read(directory / "supervision.json")),
        "costs_sha256": c.digest(read(directory / "costs.json")),
        "complete": True,
        "scientific_reporting_eligible": False,
    }


def attempt_costs(frozen, index, value, supervisor):
    cell = frozen["cells"][index]
    return {
        "measurement": previous.executor.supervised.reconcile(
            supervisor["observation"],
            value["result"],
            cell["method"],
            preparation=frozen["parents"][cell["parent"]]["preparation_seconds"],
            uses=5,
        ),
        "scenario": "PR86_observed_preparation_allocated_over_five_new_caps_not_new_cold_measurement",
        "whole_job_end_to_end_qualified": False,
    }


def execution(stage, frozen, index):
    admitted(stage, frozen)
    records = submitted(stage)
    require(
        index < len(records)
        and records[index]["job_id"] == os.environ.get("SLURM_JOB_ID"),
        "allocated_job",
    )
    directory = folder(stage, index)
    require(
        parsed(directory / "release.intent.json")
        == {"job_id": records[index]["job_id"]},
        "release_identity",
    )
    require(
        parsed(directory / "submission.json")["plan_sha256"]
        == c.digest(c.encoded(frozen)),
        "submitted_plan",
    )
    profile = parsed(directory / "held_profile.json")
    text = " ".join(k + "=" + v for k, v in profile["resources"].items())
    if profile["dependency"] is not None:
        text += " Dependency=" + profile["dependency"]
    require(
        held(
            text,
            records[index]["job_id"],
            frozen["cells"][index]["threads"],
            records[index - 1]["job_id"] if index else None,
        )
        == profile,
        "held_identity",
    )
    if index:
        require(
            parsed(folder(stage, index - 1) / "checked.json")
            == checked(stage, frozen, index - 1),
            "predecessor_artifact_gate",
        )
    return previous.executor.allocation(frozen["cells"][index]["threads"])


def child(stage, index):
    frozen = load(stage)
    _, gate = execution(stage, frozen, index)
    cell = frozen["cells"][index]
    directory = folder(stage, index)
    write(directory / "child.started.json", {"cell": cell, "maximum_calls": 1})
    base = frozen["parents"][cell["parent"]]
    mip, starts = previous.private_inputs(base)
    binding = base["start_binding"]
    bundle = {
        "cell": cell,
        "start_binding": binding,
        "private_mip_path": str(mip),
        "private_starts_path": str(starts),
    }
    _, assignments = previous.executor.assignments(bundle)
    import pr86_solver

    def claim():
        # Do not silently shorten12h optimize to fit a slow load/audit budget.
        launched = parsed(directory / "dispatch.started.json")["monotonic_seconds"]
        require(
            0 <= time.monotonic() - launched <= 900, "loading_consumed_solver_reserve"
        )
        require(environment() == base["environment"], "environment_at_optimize")
        require(
            previous.executor.existing.dependencies() == frozen["source_sha256_lf"],
            "source_bytes_at_optimize",
        )
        require(
            gate.sample() < previous.executor.memory.POLICY["cgroup_interrupt_bytes"],
            "memory",
        )
        write(
            directory / "optimize.intent.json",
            {"cell_sha256": c.digest(c.encoded(cell)), "maximum_calls": 1},
        )

    result = pr86_solver.solve(
        mip,
        cell["model_sha256"],
        [],
        "unguided_control" if assignments is None else "partial_mip_start",
        solution_path=directory / "solution.private.json.gz",
        preselected_assignments=assignments,
        reported_method=cell["method"],
        private_log_path=directory / "gurobi.private.log",
        cell=cell,
        before_optimize=claim,
        execution_policy=c,
    )
    value = {
        "plan_sha256": c.digest(c.encoded(frozen)),
        "cell": cell,
        "result": {
            **previous.executor.existing.public_result(result),
            "optimization_calls": result["optimization_calls"],
            "temporal_evidence": result["temporal_evidence"],
        },
        "gurobi_log": previous.executor.logs.seal_closed_log(
            directory / "gurobi.private.log"
        ),
    }
    write(directory / "child.json", value)
    validate_child(stage, frozen, index)


def run(stage, index):
    frozen = load(stage)
    job, gate = execution(stage, frozen, index)
    directory = folder(stage, index)
    write(directory / "batch.started.json", {"job_id": job, "index": index})
    write(directory / "dispatch.started.json", {"monotonic_seconds": time.monotonic()})
    observation = previous.executor.memory.supervise(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "child",
            "--stage",
            str(stage),
            "--index",
            str(index),
        ],
        directory / "console.private.log",
        c.CHILD_DEADLINE,
        AllocationGate(gate),
    )
    write(
        directory / "supervision.json",
        {
            "job_id": job,
            "observation": observation,
            "console_log": previous.executor.logs.seal_closed_log(
                directory / "console.private.log"
            ),
        },
    )
    value = validate_child(stage, frozen, index)
    write(
        directory / "costs.json",
        attempt_costs(frozen, index, value, parsed(directory / "supervision.json")),
    )
    write(directory / "checked.json", checked(stage, frozen, index))
    return 0


def status(stage):
    frozen = load(stage)
    admitted(stage, frozen)
    result = []
    records = submitted(stage)
    require(records, "no_submitted_jobs")
    all_text = accounting.command(
        [
            "sacct",
            "--noheader",
            "--parsable2",
            "-j",
            ",".join(r["job_id"] for r in records),
            "--format=" + accounting.FIELDS,
        ]
    )
    for record in records:
        job = record["job_id"]
        text = "\n".join(
            line
            for line in all_text.splitlines()
            if line.split("|", 1)[0].split(".", 1)[0] == job
        )
        result.append(accounting.parse_accounting(text, job))
    return {
        "jobs": result,
        "terminal": bool(result) and all(r["terminal"] for r in result),
        "submitted": len(result),
        "unsubmitted": 60 - len(result),
    }


def collect(stage):
    frozen = load(stage)
    states = status(stage)
    require(states["terminal"], "query_once_after_terminal_no_wait_loop")
    destination = stage / f"return-{len(states['jobs']):02d}.json"
    if destination.exists():
        original = read(destination)
        report = review_return(original, c.digest(original))
        return {
            "return_sha256": c.digest(original),
            "output": str(destination),
            **report,
            "preserved_existing_return": True,
        }
    rows = []
    for i, state in enumerate(states["jobs"]):
        directory = folder(stage, i)
        root = next(r for r in state["rows"] if r["JobID"] == state["job_id"])
        verified = False
        try:
            verified = parsed(directory / "checked.json") == checked(stage, frozen, i)
        except (ValueError, OSError, KeyError, TypeError):
            pass  # Preserve complete or failed envelope; never fabricate a result.
        rows.append(
            {
                "cell": frozen["cells"][i],
                "accounting": state,
                "complete": verified
                and root["State"] == "COMPLETED"
                and root["ExitCode"] == "0:0",
                "child": parsed(directory / "child.json")
                if (directory / "child.json").exists()
                else None,
                "supervision": parsed(directory / "supervision.json")
                if (directory / "supervision.json").exists()
                else None,
                "checked": parsed(directory / "checked.json") if verified else None,
                "costs": parsed(directory / "costs.json") if verified else None,
            }
        )
    value = {
        "protocol_id": c.PROTOCOL,
        "plan": frozen,
        "plan_sha256": c.digest(c.encoded(frozen)),
        "authorization": parsed(stage / "authorization.json"),
        "rows": rows,
        "complete_cells": sum(r["complete"] for r in rows),
        "scientific_reporting_eligible": False,
        "raw_logs_included": False,
        "remaining_dispatch_admitted": False,
    }
    sha = write(destination, value)
    return {
        "return_sha256": sha,
        "output": str(destination),
        "complete_cells": value["complete_cells"],
        "remaining_dispatch_admitted": False,
    }


def review_return(raw, expected_sha):
    require(c.digest(raw) == expected_sha, "transfer_hash")
    value = previous.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    require(frozen == c.plan(frozen["source_commit"]), "return_plan")
    require(value["plan_sha256"] == c.digest(c.encoded(frozen)), "return_plan_sha")
    c.validate_authorization(frozen, value["authorization"])
    require(
        value["scientific_reporting_eligible"] is False
        and value["raw_logs_included"] is False
        and value["remaining_dispatch_admitted"] is False,
        "return_scope",
    )
    rows = value["rows"]
    require(1 <= len(rows) <= 60, "return_size")
    jobs = []
    complete = 0
    for i, row in enumerate(rows):
        require(row["cell"] == frozen["cells"][i], "return_cell_order")
        state = row["accounting"]
        job = state["job_id"]
        require(re.fullmatch(r"[0-9]{1,20}", job) and job not in jobs, "return_job")
        jobs.append(job)
        # Reparse the allowlisted scheduler cells rather than trusting terminal=true.
        text = "\n".join(
            "|".join(str(r[k]) for k in accounting.FIELDS.split(","))
            for r in state["rows"]
        )
        require(
            accounting.parse_accounting(text, job) == state and state["terminal"],
            "return_accounting",
        )
        require(type(row["complete"]) is bool, "return_complete")
        if row["child"] is not None:
            child_value = row["child"]
            require(
                child_value["cell"] == row["cell"]
                and child_value["plan_sha256"] == value["plan_sha256"],
                "return_child_binding",
            )
        if row["complete"]:
            c.validate_result(row["cell"], row["child"]["result"])
            supervisor = row["supervision"]
            require(
                supervisor["job_id"] == job
                and supervisor["observation"]["guard_stop"] is None
                and supervisor["observation"]["child_exit_code"] == 0,
                "return_supervision",
            )
            root = next(r for r in state["rows"] if r["JobID"] == job)
            require(
                root["State"] == "COMPLETED" and root["ExitCode"] == "0:0",
                "return_job_success",
            )
            require(
                row["checked"]
                == {
                    "plan_sha256": value["plan_sha256"],
                    "index": i,
                    "child_sha256": c.digest(c.encoded(row["child"])),
                    "supervision_sha256": c.digest(c.encoded(supervisor)),
                    "costs_sha256": c.digest(c.encoded(row["costs"])),
                    "complete": True,
                    "scientific_reporting_eligible": False,
                },
                "nested_result_seal",
            )
            require(
                row["costs"] == attempt_costs(frozen, i, row["child"], supervisor),
                "return_cost_reconciliation",
            )
            complete += 1
    require(value["complete_cells"] == complete, "return_count")
    return {
        "transfer_and_nested_review_passed": True,
        "complete_cells": complete,
        "submitted_cells": len(rows),
        "scientific_reporting_eligible": False,
        "remaining_dispatch_admitted": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare",
            "authorize",
            "submit",
            "run",
            "child",
            "status",
            "collect",
            "review",
        ),
    )
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--authorization-sha256")
    parser.add_argument("--decision-reference")
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--index", type=int)
    args = parser.parse_args()
    if args.action == "review":
        value = review_return(read(args.receipt), args.expected_sha256)
    elif args.action == "authorize":
        value = authorize(
            args.stage, args.approved_plan_sha256, args.decision_reference
        )
    elif args.action == "submit":
        value = submit(args.stage, args.authorization_sha256, args.count)
    elif args.action in {"run", "child"}:
        value = {"run": run, "child": child}[args.action](args.stage, args.index)
    else:
        value = {"prepare": prepare, "status": status, "collect": collect}[args.action](
            args.stage
        )
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
