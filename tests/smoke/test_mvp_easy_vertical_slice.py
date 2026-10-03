from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.experiments.mvp_easy_vertical_slice import (
    CENSORED_EVIDENCE_NAME,
    LABEL_INDEX_NAME,
    PARENT_MANIFEST_NAME,
    PLAN_NAME,
    REPORT_NAME,
    MvpEasyVerticalSliceError,
    _canonical_sha256,
    compose_easy_vertical_slice,
)
from cfl_gnn.graph.instance_provenance import sha256_file


CONFIG = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "experiments"
    / "mvp_easy_vertical_slice_v1.json"
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value) + "\n" for value in values),
        encoding="utf-8",
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    vertical = tmp_path / "vertical"
    benchmark = tmp_path / "benchmark"
    output = tmp_path / "output"
    parents = [
        ("CFL_easy_instance_0", "easy", "test", 0),
        ("CFL_medium_instance_0", "medium", "test", 0),
        ("CFL_easy_instance_1", "easy", "validation", 1),
        ("CFL_medium_instance_5", "medium", "validation", 1),
        ("CFL_easy_instance_2", "easy", "train", 2),
        ("CFL_medium_instance_2", "medium", "train", 2),
    ]
    tasks: list[dict[str, object]] = []
    audits: list[dict[str, object]] = []
    gaps = {
        ("CFL_easy_instance_0", "gurobi"): 0.01,
        ("CFL_easy_instance_0", "scip"): 0.02,
        ("CFL_easy_instance_1", "gurobi"): 0.05,
        ("CFL_easy_instance_1", "scip"): 0.20,
        ("CFL_easy_instance_2", "gurobi"): 0.03,
        ("CFL_easy_instance_2", "scip"): 0.04,
    }
    for instance_id, difficulty, role, fold in parents:
        category = instance_id.rsplit("_", 1)[0]
        for solver in ("gurobi", "scip"):
            run_relative = f"{solver}/{instance_id}"
            task = {
                "task_index": len(tasks),
                "solver": solver,
                "source_instance_id": instance_id,
                "category": category,
                "difficulty": difficulty,
                "fold": fold,
                "role": role,
                "parent_mip_relative_path": f"{category}/LP/{instance_id}.lp.gz",
                "parent_mip_sha256": f"parent-{instance_id}",
                "run_dir_relative_path": run_relative,
                "augmentation_required": role == "train",
            }
            tasks.append(task)
            run_dir = benchmark / run_relative
            solution = run_dir / "parent_solution.json.gz"
            solution.parent.mkdir(parents=True, exist_ok=True)
            solution.write_bytes(f"solution:{instance_id}:{solver}".encode())
            gap = gaps.get((instance_id, solver), 0.50)
            objective = (
                9.0
                if (instance_id, solver) == ("CFL_easy_instance_0", "scip")
                else 10.0 + len(tasks)
            )
            report = {
                "solve": {
                    "solution_objective": objective,
                    "mip_gap_relative": gap,
                    "execution_time_seconds": 3600.0,
                },
                "artifacts": {
                    "solution": {
                        "file_name": solution.name,
                        "sha256": sha256_file(solution),
                    }
                },
            }
            report_path = run_dir / "scip_parent_solve_report.json"
            _write_json(report_path, report)
            audits.append(
                {
                    "task_index": task["task_index"],
                    "solver": solver,
                    "source_instance_id": instance_id,
                    "role": role,
                    "difficulty": difficulty,
                    "parent_contract_sha256": f"contract-{instance_id}-{solver}",
                    "parent_report_sha256": sha256_file(report_path),
                    "run_dir_relative_path": run_relative,
                    "mip_gap_relative": gap,
                    "execution_time_seconds": 3600.0,
                    "solution_objective": report["solve"]["solution_objective"],
                    "benchmark_status": "passed",
                    "label_eligible": gap <= 0.10,
                }
            )
    plan_payload = {
        "schema_version": 1,
        "slice_id": "mvp_vertical_slice_easy_medium_v1",
        "tasks": tasks,
    }
    source_contract = _canonical_sha256(plan_payload)
    _write_json(
        vertical / "mvp_vertical_slice_plan.json",
        {**plan_payload, "contract_sha256": source_contract, "outputs": {}},
    )
    _write_jsonl(vertical / "per_parent_solve_audit.jsonl", audits)
    _write_json(
        vertical / "mvp_vertical_slice_parent_audit_report.json",
        {
            "contract_sha256": source_contract,
            "gates": {"benchmark_observation_gate": "passed"},
            "summary": {
                "paired_parent_population": True,
                "benchmark_tasks_passed": 12,
            },
        },
    )
    rescue_audits = [
        {
            "source_instance_id": "CFL_medium_instance_2",
            "solver": "gurobi",
            "role": "train",
            "mip_gap_relative": 0.02,
            "execution_time_seconds": 14400.0,
            "integrity_status": "passed",
            "label_status": "admissible",
            "status": "passed",
        },
        {
            "source_instance_id": "CFL_medium_instance_2",
            "solver": "scip",
            "role": "train",
            "mip_gap_relative": 4.7,
            "execution_time_seconds": 14400.0,
            "integrity_status": "passed",
            "label_status": "inadmissible",
            "status": "inconclusive",
        },
        {
            "source_instance_id": "CFL_medium_instance_5",
            "solver": "gurobi",
            "role": "validation",
            "mip_gap_relative": 0.13,
            "execution_time_seconds": 14400.0,
            "integrity_status": "passed",
            "label_status": "inadmissible",
            "status": "inconclusive",
        },
    ]
    _write_jsonl(vertical / "per_label_rescue_task_audit.jsonl", rescue_audits)
    _write_json(
        vertical / "mvp_label_rescue_audit_report.json",
        {
            "schema_version": 2,
            "rescue_contract_sha256": "rescue-contract",
            "gate_status": "inconclusive",
            "summary": {
                "tasks_planned": 3,
                "execution_integrity_passed": 3,
                "execution_integrity_failed": 0,
                "labels_admissible": 1,
                "labels_inadmissible": 2,
                "tasks_failed": 0,
            },
        },
    )
    return vertical, benchmark, output


def test_compose_easy_vertical_slice_passes_and_is_path_free(tmp_path: Path) -> None:
    vertical, benchmark, output = _fixture(tmp_path)
    report = compose_easy_vertical_slice(
        vertical_slice_dir=vertical,
        benchmark_run_root=benchmark,
        output_dir=output,
        config_path=CONFIG,
    )
    assert report["gate_status"] == "passed"
    assert report["summary"] == {
        "parents": 3,
        "labels": 4,
        "training_solver_labels": 2,
        "common_evaluation_references": 2,
        "censored_evidence_records": 9,
        "parents_by_role": {"test": 1, "train": 1, "validation": 1},
    }
    assert report["checks"]["test_graphs_not_deserialized"] is True
    labels = [
        json.loads(line)
        for line in (output / LABEL_INDEX_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(labels) == 4
    assert {item["source_solver"] for item in labels if item["role"] == "train"} == {
        "gurobi",
        "scip",
    }
    assert [item["source_solver"] for item in labels if item["role"] == "test"] == [
        "scip"
    ]
    serialized = "".join(
        path.read_text(encoding="utf-8")
        for path in (
            output / PLAN_NAME,
            output / PARENT_MANIFEST_NAME,
            output / LABEL_INDEX_NAME,
            output / CENSORED_EVIDENCE_NAME,
            output / REPORT_NAME,
        )
    )
    assert str(tmp_path) not in serialized


def test_compose_rejects_tampered_solution_artifact(tmp_path: Path) -> None:
    vertical, benchmark, output = _fixture(tmp_path)
    solution = benchmark / "gurobi/CFL_easy_instance_2/parent_solution.json.gz"
    solution.write_bytes(b"tampered")
    with pytest.raises(MvpEasyVerticalSliceError, match="solution fingerprint"):
        compose_easy_vertical_slice(
            vertical_slice_dir=vertical,
            benchmark_run_root=benchmark,
            output_dir=output,
            config_path=CONFIG,
        )


def test_compose_rejects_rescue_outcome_drift(tmp_path: Path) -> None:
    vertical, benchmark, output = _fixture(tmp_path)
    rescue = vertical / "mvp_label_rescue_audit_report.json"
    value = json.loads(rescue.read_text(encoding="utf-8"))
    value["summary"]["labels_inadmissible"] = 1
    _write_json(rescue, value)
    with pytest.raises(MvpEasyVerticalSliceError, match="does not justify fallback"):
        compose_easy_vertical_slice(
            vertical_slice_dir=vertical,
            benchmark_run_root=benchmark,
            output_dir=output,
            config_path=CONFIG,
        )
