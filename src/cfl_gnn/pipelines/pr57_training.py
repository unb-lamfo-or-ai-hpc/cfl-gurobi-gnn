"""PR57-specific 54-parent graph and Gasse training adapter.

This module intentionally does not modify or reinterpret the historical PR50
39-parent confirmation pipeline. It treats the final PR57 evidence package as
a separate immutable cohort contract, reuses the 39 PR50 graph/root artifacts
by verified SHA-256, builds only the 15 later-admitted medium graphs, and then
delegates training/evaluation to the existing Gasse backend.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.training.gasse_reconnected import (
    TRAINING_HISTORY_NAME,
    TRAINING_PLAN_NAME,
    TRAINING_REPORT_NAME,
    canonical_sha256,
    load_protocol,
    read_json,
    read_jsonl,
    run_serial_training,
    validate_training_plan,
    write_json,
)

EVIDENCE_PACKAGE_SHA256 = (
    "9ced8340fb1bbd19bc02dcfab704a1663f90d097d6d3464d903a1c9f18d8e31f"
)
INDEX_NAME = "admitted_parent_label_index.jsonl"
GRAPH_MANIFEST_NAME = "pr57_54_graph_manifest.jsonl"
GRAPH_REPORT_NAME = "pr57_54_graph_report.json"
CONTRACT_NAME = "pr57_54_cohort_contract.json"
PROTOCOL_PATH = PROJECT_ROOT / "configs/training/gasse_pr57_54_v1.json"

EXPECTED_COUNTS = {"train": 34, "validation": 10, "test": 10}
EXPECTED_DIFFICULTY = {"easy": 30, "medium": 24}
EXPECTED_LABEL_FORMATS = {
    "confirmation_solution_json": 39,
    "gurobi_parent_solution_json": 15,
}
EXPECTED_NEW_PARENTS = (
    "CFL_medium_instance_3",
    "CFL_medium_instance_7",
    "CFL_medium_instance_8",
    "CFL_medium_instance_10",
    "CFL_medium_instance_11",
    "CFL_medium_instance_12",
    "CFL_medium_instance_14",
    "CFL_medium_instance_21",
    "CFL_medium_instance_22",
    "CFL_medium_instance_23",
    "CFL_medium_instance_24",
    "CFL_medium_instance_25",
    "CFL_medium_instance_27",
    "CFL_medium_instance_28",
    "CFL_medium_instance_29",
)


def _sha256(path: Path) -> str:
    return sha256_file(path)


def _json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _safe_descriptor(root: Path, descriptor: Mapping[str, Any], *, field: str) -> Path:
    relative = Path(str(descriptor["relative_path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe {field} path")
    root = root.resolve()
    path = (root / relative).resolve()
    if root != path and root not in path.parents:
        raise ValueError(f"{field} path escaped the declared root")
    if not path.is_file():
        raise ValueError(f"missing {field}: {relative.as_posix()}")
    if _sha256(path) != str(descriptor["sha256"]):
        raise ValueError(f"{field} SHA-256 mismatch: {relative.as_posix()}")
    return path


def _descriptor(root: Path, path: Path) -> dict[str, str]:
    root = root.resolve()
    path = path.resolve()
    if root != path and root not in path.parents:
        raise ValueError("artifact is outside its descriptor root")
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "sha256": _sha256(path),
    }


def _load_evidence_index(package: Path) -> tuple[list[dict[str, Any]], str]:
    package = package.resolve()
    if not package.is_file():
        raise ValueError("PR57 evidence package is missing")
    if _sha256(package) != EVIDENCE_PACKAGE_SHA256:
        raise ValueError("PR57 evidence package SHA-256 differs from the frozen package")

    with tarfile.open(package, "r:gz") as archive:
        candidates = [
            item for item in archive.getmembers()
            if item.isfile() and item.name.endswith(INDEX_NAME)
        ]
        if len(candidates) != 1:
            raise ValueError("PR57 package must contain exactly one admitted-parent index")
        raw = archive.extractfile(candidates[0])
        if raw is None:
            raise ValueError("PR57 admitted-parent index is unreadable")
        payload = raw.read()

    rows = [
        json.loads(line)
        for line in payload.decode("utf-8").splitlines()
        if line.strip()
    ]
    index_sha = hashlib.sha256(payload).hexdigest()
    return rows, index_sha


def _load_solution(path: Path) -> dict[str, Any]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, TypeError, ValueError) as error:
        raise ValueError(f"solution payload is unreadable: {path}") from error


def _normalized_objective_sense(value: Any) -> str:
    """Normalize solver/report objective-sense text for semantic comparison."""
    if value is None:
        return ""
    return str(value).strip().upper()


def _same_float(left: Any, right: Any, *, tolerance: float = 1e-12) -> bool:
    try:
        a = float(left)
        b = float(right)
    except (TypeError, ValueError):
        return False
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= tolerance


def _validate_gurobi_parent_label(
    *,
    identity: str,
    row: Mapping[str, Any],
    solution: Mapping[str, Any],
    report: Mapping[str, Any],
) -> None:
    """Validate PR53/PR54 recovered Gurobi labels without flattening receipt schemas."""

    failures: list[str] = []
    expected_mip_sha = str(row["mip"]["sha256"])
    expected_gap = float(row["mip_gap_relative"])
    expected_solution_sha = str(row["solution"]["sha256"])

    if solution.get("solution_source") != "independent_gurobi_optimization":
        failures.append("solution_source")
    if _normalized_objective_sense(
        solution.get("effective_objective_sense")
    ) != "MINIMIZE":
        failures.append("effective_objective_sense")
    if solution.get("warm_start_supplied") is not False:
        failures.append("warm_start_supplied")
    if solution.get("parent_incumbent_consumed") is not False:
        failures.append("parent_incumbent_consumed")
    if solution.get("fresh_process") is not True:
        failures.append("fresh_process")
    if not _same_float(solution.get("mip_gap_relative"), expected_gap):
        failures.append("solution_gap")

    if report.get("execution_valid") is not True:
        failures.append("execution_valid")
    if report.get("label_eligible") is not True:
        failures.append("label_eligible")
    if report.get("mathematical_audit", {}).get("valid") is not True:
        failures.append("mathematical_audit")
    if not _same_float(report.get("solve", {}).get("mip_gap_relative"), expected_gap):
        failures.append("report_gap")

    checks = report.get("checks")
    if not isinstance(checks, Mapping) or not checks or not all(
        value is True for value in checks.values()
    ):
        failures.append("receipt_checks")

    # PR53 exposed parent identity at the receipt top level. PR54 intentionally
    # stores it inside the immutable task descriptor. Accept either schema, but
    # fail closed if neither supplies the expected lineage.
    top_identity = report.get("source_instance_id")
    top_mip_sha = report.get("mip_sha256")
    task = report.get("task")

    if top_identity is not None or top_mip_sha is not None:
        if top_identity != identity:
            failures.append("top_level_source_instance_id")
        if top_mip_sha != expected_mip_sha:
            failures.append("top_level_mip_sha256")
    elif isinstance(task, Mapping):
        if task.get("source_instance_id") != identity:
            failures.append("task_source_instance_id")
        task_mip = task.get("mip")
        if not isinstance(task_mip, Mapping) or task_mip.get("sha256") != expected_mip_sha:
            failures.append("task_mip_sha256")
        if task.get("category") != row["category"]:
            failures.append("task_category")
        if task.get("difficulty") != row["difficulty"]:
            failures.append("task_difficulty")
        if int(task.get("fold", -1)) != int(row["fold"]):
            failures.append("task_fold")
        if task.get("role") != row["role"]:
            failures.append("task_role")
    else:
        failures.append("missing_receipt_lineage")

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, Mapping):
        failures.append("artifacts")
    else:
        parent_solution = artifacts.get("parent_solution.json.gz")
        if (
            not isinstance(parent_solution, Mapping)
            or parent_solution.get("sha256") != expected_solution_sha
            or parent_solution.get("relative_path") != "parent_solution.json.gz"
        ):
            failures.append("parent_solution_artifact")

    if failures:
        raise ValueError(
            f"recovered Gurobi label provenance failed for {identity}: "
            + ",".join(failures)
        )


def _validate_index_row(data_root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "category", "difficulty", "execution_time_seconds", "fold", "label_format",
        "mip", "mip_gap_relative", "report", "role", "solution", "source_instance_id",
    }
    if set(row) != required:
        raise ValueError("PR57 admitted-parent row schema changed")

    identity = str(row["source_instance_id"])
    role = str(row["role"])
    difficulty = str(row["difficulty"])
    label_format = str(row["label_format"])
    if role not in EXPECTED_COUNTS:
        raise ValueError(f"unknown role for {identity}")
    if difficulty not in EXPECTED_DIFFICULTY:
        raise ValueError(f"unknown difficulty for {identity}")
    if label_format not in EXPECTED_LABEL_FORMATS:
        raise ValueError(f"unknown label format for {identity}")

    gap = float(row["mip_gap_relative"])
    if not math.isfinite(gap) or gap < 0.0 or gap > 0.10 + 1e-12:
        raise ValueError(f"gap policy violation for {identity}")

    mip = _safe_descriptor(data_root, row["mip"], field=f"{identity} MIP")
    solution_path = _safe_descriptor(
        data_root, row["solution"], field=f"{identity} solution"
    )
    report_path = _safe_descriptor(
        data_root, row["report"], field=f"{identity} report"
    )
    solution = _load_solution(solution_path)
    report = _json(report_path)

    if label_format == "confirmation_solution_json":
        if (
            solution.get("solution_source")
            != "independently_audited_gurobi_confirmation_label"
            or solution.get("source_instance_id") != identity
            or solution.get("source_mip_sha256") != row["mip"]["sha256"]
            or solution.get("mathematical_audit", {}).get("valid") is not True
            or float(solution.get("mip_gap_relative")) != gap
            or report.get("gate_status") != "passed"
            or report.get("label_eligible") is not True
            or report.get("source_instance_id") != identity
            or report.get("mip_sha256") != row["mip"]["sha256"]
        ):
            raise ValueError(f"historical confirmation provenance failed for {identity}")

    elif label_format == "gurobi_parent_solution_json":
        _validate_gurobi_parent_label(
            identity=identity,
            row=row,
            solution=solution,
            report=report,
        )

    # Do not impose a container/schema assumption on ``solution["variables"]``
    # at the cohort-provenance gate. Historical confirmation labels and later
    # Gurobi parent labels are intentionally heterogeneous formats. Their exact
    # variable identity and feasibility are certified by their source receipts
    # and, for newly built graphs, rechecked by ``build_graph_artifact``.

    return {
        "identity": identity,
        "mip_path": mip,
        "solution_path": solution_path,
        "report_path": report_path,
        "solution": solution,
        "report": report,
    }


def _old_manifest(old_graph_root: Path) -> dict[str, dict[str, Any]]:
    path = old_graph_root / "confirmation_graph_manifest.jsonl"
    rows = read_jsonl(path)
    if len(rows) != 39:
        raise ValueError("historical PR50 graph manifest no longer has 39 rows")
    result = {str(row["source_instance_id"]): row for row in rows}
    if len(result) != 39:
        raise ValueError("historical PR50 graph manifest has duplicate identities")
    return result


def _validate_frozen_population(rows: list[dict[str, Any]]) -> None:
    identities = [str(row["source_instance_id"]) for row in rows]
    if len(rows) != 54 or len(set(identities)) != 54:
        raise ValueError("PR57 frozen cohort must contain 54 unique parents")

    roles = Counter(str(row["role"]) for row in rows)
    difficulties = Counter(str(row["difficulty"]) for row in rows)
    formats = Counter(str(row["label_format"]) for row in rows)
    if dict(roles) != EXPECTED_COUNTS:
        raise ValueError(f"PR57 partition counts changed: {dict(roles)}")
    if dict(difficulties) != EXPECTED_DIFFICULTY:
        raise ValueError(f"PR57 difficulty counts changed: {dict(difficulties)}")
    if dict(formats) != EXPECTED_LABEL_FORMATS:
        raise ValueError(f"PR57 label-format counts changed: {dict(formats)}")


def cohort_contract(
    *,
    data_root: str | Path,
    evidence_package: str | Path,
    old_graph_root: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    data = Path(data_root).resolve()
    package = Path(evidence_package).resolve()
    old_root = Path(old_graph_root).resolve()
    graph_root = (data / "bipartite_graphs").resolve()

    rows, index_sha = _load_evidence_index(package)
    _validate_frozen_population(rows)
    old = _old_manifest(old_root)

    for row in rows:
        checked = _validate_index_row(data, row)
        identity = checked["identity"]
        if row["label_format"] == "confirmation_solution_json":
            historical = old.get(identity)
            if historical is None:
                raise ValueError(f"PR50 graph missing for reusable parent {identity}")
            if (
                historical["mip_sha256"] != row["mip"]["sha256"]
                or historical["label_sha256"] != row["solution"]["sha256"]
                or historical["role"] != row["role"]
                or int(historical["fold"]) != int(row["fold"])
                or historical["difficulty"] != row["difficulty"]
            ):
                raise ValueError(f"PR50 reuse identity changed for {identity}")
            graph = old_root / historical["graph_relative_path"]
            root = old_root / historical["root_relative_path"]
            if _sha256(graph) != historical["graph_sha256"]:
                raise ValueError(f"PR50 graph SHA changed for {identity}")
            if _sha256(root) != historical["root_sha256"]:
                raise ValueError(f"PR50 root SHA changed for {identity}")
        else:
            if identity in old:
                raise ValueError(f"new PR57 parent unexpectedly exists in PR50: {identity}")

    new_ids = tuple(
        sorted(
            str(row["source_instance_id"])
            for row in rows
            if row["label_format"] == "gurobi_parent_solution_json"
        )
    )
    if new_ids != tuple(sorted(EXPECTED_NEW_PARENTS)):
        raise ValueError("PR57 new-graph parent set changed")

    contract = {
        "schema_version": 1,
        "contract_id": "pr57_54_parent_development_v1",
        "development_only": True,
        "scientific_reporting_eligible": False,
        "objective_sense": "MINIMIZE",
        "graph_authority": "gurobi",
        "seed": 42,
        "maximum_label_mip_gap_relative": 0.10,
        "root_policy": "first_optimal_root_gurobi_mipnode",
        "root_time_limit_seconds": 600,
        "root_threads": 1,
        "root_presolve": 0,
        "evidence_package_sha256": EVIDENCE_PACKAGE_SHA256,
        "admitted_parent_label_index_sha256": index_sha,
        "old_graph_root": old_root.relative_to(graph_root).as_posix(),
        "old_graph_manifest_sha256": _sha256(old_root / "confirmation_graph_manifest.jsonl"),
        "partition_counts": EXPECTED_COUNTS,
        "difficulty_counts": EXPECTED_DIFFICULTY,
        "label_format_counts": EXPECTED_LABEL_FORMATS,
        "reused_pr50_parents": sorted(old),
        "new_graph_parents": list(EXPECTED_NEW_PARENTS),
        "cohort": [str(row["source_instance_id"]) for row in rows],
    }
    return {**contract, "contract_sha256": canonical_sha256(contract)}, rows, old


def prepare(
    *,
    data_root: str | Path,
    evidence_package: str | Path,
    old_graph_root: str | Path,
    dataset_dir: str | Path,
) -> dict[str, Any]:
    output = Path(dataset_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("use a new empty PR57 dataset directory")
    output.mkdir(parents=True, exist_ok=True)

    contract, rows, _ = cohort_contract(
        data_root=data_root,
        evidence_package=evidence_package,
        old_graph_root=old_graph_root,
    )
    write_json(output / CONTRACT_NAME, contract)
    _write_jsonl(output / INDEX_NAME, rows)
    return {
        "gate_status": "passed",
        "contract": contract,
        "index": _descriptor(output, output / INDEX_NAME),
        "next_gate": "build_exactly_15_new_gurobi_authoritative_graphs",
    }


def _new_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row["source_instance_id"]): row for row in rows}
    return [by_id[identity] for identity in EXPECTED_NEW_PARENTS]


def build_graph(
    *,
    data_root: str | Path,
    evidence_package: str | Path,
    old_graph_root: str | Path,
    dataset_dir: str | Path,
    task_index: int,
) -> dict[str, Any]:
    from cfl_gnn.graph.gurobi_graph_artifact import (
        build_graph_artifact,
        capture_root_relaxation,
        write_root_artifact,
    )

    data = Path(data_root).resolve()
    output = Path(dataset_dir).resolve()
    contract, rows, _ = cohort_contract(
        data_root=data,
        evidence_package=evidence_package,
        old_graph_root=old_graph_root,
    )
    stored_contract = read_json(output / CONTRACT_NAME)
    if stored_contract != contract:
        raise ValueError("prepared PR57 contract differs from current source evidence")

    tasks = _new_rows(rows)
    if not 0 <= task_index < len(tasks):
        raise ValueError("PR57 graph task index must be between 0 and 14")

    row = tasks[task_index]
    identity = str(row["source_instance_id"])
    checked = _validate_index_row(data, row)

    receipt_path = output / "receipts" / f"{identity}.json"
    if receipt_path.is_file():
        previous = read_json(receipt_path)
        if previous.get("contract_sha256") != contract["contract_sha256"]:
            raise ValueError("existing PR57 graph receipt belongs to another contract")
        return previous

    graph_path = output / "graphs" / f"{identity}.pt"
    root_path = output / "roots" / f"{identity}.json.gz"
    if graph_path.exists() or root_path.exists():
        raise ValueError("unreceipted PR57 graph artifacts already exist")
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    root_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    root = capture_root_relaxation(
        checked["mip_path"],
        expected_mip_sha256=row["mip"]["sha256"],
        time_limit_seconds=600,
        threads=1,
        seed=42,
        presolve=0,
    )
    write_root_artifact(root_path, root)

    metadata = {
        "sample_id": identity,
        "source_instance_id": identity,
        "category": str(row["category"]),
        "difficulty": str(row["difficulty"]),
        "fold": int(row["fold"]),
        "role": str(row["role"]),
        "sampling_strategy": "original",
        "label_source_solver": "gurobi",
    }
    audit = build_graph_artifact(
        mip_path=checked["mip_path"],
        mip_sha256=row["mip"]["sha256"],
        solution_path=checked["solution_path"],
        solution_sha256=row["solution"]["sha256"],
        root_payload=root,
        output_path=graph_path,
        sample_metadata=metadata,
    )
    required_audit = (
        "roundtrip_readable",
        "label_variable_identity_match",
        "root_lp_feature_exactly_encoded",
    )
    if not all(audit.get(key) is True for key in required_audit):
        raise ValueError(f"new PR57 graph audit failed for {identity}")
    if audit.get("independent_label_feasibility", {}).get("valid") is not True:
        raise ValueError(f"new PR57 graph label feasibility failed for {identity}")

    result = {
        **metadata,
        "contract_sha256": contract["contract_sha256"],
        "mip_sha256": row["mip"]["sha256"],
        "source_label": row["solution"],
        "source_report": row["report"],
        "graph": _descriptor(output, graph_path),
        "root": _descriptor(output, root_path),
        "audit": audit,
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    write_json(receipt_path, result)
    return result


def consolidate(
    *,
    data_root: str | Path,
    evidence_package: str | Path,
    old_graph_root: str | Path,
    dataset_dir: str | Path,
) -> dict[str, Any]:
    data = Path(data_root).resolve()
    output = Path(dataset_dir).resolve()
    old_root = Path(old_graph_root).resolve()
    graph_root = (data / "bipartite_graphs").resolve()

    contract, rows, old = cohort_contract(
        data_root=data,
        evidence_package=evidence_package,
        old_graph_root=old_root,
    )
    if read_json(output / CONTRACT_NAME) != contract:
        raise ValueError("prepared PR57 contract differs from current source evidence")

    records: list[dict[str, Any]] = []
    by_id = {str(row["source_instance_id"]): row for row in rows}

    for identity in contract["cohort"]:
        row = by_id[identity]
        label_path = _safe_descriptor(data, row["solution"], field=f"{identity} solution")
        solution = _load_solution(label_path)

        if row["label_format"] == "confirmation_solution_json":
            historical = old[identity]
            graph_path = old_root / historical["graph_relative_path"]
            root_path = old_root / historical["root_relative_path"]
            graph_sha = historical["graph_sha256"]
            root_sha = historical["root_sha256"]
            provenance = {
                "mode": "immutable_pr50_reuse",
                "source_manifest_sha256": contract["old_graph_manifest_sha256"],
            }
        else:
            receipt_path = output / "receipts" / f"{identity}.json"
            if not receipt_path.is_file():
                raise ValueError(f"missing new PR57 graph receipt for {identity}")
            receipt = read_json(receipt_path)
            if receipt.get("contract_sha256") != contract["contract_sha256"]:
                raise ValueError(f"new PR57 receipt contract mismatch for {identity}")
            graph_path = _safe_descriptor(output, receipt["graph"], field=f"{identity} graph")
            root_path = _safe_descriptor(output, receipt["root"], field=f"{identity} root")
            graph_sha = receipt["graph"]["sha256"]
            root_sha = receipt["root"]["sha256"]
            provenance = {
                "mode": "pr57_new_graph",
                "receipt": _descriptor(output, receipt_path),
            }

        record = {
            "sample_id": identity,
            "source_instance_id": identity,
            "parent_instance_id": identity,
            "category": str(row["category"]),
            "difficulty": str(row["difficulty"]),
            "fold": int(row["fold"]),
            "role": str(row["role"]),
            "sampling_strategy": "original",
            "graph_authority": "gurobi",
            "mip_sha256": str(row["mip"]["sha256"]),
            "graph_relative_path": graph_path.resolve().relative_to(graph_root).as_posix(),
            "graph_sha256": str(graph_sha),
            "root_relative_path": root_path.resolve().relative_to(graph_root).as_posix(),
            "root_sha256": str(root_sha),
            "label_solver": "gurobi",
            "label_format": str(row["label_format"]),
            "label_contract_sha256": contract["contract_sha256"],
            "label_run_relative_path": label_path.parent.relative_to(data).as_posix(),
            "label_file_name": label_path.name,
            "label_sha256": str(row["solution"]["sha256"]),
            "label_mip_gap_relative": float(row["mip_gap_relative"]),
            "label_objective": float(solution["solution_objective"]),
            "label_execution_time_seconds": float(row["execution_time_seconds"]),
            "provenance": provenance,
        }
        records.append(record)

    if len(records) != 54 or len({row["mip_sha256"] for row in records}) != 54:
        raise ValueError("PR57 consolidated dataset must contain 54 unique MIPs")
    counts = Counter(record["role"] for record in records)
    if dict(counts) != EXPECTED_COUNTS:
        raise ValueError("PR57 consolidated partition counts changed")

    manifest_path = output / GRAPH_MANIFEST_NAME
    _write_jsonl(manifest_path, records)
    report = {
        "schema_version": 1,
        "contract": contract,
        "gate_status": "passed",
        "graphs": 54,
        "reused_pr50_graphs": 39,
        "new_pr57_graphs": 15,
        "partition_counts": EXPECTED_COUNTS,
        "manifest": _descriptor(output, manifest_path),
        "graph_root_relative_to_data_root": "bipartite_graphs",
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    write_json(output / GRAPH_REPORT_NAME, report)
    return report


def training_plan(
    *,
    data_root: str | Path,
    evidence_package: str | Path,
    old_graph_root: str | Path,
    dataset_dir: str | Path,
) -> dict[str, Any]:
    data = Path(data_root).resolve()
    output = Path(dataset_dir).resolve()
    graph_root = (data / "bipartite_graphs").resolve()
    contract, _, _ = cohort_contract(
        data_root=data,
        evidence_package=evidence_package,
        old_graph_root=old_graph_root,
    )
    report = read_json(output / GRAPH_REPORT_NAME)
    if (
        report.get("gate_status") != "passed"
        or report.get("contract") != contract
        or report.get("graphs") != 54
        or report.get("partition_counts") != EXPECTED_COUNTS
    ):
        raise ValueError("PR57 54-parent graph dataset is not ready")

    records = read_jsonl(
        _safe_descriptor(output, report["manifest"], field="PR57 graph manifest")
    )
    if len(records) != 54:
        raise ValueError("PR57 graph manifest length changed")

    for record in records:
        graph_path = graph_root / record["graph_relative_path"]
        root_path = graph_root / record["root_relative_path"]
        if not graph_path.is_file() or _sha256(graph_path) != record["graph_sha256"]:
            raise ValueError(f"graph identity changed: {record['sample_id']}")
        if not root_path.is_file() or _sha256(root_path) != record["root_sha256"]:
            raise ValueError(f"root identity changed: {record['sample_id']}")
        label = data / record["label_run_relative_path"] / record["label_file_name"]
        if not label.is_file() or _sha256(label) != record["label_sha256"]:
            raise ValueError(f"label identity changed: {record['sample_id']}")

    protocol = load_protocol(PROTOCOL_PATH)
    if (
        protocol["protocol_id"] != "gasse_pr57_54_parent_development_v1"
        or protocol["optimization"]["epochs"] != 100
        or protocol["optimization"]["patience"] != 100
        or protocol["optimization"]["seed"] != 42
        or protocol["sampling"]["maximum_label_mip_gap_relative"] != 0.10
    ):
        raise ValueError("PR57 training protocol changed")

    counts = Counter(record["role"] for record in records)
    if dict(counts) != EXPECTED_COUNTS:
        raise ValueError("PR57 training partition counts changed")

    payload = {
        "schema_version": 1,
        "dataset_variant": "pr57_54_parent_development_v1",
        "pr57_cohort_contract_sha256": contract["contract_sha256"],
        "graph_report_sha256": _sha256(output / GRAPH_REPORT_NAME),
        "graph_authority": "gurobi",
        "label_solver": "gurobi",
        "protocol": protocol,
        "protocol_sha256": canonical_sha256(protocol),
        "records": records,
        "partition_counts": EXPECTED_COUNTS,
        "test_partition_usage": "held_out_not_loaded_during_training",
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    plan = {
        **payload,
        "contract_sha256": canonical_sha256(payload),
        "contract_valid": True,
        "training_ready": True,
        "engineering_smoke_ready": True,
        "held_out_evaluation_ready": True,
    }
    validate_training_plan(plan)
    return plan


def _validate_training_receipt(report: Mapping[str, Any], output: Path) -> None:
    if (
        report.get("gate_status") != "passed"
        or report.get("epochs_completed") != 100
        or report.get("test_graphs_loaded") != 0
        or report.get("checkpoint_selection") != "minimum_validation_weighted_bce"
        or report.get("threshold_source") != "maximum_validation_f1"
    ):
        raise ValueError("PR57 100-epoch validation-only training contract failed")

    history_path = output / TRAINING_HISTORY_NAME
    if not history_path.is_file():
        raise ValueError("PR57 training history is missing")


def train_and_evaluate(
    *,
    data_root: str | Path,
    evidence_package: str | Path,
    old_graph_root: str | Path,
    dataset_dir: str | Path,
    output_dir: str | Path,
    device: str = "cuda",
) -> dict[str, Any]:
    from cfl_gnn.evaluation.gasse_reconnected import (
        build_evaluation_plan,
        execute_evaluation,
    )

    data = Path(data_root).resolve()
    graph_root = (data / "bipartite_graphs").resolve()
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("use a new empty PR57 training output directory")
    output.mkdir(parents=True, exist_ok=True)

    plan = training_plan(
        data_root=data,
        evidence_package=evidence_package,
        old_graph_root=old_graph_root,
        dataset_dir=dataset_dir,
    )
    write_json(output / TRAINING_PLAN_NAME, plan)

    report = run_serial_training(
        plan,
        graph_root=graph_root,
        label_root=data,
        output_dir=output,
        device_name=device,
    )
    _validate_training_receipt(report, output)

    evaluation = build_evaluation_plan(
        training_plan_path=output / TRAINING_PLAN_NAME,
        training_report_path=output / TRAINING_REPORT_NAME,
        checkpoint_path=output / "best_model.pt",
    )
    evaluation_dir = output / "evaluation"
    write_json(evaluation_dir / "gasse_evaluation_plan.json", evaluation)
    result = execute_evaluation(
        evaluation,
        graph_root=graph_root,
        label_root=data,
        checkpoint_path=output / "best_model.pt",
        output_dir=evaluation_dir,
        device_name=device,
    )
    if (
        result.get("gate_status") != "passed"
        or result.get("test_graphs_loaded") != 10
        or result.get("test_partition_usage") != "held_out_evaluation_only"
    ):
        raise ValueError("PR57 ten-parent held-out evaluation contract failed")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("preflight", "prepare", "graph", "consolidate", "dry-run", "train"),
    )
    parser.add_argument("--data_root", required=True, type=Path)
    parser.add_argument("--evidence_package", required=True, type=Path)
    parser.add_argument("--old_graph_root", required=True, type=Path)
    parser.add_argument("--dataset_dir", required=True, type=Path)
    parser.add_argument("--task_index", type=int)
    parser.add_argument("--output_dir", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cuda")
    args = parser.parse_args(argv)

    common = {
        "data_root": args.data_root,
        "evidence_package": args.evidence_package,
        "old_graph_root": args.old_graph_root,
    }

    if args.command == "preflight":
        result, rows, old = cohort_contract(**common)
        print(json.dumps({
            "gate_status": "passed",
            "contract_sha256": result["contract_sha256"],
            "parents": len(rows),
            "reused_pr50_graphs": len(old),
            "new_pr57_graphs": len(EXPECTED_NEW_PARENTS),
            "partition_counts": EXPECTED_COUNTS,
        }, sort_keys=True))
        return 0

    if args.command == "prepare":
        result = prepare(dataset_dir=args.dataset_dir, **common)
    elif args.command == "graph":
        if args.task_index is None:
            parser.error("graph requires --task_index")
        result = build_graph(
            dataset_dir=args.dataset_dir,
            task_index=args.task_index,
            **common,
        )
    elif args.command == "consolidate":
        result = consolidate(dataset_dir=args.dataset_dir, **common)
    elif args.command == "dry-run":
        result = training_plan(dataset_dir=args.dataset_dir, **common)
    else:
        if args.output_dir is None:
            parser.error("train requires --output_dir")
        result = train_and_evaluate(
            dataset_dir=args.dataset_dir,
            output_dir=args.output_dir,
            device=args.device,
            **common,
        )

    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0
