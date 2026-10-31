"""Verify population and comparison identities for existing CPU publication assets."""
import hashlib
import importlib.util
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "principal_assets", ROOT / "scripts/manuscript/build_principal_assets.py"
)
ASSETS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSETS)


class PrincipalAssetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ASSETS.INPUTS + ("manuscript/supplement/claim-evidence.json",):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)

    def test_fixed_sources_have_150_cells_and_ten_instances(self):
        rows, _, _ = ASSETS.fixed_inputs(self.root)
        self.assertEqual(len(rows), 150)
        self.assertEqual(len({r["alias"] for r in rows}), 10)
        self.assertEqual({r["seed"] for r in rows}, {"42"})

    def test_changed_source_bytes_are_not_accepted(self):
        path = self.root / ASSETS.INPUTS[0]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            ASSETS.fixed_inputs(self.root)

    def test_missing_cell_is_not_hidden_by_updating_its_hash(self):
        path = self.root / ASSETS.INPUTS[0]
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        manifest_path = self.root / "manuscript/supplement/claim-evidence.json"
        manifest = json.loads(manifest_path.read_text())
        for record in manifest["sources"]:
            if record["path"] == ASSETS.INPUTS[0]:
                record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "population or cell identity"):
            ASSETS.fixed_inputs(self.root)

    def test_cost_and_solver_ratios_keep_the_recorded_orientation(self):
        rows, _, summaries = ASSETS.fixed_inputs(self.root)
        selected = {(r["alias"], r["method"]): r for r in rows
                    if r["alias"] in ASSETS.EASY and r["threads"] == "16"}
        for field in ("solver_seconds", "scoped_cold_cost_scenario_seconds"):
            observed = math.exp(sum(
                math.log(float(selected[p, "M2"][field]) /
                         float(selected[p, "M0"][field]))
                for p in ASSETS.EASY
            ) / 6)
            expected = float(ASSETS.summary_row(
                summaries, 16, "M2", "M0", field
            )["geometric_mean_ratio"])
            self.assertAlmostEqual(observed, expected, places=12)

    def test_ambiguous_aggregate_is_rejected(self):
        _, _, summaries = ASSETS.fixed_inputs(self.root)
        target = ASSETS.summary_row(summaries, 16, "M2", "M0", "solver_seconds")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            ASSETS.summary_row(summaries + [target], 16, "M2", "M0", "solver_seconds")


if __name__ == "__main__":
    unittest.main()
