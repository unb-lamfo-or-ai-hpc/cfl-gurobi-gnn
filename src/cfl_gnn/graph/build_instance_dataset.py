"""Build one PyG graph per available Gurobi parent instance.

This is an explicit sibling of the preserved incumbent-conditioned ETL. It
selects one best available minimization label, writes stable instance-named
files to a separate output root, and carries the canonical parent fold into
every graph.
"""

from __future__ import annotations

import argparse
import gc
import gzip
import itertools
import json
import logging
import math
import pickle
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pyarrow.parquet as pq
import torch

from cfl_gnn.graph.build_dataset import build_heterodata
from cfl_gnn.graph.instance_provenance import (
    RAW_DATASET,
    STRUCTURE_ARTIFACT,
    load_verified_graph_provenance,
    mip_gap_band,
    normalize_recorded_time,
    provenance_path,
    resolve_raw_instance_path,
    sha256_file,
    summarize_label_quality,
)
from cfl_gnn.graph.instance_selection import (
    SolutionSelectionError,
    require_minimization,
    select_best_solution_with_audit,
)
from cfl_gnn.paths import PROJECT_ROOT
from cfl_gnn.splits.instance_folds import (
    CATEGORIES,
    InstanceFold,
    read_manifest,
    validate_manifest,
)


logger = logging.getLogger(__name__)
DEFAULT_MANIFEST = PROJECT_ROOT / "configs" / "splits" / "cfl_90_seed42_folds.csv"
DEFAULT_SOURCE_ROOT = Path(
    "/raid/vrcelestino/data/cfl-gurobi-gnn/data/raw/MILPBench/CFL"
)


def _iter_solution_pool(
    pool_path: Path,
    metadata: Mapping[str, Any],
    artifact_audit: dict[str, Any],
) -> Iterable[dict[str, Any]]:
    artifact_audit.update(
        {
            "artifact_path": str(pool_path.resolve()),
            "load_status": "missing",
            "records_read": 0,
        }
    )
    if not pool_path.is_file():
        return
    if pool_path.stat().st_size == 0:
        artifact_audit["load_status"] = "empty"
        return
    try:
        with gzip.open(pool_path, "rb") as stream:
            payload = pickle.load(stream)
        if not isinstance(payload, Mapping):
            raise TypeError("solution-pool payload is not a mapping")
        solutions = payload.get("solution_pool", [])
        if not isinstance(solutions, (list, tuple)):
            raise TypeError("solution_pool is not a sequence")
    except Exception as error:
        artifact_audit["load_status"] = "load_error"
        artifact_audit["load_error_type"] = type(error).__name__
        logger.warning("Could not load solution pool %s: %s", pool_path, error)
        return
    artifact_audit["load_status"] = "loaded"
    for index, solution in enumerate(solutions):
        artifact_audit["records_read"] += 1
        if not isinstance(solution, Mapping):
            logger.warning("Ignoring malformed solution %s in %s", index, pool_path)
            yield {
                "source": pool_path.name,
                "source_index": index,
            }
            continue
        yield {
            **solution,
            "mip_gap": metadata.get("mip_gap"),
            "time": metadata.get("runtime"),
            "node": metadata.get("node_count"),
            "source": pool_path.name,
            "source_index": index,
        }


def _iter_incumbents(
    incumbents_path: Path, artifact_audit: dict[str, Any]
) -> Iterable[dict[str, Any]]:
    artifact_audit.update(
        {
            "artifact_path": str(incumbents_path.resolve()),
            "load_status": "missing",
            "records_read": 0,
        }
    )
    if not incumbents_path.is_file():
        return
    if incumbents_path.stat().st_size == 0:
        artifact_audit["load_status"] = "empty"
        return
    source_index = 0
    try:
        parquet_file = pq.ParquetFile(incumbents_path)
        artifact_audit["load_status"] = "loaded"
        for batch in parquet_file.iter_batches(batch_size=32):
            frame = batch.to_pandas()
            for record in frame.to_dict(orient="records"):
                yield {
                    **record,
                    "source": incumbents_path.name,
                    "source_index": source_index,
                }
                source_index += 1
                artifact_audit["records_read"] += 1
            del frame
    except Exception as error:
        artifact_audit["load_status"] = "load_error"
        artifact_audit["load_error_type"] = type(error).__name__
        logger.warning("Could not load incumbents %s: %s", incumbents_path, error)


def _minimum_recorded_incumbent_time(incumbents_path: Path) -> float | None:
    """Return the first legacy wall-clock incumbent timestamp, when present."""
    minimum = math.inf
    try:
        parquet_file = pq.ParquetFile(incumbents_path)
        for batch in parquet_file.iter_batches(columns=["time"], batch_size=1024):
            for value in batch.column(0).to_pylist():
                try:
                    candidate = float(value)
                except (TypeError, ValueError, OverflowError):
                    continue
                if math.isfinite(candidate) and candidate >= 0.0:
                    minimum = min(minimum, candidate)
    except Exception as error:
        logger.warning("Could not determine incumbent time origin: %s", error)
    return minimum if math.isfinite(minimum) else None


def _root_relaxation(
    instance_dir: Path, num_vars: int
) -> tuple[np.ndarray, dict[str, Any]]:
    relaxation_path = instance_dir / "node_relaxations.parquet"
    if not relaxation_path.is_file() or relaxation_path.stat().st_size == 0:
        return np.zeros(num_vars, dtype=np.float64), {
            "feature": "root_lp_relaxation",
            "mode": "zeros_missing_artifact",
            "artifact": None,
            "artifact_path": None,
            "artifact_sha256": None,
        }
    provenance = {
        "feature": "root_lp_relaxation",
        "mode": "zeros_unreadable_or_invalid_artifact",
        "artifact": relaxation_path.name,
        "artifact_path": str(relaxation_path.resolve()),
        "artifact_sha256": sha256_file(relaxation_path),
    }
    try:
        table = pq.read_table(
            relaxation_path,
            columns=["node", "relaxation_vector"],
            filters=[("node", "==", 0)],
        )
        if table.num_rows:
            vector = np.asarray(table.column("relaxation_vector")[0].as_py())
            if len(vector) == num_vars:
                provenance["mode"] = "root_node_relaxation"
                return vector, provenance
    except Exception as error:
        logger.warning("Could not load root relaxation from %s: %s", instance_dir, error)
    return np.zeros(num_vars, dtype=np.float64), provenance


def _has_label_source(instance_dir: Path) -> bool:
    return any(
        path.is_file() and path.stat().st_size > 0
        for path in (
            instance_dir / "solutions.pickle.gz",
            instance_dir / "incumbents.parquet",
        )
    )


def _is_available(instance_dir: Path) -> bool:
    required = (
        instance_dir / "original_features.pickle.gz",
        instance_dir / "metadata.json",
    )
    return all(path.is_file() and path.stat().st_size > 0 for path in required) and (
        _has_label_source(instance_dir)
    )


def _existing_result(
    output_path: Path, entry: InstanceFold, instance_dir: Path
) -> dict[str, Any] | None:
    result = load_verified_graph_provenance(
        output_path,
        expected_instance=entry.source_instance_id,
        expected_fold=entry.fold,
        current_relaxation_path=instance_dir / "node_relaxations.parquet",
    )
    if result is None:
        return None
    result["status"] = "skipped_existing"
    result["output"] = str(output_path)
    result["provenance_file"] = str(provenance_path(output_path))
    return result


def _write_provenance(output_path: Path, result: Mapping[str, Any]) -> Path:
    sidecar_path = provenance_path(output_path)
    temporary_path = sidecar_path.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    temporary_path.replace(sidecar_path)
    return sidecar_path


def _process_instance(
    entry: InstanceFold,
    *,
    intermediate_root: Path,
    source_root: Path,
    output_root: Path,
    overwrite: bool,
) -> dict[str, Any]:
    instance_dir = intermediate_root / entry.category / entry.source_instance_id
    output_path = output_root / entry.category / "processed" / (
        f"{entry.source_instance_id}.pt"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        existing = _existing_result(output_path, entry, instance_dir)
        if existing is not None:
            return existing
        if output_path.exists():
            logger.warning(
                "Regenerating %s because its provenance sidecar is missing or stale",
                entry.source_instance_id,
            )

    metadata_path = instance_dir / "metadata.json"
    with metadata_path.open("r", encoding="utf-8") as stream:
        metadata = json.load(stream)
    recorded_instance = metadata.get("instance")
    if recorded_instance is not None and recorded_instance != entry.source_instance_id:
        raise SolutionSelectionError(
            f"metadata instance mismatch: {recorded_instance!r}"
        )

    structure_path = instance_dir / STRUCTURE_ARTIFACT
    raw_instance_path = resolve_raw_instance_path(
        metadata,
        source_root=source_root,
        category=entry.category,
        source_instance_id=entry.source_instance_id,
    )
    structure_provenance = {
        "raw_dataset": RAW_DATASET,
        "raw_instance_path": str(raw_instance_path),
        "raw_instance_recorded_path": metadata.get("lp_file"),
        "raw_instance_sha256": sha256_file(raw_instance_path),
        "feature_artifact": STRUCTURE_ARTIFACT,
        "feature_artifact_path": str(structure_path.resolve()),
        "feature_artifact_sha256": sha256_file(structure_path),
        "relationship": "features_extracted_from_raw_instance",
    }
    collection_provenance = {
        "artifact": metadata_path.name,
        "artifact_path": str(metadata_path.resolve()),
        "artifact_sha256": sha256_file(metadata_path),
        "objective_sense_override": metadata.get("objective_sense_override"),
        "original_objective_sense": metadata.get("original_objective_sense"),
    }

    with gzip.open(structure_path, "rb") as stream:
        raw = pickle.load(stream)

    model_features = raw["model_features"]
    require_minimization(metadata, model_features.obj_sense)

    solution_pool_path = instance_dir / "solutions.pickle.gz"
    incumbents_path = instance_dir / "incumbents.parquet"
    artifact_loading = {
        solution_pool_path.name: {},
        incumbents_path.name: {},
    }
    candidates = itertools.chain(
        _iter_solution_pool(
            solution_pool_path,
            metadata,
            artifact_loading[solution_pool_path.name],
        ),
        _iter_incumbents(
            incumbents_path,
            artifact_loading[incumbents_path.name],
        ),
    )
    selected, candidate_audit = select_best_solution_with_audit(
        candidates,
        expected_num_vars=model_features.num_vars,
    )
    for artifact, loading in artifact_loading.items():
        candidate_audit["by_artifact"][artifact].update(loading)

    label_artifact_path = instance_dir / selected.source
    epoch_origin = (
        _minimum_recorded_incumbent_time(incumbents_path)
        if selected.source == incumbents_path.name
        and selected.time is not None
        and selected.time > 1e8
        else None
    )
    time_provenance = normalize_recorded_time(
        selected.time,
        epoch_origin=epoch_origin,
    )
    label_provenance = {
        "role": "supervised_variable_target",
        "artifact": selected.source,
        "artifact_path": str(label_artifact_path.resolve()),
        "artifact_sha256": sha256_file(label_artifact_path),
        "source_index": int(selected.source_index),
        "objective": float(selected.objective),
        "mip_gap": selected.mip_gap,
        "mip_gap_band": mip_gap_band(selected.mip_gap),
        **time_provenance,
        "node": selected.node,
    }
    root_relaxation, context_provenance = _root_relaxation(
        instance_dir, model_features.num_vars
    )
    label_vector = np.array(selected.solution_vector, dtype=np.float64, copy=True)
    normalized_time = time_provenance["normalized_time"]

    graph = build_heterodata(
        model_features,
        raw["variable_features"],
        raw["constraint_features"],
        raw["edge_indices"],
        raw["edge_features"],
        label_vector,
        root_relaxation,
        selected.mip_gap if selected.mip_gap is not None else 1.0,
        float(normalized_time) if normalized_time is not None else 0.0,
        bool(selected.mip_gap is not None and selected.mip_gap <= 1e-4),
        selected.node if selected.node is not None else -1,
        entry.source_instance_id,
        metadata,
    )
    if graph is None:
        raise SolutionSelectionError("graph construction returned no graph")

    graph.source_instance_id = entry.source_instance_id
    graph.instance_fold = int(entry.fold)
    graph.parent_category = entry.category
    graph.sampling_strategy = "parent_instance_best_available"
    graph.structure_source = STRUCTURE_ARTIFACT
    graph.raw_dataset = RAW_DATASET
    graph.raw_instance_path = structure_provenance["raw_instance_path"]
    graph.raw_instance_sha256 = structure_provenance["raw_instance_sha256"]
    graph.structure_artifact_path = structure_provenance["feature_artifact_path"]
    graph.structure_artifact_sha256 = structure_provenance[
        "feature_artifact_sha256"
    ]
    graph.collection_metadata_sha256 = collection_provenance["artifact_sha256"]
    graph.root_relaxation_mode = context_provenance["mode"]
    graph.root_relaxation_artifact_path = context_provenance["artifact_path"] or ""
    graph.root_relaxation_artifact_sha256 = (
        context_provenance["artifact_sha256"] or ""
    )
    graph.label_source = selected.source
    graph.label_artifact_path = label_provenance["artifact_path"]
    graph.label_artifact_sha256 = label_provenance["artifact_sha256"]
    graph.label_source_index = int(selected.source_index)
    graph.label_objective = float(selected.objective)
    graph.label_mip_gap_band = label_provenance["mip_gap_band"]
    graph.label_time_normalization_method = label_provenance[
        "time_normalization_method"
    ]
    graph.label_selection_reason = candidate_audit["selection_reason"]
    graph.label_candidates_evaluated = int(
        candidate_audit["evaluated_candidates"]
    )
    graph.label_candidates_valid = int(candidate_audit["valid_candidates"])
    torch.save(graph, output_path)

    result = {
        "schema_version": 2,
        "instance": entry.source_instance_id,
        "status": "generated",
        "fold": entry.fold,
        "parent_category": entry.category,
        "sampling_strategy": "parent_instance_best_available",
        "objective_sense": "MINIMIZE",
        "label_source": selected.source,
        "structure_provenance": structure_provenance,
        "collection_provenance": collection_provenance,
        "context_provenance": context_provenance,
        "label_provenance": label_provenance,
        "candidate_audit": candidate_audit,
        "output": str(output_path),
        "graph_sha256": sha256_file(output_path),
    }
    provenance_path = _write_provenance(output_path, result)
    result["provenance_file"] = str(provenance_path)
    del graph, raw, root_relaxation, label_vector
    gc.collect()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build one best-available PyG graph per Gurobi parent instance."
    )
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST, help="Canonical fold CSV."
    )
    parser.add_argument(
        "--base_intermediate_dir",
        "--base_raw_dir",
        dest="base_intermediate_dir",
        type=Path,
        default=Path("/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps"),
        help=(
            "Collected Gurobi artifacts. --base_raw_dir remains as a compatibility "
            "alias."
        ),
    )
    parser.add_argument(
        "--base_source_dir",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="Root containing MILPBench/CFL/<category>/LP/*.lp.gz.",
    )
    parser.add_argument(
        "--base_pyg_dir",
        type=Path,
        default=Path(
            "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/instance_baseline"
        ),
    )
    parser.add_argument("--categories", nargs="+", choices=list(CATEGORIES))
    parser.add_argument(
        "--instances",
        nargs="+",
        help="Optional source_instance_id subset for a targeted smoke run.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--strict_inventory",
        action="store_true",
        help="Return non-zero unless every canonical parent instance is generated.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    manifest = read_manifest(args.manifest)
    validate_manifest(manifest)
    selected_categories = set(args.categories or CATEGORIES)
    selected_instances = set(args.instances or ())
    unknown_instances = selected_instances - {
        entry.source_instance_id for entry in manifest
    }
    if unknown_instances:
        parser.error(
            "unknown source_instance_id: " + ", ".join(sorted(unknown_instances))
        )
    requested = [
        entry
        for entry in manifest
        if entry.category in selected_categories
        and (
            not selected_instances
            or entry.source_instance_id in selected_instances
        )
    ]

    all_available = [
        entry
        for entry in manifest
        if _is_available(
            args.base_intermediate_dir / entry.category / entry.source_instance_id
        )
    ]
    requested_available = [entry for entry in requested if entry in all_available]
    missing_requested = [
        entry.source_instance_id
        for entry in requested
        if entry not in requested_available
    ]

    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for entry in requested_available:
        try:
            result = _process_instance(
                entry,
                intermediate_root=args.base_intermediate_dir,
                source_root=args.base_source_dir,
                output_root=args.base_pyg_dir,
                overwrite=args.overwrite,
            )
            results.append(result)
            logger.info(
                "%s | %s | fold=%s | label_source=%s",
                entry.source_instance_id,
                result["status"],
                entry.fold,
                result.get("label_provenance", {}).get("artifact", "unknown"),
            )
        except Exception as error:
            logger.exception("Failed to build %s", entry.source_instance_id)
            failures.append({"instance": entry.source_instance_id, "error": str(error)})

    complete_population = (
        len(requested) == len(manifest)
        and len(all_available) == len(manifest)
        and len(results) == len(manifest)
        and not failures
    )
    summary = {
        "schema_version": 3,
        "sampling_strategy": "parent_instance_best_available",
        "structure_source": {
            "raw_dataset": RAW_DATASET,
            "raw_file_pattern": "<category>/LP/<source_instance_id>.lp.gz",
            "feature_artifact": STRUCTURE_ARTIFACT,
            "relationship": "features_extracted_from_raw_instance",
        },
        "context_source": {
            "feature": "root_lp_relaxation",
            "candidate_artifact": "node_relaxations.parquet",
            "fallback": "zeros_when_root_relaxation_is_missing_or_invalid",
        },
        "label_source": {
            "role": "supervised_variable_target_only",
            "candidate_artifacts": [
                "solutions.pickle.gz",
                "incumbents.parquet",
            ],
        },
        "selection_order": [
            "minimum_objective",
            "minimum_mip_gap",
            "solution_pool_at_tie",
            "minimum_time",
            "minimum_node",
            "source_index",
        ],
        "objective_sense": "MINIMIZE",
        "manifest": str(args.manifest),
        "planned_instances": len(manifest),
        "base_source_dir": str(args.base_source_dir),
        "base_intermediate_dir": str(args.base_intermediate_dir),
        "available_instances": len(all_available),
        "intermediate_available_instances": len(all_available),
        "requested_instances": len(requested),
        "requested_available": len(requested_available),
        "successful_instances": len(results),
        "population_status": "complete" if complete_population else "development_partial",
        "label_quality_summary": summarize_label_quality(results),
        "missing_requested": missing_requested,
        "results": results,
        "failures": failures,
    }
    args.base_pyg_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.base_pyg_dir / "instance_dataset_summary.json"
    with summary_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)
    logger.info("Summary: %s", summary_path)

    if args.strict_inventory and not complete_population:
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
