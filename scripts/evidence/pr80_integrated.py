"""Existing tfm_env: numerical sample audit and four bounded validation forwards."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import audit_sprint_c_inputs as meta
import audit_sprint_c_numeric as numeric
import sprint_c_runtime as runtime
from verify_sprint_c_artifacts import SELECTION, AuditStop, Reader

REPO = Path(__file__).resolve().parents[2]
CASES = ("CFL_easy_instance_1", "CFL_medium_instance_11")
PROTOCOL = "pr80_existing_runtime_integrated_v1"


def write(path, value):
    raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    with Path(path).open("xb") as stream:
        stream.write(raw)
    return meta.digest(raw)


def table(path, rows):
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quantile(values, q):
    values = sorted(values)
    x = (len(values) - 1) * q
    a, b = math.floor(x), math.ceil(x)
    return values[a] + (values[b] - values[a]) * (x - a)


def descriptive(report, output):
    """One row per original parent. Never turn absent observations into zero."""
    fields = (
        "variables",
        "constraints",
        "nonzeros",
        "density",
        "binary_variables",
        "integer_variables",
        "continuous_variables",
        "discrete_targets",
        "positive_discrete_targets",
    )
    selected = numeric.selected_parents(numeric.source_receipt())
    rows = []
    for parent, record in sorted(selected.items()):
        result = report["parents"][parent]
        passed = result["state"] == "numeric_checks_passed"
        row = {
            "parent": parent,
            "difficulty": parent.split("_")[1],
            "role": record["role"],
            "state": result["state"],
            **{
                key: result.get("representation", {}).get(key) if passed else None
                for key in fields
            },
        }
        row["label_gap_declared"] = record["label_gap_declared"]
        row["positive_prevalence"] = (
            row["positive_discrete_targets"] / row["discrete_targets"]
            if passed and row["discrete_targets"]
            else None
        )
        rows.append(row)
    table(output / "parent_statistics.csv", rows)
    summary = []
    for difficulty, role in sorted({(r["difficulty"], r["role"]) for r in rows}):
        group = [r for r in rows if (r["difficulty"], r["role"]) == (difficulty, role)]
        for metric in (*fields, "positive_prevalence", "label_gap_declared"):
            values = [r[metric] for r in group if r[metric] is not None]
            summary.append(
                {
                    "difficulty": difficulty,
                    "role": role,
                    "metric": metric,
                    "parents": len(group),
                    "observed": len(values),
                    "missing": len(group) - len(values),
                    "minimum": min(values) if values else None,
                    "q1": quantile(values, 0.25) if values else None,
                    "median": quantile(values, 0.5) if values else None,
                    "q3": quantile(values, 0.75) if values else None,
                    "maximum": max(values) if values else None,
                    "mean": sum(values) / len(values) if values else None,
                }
            )
    table(output / "descriptive_statistics.csv", summary)
    return {
        "parents": len(rows),
        "numerically_passed": sum(r["state"] == "numeric_checks_passed" for r in rows),
        "quantile_rule": "linear_interpolation_type7",
        "independent_unit": "original_parent",
    }


def report_binding(plan, report):
    numeric.require(
        report.get("gate_status") == "passed"
        and report.get("training_contract_sha256") == plan["contract_sha256"]
        and report.get("test_graphs_loaded") == 0,
        "training_report_binding",
    )
    numeric.require(
        report.get("checkpoint_selection") == "minimum_validation_weighted_bce"
        and report.get("threshold_source") == "maximum_validation_f1",
        "frozen_selection_required",
    )
    threshold = report.get("selected_probability_threshold")
    numeric.require(
        type(threshold) in (int, float)
        and math.isfinite(threshold)
        and 0 <= threshold <= 1,
        "invalid_frozen_threshold",
    )
    architecture = plan["protocol"]["architecture"]
    numeric.require(
        architecture.get("model_version") == "gasse_v2_alternating_prenorm"
        and report.get("model_version") == architecture["model_version"],
        "corrected_model_required",
    )
    return threshold


def discover_model(reader, cohort):
    """Select by prior reviewed plan bytes, never by new inference outcomes."""
    plans, reports = {}, []
    for path in reader.files:
        if path.name in ("gasse_training_plan.json", "gasse_training_report.json"):
            raw = reader.read(path, content=True)
            if path.name == "gasse_training_plan.json":
                plans.setdefault(meta.digest(raw), (path, raw))
            else:
                reports.append((meta.digest(raw), path, raw))
    numeric.require(SELECTION[cohort][0] in plans, "selected_plan_missing")
    plan = meta.strict_json(plans[SELECTION[cohort][0]][1])
    numeric.require(meta.plan_summary(plan)["metadata_consistent"], "plan_contract")
    candidates = {}
    for report_hash, path, raw in reports:
        report = meta.strict_json(raw)
        if report.get("training_contract_sha256") != plan["contract_sha256"]:
            continue
        # Ignore engineering-only/failed reports, never substitute a threshold.
        if (
            report.get("gate_status") != "passed"
            or report.get("checkpoint_selection") != "minimum_validation_weighted_bce"
        ):
            continue
        threshold = report_binding(plan, report)
        descriptor = report["outputs"]["checkpoint"]
        checkpoint = reader.reference(path.parent, descriptor["file_name"])
        reader.verify(checkpoint, descriptor["sha256"])
        candidates.setdefault(report_hash, (checkpoint, report, report_hash, threshold))
    numeric.require(len(candidates) == 1, "checkpoint_report_missing_or_ambiguous")
    checkpoint, report, report_hash, threshold = next(iter(candidates.values()))
    return (
        plan,
        checkpoint,
        report,
        {
            "plan_sha256": SELECTION[cohort][0],
            "report_sha256": report_hash,
            "checkpoint_sha256": report["outputs"]["checkpoint"]["sha256"],
            "threshold": threshold,
            "architecture": plan["protocol"]["architecture"],
            "checkpoint_selection": report["checkpoint_selection"],
            "threshold_source": report["threshold_source"],
            "new_selection_performed": False,
            "training_protocol": plan["protocol"],
        },
    )


def infer(data_root, output):
    sys.path.insert(0, str(REPO / "src"))
    import torch

    from cfl_gnn.evaluation.gasse_reconnected import _metric_row, binary_curve_rows
    from cfl_gnn.experiments.pr58_guidance import (
        class_aware_gnn_assignments,
        matched_root_lp_assignments,
    )
    from cfl_gnn.models.versioning import model_class
    from cfl_gnn.training.binary_contract import binary_targets

    report = meta.strict_json((output / "numeric/numeric.json").read_bytes())
    numeric.require(
        all(v["numeric_checks_passed"] for v in report["cohorts"].values()),
        "numerical_admission_incomplete",
    )
    numeric.require(
        torch.cuda.is_available() and torch.cuda.device_count() == 1,
        "one_allocated_gpu_required",
    )
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    torch.set_num_threads(1)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    device = torch.device("cuda:0")
    reader = Reader(data_root, seconds=590, max_bytes=8 * 1024**3)
    reader.scan()
    paths = {
        meta.digest(p.relative_to(reader.root).as_posix().encode()): p
        for p in reader.files
    }
    selected = numeric.selected_parents(numeric.source_receipt())
    result = {
        "state": "complete",
        "protocol_id": PROTOCOL,
        "scientific_reporting_eligible": False,
        "cases": [],
        "models": {},
        "seed": 42,
        "device_name": torch.cuda.get_device_name(0),
        "torch_cuda_build": torch.version.cuda,
        "gpu_total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
        "gpu_compute_capability": list(torch.cuda.get_device_capability(0)),
        "cudnn_version": torch.backends.cudnn.version(),
        "torch_threads": torch.get_num_threads(),
        "tf32_matmul": False,
        "cudnn_benchmark": False,
        "cudnn_deterministic": True,
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "bitwise_reproducibility_claimed": False,
        "training_runs_added": 0,
        "optimization_runs_added": 0,
        "new_threshold_or_prenorm_fit": False,
    }
    (output / "predictions").mkdir()
    for cohort in ("easy", "mixed"):
        stage = "bind_frozen_model"
        try:
            plan, checkpoint, training, binding = discover_model(reader, cohort)
            result["models"][cohort] = binding
            stage = "load_checkpoint"
            # Existing project's weights-only state-dict route. No checkpoint conversion.
            with checkpoint.open("rb") as stream:
                checkpoint_hash = hashlib.sha256()
                for block in iter(lambda: stream.read(1024**2), b""):
                    checkpoint_hash.update(block)
                numeric.require(
                    checkpoint_hash.hexdigest() == binding["checkpoint_sha256"],
                    "checkpoint_hash_before_load",
                )
                stream.seek(0)
                state = torch.load(stream, map_location="cpu", weights_only=True)
            reader.verify(checkpoint, binding["checkpoint_sha256"])
            architecture = binding["architecture"]
            model = model_class(architecture["model_version"])(
                var_in_dim=7,
                cons_in_dim=5,
                edge_dim=1,
                hidden_dim=int(architecture["hidden_dim"]),
                num_layers=int(architecture["num_layers"]),
            )
            model.load_state_dict(
                {key.removeprefix("module."): value for key, value in state.items()},
                strict=True,
            )
            model.to(device).eval()
            for parent in CASES:
                stage = "validation_case_" + parent
                record = selected[parent]
                numeric.require(
                    numeric.split_for(parent)[1] == record["role"] == "validation",
                    "validation_role",
                )
                numeric.require(
                    parent
                    not in {
                        r["parent_instance_id"]
                        for r in plan["records"]
                        if r["role"] == "train"
                    },
                    "training_overlap",
                )
                started = time.monotonic()
                graph, _ = numeric.load_graph(
                    paths[record["graph"]["artifact_id"]], record["graph"]["sha256"]
                )
                root_path = paths[record["root"]["artifact_id"]]
                reader.verify(root_path, record["root"]["sha256"])
                names = numeric.bounded_json_gzip(root_path)["variable_names"]
                numeric.require(
                    len(names) == len(graph["variable"].x), "variable_names"
                )
                graph = graph.to(device)
                mask, targets = binary_targets(graph)
                edge = graph["variable", "rev_coef", "constraint"]
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                forward_start = time.monotonic()
                with torch.no_grad():
                    logits = model(
                        x_var=graph["variable"].x,
                        x_cons=graph["constraint"].x,
                        edge_v2c=edge.edge_index,
                        binary_mask=mask,
                        edge_attr=edge.edge_attr,
                    )
                    probabilities = torch.sigmoid(logits)
                torch.cuda.synchronize()
                forward_seconds = time.monotonic() - forward_start
                numeric.require(
                    logits.numel() == targets.numel()
                    and bool(torch.isfinite(logits).all()),
                    "prediction_shape_or_finiteness",
                )
                truth, scores = targets.cpu().tolist(), probabilities.cpu().tolist()
                indices = torch.where(mask)[0].cpu().tolist()
                predictions = [
                    {
                        "variable_name": names[i],
                        "probability": p,
                        "predicted_value": int(p >= binding["threshold"]),
                    }
                    for i, p in zip(indices, scores)
                ]
                gnn = class_aware_gnn_assignments(
                    predictions, fraction=0.1, absolute_cap=20000
                )
                lp = matched_root_lp_assignments(
                    [names[i] for i in indices],
                    graph["variable"].x[mask, 6].cpu().tolist(),
                    support=gnn["selected_support"],
                    positive_assignments=gnn["positive_assignments"],
                )
                payload = {
                    "parent": parent,
                    "role": "validation",
                    "cohort": cohort,
                    "checkpoint_sha256": binding["checkpoint_sha256"],
                    "threshold": binding["threshold"],
                    "predictions": predictions,
                    "gnn_partial_start": gnn,
                    "root_lp_matched_partial_start": lp,
                    "submitted_to_solver": False,
                    "target_labels_included": False,
                }
                artifact_name = f"{cohort}-{parent}.json"
                artifact_hash = write(output / "predictions" / artifact_name, payload)
                metrics = _metric_row(
                    "validation_parent", parent, truth, scores, binding["threshold"]
                )
                _, _, roc, pr = binary_curve_rows(truth, scores)
                result["cases"].append(
                    {
                        "cohort": cohort,
                        "parent": parent,
                        "role": "validation",
                        "metrics": metrics,
                        "roc_auc": roc,
                        "pr_auc": pr,
                        "forward_seconds": forward_seconds,
                        "case_wall_seconds": time.monotonic() - started,
                        "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                        "gpu_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                        "prediction_file": artifact_name,
                        "prediction_sha256": artifact_hash,
                        "selected_support": gnn["selected_support"],
                        "abstained": gnn["abstained"],
                        "root_precomputation_included": False,
                        "start_feasibility_or_acceptance_claimed": False,
                    }
                )
                del (
                    graph,
                    targets,
                    mask,
                    edge,
                    logits,
                    probabilities,
                    predictions,
                    payload,
                )
            del model, state
            torch.cuda.empty_cache()
        except Exception as error:
            result["state"] = "partial"
            result["failure"] = {
                "cohort": cohort,
                "stage": stage,
                "exception_type": type(error).__name__,
                "reason": str(error)
                if isinstance(error, AuditStop)
                else "inference_failed",
                "private_text_included": False,
            }
            break  # No retries or OOM cascade into another model.
    write(output / "inference.json", result)
    return result


def run(data_root, output, *, prior_return=None):
    output.mkdir()
    observed = runtime.observe()
    write(output / "runtime.json", observed)
    result = {
        "protocol_id": PROTOCOL,
        "state": "partial",
        "runtime": observed,
        "source_commit": os.environ.get("PR80_COMMIT"),
        "job_id": os.environ.get("SLURM_JOB_ID"),
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
        "training_admitted": False,
        "limits": {
            "numeric_seconds": 1800,
            "inference_seconds": 600,
            "maximum_forward_calls": 4,
            "allocated_gpus": 1,
            "allocated_cpus": 4,
            "memory_mib": 32768,
        },
    }
    stage = "numerical_audit"
    try:
        numeric.SECONDS = 1800
        audit = numeric.collect(
            data_root, output / "numeric", prior_return=prior_return
        )
        result["prior_return_sha256"] = audit.get("prior_return_sha256")
        result["reused_numerical_parents"] = len(
            audit.get("reused_parent_observations", [])
        )
        result["sample"] = descriptive(audit, output)
        stage = "inference"
        if all(v["numeric_checks_passed"] for v in audit["cohorts"].values()):
            with (output / "inference.private.log").open("xb") as log:
                child = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        __file__,
                        "infer",
                        "--data-root",
                        str(data_root),
                        "--output",
                        str(output),
                    ],
                    stdout=log,
                    stderr=log,
                    timeout=600,
                    check=False,
                )
            result["inference_returncode"] = child.returncode
            if (output / "inference.json").is_file():
                result["inference"] = meta.strict_json(
                    (output / "inference.json").read_bytes()
                )
                if (
                    child.returncode == 0
                    and result["inference"]["state"] == "complete"
                    and len(result["inference"]["cases"]) == 4
                ):
                    result["state"] = "complete_pending_independent_review"
        else:
            result["inference"] = {"state": "not_attempted_numeric_incomplete"}
    except Exception as error:
        result["failure"] = {
            "stage": stage,
            "exception_type": type(error).__name__,
            "private_text_included": False,
        }
    write(output / "integrated.json", result)
    print(
        json.dumps(
            {
                "state": result["state"],
                "optimization_runs_added": 0,
                "training_runs_added": 0,
            }
        )
    )
    return 0 if result["state"] == "complete_pending_independent_review" else 2


def package(stage):
    allowed = (
        "runtime.json",
        "integrated.json",
        "numeric/numeric.json",
        "inference.json",
        "parent_statistics.csv",
        "descriptive_statistics.csv",
    )
    members = {}
    for name in allowed:
        path = stage / "run" / name
        if path.is_file():
            raw = path.read_bytes()
            numeric.require(len(raw) <= 8 * 1024**2, "return_member_size")
            members[name] = {"sha256": meta.digest(raw), "text": raw.decode("utf-8")}
    result = {
        "protocol_id": PROTOCOL,
        "members": members,
        "job_id": (stage / "job_id.txt").read_text().strip(),
        "accounting": (stage / "accounting.txt").read_text(),
        "scientific_reporting_eligible": False,
        "raw_logs_included": False,
        "complete_return": "integrated.json" in members,
    }
    raw = json.dumps(result, sort_keys=True, indent=2).encode() + b"\n"
    target = stage / "public_return.json"
    if target.exists():
        numeric.require(target.read_bytes() == raw, "existing_return_differs")
    else:
        with target.open("xb") as stream:
            stream.write(raw)
    print("PR80_RETURN_SHA256=" + hashlib.sha256(raw).hexdigest())
    print("PR80_RETURN=" + str(target))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "infer", "package", "verify-prior"))
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-return", type=Path)
    args = parser.parse_args()
    if args.action == "verify-prior":
        reused = numeric.reuse_job3501(args.reuse_return)
        print(
            json.dumps(
                {
                    "prior_job": "3501",
                    "reused_parents": len(reused),
                    "prior_return_sha256": numeric.JOB3501_RETURN_SHA,
                    "submissions_added": 0,
                    "optimization_runs_added": 0,
                }
            )
        )
    elif args.action == "package":
        package(args.output)
    elif args.action == "infer":
        raise SystemExit(
            0 if infer(args.data_root, args.output)["state"] == "complete" else 2
        )
    else:
        raise SystemExit(
            run(args.data_root, args.output, prior_return=args.reuse_return)
        )
