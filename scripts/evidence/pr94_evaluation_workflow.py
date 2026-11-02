"""Isolated PR94 evaluation admission/dispatch; no automatic retry or cancellation."""

import argparse
import json
import os
import re
import shutil
import sys
import time
import uuid
import zipfile
from pathlib import Path

import pr94_evaluation_contract as policy
import pr94_isolated_preparation as prep

need, read, command = policy.need, prep.read, prep.command
encoded, digest, file_sha, write = (
    policy.encoded,
    policy.sha,
    prep.file_sha,
    prep.write_once,
)
SOURCE, EVIDENCE, DATA, GIB = prep.SOURCE, prep.EVIDENCE, prep.DATA, prep.GIB
PREPARATION = EVIDENCE / "pr94-preparation-c623fe858f62"
PREPARATION_PLAN = "b41953a81f48a91d73c8112bb6794ccce78e72c41ce6ddef7a28ff7e4c098a77"
CLAIM = EVIDENCE / "pr94-full-v2-evaluations.claim.json"
HISTORICAL_INPUTS = (
    EVIDENCE / "pr86/bindings-46802675ff99/prepared/private/input_paths.json"
)
HISTORICAL_ROOTS = EVIDENCE / "pr86/roots-f58a7b899ab5/run"
HISTORICAL_GUIDANCE = EVIDENCE / "pr86/guidance-4209e959021b/run"
FILE_LIMIT = 256 * 1024**2
WORKING_GIB = 256
ADMISSION_FREE_GIB = 320
TERMINAL = prep.TERMINAL


def stage_path(stage):
    p = Path(stage).resolve(strict=True)
    need(p.parent == EVIDENCE.resolve(strict=True), "evaluation_stage_parent")
    need(re.fullmatch(r"pr94-evaluation-[0-9a-f]{12}", p.name), "evaluation_stage_name")
    need(SOURCE.resolve() == p / "source", "evaluation_isolated_source")
    return p


def source_snapshot():
    snapshot = prep.source_snapshot(SOURCE)
    for p in sorted(policy.PACKAGE.rglob("*")):
        if p.is_file():
            need(not p.is_symlink(), "protocol_symlink")
            snapshot["sha256_lf"][p.relative_to(SOURCE).as_posix()] = digest(
                p.read_bytes().replace(b"\r\n", b"\n")
            )
    return snapshot


def storage(stage, admission=False):
    floor = ADMISSION_FREE_GIB if admission else 64
    need(shutil.disk_usage(stage).free >= floor * GIB, "evaluation_free_space")
    total = 0
    for p in stage.rglob("*"):
        need(not p.is_symlink(), "workspace_symlink")
        if p.is_file():
            total += p.stat().st_size
    need(total <= WORKING_GIB * GIB, "evaluation_storage_ceiling")
    return {
        "workspace_bytes": total,
        "allowance_GiB": WORKING_GIB,
        "free_floor_GiB": floor,
    }


def sample_storage_floor(stage):
    # A single filesystem query per watchdog sample; never walk the source tree
    # or every other job's files inside the timing/memory sampling loop.
    need(shutil.disk_usage(stage).free >= 64 * GIB, "evaluation_free_space")


def cell_storage(folder):
    files = list(folder.iterdir())
    need(all(p.is_file() and not p.is_symlink() for p in files), "cell_storage_entries")
    need(sum(p.stat().st_size for p in files) <= GIB, "cell_storage_ceiling")


def site_preflight():
    raw = command(["scontrol", "show", "partition", "batch", "-o"])
    fields = dict(x.split("=", 1) for x in raw.split() if "=" in x)
    need(
        fields.get("PartitionName") == "batch" and fields.get("State") == "UP",
        "partition_unavailable",
    )
    limit = fields.get("MaxTime", "")
    if limit != "UNLIMITED":
        match = re.fullmatch(r"(?:(\d+)-)?(\d+):(\d+):(\d+)", limit)
        need(match is not None, "partition_time_format")
        days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
        need(
            days * 86400 + hours * 3600 + minutes * 60 + seconds >= policy.JOB_WALL,
            "partition_wall_limit",
        )
    nodes = command(["sinfo", "-N", "-h", "-p", "batch", "-o", "%N|%c|%m"])
    candidates = [
        r.split("|") for r in nodes.splitlines() if r.split("|")[0] == "dgx-dasci"
    ]
    need(len(candidates) == 1 and len(candidates[0]) == 3, "configured_node")
    _, cpus, memory = candidates[0]
    need(int(cpus) >= 4 and int(memory) >= 4 * 65536, "configured_parallel_capacity")
    return {
        "partition": "batch",
        "MaxTime": limit,
        "configured_logical_CPUs": int(cpus),
        "configured_memory_MiB": int(memory),
        "current_free_resources_guaranteed": False,
        "license_concurrency_guaranteed": False,
        "queue_wait_is_permitted": True,
        "query_utc": prep.dt.datetime.now(prep.dt.timezone.utc).isoformat(),
    }


def public_binding(row, root):
    result = {
        k: row[k]
        for k in (
            "parent",
            "model_sha256",
            "root_sha256",
            "graph_sha256",
            "prediction_sha256",
            "private_starts_sha256",
            "M1_assignment_sha256",
            "M2_assignment_sha256",
            "checkpoint_sha256",
            "variable_order_sha256",
            "binary_variables",
            "selected_support",
            "positive_assignments",
            "abstained",
        )
    }
    result["mathematical_signature_sha256"] = root["mathematical_signature_sha256"]
    need(result["checkpoint_sha256"] == policy.CHECKPOINT, "frozen_checkpoint")
    return result


def discover_inputs(accepted_guidance_sha):
    """Use exact existing path ledgers; never search, regenerate or relabel inputs."""
    need(file_sha(PREPARATION / "plan.json") == PREPARATION_PLAN, "preparation_plan")
    receipt_path = PREPARATION / "guidance-public-return.json"
    need(file_sha(receipt_path) == accepted_guidance_sha, "accepted_guidance_hash")
    returned = read(receipt_path, maximum=32 * 1024**2)
    need(
        returned["ready_for_review"] is True and returned["kind"] == "guidance",
        "guidance_review",
    )
    need(returned["plan_sha256"] == PREPARATION_PLAN, "guidance_plan")
    need(
        returned["source_commit"] == "c623fe858f62d8fa2a70eebf6f3aeee5692e8f90",
        "preparation_source",
    )
    roots = read(PREPARATION / "roots-public-return.json")
    review = read(PREPARATION / "roots-review.json")
    need(
        review
        == {
            "plan_sha256": PREPARATION_PLAN,
            "collection_sha256": file_sha(PREPARATION / "roots-public-return.json"),
            "accepted_by_author_CLI": True,
        },
        "accepted_roots",
    )
    actual_new = returned["summary"]["rows"][0]["result"]["rows"]
    new_config = read(PREPARATION / "inputs.private.json")
    prior = read(
        SOURCE
        / "docs/research/solver-seed-extension-v1/historical-artifact-bindings.json"
    )
    private_old = read(HISTORICAL_INPUTS)
    need(len(prior["parents"]) == len(private_old) == 10, "historical_parent_count")
    private_by_parent = {p["parent"]: p for p in private_old}
    root_plan = read(HISTORICAL_ROOTS.parent / "plan.json")
    guidance_plan = read(HISTORICAL_GUIDANCE.parent / "plan.json")
    need(
        root_plan["source_commit"] == prior["root_source_commit"]
        and guidance_plan["source_commit"] == prior["guidance_source_commit"],
        "historical_preparation_sources",
    )
    root_index = {p["parent"]: i for i, p in enumerate(root_plan["parents"])}
    guidance_index = {p["parent"]: i for i, p in enumerate(guidance_plan["parents"])}
    expected_old = {p["parent"] for p in prior["parents"]}
    need(
        set(private_by_parent)
        == set(root_index)
        == set(guidance_index)
        == expected_old,
        "historical_artifact_parent_set",
    )
    need(len(actual_new) == len(roots["summary"]["rows"]) == 6, "new_parent_count")
    rows, paths = {}, {}
    for row in prior["parents"]:
        parent = row["parent"]
        private = private_by_parent[parent]
        rows[parent] = public_binding(row, row)
        paths[parent] = {
            "model": private["mip_path"],
            "root": str(
                HISTORICAL_ROOTS / str(root_index[parent]) / "root.private.json.gz"
            ),
            "graph": str(
                HISTORICAL_GUIDANCE / str(guidance_index[parent]) / "graph.private.pt"
            ),
            "predictions": str(
                HISTORICAL_GUIDANCE
                / str(guidance_index[parent])
                / "predictions.private.json"
            ),
            "starts": str(
                HISTORICAL_GUIDANCE
                / str(guidance_index[parent])
                / "starts.private.json"
            ),
        }
    for i, row in enumerate(actual_new):
        root = roots["summary"]["rows"][i]["result"]
        need(row["parent"] == root["parent"], "new_parent_order")
        need(
            row["model_sha256"] == root["model_sha256"]
            and row["root_sha256"] == root["root_sha256"],
            "new_root_binding",
        )
        parent = row["parent"]
        need(parent not in rows, "duplicate_preparation_parent")
        rows[parent] = public_binding(row, root)
        paths[parent] = {
            "model": new_config["parents"][parent],
            "root": str(PREPARATION / "run/roots" / str(i) / "root.private.json.gz"),
            "graph": str(PREPARATION / "run/guidance" / str(i) / "graph.private.pt"),
            "predictions": str(
                PREPARATION / "run/guidance" / str(i) / "predictions.private.json"
            ),
            "starts": str(
                PREPARATION / "run/guidance" / str(i) / "starts.private.json"
            ),
        }
    _, cells = policy.matrix()
    need(set(rows) == {c["parent"] for c in cells.values()}, "sixteen_parent_coverage")
    return rows, {"parents": paths, "checkpoint_path": new_config["checkpoint_path"]}


def verify_inputs(bindings, private, parents=None):
    selected = set(bindings) if parents is None else set(parents)
    need(
        selected <= set(bindings) and set(bindings) == set(private["parents"]),
        "private_parent_set",
    )
    checkpoint = prep.safe_file(private["checkpoint_path"])
    need(file_sha(checkpoint) == policy.CHECKPOINT, "checkpoint_bytes")
    parsed = {}
    for parent in sorted(selected):
        binding, paths = bindings[parent], private["parents"][parent]
        need(
            set(paths) == {"model", "root", "graph", "predictions", "starts"},
            "private_path_schema",
        )
        for name, key in (
            ("model", "model_sha256"),
            ("root", "root_sha256"),
            ("graph", "graph_sha256"),
            ("predictions", "prediction_sha256"),
            ("starts", "private_starts_sha256"),
        ):
            path = prep.safe_file(paths[name])
            need(file_sha(path) == binding[key], "private_" + name + "_bytes")
        starts = read(Path(paths["starts"]), maximum=16 * 1024**2)
        policy.validate_start(binding, starts)
        parsed[parent] = starts
    return parsed


def freeze(stage, accepted_guidance_sha):
    inspection_started = time.monotonic()
    prep.host()
    stage = stage_path(stage)
    need(not (stage / "plan.json").exists(), "evaluation_plan_exists_preserve")
    snapshot = source_snapshot()
    need(stage.name.endswith(snapshot["commit"][:12]), "stage_commit")
    capacity = storage(stage, admission=True)
    site = site_preflight()
    public, private = discover_inputs(accepted_guidance_sha)
    verify_inputs(public, private)
    matrix, cells = policy.matrix()
    baseline = policy.baseline_parameters()
    for cell in cells.values():
        need(
            public[cell["parent"]]["model_sha256"] == cell["model_sha256"],
            "matrix_model",
        )
    private_sha = write(stage / "inputs.private.json", private)
    plan = {
        "protocol_id": policy.PROTOCOL,
        "source": snapshot,
        "public_matrix_sha256": file_sha(policy.PACKAGE / "plan.json"),
        "cells_csv_sha256": file_sha(policy.PACKAGE / "planned-cells.csv"),
        "accepted_guidance_sha256": accepted_guidance_sha,
        "private_inputs_sha256": private_sha,
        "bindings": public,
        "groups": matrix["groups"],
        "environment": prep.versions(),
        "baseline_parameters": baseline,
        "baseline_parameter_receipt_sha256": policy.BASELINE_RECEIPT_SHA,
        "maximum_evaluations": 144,
        "maximum_submissions": 48,
        "concurrency_ceiling": 4,
        "physical_cores_each": 1,
        "memory_GiB_each": 64,
        "wall_seconds_each": policy.JOB_WALL,
        "storage": capacity,
        "site": site,
        "storage_allowance_GiB": WORKING_GIB,
        "admission_free_GiB": ADMISSION_FREE_GIB,
        "per_file_limit_bytes": FILE_LIMIT,
        "automatic_retry": False,
        "training_calls": 0,
        "forward_calls": 0,
        "execution_released": False,
        "scientific_reporting_eligible": False,
        "licensed_concurrency_guaranteed": False,
    }
    plan_sha = write(stage / "plan.json", plan)
    return export(
        stage,
        {
            "installation-review.json": encoded(
                {
                    "source_commit": snapshot["commit"],
                    "plan_sha256": plan_sha,
                    "private_model_and_artifact_chains_verified": 16,
                    "accepted_guidance_sha256": accepted_guidance_sha,
                    "storage": capacity,
                    "site": site,
                    "environment": plan["environment"],
                    "optimization_calls": 0,
                    "forward_calls": 0,
                    "training_calls": 0,
                    "submissions": 0,
                    "inspection_wall_seconds": time.monotonic() - inspection_started,
                    "bindings": public,
                    "resources": {
                        "evaluation_jobs": 48,
                        "concurrency_ceiling": 4,
                        "RAM_GiB_peak_ceiling": 256,
                        "solver_hours_ceiling": 144,
                        "summed_job_hours_ceiling": 192,
                        "physical_core_hours_ceiling": 192,
                        "storage_allowance_GiB": WORKING_GIB,
                        "admission_free_GiB": ADMISSION_FREE_GIB,
                    },
                    "scientific_reporting_eligible": False,
                }
            )
        },
    )


def load(stage):
    stage = stage_path(stage)
    plan = read(stage / "plan.json", maximum=16 * 1024**2)
    need(
        file_sha(SOURCE / "docs/evidence/pr86/job3522/public_return.json")
        == policy.BASELINE_RECEIPT_SHA,
        "baseline_parameter_receipt_changed",
    )
    need(plan["protocol_id"] == policy.PROTOCOL, "execution_protocol")
    need(plan["source"] == source_snapshot(), "execution_source_changed")
    need(plan["environment"] == prep.versions(), "execution_environment_changed")
    need(
        plan["baseline_parameters"] == policy.baseline_parameters(),
        "baseline_parameters_changed",
    )
    need(
        file_sha(policy.PACKAGE / "plan.json") == plan["public_matrix_sha256"],
        "public_matrix_changed",
    )
    need(
        file_sha(policy.PACKAGE / "planned-cells.csv") == plan["cells_csv_sha256"],
        "public_cells_changed",
    )
    need(
        file_sha(stage / "inputs.private.json") == plan["private_inputs_sha256"],
        "private_inputs_changed",
    )
    need(
        file_sha(PREPARATION / "guidance-public-return.json")
        == plan["accepted_guidance_sha256"],
        "guidance_return_changed",
    )
    need(
        not plan["automatic_retry"] and not plan["scientific_reporting_eligible"],
        "execution_flags",
    )
    need(plan["groups"] == policy.matrix()[0]["groups"], "group_order_changed")
    need(not (SOURCE / "gurobi.env").exists(), "unreviewed_parameter_file")
    return plan


def expected_claim(stage, plan):
    return {
        "plan_sha256": file_sha(stage / "plan.json"),
        "source_commit": plan["source"]["commit"],
        "maximum_evaluations": 144,
        "maximum_submissions": 48,
        "concurrency_ceiling": 4,
        "automatic_retry": False,
        "explicit_author_CLI": True,
    }


def approved(stage, plan):
    need(
        read(CLAIM) == read(stage / "approval.json") == expected_claim(stage, plan),
        "evaluation_approval",
    )


def held_profile(job_id, predecessor):
    raw = command(["scontrol", "show", "job", job_id, "-o"])
    fields = dict(x.split("=", 1) for x in raw.split() if "=" in x)
    need(fields.get("JobId") == job_id, "held_job_identity")
    need(fields.get("UserId", "").split("(")[0] == "vrcelestino", "held_job_owner")
    for key, value in {
        "JobState": "PENDING",
        "Reason": "JobHeldUser",
        "Partition": "batch",
        "NumTasks": "1",
        "Requeue": "0",
        "TimeLimit": "04:00:00",
        "MinCPUsNode": "1",
    }.items():
        need(fields.get(key) == value, "held_" + key)
    need(fields.get("NumNodes") in {"1", "1-1"}, "held_nodes")
    need(fields.get("CPUs/Task") == "1", "held_CPU_cap")
    need(fields.get("NumCPUs") in {"1", "2"}, "held_CPU_allocation")
    need(fields.get("ReqNodeList") == "dgx-dasci", "held_requested_node")
    need(fields.get("MinMemoryNode") in {"64G", "65536M", "65536"}, "held_memory")
    tres = dict(
        x.split("=", 1) for x in fields.get("ReqTRES", "").split(",") if "=" in x
    )
    need(
        not any(k.startswith("gres/gpu") and v != "0" for k, v in tres.items())
        and fields.get("TresPerNode", "(null)") in {"", "(null)", "gres:gpu:0"},
        "held_no_GPU",
    )
    dependency = fields.get("Dependency", "(null)")
    need(
        dependency in {"(null)", ""}
        if predecessor is None
        else re.fullmatch("afterok:" + predecessor + r"(?:\([^)]*\))?", dependency),
        "held_dependency",
    )
    return {
        "job_id": job_id,
        "predecessor": predecessor,
        "resource_profile_checked": True,
    }


def submit(stage, accepted_plan_sha):
    prep.host()
    plan = load(stage)
    need(file_sha(stage / "plan.json") == accepted_plan_sha, "accepted_evaluation_plan")
    storage(stage, admission=True)
    verify_inputs(plan["bindings"], read(stage / "inputs.private.json"))
    site = site_preflight()
    # Claims survive partial/ambiguous sbatch and source changes. No resubmission path.
    approval = expected_claim(stage, plan)
    write(CLAIM, approval)
    write(stage / "approval.json", approval)
    write(stage / "site-at-submission.json", site)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_", "SRUN_"))
        and k not in {"PYTHONHOME", "PYTHONPATH"}
    }
    env.update(PR94_EVALUATION_STAGE=str(stage), PR94_EVALUATION_PYTHON=sys.executable)
    jobs, ids = [], {}
    for index, group in enumerate(plan["groups"]):
        predecessor = ids.get(group["predecessor_group_id"])
        write(
            stage / "claims" / f"submit-{index}.json",
            {
                "group_id": group["group_id"],
                "plan_sha256": accepted_plan_sha,
                "maximum_submissions": 1,
            },
        )
        args = [
            "sbatch",
            "--parsable",
            "--hold",
            "--partition=batch",
            "--nodes=1-1",
            "--nodelist=dgx-dasci",
            "--ntasks=1",
            "--cpus-per-task=1",
            "--hint=nomultithread",
            "--mem=64G",
            "--time=04:00:00",
            "--no-requeue",
            "--job-name=cfl_pr94_eval",
            "--chdir=" + str(SOURCE),
            "--output=" + str(stage / "evaluation-%j.private.out"),
            "--error=" + str(stage / "evaluation-%j.private.err"),
        ]
        if predecessor:
            args.append("--dependency=afterok:" + predecessor)
        response = command(
            args
            + [
                str(SOURCE / "scripts/evidence/operate_pr94_evaluation.sh"),
                "batch",
                str(index),
            ],
            env=env,
            timeout=60,
        )
        need(
            re.fullmatch(r"[0-9]+(?:;[A-Za-z0-9_.-]+)?", response),
            "ambiguous_sbatch_preserve",
        )
        job = response.split(";")[0]
        need(job not in ids.values(), "duplicate_scheduler_id")
        row = {
            "group_id": group["group_id"],
            "job_id": job,
            "index": index,
            "lane": group["lane"],
            "predecessor": predecessor,
        }
        # Record the ID before resource inspection can fail.
        write(stage / "claims" / f"submitted-{index}.json", row)
        row["profile"] = held_profile(job, predecessor)
        jobs.append(row)
        ids[group["group_id"]] = job
    write(stage / "submission.json", {"plan_sha256": accepted_plan_sha, "jobs": jobs})
    for row in reversed(jobs):
        command(["scontrol", "release", row["job_id"]])
        write(
            stage / "claims" / f"released-{row['index']}.json",
            {"job_id": row["job_id"]},
        )
    return {
        "jobs": [r["job_id"] for r in jobs],
        "groups": 48,
        "maximum_evaluations": 144,
        "concurrency_ceiling": 4,
        "automatic_retry": False,
    }


def allocation(stage):
    import resource

    from pr86_isolated_executor import allocation as qualified_allocation

    before = sorted(os.sched_getaffinity(0))
    job, gate = qualified_allocation(1)
    selected = sorted(os.sched_getaffinity(0))

    def physical(cpu):
        base = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        return tuple(
            int((base / key).read_text()) for key in ("physical_package_id", "core_id")
        )

    allowed_physical = sorted({physical(cpu) for cpu in before})
    need(len(allowed_physical) == len(selected) == 1, "single_physical_core_allocation")
    storage(stage)
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))
    return (
        job,
        gate,
        {
            "job_id": job,
            "logical_CPUs_before_pinning": before,
            "physical_cores_before_pinning": allowed_physical,
            "pinned_logical_CPUs": selected,
            "memory": gate.public(),
            "scope": "process affinity and qualified job RAM; billing not inferred",
        },
    )


def verify_affinity(evidence):
    need(
        sorted(os.sched_getaffinity(0)) == evidence["pinned_logical_CPUs"],
        "affinity_changed",
    )


def check_group_job(stage, index, plan, job):
    submitted = read(stage / "submission.json")
    need(submitted["plan_sha256"] == file_sha(stage / "plan.json"), "submission_plan")
    need(len(submitted["jobs"]) == 48, "submission_count")
    row = submitted["jobs"][index]
    need(
        row["index"] == index and row["lane"] == plan["groups"][index]["lane"],
        "job_lane_binding",
    )
    need(
        row["job_id"] == job and row["group_id"] == plan["groups"][index]["group_id"],
        "job_group_binding",
    )
    if row["predecessor"]:
        prior_index = index - 4
        need(
            prior_index >= 0
            and row["predecessor"] == submitted["jobs"][prior_index]["job_id"],
            "predecessor_lane",
        )
        predecessor = read(stage / "run" / str(prior_index) / "group.json")
        need(
            predecessor["complete"] is True and predecessor["stop"] is None,
            "predecessor_artifact",
        )
        need(predecessor["plan_sha256"] == submitted["plan_sha256"], "predecessor_plan")
        need(predecessor["job_id"] == row["predecessor"], "predecessor_job")
        need(
            predecessor["group_id"] == plan["groups"][prior_index]["group_id"]
            and [r["cell_id"] for r in predecessor["rows"]]
            == plan["groups"][prior_index]["cells"],
            "predecessor_cells",
        )
        for item in predecessor["rows"]:
            need(
                file_sha(stage / item["relative_result"]) == item["sha256"],
                "predecessor_result_changed",
            )
    else:
        need(index < 4, "missing_predecessor_dependency")


def child(stage, cell_id):
    plan = load(stage)
    approved(stage, plan)
    job, gate, allocation_receipt = allocation(stage)
    _, cells = policy.matrix()
    need(cell_id in cells, "child_cell")
    cell = cells[cell_id]
    index = next(i for i, g in enumerate(plan["groups"]) if cell_id in g["cells"])
    check_group_job(stage, index, plan, job)
    need(
        read(stage / "claims" / f"group-{index}.json")
        == {"job_id": job, "group_id": plan["groups"][index]["group_id"]},
        "group_call_admission",
    )
    private = read(stage / "inputs.private.json")
    starts = verify_inputs(plan["bindings"], private, [cell["parent"]])[cell["parent"]]
    binding = plan["bindings"][cell["parent"]]
    folder = stage / "run" / cell_id
    need(folder.is_dir() and not folder.is_symlink(), "child_output")
    from pr94_evaluation_solver import solve

    def intent():
        load(stage)
        verify_affinity(allocation_receipt)
        need(gate.sample() < 56 * GIB, "memory_before_optimize")
        write(
            stage / "claims" / (cell_id + ".optimize.json"),
            {
                "cell_id": cell_id,
                "maximum_calls": 1,
                "plan_sha256": file_sha(stage / "plan.json"),
            },
        )

    selected = (
        None
        if cell["method"] == "M0"
        else starts["root_lp" if cell["method"] == "M1" else "gnn"]["assignments"]
    )
    result = solve(
        Path(private["parents"][cell["parent"]]["model"]),
        cell["model_sha256"],
        [],
        "unguided_control" if selected is None else "partial_mip_start",
        preselected_assignments=selected,
        reported_method=cell["method"],
        private_log_path=folder / "gurobi.private.log",
        solution_path=folder / "solution.private.json.gz",
        cell=cell,
        before_optimize=intent,
        execution_policy=policy,
    )
    value = {
        "cell": cell,
        "plan_sha256": file_sha(stage / "plan.json"),
        "result": result,
        "frozen_Start_abstained": cell["method"] != "M0" and binding["abstained"],
    }
    write(folder / "raw-result.json", value)
    policy.validate_result(cell, result, binding)
    write(folder / "child.json", value)


def run(stage, index):
    plan = load(stage)
    approved(stage, plan)
    need(type(index) is int and 0 <= index < 48, "group_index")
    job, raw_gate, allocation_receipt = allocation(stage)
    check_group_job(stage, index, plan, job)
    group = plan["groups"][index]
    folder = stage / "run" / str(index)
    folder.mkdir(exist_ok=False)
    write(folder / "allocation.json", allocation_receipt)
    write(
        stage / "claims" / f"group-{index}.json",
        {"job_id": job, "group_id": group["group_id"]},
    )
    from paired_memory_runtime_v2 import supervise
    from pr86_supervised_costs import reconcile

    class Gate:
        storage_failure = None

        def sample(self):
            verify_affinity(allocation_receipt)
            try:
                sample_storage_floor(stage)
            except (ValueError, OSError) as exc:
                self.storage_failure = type(exc).__name__ + ":storage_observation_lost"
                raise
            return raw_gate.sample()

    start, rows, stop, signature, parameters = time.monotonic(), [], None, None, None
    try:
        for cell_id in group["cells"]:
            need(
                time.monotonic() - start + policy.CHILD_DEADLINE <= policy.JOB_WALL,
                "group_deadline",
            )
            cell_folder = stage / "run" / cell_id
            cell_folder.mkdir(exist_ok=False)
            write(
                cell_folder / "started.json",
                {
                    "cell_id": cell_id,
                    "job_id": job,
                    "plan_sha256": file_sha(stage / "plan.json"),
                },
            )
            observed_gate = Gate()
            observation = supervise(
                [
                    sys.executable,
                    "-B",
                    str(Path(__file__).resolve()),
                    "child",
                    "--stage",
                    str(stage),
                    "--cell-id",
                    cell_id,
                ],
                cell_folder / "console.private.log",
                policy.CHILD_DEADLINE,
                observed_gate,
            )
            observation["storage_failure"] = observed_gate.storage_failure
            write(cell_folder / "supervision.json", observation)
            cell_storage(cell_folder)
            storage(stage)
            need(
                observation["child_exit_code"] == 0
                and observation["guard_stop"] is None,
                "child_stopped",
            )
            child_value = read(cell_folder / "child.json", maximum=16 * 1024**2)
            cell = policy.matrix()[1][cell_id]
            need(
                child_value["cell"] == cell
                and child_value["plan_sha256"] == file_sha(stage / "plan.json"),
                "child_identity",
            )
            result = child_value["result"]
            policy.validate_result(cell, result, plan["bindings"][cell["parent"]])
            if rows:
                need(
                    signature == result["mathematical_signature_sha256"]
                    and parameters == result["parameters"],
                    "unpaired_result",
                )
            signature, parameters = (
                result["mathematical_signature_sha256"],
                result["parameters"],
            )
            cost = reconcile(observation, result, cell["method"], uses=3)
            write(cell_folder / "costs.json", cost)
            rows.append(
                {
                    "cell_id": cell_id,
                    "relative_result": (cell_folder / "child.json")
                    .relative_to(stage)
                    .as_posix(),
                    "sha256": file_sha(cell_folder / "child.json"),
                }
            )
    except BaseException:
        stop = "group_failed_preserve_no_retry"
        raise
    finally:
        write(
            folder / "group.json",
            {
                "group_id": group["group_id"],
                "job_id": job,
                "plan_sha256": file_sha(stage / "plan.json"),
                "rows": rows,
                "complete": len(rows) == 3 and stop is None,
                "stop": stop,
                "supervisor_wall_seconds": time.monotonic() - start,
                "scientific_reporting_eligible": False,
            },
        )


def accounting(stage):
    complete = (stage / "submission.json").exists()
    jobs = (
        read(stage / "submission.json")["jobs"]
        if complete
        else [read(p) for p in sorted((stage / "claims").glob("submitted-*.json"))]
    )
    need(len(jobs) <= 48, "submission_prefix_count")
    jobs.sort(key=lambda row: row["index"])
    need(
        [r["index"] for r in jobs] == list(range(len(jobs))), "submission_prefix_order"
    )
    intents = len(list((stage / "claims").glob("submit-*.json")))
    unconfirmed = max(0, intents - len(jobs))
    if not jobs:
        return {
            "submission_complete": False,
            "recorded_jobs": 0,
            "unconfirmed_submission_intents": unconfirmed,
            "root_jobs_terminal": False,
            "rows": [],
            "missing_steps": [],
        }
    ids = [r["job_id"] for r in jobs]
    need(
        len(set(ids)) == len(ids)
        and (not complete or len(ids) == 48)
        and all(re.fullmatch(r"[0-9]+", i) for i in ids),
        "accounting_ids",
    )
    fields = [
        "JobIDRaw",
        "State",
        "ExitCode",
        "ElapsedRaw",
        "AllocCPUS",
        "TotalCPU",
        "MaxRSS",
        "ReqMem",
        "Start",
        "End",
    ]
    query_fields = ["JobIDRaw%40", "State%40"] + fields[2:]
    raw = command(
        [
            "sacct",
            "-n",
            "-P",
            "-j",
            ",".join(ids),
            "--format=" + ",".join(query_fields),
        ],
        timeout=60,
    )
    rows = []
    for line in raw.splitlines():
        values = line.split("|")
        if len(values) == len(fields) + 1 and values[-1] == "":
            values.pop()
        need(len(values) == len(fields), "accounting_columns")
        row = dict(zip(fields, values))
        need(row["JobIDRaw"].split(".")[0] in ids, "foreign_accounting_job")
        rows.append(row)
    by_id = {r["JobIDRaw"]: r for r in rows}
    need(len(by_id) == len(rows), "duplicate_accounting_job")
    roots_terminal = all(
        i in by_id and by_id[i]["State"].split()[0].rstrip("+") in TERMINAL for i in ids
    )
    missing_steps = [
        i + suffix
        for i in ids
        for suffix in (".batch", ".extern")
        if i + suffix not in by_id
    ]
    return {
        "query_utc": prep.dt.datetime.now(prep.dt.timezone.utc).isoformat(),
        "rows": rows,
        "root_jobs_terminal": roots_terminal,
        "missing_steps": missing_steps,
        "submission_complete": complete,
        "recorded_jobs": len(jobs),
        "unconfirmed_submission_intents": unconfirmed,
    }


def export(stage, members):
    manifest = {"sha256": {k: digest(raw) for k, raw in members.items()}}
    out = stage / ("pr94-evaluation-metadata-" + uuid.uuid4().hex + ".zip")
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
        archive.writestr("manifest.json", encoded(manifest))
    return {
        "ARQUIVO_HPC": str(out),
        "SHA256": file_sha(out),
        "BYTES_ZIP": out.stat().st_size,
    }


def collect(stage):
    plan = load(stage)
    state = accounting(stage)
    need(state["submission_complete"], "partial_submission_needs_diagnosis")
    submitted = read(stage / "submission.json")["jobs"]
    account = {r["JobIDRaw"]: r for r in state["rows"]}
    closed_groups, closed_cells = set(), set()
    for entry in submitted:
        ids = [entry["job_id"] + suffix for suffix in ("", ".batch", ".extern")]
        scope = ids + [i for i in account if i.startswith(entry["job_id"] + ".")]
        if all(
            i in account and account[i]["State"].split()[0].rstrip("+") in TERMINAL
            for i in scope
        ):
            closed_groups.add(entry["index"])
            closed_cells.update(plan["groups"][entry["index"]]["cells"])
    if not closed_groups:
        return {
            "terminal_groups_collected": 0,
            "accounting": state,
            "optimization_calls_added": 0,
            "no_return_created": True,
        }
    rows, seals = [], {}
    for cell_id, cell in policy.matrix()[1].items():
        path = stage / "run" / cell_id / "child.json"
        closed = cell_id in closed_cells
        result = read(path, maximum=16 * 1024**2) if closed and path.is_file() else None
        if result:
            need(
                result["cell"] == cell
                and result["plan_sha256"] == file_sha(stage / "plan.json"),
                "collected_cell",
            )
            policy.validate_result(
                cell, result["result"], plan["bindings"][cell["parent"]]
            )
        unqualified = path.parent / "raw-result.json"
        row = {
            "cell": cell,
            "received": result is not None,
            "value": result,
            "group_accounting_closed": closed,
            "raw_unqualified_value": read(unqualified, maximum=16 * 1024**2)
            if closed and result is None and unqualified.is_file()
            else None,
        }
        for name in ("supervision.json", "costs.json"):
            p = path.parent / name
            row[name] = read(p) if closed and p.is_file() else None
        rows.append(row)
        if closed and path.parent.exists():
            for p in path.parent.iterdir():
                need(not p.is_symlink(), "return_symlink")
                if p.is_file():
                    seals[p.relative_to(stage).as_posix()] = {
                        "sha256": file_sha(p),
                        "bytes": p.stat().st_size,
                    }
    for i in range(48):
        for name in ("group.json", "allocation.json"):
            p = stage / "run" / str(i) / name
            if i in closed_groups and p.is_file():
                seals[p.relative_to(stage).as_posix()] = {
                    "sha256": file_sha(p),
                    "bytes": p.stat().st_size,
                }
    value = {
        "protocol_id": policy.PROTOCOL,
        "plan_sha256": file_sha(stage / "plan.json"),
        "source_commit": plan["source"]["commit"],
        "parent_bindings": plan["bindings"],
        "accounting": state,
        "cells": rows,
        "closed_artifact_seals": seals,
        "received": sum(r["received"] for r in rows),
        "expected": 144,
        "terminal_groups_collected": len(closed_groups),
        "complete_campaign_accounting": len(closed_groups) == 48,
        "durable_optimize_intents": [
            {
                "cell_id": cell_id,
                "sha256": file_sha(stage / "claims" / (cell_id + ".optimize.json")),
            }
            for cell_id in policy.matrix()[1]
            if cell_id in closed_cells
            and (stage / "claims" / (cell_id + ".optimize.json")).is_file()
        ],
        "intent_is_not_proof_of_completed_call": True,
        "scientific_reporting_eligible": False,
        "raw_artifacts_included": False,
        "private_paths_included": False,
    }
    path = stage / (
        "evaluation-public-return.json"
        if len(closed_groups) == 48
        else "evaluation-terminal-subset-" + uuid.uuid4().hex + ".json"
    )
    write(path, value)
    return export(stage, {path.name: path.read_bytes()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["freeze", "submit", "run", "child", "status", "collect"]
    )
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--accepted-guidance-sha256")
    parser.add_argument("--accepted-plan-sha256")
    parser.add_argument("--index", type=int)
    parser.add_argument("--cell-id")
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze(args.stage, args.accepted_guidance_sha256)
    elif args.action == "submit":
        result = submit(args.stage, args.accepted_plan_sha256)
    elif args.action == "run":
        run(args.stage, args.index)
        return 0
    elif args.action == "child":
        child(args.stage, args.cell_id)
        return 0
    else:
        load(args.stage)
        result = (
            accounting(args.stage) if args.action == "status" else collect(args.stage)
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        raise SystemExit(
            "PR94_EVALUATION_ABORTED=" + type(exc).__name__ + ":" + str(exc)
        )
