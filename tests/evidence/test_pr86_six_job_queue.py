"""Offline dependency/claim/failure tests; no scheduler or solver is invoked."""

import copy
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_six_job_queue as q  # noqa: E402
import test_pr86_main_first_group as fixtures  # noqa: E402
from test_pr86_main_first_group import profile as first_profile  # noqa: E402


def held(job, threads, previous=None):
    value = first_profile(job).replace("CPUs/Task=1", f"CPUs/Task={threads}")
    value = value.replace("NumCPUs=2", f"NumCPUs={threads * 2}")
    value = value.replace("cpu=2,", f"cpu={threads * 2},")
    return value + (
        f" Dependency=afterok:{previous}(unfulfilled)"
        if previous
        else " Dependency=(null)"
    )


class SixJobs(unittest.TestCase):
    def setUp(self):
        self.frozen = q.plan("a" * 40)

    def test_exact_six_next_groups_and_budget(self):
        groups = [p["group"] for p in self.frozen["groups"]]
        self.assertEqual(
            [(g["threads"], g["seed"]) for g in groups],
            [(1, 43), (1, 44), (2, 42), (4, 42), (8, 42), (16, 42)],
        )
        ids = [c["cell_id"] for p in self.frozen["groups"] for c in p["cells"]]
        self.assertEqual(len(set(ids)), 18)
        self.assertNotIn("F0-threads1-seed42-M0", ids)
        self.assertEqual(sum(g["job_wall_seconds"] for g in groups), 86400)
        self.assertEqual(sum(g["threads"] * 4 for g in groups), 128)
        self.assertFalse(self.frozen["dispatch_after_this_wave"])

    def test_pinned_first_review_and_mutated_bytes(self):
        raw = q.read(q.RECEIPT)
        self.assertTrue(q.review_first(raw)["implementation_first_group_review_passed"])
        with self.assertRaisesRegex(ValueError, "original_hash"):
            q.review_first(raw + b" ")

    def test_profiles_require_exact_afterok_and_resources(self):
        for threads in (1, 2, 4, 8, 16):
            self.assertEqual(
                q.profile(held("900", threads, "899"), "900", threads, "899")[
                    "dependency"
                ],
                "afterok:899(unfulfilled)",
            )
        for text in (
            held("900", 1, "898"),
            held("900", 1, "899").replace("afterok", "afterany"),
            held("900", 2, "899"),
        ):
            with self.assertRaises(ValueError):
                q.profile(text, "900", 1, "899")

    def submit_fixture(self, stage, stack, *, fail_submit=None, fail_release=None):
        q.write(stage / "plan.json", self.frozen)
        stack.enter_context(patch.object(q, "CLAIM", stage / "claim"))
        stack.enter_context(patch.object(q, "load", return_value=self.frozen))
        stack.enter_context(
            patch.object(q, "installed_first", return_value=self.frozen["first_review"])
        )
        stack.enter_context(patch.object(q.first.roots.accounting, "host"))
        stack.enter_context(
            patch.object(
                q.first, "private_inputs", return_value=(Path("mip"), Path("starts"))
            )
        )
        stack.enter_context(patch.object(q.first, "bundles"))
        stack.enter_context(
            patch.dict(
                q.os.environ,
                {"CONDA_DEFAULT_ENV": "tfm_env", "SBATCH_NODES": "4", "SRUN_GPUS": "8"},
            )
        )
        calls, jobs = [], []

        def command(args, **kwargs):
            calls.append(args)
            if args[0] == "sbatch":
                index = len(jobs)
                self.assertTrue((stage / "claim/claim.json").exists())
                self.assertTrue(
                    (
                        stage / f"group-{len(self.frozen['groups']) - 1}/approval.json"
                    ).exists()
                )
                self.assertIn("--hold", args)
                self.assertIn("--kill-on-invalid-dep=yes", args)
                self.assertNotIn("SBATCH_NODES", kwargs["env"])
                self.assertNotIn("SRUN_GPUS", kwargs["env"])
                if index:
                    self.assertIn("--dependency=afterok:" + jobs[-1], args)
                if fail_submit == index:
                    raise RuntimeError("uncertain_submission")
                job = str(900 + index)
                jobs.append(job)
                return job
            if args[1] == "show":
                index = int(args[3]) - 900
                return held(
                    args[3],
                    self.frozen["groups"][index]["group"]["threads"],
                    jobs[index - 1] if index else None,
                )
            self.assertTrue((stage / "chain.json").exists())
            if args[2] == fail_release:
                raise RuntimeError("uncertain_release")
            return ""

        stack.enter_context(
            patch.object(q.first.roots.accounting, "command", side_effect=command)
        )
        return calls

    def test_all_held_before_reverse_release_and_no_repeat(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            calls = self.submit_fixture(stage, stack)
            value = q.submit(stage, q.digest(q.encoded(self.frozen)))
            self.assertEqual(value["job_ids"], [str(900 + i) for i in range(6)])
            self.assertEqual(
                calls[-6:], [["scontrol", "release", str(905 - i)] for i in range(6)]
            )
            self.assertEqual(q.admitted(stage, self.frozen), value["job_ids"])
            before = len(calls)
            with self.assertRaises(FileExistsError):
                q.submit(stage, q.digest(q.encoded(self.frozen)))
            self.assertEqual(len(calls), before)

    def test_partial_submission_never_releases_or_retries(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            calls = self.submit_fixture(stage, stack, fail_submit=3)
            with self.assertRaises(RuntimeError):
                q.submit(stage, q.digest(q.encoded(self.frozen)))
            self.assertFalse(any(c[1] == "release" for c in calls))
            self.assertTrue((stage / "group-3/submission.intent.json").exists())
            self.assertFalse((stage / "chain.json").exists())

    def test_partial_release_never_releases_root(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            calls = self.submit_fixture(stage, stack, fail_release="903")
            with self.assertRaises(RuntimeError):
                q.submit(stage, q.digest(q.encoded(self.frozen)))
            self.assertNotIn(["scontrol", "release", "900"], calls)
            self.assertTrue((stage / "chain.json").exists())

    def test_wrong_approval_never_submits(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            calls = self.submit_fixture(stage, stack)
            with self.assertRaisesRegex(ValueError, "approved_plan_sha"):
                q.submit(stage, "0" * 64)
            self.assertEqual(calls, [])

    def test_predecessor_gate_failure_prevents_execution(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            (stage / "group-0").mkdir()
            q.write(stage / "group-0/checked.json", {"altered": True})
            stack.enter_context(patch.object(q, "load", return_value=self.frozen))
            stack.enter_context(
                patch.object(
                    q, "admitted", return_value=[str(900 + i) for i in range(6)]
                )
            )
            stack.enter_context(
                patch.object(q, "checked", return_value={"altered": False})
            )
            stack.enter_context(patch.dict(q.os.environ, {"SLURM_JOB_ID": "901"}))
            allocation = stack.enter_context(
                patch.object(q.first.executor, "allocation")
            )
            with self.assertRaisesRegex(ValueError, "predecessor_gate"):
                q.run(stage, 1)
            allocation.assert_not_called()

    def test_real_admission_for_all_six_caps_and_seeds(self):
        ex = q.first.executor
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    ex.subprocess, "run", return_value=SimpleNamespace(stdout="a" * 40)
                )
            )
            stack.enter_context(
                patch.object(ex.platform, "python_version", return_value="3.10.20")
            )
            stack.enter_context(
                patch.object(
                    ex.importlib.metadata,
                    "version",
                    side_effect=lambda n: self.frozen["groups"][0]["environment"][n],
                )
            )
            stack.enter_context(patch.object(ex, "assignments"))
            for i, group in enumerate(self.frozen["groups"]):
                folder = Path(temp) / str(i)
                folder.mkdir()
                q.write(folder / "approval.json", q.first.approval(group))
                q.first.bundles(
                    group, folder, Path("private-mip"), Path("private-starts")
                )
                requests = q.parsed(folder / "requests.json")
                for cell, ref in zip(group["cells"], requests):
                    bundle = ex.load_bundle(
                        folder / "admission" / ref["file"], ref["sha256"]
                    )
                    self.assertEqual(bundle["cell"], cell)
                    self.assertEqual(bundle["allocation_threads"], cell["threads"])

    def test_return_refuses_extra_jobs_or_changed_scope(self):
        value = {
            "protocol_id": q.PROTOCOL,
            "plan": self.frozen,
            "plan_sha256": q.digest(q.encoded(self.frozen)),
            "returns": [],
            "launch": [],
            "scientific_reporting_eligible": False,
            "raw_logs_included": False,
        }
        with self.assertRaisesRegex(ValueError, "six_returns"):
            q.validate_return(q.encoded(value))
        changed = copy.deepcopy(value)
        changed["raw_logs_included"] = True
        with self.assertRaisesRegex(ValueError, "scope"):
            q.validate_return(q.encoded(changed))

    def test_six_real_nested_returns_and_dependency_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            value = {
                "protocol_id": q.PROTOCOL,
                "plan": self.frozen,
                "plan_sha256": q.digest(q.encoded(self.frozen)),
                "returns": [],
                "launch": [],
                "scientific_reporting_eligible": False,
                "raw_logs_included": False,
            }
            helper = fixtures.MainFirst()
            for i, group in enumerate(self.frozen["groups"]):
                folder = Path(temp) / str(i)
                folder.mkdir()
                helper.frozen = group
                job, previous = str(900 + i), str(899 + i) if i else None
                value["returns"].append(helper.make_return(folder, job=job))
                value["launch"].append(
                    {
                        "job_id": job,
                        "held_profile": q.profile(
                            held(job, group["group"]["threads"], previous),
                            job,
                            group["group"]["threads"],
                            previous,
                        ),
                    }
                )
            self.assertEqual(q.validate_return(q.encoded(value))["complete_groups"], 6)
            bad = copy.deepcopy(value)
            bad["launch"][1]["held_profile"]["dependency"] = "afterany:900"
            with self.assertRaisesRegex(ValueError, "serial_dependency"):
                q.validate_return(q.encoded(bad))
            bad = copy.deepcopy(value)
            bad["returns"][1]["members"].pop("run/attempt-2/child.json")
            with self.assertRaises(ValueError):
                q.validate_return(q.encoded(bad))


if __name__ == "__main__":
    unittest.main()
