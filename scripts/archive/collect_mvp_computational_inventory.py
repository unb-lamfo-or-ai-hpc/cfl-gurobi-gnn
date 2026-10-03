"""Read generated evidence and Parquet footers; never execute a solver.

Row totals are inventory observations, not counts of unique feasible incumbents.
SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

IDENTITY = re.compile(r"CFL_(?:easy|medium|hard)_instance_\d+")
COUNTERS = {"num_incumbents_collected", "incumbent_count", "incumbents_count", "num_incumbents"}


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def identities(value):
    result = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"source_instance_id", "parent_instance_id", "instance_id"} and isinstance(child, str) and IDENTITY.fullmatch(child):
                result.add(child)
            if key == "cohort" and isinstance(child, list):
                result.update(x for x in child if isinstance(x, str) and IDENTITY.fullmatch(x))
            result.update(identities(child))
    elif isinstance(value, list):
        for child in value:
            result.update(identities(child))
    return result


def counters(value, trail=""):
    result = []
    if isinstance(value, dict):
        for key, child in value.items():
            name = trail + "/" + key
            if key in COUNTERS and isinstance(child, int) and not isinstance(child, bool):
                result.append({"json_pointer": name, "reported_counter": child})
            elif isinstance(child, (dict, list)):
                result.extend(counters(child, name))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(counters(child, trail + "/" + str(index)))
    return result


def collect(data: Path, training: Path, output: Path):
    if output.exists():
        raise ValueError("preserve existing inventory; choose a fresh output")
    if output == data or output.is_relative_to(data):
        raise ValueError("inventory must be outside the frozen source data")
    plan = training / "gasse_training_plan.json"
    population = identities(json.loads(plan.read_text(encoding="utf-8-sig")))
    classes = Counter(parent.split("_")[1] for parent in population)
    if len(population) != 54 or classes != {"easy": 30, "medium": 24}:
        raise ValueError("training plan does not identify the expected 54-parent cohort")
    output.mkdir(parents=True)
    reports, tables, issues = [], [], []
    try:
        import pyarrow.parquet as pq
    except ImportError:
        pq = None
        issues.append({"reason": "pyarrow_unavailable_parquet_counts_not_observed"})
    for group in ("analysis", "intermediate", "models"):
        root = data / group
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink() or any(x in {"secrets", "tools", "bootstrap"} for x in path.relative_to(root).parts):
                continue
            relative = path.relative_to(data).as_posix()
            if path.suffix == ".json" and path.stat().st_size <= 2 * 1024 * 1024:
                try:
                    value = json.loads(path.read_text(encoding="utf-8-sig"))
                except (ValueError, UnicodeError, RecursionError):
                    issues.append({"relative_path": relative, "reason": "invalid_json"})
                    continue
                observed = counters(value)
                if observed:
                    reports.append({"relative_path": relative, "sha256": sha256(path),
                        "parent_ids": sorted(identities(value)), "observed_counters": observed,
                        "aggregation_or_run_semantics_not_yet_qualified": True})
            if path.suffix == ".parquet" and "incumbent" in path.name.lower():
                row = {"relative_path": relative, "sha256": sha256(path),
                    "parent_ids_from_path": sorted(set(IDENTITY.findall(relative))),
                    "parquet_rows": None, "columns": [], "unique_feasible_incumbents": None}
                if pq:
                    try:
                        metadata = pq.read_metadata(path)
                        row.update(parquet_rows=metadata.num_rows, columns=metadata.schema.names)
                    except Exception as error:
                        issues.append({"relative_path": relative, "reason": "parquet_footer_unreadable", "error_type": type(error).__name__})
                tables.append(row)
    result = {"schema_version": 1, "scope": "observed_artifact_inventory_not_certified_incumbent_population_counts",
        "cohort": sorted(population), "cohort_by_class": dict(classes),
        "training_plan_sha256": sha256(plan), "reported_counters": reports,
        "incumbent_tables": tables, "issues": issues,
        "complete_gurobi_54_parent_incumbent_total": None,
        "complete_scip_54_parent_incumbent_total": None,
        "solver_runs": 0, "source_files_modified": False,
        "binary_objects_deserialized": False, "scientific_reporting_eligible": False}
    (output / "incumbent_inventory.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with (output / "incumbent_table_inventory.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["relative_path", "sha256", "parent_ids_from_path", "parquet_rows", "columns", "unique_feasible_incumbents"])
        writer.writeheader()
        writer.writerows(tables)
    (output / "SHA256SUMS.txt").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in sorted(output.iterdir()) if p.is_file()), encoding="utf-8")
    print("CFL_COMPUTATIONAL_INVENTORY_OK")
    print("PARQUET_TABLES_OBSERVED=" + str(len(tables)))
    print("COUNTER_REPORTS_OBSERVED=" + str(len(reports)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--training-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.data_root.resolve(), args.training_dir.resolve(), args.output.resolve())
