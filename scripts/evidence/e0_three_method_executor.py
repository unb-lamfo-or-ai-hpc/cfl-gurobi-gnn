"""One bounded E0 job: six easy parents, three methods, existing private starts."""

import argparse
import hashlib
import json
import os
import re
import signal
import sys
import time
from pathlib import Path

import cpu_comparison_contract as contract
import paired_memory_runtime_v2 as memory
import prepare_e0_easy_starts as binding

review = binding.review
ROOT = Path(__file__).resolve().parents[2]
BINDING_SHA = "f7d4be22fd3105506e0dcde22db249d507744b4d5ab464e9b6625dd7e9f848c4"
BINDING_PATH = ROOT / "docs/evidence/e0/easy-start-binding.json"
INSTALLED = Path(
    "/raid/vrcelestino/data/cfl-mvp2-evidence/e0/starts-80bceb7cfb07/prepared"
)
DATA = Path("/raid/vrcelestino/data/cfl-gurobi-gnn/data")
PROTOCOL = "e0_existing_starts_three_method_execution_v1"
METHODS = tuple(review.proposal()["methods"])
PARAMETERS = {
    "Threads": 1,
    "Seed": 42,
    "TimeLimit": 3600,
    "MIPGap": 1e-4,
    "SoftMemLimit": 48,
}


def require(value, code):
    if not value:
        raise ValueError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def write(path, value):
    raw = encoded(value)
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


def read(path, maximum=32 * 1024**2):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), "regular_file_required")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, "size_limit")
    return raw


def parsed(path):
    return review.flow.meta.strict_json(read(path))


def receipt():
    return binding.validate(read(BINDING_PATH), BINDING_SHA)


def dependencies():
    # Source text uses LF identity on Windows and Linux; receipts retain raw bytes.
    files = [
        p
        for folder in (ROOT / "scripts/evidence", ROOT / "src", ROOT / "docs/evidence")
        for p in folder.rglob("*")
        if p.is_file() and p.suffix in {".py", ".sh"}
    ]
    return {
        p.relative_to(ROOT).as_posix(): digest(p.read_bytes().replace(b"\r\n", b"\n"))
        for p in sorted(files)
    }


def plan(head):
    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None, "source_commit")
    receipt()
    return {
        "protocol_id": PROTOCOL,
        "source_commit": head,
        "binding_sha256": BINDING_SHA,
        "source_sha256_lf": dependencies(),
        "parents": list(review.EASY),
        "methods": list(METHODS),
        "parameters": PARAMETERS,
        "effective_objective_sense": "MINIMIZE",
        "maximum_optimization_calls": 18,
        "maximum_solver_seconds": 64800,
        "child_deadline_seconds": 3780,
        "job_wall_seconds": 72000,
        "scheduler": {
            "partition": "batch",
            "nodes": 1,
            "tasks": 1,
            "cpus_per_task": 1,
            "memory_mib": 65536,
            "gpus": 0,
            "requeue": False,
            "exclusive": False,
        },
        "memory_policy": memory.POLICY,
        "automatic_retry": False,
        "new_root_solves": 0,
        "training_runs": 0,
        "new_forwards": 0,
        "root_precomputation_seconds": None,
        "scientific_reporting_eligible": False,
    }


def validate_stage(stage):
    stage = Path(stage)
    require(
        re.fullmatch(
            r"/raid/vrcelestino/data/cfl-mvp2-evidence/e0/solve-[0-9a-f]{12}",
            str(stage),
        )
        is not None,
        "stage_location",
    )
    require(stage.resolve() == stage and ROOT == stage / "source", "source_location")
    expected = plan((stage / "source_commit.txt").read_text().strip())
    require(parsed(stage / "plan.json") == expected, "plan_changed")
    return expected


def allocation():
    require(os.uname().nodename.split(".")[0] == "dgx-dasci", "host")
    for key, value in {
        "CONDA_DEFAULT_ENV": "tfm_env",
        "SLURM_CPUS_PER_TASK": "1",
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
    require(re.fullmatch(r"[0-9]+", job) is not None, "job_id")
    allowed = os.sched_getaffinity(0)
    require(bool(allowed), "affinity")
    cpu = min(allowed)
    os.sched_setaffinity(0, {cpu})
    require(os.sched_getaffinity(0) == {cpu}, "single_cpu_affinity")
    gate = memory.MemoryGate(job)
    memory.validate_public(gate.public())
    return job, gate


def private_inputs(parent):
    public = receipt()
    require(read(INSTALLED / "binding.json") == read(BINDING_PATH), "installed_binding")
    row = next(r for r in public["parents"] if r["parent"] == parent)
    candidates = parsed(INSTALLED / "private/input_paths.json")
    require(
        len(candidates) == 6 and {r["parent"] for r in candidates} == set(review.EASY),
        "input_parents",
    )
    private = next(r for r in candidates if r["parent"] == parent)
    reader = binding.Reader(DATA, seconds=120, max_bytes=2 * 1024**3)
    mip, status = binding.originals.original_model(
        reader.root / "raw/MILPBench/CFL", "easy", int(parent.rsplit("_", 1)[1])
    )
    require(
        status == "source_discovered" and str(mip) == private["mip_path"],
        "mip_identity",
    )
    reader.verify(mip, row["mip_sha256"])
    require(private["starts_file"] == parent + ".json", "start_filename")
    raw = read(INSTALLED / "private" / private["starts_file"])
    require(digest(raw) == row["private_starts_sha256"], "start_bytes")
    starts = review.flow.meta.strict_json(raw)
    sys.path.insert(0, str(ROOT / "src"))
    from cfl_gnn.graph.gurobi_graph_artifact import canonical_sha256

    for key, field in (
        ("gnn", "gnn_assignment_sha256"),
        ("root_lp", "lp_assignment_sha256"),
    ):
        assignments = starts[key]["assignments"]
        require(canonical_sha256(assignments) == row[field], "assignment_hash")
        require(
            len(assignments) == row["selected_support"]
            and sum(a["value"] for a in assignments) == row["positive_assignments"],
            "support",
        )
    return mip, starts, row


def public_result(result):
    # Never export solver messages, variable assignments or exception text.
    keys = (
        "gate_status method mip_sha256 model_fingerprint mathematical_signature_sha256 "
        "effective_objective_sense original_objective_sense fresh_model mathematical_model_unchanged "
        "solver_version python_version parameters parameter_sha256 solve independent_feasibility "
        "callback_errors trajectory timing scientific_reporting_eligible"
    ).split()
    value = {k: result[k] for k in keys}
    value["start"] = {
        k: v for k, v in result["start"].items() if k != "solver_messages"
    }
    return value


def child(stage, index):
    validate_stage(stage)
    _, gate = allocation()
    require(type(index) is int and 0 <= index < 18, "attempt_index")
    parent, method = review.EASY[index // 3], METHODS[index % 3]
    output = stage / "run" / f"attempt-{index:02d}"
    require(output.is_dir(), "supervisor_directory")
    # A durable claim forbids invoking this child twice, even after failure.
    write(output / "child.started.json", {"index": index})
    mip, starts, row = private_inputs(parent)
    require(gate.sample() < memory.POLICY["cgroup_interrupt_bytes"], "memory")
    sys.path.insert(0, str(ROOT / "src"))
    import gurobipy as gp

    from cfl_gnn.graph.instance_provenance import sha256_file
    from cfl_gnn.solvers.paired_partial_start import solve

    require(
        list(gp.gurobi.version()) == [13, 0, 1], "solver_version_before_optimization"
    )

    def claim():
        write(output / "optimize.intent.json", {"maximum_calls": 1})

    chosen = (
        None
        if index % 3 == 0
        else starts["root_lp" if index % 3 == 1 else "gnn"]["assignments"]
    )
    result = solve(
        mip,
        row["mip_sha256"],
        [],
        "unguided_control" if chosen is None else "partial_mip_start",
        solution_path=output / "solution.private.json.gz",
        preselected_assignments=chosen,
        reported_method=method,
        soft_mem_limit_gb=48,
        private_log_path=output / "gurobi.private.log",
        before_optimize=claim,
    )
    require(
        all(result["parameters"][k] == v for k, v in PARAMETERS.items()),
        "solver_parameters",
    )
    require(result["solver_version"] == [13, 0, 1], "solver_version")
    binding.Reader(DATA).verify(mip, row["mip_sha256"])
    report = {
        "index": index,
        "parent": parent,
        "method": method,
        "optimization_calls": 1,
        "result": public_result(result),
        "source_mip_unchanged": True,
        "gurobi_log": contract.seal_closed_log(output / "gurobi.private.log"),
    }
    if (output / "solution.private.json.gz").exists():
        report["private_solution_sha256"] = sha256_file(
            output / "solution.private.json.gz"
        )
    write(output / "child.json", report)


def should_stop(supervision, child_report):
    if supervision["guard_stop"] is not None:
        return supervision["guard_stop"]
    if supervision["child_exit_code"] != 0 or child_report is None:
        return "child_failed"
    result = child_report["result"]
    if result["solve"]["solve_status_code"] == 17:
        return "solver_soft_memory_stop"
    if result["gate_status"] != "passed":
        return "result_validation_failed"
    return None


def run(stage):
    frozen = validate_stage(stage)
    job, gate = allocation()
    output = stage / "run"
    output.mkdir(exist_ok=False)
    rows, stop = [], None
    started = time.monotonic()
    prior_handler = signal.getsignal(signal.SIGTERM)

    def terminate(_signum, _frame):
        raise KeyboardInterrupt("batch_termination")

    signal.signal(signal.SIGTERM, terminate)
    try:
        for index in range(18):
            if time.monotonic() - started + 3800 > 71400:
                stop = "job_deadline_reserve"
                break
            attempt = output / f"attempt-{index:02d}"
            attempt.mkdir()
            supervision = memory.supervise(
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
                attempt / "console.private.log",
                3780,
                gate,
            )
            child_report = (
                parsed(attempt / "child.json")
                if (attempt / "child.json").exists()
                else None
            )
            stop = should_stop(supervision, child_report)
            row = {
                "index": index,
                "supervision": supervision,
                "child": child_report,
                "optimization_intent_present": (
                    attempt / "optimize.intent.json"
                ).exists(),
                "console_log": contract.seal_closed_log(
                    attempt / "console.private.log"
                ),
            }
            write(attempt / "receipt.json", row)
            rows.append(row)
            if stop:
                break
    except BaseException:
        stop = "executor_interrupted_or_failed"
        raise
    finally:
        signal.signal(signal.SIGTERM, prior_handler)
        write(
            output / "matrix.json",
            {
                "protocol_id": PROTOCOL,
                "job_id": job,
                "plan_sha256": digest(encoded(frozen)),
                "attempts": rows,
                "stop_code": stop,
                "complete": len(rows) == 18 and stop is None,
                "scientific_reporting_eligible": False,
            },
        )
    return stop is None and len(rows) == 18


def validate_matrix(value, frozen):
    require(
        value["protocol_id"] == PROTOCOL
        and value["plan_sha256"] == digest(encoded(frozen)),
        "matrix_identity",
    )
    rows = value["attempts"]
    require(re.fullmatch(r"[0-9]+", value["job_id"]) is not None, "matrix_job")
    require(
        len(rows) <= 18 and [r["index"] for r in rows] == list(range(len(rows))),
        "attempt_order",
    )
    for index, row in enumerate(rows):
        child_report = row["child"]
        if child_report is not None:
            require(
                child_report["index"] == index
                and child_report["parent"] == review.EASY[index // 3]
                and child_report["method"] == METHODS[index % 3],
                "child_identity",
            )
            result = child_report["result"]
            require(
                all(result["parameters"][k] == v for k, v in PARAMETERS.items()),
                "parameters",
            )
            require(
                result["solver_version"] == [13, 0, 1]
                and child_report["optimization_calls"] == 1,
                "solver",
            )
            require(
                result["mip_sha256"] == receipt()["parents"][index // 3]["mip_sha256"],
                "mip",
            )
            require(
                result["effective_objective_sense"] == "MINIMIZE"
                and result["mathematical_model_unchanged"],
                "model",
            )
            expected = receipt()["parents"][index // 3]
            require(
                result["start"]["submitted_assignments"]
                == (0 if index % 3 == 0 else expected["selected_support"]),
                "start_support",
            )
            if index % 3:
                field = (
                    "lp_assignment_sha256"
                    if index % 3 == 1
                    else "gnn_assignment_sha256"
                )
                require(
                    result["start"]["assignment_sha256"] == expected[field]
                    and result["start"]["positive_assignments"]
                    == expected["positive_assignments"],
                    "start_binding",
                )
            else:
                require(
                    result["start"]["positive_assignments"] == 0
                    and result["start"]["status"] == "not_submitted",
                    "control_start",
                )
            require(
                child_report["source_mip_unchanged"] is True
                and row["optimization_intent_present"] is True,
                "source_or_call",
            )
            if index % 3 and rows[index - index % 3]["child"] is not None:
                control = rows[index - index % 3]["child"]["result"]
                require(
                    result["mathematical_signature_sha256"]
                    == control["mathematical_signature_sha256"]
                    and result["parameters"] == control["parameters"],
                    "unpaired_model_or_parameters",
                )
        if should_stop(row["supervision"], child_report) is not None:
            require(
                index == len(rows) - 1 and value["stop_code"] is not None,
                "stop_not_propagated",
            )
    require(
        value["complete"] == (len(rows) == 18 and value["stop_code"] is None),
        "completion",
    )
    require(
        value["complete"] or value["stop_code"] is not None, "incomplete_without_stop"
    )
    require(value["scientific_reporting_eligible"] is False, "scientific_gate")
    return value


def validate_return(value):
    require(
        value["protocol_id"] == PROTOCOL
        and value["plan"] == plan(value["plan"]["source_commit"]),
        "return_plan",
    )
    require(
        value["raw_logs_included"] is False
        and value["scientific_reporting_eligible"] is False,
        "return_scope",
    )
    rows = [r.split("|") for r in value["accounting"].splitlines()[1:]]
    job = value["job_id"]
    parent = [r for r in rows if r[0] == job]
    require(
        re.fullmatch(r"[0-9]+", job) is not None
        and len(parent) == 1
        and len(parent[0]) == 8,
        "accounting",
    )
    require(
        parent[0][1].split()[0]
        in {
            "COMPLETED",
            "FAILED",
            "TIMEOUT",
            "OUT_OF_MEMORY",
            "CANCELLED",
            "NODE_FAIL",
            "PREEMPTED",
        },
        "terminal",
    )
    matrix = value["matrix"]
    if matrix is not None:
        validate_matrix(matrix, value["plan"])
        require(matrix["job_id"] == job, "job_binding")
    ready = bool(
        matrix
        and matrix["complete"]
        and parent[0][1] == "COMPLETED"
        and parent[0][3] == "0:0"
    )
    require(
        type(value["ready_for_independent_review"]) is bool
        and value["ready_for_independent_review"] == ready,
        "review_readiness",
    )
    return value


def collect(stage):
    frozen = validate_stage(stage)
    accounting = (stage / "accounting.txt").read_text()
    job = (stage / "job_id.txt").read_text().strip()
    rows = [r.split("|") for r in accounting.splitlines()[1:]]
    parent = [r for r in rows if r[0] == job]
    require(
        len(parent) == 1
        and parent[0][1].split()[0]
        in {
            "COMPLETED",
            "FAILED",
            "TIMEOUT",
            "OUT_OF_MEMORY",
            "CANCELLED",
            "NODE_FAIL",
            "PREEMPTED",
        },
        "nonterminal",
    )
    matrix = (
        parsed(stage / "run/matrix.json")
        if (stage / "run/matrix.json").exists()
        else None
    )
    if matrix is not None:
        validate_matrix(matrix, frozen)
        for row in matrix["attempts"]:
            attempt = stage / "run" / f"attempt-{row['index']:02d}"
            require(
                contract.seal_closed_log(attempt / "console.private.log")
                == row["console_log"],
                "console_changed",
            )
            if row["child"] is not None:
                require(
                    contract.seal_closed_log(attempt / "gurobi.private.log")
                    == row["child"]["gurobi_log"],
                    "gurobi_log_changed",
                )
    value = {
        "protocol_id": PROTOCOL,
        "plan": frozen,
        "accounting": accounting,
        "job_id": job,
        "matrix": matrix,
        "raw_logs_included": False,
        "ready_for_independent_review": bool(
            matrix
            and matrix["complete"]
            and parent[0][1] == "COMPLETED"
            and parent[0][3] == "0:0"
        ),
        "scientific_reporting_eligible": False,
    }
    validate_return(value)
    target = stage / "public_return.json"
    if target.exists():
        require(read(target) == encoded(value), "preserve_return")
        sha = digest(read(target))
    else:
        sha = write(target, value)
    print(f"E0_SOLVE_RETURN_SHA256={sha}\nE0_SOLVE_RETURN={target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "run", "child", "collect", "review"))
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--index", type=int)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.action == "plan":
        frozen = plan((args.stage / "source_commit.txt").read_text().strip())
        write(args.stage / "plan.json", frozen)
    elif args.action == "run":
        return 0 if run(args.stage) else 2
    elif args.action == "child":
        child(args.stage, args.index)
    elif args.action == "collect":
        collect(args.stage)
    else:
        raw = read(args.receipt)
        require(digest(raw) == args.expected_sha256, "return_sha256")
        value = review.flow.meta.strict_json(raw)
        validate_return(value)
        print(
            json.dumps(
                {
                    "job_id": value["job_id"],
                    "ready_for_independent_review": value[
                        "ready_for_independent_review"
                    ],
                    "scientific_reporting_eligible": False,
                }
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "state": "stopped_preserve_evidence_no_retry",
                    "exception_type": type(exc).__name__,
                }
            )
        )
        raise SystemExit(2) from None
