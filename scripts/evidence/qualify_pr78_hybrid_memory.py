"""No-solver qualification of hybrid controller selection; no matrix writes."""

import argparse
import hashlib
import importlib
import json
import os
import re
import sys
from pathlib import Path

import probe_pr78_executor_gates as base


def numeric_observation(path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(81).decode("ascii").strip()
        if re.fullmatch(r"[0-9]{1,20}", raw):
            return int(raw)
        return "unlimited" if raw == "max" else "non_numeric_redacted"
    except FileNotFoundError:
        return "absent"
    except (OSError, UnicodeError):
        return "unavailable"


def observations(original, candidate, job, allocated):
    membership = original.bounded_text("/proc/self/cgroup")
    mounts = original.bounded_text("/proc/self/mountinfo")
    legacy, unified = candidate.membership_summary(membership)
    result = {
        "v1_memory_memberships": len(legacy),
        "unified_memberships": len(unified),
        "old_candidate_count": len(legacy) + len(unified),
        "membership_sha256": hashlib.sha256(membership.encode()).hexdigest(),
        "mountinfo_sha256": hashlib.sha256(mounts.encode()).hexdigest(),
        "paths_included": False,
    }
    if not allocated:
        return result
    version, leaf, _, _ = candidate.resolve_cgroup(membership, mounts, job)
    result["selected_controller_version"] = version
    limit = "memory.limit_in_bytes" if version == "v1" else "memory.max"
    usage = "memory.usage_in_bytes" if version == "v1" else "memory.current"
    chain = []
    path = Path(leaf)
    # Observe leaf through the job anchor only. These readings do not grant
    # qualification or replace the unchanged leaf-limit requirement.
    for depth in range(16):
        base.require(path.resolve(strict=True) == path)
        anchor = bool(re.fullmatch(r"job[_-]" + job + r"(?:\.scope)?", path.name))
        chain.append(
            {
                "depth_from_leaf": depth,
                "job_anchor": anchor,
                "limit_bytes": numeric_observation(path / limit),
                "usage_bytes": numeric_observation(path / usage),
                "v1_use_hierarchy": numeric_observation(path / "memory.use_hierarchy")
                if version == "v1"
                else None,
            }
        )
        if anchor:
            break
        path = path.parent
    result["job_scoped_memory_observations"] = chain
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("static", "allocated"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    allocated = args.mode == "allocated"
    report = {
        "schema_version": 1,
        "protocol_id": "pr78_hybrid_memory_qualification_v1",
        "historical_probe_job_id": "3483",
        "mode": args.mode,
        "environment": base.environment(),
        "optimization_runs_added": 0,
        "matrix_claims_added": 0,
        "scheduler_queries": 0,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
        "candidate_integrated_into_executor": False,
        "reproduces_current_environment_not_historical_proof": True,
        "stages": [base.stage("frozen_host_and_dependencies", base.fingerprint_check)],
    }
    blocker = base.NoSolver()
    sys.meta_path.insert(0, blocker)
    try:
        if report["stages"][0]["passed"]:
            sys.path.insert(0, str(base.SOURCE / "scripts/evidence"))
            executor = importlib.import_module("paired_matrix_executor")
            candidate = importlib.import_module("paired_memory_guard_v2")
            report["stages"].extend(base.gates(executor, allocated))

            def observe():
                report["controller_observations"] = observations(
                    executor.memory,
                    candidate,
                    os.environ.get("SLURM_JOB_ID", ""),
                    allocated,
                )

            report["stages"].append(base.stage("controller_inventory", observe))
            if allocated:

                def qualify():
                    gate = candidate.MemoryGate(os.environ.get("SLURM_JOB_ID", ""))
                    report["candidate_memory_receipt"] = gate.public()

                report["stages"].append(base.stage("candidate_memory_gate", qualify))
    except Exception as exc:
        report["stages"].append(
            {
                "stage": "diagnostic_setup",
                "passed": False,
                "exception_text_included": False,
                "exception_type": "ValueError"
                if isinstance(exc, ValueError)
                else "other",
            }
        )
    finally:
        sys.meta_path.remove(blocker)
    # The expected baseline failure remains visible but cannot veto a correctly
    # qualified candidate. Every other requested check remains mandatory.
    relevant = [x for x in report["stages"] if x["stage"] != "kernel_memory_gate"]
    passed = all(x["passed"] for x in relevant)
    report["static_checks_passed"] = passed if not allocated else None
    report["candidate_qualified_in_this_allocation"] = (
        allocated and passed and "candidate_memory_receipt" in report
    )
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    print(payload, end="")
    return 0 if allocated or passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
