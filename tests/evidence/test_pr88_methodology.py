"""Offline methodological contracts and arithmetic, without optional ML libraries."""

import copy
import csv
import io
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import build_pr88_methodology as m  # noqa: E402


class MethodologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = m.SOURCE.read_bytes()
        cls.original, cls.main = m.observed_rows(cls.raw)

    def test_byte_identity_and_seed_selection(self):
        self.assertEqual(len(self.original), 210)
        self.assertEqual(len(self.main), 150)
        self.assertTrue(
            all(r in self.original and r["seed"] == "42" for r in self.main)
        )
        self.assertEqual(
            Counter(r["right_censored"] for r in self.main), {"False": 97, "True": 53}
        )
        with self.assertRaises(ValueError):
            m.observed_rows(self.raw + b"\n")

    def test_speedup_direction_and_cpu_reference(self):
        pairs, scaling = m.comparisons(self.main)
        row = next(
            r
            for r in pairs
            if r["alias"] == "F0"
            and r["threads"] == "1"
            and r["comparison"] == "M2_vs_M0"
        )
        lookup = {
            r["method"]: r
            for r in self.main
            if r["alias"] == "F0" and r["threads"] == "1"
        }
        self.assertAlmostEqual(
            row["speedup_baseline_over_M2"],
            float(lookup["M0"]["solver_seconds"])
            / float(lookup["M2"]["solver_seconds"]),
        )
        self.assertTrue(
            all(
                r["same_method_cpu_speedup"] == 1
                for r in scaling
                if r["threads"] == "1" and r["eligible_common_terminal_target"]
            )
        )
        self.assertTrue(
            all(
                r["speedup_baseline_over_M2"] == ""
                for r in pairs
                if r["alias"] in {"M4", "M12"}
            )
        )

    def test_timeout_and_sensitive_rows_do_not_certify_speedup(self):
        row = copy.deepcopy(self.main[0])
        row["right_censored"] = "True"
        self.assertFalse(m.qualified(row))
        row.update(right_censored="False", alias="M12")
        self.assertFalse(m.qualified(row))

    def test_cpu_matrix_cartesian_unique_and_unapproved(self):
        rows, package = m.cpu_package()
        self.assertEqual(
            len({(r["parent"], r["method"], r["threads"], r["seed"]) for r in rows}), 60
        )
        self.assertEqual({r["alias"] for r in rows}, {"M0", "M4", "M7", "M12"})
        self.assertTrue(
            all(
                not r["execution_authorized"] and r["nodes"] == 1 and r["gpus"] == 0
                for r in rows
            )
        )
        self.assertEqual(sum(r["wall_seconds"] for r in rows) / 3600, 780)
        self.assertEqual(
            sum(r["threads"] * r["solver_limit_seconds"] for r in rows) / 3600, 4464
        )
        self.assertEqual(
            sum(r["threads"] * r["wall_seconds"] for r in rows) / 3600, 4836
        )
        self.assertFalse(package["execution_authorized"])
        self.assertEqual(len(package["gates_pending"]), 8)
        self.assertEqual(package["mip_gap_fraction"], 0.0001)

    def test_generated_outputs_match_manifest_and_preserve_cells(self):
        products = m.products(self.raw)
        manifest = json.loads(products["manifest.json"])
        for name, sha in manifest["outputs"].items():
            self.assertEqual(m.digest(products[name]), sha)
        rows = list(csv.DictReader(io.StringIO(products["seed42_main.csv"].decode())))
        self.assertEqual(rows, self.main)
        self.assertEqual(m.SOURCE.read_bytes(), self.raw)

    def test_repository_derived_files_reproduce(self):
        m.build(check=True)

    def test_figure_assets_are_bound_and_not_multiseed(self):
        receipt = json.loads((m.DEST / "figures_manifest.json").read_bytes())
        self.assertEqual(
            receipt["data_manifest_sha256"],
            m.digest((m.DEST / "manifest.json").read_bytes()),
        )
        self.assertEqual(len(receipt["assets"]), 12)
        self.assertFalse(receipt["historical_figures_modified"])
        for name, sha in receipt["assets"].items():
            self.assertNotIn("repeatability", name)
            self.assertEqual(m.digest((m.DEST / name).read_bytes()), sha)

    def test_future_method_order_preserves_seed42_predecessor(self):
        rows, _ = m.cpu_package()
        original = {
            (r["alias"], int(r["threads"]), r["method"]): int(
                r["method_order_position"]
            )
            for r in self.main
        }
        self.assertTrue(
            all(
                r["method_order_position"]
                == original[(r["alias"], r["threads"], r["method"])]
                for r in rows
            )
        )


if __name__ == "__main__":
    unittest.main()
