"""Actual allocation facts; controller advertising is never an allocation proof."""

import os
import re
from pathlib import Path, PurePosixPath

from ..contract import require
from .policy import PROFILES, memory_bytes, slurm_pairs


def expand_cpus(text):
    result = set()
    for part in text.strip().split(","):
        match = re.fullmatch(r"([0-9]+)(?:-([0-9]+))?", part)
        require(match is not None, "Invalid Linux CPU range")
        first, last = int(match[1]), int(match[2] or match[1])
        require(first <= last <= 100000, "Invalid CPU range bounds")
        result.update(range(first, last + 1))
    return sorted(result)


def topology(cpus, *, sysfs="/sys/devices/system/cpu", cpuinfo="/proc/cpuinfo"):
    mapping = []
    for cpu in cpus:
        folder = Path(sysfs) / f"cpu{cpu}" / "topology"
        mapping.append(
            {
                "logical_id": cpu,
                "package_id": int((folder / "physical_package_id").read_text()),
                "core_id": int((folder / "core_id").read_text()),
                "siblings": expand_cpus((folder / "thread_siblings_list").read_text()),
            }
        )
    vendors = sorted(
        {
            line.partition(":")[2].strip()
            for line in Path(cpuinfo).read_text().splitlines()
            if line.startswith("vendor_id")
        }
    )
    return {"logical_ids": list(cpus), "mapping": mapping, "vendors": vendors}


def _unescape(text):
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), text)


def cgroup_memory(job_id, *, pid=None, proc="/proc"):
    """v1/v2 mapping honours mount roots and proves exact PID/job membership."""
    require(
        re.fullmatch(r"[1-9][0-9]*", str(job_id)) is not None, "Invalid job identity"
    )
    process = Path(proc) / (str(pid) if pid is not None else "self")
    memberships = []
    for line in (process / "cgroup").read_text().splitlines():
        _, controllers, path = line.split(":", 2)
        if not controllers or "memory" in controllers.split(","):
            memberships.append(("v2" if not controllers else "v1", PurePosixPath(path)))
    mounts = []
    for line in (process / "mountinfo").read_text().splitlines():
        before, after = line.split(" - ", 1)
        first, second = before.split(), after.split()
        if second[0] == "cgroup2" or (
            second[0] == "cgroup" and "memory" in second[2].split(",")
        ):
            mounts.append(
                (
                    "v2" if second[0] == "cgroup2" else "v1",
                    PurePosixPath(_unescape(first[3])),
                    Path(_unescape(first[4])).resolve(),
                )
            )
    candidates = []
    for kind, member in memberships:
        require(
            member.is_absolute() and ".." not in member.parts,
            "Unsafe cgroup membership",
        )
        for mounted_kind, root, mount in mounts:
            if kind == mounted_kind and member.is_relative_to(root):
                current = (mount / str(member.relative_to(root))).resolve()
                require(current.is_relative_to(mount), "Cgroup escaped mount")
                component = re.compile(rf"job[_-]{job_id}(?:\.scope)?$")
                job = next(
                    (
                        path
                        for path in (current, *current.parents)
                        if path.is_relative_to(mount) and component.fullmatch(path.name)
                    ),
                    None,
                )
                if job is not None:
                    candidates.append((kind, root, mount, current, job))
    require(len(candidates) == 1, "Unique memory-controller PID/job scope unavailable")
    kind, root, mount, current, job = candidates[0]
    names = {
        "v2": ("memory.current", "memory.peak", "memory.max"),
        "v1": (
            "memory.usage_in_bytes",
            "memory.max_usage_in_bytes",
            "memory.limit_in_bytes",
        ),
    }[kind]

    def number(folder, name):
        try:
            text = (folder / name).read_text().strip()
            if text == "max":
                return None
            value = int(text)
            require(value >= 0, "Negative cgroup counter")
            return value
        except (OSError, ValueError):
            return None

    limits, unreadable_limits = [], []
    path = current
    while path.is_relative_to(mount):
        value = number(path, names[2])
        try:
            raw_limit = (path / names[2]).read_text().strip()
            valid_limit = raw_limit == "max" if kind == "v2" else False
            valid_limit = valid_limit or (raw_limit.isdecimal() and int(raw_limit) >= 0)
        except OSError:
            # The unified root has no memory.max by kernel design.
            valid_limit = kind == "v2" and path == mount and root == PurePosixPath("/")
        if not valid_limit:
            unreadable_limits.append(str(path))
        if value is not None and not (kind == "v1" and value >= 2**60):
            limits.append(value)
        if path == mount:
            break
        path = path.parent
    effective = min(limits) if limits else None
    hierarchy_limit = None
    if kind == "v1":
        try:
            stats = dict(
                line.split()
                for line in (current / "memory.stat").read_text().splitlines()
            )
            hierarchy_limit = int(stats["hierarchical_memory_limit"])
        except (OSError, ValueError, KeyError):
            pass
    hierarchy_consistent = kind == "v2" or (
        hierarchy_limit == effective and effective is not None
    )
    events = {}
    if kind == "v2":
        try:
            events = {
                name: int(value)
                for name, value in (
                    line.split()
                    for line in (job / "memory.events").read_text().splitlines()
                )
            }
        except (OSError, ValueError):
            events = {}
    else:
        events["failcnt"] = number(job, "memory.failcnt")
        try:
            events.update(
                {
                    name: int(value)
                    for name, value in (
                        line.split()
                        for line in (job / "memory.oom_control")
                        .read_text()
                        .splitlines()
                    )
                }
            )
        except (OSError, ValueError):
            pass
    return {
        "version": kind,
        "PID_membership_verified": True,
        "job_id": str(job_id),
        "job_scope": str(job),
        "process_scope": str(current),
        "current_job_bytes": number(job, names[0]),
        "peak_job_bytes": number(job, names[1]),
        "effective_process_memory_limit_bytes": effective,
        "kernel_hierarchical_limit_bytes": hierarchy_limit,
        "kernel_hierarchy_consistent": hierarchy_consistent,
        "limit_chain_complete": not unreadable_limits,
        "memory_mount_root_is_host_root": root == PurePosixPath("/"),
        "unreadable_limit_scopes": unreadable_limits,
        "kernel_limit_scope": "minimum_limit_through_visible_memory_mount_ancestors",
        "events": events,
        "peak_missing_reason": None
        if number(job, names[1]) is not None
        else "job_peak_counter_unavailable",
    }


def audit_allocation(
    profile,
    job_text,
    node_text,
    cpu,
    memory,
    *,
    uid,
    job_id,
    node_name,
    memtotal_bytes,
    own_job_count,
):
    require(profile in PROFILES, "Unknown production profile")
    job, node = slurm_pairs(job_text), slurm_pairs(node_text)
    tres = dict(
        item.split("=", 1)
        for item in job.get("AllocTRES", "").split(",")
        if "=" in item
    )
    cores = {}
    for row in cpu["mapping"]:
        cores.setdefault((row["package_id"], row["core_id"]), []).append(
            row["logical_id"]
        )
    requested = PROFILES[profile]["memory_GiB"] * 1024**3
    user_match = re.fullmatch(r".*\(([0-9]+)\)", job.get("UserId", ""))
    tests = {
        "job_id": job.get("JobId") == str(job_id),
        "own_job": user_match is not None and int(user_match[1]) == uid,
        "running": job.get("JobState") == "RUNNING",
        "single_node": job.get("NumNodes") == "1"
        and job.get("NodeList") == node_name == node.get("NodeName"),
        "single_task": job.get("NumTasks") == "1",
        "allocated_CPUs": job.get("NumCPUs") == "64" and tres.get("cpu") == "64",
        # Slurm22.05 job_share_string(JOB_SHARED_NONE) emits NO, not the
        # partition configuration word EXCLUSIVE. Full-node CPU checks also apply.
        "exclusive": (
            job.get("OverSubscribe") in ("NO", "EXCLUSIVE") or job.get("Shared") == "0"
        )
        and job.get("Exclusive", "NODE") == "NODE",
        "memory_reservation": memory_bytes(tres["mem"]) == requested
        if "mem" in tres
        else False,
        "no_GPU": node.get("Gres") in ("(null)", "N/A", "", "None", "none")
        and not any(
            name.startswith("gres/gpu") and value not in ("0", "0M")
            for name, value in tres.items()
        ),
        "Intel_vendor": cpu["vendors"] == ["GenuineIntel"],
        "affinity64": len(set(cpu["logical_ids"])) == 64
        and len(cpu["mapping"]) == 64
        and {row["logical_id"] for row in cpu["mapping"]} == set(cpu["logical_ids"]),
        "physical32": len(cores) == 32
        and len({key[0] for key in cores}) == 2
        and all(
            sum(key[0] == package for key in cores) == 16
            for package in {key[0] for key in cores}
        ),
        "node_topology": all(
            node.get(name) == value
            for name, value in {
                "Sockets": "2",
                "CoresPerSocket": "16",
                "ThreadsPerCore": "2",
                "CPUTot": "64",
            }.items()
        ),
        "SMT2": all(
            len(ids) == 2
            and all(
                sorted(row["siblings"]) == sorted(ids)
                for row in cpu["mapping"]
                if (row["package_id"], row["core_id"]) == key
            )
            for key, ids in cores.items()
        ),
        "physical_capacity": memtotal_bytes >= requested,
        "cgroup_membership": memory.get("PID_membership_verified") is True
        and memory.get("job_id") == str(job_id),
        "memory_enforcement": memory.get("effective_process_memory_limit_bytes")
        == requested
        and memory.get("limit_chain_complete") is True
        and memory.get("memory_mount_root_is_host_root") is True
        and memory.get("kernel_hierarchy_consistent") is True,
        "job_peak_counter": memory.get("peak_job_bytes") is not None,
        "maximum_two_jobs": 1 <= own_job_count <= 2,
    }
    if profile == "intel-256":
        tests["memory_class"] = (
            requested <= int(node.get("RealMemory", "0")) * 1024**2 < 384 * 1024**3
        )
    else:
        tests["memory_class"] = int(node.get("RealMemory", "0")) * 1024**2 >= requested
    return {
        "checks": tests,
        "allocation_qualified": all(tests.values()),
        "requested_memory_bytes": requested,
        "scheduler_fields": {
            name: job.get(name)
            for name in (
                "JobId",
                "JobState",
                "NodeList",
                "NumNodes",
                "NumTasks",
                "NumCPUs",
                "AllocTRES",
                "OverSubscribe",
                "Exclusive",
                "Shared",
                "Partition",
                "Account",
                "QOS",
                "TimeLimit",
                "Restarts",
            )
        },
        "observed_CPU": cpu,
        "observed_memory": memory,
        "memory_stress_test_performed": False,
        "real_CFL_memory_adequacy_established": False,
        "ready_for_scientific_S2": False,
    }


def live_allocation(profile, runner, environ=None):
    environ = os.environ if environ is None else environ
    job_id, node_name = (
        environ.get("SLURM_JOB_ID", ""),
        environ.get("SLURMD_NODENAME", ""),
    )
    require(
        re.fullmatch(r"[1-9][0-9]*", job_id) is not None,
        "A real author-submitted Slurm job is required",
    )
    require(node_name, "Missing Slurm node identity")
    import pwd

    from .inventory import read_commands

    user = pwd.getpwuid(os.getuid()).pw_name
    jobs = runner(read_commands(user)["own_jobs"])
    memory = cgroup_memory(job_id)
    memtotal = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemTotal:")
    )
    return audit_allocation(
        profile,
        runner(["scontrol", "show", "job", job_id, "-o"]),
        runner(["scontrol", "show", "node", node_name, "-o"]),
        topology(sorted(os.sched_getaffinity(0))),
        memory,
        uid=os.getuid(),
        job_id=job_id,
        node_name=node_name,
        memtotal_bytes=memtotal,
        own_job_count=len([line for line in jobs.splitlines() if line.strip()]),
    )
