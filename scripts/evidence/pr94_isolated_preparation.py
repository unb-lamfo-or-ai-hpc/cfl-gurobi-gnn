"""Isolated PR94 root/graph/Start preparation; no evaluation dispatch or retries."""

import argparse
import datetime as dt
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

from plan_pr94_preparation import CHECKPOINT, PARENTS, ROOT_PARAMETERS, compile_plan

THRESHOLD = 0.9991843104362488
SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE / "src"))
EVIDENCE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence")
DATA = EVIDENCE.parent
GIB = 1024**3
VERSIONS = {
    "python": "3.10.20",
    "gurobipy": "13.0.1",
    "numpy": "1.26.4",
    "torch": "2.1.2+cu121",
    "torch-geometric": "2.7.0",
}
TERMINAL = {
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


def need(value, code):
    if not value:
        raise ValueError(code)


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def canonical_sha(value):
    # Same canonical assignment/root form as gurobi_graph_artifact.
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def stream_sha(stream):
    h = hashlib.sha256()
    for raw in iter(lambda: stream.read(1024**2), b""):
        h.update(raw)
    return h.hexdigest()


def file_sha(path):
    with Path(path).open("rb") as stream:
        return stream_sha(stream)


def read(path, maximum=4 * 1024**2):
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    need(len(raw) <= maximum, "metadata_size")

    def unique(pairs):
        value = {}
        for k, v in pairs:
            need(k not in value, "duplicate_key")
            value[k] = v
        return value

    def nonfinite(_):
        raise ValueError("nonfinite_JSON")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def sync(stream):
    stream.flush()
    os.fsync(stream.fileno())


def write_once(path, value):
    raw = encoded(value)
    with Path(path).open("xb") as stream:
        stream.write(raw)
        sync(stream)
    return hashlib.sha256(raw).hexdigest()


def safe_file(path, root=None):
    root = DATA if root is None else root
    p = Path(path)
    need(not p.is_symlink(), "symlink_input")
    resolved = p.resolve(strict=True)
    need(
        resolved.is_file() and resolved.is_relative_to(root.resolve(strict=True)),
        "private_path",
    )
    return resolved


def command(args, **kwargs):
    return subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        timeout=kwargs.pop("timeout", 30),
        **kwargs,
    ).stdout.strip()


def source_snapshot(root=SOURCE):
    need(not command(["git", "-C", str(root), "status", "--porcelain"]), "dirty_source")
    commit = command(["git", "-C", str(root), "rev-parse", "HEAD"])
    need(re.fullmatch("[0-9a-f]{40}", commit), "source_commit")
    paths = command(["git", "-C", str(root), "ls-files", "-z"]).split("\0")
    selected = [
        p
        for p in paths
        if p
        and (
            p.startswith(("src/", "scripts/evidence/"))
            or p.startswith(("configs/", "docs/research/solver-seed-extension-v1/"))
            or p.startswith("docs/evidence/pr78/")
            and p.endswith((".py", ".json"))
            or p == ".gitattributes"
        )
    ]
    hashes = {}
    for name in selected:
        p = root / name
        need(not p.is_symlink() and p.is_file(), "source_file")
        # Git attributes may affect newlines in unbound Python/config source.
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        hashes[name] = hashlib.sha256(raw).hexdigest()
    need(
        "scripts/evidence/pr94_isolated_preparation.py" in hashes
        and "scripts/evidence/pr94_preparation_science.py" in hashes,
        "adapter_source",
    )
    return {"commit": commit, "sha256_lf": hashes}


def host():
    import pwd

    need(socket.gethostname().split(".")[0] == "dgx-dasci", "host")
    need(pwd.getpwuid(os.getuid()).pw_name == "vrcelestino", "user")
    need(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "environment")


def versions():
    value = {"python": ".".join(map(str, sys.version_info[:3]))}
    for name in VERSIONS:
        if name != "python":
            value[name] = importlib.metadata.version(name)
    need(value == VERSIONS, "recorded_environment_differs_do_not_upgrade")
    value["feature_imports"] = {
        name: importlib.metadata.version(name)
        for name in ("pandas", "pyarrow", "scipy", "tqdm", "packaging")
    }
    return value


def stage_path(stage, commit=None):
    p = Path(stage).resolve(strict=True)
    need(p.parent == EVIDENCE.resolve(strict=True), "stage_parent")
    need(re.fullmatch("pr94-preparation-[0-9a-f]{12}", p.name), "stage_name")
    need(SOURCE.resolve() == p / "source", "isolated_source")
    if commit:
        need(p.name == "pr94-preparation-" + commit[:12], "stage_commit")
    return p


def storage(stage, admission=False):
    # Source checkout included in workspace accounting; no traversal into input data.
    need(shutil.disk_usage(stage).free >= (80 if admission else 16) * GIB, "free_space")
    total, count = sum(p.stat().st_size for p in stage.iterdir() if p.is_file()), 0
    for parent in (stage / "run", stage / "claims", stage / "runtime"):
        if not parent.exists():
            continue
        for p in parent.rglob("*"):
            count += 1
            need(count <= 2048 and not p.is_symlink(), "working_tree")
            if p.is_file():
                total += p.stat().st_size
    baseline = (
        read(stage / "plan.json").get("source_bytes", 0)
        if (stage / "plan.json").exists()
        else 0
    )
    need(total + baseline <= 64 * GIB, "working_storage")
    return {"working_bytes_observed": total + baseline, "free_space_checked": True}


def private_inputs(config, parents, checkpoint_required=True):
    need(set(config) == {"parents", "checkpoint_path"}, "private_config_schema")
    need(set(config["parents"]) == set(PARENTS), "private_parent_set")
    expected = {r["parent"]: r["model_sha256"] for r in parents}
    resolved = {}
    for parent in PARENTS:
        path = safe_file(config["parents"][parent])
        need(file_sha(path) == expected[parent], "model_hash")
        resolved[parent] = path
    checkpoint = safe_file(config["checkpoint_path"]) if checkpoint_required else None
    if checkpoint_required:
        need(file_sha(checkpoint) == CHECKPOINT, "checkpoint_hash")
    return resolved, checkpoint


REPORT_SHA = "974236918746711d044e2c0111a1e145d9487b27e20e7953cda6b63058ef3822"


def find_checkpoint(data=DATA, seconds=120, entries_limit=20000):
    """Locate only the already-selected report/checkpoint; never load tensors."""
    data = Path(data).resolve(strict=True)
    started, entries, bytes_read = time.monotonic(), 0, 0
    found = {}
    for suffix in ("models", "analysis"):
        for base in (data / suffix, data / "cfl-gurobi-gnn/data" / suffix):
            if not base.is_dir() or base.is_symlink():
                continue
            for folder, dirs, files in os.walk(base, followlinks=False):
                need(time.monotonic() - started <= seconds, "checkpoint_lookup_time")
                relative = Path(folder).relative_to(base)
                dirs[:] = sorted(
                    name
                    for name in dirs
                    if name not in {"secrets", ".git", "__pycache__"}
                    and not (Path(folder) / name).is_symlink()
                    and len(relative.parts) < 8
                )
                entries += len(dirs) + len(files)
                need(entries <= entries_limit, "checkpoint_lookup_entries")
                if "gasse_training_report.json" not in files:
                    continue
                report_path = safe_file(
                    Path(folder) / "gasse_training_report.json", data
                )
                need(report_path.stat().st_size <= 4 * 1024**2, "training_report_size")
                raw = report_path.read_bytes()
                bytes_read += len(raw)
                need(bytes_read <= 32 * 1024**2, "training_reports_budget")
                if hashlib.sha256(raw).hexdigest() != REPORT_SHA:
                    continue
                value = read(report_path)
                descriptor = value["outputs"]["checkpoint"]
                need(descriptor["sha256"] == CHECKPOINT, "selected_report_checkpoint")
                name = descriptor["file_name"]
                need(Path(name).name == name, "checkpoint_name")
                path = safe_file(report_path.parent / name, data)
                need(path.stat().st_size <= 64 * 1024**2, "checkpoint_size")
                need(file_sha(path) == CHECKPOINT, "selected_checkpoint_bytes")
                found[str(path)] = path
    need(found, "selected_checkpoint_not_in_bounded_layouts")
    # Duplicate exact copies have identical predefined content; no metric selection.
    selected = found[sorted(found)[0]]
    return selected, {
        "report_sha256": REPORT_SHA,
        "checkpoint_sha256": CHECKPOINT,
        "matching_exact_copy_paths": len(found),
        "directory_entries_observed": entries,
        "report_bytes_read": bytes_read,
        "wall_seconds": time.monotonic() - started,
        "tensor_deserialization_calls": 0,
        "selection": "preselected_report_hash_then_exact_checkpoint_hash",
        "duplicate_copy_rule": "lexicographically_first_resolved_path_identical_bytes",
    }


def checkout_bytes(root):
    total, count = 0, 0
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            count += 1
            path = Path(folder) / name
            need(count <= 100000 and not path.is_symlink(), "source_checkout_scope")
            if path.is_file():
                total += path.stat().st_size
        need(total <= 4 * GIB, "source_checkout_bytes")
    return total


def freeze(stage, config_path):
    host()
    snapshot = source_snapshot()
    stage = stage_path(stage, snapshot["commit"])
    need(not (stage / "plan.json").exists(), "already_frozen")
    need(
        not any(
            (EVIDENCE / ("pr94-six-medium-" + kind + ".claim.json")).exists()
            for kind in ("roots", "guidance")
        ),
        "campaign_already_claimed",
    )
    storage(stage, admission=True)
    package = SOURCE / "docs/research/solver-seed-extension-v1"
    derived = compile_plan(package, SOURCE)
    parents = derived["new-artifact-bindings.json"]["parents"]
    config = read(config_path)
    private_inputs(config, parents)
    observed_environment = versions()  # Metadata only; no Gurobi/Torch import.
    private_sha = write_once(stage / "inputs.private.json", config)
    (stage / "claims").mkdir(exist_ok=False)
    (stage / "run").mkdir(exist_ok=False)
    runtime_dir = stage / "runtime"
    runtime_dir.mkdir(exist_ok=False)
    for name in ("tmp", "cache", "cuda", "torch", "extensions", "matplotlib"):
        (runtime_dir / name).mkdir(exist_ok=False)
    value = {
        "protocol_id": "pr94_isolated_preparation_v1",
        "source": snapshot,
        "environment": observed_environment,
        "package_manifest_sha256": file_sha(package / "manifest.json"),
        "preparation_contract": derived["preparation-contract.json"],
        "reservation_budget": derived["reservation-budget.json"],
        "parents": [
            {"parent": r["parent"], "model_sha256": r["model_sha256"]} for r in parents
        ],
        "private_inputs_sha256": private_sha,
        "source_bytes": checkout_bytes(SOURCE),
        "optimization_calls_maximum": 6,
        "forward_calls_maximum": 6,
        "evaluation_calls_admitted": 0,
        "automatic_retry": False,
        "scientific_reporting_eligible": False,
    }
    sha = write_once(stage / "plan.json", value)
    return {
        "plan_sha256": sha,
        "parents": 6,
        "new_scientific_calls": 0,
        "execution_submitted": False,
    }


def load(stage):
    stage = stage_path(stage)
    plan = read(stage / "plan.json")
    need(plan["protocol_id"] == "pr94_isolated_preparation_v1", "protocol")
    need(plan["source"] == source_snapshot(), "source_changed")
    stage_path(stage, plan["source"]["commit"])
    need(versions() == plan["environment"], "environment_changed")
    package = SOURCE / "docs/research/solver-seed-extension-v1"
    need(
        file_sha(package / "manifest.json") == plan["package_manifest_sha256"],
        "package_changed",
    )
    need(
        file_sha(stage / "inputs.private.json") == plan["private_inputs_sha256"],
        "private_changed",
    )
    need(not (SOURCE / "gurobi.env").exists(), "parameter_file")
    return plan


def physical_mask(cpus, topology, required):
    chosen = {}
    for cpu in sorted(cpus):
        chosen.setdefault(topology(cpu), cpu)
    need(len(chosen) >= required, "physical_core_count")
    return tuple(list(chosen.values())[:required])


def allocation(kind, stage):
    host()
    n = 1 if kind == "roots" else 4
    for key, expected in {
        "SLURM_JOB_NUM_NODES": "1",
        "SLURM_CPUS_PER_TASK": str(n),
        "SLURM_MEM_PER_NODE": "65536",
    }.items():
        need(os.environ.get(key) == expected, "allocation_" + key)
    need(os.environ.get("SLURM_RESTART_COUNT", "0") == "0", "requeue")
    job = os.environ.get("SLURM_JOB_ID", "")
    need(re.fullmatch("[0-9]+", job), "job_ID")
    batch = stage / "run" / kind / "batch.started.json"
    if batch.exists():
        need(read(batch)["job_id"] == job, "batch_job_identity")

    def topology(cpu):
        p = Path("/sys/devices/system/cpu") / ("cpu" + str(cpu)) / "topology"
        return tuple(
            int((p / x).read_text()) for x in ("physical_package_id", "core_id")
        )

    mask = physical_mask(os.sched_getaffinity(0), topology, n)
    os.sched_setaffinity(0, mask)
    need(set(os.sched_getaffinity(0)) == set(mask), "physical_affinity")
    import paired_memory_runtime_v2 as memory

    raw_gate = memory.MemoryGate(job)
    memory.validate_public(raw_gate.public())
    storage(stage, admission=True)

    class CombinedGate:
        storage_failure = None

        def sample(self):
            try:
                storage(stage)
            except ValueError as exc:
                self.storage_failure = str(exc)
                raise
            return raw_gate.sample()

    return (
        job,
        CombinedGate(),
        {"physical_cpus": list(mask), "memory": raw_gate.public()},
    )


def claim(stage, category, parent):
    need(category in {"optimize", "forward"} and parent in PARENTS, "call_claim_scope")
    return write_once(
        stage / "claims" / (category + "-" + parent + ".json"),
        {
            "parent": parent,
            "category": category,
            "maximum_calls": 1,
            "plan_sha256": file_sha(stage / "plan.json"),
        },
    )


def validate_starts(g, r, n):
    need(
        type(g["abstained"]) is bool and r["abstained"] == g["abstained"], "abstention"
    )
    expected = 0 if g["abstained"] else min(n, 20000, max(1, n // 10))
    for value in (g, r):
        rows = value["assignments"]
        need(
            value["binary_variables"] == n
            and value["selected_support"] == len(rows) == expected,
            "Start_support",
        )
        need(len({x["variable_name"] for x in rows}) == len(rows), "Start_unique")
        need(
            all(type(x["value"]) is int and x["value"] in (0, 1) for x in rows),
            "Start_values",
        )
        need(
            sum(x["value"] for x in rows) == value["positive_assignments"],
            "Start_positive",
        )
        need(canonical_sha(rows) == value["assignment_sha256"], "Start_hash")
    need(g["positive_assignments"] == r["positive_assignments"], "Start_matched")
    need(g["abstained"] or g["positive_assignments"] > 0, "G_positive")


def read_root(path, target):
    need(file_sha(path) == target["root_sha256"], "root_bytes")
    with gzip.open(path, "rb") as stream:
        raw = stream.read(512 * 1024**2 + 1)
    need(len(raw) <= 512 * 1024**2, "root_size")
    root = json.loads(raw)
    need(root["source_mip_sha256"] == target["model_sha256"], "root_model")
    need(root["effective_objective_sense"] == "MINIMIZE", "root_sense")
    need(root["capture_method"] == "first_optimal_root_gurobi_mipnode", "root_policy")
    need(
        root["solver_parameter_map"] == {**ROOT_PARAMETERS, "ModelSense": 1},
        "root_parameters",
    )
    names, vector = root["variable_names"], root["relaxation_vector"]
    need(
        len(names) == len(set(names)) == len(vector) == root["variable_count"],
        "root_length",
    )
    need(
        all(type(v) in (float, int) and math.isfinite(v) for v in vector), "finite_root"
    )
    for key, expected in (
        ("variable_order_sha256", canonical_sha(names)),
        ("vector_sha256", canonical_sha(vector)),
        ("solver_parameter_sha256", canonical_sha(root["solver_parameter_map"])),
    ):
        need(root[key] == expected == target[key], "root_hash_binding")
    need(
        root["mathematical_signature_sha256"]
        == target["mathematical_signature_sha256"],
        "root_signature_binding",
    )
    return root


def root_child(stage, index):
    plan = load(stage)
    approval(stage, "roots", plan)
    allocation("roots", stage)
    need(type(index) is int and 0 <= index < 6, "parent_index")
    target = plan["parents"][index]
    folder = stage / "run/roots" / str(index)
    need(folder.is_dir(), "owned_folder")
    inputs, _ = private_inputs(read(stage / "inputs.private.json"), plan["parents"])
    import pr94_preparation_science as science

    started = time.perf_counter()
    root = science.capture(
        inputs[target["parent"]],
        target["model_sha256"],
        folder,
        lambda: claim(stage, "optimize", target["parent"]),
    )
    capture_seconds = time.perf_counter() - started
    started = time.perf_counter()
    with (folder / "root.private.json.gz").open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as zipped:
            zipped.write(encoded(root))
        sync(stream)
    result = {
        **target,
        "root_sha256": file_sha(folder / "root.private.json.gz"),
        **{
            k: root[k]
            for k in (
                "variable_order_sha256",
                "vector_sha256",
                "solver_parameter_sha256",
                "mathematical_signature_sha256",
                "variable_count",
            )
        },
        "capture_wall_seconds": capture_seconds,
        "root_export_wall_seconds": time.perf_counter() - started,
        "optimization_calls": 1,
        "forward_calls": 0,
        "training_calls": 0,
        "scientific_reporting_eligible": False,
    }
    write_once(folder / "result.json", result)


def reviewed_roots(stage, plan):
    review = read(stage / "roots-review.json")
    need(
        review
        == {
            "plan_sha256": file_sha(stage / "plan.json"),
            "collection_sha256": file_sha(stage / "roots-public-return.json"),
            "accepted_by_author_CLI": True,
        },
        "root_review",
    )
    receipt = read(stage / "roots-public-return.json")
    need(receipt["ready_for_review"] and receipt["kind"] == "roots", "root_receipt")
    rows = receipt["summary"]["rows"]
    need(len(rows) == 6, "roots_count")
    for row, expected in zip(rows, plan["parents"]):
        need(row["result"]["parent"] == expected["parent"], "root_parent")
        need(row["result"]["model_sha256"] == expected["model_sha256"], "root_input")
    return rows


def guidance_child(stage):
    plan = load(stage)
    approval(stage, "guidance", plan)
    job, _, _ = allocation("guidance", stage)
    rows = reviewed_roots(stage, plan)
    inputs, checkpoint = private_inputs(
        read(stage / "inputs.private.json"), plan["parents"]
    )
    import pr94_preparation_science as science
    import torch

    need(torch.cuda.is_available() and torch.cuda.device_count() == 1, "one_GPU")
    need(torch.cuda.get_device_capability(0) == (7, 0), "V100_capability")
    props = torch.cuda.get_device_properties(0)
    need("V100" in props.name and props.total_memory >= 30 * GIB, "V100_32GB")
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    torch.set_num_threads(1)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    started = time.perf_counter()
    model = science.checkpoint_model(checkpoint, torch.device("cuda:0"))
    torch.cuda.synchronize()
    shared_setup = time.perf_counter() - started
    result_rows = []
    summary = {
        "job_id": job,
        "rows": result_rows,
        "complete": False,
        "shared_setup_seconds": shared_setup,
        "GPU_name": props.name,
        "GPU_total_memory_bytes": props.total_memory,
        "torch_cuda_build": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "torch_num_threads": torch.get_num_threads(),
        "tf32_cuda_matmul": torch.backends.cuda.matmul.allow_tf32,
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "bitwise_reproducibility_claimed": False,
        "failure_type": None,
    }
    try:
        for i, (expected, row) in enumerate(zip(plan["parents"], rows)):
            folder = stage / "run/guidance" / str(i)
            folder.mkdir(exist_ok=False)
            root = read_root(
                stage / "run/roots" / str(i) / "root.private.json.gz", row["result"]
            )
            result_rows.append(
                science.guidance_one(
                    expected["parent"],
                    row["result"],
                    inputs[expected["parent"]],
                    root,
                    model,
                    torch.device("cuda:0"),
                    folder,
                    lambda p=expected["parent"]: claim(stage, "forward", p),
                )
            )
            write_once(folder / "result.json", result_rows[-1])
            torch.cuda.empty_cache()
        summary["complete"] = True
    except BaseException as exc:
        summary["failure_type"] = type(exc).__name__
        raise
    finally:
        summary["wall_seconds"] = time.perf_counter() - started
        write_once(stage / "run/guidance/child.json", summary)


def approval(stage, kind, plan):
    value = read(stage / (kind + "-approval.json"))
    need(
        value
        == {
            "plan_sha256": file_sha(stage / "plan.json"),
            "kind": kind,
            "explicit_author_CLI": True,
            "maximum_optimization_calls": 6 if kind == "roots" else 0,
            "maximum_forwards": 0 if kind == "roots" else 6,
            "automatic_retry": False,
        },
        "approval",
    )
    need(
        read(EVIDENCE / ("pr94-six-medium-" + kind + ".claim.json"))
        == {
            "plan_sha256": file_sha(stage / "plan.json"),
            "source_commit": plan["source"]["commit"],
            "kind": kind,
        },
        "campaign_claim",
    )
    return value


def run(stage, kind):
    plan = load(stage)
    approval(stage, kind, plan)
    job, gate, allocation_receipt = allocation(kind, stage)
    folder = stage / "run" / kind
    folder.mkdir(exist_ok=False)
    write_once(folder / "batch.started.json", {"job_id": job})
    import paired_memory_runtime_v2 as memory

    started = time.monotonic()
    rows, stop = [], None
    try:
        indices = range(6) if kind == "roots" else (None,)
        for index in indices:
            if kind == "roots":
                attempt = folder / str(index)
                attempt.mkdir(exist_ok=False)
                args = ["--index", str(index)]
                deadline = 1140
            else:
                attempt, args, deadline = folder, [], 3540
            observed = memory.supervise(
                [
                    sys.executable,
                    "-B",
                    str(Path(__file__).resolve()),
                    "child",
                    "--stage",
                    str(stage),
                    "--kind",
                    kind,
                    *args,
                ],
                attempt / "console.private.log",
                deadline,
                gate,
            )
            result_path = attempt / ("result.json" if kind == "roots" else "child.json")
            result = read(result_path) if result_path.exists() else None
            passed = (
                observed["guard_stop"] is None
                and observed["child_exit_code"] == 0
                and result is not None
                and (kind == "roots" or result["complete"])
            )
            row = {
                "result": result,
                "supervision": observed,
                "storage_failure": gate.storage_failure,
                "complete": passed,
            }
            write_once(attempt / "supervision.json", row)
            rows.append(row)
            if not passed:
                stop = "child_failed_no_retry"
                break
    except BaseException:
        stop = "batch_exception_no_retry"
        raise
    finally:
        write_once(
            folder / "summary.json",
            {
                "kind": kind,
                "job_id": job,
                "plan_sha256": file_sha(stage / "plan.json"),
                "rows": rows,
                "complete": stop is None and len(rows) == (6 if kind == "roots" else 1),
                "stop": stop,
                "batch_wall_seconds": time.monotonic() - started,
                "allocation": allocation_receipt,
                "scientific_reporting_eligible": False,
            },
        )
    return 0 if stop is None else 2


def held_profile(text, job, kind):
    fields = dict(x.split("=", 1) for x in text.split() if "=" in x)
    cores, wall = (1, "02:00:00") if kind == "roots" else (4, "01:00:00")
    for key, value in {
        "JobId": job,
        "JobState": "PENDING",
        "Reason": "JobHeldUser",
        "Partition": "batch",
        "Requeue": "0",
        "Restarts": "0",
        "NumTasks": "1",
        "CPUs/Task": str(cores),
        "TimeLimit": wall,
    }.items():
        need(fields.get(key) == value, "held_" + key)
    need(fields.get("NumNodes") in {"1", "1-1"}, "held_nodes")
    need(fields.get("NumCPUs") in {str(cores), str(2 * cores)}, "held_CPU")
    need(fields.get("MinMemoryNode") in {"64G", "65536M"}, "held_memory")
    tres_text = fields.get("TRES", fields.get("ReqTRES", ""))
    pairs = [part.split("=", 1) for part in tres_text.split(",")]
    need(all(len(x) == 2 for x in pairs), "held_TRES")
    tres = dict(pairs)
    need(len(tres) == len(pairs), "held_duplicate_TRES")
    need(set(tres) <= {"cpu", "mem", "node", "billing", "gres/gpu"}, "held_TRES_keys")
    need(tres.get("mem") in {"64G", "65536M"} and tres.get("node") == "1", "held_TRES")
    need(tres.get("cpu") == fields.get("NumCPUs"), "held_TRES_CPU")
    need(tres.get("gres/gpu", "0") == ("0" if kind == "roots" else "1"), "held_GPU")
    return fields


def submit(stage, kind, approved_sha):
    host()
    need(kind in {"roots", "guidance"}, "stage_kind")
    plan = load(stage)
    need(file_sha(stage / "plan.json") == approved_sha, "approved_plan_hash")
    private_inputs(read(stage / "inputs.private.json"), plan["parents"])
    storage(stage, admission=True)
    if kind == "guidance":
        reviewed_roots(stage, plan)
    claim_path = EVIDENCE / ("pr94-six-medium-" + kind + ".claim.json")
    write_once(
        claim_path,
        {
            "plan_sha256": approved_sha,
            "source_commit": plan["source"]["commit"],
            "kind": kind,
        },
    )  # Survives ambiguous sbatch replies, failures and changed source commits.
    write_once(
        stage / (kind + "-approval.json"),
        {
            "plan_sha256": approved_sha,
            "kind": kind,
            "explicit_author_CLI": True,
            "maximum_optimization_calls": 6 if kind == "roots" else 0,
            "maximum_forwards": 0 if kind == "roots" else 6,
            "automatic_retry": False,
        },
    )
    cores, wall = (1, "02:00:00") if kind == "roots" else (4, "01:00:00")
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SBATCH_", "SLURM_", "SRUN_"))
        and k not in {"PYTHONHOME", "PYTHONPATH"}
    }
    env.update(PR94_STAGE=str(stage), PR94_KIND=kind, PR94_PYTHON=sys.executable)
    args = [
        "sbatch",
        "--parsable",
        "--hold",
        "--partition=batch",
        "--nodes=1-1",
        "--ntasks=1",
        "--cpus-per-task=" + str(cores),
        "--hint=nomultithread",
        "--mem=64G",
        "--time=" + wall,
        "--no-requeue",
        "--job-name=cfl_pr94_" + kind,
        "--chdir=" + str(SOURCE),
        "--output=" + str(stage / (kind + "-%j.private.out")),
        "--error=" + str(stage / (kind + "-%j.private.err")),
    ]
    if kind == "guidance":
        args.append("--gres=gpu:1")
    response = command(
        args + [str(SOURCE / "scripts/evidence/operate_pr94_preparation.sh"), "batch"],
        env=env,
    )
    job = response.split(";")[0]
    need(re.fullmatch("[0-9]+", job), "ambiguous_submission_preserve_claim")
    write_once(
        stage / (kind + "-submission.json"),
        {"job_id": job, "plan_sha256": approved_sha},
    )
    profile = held_profile(command(["scontrol", "show", "job", job, "-o"]), job, kind)
    write_once(stage / (kind + "-held-profile.json"), profile)
    command(["scontrol", "release", job])
    return {"job_id": job, "kind": kind, "automatic_retry": False}


def parse_accounting(text, job):
    fields = [
        "JobID",
        "State",
        "ExitCode",
        "ElapsedRaw",
        "TotalCPU",
        "AllocCPUS",
        "ReqMem",
        "MaxRSS",
    ]
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) == len(fields) + 1 and parts[-1] == "":
            parts.pop()
        need(len(parts) == len(fields), "accounting_columns")
        rows.append(dict(zip(fields, parts)))
    ids = [r["JobID"] for r in rows]
    need(len(ids) == len(set(ids)), "duplicate_accounting_ID")
    need({job, job + ".batch", job + ".extern"} <= set(ids), "accounting_steps")
    need(all(r == job or r.startswith(job + ".") for r in ids), "accounting_ID")
    return {
        "job_id": job,
        "rows": rows,
        "terminal": all(r["State"].split()[0].rstrip("+") in TERMINAL for r in rows),
        "query_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def accounting(stage, kind):
    job = read(stage / (kind + "-submission.json"))["job_id"]
    need(re.fullmatch("[0-9]+", job), "job_ID")
    fields = "JobID,State,ExitCode,ElapsedRaw,TotalCPU,AllocCPUS,ReqMem,MaxRSS"
    return parse_accounting(
        command(
            [
                "sacct",
                "--noheader",
                "--parsable2",
                "-j",
                job,
                "--format=" + fields,
            ]
        ),
        job,
    )


def collect(stage, kind):
    plan = load(stage)
    state = accounting(stage, kind)
    need(state["terminal"], "not_terminal_no_polling")
    path = stage / "run" / kind / "summary.json"
    summary = read(path) if path.exists() else None
    seals = {}
    if summary:
        need(summary["job_id"] == state["job_id"], "summary_job")
        need(summary["plan_sha256"] == file_sha(stage / "plan.json"), "summary_plan")
        files = sorted((stage / "run" / kind).rglob("*"))
        for p in files:
            if p.is_file():
                need(not p.is_symlink(), "artifact_symlink")
                relative = p.relative_to(stage).as_posix()
                seals[relative] = {"sha256": file_sha(p), "bytes": p.stat().st_size}
        if kind == "roots":
            for i, row in enumerate(summary["rows"]):
                if row["result"]:
                    result = row["result"]
                    need(
                        result["parent"] == plan["parents"][i]["parent"]
                        and result["model_sha256"]
                        == plan["parents"][i]["model_sha256"],
                        "root_result_identity",
                    )
                    need(
                        result == read(stage / "run/roots" / str(i) / "result.json"),
                        "result_changed",
                    )
                    need(
                        file_sha(stage / "run/roots" / str(i) / "root.private.json.gz")
                        == result["root_sha256"],
                        "root_changed",
                    )
        else:
            child_path = stage / "run/guidance/child.json"
            if child_path.exists():
                child = read(child_path)
                need(summary["rows"][0]["result"] == child, "child_changed")
                for i, row in enumerate(child["rows"]):
                    need(
                        row == read(stage / "run/guidance" / str(i) / "result.json"),
                        "result_changed",
                    )
                    for name, key in (
                        ("graph.private.pt", "graph_sha256"),
                        ("predictions.private.json", "prediction_sha256"),
                        ("starts.private.json", "private_starts_sha256"),
                    ):
                        need(
                            file_sha(stage / "run/guidance" / str(i) / name)
                            == row[key],
                            "guidance_changed",
                        )
    ready = bool(
        summary
        and summary["complete"]
        and all(
            r["State"] == "COMPLETED" and r["ExitCode"] == "0:0" for r in state["rows"]
        )
    )
    category = "optimize" if kind == "roots" else "forward"
    intents = []
    for parent in PARENTS:
        path = stage / "claims" / (category + "-" + parent + ".json")
        if path.exists():
            record = read(path)
            need(
                record
                == {
                    "parent": parent,
                    "category": category,
                    "maximum_calls": 1,
                    "plan_sha256": file_sha(stage / "plan.json"),
                },
                "call_intent_changed",
            )
            intents.append(
                {"parent": parent, "category": category, "sha256": file_sha(path)}
            )
    value = {
        "protocol_id": plan["protocol_id"],
        "kind": kind,
        "plan_sha256": file_sha(stage / "plan.json"),
        "source_commit": plan["source"]["commit"],
        "parents": plan["parents"],
        "environment": plan["environment"],
        "accounting": state,
        "summary": summary,
        "closed_artifact_seals": seals,
        "durable_call_intents": intents,
        "intent_is_not_proof_of_completed_call": True,
        "ready_for_review": ready,
        "raw_artifacts_included": False,
        "private_paths_included": False,
        "scientific_reporting_eligible": False,
    }
    output = stage / (kind + "-public-return.json")
    need(not output.exists(), "collection_already_preserved")
    write_once(output, value)
    return export_metadata(stage, {output.name: output.read_bytes()})


def export_metadata(stage, members):
    manifest = {
        "sha256": {k: hashlib.sha256(v).hexdigest() for k, v in members.items()}
    }
    out = stage / ("pr94-metadata-" + uuid.uuid4().hex + ".zip")
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
        archive.writestr("manifest.json", encoded(manifest))
    return {
        "ARQUIVO_HPC": str(out),
        "SHA256": file_sha(out),
        "BYTES_ZIP": out.stat().st_size,
    }


def inspect(stage):
    plan = load(stage)
    private_inputs(read(stage / "inputs.private.json"), plan["parents"])
    space = storage(stage, admission=True)
    value = {
        "protocol_id": plan["protocol_id"],
        "source_commit": plan["source"]["commit"],
        "plan_sha256": file_sha(stage / "plan.json"),
        "environment": plan["environment"],
        "parents": plan["parents"],
        "reservation_budget": plan["reservation_budget"],
        "source_files_bound": len(plan["source"]["sha256_lf"]),
        "storage": space,
        "optimization_calls_added": 0,
        "inference_calls_added": 0,
        "training_calls_added": 0,
        "raw_paths_included": False,
        "execution_submitted": False,
    }
    return export_metadata(stage, {"installation-preflight.json": encoded(value)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "freeze",
            "inspect",
            "submit",
            "run",
            "child",
            "status",
            "collect",
            "review-roots",
        ),
    )
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--kind", choices=("roots", "guidance"), default="roots")
    parser.add_argument("--index", type=int)
    parser.add_argument("--private-config", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--accepted-root-return-sha256")
    args = parser.parse_args()
    stage = args.stage
    if args.action == "freeze":
        need(args.private_config is not None, "private_config_required")
        result = freeze(stage, args.private_config)
    elif args.action == "inspect":
        result = inspect(stage)
    elif args.action == "submit":
        result = submit(stage, args.kind, args.approved_plan_sha256)
    elif args.action == "run":
        return run(stage, args.kind)
    elif args.action == "child":
        plan = load(stage)
        approval(stage, args.kind, plan)
        if args.kind == "roots":
            root_child(stage, args.index)
        else:
            guidance_child(stage)
        return 0
    elif args.action == "review-roots":
        load(stage)
        need(
            file_sha(stage / "roots-public-return.json")
            == args.accepted_root_return_sha256,
            "accepted_return_hash",
        )
        value = read(stage / "roots-public-return.json")
        need(value["ready_for_review"], "root_review_incomplete")
        result = {
            "review_sha256": write_once(
                stage / "roots-review.json",
                {
                    "plan_sha256": file_sha(stage / "plan.json"),
                    "collection_sha256": args.accepted_root_return_sha256,
                    "accepted_by_author_CLI": True,
                },
            )
        }
    else:
        load(stage)
        result = (
            accounting(stage, args.kind)
            if args.action == "status"
            else collect(stage, args.kind)
        )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        # Preserve all claims, partial files and held jobs. Never retry/delete/cancel.
        raise SystemExit("PR94_ABORTED=" + type(error).__name__ + ":" + str(error))
