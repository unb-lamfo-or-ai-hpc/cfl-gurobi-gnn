"""Censored medium observations and the frozen six-job continuation without HPC."""

import copy
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_wave49 as f  # noqa: E402
import test_pr86_main_first_group as fixtures  # noqa: E402
import test_pr86_six_job_queue as wave_tests  # noqa: E402

q, review = f.q, f.reviewed


class Wave49(unittest.TestCase):
    def test_real_prefix_and_regeneration_preserve_bytes(self):
        raw = q.read(review.DEST / "public_return.json")
        rows, summary = review.review(raw)
        self.assertEqual(len(rows), 147)
        self.assertEqual(summary["completed_groups"], 49)
        self.assertEqual(summary["remaining_cells"], 63)
        self.assertTrue(summary["M0_complete"])
        self.assertTrue(summary["M4_unobserved"])
        self.assertEqual(summary["target_met_cells"], 127)
        self.assertEqual(summary["right_censored_cells"], 20)
        self.assertEqual(summary["easy_cells"], 126)
        self.assertEqual(summary["medium_cells"], 21)
        self.assertFalse(summary["all_observed_target_gaps_met"])
        medium = [r for r in rows if r["alias"] == "M0"]
        reached = [r for r in medium if not r["right_censored"]]
        self.assertEqual(len(reached), 1)
        self.assertEqual(
            (reached[0]["method"], reached[0]["threads"], reached[0]["seed"]),
            ("M2", 16, 42),
        )
        self.assertEqual(reached[0]["gap_fraction"], 0)
        self.assertTrue(
            all(r["solver_seconds"] >= 3600 for r in medium if r["right_censored"])
        )
        with self.assertRaisesRegex(ValueError, "wave43_return_hash"):
            review.review(raw + b" ")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            review.publish(folder)
            review.publish(folder)
            for name in (
                "review.json",
                "campaign_results.csv",
                "m0_gap_cpu.svg",
                "m0_memory_cpu.svg",
                "manifest.json",
            ):
                self.assertEqual(q.read(folder / name), q.read(review.DEST / name))

    def test_next_prefix_and_medium_bindings(self):
        frozen = f.plan("a" * 40)
        original, cells = q.first.executor.proposal.build()
        guidance, ledger, _ = q.first.review.review(
            q.read(q.first.review.DESTINATION / "public_return.json")
        )
        for i, (group, expected) in enumerate(
            zip(frozen["groups"], original["groups"][49:55])
        ):
            self.assertEqual(group["group"], expected)
            self.assertEqual(
                group["cells"],
                [c for c in cells if c["group_id"] == expected["group_id"]],
            )
            index = 7
            self.assertEqual(
                group["start_binding"]["private_starts_sha256"],
                guidance["child"]["rows"][index]["private_starts_sha256"],
            )
            self.assertEqual(
                group["preparation_seconds"]["root"],
                ledger[index]["root_supervised_seconds"],
            )
        self.assertEqual(frozen["maximum_physical_core_hours"], 68)
        self.assertEqual(frozen["campaign_completed_calls_before_this_wave"], 147)
        self.assertEqual(frozen["maximum_optimization_calls"], 18)
        self.assertFalse(frozen["dispatch_after_this_wave"])

    def test_submit_caches_by_parent_and_never_reuses_other_parent_inputs(self):
        self.frozen = f.plan("a" * 40)
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            calls = wave_tests.SixJobs.submit_fixture(self, stage, stack)
            policy = copy.copy(f.POLICY)
            policy.claim = stage / "claim"
            policy.installed_review = lambda: self.frozen["first_review"]
            private = stack.enter_context(
                patch.object(
                    q.first,
                    "private_inputs",
                    side_effect=lambda g: (
                        Path(g["group"]["parent"]),
                        Path(g["group"]["parent"] + "-starts"),
                    ),
                )
            )
            bundles = stack.enter_context(patch.object(q.first, "bundles"))
            result = q.submit(stage, q.digest(q.encoded(self.frozen)), policy)
            self.assertEqual(private.call_count, 1)
            self.assertEqual(bundles.call_count, 6)
            for call, group in zip(bundles.call_args_list, self.frozen["groups"]):
                self.assertEqual(call.args[2], Path(group["group"]["parent"]))
                self.assertEqual(
                    call.args[3], Path(group["group"]["parent"] + "-starts")
                )
            self.assertTrue(
                all(
                    c[-3].endswith("operate_pr86_wave49.sh")
                    for c in calls
                    if c[0] == "sbatch"
                )
            )
            self.assertEqual(q.admitted(stage, self.frozen, policy), result["job_ids"])
            with self.assertRaises(FileExistsError):
                q.submit(stage, q.digest(q.encoded(self.frozen)), policy)

    def test_real_eighteen_admissions(self):
        self.frozen = f.plan("a" * 40)
        wave_tests.SixJobs.test_real_admission_for_all_six_caps_and_seeds(self)

    def test_mixed_return_and_wrong_model_or_dependency(self):
        frozen = f.plan("a" * 40)
        with tempfile.TemporaryDirectory() as temp:
            value = {
                "protocol_id": f.POLICY.protocol,
                "plan": frozen,
                "plan_sha256": q.digest(q.encoded(frozen)),
                "returns": [],
                "launch": [],
                "scientific_reporting_eligible": False,
                "raw_logs_included": False,
            }
            helper = fixtures.MainFirst()
            for i, group in enumerate(frozen["groups"]):
                folder = Path(temp) / str(i)
                folder.mkdir()
                helper.frozen = group
                job, prev = str(900 + i), str(899 + i) if i else None
                value["returns"].append(helper.make_return(folder, job=job))
                value["launch"].append(
                    {
                        "job_id": job,
                        "held_profile": q.profile(
                            wave_tests.held(job, group["group"]["threads"], prev),
                            job,
                            group["group"]["threads"],
                            prev,
                        ),
                    }
                )
            self.assertEqual(
                q.validate_return(q.encoded(value), f.POLICY)["complete_groups"], 6
            )
            bad = copy.deepcopy(value)
            bad["returns"][5]["plan"]["start_binding"]["model_sha256"] = "f" * 64
            with self.assertRaises(ValueError):
                q.validate_return(q.encoded(bad), f.POLICY)
            bad = copy.deepcopy(value)
            bad["launch"][1]["held_profile"]["dependency"] = "afterany:900"
            with self.assertRaisesRegex(ValueError, "serial_dependency"):
                q.validate_return(q.encoded(bad), f.POLICY)

    def test_medium_m4_private_paths_use_index_seven(self):
        group = f.plan("a" * 40)["groups"][5]
        self.assertEqual(group["group"]["parent"], "CFL_medium_instance_4")
        self.assertEqual(group["start_binding"]["selected_support"], 20000)
        first = q.first
        raw = q.read(first.review.DESTINATION / "public_return.json")
        guidance = first.review.review(raw)
        original, _ = first.executor.proposal.build()
        observed = []

        def sha(path):
            observed.append(path.as_posix())
            return group["start_binding"][
                {
                    "graph.private.pt": "graph_sha256",
                    "predictions.private.json": "prediction_sha256",
                    "starts.private.json": "private_starts_sha256",
                    "root.private.json.gz": "root_sha256",
                    "mip-7": "model_sha256",
                }[path.name]
            ]

        with ExitStack() as stack:
            stack.enter_context(patch.object(first, "read", return_value=raw))
            stack.enter_context(
                patch.object(first.review, "review", return_value=guidance)
            )
            stack.enter_context(
                patch.object(
                    first.roots,
                    "inputs",
                    return_value=[
                        {**p, "mip_path": f"mip-{i}"}
                        for i, p in enumerate(original["parents"])
                    ],
                )
            )
            stack.enter_context(patch.object(first.review.roots, "review"))
            stack.enter_context(
                patch.object(first.roots, "sha256_file", side_effect=sha)
            )
            mip, starts = first.private_inputs(group)
            self.assertEqual(mip, Path("mip-7"))
            self.assertIn("run/7/starts.private.json", starts.as_posix())
            self.assertTrue(all("/run/6/" not in p for p in observed))

    def test_medium_figures_distinguish_certification_censoring_and_memory_scope(self):
        rows, _ = review.review(q.read(review.DEST / "public_return.json"))
        medium = [r for r in rows if r["alias"] == "M0"]
        gap = review.medium_figure(medium, "gap")
        memory = review.medium_figure(medium, "memory")
        self.assertIn(b"20/21 censurados y 1/21", gap)
        self.assertIn(b"3204,179 s", gap)
        self.assertIn(b"no es Slurm MaxRSS", memory)
        self.assertIn(b"Parada: 56 GiB", memory)
        self.assertNotIn(b"Parada: 56 GiB", gap)
        with self.assertRaisesRegex(ValueError, "medium_figure_scope"):
            review.medium_figure(medium[:3], "gap")
        with self.assertRaisesRegex(ValueError, "figure_metric"):
            review.medium_figure(medium, "runtime")


if __name__ == "__main__":
    unittest.main()
