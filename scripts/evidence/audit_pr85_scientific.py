"""Offline scientific audit of pinned existing evidence; no solver or training."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics
import zipfile
from collections import Counter
from pathlib import Path

import audit_sprint_c_numeric as numeric
import e0_frozen_inference as inference
import prepare_e0_easy_starts as starts
import review_e0_job3506 as solver_review
import review_pr80_job3503 as c1
from verify_sprint_c_artifacts import SELECTION, SOURCE_RECEIPT

ROOT = c1.ROOT
PROTOCOL = "pr85_existing_evidence_scientific_audit_v1"
INFERENCE_SHA = "8f8f0b3c9dc350422f7a36bdb6c46d338186274ebf629d14acb88ea0ecbf9c40"
CHECKPOINTS = {
    "easy": "86e0fb9cf92e6a5d30aaa432caa4074b7e0d2bb22b344cdcbd9be7ed81279cf8",
    "mixed": "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028",
}
EXCLUDED_MEDIUM = {5, 6, 9, 13, 20, 26}


def require(condition, code):
    c1.require(condition, code)


def objective_policy(source, effective):
    """A benchmark correction, NEVER equivalence of max(c*x) and min(c*x)."""
    require(source in (-1, "MAXIMIZE"), "source_sense_not_reviewed")
    require(effective == "MINIMIZE", "incorrect_effective_objective_sense")
    return "correct_source_sense_preserve_coefficients_and_feasible_region"


def partition_rows(split_bytes, selected, observations):
    rows = list(csv.DictReader(io.StringIO(split_bytes.decode("utf-8"))))
    expected = {
        f"CFL_{difficulty}_instance_{i}"
        for difficulty in ("easy", "medium", "hard")
        for i in range(30)
    }
    require(len(rows) == 90, "population_size")
    require({r["source_instance_id"] for r in rows} == expected, "population_identity")
    require(set(observations) == set(selected), "numeric_parent_set")
    output = []
    for row in rows:
        parent = row["source_instance_id"]
        difficulty = parent.split("_")[1]
        require(row["difficulty"] == difficulty, "difficulty_identity")
        fold = int(row["fold"])
        require(fold in range(5), "canonical_fold")
        role = "test" if fold == 0 else "validation" if fold == 1 else "train"
        admitted = parent in selected
        must_admit = difficulty == "easy" or (
            difficulty == "medium"
            and int(parent.rsplit("_", 1)[1]) not in EXCLUDED_MEDIUM
        )
        require(admitted == must_admit, "admitted_parent_identity")
        item = {
            "parent": parent,
            "alias": {"easy": "F", "medium": "M", "hard": "H"}[difficulty]
            + parent.rsplit("_", 1)[1],
            "difficulty": difficulty,
            "fold": fold,
            "role": role,
            "admitted": admitted,
            "exposure": "historically_exposed"
            if admitted and role == "test"
            else "not_asserted_untouched",
            "exclusion": "" if admitted else "outside_admitted_label_quality_sample",
            "model_sha256": "",
            "graph_sha256": "",
            "root_sha256": "",
            "label_sha256": "",
            "label_gap": None,
            "numeric_checks_passed": False,
            "effective_objective_sense": "not_audited",
            "formulation_semantics_qualified": False,
        }
        if admitted:
            record, observed = selected[parent], observations[parent]
            require(record["role"] == observed["role"] == role, "parent_role_leakage")
            require(observed["parent"] == parent, "numeric_parent_identity")
            gap = record["label_gap_declared"]
            require(
                type(gap) in (int, float) and math.isfinite(gap) and 0 <= gap <= 0.1,
                "label_quality_gate",
            )
            require(
                observed["model_sha256"] == record["mip_sha256_declared"],
                "model_identity",
            )
            require(observed["state"] == "numeric_checks_passed", "numeric_gate")
            require(observed["feasibility"]["valid"] is True, "incumbent_feasibility")
            require(
                all(v is True for v in observed["feasibility"]["checks"].values()),
                "feasibility_checks",
            )
            require(observed["optimization_runs_added"] == 0, "numeric_no_optimization")
            objective_policy(
                observed["source_objective_sense"],
                observed["effective_objective_sense"],
            )
            item.update(
                model_sha256=record["mip_sha256_declared"],
                label_gap=gap,
                numeric_checks_passed=True,
                effective_objective_sense="MINIMIZE",
                **{
                    key + "_sha256": record[key]["sha256"]
                    for key in ("graph", "root", "label")
                },
            )
        output.append(item)
    admitted_rows = [r for r in output if r["admitted"]]
    counts = Counter((r["role"], r["difficulty"]) for r in admitted_rows)
    require(
        counts
        == {
            ("train", "easy"): 18,
            ("train", "medium"): 16,
            ("validation", "easy"): 6,
            ("validation", "medium"): 4,
            ("test", "easy"): 6,
            ("test", "medium"): 4,
        },
        "partition_counts",
    )
    # Cross-cohort reuse of the SAME parent is expected; cross-parent identity is not.
    for key in ("model_sha256", "graph_sha256", "root_sha256", "label_sha256"):
        hashes = [r[key] for r in admitted_rows]
        require(
            all(numeric.metadata.HASH.fullmatch(h) for h in hashes),
            "invalid_identity_hash",
        )
        require(len(set(hashes)) == 54, "duplicate_parent_artifact:" + key)
    return sorted(output, key=lambda r: r["parent"])


def predictive_summary(rows):
    require(len(rows) == 20, "twenty_forwards")
    require(
        {(r["cohort"], r["parent"]) for r in rows}
        == {(c, p) for c in CHECKPOINTS for p in inference.CASES},
        "predictive_matrix",
    )
    output = []
    for cohort in CHECKPOINTS:
        for difficulty in ("easy", "medium", "all"):
            group = [
                r
                for r in rows
                if r["cohort"] == cohort
                and (difficulty == "all" or f"_{difficulty}_" in r["parent"])
            ]
            for row in group:
                counts = [row[k] for k in ("tp", "tn", "fp", "fn")]
                require(
                    all(type(x) is int and x >= 0 for x in counts), "confusion_counts"
                )
                require(
                    sum(counts) == row["n_targets"]
                    and row["tp"] + row["fn"] == row["n_positive"],
                    "confusion_denominator",
                )
                tp, _, fp, fn = counts
                expected = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0
                require(c1.close(row["f1_score"], expected), "f1_reconciliation")
            tp, tn, fp, fn = (
                sum(r[k] for r in group) for k in ("tp", "tn", "fp", "fn")
            )
            output.append(
                {
                    "cohort": cohort,
                    "difficulty": difficulty,
                    "parents": len(group),
                    "tp": tp,
                    "tn": tn,
                    "fp": fp,
                    "fn": fn,
                    "targets": tp + tn + fp + fn,
                    "positive_fraction": (tp + fn) / (tp + tn + fp + fn),
                    "micro_precision": tp / (tp + fp) if tp + fp else 0,
                    "micro_recall": tp / (tp + fn) if tp + fn else 0,
                    "micro_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
                    "parent_macro_f1": statistics.mean(r["f1_score"] for r in group),
                    "parent_macro_pr_auc_recorded_not_rescored": statistics.mean(
                        r["pr_auc"] for r in group
                    ),
                    "independent_auc_or_calibration_rescoring": False,
                }
            )
    return output


def checkpoint_rows(metadata, artifacts, models):
    output = []
    for cohort, model in models.items():
        require(cohort in CHECKPOINTS, "unexpected_checkpoint_cohort")
        require(
            model["checkpoint_sha256"] == CHECKPOINTS[cohort], "checkpoint_identity"
        )
        require(
            model["plan_sha256"]
            == SELECTION[cohort][0]
            == artifacts["cohorts"][cohort]["plan_sha256"],
            "checkpoint_plan_binding",
        )
        require(
            model["checkpoint_selection"] == "minimum_validation_weighted_bce"
            and model["threshold_source"] == "maximum_validation_f1"
            and model["new_selection_performed"] is False,
            "checkpoint_selection",
        )
        require(
            type(model["threshold"]) in (int, float)
            and math.isfinite(model["threshold"])
            and 0 <= model["threshold"] <= 1,
            "threshold",
        )
        require(
            model["architecture"] == model["training_protocol"]["architecture"],
            "architecture_binding",
        )
        matches = [p for p in metadata["plans"] if p["sha256"] == model["plan_sha256"]]
        require(bool(matches), "training_plan_missing")
        selected = {r["parent"]: r for r in artifacts["cohorts"][cohort]["parents"]}
        for plan in matches:
            require(len(plan["records"]) == len(selected), "training_record_count")
            require(
                {r["parent"] for r in plan["records"]} == set(selected),
                "training_parent_set",
            )
            for record in plan["records"]:
                other = selected[record["parent"]]
                require(record["role"] == other["role"], "training_role_binding")
                require(
                    record["mip_sha256"] == other["mip_sha256_declared"],
                    "training_mip_binding",
                )
                for key in ("graph", "root", "label"):
                    require(
                        record[key + "_sha256"] == other[key]["sha256"],
                        "training_artifact_binding",
                    )
        output.append(
            {
                "cohort": cohort,
                "checkpoint_sha256": model["checkpoint_sha256"],
                "plan_sha256": model["plan_sha256"],
                "report_sha256": model["report_sha256"],
                "threshold": model["threshold"],
                "train_parents": sum(r["role"] == "train" for r in selected.values()),
                "validation_parents": sum(
                    r["role"] == "validation" for r in selected.values()
                ),
                "test_parents": sum(r["role"] == "test" for r in selected.values()),
                "selected_artifact_identity_reconciled": True,
                "checkpoint_bytes": "hash_verified_by_existing_job3505_not_reloaded_here",
                "checkpoint_and_threshold_selection": "validation_only_attested_in_installed_report",
                "prenorm_and_pos_weight": "train_only_code_path_reviewed_historical_fit_not_independently_replayed",
                "historical_plan_summary_issues": ";".join(
                    sorted({issue for p in matches for issue in p["issues"]})
                ),
                "derived_ancestry": "no_additional_derived_records_admitted_by_this_audit",
            }
        )
    require(len(output) == 2, "two_checkpoint_chains")
    return output


def build():
    package = c1.read_package(ROOT / "docs/evidence/pr80-job3503-return.json")
    c1.validate(package)
    observations = numeric.metadata.strict_json(
        package["members"]["numeric/numeric.json"]["text"]
    )["parents"]
    artifacts = numeric.source_receipt()
    with zipfile.ZipFile(ROOT / "docs/evidence/pr80-inputs-receipt.zip") as archive:
        require(archive.namelist() == ["inputs.json"], "metadata_members")
        raw = archive.read("inputs.json")
    require(numeric.metadata.digest(raw) == SOURCE_RECEIPT, "metadata_receipt_hash")
    metadata = numeric.metadata.strict_json(raw)
    split = (ROOT / "configs/splits/cfl_90_seed42_folds.csv").read_bytes()
    # This split is a Git text file; normalize CRLF ONLY here, never in raw receipts.
    split_lf = split.replace(b"\r\n", b"\n")
    require(
        numeric.metadata.digest(split_lf) == artifacts["split_manifest_sha256"],
        "canonical_split_hash",
    )
    parents = partition_rows(
        split_lf, numeric.selected_parents(artifacts), observations
    )
    inference_raw = (ROOT / "docs/evidence/e0/job3505-return.json").read_bytes()
    predictions = inference.validate_return(inference_raw, INFERENCE_SHA)
    value = numeric.metadata.strict_json(inference_raw)
    frozen = numeric.metadata.strict_json(value["members"]["plan.json"]["text"])
    checkpoints = checkpoint_rows(metadata, artifacts, frozen["models"])
    summary = predictive_summary(predictions)
    report = {
        "protocol_id": PROTOCOL,
        "base_develop_commit": "5d7b00d4c650c3145bd376e8e270711eba984dbd",
        "population": 90,
        "admitted_parents": 54,
        "numerically_passed_parents": 54,
        "partition_counts": {
            role: sum(r["admitted"] and r["role"] == role for r in parents)
            for role in ("train", "validation", "test")
        },
        "duplicate_selected_parent_artifacts": 0,
        "frozen_forwards_reconciled": 20,
        "source_sense": "MAXIMIZE",
        "required_effective_sense": "MINIMIZE",
        "sense_decision": "author_approved_benchmark_error_correction_20261011",
        "equivalence_to_original_maximization_claimed": False,
        "all_admitted_numeric_receipts_use_minimize": True,
        "full_benchmark_formulation_semantics_qualified": False,
        "hard_maximize_triviality": "author_reported_not_retimed_or_independently_verified_here",
        "historically_unexposed_test_claimed": False,
        "auc_or_calibration_independently_rescored": False,
        "historical_prenorm_and_pos_weight_fit_independently_replayed": False,
        "new_comparison_admitted": False,
        "resource_budget_approved": False,
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "submissions_added": 0,
        "raw_receipt_flags_rewritten": False,
        "blocking_gates": [
            "raw_CFL_constraint_domain_cost_mapping_and_units_not_in_public_receipts",
            "historical_preprocessing_fit_provenance_not_fully_exported",
            "PR86_PR87_exact_execution_budget_not_approved",
        ],
        "source_receipts": {
            "metadata": SOURCE_RECEIPT,
            "artifacts": numeric.RECEIPT_SHA,
            "numeric": c1.RETURN_SHA,
            "inference": INFERENCE_SHA,
        },
        "claim_scope": "partition_identity_and_existing_confusion_metrics_only_not_blanket_scientific_promotion",
    }
    return report, parents, checkpoints, summary


def warmstart_trace():
    """Reconcile existing six-parent binding and 18 solves; never run a solver."""
    binding = starts.validate(
        (ROOT / "docs/evidence/e0/easy-start-binding.json").read_bytes(),
        solver_review.flow.BINDING_SHA,
    )
    _, (solves, _, _) = solver_review.reviewed()
    selected = numeric.selected_parents(numeric.source_receipt())
    rows = []
    for item in binding["parents"]:
        parent = item["parent"]
        group = [r for r in solves if r["source_instance_id"] == parent]
        require(len(group) == 3, "three_method_binding")
        guided = [r for r in group if r["method"] != solver_review.flow.METHODS[0]]
        require(len(guided) == 2, "two_guided_methods")
        require(
            all(r["selected_support"] == item["selected_support"] for r in guided),
            "installed_support_binding",
        )
        require(
            all(
                r["positive_assignments"] == item["positive_assignments"]
                for r in guided
            ),
            "installed_positive_binding",
        )
        rows.append(
            {
                "parent": parent,
                "alias": c1.alias(parent),
                "model_sha256": item["mip_sha256"],
                "graph_sha256": selected[parent]["graph"]["sha256"],
                "root_sha256": item["root_sha256"],
                "prediction_sha256": item["prediction_sha256"],
                "private_starts_sha256": item["private_starts_sha256"],
                "gnn_assignment_sha256": item["gnn_assignment_sha256"],
                "lp_assignment_sha256": item["lp_assignment_sha256"],
                "selected_support": item["selected_support"],
                "positive_assignments": item["positive_assignments"],
                "accepted_starts_recorded": sum(
                    r["start_accepted_recorded"] is True for r in guided
                ),
                "source_binding_sha256": solver_review.flow.BINDING_SHA,
                "source_solve_return_sha256": solver_review.SHA,
                "variable_order_scope": "existing_installed_graph_root_prediction_start_checks_not_private_vector_reload",
                "lp_control_depends_on_gnn_support": True,
                "root_preparation_cost_seconds": None,
                "new_optimization_runs": 0,
            }
        )
    require(len(rows) == 6, "six_easy_start_bindings")
    return rows


def produce(output):
    report, parents, checkpoints, summary = build()
    trace = warmstart_trace()
    report["existing_warmstart_trace"] = {
        "parents": 6,
        "historical_solves_reconciled": 18,
        "accepted_starts_recorded": sum(r["accepted_starts_recorded"] for r in trace),
        "medium_start_binding_qualified": False,
        "private_variable_vectors_reloaded": False,
        "source_solve_return_sha256": solver_review.SHA,
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in (
        ("parents.csv", parents),
        ("checkpoints.csv", checkpoints),
        ("predictive_summary.csv", summary),
        ("warmstart_trace.csv", trace),
    ):
        c1.write_csv(output / name, rows)
    inference.legacy.write(output / "audit.json", report)
    files = {
        p.name: numeric.metadata.digest(p.read_bytes())
        for p in sorted(output.iterdir())
    }
    inputs = [
        "configs/splits/cfl_90_seed42_folds.csv",
        "scripts/evidence/audit_pr85_scientific.py",
        "src/cfl_gnn/training/gasse_reconnected.py",
        "src/cfl_gnn/models/versioning.py",
    ]
    inference.legacy.write(
        output / "manifest.json",
        {
            "protocol_id": PROTOCOL,
            "files": files,
            "source_text_sha256_lf": {
                name: numeric.metadata.digest(
                    (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
                )
                for name in inputs
            },
            "normalization_scope": "listed_source_text_only_not_historical_receipts",
        },
    )
    print(
        json.dumps(
            {
                "parents": 54,
                "forwards": 20,
                "new_comparison_admitted": False,
                "output": str(output),
            }
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    produce(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
