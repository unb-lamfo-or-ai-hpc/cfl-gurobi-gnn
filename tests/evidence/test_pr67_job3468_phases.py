"""Offline review of returned observations; no raw logs, solver or training."""

import csv
import hashlib
import io
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import collect_pr66_log_phases as phases  # noqa: E402
import pr66_thread_pilot as pilot  # noqa: E402

EVIDENCE = ROOT / "docs/evidence/pr67/job3468"
EXPORT_HASHES = {
    "phase_observations.json": "182e263ebcf899166ea05af3979041e3614d5b0d43b2c68f60a35ad8a0d32ac2",
    "phase_observations.csv": "a707028069fa4a022a66ba31bd25d8585540191958ef648638ee8ef55874673e",
    "SHA256SUMS.txt": "c30c8ea82ceaf404bf86851945fc736acc73e023f2ddf2ffbc18498c88c556ef",
}
CSV_FIELDS = [
    "attempt",
    "source_instance_id",
    "threads",
    "slurm_job_id",
    "attempt_report_sha256",
    "log_sha256",
    "log_size_bytes",
    "model_read_setup_seconds",
    "optimize_wall_seconds",
    "solver_runtime_seconds",
    "node_count",
    "termination",
    "log_state",
    "presolve_display_seconds",
    "root_relaxation_state",
    "root_relaxation_display_seconds",
    "root_relaxation_iterations",
    "solver_total_display_seconds",
    "warnings",
]


def load(name):
    return pilot.strict_json(EVIDENCE / name)


class ReturnedPhaseTests(unittest.TestCase):
    def test_original_exports_byte_exact_and_manifest(self):
        for name, expected in EXPORT_HASHES.items():
            self.assertEqual(phases.sha((EVIDENCE / name).read_bytes()), expected)
        manifest = {}
        for line in (EVIDENCE / "SHA256SUMS.txt").read_text().splitlines():
            digest, name = line.split("  ", 1)
            self.assertNotIn(name, manifest)
            self.assertIn(name, EXPORT_HASHES.keys() - {"SHA256SUMS.txt"})
            self.assertEqual(digest, EXPORT_HASHES[name])
            manifest[name] = digest
        self.assertEqual(set(manifest), EXPORT_HASHES.keys() - {"SHA256SUMS.txt"})

    def test_collector_plan_and_all_original_receipt_joins(self):
        value = load("phase_observations.json")
        self.assertEqual(value["plan_sha256"], phases.PLAN_SHA)
        self.assertEqual(value["reviewed_manifest_sha256"], phases.MANIFEST_SHA)
        self.assertEqual(
            value["collector_sha256"],
            phases.sha(
                (ROOT / "scripts/evidence/collect_pr66_log_phases.py").read_bytes()
            ),
        )
        self.assertEqual([r["attempt"] for r in value["rows"]], phases.NAMES)
        originals = phases.public_receipts()
        for row in value["rows"]:
            data = originals[row["attempt"] + "/attempt_report.json"]
            original = json.loads(data)
            self.assertEqual(row["attempt_report_sha256"], phases.sha(data))
            self.assertEqual(row["threads"], original["parameters"]["Threads"])
            for key in (
                "source_instance_id",
                "slurm_job_id",
                "model_read_setup_seconds",
                "optimize_wall_seconds",
                "solver_runtime_seconds",
                "node_count",
                "termination",
            ):
                self.assertEqual(row[key], original[key])

    def test_csv_projection_is_byte_exact(self):
        rows = load("phase_observations.json")["rows"]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({**r, "warnings": ";".join(r["warnings"])} for r in rows)
        self.assertEqual(
            stream.getvalue().encode(),
            (EVIDENCE / "phase_observations.csv").read_bytes(),
        )

    def test_nine_consistent_one_unqualified_is_retained(self):
        rows = load("phase_observations.json")["rows"]
        good = [r for r in rows if r["log_state"] == "receipt_consistent_observations"]
        self.assertEqual(len(good), 9)
        self.assertTrue(all(r["root_relaxation_state"] == "completed" for r in good))
        bad = [r for r in rows if r["log_state"] != "receipt_consistent_observations"]
        self.assertEqual([r["attempt"] for r in bad], ["medium-threads16"])
        self.assertEqual(bad[0]["warnings"], ["terminal_summary_receipt_mismatch"])
        for key in (
            "presolve_display_seconds",
            "root_relaxation_display_seconds",
            "root_relaxation_iterations",
            "solver_total_display_seconds",
        ):
            self.assertIsNone(bad[0][key])
        self.assertEqual(bad[0]["root_relaxation_state"], "unavailable")

    def test_operator_numeric_diagnostic_recomputes_runtime_only(self):
        value = load("medium16_numeric_diagnostic.json")
        row = load("phase_observations.json")["rows"][-1]
        original = json.loads(
            phases.public_receipts()["medium-threads16/attempt_report.json"]
        )
        self.assertEqual(value["log_sha256"], row["log_sha256"])
        self.assertEqual(value["attempt_report_sha256"], row["attempt_report_sha256"])
        self.assertEqual(
            value["collector_sha256"],
            load("phase_observations.json")["collector_sha256"],
        )
        checks = value["checks"]
        for key in ("primal", "dual"):
            check = checks[key]
            self.assertEqual(check["receipt"], original[key])
            self.assertEqual(
                check["absolute_delta"], abs(check["display"] - check["receipt"])
            )
            self.assertEqual(check["absolute_tolerance"], 1e-10)
            self.assertEqual(check["relative_tolerance"], 1e-10)
            self.assertTrue(
                math.isclose(
                    check["display"], check["receipt"], rel_tol=1e-10, abs_tol=1e-10
                )
            )
            self.assertTrue(check["pass"])
        runtime = checks["runtime"]
        self.assertEqual(runtime["receipt_seconds"], original["solver_runtime_seconds"])
        self.assertEqual(
            runtime["absolute_delta_seconds"],
            abs(runtime["display_seconds"] - runtime["receipt_seconds"]),
        )
        self.assertEqual(runtime["absolute_tolerance_seconds"], 0.051)
        self.assertGreater(runtime["absolute_delta_seconds"], 0.051)
        self.assertFalse(runtime["pass"])
        gap = checks["relative_gap"]
        self.assertEqual(gap["receipt_fraction"], original["mip_gap_relative"])
        self.assertEqual(
            gap["absolute_delta_fraction"],
            abs(gap["display_percent"] / 100 - gap["receipt_fraction"]),
        )
        self.assertEqual(gap["absolute_tolerance_fraction"], 0.000001)
        self.assertLessEqual(gap["absolute_delta_fraction"], 0.000001)
        self.assertEqual(checks["node_count"]["display"], original["node_count"])
        self.assertEqual(checks["node_count"]["receipt"], original["node_count"])
        self.assertEqual(
            checks["runtime_nonnegative"]["display"], runtime["display_seconds"]
        )
        self.assertGreaterEqual(checks["runtime_nonnegative"]["display"], 0)
        self.assertEqual(
            sorted(k for k, c in checks.items() if not c["pass"]), ["runtime"]
        )
        self.assertEqual(value["failed_checks"], ["runtime"])

    def test_actual_numeric_footer_does_not_requalify_parser(self):
        # Synthetic header/controls around operator-returned terminal numbers.
        # This is a regression, not a replay of the private log's phase lines.
        original = json.loads(
            phases.public_receipts()["medium-threads16/attempt_report.json"]
        )
        controls = "\n".join(f"{k} {v}" for k, v in original["parameters"].items())
        text = (
            f"Gurobi Optimizer version 13.0.1\n{controls}\n"
            "Presolve time: 1.0s\n"
            "Root relaxation: objective 1.0, 1 iterations, 1.0 seconds\n"
            "Explored 1 nodes (1 simplex iterations) in 300.10 seconds\n"
            "Best objective 25.89141802888, best bound 2.456209846529, gap 90.5134%\n"
        )
        value = phases.parse_log(text, original)
        self.assertEqual(value["log_state"], "unqualified")
        self.assertEqual(value["warnings"], ["terminal_summary_receipt_mismatch"])
        self.assertIsNone(value["root_relaxation_display_seconds"])
        self.assertIsNone(value["presolve_display_seconds"])

    def test_review_ranges_and_nonpromotion(self):
        review = load("phase_review.json")
        values = load("phase_observations.json")
        rows = values["rows"]
        medium = [
            r
            for r in rows
            if r["attempt"].startswith("medium-")
            and r["log_state"] == "receipt_consistent_observations"
        ]
        self.assertEqual(review["attempts_reviewed"], len(rows))
        self.assertEqual(review["receipt_consistent_logs"], 9)
        self.assertEqual(review["unqualified_logs"], 1)
        self.assertEqual(
            review["completed_root_lp_observations"],
            sum(r["root_relaxation_state"] == "completed" for r in rows),
        )
        self.assertEqual(
            review["medium_qualified_caps"], [r["threads"] for r in medium]
        )
        for field, metric in (
            ("medium_presolve_display_seconds_range", "presolve_display_seconds"),
            ("medium_root_lp_display_seconds_range", "root_relaxation_display_seconds"),
        ):
            self.assertEqual(
                review[field],
                [min(r[metric] for r in medium), max(r[metric] for r in medium)],
            )
        self.assertEqual(review["runtime_discrepancy_cause"], "not_established")
        self.assertTrue(review["parser_and_tolerances_unchanged"])
        self.assertTrue(review["medium16_phases_remain_unqualified"])
        self.assertEqual(review["optimization_runs_added"], 0)
        self.assertEqual(review["training_runs_added"], 0)
        for key in (
            "raw_private_logs_included",
            "execution_time_log_binding_established",
            "scientific_reporting_eligible",
            "phase_cpu_costs_qualified",
            "tree_phase_duration_qualified",
            "incumbent_uniqueness_certified",
            "expansion_authorized",
            "merge_authorized",
        ):
            self.assertFalse(review[key])
        for key in (
            "scientific_reporting_eligible",
            "phase_cpu_costs_qualified",
            "tree_phase_duration_qualified",
            "private_logs_included",
        ):
            self.assertFalse(values[key])
        self.assertEqual(values["optimization_runs"], 0)

    def test_public_member_allowlist_and_no_solver_import(self):
        self.assertEqual(
            {p.name for p in EVIDENCE.iterdir()},
            set(EXPORT_HASHES)
            | {"medium16_numeric_diagnostic.json", "phase_review.json"},
        )
        for path in EVIDENCE.iterdir():
            self.assertTrue(path.is_file())
            data = path.read_bytes()
            self.assertNotIn(b"License identifier", data)
            self.assertNotIn(b"/home/", data)
            self.assertNotIn(b"/raid/", data)
            self.assertNotIn(b"gurobi.private.log", data)
        self.assertNotIn("gurobipy", sys.modules)
        self.assertEqual(
            hashlib.sha256(
                (EVIDENCE / "phase_observations.json").read_bytes()
            ).hexdigest(),
            EXPORT_HASHES["phase_observations.json"],
        )


if __name__ == "__main__":
    unittest.main()
