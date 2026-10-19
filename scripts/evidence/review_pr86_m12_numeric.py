"""Pinned M12 six-vector review and author-approved final-nine boundary."""

import argparse
import json
import math
from pathlib import Path

import audit_pr86_wave61_numeric as audit

q = audit.q
SHA = "c34d043463cb4f3e6ea389ac00b96b779b4a0b23e5c5cf62bda404b60047e7a2"
COLLECTOR = "3a2e3bfbc9fb8eb0341603d20f6593ad1bf6a416"
AUDITOR = "5b463d2e8b3a95941c0e42f208954dbe95d47e2404f5d9777b89b9920f97f247"
DEST = q.ROOT / "docs/evidence/pr86/m12-numeric-c34d043463cb"
AUTHOR_DECISION = "continue_final_nine_with_explicit_M12_tolerance_limitation_20261018"


def review(raw):
    q.require(q.digest(raw) == SHA, "m12_numeric_hash")
    audit.validate_numeric(raw, SHA, COLLECTOR)
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    q.require(value["collector_source_sha256_lf"] == AUDITOR, "pinned_auditor")
    rows = []
    for solution in value["solutions"]:
        diag = solution["diagnostics"]
        stored, rounded = diag["stored"], diag["rounded_in_memory_only"]
        gnn = solution["cell_id"].endswith("-M2")
        q.require(stored["valid"] is True, "stored_tolerance_feasibility")
        q.require(
            rounded["valid"] is gnn
            and rounded["max_integrality_residual"] == 0
            and diag["integer_values_changed_by_rounding"] == (0 if gnn else 1),
            "observed_method_specific_rounding",
        )
        if gnn:
            q.require(
                stored["max_integrality_residual"]
                == stored["max_row_residual"]
                == rounded["max_row_residual"]
                == 0,
                "gnn_zero_observed_residuals",
            )
        else:
            q.require(
                rounded["checks"]
                == {
                    "bounds": True,
                    "integrality": True,
                    "objective": True,
                    "rows": False,
                }
                and math.isclose(
                    rounded["max_row_residual"], 4.16587e-5, rel_tol=1e-12
                ),
                "control_original_unit_rounding_failure",
            )
        for checked in (stored, rounded):
            q.require(
                checked["extended_precision"]["exact_arithmetic_certificate"] is False
                and checked["rows_above_1e_minus6_after_row_normalization"] == 0,
                "diagnostic_not_certificate",
            )
            for metric in ("recomputed_objective", "max_row_residual"):
                q.require(
                    math.isclose(
                        checked[metric],
                        checked["extended_precision"][metric],
                        rel_tol=1e-8,
                        abs_tol=1e-10,
                    ),
                    "extended_precision_parity",
                )
        rows.append(
            {
                "cell_id": solution["cell_id"],
                "method": solution["cell_id"].rsplit("-", 1)[1],
                "reported_primal": solution["reported_primal"],
                "reported_dual": solution["reported_dual"],
                "stored_max_integrality_residual": stored["max_integrality_residual"],
                "stored_max_row_residual": stored["max_row_residual"],
                "integer_values_changed_by_rounding": diag[
                    "integer_values_changed_by_rounding"
                ],
                "rounded_original_unit_feasible": rounded["valid"],
                "rounded_max_row_residual": rounded["max_row_residual"],
                "rounded_residual_over_existing_tolerance": rounded["max_row_residual"]
                / stored["feasibility_tolerance"],
                "objective_change_after_rounding": diag[
                    "rounded_objective_minus_stored_objective"
                ],
                "exact_optimality_certified": False,
                "private_solution_hash_is_historical_seal": False,
            }
        )
    return rows, {
        "protocol_id": "pr86_m12_numeric_review_v1",
        "numeric_audit_sha256": SHA,
        "wave_return_sha256": audit.SHA,
        "collector_source_commit": COLLECTOR,
        "stored_vectors_within_original_tolerances": 6,
        "gnn_vectors_with_zero_observed_integrality_and_row_residuals": 4,
        "gnn_rounded_vectors_passing_original_unit_rows": 4,
        "control_rounded_vectors_violating_original_unit_rows": 2,
        "cause_of_cross_run_discrepancy_proven": False,
        "exact_optimality_certified": False,
        "main_performance_promotion": False,
        "diagnostic_summary_eligible": True,
        "original_receipts_and_flags_unchanged": True,
        "author_decision": AUTHOR_DECISION,
        "continuation_scope": "only_final_original_nine_unchanged_protocol_no_retry",
        "continuation_authorized_by_author_not_by_raw_receipt": True,
        "optimization_runs_added": 0,
        "scientific_reporting_eligible": False,
    }


def campaign(wave_raw=None, numeric_raw=None):
    wave_raw = (
        q.read(audit.review.DEST / "public_return.json")
        if wave_raw is None
        else wave_raw
    )
    numeric_raw = (
        q.read(DEST / "numeric_audit.json") if numeric_raw is None else numeric_raw
    )
    _, numeric = review(numeric_raw)
    rows, before = audit.review.review(wave_raw)
    q.require(
        before["completed_cells"] == 201
        and len(before["new_parent_cross_run_findings"]) == 8,
        "reviewed_201_prefix",
    )
    for row in rows:
        if row["alias"] == "M12":
            row["numerical_scope"] = (
                "M12_tolerance_sensitive_no_exact_optimality_or_certified_speedup"
            )
    return rows, {
        "input_return_sha256": before["input_return_sha256"],
        "completed_cells": 201,
        "completed_groups": 67,
        "remaining_cells": 9,
        "remaining_groups": 3,
        "completed_counts_scope": before["completed_counts_scope"],
        "scoped_review_non_M4_M12_cells": 168,
        "M4_sensitive_cells": 21,
        "M12_sensitive_cells": 12,
        "M12_stored_vectors_audited": 6,
        "numeric_audits_sha256": {"M4": before["numeric_audit_sha256"], "M12": SHA},
        "author_decisions": {"M4": before["author_decision"], "M12": AUTHOR_DECISION},
        "original_cross_run_screen_findings_preserved": before["cross_run_findings"],
        "final_original_nine_continuation_review_passed": numeric[
            "continuation_authorized_by_author_not_by_raw_receipt"
        ],
        "M4_exact_optimality_or_speedup_qualified": False,
        "M12_exact_optimality_or_speedup_qualified": False,
        "whole_job_cold_cost_qualified": False,
        "original_receipts_and_flags_unchanged": True,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
    }


def publish(directory):
    rows, summary = review(q.read(DEST / "numeric_audit.json"))
    ledger, inventory = campaign()
    outputs = {
        "diagnostics.csv": audit.old.f0.csv_bytes(rows),
        "review.json": q.encoded(summary),
        "campaign_results.csv": audit.old.f0.csv_bytes(ledger),
        "campaign_inventory.json": q.encoded(inventory),
    }
    outputs["manifest.json"] = q.encoded(
        {
            "input_sha256": [SHA, *inventory["input_return_sha256"]],
            "outputs": {k: q.digest(v) for k, v in outputs.items()},
        }
    )
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        path = directory / name
        if path.exists():
            q.require(q.read(path) == raw, "preserve_output")
        else:
            with path.open("xb") as stream:
                stream.write(raw)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(publish(parser.parse_args().output), indent=2))
