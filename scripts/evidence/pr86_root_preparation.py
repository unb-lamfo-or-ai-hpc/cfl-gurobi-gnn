"""Bounded prospective roots for PR86; no training, inference or main solves.

One explicit submission, ten isolated sequential children, no automatic retry.
Reuses the qualified memory supervisor, allocation and Slurm accounting parser.
Raw roots and logs stay private; collect exports an allowlisted JSON receipt.
"""

import argparse
import importlib.metadata
import json
import os
import re
import sys
import time
from pathlib import Path

import bind_pr86_existing_starts as binding
import pr86_isolated_executor as isolated
import qualification_workflow as accounting

from cfl_gnn.graph.gurobi_graph_artifact import (
    _finite_vector,
    canonical_sha256,
    write_root_artifact,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.solvers.paired_partial_start import mathematical_signature

require = isolated.require
write = isolated.metered.write_once
read = isolated.existing.read
parsed = isolated.existing.parsed
digest = isolated.metered.digest
encoded = isolated.metered.encoded
ROOT = isolated.ROOT
PROTOCOL = "pr86_ten_prospective_roots_v1"
BASE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence/pr86")
BINDING = BASE / "bindings-46802675ff99/prepared"
BINDING_SHA = "45eab23962f8427b28de1a86557cb03f251f4ecf49d62f23001f54a3215198b2"
PARAMETERS = dict(
    Threads=1,
    Seed=42,
    Presolve=0,
    NodeLimit=1,
    TimeLimit=600,
    SoftMemLimit=48,
    OutputFlag=1,
    LogToConsole=0,
)


def head():
    return accounting.command(
        ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT), "rev-parse", "HEAD"]
    ).strip()


def plan(commit):
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "source_commit")
    proposal, _ = isolated.proposal.build()
    return {
        "protocol_id": PROTOCOL,
        "source_commit": commit,
        "source_sha256_lf": isolated.existing.dependencies(),
        "formulation_contract": isolated.FORMULATION_CONTRACT,
        "binding_sha256": BINDING_SHA,
        "parents": [
            {"parent": p["parent"], "model_sha256": p["model_sha256"]}
            for p in proposal["parents"]
        ],
        "parameters": PARAMETERS,
        "maximum_optimization_calls": 10,
        "maximum_submissions": 1,
        "concurrent_children": 1,
        "child_deadline_seconds": 1140,
        "job_wall_seconds": 12000,
        "scheduler": {
            "partition": "batch",
            "nodes": 1,
            "tasks": 1,
            "physical_cores": 1,
            "memory_mib": 65536,
            "gpus": 0,
            "exclusive": False,
            "requeue": False,
        },
        "memory": isolated.memory.POLICY,
        "automatic_retry": False,
        "main_solves_admitted": False,
        "inference_admitted": False,
        "training_admitted": False,
        "resource_budget_approved": False,
        "scientific_reporting_eligible": False,
    }


def inputs(frozen):
    public = binding.validate(read(BINDING / "public/binding.json"), BINDING_SHA)
    private = parsed(BINDING / "private/input_paths.json")
    expected = frozen["parents"]
    require(
        [p["parent"] for p in private] == [p["parent"] for p in expected], "parents"
    )
    for p, reference in zip(public["parents"], expected):
        require(
            p["parent"] == reference["parent"]
            and p["mip_sha256"] == reference["model_sha256"],
            "bound_parent",
        )
    return private


def load(stage):
    frozen = parsed(stage / "plan.json")
    require(frozen == plan(head()), "installed_plan_or_source_changed")
    require(
        stage.resolve() == BASE / ("roots-" + frozen["source_commit"][:12]), "stage"
    )
    require(not (ROOT / "gurobi.env").exists(), "unexpected_parameter_file")
    return frozen


def prepare(stage):
    accounting.host()
    frozen = plan(head())
    require(
        stage.resolve() == BASE / ("roots-" + frozen["source_commit"][:12]), "stage"
    )
    inputs(frozen)
    require(not (stage / "plan.json").exists(), "already_prepared")
    sha = write(stage / "plan.json", frozen)
    print(
        json.dumps(
            {
                "plan_sha256": sha,
                "maximum_optimization_calls": 10,
                "maximum_submissions": 1,
                "resource_budget_approved": False,
            }
        )
    )


def approve_and_submit(stage, approved_sha):
    accounting.host()
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "environment")
    frozen = load(stage)
    require(digest(read(stage / "plan.json")) == approved_sha, "approved_plan_hash")
    inputs(frozen)
    # A single campaign-wide claim survives ambiguous sbatch outcomes and source changes.
    claim = BASE / "prospective-root-preparation.claim"
    claim.mkdir(exist_ok=False)
    write(
        claim / "claim.json",
        {"plan_sha256": approved_sha, "source_commit": frozen["source_commit"]},
    )
    write(
        stage / "approval.json",
        {
            "plan_sha256": approved_sha,
            "explicit_user_authorization": True,
            "maximum_optimization_calls": 10,
            "maximum_submissions": 1,
            "automatic_retry": False,
        },
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_"))
        and k not in ("PYTHONHOME", "PYTHONPATH")
    }
    env.update(PR86_SOURCE=str(ROOT), PR86_STAGE=str(stage), PR86_PYTHON=sys.executable)
    response = accounting.command(
        [
            "sbatch",
            "--parsable",
            "--partition=batch",
            "--nodes=1-1",
            "--ntasks=1",
            "--cpus-per-task=1",
            "--hint=nomultithread",
            "--mem=64G",
            "--time=03:20:00",
            "--no-requeue",
            "--job-name=cfl_pr86_roots",
            "--chdir=" + str(ROOT),
            "--output=" + str(stage / "job-%j.private.out"),
            "--error=" + str(stage / "job-%j.private.err"),
            str(ROOT / "scripts/evidence/operate_pr86_roots.sh"),
            "batch",
        ],
        timeout=30,
        env=env,
    )
    job = response.strip().split(";")[0]
    require(re.fullmatch(r"[0-9]+", job), "ambiguous_submission_preserve_claim")
    write(stage / "submission.json", {"job_id": job, "plan_sha256": approved_sha})
    return {"job_id": job, "automatic_retry": False}


def approved(stage, frozen):
    value = parsed(stage / "approval.json")
    require(
        value
        == {
            "plan_sha256": digest(encoded(frozen)),
            "explicit_user_authorization": True,
            "maximum_optimization_calls": 10,
            "maximum_submissions": 1,
            "automatic_retry": False,
        },
        "approval",
    )


def capture(mip, expected_sha, destination, claim):
    """Same first optimal node-zero MIPNODE policy, with owned native resources."""
    import gurobipy as gp
    from pr86_native_model import NativeModel

    require(list(gp.gurobi.version()) == [13, 0, 1], "gurobi_version")
    require(sha256_file(mip) == expected_sha, "model_hash")
    backend = NativeModel(mip, "gurobi", 600)
    captured, callback_failed = {}, []
    try:
        model = backend.model
        for key, value in PARAMETERS.items():
            setattr(model.Params, key, value)
        model.Params.LogFile = str(destination / "gurobi.private.log")
        model.update()
        require(
            not (
                model.NumQNZs
                or model.NumQConstrs
                or model.NumGenConstrs
                or model.NumSOS
            ),
            "linear_milp_required",
        )
        require(model.ModelSense == gp.GRB.MINIMIZE, "effective_minimize")
        require(model.SolCount == 0 and model.NumStart == 0, "fresh_root_model")
        require(
            all(getattr(model.Params, k) == v for k, v in PARAMETERS.items()),
            "parameters",
        )
        signature = mathematical_signature(model)
        variables = tuple(model.getVars())
        names = [v.VarName for v in variables]
        require(len(names) == len(set(names)), "unique_variable_order")

        def observer(m, where):
            if captured or callback_failed or where != gp.GRB.Callback.MIPNODE:
                return
            try:
                if (
                    int(m.cbGet(gp.GRB.Callback.MIPNODE_STATUS)) != gp.GRB.OPTIMAL
                    or abs(float(m.cbGet(gp.GRB.Callback.MIPNODE_NODCNT))) > 1e-9
                ):
                    return
                vector = _finite_vector(
                    m.cbGetNodeRel(variables), expected=len(names), field="root"
                )
                objective = float(m.cbGet(gp.GRB.Callback.MIPNODE_OBJBND))
                _finite_vector([objective], expected=1, field="root_objective")
                captured.update(vector=vector.tolist(), objective=objective)
                m.terminate()
            except Exception:
                callback_failed.append(True)
                m.terminate()

        claim()
        model.optimize(observer)
        require(not callback_failed and bool(captured), "optimal_root_not_observed")
        require(int(model.Status) != 17, "root_soft_memory_stop")
        require(mathematical_signature(model) == signature, "model_changed")
        require(sha256_file(mip) == expected_sha, "source_changed")
        parameter_map = {**PARAMETERS, "ModelSense": 1}
        return {
            "schema_version": 1,
            "authority": "gurobi",
            "source_mip_sha256": expected_sha,
            "capture_method": "first_optimal_root_gurobi_mipnode",
            "original_objective_sense": backend.original_sense,
            "effective_objective_sense": "MINIMIZE",
            "variable_count": len(names),
            "variable_names": names,
            "variable_order_sha256": canonical_sha256(names),
            "relaxation_vector": captured["vector"],
            "vector_sha256": canonical_sha256(captured["vector"]),
            "node_count": 0,
            "root_objective_bound": captured["objective"],
            "solver_parameter_map": parameter_map,
            "solver_parameter_sha256": canonical_sha256(parameter_map),
            "mathematical_signature_sha256": signature,
        }
    finally:
        backend.close()


def child(stage, index):
    frozen = load(stage)
    approved(stage, frozen)
    _, gate = isolated.allocation(1)
    require(type(index) is int and 0 <= index < 10, "index")
    target = frozen["parents"][index]
    item = inputs(frozen)[index]
    mip = Path(item["mip_path"])
    require(mip.is_file() and not mip.is_symlink(), "model_file")
    folder = stage / "run" / str(index)
    write(folder / "child.started.json", {"parent": target["parent"]})
    started = time.perf_counter()

    def claim():
        load(stage)
        require(
            gate.sample() < isolated.memory.POLICY["cgroup_interrupt_bytes"], "memory"
        )
        write(
            folder / "optimize.intent.json",
            {"parent": target["parent"], "maximum_calls": 1},
        )

    root = capture(mip, target["model_sha256"], folder, claim)
    capture_seconds = time.perf_counter() - started
    export_started = time.perf_counter()
    root_sha = write_root_artifact(folder / "root.private.json.gz", root)
    export_seconds = time.perf_counter() - export_started
    write(
        folder / "result.json",
        {
            "parent": target["parent"],
            "model_sha256": target["model_sha256"],
            "root_sha256": root_sha,
            "variable_order_sha256": root["variable_order_sha256"],
            "vector_sha256": root["vector_sha256"],
            "variable_count": root["variable_count"],
            "mathematical_signature_sha256": root["mathematical_signature_sha256"],
            "source_objective_sense": root["original_objective_sense"],
            "effective_objective_sense": "MINIMIZE",
            "optimization_calls": 1,
            "capture_wall_seconds": capture_seconds,
            "root_export_wall_seconds": export_seconds,
            "gurobi_log": isolated.logs.seal_closed_log(folder / "gurobi.private.log"),
            "scientific_reporting_eligible": False,
        },
    )


def run(stage):
    frozen = load(stage)
    approved(stage, frozen)
    job, gate = isolated.allocation(1)
    # sbatch may start before its reply reaches the submitting process. The job
    # identity is recorded here and reconciled with submission.json at collection.
    folder = stage / "run"
    folder.mkdir(exist_ok=False)
    write(folder / "batch.started.json", {"job_id": job})
    rows, stop = [], None
    started = time.monotonic()
    try:
        for index, target in enumerate(frozen["parents"]):
            require(time.monotonic() - started + 1140 < 12000, "deadline_reserve")
            attempt = folder / str(index)
            attempt.mkdir()
            observation = isolated.memory.supervise(
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
                1140,
                gate,
            )
            result = (
                parsed(attempt / "result.json")
                if (attempt / "result.json").exists()
                else None
            )
            passed = (
                observation["guard_stop"] is None
                and observation["child_exit_code"] == 0
                and result is not None
            )
            if result is not None:
                require(
                    result["parent"] == target["parent"]
                    and result["model_sha256"] == target["model_sha256"],
                    "result_parent",
                )
                require(
                    result["root_sha256"]
                    == sha256_file(attempt / "root.private.json.gz"),
                    "root_bytes",
                )
                require(
                    result["gurobi_log"]
                    == isolated.logs.seal_closed_log(attempt / "gurobi.private.log"),
                    "log_bytes",
                )
            row = {
                "parent": target["parent"],
                "result": result,
                "supervision": observation,
                "console_log": isolated.logs.seal_closed_log(
                    attempt / "console.private.log"
                ),
                "optimization_intent_present": (
                    attempt / "optimize.intent.json"
                ).exists(),
                "completed": passed,
            }
            write(attempt / "supervision.json", row)
            rows.append(row)
            if not passed:
                stop = "root_preparation_stopped"
                break
    except BaseException:
        stop = "root_preparation_exception"
        raise
    finally:
        write(
            folder / "summary.json",
            {
                "protocol_id": PROTOCOL,
                "job_id": job,
                "plan_sha256": digest(encoded(frozen)),
                "rows": rows,
                "complete": len(rows) == 10 and stop is None,
                "stop_code": stop,
                "batch_observed_wall_seconds": time.monotonic() - started,
                "versions": {
                    n: importlib.metadata.version(n) for n in ("numpy", "gurobipy")
                },
                "main_solves_added": 0,
                "forwards_added": 0,
                "training_runs_added": 0,
                "scientific_reporting_eligible": False,
            },
        )
    return 0 if stop is None else 2


def status(stage):
    accounting.host()
    submission = parsed(stage / "submission.json")
    job = submission["job_id"]
    require(re.fullmatch(r"[0-9]+", job), "job_id")
    return accounting.parse_accounting(
        accounting.command(
            [
                "sacct",
                "--noheader",
                "--parsable2",
                "-j",
                job,
                "--format=" + accounting.FIELDS,
            ]
        ),
        job,
    )


def collect(stage):
    frozen = load(stage)
    state = status(stage)
    require(state["terminal"], "not_terminal_no_wait")
    summary = (
        parsed(stage / "run/summary.json")
        if (stage / "run/summary.json").exists()
        else None
    )
    if summary is not None:
        require(
            summary["job_id"] == state["job_id"]
            and summary["plan_sha256"] == digest(encoded(frozen)),
            "job_identity",
        )
        for index, row in enumerate(summary["rows"]):
            folder = stage / "run" / str(index)
            require(row == parsed(folder / "supervision.json"), "supervision_changed")
            require(
                row["console_log"]
                == isolated.logs.seal_closed_log(folder / "console.private.log"),
                "console_changed",
            )
            if row["result"] is not None:
                require(
                    row["result"] == parsed(folder / "result.json"), "result_changed"
                )
                require(
                    row["result"]["root_sha256"]
                    == sha256_file(folder / "root.private.json.gz"),
                    "root_changed",
                )
                require(
                    row["result"]["gurobi_log"]
                    == isolated.logs.seal_closed_log(folder / "gurobi.private.log"),
                    "log_changed",
                )
    output = stage / "public_return.json"
    value = {
        "protocol_id": PROTOCOL,
        "source_commit": frozen["source_commit"],
        "plan_sha256": digest(encoded(frozen)),
        "accounting": state,
        "summary": summary,
        "raw_logs_included": False,
        "root_vectors_included": False,
        "ready_for_independent_review": bool(
            summary
            and summary["complete"]
            and state["state"] == "COMPLETED"
            and all(r["ExitCode"] == "0:0" for r in state["rows"])
        ),
        "scientific_reporting_eligible": False,
    }
    if output.exists():
        require(parsed(output) == value, "preserve_prior_collection")
    else:
        write(output, value)
    return {
        "return_sha256": digest(read(output)),
        "output": str(output),
        "ready_for_independent_review": value["ready_for_independent_review"],
    }


def validate_return(raw):
    value = isolated.existing.review.flow.meta.strict_json(raw)
    require(
        set(value)
        == {
            "protocol_id",
            "source_commit",
            "plan_sha256",
            "accounting",
            "summary",
            "raw_logs_included",
            "root_vectors_included",
            "ready_for_independent_review",
            "scientific_reporting_eligible",
        },
        "return_schema",
    )
    require(value["protocol_id"] == PROTOCOL, "return_protocol")
    frozen = plan(value["source_commit"])
    require(value["plan_sha256"] == digest(encoded(frozen)), "return_plan")
    for key in (
        "raw_logs_included",
        "root_vectors_included",
        "scientific_reporting_eligible",
    ):
        require(value[key] is False, "public_scope")
    state = value["accounting"]
    text = "\n".join(
        "|".join(str(row[k]) for k in accounting.FIELDS.split(","))
        for row in state["rows"]
    )
    require(
        accounting.parse_accounting(text, state["job_id"]) == state
        and state["terminal"],
        "accounting",
    )
    summary = value["summary"]
    complete = False
    if summary is not None:
        require(
            set(summary)
            == {
                "protocol_id",
                "job_id",
                "plan_sha256",
                "rows",
                "complete",
                "stop_code",
                "batch_observed_wall_seconds",
                "versions",
                "main_solves_added",
                "forwards_added",
                "training_runs_added",
                "scientific_reporting_eligible",
            },
            "summary_schema",
        )
        require(
            summary["protocol_id"] == PROTOCOL
            and summary["job_id"] == state["job_id"]
            and summary["plan_sha256"] == value["plan_sha256"],
            "summary_identity",
        )
        for key in ("main_solves_added", "forwards_added", "training_runs_added"):
            require(type(summary[key]) is int and summary[key] == 0, "scope_count")
        require(summary["scientific_reporting_eligible"] is False, "scope")
        isolated.costs.seconds(summary["batch_observed_wall_seconds"])
        rows = summary["rows"]
        require(len(rows) <= 10, "row_count")
        for index, row in enumerate(rows):
            require(
                set(row)
                == {
                    "parent",
                    "result",
                    "supervision",
                    "console_log",
                    "optimization_intent_present",
                    "completed",
                },
                "row_schema",
            )
            validate_log(row["console_log"])
            target = frozen["parents"][index]
            require(row["parent"] == target["parent"], "row_order")
            require(type(row["optimization_intent_present"]) is bool, "intent")
            observation, result = row["supervision"], row["result"]
            passed = (
                observation["guard_stop"] is None
                and observation["child_exit_code"] == 0
                and result is not None
            )
            require(
                type(row["completed"]) is bool and row["completed"] == passed,
                "completion",
            )
            require(passed or index == len(rows) - 1, "continued_after_failure")
            if result is not None:
                require(
                    set(result)
                    == {
                        "parent",
                        "model_sha256",
                        "root_sha256",
                        "variable_order_sha256",
                        "vector_sha256",
                        "variable_count",
                        "mathematical_signature_sha256",
                        "source_objective_sense",
                        "effective_objective_sense",
                        "optimization_calls",
                        "capture_wall_seconds",
                        "root_export_wall_seconds",
                        "gurobi_log",
                        "scientific_reporting_eligible",
                    },
                    "result_schema",
                )
                validate_log(result["gurobi_log"])
                require(
                    result["parent"] == target["parent"]
                    and result["model_sha256"] == target["model_sha256"],
                    "result_parent",
                )
                require(
                    result["effective_objective_sense"] == "MINIMIZE"
                    and result["source_objective_sense"] in ("MINIMIZE", "MAXIMIZE"),
                    "result_sense",
                )
                require(
                    type(result["optimization_calls"]) is int
                    and result["optimization_calls"] == 1,
                    "root_calls",
                )
                require(
                    result["scientific_reporting_eligible"] is False
                    and row["optimization_intent_present"],
                    "result_scope",
                )
                for key in (
                    "root_sha256",
                    "variable_order_sha256",
                    "vector_sha256",
                    "mathematical_signature_sha256",
                ):
                    require(re.fullmatch(r"[0-9a-f]{64}", result[key]), "result_hash")
                require(
                    type(result["variable_count"]) is int
                    and result["variable_count"] > 0,
                    "variables",
                )
                isolated.costs.seconds(result["capture_wall_seconds"])
                isolated.costs.seconds(result["root_export_wall_seconds"])
        complete = (
            len(rows) == 10
            and all(r["completed"] for r in rows)
            and summary["stop_code"] is None
        )
        require(
            type(summary["complete"]) is bool and summary["complete"] == complete,
            "summary_completion",
        )
    ready = (
        complete
        and state["state"] == "COMPLETED"
        and all(r["ExitCode"] == "0:0" for r in state["rows"])
    )
    require(
        type(value["ready_for_independent_review"]) is bool
        and value["ready_for_independent_review"] == ready,
        "readiness",
    )
    return value


def validate_log(value):
    require(
        set(value)
        == {
            "log_sha256",
            "log_size_bytes",
            "private_log_text_included",
            "hash_scope",
        },
        "log_schema",
    )
    require(re.fullmatch(r"[0-9a-f]{64}", value["log_sha256"]), "log_hash")
    require(
        type(value["log_size_bytes"]) is int
        and 0 <= value["log_size_bytes"] <= isolated.logs.MAX_LOG_BYTES,
        "log_size",
    )
    require(
        value["private_log_text_included"] is False
        and value["hash_scope"] == "bytes_after_caller_closed_writer",
        "log_scope",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "plan",
            "prepare",
            "submit",
            "run",
            "child",
            "status",
            "collect",
            "review",
        ),
    )
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--index", type=int)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.action == "review":
        raw = read(args.receipt)
        value = validate_return(raw)
        print(
            json.dumps(
                {
                    "return_sha256": digest(raw),
                    "job_id": value["accounting"]["job_id"],
                    "ready_for_independent_review": value[
                        "ready_for_independent_review"
                    ],
                }
            )
        )
        return 0
    if args.action == "plan":
        value = plan(head())
        print(
            json.dumps({"plan_sha256": digest(encoded(value)), "plan": value}, indent=2)
        )
        return 0
    require(args.stage is not None, "stage_required")
    if args.action == "prepare":
        prepare(args.stage)
    elif args.action == "submit":
        print(json.dumps(approve_and_submit(args.stage, args.approved_plan_sha256)))
    elif args.action == "run":
        return run(args.stage)
    elif args.action == "child":
        child(args.stage, args.index)
    else:
        print(
            json.dumps(
                status(args.stage) if args.action == "status" else collect(args.stage),
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
