"""Offline preparation/admission checks; no solver, GPU, or scheduler calls."""

import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
import mvp2_concurrent_mip as campaign  # noqa: E402
import pr98_hard_inputs as inputs  # noqa: E402
import pr98_hard_preparation as hard  # noqa: E402


class HardPreparationTests(unittest.TestCase):
    def test_H0_independent_ZIP_reference_matches_constant_and_official_directory(self):
        root = (
            Path(__file__).resolve().parents[2]
            / "docs/evidence/pr98/h0-reference-20261118"
        )
        ref = json.loads((root / "reference.json").read_text())
        directory = json.loads((root / "official-zip-directory.json").read_text())
        member = next(e for e in directory["entries"] if e["name"] == ref["member"])
        self.assertEqual(
            inputs.LP_REFERENCE["H0"], (ref["decoded_bytes"], ref["decoded_sha256"])
        )
        self.assertEqual(
            ref["decoded_sha256"],
            "261d4efb2994cb61c8c2beeb1b2ae95806ee24fd9879916693baaf1cc771ea12",
        )
        self.assertEqual(ref["member_crc32"], member["crc32"])
        self.assertEqual(ref["decoded_bytes"], member["bytes"])
        self.assertEqual(
            inputs.digest(root / "official-zip-directory.json"),
            ref["official_directory_receipt_sha256"],
        )
        self.assertTrue(ref["official_directory_exact_match"])
        self.assertTrue(ref["crc_verified"])
        self.assertEqual(len(directory["entries"]), 63)
        self.assertEqual(ref["optimization_calls"], 0)
        self.assertEqual(ref["pickle_deserializations"], 0)

    def test_only_five_new_preparations_and_no_evaluations_or_training(self):
        self.assertEqual(hard.NEW, ("H0", "H5", "H10", "H15", "H20"))
        self.assertNotIn("H25", hard.NEW)
        self.assertEqual(hard.BUDGET["new_root_calls_maximum"], 5)
        self.assertEqual(hard.BUDGET["new_forward_calls_maximum"], 5)
        self.assertEqual(hard.BUDGET["evaluation_calls"], 0)
        self.assertEqual(hard.BUDGET["training_calls"], 0)
        self.assertEqual(hard.BUDGET["root_solver_seconds"], 600)
        self.assertFalse(hard.BUDGET["automatic_retry"])

    def test_child_calls_existing_preparation_and_verifier_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "run/H0").mkdir(parents=True)
            row, model, checkpoint = (
                {"parent": "CFL_hard_instance_0"},
                Path("model"),
                Path("checkpoint"),
            )
            gate = object()
            with (
                patch.object(hard, "runtime", return_value=({}, "job", gate, {})),
                patch.object(hard, "admitted", return_value=(row, model, checkpoint)),
                patch.object(hard.pilot, "prepare") as prepare,
                patch.object(hard.pilot, "verify_artifacts") as verify,
            ):
                hard.child(stage, "sealed", "H0")
                prepare.assert_called_once_with(
                    stage / "run/H0/preparation", model, row, checkpoint, gate
                )
                verify.assert_called_once_with(stage / "run/H0/preparation", row)
                with self.assertRaisesRegex(ValueError, "new_parent"):
                    hard.child(stage, "sealed", "H25")
                self.assertEqual(prepare.call_count, 1)

    def test_failed_parent_stops_sequence_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "run").mkdir()
            calls = []

            def stopped(*args):
                calls.append(args)
                return {"guard_stop": "child_deadline_exceeded", "child_exit_code": -15}

            with (
                patch.object(hard, "runtime", return_value=({}, "job", object(), {})),
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
                self.assertRaisesRegex(ValueError, "hard_preparation_failed"),
            ):
                hard.batch(stage, "sealed")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][2], 1440)
            self.assertFalse((stage / "run/H5").exists())
            self.assertFalse((stage / "run/complete.json").exists())

    def test_submit_requires_specific_decision_before_admission(self):
        with patch.object(hard, "admitted") as admitted:
            for decision in (None, "", "approved", "AUTORIZO CAMPANHA"):
                with self.assertRaisesRegex(
                    ValueError, "specific_preparation_decision"
                ):
                    hard.submit(Path("unused"), "sealed", decision)
            admitted.assert_not_called()

    def test_collect_counts_five_new_intents_and_one_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            config = {"models": {a: {"parent": a} for a in hard.ALL}}
            for alias in hard.ALL:
                folder = stage / "run" / alias / "preparation"
                folder.mkdir(parents=True)
                (folder / "artifact-receipt.json").write_text("{}")
                if alias in hard.NEW:
                    for name in ("root.intent.json", "forward.intent.json"):
                        (folder / name).write_text("{}")
                    inputs.write_once(
                        folder.parent / "supervision.private.json",
                        {"guard_stop": None, "child_exit_code": 0},
                    )
            inputs.write_once(stage / "run/complete.json", {})
            accounting = {
                "terminal": True,
                "rows": [{"State": "COMPLETED", "ExitCode": "0:0"}],
            }
            out = io.StringIO()
            with (
                patch.object(
                    hard, "admitted", return_value=({"source_commit": "source"}, config)
                ),
                patch.object(hard.flow, "accounting", return_value=accounting),
                patch.object(
                    hard.pilot, "verify_artifacts", side_effect=lambda p, r: (r, {})
                ),
                contextlib.redirect_stdout(out),
            ):
                hard.collect(stage, "sealed")
            report = inputs.read(stage / "hard-preparation-return.json")
            self.assertTrue(report["ready_for_review"])
            self.assertEqual(report["root_intents"], 5)
            self.assertEqual(report["forward_intents"], 5)
            self.assertEqual(report["rows"]["H25"]["reused_from_job"], "3906")
            self.assertFalse(report["rows"]["H25"]["root_intent"])


class CampaignAdmissionTests(unittest.TestCase):
    def profile(self):
        return (
            "JobId=9001 ArrayJobId=9001 ArrayTaskId=0-65%4 "
            "JobState=PENDING Reason=JobHeldUser Partition=batch Requeue=0 Restarts=0 "
            "NumTasks=1 CPUs/Task=1 TimeLimit=04:00:00 JobName=cfl-mvp2-concurrent "
            "UserId=vrcelestino(1000) WorkDir=source NumNodes=1 NumCPUs=2 "
            "MinMemoryNode=64G TRES=cpu=2,mem=64G,node=1,billing=2 Dependency=(null)"
        )

    def test_held_array_identity_resources_and_dependency_checked(self):
        with patch.object(campaign, "ROOT", Path("source")):
            text = self.profile()
            self.assertEqual(
                campaign.held_profile(text, "9001", 1, 66, None)["NumCPUs"], "2"
            )
            for bad in (
                text.replace("0-65%4", "0-65%5"),
                text.replace("vrcelestino", "another"),
                text.replace("04:00:00", "08:00:00"),
                text.replace("mem=64G", "mem=32G"),
                text.replace("Dependency=(null)", "Dependency=afterany:9000"),
                text.replace("billing=2", "billing=2,gres/gpu=1"),
            ):
                with self.assertRaises(ValueError):
                    campaign.held_profile(bad, "9001", 1, 66, None)
            with self.assertRaisesRegex(ValueError, "dependency"):
                campaign.held_profile(text, "9001", 1, 66, "9000")

    def test_global_claim_and_license_export_prevent_duplicate_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stage = base / "stage"
            (stage / "claims").mkdir(parents=True)
            (stage / "inputs.private.json").write_text('{"E0":{"model_sha256":"hash"}}')
            plan = {"matrix": campaign.matrix(), "license": {"path": "canonical"}}
            calls = []

            def submit(args, **kwargs):
                self.assertTrue((base / "pr98-full-990-v1.claim.json").exists())
                self.assertEqual(kwargs["env"]["GRB_LICENSE_FILE"], "canonical")
                calls.append(args)
                return str(9000 + len(calls)) + "\n"

            with (
                patch.object(campaign, "EVIDENCE", base),
                patch.object(campaign, "admitted", return_value=plan),
                patch.object(campaign, "site_preflight", return_value={}),
                patch.object(campaign, "inspect_input"),
                patch.object(
                    campaign.shutil,
                    "disk_usage",
                    return_value=types.SimpleNamespace(free=500 * 1024**3),
                ),
                patch.object(campaign.subprocess, "check_output", side_effect=submit),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                campaign.queue(stage, "sealed", "pdi", "batch")
                with self.assertRaises(FileExistsError):
                    campaign.queue(stage, "sealed", "pdi", "batch")
            self.assertEqual(len(calls), 3)
            self.assertTrue(all("--hold" in c and "--no-requeue" in c for c in calls))
            self.assertIn("--export=ALL,GRB_LICENSE_FILE=canonical", calls[0])
            self.assertIn("--dependency=afterok:9001", calls[1])
            self.assertIn("--dependency=afterok:9002", calls[2])
            self.assertEqual(
                [next(x for x in c if x.startswith("--array=")) for c in calls],
                ["--array=0-65%4", "--array=0-131%4", "--array=0-131%4"],
            )

    def test_terminal_validation_rejects_Start_and_model_drift(self):
        row = campaign.matrix()[0]
        item = {
            "model_sha256": "model",
            "mathematical_signature_sha256": "signature",
            "selected_support": 2,
            "positive_assignments": 1,
            "M2_assignment_sha256": "start",
        }
        result = {
            "gate_status": "passed",
            "callback_errors": [],
            "optimization_calls": 1,
            "method": "M2",
            "mip_sha256": "model",
            "effective_objective_sense": "MINIMIZE",
            "fresh_model": True,
            "mathematical_model_unchanged": True,
            "parameters": {"expected": True},
            "mathematical_signature_sha256": "signature",
            "start": {
                "submitted_assignments": 2,
                "positive_assignments": 1,
                "assignment_sha256": "start",
            },
        }
        with patch.object(
            campaign,
            "policy_for",
            return_value=types.SimpleNamespace(parameters=lambda c: {"expected": True}),
        ):
            campaign.validate_result(result, row, item, "M2")
            result["start"]["assignment_sha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "Start identity"):
                campaign.validate_result(result, row, item, "M2")
            result["start"]["assignment_sha256"] = "start"
            result["mathematical_signature_sha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "mathematical model"):
                campaign.validate_result(result, row, item, "M2")

    def test_release_never_runs_if_any_held_profile_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "claims").mkdir()
            campaign.write(
                stage / "submission.json",
                {
                    "plan_sha256": "sealed",
                    "held_arrays": {"1": "9001", "4": "9002", "8": "9003"},
                },
            )
            with (
                patch.object(campaign, "admitted"),
                patch.object(
                    campaign,
                    "held_profile",
                    side_effect=ValueError("invalid held array"),
                ),
                patch(
                    "pr94_isolated_preparation.command", return_value="invalid"
                ) as command,
                self.assertRaisesRegex(ValueError, "invalid held array"),
            ):
                campaign.release(stage, "sealed")
            self.assertEqual(command.call_count, 1)
            self.assertFalse((stage / "released.json").exists())
            self.assertFalse((stage / "claims/release.json").exists())

    def test_hard_submission_is_one_held_GPU_job_and_preserves_H25(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stage = base / "new"
            stage.mkdir()
            source = base / "old/run/pilot/preparation"
            source.mkdir(parents=True)
            originals = {}
            for name in (*hard.pilot.ARTIFACTS.values(), "artifact-receipt.json"):
                raw = name.encode()
                (source / name).write_bytes(raw)
                originals[name] = raw
            calls = []

            def command(args, **kwargs):
                self.assertTrue((base / hard.CLAIM).exists())
                calls.append(args)
                return "9100" if args[0] == "sbatch" else "TimeLimit=03:00:00"

            with (
                patch.object(inputs, "EVIDENCE", base),
                patch.object(hard, "H25_STAGE", base / "old"),
                patch.object(
                    hard,
                    "admitted",
                    return_value=(
                        {"H25": {"seal": "accepted"}},
                        {"models": {"H25": {}}},
                    ),
                ),
                patch.object(hard, "h25_review", return_value={"seal": "accepted"}),
                patch.object(hard.flow, "storage"),
                patch.object(hard.flow, "command", side_effect=command),
                patch.object(hard.flow, "held_profile", return_value={"checked": True}),
                patch.object(hard.pilot, "verify_artifacts"),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                hard.submit(stage, "sealed", "AUTORIZO PREPARACAO CINCO HARD PR98")
                with self.assertRaises(FileExistsError):
                    hard.submit(stage, "sealed", "AUTORIZO PREPARACAO CINCO HARD PR98")
            self.assertEqual(len(calls), 3)
            self.assertEqual([a[0] for a in calls], ["sbatch", "scontrol", "scontrol"])
            for option in (
                "--hold",
                "--no-requeue",
                "--cpus-per-task=4",
                "--mem=64G",
                "--gres=gpu:1",
                "--time=03:00:00",
            ):
                self.assertIn(option, calls[0])
            self.assertEqual(
                originals, {p.name: p.read_bytes() for p in source.iterdir()}
            )

    @patch.dict("os.environ")
    def test_campaign_freeze_accepts_isolated_checkout_and_binds_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "source").mkdir()
            (stage / "binding-receipts").mkdir()
            parents = {r["instance"]: r["parent"] for r in campaign.matrix()}
            values = {
                a: {"parent": p, "model_sha256": str(i)}
                for i, (a, p) in enumerate(parents.items())
            }
            contract = types.SimpleNamespace(baseline_parameters=lambda: {"Method": -1})
            with (
                patch.dict(sys.modules, {"pr94_evaluation_contract": contract}),
                patch.object(campaign, "inspect_input"),
                patch.object(campaign, "source_commit", return_value="exact-source"),
                patch.object(campaign, "site_preflight", return_value={}),
                patch.object(
                    campaign.shutil,
                    "disk_usage",
                    return_value=types.SimpleNamespace(free=500 * 1024**3),
                ),
                patch.object(hard.flow, "versions", return_value={"python": "3.10.20"}),
                patch.object(
                    hard.licensing,
                    "license_binding",
                    return_value={"path": "canonical", "sha256": "sealed"},
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                campaign.freeze(stage, values)
            plan = campaign.read(stage / "plan.json")
            self.assertEqual(plan["source_commit"], "exact-source")
            self.assertEqual(plan["baseline_parameters"], {"Method": -1})
            self.assertEqual(plan["budget"]["solves"], 990)
            self.assertEqual(plan["child_deadline_seconds"], 4500)
            self.assertEqual(plan["working_storage_GiB_ceiling"], 320)

    def test_runtime_caches_stay_inside_stage_without_overriding_home(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            with patch.dict(os.environ, {"HOME": "preserve-user-home"}):
                value = hard.workspace_environment(stage, create=True)
                self.assertEqual(os.environ["HOME"], "preserve-user-home")
                self.assertTrue(
                    all(
                        Path(p).is_dir() and Path(p).is_relative_to(stage)
                        for p in value.values()
                    )
                )
                self.assertEqual(hard.workspace_environment(stage), value)
                wrong = stage / "runtime/tmp"
                wrong.rmdir()
                wrong.write_text("invalid cache path")
                with self.assertRaisesRegex(ValueError, "runtime_cache_path"):
                    hard.workspace_environment(stage)
