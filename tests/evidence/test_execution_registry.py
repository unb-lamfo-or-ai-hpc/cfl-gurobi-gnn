"""Synthetic joins plus frozen pilot receipts; no solver or private vectors."""

import copy
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import build_execution_registry as registry  # noqa: E402

SHA = "a" * 64
ACCOUNTING = (
    "JobID|State|ExitCode|Elapsed|ElapsedRaw|TotalCPU|AllocCPUS|ReqMem|MaxRSS\n"
    "3468|COMPLETED|0:0|00:29:54|1794|46:43.115|32|64G|\n"
    "3468.batch|COMPLETED|0:0|00:29:54|1794|00:00.024|32||4208K\n"
    "3468.extern|COMPLETED|0:0|00:29:54|1794|00:00:00|32||0\n"
    "3468.0|COMPLETED|0:0|00:29:54|1794|46:43.090|32||3456600K\n"
).encode()


class RegistryTests(unittest.TestCase):
    def subject(self):
        return {"subject_id": SHA, "report_sha256": "b" * 64}

    def allocation(self):
        return {
            "allocation_observation_id": "c" * 64,
            "accounting_sha256": "d" * 64,
            "cluster": "dgx-dasci",
            "job_id": "3468",
        }

    def claim(self):
        return {
            **self.subject(),
            **{
                k: self.allocation()[k]
                for k in ("accounting_sha256", "cluster", "job_id")
            },
        }

    def observation(self, ref=SHA):
        return {
            "attempt_id": ref,
            "report_sha256": "b" * 64,
            "source_instance_id": "CFL_easy_instance_1",
            "solver": "gurobi",
        }

    def test_no_claim_is_unmatched_not_zero_cost(self):
        value = registry.join_claim(self.subject(), None, [self.allocation()])
        self.assertEqual(value["join_state"], "unmatched")
        self.assertIsNone(value["allocation_observation_id"])

    def test_partial_claim_does_not_match_job_number_alone(self):
        value = registry.join_claim(
            self.subject(),
            {"job_id": "3468", "cluster": "dgx-dasci"},
            [self.allocation()],
        )
        self.assertEqual(value["join_state"], "unmatched")

    def test_explicit_claim_matches_within_snapshot(self):
        value = registry.join_claim(self.subject(), self.claim(), [self.allocation()])
        self.assertEqual(value["join_state"], "matched")
        self.assertEqual(value["allocation_observation_id"], "c" * 64)

    def test_foreign_cluster_snapshot_or_report_is_unmatched(self):
        for key, value in (
            ("cluster", "another-cluster"),
            ("accounting_sha256", "e" * 64),
            ("report_sha256", "f" * 64),
        ):
            with self.subTest(key=key):
                claim = {**self.claim(), key: value}
                self.assertEqual(
                    registry.join_claim(self.subject(), claim, [self.allocation()])[
                        "join_state"
                    ],
                    "unmatched",
                )

    def test_multiple_candidates_remain_ambiguous(self):
        candidates = [
            self.allocation(),
            {**self.allocation(), "allocation_observation_id": "e" * 64},
        ]
        value = registry.join_claim(self.subject(), self.claim(), candidates)
        self.assertEqual(value["join_state"], "ambiguous")
        self.assertIsNone(value["allocation_observation_id"])

    def test_duplicate_allocation_observation_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate_allocation_observation"):
            registry.join_claim(self.subject(), self.claim(), [self.allocation()] * 2)

    def test_step_cannot_be_concrete_allocation(self):
        value = registry.join_claim(
            self.subject(),
            {**self.claim(), "job_id": "3468.batch"},
            [self.allocation()],
        )
        self.assertEqual(value["join_state"], "unmatched")

    def test_equal_report_bytes_are_aliases_not_one_execution(self):
        observations = registry.historical_observations(
            [self.observation(), self.observation("c" * 64)], "d" * 64
        )
        aliases = registry.aliases(observations)
        self.assertEqual(len(observations), 2)
        self.assertEqual(len(aliases), 1)
        self.assertEqual(len(aliases[0]["observation_ids"]), 2)
        self.assertFalse(aliases[0]["execution_equivalence_qualified"])
        self.assertTrue(all(r["execution_id"] is None for r in observations))

    def test_duplicate_observation_invalid_parent_and_private_id_rejected(self):
        for records in (
            [self.observation()] * 2,
            [{**self.observation(), "source_instance_id": "CFL_easy_instance_31"}],
            [self.observation("/home/private")],
        ):
            with self.subTest(records=records), self.assertRaises(ValueError):
                registry.historical_observations(records, SHA)

    def test_parent_accounting_once_not_steps(self):
        value = registry.accounting_projection(ACCOUNTING)
        self.assertEqual(registry.sha(ACCOUNTING), registry.ACCOUNTING_SHA)
        self.assertEqual(value["child_step_rows_not_added"], 3)
        self.assertAlmostEqual(value["allocated_logical_cpu_hours"], 32 * 1794 / 3600)
        self.assertAlmostEqual(value["reported_cpu_hours"], 2803.115 / 3600)
        self.assertFalse(value["globally_unique_allocation_identity_qualified"])
        self.assertFalse(value["phase_costs_qualified"])

    def test_changed_accounting_rejected(self):
        with self.assertRaisesRegex(ValueError, "reviewed_accounting_bytes_changed"):
            registry.accounting_projection(ACCOUNTING + b"\n")

    def test_duplicate_parent_and_wrong_columns_rejected(self):
        for changed in (
            ACCOUNTING.replace(b"JobID|", b"JobIDRaw|"),
            ACCOUNTING.replace(b"3468.batch", b"3468"),
        ):
            with (
                patch.object(registry, "ACCOUNTING_SHA", registry.sha(changed)),
                self.assertRaises(ValueError),
            ):
                registry.accounting_projection(changed)

    def test_real_pilot_ten_explicit_edges_one_allocation(self):
        allocation = registry.accounting_projection(ACCOUNTING)
        attempts, edges = registry.pilot_registry(
            registry.phases.public_receipts(), allocation
        )
        self.assertEqual(len(attempts), 10)
        self.assertEqual(len({a["execution_id"] for a in attempts}), 10)
        self.assertTrue(all(e["join_state"] == "matched" for e in edges))
        self.assertEqual(
            {e["allocation_observation_id"] for e in edges},
            {allocation["allocation_observation_id"]},
        )
        self.assertTrue(all(a["unique_feasible_incumbents"] is None for a in attempts))
        self.assertNotIn("gurobipy", sys.modules)

    def test_changed_execution_binding_rejected(self):
        payloads = copy.copy(registry.phases.public_receipts())
        payloads["pilot_execution_report.json"] = payloads[
            "pilot_execution_report.json"
        ].replace(b'"exit_code": 0', b'"exit_code": 1', 1)
        with self.assertRaisesRegex(ValueError, "explicit_report_binding_changed"):
            registry.pilot_registry(
                payloads, registry.accounting_projection(ACCOUNTING)
            )

    def test_fresh_allowlisted_package_and_input_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            accounting = base / "accounting.txt"
            accounting.write_bytes(ACCOUNTING)
            output = base / "output"
            ledger = (
                "attempt_id,report_sha256,source_instance_id,solver\n"
                + f"{SHA},{'b' * 64},CFL_easy_instance_1,gurobi\n"
            ).encode()
            with patch.object(
                registry,
                "read_package",
                return_value={"ledger/parent_solver_ledger.csv": ledger},
            ):
                value = registry.collect(base / "synthetic-package", accounting, output)
            self.assertEqual(accounting.read_bytes(), ACCOUNTING)
            self.assertEqual(value["summary"]["historical_report_observations"], 1)
            self.assertIsNone(value["complete_historical_compute_cost"])
            self.assertFalse(value["scientific_reporting_eligible"])
            with tarfile.open(output / "execution_registry.tar.gz") as archive:
                self.assertEqual(
                    set(archive.getnames()),
                    {"execution_registry.json", "SHA256SUMS.txt"},
                )
                content = archive.extractfile("execution_registry.json").read()
                self.assertEqual(json.loads(content), value)
                self.assertNotIn(b"/home/", content)
                self.assertNotIn(b"/raid/", content)
            with self.assertRaisesRegex(ValueError, "fresh_output"):
                registry.collect(base / "synthetic-package", accounting, output)

    def test_mutating_accounting_stops_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with (
                patch.object(
                    registry,
                    "bounded_accounting",
                    side_effect=[ACCOUNTING, ACCOUNTING + b"\n"],
                ),
                patch.object(
                    registry,
                    "read_package",
                    return_value={
                        "ledger/parent_solver_ledger.csv": b"attempt_id,report_sha256,source_instance_id,solver\n"
                    },
                ),
                self.assertRaisesRegex(ValueError, "accounting_changed_during_read"),
            ):
                registry.collect(
                    base / "synthetic-package", base / "accounting.txt", base / "output"
                )
            self.assertFalse((base / "output").exists())

    def test_output_under_original_receipts_rejected(self):
        with self.assertRaisesRegex(ValueError, "fresh_output"):
            registry.collect(
                "unused", "unused", registry.phases.EVIDENCE / "new-registry"
            )


if __name__ == "__main__":
    unittest.main()
