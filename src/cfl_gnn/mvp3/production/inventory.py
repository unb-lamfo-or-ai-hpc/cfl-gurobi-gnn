"""Bounded read-only Slurm discovery; never submits or cancels anything."""

import importlib.metadata
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..contract import load_json, require
from ..journal import durable_json
from . import VERSION
from .layout import DEFAULT_EXECUTION_ROOT, run_paths
from .layout import execution_root as checked_root
from .policy import candidate, slurm_pairs, token

NODE_FIELDS = {
    "NodeName",
    "CPUTot",
    "Sockets",
    "CoresPerSocket",
    "ThreadsPerCore",
    "RealMemory",
    "AvailableFeatures",
    "ActiveFeatures",
    "Partitions",
    "State",
    "Gres",
}
PARTITION_FIELDS = {
    "PartitionName",
    "Nodes",
    "State",
    "MaxTime",
    "AllowAccounts",
    "DenyAccounts",
    "AllowQos",
    "DenyQos",
    "QoS",
    "OverSubscribe",
    "MaxMemPerCPU",
    "DefMemPerCPU",
}
CONFIG_FIELDS = {
    "ClusterName",
    "SelectType",
    "SelectTypeParameters",
    "TaskPlugin",
    "ProctrackType",
    "PreemptMode",
    "SchedulerType",
}


def read_commands(user):
    token(user)
    return {
        "version": ["scontrol", "--version"],
        "nodes": ["scontrol", "show", "nodes", "-o"],
        "partitions": ["scontrol", "show", "partitions", "-o"],
        "config": ["scontrol", "show", "config"],
        "own_jobs": ["squeue", "--noheader", "--user", user, "--format=%i|%T|%j"],
        "own_associations": [
            "sacctmgr",
            "--noheader",
            "--parsable2",
            "show",
            "assoc",
            "where",
            f"user={user}",
            "format=Cluster,Account,Partition,QOS,DefaultQOS",
        ],
    }


def bounded_read(argv, *, timeout=20, maximum_bytes=2 * 1024 * 1024):
    """Drain a bounded pipe into memory and terminate the owned reader on overflow."""
    import threading

    output = bytearray()
    overflow = threading.Event()
    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False
    )

    def drain():
        while block := process.stdout.read(65536):
            if len(output) + len(block) > maximum_bytes:
                overflow.set()
                process.kill()
                break
            output.extend(block)

    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise ValueError("Read-only command timeout") from None
    finally:
        thread.join(timeout=2)
        process.stdout.close()
    require(
        not overflow.is_set() and not thread.is_alive(),
        "Read-only command output exceeded its envelope",
    )
    require(code == 0, "Read-only command failed; preserve diagnostic status")
    return output.decode("utf-8", errors="replace")


def parse_inventory(outputs):
    def rows(name, allowed):
        return [
            {key: value for key, value in slurm_pairs(line).items() if key in allowed}
            for line in outputs[name].splitlines()
            if line.strip()
        ]

    config = {}
    for line in outputs["config"].splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key.strip() in CONFIG_FIELDS:
            config[key.strip()] = value.strip()
    nodes = rows("nodes", NODE_FIELDS)
    require(
        nodes and all("NodeName" in row for row in nodes), "Incomplete node inventory"
    )
    jobs = []
    for line in outputs["own_jobs"].splitlines():
        if line.strip():
            parts = line.split("|", 2)
            require(len(parts) == 3, "Malformed own-job inventory")
            jobs.append(dict(zip(("job_id", "state", "name"), parts)))
    associations = []
    for line in outputs["own_associations"].splitlines():
        if line.strip():
            parts = line.split("|")
            if len(parts) == 6 and not parts[-1]:
                parts.pop()
            require(len(parts) == 5, "Malformed association inventory")
            associations.append(
                dict(
                    zip(
                        ("cluster", "account", "partition", "qos", "default_qos"), parts
                    )
                )
            )
    return {
        "slurm_version": outputs["version"].strip(),
        "nodes": nodes,
        "partitions": rows("partitions", PARTITION_FIELDS),
        "config": config,
        "own_jobs": jobs,
        "own_associations": associations,
        "candidate_nodes": {
            name: [node["NodeName"] for node in nodes if candidate(node, name)]
            for name in ("intel-256", "intel-512")
        },
        "candidate_scope": "advertised_topology_memory_no_GPU_vendor_and_effective_allocation_not_yet_observed",
    }


def storage_inventory(data_root, output, catalogue):
    """File metadata only: no opening, hashing or decompressing production inputs."""
    root = Path(data_root).resolve()
    expected = {row["original_id"] + ".lp.gz": row for row in catalogue["parents"]}
    observed = {}
    for path in root.rglob("*.lp.gz"):
        require(len(observed) < 1000, "Unexpectedly large input inventory")
        require(
            not path.is_symlink() and path.resolve().is_relative_to(root),
            "Input metadata escaped declared root",
        )
        relative = path.relative_to(root).as_posix()
        observed[relative] = {"name": path.name, "bytes": path.stat().st_size}
    coverage = {}
    for name, row in expected.items():
        matches = [
            relative for relative, item in observed.items() if item["name"] == name
        ]
        coverage[row["alias"]] = {
            "relative_paths": matches,
            "unique_name_and_stored_size_match": len(matches) == 1
            and observed[matches[0]]["bytes"] == row["stored_bytes"],
        }
    disk = shutil.disk_usage(output)
    fs = os.statvfs(output)
    return {
        "data_root": str(root),
        "stored_file_metadata": observed,
        "coverage": coverage,
        "all_expected_metadata_present": len(observed) == len(expected)
        and all(row["unique_name_and_stored_size_match"] for row in coverage.values()),
        "input_contents_opened_hashed_or_decompressed": False,
        "identity_scope": "names_and_sizes_only_accepted_decoded_equivalence_unchanged",
        "output_filesystem": {
            "total_bytes": disk.total,
            "free_bytes": disk.free,
            "free_inodes": fs.f_favail,
            "quota_verified": False,
        },
        "S2_input_readiness_established": False,
    }


def discover(
    output,
    source_commit,
    *,
    license_file,
    installed_repo,
    data_root,
    catalogue_path,
    execution_root=DEFAULT_EXECUTION_ROOT,
    runner=bounded_read,
):
    execution_root = checked_root(execution_root)
    run_paths(execution_root, output, catalogue_path)
    require(
        platform.system() == "Linux",
        "Production discovery must be run by the author on the Linux target",
    )
    import pwd

    user = pwd.getpwuid(os.getuid()).pw_name
    folder = Path(output).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    results, failures = {}, {}
    for name, argv in read_commands(user).items():
        try:
            results[name] = runner(argv)
        except (OSError, ValueError) as error:
            failures[name] = {
                "exception_type": type(error).__name__,
                "missing_reason": "bounded_read_only_command_failed",
            }
    packages = {}
    for name in (
        "gurobipy",
        "numpy",
        "torch",
        "torch-geometric",
        "pyarrow",
        "jsonschema",
        "psutil",
        "gurobi-logtools",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    installed = None
    try:
        installed = runner(
            ["git", "-C", str(Path(installed_repo)), "rev-parse", "HEAD"]
        ).strip()
    except (OSError, ValueError):
        failures["installed_repo"] = {
            "missing_reason": "installed_source_ref_unavailable"
        }
    inventory = None
    if not failures:
        try:
            inventory = parse_inventory(results)
        except (ValueError, KeyError, TypeError) as error:
            failures["inventory_parse"] = {
                "exception_type": type(error).__name__,
                "missing_reason": "malformed_read_only_inventory",
            }
    storage = None
    try:
        storage = storage_inventory(data_root, folder, load_json(catalogue_path))
    except (OSError, ValueError, KeyError) as error:
        failures["storage_metadata"] = {
            "exception_type": type(error).__name__,
            "missing_reason": "storage_metadata_unavailable",
        }
    report = {
        "schema_version": VERSION,
        "source_commit": source_commit,
        "execution_root": str(execution_root),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "uid": os.getuid(),
        "user": user,
        "python": platform.python_version(),
        "python_executable": os.sys.executable,
        "python_prefix": os.sys.prefix,
        "package_versions": packages,
        "license_file_path": str(Path(license_file).resolve()),
        "license_file_exists": Path(license_file).is_file(),
        "license_contents_read": False,
        "installed_source_commit": installed,
        "commands_failed": failures,
        "inventory": inventory,
        "storage": storage,
        "qualification": "discovery_only_not_an_allocation_or_license_initialization",
        "Slurm_jobs_submitted": 0,
        "native_environments_started": 0,
        "native_optimization_calls": 0,
        "scientific_observations": 0,
        "ready_for_S2": False,
    }
    durable_json(folder / "discovery.json", report)
    return report
