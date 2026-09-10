"""Deterministic PCA and descriptive clustering for graph manifests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


REPORT_NAME = "graph_clustering_report.json"
TABLE_NAME = "graph_clustering.csv"
FIGURE_NAME = "graph_clustering.svg"
FEATURES = ("density", "discrete_fraction", "constraint_variable_ratio")


class GraphClusteringError(RuntimeError):
    """Raised when deterministic graph clustering cannot be audited."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise TypeError("manifest record is not an object")
                    records.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise GraphClusteringError("graph manifest is unreadable") from error
    if not records:
        raise GraphClusteringError("graph manifest is empty")
    return records


def _standardize(matrix: np.ndarray) -> np.ndarray:
    means = matrix.mean(axis=0)
    standard_deviations = matrix.std(axis=0)
    standard_deviations[standard_deviations == 0.0] = 1.0
    return (matrix - means) / standard_deviations


def _pca(matrix: np.ndarray) -> tuple[np.ndarray, list[float]]:
    if len(matrix) == 1:
        return np.zeros((1, 2), dtype=np.float64), [0.0, 0.0]
    _, singular, right = np.linalg.svd(matrix, full_matrices=False)
    coordinates = matrix @ right[:2].T
    if coordinates.shape[1] == 1:
        coordinates = np.column_stack([coordinates[:, 0], np.zeros(len(matrix))])
    variance = singular**2
    total = float(variance.sum())
    ratios = (variance / total).tolist() if total else [0.0] * len(variance)
    return coordinates[:, :2], (ratios + [0.0, 0.0])[:2]


def _kmeans(matrix: np.ndarray, clusters: int) -> np.ndarray:
    if clusters <= 1:
        return np.zeros(len(matrix), dtype=np.int64)
    order = np.argsort(matrix[:, 0], kind="stable")
    positions = np.linspace(0, len(order) - 1, clusters).round().astype(int)
    centroids = matrix[order[positions]].copy()
    assignments = np.full(len(matrix), -1, dtype=np.int64)
    for _ in range(100):
        distances = ((matrix[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        updated = distances.argmin(axis=1)
        if np.array_equal(updated, assignments):
            break
        assignments = updated
        for cluster in range(clusters):
            members = matrix[assignments == cluster]
            if len(members):
                centroids[cluster] = members.mean(axis=0)
    return assignments


def _scatter_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    width, height = 720, 520
    x_values = [float(row["pca_component_1"]) for row in rows]
    y_values = [float(row["pca_component_2"]) for row in rows]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    x_span = x_max - x_min or 1.0
    y_span = y_max - y_min or 1.0
    colors = ("#3264a8", "#d1495b", "#2a9d8f")
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="360" y="30" text-anchor="middle" font-size="18">'
        "Graph PCA and deterministic clusters</text>",
    ]
    for row, x_value, y_value in zip(rows, x_values, y_values):
        x = 70 + 580 * (x_value - x_min) / x_span
        y = 450 - 370 * (y_value - y_min) / y_span
        color = colors[int(row["cluster_id"]) % len(colors)]
        elements.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="{color}"/>')
    elements.append('</svg>')
    return "\n".join(elements) + "\n"


def cluster_graph_manifest(
    *,
    manifest_path: str | Path,
    graph_root: str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Project audited macro-features and assign deterministic clusters."""
    import torch

    manifest = Path(manifest_path).resolve()
    root = Path(graph_root).resolve()
    output = Path(output_dir).resolve()
    expected = [output / REPORT_NAME, output / TABLE_NAME, output / FIGURE_NAME]
    if not overwrite and any(path.exists() for path in expected):
        raise GraphClusteringError("clustering output exists; use --overwrite")
    output.mkdir(parents=True, exist_ok=True)
    records = sorted(_read_jsonl(manifest), key=lambda item: str(item["sample_id"]))
    raw: list[dict[str, Any]] = []
    identities: set[str] = set()
    for record in records:
        sample_id = str(record.get("sample_id", ""))
        if not sample_id or sample_id in identities:
            raise GraphClusteringError("invalid or duplicate graph identity")
        identities.add(sample_id)
        path = root / str(record["graph_relative_path"])
        if not path.is_file() or _sha256(path) != record.get("graph_sha256"):
            raise GraphClusteringError(f"graph artifact failed SHA-256: {sample_id}")
        graph = torch.load(path, map_location="cpu", weights_only=False)
        variables = int(graph["variable"].x.shape[0])
        constraints = int(graph["constraint"].x.shape[0])
        nonzeros = int(
            graph["variable", "rev_coef", "constraint"].edge_index.shape[1]
        )
        raw.append(
            {
                "sample_id": sample_id,
                "source_instance_id": str(record["source_instance_id"]),
                "difficulty": str(record["difficulty"]),
                "density": nonzeros / (variables * constraints),
                "discrete_fraction": float(
                    graph["variable"].is_discrete.sum().item() / variables
                ),
                "constraint_variable_ratio": constraints / variables,
                "positive_label_fraction": float(
                    (graph["variable"].y >= 0.5).sum().item() / variables
                ),
                "mip_gap_relative": float(graph.mip_gap),
                "execution_time_seconds": float(graph.exec_time),
            }
        )
    matrix = np.asarray([[float(row[key]) for key in FEATURES] for row in raw])
    standardized = _standardize(matrix)
    coordinates, explained = _pca(standardized)
    cluster_count = min(3, len(raw))
    assignments = _kmeans(standardized, cluster_count)
    rows: list[dict[str, Any]] = []
    for row, coordinate, assignment in zip(raw, coordinates, assignments):
        rows.append(
            {
                **row,
                "pca_component_1": float(coordinate[0]),
                "pca_component_2": float(coordinate[1]),
                "cluster_id": int(assignment),
            }
        )
    fields = tuple(rows[0])
    with (output / TABLE_NAME).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (output / FIGURE_NAME).write_text(_scatter_svg(rows), encoding="utf-8")
    report = {
        "schema_version": 1,
        "gate_status": "passed",
        "graph_manifest_sha256": _sha256(manifest),
        "methodology": {
            "features": list(FEATURES),
            "standardization": "population_z_score_zero_variance_to_zero",
            "projection": "deterministic_numpy_svd_pca",
            "clustering": "deterministic_kmeans_maximum_three_clusters",
            "random_seed_required": False,
        },
        "summary": {
            "graphs": len(rows),
            "clusters": cluster_count,
            "pca_explained_variance_ratio": explained,
        },
        "outputs": {
            TABLE_NAME: {"sha256": _sha256(output / TABLE_NAME)},
            FIGURE_NAME: {"sha256": _sha256(output / FIGURE_NAME)},
        },
        "eligibility": {
            "descriptive_analysis_complete": True,
            "inferential_cluster_claims_allowed": False,
        },
    }
    (output / REPORT_NAME).write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cluster manifest-bound graph features."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--graph_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = cluster_graph_manifest(
            manifest_path=args.manifest,
            graph_root=args.graph_root,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError, GraphClusteringError) as error:
        print(f"[ERROR] {error}")
        return 2
    print(f"[INFO] gate={report['gate_status']} | graphs={report['summary']['graphs']}")
    print(f"[INFO] Report: {Path(args.output_dir).resolve() / REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
