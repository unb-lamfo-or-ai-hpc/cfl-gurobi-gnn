import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
import pr98_hard_inputs as inputs  # noqa: E402
import pr98_hard_pilot as pilot  # noqa: E402
import pr98_pilot_license_recovery as recovery  # noqa: E402


class LicenseRecoveryTests(unittest.TestCase):
    def test_license_uses_the_required_path_and_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gurobi.lic"
            path.write_text("synthetic fixture")
            with (
                patch.object(recovery, "LICENSE_PATH", path),
                patch.object(recovery, "LICENSE_SHA256", inputs.digest(path)),
                patch.dict(os.environ, {"GRB_LICENSE_FILE": str(path)}),
            ):
                expected = {"path": str(path), "sha256": inputs.digest(path)}
                self.assertEqual(recovery.license_binding(), expected)
                path.write_text("changed")
                with self.assertRaisesRegex(ValueError, "canonical_license_bytes"):
                    recovery.license_binding()
                os.environ["GRB_LICENSE_FILE"] = str(path.parent)
                with self.assertRaisesRegex(ValueError, "canonical_license_path"):
                    recovery.license_binding()

    def test_submitted_environment_exports_the_canonical_file(self):
        with patch.dict(
            os.environ, {"GRB_LICENSE_FILE": "/wrong", "SLURM_JOB_ID": "3891"}
        ):
            environment = pilot.clean_env()
        self.assertEqual(environment["GRB_LICENSE_FILE"], str(recovery.LICENSE_PATH))
        self.assertNotIn("SLURM_JOB_ID", environment)

    def test_recovery_marker_binds_parent_inputs_budget_and_license(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            stage, parent = base / "new", base / "old"
            stage.mkdir()
            parent.mkdir()
            inputs.write_once(
                stage / "inputs.private.json", {"checkpoint": "unchanged"}
            )
            inputs.write_once(stage / "preflight.json", {"source": "new"})
            accepted = inputs.digest(stage / "preflight.json")
            snapshot = {"job_id": "3891", "files_sha256": {"log": "old"}}
            license_record = {"path": "canonical", "sha256": "fixed"}
            global_claim = base / "pr98-h25-technical-pilot.claim.json"
            global_claim.write_text("preserved")
            with (
                patch.object(inputs, "EVIDENCE", base),
                patch.object(recovery, "PARENT_STAGE", parent),
                patch.object(
                    recovery,
                    "PARENT_INPUTS",
                    inputs.digest(stage / "inputs.private.json"),
                ),
                patch.object(
                    recovery, "parent_snapshot", return_value=snapshot
                ) as snapshot_reader,
                patch.object(recovery, "license_binding", return_value=license_record),
                patch.object(pilot, "admitted"),
            ):
                recovery.approve(stage, accepted, "author approved this replacement")
                snapshot_reader.assert_called_once_with(fresh_accounting=True)
                self.assertEqual(
                    recovery.claim_path(stage), base / recovery.RECOVERY_CLAIM
                )
                self.assertEqual(global_claim.read_text(), "preserved")
                with self.assertRaises(FileExistsError):
                    recovery.approve(stage, accepted, "do not silently resubmit")
                record = inputs.read(stage / recovery.MARKER)
                record["parent"]["files_sha256"]["log"] = "altered"
                (stage / recovery.MARKER).write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, "parent_evidence_changed"):
                    recovery.claim_path(stage)

    def test_recovery_rejects_changed_inputs_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder)
            inputs.write_once(stage / "inputs.private.json", {"different": True})
            with (
                patch.object(pilot, "admitted"),
                patch.object(recovery, "PARENT_INPUTS", "wrong"),
                self.assertRaisesRegex(ValueError, "unchanged_inputs"),
            ):
                recovery.approve(stage, "accepted", "decision")
            self.assertFalse((stage / recovery.MARKER).exists())

    def test_held_job_keeps_the_budget_and_original_claim(self):
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder) / "stage"
            stage.mkdir()
            destination = Path(folder) / recovery.RECOVERY_CLAIM
            original = Path(folder) / "pr98-h25-technical-pilot.claim.json"
            original.write_bytes(b"original claim")
            license_record = {"path": str(recovery.LICENSE_PATH), "sha256": "sealed"}
            prior = types.SimpleNamespace(
                command=lambda argv, **kwargs: calls.append((argv, kwargs)) or "4000",
                versions=lambda: {"python": "3.10.20"},
                storage=lambda *args, **kwargs: None,
                held_profile=lambda *args: {"checked": True},
            )
            with (
                patch.dict(sys.modules, {"pr94_isolated_preparation": prior}),
                patch.object(pilot, "admitted"),
                patch.object(recovery, "license_binding", return_value=license_record),
                patch.object(recovery, "claim_path", return_value=destination),
            ):
                pilot.submit(stage, "sealed", "approved recovery")
                with self.assertRaises(FileExistsError):
                    pilot.submit(stage, "sealed", "no second attempt")
            self.assertEqual(original.read_bytes(), b"original claim")
            sbatch = calls[0][0]
            self.assertIn(
                "--export=ALL,GRB_LICENSE_FILE=" + str(recovery.LICENSE_PATH), sbatch
            )
            for expected in (
                "--hold",
                "--no-requeue",
                "--cpus-per-task=4",
                "--mem=64G",
                "--gres=gpu:1",
                "--time=01:00:00",
            ):
                self.assertIn(expected, sbatch)
            self.assertEqual(
                [argv[0] for argv, _ in calls], ["sbatch", "scontrol", "scontrol"]
            )
            self.assertEqual(
                inputs.read(stage / "pilot-approval.json")["license"], license_record
            )

    def test_parent_requires_terminal_license_failure_and_no_scientific_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            parent = base / "parent"
            run = parent / "run/pilot"
            (run / "preparation").mkdir(parents=True)
            (parent / "source").mkdir()
            inputs.write_once(parent / "preflight.json", {"source": "original"})
            inputs.write_once(parent / "inputs.private.json", {"frozen": "inputs"})
            preflight_hash = inputs.digest(parent / "preflight.json")
            approval = {"budget": pilot.BUDGET, "preflight_sha256": preflight_hash}
            inputs.write_once(parent / "pilot-approval.json", approval)
            inputs.write_once(base / "pr98-h25-technical-pilot.claim.json", approval)
            inputs.write_once(
                parent / "pilot-submission.json",
                {
                    "job_id": "3891",
                    "preflight_sha256": recovery.PARENT_PREFLIGHT,
                    "scope": pilot.PILOT_SCOPE,
                },
            )
            inputs.write_once(
                parent / "pilot-held-profile.private.json", {"held": True}
            )
            inputs.write_once(run / "batch.json", {"job_id": "3891"})
            inputs.write_once(
                run / "preparation/root.intent.json", {"maximum_calls": 1}
            )
            inputs.write_once(
                run / "preparation.supervision.private.json",
                {
                    "child_exit_code": 1,
                    "guard_stop": None,
                },
            )
            (run / "preparation.console.private.log").write_text(
                "model.optimize(observer)\nModel too large for size-limited license\n"
            )
            (run / "preparation/gurobi.private.log").write_text("license refusal")
            (parent / "pilot-3891.private.err").write_text("preserved failure")
            (parent / "pilot-3891.private.out").write_text("")
            accounting_rows = [
                {"JobID": "3891", "State": "FAILED", "ExitCode": "1:0"},
                {"JobID": "3891.batch", "State": "FAILED", "ExitCode": "1:0"},
                {"JobID": "3891.extern", "State": "COMPLETED", "ExitCode": "0:0"},
            ]
            prior = types.SimpleNamespace(
                accounting=lambda *args: {
                    "job_id": "3891",
                    "terminal": True,
                    "rows": accounting_rows,
                }
            )
            # The fixed parent submission binds the fixed historical preflight.
            submission = inputs.read(parent / "pilot-submission.json")
            submission["preflight_sha256"] = preflight_hash
            (parent / "pilot-submission.json").write_text(json.dumps(submission))
            with (
                patch.object(inputs, "EVIDENCE", base),
                patch.object(recovery, "PARENT_STAGE", parent),
                patch.object(recovery, "PARENT_PREFLIGHT", preflight_hash),
                patch.object(
                    recovery,
                    "PARENT_INPUTS",
                    inputs.digest(parent / "inputs.private.json"),
                ),
                patch.object(
                    recovery.subprocess,
                    "check_output",
                    side_effect=lambda args, **kwargs: (
                        recovery.PARENT_SOURCE + "\n" if "rev-parse" in args else ""
                    ),
                ),
                patch.dict(sys.modules, {"pr94_isolated_preparation": prior}),
            ):
                snapshot = recovery.parent_snapshot(fresh_accounting=True)
                self.assertEqual(snapshot["job_id"], "3891")
                self.assertEqual(
                    snapshot["original_claim_sha256"],
                    inputs.digest(base / "pr98-h25-technical-pilot.claim.json"),
                )
                accounting_rows[0]["State"] = "RUNNING"
                with self.assertRaisesRegex(
                    ValueError, "parent_accounting_disposition"
                ):
                    recovery.parent_snapshot(fresh_accounting=True)
                accounting_rows[0]["State"] = "FAILED"
                (run / "preparation/forward.intent.json").write_text("{}")
                with self.assertRaisesRegex(
                    ValueError, "parent_unexpected_scientific_artifact"
                ):
                    recovery.parent_snapshot()
                (run / "preparation/forward.intent.json").unlink()
                (run / "c1-M0").mkdir()
                with self.assertRaisesRegex(ValueError, "parent_evaluation_activity"):
                    recovery.parent_snapshot()
