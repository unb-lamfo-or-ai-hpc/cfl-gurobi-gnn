"""Distinguish canonical PR57 role contracts from stored JSON file digests.

SPDX-License-Identifier: MIT
"""

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr66_thread_pilot as pilot  # noqa: E402
from collect_computational_ledger import digest  # noqa: E402


class RoleContractTests(unittest.TestCase):
    def fixture(self):
        records = []
        for difficulty, size, train, validation in (
            ("easy", 30, 18, 6),
            ("medium", 24, 16, 4),
        ):
            for index in range(size):
                role = (
                    "train"
                    if index < train
                    else "validation"
                    if index < train + validation
                    else "test"
                )
                records.append(
                    {
                        "parent_instance_id": f"CFL_{difficulty}_instance_{index}",
                        "role": role,
                    }
                )
        payload = {
            "schema_version": 1,
            "dataset_variant": "pr57_54_parent_development_v1",
            "records": records,
            "partition_counts": {"train": 34, "validation": 10, "test": 10},
            "graph_authority": "gurobi",
            "label_solver": "gurobi",
            "development_only": True,
            "scientific_reporting_eligible": False,
            "fixture_metadata": "UTF-8 α",
        }
        sha = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        value = {
            **payload,
            "contract_sha256": sha,
            "contract_valid": True,
            "training_ready": True,
            "engineering_smoke_ready": True,
            "held_out_evaluation_ready": True,
        }
        return value, sha

    def resign(self, value):
        ignored = {
            "contract_sha256",
            "contract_valid",
            "training_ready",
            "engineering_smoke_ready",
            "held_out_evaluation_ready",
            "warnings",
            "next_gate",
        }
        value["contract_sha256"] = hashlib.sha256(
            pilot.canonical(
                {key: item for key, item in value.items() if key not in ignored}
            ).encode()
        ).hexdigest()
        return value["contract_sha256"]

    def test_stored_file_hash_is_not_the_canonical_contract_and_freeze_records_both(
        self,
    ):
        value, contract = self.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            role_path = root / "roles.json"
            role_path.write_text(
                json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            file_hash = digest(role_path)
            self.assertNotEqual(file_hash, contract)
            raw = root / "raw"
            config = pilot.strict_json(pilot.BASE_CONFIG)
            _, selected = pilot.draw_pair(
                pilot.roles_from_plan(value),
                config["frozen_optimization_test_parent_ids"],
            )
            for difficulty, parent in selected.items():
                path = raw / f"CFL_{difficulty}_instance/LP/{parent}.lp.gz"
                path.parent.mkdir(parents=True)
                path.write_bytes(b"offline stored LP fixture")
            receipt = pilot.freeze(raw, role_path, None, root / "plan", contract)
            self.assertEqual(receipt["role_plan_sha256"], file_hash)
            self.assertEqual(receipt["role_plan_contract_sha256"], contract)
            self.assertEqual(
                receipt["role_plan_sha256_semantics"], "original_stored_json_bytes"
            )

    def test_reformatting_changes_bytes_not_validated_roles_or_contract(self):
        value, expected = self.fixture()
        pretty = json.dumps(value, indent=2, ensure_ascii=False).encode()
        compact = json.dumps(value, separators=(",", ":")).encode()
        self.assertNotEqual(
            hashlib.sha256(pretty).digest(), hashlib.sha256(compact).digest()
        )
        self.assertEqual(
            pilot.qualify_role_contract(json.loads(pretty), expected), expected
        )
        self.assertEqual(
            pilot.qualify_role_contract(json.loads(compact), expected), expected
        )

    def test_modified_role_with_unchanged_declared_hash_is_rejected(self):
        value, expected = self.fixture()
        value["records"][0]["role"] = "test"
        with self.assertRaisesRegex(ValueError, "contract_hash_mismatch"):
            pilot.qualify_role_contract(value, expected)

    def test_recomputed_changed_contract_cannot_replace_the_expected_pin(self):
        value, expected = self.fixture()
        value["records"][0]["role"] = "test"
        self.resign(value)
        with self.assertRaisesRegex(ValueError, "contract_hash_mismatch"):
            pilot.qualify_role_contract(value, expected)

    def test_duplicate_parent_and_partition_changes_are_not_qualified(self):
        value, _ = self.fixture()
        for change in ("duplicate", "partition"):
            with self.subTest(change=change):
                altered = copy.deepcopy(value)
                if change == "duplicate":
                    altered["records"][1] = altered["records"][0]
                else:
                    altered["partition_counts"]["train"] = 33
                expected = self.resign(altered)
                with self.assertRaisesRegex(ValueError, "cohort_changed"):
                    pilot.qualify_role_contract(altered, expected)

    def test_ready_flags_must_be_true_even_though_outside_the_contract_payload(self):
        value, expected = self.fixture()
        value["training_ready"] = False
        with self.assertRaisesRegex(ValueError, "unqualified_pr57"):
            pilot.qualify_role_contract(value, expected)

    def test_historical_warnings_and_next_gate_are_excluded_like_pr57_validator(self):
        value, expected = self.fixture()
        value.update(warnings=["fixture"], next_gate="fixture")
        self.assertEqual(pilot.qualify_role_contract(value, expected), expected)

    def test_launcher_pins_contract_not_an_unverified_observed_file_hash(self):
        script = (
            pilot.BASE_CONFIG.parents[2]
            / "scripts/slurm/dasci/launch_pr66_thread_screen.sh"
        ).read_text()
        self.assertIn("--expected-role-contract", script)
        self.assertNotIn("--expected-role-sha", script)
        self.assertIn(
            "432a42dab9f49f01a31d7b28f658bd14f7c50450ac2d83d1ae3102bcc12f0d40", script
        )


if __name__ == "__main__":
    unittest.main()
