"""Reconcile declared generated evidence without optimization or binary loading.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

from publish_mvp2_baseline import PRIVATE

PARENT = re.compile(r"CFL_(easy|medium|hard)_instance_([0-9]+)")
HEX = re.compile(r"[0-9a-f]{64}")
EXCLUDED = {"secrets", "bootstrap", "tools", ".git", "__pycache__"}
MAX_JSON = 32 * 1024 * 1024
OUTPUTS = {
    "parent_solver_ledger.csv",
    "training_membership.csv",
    "incumbent_table_inventory.csv",
    "augmentation_lineage.csv",
    "hardware_usage.csv",
    "missing_evidence.json",
    "ledger_report.json",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path):
    before = path.stat()
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("source_changed_during_read")
    return result.hexdigest()


def regular(path, root):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        return False
    return path.resolve().is_relative_to(root.resolve())


def discover(root):
    """Do not traverse symlink directories, raw inputs, or operational packages."""
    for group in ("analysis", "intermediate", "models"):
        start = root / group
        if not start.is_dir() or start.is_symlink():
            continue
        for directory, children, files in os.walk(start, followlinks=False):
            children[:] = sorted(
                x
                for x in children
                if x not in EXCLUDED and not (Path(directory) / x).is_symlink()
            )
            for name in sorted(files):
                path = Path(directory) / name
                if regular(path, root) and (
                    path.suffix == ".json"
                    or (path.suffix == ".parquet" and "incumbent" in name.lower())
                ):
                    yield path


def identity(value):
    match = PARENT.fullmatch(value) if isinstance(value, str) else None
    return (
        value
        if (
            match
            and 0 <= int(match[2]) < 30
            and value == f"CFL_{match[1]}_instance_{int(match[2])}"
        )
        else None
    )


def number(value, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or (nonnegative and value < 0):
        return None
    return value


def count(value):
    value = number(value, True)
    return value if isinstance(value, int) else None


def safe_string(value):
    return value if isinstance(value, str) and not PRIVATE.search(value) else None


def checksum(value):
    return value if isinstance(value, str) and HEX.fullmatch(value) else None


def read_json(path):
    if path.stat().st_size > MAX_JSON:
        raise ValueError("json_size_limit")
    before = digest(path)
    value = json.loads(
        path.read_text(encoding="utf-8-sig"),
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")),
    )
    if not isinstance(value, dict):
        raise ValueError("json_object_required")
    if digest(path) != before:
        raise ValueError("source_changed_during_read")
    return value, before


def artifact_id(relative):
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()


def references(path, report, root):
    """Check sibling artifacts only; descriptors must not escape the input root."""
    items = report.get("artifacts")
    if not isinstance(items, dict) or not items:
        return None
    for value in items.values():
        if not isinstance(value, dict):
            return False
        name = value.get("file_name")
        expected = checksum(value.get("sha256"))
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or "/" in name
            or "\\" in name
            or not expected
        ):
            return False
        child = path.parent / name
        if not regular(child, root) or digest(child) != expected:
            return False
    return True


def attempt(path, value, sha, root):
    solver = {
        "gurobi_parent_solve_report.json": "gurobi",
        "scip_parent_solve_report.json": "scip",
    }.get(path.name)
    if solver is None:
        return None
    parent = value.get("parent")
    solve = value.get("solve")
    if not isinstance(parent, dict) or not isinstance(solve, dict):
        raise ValueError("unsupported_parent_report_schema")
    name = identity(parent.get("source_instance_id"))
    if not name:
        raise ValueError("unknown_original_parent")
    params = value.get("solver_parameter_map", {})
    online = value.get("online_incumbent_capture", {})
    times = value.get("time_regions", {})
    eligibility = value.get("eligibility", {})
    if not all(isinstance(x, dict) for x in (params, online, times, eligibility)):
        raise ValueError("unsupported_parent_report_schema")
    parameter_hash_valid = (
        checksum(value.get("solver_parameter_sha256"))
        == hashlib.sha256(canonical(params).encode()).hexdigest()
    )
    status = safe_string(solve.get("solve_status"))
    return {
        "attempt_id": artifact_id(path.relative_to(root).as_posix()),
        "report_sha256": sha,
        "source_instance_id": name,
        "difficulty": name.split("_")[1],
        "solver": solver,
        "original_lp_sha256": checksum(parent.get("sha256")),
        "contract_sha256": checksum(value.get("contract_sha256")),
        "declared_role": parent.get("role")
        if parent.get("role") in {"train", "validation", "test"}
        else None,
        "effective_objective_sense": solve.get("objective_sense")
        if solve.get("objective_sense")
        in {"minimize", "maximize", "MINIMIZE", "MAXIMIZE"}
        else None,
        "status": status,
        "right_censored": status.lower()
        in {"timelimit", "time_limit", "nodelimit", "node_limit", "interrupted"}
        if status
        else None,
        "primal": number(solve.get("solution_objective")),
        "dual": number(solve.get("best_bound")),
        "mip_gap_relative": number(solve.get("mip_gap_relative"), True),
        "solver_runtime_seconds": number(solve.get("execution_time_seconds"), True),
        "optimize_wall_seconds": number(
            times.get("model_optimize_wall_time_seconds"), True
        ),
        "solver_solution_count": count(solve.get("solution_count")),
        "callback_events_recorded": count(online.get("events_recorded")),
        "vectors_streamed": count(online.get("vectors_streamed")),
        "variable_order_sha256": checksum(online.get("variable_order_sha256")),
        "declared_label_eligible": eligibility.get("label_eligible")
        if isinstance(eligibility.get("label_eligible"), bool)
        else None,
        "unique_feasible_incumbents": None,
        "parameter_hash_valid": parameter_hash_valid,
        "artifact_reference_hashes_valid": references(path, value, root),
        "parameters_json": canonical(
            {
                k: v
                for k, v in params.items()
                if k
                in {
                    "TimeLimit",
                    "Threads",
                    "Seed",
                    "Method",
                    "NodeMethod",
                    "Crossover",
                    "Presolve",
                    "ModelSense",
                    "MIPGap",
                    "NodeLimit",
                    "limits/time",
                    "parallel/maxnthreads",
                    "randomization/randomseedshift",
                    "limits/gap",
                }
                and number(v) is not None
            }
        ),
        "solver_versions_json": canonical(
            {
                k: v
                for k, v in value.get("solver_versions", {}).items()
                if k in {"gurobi", "gurobipy", "scip", "pyscipopt"}
                and (
                    safe_string(v) is not None
                    or isinstance(v, list)
                    and all(count(x) is not None for x in v)
                )
            }
        ),
    }


def memberships(value, source, sha):
    rows, seen = [], {}
    records = value.get("records")
    if not isinstance(records, list):
        raise ValueError("training_records_missing")
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid_training_record")
        name = identity(
            record.get("parent_instance_id", record.get("source_instance_id"))
        )
        role = record.get("role")
        if not name or role not in {"train", "validation", "test"}:
            raise ValueError("invalid_training_membership")
        if name in seen and seen[name] != role:
            raise ValueError("parent_role_leakage_in_one_training_plan")
        seen[name] = role
        strategy = record.get("sampling_strategy")
        rows.append(
            {
                "plan_id": source,
                "plan_sha256": sha,
                "source_instance_id": name,
                "role": role,
                "sampling_strategy": strategy
                if strategy in {"original", "derived", "local_branching"}
                else None,
                "mip_sha256": checksum(record.get("mip_sha256")),
                "checkpoint_training_execution_verified": False,
            }
        )
    return rows


def parquet_footer(path):
    """Never read vector batches or deserialize Python/PyTorch objects."""
    import pyarrow.parquet as pq

    meta = pq.read_metadata(path)
    return {"parquet_rows": meta.num_rows, "column_names": canonical(meta.schema.names)}


def hardware(text):
    header = "JobID|JobName|State|ExitCode|ElapsedRaw|TotalCPU|AllocCPUS|AllocTRES|MaxRSS|ReqMem"
    lines = text.splitlines()
    if not lines or lines[0] != header:
        raise ValueError("slurm_schema_invalid")
    rows, seen = [], set()
    for line in lines[1:]:
        values = line.split("|")
        if len(values) != 10 or not re.fullmatch(
            r"[0-9]+(?:_[0-9]+)?(?:\.[a-zA-Z0-9]+)?", values[0]
        ):
            raise ValueError("slurm_row_invalid")
        job, _, state, code, elapsed, cpu, cpus, tres, rss, mem = values
        if job in seen:
            raise ValueError("duplicate_slurm_row")
        seen.add(job)
        if not elapsed.isdigit() or not cpus.isdigit():
            raise ValueError("slurm_numeric_field_invalid")
        resources = dict(x.split("=", 1) for x in tres.split(",") if "=" in x)
        gpu = resources.get("gres/gpu")
        rows.append(
            {
                "job_id": job,
                "is_step": "." in job,
                "state": safe_string(state),
                "exit_code": safe_string(code),
                "elapsed_seconds": int(elapsed),
                "allocated_cpus": int(cpus),
                "allocated_gpus": int(gpu) if gpu and gpu.isdigit() else None,
                "reported_total_cpu_time": safe_string(cpu) or None,
                "reported_max_rss": safe_string(rss) or None,
                "requested_memory": safe_string(mem) or None,
                "gpu_utilization": None,
                "attempt_join_verified": False,
            }
        )
    return rows


def write_json(path, value):
    path.write_bytes(
        (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    )


def write_csv(path, rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(stream.getvalue().encode())


def collect(root, output, accounting=None, footer_reader=parquet_footer):
    root, output = Path(root).resolve(), Path(output).resolve()
    if (
        not root.is_dir()
        or output.exists()
        or output.is_relative_to(root)
        or root.is_relative_to(output)
    ):
        raise ValueError("use_fresh_output_outside_source_data")
    output.mkdir(parents=True)
    attempts, members, tables, lineage, sources, issues = [], [], [], [], [], []
    for path in discover(root):
        relative = path.relative_to(root).as_posix()
        ref = artifact_id(relative)
        try:
            sha = digest(path)
            sources.append(
                {"artifact_id": ref, "relative_path": relative, "sha256": sha}
            )
            if path.suffix == ".parquet":
                parents = sorted(
                    {
                        identity(x[0])
                        for x in re.finditer(PARENT, relative)
                        if identity(x[0])
                    }
                )
                table = {
                    "artifact_id": ref,
                    "sha256": sha,
                    "source_instance_id": parents[0] if len(parents) == 1 else None,
                    "solver_attribution": None,
                    "parquet_rows": None,
                    "column_names": None,
                    "unique_feasible_incumbents": None,
                }
                try:
                    table.update(footer_reader(path))
                except (ImportError, OSError, ValueError) as error:
                    issues.append(
                        {
                            "artifact_id": ref,
                            "reason": "parquet_footer_unavailable",
                            "error_type": type(error).__name__,
                        }
                    )
                if digest(path) != sha:
                    raise ValueError("source_changed_during_read")
                tables.append(table)
                continue
            value, checked_sha = read_json(path)
            if checked_sha != sha:
                raise ValueError("source_changed_during_read")
            row = attempt(path, value, sha, root)
            if row:
                attempts.append(row)
            elif path.name == "gasse_training_plan.json":
                members.extend(memberships(value, ref, sha))
            elif path.name in {
                "local_branching_generation_report.json",
                "derived_mip_solution_report.json",
            }:
                lineage.append(
                    {
                        "artifact_id": ref,
                        "report_sha256": sha,
                        "stage": "generation"
                        if path.name.startswith("local")
                        else "independent_labelling",
                        "source_instance_id": identity(value.get("parent_instance_id")),
                        "solver": value.get("solver")
                        if value.get("solver") in {"gurobi", "scip"}
                        else None,
                        "contract_sha256": checksum(value.get("contract_sha256")),
                        "declared_candidate_count": count(
                            value.get("summary", {}).get("candidate_count")
                        ),
                        "unique_feasible_derivatives": None,
                        "training_usage_verified": False,
                    }
                )
        except (
            OSError,
            ValueError,
            UnicodeError,
            RecursionError,
            TypeError,
            AttributeError,
        ) as error:
            issues.append(
                {
                    "artifact_id": ref,
                    "reason": "unreadable_or_unsupported_artifact",
                    "error_type": type(error).__name__,
                }
            )
    # Never sum events across repeated attempts, aliases or solver configurations.
    resource_rows = (
        hardware(Path(accounting).read_text(encoding="utf-8-sig")) if accounting else []
    )
    if accounting:
        sources.append(
            {
                "artifact_id": "slurm_accounting",
                "relative_path": str(Path(accounting).resolve()),
                "sha256": digest(Path(accounting)),
            }
        )
    write_json(output / "source_inventory.private.json", sources)
    public = {
        "parent_solver_ledger.csv": attempts,
        "training_membership.csv": members,
        "incumbent_table_inventory.csv": tables,
        "augmentation_lineage.csv": lineage,
        "hardware_usage.csv": resource_rows,
    }
    defaults = {
        "parent_solver_ledger.csv": ["attempt_id", "source_instance_id", "solver"],
        "training_membership.csv": ["plan_id", "source_instance_id", "role"],
        "incumbent_table_inventory.csv": [
            "artifact_id",
            "source_instance_id",
            "parquet_rows",
        ],
        "augmentation_lineage.csv": ["artifact_id", "source_instance_id", "stage"],
        "hardware_usage.csv": ["job_id", "allocated_cpus", "allocated_gpus"],
    }
    for name, rows in public.items():
        write_csv(output / name, rows, list(rows[0]) if rows else defaults[name])
    observed = {r["source_instance_id"] for r in attempts}
    missing = [
        f"CFL_{difficulty}_instance_{i}"
        for difficulty in ("easy", "medium", "hard")
        for i in range(30)
        if f"CFL_{difficulty}_instance_{i}" not in observed
    ]
    write_json(
        output / "missing_evidence.json",
        {
            "issues": issues,
            "parents_without_supported_solve_reports": missing,
            "remaining_gates": [
                "qualify_legacy_schema_and_attempt_aliases",
                "join_slurm_jobs_to_attempts",
                "validate_variable_order_and_unique_feasible_vectors",
                "verify_derivative_training_usage",
            ],
            "unknown_is_not_zero": True,
        },
    )
    report = {
        "schema_version": 1,
        "scope": "declared_evidence_reconciliation_not_solution_certification",
        "source_files_inventoried": len(sources),
        "supported_attempt_reports": len(attempts),
        "supported_parents": len(observed),
        "attempts_by_solver": dict(Counter(r["solver"] for r in attempts)),
        "parquet_tables_observed": len(tables),
        "training_membership_rows": len(members),
        "lineage_stage_reports": len(lineage),
        "issues": len(issues),
        "gate_status": "collected_with_missing_evidence"
        if issues or missing
        else "collected",
        "complete_gurobi_54_parent_unique_feasible_incumbents": None,
        "complete_scip_54_parent_unique_feasible_incumbents": None,
        "historical_compute_cost_complete": False,
        "hardware_scope": "account_jobs_not_yet_attributed_to_cfl_attempts",
        "private_source_inventory_sha256": digest(
            output / "source_inventory.private.json"
        ),
        "collector_sha256": digest(Path(__file__)),
        "scientific_reporting_eligible": False,
        "optimization_runs": 0,
        "training_runs": 0,
        "binary_objects_deserialized": False,
        "original_files_modified": False,
        "zenodo_upload_performed": False,
    }
    write_json(output / "ledger_report.json", report)
    verify(output, create_manifest=True)
    return report


def verify(output, create_manifest=False):
    output = Path(output)
    for name in sorted(OUTPUTS):
        path = output / name
        if not regular(path, output) or PRIVATE.search(
            path.read_text(encoding="utf-8")
        ):
            raise ValueError("public_artifact_missing_or_private_marker_detected")
    expected = {name: digest(output / name) for name in sorted(OUTPUTS)}
    manifest = "".join(f"{sha}  {name}\n" for name, sha in expected.items()).encode()
    if create_manifest:
        if (output / "SHA256SUMS.txt").exists():
            raise ValueError("manifest_already_exists")
        (output / "SHA256SUMS.txt").write_bytes(manifest)
    elif (output / "SHA256SUMS.txt").read_bytes() != manifest:
        raise ValueError("manifest_mismatch")
    return len(expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("collect")
    run.add_argument("--data-root", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--accounting", type=Path)
    check = sub.add_parser("verify")
    check.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "collect":
        print(
            json.dumps(collect(args.data_root, args.output, args.accounting), indent=2)
        )
    else:
        print(f"PUBLIC_ARTIFACTS_VERIFIED={verify(args.output)}")
    print("PR65_LEDGER_HASHES_OK")
    print("PR65_LEDGER_DECLARED_TEXT_SANITIZATION_OK")
