"""Synthetic CPU12h qualification: no actual Gurobi, scheduler, GPU or HPC."""

import copy
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/evidence"))
sys.path.insert(0, str(ROOT / "tests/evidence"))
import pr89_cpu_contract as c  # noqa: E402
import pr89_cpu_temporal as temporal  # noqa: E402
import pr89_cpu_workflow as workflow  # noqa: E402
import test_pr86_prospective_executor as fixture  # noqa: E402
import test_pr86_six_job_queue as queue_fixture  # noqa: E402


def item(method="M0", threads=1):
    result = fixture.cell(method, threads)
    result.update(
        parent="CFL_medium_instance_0",
        cell_id=f"M0-threads{threads}-seed42-{method}",
        time_limit_seconds=43200,
    )
    return result


def observations():
    recorder = temporal.Recorder()
    for point in (
        (1, None, 0, "MIP"),
        (3500, 100, 85, "MIP"),
        (3610, 100, 91, "MIP"),
        (15000, 100, 96, "MIP"),
        (30000, 100, 99.5, "MIP"),
        (43201, 100, 99.995, "terminal"),
    ):
        recorder.observe(*point)
    return recorder.finish()


class TemporalTests(unittest.TestCase):
    def test_crossings_and_actual_brackets(self):
        value = temporal.validate(observations())
        self.assertEqual(
            value["first_observed_thresholds"]["0.1"]["crossing"]["first_observed"][
                "seconds"
            ],
            3610,
        )
        self.assertEqual(
            value["first_observed_thresholds"]["0.0001"]["crossing"]["first_observed"][
                "seconds"
            ],
            43201,
        )
        h = value["horizons"]["3600"]
        self.assertEqual(
            (h["before"]["seconds"], h["after"]["seconds"], h["staleness_seconds"]),
            (3500, 3610, 100),
        )
        self.assertEqual(h["state"], "bracketed")

    def test_early_terminal_not_filled_to_12h(self):
        r = temporal.Recorder()
        r.observe(100, 10, 10, "terminal")
        value = temporal.validate(r.finish())
        self.assertTrue(
            all(
                h["state"] == "terminated_before_horizon"
                for h in value["horizons"].values()
            )
        )
        self.assertEqual(
            value["horizons"]["43200"]["terminal_if_earlier"]["seconds"], 100
        )

    def test_exact_horizon_distinct_from_nearby(self):
        r = temporal.Recorder()
        r.observe(3600, 10, 9, "MIP")
        r.observe(4000, 10, 9.5, "terminal")
        value = temporal.validate(r.finish())
        self.assertEqual(value["horizons"]["3600"]["state"], "exact_observation")

    def test_timeout_not_target_time(self):
        r = temporal.Recorder()
        r.observe(43201, 10, 5, "terminal")
        value = temporal.validate(r.finish())
        self.assertTrue(
            all(
                t["state"] == "right_censored" and t["crossing"] is None
                for t in value["first_observed_thresholds"].values()
            )
        )

    def test_infinity_and_zero_objective_are_json_safe(self):
        r = temporal.Recorder()
        r.observe(1, 1e100, -1e100, "MIP")
        r.observe(2, 0, -1, "MIPSOL")
        r.observe(3, 0, 0, "terminal")
        temporal.validate(r.finish())
        c.encoded(r.finish())
        self.assertIsNone(temporal.gap(0, -1))

    def test_no_incumbent_is_not_zero_gap(self):
        r = temporal.Recorder()
        r.observe(2, None, 0, "terminal")
        v = temporal.validate(r.finish())
        self.assertTrue(
            all(
                t["state"] == "unavailable"
                for t in v["first_observed_thresholds"].values()
            )
        )

    def test_missing_terminal_nonmonotonic_or_postterminal_fail(self):
        r = temporal.Recorder()
        with self.assertRaises(ValueError):
            r.finish()
        r.observe(10, 10, 1, "MIP")
        with self.assertRaises(ValueError):
            r.observe(9, 10, 1, "MIP")
        r.observe(11, 10, 1, "terminal")
        with self.assertRaises(ValueError):
            r.observe(12, 10, 1, "MIP")

    def test_tampered_horizon_crossing_scope_and_gap_rejected(self):
        for change in (
            lambda v: v["horizons"]["3600"].update(interpolated=True),
            lambda v: v["horizons"]["3600"].update(state="exact_observation"),
            lambda v: v["first_observed_thresholds"]["0.1"]["crossing"][
                "first_observed"
            ].update(gap_fraction=0),
            lambda v: v.update(numerical_eligibility="certified"),
        ):
            value = observations()
            change(value)
            with self.assertRaises(ValueError):
                temporal.validate(value)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = c.plan("a" * 40)

    def test_sixty_only_seed42_and_budget_arithmetic(self):
        f = self.frozen
        self.assertEqual(len(f["cells"]), 60)
        self.assertEqual(len({v["cell_id"] for v in f["cells"]}), 60)
        self.assertEqual({v["seed"] for v in f["cells"]}, {42})
        self.assertEqual(sum(v["threads"] * 13 for v in f["cells"]), 4836)
        self.assertEqual(sum(v["threads"] * 12 for v in f["cells"]), 4464)
        self.assertFalse(f["resource_budget_approved"])
        self.assertFalse(f["automatic_retry"])
        self.assertEqual(f["new_preparation_calls"], 0)
        self.assertIn("M4", f["numerical_scope_by_alias"])

    def test_same_method_order_and_checkpoint_not_gpu_model(self):
        matrix, _ = c.methodology.cpu_package()
        self.assertEqual(
            [(v["parent"], v["threads"], v["method"]) for v in self.frozen["cells"]],
            [(v["parent"], v["threads"], v["method"]) for v in matrix],
        )
        self.assertTrue(
            all(
                p["start_binding"]["checkpoint_sha256"]
                == c.previous.executor.proposal.CHECKPOINT
                for p in self.frozen["parents"].values()
            )
        )

    def test_preserve_all_historical_parameters_except_limit_and_cap(self):
        baseline = c.baseline_parameters()
        for cap in (1, 2, 4, 8, 16):
            actual = c.parameters(item(threads=cap))
            self.assertEqual(actual, {**baseline, "TimeLimit": 43200, "Threads": cap})
            self.assertGreater(c.CHILD_DEADLINE - actual["TimeLimit"], 900)
            self.assertGreater(c.JOB_WALL, c.CHILD_DEADLINE)

    def test_wrong_seed_parent_sense_or_limit_not_admitted(self):
        for key, value in (
            ("seed", 43),
            ("parent", "CFL_easy_instance_0"),
            ("time_limit_seconds", 3600),
            ("effective_objective_sense", "MAXIMIZE"),
            ("threads", 3),
        ):
            v = item()
            v[key] = value
            with self.assertRaises(ValueError):
                c.parameters(v)

    def test_cpu_specific_approval_not_gpu_or_plan(self):
        approval = c.authorization(self.frozen, "author decision reference")
        c.validate_authorization(self.frozen, approval)
        for key, value in (
            ("budget", {"gpu_hours": 60}),
            ("explicit_user_authorization", False),
            ("plan_sha256", "b" * 64),
            ("automatic_retry", True),
        ):
            changed = copy.deepcopy(approval)
            changed[key] = value
            with self.assertRaises(ValueError):
                c.validate_authorization(self.frozen, changed)

    def test_cpu_decision_preserves_original_bytes_across_windows_checkout(self):
        attributes = (ROOT / ".gitattributes").read_text()
        self.assertIn("docs/evidence/pr89/** -text -whitespace", attributes)

    def test_long_policy_reaches_same_solver_once_all_caps_methods(self):
        fake = fixture.SyntheticSolverTests()
        for cap in (1, 2, 4, 8, 16):
            for method in ("M0", "M1", "M2"):
                value = fake.call_fake(item(method, cap), execution_policy=c)
                c.validate_result(item(method, cap), value)
                self.assertEqual(value["optimization_calls"], 1)
                self.assertEqual(value["parameters"]["TimeLimit"], 43200)
                self.assertEqual(value["temporal_evidence"]["observation_count"], 1)

    def test_public_result_rejects_missing_temporal_or_changed_parameters(self):
        fake = fixture.SyntheticSolverTests()
        value = fake.call_fake(item(), execution_policy=c)
        value["parameters"]["IntFeasTol"] = 0.001
        with self.assertRaises(ValueError):
            c.validate_result(item(), value)


class OperatorTests(unittest.TestCase):
    def test_partition_and_time_limit_parsing(self):
        text = "PartitionName=batch State=UP Nodes=dgx-dasci TotalNodes=1 MaxTime=UNLIMITED"
        context = workflow.partition_context(text)
        self.assertTrue(context["13h_within_displayed_maximum"])
        self.assertFalse(context["submission_permission_proven"])
        self.assertEqual(workflow.wall_seconds("1-01:00:00"), 90000)
        for t in ("12:00:00", "INVALID", "00:99:00"):
            with self.assertRaises(ValueError):
                workflow.partition_context(text.replace("UNLIMITED", t))

    def test_spooled_entry_locates_stage_not_script_directory(self):
        script = (ROOT / "scripts/evidence/operate_pr89_cpu.sh").read_text()
        self.assertIn('SOURCE="$STAGE/source"', script)
        self.assertIn('"$ACTION" != batch', script)
        self.assertNotIn("scontrol", script)
        self.assertIn('"${3:?authorization SHA256}"', script)

    @unittest.skipIf(sys.platform == "win32", "POSIX batch-entry execution in Linux CI")
    def test_spooled_entry_missing_or_wrong_host_fails_without_optimizer(self):
        path = ROOT / "scripts/evidence/operate_pr89_cpu.sh"
        result = subprocess.run(
            ["bash", str(path), "batch", "/tmp/unapproved", "0"],
            capture_output=True,
            check=False,
            env={**os.environ, "CONDA_DEFAULT_ENV": "tfm_env"},
        )
        self.assertNotEqual(result.returncode, 0)

    def test_affinity_observation_loss_stops_guard(self):
        with patch.object(os, "sched_getaffinity", return_value={1, 3}, create=True):
            guard = workflow.AllocationGate(
                type("Gate", (), {"sample": lambda self: 123})()
            )
        with patch.object(os, "sched_getaffinity", return_value={1, 3}, create=True):
            self.assertEqual(guard.sample(), 123)
        with (
            patch.object(os, "sched_getaffinity", return_value={1, 2}, create=True),
            self.assertRaises(ValueError),
        ):
            guard.sample()

    def test_partial_or_ambiguous_submission_never_repeats(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            workflow.folder(stage, 1).mkdir(parents=True)
            c.write(workflow.folder(stage, 1) / "submission.json", {"job_id": "1"})
            with self.assertRaises(ValueError):
                workflow.submitted(stage)


class SubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = c.plan("b" * 40)

    def fixture(self, stage, stack, fail=None):
        approval = c.authorization(self.frozen, "specific human CPU decision")
        sha = c.write(stage / "authorization.json", approval)
        stack.enter_context(patch.object(workflow, "CLAIM", stage / "claim"))
        stack.enter_context(patch.object(workflow, "load", return_value=self.frozen))
        stack.enter_context(
            patch.object(
                c.previous,
                "private_inputs",
                return_value=(Path("model"), Path("starts")),
            )
        )
        stack.enter_context(
            patch.object(workflow, "checkpoint_identity", return_value="c" * 64)
        )
        stack.enter_context(
            patch.dict(os.environ, {"SBATCH_NODES": "2", "SLURM_GPUS": "8"})
        )
        calls, jobs = [], []

        def command(args, **kwargs):
            calls.append(args)
            if args[0] == "sbatch":
                self.assertNotIn("SBATCH_NODES", kwargs["env"])
                self.assertNotIn("SLURM_GPUS", kwargs["env"])
                self.assertIn("--nodes=1-1", args)
                self.assertIn("--time=13:00:00", args)
                self.assertIn("--hold", args)
                self.assertIn("--no-requeue", args)
                self.assertNotIn("--exclusive", args)
                if fail == len(jobs):
                    raise RuntimeError("ambiguous_sbatch")
                if jobs:
                    self.assertIn("--dependency=afterok:" + jobs[-1], args)
                jobs.append(str(1000 + len(jobs)))
                return jobs[-1]
            if args[:3] == ["scontrol", "show", "partition"]:
                return "PartitionName=batch State=UP Nodes=dgx-dasci TotalNodes=1 MaxTime=UNLIMITED"
            if args[:3] == ["scontrol", "show", "job"]:
                i = int(args[3]) - 1000
                return queue_fixture.held(
                    args[3],
                    self.frozen["cells"][i]["threads"],
                    jobs[i - 1] if i else None,
                ).replace("04:00:00", "13:00:00")
            if args[:2] == ["scontrol", "release"]:
                return ""
            self.fail("unexpected scheduler command")

        stack.enter_context(
            patch.object(workflow.accounting, "command", side_effect=command)
        )
        return sha, calls, jobs

    def test_six_held_jobs_released_tail_first_without_wait(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            sha, calls, jobs = self.fixture(stage, stack)
            result = workflow.submit(stage, sha, 6)
            self.assertEqual(result["remaining_unsubmitted"], 54)
            self.assertEqual(
                [a[2] for a in calls if a[:2] == ["scontrol", "release"]],
                list(reversed(jobs)),
            )
            self.assertEqual(len(workflow.submitted(stage)), 6)
            before = len(calls)
            with self.assertRaises((FileExistsError, ValueError)):
                workflow.submit(stage, sha, 6)
            self.assertFalse(any(a[0] == "sbatch" for a in calls[before:]))

    def test_partial_ambiguous_submission_preserves_claim_and_no_release(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            sha, calls, jobs = self.fixture(stage, stack, fail=2)
            with self.assertRaises(RuntimeError):
                workflow.submit(stage, sha, 6)
            self.assertEqual(len(jobs), 2)
            self.assertTrue((stage / "claim/claim.json").exists())
            self.assertTrue(
                (workflow.folder(stage, 2) / "submission.intent.json").exists()
            )
            self.assertFalse(any(a[:2] == ["scontrol", "release"] for a in calls))
            before = len(calls)
            with self.assertRaises((FileNotFoundError, ValueError)):
                workflow.submit(stage, sha, 6)
            self.assertFalse(any(a[0] == "sbatch" for a in calls[before:]))

    def test_wrong_authorization_never_mutates_scheduler(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            _, calls, _ = self.fixture(stage, stack)
            with self.assertRaises(ValueError):
                workflow.submit(stage, "0" * 64, 6)
            self.assertEqual(calls, [])

    def test_held_profile_rejects_nodes_gpu_requeue_wall_dependency_changes(self):
        text = queue_fixture.held("1000", 16, "999").replace("04:00:00", "13:00:00")
        workflow.held(text, "1000", 16, "999")
        for value in (
            text.replace("NumNodes=1-1", "NumNodes=2"),
            text.replace("Requeue=0", "Requeue=1"),
            text.replace("13:00:00", "12:00:00"),
            text.replace("afterok", "afterany"),
            text.replace("mem=64G,", "gres/gpu=1,mem=64G,"),
        ):
            if value == text:
                continue
            with self.assertRaises(ValueError):
                workflow.held(value, "1000", 16, "999")

    def test_all_sixty_fit_same_operator_without_new_wave_code(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            sha, calls, jobs = self.fixture(stage, stack)
            result = workflow.submit(stage, sha, 60)
            self.assertEqual(len(jobs), 60)
            self.assertEqual(result["remaining_unsubmitted"], 0)
            self.assertEqual(len([a for a in calls if a[0] == "sbatch"]), 60)
            self.assertEqual(
                [a[2] for a in calls if a[:2] == ["scontrol", "release"]],
                list(reversed(jobs)),
            )

    def test_status_uses_one_accounting_query_not_a_wait_loop(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(workflow, "load", return_value=self.frozen)
            )
            stack.enter_context(patch.object(workflow, "admitted"))
            stack.enter_context(
                patch.object(
                    workflow,
                    "submitted",
                    return_value=[{"job_id": "900"}, {"job_id": "901"}],
                )
            )
            query = stack.enter_context(
                patch.object(
                    workflow.accounting,
                    "command",
                    return_value="900|COMPLETED|0:0|100|01:00|2|64G|\n901|PENDING|0:0|0|00:00|1|64G|\n",
                )
            )
            result = workflow.status(Path("synthetic"))
            self.assertEqual(query.call_count, 1)
            self.assertFalse(result["terminal"])
            self.assertEqual(result["submitted"], 2)

    def test_no_preflight_no_runtime_authorization(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(workflow, "load", return_value=self.frozen),
        ):
            stage = Path(temp)
            sha = c.write(stage / "plan.json", self.frozen)
            with self.assertRaises((ValueError, FileNotFoundError)):
                workflow.authorize(stage, sha, "author approved")
            self.assertFalse((stage / "authorization.json").exists())


class ReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = c.plan("c" * 40)
        cls.frozen["cells"][0] = item()

    def value(self):
        frozen = copy.deepcopy(self.frozen)
        result = fixture.SyntheticSolverTests().call_fake(item(), execution_policy=c)
        plan_sha = c.digest(c.encoded(frozen))
        child = {"cell": frozen["cells"][0], "plan_sha256": plan_sha, "result": result}
        supervisor = {
            "job_id": "900",
            "observation": {
                "guard_stop": None,
                "child_exit_code": 0,
                "supervisor_wall_seconds": 2,
            },
        }
        costs = workflow.attempt_costs(frozen, 0, child, supervisor)
        return {
            "protocol_id": c.PROTOCOL,
            "plan": frozen,
            "plan_sha256": plan_sha,
            "authorization": c.authorization(frozen, "author decision"),
            "raw_logs_included": False,
            "scientific_reporting_eligible": False,
            "remaining_dispatch_admitted": False,
            "complete_cells": 1,
            "rows": [
                {
                    "cell": frozen["cells"][0],
                    "child": child,
                    "supervision": supervisor,
                    "costs": costs,
                    "complete": True,
                    "accounting": workflow.accounting.parse_accounting(
                        "900|COMPLETED|0:0|100|01:00|2|64G|", "900"
                    ),
                    "checked": {
                        "plan_sha256": plan_sha,
                        "index": 0,
                        "complete": True,
                        "scientific_reporting_eligible": False,
                        "child_sha256": c.digest(c.encoded(child)),
                        "supervision_sha256": c.digest(c.encoded(supervisor)),
                        "costs_sha256": c.digest(c.encoded(costs)),
                    },
                }
            ],
        }

    def review(self, value):
        raw = c.encoded(value)
        with patch.object(c, "plan", return_value=self.frozen):
            return workflow.review_return(raw, c.digest(raw))

    def test_complete_nested_return_and_failed_envelope_are_distinct(self):
        value = self.value()
        self.assertEqual(self.review(value)["complete_cells"], 1)
        value["rows"][0].update(
            complete=False,
            child=None,
            checked=None,
            supervision=None,
            accounting=workflow.accounting.parse_accounting(
                "900|FAILED|2:0|1|00:00|2|64G|", "900"
            ),
        )
        value["complete_cells"] = 0
        self.assertEqual(self.review(value)["complete_cells"], 0)

    def test_hash_cell_parameter_accounting_or_nested_seal_tampering_rejected(self):
        for change in (
            lambda v: v.update(complete_cells=2),
            lambda v: v["rows"][0]["checked"].update(child_sha256="0" * 64),
            lambda v: v["rows"][0]["accounting"].update(terminal=False),
            lambda v: v["rows"][0]["child"]["result"]["parameters"].update(
                TimeLimit=3600
            ),
            lambda v: v.update(scientific_reporting_eligible=True),
        ):
            v = self.value()
            change(v)
            with self.assertRaises(ValueError):
                self.review(v)

    def test_scp_batch_is_single_connection_and_source_pin_explicit(self):
        source = (ROOT / "scripts/evidence/receive_pr89_cpu.ps1").read_text()
        self.assertEqual(source.count("& scp "), 1)
        self.assertNotIn("Read-Host", source)
        self.assertIn("$SourceCommit.Substring(0,12)", source)


if __name__ == "__main__":
    unittest.main()
