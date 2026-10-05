"""Read-only artifact/attempt/job registry; no historical execution inference.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

import collect_pr66_log_phases as phases
from collect_computational_ledger import identity
from pr66_reconciliation import provenance, seconds
from publish_mvp2_baseline import PRIVATE
from verify_pr65_recovery import RECOVERY_SHA256, load_json, read_package, rows

ACCOUNTING_SHA = "420354974a6269891bc467529104227d8ba0715e54c767d7866cde10c313fa89"
MAX_BYTES = 16 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_id(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def historical_observations(records, ledger_sha):
    """PR65's path-derived attempt_id is an artifact observation, not a run ID."""
    provenance(ledger_sha)
    result, seen = [], set()
    for row in records:
        observation = provenance(row["attempt_id"])
        report = provenance(row["report_sha256"])
        if observation in seen or not identity(row["source_instance_id"]):
            raise ValueError("duplicate_or_invalid_observation")
        if row["solver"] not in {"gurobi", "scip"}:
            raise ValueError("unsupported_solver")
        seen.add(observation)
        result.append(
            {
                "observation_id": observation,
                "report_sha256": report,
                "ledger_sha256": ledger_sha,
                "source_instance_id": row["source_instance_id"],
                "solver": row["solver"],
                "execution_id": None,
                "join_state": "unmatched",
                "join_reason": "no_explicit_execution_job_binding",
                "unique_feasible_incumbents": None,
            }
        )
    return sorted(result, key=lambda row: row["observation_id"])


def aliases(observations):
    groups = {}
    for row in observations:
        groups.setdefault(row["report_sha256"], []).append(row["observation_id"])
    return [
        {
            "report_sha256": digest,
            "observation_ids": sorted(ids),
            "execution_equivalence_qualified": False,
        }
        for digest, ids in sorted(groups.items())
    ]


def join_claim(subject, claim, allocations):
    """Match explicit, reviewed projections within an accounting snapshot only.

    Hash-shaped strings alone are not authenticity certificates; callers must
    validate the source bytes. A cluster/job number without snapshot evidence
    does not identify a globally unique Slurm allocation.
    """
    provenance(subject["report_sha256"])
    base = {
        "subject_id": provenance(subject["subject_id"]),
        "allocation_observation_id": None,
        "join_state": "unmatched",
        "reason": "missing_explicit_binding",
    }
    if claim is None:
        return base
    required = ("subject_id", "report_sha256", "accounting_sha256", "cluster", "job_id")
    if any(claim.get(key) is None for key in required):
        return base
    for key in ("subject_id", "report_sha256", "accounting_sha256"):
        provenance(claim[key])
    if (
        claim["subject_id"] != base["subject_id"]
        or claim["report_sha256"] != subject["report_sha256"]
    ):
        return {**base, "reason": "subject_or_report_mismatch"}
    if not re.fullmatch(r"\d+(?:_\d+)?", claim["job_id"]):
        return {**base, "reason": "concrete_allocation_not_step_required"}
    seen = set()
    candidates = []
    for row in allocations:
        allocation = provenance(row["allocation_observation_id"])
        if allocation in seen:
            raise ValueError("duplicate_allocation_observation")
        seen.add(allocation)
        if all(
            row[key] == claim[key] for key in ("accounting_sha256", "cluster", "job_id")
        ):
            candidates.append(allocation)
    if not candidates:
        return {**base, "reason": "allocation_snapshot_not_found"}
    if len(candidates) > 1:
        return {
            **base,
            "join_state": "ambiguous",
            "reason": "multiple_allocation_candidates",
        }
    return {
        **base,
        "allocation_observation_id": candidates[0],
        "join_state": "matched",
        "reason": "explicit_binding_within_reviewed_snapshot",
    }


def accounting_projection(data):
    """Allowlisted operator-returned snapshot, not a new sacct query."""
    if sha(data) != ACCOUNTING_SHA:
        raise ValueError("reviewed_accounting_bytes_changed")
    reader = csv.DictReader(io.StringIO(data.decode("ascii")), delimiter="|")
    expected = [
        "JobID",
        "State",
        "ExitCode",
        "Elapsed",
        "ElapsedRaw",
        "TotalCPU",
        "AllocCPUS",
        "ReqMem",
        "MaxRSS",
    ]
    if reader.fieldnames != expected:
        raise ValueError("unsupported_accounting_columns")
    records = list(reader)
    if any(None in row or None in row.values() for row in records):
        raise ValueError("ragged_accounting")
    if [r["JobID"] for r in records] != ["3468", "3468.batch", "3468.extern", "3468.0"]:
        raise ValueError("accounting_membership_changed")
    parent = records[0]
    if parent["State"] != "COMPLETED" or parent["ExitCode"] != "0:0":
        raise ValueError("terminal_accounting_changed")
    cpus, elapsed = int(parent["AllocCPUS"]), int(parent["ElapsedRaw"])
    if (cpus, elapsed) != (32, 1794):
        raise ValueError("reviewed_allocation_resources_changed")
    return {
        "allocation_observation_id": canonical_id(
            ["dgx-dasci", ACCOUNTING_SHA, "3468"]
        ),
        "cluster": "dgx-dasci",
        "cluster_identity_scope": "declared_plan_and_operator_context",
        "job_id": "3468",
        "accounting_sha256": ACCOUNTING_SHA,
        "state": "COMPLETED",
        "elapsed_seconds": elapsed,
        "allocated_logical_cpus": cpus,
        "reported_cpu_seconds": seconds(parent["TotalCPU"]),
        "allocated_logical_cpu_hours": cpus * elapsed / 3600,
        "reported_cpu_hours": seconds(parent["TotalCPU"]) / 3600,
        "child_step_rows_not_added": len(records) - 1,
        "globally_unique_allocation_identity_qualified": False,
        "phase_costs_qualified": False,
    }


def pilot_registry(payloads, allocation):
    plan = load_json(payloads["pilot_plan.json"])
    execution = load_json(payloads["pilot_execution_report.json"])
    if (
        plan["config"]["cluster"] != "dgx-dasci"
        or execution["plan_sha256"] != phases.PLAN_SHA
    ):
        raise ValueError("pilot_plan_or_cluster_changed")
    if [r["attempt"] for r in execution["executions"]] != phases.NAMES:
        raise ValueError("execution_attempt_membership_changed")
    attempts, edges = [], []
    execution_sha = sha(payloads["pilot_execution_report.json"])
    for binding in execution["executions"]:
        name = binding["attempt"]
        data = payloads[name + "/attempt_report.json"]
        report = load_json(data)
        digest = sha(data)
        if binding["report_sha256"] != digest or binding["exit_code"] != 0:
            raise ValueError("explicit_report_binding_changed")
        if report["plan_sha256"] != phases.PLAN_SHA or report["slurm_job_id"] != "3468":
            raise ValueError("explicit_job_binding_changed")
        if not identity(report["source_instance_id"]):
            raise ValueError("invalid_pilot_parent")
        execution_id = canonical_id([phases.PLAN_SHA, execution_sha, name, digest])
        subject = {"subject_id": execution_id, "report_sha256": digest}
        claim = {
            **subject,
            "accounting_sha256": ACCOUNTING_SHA,
            "cluster": "dgx-dasci",
            "job_id": "3468",
        }
        edge = join_claim(subject, claim, [allocation])
        attempts.append(
            {
                "execution_id": execution_id,
                "attempt": name,
                "report_sha256": digest,
                "execution_report_sha256": execution_sha,
                "plan_sha256": phases.PLAN_SHA,
                "source_instance_id": report["source_instance_id"],
                "original_lp_sha256": provenance(report["original_lp_sha256"]),
                "solver": "gurobi",
                "threads": report["parameters"]["Threads"],
                "termination": report["termination"],
                "unique_feasible_incumbents": None,
            }
        )
        edges.append(edge)
    return attempts, edges


def build(package_data, accounting_data, pilot_payloads):
    ledger = package_data["ledger/parent_solver_ledger.csv"]
    observations = historical_observations(rows(ledger), sha(ledger))
    allocation = accounting_projection(accounting_data)
    attempts, edges = pilot_registry(pilot_payloads, allocation)
    matched = {
        r["allocation_observation_id"] for r in edges if r["join_state"] == "matched"
    }
    if matched != {allocation["allocation_observation_id"]}:
        raise ValueError("pilot_join_incomplete")
    return {
        "schema_version": 1,
        "scope": "reviewed_artifact_observations_and_single_pilot_accounting_snapshot",
        "pr65_package_sha256": RECOVERY_SHA256,
        "pr66_plan_sha256": phases.PLAN_SHA,
        "accounting_sha256": ACCOUNTING_SHA,
        "historical_observations": observations,
        "artifact_alias_groups": aliases(observations),
        "pilot_attempts": attempts,
        "attempt_job_edges": edges,
        "allocation_observations": [allocation],
        "summary": {
            "historical_report_observations": len(observations),
            "historical_distinct_executions": None,
            "historical_job_bindings_qualified": 0,
            "pilot_attempts_explicitly_bound": len(attempts),
            "pilot_allocation_observations_counted_once": len(matched),
        },
        "complete_historical_compute_cost": None,
        "complete_54_parent_unique_incumbent_totals": None,
        "scientific_reporting_eligible": False,
        "phase_costs_qualified": False,
        "optimization_runs": 0,
        "training_runs": 0,
    }


def bounded_accounting(accounting):
    if (
        accounting.is_symlink()
        or not accounting.is_file()
        or accounting.stat().st_size > MAX_BYTES
    ):
        raise ValueError("unsafe_accounting_source")
    with accounting.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("accounting_grew_beyond_bound")
    return data


def collect(pr65_package, accounting, output):
    accounting, output = Path(accounting), Path(output).absolute()
    if output.exists() or output.resolve().is_relative_to(phases.EVIDENCE.resolve()):
        raise ValueError("fresh_output_outside_public_sources_required")
    data = bounded_accounting(accounting)
    package_data = read_package(pr65_package, RECOVERY_SHA256, True)
    value = build(package_data, data, phases.public_receipts())
    value["builder_sha256"] = sha(Path(__file__).read_bytes())
    if bounded_accounting(accounting) != data:
        raise ValueError("accounting_changed_during_read")
    payload = (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    if PRIVATE.search(payload.decode()):
        raise ValueError("private_marker_in_projection")
    exported = {"execution_registry.json": payload}
    exported["SHA256SUMS.txt"] = f"{sha(payload)}  execution_registry.json\n".encode()
    output.mkdir(parents=True, exist_ok=False)
    for name, content in exported.items():
        with (output / name).open("xb") as stream:
            stream.write(content)
    package = output / "execution_registry.tar.gz"
    with (
        package.open("xb") as stream,
        tarfile.open(fileobj=stream, mode="w:gz") as archive,
    ):
        for name, content in sorted(exported.items()):
            member = tarfile.TarInfo(name)
            member.size, member.mtime = len(content), 0
            archive.addfile(member, io.BytesIO(content))
    with tarfile.open(package) as archive:
        if len(archive.getmembers()) != 2 or {
            m.name for m in archive.getmembers()
        } != set(exported):
            raise ValueError("package_membership_changed")
        if any(
            archive.extractfile(name).read() != content
            for name, content in exported.items()
        ):
            raise ValueError("package_readback_failed")
    print("EXECUTION_REGISTRY_READ_ONLY_NO_OPTIMIZATION_NO_TRAINING")
    print(json.dumps(value["summary"], sort_keys=True))
    print("PACKAGE_SHA256=" + sha(package.read_bytes()))
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr65-package", required=True, type=Path)
    parser.add_argument("--accounting", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    collect(args.pr65_package, args.accounting, args.output)
