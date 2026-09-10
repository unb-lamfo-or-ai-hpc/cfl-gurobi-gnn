"""Manifest-bound descriptive statistics for materialized PyG graphs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPORT_NAME = "graph_statistics_report.json"
TABLE_NAME = "graph_statistics.csv"
FIGURE_NAME = "graph_statistics.svg"


class GraphStatisticsError(RuntimeError):
    """Raised when the graph-statistics contract cannot be verified."""


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
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise TypeError("manifest record is not an object")
                    records.append(item)
    except (OSError, TypeError, ValueError) as error:
        raise GraphStatisticsError("graph manifest is unreadable") from error
    if not records:
        raise GraphStatisticsError("graph manifest is empty")
    return records


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: Sequence[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def _standard_deviation(values: Sequence[float]) -> float:
    return float(statistics.stdev(values)) if len(values) > 1 else 0.0


def _ci95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return 1.96 * _standard_deviation(values) / math.sqrt(len(values))


def _bar_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    width, height = 920, 420
    values = [float(row["nonzeros"]) for row in rows]
    maximum = max(values, default=1.0) or 1.0
    bar_width = max(8.0, 760.0 / max(len(rows), 1))
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="460" y="30" text-anchor="middle" font-size="18">'
        "Graph nonzero counts</text>",
    ]
    for index, row in enumerate(rows):
        value = float(row["nonzeros"])
        bar_height = 310.0 * value / maximum
        x = 80.0 + index * bar_width
        y = 360.0 - bar_height
        elements.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width * 0.7:.2f}" '
            f'height="{bar_height:.2f}" fill="#3264a8"/>'
        )
        elements.append(
            f'<text x="{x + bar_width * 0.35:.2f}" y="380" text-anchor="middle" '
            f'font-size="9">{index + 1}</text>'
        )
    elements.append('</svg>')
    return "\n".join(elements) + "\n"


def analyze_graph_manifest(
    *,
    manifest_path: str | Path,
    graph_root: str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Load every manifest graph once and emit descriptive audit artifacts."""
    import torch

    manifest = Path(manifest_path).resolve()
    root = Path(graph_root).resolve()
    output = Path(output_dir).resolve()
    expected_outputs = [output / REPORT_NAME, output / TABLE_NAME, output / FIGURE_NAME]
    if not overwrite and any(path.exists() for path in expected_outputs):
        raise GraphStatisticsError("statistics output exists; use --overwrite")
    output.mkdir(parents=True, exist_ok=True)
    records = _read_jsonl(manifest)
    rows: list[dict[str, Any]] = []
    identities: set[str] = set()
    for record in records:
        sample_id = str(record.get("sample_id", ""))
        relative_path = str(record.get("graph_relative_path", ""))
        if not sample_id or sample_id in identities or not relative_path:
            raise GraphStatisticsError("invalid or duplicate graph identity")
        identities.add(sample_id)
        graph_path = root / relative_path
        if (
            not graph_path.is_file()
            or _sha256(graph_path) != record.get("graph_sha256")
        ):
            raise GraphStatisticsError(f"graph artifact failed SHA-256: {sample_id}")
        graph = torch.load(graph_path, map_location="cpu", weights_only=False)
        variables = int(graph["variable"].x.shape[0])
        constraints = int(graph["constraint"].x.shape[0])
        nonzeros = int(
            graph["variable", "rev_coef", "constraint"].edge_index.shape[1]
        )
        rows.append(
            {
                "sample_id": sample_id,
                "source_instance_id": str(record["source_instance_id"]),
                "difficulty": str(record["difficulty"]),
                "sampling_strategy": str(record["sampling_strategy"]),
                "variables": variables,
                "constraints": constraints,
                "nonzeros": nonzeros,
                "density": (
                    nonzeros / (variables * constraints)
                    if variables and constraints
                    else 0.0
                ),
                "discrete_fraction": float(
                    graph["variable"].is_discrete.sum().item() / variables
                ),
                "positive_label_fraction": float(
                    (graph["variable"].y >= 0.5).sum().item() / variables
                ),
                "mip_gap_relative": float(graph.mip_gap),
                "execution_time_seconds": float(graph.exec_time),
                "root_lp_minimum": float(graph["variable"].x[:, 6].min().item()),
                "root_lp_maximum": float(graph["variable"].x[:, 6].max().item()),
                "root_lp_nonzero_fraction": float(
                    (graph["variable"].x[:, 6] != 0).sum().item() / variables
                ),
            }
        )
    fields = tuple(rows[0])
    _write_csv(output / TABLE_NAME, rows, fields)
    (output / FIGURE_NAME).write_text(_bar_svg(rows), encoding="utf-8")
    grouped: dict[str, Any] = {}
    for difficulty in sorted({str(row["difficulty"]) for row in rows}):
        selected = [row for row in rows if row["difficulty"] == difficulty]
        gaps = [float(row["mip_gap_relative"]) for row in selected]
        times = [float(row["execution_time_seconds"]) for row in selected]
        grouped[difficulty] = {
            "graphs": len(selected),
            "mip_gap_relative_mean": _mean(gaps),
            "mip_gap_relative_standard_deviation": _standard_deviation(gaps),
            "mip_gap_relative_ci95_half_width": _ci95(gaps),
            "execution_time_seconds_mean": _mean(times),
            "execution_time_seconds_standard_deviation": _standard_deviation(times),
            "execution_time_seconds_ci95_half_width": _ci95(times),
        }
    report = {
        "schema_version": 1,
        "gate_status": "passed",
        "graph_manifest_sha256": _sha256(manifest),
        "summary": {
            "graphs": len(rows),
            "unique_samples": len(identities),
            "by_difficulty": grouped,
        },
        "outputs": {
            TABLE_NAME: {"sha256": _sha256(output / TABLE_NAME)},
            FIGURE_NAME: {"sha256": _sha256(output / FIGURE_NAME)},
        },
        "eligibility": {"descriptive_analysis_complete": True},
    }
    _write_json(output / REPORT_NAME, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit manifest-bound graph statistics."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--graph_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = analyze_graph_manifest(
            manifest_path=args.manifest,
            graph_root=args.graph_root,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except (OSError, ValueError, GraphStatisticsError) as error:
        print(f"[ERROR] {error}")
        return 2
    print(f"[INFO] gate={report['gate_status']} | graphs={report['summary']['graphs']}")
    print(f"[INFO] Report: {Path(args.output_dir).resolve() / REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
