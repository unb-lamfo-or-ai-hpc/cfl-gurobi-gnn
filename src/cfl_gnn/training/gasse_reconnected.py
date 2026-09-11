"""Manifest-driven reconnection of the preserved Gasse training baseline."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.pipelines.gurobi_graph_dataset import (
    GRAPH_MANIFEST_NAME,
    GRAPH_REPORT_NAME,
)
from cfl_gnn.pipelines.parent_collection_task import validate_campaign_plan
from cfl_gnn.pipelines.parent_population import PLAN_NAME as PARENT_PLAN_NAME
from cfl_gnn.pipelines.parent_solutions import report_name
from cfl_gnn.training.mvp_arm import build_parent_balanced_epoch_indices
from cfl_gnn.training.binary_contract import binary_targets


SCHEMA_VERSION = 1
TRAINING_PLAN_NAME = "gasse_training_plan.json"
TRAINING_REPORT_NAME = "gasse_training_report.json"
TRAINING_HISTORY_NAME = "training_epoch_metrics.csv"
LEGACY_GASSE_GIT_BLOB_SHA1 = "e2937ebcca149f8a99ec437c3c8e7fd31e49438b"
ROLES = ("train", "validation", "test")


class GasseTrainingError(RuntimeError):
    """Raised when the reconnected Gasse contract fails closed."""


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def git_blob_sha1(path: str | Path) -> str:
    """Return the Git blob identity after Git's text newline normalization."""
    payload = Path(path).read_bytes().replace(b"\r\n", b"\n")
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as error:
        raise GasseTrainingError(f"unreadable JSON artifact: {source.name}") from error
    if not isinstance(value, dict):
        raise GasseTrainingError(f"expected JSON object: {source.name}")
    return value


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    records: list[dict[str, Any]] = []
    line_number = 0
    try:
        with source.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise TypeError("record is not an object")
                records.append(value)
    except (OSError, TypeError, ValueError) as error:
        raise GasseTrainingError(
            f"unreadable JSONL artifact: {source.name}:{line_number}"
        ) from error
    return records


def write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise GasseTrainingError(f"{field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise GasseTrainingError(f"{field} must be a positive integer") from error
    if normalized <= 0 or normalized != value:
        raise GasseTrainingError(f"{field} must be a positive integer")
    return normalized


def _finite(value: Any, *, field: str, positive: bool = False) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise GasseTrainingError(f"{field} must be finite") from error
    if not math.isfinite(normalized) or (positive and normalized <= 0.0):
        raise GasseTrainingError(f"{field} must be finite")
    return normalized


def load_protocol(path: str | Path) -> dict[str, Any]:
    protocol = read_json(path)
    if protocol.get("schema_version") != SCHEMA_VERSION:
        raise GasseTrainingError("unsupported training protocol schema")
    architecture = protocol.get("architecture", {})
    if architecture.get("model_version", "legacy") not in ("legacy", "gasse_v2_alternating_prenorm"):
        raise GasseTrainingError("unsupported model_version")
    optimization = protocol.get("optimization", {})
    sampling = protocol.get("sampling", {})
    checkpoint = protocol.get("checkpoint_selection", {})
    threshold = protocol.get("threshold_selection", {})
    if architecture.get("legacy_gasse_git_blob_sha1") != (
        LEGACY_GASSE_GIT_BLOB_SHA1
    ):
        raise GasseTrainingError(
            "training protocol does not pin the legacy Gasse model"
        )
    _positive_int(architecture.get("hidden_dim"), field="hidden_dim")
    _positive_int(architecture.get("num_layers"), field="num_layers")
    _positive_int(optimization.get("epochs"), field="epochs")
    _positive_int(optimization.get("patience"), field="patience")
    _finite(
        optimization.get("learning_rate"),
        field="learning_rate",
        positive=True,
    )
    _finite(
        optimization.get("gradient_clip_norm"),
        field="gradient_clip_norm",
        positive=True,
    )
    _positive_int(
        sampling.get("draws_per_parent_per_epoch"),
        field="draws_per_parent_per_epoch",
    )
    maximum_gap = _finite(
        sampling.get("maximum_label_mip_gap_relative"),
        field="maximum_label_mip_gap_relative",
    )
    if maximum_gap < 0.0 or maximum_gap > 0.10:
        raise GasseTrainingError("label MIP gap must be between zero and 10%")
    if sampling.get("method") != "deterministic_parent_balanced_cycle_v1":
        raise GasseTrainingError("unsupported parent-balancing method")
    if checkpoint != {
        "metric": "validation_weighted_bce",
        "mode": "minimum",
        "test_partition_access": "held_out_evaluation_only",
    }:
        raise GasseTrainingError("unsupported checkpoint-selection contract")
    if threshold.get("method") != "maximum_validation_f1":
        raise GasseTrainingError("threshold selection must use validation F1")
    fallback = _finite(
        threshold.get("fallback_for_partial_smoke"),
        field="fallback_for_partial_smoke",
    )
    if fallback != 0.5:
        raise GasseTrainingError("the partial-smoke threshold must be 0.5")
    return protocol


def _safe_file(root: Path, relative_path: str, *, artifact: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise GasseTrainingError(f"unsafe {artifact} path")
    resolved = (root / relative).resolve()
    if root.resolve() not in resolved.parents or not resolved.is_file():
        raise GasseTrainingError(f"missing {artifact}: {relative.as_posix()}")
    return resolved


def _solution_descriptor(
    *,
    task: Mapping[str, Any],
    run_root: Path,
    solver: str,
    expected_parent_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_relative = str(task["run_dir_relative_path"])
    run_dir = run_root / run_relative
    report = read_json(run_dir / report_name(solver))
    if (
        report.get("parent", {}).get("sha256") != expected_parent_sha256
        or report.get("eligibility", {}).get("label_eligible") is not True
    ):
        raise GasseTrainingError("parent label is not eligible")
    solution = report.get("artifacts", {}).get("solution", {})
    solution_path = _safe_file(
        run_dir,
        str(solution.get("file_name", "")),
        artifact="parent solution",
    )
    solution_sha256 = str(solution.get("sha256", ""))
    if sha256_file(solution_path) != solution_sha256:
        raise GasseTrainingError("parent solution SHA-256 mismatch")
    expected_source = {
        "gurobi": "independent_gurobi_optimization",
        "scip": "independent_pyscipopt_optimization",
    }[solver]
    try:
        with gzip.open(solution_path, "rt", encoding="utf-8") as stream:
            solution_payload = json.load(stream)
    except (OSError, TypeError, ValueError) as error:
        raise GasseTrainingError("parent solution payload is unreadable") from error
    if solution_payload.get("solution_source") != expected_source:
        raise GasseTrainingError("parent solution source does not match its solver")
    solve = report.get("solve", {})
    gap = _finite(solve.get("mip_gap_relative"), field="mip_gap_relative")
    return report, {
        "label_run_relative_path": run_relative,
        "label_file_name": solution_path.name,
        "label_sha256": solution_sha256,
        "label_mip_gap_relative": gap,
        "label_objective": _finite(
            solve.get("solution_objective"), field="solution_objective"
        ),
        "label_execution_time_seconds": _finite(
            solve.get("execution_time_seconds"),
            field="execution_time_seconds",
        ),
    }


def build_gasse_training_plan(
    *,
    graph_dataset_dir: str | Path,
    parent_collection_plan_dir: str | Path,
    parent_collection_run_root: str | Path,
    protocol_path: str | Path,
    label_solver: str = "gurobi",
    allow_partial_smoke: bool = False,
) -> dict[str, Any]:
    """Build a path-neutral plan over one graph identity and solver label view."""
    if label_solver not in {"gurobi", "scip"}:
        raise GasseTrainingError("label_solver must be gurobi or scip")
    graph_root = Path(graph_dataset_dir).resolve()
    run_root = Path(parent_collection_run_root).resolve()
    protocol = load_protocol(protocol_path)
    graph_report = read_json(graph_root / GRAPH_REPORT_NAME)
    if (
        graph_report.get("gate_status") != "passed"
        or graph_report.get("graph_contract", {}).get("authority") != "gurobi"
        or graph_report.get("eligibility", {}).get("dataset_eligible") is not True
    ):
        raise GasseTrainingError("Gurobi graph dataset is not eligible")
    graph_manifest_path = graph_root / GRAPH_MANIFEST_NAME
    if sha256_file(graph_manifest_path) != graph_report.get("outputs", {}).get(
        GRAPH_MANIFEST_NAME, {}
    ).get("sha256"):
        raise GasseTrainingError("graph manifest SHA-256 mismatch")
    parent_plan = read_json(Path(parent_collection_plan_dir) / PARENT_PLAN_NAME)
    try:
        validate_campaign_plan(parent_plan)
    except Exception as error:
        raise GasseTrainingError("parent collection plan is invalid") from error
    tasks = {
        (str(task["solver"]), str(task["source_instance_id"])): task
        for task in parent_plan.get("tasks", [])
    }
    maximum_gap = float(protocol["sampling"]["maximum_label_mip_gap_relative"])
    records: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    graph_identities: dict[str, str] = {}
    for graph_record in read_jsonl(graph_manifest_path):
        sample_id = str(graph_record["sample_id"])
        parent_id = str(
            graph_record.get("parent_instance_id")
            or graph_record["source_instance_id"]
        )
        graph_path = _safe_file(
            graph_root,
            str(graph_record["graph_relative_path"]),
            artifact="graph",
        )
        if sha256_file(graph_path) != graph_record.get("graph_sha256"):
            raise GasseTrainingError(f"graph SHA-256 mismatch: {sample_id}")
        root_path = _safe_file(
            graph_root,
            str(graph_record["root_relative_path"]),
            artifact="root relaxation",
        )
        if sha256_file(root_path) != graph_record.get("root_sha256"):
            raise GasseTrainingError(f"root SHA-256 mismatch: {sample_id}")
        mip_sha256 = str(graph_record["mip_sha256"])
        previous = graph_identities.get(mip_sha256)
        if previous is not None and previous != str(graph_record["graph_sha256"]):
            raise GasseTrainingError("one mathematical MIP has multiple graph hashes")
        graph_identities[mip_sha256] = str(graph_record["graph_sha256"])
        task = tasks.get((label_solver, parent_id))
        if task is None:
            raise GasseTrainingError(f"missing {label_solver} label task: {parent_id}")
        report, label = _solution_descriptor(
            task=task,
            run_root=run_root,
            solver=label_solver,
            expected_parent_sha256=str(task["parent_mip_sha256"]),
        )
        if label["label_mip_gap_relative"] > maximum_gap + 1e-12:
            excluded.append(
                {
                    "sample_id": sample_id,
                    "parent_instance_id": parent_id,
                    "reason_code": "label_mip_gap_above_precommitted_threshold",
                    "label_mip_gap_relative": label["label_mip_gap_relative"],
                }
            )
            continue
        role = str(graph_record["role"])
        sampling_strategy = str(graph_record["sampling_strategy"])
        if role not in ROLES:
            raise GasseTrainingError("unknown graph partition role")
        if sampling_strategy != "original":
            raise GasseTrainingError(
                "PR44 reconnects original-parent labels only; derived labels "
                "must enter through the audited augmentation adapter"
            )
        if mip_sha256 != str(task["parent_mip_sha256"]):
            raise GasseTrainingError("graph MIP and parent-label MIP differ")
        records.append(
            {
                "sample_id": sample_id,
                "parent_instance_id": parent_id,
                "source_instance_id": str(graph_record["source_instance_id"]),
                "category": str(graph_record["category"]),
                "difficulty": str(graph_record["difficulty"]),
                "fold": int(graph_record["fold"]),
                "role": role,
                "sampling_strategy": sampling_strategy,
                "mip_sha256": mip_sha256,
                "graph_relative_path": str(graph_record["graph_relative_path"]),
                "graph_sha256": str(graph_record["graph_sha256"]),
                "root_relative_path": str(graph_record["root_relative_path"]),
                "root_sha256": str(graph_record["root_sha256"]),
                "graph_authority": "gurobi",
                "label_solver": label_solver,
                "label_contract_sha256": str(report["contract_sha256"]),
                **label,
            }
        )
    if not records:
        raise GasseTrainingError("no gap-eligible graph-label views")
    if protocol.get("protocol_id") == "gasse_42_parent_confirmation_v2":
        from cfl_gnn.pipelines.confirmation_campaign import COHORT
        if {r["parent_instance_id"] for r in records} != set(COHORT) or len(records) != 42:
            raise GasseTrainingError("42-parent confirmation requires exactly the frozen 30 easy and 12 medium parents")
        if any(r["sampling_strategy"] != "original" for r in records):
            raise GasseTrainingError("broad confirmation is original-only; keep paired augmentation separate")
    parents_by_role = {
        role: {
            record["parent_instance_id"]
            for record in records
            if record["role"] == role
        }
        for role in ROLES
    }
    if (
        parents_by_role["train"] & parents_by_role["validation"]
        or parents_by_role["train"] & parents_by_role["test"]
        or parents_by_role["validation"] & parents_by_role["test"]
    ):
        raise GasseTrainingError("parent leakage across partitions")
    counts = {
        role: sum(record["role"] == role for record in records) for role in ROLES
    }
    full_ready = all(counts[role] > 0 for role in ROLES)
    if not full_ready and not allow_partial_smoke:
        raise GasseTrainingError(
            "train, validation, and held-out test partitions are required"
        )
    source_root = Path(__file__).resolve().parents[1]
    gasse_path = source_root / "models" / "gasse.py"
    gasse_blob = git_blob_sha1(gasse_path)
    if gasse_blob != LEGACY_GASSE_GIT_BLOB_SHA1:
        raise GasseTrainingError("the preserved Gasse architecture changed")
    contract = {
        "schema_version": SCHEMA_VERSION,
        "dataset_variant": "gurobi_authoritative_graph_solver_label_view_v1",
        "graph_dataset_contract_sha256": graph_report["contract_sha256"],
        "parent_collection_contract_sha256": parent_plan["contract_sha256"],
        "graph_manifest_sha256": sha256_file(graph_manifest_path),
        "graph_identity": "one_graph_per_mathematical_mip",
        "graph_authority": "gurobi",
        "label_solver": label_solver,
        "label_view": "named_solution_overlay_at_load_time",
        "legacy_gasse_git_blob_sha1": gasse_blob,
        "implementation_sha256": {
            "gasse": sha256_file(gasse_path),
            "selected_gasse": sha256_file(source_root / "models" / (
                "gasse_calibrated.py" if protocol["architecture"].get("model_version") == "gasse_v2_alternating_prenorm" else "gasse.py")),
            "binary_target_contract": sha256_file(source_root / "training" / "binary_contract.py"),
            "serial_backend": sha256_file(source_root / "training" / "serial.py"),
            "ddp_backend": sha256_file(
                source_root / "training" / "distributed.py"
            ),
            "legacy_evaluator": sha256_file(
                source_root / "evaluation" / "model.py"
            ),
        },
        "protocol": protocol,
        "protocol_sha256": canonical_sha256(protocol),
        "records": sorted(records, key=lambda item: item["sample_id"]),
        "excluded_records": sorted(excluded, key=lambda item: item["sample_id"]),
        "partition_counts": counts,
        "parent_ids_by_role": {
            role: sorted(values) for role, values in parents_by_role.items()
        },
        "test_partition_usage": "held_out_not_loaded_during_training",
        "allow_partial_smoke": bool(allow_partial_smoke),
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "contract_valid": True,
        "training_ready": full_ready,
        "engineering_smoke_ready": counts["train"] > 0,
        "held_out_evaluation_ready": counts["test"] > 0,
        "warnings": (
            []
            if full_ready
            else ["partial_partition_inventory_engineering_smoke_only"]
        ),
        "next_gate": (
            "gasse_serial_then_ddp_training"
            if full_ready
            else "gasse_train_only_engineering_smoke"
        ),
    }


def validate_training_plan(plan: Mapping[str, Any]) -> None:
    ignored = {
        "contract_sha256",
        "contract_valid",
        "training_ready",
        "engineering_smoke_ready",
        "held_out_evaluation_ready",
        "warnings",
        "next_gate",
    }
    payload = {key: value for key, value in plan.items() if key not in ignored}
    if canonical_sha256(payload) != plan.get("contract_sha256"):
        raise GasseTrainingError("training plan contract hash mismatch")


class GasseLabelViewDataset:
    """Load a Gurobi graph and overlay one solver-specific named label view."""

    def __init__(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        graph_root: str | Path,
        label_root: str | Path,
    ) -> None:
        self.records = tuple(dict(record) for record in records)
        self.graph_root = Path(graph_root).resolve()
        self.label_root = Path(label_root).resolve()

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> Any:
        import torch

        record = self.records[index]
        graph_path = _safe_file(
            self.graph_root,
            record["graph_relative_path"],
            artifact="graph",
        )
        root_path = _safe_file(
            self.graph_root,
            record["root_relative_path"],
            artifact="root relaxation",
        )
        label_dir = self.label_root / record["label_run_relative_path"]
        label_path = _safe_file(
            label_dir,
            record["label_file_name"],
            artifact="solver label",
        )
        for path, expected, label in (
            (graph_path, record["graph_sha256"], "graph"),
            (root_path, record["root_sha256"], "root relaxation"),
            (label_path, record["label_sha256"], "solver label"),
        ):
            if sha256_file(path) != expected:
                raise GasseTrainingError(f"{label} SHA-256 mismatch at load time")
        graph = torch.load(graph_path, map_location="cpu", weights_only=False)
        if (
            getattr(graph, "sample_id", None) != record["sample_id"]
            or getattr(graph, "graph_authority", None) != "gurobi"
        ):
            raise GasseTrainingError("serialized graph identity mismatch")
        with gzip.open(root_path, "rt", encoding="utf-8") as stream:
            root_payload = json.load(stream)
        with gzip.open(label_path, "rt", encoding="utf-8") as stream:
            label_payload = json.load(stream)
        names = root_payload.get("variable_names")
        values = label_payload.get("variables")
        if not isinstance(names, list) or not isinstance(values, list):
            raise GasseTrainingError("named label overlay is malformed")
        by_name: dict[str, float] = {}
        for item in values:
            name = str(item.get("name", ""))
            if not name or name in by_name:
                raise GasseTrainingError("duplicate or unnamed label variable")
            by_name[name] = _finite(item.get("value"), field="label value")
        if set(names) != set(by_name):
            raise GasseTrainingError("graph and label variable identities differ")
        graph["variable"].y = torch.tensor(
            [by_name[name] for name in names], dtype=torch.float32
        )
        graph.label_source_solver = record["label_solver"]
        graph.label_solution_sha256 = record["label_sha256"]
        graph.variable_names = names
        return graph


class _IndexSampler:
    def __init__(self, indices: Sequence[int]) -> None:
        self.indices = tuple(int(index) for index in indices)

    def __iter__(self) -> Iterable[int]:
        return iter(self.indices)

    def __len__(self) -> int:
        return len(self.indices)


def classification_metrics(tp: int, tn: int, fp: int, fn: int) -> dict[str, float]:
    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1_score": (
            2.0 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        ),
    }


def threshold_from_validation(targets: Any, probabilities: Any) -> float:
    """Choose the deterministic validation-F1 threshold without test access."""
    import numpy as np

    truth = np.asarray(targets, dtype=np.float64) >= 0.5
    scores = np.asarray(probabilities, dtype=np.float64)
    if truth.size == 0 or scores.shape != truth.shape:
        raise GasseTrainingError("validation predictions are empty or malformed")
    if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
        raise GasseTrainingError("validation probabilities are invalid")
    order = np.argsort(scores, kind="stable")
    sorted_scores, sorted_truth = scores[order], truth[order]
    prefix = np.concatenate(([0], np.cumsum(sorted_truth, dtype=np.int64)))
    positives = int(prefix[-1])
    candidates = np.unique(np.concatenate(([0.0, 0.5, 1.0], scores)))
    best = (float("-inf"), float("-inf"), 0.5)
    for threshold in candidates:
        first = int(np.searchsorted(sorted_scores, threshold, side="left"))
        tp = positives - int(prefix[first])
        fp = len(scores) - first - tp
        fn = positives - tp
        metrics = classification_metrics(tp, 0, fp, fn)
        candidate = (
            metrics["f1_score"],
            -abs(float(threshold) - 0.5),
            -float(threshold),
        )
        if candidate > best:
            best = candidate
    return -best[2]


def _predict(model: Any, loader: Any, device: Any) -> tuple[list[float], list[float]]:
    import torch

    model.eval()
    targets: list[float] = []
    probabilities: list[float] = []
    with torch.no_grad():
        for graph in loader:
            graph = graph.to(device)
            mask = graph["variable"].is_discrete.bool()
            edge = graph["variable", "rev_coef", "constraint"]
            logits = model(
                x_var=graph["variable"].x,
                x_cons=graph["constraint"].x,
                edge_v2c=edge.edge_index,
                binary_mask=mask,
                edge_attr=edge.edge_attr,
            )
            probabilities.extend(torch.sigmoid(logits).cpu().tolist())
            targets.extend(
                binary_targets(graph)[1].cpu().tolist()
            )
    return targets, probabilities


def run_serial_training(
    plan: Mapping[str, Any],
    *,
    graph_root: str | Path,
    label_root: str | Path,
    output_dir: str | Path,
    epochs_override: int | None = None,
    device_name: str = "auto",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the legacy Gasse serial loop over the audited manifest loader."""
    validate_training_plan(plan)
    import torch
    import torch.nn as nn
    from torch_geometric.loader import DataLoader

    from cfl_gnn.models.versioning import model_class, fit_versioned_prenorm
    from cfl_gnn.training.serial import (
        compute_pos_weight,
        eval_loop,
        set_global_seed,
        train_loop,
    )

    if not plan.get("engineering_smoke_ready"):
        raise GasseTrainingError("training plan has no training partition")
    output = Path(output_dir).resolve()
    report_path = output / TRAINING_REPORT_NAME
    if report_path.exists() and not overwrite:
        raise GasseTrainingError("training output exists; use --overwrite")
    output.mkdir(parents=True, exist_ok=True)
    protocol = plan["protocol"]
    optimization = protocol["optimization"]
    epochs = (
        _positive_int(epochs_override, field="epochs_override")
        if epochs_override is not None
        else int(optimization["epochs"])
    )
    set_global_seed(int(optimization["seed"]))
    if device_name == "cuda" and not torch.cuda.is_available():
        raise GasseTrainingError("CUDA was requested but is unavailable")
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device_name)
    by_role = {
        role: [record for record in plan["records"] if record["role"] == role]
        for role in ROLES
    }
    train_dataset = GasseLabelViewDataset(
        by_role["train"], graph_root=graph_root, label_root=label_root
    )
    draws = int(protocol["sampling"]["draws_per_parent_per_epoch"])
    first_schedule = build_parent_balanced_epoch_indices(
        by_role["train"],
        seed=int(optimization["seed"]),
        epoch=0,
        draws_per_parent=draws,
    )
    train_loader = DataLoader(
        train_dataset, batch_size=1, sampler=_IndexSampler(first_schedule)
    )
    validation_loader = None
    if by_role["validation"]:
        validation_loader = DataLoader(
            GasseLabelViewDataset(
                by_role["validation"], graph_root=graph_root, label_root=label_root
            ),
            batch_size=1,
            shuffle=False,
        )
    representative = next(iter(train_loader)).to(device)
    edge = representative["variable", "rev_coef", "constraint"]
    edge_dim = int(edge.edge_attr.shape[-1]) if edge.edge_attr is not None else 0
    model_version = protocol["architecture"].get("model_version", "legacy")
    model = model_class(model_version)(
        var_in_dim=int(representative["variable"].x.shape[-1]),
        cons_in_dim=int(representative["constraint"].x.shape[-1]),
        edge_dim=edge_dim,
        hidden_dim=int(protocol["architecture"]["hidden_dim"]),
        num_layers=int(protocol["architecture"]["num_layers"]),
    ).to(device)
    prenorm_audit = fit_versioned_prenorm(model, model_version, train_dataset, representative, device)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=float(optimization["learning_rate"])
    )
    pos_weight = compute_pos_weight(train_loader, device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    args = type(
        "TrainingArguments",
        (),
        {
            "grad_clip": float(optimization["gradient_clip_norm"]),
            "clear_cache": False,
        },
    )()
    history: list[dict[str, Any]] = []
    best_loss = float("inf")
    patience = 0
    checkpoint = output / "best_model.pt"
    for epoch in range(epochs):
        schedule = build_parent_balanced_epoch_indices(
            by_role["train"],
            seed=int(optimization["seed"]),
            epoch=epoch,
            draws_per_parent=draws,
        )
        train_loader = DataLoader(
            train_dataset, batch_size=1, sampler=_IndexSampler(schedule)
        )
        train_loss = train_loop(
            model, train_loader, optimizer, loss_fn, device, args
        )
        if validation_loader is not None:
            validation_loss, tp, tn, fp, fn = eval_loop(
                model, validation_loader, loss_fn, device, args
            )
            metric = validation_loss
        else:
            validation_loss, tp, tn, fp, fn = None, 0, 0, 0, 0
            metric = train_loss
        metrics = classification_metrics(int(tp), int(tn), int(fp), int(fn))
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "validation_loss": validation_loss,
                **metrics,
            }
        )
        if metric < best_loss:
            best_loss = metric
            patience = 0
            torch.save(model.state_dict(), checkpoint)
        else:
            patience += 1
        if (
            validation_loader is not None
            and patience >= int(optimization["patience"])
        ):
            break
    threshold = 0.5
    threshold_source = "fixed_partial_smoke_without_validation"
    if validation_loader is not None:
        model.load_state_dict(
            torch.load(checkpoint, map_location=device, weights_only=True)
        )
        targets, probabilities = _predict(model, validation_loader, device)
        threshold = threshold_from_validation(targets, probabilities)
        threshold_source = "maximum_validation_f1"
    history_path = output / TRAINING_HISTORY_NAME
    with history_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    from cfl_gnn.training.figures import write_training_validation_loss_figure
    curve_path = output / "training_validation_loss.svg"
    write_training_validation_loss_figure(history, curve_path, title="Training and validation weighted BCE")
    report = {
        "model_version": model_version,
        "prenorm_audit": prenorm_audit,
        "schema_version": SCHEMA_VERSION,
        "training_contract_sha256": plan["contract_sha256"],
        "gate_status": "passed",
        "execution_mode": "serial",
        "legacy_gasse_git_blob_sha1": git_blob_sha1(
            Path(__file__).resolve().parents[1] / "models" / "gasse.py"
        ),
        "epochs_completed": len(history),
        "device_effective": str(device),
        "pos_weight": float(pos_weight.item()),
        "checkpoint_selection": (
            "minimum_validation_weighted_bce"
            if validation_loader is not None
            else "minimum_training_loss_engineering_smoke_only"
        ),
        "selected_probability_threshold": threshold,
        "threshold_source": threshold_source,
        "test_graphs_loaded": 0,
        "outputs": {
            "checkpoint": {
                "file_name": checkpoint.name,
                "sha256": sha256_file(checkpoint),
            },
            TRAINING_HISTORY_NAME: {"sha256": sha256_file(history_path)},
            "training_validation_loss.svg": {"sha256": sha256_file(curve_path)},
        },
        "eligibility": {
            "training_complete": True,
            "held_out_evaluation_ready": plan["held_out_evaluation_ready"],
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "next_gate": (
                "gasse_ddp_parity_and_held_out_evaluation"
                if plan["training_ready"]
                else "complete_validation_and_test_graph_inventory"
            )
        },
    }
    write_json(report_path, report)
    return report


def _distributed_prediction_payload(
    model: Any, loader: Any, device: Any
) -> tuple[list[float], list[float]]:
    """Collect local validation predictions for a later asymmetric gather."""
    return _predict(model, loader, device) if loader is not None else ([], [])


def run_distributed_training(
    plan: Mapping[str, Any],
    *,
    graph_root: str | Path,
    label_root: str | Path,
    output_dir: str | Path,
    epochs_override: int | None = None,
    overwrite: bool = False,
) -> dict[str, Any] | None:
    """Run the preserved DDP loops with the same audited manifest contract.

    The function expects ``torchrun`` to provide the process-group environment.
    Only rank zero writes artifacts; every rank uses a disjoint slice of the same
    deterministic, parent-balanced global schedule.
    """
    validate_training_plan(plan)
    import os

    import torch
    import torch.distributed as dist
    import torch.nn as nn
    from torch.nn.parallel import DistributedDataParallel as DDP
    from torch_geometric.loader import DataLoader

    from cfl_gnn.models.versioning import model_class, fit_versioned_prenorm
    from cfl_gnn.training.distributed import (
        compute_pos_weight,
        eval_loop,
        set_global_seed,
        train_loop,
    )

    if not dist.is_initialized():
        backend = "nccl" if torch.cuda.is_available() else "gloo"
        dist.init_process_group(backend=backend)
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    local_rank = int(os.environ.get("LOCAL_RANK", rank))
    is_master = rank == 0
    if torch.cuda.is_available():
        torch.cuda.set_device(local_rank)
        device = torch.device(f"cuda:{local_rank}")
    else:
        device = torch.device("cpu")
    if not plan.get("engineering_smoke_ready"):
        raise GasseTrainingError("training plan has no training partition")
    output = Path(output_dir).resolve()
    report_path = output / TRAINING_REPORT_NAME
    if is_master:
        if report_path.exists() and not overwrite:
            raise GasseTrainingError("training output exists; use --overwrite")
        output.mkdir(parents=True, exist_ok=True)
    dist.barrier()
    protocol = plan["protocol"]
    optimization = protocol["optimization"]
    epochs = (
        _positive_int(epochs_override, field="epochs_override")
        if epochs_override is not None
        else int(optimization["epochs"])
    )
    set_global_seed(int(optimization["seed"]))
    by_role = {
        role: [record for record in plan["records"] if record["role"] == role]
        for role in ROLES
    }
    train_dataset = GasseLabelViewDataset(
        by_role["train"], graph_root=graph_root, label_root=label_root
    )
    validation_dataset = (
        GasseLabelViewDataset(
            by_role["validation"], graph_root=graph_root, label_root=label_root
        )
        if by_role["validation"]
        else None
    )
    # The identical first audited graph fits prenorm on every rank before DDP.
    representative = train_dataset[0].to(device)
    edge = representative["variable", "rev_coef", "constraint"]
    edge_dim = int(edge.edge_attr.shape[-1]) if edge.edge_attr is not None else 0
    model_version = protocol["architecture"].get("model_version", "legacy")
    base_model = model_class(model_version)(
        var_in_dim=int(representative["variable"].x.shape[-1]),
        cons_in_dim=int(representative["constraint"].x.shape[-1]),
        edge_dim=edge_dim,
        hidden_dim=int(protocol["architecture"]["hidden_dim"]),
        num_layers=int(protocol["architecture"]["num_layers"]),
    ).to(device)
    prenorm_audit = fit_versioned_prenorm(base_model, model_version, train_dataset, representative, device)
    model = DDP(
        base_model,
        device_ids=[local_rank] if device.type == "cuda" else None,
    )
    draws = int(protocol["sampling"]["draws_per_parent_per_epoch"])

    def rank_loader(records: Sequence[Mapping[str, Any]], epoch: int) -> Any:
        global_indices = build_parent_balanced_epoch_indices(
            records,
            seed=int(optimization["seed"]),
            epoch=epoch,
            draws_per_parent=draws,
        )
        local_indices = global_indices[rank::world_size]
        if not local_indices:
            raise GasseTrainingError(
                "parent-balanced draws must be at least the DDP world size"
            )
        return DataLoader(
            train_dataset, batch_size=1, sampler=_IndexSampler(local_indices)
        )

    train_loader = rank_loader(by_role["train"], 0)
    validation_loader = None
    if validation_dataset is not None:
        local_indices = tuple(range(rank, len(validation_dataset), world_size))
        validation_loader = DataLoader(
            validation_dataset,
            batch_size=1,
            sampler=_IndexSampler(local_indices),
        )
    optimizer = torch.optim.Adam(
        model.parameters(), lr=float(optimization["learning_rate"])
    )
    pos_weight = compute_pos_weight(train_loader, device, is_master)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    args = type(
        "TrainingArguments",
        (),
        {
            "grad_clip": float(optimization["gradient_clip_norm"]),
            "clear_cache": False,
        },
    )()
    history: list[dict[str, Any]] = []
    best_loss = float("inf")
    patience = 0
    checkpoint = output / "best_model.pt"
    for epoch in range(epochs):
        train_loader = rank_loader(by_role["train"], epoch)
        train_loss = train_loop(
            model, train_loader, optimizer, loss_fn, device, args
        )
        if validation_loader is not None:
            validation_loss, tp, tn, fp, fn = eval_loop(
                model, validation_loader, loss_fn, device, args
            )
            metric = validation_loss
        else:
            validation_loss, tp, tn, fp, fn = None, 0, 0, 0, 0
            metric = train_loss
        stop = torch.tensor([0], dtype=torch.int64, device=device)
        if is_master:
            metrics = classification_metrics(int(tp), int(tn), int(fp), int(fn))
            history.append(
                {
                    "epoch": epoch + 1,
                    "train_loss": train_loss,
                    "validation_loss": validation_loss,
                    **metrics,
                }
            )
            if metric < best_loss:
                best_loss = metric
                patience = 0
                torch.save(model.module.state_dict(), checkpoint)
            else:
                patience += 1
            if validation_loader is not None and patience >= int(
                optimization["patience"]
            ):
                stop.fill_(1)
        dist.broadcast(stop, src=0)
        if stop.item():
            break
    dist.barrier()
    state_dict = torch.load(checkpoint, map_location=device, weights_only=True)
    model.module.load_state_dict(state_dict)
    local_targets, local_probabilities = _distributed_prediction_payload(
        model, validation_loader, device
    )
    gathered: list[Any] = [None for _ in range(world_size)]
    dist.all_gather_object(
        gathered, (local_targets, local_probabilities)
    )
    result: dict[str, Any] | None = None
    if is_master:
        if validation_loader is not None:
            targets = [value for item in gathered for value in item[0]]
            probabilities = [value for item in gathered for value in item[1]]
            threshold = threshold_from_validation(targets, probabilities)
            threshold_source = "maximum_validation_f1"
            checkpoint_selection = "minimum_validation_weighted_bce"
        else:
            threshold = 0.5
            threshold_source = "fixed_partial_smoke_without_validation"
            checkpoint_selection = "minimum_training_loss_engineering_smoke_only"
        history_path = output / TRAINING_HISTORY_NAME
        with history_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(history[0]))
            writer.writeheader()
            writer.writerows(history)
        result = {
            "model_version": model_version,
            "prenorm_audit": prenorm_audit,
            "schema_version": SCHEMA_VERSION,
            "training_contract_sha256": plan["contract_sha256"],
            "gate_status": "passed",
            "execution_mode": "ddp",
            "world_size": world_size,
            "legacy_gasse_git_blob_sha1": git_blob_sha1(
                Path(__file__).resolve().parents[1] / "models" / "gasse.py"
            ),
            "epochs_completed": len(history),
            "device_effective": str(device),
            "pos_weight": float(pos_weight.item()),
            "checkpoint_selection": checkpoint_selection,
            "selected_probability_threshold": threshold,
            "threshold_source": threshold_source,
            "test_graphs_loaded": 0,
            "outputs": {
                "checkpoint": {
                    "file_name": checkpoint.name,
                    "sha256": sha256_file(checkpoint),
                },
                TRAINING_HISTORY_NAME: {"sha256": sha256_file(history_path)},
            },
            "eligibility": {
                "training_complete": True,
                "held_out_evaluation_ready": plan["held_out_evaluation_ready"],
                "development_only": True,
                "scientific_reporting_eligible": False,
            },
            "decision": {
                "next_gate": (
                    "held_out_gasse_evaluation"
                    if plan["training_ready"]
                    else "complete_validation_and_test_graph_inventory"
                )
            },
        }
        write_json(report_path, result)
    dist.barrier()
    return result
