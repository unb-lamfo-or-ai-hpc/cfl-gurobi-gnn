"""Dependency-free provenance helpers for parent-instance graph artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


RAW_DATASET = "MILPBench/CFL"
STRUCTURE_ARTIFACT = "original_features.pickle.gz"


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of an artifact without loading it into memory."""
    artifact = Path(path)
    digest = hashlib.sha256()
    with artifact.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def provenance_path(output_path: str | Path) -> Path:
    """Return the sidecar path paired with one serialized graph."""
    return Path(output_path).with_suffix(".provenance.json")


def _digest_matches(
    provenance: Mapping[str, Any], path_key: str, digest_key: str
) -> bool:
    path_value = provenance.get(path_key)
    expected_digest = provenance.get(digest_key)
    if not path_value or not expected_digest:
        return False
    path = Path(str(path_value))
    try:
        return path.is_file() and sha256_file(path) == expected_digest
    except OSError:
        return False


def load_verified_graph_provenance(
    output_path: str | Path,
    *,
    expected_instance: str,
    expected_fold: int,
    current_relaxation_path: str | Path,
) -> dict[str, Any] | None:
    """Load a sidecar only when every recorded input and output still matches."""
    graph_path = Path(output_path)
    sidecar_path = provenance_path(graph_path)
    if not (
        graph_path.is_file()
        and graph_path.stat().st_size > 0
        and sidecar_path.is_file()
        and sidecar_path.stat().st_size > 0
    ):
        return None
    try:
        with sidecar_path.open("r", encoding="utf-8") as stream:
            result = json.load(stream)
        if (
            result.get("schema_version") != 2
            or result.get("instance") != expected_instance
            or result.get("fold") != expected_fold
            or not isinstance(result.get("label_source"), str)
            or not isinstance(result.get("structure_provenance"), Mapping)
            or not isinstance(result.get("collection_provenance"), Mapping)
            or not isinstance(result.get("context_provenance"), Mapping)
            or not isinstance(result.get("label_provenance"), Mapping)
            or not isinstance(result.get("candidate_audit"), Mapping)
        ):
            return None
        structure = result["structure_provenance"]
        collection = result["collection_provenance"]
        context = result["context_provenance"]
        label = result["label_provenance"]
        if result["label_source"] != label.get("artifact"):
            return None
        if (
            sha256_file(graph_path) != result.get("graph_sha256")
            or not _digest_matches(
                structure, "raw_instance_path", "raw_instance_sha256"
            )
            or not _digest_matches(
                structure, "feature_artifact_path", "feature_artifact_sha256"
            )
            or not _digest_matches(
                collection, "artifact_path", "artifact_sha256"
            )
            or not _digest_matches(label, "artifact_path", "artifact_sha256")
        ):
            return None
        if context.get("artifact") is None:
            relaxation_path = Path(current_relaxation_path)
            if relaxation_path.is_file() and relaxation_path.stat().st_size > 0:
                return None
        elif not _digest_matches(context, "artifact_path", "artifact_sha256"):
            return None
    except (OSError, ValueError, TypeError):
        return None
    return result


def resolve_raw_instance_path(
    metadata: Mapping[str, Any],
    *,
    source_root: str | Path,
    category: str,
    source_instance_id: str,
) -> Path:
    """Resolve the exact MILPBench file behind a collected feature artifact."""
    expected_name = f"{source_instance_id}.lp.gz"
    recorded = metadata.get("lp_file")
    candidates = [Path(source_root) / category / "LP" / expected_name]
    if recorded:
        candidates.append(Path(str(recorded)).expanduser())

    for candidate in candidates:
        if candidate.is_file() and candidate.name == expected_name:
            return candidate.resolve()

    rendered = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"raw MILPBench instance {expected_name} was not found; checked: {rendered}"
    )


def mip_gap_band(value: Any) -> str:
    """Classify label quality without presenting a feasible label as optimal."""
    try:
        gap = float(value)
    except (TypeError, ValueError, OverflowError):
        return "unknown"
    if not math.isfinite(gap) or gap < 0.0:
        return "unknown"
    if gap <= 1e-4:
        return "optimal_tolerance"
    if gap <= 0.10:
        return "gap_le_10pct"
    if gap <= 0.40:
        return "gap_le_40pct"
    return "gap_gt_40pct"


def normalize_recorded_time(
    recorded_time: Any, *, epoch_origin: Any = None
) -> dict[str, float | str | None]:
    """Normalize mixed Gurobi-runtime and legacy Unix-epoch timestamps."""
    try:
        recorded = float(recorded_time)
    except (TypeError, ValueError, OverflowError):
        recorded = math.nan
    if not math.isfinite(recorded) or recorded < 0.0:
        return {
            "recorded_time": None,
            "normalized_time": None,
            "time_normalization_method": "missing_or_invalid",
            "time_origin": None,
        }
    if recorded <= 1e8:
        return {
            "recorded_time": recorded,
            "normalized_time": recorded,
            "time_normalization_method": "recorded_gurobi_runtime_seconds",
            "time_origin": None,
        }

    try:
        origin = float(epoch_origin)
    except (TypeError, ValueError, OverflowError):
        origin = math.nan
    if not math.isfinite(origin) or origin < 0.0 or origin > recorded:
        return {
            "recorded_time": recorded,
            "normalized_time": None,
            "time_normalization_method": "unix_epoch_unresolved",
            "time_origin": None,
        }
    return {
        "recorded_time": recorded,
        "normalized_time": recorded - origin,
        "time_normalization_method": "unix_epoch_minus_first_incumbent",
        "time_origin": origin,
    }


def summarize_label_quality(
    results: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, int]]:
    """Count label sources and quality bands from generated or reused graphs."""
    sources: Counter[str] = Counter()
    bands: Counter[str] = Counter()
    for result in results:
        label = result.get("label_provenance")
        if not isinstance(label, Mapping):
            continue
        sources[str(label.get("artifact", "unknown"))] += 1
        bands[str(label.get("mip_gap_band", "unknown"))] += 1
    return {
        "by_artifact": dict(sorted(sources.items())),
        "by_mip_gap_band": dict(sorted(bands.items())),
    }
