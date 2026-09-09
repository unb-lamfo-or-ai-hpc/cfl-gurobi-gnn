"""End-to-end provenance gate for the development-only MVP pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.analysis.mvp_neural_diving_comparison import (
    ARM_TABLE_NAME,
    EFFECT_TABLE_NAME,
    MANIFEST_NAME as COMPARISON_MANIFEST_NAME,
    PLAN_NAME as COMPARISON_PLAN_NAME,
    REPORT_NAME as COMPARISON_REPORT_NAME,
    RUN_TABLE_NAME,
    validate_plan as validate_comparison_plan,
)
from cfl_gnn.evaluation.mvp_four_arm import (
    METRICS_NAME as EVALUATION_METRICS_NAME,
    PLAN_NAME as EVALUATION_PLAN_NAME,
    REPORT_NAME as EVALUATION_REPORT_NAME,
)
from cfl_gnn.experiments.mvp_neural_diving import (
    COMPARISONS_NAME as BENCHMARK_COMPARISONS_NAME,
    PLAN_NAME as BENCHMARK_PLAN_NAME,
    REPORT_NAME as BENCHMARK_REPORT_NAME,
    RUN_METRICS_NAME as BENCHMARK_METRICS_NAME,
    validate_plan as validate_benchmark_plan,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.pipelines.mvp_dataset import (
    ARM_DIR,
    AUDIT_NAME as DATASET_AUDIT_NAME,
    MANIFEST_NAME as DATASET_MANIFEST_NAME,
    PLAN_NAME as DATASET_PLAN_NAME,
    REFERENCE_NAME as DATASET_REFERENCE_NAME,
    REPORT_NAME as DATASET_REPORT_NAME,
)
from cfl_gnn.training.mvp_four_arm import (
    ARM_SUMMARY_NAME,
    CHECKPOINT_NAME,
    EXPECTED_ARMS,
    HISTORY_NAME,
    RUN_PLAN_NAME as TRAINING_PLAN_NAME,
    RUN_REPORT_NAME as TRAINING_REPORT_NAME,
)


SCHEMA_VERSION = 1
PLAN_NAME = "mvp_pipeline_reproducibility_plan.json"
REPORT_NAME = "mvp_pipeline_reproducibility_report.json"
LEDGER_NAME = "mvp_pipeline_artifact_ledger.jsonl"
MANIFEST_NAME = "mvp_pipeline_reproducibility_manifest.json"
DEFAULT_CONFIG = (
    PROJECT_ROOT
    / "configs"
    / "evaluation"
    / "mvp_pipeline_reproducibility_v1.json"
)


class MvpPipelineReproducibilityError(RuntimeError):
    """Raised when an MVP provenance or artifact invariant fails closed."""


def canonical_sha256(value: Any) -> str:
    """Return a deterministic SHA-256 digest for a JSON-compatible value."""
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path, *, artifact: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise MvpPipelineReproducibilityError(
            f"unreadable {artifact}: {path.name}"
        ) from error
    if not isinstance(value, dict):
        raise MvpPipelineReproducibilityError(
            f"{artifact} must be a JSON object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _safe_file(root: Path, relative_value: Any, *, artifact: str) -> Path:
    relative = Path(str(relative_value))
    resolved_root = root.resolve()
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise MvpPipelineReproducibilityError(f"unsafe {artifact} path")
    resolved = (resolved_root / relative).resolve()
    if resolved_root not in resolved.parents or not resolved.is_file():
        raise MvpPipelineReproducibilityError(
            f"missing or unsafe {artifact}: {relative.as_posix()}"
        )
    return resolved


def _contract_digest(
    plan: Mapping[str, Any], excluded: set[str]
) -> str:
    return canonical_sha256(
        {key: value for key, value in plan.items() if key not in excluded}
    )


def _validate_embedded_contract(
    plan: Mapping[str, Any], *, stage: str, excluded: set[str]
) -> None:
    expected = _contract_digest(plan, excluded)
    if plan.get("contract_sha256") != expected:
        raise MvpPipelineReproducibilityError(
            f"{stage} plan contract mismatch"
        )


def _controls_passed(report: Mapping[str, Any], field: str) -> bool:
    controls = report.get(field)
    return (
        isinstance(controls, Mapping)
        and bool(controls)
        and all(value is True for value in controls.values())
    )


def _eligibility_is_development_only(report: Mapping[str, Any]) -> bool:
    eligibility = report.get("eligibility", {})
    return (
        isinstance(eligibility, Mapping)
        and eligibility.get("development_only") is True
        and eligibility.get("scientific_reporting_eligible") is False
    )


def _artifact_record(
    *,
    stage: str,
    kind: str,
    root: Path,
    relative_path: str | Path,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    relative = Path(relative_path)
    path = _safe_file(root, relative, artifact=f"{stage} {kind}")
    actual_sha256 = sha256_file(path)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise MvpPipelineReproducibilityError(
            f"{stage} {kind} SHA-256 mismatch"
        )
    return {
        "stage": stage,
        "artifact_kind": kind,
        "relative_path": relative.as_posix(),
        "sha256": actual_sha256,
        "size_bytes": path.stat().st_size,
    }


def _load_stage(root: Path, plan_name: str, report_name: str) -> dict[str, Any]:
    plan_path = _safe_file(root, plan_name, artifact="stage plan")
    report_path = _safe_file(root, report_name, artifact="stage report")
    return {
        "root": root.resolve(),
        "plan_path": plan_path,
        "report_path": report_path,
        "plan": _read_json(plan_path, artifact="stage plan"),
        "report": _read_json(report_path, artifact="stage report"),
    }


def _validate_config(config: Mapping[str, Any]) -> None:
    if (
        config.get("schema_version") != SCHEMA_VERSION
        or config.get("expected_stages")
        != ["dataset", "training", "evaluation", "benchmark", "comparison"]
        or config.get("expected_arms") != list(EXPECTED_ARMS)
        or config.get("required_gate_status") != "passed"
        or config.get("arm_selection_performed") is not False
        or config.get("development_only") is not True
        or config.get("scientific_reporting_eligible") is not False
    ):
        raise MvpPipelineReproducibilityError(
            "reproducibility configuration is not the precommitted policy"
        )


def _validate_contract_chain(stages: Mapping[str, Mapping[str, Any]]) -> None:
    dataset = stages["dataset"]
    training = stages["training"]
    evaluation = stages["evaluation"]
    benchmark = stages["benchmark"]
    comparison = stages["comparison"]

    _validate_embedded_contract(
        dataset["plan"],
        stage="dataset",
        excluded={"contract_sha256", "original_count", "derived_count"},
    )
    _validate_embedded_contract(
        training["plan"],
        stage="training",
        excluded={
            "contract_sha256",
            "contract_valid",
            "mvp_execution_ready",
            "test_graphs_loaded",
            "next_gate",
        },
    )
    _validate_embedded_contract(
        evaluation["plan"],
        stage="evaluation",
        excluded={
            "contract_sha256",
            "contract_valid",
            "arm_selection_performed",
            "all_four_arms_forwarded",
            "next_gate",
        },
    )
    try:
        validate_benchmark_plan(benchmark["plan"])
        validate_comparison_plan(comparison["plan"])
    except Exception as error:
        raise MvpPipelineReproducibilityError(
            "benchmark or comparison plan contract mismatch"
        ) from error

    dataset_contract = dataset["plan"]["contract_sha256"]
    training_contract = training["plan"]["contract_sha256"]
    evaluation_contract = evaluation["plan"]["contract_sha256"]
    benchmark_contract = benchmark["plan"]["contract_sha256"]
    comparison_contract = comparison["plan"]["contract_sha256"]
    links = {
        "dataset_plan_report": (
            dataset["report"].get("contract_sha256") == dataset_contract
        ),
        "dataset_training": (
            training["plan"].get("dataset_contract_sha256") == dataset_contract
        ),
        "training_plan_report": (
            training["report"].get("training_run_contract_sha256")
            == training_contract
        ),
        "training_evaluation": (
            evaluation["plan"].get("training_run_contract_sha256")
            == training_contract
            and evaluation["report"].get("training_run_contract_sha256")
            == training_contract
        ),
        "dataset_evaluation": (
            evaluation["plan"].get("dataset_contract_sha256")
            == dataset_contract
        ),
        "evaluation_plan_report": (
            evaluation["report"].get("evaluation_contract_sha256")
            == evaluation_contract
        ),
        "evaluation_benchmark": (
            benchmark["plan"].get("source_evaluation_contract_sha256")
            == evaluation_contract
        ),
        "benchmark_plan_report": (
            benchmark["report"].get("benchmark_contract_sha256")
            == benchmark_contract
        ),
        "benchmark_comparison": (
            comparison["plan"].get("source_benchmark_contract_sha256")
            == benchmark_contract
        ),
        "comparison_plan_report": (
            comparison["report"].get("comparison_contract_sha256")
            == comparison_contract
        ),
    }
    if not all(links.values()):
        failed = ",".join(key for key, value in links.items() if not value)
        raise MvpPipelineReproducibilityError(
            f"end-to-end contract chain failed: {failed}"
        )

    file_links = {
        "training_plan": (
            evaluation["plan"].get("training_plan_sha256")
            == sha256_file(training["plan_path"])
        ),
        "training_report": (
            evaluation["plan"].get("training_report_sha256")
            == sha256_file(training["report_path"])
        ),
        "evaluation_plan": (
            benchmark["plan"].get("source_evaluation_plan_sha256")
            == sha256_file(evaluation["plan_path"])
        ),
        "evaluation_report": (
            benchmark["plan"].get("source_evaluation_report_sha256")
            == sha256_file(evaluation["report_path"])
        ),
    }
    source_artifacts = comparison["plan"].get("source_artifacts", {})
    for name, file_name in (
        ("benchmark_plan", BENCHMARK_PLAN_NAME),
        ("benchmark_report", BENCHMARK_REPORT_NAME),
        ("per_run_metrics", BENCHMARK_METRICS_NAME),
        ("paired_comparisons", BENCHMARK_COMPARISONS_NAME),
    ):
        artifact = source_artifacts.get(name, {})
        file_links[f"comparison_{name}"] = (
            artifact.get("file_name") == file_name
            and artifact.get("sha256")
            == sha256_file(_safe_file(benchmark["root"], file_name, artifact=name))
        )
    if not all(file_links.values()):
        failed = ",".join(key for key, value in file_links.items() if not value)
        raise MvpPipelineReproducibilityError(
            f"source artifact chain failed: {failed}"
        )


def _validate_stage_gates(stages: Mapping[str, Mapping[str, Any]]) -> None:
    for stage, value in stages.items():
        if value["report"].get("gate_status") != "passed":
            raise MvpPipelineReproducibilityError(
                f"{stage} source gate did not pass"
            )
        if not _eligibility_is_development_only(value["report"]):
            raise MvpPipelineReproducibilityError(
                f"{stage} eligibility semantics changed"
            )
    for stage, field in (
        ("training", "paired_controls"),
        ("evaluation", "common_controls"),
        ("benchmark", "common_controls"),
        ("comparison", "common_controls"),
    ):
        if not _controls_passed(stages[stage]["report"], field):
            raise MvpPipelineReproducibilityError(
                f"{stage} common controls did not pass"
            )
    evaluation = stages["evaluation"]
    if evaluation["report"].get("arm_selection", {}).get("performed") is not False:
        raise MvpPipelineReproducibilityError(
            "evaluation performed forbidden arm selection"
        )


def _collect_ledger(
    stages: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for stage, value in stages.items():
        records.extend(
            [
                _artifact_record(
                    stage=stage,
                    kind="plan",
                    root=value["root"],
                    relative_path=value["plan_path"].name,
                ),
                _artifact_record(
                    stage=stage,
                    kind="report",
                    root=value["root"],
                    relative_path=value["report_path"].name,
                ),
            ]
        )

    dataset = stages["dataset"]
    dataset_outputs = dataset["report"]["outputs"]
    for kind, name, sha_field in (
        ("sample_manifest", DATASET_MANIFEST_NAME, "sample_manifest_sha256"),
        ("graph_audit", DATASET_AUDIT_NAME, "original_graph_audit_sha256"),
        (
            "evaluation_reference",
            DATASET_REFERENCE_NAME,
            "evaluation_reference_manifest_sha256",
        ),
    ):
        records.append(
            _artifact_record(
                stage="dataset",
                kind=kind,
                root=dataset["root"],
                relative_path=name,
                expected_sha256=dataset_outputs.get(sha_field),
            )
        )
    for arm_id in EXPECTED_ARMS:
        records.append(
            _artifact_record(
                stage="dataset",
                kind="arm_manifest",
                root=dataset["root"],
                relative_path=Path(ARM_DIR) / f"{arm_id}.jsonl",
                expected_sha256=dataset["report"]["arms"][arm_id]["sha256"],
            )
        )

    training = stages["training"]
    for arm_id in EXPECTED_ARMS:
        arm = training["report"]["arms"][arm_id]
        arm_root = Path("arms") / arm_id
        records.extend(
            [
                _artifact_record(
                    stage="training",
                    kind="checkpoint",
                    root=training["root"],
                    relative_path=arm_root / CHECKPOINT_NAME,
                    expected_sha256=arm["checkpoint"]["sha256"],
                ),
                _artifact_record(
                    stage="training",
                    kind="history",
                    root=training["root"],
                    relative_path=arm_root / HISTORY_NAME,
                    expected_sha256=arm["history"]["sha256"],
                ),
                _artifact_record(
                    stage="training",
                    kind="arm_summary",
                    root=training["root"],
                    relative_path=arm_root / ARM_SUMMARY_NAME,
                    expected_sha256=arm["summary_sha256"],
                ),
            ]
        )

    evaluation = stages["evaluation"]
    records.append(
        _artifact_record(
            stage="evaluation",
            kind="per_arm_metrics",
            root=evaluation["root"],
            relative_path=EVALUATION_METRICS_NAME,
            expected_sha256=evaluation["report"]["outputs"][
                "per_arm_metrics_sha256"
            ],
        )
    )
    for arm_id in EXPECTED_ARMS:
        for hint in evaluation["report"]["arms"][arm_id]["hint_artifacts"]:
            records.append(
                _artifact_record(
                    stage="evaluation",
                    kind="solver_neutral_hint",
                    root=evaluation["root"],
                    relative_path=hint["relative_path"],
                    expected_sha256=hint["sha256"],
                )
            )

    benchmark = stages["benchmark"]
    for kind, name, sha_field in (
        ("per_run_metrics", BENCHMARK_METRICS_NAME, "per_run_metrics_sha256"),
        (
            "paired_comparisons",
            BENCHMARK_COMPARISONS_NAME,
            "paired_comparisons_sha256",
        ),
    ):
        records.append(
            _artifact_record(
                stage="benchmark",
                kind=kind,
                root=benchmark["root"],
                relative_path=name,
                expected_sha256=benchmark["report"]["outputs"][sha_field],
            )
        )
    task_sha = {
        item["relative_path"]: item["sha256"]
        for item in stages["comparison"]["plan"]["source_task_results"]
    }
    for task in benchmark["plan"]["tasks"]:
        relative = task["output_relative_path"]
        records.append(
            _artifact_record(
                stage="benchmark",
                kind="task_result",
                root=benchmark["root"],
                relative_path=relative,
                expected_sha256=task_sha.get(relative),
            )
        )

    comparison = stages["comparison"]
    for kind, output_key, name in (
        ("per_run_table", RUN_TABLE_NAME, RUN_TABLE_NAME),
        ("per_arm_table", ARM_TABLE_NAME, ARM_TABLE_NAME),
        ("paired_effect_table", EFFECT_TABLE_NAME, EFFECT_TABLE_NAME),
        (
            "comparison_manifest",
            "reproducibility_manifest",
            COMPARISON_MANIFEST_NAME,
        ),
    ):
        output = comparison["report"]["outputs"][output_key]
        records.append(
            _artifact_record(
                stage="comparison",
                kind=kind,
                root=comparison["root"],
                relative_path=output["file_name"],
                expected_sha256=output["sha256"],
            )
        )
    return sorted(
        records,
        key=lambda item: (
            item["stage"],
            item["artifact_kind"],
            item["relative_path"],
        ),
    )


def _load_pipeline(
    *,
    dataset_dir: str | Path,
    training_dir: str | Path,
    evaluation_dir: str | Path,
    benchmark_dir: str | Path,
    comparison_dir: str | Path,
) -> dict[str, dict[str, Any]]:
    roots = {
        "dataset": (Path(dataset_dir), DATASET_PLAN_NAME, DATASET_REPORT_NAME),
        "training": (Path(training_dir), TRAINING_PLAN_NAME, TRAINING_REPORT_NAME),
        "evaluation": (
            Path(evaluation_dir),
            EVALUATION_PLAN_NAME,
            EVALUATION_REPORT_NAME,
        ),
        "benchmark": (
            Path(benchmark_dir),
            BENCHMARK_PLAN_NAME,
            BENCHMARK_REPORT_NAME,
        ),
        "comparison": (
            Path(comparison_dir),
            COMPARISON_PLAN_NAME,
            COMPARISON_REPORT_NAME,
        ),
    }
    stages = {
        stage: _load_stage(root, plan_name, report_name)
        for stage, (root, plan_name, report_name) in roots.items()
    }
    _validate_contract_chain(stages)
    _validate_stage_gates(stages)
    return stages


def build_plan(
    *,
    dataset_dir: str | Path,
    training_dir: str | Path,
    evaluation_dir: str | Path,
    benchmark_dir: str | Path,
    comparison_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Verify the source chain and precommit the reproducibility audit."""
    config_file = Path(config_path).resolve()
    config = _read_json(config_file, artifact="reproducibility configuration")
    _validate_config(config)
    stages = _load_pipeline(
        dataset_dir=dataset_dir,
        training_dir=training_dir,
        evaluation_dir=evaluation_dir,
        benchmark_dir=benchmark_dir,
        comparison_dir=comparison_dir,
    )
    source_contracts = {
        stage: value["plan"]["contract_sha256"]
        for stage, value in stages.items()
    }
    source_artifacts = {
        stage: {
            "plan": {
                "file_name": value["plan_path"].name,
                "sha256": sha256_file(value["plan_path"]),
            },
            "report": {
                "file_name": value["report_path"].name,
                "sha256": sha256_file(value["report_path"]),
            },
        }
        for stage, value in stages.items()
    }
    contract = {
        "schema_version": SCHEMA_VERSION,
        "audit_stage": "mvp_pipeline_end_to_end_reproducibility",
        "source_contracts": source_contracts,
        "source_artifacts": source_artifacts,
        "configuration": config,
        "configuration_sha256": sha256_file(config_file),
        "development_only": True,
        "scientific_reporting_eligible": False,
        "arm_selection_performed": False,
    }
    return {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "contract_valid": True,
        "next_gate": "mvp_pipeline_reproducibility_execution",
    }


def validate_plan(plan: Mapping[str, Any]) -> None:
    excluded = {"contract_sha256", "contract_valid", "next_gate"}
    if (
        plan.get("contract_valid") is not True
        or plan.get("contract_sha256") != _contract_digest(plan, excluded)
    ):
        raise MvpPipelineReproducibilityError(
            "reproducibility plan contract mismatch"
        )


def run_audit(
    *,
    dataset_dir: str | Path,
    training_dir: str | Path,
    evaluation_dir: str | Path,
    benchmark_dir: str | Path,
    comparison_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write the immutable plan and, unless dry, the verified artifact ledger."""
    output = Path(output_dir).resolve()
    existing = [output / PLAN_NAME, output / REPORT_NAME, output / LEDGER_NAME]
    if not overwrite and any(path.exists() for path in existing):
        raise FileExistsError("reproducibility output exists; use --overwrite")
    plan = build_plan(
        dataset_dir=dataset_dir,
        training_dir=training_dir,
        evaluation_dir=evaluation_dir,
        benchmark_dir=benchmark_dir,
        comparison_dir=comparison_dir,
        config_path=config_path,
    )
    validate_plan(plan)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / PLAN_NAME, plan)
    if dry_run:
        return plan

    stages = _load_pipeline(
        dataset_dir=dataset_dir,
        training_dir=training_dir,
        evaluation_dir=evaluation_dir,
        benchmark_dir=benchmark_dir,
        comparison_dir=comparison_dir,
    )
    current_plan = build_plan(
        dataset_dir=dataset_dir,
        training_dir=training_dir,
        evaluation_dir=evaluation_dir,
        benchmark_dir=benchmark_dir,
        comparison_dir=comparison_dir,
        config_path=config_path,
    )
    if current_plan["contract_sha256"] != plan["contract_sha256"]:
        raise MvpPipelineReproducibilityError(
            "source chain changed between planning and execution"
        )
    ledger = _collect_ledger(stages)
    with (output / LEDGER_NAME).open("w", encoding="utf-8", newline="\n") as stream:
        for record in ledger:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    ledger_sha256 = sha256_file(output / LEDGER_NAME)
    stage_counts = {
        stage: sum(record["stage"] == stage for record in ledger)
        for stage in plan["configuration"]["expected_stages"]
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "reproducibility_contract_sha256": plan["contract_sha256"],
        "source_contracts": plan["source_contracts"],
        "source_artifacts": plan["source_artifacts"],
        "artifact_ledger": {
            "file_name": LEDGER_NAME,
            "sha256": ledger_sha256,
            "records": len(ledger),
            "records_by_stage": stage_counts,
        },
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    _write_json(output / MANIFEST_NAME, manifest)
    report = {
        "schema_version": SCHEMA_VERSION,
        "reproducibility_contract_sha256": plan["contract_sha256"],
        "probe_completed": True,
        "gate_status": "passed",
        "contract_chain": {
            "stages": plan["configuration"]["expected_stages"],
            "links_verified": 10,
            "status": "passed",
        },
        "artifact_ledger": manifest["artifact_ledger"],
        "common_controls": {
            "all_source_gates_passed": True,
            "all_source_contracts_recomputed": True,
            "all_cross_stage_contract_links_match": True,
            "all_cross_stage_artifact_hashes_match": True,
            "all_ledger_artifacts_sha256_verified": True,
            "all_paths_sanitized_and_relative": True,
            "four_arms_preserved_without_selection": True,
            "development_only_semantics_preserved": True,
            "scientific_reporting_disabled": True,
        },
        "outputs": {
            "artifact_ledger": {
                "file_name": LEDGER_NAME,
                "sha256": ledger_sha256,
            },
            "reproducibility_manifest": {
                "file_name": MANIFEST_NAME,
                "sha256": sha256_file(output / MANIFEST_NAME),
            },
        },
        "eligibility": {
            "pipeline_execution_ready": True,
            "publication_output_layer_ready": True,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "reason_code": "mvp_end_to_end_reproducibility_gate_passed",
            "next_gate": "mvp_publication_tables_and_figures",
        },
    }
    _write_json(output / REPORT_NAME, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit the complete development-only MVP artifact chain."
    )
    parser.add_argument("--dataset_dir", required=True)
    parser.add_argument("--training_dir", required=True)
    parser.add_argument("--evaluation_dir", required=True)
    parser.add_argument("--benchmark_dir", required=True)
    parser.add_argument("--comparison_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_audit(
            dataset_dir=args.dataset_dir,
            training_dir=args.training_dir,
            evaluation_dir=args.evaluation_dir,
            benchmark_dir=args.benchmark_dir,
            comparison_dir=args.comparison_dir,
            output_dir=args.output_dir,
            config_path=args.config,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
    except (MvpPipelineReproducibilityError, FileExistsError) as error:
        print(f"[ERROR] {error}")
        return 1
    if args.dry_run:
        print(
            f"[INFO] contract={result['contract_sha256']} | "
            "stages=5 | dry_run=true"
        )
        print(f"[INFO] Plan: {Path(args.output_dir).resolve() / PLAN_NAME}")
    else:
        print(
            f"[INFO] gate={result['gate_status']} | "
            f"artifacts={result['artifact_ledger']['records']} | "
            "next=mvp_publication_tables_and_figures"
        )
        print(f"[INFO] Report: {Path(args.output_dir).resolve() / REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
