"""Offline checks for the one-time, CPU-only H25 deadline recovery."""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr98_hard_inputs as inputs
import pr98_hard_pilot as pilot
import pr98_pilot_deadline_recovery as recovery


class DeadlineRecoveryTests(unittest.TestCase):
    def test_scientific_policy_is_unchanged_and_no_new_preparation(self):
        self.assertEqual(recovery.BUDGET["new_root_calls"], 0)
        self.assertEqual(recovery.BUDGET["new_forward_calls"], 0)
        self.assertEqual(recovery.BUDGET["new_training_calls"], 0)
        self.assertEqual(recovery.BUDGET["new_pilot_solve_calls_maximum"], 6)
        self.assertEqual(recovery.BUDGET["GPUs_reserved"], 0)
        self.assertEqual(recovery.BUDGET["wall_seconds_reserved"], 7200)
        self.assertEqual(recovery.DEADLINE, 900)
        for c in pilot.PROFILES:
            with patch.dict(
                sys.modules,
                {
                    "pr94_evaluation_contract": types.SimpleNamespace(
                        baseline_parameters=dict
                    )
                },
            ):
                params = pilot.Policy.parameters({"concurrent": c})
            self.assertEqual(params["TimeLimit"], 120)
            self.assertEqual(params["Threads"], 4)
            self.assertEqual(params["Seed"], 42)
            self.assertEqual(params["ConcurrentMIP"], c)

    def test_cpu_held_profile_rejects_gpu_and_resource_drift(self):
        text = (
            "JobId=4000 JobState=PENDING Reason=JobHeldUser Partition=batch "
            "Requeue=0 Restarts=0 NumTasks=1 CPUs/Task=4 TimeLimit=02:00:00 "
            "NumNodes=1-1 NumCPUs=8 MinMemoryNode=64G "
            "TRES=cpu=8,mem=64G,node=1,billing=8"
        )
        self.assertEqual(recovery.held_profile(text, "4000")["NumCPUs"], "8")
        for bad in (
            text + ",gres/gpu=1",
            text.replace("02:00:00", "01:00:00"),
            text.replace("JobHeldUser", "Priority"),
            text.replace("CPUs/Task=4", "CPUs/Task=8"),
            text + ",cpu=8",
        ):
            with self.assertRaises(ValueError):
                recovery.held_profile(bad, "4000")

    def test_submit_preserves_parent_copies_artifacts_and_claims_before_sbatch(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            stage, parent = base / "new", base / "parent"
            stage.mkdir()
            prep = parent / "run/pilot/preparation"
            prep.mkdir(parents=True)
            for name in (*pilot.ARTIFACTS.values(), "artifact-receipt.json"):
                (prep / name).write_bytes(name.encode())
            (stage / "inputs.private.json").write_text("{}")
            calls = []

            def command(args, **kwargs):
                self.assertTrue((base / recovery.CLAIM).is_file())
                self.assertTrue((stage / "deadline-recovery.json").is_file())
                calls.append(args)
                return "4000" if args[0] == "sbatch" else ""

            prior = types.SimpleNamespace(
                command=command,
                storage=lambda *a, **k: None,
                versions=lambda: {"python": "3.10.20"},
            )
            before = {p.name: p.read_bytes() for p in prep.iterdir()}
            with (
                patch.dict(sys.modules, {"pr94_isolated_preparation": prior}),
                patch.object(inputs, "EVIDENCE", base),
                patch.object(inputs, "source_commit", return_value="source"),
                patch.object(recovery, "PARENT", parent),
                patch.object(
                    recovery, "INPUTS_SHA", inputs.digest(stage / "inputs.private.json")
                ),
                patch.object(
                    recovery, "parent_snapshot", return_value={"parent": "sealed"}
                ),
                patch.object(recovery, "held_profile", return_value={"checked": True}),
                patch.object(
                    recovery.license_recovery,
                    "license_binding",
                    return_value={"path": "canonical", "sha256": "hash"},
                ),
                patch.object(pilot, "admitted", return_value=({}, None, None)),
                patch.object(pilot, "verify_artifacts"),
            ):
                recovery.submit(stage, "preflight", "AUTORIZO RECUPERACAO H25 3905")
                with self.assertRaises(FileExistsError):
                    recovery.submit(stage, "preflight", "AUTORIZO RECUPERACAO H25 3905")
            self.assertEqual(before, {p.name: p.read_bytes() for p in prep.iterdir()})
            for name, raw in before.items():
                self.assertEqual(
                    (stage / "run/pilot/preparation" / name).read_bytes(), raw
                )
            self.assertEqual(
                [args[0] for args in calls], ["sbatch", "scontrol", "scontrol"]
            )
            sbatch = calls[0]
            self.assertIn("--time=02:00:00", sbatch)
            self.assertIn("--cpus-per-task=4", sbatch)
            self.assertIn("--mem=64G", sbatch)
            self.assertIn("--hold", sbatch)
            self.assertFalse(any(x.startswith("--gres") for x in sbatch))
            self.assertIn(
                "--export=ALL,GRB_LICENSE_FILE="
                + str(recovery.license_recovery.LICENSE_PATH),
                sbatch,
            )

    def test_missing_specific_decision_stops_before_any_work(self):
        with patch.object(pilot, "admitted") as admitted:
            for value in (None, "", "approved", "AUTORIZO RECUPERACAO H25 3891"):
                with self.assertRaisesRegex(ValueError, "specific_recovery_decision"):
                    recovery.submit(Path("unused"), "unused", value)
            admitted.assert_not_called()

    def test_parent_drift_or_changed_budget_rejects_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            stage = base / "new"
            stage.mkdir()
            (stage / "inputs.private.json").write_text("{}")
            license_record = {"path": "canonical", "sha256": "hash"}
            value = {
                "budget": recovery.BUDGET,
                "scope": pilot.PILOT_SCOPE,
                "decision": "AUTORIZO RECUPERACAO H25 3905",
                "preflight_sha256": "sealed",
                "source_commit": "source",
                "license": license_record,
                "versions": {},
                "parent": {"seal": "old"},
            }
            inputs.write_once(stage / "deadline-recovery.json", value)
            inputs.write_once(base / recovery.CLAIM, value)
            prior = types.SimpleNamespace(versions=dict)
            with (
                patch.dict(sys.modules, {"pr94_isolated_preparation": prior}),
                patch.object(inputs, "EVIDENCE", base),
                patch.object(inputs, "source_commit", return_value="source"),
                patch.object(
                    recovery, "INPUTS_SHA", inputs.digest(stage / "inputs.private.json")
                ),
                patch.object(pilot, "admitted"),
                patch.object(
                    recovery.license_recovery,
                    "license_binding",
                    return_value=license_record,
                ),
                patch.object(recovery, "parent_snapshot", return_value={"seal": "new"}),
            ):
                with self.assertRaisesRegex(ValueError, "parent_evidence_changed"):
                    recovery.approval(stage, "sealed")
                value["budget"] = {**recovery.BUDGET, "seconds_per_solve": 600}
                for p in (stage / "deadline-recovery.json", base / recovery.CLAIM):
                    p.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, "recovery_approval"):
                    recovery.approval(stage, "sealed")

    def test_six_ordered_cells_stop_at_first_failure_without_repreparation(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            (stage / "run/pilot").mkdir(parents=True)
            commands = []

            def supervise(command, console, deadline, gate):
                commands.append((command, deadline))
                return {"guard_stop": None, "child_exit_code": 0}

            with (
                patch.dict(
                    sys.modules,
                    {
                        "paired_memory_runtime_v2": types.SimpleNamespace(
                            supervise=supervise
                        ),
                        "resource": types.SimpleNamespace(
                            RLIMIT_FSIZE=1, setrlimit=lambda *a: None
                        ),
                    },
                ),
                patch.object(recovery, "runtime", return_value=("4000", object(), {})),
            ):
                recovery.batch(stage, "sealed")
            self.assertEqual(len(commands), 6)
            self.assertEqual(
                [
                    (a[a.index("--concurrent") + 1], a[a.index("--method") + 1])
                    for a, _ in commands
                ],
                [
                    ("1", "M0"),
                    ("1", "M1"),
                    ("1", "M2"),
                    ("2", "M0"),
                    ("2", "M1"),
                    ("2", "M2"),
                ],
            )
            self.assertTrue(all(deadline == 900 for _, deadline in commands))
            self.assertTrue((stage / "run/pilot/complete.json").is_file())
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            (stage / "run/pilot").mkdir(parents=True)
            calls = []

            def stopped(*args):
                calls.append(args)
                return {"guard_stop": "child_deadline_exceeded", "child_exit_code": -15}

            with (
                patch.dict(
                    sys.modules,
                    {
                        "paired_memory_runtime_v2": types.SimpleNamespace(
                            supervise=stopped
                        ),
                        "resource": types.SimpleNamespace(
                            RLIMIT_FSIZE=1, setrlimit=lambda *a: None
                        ),
                    },
                ),
                patch.object(recovery, "runtime", return_value=("4000", object(), {})),
                self.assertRaisesRegex(ValueError, "pilot_child_failed"),
            ):
                recovery.batch(stage, "sealed")
            self.assertEqual(len(calls), 1)
            self.assertFalse((stage / "run/pilot/complete.json").exists())

    def test_parent_timeout_artifacts_and_terminal_state_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            parent = base / "parent"
            run = parent / "run/pilot"
            prep = run / "preparation"
            prep.mkdir(parents=True)
            (run / "c1-M0").mkdir()
            (parent / "source").mkdir()
            names = [
                "preflight.json",
                "inputs.private.json",
                "pilot-approval.json",
                "pilot-submission.json",
                "pilot-held-profile.private.json",
                "license-recovery.json",
                "pilot-3905.private.err",
                "pilot-3905.private.out",
                "run/pilot/batch.json",
                "run/pilot/preparation.supervision.private.json",
                "run/pilot/preparation.console.private.log",
                "run/pilot/preparation/artifact-receipt.json",
                "run/pilot/preparation/root.intent.json",
                "run/pilot/preparation/forward.intent.json",
                "run/pilot/c1-M0.supervision.private.json",
                "run/pilot/c1-M0.console.private.log",
                "run/pilot/c1-M0/solve.intent.json",
                "run/pilot/c1-M0/gurobi.private.log",
            ]
            for name in names:
                (parent / name).write_text("{}")
            (parent / "inputs.private.json").write_text('{"models":{"H25":{}}}')
            preflight_hash = inputs.digest(parent / "preflight.json")
            old = {"budget": pilot.BUDGET, "preflight_sha256": preflight_hash}
            (parent / "pilot-approval.json").write_text(json.dumps(old))
            (base / "parent.claim").write_text(json.dumps(old))
            (base / recovery.license_recovery.RECOVERY_CLAIM).write_text(
                json.dumps(old)
            )
            (parent / "pilot-submission.json").write_text(
                json.dumps(
                    {
                        "job_id": "3905",
                        "preflight_sha256": preflight_hash,
                        "scope": pilot.PILOT_SCOPE,
                    }
                )
            )
            (run / "preparation.supervision.private.json").write_text(
                json.dumps({"child_exit_code": 0, "guard_stop": None})
            )
            (run / "c1-M0.supervision.private.json").write_text(
                json.dumps(
                    {"child_exit_code": -15, "guard_stop": "child_deadline_exceeded"}
                )
            )
            (run / "c1-M0/solve.intent.json").write_text('{"maximum_calls":1}')
            (run / "c1-M0/gurobi.private.log").write_text(
                "TimeLimit  120\nin 121.78 seconds\nTime limit reached\n"
                "Best objective 2.091003359181e+02"
            )
            rows = [
                {"JobID": j, "State": "FAILED", "ExitCode": "1:0"}
                for j in ("3905", "3905.batch")
            ]
            rows.append({"JobID": "3905.extern", "State": "COMPLETED"})
            prior = types.SimpleNamespace(
                command=lambda args, **kwargs: (
                    recovery.PARENT_SOURCE if "rev-parse" in args else ""
                ),
                accounting=lambda *a: {
                    "job_id": "3905",
                    "terminal": True,
                    "rows": rows,
                },
            )
            with (
                patch.dict(sys.modules, {"pr94_isolated_preparation": prior}),
                patch.object(inputs, "EVIDENCE", base),
                patch.object(recovery, "PARENT", parent),
                patch.object(recovery, "PARENT_PREFLIGHT", preflight_hash),
                patch.object(
                    recovery,
                    "INPUTS_SHA",
                    inputs.digest(parent / "inputs.private.json"),
                ),
                patch.object(
                    recovery.license_recovery,
                    "claim_path",
                    return_value=base / "parent.claim",
                ),
                patch.object(
                    pilot,
                    "verify_artifacts",
                    return_value=({**recovery.ARTIFACT_HASHES, "abstained": False}, {}),
                ),
            ):
                first = recovery.parent_snapshot(True)
                rows[0]["State"] = "RUNNING"
                with self.assertRaisesRegex(ValueError, "parent_accounting"):
                    recovery.parent_snapshot(True)
                rows[0]["State"] = "FAILED"
                (run / "c1-M0.console.private.log").write_text(
                    "changed terminal evidence"
                )
                self.assertNotEqual(first, recovery.parent_snapshot(True))
                (run / "c1-M1").mkdir()
                with self.assertRaisesRegex(ValueError, "unexpected_parent_call"):
                    recovery.parent_snapshot(True)

    def test_report_distinguishes_reused_preparation_from_new_calls(self):
        import contextlib
        import io

        out = io.StringIO()
        with (
            patch.object(recovery, "approval"),
            patch.object(
                pilot, "report", side_effect=lambda *a: print(json.dumps({"cells": []}))
            ),
            contextlib.redirect_stdout(out),
        ):
            recovery.report(Path("unused"), "sealed")
        result = json.loads(out.getvalue())
        self.assertEqual(result["predecessor_job_id"], "3905")
        self.assertEqual(result["new_root_calls"], 0)
        self.assertEqual(result["new_forward_calls"], 0)
        self.assertTrue(result["artifact_receipt_call_counts_refer_to_parent"])
