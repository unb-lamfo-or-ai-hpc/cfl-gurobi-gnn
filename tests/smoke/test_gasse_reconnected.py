from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.evaluation.gasse_reconnected import (
    build_evaluation_plan,
    binary_curve_rows,
    calibration_rows,
    confusion_counts,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.gurobi_graph_dataset import (
    GRAPH_MANIFEST_NAME,
    GRAPH_REPORT_NAME,
)
from cfl_gnn.pipelines.parent_population import write_parent_collection_plan
from cfl_gnn.pipelines.parent_solutions import report_name
from cfl_gnn.training.gasse_reconnected import (
    GasseTrainingError,
    LEGACY_GASSE_GIT_BLOB_SHA1,
    build_gasse_training_plan,
    canonical_sha256,
    git_blob_sha1,
    threshold_from_validation,
    validate_training_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
CAMPAIGN = PROJECT_ROOT / "configs" / "experiments" / "parent_collection_v1.json"
EXPERIMENT = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
PROTOCOL = PROJECT_ROOT / "configs" / "training" / "gasse_reconnected_v1.json"


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "raw"
    parent = (
        source_root
        / "CFL_easy_instance"
        / "LP"
        / "CFL_easy_instance_2.lp.gz"
    )
    parent.parent.mkdir(parents=True)
    parent.write_bytes(b"immutable-parent-mip")
    plan_dir = tmp_path / "parent-plan"
    parent_plan = write_parent_collection_plan(
        base_source_dir=source_root,
        output_dir=plan_dir,
        parent_manifest_path=MANIFEST,
        campaign_config_path=CAMPAIGN,
        experiment_config_path=EXPERIMENT,
        instances=("CFL_easy_instance_2",),
    )
    run_root = tmp_path / "parent-runs"
    for task in parent_plan["tasks"]:
        solver = task["solver"]
        run_dir = run_root / task["run_dir_relative_path"]
        run_dir.mkdir(parents=True)
        solution = run_dir / "parent_solution.json.gz"
        with gzip.open(solution, "wt", encoding="utf-8") as stream:
            json.dump(
                {
                    "solution_source": {
                        "gurobi": "independent_gurobi_optimization",
                        "scip": "independent_pyscipopt_optimization",
                    }[solver],
                    "variables": [
                        {"name": "x0", "value": 1.0},
                        {"name": "x1", "value": 0.0},
                    ],
                },
                stream,
            )
        report = {
            "contract_sha256": f"{solver}-solve-contract",
            "gate_status": "passed",
            "parent": {"sha256": task["parent_mip_sha256"]},
            "solve": {
                "mip_gap_relative": 0.05 if solver == "scip" else 0.0,
                "solution_objective": 6.5,
                "execution_time_seconds": 10.0,
            },
            "artifacts": {
                "solution": {
                    "file_name": solution.name,
                    "sha256": sha256_file(solution),
                }
            },
            "eligibility": {"label_eligible": True},
        }
        (run_dir / report_name(solver)).write_text(
            json.dumps(report), encoding="utf-8"
        )
    graph_root = tmp_path / "graphs"
    graph = graph_root / "graphs" / "CFL_easy_instance_2.pt"
    root = (
        graph_root
        / "root_relaxations"
        / "CFL_easy_instance_2.root.json.gz"
    )
    graph.parent.mkdir(parents=True)
    root.parent.mkdir(parents=True)
    graph.write_bytes(b"gurobi-authoritative-graph")
    with gzip.open(root, "wt", encoding="utf-8") as stream:
        json.dump({"variable_names": ["x0", "x1"]}, stream)
    manifest_record = {
        "sample_id": "CFL_easy_instance_2",
        "source_instance_id": "CFL_easy_instance_2",
        "category": "CFL_easy_instance",
        "difficulty": "easy",
        "fold": 2,
        "role": "train",
        "sampling_strategy": "original",
        "graph_authority": "gurobi",
        "mip_sha256": sha256_file(parent),
        "graph_relative_path": graph.relative_to(graph_root).as_posix(),
        "graph_sha256": sha256_file(graph),
        "root_relative_path": root.relative_to(graph_root).as_posix(),
        "root_sha256": sha256_file(root),
    }
    graph_manifest = graph_root / GRAPH_MANIFEST_NAME
    graph_manifest.write_text(json.dumps(manifest_record) + "\n", encoding="utf-8")
    graph_report = {
        "contract_sha256": "graph-contract",
        "gate_status": "passed",
        "graph_contract": {"authority": "gurobi"},
        "outputs": {
            GRAPH_MANIFEST_NAME: {"sha256": sha256_file(graph_manifest)}
        },
        "eligibility": {"dataset_eligible": True},
    }
    (graph_root / GRAPH_REPORT_NAME).write_text(
        json.dumps(graph_report), encoding="utf-8"
    )
    return graph_root, plan_dir, run_root


@pytest.mark.parametrize("solver", ["gurobi", "scip"])
def test_plan_uses_one_gurobi_graph_with_solver_specific_label_view(
    tmp_path: Path, solver: str
) -> None:
    graph_root, plan_dir, run_root = _fixture(tmp_path)

    plan = build_gasse_training_plan(
        graph_dataset_dir=graph_root,
        parent_collection_plan_dir=plan_dir,
        parent_collection_run_root=run_root,
        protocol_path=PROTOCOL,
        label_solver=solver,
        allow_partial_smoke=True,
    )

    validate_training_plan(plan)
    assert plan["graph_authority"] == "gurobi"
    assert plan["label_solver"] == solver
    assert plan["label_view"] == "named_solution_overlay_at_load_time"
    assert plan["partition_counts"] == {"train": 1, "validation": 0, "test": 0}
    assert plan["test_partition_usage"] == "held_out_not_loaded_during_training"
    assert plan["training_ready"] is False
    assert str(tmp_path) not in json.dumps(plan)


def test_partial_inventory_requires_explicit_engineering_smoke(tmp_path: Path) -> None:
    graph_root, plan_dir, run_root = _fixture(tmp_path)

    with pytest.raises(GasseTrainingError, match="train, validation"):
        build_gasse_training_plan(
            graph_dataset_dir=graph_root,
            parent_collection_plan_dir=plan_dir,
            parent_collection_run_root=run_root,
            protocol_path=PROTOCOL,
            label_solver="gurobi",
        )


def test_plan_fails_when_graph_mip_and_label_parent_differ(tmp_path: Path) -> None:
    graph_root, plan_dir, run_root = _fixture(tmp_path)
    manifest = graph_root / GRAPH_MANIFEST_NAME
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["mip_sha256"] = "0" * 64
    manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
    report = json.loads((graph_root / GRAPH_REPORT_NAME).read_text(encoding="utf-8"))
    report["outputs"][GRAPH_MANIFEST_NAME]["sha256"] = sha256_file(manifest)
    (graph_root / GRAPH_REPORT_NAME).write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(GasseTrainingError, match="graph MIP"):
        build_gasse_training_plan(
            graph_dataset_dir=graph_root,
            parent_collection_plan_dir=plan_dir,
            parent_collection_run_root=run_root,
            protocol_path=PROTOCOL,
            label_solver="gurobi",
            allow_partial_smoke=True,
        )


def test_preserved_gasse_model_is_git_blob_identical_to_legacy() -> None:
    path = PROJECT_ROOT / "src" / "cfl_gnn" / "models" / "gasse.py"
    assert git_blob_sha1(path) == LEGACY_GASSE_GIT_BLOB_SHA1


def test_validation_threshold_and_diagnostics_are_deterministic() -> None:
    targets = [0.0, 0.0, 1.0, 1.0]
    probabilities = [0.1, 0.4, 0.6, 0.9]

    assert threshold_from_validation(targets, probabilities) == 0.5
    assert confusion_counts(targets, probabilities, 0.6) == (2, 2, 0, 0)
    roc, precision_recall, roc_auc, pr_auc = binary_curve_rows(
        targets, probabilities
    )
    calibration = calibration_rows(targets, probabilities, bins=2)

    assert len(roc) == len(precision_recall)
    assert roc_auc == pytest.approx(1.0)
    assert pr_auc is not None and 0.0 <= pr_auc <= 1.0
    assert sum(row["count"] for row in calibration) == 4


def test_ddp_adapter_uses_disjoint_parent_balanced_rank_slices() -> None:
    source = (
        PROJECT_ROOT / "src" / "cfl_gnn" / "training" / "gasse_reconnected.py"
    ).read_text(encoding="utf-8")
    assert "global_indices[rank::world_size]" in source
    assert "dist.all_gather_object" in source
    assert '"test_graphs_loaded": 0' in source


def test_evaluation_plan_consumes_validation_threshold_and_test_only(
    tmp_path: Path,
) -> None:
    graph_root, plan_dir, run_root = _fixture(tmp_path)
    plan = build_gasse_training_plan(
        graph_dataset_dir=graph_root,
        parent_collection_plan_dir=plan_dir,
        parent_collection_run_root=run_root,
        protocol_path=PROTOCOL,
        label_solver="gurobi",
        allow_partial_smoke=True,
    )
    template = plan["records"][0]
    plan["records"] = [
        {
            **template,
            "sample_id": f"sample-{role}",
            "parent_instance_id": f"parent-{role}",
            "role": role,
        }
        for role in ("train", "validation", "test")
    ]
    plan["partition_counts"] = {"train": 1, "validation": 1, "test": 1}
    plan["parent_ids_by_role"] = {
        role: [f"parent-{role}"] for role in ("train", "validation", "test")
    }
    plan["training_ready"] = True
    plan["held_out_evaluation_ready"] = True
    ignored = {
        "contract_sha256",
        "contract_valid",
        "training_ready",
        "engineering_smoke_ready",
        "held_out_evaluation_ready",
        "warnings",
        "next_gate",
    }
    plan["contract_sha256"] = canonical_sha256(
        {key: value for key, value in plan.items() if key not in ignored}
    )
    training_plan_path = tmp_path / "gasse_training_plan.json"
    training_plan_path.write_text(json.dumps(plan), encoding="utf-8")
    checkpoint = tmp_path / "best_model.pt"
    checkpoint.write_bytes(b"checkpoint")
    training_report = {
        "gate_status": "passed",
        "training_contract_sha256": plan["contract_sha256"],
        "test_graphs_loaded": 0,
        "threshold_source": "maximum_validation_f1",
        "selected_probability_threshold": 0.37,
        "outputs": {
            "checkpoint": {"sha256": sha256_file(checkpoint)}
        },
    }
    training_report_path = tmp_path / "gasse_training_report.json"
    training_report_path.write_text(
        json.dumps(training_report), encoding="utf-8"
    )

    evaluation = build_evaluation_plan(
        training_plan_path=training_plan_path,
        training_report_path=training_report_path,
        checkpoint_path=checkpoint,
    )

    assert evaluation["probability_threshold"] == 0.37
    assert evaluation["threshold_source"] == "maximum_validation_f1"
    assert evaluation["test_partition_usage"] == "held_out_evaluation_only"
    assert {record["role"] for record in evaluation["test_records"]} == {"test"}


def test_reconnected_pipeline_has_no_random_split_or_hardcoded_dataset() -> None:
    sources = [
        PROJECT_ROOT / "src" / "cfl_gnn" / "training" / "gasse_reconnected.py",
        PROJECT_ROOT / "src" / "cfl_gnn" / "evaluation" / "gasse_reconnected.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    assert "random_split" not in text
    assert "/raid/" not in text
    assert "maximum_validation_f1" in text
