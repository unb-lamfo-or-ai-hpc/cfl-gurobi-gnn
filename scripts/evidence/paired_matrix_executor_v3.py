#!/usr/bin/env python3
"""Approval-bound two-parent serial executor. No scheduler submission interface.

Existing PR69/PR71/PR72 protocols and source pins are not modified.
SPDX-License-Identifier: MIT
"""

import argparse
import gzip
import io
import json
import os
import re
import signal
import sys
import tarfile
import time
from contextlib import ExitStack
from pathlib import Path

import isolated_attempt_worker as old
import paired_memory_runtime_v2 as memory
import pr78_scoped_evidence as evidence
import qualification_workflow as workflow

contract = old.contract
adapter = old.adapter
require = old.require
PROTOCOL = "paired_matrix_isolated_executor_v3"
PARENTS = ("easy", "medium")
AUDIT_SHA = "0c26533eb90b27b4e1115500997682af3d95713edd6197bc0f8d0a4eeb432eee"
SITE_SHA = "1f0cdb91c6abe628335265fa1a22059530d845789b84c4fd6ff6a3c9876f699f"
STOP_CODES = {
    "memory_guard_stop",
    "memory_observation_lost",
    "child_deadline_exceeded",
    "unexpected_process_group_survivor",
    "child_process_failed",
    "worker_or_resource_stop",
    "validation_failed",
    "parent_deadline_reserve",
}
MAX_PACKAGE = 100 * 1024 * 1024


def pins():
    return {
        **old.dependency_hashes(),
        **{
            n: adapter.screen.digest(Path(__file__).with_name(n))
            for n in (
                "paired_memory_guard.py",
                "paired_memory_guard_v2.py",
                "paired_memory_guard_v3.py",
                "paired_memory_runtime.py",
                "pr78_hierarchy_evidence.py",
                "paired_memory_runtime_v2.py",
                "pr78_scoped_evidence.py",
                "paired_matrix_executor_v3.py",
                "qualification_workflow.py",
            )
        },
    }


def reviewed_evidence():
    evidence.review(workflow.SOURCE)
    root = workflow.SOURCE / "docs/evidence"
    audit = old.read_bytes(root / "pr73/job3479/job3479_private_review.json")
    site = old.read_bytes(root / "pr74/job3479/current_slurm_resource_context.json")
    require(contract.sha(audit) == AUDIT_SHA and contract.sha(site) == SITE_SHA)
    value = old.strict_payload(audit)
    require(value["installed_callback_observation_supported"] is True)
    require(value["terminal_numeric_parity_supported"] is True)
    require(value["scientific_reporting_eligible"] is False)


def plan_for(head):
    old.hexadecimal(head, 40)
    proposal = contract.compile_proposal()
    value = {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "source_commit": head,
        "dependency_sha256": pins(),
        "proposal_sha256": proposal["proposal_sha256"],
        "installed_callback_audit_sha256": AUDIT_SHA,
        "current_site_receipt_sha256": SITE_SHA,
        "attempts": proposal["attempts"],
        "parent_order": list(PARENTS),
        "maximum_optimization_calls": 10,
        "optimization_limit_seconds_per_attempt": 3600,
        "child_deadline_seconds": 3780,
        "parent_deadline_seconds": 19800,
        "maximum_parent_blocks": 2,
        "scheduler_memory_mib": 65536,
        "physical_cores": 16,
        "concurrent_attempts": 1,
        "memory_policy": memory.POLICY,
        "memory_gate_protocol": memory.PROTOCOL,
        "installed_hierarchical_qualification_sha256": evidence.QUALIFICATION_SHA,
        "resource_budget_approved": False,
        "scientific_reporting_eligible": False,
        "historical_memory_reconciliation_required": False,
        "automatic_retry": False,
    }
    value["plan_sha256"] = contract.sha(contract.encoded(value))
    return value


def validate_plan(plan):
    require(isinstance(plan, dict) and plan == plan_for(plan["source_commit"]))
    old.strict_payload(contract.encoded(plan))


def rows_for(plan, parent):
    require(parent in PARENTS)
    rows = [r for r in plan["attempts"] if r["attempt_id"].startswith(parent + "-")]
    require(
        len(rows) == 5 and [r["within_parent_order"] for r in rows] == list(range(5))
    )
    return rows


def approval_template(plan):
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "plan_sha256": plan["plan_sha256"],
        "source_commit": plan["source_commit"],
        "maximum_optimization_calls": 10,
        "maximum_parent_blocks": 2,
        "maximum_optimization_seconds": 36000,
        "maximum_parent_wall_seconds": 19800,
        "exact_head_four_ci_arms_reviewed": False,
        "installed_no_solver_fault_probe_reviewed": False,
        "explicit_resource_budget_and_submission_approved": False,
        "scientific_reporting_eligible": False,
    }


def validate_approval(plan, approval, sha):
    old.hexadecimal(sha)
    require(contract.sha(contract.encoded(approval)) == sha)
    expected = approval_template(plan)
    for gate in (
        "exact_head_four_ci_arms_reviewed",
        "installed_no_solver_fault_probe_reviewed",
        "explicit_resource_budget_and_submission_approved",
    ):
        expected[gate] = True
    require(approval == expected)
    require(
        all(type(approval[k]) is bool for k in expected if type(expected[k]) is bool)
    )


def load_flow(directory, approval_sha=None):
    directory = Path(directory)
    plan = old.strict_payload(old.read_bytes(directory / "plan.json"))
    validate_plan(plan)
    if approval_sha is not None:
        approval = old.strict_payload(old.read_bytes(directory / "approval.json"))
        validate_approval(plan, approval, approval_sha)
    return plan


def prepare(directory):
    workflow.host()
    directory = workflow.location(directory)
    require(not directory.exists())
    reviewed_evidence()
    plan = plan_for(workflow.source_head())
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    old.write_json(directory / "plan.json", plan)
    old.write_json(directory / "approval.json", approval_template(plan))
    return plan


def execution_host(plan, directory):
    workflow.host()
    directory = workflow.location(directory)
    require(workflow.source_head() == plan["source_commit"])
    require(os.environ.get("SLURM_CPUS_PER_TASK") == "16")
    require(os.environ.get("SLURM_MEM_PER_NODE") == "65536")
    require(os.environ.get("SLURM_JOB_NUM_NODES") == "1")
    require(
        not os.environ.get("SLURM_JOB_GPUS") and not os.environ.get("SLURM_STEP_GPUS")
    )
    job = os.environ.get("SLURM_JOB_ID", "")
    require(re.fullmatch(r"[0-9]{1,20}", job) is not None)
    require(os.environ.get("SLURM_RESTART_COUNT", "0") == "0")
    reviewed_evidence()
    require(adapter.RAW_ROOT.resolve(strict=True) == adapter.RAW_ROOT)
    return directory, job


def claim_root(directory, plan, approval_sha, parent, job):
    root = adapter.EVIDENCE_ROOT / "paired-matrix-locks" / approval_sha
    require(root.resolve() == root)
    binding = {
        "plan_sha256": plan["plan_sha256"],
        "approval_sha256": approval_sha,
        "output_directory_sha256": contract.sha(str(directory).encode()),
    }
    if parent == "easy":
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
        old.write_json(root / "binding.json", binding)
    else:
        require(old.strict_payload(old.read_bytes(root / "binding.json")) == binding)
        prior = validate_parent_directory(
            directory / "easy", plan, approval_sha, "easy"
        )
        require(prior["complete_parent"] and prior["job_id"] != job)
    require(not (root / "STOP.json").exists())
    # A consumed parent claim never resumes after crash or partial output.
    with (root / (parent + ".started")).open("xb") as stream:
        stream.write(job.encode())
        stream.flush()
        os.fsync(stream.fileno())
    return root


def request_for(plan, approval_sha, row):
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "plan_sha256": plan["plan_sha256"],
        "approval_sha256": approval_sha,
        "source_commit": plan["source_commit"],
        "dependency_sha256": plan["dependency_sha256"],
        "attempt": row,
        "optimization_limit_seconds": 3600,
        "child_deadline_seconds": 3780,
        "maximum_optimization_calls": 1,
        "memory_policy": memory.POLICY,
        "scientific_reporting_eligible": False,
    }


def run_child(request, output, job):
    """New longer-budget protocol; reuse unmodified callback and validators."""
    row = request["attempt"]
    proposal = contract.compile_proposal()
    gate = memory.MemoryGate(job)
    affinity = adapter.screen.qualify_affinity()
    original = next(
        r
        for r in json.loads(contract.original.public_receipts()["pilot_plan.json"])[
            "models"
        ]
        if r["source_instance_id"] == row["source_instance_id"]
    )
    source = adapter.screen.frozen_source(adapter.RAW_ROOT, original)
    telemetry = contract.Telemetry(3600, row["stopping_gap_relative"])
    phases = contract.Telemetry(3600, row["stopping_gap_relative"])
    value = {
        "request_sha256": contract.sha(contract.encoded(request)),
        "optimization_calls": 0,
        "failure_code": None,
        "result": None,
        "effective_parameters": None,
        "algorithm_defaults": None,
        "original_lp_unchanged": False,
        "gurobi_log": None,
        "affinity": affinity,
        "job_id": job,
        "memory_gate": gate.public(),
        "peak_rss_bytes": None,
        "current_process_cpu_seconds": None,
        "phases": [],
    }
    log = output / "gurobi.private.log"
    stack, stage = ExitStack(), "read_setup"
    try:
        with phases.phase("read_setup"):
            gp = adapter.screen.licensed_runtime(proposal["controls"])
            env = stack.enter_context(gp.Env(empty=True))
            env.setParam("OutputFlag", 0)
            env.setParam("ThreadLimit", 16)
            env.start()
            model = stack.enter_context(gp.read(str(source), env=env))
            config = adapter.source_config(proposal, row)
            parameters, defaults = adapter.screen.configure_model(
                model, config, row["threads"], log
            )
            adapter.screen.prepare_original_model(model, config)
            require(parameters == old.expected_parameters(request, row))
            require(
                defaults
                == {
                    n: {"effective": v, "version_default": v}
                    for n, v in old.DEFAULTS.items()
                }
            )
            value.update(effective_parameters=parameters, algorithm_defaults=defaults)
            callback = adapter.GurobiCallbackAdapter(gp, telemetry)
            require(gate.sample() < memory.POLICY["cgroup_interrupt_bytes"])
        stage = "optimization"
        with phases.phase("optimization"):
            value["optimization_calls"] = 1
            model.optimize(callback)
        stage = "terminal_inspection"
        value["result"] = callback.finish_model(model)
    except Exception:
        value["failure_code"] = "worker_" + stage + "_failed"
    finally:
        try:
            with phases.phase("cleanup"):
                stack.close()
        except Exception:
            value["failure_code"] = "worker_cleanup_failed"
    if value["failure_code"] != "worker_cleanup_failed" and log.exists():
        try:
            value["gurobi_log"] = contract.seal_closed_log(log)
        except Exception:
            value["failure_code"] = "worker_log_seal_failed"
    value["original_lp_unchanged"] = (
        adapter.screen.digest(source) == row["original_lp_sha256"]
    )
    if not value["original_lp_unchanged"]:
        value["failure_code"] = "worker_source_changed"
    import resource

    value["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    value["current_process_cpu_seconds"] = time.process_time()
    value["phases"] = list(phases.phases)
    if value["result"] is not None:
        value["result"]["phases"] = value["phases"]
    validate_child(value, request, job)
    old.write_json(output / "child.private.json", value)


def validate_gate(value):
    memory.validate_public(value)


def validate_child(value, request, job):
    old.keys(
        value,
        "request_sha256 optimization_calls failure_code result effective_parameters algorithm_defaults original_lp_unchanged gurobi_log affinity job_id memory_gate peak_rss_bytes current_process_cpu_seconds phases",
    )
    require(value["request_sha256"] == contract.sha(contract.encoded(request)))
    require(value["job_id"] == job)
    validate_gate(value["memory_gate"])
    calls = old.integer(value["optimization_calls"], 0, 1)
    require(
        value["failure_code"]
        in {
            None,
            "worker_read_setup_failed",
            "worker_optimization_failed",
            "worker_terminal_inspection_failed",
            "worker_cleanup_failed",
            "worker_log_seal_failed",
            "worker_source_changed",
        }
    )
    require(type(value["original_lp_unchanged"]) is bool)
    affinity = value["affinity"]
    old.keys(affinity, "observed_cpu_ids bound_cpu_ids physical_cores")
    require(old.integer(affinity["physical_cores"]) == 16)
    for name in ("observed_cpu_ids", "bound_cpu_ids"):
        ids = affinity[name]
        require(isinstance(ids, list) and ids == sorted(set(ids)))
        for cpu in ids:
            old.integer(cpu)
    require(
        len(affinity["bound_cpu_ids"]) == 16
        and set(affinity["bound_cpu_ids"]) <= set(affinity["observed_cpu_ids"])
    )
    old.integer(value["peak_rss_bytes"])
    contract.number(value["current_process_cpu_seconds"])
    old.validate_phases(value["phases"])
    require(
        sum(p["process_cpu_seconds"] for p in value["phases"])
        <= value["current_process_cpu_seconds"] + 1e-9
    )
    if value["effective_parameters"] is None:
        require(value["algorithm_defaults"] is None and calls == 0)
    else:
        require(
            value["effective_parameters"]
            == old.expected_parameters(request, request["attempt"])
        )
        require(
            value["algorithm_defaults"]
            == {
                n: {"effective": v, "version_default": v}
                for n, v in old.DEFAULTS.items()
            }
        )
    if value["gurobi_log"] is not None:
        old.log_binding(value["gurobi_log"])
    if value["result"] is not None:
        require(calls == 1)
        old.validate_result(value["result"], request, request["attempt"])
        require(value["result"]["phases"] == value["phases"])
    if value["failure_code"] is None:
        require(
            calls == 1
            and value["original_lp_unchanged"]
            and value["result"] is not None
            and value["gurobi_log"] is not None
        )
        require(
            [p["phase"] for p in value["phases"]]
            == ["read_setup", "optimization", "cleanup"]
        )
        require(not any(p["call_failed"] for p in value["phases"]))
    old.strict_payload(contract.encoded(value))


def internal_child(output, request_sha):
    output = Path(output)
    flow, parent = output.parents[1], output.parent.name
    raw = old.read_bytes(output / "request.json")
    require(contract.sha(raw) == request_sha)
    request = old.strict_payload(raw)
    plan = load_flow(flow, request["approval_sha256"])
    _, job = execution_host(plan, flow)
    row = next(r for r in rows_for(plan, parent) if r["attempt_id"] == output.name)
    require(request == request_for(plan, request["approval_sha256"], row))
    root = adapter.EVIDENCE_ROOT / "paired-matrix-locks" / request["approval_sha256"]
    require(old.read_bytes(root / (parent + ".started"), 64) == job.encode())
    require(
        old.strict_payload(old.read_bytes(root / "binding.json"))[
            "output_directory_sha256"
        ]
        == contract.sha(str(flow).encode())
    )
    require(not (root / "STOP.json").exists())
    with (output / "child.started").open("xb") as stream:
        stream.write(request_sha.encode())
    run_child(request, output, job)


def execute_attempt(request, output, job, *, child_module="paired_matrix_executor_v3"):
    require(child_module in {"paired_matrix_executor_v3", "pr78_medium_workflow"})
    gate = memory.MemoryGate(job)
    initial_gate = gate.public()
    output.mkdir(mode=0o700, exist_ok=False)
    old.write_json(output / "request.json", request)
    command = [
        sys.executable,
        "-B",
        "-c",
        "import sys;sys.path.insert(0,sys.argv[1]);import "
        + child_module
        + " as m;m.internal_child(*sys.argv[2:])",
        str(Path(__file__).parent),
        str(output),
        contract.sha(contract.encoded(request)),
    ]
    guard = memory.supervise(command, output / "console.private.log", 3780, gate)
    receipt = {
        "schema_version": 1,
        "request_sha256": contract.sha(contract.encoded(request)),
        "job_id": job,
        "guard": guard,
        "memory_gate": initial_gate,
        "child": None,
        "child_report_sha256": None,
        "console_log": contract.seal_closed_log(output / "console.private.log"),
        "stop_code": guard["guard_stop"] or "child_process_failed",
        "pause_remaining_matrix": True,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
    }
    if guard["guard_stop"] is None and guard["child_exit_code"] == 0:
        try:
            raw = old.read_bytes(output / "child.private.json")
            child = old.strict_payload(raw)
            validate_child(child, request, job)
            if child["gurobi_log"] is not None:
                require(
                    contract.seal_closed_log(output / "gurobi.private.log")
                    == child["gurobi_log"]
                )
            safe = child["failure_code"] is None and child["result"]["stop"] in {
                "gap_target",
                "time_limit",
            }
            receipt.update(
                child=child,
                child_report_sha256=contract.sha(raw),
                stop_code=None if safe else "worker_or_resource_stop",
                pause_remaining_matrix=not safe,
            )
        except Exception:
            receipt["stop_code"] = "validation_failed"
    validate_attempt(receipt, request, job)
    old.write_json(output / "attempt_receipt.json", receipt)
    return receipt


def validate_attempt(receipt, request, job):
    old.keys(
        receipt,
        "schema_version request_sha256 job_id guard memory_gate child child_report_sha256 console_log stop_code pause_remaining_matrix raw_logs_included scientific_reporting_eligible",
    )
    require(old.integer(receipt["schema_version"]) == 1 and receipt["job_id"] == job)
    require(receipt["request_sha256"] == contract.sha(contract.encoded(request)))
    validate_gate(receipt["memory_gate"])
    old.log_binding(receipt["console_log"])
    guard = receipt["guard"]
    old.keys(
        guard,
        "child_exit_code guard_stop sampled_cgroup_peak_bytes supervisor_wall_seconds peak_is_sampled_not_exact memory_failure_diagnostic",
    )
    require(
        type(guard["child_exit_code"]) is int
        and guard["peak_is_sampled_not_exact"] is True
    )
    require(guard["guard_stop"] is None or guard["guard_stop"] in STOP_CODES)
    memory.validate_diagnostic(guard["memory_failure_diagnostic"], guard["guard_stop"])
    old.integer(guard["sampled_cgroup_peak_bytes"])
    contract.number(guard["supervisor_wall_seconds"])
    require(
        receipt["raw_logs_included"] is False
        and receipt["scientific_reporting_eligible"] is False
    )
    require(receipt["stop_code"] is None or receipt["stop_code"] in STOP_CODES)
    require(type(receipt["pause_remaining_matrix"]) is bool)
    require(receipt["pause_remaining_matrix"] == (receipt["stop_code"] is not None))
    if receipt["child"] is not None:
        require(guard["child_exit_code"] == 0 and guard["guard_stop"] is None)
        child = receipt["child"]
        validate_child(child, request, job)
        require(receipt["child_report_sha256"] == contract.sha(contract.encoded(child)))
        safe = child["failure_code"] is None and child["result"]["stop"] in {
            "gap_target",
            "time_limit",
        }
        require(receipt["stop_code"] == (None if safe else "worker_or_resource_stop"))
    else:
        require(
            receipt["child_report_sha256"] is None and receipt["pause_remaining_matrix"]
        )
    if guard["guard_stop"] is not None:
        require(
            receipt["stop_code"] == guard["guard_stop"] and receipt["child"] is None
        )
    old.strict_payload(contract.encoded(receipt))


def parent_report(plan, approval_sha, parent, job, attempts, stop):
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "plan_sha256": plan["plan_sha256"],
        "approval_sha256": approval_sha,
        "parent": parent,
        "job_id": job,
        "attempt_receipt_sha256": attempts,
        "complete_parent": len(attempts) == 5 and stop is None,
        "stop_code": stop,
        "pause_remaining_matrix": stop is not None,
        "automatic_retry": False,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
    }


def run_parent(directory, approval_sha, parent):
    plan = load_flow(directory, approval_sha)
    directory, job = execution_host(plan, directory)
    memory.MemoryGate(job)  # No claim or model read if kernel RAM bound is absent.
    adapter.screen.qualify_affinity()
    root = claim_root(directory, plan, approval_sha, parent, job)
    output = directory / parent
    output.mkdir(mode=0o700, exist_ok=False)
    started, receipts, stop = time.monotonic(), {}, None
    previous_handler = signal.getsignal(signal.SIGTERM)

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("batch_termination")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        for row in rows_for(plan, parent):
            if time.monotonic() - started + 3780 + 20 > 19800:
                stop = "parent_deadline_reserve"
                break
            receipt = execute_attempt(
                request_for(plan, approval_sha, row), output / row["attempt_id"], job
            )
            receipts[row["attempt_id"]] = contract.sha(contract.encoded(receipt))
            if receipt["pause_remaining_matrix"]:
                stop = receipt["stop_code"]
                break
    except BaseException:
        stop = "validation_failed"
        if not (root / "STOP.json").exists():
            old.write_json(root / "STOP.json", {"stop_code": stop})
        raise
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
    if stop is not None:
        old.write_json(root / "STOP.json", {"stop_code": stop})
    report = parent_report(plan, approval_sha, parent, job, receipts, stop)
    old.write_json(output / "parent_receipt.json", report)
    validate_parent_directory(output, plan, approval_sha, parent)
    return report


def validate_parent_directory(
    output, plan, approval_sha, parent, reader=old.read_bytes
):
    report = old.strict_payload(reader(Path(output) / "parent_receipt.json"))
    require(re.fullmatch(r"[0-9]{1,20}", report["job_id"]) is not None)
    receipts = report["attempt_receipt_sha256"]
    require(isinstance(receipts, dict))
    require(len(receipts) <= 5)
    rows = rows_for(plan, parent)
    require(
        list(receipts) == sorted(receipts)
    )  # Canonical JSON map order, not run order.
    expected_ids = {r["attempt_id"] for r in rows[: len(receipts)]}
    require(set(receipts) == expected_ids)
    stop = report["stop_code"]
    require(stop is None or stop in STOP_CODES)
    require(
        report
        == parent_report(plan, approval_sha, parent, report["job_id"], receipts, stop)
    )
    for index, row in enumerate(rows[: len(receipts)]):
        attempt = Path(output) / row["attempt_id"]
        request = old.strict_payload(reader(attempt / "request.json"))
        require(request == request_for(plan, approval_sha, row))
        raw = reader(attempt / "attempt_receipt.json")
        require(contract.sha(raw) == receipts[row["attempt_id"]])
        receipt = old.strict_payload(raw)
        validate_attempt(receipt, request, report["job_id"])
        if receipt["pause_remaining_matrix"]:
            require(index == len(receipts) - 1 and stop == receipt["stop_code"])
        else:
            require(
                index < len(receipts) - 1 or stop in {None, "parent_deadline_reserve"}
            )
    require(len(receipts) == 5 or stop is not None)
    return report


def export_parent(directory, approval_sha, parent, destination):
    plan = load_flow(directory, approval_sha)
    output = Path(directory) / parent
    report = validate_parent_directory(output, plan, approval_sha, parent)
    names = ["plan.json", "approval.json", parent + "/parent_receipt.json"]
    for row in rows_for(plan, parent):
        if row["attempt_id"] in report["attempt_receipt_sha256"]:
            # Rebind both closed logs at export, without exporting their text.
            attempt = output / row["attempt_id"]
            receipt = old.strict_payload(
                old.read_bytes(attempt / "attempt_receipt.json")
            )
            require(
                contract.seal_closed_log(attempt / "console.private.log")
                == receipt["console_log"]
            )
            if (
                receipt["child"] is not None
                and receipt["child"]["gurobi_log"] is not None
            ):
                require(
                    contract.seal_closed_log(attempt / "gurobi.private.log")
                    == receipt["child"]["gurobi_log"]
                )
            for name in ("request.json", "attempt_receipt.json"):
                names.append(parent + "/" + row["attempt_id"] + "/" + name)
    payloads = {n: old.read_bytes(Path(directory) / n) for n in names}
    payloads["SHA256SUMS.txt"] = "".join(
        contract.sha(payloads[n]) + "  " + n + "\n" for n in sorted(names)
    ).encode()
    require(sum(map(len, payloads.values())) <= MAX_PACKAGE)
    with (
        Path(destination).open("xb") as stream,
        tarfile.open(fileobj=stream, mode="w:gz") as archive,
    ):
        for name, raw in sorted(payloads.items()):
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = len(raw), 0o600, 0
            archive.addfile(member, io.BytesIO(raw))
    return adapter.screen.digest(destination)


def validate_package(package, expected_sha):
    """Bounded in-memory inspection; never extract untrusted archive paths."""
    raw = old.read_bytes(package, MAX_PACKAGE)
    require(contract.sha(raw) == expected_sha)
    payloads, total = {}, 0
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        decoded = stream.read(MAX_PACKAGE + 65537)
    require(len(decoded) <= MAX_PACKAGE + 65536)
    end = 0
    with tarfile.open(fileobj=io.BytesIO(decoded), mode="r:") as archive:
        for member in archive:
            require(
                member.isfile() and member.name not in payloads and len(payloads) < 14
            )
            require(not member.sparse and not member.pax_headers)
            require(0 <= member.size <= old.MAX_JSON)
            require(
                member.name in {"plan.json", "approval.json", "SHA256SUMS.txt"}
                or re.fullmatch(
                    r"(?:easy|medium)/(?:parent_receipt\.json|(?:easy|medium)-seed42-threads(?:1|2|4|8|16)/(?:request|attempt_receipt)\.json)",
                    member.name,
                )
            )
            total += member.size
            require(total <= MAX_PACKAGE)
            stream = archive.extractfile(member)
            require(stream is not None)
            payloads[member.name] = stream.read(member.size + 1)
            require(len(payloads[member.name]) == member.size)
            end = member.offset_data + ((member.size + 511) // 512) * 512
    require(len(decoded) >= end + 1024 and not any(decoded[end:]))
    names = sorted(n for n in payloads if n != "SHA256SUMS.txt")
    manifest = "".join(
        contract.sha(payloads[n]) + "  " + n + "\n" for n in names
    ).encode()
    require(payloads.get("SHA256SUMS.txt") == manifest)
    plan = old.strict_payload(payloads["plan.json"])
    validate_plan(plan)
    approval = old.strict_payload(payloads["approval.json"])
    approval_sha = contract.sha(payloads["approval.json"])
    validate_approval(plan, approval, approval_sha)
    parents = [p for p in PARENTS if p + "/parent_receipt.json" in payloads]
    require(len(parents) == 1)
    parent = parents[0]
    report = validate_parent_directory(
        parent, plan, approval_sha, parent, lambda p: payloads[p.as_posix()]
    )
    expected = {
        "plan.json",
        "approval.json",
        "SHA256SUMS.txt",
        parent + "/parent_receipt.json",
    }
    expected.update(
        parent + "/" + attempt + "/" + n
        for attempt in report["attempt_receipt_sha256"]
        for n in ("request.json", "attempt_receipt.json")
    )
    require(set(payloads) == expected)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "run-parent", "export-parent", "validate-package")
    )
    parser.add_argument("--directory")
    parser.add_argument("--approval-sha")
    parser.add_argument("--parent", choices=PARENTS)
    parser.add_argument("--output")
    parser.add_argument("--package")
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    if args.action == "validate-package":
        require(
            args.package is not None
            and args.expected_sha is not None
            and args.directory is None
        )
        value = validate_package(args.package, args.expected_sha)
    elif args.action == "prepare":
        require(args.directory is not None)
        require(
            args.approval_sha is None and args.parent is None and args.output is None
        )
        value = prepare(args.directory)
    else:
        require(
            args.directory is not None
            and args.approval_sha is not None
            and args.parent is not None
        )
        if args.action == "run-parent":
            require(args.output is None)
            value = run_parent(args.directory, args.approval_sha, args.parent)
        else:
            require(args.output is not None)
            value = {
                "package_sha256": export_parent(
                    args.directory, args.approval_sha, args.parent, args.output
                )
            }
    print(json.dumps(value, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("PR75_EXECUTOR_REJECTED_PRESERVE_EVIDENCE_NO_RETRY", file=sys.stderr)
        sys.exit(1)
