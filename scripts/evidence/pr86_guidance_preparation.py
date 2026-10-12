"""Prospective graph construction, frozen mixed inference and matched starts.

No optimize/training call. One supervised GPU child; no automatic retry.
Historical graphs, predictions, sources and root-stage code remain unchanged.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import e0_frozen_inference as historical
import pr86_root_preparation as roots
import review_pr86_job3520 as review
import sprint_c_runtime

require, read, parsed, write = roots.require, roots.read, roots.parsed, roots.write
digest, encoded = roots.digest, roots.encoded
ROOT, BASE = roots.ROOT, roots.BASE
ROOT_STAGE = BASE / ("roots-" + review.COMMIT[:12])
PROTOCOL = "pr86_prospective_guidance_preparation_v1"
DATA = roots.isolated.existing.DATA
REGIONS = ("features", "inference", "assembly_gnn", "assembly_lp", "private_export")


def plan(commit):
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "commit")
    value, _, _ = review.review(read(review.DESTINATION / "public_return.json"))
    model = historical.plan()["models"]["mixed"]
    return {
        "protocol_id": PROTOCOL,
        "source_commit": commit,
        "source_sha256_lf": roots.isolated.existing.dependencies(),
        "root_return_sha256": review.SHA,
        "parents": [r["result"] for r in value["summary"]["rows"]],
        "frozen_model": model,
        "formulation_contract": roots.isolated.FORMULATION_CONTRACT,
        "maximum_forwards": 10,
        "maximum_submissions": 1,
        "optimization_calls": 0,
        "training_runs": 0,
        "scheduler": {
            "nodes": 1,
            "tasks": 1,
            "physical_cores": 4,
            "gpus": 1,
            "memory_mib": 65536,
            "wall_seconds": 3600,
        },
        "child_deadline_seconds": 3540,
        "memory": roots.isolated.memory.POLICY,
        "automatic_retry": False,
        "resource_budget_approved": False,
        "main_comparison_admitted": False,
        "scientific_reporting_eligible": False,
    }


def load(stage):
    frozen = parsed(stage / "plan.json")
    require(frozen == plan(roots.head()), "installed_plan_or_source_changed")
    require(
        stage.resolve() == BASE / ("guidance-" + frozen["source_commit"][:12]), "stage"
    )
    require(not (ROOT / "gurobi.env").exists(), "unexpected_parameter_file")
    return frozen


def approved(stage, frozen):
    require(
        parsed(stage / "approval.json")
        == {
            "plan_sha256": digest(encoded(frozen)),
            "explicit_user_authorization": True,
            "maximum_forwards": 10,
            "maximum_submissions": 1,
            "optimization_calls": 0,
            "training_runs": 0,
            "automatic_retry": False,
        },
        "approval",
    )


def prepare(stage):
    roots.accounting.host()
    frozen = plan(roots.head())
    require(
        stage.resolve() == BASE / ("guidance-" + frozen["source_commit"][:12]), "stage"
    )
    review.review(read(ROOT_STAGE / "public_return.json"))
    return {
        "plan_sha256": write(stage / "plan.json", frozen),
        "resource_budget_approved": False,
    }


def submit(stage, sha):
    roots.accounting.host()
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "environment")
    load(stage)
    require(digest(read(stage / "plan.json")) == sha, "approved_plan_hash")
    review.review(read(ROOT_STAGE / "public_return.json"))
    claim = BASE / "prospective-guidance-preparation.claim"
    claim.mkdir(exist_ok=False)
    write(claim / "claim.json", {"plan_sha256": sha})
    write(
        stage / "approval.json",
        {
            "plan_sha256": sha,
            "explicit_user_authorization": True,
            "maximum_forwards": 10,
            "maximum_submissions": 1,
            "optimization_calls": 0,
            "training_runs": 0,
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
    response = roots.accounting.command(
        [
            "sbatch",
            "--parsable",
            "--partition=batch",
            "--nodes=1-1",
            "--ntasks=1",
            "--cpus-per-task=4",
            "--hint=nomultithread",
            "--mem=64G",
            "--gres=gpu:1",
            "--time=01:00:00",
            "--no-requeue",
            "--job-name=cfl_pr86_guidance",
            "--chdir=" + str(ROOT),
            "--output=" + str(stage / "job-%j.private.out"),
            "--error=" + str(stage / "job-%j.private.err"),
            str(ROOT / "scripts/evidence/operate_pr86_guidance.sh"),
            "batch",
        ],
        timeout=30,
        env=env,
    )
    job = response.strip().split(";")[0]
    require(re.fullmatch(r"[0-9]+", job), "ambiguous_submission_preserve_claim")
    write(stage / "submission.json", {"job_id": job, "plan_sha256": sha})
    return {"job_id": job, "automatic_retry": False}


def allocation():
    roots.accounting.host()
    for k, v in {
        "CONDA_DEFAULT_ENV": "tfm_env",
        "SLURM_JOB_NUM_NODES": "1",
        "SLURM_CPUS_PER_TASK": "4",
        "SLURM_MEM_PER_NODE": "65536",
    }.items():
        require(os.environ.get(k) == v, "allocation_" + k)
    require(os.environ.get("SLURM_RESTART_COUNT", "0") == "0", "requeue")
    job = os.environ.get("SLURM_JOB_ID", "")
    require(re.fullmatch(r"[0-9]+", job), "job")

    def topology(cpu):
        p = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        return tuple(
            int((p / n).read_text()) for n in ("physical_package_id", "core_id")
        )

    mask = roots.isolated.physical_mask(os.sched_getaffinity(0), topology, required=4)
    os.sched_setaffinity(0, mask)
    require(set(os.sched_getaffinity(0)) == set(mask), "affinity")
    gate = roots.isolated.memory.MemoryGate(job)
    roots.isolated.memory.validate_public(gate.public())
    require(
        gate.sample() < roots.isolated.memory.POLICY["cgroup_interrupt_bytes"], "memory"
    )
    return job, gate


def root_input(index, target):
    source = ROOT_STAGE / "run" / str(index) / "root.private.json.gz"
    require(
        not source.is_symlink() and roots.sha256_file(source) == target["root_sha256"],
        "root_hash",
    )
    root = historical.legacy.numeric.bounded_json_gzip(source)
    for key in (
        "variable_count",
        "variable_order_sha256",
        "vector_sha256",
        "mathematical_signature_sha256",
    ):
        require(root[key] == target[key], "root_" + key)
    require(root["source_mip_sha256"] == target["model_sha256"], "root_model")
    require(root["effective_objective_sense"] == "MINIMIZE", "root_sense")
    require(
        root["capture_method"] == "first_optimal_root_gurobi_mipnode", "root_policy"
    )
    require(
        roots.canonical_sha256(root["variable_names"]) == root["variable_order_sha256"],
        "root_order",
    )
    require(
        roots.canonical_sha256(root["relaxation_vector"]) == root["vector_sha256"],
        "root_vector",
    )
    roots._finite_vector(
        root["relaxation_vector"], expected=target["variable_count"], field="root"
    )
    return root


def shared_model(reader, frozen, device):
    import torch

    from cfl_gnn.models.versioning import model_class

    training, checkpoint, _, binding = historical.legacy.discover_model(reader, "mixed")
    require(binding == frozen["frozen_model"], "frozen_model")
    train = {
        r["parent_instance_id"] for r in training["records"] if r["role"] == "train"
    }
    require(
        not train.intersection(p["parent"] for p in frozen["parents"]),
        "training_overlap",
    )
    with checkpoint.open("rb") as stream:
        import hashlib

        hasher = hashlib.sha256()
        for block in iter(lambda: stream.read(1024**2), b""):
            hasher.update(block)
        require(hasher.hexdigest() == binding["checkpoint_sha256"], "checkpoint_hash")
        stream.seek(0)
        state = torch.load(stream, map_location="cpu", weights_only=True)
    arch = binding["architecture"]
    model = model_class(arch["model_version"])(
        var_in_dim=7,
        cons_in_dim=5,
        edge_dim=1,
        hidden_dim=int(arch["hidden_dim"]),
        num_layers=int(arch["num_layers"]),
    )
    model.load_state_dict(
        {k.removeprefix("module."): v for k, v in state.items()}, strict=True
    )
    model.to(device).eval()
    torch.cuda.synchronize()
    return model


def one_parent(
    index, target, frozen, reader, paths, selected, private, model, device, folder
):
    import torch
    from pr86_native_model import NativeModel

    from cfl_gnn.experiments.pr58_guidance import (
        class_aware_gnn_assignments,
        matched_root_lp_assignments,
    )
    from cfl_gnn.graph.gurobi_graph_artifact import build_graph_artifact

    numeric = historical.legacy.numeric
    parent = target["parent"]
    record = selected[parent]
    timings = {}
    started = time.perf_counter()
    root = root_input(index, target)
    mip = Path(private[index]["mip_path"])
    require(private[index]["parent"] == parent, "private_parent")
    reader.verify(mip, target["model_sha256"])
    # Explicit no-optimize native inspection before production graph encoding.
    native = NativeModel(mip, "gurobi", 600)
    try:
        require(
            roots.mathematical_signature(native.model)
            == target["mathematical_signature_sha256"],
            "mathematical_identity",
        )
        binary = {v.VarName for v in native.model.getVars() if v.VType == "B"}
    finally:
        native.close()
    label = paths[record["label"]["artifact_id"]]
    reader.verify(label, record["label"]["sha256"])
    fold, role = numeric.split_for(parent)
    require(role == record["role"] == "test", "role")
    graph_path = folder / "graph.private.pt"
    require(not graph_path.exists(), "preserve_graph")
    graph_receipt = build_graph_artifact(
        mip_path=mip,
        mip_sha256=target["model_sha256"],
        solution_path=label,
        solution_sha256=record["label"]["sha256"],
        root_payload=root,
        output_path=graph_path,
        sample_metadata={
            "sample_id": parent,
            "source_instance_id": parent,
            "difficulty": parent.split("_")[1],
            "category": "original",
            "fold": fold,
            "role": "test",
            "sampling_strategy": "original",
            "label_source_solver": "gurobi",
        },
    )
    graph, _ = numeric.load_graph(graph_path, graph_receipt["graph_sha256"])
    names = root["variable_names"]
    require(len(names) == graph["variable"].x.shape[0], "graph_identity")
    require(
        torch.equal(
            graph["variable"].x[:, 6],
            torch.tensor(root["relaxation_vector"], dtype=torch.float32),
        ),
        "root_feature",
    )
    # Targets are never inspected for inference/selection. Labels were used only
    # by the production encoder's independent feasibility audit above.
    mask = graph["variable"].is_discrete.bool()
    indices = torch.where(mask)[0].tolist()
    require({names[i] for i in indices} == binary, "binary_identity")
    timings["features"] = time.perf_counter() - started
    started = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    graph = graph.to(device)
    mask = mask.to(device)
    edge = graph["variable", "rev_coef", "constraint"]
    torch.cuda.synchronize()
    write(folder / "forward.intent.json", {"parent": parent, "maximum_forwards": 1})
    forward_started = time.perf_counter()
    with torch.no_grad():
        logits = model(
            x_var=graph["variable"].x,
            x_cons=graph["constraint"].x,
            edge_v2c=edge.edge_index,
            binary_mask=mask,
            edge_attr=edge.edge_attr,
        )
        probabilities = torch.sigmoid(logits)
    torch.cuda.synchronize()
    forward_seconds = time.perf_counter() - forward_started
    require(
        logits.numel() == len(indices) and bool(torch.isfinite(logits).all()),
        "forward_shape",
    )
    scores = probabilities.cpu().tolist()
    predictions = [
        {
            "variable_name": names[i],
            "probability": p,
            "predicted_value": int(p >= frozen["frozen_model"]["threshold"]),
        }
        for i, p in zip(indices, scores)
    ]
    timings["inference"] = time.perf_counter() - started
    started = time.perf_counter()
    gnn = class_aware_gnn_assignments(predictions, fraction=0.1, absolute_cap=20000)
    timings["assembly_gnn"] = time.perf_counter() - started
    started = time.perf_counter()
    lp = matched_root_lp_assignments(
        [names[i] for i in indices],
        [root["relaxation_vector"][i] for i in indices],
        support=gnn["selected_support"],
        positive_assignments=gnn["positive_assignments"],
    )
    timings["assembly_lp"] = time.perf_counter() - started
    started = time.perf_counter()
    prediction_sha = write(
        folder / "predictions.private.json",
        {
            "predictions": predictions,
            "checkpoint_sha256": frozen["frozen_model"]["checkpoint_sha256"],
            "parent": parent,
        },
    )
    starts_sha = write(folder / "starts.private.json", {"gnn": gnn, "root_lp": lp})
    timings["private_export"] = time.perf_counter() - started
    result = {
        "parent": parent,
        "model_sha256": target["model_sha256"],
        "root_sha256": target["root_sha256"],
        "graph_sha256": graph_receipt["graph_sha256"],
        "prediction_sha256": prediction_sha,
        "private_starts_sha256": starts_sha,
        "M1_assignment_sha256": lp["assignment_sha256"],
        "M2_assignment_sha256": gnn["assignment_sha256"],
        "checkpoint_sha256": frozen["frozen_model"]["checkpoint_sha256"],
        "binary_variables": len(indices),
        "selected_support": gnn["selected_support"],
        "positive_assignments": gnn["positive_assignments"],
        "abstained": gnn["abstained"],
        "effective_objective_sense": "MINIMIZE",
        "regions_seconds": timings,
        "forward_seconds_nested_in_inference": forward_seconds,
        "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "gpu_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "forward_calls": 1,
        "optimization_calls": 0,
        "training_runs": 0,
        "scientific_reporting_eligible": False,
    }
    write(folder / "result.json", result)
    return result


def child(stage):
    frozen = load(stage)
    approved(stage, frozen)
    job, _ = allocation()
    folder = stage / "run"
    started = time.perf_counter()
    result = {
        "job_id": job,
        "rows": [],
        "complete": False,
        "failure_type": None,
        "shared_setup_seconds": None,
        "child_observed_wall_seconds": None,
        "runtime": None,
        "scientific_reporting_eligible": False,
    }
    try:
        import torch

        require(torch.cuda.is_available() and torch.cuda.device_count() == 1, "one_gpu")
        require(torch.cuda.get_device_capability(0) == (7, 0), "V100_capability")
        torch.manual_seed(42)
        torch.cuda.manual_seed_all(42)
        torch.set_num_threads(1)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.backends.cuda.matmul.allow_tf32 = False
        result["runtime"] = {
            "packages": sprint_c_runtime.observe(),
            "gpu_name": torch.cuda.get_device_name(0),
            "torch_cuda_build": torch.version.cuda,
            "bitwise_reproducibility_claimed": False,
        }
        require(
            result["runtime"]["packages"]["packages"]["gurobipy"] == "13.0.1",
            "gurobi_version",
        )
        reader = historical.legacy.Reader(DATA, seconds=3500, max_bytes=16 * 1024**3)
        reader.scan()
        paths = {
            digest(p.relative_to(reader.root).as_posix().encode()): p
            for p in reader.files
        }
        selected = historical.legacy.numeric.selected_parents(
            historical.legacy.numeric.source_receipt()
        )
        private = roots.inputs(
            {
                "parents": [
                    {"parent": p["parent"], "model_sha256": p["model_sha256"]}
                    for p in frozen["parents"]
                ]
            }
        )
        device = torch.device("cuda:0")
        model = shared_model(reader, frozen, device)
        result["shared_setup_seconds"] = time.perf_counter() - started
        for index, target in enumerate(frozen["parents"]):
            attempt = folder / str(index)
            attempt.mkdir(exist_ok=False)
            row = one_parent(
                index,
                target,
                frozen,
                reader,
                paths,
                selected,
                private,
                model,
                device,
                attempt,
            )
            result["rows"].append(row)
            torch.cuda.empty_cache()
        result["complete"] = True
    except Exception as error:
        result["failure_type"] = type(error).__name__
        raise
    finally:
        result["child_observed_wall_seconds"] = time.perf_counter() - started
        write(folder / "child.json", result)


def run(stage):
    frozen = load(stage)
    approved(stage, frozen)
    job, gate = allocation()
    folder = stage / "run"
    folder.mkdir(exist_ok=False)
    write(folder / "batch.started.json", {"job_id": job})
    observed = roots.isolated.memory.supervise(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "child",
            "--stage",
            str(stage),
        ],
        folder / "console.private.log",
        frozen["child_deadline_seconds"],
        gate,
    )
    write(folder / "supervision.json", observed)
    return (
        0 if observed["guard_stop"] is None and observed["child_exit_code"] == 0 else 2
    )


def collect(stage):
    frozen = load(stage)
    state = roots.status(stage)
    require(state["terminal"], "not_terminal_no_wait")
    folder = stage / "run"
    child_result = (
        parsed(folder / "child.json") if (folder / "child.json").is_file() else None
    )
    supervision = (
        parsed(folder / "supervision.json")
        if (folder / "supervision.json").is_file()
        else None
    )
    if child_result:
        require(child_result["job_id"] == state["job_id"], "job_identity")
        for i, row in enumerate(child_result["rows"]):
            attempt = folder / str(i)
            require(row == parsed(attempt / "result.json"), "result_changed")
            for filename, key in (
                ("graph.private.pt", "graph_sha256"),
                ("predictions.private.json", "prediction_sha256"),
                ("starts.private.json", "private_starts_sha256"),
            ):
                require(
                    roots.sha256_file(attempt / filename) == row[key],
                    "private_artifact_changed",
                )
    value = {
        "protocol_id": PROTOCOL,
        "plan": frozen,
        "plan_sha256": digest(encoded(frozen)),
        "accounting": state,
        "child": child_result,
        "supervision": supervision,
        "private_log": roots.isolated.logs.seal_closed_log(
            folder / "console.private.log"
        )
        if (folder / "console.private.log").is_file()
        else None,
        "raw_logs_included": False,
        "raw_predictions_included": False,
        "scientific_reporting_eligible": False,
    }
    ready = validate_return(encoded(value))["ready"]
    path = stage / "public_return.json"
    if path.exists():
        require(read(path) == encoded(value), "preserve_prior_collection")
    else:
        write(path, value)
    return {
        "return_sha256": digest(read(path)),
        "ready_for_independent_review": ready,
        "output": str(path),
    }


def validate_return(raw):
    value = roots.isolated.existing.review.flow.meta.strict_json(raw)
    require(
        set(value)
        == {
            "protocol_id",
            "plan",
            "plan_sha256",
            "accounting",
            "child",
            "supervision",
            "private_log",
            "raw_logs_included",
            "raw_predictions_included",
            "scientific_reporting_eligible",
        },
        "public_schema",
    )
    require(value["protocol_id"] == PROTOCOL, "protocol")
    frozen = value["plan"]
    require(frozen == plan(frozen["source_commit"]), "source_plan")
    require(value["plan_sha256"] == digest(encoded(frozen)), "plan_hash")
    for key in (
        "raw_logs_included",
        "raw_predictions_included",
        "scientific_reporting_eligible",
    ):
        require(value[key] is False, "public_scope")
    if value["private_log"] is not None:
        roots.validate_log(value["private_log"])
    accounting = value["accounting"]
    text = "\n".join(
        "|".join(str(r[k]) for k in roots.accounting.FIELDS.split(","))
        for r in accounting["rows"]
    )
    require(
        roots.accounting.parse_accounting(text, accounting["job_id"]) == accounting
        and accounting["terminal"],
        "accounting",
    )
    child_result, supervision = value["child"], value["supervision"]
    if supervision is not None:
        require(
            set(supervision)
            == {
                "guard_stop",
                "child_exit_code",
                "memory_failure_diagnostic",
                "peak_is_sampled_not_exact",
                "sampled_cgroup_peak_bytes",
                "supervisor_wall_seconds",
            },
            "supervision_schema",
        )
        require(type(supervision["child_exit_code"]) is int, "exit_type")
        require(supervision["peak_is_sampled_not_exact"] is True, "sampled_peak")
        peak = supervision["sampled_cgroup_peak_bytes"]
        require(type(peak) is int and peak >= 0, "sampled_peak")
        roots.isolated.costs.seconds(supervision["supervisor_wall_seconds"])
        roots.isolated.memory.validate_diagnostic(
            supervision["memory_failure_diagnostic"], supervision["guard_stop"]
        )
    complete = False
    if child_result is not None:
        require(
            set(child_result)
            == {
                "job_id",
                "rows",
                "complete",
                "failure_type",
                "shared_setup_seconds",
                "child_observed_wall_seconds",
                "runtime",
                "scientific_reporting_eligible",
            },
            "child_schema",
        )
        require(
            child_result["job_id"] == accounting["job_id"]
            and child_result["scientific_reporting_eligible"] is False,
            "child_identity",
        )
        require(len(child_result["rows"]) <= 10, "rows")
        failure = child_result["failure_type"]
        require(
            failure is None
            or (
                isinstance(failure, str)
                and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", failure)
            ),
            "failure_type",
        )
        total = 0.0
        for i, row in enumerate(child_result["rows"]):
            require(
                set(row)
                == {
                    "parent",
                    "model_sha256",
                    "root_sha256",
                    "graph_sha256",
                    "prediction_sha256",
                    "private_starts_sha256",
                    "M1_assignment_sha256",
                    "M2_assignment_sha256",
                    "checkpoint_sha256",
                    "binary_variables",
                    "selected_support",
                    "positive_assignments",
                    "abstained",
                    "effective_objective_sense",
                    "regions_seconds",
                    "forward_seconds_nested_in_inference",
                    "gpu_peak_allocated_bytes",
                    "gpu_peak_reserved_bytes",
                    "forward_calls",
                    "optimization_calls",
                    "training_runs",
                    "scientific_reporting_eligible",
                },
                "row_schema",
            )
            target = frozen["parents"][i]
            for key in ("parent", "model_sha256", "root_sha256"):
                require(row[key] == target[key], "parent_binding")
            for key in (
                "graph_sha256",
                "prediction_sha256",
                "private_starts_sha256",
                "M1_assignment_sha256",
                "M2_assignment_sha256",
            ):
                require(re.fullmatch(r"[0-9a-f]{64}", row[key]), "artifact_hash")
            require(
                row["checkpoint_sha256"] == frozen["frozen_model"]["checkpoint_sha256"],
                "checkpoint",
            )
            require(row["effective_objective_sense"] == "MINIMIZE", "sense")
            for key, expected in (
                ("forward_calls", 1),
                ("optimization_calls", 0),
                ("training_runs", 0),
            ):
                require(type(row[key]) is int and row[key] == expected, "calls")
            require(row["scientific_reporting_eligible"] is False, "eligibility")
            require(type(row["abstained"]) is bool, "abstention")
            n, k, pos = (
                row[x]
                for x in (
                    "binary_variables",
                    "selected_support",
                    "positive_assignments",
                )
            )
            require(
                all(type(x) is int for x in (n, k, pos))
                and n > 0
                and 0 <= pos <= k <= n,
                "support",
            )
            require(
                k == (0 if row["abstained"] else min(20000, max(1, n // 10))),
                "support_rule",
            )
            require(set(row["regions_seconds"]) == set(REGIONS), "regions")
            total += sum(
                roots.isolated.costs.seconds(v) for v in row["regions_seconds"].values()
            )
            forward = roots.isolated.costs.seconds(
                row["forward_seconds_nested_in_inference"]
            )
            require(forward <= row["regions_seconds"]["inference"], "nested_forward")
            for key in ("gpu_peak_allocated_bytes", "gpu_peak_reserved_bytes"):
                require(type(row[key]) is int and row[key] >= 0, "gpu_peak")
        complete = (
            len(child_result["rows"]) == 10 and child_result["failure_type"] is None
        )
        require(child_result["complete"] is complete, "completion")
        wall = roots.isolated.costs.seconds(child_result["child_observed_wall_seconds"])
        if child_result["shared_setup_seconds"] is not None:
            require(
                total
                + roots.isolated.costs.seconds(child_result["shared_setup_seconds"])
                <= wall + 1e-6,
                "disjoint_costs",
            )
    ready = bool(
        complete
        and supervision
        and supervision["guard_stop"] is None
        and supervision["child_exit_code"] == 0
        and accounting["state"] == "COMPLETED"
        and all(r["ExitCode"] == "0:0" for r in accounting["rows"])
    )
    return {"ready": ready, "value": value}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("prepare", "submit", "status", "collect", "run", "child", "review"),
    )
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.action == "review":
        raw = read(args.receipt)
        result = validate_return(raw)
        print(
            json.dumps(
                {
                    "return_sha256": digest(raw),
                    "ready_for_independent_review": result["ready"],
                }
            )
        )
        return 0
    require(args.stage is not None, "stage")
    if args.action == "run":
        return run(args.stage)
    if args.action == "child":
        child(args.stage)
        return 0
    value = (
        submit(args.stage, args.approved_plan_sha256)
        if args.action == "submit"
        else roots.status(args.stage)
        if args.action == "status"
        else collect(args.stage)
        if args.action == "collect"
        else prepare(args.stage)
    )
    print(json.dumps(value, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
