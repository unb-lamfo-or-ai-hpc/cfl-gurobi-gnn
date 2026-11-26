"""Closed-job reconciliation; no retry, submission, repair or scientific release."""

import hashlib
import re
from pathlib import Path

from ..audit import AuditPolicy
from ..collection import collect_attempt
from ..contract import digest, load_json, require
from ..identity import model_identity
from ..journal import durable_json, file_sha256
from ..matrix import DescriptionMatrix
from ..qualification import TINY_LP
from .inventory import bounded_read
from .policy import PROFILES, memory_bytes, technical_parameters


def tiny_geometry():
    return {
        "declared_sense": "MAXIMIZE",
        "effective_sense": "MINIMIZE",
        "objective_constant": 0,
        "variables": [
            {"name": f"x{i}", "domain": "B", "lower": 0, "upper": 1, "objective": 1}
            for i in range(20)
        ],
        "rows": [
            {
                "name": "capacity",
                "sense": ">=",
                "rhs": 10.5,
                "terms": [[i, 1] for i in range(20)],
            }
        ],
    }


def collect(plan, output, runner=bounded_read):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results = {}
    for profile, slot in plan["slots"].items():
        folder = Path(slot["output"])
        record = {"profile": profile, "qualified": False, "missing_reason": None}
        try:
            terminal = load_json(folder / "worker-terminal.json")
            require(
                terminal["source_commit"] == plan["source_commit"]
                and terminal["plan_identity_sha256"] == digest(plan)
                and terminal["profile"] == profile,
                "Cross-plan worker return",
            )
            require(
                terminal["child_returncode"] == 0 and terminal["guard"] is None,
                "Probe did not return cleanly",
            )
            require(
                set(terminal["admission_receipts"])
                == {"allocation.json", "worker-admission.json"},
                "Missing admission receipts",
            )
            for name, checksum in terminal["admission_receipts"].items():
                require(
                    file_sha256(folder / name) == checksum, "Admission receipt changed"
                )
            stdout = folder / "native.stdout.log"
            require(
                stdout.stat().st_size <= 16 * 1024 * 1024
                and file_sha256(stdout) == terminal["stdout_sha256"],
                "Raw log was altered",
            )
            job = terminal["job_id"]
            require(
                re.fullmatch(r"[1-9][0-9]*", job) is not None, "Invalid returned job ID"
            )
            raw = runner(
                [
                    "sacct",
                    "--noheader",
                    "--parsable2",
                    "--jobs",
                    job,
                    "--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocTRES,NodeList,MaxRSS",
                ]
            )
            rows = [line.split("|") for line in raw.splitlines() if line.strip()]
            parent = [row for row in rows if row[0] == job]
            require(
                len(parent) == 1 and len(parent[0]) >= 7,
                "Unique parent accounting row unavailable",
            )
            row = parent[0]
            tres = dict(item.split("=", 1) for item in row[4].split(",") if "=" in item)
            require(
                row[1] == "COMPLETED"
                and row[2] == "0:0"
                and row[5] == slot["node"]
                and tres.get("cpu") == "64"
                and memory_bytes(tres.get("mem", "invalid"))
                == PROFILES[profile]["memory_GiB"] * 1024**3
                and not any(
                    k.startswith("gres/gpu") and v != "0" for k, v in tres.items()
                ),
                "Job did not complete at the reviewed node",
            )
            attempt = collect_attempt(
                folder / "attempt",
                matrix=DescriptionMatrix(tiny_geometry()),
                policy=AuditPolicy(),
            )
            require(
                attempt["state"] == "native_returned"
                and attempt["budget_reserved_calls"]
                == attempt["observed_native_returns"]
                == 1
                and attempt["worker_error"] is None,
                "Call accounting not qualified",
            )
            require(
                attempt["binding"]["plan_identity_sha256"] == digest(plan)
                and attempt["binding"]["source_commit"] == plan["source_commit"]
                and attempt["binding"]["input_sha256"]
                == hashlib.sha256(TINY_LP.encode("ascii")).hexdigest()
                and attempt["binding"]["job_id"] == job
                and attempt["binding"]["key"]["attempt"] == slot["attempt"],
                "Native attempt binding changed",
            )
            native = attempt["native_result"]
            require(
                native["native"]["gurobi_version"] == [14, 0, 0], "Wrong native version"
            )
            parameters = native["parameters"]
            require(
                parameters["defaults_sha256"] == digest(parameters["defaults"])
                and parameters["effective"]
                == {**parameters["defaults"], **technical_parameters()},
                "Native parameters drifted",
            )
            require(
                any(
                    re.search(
                        r"Thread count: 32 physical cores, 64 logical processors, using up to 32 threads",
                        line,
                    )
                    for line in native["native"]["observer"]["native_thread_lines"]
                ),
                "Native Threads=0 header missing",
            )
            require(
                native["identity"] == model_identity(tiny_geometry()),
                "Original tiny model identity mismatch",
            )
            root_audits = [
                item
                for item in attempt["replayed_candidate_audits"]
                if item["audit"]["status"] == "qualified"
            ]
            require(
                root_audits
                and native["root_audit"]["status"] == "qualified"
                and native["native"]["observer"]["failure"] is None,
                "Root replay did not qualify",
            )
            allocation = load_json(folder / "allocation.json")
            require(
                allocation["allocation_qualified"]
                and all(allocation["checks"].values()),
                "Effective allocation not qualified",
            )
            thread_use = [
                int(value)
                for value in re.findall(
                    r"Thread count was (\d+) \(of \d+ available processors\)",
                    stdout.read_text(encoding="utf-8", errors="replace"),
                )
            ]
            record.update(
                qualified=True,
                job_id=job,
                accounting={
                    "state": row[1],
                    "exit_code": row[2],
                    "elapsed_seconds": int(row[3]),
                    "allocated_TRES": row[4],
                    "node": row[5],
                    "MaxRSS": row[6],
                    "MaxRSS_scope": "scheduler_sampled_separate_from_kernel_job_peak",
                },
                native_attempt_sha256=attempt["attempt_sha256"],
                independent_root_replays=len(root_audits),
                native_actual_thread_messages=thread_use,
                thread_activity_scope="tiny_probe_no_scaling_or_full_utilisation_claim",
                native_runtime=native["native"],
                last_live_job_memory=terminal.get("last_live_job_memory"),
                last_live_job_memory_scope="kernel_snapshot_before_worker_exit_not_post_teardown_accounting",
                step_accounting_rows=[
                    dict(
                        zip(
                            (
                                "job_id",
                                "state",
                                "exit_code",
                                "elapsed_seconds",
                                "allocated_TRES",
                                "node",
                                "MaxRSS",
                            ),
                            values[:7],
                        )
                    )
                    for values in rows
                    if values[0].startswith(job + ".") and len(values) >= 7
                ],
                allocation=allocation,
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            record["missing_reason"] = (
                "missing_failed_or_ineligible_return_review_preserved_files"
            )
            record["exception_type"] = type(error).__name__
        results[profile] = record
    result = {
        "schema_version": plan["schema_version"],
        "source_commit": plan["source_commit"],
        "plan_identity_sha256": digest(plan),
        "profiles": results,
        "two_production_envelopes_technically_qualified": all(
            record["qualified"] for record in results.values()
        ),
        "scientific_S2_released": False,
        "real_CFL_memory_or_performance_qualified": False,
        "other_Gurobi_sessions_globally_machine_verified": False,
        "further_native_calls_authorized": False,
        "automatic_retry": False,
    }
    durable_json(output / "production-qualification-review.json", result)
    return result
