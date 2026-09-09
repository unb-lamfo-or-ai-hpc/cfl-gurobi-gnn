from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.analysis.parent_collection_audit import audit_parent_collection
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.parent_population import write_parent_collection_plan


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
CAMPAIGN = PROJECT_ROOT / "configs" / "experiments" / "parent_collection_v1.json"
EXPERIMENT = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"


def _write_gzip_json(path: Path, value: object) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(value, stream)


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "raw" / "CFL_easy_instance" / "LP"
    source.mkdir(parents=True)
    parent = source / "CFL_easy_instance_2.lp.gz"
    parent.write_bytes(b"fixed-parent")
    plan_dir = tmp_path / "plan"
    plan = write_parent_collection_plan(
        base_source_dir=tmp_path / "raw",
        output_dir=plan_dir,
        parent_manifest_path=MANIFEST,
        campaign_config_path=CAMPAIGN,
        experiment_config_path=EXPERIMENT,
        instances=("CFL_easy_instance_2",),
    )
    runs = tmp_path / "runs"
    for task in plan["tasks"]:
        solver = task["solver"]
        run_dir = runs / task["run_dir_relative_path"]
        run_dir.mkdir(parents=True)
        solution = run_dir / "parent_solution.json.gz"
        contract = f"{solver}-contract"
        trace = [
            {
                "incumbent_discovery_time_seconds": 1.0,
                "incumbent_objective": 8.0 if solver == "gurobi" else 9.0,
                "incumbent_best_bound_at_discovery": 6.0,
                "incumbent_mip_gap_relative_at_discovery": 0.25,
                "node_count_at_discovery": 3,
            },
            {
                "incumbent_discovery_time_seconds": 2.0,
                "incumbent_objective": 7.0 if solver == "gurobi" else 8.0,
                "incumbent_best_bound_at_discovery": 6.5,
                "incumbent_mip_gap_relative_at_discovery": 0.1,
                "node_count_at_discovery": 9,
            },
        ]
        _write_gzip_json(
            solution,
            {
                "contract_sha256": contract,
                "candidate_sha256": task["parent_mip_sha256"],
                "incumbent_trace": trace,
            },
        )
        incumbents = run_dir / "incumbents.parquet"
        variable_order = run_dir / "incumbent_variable_order.json.gz"
        incumbents.write_bytes(b"parquet")
        variable_order.write_bytes(b"order")
        optimize = 10.0 if solver == "gurobi" else 15.0
        report = {
            "contract_sha256": contract,
            "parent": {
                "source_instance_id": task["source_instance_id"],
                "sha256": task["parent_mip_sha256"],
            },
            "solve": {
                "objective_sense": "minimize",
                "solve_status": "timelimit",
                "solution_objective": trace[-1]["incumbent_objective"],
                "best_bound": 6.5,
                "mip_gap_relative": 0.05 if solver == "gurobi" else 0.08,
                "mip_gap_percent": 5.0 if solver == "gurobi" else 8.0,
                "execution_time_seconds": optimize,
                "best_incumbent_discovery_time_seconds": 2.0,
                "nodes_current_run": 10,
                "nodes_total": 10,
            },
            "time_regions": {
                "total_wall_time_seconds": optimize + 2.0,
                "data_read_wall_time_seconds": 0.5,
                "model_build_wall_time_seconds": 0.5,
                "model_optimize_wall_time_seconds": optimize,
            },
            "solver_parameter_sha256": f"{solver}-parameters",
            "runtime_environment": {
                "hostname": f"{solver}-node",
                "platform": "Linux",
                "machine": "x86_64",
                "processor": "test-cpu",
                "logical_cpu_count": 8,
                "slurm": {"slurm_job_partition": "batch"},
            },
            "artifacts": {
                "solution": {"file_name": solution.name, "sha256": sha256_file(solution)},
                "incumbents": {"file_name": incumbents.name, "sha256": sha256_file(incumbents)},
                "variable_order": {"file_name": variable_order.name, "sha256": sha256_file(variable_order)},
            },
            "eligibility": {
                "label_eligible": True,
                "augmentation_source_eligible": True,
            },
        }
        (run_dir / f"{solver}_parent_solve_report.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
    return plan_dir, runs


def test_audit_restores_paired_phase1_tables_and_figures(tmp_path: Path) -> None:
    plan_dir, runs = _fixture(tmp_path)
    output = tmp_path / "audit"

    report = audit_parent_collection(
        plan_dir=plan_dir, run_root=runs, output_dir=output
    )

    assert report["gate_status"] == "passed"
    assert report["summary"]["valid_tasks"] == 2
    assert report["summary"]["paired_parents"] == 1
    assert report["summary"]["incumbent_observations"] == 4
    assert report["methodology"]["priority_solver"] == "gurobi"
    assert report["eligibility"]["scientific_reporting_eligible"] is False
    for name in (
        "parent_solve_metrics.csv",
        "incumbent_trajectory.csv",
        "paired_parent_metrics.csv",
        "parent_gap_sensitivity.csv",
        "figure_parent_terminal_mip_gap.svg",
        "figure_parent_time_regions.svg",
        "figure_parent_incumbent_trajectories.svg",
    ):
        assert (output / name).stat().st_size > 0
    with (output / "paired_parent_metrics.csv").open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert float(row["scip_minus_gurobi_terminal_mip_gap_relative"]) == pytest.approx(0.03)
    assert float(row["scip_minus_gurobi_model_optimize_wall_time_seconds"]) == 5.0


def test_audit_fails_closed_when_one_solver_report_is_missing(tmp_path: Path) -> None:
    plan_dir, runs = _fixture(tmp_path)
    missing = next(runs.rglob("scip_parent_solve_report.json"))
    missing.unlink()

    report = audit_parent_collection(
        plan_dir=plan_dir, run_root=runs, output_dir=tmp_path / "audit"
    )

    assert report["gate_status"] == "failed"
    assert report["summary"]["failed_tasks"] == 1
    assert report["decision"]["next_gate"] == "resume_or_repair_parent_collection"
