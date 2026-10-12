"""Root-stage control flow with fake scheduler, allocation and native solver."""

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import pr86_native_model as native  # noqa: E402
import pr86_root_preparation as roots  # noqa: E402


class Roots(unittest.TestCase):
    def test_persisted_plan_change_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            # Windows runners can expose TEMP via an 8.3 alias (RUNNER~1).
            # The production gate intentionally requires a canonical stage.
            canonical_base = Path(temp).resolve()
            stage = canonical_base / ("roots-" + "a" * 12)
            stage.mkdir()
            frozen = roots.plan("a" * 40)
            roots.write(stage / "plan.json", frozen)
            with (
                patch.object(roots, "head", return_value="a" * 40),
                patch.object(roots, "BASE", canonical_base),
            ):
                self.assertEqual(roots.load(stage), frozen)
                with (
                    patch.object(
                        roots,
                        "plan",
                        return_value={**frozen, "maximum_optimization_calls": 11},
                    ),
                    self.assertRaisesRegex(
                        ValueError, "installed_plan_or_source_changed"
                    ),
                ):
                    roots.load(stage)

    def test_public_return_review_rejects_scope_sense_and_count_changes(self):
        frozen = roots.plan("a" * 40)
        log = {
            "log_sha256": "a" * 64,
            "log_size_bytes": 3,
            "private_log_text_included": False,
            "hash_scope": "bytes_after_caller_closed_writer",
        }
        rows = []
        for target in frozen["parents"]:
            rows.append(
                {
                    "parent": target["parent"],
                    "completed": True,
                    "optimization_intent_present": True,
                    "supervision": {"guard_stop": None, "child_exit_code": 0},
                    "console_log": log,
                    "result": {
                        "parent": target["parent"],
                        "model_sha256": target["model_sha256"],
                        "effective_objective_sense": "MINIMIZE",
                        "source_objective_sense": "MAXIMIZE",
                        "optimization_calls": 1,
                        "scientific_reporting_eligible": False,
                        "root_sha256": "b" * 64,
                        "variable_order_sha256": "c" * 64,
                        "vector_sha256": "d" * 64,
                        "mathematical_signature_sha256": "e" * 64,
                        "variable_count": 2,
                        "capture_wall_seconds": 1,
                        "root_export_wall_seconds": 0.1,
                        "gurobi_log": log,
                    },
                }
            )
        state = roots.accounting.parse_accounting(
            "123|COMPLETED|0:0|20|00:20|2|64G|", "123"
        )
        sha = roots.digest(roots.encoded(frozen))
        summary = {
            "protocol_id": roots.PROTOCOL,
            "job_id": "123",
            "plan_sha256": sha,
            "rows": rows,
            "complete": True,
            "stop_code": None,
            "batch_observed_wall_seconds": 20,
            "versions": {},
            "main_solves_added": 0,
            "forwards_added": 0,
            "training_runs_added": 0,
            "scientific_reporting_eligible": False,
        }
        value = {
            "protocol_id": roots.PROTOCOL,
            "source_commit": "a" * 40,
            "plan_sha256": sha,
            "accounting": state,
            "summary": summary,
            "raw_logs_included": False,
            "root_vectors_included": False,
            "ready_for_independent_review": True,
            "scientific_reporting_eligible": False,
        }
        with patch.object(roots, "plan", return_value=frozen):
            self.assertEqual(roots.validate_return(roots.encoded(value)), value)
            for key, change in (
                ("effective_objective_sense", "MAXIMIZE"),
                ("optimization_calls", 2),
                ("scientific_reporting_eligible", True),
                ("model_sha256", "f" * 64),
            ):
                bad = copy.deepcopy(value)
                bad["summary"]["rows"][0]["result"][key] = change
                with self.assertRaises(ValueError):
                    roots.validate_return(roots.encoded(bad))
            bad = copy.deepcopy(value)
            bad["summary"]["rows"] = bad["summary"]["rows"][:-1]
            with self.assertRaisesRegex(ValueError, "summary_completion"):
                roots.validate_return(roots.encoded(bad))

    def test_plan_preserves_ten_parents_policy_and_no_admission(self):
        value = roots.plan("a" * 40)
        self.assertEqual(len(value["parents"]), 10)
        self.assertEqual(value["maximum_optimization_calls"], 10)
        self.assertEqual(value["parameters"]["TimeLimit"], 600)
        self.assertEqual(value["parameters"]["NodeLimit"], 1)
        self.assertEqual(
            value["formulation_contract"], roots.isolated.FORMULATION_CONTRACT
        )
        self.assertNotIn("formulation_review", roots.isolated.GATES)
        for key in (
            "resource_budget_approved",
            "training_admitted",
            "inference_admitted",
            "main_solves_admitted",
            "automatic_retry",
        ):
            self.assertIs(value[key], False)

    def fake_native(self, scenario):
        codes = SimpleNamespace(
            MIPNODE=1, MIPNODE_STATUS=2, MIPNODE_NODCNT=3, MIPNODE_OBJBND=4
        )
        model = Mock(
            ModelSense=1,
            Params=SimpleNamespace(),
            SolCount=0,
            NumStart=0,
            Status=11,
            NumQNZs=0,
            NumQConstrs=0,
            NumGenConstrs=0,
            NumSOS=0,
        )
        model.getVars.return_value = [SimpleNamespace(VarName="x")]
        model.cbGet.side_effect = lambda code: {2: 2, 3: 0, 4: 1.2}[code]
        model.cbGetNodeRel.return_value = [0.25]
        if scenario == "callback_failure":
            model.cbGetNodeRel.return_value = [float("nan")]
        if scenario == "soft_limit":
            model.Status = 17
        backend = Mock(model=model, original_sense="MAXIMIZE")
        self.backend = backend
        self.model = model
        if scenario == "optimize_failure":
            model.optimize.side_effect = RuntimeError("synthetic")
        elif scenario != "absent":
            model.optimize.side_effect = lambda observer: observer(model, 1)
        api = SimpleNamespace(
            GRB=SimpleNamespace(Callback=codes, OPTIMAL=2, MINIMIZE=1),
            gurobi=SimpleNamespace(version=lambda: (13, 0, 1)),
        )
        return api, backend

    def test_capture_is_minimize_single_optimize_and_always_closes(self):
        for scenario in (
            "success",
            "absent",
            "callback_failure",
            "soft_limit",
            "optimize_failure",
            "claim_failure",
        ):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                api, backend = self.fake_native(scenario)
                claim = Mock(
                    side_effect=ValueError("claim")
                    if scenario == "claim_failure"
                    else None
                )
                with (
                    patch.dict(sys.modules, gurobipy=api),
                    patch.object(native, "NativeModel", return_value=backend),
                    patch.object(roots, "sha256_file", return_value="a" * 64),
                    patch.object(
                        roots, "mathematical_signature", return_value="b" * 64
                    ),
                ):
                    if scenario == "success":
                        result = roots.capture(
                            Path(temp) / "model", "a" * 64, Path(temp), claim
                        )
                        self.assertEqual(
                            result["effective_objective_sense"], "MINIMIZE"
                        )
                        self.assertEqual(result["original_objective_sense"], "MAXIMIZE")
                        self.assertEqual(result["relaxation_vector"], [0.25])
                        self.assertEqual(
                            result["solver_parameter_map"]["SoftMemLimit"], 48
                        )
                    else:
                        with self.assertRaises((ValueError, RuntimeError)):
                            roots.capture(
                                Path(temp) / "model", "a" * 64, Path(temp), claim
                            )
                self.assertEqual(
                    self.model.optimize.call_count, int(scenario != "claim_failure")
                )
                claim.assert_called_once()
                backend.close.assert_called_once()

    def test_unapproved_plan_does_not_claim_or_submit(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            roots.write(stage / "plan.json", {"test": True})
            with (
                patch.object(roots.accounting, "host"),
                patch.object(roots, "load", return_value={}),
                patch.dict(roots.os.environ, CONDA_DEFAULT_ENV="tfm_env"),
                patch.object(roots.accounting, "command") as command,
                self.assertRaisesRegex(ValueError, "approved_plan_hash"),
            ):
                roots.approve_and_submit(stage, "a" * 64)
            command.assert_not_called()

    def test_submission_claim_survives_uncertain_scheduler_reply(self):
        for reply in ("not-a-job", "12345"):
            with self.subTest(reply=reply), tempfile.TemporaryDirectory() as temp:
                stage = Path(temp) / "stage"
                stage.mkdir()
                frozen = {"source_commit": "a" * 40}
                sha = roots.write(stage / "plan.json", frozen)
                with (
                    patch.object(roots.accounting, "host"),
                    patch.object(roots, "load", return_value=frozen),
                    patch.object(roots, "inputs"),
                    patch.object(roots, "BASE", Path(temp)),
                    patch.dict(
                        roots.os.environ, CONDA_DEFAULT_ENV="tfm_env", SBATCH_NODES="9"
                    ),
                    patch.object(
                        roots.accounting, "command", return_value=reply
                    ) as command,
                ):
                    if reply == "12345":
                        self.assertEqual(
                            roots.approve_and_submit(stage, sha)["job_id"], reply
                        )
                    else:
                        with self.assertRaisesRegex(ValueError, "ambiguous_submission"):
                            roots.approve_and_submit(stage, sha)
                    self.assertNotIn("SBATCH_NODES", command.call_args.kwargs["env"])
                    self.assertIn("--nodes=1-1", command.call_args.args[0])
                    with self.assertRaises(FileExistsError):
                        roots.approve_and_submit(stage, sha)
                    self.assertEqual(command.call_count, 1)

    def test_runner_stops_at_first_failure_and_preserves_report(self):
        frozen = {
            "parents": [{"parent": str(i), "model_sha256": "a" * 64} for i in range(10)]
        }
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)

            def supervise(command, console, deadline, gate):
                self.assertEqual(deadline, 1140)
                console.write_bytes(b"private")
                return {"guard_stop": "memory_observation_lost", "child_exit_code": -9}

            with (
                patch.object(roots, "load", return_value=frozen),
                patch.object(roots, "approved"),
                patch.object(roots.isolated, "allocation", return_value=("123", None)),
                patch.object(
                    roots.importlib.metadata, "version", return_value="synthetic"
                ),
                patch.object(
                    roots.isolated.memory, "supervise", side_effect=supervise
                ) as supervisor,
            ):
                self.assertEqual(roots.run(stage), 2)
                self.assertEqual(supervisor.call_count, 1)
                summary = roots.parsed(stage / "run/summary.json")
                self.assertFalse(summary["complete"])
                self.assertEqual(len(summary["rows"]), 1)
                with self.assertRaises(FileExistsError):
                    roots.run(stage)

    def test_runner_and_collection_ten_synthetic_roots_and_tamper_rejection(self):
        frozen = {
            "parents": [
                {"parent": str(i), "model_sha256": "a" * 64} for i in range(10)
            ],
            "source_commit": "b" * 40,
        }
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)

            def supervise(command, console, deadline, gate):
                i = int(command[-1])
                folder = console.parent
                console.write_bytes(b"private console")
                (folder / "root.private.json.gz").write_bytes(b"private root")
                (folder / "gurobi.private.log").write_bytes(b"private log")
                roots.write(
                    folder / "result.json",
                    {
                        "parent": str(i),
                        "model_sha256": "a" * 64,
                        "root_sha256": roots.sha256_file(
                            folder / "root.private.json.gz"
                        ),
                        "gurobi_log": roots.isolated.logs.seal_closed_log(
                            folder / "gurobi.private.log"
                        ),
                    },
                )
                return {"guard_stop": None, "child_exit_code": 0}

            with (
                patch.object(roots, "load", return_value=frozen),
                patch.object(roots, "approved"),
                patch.object(roots.isolated, "allocation", return_value=("123", None)),
                patch.object(
                    roots.importlib.metadata, "version", return_value="synthetic"
                ),
                patch.object(
                    roots.isolated.memory, "supervise", side_effect=supervise
                ) as supervisor,
            ):
                self.assertEqual(roots.run(stage), 0)
                self.assertEqual(supervisor.call_count, 10)
                state = {
                    "job_id": "123",
                    "terminal": True,
                    "state": "COMPLETED",
                    "rows": [{"ExitCode": "0:0"}],
                }
                with patch.object(roots, "status", return_value=state):
                    collected = roots.collect(stage)
                    self.assertTrue(collected["ready_for_independent_review"])
                    raw = roots.read(stage / "public_return.json")
                    self.assertNotIn(b"private root", raw)
                    self.assertNotIn(b"private console", raw)
                    self.assertEqual(roots.collect(stage), collected)
                    (stage / "run/0/root.private.json.gz").write_bytes(b"changed")
                    with self.assertRaisesRegex(ValueError, "root_changed"):
                        roots.collect(stage)

    def test_frozen_formulation_rejects_maximize_before_dependency_or_solver(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bundle.json"
            contract = copy.deepcopy(roots.isolated.FORMULATION_CONTRACT)
            contract["effective_objective_sense"] = "MAXIMIZE"
            value = {
                "protocol_id": roots.isolated.PROTOCOL,
                "automatic_retry": False,
                "scientific_reporting_eligible": False,
                "formulation_contract": contract,
            }
            sha = roots.write(path, value)
            with (
                patch.object(roots.isolated.existing, "dependencies") as deps,
                self.assertRaisesRegex(ValueError, "frozen_formulation_contract"),
            ):
                roots.isolated.load_bundle(path, sha)
            deps.assert_not_called()


if __name__ == "__main__":
    unittest.main()
