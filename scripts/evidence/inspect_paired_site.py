"""Read-only Slurm inventory and paired submission diagnosis; no solver imports.

The output describes current site state, not historical job configuration.
SPDX-License-Identifier: MIT
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

JOB_FIELDS = set(
    "JobId JobState Reason Priority Partition Requeue Restarts BatchFlag NumNodes "
    "NumTasks NumCPUs CPUs/Task TimeLimit MinMemoryNode MinMemoryCPU OverSubscribe "
    "ReqB:S:C:T Socks/Node NtasksPerN:B:S:C CoreSpec TRES ReqTRES AllocTRES".split()
)
NODE_FIELDS = set(
    "NodeName Arch CoresPerSocket CPUAlloc CPUEfctv CPUTot CPULoad RealMemory "
    "AllocMem FreeMem Sockets State ThreadsPerCore CfgTRES AllocTRES".split()
)
PARTITION_FIELDS = set(
    "PartitionName Nodes TotalNodes TotalCPUs DefaultTime MaxTime MinNodes "
    "MaxNodes DefMemPerCPU DefMemPerNode MaxMemPerCPU MaxMemPerNode State "
    "OverSubscribe SelectTypeParameters".split()
)
CONFIG_FIELDS = set(
    "SlurmctldVersion SelectType SelectTypeParameters TaskPlugin TaskPluginParam "
    "ProctrackType JobSubmitPlugins JobAcctGatherType JobAcctGatherFrequency "
    "DefMemPerCPU DefMemPerNode MaxMemPerCPU MaxMemPerNode".split()
)
EXPECTED = {
    "JobState": "PENDING",
    "Reason": "JobHeldUser",
    "Priority": "0",
    "Partition": "batch",
    "Requeue": "0",
    "Restarts": "0",
    "BatchFlag": "1",
    "NumNodes": "1",
    "NumTasks": "1",
    "CPUs/Task": "16",
    "TimeLimit": "05:30:00",
    "OverSubscribe": "OK",
}


def safe_value(value):
    if re.fullmatch(r"[A-Za-z0-9_.,:/+*()=\[\]-]{1,256}", value):
        return value
    return "unavailable_or_redacted"


def fields(text, allowed):
    result = {}
    for key, value in re.findall(
        r"(?:^|\s)([A-Za-z][A-Za-z0-9/:_]*)\s*=\s*(\S+)", text
    ):
        if key not in allowed:
            continue
        if key in result:
            result[key] = "duplicate_field"
        elif key.endswith("TRES"):
            result[key] = {
                name: safe_value(amount)
                for name, sep, amount in (
                    item.partition("=") for item in value.split(",")
                )
                if sep and name in {"cpu", "mem", "node", "billing"}
            }
        else:
            result[key] = safe_value(value)
    return result


def held_differences(profile, job):
    expected = {**EXPECTED, "JobId": job}
    differences = [
        {"field": key, "expected": value, "observed": profile.get(key)}
        for key, value in expected.items()
        if profile.get(key) != value
    ]
    for key, allowed in (
        ("NumCPUs", ["16", "32"]),
        ("MinMemoryNode", ["64G", "65536M"]),
    ):
        if profile.get(key) not in allowed:
            differences.append(
                {"field": key, "expected": allowed, "observed": profile.get(key)}
            )
    tres = profile.get("TRES", {})
    for key, allowed in (
        ("node", ["1"]),
        ("cpu", [profile.get("NumCPUs")]),
        ("mem", ["64G", "65536M"]),
    ):
        if not isinstance(tres, dict) or key not in tres or tres[key] not in allowed:
            differences.append(
                {
                    "field": "TRES." + key,
                    "expected": allowed,
                    "observed": tres.get(key) if isinstance(tres, dict) else None,
                }
            )
    return differences


def query(args):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
        return result.returncode, result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""


def topology(text):
    rows = [
        line.split(",")
        for line in text.splitlines()
        if line and not line.startswith("#")
    ]
    online = [
        row
        for row in rows
        if len(row) == 4
        and row[3].strip().lower() in {"y", "yes", "1"}
        and all(x.isdigit() for x in row[:3])
    ]
    return {
        "online_logical_cpus": len(online),
        "online_physical_cores": len({(r[2], r[1]) for r in online}),
        "online_sockets": len({r[2] for r in online}),
        "process_affinity_logical_cpus": len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
    }


def workflow_state(directory):
    state = directory / "operator-state/easy"
    result = {}
    for name in (
        "submission.json",
        "held_profile.json",
        "release.started",
        "released.json",
        "batch.started",
        "collection.started",
    ):
        path = state / name
        if path.is_symlink():
            result[name] = {"state": "symlink_not_read"}
        elif path.is_file():
            result[name] = {
                "state": "present",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        else:
            result[name] = {"state": "absent"}
    # Absence of a marker is not a proof of zero solver calls.
    return result


def inspect(directory, job):
    queries = {}
    result = {
        "schema_version": 1,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "job_id": job,
        "current_configuration_is_historical_evidence": False,
        "scientific_reporting_eligible": False,
        "submissions_added": 0,
        "optimization_runs_added": 0,
    }
    for label, command, allowed in (
        ("nodes", ["scontrol", "show", "nodes", "--oneliner"], NODE_FIELDS),
        (
            "partition",
            ["scontrol", "show", "partition", "batch", "--oneliner"],
            PARTITION_FIELDS,
        ),
        ("configuration", ["scontrol", "show", "config"], CONFIG_FIELDS),
        ("job", ["scontrol", "show", "job", "--oneliner", job], JOB_FIELDS),
    ):
        rc, text = query(command)
        queries[label] = {"returncode": rc}
        result[label] = (
            [fields(line, allowed) for line in text.splitlines() if line.strip()]
            if label == "nodes"
            else fields(text, allowed)
        )
    result["job_current_differences_from_held_contract"] = (
        held_differences(result["job"], job) if result["job"] else None
    )
    result["difference_scope"] = (
        "current_job_only; cancellation changes state and reason"
    )
    rc, text = query(["lscpu", "-p=CPU,CORE,SOCKET,ONLINE"])
    queries["lscpu"] = {"returncode": rc}
    result["cpu_topology"] = topology(text) if rc == 0 else None
    memory = Path("/proc/meminfo")
    result["host_memory_kib"] = {
        key: int(value)
        for key, value in re.findall(
            r"^(MemTotal|MemAvailable):\s+(\d+) kB$",
            memory.read_text() if memory.is_file() else "",
            re.M,
        )
    }
    columns = [
        "JobIDRaw",
        "State",
        "ExitCode",
        "ElapsedRaw",
        "Start",
        "End",
        "NNodes",
        "NTasks",
        "ReqCPUS",
        "AllocCPUS",
        "ReqMem",
        "MaxRSS",
    ]
    rc, text = query(
        [
            "sacct",
            "--noheader",
            "--parsable2",
            "-j",
            job,
            "--format=" + ",".join(columns),
        ]
    )
    queries["accounting"] = {"returncode": rc}
    result["accounting"] = [
        {
            key: safe_value(value.split(" by ", 1)[0]) if value else None
            for key, value in zip(columns, row)
        }
        for row in (line.split("|") for line in text.splitlines())
        if len(row) == len(columns)
    ]
    result["workflow_markers"] = workflow_state(directory)
    result["command_paths"] = {
        name: shutil.which(name) for name in ("sbatch", "scontrol", "sacct")
    }
    result["query_results"] = queries
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{1,20}", args.job_id):
        parser.error("job-id must be numeric")
    directory = args.directory.absolute()
    root = Path("/raid/vrcelestino/data/cfl-mvp2-evidence")
    if (
        not directory.is_relative_to(root)
        or directory.resolve() != directory
        or not directory.is_dir()
    ):
        parser.error("directory must be an existing physical RAID evidence directory")
    print(json.dumps(inspect(directory, args.job_id), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
