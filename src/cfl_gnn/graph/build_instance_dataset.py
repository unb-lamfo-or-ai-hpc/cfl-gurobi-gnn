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
import os
import pickle
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pyarrow.parquet as pq
import torch

from cfl_gnn.graph.build_dataset import build_heterodata
from cfl_gnn.graph.instance_selection import (
    SolutionSelectionError,
    require_minimization,
    select_best_solution,
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


def _iter_solution_pool(
    pool_path: Path, metadata: Mapping[str, Any]
) -> Iterable[dict[str, Any]]:
    if not pool_path.is_file() or pool_path.stat().st_size == 0:
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
        logger.warning("Could not load solution pool %s: %s", pool_path, error)
        return
    for index, solution in enumerate(solutions):
        if not isinstance(solution, Mapping):
            logger.warning("Ignoring malformed solution %s in %s", index, pool_path)
            continue
        yield {
            **solution,
            "mip_gap": metadata.get("mip_gap"),
            "time": metadata.get("runtime"),
            "node": metadata.get("node_count"),
            "source": pool_path.name,
            "source_index": index,
        }


def _iter_incumbents(incumbents_path: Path) -> Iterable[dict[str, Any]]:
    if not incumbents_path.is_file() or incumbents_path.stat().st_size == 0:
        return
    source_index = 0
    try:
        parquet_file = pq.ParquetFile(incumbents_path)
        for batch in parquet_file.iter_batches(batch_size=32):
            frame = batch.to_pandas()
            for record in frame.to_dict(orient="records"):
                yield {
                    **record,
                    "source": incumbents_path.name,
                    "source_index": source_index,
                }
                source_index += 1
            del frame
    except Exception as error:
        logger.warning("Could not load incumbents %s: %s", incumbents_path, error)


def _root_relaxation(instance_dir: Path, num_vars: int) -> np.ndarray:
    relaxation_path = instance_dir / "node_relaxations.parquet"
    if not relaxation_path.is_file() or relaxation_path.stat().st_size == 0:
        return np.zeros(num_vars, dtype=np.float64)
    try:
        table = pq.read_table(
            relaxation_path,
            columns=["node", "relaxation_vector"],
            filters=[("node", "==", 0)],
        )
        if table.num_rows:
            vector = np.asarray(table.column("relaxation_vector")[0].as_py())
            if len(vector) == num_vars:
                return vector
    except Exception as error:
        logger.warning("Could not load root relaxation from %s: %s", instance_dir, error)
    return np.zeros(num_vars, dtype=np.float64)


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


def _process_instance(
    entry: InstanceFold,
    *,
    raw_root: Path,
    output_root: Path,
    overwrite: bool,
) -> dict[str, Any]:
    instance_dir = raw_root / entry.category / entry.source_instance_id
    output_path = output_root / entry.category / "processed" / (
        f"{entry.source_instance_id}.pt"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.is_file() and output_path.stat().st_size > 0 and not overwrite:
        return {
            "instance": entry.source_instance_id,
            "status": "skipped_existing",
            "output": str(output_path),
        }

    with (instance_dir / "metadata.json").open("r", encoding="utf-8") as stream:
        metadata = json.load(stream)
    with gzip.open(instance_dir / "original_features.pickle.gz", "rb") as stream:
        raw = pickle.load(stream)

    model_features = raw["model_features"]
    require_minimization(metadata, model_features.obj_sense)

    candidates = itertools.chain(
        _iter_solution_pool(instance_dir / "solutions.pickle.gz", metadata),
        _iter_incumbents(instance_dir / "incumbents.parquet"),
    )
    selected = select_best_solution(
        candidates,
        expected_num_vars=model_features.num_vars,
    )
    root_relaxation = _root_relaxation(instance_dir, model_features.num_vars)

    graph = build_heterodata(
        model_features,
        raw["variable_features"],
        raw["constraint_features"],
        raw["edge_indices"],
        raw["edge_features"],
        np.asarray(selected.solution_vector),
        root_relaxation,
        selected.mip_gap if selected.mip_gap is not None else 1.0,
        selected.time if selected.time is not None else 0.0,
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
    graph.label_source = selected.source
    graph.label_source_index = int(selected.source_index)
    graph.label_objective = float(selected.objective)
    torch.save(graph, output_path)

    result = {
        "instance": entry.source_instance_id,
        "status": "generated",
        "fold": entry.fold,
        "label_source": selected.source,
        "label_objective": selected.objective,
        "label_mip_gap": selected.mip_gap,
        "output": str(output_path),
    }
    del graph, raw, root_relaxation
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
        "--base_raw_dir",
        type=Path,
        default=Path("/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps"),
    )
    parser.add_argument(
        "--base_pyg_dir",
        type=Path,
        default=Path(
            "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/instance_baseline"
        ),
    )
    parser.add_argument("--categories", nargs="+", choices=list(CATEGORIES))
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
    requested = [entry for entry in manifest if entry.category in selected_categories]

    all_available = [
        entry
        for entry in manifest
        if _is_available(
            args.base_raw_dir / entry.category / entry.source_instance_id
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
                raw_root=args.base_raw_dir,
                output_root=args.base_pyg_dir,
                overwrite=args.overwrite,
            )
            results.append(result)
            logger.info(
                "%s | %s | fold=%s | source=%s",
                entry.source_instance_id,
                result["status"],
                entry.fold,
                result.get("label_source", "existing"),
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
        "schema_version": 1,
        "sampling_strategy": "parent_instance_best_available",
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
        "available_instances": len(all_available),
        "requested_instances": len(requested),
        "requested_available": len(requested_available),
        "population_status": "complete" if complete_population else "development_partial",
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
