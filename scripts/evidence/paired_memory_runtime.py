"""Runtime adapter for the installed-qualified hierarchy; frozen watchdog reused."""

import isolated_attempt_worker as old
import paired_memory_guard as watchdog
import paired_memory_guard_v3 as qualified

PROTOCOL = "job_scoped_hierarchical_ram_v1"
GIB = watchdog.GIB
POLICY = dict(watchdog.POLICY)
MemoryGate = qualified.MemoryGate
supervise = watchdog.supervise
require = old.require


def validate_public(value):
    old.keys(
        value,
        "memory_gate_protocol cgroup_version_observed job_anchor_ram_limit_bytes "
        "job_scoped_min_ram_limit_bytes leaf_ram_limit_bytes validated_group_count "
        "job_anchor_depth_from_leaf current_max_job_scoped_usage_bytes usage_scope "
        "membership_and_mounts_verified hierarchy_rechecked_each_sample "
        "ancestor_limits_rechecked_each_sample swap_limit_qualified historical_rss_reconciled",
    )
    require(value["memory_gate_protocol"] == PROTOCOL)
    require(value["cgroup_version_observed"] in {"v1", "v2"})
    job = old.integer(value["job_anchor_ram_limit_bytes"])
    scoped = old.integer(value["job_scoped_min_ram_limit_bytes"])
    require(56 * GIB < scoped <= job <= 64 * GIB)
    leaf = value["leaf_ram_limit_bytes"]
    require(leaf is not None or value["cgroup_version_observed"] == "v2")
    if leaf is not None:
        require(old.integer(leaf) >= scoped)
    groups = old.integer(value["validated_group_count"], 1, 16)
    require(old.integer(value["job_anchor_depth_from_leaf"], 0, 15) == groups - 1)
    if groups == 1:
        require(leaf == scoped == job)
    require(old.integer(value["current_max_job_scoped_usage_bytes"]) < 56 * GIB)
    require(
        value["usage_scope"] == "maximum_leaf_through_job_anchor_including_siblings"
    )
    for name in (
        "membership_and_mounts_verified",
        "hierarchy_rechecked_each_sample",
        "ancestor_limits_rechecked_each_sample",
    ):
        require(value[name] is True)
    require(value["swap_limit_qualified"] is False)
    require(value["historical_rss_reconciled"] is False)
