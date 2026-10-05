#!/usr/bin/env python3
"""Read-only Linux memory gate and watchdog; never configure site cgroups."""

import os
import re
import signal
import subprocess
import time
from pathlib import Path, PurePosixPath

GIB = 1024**3
POLICY = {
    "schema_version": 1,
    "soft_mem_limit_decimal_gb": 48,
    "cgroup_interrupt_bytes": 56 * GIB,
    "maximum_kernel_ram_limit_bytes": 64 * GIB,
    "poll_seconds": 0.25,
    "termination_grace_seconds": 10,
    "kernel_limit_required_before_model_read": True,
    "memory_stop_pauses_all_remaining_attempts": True,
    "automatic_retry": False,
    "automatic_thread_reduction": False,
    "swap_limit_qualified": False,
    "historical_rss_reconciled": False,
}


def require(value):
    if not value:
        raise ValueError("memory_gate_unqualified")


def bounded_text(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    require(len(raw) <= 65536)
    return raw.decode("ascii")


def numeric(path):
    raw = bounded_text(path).strip()
    require(re.fullmatch(r"[0-9]{1,20}", raw) is not None)
    return int(raw)


def resolve_cgroup(membership, mounts, job):
    """Only an unambiguous mounted job leaf; unknown layouts fail closed."""
    require(re.fullmatch(r"[0-9]{1,20}", job) is not None)
    entries = []
    for line in membership.splitlines():
        fields = line.split(":", 2)
        require(len(fields) == 3)
        if fields[0] == "0" and fields[1] == "":
            entries.append(("v2", fields[2]))
        elif "memory" in fields[1].split(","):
            entries.append(("v1", fields[2]))
    require(len(entries) == 1)
    version, relative = entries[0]
    parts = PurePosixPath(relative).parts
    require(relative.startswith("/") and ".." not in parts)
    require(any(re.fullmatch(r"job[_-]" + job + r"(?:\.scope)?", p) for p in parts))
    candidates = []
    for line in mounts.splitlines():
        left, sep, right = line.partition(" - ")
        require(bool(sep))
        a, b = left.split(), right.split()
        require(len(a) >= 6 and len(b) >= 3)
        matches = (
            b[0] == "cgroup2"
            if version == "v2"
            else (b[0] == "cgroup" and "memory" in b[2].split(","))
        )
        if matches:
            # Do not guess namespace-relative or escaped mount roots.
            require(a[3] == "/" and "\\" not in a[4])
            mount = PurePosixPath(a[4])
            require(mount.is_absolute() and mount.is_relative_to("/sys/fs/cgroup"))
            candidates.append(mount / relative.lstrip("/"))
    require(len(candidates) == 1)
    leaf = candidates[0]
    limit = "memory.max" if version == "v2" else "memory.limit_in_bytes"
    usage = "memory.current" if version == "v2" else "memory.usage_in_bytes"
    return version, leaf, leaf / limit, leaf / usage


class MemoryGate:
    def __init__(self, job, pid=None):
        self.job = job
        self.pid = os.getpid() if pid is None else pid
        self.membership = bounded_text(f"/proc/{self.pid}/cgroup")
        self.version, self.leaf, self.limit_file, self.usage_file = resolve_cgroup(
            self.membership, bounded_text(f"/proc/{self.pid}/mountinfo"), job
        )
        self.leaf, self.limit_file, self.usage_file = map(
            Path, (self.leaf, self.limit_file, self.usage_file)
        )
        require(self.leaf.resolve(strict=True) == self.leaf)
        if self.version == "v1":
            require(numeric(self.leaf / "memory.use_hierarchy") == 1)
        self.limit = numeric(self.limit_file)
        require(POLICY["cgroup_interrupt_bytes"] < self.limit <= 64 * GIB)
        require(self.sample() < POLICY["cgroup_interrupt_bytes"])

    def sample(self):
        require(bounded_text(f"/proc/{self.pid}/cgroup") == self.membership)
        require(numeric(self.limit_file) == self.limit)
        return numeric(self.usage_file)

    def public(self):
        return {
            "cgroup_version_observed": self.version,
            "job_leaf_ram_limit_bytes": self.limit,
            "current_usage_bytes": self.sample(),
            "job_leaf_membership_verified": True,
            "swap_limit_qualified": False,
            "historical_rss_reconciled": False,
        }


def kill_owned_group(process, sig):
    # start_new_session=True makes this child PID its dedicated group ID.
    require(process.pid != os.getpgrp())
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def stop_owned(process):
    kill_owned_group(process, signal.SIGTERM)
    try:
        process.wait(timeout=POLICY["termination_grace_seconds"])
    except subprocess.TimeoutExpired:
        kill_owned_group(process, signal.SIGKILL)
        process.wait(timeout=POLICY["termination_grace_seconds"])
    # Reap the leader, then kill any retained descendants in the same group.
    kill_owned_group(process, signal.SIGKILL)


def supervise(command, console, deadline, gate):
    """Polling exists only inside a batch executor, not interactive status."""
    peak = gate.sample()
    require(peak < POLICY["cgroup_interrupt_bytes"])
    started = time.monotonic()
    reason = None
    with Path(console).open("xb") as stream:
        process = subprocess.Popen(
            command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            while process.poll() is None:
                try:
                    usage = gate.sample()
                    peak = max(peak, usage)
                    if usage >= POLICY["cgroup_interrupt_bytes"]:
                        reason = "memory_guard_stop"
                except Exception:
                    reason = "memory_observation_lost"
                if reason is None and time.monotonic() - started >= deadline:
                    reason = "child_deadline_exceeded"
                if reason is not None:
                    stop_owned(process)
                    break
                try:
                    process.wait(timeout=POLICY["poll_seconds"])
                except subprocess.TimeoutExpired:
                    pass
            # Even a successful leader exit must not leave live descendants.
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                pass
            else:
                reason = reason or "unexpected_process_group_survivor"
                stop_owned(process)
            if reason is None:
                try:
                    peak = max(peak, gate.sample())
                    if peak >= POLICY["cgroup_interrupt_bytes"]:
                        reason = "memory_guard_stop"
                except Exception:
                    reason = "memory_observation_lost"
        except BaseException:
            stop_owned(process)
            raise
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "child_exit_code": process.returncode,
        "guard_stop": reason,
        "sampled_cgroup_peak_bytes": peak,
        "supervisor_wall_seconds": time.monotonic() - started,
        "peak_is_sampled_not_exact": True,
    }
