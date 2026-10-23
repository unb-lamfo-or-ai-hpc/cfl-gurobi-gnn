"""Qualification boundaries, not counts certified from private history.

SPDX-License-Identifier: MIT
"""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr66_reconciliation as recon  # noqa: E402

SHA = "a" * 64


class ReconciliationTests(unittest.TestCase):
    def model(self):
        return {
            "original_lp_sha256": SHA,
            "adapter_source_sha256": SHA,
            "effective_objective_sense": "MINIMIZE",
            "variable_names": ["x", "y"],
            "lb": [0, 0],
            "ub": [1, 2],
            "types": ["B", "C"],
            "objective": [3, 1],
            "objective_constant": 2,
            "constraints": [{"terms": [(0, 1), (1, 1)], "sense": ">", "rhs": 1}],
            "feasibility_tol": 1e-6,
            "integer_tol": 1e-5,
        }

    def test_artifact_aliases_do_not_deduplicate_executions(self):
        rows = [{"artifact_id": x * 64, "report_sha256": SHA} for x in ("b", "c")]
        result = recon.artifact_aliases(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["artifact_ids"]), 2)
        self.assertFalse(result[0]["execution_identity_qualified"])

    def test_duplicate_observation_and_invalid_hash_rejected(self):
        row = {"artifact_id": SHA, "report_sha256": SHA}
        with self.assertRaises(ValueError):
            recon.artifact_aliases([row, row])
        with self.assertRaises(ValueError):
            recon.provenance("not a hash")

    def test_adapter_preserves_unknown_effective_sense_and_execution(self):
        value = {
            "parent": {"source_instance_id": "CFL_easy_instance_1", "sha256": SHA},
            "solve": {},
        }
        row = recon.adapt_parent_report(value, SHA, "gurobi")
        self.assertIsNone(row["effective_objective_sense"])
        self.assertIsNone(row["execution_identity"])
        self.assertIsNone(row["unique_feasible_incumbents"])

    def test_unsupported_legacy_not_silently_counted(self):
        with self.assertRaises(ValueError):
            recon.adapt_parent_report({"execution_time": 100}, SHA, "scip")

    def test_steps_and_shared_attempt_edges_do_not_double_count(self):
        base = {
            "job_id": "1",
            "allocated_cpus": 16,
            "elapsed_seconds": 300,
            "reported_total_cpu_time": "00:05:00",
        }
        jobs = [base, {**base, "job_id": "1.batch"}, {**base, "job_id": "2"}]
        edges = [
            {
                "attempt_id": a,
                "job_id": "1",
                "join_state": "matched",
                "receipt_sha256": SHA,
            }
            for a in ("a", "b")
        ]
        rows = recon.attributed_cost(jobs, edges)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            sum(r["allocated_cpu_hours"] for r in rows if r["attributed_to_cfl"]),
            16 * 300 / 3600,
        )
        self.assertEqual(rows[0]["reported_cpu_hours"], 300 / 3600)
        self.assertFalse(rows[1]["attributed_to_cfl"])

    def test_duplicate_jobs_edges_and_missing_matches_rejected(self):
        job = {"job_id": "1", "allocated_cpus": 16, "elapsed_seconds": 300}
        edge = {
            "attempt_id": "a",
            "job_id": "1",
            "join_state": "matched",
            "receipt_sha256": SHA,
        }
        for jobs, edges in (([job, job], []), ([job], [edge, edge]), ([], [edge])):
            with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                recon.attributed_cost(jobs, edges)

    def test_duration_missing_not_zero(self):
        self.assertIsNone(recon.seconds(""))
        self.assertEqual(recon.seconds("1-02:03:04.5"), 93784.5)
        with self.assertRaises(ValueError):
            recon.seconds("01:65:00")

    def test_full_vector_feasibility_objective_and_nonbinary_uniqueness(self):
        model = self.model()
        order = recon.variable_order_sha(model["variable_names"])
        first = recon.audit_vector(model, [1, 0], order)
        second = recon.audit_vector(model, [1, 1], order)
        self.assertTrue(first["feasible_at_declared_tolerances"])
        self.assertEqual(first["objective"], 5)
        self.assertNotEqual(first["full_vector_sha256"], second["full_vector_sha256"])
        self.assertIsNone(first["gap_qualified"])

    def test_constraint_integrality_bounds_checked_without_rounding(self):
        model = self.model()
        order = recon.variable_order_sha(model["variable_names"])
        for values, reason in (
            ([0, 0], "constraints"),
            ([0.5, 1], "integrality"),
            ([1, 3], "bounds"),
        ):
            with self.subTest(values=values):
                result = recon.audit_vector(model, values, order)
                self.assertIn(reason, result["violations"])
                self.assertFalse(result["feasible_at_declared_tolerances"])

    def test_wrong_order_nonfinite_short_and_maximize_rejected(self):
        model = self.model()
        order = recon.variable_order_sha(model["variable_names"])
        for vector, expected in (
            ([1, 0], "b" * 64),
            ([float("nan"), 0], order),
            ([1], order),
        ):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                recon.audit_vector(model, vector, expected)
        model["effective_objective_sense"] = "MAXIMIZE"
        with self.assertRaises(ValueError):
            recon.audit_vector(model, [1, 0], order)

    def test_planned_membership_is_not_actual_consumption(self):
        record = {
            "lineage_source_sha256": SHA,
            "planned_role": "train",
            "parent_role": "train",
            "derivative_id": "d",
        }
        self.assertEqual(
            recon.derivative_usage(record)["fitting_consumption"], "unknown"
        )
        event = {
            "receipt_sha256": SHA,
            "dataset_sha256": SHA,
            "derivative_id": "d",
            "optimizer_updates_observed": 1,
        }
        record["fitting_event"] = event
        self.assertFalse(
            recon.derivative_usage(record)["complete_training_usage_verified"]
        )
        changed = copy.deepcopy(record)
        changed["parent_role"] = "test"
        with self.assertRaises(ValueError):
            recon.derivative_usage(changed)


if __name__ == "__main__":
    unittest.main()
