"""Compose the reduced easy-only MVP slice from immutable solve evidence."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.experiments.mvp_vertical_slice import (
    AUDIT_NAME as BENCHMARK_AUDIT_NAME,
    AUDIT_REPORT_NAME as BENCHMARK_REPORT_NAME,
    PLAN_NAME as SOURCE_PLAN_NAME,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.mvp_label_rescue import (
    AUDIT_REPORT_NAME as RESCUE_REPORT_NAME,
    PER_TASK_AUDIT_NAME as RESCUE_AUDIT_NAME,
)


SCHEMA_VERSION = 1
PLAN_NAME = "mvp_easy_vertical_slice_plan.json"
PARENT_MANIFEST_NAME = "mvp_easy_parent_manifest.jsonl"
LABEL_INDEX_NAME = "mvp_easy_label_index.jsonl"
CENSORED_EVIDENCE_NAME = "mvp_censored_evidence.jsonl"
REPORT_NAME = "mvp_easy_vertical_slice_report.json"
REQUIRED_SOLVERS = ("gurobi", "scip")
REQUIRED_ROLES = ("train", "validation", "test")
COMMON_REFERENCE_SELECTION_ORDER = (
    "minimum_objective",
    "minimum_mip_gap",
    "minimum_execution_time",
    "solver_name",
)


class MvpEasyVerticalSliceError(RuntimeError):
    """Raised when the reduced-slice evidence contract fails closed."""


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise MvpEasyVerticalSliceError(
            f"unreadable JSON artifact: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise MvpEasyVerticalSliceError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    line_number = 0
    try:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError("record is not an object")
            records.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise MvpEasyVerticalSliceError(
            f"unreadable JSONL artifact: {path.name}:{line_number}"
        ) from error
    return records


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def _validate_config(value: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    if value.get("schema_version") != SCHEMA_VERSION:
        raise MvpEasyVerticalSliceError("unsupported easy-slice schema")
    if value.get("development_only") is not True:
        raise MvpEasyVerticalSliceError("easy-only slice must remain development-only")
    if value.get("solvers") != list(REQUIRED_SOLVERS):
        raise MvpEasyVerticalSliceError("easy-only slice requires Gurobi and SCIP")
    if value.get("common_reference_selection_order") != list(
        COMMON_REFERENCE_SELECTION_ORDER
    ):
        raise MvpEasyVerticalSliceError(
            "unexpected common-reference selection order"
        )
    if value.get("selection_policy") != (
        "precommitted_easy_stratum_fallback_after_medium_label_incompleteness_v1"
    ):
        raise MvpEasyVerticalSliceError("unexpected easy-only selection policy")
    parents = value.get("parents")
    if not isinstance(parents, list) or len(parents) != 3:
        raise MvpEasyVerticalSliceError("easy-only slice requires exactly three parents")
    normalized: list[dict[str, Any]] = []
    for parent in parents:
        if not isinstance(parent, dict):
            raise MvpEasyVerticalSliceError("easy-only parent must be an object")
        record = {
            "source_instance_id": str(parent.get("source_instance_id", "")).strip(),
            "difficulty": str(parent.get("difficulty", "")).strip(),
            "role": str(parent.get("role", "")).strip(),
        }
        if not record["source_instance_id"] or record["difficulty"] != "easy":
            raise MvpEasyVerticalSliceError("only explicit easy parents are permitted")
        if record["role"] not in REQUIRED_ROLES:
            raise MvpEasyVerticalSliceError("invalid easy-only parent role")
        normalized.append(record)
    if Counter(item["role"] for item in normalized) != Counter(REQUIRED_ROLES):
        raise MvpEasyVerticalSliceError("easy-only slice requires one parent per role")
    if len({item["source_instance_id"] for item in normalized}) != 3:
        raise MvpEasyVerticalSliceError("easy-only parents must be unique")
    maximum_gap = value.get("maximum_admissible_relative_gap")
    if not isinstance(maximum_gap, (int, float)) or not math.isclose(
        float(maximum_gap), 0.10, abs_tol=1e-12
    ):
        raise MvpEasyVerticalSliceError("the precommitted 10% gap threshold is required")
    return tuple(normalized)


def _contract_from_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in {"contract_sha256", "outputs"}
    }


def _artifact_descriptor(
    *, run_root: Path, audit: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_relative = str(audit["run_dir_relative_path"])
    run_dir = run_root / run_relative
    report_path = run_dir / "scip_parent_solve_report.json"
    if not report_path.is_file() or sha256_file(report_path) != audit.get(
        "parent_report_sha256"
    ):
        raise MvpEasyVerticalSliceError(
            f"parent report fingerprint mismatch: {audit['source_instance_id']}:{audit['solver']}"
        )
    report = _read_json(report_path)
    descriptor = report.get("artifacts", {}).get("solution", {})
    if not isinstance(descriptor, dict):
        raise MvpEasyVerticalSliceError("parent solution descriptor is missing")
    file_name = str(descriptor.get("file_name", ""))
    artifact = run_dir / file_name
    if not artifact.is_file() or sha256_file(artifact) != descriptor.get("sha256"):
        raise MvpEasyVerticalSliceError(
            f"parent solution fingerprint mismatch: {audit['source_instance_id']}:{audit['solver']}"
        )
    return report, {
        "relative_path": (Path(run_relative) / file_name).as_posix(),
        "sha256": descriptor["sha256"],
    }


def _label_record(
    *, run_root: Path, audit: Mapping[str, Any], use: str
) -> dict[str, Any]:
    report, solution = _artifact_descriptor(run_root=run_root, audit=audit)
    solve = report.get("solve", {})
    return {
        "label_id": (
            f"{audit['source_instance_id']}__{audit['solver']}__{use}"
        ),
        "source_instance_id": audit["source_instance_id"],
        "role": audit["role"],
        "difficulty": audit["difficulty"],
        "source_solver": audit["solver"],
        "label_use": use,
        "solution_objective": solve.get("solution_objective"),
        "mip_gap_relative": solve.get("mip_gap_relative"),
        "execution_time_seconds": solve.get("execution_time_seconds"),
        "solution_artifact": solution,
        "parent_contract_sha256": audit["parent_contract_sha256"],
        "benchmark_observation": True,
        "rescue_observation": False,
    }


def compose_easy_vertical_slice(
    *,
    vertical_slice_dir: str | Path,
    benchmark_run_root: str | Path,
    output_dir: str | Path,
    config_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a path-sanitized reduced-slice contract and deterministic label index."""
    vertical_root = Path(vertical_slice_dir).resolve()
    run_root = Path(benchmark_run_root).resolve()
    output = Path(output_dir).resolve()
    expected_outputs = (
        output / PLAN_NAME,
        output / PARENT_MANIFEST_NAME,
        output / LABEL_INDEX_NAME,
        output / CENSORED_EVIDENCE_NAME,
        output / REPORT_NAME,
    )
    if not overwrite and any(path.exists() for path in expected_outputs):
        raise MvpEasyVerticalSliceError("easy-only slice exists; use --overwrite")

    config = _read_json(Path(config_path))
    requested = _validate_config(config)
    source_plan_path = vertical_root / SOURCE_PLAN_NAME
    benchmark_report_path = vertical_root / BENCHMARK_REPORT_NAME
    benchmark_audit_path = vertical_root / BENCHMARK_AUDIT_NAME
    rescue_report_path = vertical_root / RESCUE_REPORT_NAME
    rescue_audit_path = vertical_root / RESCUE_AUDIT_NAME
    source_plan = _read_json(source_plan_path)
    benchmark_report = _read_json(benchmark_report_path)
    benchmark_audits = _read_jsonl(benchmark_audit_path)
    rescue_report = _read_json(rescue_report_path)
    rescue_audits = _read_jsonl(rescue_audit_path)

    source_contract = _canonical_sha256(_contract_from_summary(source_plan))
    source_checks = {
        "source_plan_contract_valid": source_plan.get("contract_sha256")
        == source_contract,
        "source_slice_id_match": source_plan.get("slice_id")
        == config.get("source_slice_id"),
        "benchmark_contract_match": benchmark_report.get("contract_sha256")
        == source_contract,
        "benchmark_observation_gate_passed": benchmark_report.get("gates", {}).get(
            "benchmark_observation_gate"
        )
        == "passed",
        "benchmark_population_paired": benchmark_report.get("summary", {}).get(
            "paired_parent_population"
        )
        is True,
        "benchmark_tasks_complete": benchmark_report.get("summary", {}).get(
            "benchmark_tasks_passed"
        )
        == 12,
    }
    expected_rescue = config.get("fallback_evidence", {})
    rescue_summary = rescue_report.get("summary", {})
    rescue_checks = {
        "rescue_gate_inconclusive": rescue_report.get("gate_status")
        == expected_rescue.get("rescue_gate_status"),
        "rescue_tasks_match": rescue_summary.get("tasks_planned")
        == expected_rescue.get("tasks_planned"),
        "rescue_integrity_complete": rescue_summary.get(
            "execution_integrity_passed"
        )
        == expected_rescue.get("execution_integrity_passed"),
        "rescue_admissible_count_match": rescue_summary.get("labels_admissible")
        == expected_rescue.get("labels_admissible"),
        "rescue_inadmissible_count_match": rescue_summary.get("labels_inadmissible")
        == expected_rescue.get("labels_inadmissible"),
        "rescue_failures_absent": rescue_summary.get("tasks_failed")
        == expected_rescue.get("tasks_failed")
        == 0,
    }
    if not all(source_checks.values()):
        raise MvpEasyVerticalSliceError("source vertical-slice evidence is invalid")
    if not all(rescue_checks.values()):
        raise MvpEasyVerticalSliceError("label-rescue outcome does not justify fallback")

    tasks = source_plan.get("tasks")
    if not isinstance(tasks, list):
        raise MvpEasyVerticalSliceError("source task manifest is missing")
    task_by_parent = {
        (str(item["source_instance_id"]), str(item["solver"])): item
        for item in tasks
    }
    requested_by_id = {item["source_instance_id"]: item for item in requested}
    parents: list[dict[str, Any]] = []
    for instance_id, requested_parent in sorted(requested_by_id.items()):
        pairs = [task_by_parent.get((instance_id, solver)) for solver in REQUIRED_SOLVERS]
        if any(task is None for task in pairs):
            raise MvpEasyVerticalSliceError(f"source pair is missing: {instance_id}")
        first = pairs[0]
        assert first is not None
        if any(
            first.get(field) != requested_parent[field]
            for field in ("source_instance_id", "role", "difficulty")
        ):
            raise MvpEasyVerticalSliceError(
                f"configured parent disagrees with source plan: {instance_id}"
            )
        parents.append(
            {
                key: first[key]
                for key in (
                    "source_instance_id",
                    "category",
                    "difficulty",
                    "fold",
                    "role",
                    "parent_mip_relative_path",
                    "parent_mip_sha256",
                )
            }
        )

    audits_by_parent: dict[str, list[dict[str, Any]]] = {}
    for audit in benchmark_audits:
        audits_by_parent.setdefault(str(audit.get("source_instance_id")), []).append(audit)
    selected_audits: list[tuple[dict[str, Any], str]] = []
    maximum_gap = float(config["maximum_admissible_relative_gap"])
    for parent in parents:
        instance_id = str(parent["source_instance_id"])
        records = audits_by_parent.get(instance_id, [])
        if len(records) != 2 or {item.get("solver") for item in records} != set(
            REQUIRED_SOLVERS
        ):
            raise MvpEasyVerticalSliceError(f"paired audit is missing: {instance_id}")
        if any(item.get("benchmark_status") != "passed" for item in records):
            raise MvpEasyVerticalSliceError(f"benchmark audit failed: {instance_id}")
        eligible = [
            item
            for item in records
            if item.get("label_eligible") is True
            and isinstance(item.get("mip_gap_relative"), (int, float))
            and float(item["mip_gap_relative"]) <= maximum_gap + 1e-12
            and isinstance(item.get("solution_objective"), (int, float))
            and math.isfinite(float(item["solution_objective"]))
            and isinstance(item.get("execution_time_seconds"), (int, float))
            and math.isfinite(float(item["execution_time_seconds"]))
            and float(item["execution_time_seconds"]) >= 0.0
        ]
        if parent["role"] == "train":
            if len(eligible) != 2:
                raise MvpEasyVerticalSliceError(
                    "both solver-specific training labels must be admissible"
                )
            selected_audits.extend((item, "solver_arm_training_label") for item in eligible)
        else:
            if not eligible:
                raise MvpEasyVerticalSliceError(
                    f"common evaluation reference is unavailable: {instance_id}"
                )
            selected_audits.append(
                (
                    min(
                        eligible,
                        key=lambda item: (
                            float(item["solution_objective"]),
                            float(item["mip_gap_relative"]),
                            float(item["execution_time_seconds"]),
                            str(item["solver"]),
                        ),
                    ),
                    "common_evaluation_reference",
                )
            )

    labels = sorted(
        (
            _label_record(run_root=run_root, audit=audit, use=use)
            for audit, use in selected_audits
        ),
        key=lambda item: (item["role"], item["source_instance_id"], item["source_solver"]),
    )
    censored: list[dict[str, Any]] = []
    for audit in benchmark_audits:
        if audit.get("difficulty") != "medium":
            continue
        censored.append(
            {
                "evidence_source": "one_hour_paired_benchmark",
                "source_instance_id": audit.get("source_instance_id"),
                "solver": audit.get("solver"),
                "role": audit.get("role"),
                "difficulty": audit.get("difficulty"),
                "mip_gap_relative": audit.get("mip_gap_relative"),
                "execution_time_seconds": audit.get("execution_time_seconds"),
                "solution_objective": audit.get("solution_objective"),
                "benchmark_status": audit.get("benchmark_status"),
                "label_eligible": audit.get("label_eligible"),
                "right_censored": not bool(audit.get("label_eligible")),
            }
        )
    for audit in rescue_audits:
        if not str(audit.get("source_instance_id", "")).startswith("CFL_medium_"):
            continue
        censored.append(
            {
                "evidence_source": "four_hour_label_rescue",
                "source_instance_id": audit.get("source_instance_id"),
                "solver": audit.get("solver"),
                "role": audit.get("role"),
                "difficulty": "medium",
                "mip_gap_relative": audit.get("mip_gap_relative"),
                "execution_time_seconds": audit.get("execution_time_seconds"),
                "integrity_status": audit.get("integrity_status"),
                "label_status": audit.get("label_status"),
                "status": audit.get("status"),
                "right_censored": audit.get("label_status") != "admissible",
            }
        )
    censored.sort(
        key=lambda item: (
            item["evidence_source"],
            str(item["source_instance_id"]),
            str(item["solver"]),
        )
    )

    source_fingerprints = {
        "vertical_slice_plan_sha256": sha256_file(source_plan_path),
        "benchmark_audit_report_sha256": sha256_file(benchmark_report_path),
        "benchmark_audit_sha256": sha256_file(benchmark_audit_path),
        "rescue_audit_report_sha256": sha256_file(rescue_report_path),
        "rescue_audit_sha256": sha256_file(rescue_audit_path),
    }
    contract_payload = {
        "schema_version": SCHEMA_VERSION,
        "slice_id": config["slice_id"],
        "source_slice_id": config["source_slice_id"],
        "selection_policy": config["selection_policy"],
        "common_reference_selection_order": list(
            COMMON_REFERENCE_SELECTION_ORDER
        ),
        "development_only": True,
        "scientific_reporting_eligible": False,
        "solvers": list(REQUIRED_SOLVERS),
        "maximum_admissible_relative_gap": maximum_gap,
        "source_vertical_slice_contract_sha256": source_contract,
        "source_rescue_contract_sha256": rescue_report.get(
            "rescue_contract_sha256"
        ),
        "source_fingerprints": source_fingerprints,
        "source_checks": source_checks,
        "rescue_checks": rescue_checks,
        "parents": parents,
        "labels": labels,
        "censored_evidence_sha256": _canonical_sha256(censored),
        "augmentation_policy": {
            "train_only": True,
            "validation_test_original_only": True,
        },
        "test_partition_usage": "held_out_not_deserialized_during_composition",
    }
    contract_sha256 = _canonical_sha256(contract_payload)
    plan = {
        **contract_payload,
        "contract_sha256": contract_sha256,
        "outputs": {
            "parent_manifest": PARENT_MANIFEST_NAME,
            "label_index": LABEL_INDEX_NAME,
            "censored_evidence": CENSORED_EVIDENCE_NAME,
            "report": REPORT_NAME,
            "solution_path_semantics": "relative_to_benchmark_run_root",
        },
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": contract_sha256,
        "probe_completed": True,
        "gate_status": "passed",
        "checks": {
            **source_checks,
            **rescue_checks,
            "three_roles_present": Counter(parent["role"] for parent in parents)
            == Counter(REQUIRED_ROLES),
            "both_training_solver_labels_present": sum(
                item["label_use"] == "solver_arm_training_label" for item in labels
            )
            == 2,
            "common_validation_reference_present": sum(
                item["role"] == "validation" for item in labels
            )
            == 1,
            "common_test_reference_present": sum(item["role"] == "test" for item in labels)
            == 1,
            "test_graphs_not_deserialized": True,
        },
        "summary": {
            "parents": len(parents),
            "labels": len(labels),
            "training_solver_labels": 2,
            "common_evaluation_references": 2,
            "censored_evidence_records": len(censored),
            "parents_by_role": dict(sorted(Counter(parent["role"] for parent in parents).items())),
        },
        "eligibility": {
            "easy_vertical_slice_composition_ready": True,
            "dataset_eligible": False,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": "easy_only_vertical_slice_evidence_contract_passed",
            "next_gate": "easy_only_four_arm_dataset_composition",
        },
    }
    if not all(report["checks"].values()):
        raise MvpEasyVerticalSliceError("easy-only slice checks failed")
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / PLAN_NAME, plan)
    _write_jsonl(output / PARENT_MANIFEST_NAME, parents)
    _write_jsonl(output / LABEL_INDEX_NAME, labels)
    _write_jsonl(output / CENSORED_EVIDENCE_NAME, censored)
    _write_json(output / REPORT_NAME, report)
    return report
