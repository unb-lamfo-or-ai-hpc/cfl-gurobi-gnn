"""Synthetic PR94 evaluation safety: no Gurobi, Torch, scheduler or HPC calls."""

import ast
import copy
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import pr94_evaluation_contract as contract  # noqa: E402
import pr94_evaluation_workflow as flow  # noqa: E402


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contract.encoded(value))


def start_fixture(abstained=False):
    r = [] if abstained else [{"variable_name": "root_choice", "value": 1}]
    g = [] if abstained else [{"variable_name": "neural_choice", "value": 1}]
    binding = {
        "binary_variables": 10,
        "selected_support": 0 if abstained else 1,
        "positive_assignments": 0 if abstained else 1,
        "abstained": abstained,
        "M1_assignment_sha256": contract.sha(
            json.dumps(r, sort_keys=True, separators=(",", ":")).encode()
        ),
        "M2_assignment_sha256": contract.sha(
            json.dumps(g, sort_keys=True, separators=(",", ":")).encode()
        ),
    }
    return binding, {"root_lp": {"assignments": r}, "gnn": {"assignments": g}}


class ContractTests(unittest.TestCase):
    def test_all_144_native_cells_admit_their_own_seed_and_identity(self):
        _, cells = contract.matrix()
        self.assertEqual(len(cells), 144)
        for cell in cells.values():
            p = contract.parameters(cell)
            self.assertEqual(p["Seed"], cell["seed"])
            self.assertEqual(p["Threads"], 1)
            self.assertEqual(p["TimeLimit"], 3600)
        self.assertEqual(
            sum(c["parent"] == "CFL_medium_instance_7" for c in cells.values()), 9
        )

    def test_changed_identity_or_resource_cannot_be_relabelled_as_planned(self):
        original = next(iter(contract.matrix()[1].values()))
        for key, value in (
            ("parent", "CFL_medium_instance_90"),
            ("seed", 45),
            ("threads", 4),
            ("model_sha256", "0" * 64),
            ("time_limit_seconds", 43200),
            ("method", "M2"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                contract.parameters({**original, key: value})

    def test_bool_is_not_a_physical_thread_parameter(self):
        cell = next(iter(contract.matrix()[1].values()))
        with self.assertRaisesRegex(ValueError, "typed_parameters"):
            contract.parameters({**cell, "threads": True})

    def test_R_and_G_match_cardinality_and_positives_not_selected_names(self):
        binding, starts = start_fixture()
        contract.validate_start(binding, starts)
        self.assertNotEqual(starts["root_lp"], starts["gnn"])

    def test_two_empty_starts_preserve_abstention_without_reselection(self):
        binding, starts = start_fixture(True)
        contract.validate_start(binding, starts)
        with self.assertRaises(ValueError):
            contract.validate_start({**binding, "abstained": False}, starts)

    def test_tampered_assignment_or_support_is_rejected(self):
        binding, starts = start_fixture()
        for candidate in (
            {**binding, "selected_support": 2},
            {**binding, "positive_assignments": 0},
            {**binding, "M1_assignment_sha256": "0" * 64},
        ):
            with self.assertRaises(ValueError):
                contract.validate_start(candidate, starts)

    def test_observed_threshold_can_be_available_while_terminal_target_is_censored(
        self,
    ):
        recorder = contract.Recorder()
        recorder.observe(10, 100, 89, "MIP")
        recorder.observe(20, 100, 95, "MIP")
        recorder.observe(3600.5, 100, 98, "terminal")
        value = recorder.finish()
        self.assertEqual(value["analysis_horizons_seconds"], [3600])
        self.assertTrue(value["later_horizons_are_outside_evaluation_budget"])
        self.assertIsNotNone(recorder.crossings["0.1"])
        self.assertIsNone(recorder.crossings["0.0001"])

    def test_isolated_solver_changes_only_documentation_and_explicit_empty_Start_gate(
        self,
    ):
        reference = ast.parse(
            (
                ROOT
                / "docs/research/solver-seed-extension-v2/pr89-solver-reference.py.txt"
            ).read_text()
        )
        derived = ast.parse(
            (ROOT / "scripts/evidence/pr94_evaluation_solver.py").read_text()
        )
        derived.body[0] = copy.deepcopy(reference.body[0])
        for module in (reference, derived):
            imports = [
                n for n in module.body if isinstance(n, (ast.Import, ast.ImportFrom))
            ]
            module.body = sorted(imports, key=ast.dump) + [
                n
                for n in module.body
                if not isinstance(n, (ast.Import, ast.ImportFrom))
            ]

        class ChangeEmptyStart(ast.NodeTransformer):
            count = 0

            def visit_UnaryOp(self, node):
                if (
                    isinstance(node.op, ast.Not)
                    and isinstance(node.operand, ast.Name)
                    and node.operand.id == "assignments"
                ):
                    self.count += 1
                    return ast.parse(
                        "not assignments and not (execution_policy and execution_policy.ALLOW_ABSTENTION)",
                        mode="eval",
                    ).body
                return self.generic_visit(node)

        transform = ChangeEmptyStart()
        expected = transform.visit(reference)
        self.assertEqual(transform.count, 1)
        self.assertEqual(
            ast.dump(derived, include_attributes=False),
            ast.dump(expected, include_attributes=False),
        )


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage = Path(self.tmp.name) / "stage"
        for p in (self.stage, self.stage / "claims", self.stage / "run"):
            p.mkdir(exist_ok=True)
        self.plan = {
            "source": {"commit": "a" * 40},
            "groups": copy.deepcopy(contract.matrix()[0]["groups"]),
            "bindings": {},
        }
        dump(self.stage / "plan.json", self.plan)
        dump(self.stage / "inputs.private.json", {})
        self.plan_sha = flow.file_sha(self.stage / "plan.json")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target, value in (
            ("load", self.plan),
            ("storage", {}),
            ("verify_inputs", {}),
        ):
            self.stack.enter_context(patch.object(flow, target, return_value=value))
        self.stack.enter_context(patch.object(flow.prep, "host"))
        self.stack.enter_context(patch.object(flow, "site_preflight", return_value={}))
        self.stack.enter_context(
            patch.object(flow, "CLAIM", self.stage.parent / "global.claim.json")
        )
        self.commands, self.events = [], []

    def scheduler(self, args, **kwargs):
        self.commands.append((args, kwargs))
        if args[0] == "sbatch":
            self.events.append("submit")
            return str(8000 + sum(c[0][0] == "sbatch" for c in self.commands) - 1)
        self.events.append("release")
        return ""

    def test_all_48_jobs_are_held_and_checked_before_tail_first_release(self):
        def profile(job, prior):
            self.events.append("profile")
            return {"job_id": job, "predecessor": prior}

        with (
            patch.object(flow, "command", side_effect=self.scheduler),
            patch.object(flow, "held_profile", side_effect=profile),
        ):
            result = flow.submit(self.stage, self.plan_sha)
        self.assertEqual(len(result["jobs"]), 48)
        self.assertEqual(self.events[:96], ["submit", "profile"] * 48)
        self.assertEqual(self.events[96:], ["release"] * 48)
        releases = [
            args[-1] for args, _ in self.commands if args[:2] == ["scontrol", "release"]
        ]
        self.assertEqual(releases, [str(i) for i in reversed(range(8000, 8048))])
        for index, (args, _) in enumerate(
            c for c in self.commands if c[0][0] == "sbatch"
        ):
            self.assertIn("--hold", args)
            self.assertIn("--cpus-per-task=1", args)
            self.assertIn("--mem=64G", args)
            if index < 4:
                self.assertFalse(any(x.startswith("--dependency") for x in args))
            else:
                self.assertIn("--dependency=afterok:" + str(8000 + index - 4), args)

    def test_injected_SBATCH_SLURM_and_python_environment_are_removed(self):
        injected = {
            "SBATCH_MEM_PER_NODE": "1T",
            "SLURM_JOB_ID": "999",
            "SRUN_CPUS_PER_TASK": "80",
            "PYTHONPATH": "/bad",
        }
        with (
            patch.dict(os.environ, injected),
            patch.object(flow, "command", side_effect=self.scheduler),
            patch.object(flow, "held_profile", return_value={}),
        ):
            flow.submit(self.stage, self.plan_sha)
        for args, kw in self.commands:
            if args[0] == "sbatch":
                self.assertTrue(set(injected).isdisjoint(kw["env"]))

    def test_changed_plan_blocks_before_any_claim_or_submission(self):
        with (
            patch.object(flow, "command") as cmd,
            self.assertRaisesRegex(ValueError, "accepted_evaluation_plan"),
        ):
            flow.submit(self.stage, "0" * 64)
        cmd.assert_not_called()
        self.assertFalse(flow.CLAIM.exists())

    def test_ambiguous_third_reply_preserves_two_ids_and_never_releases_or_retries(
        self,
    ):
        calls = 0

        def scheduler(args, **kwargs):
            nonlocal calls
            calls += 1
            return str(8000 + calls) if calls < 3 else "unconfirmed response"

        with (
            patch.object(flow, "command", side_effect=scheduler),
            patch.object(flow, "held_profile", return_value={}),
        ):
            with self.assertRaisesRegex(ValueError, "ambiguous_sbatch"):
                flow.submit(self.stage, self.plan_sha)
            self.assertEqual(calls, 3)
            self.assertTrue((self.stage / "claims/submitted-1.json").exists())
            self.assertFalse((self.stage / "claims/submitted-2.json").exists())
            self.assertTrue((self.stage / "claims/submit-2.json").exists())
            with self.assertRaises(FileExistsError):
                flow.submit(self.stage, self.plan_sha)
            self.assertEqual(calls, 3)
        self.assertFalse((self.stage / "submission.json").exists())

    def test_bad_held_profile_preserves_the_returned_id_and_no_release(self):
        with (
            patch.object(flow, "command", side_effect=self.scheduler),
            patch.object(flow, "held_profile", side_effect=ValueError("held_memory")),
            self.assertRaisesRegex(ValueError, "held_memory"),
        ):
            flow.submit(self.stage, self.plan_sha)
        self.assertTrue((self.stage / "claims/submitted-0.json").exists())
        self.assertEqual(self.events, ["submit"])

    def test_second_invocation_after_success_is_not_a_release_or_submit_retry(self):
        with (
            patch.object(flow, "command", side_effect=self.scheduler),
            patch.object(flow, "held_profile", return_value={}),
        ):
            flow.submit(self.stage, self.plan_sha)
            count = len(self.commands)
            with self.assertRaises(FileExistsError):
                flow.submit(self.stage, self.plan_sha)
            self.assertEqual(len(self.commands), count)


class ProfileTests(unittest.TestCase):
    def profile(self, **changes):
        fields = dict(
            JobId="8000",
            UserId="vrcelestino(123)",
            JobState="PENDING",
            Reason="JobHeldUser",
            Partition="batch",
            NumTasks="1",
            NumCPUs="2",
            Requeue="0",
            TimeLimit="04:00:00",
            MinCPUsNode="1",
            NumNodes="1-1",
            ReqNodeList="dgx-dasci",
            **{"CPUs/Task": "1"},
            MinMemoryNode="64G",
            ReqTRES="cpu=1,mem=64G,node=1",
            Dependency="(null)",
            TresPerNode="(null)",
        )
        fields.update(changes)
        return " ".join(k + "=" + v for k, v in fields.items())

    def test_exact_CPU_resource_profile_is_accepted(self):
        with patch.object(flow, "command", return_value=self.profile()):
            self.assertTrue(flow.held_profile("8000", None)["resource_profile_checked"])

    def test_wrong_owner_memory_GPU_or_wall_never_releases(self):
        for key, value in (
            ("UserId", "someone(7)"),
            ("MinMemoryNode", "1G"),
            ("ReqTRES", "gres/gpu=1"),
            ("TimeLimit", "12:00:00"),
            ("NumNodes", "2"),
            ("Requeue", "1"),
        ):
            with (
                self.subTest(key=key),
                patch.object(
                    flow, "command", return_value=self.profile(**{key: value})
                ),
                self.assertRaises(ValueError),
            ):
                flow.held_profile("8000", None)

    def test_dependency_must_point_to_the_recorded_same_lane_predecessor(self):
        with patch.object(
            flow,
            "command",
            return_value=self.profile(Dependency="afterok:7996(unfulfilled)"),
        ):
            flow.held_profile("8000", "7996")
            with self.assertRaisesRegex(ValueError, "held_dependency"):
                flow.held_profile("8000", "7995")


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage = Path(self.tmp.name)
        (self.stage / "run").mkdir()
        (self.stage / "claims").mkdir()
        self.plan = {
            "groups": copy.deepcopy(contract.matrix()[0]["groups"]),
            "bindings": {},
        }
        dump(self.stage / "plan.json", self.plan)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in ("load",):
            self.stack.enter_context(patch.object(flow, name, return_value=self.plan))
        for name in ("approved", "check_group_job", "storage", "verify_affinity"):
            self.stack.enter_context(patch.object(flow, name))
        self.stack.enter_context(
            patch.object(
                flow,
                "allocation",
                return_value=(
                    "8000",
                    types.SimpleNamespace(sample=lambda: 1),
                    {"pinned_logical_CPUs": [0]},
                ),
            )
        )
        self.stack.enter_context(patch.object(contract, "validate_result"))
        self.calls = 0
        for c in contract.matrix()[1].values():
            self.plan["bindings"][c["parent"]] = {}

    def supervisor(self, args, console, deadline, gate):
        self.calls += 1
        cell_id = args[-1]
        result = {
            "mathematical_signature_sha256": "same",
            "parameters": {"Seed": 42},
            "gate_status": "passed",
        }
        dump(
            console.parent / "child.json",
            {
                "cell": contract.matrix()[1][cell_id],
                "plan_sha256": flow.file_sha(self.stage / "plan.json"),
                "result": result,
            },
        )
        return {"child_exit_code": 0, "guard_stop": None, "supervisor_wall_seconds": 1}

    def modules(self, supervisor):
        return patch.dict(
            sys.modules,
            {
                "paired_memory_runtime_v2": types.SimpleNamespace(supervise=supervisor),
                "pr86_supervised_costs": types.SimpleNamespace(
                    reconcile=lambda *a, **k: {"uses": k["uses"]}
                ),
            },
        )

    def test_three_fresh_children_in_frozen_group_order(self):
        with self.modules(self.supervisor):
            flow.run(self.stage, 0)
        result = flow.read(self.stage / "run/0/group.json")
        self.assertTrue(result["complete"])
        self.assertEqual(
            [r["cell_id"] for r in result["rows"]], self.plan["groups"][0]["cells"]
        )
        self.assertEqual(self.calls, 3)

    def test_memory_or_child_failure_stops_the_remaining_arms(self):
        def fail(*args):
            self.calls += 1
            return {"child_exit_code": -15, "guard_stop": "memory_guard_stop"}

        with self.modules(fail), self.assertRaisesRegex(ValueError, "child_stopped"):
            flow.run(self.stage, 0)
        self.assertEqual(self.calls, 1)
        result = flow.read(self.stage / "run/0/group.json")
        self.assertFalse(result["complete"])
        self.assertEqual(result["rows"], [])
        self.assertTrue(
            (
                self.stage
                / "run"
                / self.plan["groups"][0]["cells"][0]
                / "supervision.json"
            ).exists()
        )

    def test_different_model_signature_stops_before_third_arm(self):
        def different(*args):
            value = self.supervisor(*args)
            if self.calls == 2:
                p = args[1].parent / "child.json"
                raw = flow.read(p)
                raw["result"]["mathematical_signature_sha256"] = "different"
                dump(p, raw)
            return value

        with (
            self.modules(different),
            self.assertRaisesRegex(ValueError, "unpaired_result"),
        ):
            flow.run(self.stage, 0)
        self.assertEqual(self.calls, 2)

    def test_existing_group_directory_is_not_reused(self):
        (self.stage / "run/0").mkdir()
        with self.modules(self.supervisor), self.assertRaises(FileExistsError):
            flow.run(self.stage, 0)
        self.assertEqual(self.calls, 0)


class PrivatePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.binding, self.starts = start_fixture()
        self.parent = "CFL_easy_instance_0"
        self.paths = {}
        for name, key in (
            ("model", "model_sha256"),
            ("root", "root_sha256"),
            ("graph", "graph_sha256"),
            ("predictions", "prediction_sha256"),
            ("starts", "private_starts_sha256"),
        ):
            path = self.root / name
            path.write_bytes(
                contract.encoded(self.starts) if name == "starts" else name.encode()
            )
            self.paths[name] = str(path)
            self.binding[key] = flow.file_sha(path)
        checkpoint = self.root / "checkpoint"
        checkpoint.write_bytes(b"frozen fake checkpoint, never deserialized")
        self.private = {
            "parents": {self.parent: self.paths},
            "checkpoint_path": str(checkpoint),
        }
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(
            patch.object(flow.prep, "safe_file", side_effect=lambda p: Path(p))
        )
        self.stack.enter_context(
            patch.object(contract, "CHECKPOINT", flow.file_sha(checkpoint))
        )

    def test_private_artifacts_are_hashed_without_deserializing_graphs_or_weights(self):
        result = flow.verify_inputs({self.parent: self.binding}, self.private)
        self.assertEqual(result[self.parent], self.starts)

    def test_each_changed_model_root_graph_prediction_or_Start_stops(self):
        for name in self.paths:
            p = Path(self.paths[name])
            original = p.read_bytes()
            p.write_bytes(original + b"changed")
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(ValueError, "private_" + name + "_bytes"),
            ):
                flow.verify_inputs({self.parent: self.binding}, self.private)
            p.write_bytes(original)

    def test_checkpoint_change_is_not_an_automatic_model_replacement(self):
        Path(self.private["checkpoint_path"]).write_bytes(b"other model")
        with self.assertRaisesRegex(ValueError, "checkpoint_bytes"):
            flow.verify_inputs({self.parent: self.binding}, self.private)

    def test_input_not_in_the_sixteen_parent_ledger_cannot_be_added(self):
        with self.assertRaisesRegex(ValueError, "private_parent_set"):
            flow.verify_inputs({}, self.private)


class ChildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage = Path(self.tmp.name)
        (self.stage / "claims").mkdir()
        (self.stage / "run").mkdir()
        self.cell = next(iter(contract.matrix()[1].values()))
        self.group = contract.matrix()[0]["groups"][0]
        self.binding, self.starts = start_fixture()
        self.plan = {
            "groups": contract.matrix()[0]["groups"],
            "bindings": {self.cell["parent"]: self.binding},
        }
        dump(self.stage / "plan.json", self.plan)
        dump(
            self.stage / "inputs.private.json",
            {"parents": {self.cell["parent"]: {"model": str(self.stage / "model")}}},
        )
        dump(
            self.stage / "claims/group-0.json",
            {"job_id": "8000", "group_id": self.group["group_id"]},
        )
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(flow, "load", return_value=self.plan))
        self.stack.enter_context(patch.object(flow, "approved"))
        self.stack.enter_context(
            patch.object(
                flow,
                "allocation",
                return_value=(
                    "8000",
                    types.SimpleNamespace(sample=lambda: 1),
                    {"pinned_logical_CPUs": [0]},
                ),
            )
        )
        self.stack.enter_context(patch.object(flow, "verify_affinity"))
        self.check_job = self.stack.enter_context(patch.object(flow, "check_group_job"))
        self.stack.enter_context(
            patch.object(
                flow, "verify_inputs", return_value={self.cell["parent"]: self.starts}
            )
        )
        self.validate = self.stack.enter_context(
            patch.object(contract, "validate_result")
        )
        self.calls = []

    def solve(self, *args, **kwargs):
        kwargs["before_optimize"]()
        self.calls.append(kwargs)
        return {"gate_status": "passed", "scientific_reporting_eligible": False}

    def execute(self, cell):
        folder = self.stage / "run" / cell["cell_id"]
        folder.mkdir(exist_ok=True)
        with patch.dict(
            sys.modules,
            {"pr94_evaluation_solver": types.SimpleNamespace(solve=self.solve)},
        ):
            flow.child(self.stage, cell["cell_id"])
        return folder

    def test_durable_optimize_claim_precedes_each_single_solve(self):
        folder = self.execute(self.cell)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(
            (self.stage / "claims" / (self.cell["cell_id"] + ".optimize.json")).exists()
        )
        self.assertTrue((folder / "raw-result.json").exists())
        self.assertTrue((folder / "child.json").exists())
        self.assertIsNone(self.calls[0]["preselected_assignments"])
        self.check_job.assert_called_once()

    def test_validation_failure_preserves_the_unqualified_raw_result(self):
        self.validate.side_effect = ValueError("result_gate")
        with self.assertRaisesRegex(ValueError, "result_gate"):
            self.execute(self.cell)
        folder = self.stage / "run" / self.cell["cell_id"]
        self.assertTrue((folder / "raw-result.json").exists())
        self.assertFalse((folder / "child.json").exists())

    def test_repeated_child_cannot_optimize_again(self):
        self.execute(self.cell)
        with self.assertRaises(FileExistsError):
            self.execute(self.cell)
        self.assertEqual(len(self.calls), 1)

    def test_abstained_G_is_an_empty_partial_Start_not_a_new_prediction(self):
        binding, starts = start_fixture(True)
        self.binding.clear()
        self.binding.update(binding)
        self.starts.clear()
        self.starts.update(starts)
        cell = next(
            c
            for c in contract.matrix()[1].values()
            if c["parent"] == self.cell["parent"]
            and c["method"] == "M2"
            and c["seed"] == 42
        )
        self.execute(cell)
        self.assertEqual(self.calls[0]["preselected_assignments"], [])
        self.assertIs(self.calls[0]["execution_policy"], contract)
        self.assertEqual(self.calls[0]["reported_method"], "M2")


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage = Path(self.tmp.name)
        (self.stage / "claims").mkdir()
        (self.stage / "run").mkdir()
        self.plan = {
            "groups": contract.matrix()[0]["groups"],
            "bindings": {},
            "source": {"commit": "a" * 40},
        }
        dump(self.stage / "plan.json", self.plan)
        self.jobs = [
            {
                "job_id": str(8000 + i),
                "index": i,
                "lane": i % 4,
                "group_id": g["group_id"],
                "predecessor": str(7996 + i) if i >= 4 else None,
            }
            for i, g in enumerate(self.plan["groups"])
        ]
        dump(
            self.stage / "submission.json",
            {"jobs": self.jobs, "plan_sha256": flow.file_sha(self.stage / "plan.json")},
        )

    def state(self, terminal_groups=1):
        rows = []
        for index in range(48):
            for suffix in ("", ".batch", ".extern"):
                rows.append(
                    {
                        "JobIDRaw": str(8000 + index) + suffix,
                        "State": "COMPLETED" if index < terminal_groups else "RUNNING",
                        "ExitCode": "0:0",
                        "ElapsedRaw": "10",
                        "AllocCPUS": "2",
                        "TotalCPU": "00:00:09",
                        "MaxRSS": "",
                        "ReqMem": "64G",
                        "Start": "Unknown",
                        "End": "Unknown",
                    }
                )
        return {
            "submission_complete": True,
            "root_jobs_terminal": terminal_groups == 48,
            "missing_steps": [],
            "rows": rows,
        }

    def test_one_accounting_query_binds_all_48_ids_and_preserves_empty_fields(self):
        fields = [
            "JobIDRaw",
            "State",
            "ExitCode",
            "ElapsedRaw",
            "AllocCPUS",
            "TotalCPU",
            "MaxRSS",
            "ReqMem",
            "Start",
            "End",
        ]
        rows = self.state()["rows"]
        rows[0]["End"] = ""
        raw = "\n".join("|".join(r[k] for k in fields) + "|" for r in rows)
        with patch.object(flow, "command", return_value=raw) as query:
            value = flow.accounting(self.stage)
        self.assertEqual(len(value["rows"]), 144)
        self.assertFalse(value["root_jobs_terminal"])
        self.assertEqual(value["rows"][0]["End"], "")
        self.assertEqual(query.call_count, 1)

    def test_partial_submission_status_preserves_known_ids_and_unknown_reply(self):
        (self.stage / "submission.json").unlink()
        dump(self.stage / "claims/submitted-0.json", self.jobs[0])
        dump(self.stage / "claims/submit-0.json", {})
        dump(self.stage / "claims/submit-1.json", {})
        raw = "8000|PENDING|0:0|0|0|0:0|||Unknown|Unknown|"
        with patch.object(flow, "command", return_value=raw):
            value = flow.accounting(self.stage)
        self.assertFalse(value["submission_complete"])
        self.assertEqual(value["recorded_jobs"], 1)
        self.assertEqual(value["unconfirmed_submission_intents"], 1)

    def test_foreign_or_duplicate_accounting_rows_are_rejected(self):
        rows = [
            "9999|COMPLETED|0:0|1|2|0:0|||Unknown|Unknown|",
            "8000|COMPLETED|0:0|1|2|0:0|||Unknown|Unknown|\n" * 2,
        ]
        for raw in rows:
            with (
                patch.object(flow, "command", return_value=raw),
                self.assertRaises(ValueError),
            ):
                flow.accounting(self.stage)

    def test_collection_never_reads_an_incomplete_live_JSON(self):
        live = self.plan["groups"][1]["cells"][0]
        path = self.stage / "run" / live / "child.json"
        path.parent.mkdir()
        path.write_text("{incomplete")
        with (
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "accounting", return_value=self.state()),
            patch.object(flow, "export", side_effect=lambda stage, members: members),
        ):
            value = flow.collect(self.stage)
        returned = json.loads(next(iter(value.values())))
        self.assertEqual(returned["terminal_groups_collected"], 1)
        self.assertEqual(returned["received"], 0)
        self.assertEqual(len(returned["cells"]), 144)
        self.assertFalse(returned["complete_campaign_accounting"])
        self.assertNotIn(
            path.relative_to(self.stage).as_posix(), returned["closed_artifact_seals"]
        )

    def test_root_done_with_batch_running_does_not_close_the_group(self):
        state = self.state()
        state["rows"][1]["State"] = "RUNNING"
        with (
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "accounting", return_value=state),
        ):
            value = flow.collect(self.stage)
        self.assertTrue(value["no_return_created"])

    def test_final_missing_results_stay_missing_and_return_cannot_be_overwritten(self):
        with (
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "accounting", return_value=self.state(48)),
            patch.object(flow, "export", side_effect=lambda stage, members: members),
        ):
            result = flow.collect(self.stage)
            returned = json.loads(result["evaluation-public-return.json"])
            self.assertEqual(returned["received"], 0)
            self.assertFalse(returned["scientific_reporting_eligible"])
            with self.assertRaises(FileExistsError):
                flow.collect(self.stage)


class SiteAndStorageTests(unittest.TestCase):
    def test_busy_node_is_not_mistaken_for_insufficient_configured_capacity(self):
        with patch.object(
            flow,
            "command",
            side_effect=[
                "PartitionName=batch State=UP MaxTime=1-00:00:00",
                "dgx-dasci|80|490042",
            ],
        ):
            value = flow.site_preflight()
        self.assertTrue(value["queue_wait_is_permitted"])
        self.assertFalse(value["current_free_resources_guaranteed"])
        self.assertFalse(value["license_concurrency_guaranteed"])

    def test_short_maxwall_or_small_configured_node_does_not_silently_change_budget(
        self,
    ):
        cases = [
            ["PartitionName=batch State=UP MaxTime=01:00:00"],
            ["PartitionName=batch State=UP MaxTime=UNLIMITED", "dgx-dasci|80|131072"],
        ]
        for replies in cases:
            with (
                patch.object(flow, "command", side_effect=replies),
                self.assertRaises(ValueError),
            ):
                flow.site_preflight()

    def test_low_storage_is_observed_without_deleting_any_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            saved = root / "preserve.txt"
            saved.write_text("evidence")
            with (
                patch.object(
                    flow.shutil,
                    "disk_usage",
                    return_value=types.SimpleNamespace(free=10 * flow.GIB),
                ),
                self.assertRaisesRegex(ValueError, "free_space"),
            ):
                flow.storage(root, admission=True)
            self.assertEqual(saved.read_text(), "evidence")

    def test_storage_sampling_does_not_walk_other_jobs_files(self):
        with (
            patch.object(
                flow.shutil,
                "disk_usage",
                return_value=types.SimpleNamespace(free=100 * flow.GIB),
            ) as query,
            patch.object(
                Path, "rglob", side_effect=AssertionError("unbounded filesystem walk")
            ),
        ):
            flow.sample_storage_floor(Path("unused"))
        query.assert_called_once()


class PredecessorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage = Path(self.tmp.name)
        groups = contract.matrix()[0]["groups"]
        self.plan = {"groups": groups}
        dump(self.stage / "plan.json", self.plan)
        self.jobs = [
            {
                "job_id": str(8000 + i),
                "index": i,
                "lane": i % 4,
                "group_id": g["group_id"],
                "predecessor": str(7996 + i) if i >= 4 else None,
            }
            for i, g in enumerate(groups)
        ]
        dump(
            self.stage / "submission.json",
            {"jobs": self.jobs, "plan_sha256": flow.file_sha(self.stage / "plan.json")},
        )
        self.previous = {
            "group_id": groups[0]["group_id"],
            "job_id": "8000",
            "complete": True,
            "stop": None,
            "plan_sha256": flow.file_sha(self.stage / "plan.json"),
            "rows": [],
        }
        for cell_id in groups[0]["cells"]:
            path = self.stage / "run" / cell_id / "child.json"
            dump(path, {"synthetic": True})
            self.previous["rows"].append(
                {
                    "cell_id": cell_id,
                    "relative_result": path.relative_to(self.stage).as_posix(),
                    "sha256": flow.file_sha(path),
                }
            )
        dump(self.stage / "run/0/group.json", self.previous)

    def test_closed_same_lane_predecessor_is_required_before_starting_successor(self):
        flow.check_group_job(self.stage, 4, self.plan, "8004")
        with self.assertRaisesRegex(ValueError, "job_group_binding"):
            flow.check_group_job(self.stage, 4, self.plan, "9999")

    def test_changed_predecessor_bytes_stop_the_successor(self):
        path = self.stage / self.previous["rows"][0]["relative_result"]
        path.write_text("changed")
        with self.assertRaisesRegex(ValueError, "predecessor_result_changed"):
            flow.check_group_job(self.stage, 4, self.plan, "8004")

    def test_incomplete_or_wrong_predecessor_group_cannot_unlock_the_chain(self):
        self.previous["rows"] = []
        dump(self.stage / "run/0/group.json", self.previous)
        with self.assertRaisesRegex(ValueError, "predecessor_cells"):
            flow.check_group_job(self.stage, 4, self.plan, "8004")


class ResultTests(unittest.TestCase):
    def fixture(self, method="M0"):
        cell = next(c for c in contract.matrix()[1].values() if c["method"] == method)
        binding, _ = start_fixture()
        binding["mathematical_signature_sha256"] = "a" * 64
        recorder = contract.Recorder()
        recorder.observe(12.5, 1, 1, "terminal")
        result = {
            "optimization_calls": 1,
            "method": method,
            "mip_sha256": cell["model_sha256"],
            "solver_version": [13, 0, 1],
            "effective_objective_sense": "MINIMIZE",
            "fresh_model": True,
            "mathematical_model_unchanged": True,
            "parameters": contract.parameters(cell),
            "scientific_reporting_eligible": False,
            "mathematical_signature_sha256": "a" * 64,
            "gate_status": "passed",
            "callback_errors": [],
            "solve": {"solve_status_code": 2, "solver_runtime_seconds": 12.5},
            "temporal_evidence": recorder.finish(),
            "start": {
                "submitted_assignments": 0 if method == "M0" else 1,
                "assignment_sha256": binding.get(method + "_assignment_sha256"),
                "positive_assignments": 0 if method == "M0" else 1,
            },
        }
        return cell, binding, result

    def test_qualified_control_and_guided_metadata_keep_reporting_false(self):
        for method in ("M0", "M1", "M2"):
            cell, binding, result = self.fixture(method)
            contract.validate_result(cell, result, binding)
            self.assertFalse(result["scientific_reporting_eligible"])

    def test_changed_Method_or_integrality_tolerance_is_not_an_admitted_ablation(self):
        for field, value in (("Method", 1), ("IntFeasTol", 1e-9), ("Presolve", 0)):
            cell, binding, result = self.fixture()
            result["parameters"][field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, "result_parameters"),
            ):
                contract.validate_result(cell, result, binding)

    def test_soft_memory_callback_failure_and_promotion_are_not_successful_returns(
        self,
    ):
        for change in ("memory", "callback", "reporting", "count"):
            cell, binding, result = self.fixture()
            if change == "memory":
                result["solve"]["solve_status_code"] = 17
            elif change == "callback":
                result["callback_errors"] = ["SyntheticError"]
            elif change == "reporting":
                result["scientific_reporting_eligible"] = True
            else:
                result["optimization_calls"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.validate_result(cell, result, binding)

    def test_another_Start_cannot_be_attributed_to_G(self):
        cell, binding, result = self.fixture("M2")
        result["start"]["assignment_sha256"] = binding["M1_assignment_sha256"]
        with self.assertRaisesRegex(ValueError, "result_start_hash"):
            contract.validate_result(cell, result, binding)


class InspectionTests(unittest.TestCase):
    def test_installation_exports_sixteen_bindings_but_zero_scientific_calls_or_submissions(
        self,
    ):
        import zipfile

        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp) / ("pr94-evaluation-" + "a" * 12)
            stage.mkdir()
            public = {
                c["parent"]: {"model_sha256": c["model_sha256"]}
                for c in contract.matrix()[1].values()
            }
            private = {
                "parents": {p: {} for p in public},
                "checkpoint_path": "not_loaded",
            }
            with (
                patch.object(flow.prep, "host"),
                patch.object(flow, "stage_path", return_value=stage),
                patch.object(
                    flow, "source_snapshot", return_value={"commit": "a" * 40}
                ),
                patch.object(flow, "storage", return_value={}),
                patch.object(flow, "site_preflight", return_value={}),
                patch.object(flow, "discover_inputs", return_value=(public, private)),
                patch.object(flow, "verify_inputs") as verify,
                patch.object(flow.prep, "versions", return_value={"synthetic": True}),
            ):
                exported = flow.freeze(stage, "b" * 64)
                with self.assertRaisesRegex(ValueError, "evaluation_plan_exists"):
                    flow.freeze(stage, "b" * 64)
            verify.assert_called_once()
            with zipfile.ZipFile(exported["ARQUIVO_HPC"]) as archive:
                value = json.loads(archive.read("installation-review.json"))
            self.assertEqual(value["private_model_and_artifact_chains_verified"], 16)
            self.assertEqual(value["optimization_calls"], 0)
            self.assertEqual(value["forward_calls"], 0)
            self.assertEqual(value["training_calls"], 0)
            self.assertEqual(value["submissions"], 0)
            self.assertFalse(value["scientific_reporting_eligible"])

    def test_affinity_drift_is_rejected(self):
        with patch.object(flow.os, "sched_getaffinity", return_value={3}, create=True):
            flow.verify_affinity({"pinned_logical_CPUs": [3]})
            with self.assertRaisesRegex(ValueError, "affinity_changed"):
                flow.verify_affinity({"pinned_logical_CPUs": [4]})


if __name__ == "__main__":
    unittest.main()
