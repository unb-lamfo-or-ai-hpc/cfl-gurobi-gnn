from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.pipelines.scalable_augmentation import (
    ScalableAugmentationError,
    audit_campaign,
    build_campaign_plan,
    canonical_sha256,
    sha256_file,
    validate_plan,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in values))


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    plan_dir = tmp_path / "parent-plan"
    progress_dir = tmp_path / "progress"
    run_root = tmp_path / "parent-runs"
    source_root = tmp_path / "raw"
    config = tmp_path / "mvp.json"
    _write_json(
        config,
        {
            "objective_sense": "MINIMIZE",
            "rotation": 0,
            "augmentation": {
                "operator": "incumbent_local_branching_v1",
                "train_only": True,
                "inherit_parent_fold": True,
                "parent_weighting": "equal_parent_mass",
                "maximum_derived_per_parent": 3,
                "radius_policy": {
                    "fractions": [0.001, 0.005, 0.01],
                    "minimum_radius": 1,
                },
            },
            "gap_policy": {
                "maximum_admissible_relative_gap": 0.1,
                "sensitivity_thresholds_relative": [0.01, 0.05, 0.06, 0.1],
            },
        },
    )
    tasks = []
    parents = (("train-parent", "train", 2), ("test-parent", "test", 0))
    for parent, role, fold in parents:
        mip = source_root / "CFL_easy_instance" / "LP" / f"{parent}.lp.gz"
        mip.parent.mkdir(parents=True, exist_ok=True)
        mip.write_bytes(parent.encode())
        for solver in ("gurobi", "scip"):
            run_relative = Path("budget_3600s") / solver / "CFL_easy_instance" / parent
            run_dir = run_root / run_relative
            solution = run_dir / "parent_solution.json.gz"
            run_dir.mkdir(parents=True, exist_ok=True)
            with gzip.open(solution, "wt", encoding="utf-8") as stream:
                json.dump({"solver": solver, "parent": parent}, stream)
            report = {
                "contract_sha256": f"{solver}-{parent}",
                "parent": {"sha256": sha256_file(mip)},
                "checks": {"fixture": True},
                "artifacts": {
                    "solution": {
                        "file_name": solution.name,
                        "sha256": sha256_file(solution),
                    }
                },
                "eligibility": {"augmentation_source_eligible": role == "train"},
            }
            _write_json(run_dir / f"{solver}_parent_solve_report.json", report)
            tasks.append(
                {
                    "solver": solver,
                    "source_instance_id": parent,
                    "category": "CFL_easy_instance",
                    "difficulty": "easy",
                    "fold": fold,
                    "role": role,
                    "parent_mip_relative_path": f"CFL_easy_instance/LP/{parent}.lp.gz",
                    "parent_mip_sha256": sha256_file(mip),
                    "run_dir_relative_path": run_relative.as_posix(),
                }
            )
    _write_json(
        plan_dir / "parent_collection_plan.json",
        {"contract_sha256": "p" * 64, "tasks": tasks},
    )
    eligibility = [
        {
            "source_instance_id": "train-parent",
            "category": "CFL_easy_instance",
            "difficulty": "easy",
            "fold": 2,
            "role": "train",
            "paired_label_eligible": True,
            "paired_augmentation_source_eligible": True,
        },
        {
            "source_instance_id": "test-parent",
            "category": "CFL_easy_instance",
            "difficulty": "easy",
            "fold": 0,
            "role": "test",
            "paired_label_eligible": True,
            "paired_augmentation_source_eligible": False,
        },
    ]
    eligibility_path = progress_dir / "paired_parent_eligibility.jsonl"
    _write_jsonl(eligibility_path, eligibility)
    _write_json(
        progress_dir / "parent_collection_progress_report.json",
        {
            "gate_status": "passed",
            "parent_collection_contract_sha256": "p" * 64,
            "outputs": {
                "paired_parent_eligibility.jsonl": {
                    "sha256": sha256_file(eligibility_path)
                }
            },
            "eligibility": {"development_only": True},
        },
    )
    return plan_dir, progress_dir, run_root, source_root, config


def test_plan_selects_only_paired_train_parents(tmp_path: Path) -> None:
    plan_dir, progress, runs, sources, config = _fixture(tmp_path)
    output = tmp_path / "augmentation-plan"
    plan = build_campaign_plan(
        parent_collection_plan_dir=plan_dir,
        parent_collection_progress_dir=progress,
        parent_collection_run_root=runs,
        base_source_dir=sources,
        output_dir=output,
        experiment_config_path=config,
    )
    tasks = [
        json.loads(line)
        for line in (output / "scalable_augmentation_tasks.jsonl")
        .read_text()
        .splitlines()
    ]
    validate_plan(plan, tasks)
    assert plan["summary"]["paired_train_parents"] == 1
    assert plan["summary"]["solver_tasks"] == 2
    assert plan["summary"]["planned_derived_mips"] == 6
    assert {item["solver"] for item in tasks} == {"gurobi", "scip"}
    assert {item["source_instance_id"] for item in tasks} == {"train-parent"}
    assert all(item["role"] == "train" for item in tasks)
    assert all(
        not Path(item["parent_solution_relative_path"]).is_absolute()
        for item in tasks
    )


def test_requested_non_train_parent_fails_closed(tmp_path: Path) -> None:
    plan_dir, progress, runs, sources, config = _fixture(tmp_path)
    with pytest.raises(ScalableAugmentationError, match="not paired train-eligible"):
        build_campaign_plan(
            parent_collection_plan_dir=plan_dir,
            parent_collection_progress_dir=progress,
            parent_collection_run_root=runs,
            base_source_dir=sources,
            output_dir=tmp_path / "out",
            experiment_config_path=config,
            instances=("test-parent",),
        )


def test_task_manifest_tampering_is_rejected(tmp_path: Path) -> None:
    plan_dir, progress, runs, sources, config = _fixture(tmp_path)
    output = tmp_path / "out"
    plan = build_campaign_plan(
        parent_collection_plan_dir=plan_dir,
        parent_collection_progress_dir=progress,
        parent_collection_run_root=runs,
        base_source_dir=sources,
        output_dir=output,
        experiment_config_path=config,
    )
    tasks = [
        json.loads(line)
        for line in (output / "scalable_augmentation_tasks.jsonl")
        .read_text()
        .splitlines()
    ]
    tasks[0]["fold"] = 4
    with pytest.raises(ScalableAugmentationError, match="task manifest hash"):
        validate_plan(plan, tasks)


def test_audit_requires_symmetric_radii(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir, progress, runs, sources, config = _fixture(tmp_path)
    output = tmp_path / "plan"
    plan = build_campaign_plan(
        parent_collection_plan_dir=plan_dir,
        parent_collection_progress_dir=progress,
        parent_collection_run_root=runs,
        base_source_dir=sources,
        output_dir=output,
        experiment_config_path=config,
    )
    assert plan["contract_sha256"]
    monkeypatch.setattr(
        "cfl_gnn.pipelines.scalable_augmentation._generation_valid",
        lambda task, directory: (
            True,
            [1, 2, 3] if task["solver"] == "gurobi" else [1, 2, 4],
        ),
    )
    monkeypatch.setattr(
        "cfl_gnn.pipelines.scalable_augmentation._solve_valid",
        lambda task, directory: True,
    )
    report = audit_campaign(
        plan_dir=output,
        run_root=tmp_path / "augmentation-runs",
        output_dir=tmp_path / "audit",
    )
    assert report["gate_status"] == "failed"
    assert report["summary"]["symmetric_pairs"] == 0


def test_canonical_hash_is_order_independent() -> None:
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})
