"""Candidate memory-controller-aware resolver; frozen v1 policy is unchanged.

Linux binds a controller to v1 or v2, not both. An explicit v1 memory
membership therefore takes precedence over the unrelated unified membership.
See https://docs.kernel.org/admin-guide/cgroup-v2.html#mounting .
No fallback to another hierarchy after a selected controller fails validation.
"""

import os
import re
from pathlib import Path

import paired_memory_guard as original

POLICY = dict(original.POLICY)
require = original.require


def membership_summary(membership):
    legacy, unified = [], []
    for line in membership.splitlines():
        fields = line.split(":", 2)
        require(len(fields) == 3 and re.fullmatch(r"[0-9]+", fields[0]))
        if fields[0] == "0" and fields[1] == "":
            unified.append(line)
        elif "memory" in fields[1].split(","):
            require(fields[0] != "0")
            require(fields[1].split(",").count("memory") == 1)
            legacy.append(line)
    return legacy, unified


def resolve_cgroup(membership, mounts, job):
    legacy, unified = membership_summary(membership)
    require(len(legacy) <= 1 and len(unified) <= 1)
    selected = legacy if legacy else unified
    require(len(selected) == 1)
    # The frozen resolver still checks job membership, an unambiguous mount,
    # filesystem type, namespace root and location under /sys/fs/cgroup.
    return original.resolve_cgroup(selected[0], mounts, job)


class MemoryGate(original.MemoryGate):
    def __init__(self, job, pid=None):
        self.job = job
        self.pid = os.getpid() if pid is None else pid
        self.membership = original.bounded_text(f"/proc/{self.pid}/cgroup")
        self.version, self.leaf, self.limit_file, self.usage_file = resolve_cgroup(
            self.membership,
            original.bounded_text(f"/proc/{self.pid}/mountinfo"),
            job,
        )
        self.leaf, self.limit_file, self.usage_file = map(
            Path, (self.leaf, self.limit_file, self.usage_file)
        )
        require(self.leaf.resolve(strict=True) == self.leaf)
        if self.version == "v1":
            require(original.numeric(self.leaf / "memory.use_hierarchy") == 1)
        self.limit = original.numeric(self.limit_file)
        require(POLICY["cgroup_interrupt_bytes"] < self.limit <= 64 * original.GIB)
        require(self.sample() < POLICY["cgroup_interrupt_bytes"])
        # sample(), public() and watchdog behavior remain inherited/unchanged.
