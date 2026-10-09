"""Twenty frozen-model test forwards, using PR80-admitted graphs and cached roots."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
from pathlib import Path

import audit_sprint_c_inputs as meta
import pr80_integrated as legacy
import review_pr80_job3503 as c1
import sprint_c_runtime

PROTOCOL = "e0_frozen_test_inference_v1"
CASES = tuple(f"CFL_easy_instance_{i}" for i in (0, 3, 6, 14, 27, 29)) + tuple(
    f"CFL_medium_instance_{i}" for i in (0, 4, 7, 12)
)
MEMBERS = {"plan.json", "runtime.json", "inference.json"}


def plan():
    package = c1.read_package(c1.ROOT / "docs/evidence/pr80-job3503-return.json")
    c1.validate(package)
    original = meta.strict_json(package["members"]["inference.json"]["text"])
    return {
        "protocol_id": PROTOCOL,
        "source_c1_return_sha256": c1.RETURN_SHA,
        "cases": list(CASES),
        "role": "test",
        "models": original["models"],
        "maximum_forwards": 20,
        "training_runs_added": 0,
        "optimization_runs_added": 0,
        "new_threshold_or_prenorm_fit": False,
        "raw_predictions_exported": False,
        "scientific_reporting_eligible": False,
        "label_use": "scoring_only_not_start_selection",
        "historical_exposure": "existing_split_not_new_untouched_holdout",
        "lp_start_source": "original_root_json_values",
        "root_reoptimized": False,
        "solver_execution_admitted": False,
        "scheduler": {
            "nodes": 1,
            "tasks": 1,
            "cpus_per_task": 4,
            "gpus": 1,
            "memory_mib": 32768,
            "wall_seconds": 2400,
            "requeue": False,
            "exclusive": False,
        },
        "support": {
            "fraction": 0.1,
            "maximum": 20000,
            "rule": "existing_pr58_class_aware_and_matched_lp",
        },
    }


def run(data_root, output):
    frozen = plan()
    expected = {
        "SLURM_JOB_NUM_NODES": "1",
        "SLURM_CPUS_PER_TASK": "4",
        "SLURM_MEM_PER_NODE": "32768",
    }
    c1.require(all(os.environ.get(k) == v for k, v in expected.items()), "allocation")
    c1.require(os.environ.get("SLURM_RESTART_COUNT", "0") == "0", "no_requeue")
    output.mkdir(exist_ok=False)
    legacy.write(output / "plan.json", frozen)
    legacy.write(output / "runtime.json", sprint_c_runtime.observe())
    package = c1.read_package(c1.ROOT / "docs/evidence/pr80-job3503-return.json")
    (output / "numeric").mkdir()
    # Exact reviewed member, reused; no numerical audit or graph regeneration.
    with (output / "numeric/numeric.json").open("xb") as stream:
        stream.write(package["members"]["numeric/numeric.json"]["text"].encode())
    inference = legacy.infer(
        data_root,
        output,
        cases=CASES,
        role="test",
        protocol=PROTOCOL,
        expected_models=frozen["models"],
        original_root_values=True,
        reader_seconds=2100,
    )
    return (
        0 if inference["state"] == "complete" and len(inference["cases"]) == 20 else 2
    )


def package(stage):
    members = {}
    for name in sorted(MEMBERS):
        path = stage / "run" / name
        if path.is_file():
            data = path.read_bytes()
            c1.require(len(data) <= 8 * 1024**2, "member_size")
            members[name] = {"text": data.decode(), "sha256": meta.digest(data)}
    result = {
        "protocol_id": PROTOCOL,
        "members": members,
        "job_id": (stage / "job_id.txt").read_text().strip(),
        "source_commit": (stage / "source_commit.txt").read_text().strip(),
        "accounting": (stage / "accounting.txt").read_text(),
        "raw_logs_included": False,
        "raw_predictions_exported": False,
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "scientific_reporting_eligible": False,
        "complete_members": set(members) == MEMBERS,
    }
    target = stage / "public_return.json"
    data = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if target.exists():
        c1.require(target.read_bytes() == data, "preserve_existing_return")
    else:
        with target.open("xb") as stream:
            stream.write(data)
    print("E0_RETURN_SHA256=" + meta.digest(data))
    print("E0_RETURN=" + str(target))


def validate_return(data, expected_sha):
    c1.require(meta.digest(data) == expected_sha, "outer_sha")
    value = meta.strict_json(data)
    c1.require(value["protocol_id"] == PROTOCOL, "protocol")
    c1.require(set(value["members"]) == MEMBERS, "members")
    c1.require(value["raw_logs_included"] is False, "logs")
    c1.require(value["raw_predictions_exported"] is False, "predictions")
    parsed = {}
    for name, member in value["members"].items():
        c1.require(
            meta.digest(member["text"].encode()) == member["sha256"], "member_sha"
        )
        parsed[name] = meta.strict_json(member["text"])
    frozen = plan()
    c1.require(parsed["plan.json"] == frozen, "frozen_plan")
    inference = parsed["inference.json"]
    c1.require(inference["protocol_id"] == PROTOCOL, "inference_protocol")
    c1.require(inference["state"] == "complete", "inference_incomplete")
    c1.require(inference["models"] == frozen["models"], "models")
    c1.require(parsed["runtime.json"]["packages_modified"] is False, "runtime")
    for obj in (value, inference):
        for key in ("optimization_runs_added", "training_runs_added"):
            c1.require(type(obj[key]) is int and obj[key] == 0, key)
        c1.require(obj["scientific_reporting_eligible"] is False, "eligibility")
    c1.require(inference["new_threshold_or_prenorm_fit"] is False, "selection")
    expected = {(cohort, parent) for cohort in ("easy", "mixed") for parent in CASES}
    cases = inference["cases"]
    c1.require(
        len(cases) == 20 and {(r["cohort"], r["parent"]) for r in cases} == expected,
        "case_matrix",
    )
    rows = []
    admitted = c1.audit.selected_parents(c1.audit.source_receipt())
    c1_package = c1.read_package(c1.ROOT / "docs/evidence/pr80-job3503-return.json")
    numerical = meta.strict_json(c1_package["members"]["numeric/numeric.json"]["text"])
    for row in cases:
        c1.require(row["role"] == "test", "role")
        c1.require(
            row["lp_start_source"] == "original_root_json_values", "lp_precision"
        )
        c1.require(
            row["start_feasibility_or_acceptance_claimed"] is False, "start_claim"
        )
        c1.require(
            meta.HASH.fullmatch(row["prediction_sha256"]) is not None, "prediction_hash"
        )
        for artifact in ("graph", "root"):
            c1.require(
                row[artifact + "_sha256"]
                == admitted[row["parent"]][artifact]["sha256"],
                "input_artifact",
            )
        metrics = row["metrics"]
        tp, tn, fp, fn = (metrics[k] for k in ("tp", "tn", "fp", "fn"))
        c1.require(all(type(n) is int and n >= 0 for n in (tp, tn, fp, fn)), "counts")
        rep = numerical["parents"][row["parent"]]["representation"]
        c1.require(
            tp + tn + fp + fn == metrics["n_targets"] == rep["discrete_targets"],
            "targets",
        )
        c1.require(
            tp + fn == metrics["n_positive"] == rep["positive_discrete_targets"],
            "positives",
        )
        for key, expected_value in {
            "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 0,
            "f1_score": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
            "accuracy": (tp + tn) / metrics["n_targets"],
        }.items():
            c1.require(c1.close(metrics[key], expected_value), "confusion_metric")
        c1.require(
            row["selected_support"]
            == (
                0
                if row["abstained"]
                else min(20000, math.floor(0.1 * metrics["n_targets"]))
            ),
            "support",
        )
        for key in (
            "forward_seconds",
            "case_wall_seconds",
            "gpu_peak_allocated_bytes",
            "gpu_peak_reserved_bytes",
        ):
            c1.require(
                type(row[key]) in (int, float)
                and math.isfinite(row[key])
                and row[key] >= 0,
                "timing_or_memory",
            )
        rows.append(
            {
                "cohort": row["cohort"],
                "parent": row["parent"],
                "role": row["role"],
                **row["metrics"],
                "pr_auc": row["pr_auc"],
                "roc_auc": row["roc_auc"],
                "forward_seconds": row["forward_seconds"],
                "case_wall_seconds": row["case_wall_seconds"],
                "gpu_peak_allocated_bytes": row["gpu_peak_allocated_bytes"],
                "selected_support": row["selected_support"],
                "abstained": row["abstained"],
                "prediction_sha256": row["prediction_sha256"],
            }
        )
    accounting = list(csv.DictReader(io.StringIO(value["accounting"]), delimiter="|"))
    c1.require(
        any(
            r["JobID"] == value["job_id"]
            and r["State"] == "COMPLETED"
            and r["ExitCode"] == "0:0"
            for r in accounting
        ),
        "job_not_completed",
    )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "run", "package", "review"))
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.action == "plan":
        print("E0_PLAN_SHA256=" + legacy.write(args.output, plan()))
    elif args.action == "run":
        return run(args.data_root, args.output)
    elif args.action == "package":
        package(args.output)
    else:
        c1.require(args.receipt.stat().st_size <= 8 * 1024**2, "return_size")
        rows = validate_return(args.receipt.read_bytes(), args.expected_sha256)
        args.output.mkdir(exist_ok=False)
        c1.write_csv(args.output / "test_inference.csv", rows)
        print("E0_TWENTY_FROZEN_FORWARDS_RECONCILED_NO_SOLVER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
