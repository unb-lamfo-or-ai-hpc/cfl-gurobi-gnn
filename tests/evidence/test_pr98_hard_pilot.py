import gzip
import hashlib
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "evidence"
sys.path.insert(0, str(SCRIPTS))
import pr98_hard_inputs as inputs  # noqa: E402
import pr98_hard_pilot as pilot  # noqa: E402

LP = b"\\ synthetic fixture\nMaximize\n obj: x0\nSubject To\n c: x0 <= 1\nBinaries\n x0\nEnd\n"


class HardInputTests(unittest.TestCase):
    def test_same_decoded_bytes_do_not_replace_the_archived_gzip_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            folder = data / "raw/MILPBench/CFL/CFL_hard_instance/LP"
            folder.mkdir(parents=True)
            model = folder / "CFL_hard_instance_25.lp.gz"
            original = gzip.compress(LP, mtime=0)
            model.write_bytes(original)
            model.with_suffix("").write_bytes(LP)
            archive = {"H25": (len(original), hashlib.sha256(original).hexdigest())}
            with patch.object(inputs, "ARCHIVE", archive):
                records, bound = inputs.inspect_models(data, time.monotonic() + 10)
                self.assertEqual(records["H25"]["status"], "PaScal_model_bytes_matched")
                self.assertEqual(Path(bound["H25"]["model"]), model.resolve())
                model.unlink()
                records, bound = inputs.inspect_models(data, time.monotonic() + 10)
                self.assertEqual(
                    records["H25"]["status"], "PaScal_gzip_digest_not_matched"
                )
                self.assertEqual(bound, {})

    def test_conflicting_copies_and_missing_H0_reference_do_not_admit(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            folder = data / "raw/MILPBench/CFL/CFL_hard_instance/LP"
            folder.mkdir(parents=True)
            parent = "CFL_hard_instance_0"
            (folder / (parent + ".lp")).write_bytes(LP)
            with patch.object(inputs, "ARCHIVE", {"H0": None}):
                report, bound = inputs.inspect_models(data, time.monotonic() + 10)
                self.assertEqual(
                    report["H0"]["status"], "independent_LP_reference_required"
                )
                self.assertEqual(bound, {})
                (folder / (parent + ".lp.gz")).write_bytes(
                    gzip.compress(LP.replace(b"x0", b"x1"))
                )
                report, bound = inputs.inspect_models(data, time.monotonic() + 10)
                self.assertEqual(report["H0"]["status"], "conflicting_LP_bytes")
                self.assertEqual(bound, {})


class PilotTests(unittest.TestCase):
    def test_budget_and_effective_parameter_override(self):
        contract = types.SimpleNamespace(
            baseline_parameters=lambda: {"Threads": 1, "TimeLimit": 3600, "Method": -1}
        )
        with patch.dict(sys.modules, {"pr94_evaluation_contract": contract}):
            for concurrency in (1, 2):
                parameters = pilot.Policy.parameters({"concurrent": concurrency})
                self.assertEqual(parameters["ConcurrentMIP"], concurrency)
                self.assertEqual(parameters["Threads"], 4)
                self.assertEqual(parameters["TimeLimit"], 120)
                self.assertEqual(parameters["Seed"], 42)
                self.assertEqual(parameters["Method"], -1)
        self.assertFalse(pilot.Policy.RECORD_PROGRESS)
        self.assertEqual(
            pilot.BUDGET["pilot_solve_calls"], len(pilot.PROFILES) * len(pilot.ORDER)
        )
        self.assertLess(
            pilot.ROOT_DEADLINE + pilot.SOLVE_DEADLINE * 6,
            pilot.BUDGET["wall_seconds_reserved"],
        )

    def test_failed_held_profile_cannot_release_or_resubmit(self):
        calls = []

        def command(argv, **kwargs):
            calls.append(argv)
            return "123" if argv[0] == "sbatch" else "invalid profile"

        def invalid(*args):
            raise ValueError("held_profile_mismatch")

        prior = types.SimpleNamespace(
            command=command,
            held_profile=invalid,
            storage=lambda *args, **kwargs: None,
            versions=lambda: {"python": "3.10.20"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = root / "stage"
            stage.mkdir()
            with (
                patch.dict(sys.modules, {"pr94_isolated_preparation": prior}),
                patch.object(inputs, "EVIDENCE", root),
                patch.object(pilot, "admitted", return_value=None),
            ):
                with self.assertRaisesRegex(ValueError, "held_profile_mismatch"):
                    pilot.submit(stage, "evidence_digest", "author approved H25 pilot")
                with self.assertRaises(FileExistsError):
                    pilot.submit(stage, "evidence_digest", "author approved H25 pilot")
            self.assertEqual([args[0] for args in calls], ["sbatch", "scontrol"])
            self.assertIn("--hold", calls[0])
            self.assertEqual(calls[1], ["scontrol", "show", "job", "123", "-o"])

    def test_artifact_seal_does_not_accept_altered_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            row = {"parent": "CFL_hard_instance_25", "model_sha256": "a" * 64}
            receipt = {
                **row,
                "checkpoint_sha256": inputs.CHECKPOINT,
                "root_optimization_calls": 1,
                "forward_calls": 1,
                "training_calls": 0,
                "labels_loaded": False,
                "graph_round_trip": True,
                "effective_objective_sense": "MINIMIZE",
            }
            for key, name in pilot.ARTIFACTS.items():
                path = folder / name
                path.write_bytes(b"{}")
                receipt[key] = inputs.digest(path)
            inputs.write_once(folder / "artifact-receipt.json", receipt)
            called = []
            contract = types.SimpleNamespace(
                validate_start=lambda *args: called.append(args)
            )
            with patch.dict(sys.modules, {"pr94_evaluation_contract": contract}):
                pilot.verify_artifacts(folder, row)
                self.assertEqual(len(called), 1)
                (folder / pilot.ARTIFACTS["graph_sha256"]).write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "artifact_bytes_graph_sha256"):
                    pilot.verify_artifacts(folder, row)
