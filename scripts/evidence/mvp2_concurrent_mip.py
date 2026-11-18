#!/usr/bin/env python3
"""Plan and run a separate paired CFL campaign, with explicit Slurm admission."""

import argparse
import hashlib
import itertools
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
EVIDENCE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence")
COHORTS = {
    "easy": (0, 3, 6, 14, 27, 29),
    "medium": (0, 4, 5, 6, 7, 9, 12, 13, 20, 26),
    "hard": (0, 5, 10, 15, 20, 25),
}
PROFILES = ((1, 1), (4, 1), (4, 2), (8, 1), (8, 2))
METHODS = ("M0", "M1", "M2")
SEEDS = (42, 43, 44)
TIME_LIMIT = 3600
WALL_HOURS = 4
MEMORY_MIB = 65536
ARRAY_CAP = 4
CHECKPOINT = "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024**2), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def read(path):
    require(
        path.is_file() and not path.is_symlink(), f"regular file required: {path.name}"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def matrix():
    blocks = []
    for difficulty, indices in COHORTS.items():
        for number, seed, (threads, concurrent) in itertools.product(
            indices, SEEDS, PROFILES
        ):
            alias = f"{difficulty[0].upper()}{number}"
            rotation = (number + seed - SEEDS[0]) % len(METHODS)
            order = METHODS[rotation:] + METHODS[:rotation]
            blocks.append(
                {
                    "id": f"{alias}-s{seed}-t{threads}-c{concurrent}",
                    "instance": alias,
                    "parent": f"CFL_{difficulty}_instance_{number}",
                    "difficulty": difficulty,
                    "seed": seed,
                    "threads": threads,
                    "concurrent": concurrent,
                    "methods": list(order),
                }
            )
    return blocks


def budget(blocks):
    return {
        "instances": len({block["instance"] for block in blocks}),
        "blocks": len(blocks),
        "solves": sum(len(block["methods"]) for block in blocks),
        "solver_physical_core_hours_ceiling": sum(
            len(block["methods"]) * block["threads"] * TIME_LIMIT / 3600
            for block in blocks
        ),
        "reserved_physical_core_hours_ceiling": sum(
            block["threads"] * WALL_HOURS for block in blocks
        ),
        "peak_blocks": ARRAY_CAP,
        "memory_mib_per_block": MEMORY_MIB,
        "peak_memory_mib": ARRAY_CAP * MEMORY_MIB,
        "peak_physical_cores": ARRAY_CAP * max(t for t, _ in PROFILES),
    }


def site_stage(path):
    from pr94_isolated_preparation import host

    host()
    require(
        sys.platform == "linux" and os.uname().nodename.split(".")[0] == "dgx-dasci",
        "use the dgx-dasci CLI",
    )
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "activate tfm_env")
    root = EVIDENCE.resolve(strict=True)
    stage = path.resolve(strict=True)
    require(
        not path.is_symlink()
        and stage.is_dir()
        and stage.parent == root
        and stage.name.startswith("mvp2-concurrent-")
        and ROOT.resolve() == stage / "source",
        "invalid isolated stage",
    )
    return stage


def source_commit():
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(ROOT), *args], text=True
        ).strip()

    require(not git("status", "--porcelain", "--untracked-files=all"), "source changed")
    return git("rev-parse", "HEAD")


def checked_file(item, key, sha_key):
    path = Path(item[key])
    require(
        path.is_absolute() and path.resolve().is_relative_to(EVIDENCE.parent),
        "bound files must reside under the data root",
    )
    require(
        path.is_file() and not path.is_symlink() and digest(path) == item[sha_key],
        f"{key} bytes do not match the admitted hash",
    )
    return path


def inspect_input(item, parent):
    from pr94_evaluation_contract import validate_start

    require(item["parent"] == parent, "parent binding mismatch")
    require(item["checkpoint_sha256"] == CHECKPOINT, "wrong checkpoint")
    model = checked_file(item, "model", "model_sha256")
    starts = read(checked_file(item, "starts", "private_starts_sha256"))
    preparation = read(
        checked_file(item, "reviewed_preparation", "reviewed_preparation_sha256")
    )
    keys = (
        "parent",
        "checkpoint_sha256",
        "model_sha256",
        "private_starts_sha256",
        "root_sha256",
        "graph_sha256",
        "prediction_sha256",
        "M1_assignment_sha256",
        "M2_assignment_sha256",
        "binary_variables",
        "selected_support",
        "positive_assignments",
        "abstained",
    )
    require(all(preparation[key] == item[key] for key in keys), "preparation binding")
    require(
        all(
            re.fullmatch(r"[0-9a-f]{64}", preparation[k])
            for k in ("root_sha256", "graph_sha256", "prediction_sha256")
        ),
        "preparation seals",
    )
    for name, key in (
        ("root", "root_sha256"),
        ("graph", "graph_sha256"),
        ("predictions", "prediction_sha256"),
    ):
        checked_file(item, name, key)
    require(
        preparation["mathematical_signature_sha256"]
        == item["mathematical_signature_sha256"],
        "model signature binding",
    )
    validate_start(item, starts)
    return model, starts


def site_preflight():
    from pr94_evaluation_workflow import site_preflight as reviewed_site
    from pr94_isolated_preparation import command

    value = reviewed_site()
    text = command(["scontrol", "show", "node", "dgx-dasci", "-o"])
    fields = dict(p.split("=", 1) for p in text.split() if "=" in p)
    require(fields.get("NodeName") == "dgx-dasci", "configured node identity")
    state = fields.get("State", "")
    require(
        state
        and not any(flag in state for flag in ("DOWN", "DRAIN", "NOT_RESPONDING")),
        "node unavailable",
    )
    physical = int(fields["Sockets"]) * int(fields["CoresPerSocket"])
    require(physical >= ARRAY_CAP * max(t for t, _ in PROFILES), "physical capacity")
    require(int(fields["RealMemory"]) >= ARRAY_CAP * MEMORY_MIB, "memory capacity")
    return {
        **value,
        "configured_physical_cores": physical,
        "node_state": state,
        "concurrent_start_not_guaranteed": True,
    }


def freeze(stage, inputs):
    from pr94_evaluation_contract import baseline_parameters
    from pr94_isolated_preparation import versions
    from pr98_hard_preparation import workspace_environment
    from pr98_pilot_license_recovery import license_binding

    require(
        {p.name for p in stage.iterdir()}
        <= {
            "source",
            "binding-receipts",
            "input-bindings.private.json",
            "preparation-review.json",
        },
        "fresh isolated campaign stage",
    )
    require((stage / "source").is_dir(), "isolated source")
    blocks = matrix()
    parents = {b["instance"]: b["parent"] for b in blocks}
    require(
        set(inputs) == set(parents), "input bindings must cover exactly 22 instances"
    )
    for alias, parent in parents.items():
        inspect_input(inputs[alias], parent)
    require(
        len({item["model_sha256"] for item in inputs.values()}) == len(parents),
        "duplicate model identities",
    )
    require(shutil.disk_usage(stage).free >= 384 * 1024**3, "storage admission")
    for name in ("run", "logs", "claims"):
        (stage / name).mkdir()
    write(stage / "inputs.private.json", inputs)
    write(
        stage / "plan.json",
        {
            "source_commit": source_commit(),
            "runtime_environment": workspace_environment(stage, create=True),
            "environment": versions(),
            "site": site_preflight(),
            "license": license_binding(),
            "baseline_parameters": baseline_parameters(),
            "working_storage_GiB_ceiling": 320,
            "child_deadline_seconds": 4500,
            "inputs_sha256": digest(stage / "inputs.private.json"),
            "matrix": blocks,
            "budget": budget(blocks),
            "time_limit_seconds": TIME_LIMIT,
            "automatic_retry": False,
        },
    )
    print(digest(stage / "plan.json"))


def admitted(stage, expected):
    from pr94_evaluation_contract import baseline_parameters
    from pr94_isolated_preparation import versions
    from pr98_hard_preparation import workspace_environment
    from pr98_pilot_license_recovery import license_binding

    path = stage / "plan.json"
    require(digest(path) == expected, "plan hash")
    plan = read(path)
    require(
        plan["runtime_environment"] == workspace_environment(stage),
        "runtime environment",
    )
    require(
        plan["source_commit"] == source_commit()
        and plan["matrix"] == matrix()
        and plan["budget"] == budget(matrix())
        and plan["time_limit_seconds"] == TIME_LIMIT
        and plan["automatic_retry"] is False,
        "plan drift",
    )
    require(
        plan["environment"] == versions()
        and plan["license"] == license_binding()
        and plan["baseline_parameters"] == baseline_parameters()
        and plan["working_storage_GiB_ceiling"] == 320
        and plan["child_deadline_seconds"] == 4500,
        "execution environment or policy drift",
    )
    require(
        digest(stage / "inputs.private.json") == plan["inputs_sha256"],
        "input manifest drift",
    )
    approval = read(stage / "authorization.json")
    require(
        approval.get("plan_sha256") == expected
        and approval.get("budget") == plan["budget"]
        and approval.get("execution_approved") is True
        and isinstance(approval.get("decision"), str)
        and approval["decision"].strip(),
        "recorded author authorization required",
    )
    return plan


def block_at(threads, index):
    rows = [row for row in matrix() if row["threads"] == threads]
    require(0 <= index < len(rows), "invalid array index")
    return rows[index]


def queue(stage, expected, account, partition):
    plan = admitted(stage, expected)
    site_preflight()
    require(
        all(re.fullmatch(r"[A-Za-z0-9_-]+", x) for x in (account, partition)),
        "invalid account or partition",
    )
    require(shutil.disk_usage(stage).free >= 384 * 1024**3, "storage admission")
    inputs = read(stage / "inputs.private.json")
    for alias, item in inputs.items():
        inspect_input(
            item,
            next(row["parent"] for row in plan["matrix"] if row["instance"] == alias),
        )
    write(
        EVIDENCE / "pr98-full-990-v1.claim.json",
        {"stage": str(stage), "plan_sha256": expected},
    )
    write(stage / "claims" / "submit.json", {"plan_sha256": expected})
    jobs = {}
    previous = None
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_", "SRUN_"))
        and k not in {"PYTHONPATH", "PYTHONHOME"}
    }
    env["GRB_LICENSE_FILE"] = plan["license"]["path"]
    env["CUDA_VISIBLE_DEVICES"] = ""
    for threads in sorted({threads for threads, _ in PROFILES}):
        count = sum(b["threads"] == threads for b in plan["matrix"])
        command = [
            "sbatch",
            "--parsable",
            "--hold",
            "--no-requeue",
            "--nodes=1",
            "--ntasks=1",
            f"--cpus-per-task={threads}",
            "--hint=nomultithread",
            f"--mem={MEMORY_MIB}M",
            f"--time={WALL_HOURS}:00:00",
            f"--account={account}",
            f"--partition={partition}",
            "--job-name=cfl-mvp2-concurrent",
            "--export=ALL,GRB_LICENSE_FILE=" + plan["license"]["path"],
            f"--array=0-{count - 1}%{ARRAY_CAP}",
            f"--chdir={ROOT}",
            f"--output={stage / 'logs' / '%A_%a.out'}",
            f"--error={stage / 'logs' / '%A_%a.err'}",
        ]
        if previous is not None:
            command.append(f"--dependency=afterok:{previous}")
        command.append(
            "--wrap="
            + shlex.join(
                [
                    sys.executable,
                    "-B",
                    str(Path(__file__).resolve()),
                    "worker",
                    str(stage),
                    expected,
                    str(threads),
                ]
            )
        )
        # A partial scheduler response is retained in the held state for reconciliation.
        raw = subprocess.check_output(command, env=env, text=True, timeout=60).strip()
        write(stage / "claims" / f"array-{threads}.json", {"scheduler_receipt": raw})
        previous = raw.split(";", 1)[0]
        require(previous.isdigit(), "ambiguous scheduler receipt; preserve all holds")
        jobs[str(threads)] = previous
    write(stage / "submission.json", {"plan_sha256": expected, "held_arrays": jobs})
    print(json.dumps(jobs, sort_keys=True))


def policy_for(row):
    from pr94_evaluation_contract import baseline_parameters

    class Policy:
        THRESHOLDS = ()
        ALLOW_ABSTENTION = True
        RECORD_PROGRESS = False

        @staticmethod
        def parameters(cell):
            return {
                **baseline_parameters(),
                "Threads": row["threads"],
                "Seed": row["seed"],
                "ConcurrentMIP": row["concurrent"],
                "TimeLimit": TIME_LIMIT,
                "MIPGap": 1e-4,
                "SoftMemLimit": 48,
            }

        @staticmethod
        def Recorder():
            return None

    return Policy


def runtime(stage, expected, threads):
    from pr86_isolated_executor import allocation

    admitted(stage, expected)
    submission = read(stage / "submission.json")
    require(
        read(EVIDENCE / "pr98-full-990-v1.claim.json")
        == {"stage": str(stage), "plan_sha256": expected},
        "campaign-wide claim",
    )
    require(
        submission["plan_sha256"] == expected
        and os.environ.get("SLURM_ARRAY_JOB_ID")
        == submission["held_arrays"][str(threads)],
        "scheduler identity",
    )
    row = block_at(threads, int(os.environ["SLURM_ARRAY_TASK_ID"]))
    job, gate = allocation(threads)
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    return row, job, gate


def validate_result(result, row, item, method):
    require(
        result["gate_status"] == "passed"
        and result["callback_errors"] == []
        and result["optimization_calls"] == 1
        and result["method"] == method
        and result["mip_sha256"] == item["model_sha256"]
        and result["effective_objective_sense"] == "MINIMIZE"
        and result["fresh_model"]
        and result["mathematical_model_unchanged"],
        "terminal result gate",
    )
    require(
        result["parameters"] == policy_for(row).parameters({})
        and result["mathematical_signature_sha256"]
        == item["mathematical_signature_sha256"],
        "terminal parameters or mathematical model",
    )
    start = result["start"]
    require(
        start["submitted_assignments"]
        == (0 if method == "M0" else item["selected_support"]),
        "terminal Start cardinality",
    )
    if method != "M0":
        require(
            start["assignment_sha256"] == item[method + "_assignment_sha256"]
            and start["positive_assignments"] == item["positive_assignments"],
            "terminal Start identity",
        )


def cell(stage, expected, threads, method):
    from pr94_evaluation_solver import solve

    row, _, gate = runtime(stage, expected, threads)
    require(method in row["methods"], "method not in paired block")
    item = read(stage / "inputs.private.json")[row["instance"]]
    model, starts = inspect_input(item, row["parent"])
    folder = stage / "run" / row["id"]
    require(folder.is_dir() and not folder.is_symlink(), "owned block")
    chosen = (
        None
        if method == "M0"
        else starts[{"M1": "root_lp", "M2": "gnn"}[method]]["assignments"]
    )

    def intent():
        require(gate.sample() < 56 * 1024**3, "memory before optimize")
        require(
            shutil.disk_usage(stage).free >= 64 * 1024**3, "storage before optimize"
        )
        write(
            folder / (method + ".intent.json"),
            {"maximum_calls": 1, "plan_sha256": expected},
        )

    result = solve(
        model,
        item["model_sha256"],
        [],
        "unguided_control" if chosen is None else "partial_mip_start",
        preselected_assignments=chosen,
        reported_method=method,
        private_log_path=folder / (method + ".private.log"),
        solution_path=folder / (method + ".solution.private.json.gz"),
        cell={
            "method": method,
            "seed": row["seed"],
            "model_sha256": item["model_sha256"],
        },
        before_optimize=intent,
        execution_policy=policy_for(row),
    )
    write(
        folder / (method + ".result.json"),
        {
            "result": result,
            "plan_sha256": expected,
            "block": row,
            "progress_scope": "terminal_only",
            "start_message_scope": "first_racer"
            if row["concurrent"] > 1
            else "conventional",
        },
    )
    validate_result(result, row, item, method)


def worker(stage, expected, threads):
    import resource
    import time

    from paired_memory_runtime_v2 import supervise

    row, job, gate = runtime(stage, expected, threads)
    folder = stage / "run" / row["id"]
    folder.mkdir()
    write(folder / "block.json", {"row": row, "job_id": job, "plan_sha256": expected})
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024**2, 512 * 1024**2))
    started = time.monotonic()
    for method in row["methods"]:
        require(time.monotonic() - started + 4500 <= 14100, "block time reserve")
        observed = supervise(
            [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "cell",
                str(stage),
                expected,
                str(threads),
                "--method",
                method,
            ],
            folder / (method + ".console.private.log"),
            4500,
            gate,
        )
        write(folder / (method + ".supervision.private.json"), observed)
        require(
            observed["guard_stop"] is None and observed["child_exit_code"] == 0,
            "preserve failed cell and stop paired block",
        )
        storage(stage)
    write(folder / "complete.json", {"plan_sha256": expected, "block_id": row["id"]})


def storage(stage, admission=False):
    require(
        shutil.disk_usage(stage).free >= (384 if admission else 64) * 1024**3,
        "campaign free storage",
    )
    total = 0
    for parent in (stage / "run", stage / "logs"):
        if parent.exists():
            for p in parent.rglob("*"):
                require(not p.is_symlink(), "output symlink")
                if p.is_file():
                    total += p.stat().st_size
    require(total <= 320 * 1024**3, "campaign working storage ceiling")
    return total


def held_profile(text, job, threads, count, previous):
    fields = dict(x.split("=", 1) for x in text.split() if "=" in x)
    require(
        fields.get("JobId", "").split("_", 1)[0] == job
        and fields.get("ArrayJobId") == job
        and fields.get("ArrayTaskId") == f"0-{count - 1}%{ARRAY_CAP}",
        "held array identity",
    )
    for key, value in {
        "JobState": "PENDING",
        "Reason": "JobHeldUser",
        "Partition": "batch",
        "Requeue": "0",
        "Restarts": "0",
        "NumTasks": "1",
        "CPUs/Task": str(threads),
        "TimeLimit": "04:00:00",
        "JobName": "cfl-mvp2-concurrent",
    }.items():
        require(fields.get(key) == value, "held " + key)
    require(fields.get("UserId", "").split("(", 1)[0] == "vrcelestino", "held user")
    require(fields.get("WorkDir") == str(ROOT), "held source")
    require(
        fields.get("NumNodes") in {"1", "1-1"}
        and fields.get("NumCPUs") in {str(threads), str(2 * threads)}
        and fields.get("MinMemoryNode") in {"64G", "65536M"},
        "held resources",
    )
    pairs = [
        p.split("=", 1)
        for p in fields.get("TRES", fields.get("ReqTRES", "")).split(",")
    ]
    require(all(len(p) == 2 for p in pairs), "held TRES syntax")
    tres = dict(pairs)
    require(
        len(pairs) == len(tres)
        and set(tres) <= {"cpu", "mem", "node", "billing", "gres/gpu"}
        and tres.get("cpu") == fields["NumCPUs"]
        and tres.get("mem") in {"64G", "65536M"}
        and tres.get("node") == "1"
        and tres.get("gres/gpu", "0") == "0",
        "held TRES",
    )
    dependency = fields.get("Dependency", "(null)")
    require(
        dependency == "(null)"
        if previous is None
        else dependency in {f"afterok:{previous}", f"afterok:{previous}(unfulfilled)"},
        "held dependency",
    )
    return fields


def release(stage, expected):
    from pr94_isolated_preparation import command

    admitted(stage, expected)
    submission = read(stage / "submission.json")
    require(
        submission["plan_sha256"] == expected
        and set(submission["held_arrays"]) == {"1", "4", "8"},
        "three held arrays",
    )
    profiles = {}
    previous = None
    for threads in (1, 4, 8):
        job = submission["held_arrays"][str(threads)]
        count = sum(row["threads"] == threads for row in matrix())
        profiles[str(threads)] = held_profile(
            command(["scontrol", "show", "job", job, "-o"]),
            job,
            threads,
            count,
            previous,
        )
        previous = job
    write(stage / "held-review.private.json", profiles)
    write(stage / "claims/release.json", {"plan_sha256": expected})
    for threads in (1, 4, 8):
        command(["scontrol", "release", submission["held_arrays"][str(threads)]])
    write(
        stage / "released.json",
        {"plan_sha256": expected, "arrays": submission["held_arrays"]},
    )
    print(
        json.dumps(
            {"released_arrays": submission["held_arrays"], "maximum_evaluations": 990}
        )
    )


def collect(stage, expected):
    import csv
    import io
    import uuid
    import zipfile

    from pr94_isolated_preparation import command

    plan = admitted(stage, expected)
    submission = read(stage / "submission.json")
    jobs = submission["held_arrays"]
    raw = command(
        [
            "sacct",
            "-X",
            "-n",
            "-P",
            "-j",
            ",".join(jobs.values()),
            "--format=JobID%40,State,ElapsedRaw,ExitCode,AllocCPUS,MaxRSS,TotalCPU",
        ]
    )
    terminal = {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "TIMEOUT",
        "OUT_OF_MEMORY",
        "NODE_FAIL",
        "PREEMPTED",
        "BOOT_FAIL",
        "DEADLINE",
        "REVOKED",
    }
    by_array = {v: int(k) for k, v in jobs.items()}
    observed = {}
    for fields in csv.reader(io.StringIO(raw), delimiter="|"):
        match = (
            re.fullmatch(r"([0-9]+)_([0-9]+)", fields[0].strip()) if fields else None
        )
        if not match:
            continue
        base, index = match.groups()
        require(base in by_array, "foreign accounting array")
        row = block_at(by_array[base], int(index))
        require(row["id"] not in observed, "duplicate accounting")
        require(fields[1].split()[0].rstrip("+") in terminal, "campaign not terminal")
        observed[row["id"]] = fields
    require(
        set(observed) == {row["id"] for row in matrix()},
        "330 terminal array tasks required",
    )
    members = {
        "plan.json": (stage / "plan.json").read_bytes(),
        "inputs.private.json": (stage / "inputs.private.json").read_bytes(),
        "submission.json": (stage / "submission.json").read_bytes(),
        "accounting.txt": raw.encode(),
    }
    dispositions = []
    for row in plan["matrix"]:
        folder = stage / "run" / row["id"]
        item = read(stage / "inputs.private.json")[row["instance"]]
        for method in row["methods"]:
            result = folder / (method + ".result.json")
            status = "missing_result"
            if result.exists():
                payload = result.read_bytes()
                require(len(payload) <= 4 * 1024**2, "bounded result metadata")
                members[f"results/{row['id']}/{method}.json"] = payload
                try:
                    value = json.loads(payload)
                    require(
                        value["plan_sha256"] == expected and value["block"] == row,
                        "result binding",
                    )
                    validate_result(value["result"], row, item, method)
                    status = "gate_passed_pending_scientific_qualification"
                except (KeyError, ValueError, TypeError):
                    status = "unqualified_record_preserved"
            for name in (method + ".intent.json", method + ".supervision.private.json"):
                path = folder / name
                if path.exists():
                    members[f"diagnostics/{row['id']}/{name}"] = path.read_bytes()
            dispositions.append(
                {"block": row["id"], "method": method, "status": status}
            )
    members["dispositions.json"] = json.dumps(dispositions, sort_keys=True).encode()
    members["manifest.json"] = json.dumps(
        {
            "members": {
                name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                for name, raw in members.items()
            },
            "expected": 990,
            "received": sum(d["status"] != "missing_result" for d in dispositions),
            "scientific_reporting_eligible": False,
        },
        sort_keys=True,
    ).encode()
    path = stage / ("terminal-results-" + uuid.uuid4().hex + ".private.zip")
    with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    print(
        json.dumps(
            {
                "ARQUIVO_HPC": str(path),
                "SHA256": digest(path),
                "EXPECTED": 990,
                "RECEIVED": sum(d["status"] != "missing_result" for d in dispositions),
                "UNQUALIFIED": sum(
                    d["status"] == "unqualified_record_preserved" for d in dispositions
                ),
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("matrix")
    freeze_parser = subs.add_parser("freeze")
    queue_parser = subs.add_parser("queue-held")
    worker_parser = subs.add_parser("worker")
    cell_parser = subs.add_parser("cell")
    release_parser = subs.add_parser("release")
    collect_parser = subs.add_parser("collect")
    for sub in (
        freeze_parser,
        queue_parser,
        worker_parser,
        cell_parser,
        release_parser,
        collect_parser,
    ):
        sub.add_argument("stage", type=Path)
    freeze_parser.add_argument("inputs", type=Path)
    for sub in (
        queue_parser,
        worker_parser,
        cell_parser,
        release_parser,
        collect_parser,
    ):
        sub.add_argument("plan_sha256")
    queue_parser.add_argument("account")
    queue_parser.add_argument("partition")
    worker_parser.add_argument("threads", type=int)
    cell_parser.add_argument("threads", type=int)
    cell_parser.add_argument("--method", choices=METHODS, required=True)
    args = parser.parse_args()
    if args.command == "matrix":
        rows = matrix()
        print(json.dumps({"budget": budget(rows), "blocks": rows}, indent=2))
        return
    os.umask(0o077)
    stage = site_stage(args.stage)
    if args.command == "freeze":
        freeze(stage, read(args.inputs))
    elif args.command == "queue-held":
        queue(stage, args.plan_sha256, args.account, args.partition)
    elif args.command == "release":
        release(stage, args.plan_sha256)
    elif args.command == "collect":
        collect(stage, args.plan_sha256)
    elif args.command == "cell":
        cell(stage, args.plan_sha256, args.threads, args.method)
    else:
        worker(stage, args.plan_sha256, args.threads)


if __name__ == "__main__":
    main()
