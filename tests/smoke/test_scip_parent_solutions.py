from __future__ import annotations

import json
from pathlib import Path

from cfl_gnn.pipelines.scip_parent_solutions import (
    INCUMBENTS_NAME,
    SOLUTION_NAME,
    VARIABLE_ORDER_NAME,
    build_plan,
    evaluate_solution,
    worker_request,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"


def _plan(tmp_path: Path, *, fold: int = 2):
    parent = tmp_path / "parent.lp"
    parent.write_text("Minimize\n obj: x\nBinary\n x\nEnd\n", encoding="utf-8")
    return build_plan(
        parent_mip=parent,
        output_dir=tmp_path / "output",
        parent_instance_id="CFL_easy_instance_2",
        category="CFL_easy_instance",
        difficulty="easy",
        fold=fold,
        config_path=CONFIG,
        time_limit=3600.0,
        node_limit=1_000_000,
        seed=42,
        threads=1,
        solver_profile="default",
    )


def _payload(plan, *, gap: float = 0.05) -> dict[str, object]:
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    (plan.output_dir / SOLUTION_NAME).write_bytes(b"solution")
    (plan.output_dir / INCUMBENTS_NAME).write_bytes(b"incumbents")
    (plan.output_dir / VARIABLE_ORDER_NAME).write_bytes(b"order")
    return {
        "candidate_sha256": plan.parent_sha256,
        "fresh_process": True,
        "pre_solve_solution_count": 0,
        "warm_start_supplied": False,
        "original_objective_sense": "maximize",
        "objective_sense": "minimize",
        "solve_status": "timelimit",
        "solution_count": 3,
        "solution_objective": 6.2,
        "best_bound": 5.89,
        "mip_gap_relative": gap,
        "mip_gap_percent": 100.0 * gap,
        "execution_time_seconds": 3600.0,
        "best_incumbent_discovery_time_seconds": 1200.0,
        "nodes_current_run": 100,
        "nodes_total": 100,
        "solver_feasibility_check": True,
        "variables": [{"name": "x", "value": 1.0}],
        "online_incumbent_capture": {
            "events_recorded": 3,
            "vectors_streamed": 3,
            "capture_error_count": 0,
            "stream_committed": True,
        },
        "incumbent_trace_audit": {"incumbent_trace_consistent": True},
    }


def test_parent_plan_is_train_only_and_deterministic(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    duplicate = _plan(tmp_path)

    assert plan.role == "train"
    assert plan.maximum_admissible_relative_gap == 0.10
    assert plan.contract_sha256 == duplicate.contract_sha256
    request = worker_request(plan)
    assert request["force_minimize"] is True
    assert request["capture_incumbent_vectors"] is True
    assert request["solver_profile"] == "default"


def test_five_percent_train_solution_is_augmentation_eligible(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    report = evaluate_solution(plan, _payload(plan, gap=0.05))

    assert report["gate_status"] == "passed"
    assert report["eligibility"]["label_eligible"] is True
    assert report["eligibility"]["augmentation_source_eligible"] is True
    assert report["eligibility"]["dataset_eligible"] is False


def test_gap_above_ten_percent_is_not_eligible(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    report = evaluate_solution(plan, _payload(plan, gap=0.1001))

    assert report["gate_status"] == "inconclusive"
    assert report["eligibility"]["label_eligible"] is False
    assert report["decision"]["reason_code"] == "terminal_gap_above_augmentation_policy"


def test_non_training_parent_never_becomes_augmentation_source(tmp_path: Path) -> None:
    plan = _plan(tmp_path, fold=0)

    report = evaluate_solution(plan, _payload(plan, gap=0.01))

    assert plan.role == "test"
    assert report["eligibility"]["label_eligible"] is True
    assert report["eligibility"]["augmentation_source_eligible"] is False
    assert report["decision"]["reason_code"] == "parent_not_in_training_partition"


def test_parent_pipeline_contract_excludes_pyomo_and_records_primary_metrics() -> None:
    source = (
        PROJECT_ROOT / "src" / "cfl_gnn" / "pipelines" / "scip_parent_solutions.py"
    ).read_text(encoding="utf-8")

    assert "mip_gap_relative" in source
    assert "execution_time_seconds" in source
    assert "BESTSOLFOUND" in source
    assert "import pyomo" not in source
    assert "from pyomo" not in source


