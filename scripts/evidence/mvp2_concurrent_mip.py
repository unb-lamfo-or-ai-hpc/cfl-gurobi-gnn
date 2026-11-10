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
        and stage.name.startswith("mvp2-concurrent-"),
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
    validate_start(item, starts)
    return model, starts


def freeze(stage, inputs):
    require(not any(stage.iterdir()), "start with a fresh, empty stage")
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
            "inputs_sha256": digest(stage / "inputs.private.json"),
            "matrix": blocks,
            "budget": budget(blocks),
            "time_limit_seconds": TIME_LIMIT,
            "automatic_retry": False,
        },
    )
    print(digest(stage / "plan.json"))


def admitted(stage, expected):
    path = stage / "plan.json"
    require(digest(path) == expected, "plan hash")
    plan = read(path)
    require(
        plan["source_commit"] == source_commit()
        and plan["matrix"] == matrix()
        and plan["budget"] == budget(matrix())
        and plan["time_limit_seconds"] == TIME_LIMIT
        and plan["automatic_retry"] is False,
        "plan drift",
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
    write(stage / "claims" / "submit.json", {"plan_sha256": expected})
    jobs = {}
    previous = None
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_", "SRUN_"))
        and k not in {"PYTHONPATH", "PYTHONHOME"}
    }
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
            f"--array=0-{count - 1}%{ARRAY_CAP}",
            f"--chdir={ROOT}",
            f"--output={stage / 'logs' / '%A_%a.out'}",
            f"--error={stage / 'logs' / '%A_%a.err'}",
        ]
        if previous is not None:
            command.append(f"--dependency=afterany:{previous}")
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
        raw = subprocess.check_output(command, env=env, text=True).strip()
        write(stage / "claims" / f"array-{threads}.json", {"scheduler_receipt": raw})
        previous = raw.split(";", 1)[0]
        require(previous.isdigit(), "ambiguous scheduler receipt; preserve all holds")
        jobs[str(threads)] = previous
    write(stage / "submission.json", {"plan_sha256": expected, "held_arrays": jobs})
    print(json.dumps(jobs, sort_keys=True))


def worker(stage, expected, threads):
    from pr86_isolated_executor import allocation
    from pr94_evaluation_contract import baseline_parameters
    from pr94_evaluation_solver import solve

    admitted(stage, expected)
    submission = read(stage / "submission.json")
    require(
        submission["plan_sha256"] == expected
        and os.environ.get("SLURM_ARRAY_JOB_ID")
        == submission["held_arrays"][str(threads)],
        "scheduler identity",
    )
    row = block_at(threads, int(os.environ["SLURM_ARRAY_TASK_ID"]))
    job, gate = allocation(threads)
    item = read(stage / "inputs.private.json")[row["instance"]]
    model, starts = inspect_input(item, row["parent"])
    folder = stage / "run" / row["id"]
    folder.mkdir()
    write(folder / "block.json", {"row": row, "job_id": job, "plan_sha256": expected})

    class Policy:
        # Both profiles report terminal endpoints. Concurrent callbacks only see one racer.
        THRESHOLDS = ()
        ALLOW_ABSTENTION = True
        RECORD_PROGRESS = False

        @staticmethod
        def parameters(cell):
            return {
                **baseline_parameters(),
                "Threads": threads,
                "Seed": cell["seed"],
                "ConcurrentMIP": row["concurrent"],
                "TimeLimit": TIME_LIMIT,
                "MIPGap": 1e-4,
                "SoftMemLimit": 48,
            }

        @staticmethod
        def Recorder():
            return None

    for method in row["methods"]:
        chosen = (
            None
            if method == "M0"
            else starts[{"M1": "root_lp", "M2": "gnn"}[method]]["assignments"]
        )

        def intent():
            require(gate.sample() < 56 * 1024**3, "memory before optimize")
            require(
                shutil.disk_usage(stage).free >= 32 * 1024**3, "storage before optimize"
            )
            write(
                folder / f"{method}.intent.json",
                {"maximum_calls": 1, "plan_sha256": expected},
            )

        result = solve(
            model,
            item["model_sha256"],
            [],
            "unguided_control" if chosen is None else "partial_mip_start",
            preselected_assignments=chosen,
            reported_method=method,
            private_log_path=folder / f"{method}.private.log",
            solution_path=folder / f"{method}.solution.private.json.gz",
            cell={
                "method": method,
                "seed": row["seed"],
                "model_sha256": item["model_sha256"],
            },
            before_optimize=intent,
            execution_policy=Policy,
        )
        write(
            folder / f"{method}.result.json",
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
        require(
            result["gate_status"] == "passed", "preserve failed record and stop block"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("matrix")
    freeze_parser = subs.add_parser("freeze")
    queue_parser = subs.add_parser("queue-held")
    worker_parser = subs.add_parser("worker")
    for sub in (freeze_parser, queue_parser, worker_parser):
        sub.add_argument("stage", type=Path)
    freeze_parser.add_argument("inputs", type=Path)
    for sub in (queue_parser, worker_parser):
        sub.add_argument("plan_sha256")
    queue_parser.add_argument("account")
    queue_parser.add_argument("partition")
    worker_parser.add_argument("threads", type=int)
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
    else:
        worker(stage, args.plan_sha256, args.threads)


if __name__ == "__main__":
    main()
