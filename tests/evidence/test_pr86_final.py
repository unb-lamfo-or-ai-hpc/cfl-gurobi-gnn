"""Final210 receipt pins, paired statistics and publication reproducibility."""

import csv
import io
import json
import math
import statistics
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import review_pr86_final as final  # noqa: E402


class FinalReview(unittest.TestCase):
    def equivalent_json(self, actual, expected):
        if isinstance(expected, dict):
            self.assertEqual(set(actual), set(expected))
            for key in expected:
                self.equivalent_json(actual[key], expected[key])
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected))
            for a, b in zip(actual, expected):
                self.equivalent_json(a, b)
        elif isinstance(expected, float):
            self.assertTrue(
                math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
            )
        else:
            self.assertEqual(actual, expected)

    @classmethod
    def setUpClass(cls):
        cls.raw = final.q.read(final.DEST / "public_return.json")
        cls.rows, cls.prior, cls.wave = final.review(cls.raw)

    def test_exact_coverage_and_historical_prefix(self):
        self.assertEqual(len(self.rows), 210)
        self.assertEqual(len({r["cell_id"] for r in self.rows}), 210)
        self.assertEqual(
            self.rows[:201],
            final.read_csv(final.q.read(final.PRIOR / "campaign_results.csv")),
        )
        self.assertEqual(sum(r["right_censored"] for r in self.rows), 75)
        self.assertEqual(sum(r["alias"] == "M12" for r in self.rows), 21)
        self.assertTrue(
            all(
                r["numerical_scope"].startswith("M12_tolerance_sensitive")
                for r in self.rows[-9:]
            )
        )

    def test_final_hash_rejects_byte_changes(self):
        with self.assertRaisesRegex(ValueError, "final_return_hash"):
            final.review(self.raw + b" ")

    def test_historical_source_cannot_be_relabelled(self):
        value = json.loads(self.raw)
        value["plan"]["source_commit"] = "0" * 40
        raw = final.q.encoded(value)
        with (
            patch.object(final, "SHA", final.q.digest(raw)),
            self.assertRaisesRegex(ValueError, "historical_source"),
        ):
            final.review(raw)

    def test_nested_member_corruption_rejected(self):
        value = json.loads(self.raw)
        value["returns"][0]["members"]["run/attempt-0/child.json"]["sha256"] = "0" * 64
        raw = final.q.encoded(value)
        with (
            patch.object(final, "SHA", final.q.digest(raw)),
            self.assertRaisesRegex(ValueError, "member"),
        ):
            final.review(raw)

    def test_preparation_pinned_before_calculation(self):
        original = final.q.read
        with (
            patch.object(
                final.q,
                "read",
                side_effect=lambda path: (
                    original(path) + (b"\n" if path == final.PREP else b"")
                ),
            ),
            self.assertRaisesRegex(ValueError, "frozen_preparation_costs"),
        ):
            final.annotate_costs(self.rows)

    def test_m12_previous_return_pinned(self):
        original = final.q.read
        prior_path = final.flow.reviewed.audit.review.DEST / "public_return.json"
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(
                final.q,
                "read",
                side_effect=lambda path: (
                    original(path) + (b"\n" if path == prior_path else b"")
                ),
            ),
            self.assertRaisesRegex(ValueError, "m12_original_wave_hash"),
        ):
            final.publish(Path(temp).resolve())

    def test_constant_exact_bootstrap_and_loo(self):
        result = final.paired_summary([math.log(2)] * 6)
        for key in (
            "geometric_mean_ratio",
            "bootstrap_percentile_lower_95",
            "bootstrap_percentile_upper_95",
            "leave_one_parent_out_min",
            "leave_one_parent_out_max",
        ):
            self.assertAlmostEqual(result[key], 2)
        self.assertEqual(result["bootstrap_ordered_resamples"], 46656)

    def test_reciprocal_and_scale_equivariance(self):
        logs = [math.log(v) for v in (0.5, 1, 2, 3, 0.7, 1.4)]
        direct = final.paired_summary(logs)
        inverse = final.paired_summary([-v for v in logs])
        shifted = final.paired_summary([v + math.log(3) for v in logs])
        self.assertAlmostEqual(
            inverse["geometric_mean_ratio"], 1 / direct["geometric_mean_ratio"]
        )
        self.assertAlmostEqual(
            inverse["bootstrap_percentile_upper_95"],
            1 / direct["bootstrap_percentile_lower_95"],
        )
        self.assertAlmostEqual(
            shifted["bootstrap_percentile_lower_95"],
            3 * direct["bootstrap_percentile_lower_95"],
        )

    def test_bootstrap_rejects_invalid_scope(self):
        for logs in ([0], [0] * 7, [float("nan"), 0]):
            with self.assertRaisesRegex(ValueError, "paired_logs"):
                final.paired_summary(logs)

    def test_accounting_units_and_unavailable_values(self):
        self.assertIsNone(final.slurm_seconds(""))
        self.assertEqual(final.slurm_seconds("0:0:00"), 0)
        self.assertEqual(final.slurm_seconds("1-02:03:04.5"), 93784.5)
        self.assertEqual(final.slurm_seconds("02:03.5"), 123.5)
        with self.assertRaises(ValueError):
            final.slurm_seconds("broken")

    def test_full_source_details_and_job_denominators(self):
        outputs, totals = final.detailed_sources(self.rows)
        details = list(
            csv.DictReader(io.StringIO(outputs["solve_details.csv"].decode()))
        )
        accounting = list(
            csv.DictReader(io.StringIO(outputs["scheduler_accounting.csv"].decode()))
        )
        self.assertEqual(len(details), 210)
        self.assertEqual(len({r["job_id"] for r in accounting}), 70)
        self.assertEqual(totals["scheduler_jobs_counted_once"], 70)
        self.assertEqual(totals["scheduler_job_elapsed_sum_seconds"], 301402)
        self.assertAlmostEqual(
            totals["scheduler_job_total_cpu_sum_seconds"], 749533.491
        )
        self.assertTrue(
            all(r["effective_objective_sense"] == "MINIMIZE" for r in details)
        )
        self.assertTrue(
            all(float(r["terminal_target_fraction"]) == 1e-4 for r in details)
        )

    def test_paired_seed_average_is_within_parent(self):
        outputs = final.analyses(self.rows)
        summary = list(
            csv.DictReader(io.StringIO(outputs["paired_uncertainty.csv"].decode()))
        )
        self.assertEqual(len(summary), 90)
        observed = next(
            r
            for r in summary
            if r["metric"] == "solver_seconds"
            and r["numerator"] == "M2"
            and r["denominator"] == "M0"
            and r["seed_scope"].startswith("parent_mean")
        )
        self.assertEqual(int(observed["parents"]), 6)
        expected = []
        for alias in sorted(
            {r["alias"] for r in self.rows if r["alias"].startswith("F")}
        ):
            logs = []
            for seed in (42, 43, 44):
                pair = {
                    r["method"]: r
                    for r in self.rows
                    if r["alias"] == alias and r["threads"] == 1 and r["seed"] == seed
                }
                logs.append(
                    math.log(
                        pair["M2"]["solver_seconds"] / pair["M0"]["solver_seconds"]
                    )
                )
            expected.append(statistics.mean(logs))
        self.assertAlmostEqual(
            float(observed["geometric_mean_ratio"]), math.exp(statistics.mean(expected))
        )
        self.assertAlmostEqual(
            float(observed["geometric_mean_ratio"]), 1.0912218831365992
        )

    def test_cold_allocation_sensitivity_and_no_medium_speedup(self):
        outputs = final.analyses(self.rows)
        summary = list(
            csv.DictReader(io.StringIO(outputs["paired_uncertainty.csv"].decode()))
        )
        cold = next(
            r
            for r in summary
            if r["threads"] == "16"
            and r["seed_scope"] == "seed42"
            and r["numerator"] == "M2"
            and r["denominator"] == "M0"
            and r["metric"] == "allocated_cold_scenario_seconds"
        )
        self.assertGreater(float(cold["geometric_mean_ratio"]), 1.06)
        effects = list(
            csv.DictReader(io.StringIO(outputs["paired_parent_effects.csv"].decode()))
        )
        self.assertTrue(all(r["parent_alias"].startswith("F") for r in effects))
        self.assertEqual(len(effects), 450)

    def test_published_assets_and_repeat_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            report = final.publish(directory)
            final.publish(directory)
            self.assertFalse(report["scientific_reporting_eligible"])
            self.assertFalse(report["M4_M12_exact_optimality_or_certified_speedup"])
            self.assertFalse(report["further_dispatch_admitted"])
            self.assertEqual(
                [s["reported_target_met"] for s in report["scope_counts"]], [127, 1, 7]
            )
            self.assertEqual(report["m12_cross_run_comparisons"], 14)
            for name in json.loads(final.q.read(directory / "manifest.json"))[
                "outputs"
            ]:
                current, published = (
                    final.q.read(directory / name),
                    final.q.read(final.DEST / name),
                )
                # Byte seals apply to published observations/assets. Recomputed
                # libm/stdlib arithmetic can differ at roundoff across OS/Python.
                if name.endswith(".csv"):
                    current_rows = list(csv.DictReader(io.StringIO(current.decode())))
                    published_rows = list(
                        csv.DictReader(io.StringIO(published.decode()))
                    )
                    self.assertEqual(len(current_rows), len(published_rows), name)
                    for actual, expected in zip(current_rows, published_rows):
                        self.assertEqual(set(actual), set(expected))
                        for key in expected:
                            if actual[key] == expected[key]:
                                continue
                            self.assertNotIn(
                                key,
                                {
                                    "cell_id",
                                    "job_id",
                                    "method",
                                    "parent",
                                    "alias",
                                    "parent_alias",
                                    "threads",
                                    "seed",
                                    "numerator",
                                    "denominator",
                                    "numerical_scope",
                                },
                            )
                            self.assertNotIn("sha256", key)
                            self.assertTrue(
                                math.isclose(
                                    float(actual[key]),
                                    float(expected[key]),
                                    rel_tol=1e-12,
                                    abs_tol=1e-12,
                                ),
                                (name, key),
                            )
                else:
                    self.equivalent_json(json.loads(current), json.loads(published))
            (directory / "review.json").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "preserve_output"):
                final.publish(directory)
        self.assertEqual(
            final.q.digest(final.q.read(final.DEST / "public_return.json")), final.SHA
        )

    def test_figure_hashes_and_rendering_source_binding(self):
        manifest = json.loads(final.q.read(final.DEST / "figure_manifest.json"))
        self.assertEqual(len(manifest["outputs"]), 18)
        self.assertEqual(
            manifest["source_manifest_sha256"],
            final.q.digest(final.q.read(final.DEST / "manifest.json")),
        )
        for name, digest in {**manifest["inputs"], **manifest["outputs"]}.items():
            self.assertEqual(
                final.q.digest(final.q.read(final.DEST / name)), digest, name
            )
        svg = final.q.read(final.DEST / "medium_terminal_gap.svg").decode()
        self.assertIn("sensible a tolerancias", svg)
        self.assertIn("no certifican", svg)

    def test_complete_publication_seal(self):
        seal = json.loads(final.q.read(final.DEST / "publication_manifest.json"))
        expected = {p.name for p in final.DEST.iterdir() if p.is_file()} - {
            "publication_manifest.json"
        }
        self.assertEqual(set(seal["payloads_sha256"]), expected)
        for name, digest in seal["payloads_sha256"].items():
            self.assertEqual(final.q.digest(final.q.read(final.DEST / name)), digest)
        for name, digest in seal["source_sha256_lf"].items():
            self.assertEqual(
                final.q.digest(
                    final.q.read(final.q.ROOT / name).replace(b"\r\n", b"\n")
                ),
                digest,
            )


if __name__ == "__main__":
    unittest.main()
