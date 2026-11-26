"""Prospective one-call compute-node probe, guarded by actual allocation facts."""

import os
import platform
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from ..audit import AuditPolicy, audit_point
from ..contract import digest, load_json, require
from ..identity import model_identity
from ..journal import AttemptStore, durable_json, file_sha256, read_vector
from ..matrix import NativeMatrix, streamed_identity
from ..native import parameter_inventory
from ..observer import NativeObserver, available
from ..qualification import TINY_LP, safe_worker_error
from .allocation import cgroup_memory, live_allocation
from .collection import tiny_geometry
from .inventory import bounded_read
from .planning import load_plan
from .policy import ascii_path, technical_parameters


def task_ticks(proc="/proc/self/task"):
    result, missing = {}, 0
    for path in Path(proc).glob("*/stat"):
        try:
            text = path.read_text()
            fields = text[text.rfind(")") + 2 :].split()
            result[path.parent.name] = int(fields[11]) + int(fields[12])
        except (OSError, ValueError, IndexError):
            missing += 1
    return {
        "ticks": result,
        "unreadable_tasks": missing,
        "scope": "sampled_task_CPU_jiffies_not_peak_thread_activity",
    }


def admission(plan, profile, runner=bounded_read):
    require(platform.system() == "Linux", "Compute qualification is Linux/Slurm only")
    require(
        Path(sys.executable).absolute() == Path(plan["python"]).absolute()
        and Path(sys.prefix).absolute() == Path(plan["python_prefix"]).absolute(),
        "Compute interpreter differs from the reviewed target",
    )
    result = live_allocation(profile, runner)
    fields = result["scheduler_fields"]
    slot = plan["slots"][profile]
    extra = {
        "reviewed_node": fields["NodeList"] == slot["node"],
        "reviewed_partition": fields["Partition"] == plan["partition"],
        "reviewed_account": fields["Account"] == plan["account"],
        "reviewed_qos": fields["QOS"] == plan["qos"],
        "five_minute_job": fields["TimeLimit"] == "00:05:00",
        "not_restarted": fields["Restarts"] == "0",
    }
    result["checks"].update(extra)
    result["allocation_qualified"] = all(result["checks"].values())
    return result


def probe(plan, profile, source_commit, *, api=None):
    """No primary model path exists in this interface; exactly one tiny optimize."""
    folder = ascii_path(plan["slots"][profile]["output"])
    allocation = admission(plan, profile)
    require(
        allocation["allocation_qualified"],
        "Actual allocation differs from the reviewed envelope",
    )
    require(
        (folder / "worker-admission.json").is_file(), "Owning worker admission missing"
    )
    parent = load_json(folder / "worker-admission.json")
    require(
        parent["source_commit"] == source_commit
        and parent["plan_identity_sha256"] == digest(plan)
        and parent["job_id"] == os.environ["SLURM_JOB_ID"],
        "Parent/child admission binding mismatch",
    )
    license_file = ascii_path(plan["license_file"])
    require(license_file.is_file(), "Own-project license path unavailable")
    os.environ["GRB_LICENSE_FILE"] = str(license_file)
    input_path = folder / "technical-fixture.lp"
    with input_path.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(TINY_LP)
    binding = {
        "source_commit": source_commit,
        "mode": "production_qualification",
        "plan_identity_sha256": digest(plan),
        "job_id": os.environ["SLURM_JOB_ID"],
        "input_sha256": file_sha256(input_path),
        "key": {
            "parent_id": "QUAL_PRODUCTION_TINY20",
            "stage": "root_relaxation",
            "method": None,
            "seed": 42,
            "attempt": plan["slots"][profile]["attempt"],
        },
    }
    store = AttemptStore(
        folder / "attempt",
        binding,
        event_limit=1000,
        artifact_bytes_limit=8 * 1024 * 1024,
        candidate_limit=16,
    )
    environment = model = None
    phase, outcome = "API_import", "probe_failure"
    try:
        if api is None:
            import gurobipy as api
        require(
            tuple(api.gurobi.version()) == (14, 0, 0),
            "Actual native Gurobi14.0.0 required",
        )
        phase = "environment_start"
        environment = api.Env(empty=True)
        environment.start()
        phase = "original_model_read"
        model = api.read(str(input_path), env=environment)
        declared = {1: "MINIMIZE", -1: "MAXIMIZE"}[model.ModelSense]
        model.ModelSense = api.GRB.MINIMIZE
        model.update()
        require(
            model.SolCount == 0 and model.NumStart == 0, "Probe is not a fresh model"
        )
        parameters = technical_parameters()
        phase = "native_parameters"
        for name, value in parameters.items():
            model.setParam(name, value)
        matrix = NativeMatrix(model, declared, api.GRB.INFINITY)
        identity = streamed_identity(matrix)
        require(
            identity == model_identity(tiny_geometry()),
            "Unexpected synthetic model geometry",
        )
        inventory = parameter_inventory(api, model)
        require(
            inventory["effective"] == {**inventory["defaults"], **parameters},
            "Undeclared parameter drift",
        )
        store.reserve_final_vectors(len(matrix.variables))
        require(
            store.append(
                {
                    "kind": "native_admission",
                    "identity": identity,
                    "parameter_inventory": inventory,
                },
                critical=True,
            )
            is not None,
            "Native admission was not retained",
        )
        observer = NativeObserver(api, matrix, store, "root_relaxation")
        before = task_ticks()
        phase = "durable_optimize_intent"
        store.optimize_intent(plan["approval_reference"])
        phase = "native_optimize"
        started = time.perf_counter()
        model.optimize(observer)
        wall = time.perf_counter() - started
        store.native_returned(int(model.Status))
        phase = "audit_after_return"
        require(
            streamed_identity(NativeMatrix(model, declared, api.GRB.INFINITY))
            == identity,
            "Original mathematical model drifted",
        )
        require(
            file_sha256(input_path) == binding["input_sha256"], "Probe bytes changed"
        )
        root = None
        if observer.captured_root:
            root = audit_point(
                matrix,
                read_vector(store.folder, observer.captured_root["root_vector"]),
                AuditPolicy(),
                continuous=True,
                identity=identity,
            )
            root.pop("vector", None)
        result = {
            "schema_version": "mvp3-s1b-native-v1",
            "binding_sha256": store.binding_sha256,
            "identity": identity,
            "parameters": inventory,
            "native": {
                "gurobi_version": list(api.gurobi.version()),
                "python_executable": str(Path(sys.executable).absolute()),
                "python_prefix": sys.prefix,
                "python_version": platform.python_version(),
                "kernel_release": platform.release(),
                "native_status": int(model.Status),
                "native_runtime": available(float(model.Runtime)),
                "native_Work": available(float(model.Work)),
                "optimize_external_wall_seconds": wall,
                "observer": observer.summary(),
            },
            "root_audit": root,
            "final_audit": None,
            "call_returned": True,
            "scientific_population": "production_qualification",
            "CPU_activity_before": before,
            "CPU_activity_after": task_ticks(),
            "job_memory_after": cgroup_memory(binding["job_id"]),
        }
        durable_json(store.folder / "native-result.json", result)
        require(
            observer.failure is None
            and root is not None
            and root["status"] == "qualified",
            "Missing independently audited optimal root capture",
        )
        headers = [
            re.search(
                r"Thread count: (\d+) physical cores, (\d+) logical processors, using up to (\d+) threads",
                line,
            )
            for line in observer.native_thread_lines
        ]
        require(
            any(
                match and tuple(map(int, match.groups())) == (32, 64, 32)
                for match in headers
            ),
            "Native automatic-thread header does not match Intel32/64 soft ceiling32",
        )
        outcome = "qualified_tiny_production_probe_pending_scheduler_return"
        return result
    except Exception as error:
        durable_json(
            store.folder / "worker-error.json",
            safe_worker_error(error, phase, store.binding_sha256),
        )
        raise
    finally:
        try:
            if model is not None:
                model.dispose()
        finally:
            if environment is not None:
                environment.dispose()
            store.close(outcome)


def worker(bundle, manifest, manifest_sha256, plan_path, plan_sha256, profile):
    plan = load_plan(
        plan_path, plan_sha256, manifest, bundle=bundle, manifest_sha256=manifest_sha256
    )
    folder = ascii_path(plan["slots"][profile]["output"])
    folder.mkdir(parents=True, exist_ok=False)
    phase = "allocation_admission"
    try:
        observed = admission(plan, profile)
        durable_json(folder / "allocation.json", observed)
        require(
            observed["allocation_qualified"],
            "Allocation qualification failed before native initialization",
        )
        durable_json(
            folder / "worker-admission.json",
            {
                "source_commit": manifest["source_commit"],
                "plan_identity_sha256": digest(plan),
                "job_id": os.environ["SLURM_JOB_ID"],
                "maximum_optimize_calls": 1,
                "other_Gurobi_sessions_scope": "author_attestation_required_not_globally_machine_observed",
            },
        )
        phase = "owned_probe_process"
        argv = [
            sys.executable,
            "-B",
            str(Path(bundle) / "scripts/mvp3/qualify_production.py"),
            "--bundle",
            str(bundle),
            "--manifest-sha256",
            manifest_sha256,
            "probe",
            "--plan",
            str(plan_path),
            "--plan-sha256",
            plan_sha256,
            "--profile",
            profile,
        ]
        with (folder / "native.stdout.log").open("xb") as output:
            child = subprocess.Popen(
                argv,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                shell=False,
            )
            start = time.perf_counter()
            guard = None
            try:
                while child.poll() is None:
                    if time.perf_counter() - start > 60:
                        guard = "external_wall_guard"
                    elif (
                        folder / "native.stdout.log"
                    ).stat().st_size > 16 * 1024 * 1024:
                        guard = "observed_stdout_guard"
                    if guard:
                        # Unreaped owned child PID cannot be reused by an unrelated group.
                        os.killpg(child.pid, signal.SIGKILL)
                        break
                    time.sleep(0.1)
                code = child.wait(timeout=10)
            except BaseException:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=10)
                raise
        terminal = {
            "source_commit": manifest["source_commit"],
            "plan_identity_sha256": digest(plan),
            "profile": profile,
            "job_id": os.environ["SLURM_JOB_ID"],
            "child_returncode": code,
            "guard": guard,
            "stdout_sha256": file_sha256(folder / "native.stdout.log"),
            "last_live_job_memory": cgroup_memory(os.environ["SLURM_JOB_ID"]),
            "last_live_job_memory_scope": "kernel_job_peak_before_worker_exit_not_post_teardown_accounting",
            "admission_receipts": {
                name: file_sha256(folder / name)
                for name in ("allocation.json", "worker-admission.json")
            },
            "automatic_retry": False,
            "scheduler_terminal_state": None,
            "scheduler_missing_reason": "collect_after_actual_job_terminal_accounting",
            "scientific_release": False,
        }
        durable_json(folder / "worker-terminal.json", terminal)
        require(code == 0 and guard is None, "Owned probe did not complete cleanly")
        return terminal
    except Exception as error:
        durable_json(
            folder / "admission-error.json",
            {
                "phase": phase,
                "exception_type": type(error).__name__,
                "message_copied": False,
                "automatic_retry": False,
            },
        )
        raise
