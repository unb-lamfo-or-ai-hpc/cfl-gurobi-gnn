"""Read-only continuation accounting; every runtime is mocked, never licensed."""

import copy
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import pr78_medium_continuation_plan as plan  # noqa: E402


def returned(parent):
    easy = parent == "easy"
    return {
        "parent": parent,
        "accounting": {"job_id": "3489" if easy else "3490"},
        "operator_plan_sha256": plan.OPERATOR_PLAN,
        "operator_approval_sha256": plan.OPERATOR_APPROVAL,
        "matrix_approval_sha256": plan.MATRIX_APPROVAL,
        "matrix_package_sha256": plan.PACKAGES[parent],
        "parent_evidence_state": "validated",
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
        "complete_parent": easy,
        "exact_optimization_call_count": 5 if easy else None,
        "completed_attempts_observed": 5 if easy else 1,
        "ready_for_independent_review": easy,
        "pause_remaining_matrix": not easy,
        "workflow_stop_present": not easy,
    }


class ContinuationTests(unittest.TestCase):
    def enter_context(self, context):
        # unittest.TestCase.enterContext is unavailable on CI Python 3.10.
        value = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        return value

    def setUp(self):
        self.returns = {parent: returned(parent) for parent in ("easy", "medium")}
        self.report = {
            "attempt_receipt_sha256": {plan.INTERRUPTED: "a" * 64},
            "stop_code": "memory_observation_lost",
        }
        self.validator = self.enter_context(
            patch.object(
                plan.historical,
                "validate_return",
                side_effect=lambda directory, sha: self.returns[str(directory)],
            )
        )
        self.enter_context(
            patch.object(plan.historical, "clean_accounting", return_value=True)
        )
        self.record = {"easy_review_sha256": plan.EASY_REVIEW}
        self.loader = self.enter_context(
            patch.object(plan.historical, "load", side_effect=lambda _: self.record)
        )
        self.package = self.enter_context(
            patch.object(
                plan.historical.matrix,
                "validate_package",
                side_effect=lambda *_: self.report,
            )
        )

    def compile(self, scope="full-medium"):
        return plan.compile_plan("a" * 40, "easy", "medium", scope)

    def test_exact_prior_returns_and_nested_package_are_required(self):
        value = self.compile()
        self.assertEqual(self.validator.call_count, 2)
        self.validator.assert_any_call("easy", plan.RETURNS["easy"])
        self.validator.assert_any_call("medium", plan.RETURNS["medium"])
        self.package.assert_called_once_with(
            Path("medium/matrix.tar.gz"), plan.PACKAGES["medium"]
        )
        self.assertIsNone(value["predecessor"]["medium_exact_optimization_calls"])
        self.assertEqual(value["predecessor"]["medium_reserved_optimization_slots"], 1)

    def test_full_medium_requires_explicit_new_budget_and_never_repeats_easy(self):
        value = self.compile()
        self.assertEqual([r["threads"] for r in value["attempts"]], [16, 8, 2, 1, 4])
        self.assertTrue(
            all(r["attempt_id"].startswith("medium-") for r in value["attempts"])
        )
        budget = value["budget"]
        self.assertEqual(budget["remaining_original_submission_slots"], 0)
        self.assertEqual(budget["proposed_cumulative_submission_ceiling"], 3)
        self.assertEqual(budget["proposed_cumulative_optimization_slot_ceiling"], 11)
        self.assertEqual(budget["proposed_cumulative_solver_seconds_ceiling"], 39600)
        self.assertEqual(budget["additional_solver_seconds_required"], 3600)
        self.assertEqual(budget["additional_optimization_slots_required"], 1)
        self.assertEqual(budget["additional_submission_slots_required"], 1)
        self.assertEqual(budget["proposed_new_wall_seconds"], 19800)
        self.assertTrue(value["matrix_complete_if_all_new_attempts_validate"])

    def test_unattempted_only_does_not_claim_a_complete_matrix(self):
        value = self.compile("unattempted-only")
        self.assertEqual([r["threads"] for r in value["attempts"]], [8, 2, 1, 4])
        self.assertEqual(
            [r["within_parent_order"] for r in value["attempts"]], [1, 2, 3, 4]
        )
        self.assertEqual(value["unresolved_attempts_after_success"], [plan.INTERRUPTED])
        self.assertFalse(value["matrix_complete_if_all_new_attempts_validate"])
        self.assertFalse(value["interrupted_attempt_reexecution_proposed"])
        self.assertEqual(value["budget"]["proposed_new_wall_seconds"], 16020)
        self.assertEqual(value["budget"]["additional_submission_slots_required"], 1)
        self.assertEqual(value["budget"]["additional_optimization_slots_required"], 0)
        self.assertEqual(value["budget"]["additional_solver_seconds_required"], 0)

    def test_unchanged_resource_and_model_contract(self):
        value = self.compile()
        self.assertEqual(value["memory_policy"], plan.successor.memory.POLICY)
        self.assertEqual(value["scheduler"], plan.historical.PROFILE)
        original = plan.contract.compile_proposal()["attempts"]
        self.assertEqual(
            value["attempts"],
            [r for r in original if r["attempt_id"].startswith("medium-")],
        )
        self.assertEqual(value["child_deadline_seconds"], 3780)

    def test_false_gates_and_zero_actions_are_not_inferred_from_historical_approval(
        self,
    ):
        value = self.compile()
        for name in (
            "execution_enabled",
            "scheduler_adapter_implemented",
            "resource_budget_approved",
            "exact_head_ci_reviewed",
            "automatic_retry",
            "raw_logs_included",
            "scientific_reporting_eligible",
        ):
            self.assertIs(value[name], False)
        for name in (
            "optimization_runs_added",
            "submissions_added",
            "scheduler_queries",
        ):
            self.assertEqual(value[name], 0)

    def test_every_top_level_mutation_rejected_even_if_rehashed(self):
        value = self.compile()
        for key in value:
            with self.subTest(key=key):
                changed = copy.deepcopy(value)
                changed[key] = None
                recomputed_sha = plan.contract.sha(
                    plan.contract.encoded(
                        {
                            k: v
                            for k, v in changed.items()
                            if k != "continuation_plan_sha256"
                        }
                    )
                )
                if key != "continuation_plan_sha256":
                    changed["continuation_plan_sha256"] = recomputed_sha
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    plan.validate_plan(changed, "easy", "medium")

    def test_boolean_numeric_extra_keys_and_budget_tampering_rejected(self):
        original = self.compile()
        changes = []
        for field, value in (
            ("schema_version", True),
            ("concurrent_attempts", 1.0),
            ("resource_budget_approved", True),
            ("extra", "not_allowed"),
        ):
            changed = copy.deepcopy(original)
            changed[field] = value
            changes.append(changed)
        changed = copy.deepcopy(original)
        changed["budget"]["prior_optimization_slots_conservatively_reserved"] = 5
        changes.append(changed)
        changed = copy.deepcopy(original)
        changed["attempts"].reverse()
        changes.append(changed)
        for value in changes:
            with self.assertRaises(ValueError):
                plan.validate_plan(value, "easy", "medium")

    def test_plan_roundtrip_and_revalidation_of_evidence(self):
        value = self.compile()
        decoded = plan.old.strict_payload(plan.contract.encoded(value))
        self.assertEqual(plan.validate_plan(decoded, "easy", "medium"), value)
        self.validator.side_effect = ValueError("bad_hash")
        with self.assertRaises(ValueError):
            plan.validate_plan(decoded, "easy", "medium")

    def test_changed_hash_and_scope_fail_closed(self):
        self.returns["medium"]["matrix_package_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            self.compile()
        with self.assertRaises(ValueError):
            self.compile("easy")
        with self.assertRaises(ValueError):
            plan.compile_plan("not_sha", "easy", "medium", "full-medium")

    def test_historical_unknown_count_cannot_be_promoted_to_zero_or_one(self):
        for count in (0, 1, 5):
            self.returns["medium"]["exact_optimization_call_count"] = count
            with self.assertRaises(ValueError):
                self.compile()

    def test_missing_or_promoted_historical_evidence_rejected(self):
        original = copy.deepcopy(self.returns)
        for parent, field, value in (
            ("easy", "complete_parent", False),
            ("easy", "exact_optimization_call_count", 4),
            ("easy", "ready_for_independent_review", False),
            ("easy", "pause_remaining_matrix", True),
            ("medium", "complete_parent", True),
            ("medium", "completed_attempts_observed", 2),
            ("medium", "workflow_stop_present", False),
            ("medium", "pause_remaining_matrix", False),
            ("medium", "scientific_reporting_eligible", True),
            ("medium", "raw_logs_included", True),
        ):
            self.returns = copy.deepcopy(original)
            self.returns[parent][field] = value
            with (
                self.subTest(parent=parent, field=field),
                self.assertRaises(ValueError),
            ):
                self.compile()

    def test_wrong_interrupted_attempt_or_stop_rejected(self):
        for report in (
            {"attempt_receipt_sha256": {}, "stop_code": "memory_observation_lost"},
            {
                "attempt_receipt_sha256": {"medium-seed42-threads8": "a" * 64},
                "stop_code": "memory_observation_lost",
            },
            {"attempt_receipt_sha256": {plan.INTERRUPTED: "a" * 64}, "stop_code": None},
        ):
            self.report = report
            with self.assertRaises(ValueError):
                self.compile()

    def test_missing_easy_review_rejected(self):
        self.record["easy_review_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.compile()

    def test_preview_cli_requires_explicit_scope_and_has_no_write_or_submit(self):
        with (
            patch.object(plan.historical.site, "source_head", return_value="a" * 40),
            patch.object(
                plan.historical.site,
                "command",
                side_effect=AssertionError("no scheduler"),
            ),
            patch.object(
                plan.historical, "submit", side_effect=AssertionError("no submit")
            ),
            patch.object(
                plan.old, "write_json", side_effect=AssertionError("no write")
            ),
            patch.object(
                plan.successor.adapter.screen,
                "licensed_runtime",
                side_effect=AssertionError("no solver"),
            ),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            plan.main(
                [
                    "preview",
                    "--scope",
                    "full-medium",
                    "--easy-return",
                    "easy",
                    "--medium-return",
                    "medium",
                ]
            )
            self.assertFalse(
                plan.old.strict_payload(stdout.getvalue().encode())["execution_enabled"]
            )
            with self.assertRaises(ValueError):
                plan.main(
                    ["preview", "--easy-return", "easy", "--medium-return", "medium"]
                )

    def test_validate_cli_has_no_network_or_git_calls(self):
        value = self.compile()
        self.loader.side_effect = lambda path: (
            value if str(path) == "proposal.json" else self.record
        )
        with (
            patch.object(
                plan.historical.site,
                "command",
                side_effect=AssertionError("no command"),
            ),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            plan.main(
                [
                    "validate",
                    "--plan",
                    "proposal.json",
                    "--easy-return",
                    "easy",
                    "--medium-return",
                    "medium",
                ]
            )
        self.assertEqual(plan.old.strict_payload(stdout.getvalue().encode()), value)

    def test_dependencies_include_frozen_validator_and_qualified_executor(self):
        value = self.compile()
        for name in (
            "paired_matrix_workflow_v3.py",
            "paired_matrix_executor_v2.py",
            "paired_matrix_executor_v3.py",
            "pr78_medium_continuation_plan.py",
            "paired_memory_runtime_v2.py",
        ):
            self.assertIn(name, value["dependency_sha256"])
        self.assertEqual(
            value["runtime_protocol"], "paired_matrix_isolated_executor_v3"
        )


if __name__ == "__main__":
    unittest.main()
