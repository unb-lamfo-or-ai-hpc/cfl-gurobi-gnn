"""Read-only resource scopes; sampled process RSS is not job or native memory."""

import re
from pathlib import Path

from .audit import quantity
from .contract import require


class JobCgroup:
    """A caller-supplied cgroup-v2 path must prove the exact scheduler job scope."""

    def __init__(self, path, job_id, *, root="/sys/fs/cgroup"):
        require(re.fullmatch(r"[1-9][0-9]*", str(job_id)) is not None, "Invalid job ID")
        self.path, root = Path(path).resolve(), Path(root).resolve()
        require(
            self.path != root and self.path.is_relative_to(root),
            "Cgroup escapes its filesystem scope",
        )
        job_component = re.compile(rf"job[_-]{re.escape(str(job_id))}(?:\.scope)?$")
        require(
            any(job_component.fullmatch(part) for part in self.path.parts),
            "Cgroup is not bound to the exact job",
        )
        # Read at the job directory, not an arbitrary sibling or child-step scope.
        while not job_component.fullmatch(self.path.name):
            self.path = self.path.parent

    def snapshot(self):
        def read_number(name):
            try:
                value = int((self.path / name).read_text().strip())
                require(value >= 0, "Negative cgroup memory")
                return quantity(value)
            except (OSError, ValueError):
                return quantity(None, "job_cgroup_counter_unavailable")

        try:
            events = {}
            for line in (self.path / "memory.events").read_text().splitlines():
                name, value = line.split()
                events[name] = int(value)
            require(
                all(value >= 0 for value in events.values()),
                "Negative cgroup event count",
            )
        except (OSError, ValueError):
            events = None
        return {
            "scope": "exact_job_cgroup_v2",
            "path": str(self.path),
            "current_bytes": read_number("memory.current"),
            "peak_bytes": read_number("memory.peak"),
            "memory_events": events,
            "events_missing_reason": None
            if events is not None
            else "job_memory_events_unavailable",
        }

    def contains_pid(self, pid, *, proc="/proc", root="/sys/fs/cgroup"):
        try:
            lines = (Path(proc) / str(pid) / "cgroup").read_text().splitlines()
            unified = [
                line.split("::", 1)[1] for line in lines if line.startswith("0::")
            ]
            require(len(unified) == 1, "Missing unique unified cgroup membership")
            member = (Path(root) / unified[0].lstrip("/")).resolve()
            return member == self.path or member.is_relative_to(self.path)
        except (OSError, ValueError):
            return False


def affinity_evidence(process, *, sysfs="/sys/devices/system/cpu"):
    from psutil import Error

    try:
        logical = sorted(process.cpu_affinity())
    except (AttributeError, OSError, RuntimeError, Error):
        return {
            "logical_ids": None,
            "physical_cores": None,
            "missing_reason": "process_affinity_unavailable",
        }
    mapping = []
    for cpu in logical:
        try:
            topology = Path(sysfs) / f"cpu{cpu}" / "topology"
            mapping.append(
                {
                    "logical_id": cpu,
                    "package_id": int((topology / "physical_package_id").read_text()),
                    "core_id": int((topology / "core_id").read_text()),
                }
            )
        except (OSError, ValueError):
            return {
                "logical_ids": logical,
                "physical_cores": None,
                "missing_reason": "physical_core_mapping_unavailable",
            }
    return {"logical_ids": logical, "physical_cores": mapping, "missing_reason": None}


class OwnedProcessTree:
    """Track creation times; never signal a reused PID or an unrelated process."""

    def __init__(self, pid, psutil):
        self.psutil = psutil
        self.root = psutil.Process(pid)
        self.identities = {pid: self.root.create_time()}

    def _same(self, pid, created):
        try:
            process = self.psutil.Process(pid)
            return process if process.create_time() == created else None
        except self.psutil.Error:
            return None

    def sample(self, *, include_root=True):
        root = self._same(self.root.pid, self.identities[self.root.pid])
        if root is not None:
            try:
                for child in root.children(recursive=True):
                    self.identities[child.pid] = child.create_time()
            except self.psutil.Error:
                pass
        rss, seen, missing = 0, 0, 0
        for pid, created in tuple(self.identities.items()):
            if not include_root and pid == self.root.pid:
                continue
            process = self._same(pid, created)
            if process is not None:
                try:
                    rss += process.memory_info().rss
                    seen += 1
                except self.psutil.Error:
                    missing += 1
        return {
            "scope": "sampled_owned_process_tree_RSS_sum",
            "bytes": rss if seen else None,
            "live_processes": seen,
            "unreadable_processes": missing,
            "exact_continuous_peak": False,
        }

    def stop(self):
        # Stop the owned parent first to limit further spawning, then known children.
        root = self._same(self.root.pid, self.identities[self.root.pid])
        if root is not None:
            try:
                root.suspend()
                for child in root.children(recursive=True):
                    self.identities[child.pid] = child.create_time()
            except self.psutil.Error:
                pass
        signalled = []
        for pid, created in reversed(tuple(self.identities.items())):
            process = self._same(pid, created)
            if process is not None:
                try:
                    process.kill()
                    signalled.append(pid)
                except self.psutil.Error:
                    pass
        return signalled
