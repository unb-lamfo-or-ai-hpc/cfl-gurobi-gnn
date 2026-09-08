from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from cfl_gnn.experiments.mvp_contract import load_experiment_config
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines import mvp_easy_dataset as pipeline
from cfl_gnn.pipelines.mvp_dataset import ARM_DIR, MANIFEST_NAME, REFERENCE_NAME


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
PARENT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
CATEGORY = "CFL_easy_instance"
PARENTS = (
    ("CFL_easy_instance_0", 0, "test"),
    ("CFL_easy_instance_1", 1, "validation"),
    ("CFL_easy_instance_2", 2, "train"),
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def _write_solution(
    path: Path, *, parent_sha256: str, objective: float
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(
            {
                "candidate_sha256": parent_sha256,
                "solution_objective": objective,
                "variables": [{"name": "x", "value": 1.0}],
            },
            stream,
        )
    return sha256_file(path)


def _easy_slice_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, list[dict[str, object]]]:
    raw_root = tmp_path / "raw"
    benchmark_root = tmp_path / "benchmark"
    easy_root = tmp_path / "easy_slice"
    parents: list[dict[str, object]] = []
    labels: list[dict[str, object]] = []
    for parent_id, fold, role in PARENTS:
        candidate = raw_root / CATEGORY / "LP" / f"{parent_id}.lp.gz"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(f"mip:{parent_id}".encode())
        parent_sha256 = sha256_file(candidate)
        parents.append(
            {
                "source_instance_id": parent_id,
                "category": CATEGORY,
                "difficulty": "easy",
                "fold": fold,
                "role": role,
                "parent_mip_relative_path": (
                    Path(CATEGORY) / "LP" / candidate.name
                ).as_posix(),
                "parent_mip_sha256": parent_sha256,
            }
        )
        source_solvers = ("gurobi", "scip") if role == "train" else ("scip",)
        for source_solver in source_solvers:
            objective = 6.0 + fold + (0.1 if source_solver == "scip" else 0.0)
            relative = Path(source_solver) / parent_id / "parent_solution.json.gz"
            solution_sha256 = _write_solution(
                benchmark_root / relative,
                parent_sha256=parent_sha256,
                objective=objective,
            )
            labels.append(
                {
                    "label_id": f"{parent_id}__{source_solver}",
                    "source_instance_id": parent_id,
                    "role": role,
                    "difficulty": "easy",
                    "source_solver": source_solver,
                    "label_use": (
                        "solver_arm_training_label"
                        if role == "train"
                        else "common_evaluation_reference"
                    ),
                    "solution_objective": objective,
                    "mip_gap_relative": 0.01,
                    "execution_time_seconds": 100.0 + fold,
                    "solution_artifact": {
                        "relative_path": relative.as_posix(),
                        "sha256": solution_sha256,
                    },
                    "parent_contract_sha256": source_solver[0] * 64,
                }
            )
    censored = [
        {"evidence_id": f"censored-{index}", "status": "right_censored"}
        for index in range(9)
    ]
    contract_payload = {
        "schema_version": 1,
        "maximum_admissible_relative_gap": 0.10,
        "augmentation_policy": {
            "train_only": True,
            "validation_test_original_only": True,
        },
        "parents": parents,
        "labels": labels,
        "censored_evidence_sha256": pipeline._canonical_sha256(censored),
    }
    contract_sha256 = pipeline._canonical_sha256(contract_payload)
    _write_json(
        easy_root / pipeline.EASY_SLICE_PLAN_NAME,
        {**contract_payload, "contract_sha256": contract_sha256, "outputs": {}},
    )
    _write_jsonl(easy_root / pipeline.PARENT_MANIFEST_NAME, parents)
    _write_jsonl(easy_root / pipeline.LABEL_INDEX_NAME, labels)
    _write_jsonl(easy_root / pipeline.CENSORED_EVIDENCE_NAME, censored)
    _write_json(
        easy_root / pipeline.EASY_SLICE_REPORT_NAME,
        {
            "contract_sha256": contract_sha256,
            "gate_status": "passed",
            "eligibility": {
                "easy_vertical_slice_composition_ready": True,
                "development_only": True,
                "scientific_reporting_eligible": False,
            },
        },
    )
    return easy_root, benchmark_root, raw_root, parents


def _derived_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "derived"
    records: list[dict[str, object]] = []
    for solver in pipeline.SOLVERS:
        for radius, fraction in ((1, 0.001), (5, 0.005), (10, 0.01)):
            sample_id = f"CFL_easy_instance_2__{solver}__lb_r{radius}"
            graph = root / "graphs" / solver / f"{sample_id}.pt"
            graph.parent.mkdir(parents=True, exist_ok=True)
            graph.write_bytes(f"graph:{sample_id}".encode())
            record = {
                "sample_id": sample_id,
                "parent_instance_id": "CFL_easy_instance_2",
                "category": CATEGORY,
                "difficulty": "easy",
                "fold": 2,
                "solver": solver,
                "sampling_strategy": "incumbent_local_branching",
                "graph_path": (Path("graphs") / solver / graph.name).as_posix(),
                "graph_sha256": sha256_file(graph),
                "label_source": f"{sample_id}.solution.json.gz",
                "label_solution_sha256": (
                    "c" if solver == "gurobi" else "d"
                )
                * 64,
                "label_objective": 6.0,
                "label_mip_gap_relative": 0.0,
                "label_mip_gap_percent": 0.0,
                "label_execution_time_seconds": 50.0,
                "source_incumbent_id": f"{solver}:incumbent",
                "source_incumbent_artifact_sha256": ("a" if solver == "gurobi" else "b")
                * 64,
                "source_incumbent_objective": 6.5,
                "source_incumbent_mip_gap_relative": 0.05,
                "source_incumbent_mip_gap_percent": 5.0,
                "source_incumbent_execution_time_seconds": 100.0,
                "local_branching_radius": radius,
                "local_branching_radius_fraction": fraction,
            }
            records.append(record)
            _write_json(
                root
                / "provenance"
                / solver
                / f"{sample_id}.provenance.json",
                {
                    "sample": {"sample_id": sample_id},
                    "graph": {"graph_sha256": record["graph_sha256"]},
                    "eligibility": {"dataset_eligible": True},
                },
            )
    _write_jsonl(root / MANIFEST_NAME, records)
    _write_json(
        root / "mvp_derived_graph_report.json",
        {
            "gate_status": "passed",
            "experiment_contract_sha256": load_experiment_config(
                CONFIG
            ).contract_sha256,
            "outputs": {
                "sample_manifest_sha256": sha256_file(root / MANIFEST_NAME)
            },
            "eligibility": {"dataset_eligible": True},
        },
    )
    return root


def _plan(tmp_path: Path) -> pipeline.DatasetPlan:
    easy, benchmark, raw, _ = _easy_slice_fixture(tmp_path)
    derived = _derived_fixture(tmp_path)
    return pipeline.build_easy_plan(
        easy_slice_dir=easy,
        benchmark_run_root=benchmark,
        derived_graph_dir=derived,
        base_source_dir=raw,
        output_dir=tmp_path / "output",
        config_path=CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
    )


def test_easy_plan_has_symmetric_labels_and_is_path_free(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    assert plan.dataset_variant == pipeline.DATASET_VARIANT
    assert len(plan.originals) == 6
    assert len(plan.derived_records) == 6
    train = [item for item in plan.originals if item.role == "train"]
    assert {item.solver for item in train} == {"gurobi", "scip"}
    assert all(item.label_source_solver == item.solver for item in train)
    for role in ("validation", "test"):
        records = [item for item in plan.originals if item.role == role]
        assert len({item.solution_sha256 for item in records}) == 1
        assert len({item.label_source_solver for item in records}) == 1
    assert str(tmp_path) not in json.dumps(plan.to_summary())


def test_easy_composition_writes_expected_four_arm_dataset(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    def fake_builder(spec: pipeline.OriginalGraphSpec, output: Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(spec.sample_id.encode())
        return {
            "graph_sha256": sha256_file(output),
            "structural_graph_sha256": spec.parent_instance_id,
            "graph_content_sha256": spec.sample_id,
            "variables": 3,
            "constraints": 2,
            "nonzeros": 4,
            "binary_variables": 1,
            "integer_variables": 0,
            "continuous_variables": 2,
            "input_objective_sense": "MAXIMIZE",
            "effective_objective_sense": "MINIMIZE",
            "objective_sense_override_applied": True,
            "roundtrip_readable": True,
            "label_variable_identity_match": True,
        }

    report = pipeline.run_composition(
        plan,
        config_path=CONFIG,
        parent_manifest_path=PARENT_MANIFEST,
        overwrite=False,
        graph_builder=fake_builder,
    )
    assert report["gate_status"] == "passed"
    assert report["summary"]["original_graphs_written"] == 6
    assert report["summary"]["derived_graphs_materialized"] == 6
    assert report["summary"]["unified_manifest_records"] == 12
    assert report["summary"]["common_evaluation_labels_match_across_arms"]
    assert report["summary"]["derived_train_only"]
    assert report["decision"]["reason_code"] == (
        "easy_only_four_arm_dataset_admissible"
    )
    expected = {
        "gurobi_original": {"test": 1, "train": 1, "validation": 1},
        "scip_original": {"test": 1, "train": 1, "validation": 1},
        "gurobi_incumbent_augmented": {
            "test": 1,
            "train": 4,
            "validation": 1,
        },
        "scip_incumbent_augmented": {
            "test": 1,
            "train": 4,
            "validation": 1,
        },
    }
    assert {
        arm: value["partitions"] for arm, value in report["arms"].items()
    } == expected
    manifest = pipeline._read_jsonl(plan.output_dir / MANIFEST_NAME)
    assert len(manifest) == 12
    assert all("label_source_solver" in item for item in manifest)
    references = pipeline._read_jsonl(plan.output_dir / REFERENCE_NAME)
    assert len(references) == 3
    assert all(item["candidate_count"] == 2 for item in references)
    for solver in pipeline.SOLVERS:
        augmented = pipeline._read_jsonl(
            plan.output_dir / ARM_DIR / f"{solver}_incumbent_augmented.jsonl"
        )
        train = [item for item in augmented if item["role"] == "train"]
        assert len(train) == 4
        assert {item["sample_weight"] for item in train} == {0.25}


def test_easy_plan_rejects_tampered_label_artifact(tmp_path: Path) -> None:
    easy, benchmark, raw, _ = _easy_slice_fixture(tmp_path)
    derived = _derived_fixture(tmp_path)
    target = benchmark / "scip" / "CFL_easy_instance_0" / "parent_solution.json.gz"
    target.write_bytes(b"tampered")
    with pytest.raises(pipeline.MvpDatasetError, match="label fingerprint"):
        pipeline.build_easy_plan(
            easy_slice_dir=easy,
            benchmark_run_root=benchmark,
            derived_graph_dir=derived,
            base_source_dir=raw,
            output_dir=tmp_path / "output",
            config_path=CONFIG,
            parent_manifest_path=PARENT_MANIFEST,
        )


def test_dasci_launcher_is_lf_only_and_submit_directory_aware() -> None:
    launcher = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_mvp_easy_dataset_composition.sbs"
    )
    payload = launcher.read_bytes()
    assert b"\r" not in payload
    text = payload.decode("utf-8")
    assert "SLURM_SUBMIT_DIR" in text
    assert "--easy_slice_dir" in text
    assert "--derived_graph_dir" in text
