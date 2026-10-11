"""Consolidate the existing PR85 receipt offline, retaining all scientific limits."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import audit_pr85_scientific as audit
import collect_pr85_private_context as context

ROOT = audit.ROOT
PROTOCOL = "pr85_documentary_closure_v1"
RECEIPT = "docs/evidence/e0/pr85-context-return.json"
RECEIPT_SHA = "15136b4d0d22bc97b82ef5f778bca6dbe0686fb32209980dd62b2df0c907a282"
REQUEST = "docs/evidence/e0/pr85-context-request.json"


def reconcile_training(item, model, chain):
    for key in ("checkpoint_sha256", "plan_sha256", "report_sha256", "threshold"):
        audit.require(item[key] == model[key] == chain[key], "training_binding:" + key)
    audit.require(
        type(item["epochs_completed"]) is int
        and item["epochs_completed"]
        == model["training_protocol"]["optimization"]["epochs"],
        "epochs_binding",
    )
    audit.require(
        type(item["train_parents"]) is int
        and type(item["prenorm_training_graphs"]) is int
        and item["train_parents"]
        == item["prenorm_training_graphs"]
        == chain["train_parents"],
        "prenorm_parent_binding",
    )
    audit.require(
        type(item["test_graphs_loaded"]) is int and item["test_graphs_loaded"] == 0,
        "historical_test_access",
    )
    audit.require(
        item["train_only_prenorm_attested_by_hashed_report"] is True,
        "prenorm_attestation",
    )
    audit.require(item["historical_fit_replayed"] is False, "no_fit_replay")
    audit.require(
        item["pos_weight_train_only_scope"]
        == "code_path_review_not_consumed_sample_replay",
        "class_weight_scope",
    )
    weight = item["pos_weight"]
    audit.require(
        type(weight) in (int, float) and math.isfinite(weight) and weight > 0,
        "class_weight_value",
    )
    return {
        "cohort": chain["cohort"],
        **item,
        "qualification": "hashed_report_attestation_not_independent_fit_replay",
    }


def reconcile_model(parent, item, observed):
    audit.objective_policy(item["source_sense"], item["required_effective_sense"])
    audit.require(
        item["source_sha256"] == observed["model_sha256"], "lp_numeric_identity"
    )
    audit.require(item["full_semantics_qualified"] is False, "no_semantic_promotion")
    audit.require(
        item["coverage"] == "representative_parent_only_not_all_54",
        "representative_scope",
    )
    audit.require(item["economic_units"] == "not_encoded_or_inferred", "unit_scope")
    representation = observed["representation"]
    mapping = {
        "variables_observed": "variables",
        "explicit_binary_variables": "binary_variables",
        "explicit_general_variables": "integer_variables",
        "remaining_continuous_by_linear_lp_default": "continuous_variables",
    }
    for private_key, numeric_key in mapping.items():
        audit.require(
            type(item[private_key]) is int
            and item[private_key] == representation[numeric_key],
            "lp_dimension_binding:" + private_key,
        )
    audit.require(
        sum(item["row_senses"].values()) == representation["constraints"],
        "constraint_count_binding",
    )
    audit.require(
        set(item["row_senses"]) == {"<=", ">="}, "representative_inequalities"
    )
    audit.require(
        item["objective"]["constant"] == 0, "representative_objective_constant"
    )
    families = item["objective"]["families"]
    audit.require(bool(families), "objective_families")
    for family in families.values():
        audit.require(
            family["negative"] == family["zero"] == 0
            and math.isfinite(family["minimum"])
            and family["minimum"] > 0
            and math.isfinite(family["maximum"])
            and family["maximum"] >= family["minimum"],
            "positive_observed_objective_terms",
        )
    return {
        "parent": parent,
        "alias": audit.c1.alias(parent),
        "source_sha256": item["source_sha256"],
        "variables": representation["variables"],
        "binary_variables": representation["binary_variables"],
        "continuous_variables": representation["continuous_variables"],
        "general_integer_variables": representation["integer_variables"],
        "constraints": representation["constraints"],
        "nonzeros_from_existing_numeric_receipt": representation["nonzeros"],
        "objective_constant": item["objective"]["constant"],
        "source_sense": item["source_sense"],
        "effective_sense": "MINIMIZE",
        "positive_lexical_objective_terms_observed": True,
        "full_economic_constraint_mapping_qualified": False,
        "all_54_lp_semantics_qualified": False,
    }


def build():
    request = json.loads((ROOT / REQUEST).read_bytes())
    audit.require(request == context.prepare(), "frozen_request_reproducibility")
    value = context.review((ROOT / RECEIPT).read_bytes(), RECEIPT_SHA, request)
    original, _, chains, _ = audit.build()
    package = audit.c1.read_package(ROOT / "docs/evidence/pr80-job3503-return.json")
    audit.c1.validate(package)
    observations = json.loads(package["members"]["numeric/numeric.json"]["text"])[
        "parents"
    ]
    training = [
        reconcile_training(
            value["training_reports"][chain["cohort"]],
            request["models"][chain["cohort"]],
            chain,
        )
        for chain in chains
    ]
    models = [
        reconcile_model(parent, item, observations[parent])
        for parent, item in sorted(value["representative_models"].items())
    ]
    trace = audit.warmstart_trace()
    report = {
        "protocol_id": PROTOCOL,
        "state": "audit_complete_with_explicit_limitations",
        "source_receipt_sha256": RECEIPT_SHA,
        "parent_population": original["population"],
        "admitted_numeric_parents_reconciled": original["numerically_passed_parents"],
        "partition_counts": original["partition_counts"],
        "frozen_forwards_reconciled": original["frozen_forwards_reconciled"],
        "training_report_chains_reconciled": len(training),
        "representative_lp_structures_reconciled": len(models),
        "existing_easy_warmstart_bindings_reconciled": len(trace),
        "required_effective_sense": "MINIMIZE",
        "objective_policy": "author_approved_cost_minimization_correction_not_max_equivalence",
        "historical_fit_independently_replayed": False,
        "full_benchmark_formulation_semantics_qualified": False,
        "new_comparison_admitted": False,
        "resource_budget_approved": False,
        "raw_receipt_flags_rewritten": False,
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "submissions_added": 0,
        "allowed_claims": [
            "54_selected_parent_identities_partitions_and_existing_numeric_checks",
            "20_existing_confusion_matrices_and_recomputed_micro_parent_macro_metrics",
            "two_frozen_training_reports_attest_train_only_prenorm_not_fit_replay",
            "two_representative_lp_dimensions_match_existing_numeric_receipts",
            "six_easy_existing_starts_reconciled_not_medium_start_qualification",
        ],
        "not_qualified": [
            "all_54_economic_variable_constraint_mapping_and_units",
            "historically_untouched_test_or_independent_generalization",
            "independent_historical_preprocessing_fit_replay",
            "independent_probability_based_auc_or_calibration_rescoring",
            "historical_end_to_end_speedup_or_consistent_gnn_superiority",
            "hard_maximize_runtime_claim_independently_verified",
        ],
        "remaining_execution_gates": [
            "document_exact_source_formulation_mapping_for_intended_comparison",
            "bind_medium_partial_starts_and_preparation_cost_measurements",
            "freeze_complete_prospective_cost_resource_manifest",
            "obtain_separate_exact_PR86_PR87_execution_budget_approval",
        ],
        "lp_matching": "same_support_cardinality_and_positive_count_not_necessarily_same_variable_ids",
    }
    return report, training, models


def produce(output):
    report, training, models = build()
    output.mkdir(parents=True, exist_ok=False)
    audit.inference.legacy.write(output / "review.json", report)
    audit.c1.write_csv(output / "training_reports.csv", training)
    audit.c1.write_csv(output / "representative_models.csv", models)
    inputs = [RECEIPT, REQUEST, "docs/evidence/e0/pr85/manifest.json"]
    audit.inference.legacy.write(
        output / "manifest.json",
        {
            "protocol_id": PROTOCOL,
            "files": {
                p.name: context.digest(p.read_bytes()) for p in sorted(output.iterdir())
            },
            "source_receipts_sha256_raw": {
                name: context.digest((ROOT / name).read_bytes()) for name in inputs
            },
            "reviewer_source_sha256_lf": context.digest(
                Path(__file__).read_bytes().replace(b"\r\n", b"\n")
            ),
            "raw_receipts_normalized": False,
        },
    )
    print(
        json.dumps(
            {
                "state": report["state"],
                "numeric_parents": 54,
                "new_comparison_admitted": False,
                "output": str(output),
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    produce(parser.parse_args().output)


if __name__ == "__main__":
    main()
