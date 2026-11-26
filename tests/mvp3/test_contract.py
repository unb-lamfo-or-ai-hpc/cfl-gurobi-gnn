"""Offline regressions for frozen identities, partitioning and budget boundaries."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fixtures import bundle  # noqa: E402

from cfl_gnn.mvp3.__main__ import export_bundle  # noqa: E402
from cfl_gnn.mvp3.contract import (  # noqa: E402
    ContractError,
    approved_contract,
    freeze_parents,
    load_bundle,
    load_json,
    summary,
    validate_catalogue,
)


class FrozenPlanTests(unittest.TestCase):
    def test_population_budget_and_stratification(self):
        data = bundle()
        counts = Counter(
            (row["role"], row["family"]) for row in data["parents"]["parents"]
        )
        self.assertEqual(
            counts,
            {
                ("train", "easy"): 21,
                ("train", "medium"): 21,
                ("validation", "easy"): 5,
                ("validation", "medium"): 4,
                ("test", "easy"): 4,
                ("test", "medium"): 5,
                ("transfer_only", "hard"): 6,
            },
        )
        self.assertEqual(
            summary(data)["stage_counts"],
            {"root_relaxation": 66, "incumbent": 66, "evaluation": 45},
        )
        self.assertEqual(
            len({row["original_id"] for row in data["parents"]["parents"]}), 66
        )
        self.assertEqual(177 * 8, data["contract"]["budget"]["maximum_solver_hours"])
        self.assertEqual(
            177 * 12, data["contract"]["budget"]["reserved_solver_job_hours"]
        )

    def test_known_heldout_ids_are_frozen(self):
        rows = bundle()["parents"]["parents"]
        self.assertEqual(
            [row["alias"] for row in rows if row["role"] == "test"],
            ["E14", "E17", "E27", "E29", "M10", "M18", "M21", "M22", "M26"],
        )
        self.assertEqual(
            [row["alias"] for row in rows if row["role"] == "validation"],
            ["E1", "E2", "E6", "E10", "E18", "M0", "M1", "M4", "M29"],
        )
        self.assertEqual(
            [row["alias"] for row in rows if row["role"] == "transfer_only"],
            ["H0", "H5", "H10", "H15", "H20", "H25"],
        )

    def test_partition_is_independent_of_input_iteration_order(self):
        catalogue = copy.deepcopy(bundle()["catalogue"])
        catalogue["parents"].reverse()
        frozen = freeze_parents(catalogue)
        self.assertEqual(frozen["parents"], bundle()["parents"]["parents"])
        self.assertNotEqual(
            frozen["catalogue_sha256"], bundle()["parents"]["catalogue_sha256"]
        )

    def test_missing_duplicate_and_renamed_parents_fail(self):
        for change in ("missing", "duplicate", "alias", "family"):
            with self.subTest(change=change):
                data = copy.deepcopy(bundle()["catalogue"])
                if change == "missing":
                    data["parents"].pop()
                elif change == "duplicate":
                    data["parents"][-1] = copy.deepcopy(data["parents"][0])
                else:
                    data["parents"][0][change] = "other"
                with self.assertRaises(ContractError):
                    freeze_parents(data)

    def test_catalogue_rejects_per_parent_hash_swaps_and_outcome_fields(self):
        for change in ("swap", "outcome"):
            data = copy.deepcopy(bundle()["catalogue"])
            if change == "swap":
                first, second = data["parents"][:2]
                first["stored_sha256"], second["stored_sha256"] = (
                    second["stored_sha256"],
                    first["stored_sha256"],
                )
            else:
                data["parents"][0]["label_gap"] = 0
            with self.assertRaises(ContractError):
                validate_catalogue(data)

    def test_rotating_blocks_are_balanced_fresh_unique_cells(self):
        cells = bundle()["plan"]["cells"]
        self.assertEqual(len({row["cell_id"] for row in cells}), 177)
        evaluation = [row for row in cells if row["stage"] == "evaluation"]
        self.assertEqual(
            Counter((row["method"], row["position"]) for row in evaluation),
            {(method, position): 5 for method in "BRG" for position in range(3)},
        )
        self.assertEqual(len({row["parent_id"] for row in evaluation}), 15)
        self.assertTrue(
            all(row["status"] == "PLANNED" and "attempt" not in row for row in cells)
        )
        self.assertFalse(bundle()["plan"]["scientific_execution_authorized"])

    def test_primary_and_contingent_budgets_stay_separate(self):
        contract = approved_contract()
        self.assertEqual(contract["budget"]["conditional_hard_diagnostic_calls"], 6)
        self.assertIsNone(contract["budget"]["Benders_standing_budget"])
        self.assertEqual(
            set(contract["solver"]["profiles"]),
            {"root_relaxation", "incumbent", "evaluation"},
        )
        self.assertTrue(
            all(
                profile["MIPFocus"] == 0
                for profile in contract["solver"]["profiles"].values()
            )
        )
        self.assertEqual(contract["learning"]["updates_per_arm"], 4200)
        self.assertEqual(contract["learning"]["presentations_per_arm"], 16800)


class BundleIntegrityTests(unittest.TestCase):
    def test_exclusive_export_is_byte_identical_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "new"
            export_bundle(bundle()["catalogue"], target)
            self.assertEqual(summary(load_bundle(target)), summary(bundle()))
            for path in target.iterdir():
                self.assertEqual(
                    path.read_bytes(),
                    (ROOT / "configs/mvp3/v1" / path.name).read_bytes(),
                )
            with self.assertRaises(FileExistsError):
                export_bundle(bundle()["catalogue"], target)

    def test_corrupt_and_resealed_scientific_changes_are_rejected(self):
        for reseal in (False, True):
            with self.subTest(reseal=reseal), tempfile.TemporaryDirectory() as temp:
                target = export_bundle(bundle()["catalogue"], Path(temp) / "bundle")
                path = target / "contract.json"
                data = load_json(path)
                data["solver"]["profiles"]["evaluation"]["Threads"] = 32
                raw = (json.dumps(data) + "\n").encode()
                path.write_bytes(raw)
                if reseal:
                    seal = load_json(target / "bundle-manifest.json")
                    seal["files"][path.name] = {
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                    (target / "bundle-manifest.json").write_text(
                        json.dumps(seal), encoding="utf-8"
                    )
                with self.assertRaises(ContractError):
                    load_bundle(target)

    def test_resealed_schema_cannot_weaken_evidence_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            target = export_bundle(bundle()["catalogue"], Path(temp) / "bundle")
            path = target / "evidence.schema.json"
            raw = b'{"type":"object"}\n'
            path.write_bytes(raw)
            seal = load_json(target / "bundle-manifest.json")
            seal["files"][path.name] = {
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            (target / "bundle-manifest.json").write_text(
                json.dumps(seal), encoding="utf-8"
            )
            with self.assertRaisesRegex(ContractError, "schema differs"):
                load_bundle(target)

    def test_bundle_rejects_unexpected_path_before_read(self):
        with tempfile.TemporaryDirectory() as temp:
            target = export_bundle(bundle()["catalogue"], Path(temp) / "bundle")
            path = target / "bundle-manifest.json"
            seal = load_json(path)
            seal["files"]["../secret"] = seal["files"].pop("contract.json")
            path.write_text(json.dumps(seal), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "Unexpected bundle files"):
                load_bundle(target)

    def test_json_rejects_duplicate_keys_and_nonfinite_values(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "input.json"
                path.write_text(raw, encoding="utf-8")
                with self.assertRaises(ContractError):
                    load_json(path)

    def test_import_has_no_solver_or_tensor_side_effect(self):
        code = "import sys; from cfl_gnn.mvp3 import contract,identity,records,schema; assert not any(n in sys.modules for n in ['gurobipy','torch','torch_geometric','subprocess']); print('OFFLINE_IMPORT_PASS')"
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                f"import sys; sys.path.insert(0, {str(ROOT / 'src')!r}); {code}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("OFFLINE_IMPORT_PASS", result.stdout)

    def test_cli_validates_without_writing_observations(self):
        environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "cfl_gnn.mvp3",
                "--bundle",
                str(ROOT / "configs/mvp3/v1"),
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["primary_cells"], 177)
        self.assertFalse(data["scientific_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
