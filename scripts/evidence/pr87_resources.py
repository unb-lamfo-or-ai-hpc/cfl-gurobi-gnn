"""Reuse the scoped memory gate at PR87's explicit 112/128-GiB limits."""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import time
from pathlib import Path

import pr78_scoped_evidence as scoped
import pr87_contract as c

GIB = 1024**3


def gate_class():
    qualified = scoped.load_candidate()

    class Gate(qualified.MemoryGate):
        def __init__(self, job):
            # Parameterized capacity only; inherited scoped mount/usage checking.
            self.job, self.pid = job, os.getpid()
            self.last_failure, self._mount_signature = None, None
            original = qualified.original
            self.membership = original.bounded_text(f"/proc/{self.pid}/cgroup")
            self.mounts = original.bounded_text(f"/proc/{self.pid}/mountinfo")
            self.version, leaf, limit_file, usage_file = qualified.prior.resolve_cgroup(
                self.membership, self.mounts, job
            )
            self.chain = qualified.job_chain(Path(leaf), job)
            self.limit_name, self.usage_name = limit_file.name, usage_file.name
            self.limits = self.read_limits()
            self.job_limit = self.limits[-1]
            c.require(self.job_limit == 128 * GIB, "kernel_128GiB_job_cap_required")
            c.require(
                all(value is None or value > 112 * GIB for value in self.limits),
                "descendant_memory_limit",
            )
            self.scoped_limit = min(value for value in self.limits if value is not None)
            c.require(self.sample() < 112 * GIB, "initial_memory_usage")

    return Gate


class GPUObservation:
    def __init__(self, gate, world):
        self.gate, self.world = gate, world
        self.last, self.observations, self.missing = -float("inf"), [], 0
        visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
        values = visible.split(",")
        c.require(
            len(values) == world
            and all(re.fullmatch(r"[0-9]+|GPU-[A-Za-z0-9-]+", v) for v in values),
            "visible_gpu_identity",
        )
        self.visible = visible

    def sample(self):
        usage = self.gate.sample()  # Memory failure is mandatory, never ignored.
        if time.monotonic() - self.last >= 5:
            self.last = time.monotonic()
            try:
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "-i",
                        self.visible,
                        "--query-gpu=utilization.gpu,memory.used,power.draw",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=3,
                )
                rows = [
                    tuple(float(x.strip()) for x in line.split(","))
                    for line in result.stdout.splitlines()
                ]
                c.require(
                    len(rows) == self.world and all(len(row) == 3 for row in rows),
                    "gpu_telemetry",
                )
                self.observations.append(rows)
            except (OSError, ValueError, subprocess.SubprocessError):
                self.missing += 1
        return usage

    def public(self):
        rows = self.observations
        return {
            "interval_seconds": 5,
            "samples": len(rows),
            "missing_queries": self.missing,
            "scope": "allocated_device_samples_not_process_exclusive_or_continuous_peak",
            "gpu_utilization_mean_percent": [
                sum(row[i][0] for row in rows) / len(rows) for i in range(self.world)
            ]
            if rows
            else None,
            "gpu_sampled_max_memory_mib": [
                max(row[i][1] for row in rows) for i in range(self.world)
            ]
            if rows
            else None,
            "gpu_sampled_mean_power_watts": [
                sum(row[i][2] for row in rows) / len(rows) for i in range(self.world)
            ]
            if rows
            else None,
        }


def supervise(command, console, gate, world):
    # Separate module instance: historical policy/source is NOT mutated.
    spec = importlib.util.spec_from_file_location(
        "pr87_owned_watchdog", c.REPO / "scripts/evidence/paired_memory_guard.py"
    )
    watchdog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watchdog)
    watchdog.POLICY = {
        **watchdog.POLICY,
        "cgroup_interrupt_bytes": 112 * GIB,
        "maximum_kernel_ram_limit_bytes": 128 * GIB,
        "poll_seconds": 5,
    }
    observer = GPUObservation(gate, world)
    result = watchdog.supervise(command, console, 42600, observer)
    result["gpu_telemetry"] = observer.public()
    result["host_memory_stop_bytes"] = 112 * GIB
    result["kernel_ram_limit_bytes"] = gate.job_limit
    result["memory_gate"] = gate.public()
    result["capacity_policy"] = "PR87_112GiB_sampled_stop_128GiB_kernel_cap"
    result["swap_limit_qualified"] = False
    result["historical_128GiB_training_qualification_claimed"] = False
    return result
