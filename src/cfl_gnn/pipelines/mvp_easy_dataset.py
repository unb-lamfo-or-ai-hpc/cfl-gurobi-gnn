"""Compose the easy-only four-arm dataset from PR #33 evidence."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.experiments.mvp_contract import (
    load_experiment_config,
    read_sample_manifest,
)
from cfl_gnn.experiments.mvp_easy_vertical_slice import (
    CENSORED_EVIDENCE_NAME,
    LABEL_INDEX_NAME,
    PARENT_MANIFEST_NAME,
    PLAN_NAME as EASY_SLICE_PLAN_NAME,
    REPORT_NAME as EASY_SLICE_REPORT_NAME,
)
from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.pipelines.derived_graphs import DerivedGraphError, GRAPH_FEATURE_SCHEMA
from cfl_gnn.pipelines.mvp_dataset import (
    MANIFEST_NAME,
    PLAN_NAME,
    REPORT_NAME,
    DatasetPlan,
    MvpDatasetError,
    OriginalGraphSpec,
    _canonical_sha256,
    _finite,
    _read_gzip_json,
    _read_json,
    _read_jsonl,
    _safe_derived_graph,
    _write_json,
    run_composition,
)
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold


DATASET_VARIANT = "mvp_easy_four_arm_dataset"
SOLVERS = ("gurobi", "scip")
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "experiments" / "mvp_partial_v1.json"
DEFAULT_PARENT_MANIFEST = (
    PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
)


def _contract_from_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in {"contract_sha256", "outputs"}
    }


def _safe_relative(root: Path, relative_value: Any, *, field: str) -> Path:
    relative = Path(str(relative_value))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise MvpDatasetError(f"unsafe {field} path")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved_root not in resolved.parents:
        raise MvpDatasetError(f"{field} escapes its artifact root")
    return resolved


def _load_easy_contract(
    easy_root: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    plan_path = easy_root / EASY_SLICE_PLAN_NAME
    report_path = easy_root / EASY_SLICE_REPORT_NAME
    parents_path = easy_root / PARENT_MANIFEST_NAME
    labels_path = easy_root / LABEL_INDEX_NAME
    censored_path = easy_root / CENSORED_EVIDENCE_NAME
    plan = _read_json(plan_path)
    report = _read_json(report_path)
    parents = _read_jsonl(parents_path)
    labels = _read_jsonl(labels_path)
    censored = _read_jsonl(censored_path)
    contract_sha256 = _canonical_sha256(_contract_from_summary(plan))
    checks = {
        "easy_contract_valid": plan.get("contract_sha256") == contract_sha256,
        "report_contract_match": report.get("contract_sha256") == contract_sha256,
        "easy_gate_passed": report.get("gate_status") == "passed",
        "easy_slice_ready": report.get("eligibility", {}).get(
            "easy_vertical_slice_composition_ready"
        )
        is True,
        "development_only": report.get("eligibility", {}).get("development_only")
        is True,
        "scientific_reporting_disabled": report.get("eligibility", {}).get(
            "scientific_reporting_eligible"
        )
        is False,
        "parent_manifest_match": parents == plan.get("parents"),
        "label_index_match": labels == plan.get("labels"),
        "censored_evidence_match": _canonical_sha256(censored)
        == plan.get("censored_evidence_sha256"),
        "train_only_augmentation": plan.get("augmentation_policy", {}).get(
            "train_only"
        )
        is True,
        "evaluation_original_only": plan.get("augmentation_policy", {}).get(
            "validation_test_original_only"
        )
        is True,
    }
    if not all(checks.values()):
        raise MvpDatasetError("PR #33 easy-slice contract is not admissible")
    return plan, parents, labels, checks


def _original_specs(
    *,
    parents: Sequence[Mapping[str, Any]],
    labels: Sequence[Mapping[str, Any]],
    benchmark_root: Path,
    base_source_dir: Path,
    experiment_contract_sha256: str,
    canonical_parents: Mapping[str, tuple[int, str, str]],
    maximum_gap: float,
) -> tuple[OriginalGraphSpec, ...]:
    labels_by_parent: dict[str, list[Mapping[str, Any]]] = {}
    for label in labels:
        labels_by_parent.setdefault(str(label.get("source_instance_id")), []).append(label)
    specs: list[OriginalGraphSpec] = []
    for parent in parents:
        parent_id = str(parent["source_instance_id"])
        role = str(parent["role"])
        try:
            fold, category, difficulty = canonical_parents[parent_id]
        except KeyError as error:
            raise MvpDatasetError(f"unknown easy parent: {parent_id}") from error
        if (
            fold != int(parent["fold"])
            or category != parent["category"]
            or difficulty != "easy"
            or difficulty != parent["difficulty"]
            or role != role_for_fold(fold, 0)
        ):
            raise MvpDatasetError(f"easy parent metadata mismatch: {parent_id}")
        candidate = _safe_relative(
            base_source_dir,
            parent["parent_mip_relative_path"],
            field="parent MIP",
        )
        if not candidate.is_file() or sha256_file(candidate) != parent.get(
            "parent_mip_sha256"
        ):
            raise MvpDatasetError(f"easy parent fingerprint mismatch: {parent_id}")
        parent_labels = labels_by_parent.get(parent_id, [])
        for arm_solver in SOLVERS:
            matching = (
                [
                    label
                    for label in parent_labels
                    if label.get("label_use") == "solver_arm_training_label"
                    and label.get("source_solver") == arm_solver
                ]
                if role == "train"
                else [
                    label
                    for label in parent_labels
                    if label.get("label_use") == "common_evaluation_reference"
                ]
            )
            if len(matching) != 1:
                raise MvpDatasetError(
                    f"expected one easy label for {parent_id}:{arm_solver}"
                )
            label = matching[0]
            artifact = label.get("solution_artifact", {})
            if not isinstance(artifact, Mapping):
                raise MvpDatasetError("easy label solution descriptor is missing")
            solution = _safe_relative(
                benchmark_root,
                artifact.get("relative_path"),
                field="label solution",
            )
            if not solution.is_file() or sha256_file(solution) != artifact.get(
                "sha256"
            ):
                raise MvpDatasetError(f"easy label fingerprint mismatch: {parent_id}")
            payload = _read_gzip_json(solution)
            if payload.get("candidate_sha256") != parent["parent_mip_sha256"]:
                raise MvpDatasetError("easy label is linked to another parent MIP")
            objective = _finite(label.get("solution_objective"), field="label objective")
            if not math.isclose(
                objective,
                _finite(payload.get("solution_objective"), field="solution objective"),
                rel_tol=1e-8,
                abs_tol=1e-8,
            ):
                raise MvpDatasetError("easy label objective disagrees with its artifact")
            gap = _finite(
                label.get("mip_gap_relative"), field="label gap", nonnegative=True
            )
            if gap > maximum_gap + 1e-12:
                raise MvpDatasetError("easy label violates the MIP-gap policy")
            source_solver = str(label.get("source_solver"))
            if source_solver not in SOLVERS:
                raise MvpDatasetError("easy label has an unknown source solver")
            specs.append(
                OriginalGraphSpec(
                    solver=arm_solver,
                    sample_id=f"{parent_id}__{arm_solver}__original",
                    parent_instance_id=parent_id,
                    category=category,
                    difficulty=difficulty,
                    fold=fold,
                    role=role,
                    candidate_path=candidate,
                    candidate_sha256=str(parent["parent_mip_sha256"]),
                    solution_path=solution,
                    solution_sha256=str(artifact["sha256"]),
                    label_source_solver=source_solver,
                    label_use=str(label["label_use"]),
                    parent_solve_contract_sha256=str(
                        label["parent_contract_sha256"]
                    ),
                    experiment_contract_sha256=experiment_contract_sha256,
                    label_objective=objective,
                    label_mip_gap_relative=gap,
                    label_mip_gap_percent=100.0 * gap,
                    label_execution_time_seconds=_finite(
                        label.get("execution_time_seconds"),
                        field="label execution time",
                        nonnegative=True,
                    ),
                )
            )
    return tuple(sorted(specs, key=lambda item: item.sample_id))


def _derived_records(
    *,
    derived_root: Path,
    experiment_contract_sha256: str,
    train_parent_id: str,
) -> tuple[str, tuple[dict[str, Any], ...], dict[str, Any]]:
    manifest_path = derived_root / MANIFEST_NAME
    manifest_sha256 = sha256_file(manifest_path)
    report_path = derived_root / "mvp_derived_graph_report.json"
    report = _read_json(report_path)
    checks = {
        "derived_gate_passed": report.get("gate_status") == "passed",
        "derived_dataset_eligible": report.get("eligibility", {}).get(
            "dataset_eligible"
        )
        is True,
        "derived_experiment_contract_match": report.get(
            "experiment_contract_sha256"
        )
        == experiment_contract_sha256,
        "derived_manifest_hash_match": report.get("outputs", {}).get(
            "sample_manifest_sha256"
        )
        == manifest_sha256,
    }
    if not all(checks.values()):
        raise MvpDatasetError("derived graph report is not admissible")
    records = _read_jsonl(manifest_path)
    parsed = read_sample_manifest(manifest_path)
    if len(records) != len(parsed) or len(records) != 6:
        raise MvpDatasetError("easy dataset requires exactly six derived graphs")
    by_solver = {solver: 0 for solver in SOLVERS}
    for record in records:
        solver = str(record.get("solver"))
        if (
            solver not in SOLVERS
            or record.get("parent_instance_id") != train_parent_id
            or record.get("difficulty") != "easy"
            or int(record.get("fold", -1)) != 2
            or record.get("sampling_strategy") != "incumbent_local_branching"
        ):
            raise MvpDatasetError("derived graph lies outside the easy training cell")
        by_solver[solver] += 1
        graph = _safe_derived_graph(derived_root, record.get("graph_path"))
        if not graph.is_file() or sha256_file(graph) != record.get("graph_sha256"):
            raise MvpDatasetError("derived graph fingerprint mismatch")
        provenance_path = (
            derived_root
            / "provenance"
            / solver
            / f"{record['sample_id']}.provenance.json"
        )
        provenance = _read_json(provenance_path)
        if (
            provenance.get("eligibility", {}).get("dataset_eligible") is not True
            or provenance.get("sample", {}).get("sample_id") != record["sample_id"]
            or provenance.get("graph", {}).get("graph_sha256")
            != record["graph_sha256"]
        ):
            raise MvpDatasetError("derived graph provenance is not admissible")
    if by_solver != {"gurobi": 3, "scip": 3}:
        raise MvpDatasetError("derived graphs are not symmetric across solvers")
    return manifest_sha256, tuple(sorted(records, key=lambda item: item["sample_id"])), checks


def build_easy_plan(
    *,
    easy_slice_dir: str | Path,
    benchmark_run_root: str | Path,
    derived_graph_dir: str | Path,
    base_source_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path,
    parent_manifest_path: str | Path,
) -> DatasetPlan:
    """Validate PR #33 plus PR #28 and prepare the easy four-arm plan."""
    easy_root = Path(easy_slice_dir).resolve()
    benchmark_root = Path(benchmark_run_root).resolve()
    derived_root = Path(derived_graph_dir).resolve()
    config = load_experiment_config(config_path)
    if config.rotation != 0:
        raise MvpDatasetError("the easy MVP slice requires rotation zero")
    easy_plan, parents, labels, easy_checks = _load_easy_contract(easy_root)
    if not math.isclose(
        float(easy_plan["maximum_admissible_relative_gap"]),
        config.gap_policy.maximum_admissible_relative_gap,
        abs_tol=1e-12,
    ):
        raise MvpDatasetError("easy slice and MVP gap policies disagree")
    manifest = read_manifest(parent_manifest_path)
    canonical_parents = {
        item.source_instance_id: (item.fold, item.category, item.difficulty)
        for item in manifest
    }
    originals = _original_specs(
        parents=parents,
        labels=labels,
        benchmark_root=benchmark_root,
        base_source_dir=Path(base_source_dir).resolve(),
        experiment_contract_sha256=config.contract_sha256,
        canonical_parents=canonical_parents,
        maximum_gap=config.gap_policy.maximum_admissible_relative_gap,
    )
    train_parents = [item for item in parents if item["role"] == "train"]
    if len(train_parents) != 1:
        raise MvpDatasetError("easy slice requires exactly one training parent")
    derived_sha, derived_records, derived_checks = _derived_records(
        derived_root=derived_root,
        experiment_contract_sha256=config.contract_sha256,
        train_parent_id=str(train_parents[0]["source_instance_id"]),
    )
    evidence = {
        "schema_version": 1,
        "easy_slice_contract_sha256": easy_plan["contract_sha256"],
        "easy_slice_plan_sha256": sha256_file(easy_root / EASY_SLICE_PLAN_NAME),
        "easy_slice_report_sha256": sha256_file(easy_root / EASY_SLICE_REPORT_NAME),
        "easy_parent_manifest_sha256": sha256_file(
            easy_root / PARENT_MANIFEST_NAME
        ),
        "easy_label_index_sha256": sha256_file(easy_root / LABEL_INDEX_NAME),
        "derived_graph_report_sha256": sha256_file(
            derived_root / "mvp_derived_graph_report.json"
        ),
        "derived_manifest_sha256": derived_sha,
        "easy_slice_checks": easy_checks,
        "derived_graph_checks": derived_checks,
        "augmentation_center_policy": (
            "independent_admissible_same_solver_parent_incumbent"
        ),
        "common_evaluation_label_policy": (
            "same_pr33_reference_replicated_across_solver_arms"
        ),
    }
    return DatasetPlan(
        output_dir=Path(output_dir).resolve(),
        derived_graph_dir=derived_root,
        derived_manifest_sha256=derived_sha,
        experiment_contract_sha256=config.contract_sha256,
        originals=originals,
        derived_records=derived_records,
        source_evidence_contract=evidence,
        dataset_variant=DATASET_VARIANT,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compose the development-only easy four-arm MVP dataset."
    )
    parser.add_argument("--easy_slice_dir", type=Path, required=True)
    parser.add_argument("--benchmark_run_root", type=Path, required=True)
    parser.add_argument("--derived_graph_dir", type=Path, required=True)
    parser.add_argument("--base_source_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--parent_manifest", type=Path, default=DEFAULT_PARENT_MANIFEST)
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = build_easy_plan(
            easy_slice_dir=args.easy_slice_dir,
            benchmark_run_root=args.benchmark_run_root,
            derived_graph_dir=args.derived_graph_dir,
            base_source_dir=args.base_source_dir,
            output_dir=args.output_dir,
            config_path=args.config,
            parent_manifest_path=args.parent_manifest,
        )
        plan.output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(plan.output_dir / PLAN_NAME, plan.to_summary())
        print(
            f"[INFO] contract={plan.contract_sha256} | "
            f"originals={len(plan.originals)} | derived={len(plan.derived_records)}"
        )
        print("[INFO] parents=3 | train=easy-2 | validation=easy-1 | test=easy-0")
        print(f"[INFO] Plan: {plan.output_dir / PLAN_NAME}")
        if args.dry_run:
            return 0
        report = run_composition(
            plan,
            config_path=args.config,
            parent_manifest_path=args.parent_manifest,
            overwrite=args.overwrite,
        )
        print(
            f"[INFO] gate={report['gate_status']} | "
            f"original={report['summary']['original_graphs_written']} | "
            f"derived={report['summary']['derived_graphs_materialized']}"
        )
        print(f"[INFO] Report: {plan.output_dir / REPORT_NAME}")
        return 0
    except (
        OSError,
        TypeError,
        ValueError,
        DerivedGraphError,
        MvpDatasetError,
    ) as error:
        print(f"[ERROR] {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
