"""Isolated PR86 attempt adapter; no scheduler, budget recorder or retry.

An admission review is an input, not something this executor can grant itself.
Only private execution bundles with separately reviewed preparation/formulation
and explicit resource approval can reach the solver. No admitted bundle exists
in the repository. Historical E0 executors and receipts are not rewritten.
"""

import argparse
import importlib.metadata
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

import cpu_comparison_contract as logs
import e0_three_method_executor as existing
import paired_memory_runtime_v2 as memory
import plan_pr86_comparison as proposal
import pr86_attempt_instrumentation as metered
import pr86_cost_accounting as costs
import pr86_supervised_costs as supervised
from pr66_thread_pilot import physical_mask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from cfl_gnn.graph.gurobi_graph_artifact import canonical_sha256  # noqa: E402
from cfl_gnn.graph.instance_provenance import sha256_file  # noqa: E402

require = metered.require
PROTOCOL = "pr86_isolated_attempt_adapter_v1"
GATES = (
    "formulation_review",
    "preparation_review",
    "environment_review",
    "resource_approval",
)


def load_bundle(path, expected_sha):
    """Recheck the same admission at launch AND inside the child process."""
    path = Path(path)
    raw = existing.read(path)
    require(metered.digest(raw) == expected_sha, "execution_bundle_hash")
    bundle = existing.review.flow.meta.strict_json(raw)
    require(bundle["protocol_id"] == PROTOCOL, "execution_protocol")
    require(bundle["automatic_retry"] is False, "retry")
    require(bundle["scientific_reporting_eligible"] is False, "scientific_scope")
    require(bundle["source_sha256_lf"] == existing.dependencies(), "source_bytes")
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    require(head == bundle["context"]["source_commit"], "installed_commit")
    require(
        re.fullmatch(r"[0-9a-f]{40}", bundle["context"]["source_commit"]) is not None,
        "source_commit",
    )
    cell = bundle["cell"]
    metered.parameters(cell)
    plan, cells = proposal.build()
    require(cell in cells, "cell_not_in_frozen_matrix")
    require(
        bundle["context"]["plan_sha256"] == proposal.digest(proposal.encoded(plan)),
        "frozen_plan",
    )
    require(
        bundle["context"]["binding_sha256"]
        == metered.digest(metered.encoded(bundle["start_binding"])),
        "start_binding_hash",
    )
    for field in (
        "model_sha256",
        "root_sha256",
        "graph_sha256",
        "prediction_sha256",
        "checkpoint_sha256",
        "private_starts_sha256",
        "M1_assignment_sha256",
        "M2_assignment_sha256",
    ):
        require(
            re.fullmatch(r"[0-9a-f]{64}", bundle["start_binding"][field]),
            "binding_digest",
        )
    require(
        bundle["start_binding"]["checkpoint_sha256"] == proposal.CHECKPOINT,
        "bound_checkpoint",
    )
    for key in GATES:
        ref = bundle[key]
        require(re.fullmatch(r"[A-Za-z0-9_-]+\.json", ref["file"]), "review_filename")
        review_raw = existing.read(path.parent / ref["file"])
        require(metered.digest(review_raw) == ref["sha256"], key + "_hash")
        review = existing.review.flow.meta.strict_json(review_raw)
        require(review["accepted"] is True, key + "_not_accepted")
        require(
            review["context"]
            == {k: bundle["context"][k] for k in ("source_commit", "plan_sha256")},
            key + "_context",
        )
        require(
            review["accepted_parent_bindings"][cell["parent"]]
            == bundle["context"]["binding_sha256"],
            key + "_binding",
        )
        if key == "resource_approval":
            require(
                review["explicit_user_authorization"] is True, "budget_not_approved"
            )
            require(
                type(review["maximum_optimization_calls"]) is int
                and 1 <= review["maximum_optimization_calls"] <= 210
                and len(review["approved_cell_ids"])
                == review["maximum_optimization_calls"]
                and len(set(review["approved_cell_ids"]))
                == len(review["approved_cell_ids"])
                and set(review["approved_cell_ids"]).issubset(
                    {c["cell_id"] for c in cells}
                )
                and cell["cell_id"] in review["approved_cell_ids"],
                "call_budget",
            )
            require(review["child_deadline_seconds"] == 3780, "deadline_budget")
        if key == "environment_review":
            actual = {
                "python": platform.python_version(),
                **{
                    name: importlib.metadata.version(name)
                    for name in ("numpy", "gurobipy")
                },
            }
            require(review["versions"] == actual, "installed_environment")
        if key == "preparation_review":
            require(
                review["preparation_seconds_by_parent"][cell["parent"]]
                == bundle["preparation_seconds"],
                "reviewed_preparation_costs",
            )
    # These reviews must be independently produced and accepted. Hash integrity
    # is not proof of their scientific truth or of human authorization.
    preparation = bundle["preparation_seconds"]
    require(set(preparation) == set(costs.PREPARATION), "preparation_regions")
    for value in preparation.values():
        costs.seconds(value)
    require(
        bundle["preparation_binding"] == bundle["start_binding"],
        "preparation_start_identity",
    )
    require(bundle["allocation_threads"] == cell["threads"], "allocation_threads")
    require(bundle["checkpoint_sha256"] == proposal.CHECKPOINT, "checkpoint")
    return bundle


def allocation(threads):
    require(sys.platform == "linux", "linux_required")
    require(os.uname().nodename.split(".")[0] == "dgx-dasci", "host")
    for key, value in {
        "CONDA_DEFAULT_ENV": "tfm_env",
        "SLURM_CPUS_PER_TASK": str(threads),
        "SLURM_JOB_NUM_NODES": "1",
        "SLURM_MEM_PER_NODE": "65536",
    }.items():
        require(os.environ.get(key) == value, "allocation_" + key)
    require(os.environ.get("SLURM_RESTART_COUNT", "0") == "0", "requeue")
    require(
        not os.environ.get("SLURM_JOB_GPUS") and not os.environ.get("SLURM_STEP_GPUS"),
        "gpu",
    )
    job = os.environ.get("SLURM_JOB_ID", "")
    require(re.fullmatch(r"[0-9]+", job), "job")

    def topology(cpu):
        folder = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        return tuple(
            int((folder / field).read_text())
            for field in ("physical_package_id", "core_id")
        )

    selected = physical_mask(os.sched_getaffinity(0), topology, required=threads)
    os.sched_setaffinity(0, selected)
    require(set(os.sched_getaffinity(0)) == set(selected), "affinity")
    gate = memory.MemoryGate(job)
    memory.validate_public(gate.public())
    require(gate.sample() < memory.POLICY["cgroup_interrupt_bytes"], "initial_memory")
    return job, gate


def assignments(bundle):
    cell = bundle["cell"]
    binding = bundle["start_binding"]
    require(binding["model_sha256"] == cell["model_sha256"], "bound_model")
    mip = Path(bundle["private_mip_path"])
    require(not mip.is_symlink() and mip.is_file(), "model_file")
    require(sha256_file(mip) == cell["model_sha256"], "model_bytes")
    raw = existing.read(Path(bundle["private_starts_path"]))
    require(metered.digest(raw) == binding["private_starts_sha256"], "start_bytes")
    starts = existing.review.flow.meta.strict_json(raw)
    for method, key in (("M1", "root_lp"), ("M2", "gnn")):
        chosen = starts[key]["assignments"]
        require(
            canonical_sha256(chosen) == binding[method + "_assignment_sha256"],
            "assignment_hash",
        )
        require(
            len(chosen) == binding["selected_support"]
            and sum(a["value"] for a in chosen) == binding["positive_assignments"],
            "matched_budget",
        )
    return mip, None if cell["method"] == "M0" else starts[
        "root_lp" if cell["method"] == "M1" else "gnn"
    ]["assignments"]


def validate_child(bundle, value, output):
    result = value["result"]
    metered.validate_result(bundle["cell"], result)
    require(
        value["cell_sha256"] == metered.digest(metered.encoded(bundle["cell"])),
        "child_cell",
    )
    method = bundle["cell"]["method"]
    binding = bundle["start_binding"]
    start = result["start"]
    if method == "M0":
        require(
            start["submitted_assignments"] == 0 and start["status"] == "not_submitted",
            "control_start",
        )
    else:
        require(
            start["assignment_sha256"] == binding[method + "_assignment_sha256"]
            and start["submitted_assignments"] == binding["selected_support"]
            and start["positive_assignments"] == binding["positive_assignments"],
            "child_start",
        )
    require(
        value["gurobi_log"] == logs.seal_closed_log(output / "gurobi.private.log"),
        "solver_log_changed",
    )
    return result


def child(bundle_path, expected_sha, output):
    bundle = load_bundle(bundle_path, expected_sha)
    _, gate = allocation(bundle["allocation_threads"])
    require(output.is_dir() and not output.is_symlink(), "attempt_directory")
    identity = existing.parsed(output / "attempt.started.json")
    require(
        identity["cell"] == bundle["cell"] and identity["context"] == bundle["context"],
        "child_attempt_identity",
    )
    metered.write_once(output / "child.started.json", {"bundle_sha256": expected_sha})
    mip, chosen = assignments(bundle)
    import pr86_solver

    def claim():
        # Revalidate immediately before the only optimization. Never a retry.
        load_bundle(bundle_path, expected_sha)
        require(gate.sample() < memory.POLICY["cgroup_interrupt_bytes"], "memory")
        metered.write_once(
            output / "optimize.intent.json",
            {
                "cell_sha256": metered.digest(metered.encoded(bundle["cell"])),
                "maximum_calls": 1,
            },
        )

    result = pr86_solver.solve(
        mip,
        bundle["cell"]["model_sha256"],
        [],
        "unguided_control" if chosen is None else "partial_mip_start",
        preselected_assignments=chosen,
        reported_method=bundle["cell"]["method"],
        private_log_path=output / "gurobi.private.log",
        solution_path=output / "solution.private.json.gz",
        cell=bundle["cell"],
        before_optimize=claim,
    )
    require(sha256_file(mip) == bundle["cell"]["model_sha256"], "model_changed")
    value = {
        "cell_sha256": metered.digest(metered.encoded(bundle["cell"])),
        "result": {
            **existing.public_result(result),
            "optimization_calls": result["optimization_calls"],
        },
        "gurobi_log": logs.seal_closed_log(output / "gurobi.private.log"),
    }
    validate_child(bundle, value, output)
    metered.write_once(output / "child.json", value)


def run_attempt(bundle_path, expected_sha, output):
    bundle = load_bundle(bundle_path, expected_sha)
    job, gate = allocation(bundle["allocation_threads"])
    assignments(bundle)

    def dispatch(directory, _claim):
        # The child, not this parent, owns the durable optimize intent.
        observation = memory.supervise(
            [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "child",
                "--bundle",
                str(bundle_path),
                "--expected-sha256",
                expected_sha,
                "--output",
                str(directory),
            ],
            directory / "console.private.log",
            3780,
            gate,
        )
        metered.write_once(
            directory / "supervision.json",
            {
                "job_id": job,
                "bundle_sha256": expected_sha,
                "observation": observation,
                "console_log": logs.seal_closed_log(directory / "console.private.log"),
            },
        )
        result = None
        if (directory / "child.json").exists():
            result = validate_child(
                bundle, existing.parsed(directory / "child.json"), directory
            )
        return observation, result

    report = metered.observe_attempt(
        output, bundle["cell"], bundle["context"], dispatch=dispatch
    )
    if report["pause_remaining_matrix"]:
        return report
    result = existing.parsed(output / "child.json")["result"]
    observation = existing.parsed(output / "supervision.json")["observation"]
    measured = supervised.reconcile(
        observation,
        result,
        bundle["cell"]["method"],
        preparation=bundle["preparation_seconds"],
    )
    metered.write_once(
        output / "prepared_costs.json",
        {
            "execution_bundle_sha256": expected_sha,
            "measurement": measured,
            "whole_job_end_to_end_qualified": False,
        },
    )
    return report


def run_group(requests, output):
    """One frozen three-method group, no scheduler or automatic continuation.

    The surrounding operator must own campaign-wide claims, approved budgets
    and Slurm accounting. This function does not admit a campaign by itself.
    """
    require(len(requests) == 3, "three_method_group")
    bundles = [load_bundle(path, sha) for path, sha in requests]
    plan, cells = proposal.build()
    group_id = bundles[0]["cell"]["group_id"]
    expected = [c for c in cells if c["group_id"] == group_id]
    require([b["cell"] for b in bundles] == expected, "frozen_group_order")
    require(
        all(
            b["context"] == bundles[0]["context"]
            and b["start_binding"] == bundles[0]["start_binding"]
            and b["preparation_seconds"] == bundles[0]["preparation_seconds"]
            for b in bundles
        ),
        "paired_group_context",
    )
    group = next(g for g in plan["groups"] if g["group_id"] == group_id)
    output = Path(output)
    output.mkdir(exist_ok=False)
    metered.write_once(
        output / "group.started.json",
        {"group_id": group_id, "bundle_sha256": [sha for _, sha in requests]},
    )
    started = time.monotonic()
    rows, stop, paired_signature, paired_parameters = [], None, None, None
    try:
        for index, (path, sha) in enumerate(requests):
            if (
                time.monotonic() - started + group["child_deadline_seconds"]
                > group["job_wall_seconds"]
            ):
                stop = "group_deadline_reserve"
                break
            attempt = output / f"attempt-{index}"
            report = run_attempt(path, sha, attempt)
            rows.append(
                {
                    "cell_id": bundles[index]["cell"]["cell_id"],
                    "attempt_sha256": metered.digest(
                        existing.read(attempt / "attempt.json")
                    ),
                    "stop_code": report["stop_code"],
                }
            )
            if report["pause_remaining_matrix"]:
                stop = report["stop_code"]
                break
            result = existing.parsed(attempt / "child.json")["result"]
            signature, parameters = (
                result["mathematical_signature_sha256"],
                result["parameters"],
            )
            if index:
                require(
                    signature == paired_signature and parameters == paired_parameters,
                    "unpaired_model_or_parameters",
                )
            paired_signature, paired_parameters = signature, parameters
    except BaseException:
        stop = "group_interrupted_or_failed"
        raise
    finally:
        metered.write_once(
            output / "group.json",
            {
                "protocol_id": PROTOCOL,
                "group_id": group_id,
                "attempts": rows,
                "stop_code": stop,
                "complete": len(rows) == 3 and stop is None,
                "pause_remaining_matrix": stop is not None,
                "scientific_reporting_eligible": False,
                "whole_job_end_to_end_qualified": False,
            },
        )
    return existing.parsed(output / "group.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("child",))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    child(args.bundle.resolve(), args.expected_sha256, args.output.resolve())


if __name__ == "__main__":
    main()
