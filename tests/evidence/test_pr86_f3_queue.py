"""F0 review and F3 continuation tests; no HPC or solver."""

import copy
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_f3_queue as f  # noqa: E402
import review_pr86_f0 as review  # noqa: E402
import test_pr86_main_first_group as fixtures  # noqa: E402
import test_pr86_six_job_queue as wave_tests  # noqa: E402

q = f.q


class F3Tests(unittest.TestCase):
    def test_real_admission_binds_all_eighteen_f3_cells(self):
        self.frozen = f.plan("a" * 40)
        wave_tests.SixJobs.test_real_admission_for_all_six_caps_and_seeds(self)

    def test_review_all_cells_and_regeneration(self):
        raw = q.read(review.DEST / "public_return.json")
        rows, summary = review.review(raw)
        self.assertEqual((len(rows), summary["independent_parents"]), (21, 1))
        self.assertEqual(summary["wave_scheduler_elapsed_sum_seconds"], 3824)
        self.assertEqual(summary["remaining_cells"], 189)
        self.assertTrue(all(r["gap_fraction"] <= 1e-4 for r in rows))
        with self.assertRaisesRegex(ValueError, "f0_return_hash"):
            review.review(raw + b" ")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            review.publish(output)
            review.publish(output)
            for name in (
                "review.json",
                "f0_results.csv",
                "f0_cpu.svg",
                "manifest.json",
            ):
                self.assertEqual(q.read(output / name), q.read(review.DEST / name))

    def test_plan_is_next_six_and_uses_f3_preparation(self):
        frozen = f.plan("a" * 40)
        original, cells = q.first.executor.proposal.build()
        value, ledger, _ = q.first.review.review(
            q.read(q.first.review.DESTINATION / "public_return.json")
        )
        for group, expected in zip(frozen["groups"], original["groups"][7:13]):
            self.assertEqual(group["group"], expected)
            self.assertEqual(
                group["cells"],
                [c for c in cells if c["group_id"] == expected["group_id"]],
            )
            self.assertEqual(
                group["start_binding"]["private_starts_sha256"],
                value["child"]["rows"][1]["private_starts_sha256"],
            )
            self.assertEqual(
                group["preparation_seconds"]["root"],
                ledger[1]["root_supervised_seconds"],
            )
            self.assertNotEqual(
                group["start_binding"]["model_sha256"],
                value["child"]["rows"][0]["model_sha256"],
            )
        self.assertEqual(frozen["maximum_physical_core_hours"], 68)
        self.assertEqual(frozen["campaign_completed_calls_before_this_wave"], 21)
        self.assertEqual(frozen["maximum_optimization_calls"], 18)

    def test_private_inputs_select_f3_index_and_reject_f0(self):
        group = f.plan("a" * 40)["groups"][0]
        first = q.first
        guidance_raw = q.read(first.review.DESTINATION / "public_return.json")
        guidance_review = first.review.review(guidance_raw)
        original, _ = first.executor.proposal.build()
        bindings = group["start_binding"]
        observed = []

        def sha(path):
            observed.append(str(path).replace("\\", "/"))
            return bindings[
                {
                    "graph.private.pt": "graph_sha256",
                    "predictions.private.json": "prediction_sha256",
                    "starts.private.json": "private_starts_sha256",
                    "root.private.json.gz": "root_sha256",
                    "mip-1": "model_sha256",
                }[path.name]
            ]

        with ExitStack() as stack:
            stack.enter_context(patch.object(first, "read", return_value=guidance_raw))
            stack.enter_context(
                patch.object(first.review, "review", return_value=guidance_review)
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
            self.assertEqual(mip, Path("mip-1"))
            self.assertIn("run/1/starts.private.json", starts.as_posix())
            self.assertTrue(all("/run/0/" not in p for p in observed))
            changed = copy.deepcopy(group)
            changed["start_binding"]["private_starts_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "review_binding"):
                first.private_inputs(changed)

    def test_submit_uses_f3_operator_claim_and_serial_order(self):
        self.frozen = f.plan("a" * 40)
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            calls = wave_tests.SixJobs.submit_fixture(self, stage, stack)
            policy = copy.copy(f.POLICY)
            policy.claim = stage / "claim"
            policy.installed_review = lambda: self.frozen["first_review"]
            result = q.submit(stage, q.digest(q.encoded(self.frozen)), policy)
            self.assertEqual(result["job_ids"], [str(900 + i) for i in range(6)])
            for i, call in enumerate(c for c in calls if c[0] == "sbatch"):
                self.assertIn(f"--job-name=cfl_pr86_f3_{i}", call)
            self.assertTrue(
                all(
                    c[-3].endswith("operate_pr86_f3_jobs.sh")
                    for c in calls
                    if c[0] == "sbatch"
                )
            )
            self.assertEqual(q.admitted(stage, self.frozen, policy), result["job_ids"])
            with self.assertRaises(FileExistsError):
                q.submit(stage, q.digest(q.encoded(self.frozen)), policy)

    def test_six_nested_f3_returns_reject_f0_or_dependency_change(self):
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
            bad["returns"][0]["plan"]["start_binding"]["model_sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                q.validate_return(q.encoded(bad), f.POLICY)
            bad = copy.deepcopy(value)
            bad["launch"][1]["held_profile"]["dependency"] = "afterany:900"
            with self.assertRaisesRegex(ValueError, "serial_dependency"):
                q.validate_return(q.encoded(bad), f.POLICY)


if __name__ == "__main__":
    unittest.main()
