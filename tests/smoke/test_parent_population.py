from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.pipelines.parent_collection_task import validate_campaign_plan
from cfl_gnn.pipelines.parent_population import (
    ParentPopulationError,
    build_parent_collection_plan,
    write_parent_collection_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
CAMPAIGN = PROJECT_ROOT / "configs" / "experiments" / "parent_collection_v1.json"
EXPERIMENT = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"


def _source_root(tmp_path: Path) -> Path:
    root = tmp_path / "raw"
    directory = root / "CFL_easy_instance" / "LP"
    directory.mkdir(parents=True)
    for instance_id in ("CFL_easy_instance_0", "CFL_easy_instance_2"):
        (directory / f"{instance_id}.lp.gz").write_bytes(instance_id.encode())
    return root


def test_plan_orders_all_gurobi_tasks_before_matched_scip(tmp_path: Path) -> None:
    plan, tasks = build_parent_collection_plan(
        base_source_dir=_source_root(tmp_path),
        parent_manifest_path=MANIFEST,
        campaign_config_path=CAMPAIGN,
        experiment_config_path=EXPERIMENT,
        instances=("CFL_easy_instance_2", "CFL_easy_instance_0"),
    )

    assert plan["planned_parent_population"] == 90
    assert plan["available_parent_population"] == 2
    assert plan["population_status"] == "development_partial"
    assert [task["solver"] for task in tasks] == [
        "gurobi", "gurobi", "scip", "scip"
    ]
    assert {task["source_instance_id"] for task in tasks[:2]} == {
        "CFL_easy_instance_0", "CFL_easy_instance_2"
    }
    assert plan["execution"]["scip_submission_dependency"].startswith("afterok:")
    assert plan["execution"]["preferred_execution_mode"] == (
        "paired_parent_array_gurobi_then_scip"
    )
    assert all(task["budget_id"] == "budget_3600s" for task in tasks)
    assert all(
        task["run_dir_relative_path"].startswith("budget_3600s/")
        for task in tasks
    )
    validate_campaign_plan(plan)


def test_plan_records_missing_requested_parents_without_fabricating_tasks(
    tmp_path: Path,
) -> None:
    plan, tasks = build_parent_collection_plan(
        base_source_dir=_source_root(tmp_path),
        parent_manifest_path=MANIFEST,
        campaign_config_path=CAMPAIGN,
        experiment_config_path=EXPERIMENT,
        instances=("CFL_easy_instance_0", "CFL_medium_instance_0"),
    )

    assert plan["available_parent_population"] == 1
    assert plan["missing_parent_population"] == 1
    assert len(tasks) == 2
    assert plan["missing_parents"][0]["source_instance_id"] == "CFL_medium_instance_0"
    assert str(tmp_path) not in json.dumps(plan)


def test_only_precommitted_time_budgets_are_accepted(tmp_path: Path) -> None:
    with pytest.raises(ParentPopulationError, match="precommitted"):
        build_parent_collection_plan(
            base_source_dir=_source_root(tmp_path),
            parent_manifest_path=MANIFEST,
            campaign_config_path=CAMPAIGN,
            experiment_config_path=EXPERIMENT,
            instances=("CFL_easy_instance_0",),
            time_limit=7200,
        )


def test_time_budgets_use_disjoint_run_directories(tmp_path: Path) -> None:
    source = _source_root(tmp_path)
    short, _ = build_parent_collection_plan(
        base_source_dir=source,
        parent_manifest_path=MANIFEST,
        campaign_config_path=CAMPAIGN,
        experiment_config_path=EXPERIMENT,
        instances=("CFL_easy_instance_0",),
        time_limit=3600,
    )
    long, _ = build_parent_collection_plan(
        base_source_dir=source,
        parent_manifest_path=MANIFEST,
        campaign_config_path=CAMPAIGN,
        experiment_config_path=EXPERIMENT,
        instances=("CFL_easy_instance_0",),
        time_limit=14400,
    )

    short_paths = {task["run_dir_relative_path"] for task in short["tasks"]}
    long_paths = {task["run_dir_relative_path"] for task in long["tasks"]}
    assert short_paths.isdisjoint(long_paths)


def test_written_plan_has_separate_solver_manifests(tmp_path: Path) -> None:
    output = tmp_path / "plan"
    plan = write_parent_collection_plan(
        base_source_dir=_source_root(tmp_path),
        output_dir=output,
        parent_manifest_path=MANIFEST,
        campaign_config_path=CAMPAIGN,
        experiment_config_path=EXPERIMENT,
        instances=("CFL_easy_instance_0",),
    )

    gurobi = [json.loads(line) for line in (
        output / "gurobi_parent_collection_tasks.jsonl"
    ).read_text().splitlines()]
    scip = [json.loads(line) for line in (
        output / "scip_parent_collection_tasks.jsonl"
    ).read_text().splitlines()]
    assert len(gurobi) == len(scip) == 1
    assert gurobi[0]["solver_phase_index"] == 0
    assert scip[0]["solver_phase_index"] == 1
    assert plan["priority_solver"] == "gurobi"
