"""Qualification-only job-scoped hierarchical RAM gate; never writes cgroups.

Keep controller selection separate from enforcement scope. Slurm can put an
unlimited task leaf below capped step/job groups. Require a finite job anchor,
hierarchical accounting on the entire path, and monitor all groups through it.
This is not an RSS measurement or a claim about swap or host-wide ancestors.
"""

import os
import re
from pathlib import Path

import paired_memory_guard_v2 as controller

original = controller.original
POLICY = dict(original.POLICY)
require = original.require
membership_summary = controller.membership_summary
resolve_cgroup = controller.resolve_cgroup


def job_chain(leaf, job):
    """Exact job anchor only; never borrow limits from another job or uid."""
    require(re.fullmatch(r"[0-9]{1,20}", job) is not None)
    pattern = r"job[_-]" + job + r"(?:\.scope)?"
    require(sum(bool(re.fullmatch(pattern, p)) for p in leaf.parts) == 1)
    chain = []
    for path in (leaf, *leaf.parents):
        require(len(chain) < 16)
        require(path.is_relative_to("/sys/fs/cgroup"))
        require(path.resolve(strict=True) == path)
        chain.append(path)
        if re.fullmatch(pattern, path.name):
            return tuple(chain)
    raise ValueError("job_anchor_missing")


class MemoryGate:
    def __init__(self, job, pid=None):
        self.job = job
        self.pid = os.getpid() if pid is None else pid
        self.membership = original.bounded_text(f"/proc/{self.pid}/cgroup")
        self.mounts = original.bounded_text(f"/proc/{self.pid}/mountinfo")
        self.version, leaf, limit_file, usage_file = resolve_cgroup(
            self.membership, self.mounts, job
        )
        self.chain = job_chain(Path(leaf), job)
        self.limit_name = limit_file.name
        self.usage_name = usage_file.name
        self.limits = self.read_limits()
        self.job_limit = self.limits[-1]
        require(self.job_limit is not None)
        require(
            POLICY["cgroup_interrupt_bytes"]
            < self.job_limit
            <= POLICY["maximum_kernel_ram_limit_bytes"]
        )
        # A tighter descendant must still leave the watchdog's safety margin.
        require(
            all(x is None or x > POLICY["cgroup_interrupt_bytes"] for x in self.limits)
        )
        self.scoped_limit = min(x for x in self.limits if x is not None)
        require(self.sample() < POLICY["cgroup_interrupt_bytes"])

    def read_limits(self):
        result = []
        for path in self.chain:
            require(path.resolve(strict=True) == path)
            if self.version == "v1":
                require(original.numeric(path / "memory.use_hierarchy") == 1)
            raw = original.bounded_text(path / self.limit_name).strip()
            if self.version == "v2" and raw == "max":
                result.append(None)
            else:
                require(re.fullmatch(r"[0-9]{1,20}", raw) is not None)
                result.append(int(raw))
        return tuple(result)

    def sample(self):
        require(original.bounded_text(f"/proc/{self.pid}/cgroup") == self.membership)
        require(original.bounded_text(f"/proc/{self.pid}/mountinfo") == self.mounts)
        require(self.read_limits() == self.limits)
        # Include aggregate job usage, hence sibling steps/children. The maximum
        # is conservative across non-atomic kernel reads, not an exact RSS peak.
        return max(original.numeric(p / self.usage_name) for p in self.chain)

    def public(self):
        return {
            "memory_gate_protocol": "job_scoped_hierarchical_ram_v1",
            "cgroup_version_observed": self.version,
            "job_anchor_ram_limit_bytes": self.job_limit,
            "job_scoped_min_ram_limit_bytes": self.scoped_limit,
            "leaf_ram_limit_bytes": self.limits[0],
            "validated_group_count": len(self.chain),
            "job_anchor_depth_from_leaf": len(self.chain) - 1,
            "current_max_job_scoped_usage_bytes": self.sample(),
            "usage_scope": "maximum_leaf_through_job_anchor_including_siblings",
            "membership_and_mounts_verified": True,
            "hierarchy_rechecked_each_sample": True,
            "ancestor_limits_rechecked_each_sample": True,
            "swap_limit_qualified": False,
            "historical_rss_reconciled": False,
        }
