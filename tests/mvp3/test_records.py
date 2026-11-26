"""Synthetic evidence rejects leakage, censoring substitution and broken audits."""

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fixtures import (  # noqa: E402
    audit,
    binding,
    bundle,
    event,
    label,
    quantity,
    root,
    run,
    start,
    target,
)

from cfl_gnn.mvp3.contract import ContractError, digest  # noqa: E402
from cfl_gnn.mvp3.records import (  # noqa: E402
    paired_time_factor,
    relative_gap,
    run_identity,
    validate_record,
    validate_records,
)


class ObservationTests(unittest.TestCase):
    def test_valid_run_root_label_start_event_target_and_disposition(self):
        data = bundle()
        preparation = run(stage="root_relaxation")
        preparation["outcome"] = "feature_captured"
        incumbent = run(stage="incumbent")
        evaluation = run()
        observation = event(evaluation)
        disposition = binding(run("R"), "disposition")
        disposition.update(
            outcome="infrastructure_interruption",
            reason="synthetic interrupted process",
            preserved_partial_artifacts=[],
        )
        records = [
            preparation,
            root(preparation),
            incumbent,
            label(incumbent, "test"),
            evaluation,
            start(evaluation),
            observation,
            target(evaluation, observation),
        ]
        self.assertEqual(validate_records(records, data)["runs"], 3)
        validate_record(disposition, data)

    def test_unknown_fields_versions_nan_infinity_and_bool_numbers_fail(self):
        source = run()
        changes = [
            lambda r: r.update(unknown="field"),
            lambda r: r.update(schema_version="mvp2"),
            lambda r: r["native_Work"].update(value=float("nan")),
            lambda r: r["native_Work"].update(value=float("inf")),
            lambda r: r["native_Work"].update(value=True),
        ]
        for change in changes:
            record = copy.deepcopy(source)
            change(record)
            with self.assertRaises(ContractError):
                validate_record(record, bundle())

    def test_missing_measurement_is_null_with_reason_not_zero(self):
        record = run()
        record["supervision"]["peak_job_bytes"] = quantity(None, "sampler_unavailable")
        validate_record(record, bundle())
        for bad in (quantity(None), quantity(None, " "), quantity(0, "not_sampled")):
            record["supervision"]["peak_job_bytes"] = bad
            with self.assertRaises(ContractError):
                validate_record(record, bundle())

    def test_hash_and_attempt_whitespace_cannot_enter_immutable_keys(self):
        for field in ("source_commit", "environment_sha256", "attempt"):
            record = run()
            if field == "attempt":
                record["key"][field] += "\n"
            else:
                record[field] += "\n"
            record["run_sha256"] = run_identity(record)
            with self.subTest(field=field), self.assertRaises(ContractError):
                validate_record(record, bundle())

    def test_primary_parameter_resource_and_default_reference_drift_fail(self):
        for mutation in (
            "focus",
            "threads",
            "memory",
            "defaults",
            "input",
            "version",
            "extra_parameter",
        ):
            record = run()
            if mutation == "focus":
                record["effective_parameters"]["MIPFocus"] = 1
            elif mutation == "threads":
                record["effective_parameters"]["Threads"] = 32
            elif mutation == "memory":
                record["resources"]["memory_GiB"] = 384
            elif mutation == "defaults":
                record["native_defaults"]["Cuts"] = 0
            elif mutation == "input":
                record["input_sha256"] = "0" * 64
            elif mutation == "version":
                record["solver_version"] = "13.0.3"
            else:
                record["effective_parameters"]["Cuts"] = 0
            record["run_sha256"] = run_identity(record)
            with self.subTest(mutation=mutation), self.assertRaises(ContractError):
                validate_record(record, bundle())

    def test_heldout_roles_and_method_stage_are_enforced(self):
        training = next(
            row for row in bundle()["parents"]["parents"] if row["role"] == "train"
        )
        with self.assertRaises(ContractError):
            validate_record(run(parent_id=training["original_id"]), bundle())
        record = run(stage="incumbent")
        record["key"]["method"] = "B"
        record["run_sha256"] = run_identity(record)
        with self.assertRaises(ContractError):
            validate_record(record, bundle())

    def test_native_float_parameter_spelling_is_accepted_but_bool_is_not(self):
        record = run(stage="root_relaxation")
        record["effective_parameters"].update(TimeLimit=28800.0, Heuristics=0.0)
        record["run_sha256"] = run_identity(record)
        validate_record(record, bundle())
        record["effective_parameters"]["Heuristics"] = False
        record["run_sha256"] = run_identity(record)
        with self.assertRaises(ContractError):
            validate_record(record, bundle())

    def test_partial_root_cannot_be_a_qualified_feature(self):
        source = run(stage="root_relaxation")
        record = root(source)
        record["captured_count"] = 19
        with self.assertRaises(ContractError):
            validate_record(record, bundle())

    def test_pre_cut_claim_requires_actual_first_root_event(self):
        source = run(stage="root_relaxation")
        record = root(source)
        record["event"]["ordinal"] = 2
        with self.assertRaises(ContractError):
            validate_record(record, bundle())
        record["event"].update(cut_state="later_cut_pass", cut_pass=1)
        validate_record(record, bundle())

    def test_root_and_label_provenance_cannot_be_interchanged(self):
        source = run(stage="incumbent")
        record = root(source)
        with self.assertRaises(ContractError):
            validate_record(record, bundle())
        source = run(stage="root_relaxation")
        with self.assertRaises(ContractError):
            validate_record(label(source, "test"), bundle())

    def test_hard_labels_remain_transfer_only_and_benders_requires_separate_evidence(
        self,
    ):
        source = run(stage="incumbent", parent_id="CFL_hard_instance_0")
        record = label(source, "transfer_only")
        validate_record(record, bundle())
        record["admissible_primary_label"] = True
        with self.assertRaises(ContractError):
            validate_record(record, bundle())
        record["admissible_primary_label"] = False
        record["origin"] = "BENDERS"
        with self.assertRaises(ContractError):
            validate_record(record, bundle())
        record.update(
            conditional_release_sha256="a" * 64, equivalence_audit_sha256="b" * 64
        )
        validate_record(record, bundle())

    def test_intermediate_gap_is_retained_but_not_admitted_to_primary_labels(self):
        source = run(stage="incumbent")
        record = label(source, "test")
        record.update(gap=0.2, tier="intermediate", admissible_primary_label=False)
        validate_record(record, bundle())
        record["admissible_primary_label"] = True
        with self.assertRaises(ContractError):
            validate_record(record, bundle())

    def test_start_independence_cap_bounds_and_undefined_coordinates(self):
        for method in "BRG":
            validate_record(start(run(method)), bundle())
        source = run("R")
        changes = [
            lambda s: s.update(predictor_sha256="a" * 64),
            lambda s: s.update(unselected_coordinates="ZERO"),
            lambda s: s.update(original_model_preserved=False),
            lambda s: s["support"][0].update(lower_bound=1),
            lambda s: s["support"][0].update(value=True),
            lambda s: s["support"][1].update(variable_name="x0"),
        ]
        for change in changes:
            record = start(source)
            change(record)
            with self.assertRaises(ContractError):
                validate_record(record, bundle())
        with self.assertRaises(ContractError):
            validate_record(start(source, size=3), bundle())

    def test_R_G_support_need_not_be_matched(self):
        relaxation = start(run("R"), size=1)
        guidance = start(run("G"), size=2)
        validate_record(relaxation, bundle())
        validate_record(guidance, bundle())

    def test_audit_must_bind_exact_model_vector_and_explicit_residuals(self):
        source = run()
        for change in ("model", "vector", "residual", "missing"):
            record = event(source)
            if change in ("model", "vector"):
                record["candidate_audit"][f"{change}_sha256"] = "a" * 64
            elif change == "residual":
                record["candidate_audit"]["row_max_violation"] = quantity(0.1)
            else:
                record["candidate_audit"]["integrality_max_violation"] = quantity(
                    None, "not_audited"
                )
            with self.subTest(change=change), self.assertRaises(ContractError):
                validate_record(record, bundle())

    def test_run_attempt_and_vector_order_links_are_checked(self):
        source = run()
        record = event(source)
        record["key"]["attempt"] = "different-attempt"
        with self.assertRaises(ContractError):
            validate_records([source, record], bundle())
        other = copy.deepcopy(source)
        other["environment_sha256"] = "a" * 64
        other["run_sha256"] = run_identity(other)
        with self.assertRaisesRegex(ContractError, "Attempt key reused"):
            validate_records([source, other], bundle())
        record = start(source)
        record["variable_order_sha256"] = "a" * 64
        with self.assertRaises(ContractError):
            validate_records([source, record], bundle())

    def test_audit_policy_cannot_change_between_run_and_candidate(self):
        source = run()
        record = event(source)
        record["candidate_audit"]["tolerances"]["row"] = 1
        with self.assertRaisesRegex(ContractError, "audit policy"):
            validate_records([source, record], bundle())

    def test_early_capture_is_successful_feature_outcome_not_generic_failure(self):
        source = run(stage="root_relaxation")
        artifact = root(source)
        with self.assertRaises(ContractError):
            validate_records([source, artifact], bundle())
        source["outcome"] = "feature_captured"
        source["native_status"] = quantity("INTERRUPTED")
        validate_records([source, artifact], bundle())

    def test_final_audit_does_not_qualify_another_intermediate_vector(self):
        source = run()
        observation = event(source)
        observation["candidate_vector_sha256"] = digest([0] * 20)
        record = target(source, observation)
        with self.assertRaises(ContractError):
            validate_records([source, observation, record], bundle())

    def test_label_must_match_audited_final_incumbent(self):
        source = run(stage="incumbent")
        record = label(source, "test")
        record["vector_sha256"] = "a" * 64
        record["audit"] = audit(source["model_sha256"], record["vector_sha256"])
        with self.assertRaisesRegex(ContractError, "source incumbent"):
            validate_records([source, record], bundle())

    def test_plan_slot_is_not_an_observation(self):
        with self.assertRaises(ContractError):
            validate_record(bundle()["plan"]["cells"][0], bundle())


class TargetAndPairTests(unittest.TestCase):
    def pair(self, method="B", first=180, second=120):
        comparator, guidance = run(method), run("G")
        ce, ge = event(comparator, first), event(guidance, second)
        return (
            target(comparator, ce),
            target(guidance, ge),
            [comparator, guidance, ce, ge],
        )

    def test_B_G_and_R_G_orientation_and_signed_savings(self):
        for method, time, factor, saving in (("B", 180, 1.5, 60), ("R", 150, 1.25, 30)):
            comparator, guidance, sources = self.pair(method, time)
            result = paired_time_factor(comparator, guidance, bundle(), sources)
            self.assertEqual(
                result,
                {
                    "ratio": factor,
                    "signed_saving_seconds": saving,
                    "eligibility_reason": None,
                },
            )

    def test_zero_time_is_attained_but_numeric_factor_is_ineligible(self):
        comparator, guidance, sources = self.pair(second=0)
        result = paired_time_factor(comparator, guidance, bundle(), sources)
        self.assertEqual(guidance["outcome"], "attained")
        self.assertIsNone(result["ratio"])
        self.assertEqual(result["eligibility_reason"], "nonpositive_observed_time")

    def test_censored_limits_are_never_observed_target_times(self):
        source = run("B")
        source["outcome"] = "time_limit"
        source["final"].update(dual=quantity(16), gap=quantity(0.2))
        record = target(source, outcome="right_censored")
        record["observed_gap"] = quantity(0.2)
        validate_records([source, record], bundle())
        record["attainment_seconds"] = quantity(300)
        with self.assertRaises(ContractError):
            validate_record(record, bundle())

    def test_one_sided_attainment_has_no_numeric_factor(self):
        comparator, guidance, sources = self.pair()
        sources[0]["outcome"] = "time_limit"
        sources[0]["final"].update(dual=quantity(16), gap=quantity(0.2))
        sources[2]["dual"] = quantity(16)
        sources[2]["gap"] = quantity(0.2)
        comparator.update(
            outcome="right_censored",
            attainment_seconds=quantity(None, "time_limit"),
            source_event_sha256=None,
            observed_gap=quantity(0.2),
        )
        result = paired_time_factor(comparator, guidance, bundle(), sources)
        self.assertIsNone(result["ratio"])
        self.assertEqual(result["eligibility_reason"], "no_common_qualified_attainment")

    def test_infrastructure_interruption_is_not_time_limit_censoring(self):
        source = run("B")
        source["outcome"] = "infrastructure_interruption"
        record = target(source, outcome="right_censored")
        record["observed_gap"] = quantity(0.2)
        with self.assertRaisesRegex(ContractError, "recast"):
            validate_records([source, record], bundle())
        record["outcome"] = "infrastructure_interruption"
        validate_records([source, record], bundle())

    def test_censoring_cannot_hide_a_qualified_final_gap(self):
        source = run("B")
        record = target(source, outcome="right_censored")
        record["observed_gap"] = quantity(0.2)
        with self.assertRaisesRegex(ContractError, "qualified final gap"):
            validate_records([source, record], bundle())

    def test_first_qualified_attainment_and_monotone_event_clock(self):
        source = run()
        first, later = event(source, 80), event(source, 120, ordinal=2)
        record = target(source, later)
        with self.assertRaisesRegex(ContractError, "first qualified"):
            validate_records([source, first, later, record], bundle())
        later["elapsed_seconds"] = 79
        with self.assertRaisesRegex(ContractError, "Nonmonotone"):
            validate_records([source, first, later], bundle())

    def test_clock_origin_mismatch_is_rejected(self):
        record = target(run())
        record["clock"]["origin"] = "worker_entry"
        with self.assertRaises(ContractError):
            validate_record(record, bundle())

    def test_different_valid_clocks_are_not_combined(self):
        comparator, guidance = run("B"), run("G")
        ce, ge = event(comparator, 180, name="worker_elapsed"), event(guidance, 120)
        result = paired_time_factor(
            target(comparator, ce),
            target(guidance, ge),
            bundle(),
            [comparator, guidance, ce, ge],
        )
        self.assertEqual(result["eligibility_reason"], "different_clock")

    def test_different_environments_are_not_paired(self):
        comparator, guidance = run("B"), run("G")
        comparator["environment_sha256"] = "a" * 64
        comparator["run_sha256"] = run_identity(comparator)
        ce, ge = event(comparator, 180), event(guidance, 120)
        result = paired_time_factor(
            target(comparator, ce),
            target(guidance, ge),
            bundle(),
            [comparator, guidance, ce, ge],
        )
        self.assertEqual(result["eligibility_reason"], "different_pairing_contract")

    def test_attainment_requires_matching_source_event_and_qualified_audit(self):
        source = run()
        observation = event(source)
        record = target(source, observation)
        with self.assertRaises(ContractError):
            validate_records([source, record], bundle())
        record["attainment_seconds"] = quantity(121)
        with self.assertRaises(ContractError):
            validate_records([source, observation, record], bundle())
        record = target(source, observation)
        record["candidate_audit"]["status"] = "unqualified"
        with self.assertRaises(ContractError):
            validate_record(record, bundle())

    def test_observation_cannot_exceed_its_run_followup(self):
        source = run()
        observation = event(source, 301)
        with self.assertRaises(ContractError):
            validate_records([source, observation], bundle())

    def test_duplicate_and_missing_run_records_fail(self):
        source = run()
        observation = event(source)
        with self.assertRaises(ContractError):
            validate_records([observation], bundle())
        with self.assertRaises(ContractError):
            validate_records([source, observation, observation], bundle())

    def test_zero_primal_and_missing_incumbent_gap_conventions(self):
        self.assertEqual(relative_gap(0, 0), quantity(0))
        self.assertEqual(
            relative_gap(0, 1), quantity(None, "native_infinite_gap_zero_primal")
        )
        self.assertEqual(relative_gap(None, 1), quantity(None, "no_incumbent"))
        self.assertEqual(relative_gap(1, None), quantity(None, "dual_unavailable"))
        self.assertEqual(relative_gap(-10, -11), quantity(0.1))


if __name__ == "__main__":
    unittest.main()
