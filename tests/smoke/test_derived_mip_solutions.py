from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.experiments.mvp_contract import load_experiment_config
from cfl_gnn.pipelines.derived_mip_solutions import (
    DerivedMipSolveError,
    _artifact_paths,
    build_plan,
    evaluate_candidate,
    worker_request,
)
from cfl_gnn.solvers.pyscipopt_solution import sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"


def _cohort(tmp_path: Path, *, solver: str = "gurobi") -> Path:
    source = tmp_path / "variants"
    source.mkdir()
    config = load_experiment_config(CONFIG)
    for radius, fraction in ((148, 0.001), (736, 0.005), (1472, 0.01)):
        candidate = source / f"CFL_easy_instance_2__{solver}__lb_r{radius}.lp"
        candidate.write_text(f"candidate-{solver}-{radius}", encoding="utf-8")
        provenance = {
            "schema_version": 1,
            "experiment_contract_sha256": config.contract_sha256,
            "operator_contract_sha256": "a" * 64,
            "sample_status": "derived_mip_unlabelled",
            "solver": solver,
            "sampling_strategy": "incumbent_local_branching",
            "parent_instance_id": "CFL_easy_instance_2",
            "category": "CFL_easy_instance",
            "difficulty": "easy",
            "fold": 2,
            "role": "train",
            "source_incumbent": {
                "incumbent_id": f"{solver}:incumbent",
                "artifact_sha256": "b" * 64,
            },
            "local_branching": {
                "radius": radius,
                "radius_fraction": fraction,
            },
            "output": {
                "file_name": candidate.name,
                "sha256": sha256_file(candidate),
            },
        }
        candidate.with_suffix(".provenance.json").write_text(
            json.dumps(provenance), encoding="utf-8"
        )
    return source


def _plan(tmp_path: Path, *, solver: str = "gurobi"):
    return build_plan(
        solver=solver,
        candidate_dir=_cohort(tmp_path, solver=solver),
        output_dir=tmp_path / "output",
        config_path=CONFIG,
        time_limit=3600,
        node_limit=1_000_000,
        threads_per_candidate=1,
        seed=42,
        max_parallel=3,
    )


def _payload(plan, candidate, *, gap: float = 0.05) -> dict[str, object]:
    paths = _artifact_paths(plan, candidate)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(path.name.encode())
    event_type = "MIPSOL" if plan.solver == "gurobi" else "BESTSOLFOUND"
    return {
        "candidate_sha256": candidate.sha256,
        "solution_source": f"independent_{plan.solver}_optimization",
        "fresh_process": True,
        "pre_solve_solution_count": 0,
        "warm_start_supplied": False,
        "parent_incumbent_consumed": False,
        "original_objective_sense": "minimize",
        "objective_sense": "minimize",
        "solve_status": "timelimit",
        "solution_count": 4,
        "solution_objective": 6.2,
        "best_bound": 5.89,
        "mip_gap_relative": gap,
        "mip_gap_percent": 100.0 * gap,
        "execution_time_seconds": 3600.0,
        "best_incumbent_discovery_time_seconds": 1000.0,
        "nodes_current_run": 100,
        "nodes_total": 100,
        "solver_feasibility_check": True,
        "variables": [{"name": "x", "value": 1.0}],
        "online_incumbent_capture": {
            "event_type": event_type,
            "events_recorded": 3,
            "vectors_streamed": 3,
            "capture_error_count": 0,
            "stream_committed": True,
        },
        "incumbent_trace_audit": {"incumbent_trace_consistent": True},
    }


@pytest.mark.parametrize("solver", ["gurobi", "scip"])
def test_plan_is_solver_symmetric_path_sanitized_and_deterministic(
    tmp_path: Path, solver: str
) -> None:
    plan = _plan(tmp_path, solver=solver)

    assert len(plan.candidates) == 3
    assert plan.max_parallel == 3
    assert plan.maximum_admissible_relative_gap == 0.10
    assert str(tmp_path) not in json.dumps(plan.to_summary())
    assert plan.to_summary()["metric_semantics"]["comparative_use"].endswith(
        "not_final_solver_benchmark"
    )
    request = worker_request(plan, plan.candidates[0])
    assert request["force_minimize"] is True
    assert request["capture_incumbent_vectors"] is True
    assert request["threads"] == 1


@pytest.mark.parametrize("solver", ["gurobi", "scip"])
def test_admissible_independent_label_passes_but_dataset_stays_closed(
    tmp_path: Path, solver: str
) -> None:
    plan = _plan(tmp_path, solver=solver)
    candidate = plan.candidates[0]

    record = evaluate_candidate(
        plan, candidate, _payload(plan, candidate, gap=0.05), reused=False
    )

    assert record["gate_status"] == "passed"
    assert record["eligibility"]["label_eligible"] is True
    assert record["eligibility"]["dataset_eligible"] is False
    assert record["gap_sensitivity_memberships"] == [
        "gap_le_0.05",
        "gap_le_0.06",
        "gap_le_0.1",
    ]


def test_gap_above_ten_percent_is_inconclusive_not_failed(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    candidate = plan.candidates[0]

    record = evaluate_candidate(
        plan, candidate, _payload(plan, candidate, gap=0.1001), reused=False
    )

    assert record["gate_status"] == "inconclusive"
    assert record["eligibility"]["label_eligible"] is False
    assert record["decision"]["reason_code"] == "terminal_gap_above_label_policy"


def test_callback_evidence_failure_fails_closed(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    candidate = plan.candidates[0]
    payload = _payload(plan, candidate)
    payload["online_incumbent_capture"]["capture_error_count"] = 1  # type: ignore[index]

    record = evaluate_candidate(plan, candidate, payload, reused=False)

    assert record["gate_status"] == "failed"
    assert record["eligibility"]["label_eligible"] is False


def test_cross_solver_provenance_is_rejected(tmp_path: Path) -> None:
    source = _cohort(tmp_path, solver="scip")
    with pytest.raises(DerivedMipSolveError, match="expected 3 gurobi"):
        build_plan(
            solver="gurobi",
            candidate_dir=source,
            output_dir=tmp_path / "output",
            config_path=CONFIG,
            time_limit=3600,
            node_limit=1_000_000,
            threads_per_candidate=1,
            seed=42,
            max_parallel=3,
        )


def test_pipeline_source_excludes_pyomo_and_solver_imports_are_lazy() -> None:
    source = (
        PROJECT_ROOT
        / "src"
        / "cfl_gnn"
        / "pipelines"
        / "derived_mip_solutions.py"
    ).read_text(encoding="utf-8")

    assert "import gurobipy" not in source
    assert "import pyscipopt" not in source
    assert "import pyomo" not in source
    assert "from pyomo" not in source
    assert "fresh_process_per_candidate" in source
    assert "parent_incumbent_consumed" in source


