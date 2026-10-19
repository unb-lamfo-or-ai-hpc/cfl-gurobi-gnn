"""Review stored M4 diagnostics, not exact optimality or repaired solutions."""

import argparse
import math
from pathlib import Path

import audit_pr86_wave49_numeric as audit
import review_pr86_wave43 as prior

q = audit.q
SHA = "62232bb0347a58f13d659abbdee408d38e6549654a20bdbc70e7e81548600cc8"
COLLECTOR = "13eaff38457fb5c9aba168f4f2959caaa20fe00c"
AUDITOR = "081d5d484aed191bae2740a4dd576791c02e6cc0857adfa48bc4fb3c2fee68a5"
DEST = q.ROOT / "docs/evidence/pr86/m4-numeric-62232bb0347a"
AUTHOR_DECISION = "continue_frozen_matrix_with_explicit_M4_numeric_limitation_20261016"


def review(raw, wave_raw=None):
    q.require(q.digest(raw) == SHA, "m4_numeric_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    q.require(
        value["protocol_id"] == "pr86_wave49_stored_solution_numeric_audit_v1"
        and value["source_commit"] == audit.COMMIT
        and value["collector_source_commit"] == COLLECTOR
        and value["collector_source_sha256_lf"] == AUDITOR
        and value["return_sha256"] == audit.SHA,
        "m4_numeric_identity",
    )
    for key in ("optimization_runs_added", "scheduler_queries", "submissions_added"):
        q.require(type(value[key]) is int and value[key] == 0, "read_only_scope")
    for key in (
        "cause_proven",
        "mathematical_model_or_solver_parameters_changed",
        "rounded_values_persisted_or_used_as_start",
        "raw_logs_or_variable_values_included",
        "remaining_dispatch_admitted",
        "scientific_reporting_eligible",
    ):
        q.require(value[key] is False, "false_diagnostic_gates")
    q.require(
        value["original_solution_hashes_were_not_exported_in_historical_return"] is True
        and value["newly_observed_private_hashes_are_not_historical_seals"] is True,
        "historical_hash_limitation",
    )
    wave = audit.load_wave(
        q.read(audit.DEST / "public_return.json") if wave_raw is None else wave_raw
    )
    observed = audit.records(wave)
    findings = audit.cross_run_findings(observed)
    expected = {v[k] for v in findings for k in ("bound_cell", "candidate_cell")}
    solutions = value["solutions"]
    q.require(
        len(solutions) == len(expected) == 4
        and {s["cell_id"] for s in solutions} == expected,
        "four_numeric_cells",
    )
    model = value["model"]
    q.require(
        model["sha256"] == audit.MODEL
        and all(
            model["mathematical_signature_sha256"] == r["mathematical_signature_sha256"]
            for r in observed
        ),
        "same_model_signature",
    )
    rows = []
    for solution in solutions:
        row = next(r for r in observed if r["cell_id"] == solution["cell_id"])
        child = audit.f0.member(
            wave["returns"][row["group_index"]],
            f"run/attempt-{row['attempt_index']}/child.json",
        )
        q.require(
            solution["child_sha256"] == row["child_sha256"]
            and solution["sealed_log_sha256"] == child["gurobi_log"]["log_sha256"]
            and solution["reported_primal"] == row["primal"]
            and solution["reported_dual"] == row["dual"],
            "numeric_cell_and_sealed_log",
        )
        diagnostics = solution["diagnostics"]
        stored = diagnostics["stored"]
        rounded = diagnostics["rounded_in_memory_only"]
        q.require(
            stored["valid"] is True
            and all(v is True for v in stored["checks"].values())
            and stored["feasibility_tolerance"] == 1e-6
            and stored["integrality_tolerance"] == 1e-5
            and rounded["feasibility_tolerance"] == 1e-6
            and rounded["integrality_tolerance"] == 1e-5,
            "original_tolerances_preserved",
        )
        q.require(
            rounded["valid"] is False
            and rounded["checks"]
            == {"bounds": True, "integrality": True, "objective": True, "rows": False}
            and rounded["max_integrality_residual"] == 0
            and rounded["max_row_residual"] > 1e-6,
            "rounded_row_failure",
        )
        for checked in (stored, rounded):
            extended = checked["extended_precision"]
            q.require(
                checked["row_normalization_is_diagnostic_not_new_acceptance_rule"]
                is True
                and extended["exact_arithmetic_certificate"] is False,
                "diagnostic_not_certificate",
            )
            for metric in ("recomputed_objective", "max_row_residual"):
                q.require(
                    math.isfinite(checked[metric])
                    and math.isfinite(extended[metric])
                    and math.isclose(
                        checked[metric], extended[metric], rel_tol=1e-8, abs_tol=1e-10
                    ),
                    "extended_precision_parity",
                )
        rows.append(
            {
                "cell_id": row["cell_id"],
                "reported_primal": row["primal"],
                "reported_dual": row["dual"],
                "stored_max_integrality_residual": stored["max_integrality_residual"],
                "integer_values_changed_by_rounding": diagnostics[
                    "integer_values_changed_by_rounding"
                ],
                "stored_max_row_residual": stored["max_row_residual"],
                "rounded_max_row_residual": rounded["max_row_residual"],
                "rounded_residual_over_existing_tolerance": rounded["max_row_residual"]
                / stored["feasibility_tolerance"],
                "rounded_max_row_normalized_residual": rounded[
                    "max_row_violation_divided_by_max_abs_row_coefficient"
                ],
                "normalized_rows_above_1e_minus6": rounded[
                    "rows_above_1e_minus6_after_row_normalization"
                ],
                "objective_change_after_rounding": diagnostics[
                    "rounded_objective_minus_stored_objective"
                ],
                "rounded_original_unit_feasible": False,
                "exact_optimality_certified": False,
                "private_solution_hash_is_historical_seal": False,
            }
        )
    return rows, {
        "protocol_id": "pr86_m4_numeric_review_v1",
        "numeric_audit_sha256": SHA,
        "wave_return_sha256": audit.SHA,
        "collector_source_commit": COLLECTOR,
        "stored_vectors_within_original_tolerances": 4,
        "rounded_vectors_violating_original_unit_rows": 4,
        "reported_zero_gap_vector_also_fails_rounding": True,
        "cause_of_cross_run_conflict_proven": False,
        "exact_optimality_certified": False,
        "main_performance_promotion": False,
        "diagnostic_summary_eligible": True,
        "original_receipts_and_flags_unchanged": True,
        "author_decision": AUTHOR_DECISION,
        "continuation_scope": "remaining_original_cells_only_unchanged_protocol_no_retry",
        "remaining_dispatch_admitted_by_diagnostic": False,
        "optimization_runs_added": 0,
    }


def campaign(wave_raw=None, numeric_raw=None):
    old_rows, old = prior.review(q.read(prior.DEST / "public_return.json"))
    wave_raw = (
        q.read(audit.DEST / "public_return.json") if wave_raw is None else wave_raw
    )
    numeric_raw = (
        q.read(DEST / "numeric_audit.json") if numeric_raw is None else numeric_raw
    )
    wave = audit.load_wave(wave_raw)
    _, numeric = review(numeric_raw, wave_raw)
    rows = old_rows + audit.f0.rows_from_returns(
        wave["returns"], {str(j): audit.SHA for j in range(3609, 3615)}
    )
    _, cells = q.first.executor.proposal.build()
    q.require(
        len(rows) == len({r["cell_id"] for r in rows}) == 165
        and {r["cell_id"] for r in rows} == {c["cell_id"] for c in cells[:165]},
        "collected_prefix165",
    )
    for row in rows:
        row["numerical_scope"] = (
            "M4_sensitive_no_optimality_or_speedup_qualification"
            if row["alias"] == "M4"
            else "previous_scoped_review"
        )
    return rows, {
        "input_return_sha256": old["input_return_sha256"] + [audit.SHA],
        "numeric_audit_sha256": numeric["numeric_audit_sha256"],
        "completed_cells": 165,
        "completed_groups": 55,
        "completed_counts_scope": "structurally_collected_not_blanket_scientific_qualification",
        "previously_scoped_reviewed_cells": 147,
        "numerically_sensitive_cells": 18,
        "numerically_sensitive_parent": "CFL_medium_instance_4",
        "remaining_cells": 45,
        "remaining_groups": 15,
        "author_decision": AUTHOR_DECISION,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
    }


def publish(directory):
    rows, summary = review(q.read(DEST / "numeric_audit.json"))
    ledger, inventory = campaign()
    directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "diagnostics.csv": audit.f0.csv_bytes(rows),
        "review.json": q.encoded(summary),
        "campaign_results.csv": audit.f0.csv_bytes(ledger),
        "campaign_inventory.json": q.encoded(inventory),
    }
    for name, raw in outputs.items():
        path = directory / name
        if path.exists():
            q.require(q.read(path) == raw, "preserve_output")
        else:
            with path.open("xb") as stream:
                stream.write(raw)
    audit.emit(
        directory / "manifest.json",
        {"input_sha256": SHA, "outputs": {k: q.digest(v) for k, v in outputs.items()}},
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import json

    print(json.dumps(publish(args.output), indent=2))
