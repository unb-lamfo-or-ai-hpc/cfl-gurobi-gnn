"""Bounded, one-worker local supervision, called only by a concrete CLI release."""

import math
import subprocess
import time
from pathlib import Path

from .contract import require
from .journal import durable_json, file_sha256
from .resources import OwnedProcessTree, affinity_evidence


def supervise(
    argv,
    folder,
    *,
    cwd,
    wall_seconds,
    memory_bytes,
    approval_reference,
    interval=0.25,
    log_bytes=64 * 1024 * 1024,
    cgroup=None,
    psutil_api=None,
):
    """No shell, retries, remote access, scheduler submission or global signalling.

    This generic primitive confers no execution authority. Its caller binds an
    exact reviewed worker/input/source and obtains author CLI approval first.
    """
    require(
        isinstance(argv, list)
        and argv
        and all(isinstance(arg, str) and arg for arg in argv),
        "An explicit argument vector is required",
    )
    require(
        type(wall_seconds) in (int, float)
        and math.isfinite(wall_seconds)
        and wall_seconds > 0,
        "Finite positive wall limit required",
    )
    require(
        type(memory_bytes) is int and memory_bytes > 0, "Positive memory limit required"
    )
    require(type(log_bytes) is int and log_bytes > 0, "Positive stdout limit required")
    require(
        type(interval) in (int, float)
        and math.isfinite(interval)
        and 0 < interval <= 5,
        "Invalid sampling interval",
    )
    require(
        isinstance(approval_reference, str) and approval_reference.strip(),
        "External concrete CLI approval reference required",
    )
    if psutil_api is None:
        import psutil as psutil_api
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    durable_json(
        folder / "supervisor-intent.json",
        {
            "argv": argv,
            "cwd": str(Path(cwd).resolve()),
            "wall_seconds": wall_seconds,
            "memory_bytes": memory_bytes,
            "stdout_observed_byte_limit": log_bytes,
            "interval_seconds": interval,
            "approval_reference": approval_reference,
            "automatic_retry": False,
        },
    )
    started = time.perf_counter()
    samples, maximum = 0, None
    guard, signalled = None, []
    before = cgroup.snapshot() if cgroup else None
    with (folder / "native.stdout.log").open("xb") as stdout:
        process = subprocess.Popen(
            argv, cwd=cwd, stdout=stdout, stderr=subprocess.STDOUT, shell=False
        )
        try:
            try:
                owned = OwnedProcessTree(process.pid, psutil_api)
            except psutil_api.Error:
                if process.poll() is None:
                    raise
                owned = None
            affinity = (
                affinity_evidence(owned.root)
                if owned is not None
                else {
                    "logical_ids": None,
                    "physical_cores": None,
                    "missing_reason": "worker_exited_before_process_admission",
                }
            )
            require(
                cgroup is None or cgroup.contains_pid(process.pid),
                "Worker is outside the admitted job cgroup",
            )
            while process.poll() is None:
                measurement = owned.sample()
                samples += 1
                observed = measurement["bytes"]
                if observed is not None:
                    maximum = observed if maximum is None else max(maximum, observed)
                job = cgroup.snapshot() if cgroup else None
                job_bytes = job["current_bytes"]["value"] if job else None
                if (folder / "native.stdout.log").stat().st_size > log_bytes:
                    guard = "observed_stdout_guard"
                elif time.perf_counter() - started >= wall_seconds:
                    guard = "external_wall_guard"
                elif (observed is not None and observed > memory_bytes) or (
                    job_bytes is not None and job_bytes > memory_bytes
                ):
                    guard = "observed_memory_guard"
                if guard:
                    signalled = owned.stop()
                    break
                time.sleep(interval)
            returncode = process.wait(timeout=10)
            if owned is not None and owned.sample(include_root=False)["live_processes"]:
                signalled.extend(owned.stop())
                guard = guard or "owned_descendants_survived_worker_return"
        except BaseException:
            if process.poll() is None:
                if "owned" in locals() and owned is not None:
                    owned.stop()
                else:
                    process.kill()  # Popen still owns this live child handle.
                process.wait(timeout=10)
            raise
    after = cgroup.snapshot() if cgroup else None
    result = {
        "schema_version": "mvp3-s1b-supervision-v1",
        "child_returncode": returncode,
        "guard": guard,
        "signalled_owned_pids": signalled,
        "external_wall_seconds": time.perf_counter() - started,
        "sample_count": samples,
        "sampled_process_peak_bytes": maximum,
        "process_memory_missing_reason": "no_readable_owned_process_sample"
        if maximum is None
        else None,
        "process_memory_scope": "sampled_owned_tree_RSS_sum_not_exact_peak",
        "affinity": affinity,
        "job_memory_before": before,
        "job_memory_after": after,
        "job_memory_missing_reason": None if cgroup else "no_qualified_job_cgroup",
        "native_memory_scope": "separate_native_callback_GB",
        "stdout_sha256": file_sha256(folder / "native.stdout.log"),
        "automatic_retry": False,
    }
    durable_json(folder / "supervisor-terminal.json", result)
    return result
