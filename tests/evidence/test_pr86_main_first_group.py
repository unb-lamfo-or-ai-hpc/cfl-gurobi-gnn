"""Exercise real admission and nested return arithmetic with fake external IO."""

import base64
import copy
import itertools
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_main_first_group as flow  # noqa: E402
from test_pr86_prospective_executor import successful_result  # noqa: E402


def profile(job="999"):
    return f"JobId={job} JobState=PENDING Reason=JobHeldUser Partition=batch Requeue=0 Restarts=0 NumTasks=1 CPUs/Task=1 TimeLimit=04:00:00 NumNodes=1-1 NumCPUs=2 MinMemoryNode=64G OverSubscribe=OK TRES=cpu=2,mem=64G,node=1,billing=2"


class MainFirst(unittest.TestCase):
    def setUp(self):
        self.frozen = flow.plan("a" * 40)

    def test_first_group_is_inside_fixed_budget(self):
        p = self.frozen
        self.assertEqual(p["group"]["group_id"], flow.GROUP)
        self.assertEqual([c["method"] for c in p["cells"]], ["M0", "M1", "M2"])
        self.assertEqual(p["maximum_optimization_calls"], 3)
        self.assertFalse(p["remaining_dispatch_admitted"])
        self.assertFalse(p["resource_budget_approved"])
        self.assertEqual(flow.approval(p)["approved_campaign_calls_ceiling"], 210)
        self.assertEqual(
            p["environment"],
            {"python": "3.10.20", "numpy": "1.26.4", "gurobipy": "13.0.1"},
        )

    def test_held_profile_accepts_slurm_range_but_rejects_wider_resources(self):
        self.assertEqual(flow.held_profile(profile(), "999")["NumNodes"], "1-1")
        for old, new in (
            ("NumNodes=1-1", "NumNodes=1-2"),
            ("NumCPUs=2", "NumCPUs=80"),
            ("CPUs/Task=1", "CPUs/Task=16"),
            ("Restarts=0", "Restarts=1"),
            ("TimeLimit=04:00:00", "TimeLimit=05:00:00"),
            ("node=1,billing=2", "node=1,gres/gpu=1"),
        ):
            with self.subTest(new=new), self.assertRaises(ValueError):
                flow.held_profile(profile().replace(old, new), "999")

    def test_submission_claim_precedes_sbatch_and_survives_uncertain_outcome(self):
        for outcome in (RuntimeError("ambiguous"), "999", "garbled"):
            with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
                stage = Path(temp) / "stage"
                stage.mkdir()
                flow.write(stage / "plan.json", self.frozen)
                claim = Path(temp) / "claim"
                stack.enter_context(patch.object(flow, "CLAIM", claim))
                stack.enter_context(patch.object(flow.roots.accounting, "host"))
                stack.enter_context(
                    patch.object(flow, "load", return_value=self.frozen)
                )
                stack.enter_context(
                    patch.object(
                        flow,
                        "private_inputs",
                        return_value=(Path("mip"), Path("starts")),
                    )
                )
                stack.enter_context(patch.object(flow, "bundles"))
                stack.enter_context(
                    patch.dict(
                        flow.os.environ,
                        {
                            "CONDA_DEFAULT_ENV": "tfm_env",
                            "SBATCH_NODES": "9",
                            "SRUN_GPUS": "8",
                        },
                    )
                )
                calls = []

                def command(args, **kwargs):
                    calls.append(args)
                    if args[0] == "sbatch":
                        self.assertTrue((claim / "claim.json").is_file())
                        self.assertTrue((stage / "approval.json").is_file())
                        self.assertIn("--hold", args)
                        self.assertNotIn("SBATCH_NODES", kwargs["env"])
                        self.assertNotIn("SRUN_GPUS", kwargs["env"])
                        if isinstance(outcome, Exception):
                            raise outcome
                        return outcome
                    if args[1] == "show":
                        self.assertTrue((stage / "submission.json").is_file())
                        return profile()
                    self.assertTrue((stage / "held_profile.json").is_file())
                    return ""

                stack.enter_context(
                    patch.object(flow.roots.accounting, "command", side_effect=command)
                )
                sha = flow.digest(flow.read(stage / "plan.json"))
                if outcome == "999":
                    self.assertEqual(flow.submit(stage, sha)["job_id"], "999")
                    self.assertEqual(calls[-1], ["scontrol", "release", "999"])
                else:
                    with self.assertRaises((ValueError, RuntimeError)):
                        flow.submit(stage, sha)
                    self.assertEqual(len(calls), 1)
                with self.assertRaises(FileExistsError):
                    flow.submit(stage, sha)

    def test_wrong_approval_never_submits_or_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            flow.write(stage / "plan.json", self.frozen)
            with (
                patch.object(flow.roots.accounting, "host"),
                patch.object(flow, "load", return_value=self.frozen),
                patch.dict(flow.os.environ, {"CONDA_DEFAULT_ENV": "tfm_env"}),
                patch.object(flow.roots.accounting, "command") as command,
                self.assertRaisesRegex(ValueError, "approved_plan_sha"),
            ):
                flow.submit(stage, "b" * 64)
            command.assert_not_called()

    def test_real_bundle_admission_checks_all_three_methods(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stage = Path(temp)
            flow.write(stage / "approval.json", flow.approval(self.frozen))
            ex = flow.executor
            stack.enter_context(
                patch.object(
                    ex.existing,
                    "dependencies",
                    return_value=self.frozen["source_sha256_lf"],
                )
            )
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
                    side_effect=lambda name: self.frozen["environment"][name],
                )
            )
            assign = stack.enter_context(patch.object(ex, "assignments"))
            flow.bundles(
                self.frozen, stage, Path("private-mip"), Path("private-starts")
            )
            self.assertEqual(assign.call_count, 3)
            requests = flow.parsed(stage / "requests.json")
            for item in requests:
                value = ex.load_bundle(
                    stage / "admission" / item["file"], item["sha256"]
                )
                self.assertEqual(value["context"], self.frozen["context"])
            self.assertEqual(
                flow.parsed(stage / "admission/resource_approval.json")[
                    "maximum_optimization_calls"
                ],
                3,
            )

    def make_return(self, stage):
        members = {}
        rows = []
        for i, cell in enumerate(self.frozen["cells"]):
            folder = stage / "run" / f"attempt-{i}"
            folder.parent.mkdir(exist_ok=True)
            result = successful_result(cell)
            result["mathematical_signature_sha256"] = "f" * 64
            binding = self.frozen["start_binding"]
            result["start"] = {
                "status": "not_submitted" if i == 0 else "accepted",
                "submitted_assignments": 0 if i == 0 else binding["selected_support"],
                "positive_assignments": 0
                if i == 0
                else binding["positive_assignments"],
                "assignment_sha256": ""
                if i == 0
                else binding[cell["method"] + "_assignment_sha256"],
            }
            observation = {
                "supervisor_wall_seconds": 0.5,
                "child_exit_code": 0,
                "guard_stop": None,
            }

            def dispatch(path, claim):
                claim()
                return observation, result

            ticks = itertools.count()
            report = flow.executor.metered.observe_attempt(
                folder,
                cell,
                self.frozen["context"],
                dispatch=dispatch,
                clock=lambda: next(ticks),
            )
            flow.write(
                folder / "child.json",
                {
                    "cell_sha256": flow.digest(flow.encoded(cell)),
                    "result": result,
                    "gurobi_log": {},
                },
            )
            flow.write(
                folder / "supervision.json",
                {"job_id": "999", "observation": observation},
            )
            measured = flow.executor.supervised.reconcile(
                observation, result, cell["method"], self.frozen["preparation_seconds"]
            )
            flow.write(folder / "prepared_costs.json", {"measurement": measured})
            rows.append(
                {
                    "cell_id": cell["cell_id"],
                    "attempt_sha256": flow.digest(flow.read(folder / "attempt.json")),
                    "stop_code": report["stop_code"],
                }
            )
        flow.write(
            stage / "run/group.started.json",
            {"group_id": flow.GROUP, "bundle_sha256": ["a" * 64] * 3},
        )
        flow.write(
            stage / "run/group.json",
            {
                "group_id": flow.GROUP,
                "attempts": rows,
                "complete": True,
                "stop_code": None,
                "pause_remaining_matrix": False,
                "scientific_reporting_eligible": False,
            },
        )
        flow.write(stage / "batch.json", {"job_id": "999"})
        for path in stage.rglob("*.json"):
            if path.name == "optimize.intent.json":
                continue
            raw = path.read_bytes()
            members[path.relative_to(stage).as_posix()] = {
                "sha256": flow.digest(raw),
                "base64": base64.b64encode(raw).decode(),
            }
        return {
            "protocol_id": flow.PROTOCOL,
            "plan": self.frozen,
            "plan_sha256": flow.digest(flow.encoded(self.frozen)),
            "accounting": flow.roots.accounting.parse_accounting(
                "999|COMPLETED|0:0|10|00:00:09|2|64G|", "999"
            ),
            "members": members,
            "raw_logs_included": False,
            "scientific_reporting_eligible": False,
            "remaining_dispatch_admitted": False,
        }

    def test_nested_three_method_return_and_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            value = self.make_return(Path(temp))
            self.assertTrue(flow.validate_return(flow.encoded(value)))
            changed = copy.deepcopy(value)
            name = "run/attempt-0/attempt.json"
            original = flow.executor.existing.review.flow.meta.strict_json(
                base64.b64decode(changed["members"][name]["base64"])
            )
            original["measurement"]["solver_function_seconds"] += 1
            raw = flow.encoded(original)
            changed["members"][name] = {
                "sha256": flow.digest(raw),
                "base64": base64.b64encode(raw).decode(),
            }
            for member_name, mutate in (
                (
                    "run/attempt-0/timing_tail.json",
                    lambda v: v.update(attempt_sha256=flow.digest(raw)),
                ),
                (
                    "run/group.json",
                    lambda v: v["attempts"][0].update(attempt_sha256=flow.digest(raw)),
                ),
            ):
                member = flow.executor.existing.review.flow.meta.strict_json(
                    base64.b64decode(changed["members"][member_name]["base64"])
                )
                mutate(member)
                updated = flow.encoded(member)
                changed["members"][member_name] = {
                    "sha256": flow.digest(updated),
                    "base64": base64.b64encode(updated).decode(),
                }
            with self.assertRaisesRegex(
                ValueError, "attempt_measurement_reconciliation"
            ):
                flow.validate_return(flow.encoded(changed))
            for mutation in (
                lambda v: v["members"].update({"../private.log": {}}),
                lambda v: v["members"]["batch.json"].update(sha256="0" * 64),
                lambda v: v["plan"].update(maximum_optimization_calls=4),
                lambda v: v["members"].pop("run/attempt-2/child.json"),
                lambda v: v.update(remaining_dispatch_admitted=True),
            ):
                changed = copy.deepcopy(value)
                mutation(changed)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    flow.validate_return(flow.encoded(changed))

    def test_empty_failed_return_preserves_failure_not_zero_cost(self):
        value = {
            "protocol_id": flow.PROTOCOL,
            "plan": self.frozen,
            "plan_sha256": flow.digest(flow.encoded(self.frozen)),
            "accounting": flow.roots.accounting.parse_accounting(
                "999|FAILED|2:0|1|00:00:00|2|64G|", "999"
            ),
            "members": {},
            "raw_logs_included": False,
            "scientific_reporting_eligible": False,
            "remaining_dispatch_admitted": False,
        }
        self.assertFalse(flow.validate_return(flow.encoded(value)))


if __name__ == "__main__":
    unittest.main()
