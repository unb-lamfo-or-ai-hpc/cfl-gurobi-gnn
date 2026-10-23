"""First approved PR86 paired group; one submission, three solves, no retry.

The first group is inside the 210-cell budget. Remaining dispatch is deliberately
blocked until independent review. Reuses the isolated executor and watchdog.
"""

import argparse
import base64
import json
import os
import re
import tempfile
import time
from pathlib import Path

import paired_matrix_workflow_v3 as site
import pr86_isolated_executor as executor
import pr86_root_preparation as roots
import review_pr86_job3521 as review

require, read, parsed, write = roots.require, roots.read, roots.parsed, roots.write
encoded, digest = roots.encoded, roots.digest
ROOT, BASE = roots.ROOT, roots.BASE
PROTOCOL = "pr86_first_main_group_v1"
GROUP = "F0-threads1-seed42"
GUIDANCE = BASE / ("guidance-" + review.COMMIT[:12])
CLAIM = BASE / "main-comparison-first-group.claim"
FILES = (
    "attempt.started.json",
    "attempt.json",
    "timing_tail.json",
    "child.json",
    "supervision.json",
    "prepared_costs.json",
)


def plan(commit):
    return plan_for_group(commit, 0)


def plan_for_group(commit, group_index):
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "commit")
    original, cells = executor.proposal.build()
    require(type(group_index) is int and 0 <= group_index < 70, "group_index")
    group = original["groups"][group_index]
    value, rows, report = review.review(read(review.DESTINATION / "public_return.json"))
    index = next(i for i, r in enumerate(rows) if r["parent"] == group["parent"])
    row = value["child"]["rows"][index]
    binding = {
        k: row[k]
        for k in (
            "model_sha256",
            "root_sha256",
            "graph_sha256",
            "prediction_sha256",
            "checkpoint_sha256",
            "private_starts_sha256",
            "M1_assignment_sha256",
            "M2_assignment_sha256",
            "selected_support",
            "positive_assignments",
        )
    }
    context = {
        "source_commit": commit,
        "plan_sha256": executor.proposal.digest(executor.proposal.encoded(original)),
        "binding_sha256": digest(encoded(binding)),
    }
    runtime = value["child"]["runtime"]["packages"]
    return {
        "protocol_id": PROTOCOL,
        "source_commit": commit,
        "source_sha256_lf": executor.existing.dependencies(),
        "context": context,
        "group": group,
        "cells": [c for c in cells if c["group_id"] == group["group_id"]],
        "start_binding": binding,
        "preparation_seconds": {
            "root": rows[index]["root_supervised_seconds"],
            **{
                k: row["regions_seconds"][k]
                for k in ("features", "inference", "assembly_gnn", "assembly_lp")
            },
        },
        "environment": {
            "python": runtime["python"],
            **{k: runtime["packages"][k] for k in ("numpy", "gurobipy")},
        },
        "guidance_return_sha256": review.SHA,
        "root_return_sha256": review.roots.SHA,
        "campaign_budget_request_sha256": digest(encoded(review.budget(report))),
        "maximum_optimization_calls": 3,
        "maximum_submissions": 1,
        "job_wall_seconds": 14400,
        "child_deadline_seconds": 3780,
        "memory": executor.memory.POLICY,
        "automatic_retry": False,
        "remaining_dispatch_admitted": False,
        "resource_budget_approved": False,
        "scientific_reporting_eligible": False,
    }


def load(stage):
    frozen = parsed(stage / "plan.json")
    require(frozen == plan(roots.head()), "source_or_plan_changed")
    require(
        stage.resolve() == BASE / ("main-first-" + frozen["source_commit"][:12]),
        "stage",
    )
    require(not (ROOT / "gurobi.env").exists(), "unexpected_parameter_file")
    return frozen


def private_inputs(frozen):
    value, _, _ = review.review(read(GUIDANCE / "public_return.json"))
    parent = frozen["group"]["parent"]
    index = next(
        i for i, r in enumerate(value["child"]["rows"]) if r["parent"] == parent
    )
    require(
        frozen["start_binding"]["private_starts_sha256"]
        == value["child"]["rows"][index]["private_starts_sha256"],
        "review_binding",
    )
    original, _ = executor.proposal.build()
    inputs = roots.inputs({"parents": original["parents"]})
    folder = GUIDANCE / "run" / str(index)
    for filename, key in (
        ("graph.private.pt", "graph_sha256"),
        ("predictions.private.json", "prediction_sha256"),
        ("starts.private.json", "private_starts_sha256"),
    ):
        require(
            roots.sha256_file(folder / filename) == frozen["start_binding"][key],
            "private_artifact_changed",
        )
    review.roots.review(read(review.guidance.ROOT_STAGE / "public_return.json"))
    require(
        roots.sha256_file(
            review.guidance.ROOT_STAGE / "run" / str(index) / "root.private.json.gz"
        )
        == frozen["start_binding"]["root_sha256"],
        "private_root_changed",
    )
    require(inputs[index]["parent"] == parent, "private_parent_index")
    mip = Path(inputs[index]["mip_path"])
    require(
        roots.sha256_file(mip) == frozen["cells"][0]["model_sha256"],
        "private_model_changed",
    )
    return mip, folder / "starts.private.json"


def prepare(stage):
    roots.accounting.host()
    frozen = plan(roots.head())
    require(
        stage.resolve() == BASE / ("main-first-" + frozen["source_commit"][:12]),
        "stage",
    )
    private_inputs(frozen)
    return {
        "plan_sha256": write(stage / "plan.json", frozen),
        "maximum_optimization_calls": 3,
        "resource_budget_approved": False,
    }


def approval(frozen):
    return {
        "plan_sha256": digest(encoded(frozen)),
        "explicit_user_authorization": True,
        "campaign_budget_request_sha256": frozen["campaign_budget_request_sha256"],
        "approved_campaign_calls_ceiling": 210,
        "approved_campaign_jobs_ceiling": 70,
        "this_stage_calls_ceiling": 3,
        "this_stage_jobs_ceiling": 1,
        "remaining_dispatch_requires_first_group_review": True,
        "automatic_retry": False,
    }


def bundles(frozen, stage, mip, starts):
    """Written only after explicit approval, never by prepare()."""
    folder = stage / "admission"
    folder.mkdir(exist_ok=False)
    context, parent = frozen["context"], frozen["cells"][0]["parent"]
    common = {
        "accepted": True,
        "context": {k: context[k] for k in ("source_commit", "plan_sha256")},
        "accepted_parent_bindings": {parent: context["binding_sha256"]},
    }
    refs = {}
    for key, details in {
        "preparation_review": {
            "preparation_seconds_by_parent": {parent: frozen["preparation_seconds"]},
            "guidance_return_sha256": review.SHA,
            "root_return_sha256": review.roots.SHA,
            "scope": "reviewed_scoped_costs_not_standalone_cold_measurement",
        },
        "environment_review": {"versions": frozen["environment"]},
        "resource_approval": {
            "explicit_user_authorization": True,
            "maximum_optimization_calls": 3,
            "approved_cell_ids": [c["cell_id"] for c in frozen["cells"]],
            "child_deadline_seconds": 3780,
            "stage_approval_sha256": digest(read(stage / "approval.json")),
        },
    }.items():
        filename = key + ".json"
        refs[key] = {
            "file": filename,
            "sha256": write(folder / filename, {**common, **details}),
        }
    requests = []
    for i, cell in enumerate(frozen["cells"]):
        value = {
            "protocol_id": executor.PROTOCOL,
            "formulation_contract": executor.FORMULATION_CONTRACT,
            "automatic_retry": False,
            "scientific_reporting_eligible": False,
            "source_sha256_lf": frozen["source_sha256_lf"],
            "context": context,
            "cell": cell,
            "start_binding": frozen["start_binding"],
            "preparation_binding": frozen["start_binding"],
            "preparation_seconds": frozen["preparation_seconds"],
            "checkpoint_sha256": executor.proposal.CHECKPOINT,
            "allocation_threads": cell["threads"],
            "private_mip_path": str(mip),
            "private_starts_path": str(starts),
            **refs,
        }
        path = folder / f"bundle-{i}.json"
        sha = write(path, value)
        executor.load_bundle(path, sha)
        executor.assignments(value)
        requests.append({"file": path.name, "sha256": sha})
    write(stage / "requests.json", requests)


def held_profile(text, job, threads=1):
    expected = {
        "JobId": job,
        "JobState": "PENDING",
        "Reason": "JobHeldUser",
        "Partition": "batch",
        "Requeue": "0",
        "Restarts": "0",
        "NumTasks": "1",
        "CPUs/Task": str(threads),
        "TimeLimit": "04:00:00",
    }
    fields = site.selected_fields(
        text,
        set(expected)
        | {"NumNodes", "NumCPUs", "MinMemoryNode", "TRES", "OverSubscribe"},
    )
    require(
        all(fields.get(k) == v for k, v in expected.items()), "held_profile_contract"
    )
    require(
        site.singleton(fields.get("NumNodes")) == 1
        and site.singleton(fields.get("NumCPUs")) in (threads, 2 * threads),
        "held_cpu_topology",
    )
    require(fields.get("MinMemoryNode") in ("64G", "65536M"), "held_memory")
    require(fields.get("OverSubscribe") in ("OK", "NO"), "shared_node")
    items = [part.split("=") for part in fields.get("TRES", "").split(",")]
    require(all(len(pair) == 2 for pair in items), "tres")
    tres = dict(items)
    require(
        len(tres) == len(items) and set(tres) <= {"cpu", "mem", "node", "billing"},
        "tres_unique_no_gpu",
    )
    require(
        tres.get("node") == "1"
        and tres.get("mem") in ("64G", "65536M")
        and site.singleton(tres.get("cpu")) == site.singleton(fields["NumCPUs"]),
        "tres_resources",
    )
    if "billing" in tres:
        require(re.fullmatch(r"[0-9]+", tres["billing"]), "billing")
    return fields


def submit(stage, approved_sha):
    roots.accounting.host()
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "environment")
    frozen = load(stage)
    require(digest(read(stage / "plan.json")) == approved_sha, "approved_plan_sha")
    mip, starts = private_inputs(frozen)
    CLAIM.mkdir(exist_ok=False)  # Survives changed source and ambiguous sbatch.
    write(CLAIM / "claim.json", {"plan_sha256": approved_sha, "stage": str(stage)})
    write(stage / "approval.json", approval(frozen))
    bundles(frozen, stage, mip, starts)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_", "SRUN_"))
        and k not in ("PYTHONHOME", "PYTHONPATH")
    }
    env.update(
        PR86_SOURCE=str(ROOT), PR86_STAGE=str(stage), PR86_PYTHON=os.sys.executable
    )
    response = roots.accounting.command(
        [
            "sbatch",
            "--parsable",
            "--hold",
            "--partition=batch",
            "--nodes=1-1",
            "--ntasks=1",
            "--cpus-per-task=1",
            "--hint=nomultithread",
            "--mem=64G",
            "--time=04:00:00",
            "--no-requeue",
            "--job-name=cfl_pr86_first",
            "--chdir=" + str(ROOT),
            "--output=" + str(stage / "job-%j.private.out"),
            "--error=" + str(stage / "job-%j.private.err"),
            str(ROOT / "scripts/evidence/operate_pr86_main_first.sh"),
            "batch",
        ],
        env=env,
        timeout=30,
    )
    job = response.strip()
    require(re.fullmatch(r"[0-9]{1,20}", job), "ambiguous_sbatch_preserve_claim")
    write(stage / "submission.json", {"job_id": job, "plan_sha256": approved_sha})
    profile = held_profile(
        roots.accounting.command(["scontrol", "show", "job", job, "--oneliner"]), job
    )
    write(stage / "held_profile.json", profile)
    write(stage / "release.intent.json", {"job_id": job})
    roots.accounting.command(["scontrol", "release", job])
    write(stage / "released.json", {"job_id": job})
    return {
        "job_id": job,
        "submission": "released",
        "maximum_optimization_calls": 3,
        "automatic_retry": False,
    }


def admitted(stage, frozen):
    require(parsed(stage / "approval.json") == approval(frozen), "approval")
    require(
        parsed(CLAIM / "claim.json")
        == {"plan_sha256": digest(encoded(frozen)), "stage": str(stage)},
        "global_claim",
    )
    record = parsed(stage / "submission.json")
    require(record["plan_sha256"] == digest(encoded(frozen)), "submitted_plan")
    require(re.fullmatch(r"[0-9]{1,20}", record["job_id"]), "job_id")
    profile = parsed(stage / "held_profile.json")
    require(
        held_profile(
            " ".join(k + "=" + v for k, v in profile.items()), record["job_id"]
        )
        == profile,
        "held_record",
    )
    require(
        parsed(stage / "release.intent.json") == {"job_id": record["job_id"]},
        "release_intent",
    )
    return record


def run(stage):
    frozen = load(stage)
    record = admitted(stage, frozen)
    require(record["job_id"] == os.environ.get("SLURM_JOB_ID"), "allocated_job")
    executor.allocation(1)
    requests = parsed(stage / "requests.json")
    require(
        len(requests) == 3
        and [r["file"] for r in requests] == [f"bundle-{i}.json" for i in range(3)],
        "requests",
    )
    started = time.monotonic()
    try:
        value = executor.run_group(
            [(stage / "admission" / r["file"], r["sha256"]) for r in requests],
            stage / "run",
        )
        return 0 if value["complete"] else 2
    finally:
        write(
            stage / "batch.json",
            {
                "job_id": record["job_id"],
                "observed_group_dispatch_seconds": time.monotonic() - started,
                "excludes": [
                    "pre_dispatch_validation",
                    "batch_receipt_write",
                    "queueing",
                ],
                "scientific_reporting_eligible": False,
            },
        )


def collect(stage):
    frozen = load(stage)
    admitted(stage, frozen)
    state = roots.status(stage)
    require(state["terminal"], "not_terminal_no_wait")
    value = public_value(stage, frozen, state)
    ready = validate_return(encoded(value))
    output = stage / "public_return.json"
    if output.exists():
        require(read(output) == encoded(value), "preserve_prior_return")
    else:
        write(output, value)
    return {
        "job_id": state["job_id"],
        "return_sha256": digest(read(output)),
        "ready_for_independent_review": ready,
        "output": str(output),
        "remaining_dispatch_admitted": False,
    }


def export_members(stage):
    """Seal allowlisted closed outputs; no scheduler query or approval."""
    members = {}
    paths = [
        stage / "run/group.started.json",
        stage / "run/group.json",
        stage / "batch.json",
    ]
    for i in range(3):
        folder = stage / "run" / f"attempt-{i}"
        if (folder / "child.json").is_file():
            ref = parsed(stage / "requests.json")[i]
            bundle = executor.load_bundle(
                stage / "admission" / ref["file"], ref["sha256"]
            )
            executor.validate_child(bundle, parsed(folder / "child.json"), folder)
            observation = parsed(folder / "supervision.json")
            require(
                observation["console_log"]
                == executor.logs.seal_closed_log(folder / "console.private.log"),
                "console_changed",
            )
        if (folder / "timing_tail.json").is_file():
            executor.metered.validate_timing_files(folder)
        paths += [folder / name for name in FILES]
    for path in paths:
        if path.is_file():
            raw = read(path)
            members[path.relative_to(stage).as_posix()] = {
                "sha256": digest(raw),
                "base64": base64.b64encode(raw).decode("ascii"),
            }
    return members


def public_value(stage, frozen, state):
    return {
        "protocol_id": PROTOCOL,
        "plan": frozen,
        "plan_sha256": digest(encoded(frozen)),
        "accounting": state,
        "members": export_members(stage),
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
        "remaining_dispatch_admitted": False,
    }


def validate_return(raw, *, expected_plan=None):
    value = executor.existing.review.flow.meta.strict_json(raw)
    require(
        set(value)
        == {
            "protocol_id",
            "plan",
            "plan_sha256",
            "accounting",
            "members",
            "raw_logs_included",
            "scientific_reporting_eligible",
            "remaining_dispatch_admitted",
        },
        "public_schema",
    )
    require(value["protocol_id"] == PROTOCOL, "protocol")
    frozen = value["plan"]
    require(
        frozen
        == (plan(frozen["source_commit"]) if expected_plan is None else expected_plan)
        and value["plan_sha256"] == digest(encoded(frozen)),
        "source_plan",
    )
    require(
        all(
            value[k] is False
            for k in (
                "raw_logs_included",
                "scientific_reporting_eligible",
                "remaining_dispatch_admitted",
            )
        ),
        "public_scope",
    )
    state = value["accounting"]
    text = "\n".join(
        "|".join(str(r[k]) for k in roots.accounting.FIELDS.split(","))
        for r in state["rows"]
    )
    require(
        roots.accounting.parse_accounting(text, state["job_id"]) == state
        and state["terminal"],
        "accounting",
    )
    complete = validate_members(frozen, value["members"], state["job_id"])
    return bool(
        complete
        and state["state"] == "COMPLETED"
        and all(r["ExitCode"] == "0:0" for r in state["rows"])
    )


def validate_members(frozen, members, job_id):
    """Artifact gate independent of scheduler accounting; not job completion."""
    group_id = frozen["group"]["group_id"]
    allowed = {"run/group.started.json", "run/group.json", "batch.json"} | {
        f"run/attempt-{i}/{name}" for i in range(3) for name in FILES
    }
    require(set(members) <= allowed, "member_allowlist")
    complete = False
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        for name, entry in members.items():
            require(set(entry) == {"sha256", "base64"}, "member_schema")
            member = base64.b64decode(entry["base64"], validate=True)
            require(digest(member) == entry["sha256"], "member_hash")
            executor.existing.review.flow.meta.strict_json(member)
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(member)
        group_path = directory / "run/group.json"
        if group_path.exists():
            group = parsed(group_path)
            require(
                group["group_id"] == group_id
                and group["scientific_reporting_eligible"] is False,
                "group_identity",
            )
            require(len(group["attempts"]) <= 3, "attempt_count")
            signatures, parameters = [], []
            for i, item in enumerate(group["attempts"]):
                folder = directory / "run" / f"attempt-{i}"
                attempt, _ = executor.metered.validate_timing_files(folder)
                cell = frozen["cells"][i]
                require(
                    attempt["cell"] == cell
                    and attempt["context"] == frozen["context"]
                    and item["cell_id"] == cell["cell_id"],
                    "cell_context",
                )
                require(
                    digest(read(folder / "attempt.json")) == item["attempt_sha256"]
                    and attempt["stop_code"] == item["stop_code"],
                    "attempt_binding",
                )
                child_path = folder / "child.json"
                if child_path.exists():
                    child = parsed(child_path)
                    require(
                        set(child) == {"cell_sha256", "result", "gurobi_log"},
                        "child_schema",
                    )
                    result = child["result"]
                    executor.metered.validate_result(cell, result)
                    require(child["cell_sha256"] == digest(encoded(cell)), "child_cell")
                    if not attempt["pause_remaining_matrix"]:
                        require(
                            attempt["child_result_sha256"] == digest(encoded(result))
                            and attempt["exact_optimization_call_count"] == 1,
                            "child_result_hash",
                        )
                        start = result["start"]
                        if cell["method"] == "M0":
                            require(
                                start["submitted_assignments"] == 0
                                and start["status"] == "not_submitted",
                                "control",
                            )
                        else:
                            require(
                                start["submitted_assignments"]
                                == frozen["start_binding"]["selected_support"]
                                and start["positive_assignments"]
                                == frozen["start_binding"]["positive_assignments"]
                                and start["assignment_sha256"]
                                == frozen["start_binding"][
                                    cell["method"] + "_assignment_sha256"
                                ],
                                "guided_start",
                            )
                        supervision = parsed(folder / "supervision.json")
                        require(supervision["job_id"] == job_id, "supervision_job")
                        reason, scoped_measurement = executor.metered.reconcile(
                            cell, supervision["observation"], result
                        )
                        require(
                            reason == attempt["stop_code"]
                            and scoped_measurement == attempt["measurement"],
                            "attempt_measurement_reconciliation",
                        )
                        measured = executor.supervised.reconcile(
                            supervision["observation"],
                            result,
                            cell["method"],
                            frozen["preparation_seconds"],
                        )
                        require(
                            parsed(folder / "prepared_costs.json")["measurement"]
                            == measured,
                            "cost_reconciliation",
                        )
                        signatures.append(result["mathematical_signature_sha256"])
                        parameters.append(result["parameters"])
            complete = (
                len(group["attempts"]) == 3
                and all(a["stop_code"] is None for a in group["attempts"])
                and group["stop_code"] is None
            )
            require(
                group["complete"] is complete
                and group["pause_remaining_matrix"] is (group["stop_code"] is not None),
                "completion_flags",
            )
            if complete:
                require(set(members) == allowed, "complete_members")
                started = parsed(directory / "run/group.started.json")
                require(
                    started["group_id"] == group_id
                    and len(started["bundle_sha256"]) == 3
                    and all(
                        re.fullmatch(r"[0-9a-f]{64}", s)
                        for s in started["bundle_sha256"]
                    ),
                    "group_start",
                )
                require(
                    len(signatures) == 3
                    and len(set(signatures)) == 1
                    and all(p == parameters[0] for p in parameters),
                    "paired_model_parameters",
                )
                batch = parsed(directory / "batch.json")
                require(batch["job_id"] == job_id, "batch_job")
    return complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "submit", "status", "run", "collect", "review")
    )
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.action == "review":
        print(
            json.dumps(
                {
                    "ready_for_independent_review": validate_return(read(args.receipt)),
                    "remaining_dispatch_admitted": False,
                }
            )
        )
        return 0
    require(args.stage is not None, "stage")
    if args.action == "run":
        return run(args.stage)
    result = (
        submit(args.stage, args.approved_plan_sha256)
        if args.action == "submit"
        else roots.status(args.stage)
        if args.action == "status"
        else collect(args.stage)
        if args.action == "collect"
        else prepare(args.stage)
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
