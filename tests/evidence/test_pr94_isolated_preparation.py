"""Offline PR94 admission/fault tests; no scheduler, solver, GPU or training."""

import ast
import gzip
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
flow = importlib.import_module("pr94_isolated_preparation")
science = importlib.import_module("pr94_preparation_science")


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.stage = self.base / "stage"
        self.stage.mkdir()
        (self.stage / "claims").mkdir()
        (self.stage / "run").mkdir()
        self.plan = {
            "protocol_id": "pr94_isolated_preparation_v1",
            "environment": flow.VERSIONS,
            "source": {"commit": "a" * 40},
            "parents": [],
        }
        flow.write_once(self.stage / "plan.json", self.plan)
        flow.write_once(self.stage / "inputs.private.json", {"private": "never_export"})
        self.mip = self.base / "model.lp"
        self.mip.write_bytes(b"synthetic-model")

    def test_installation_template_has_no_scientific_dispatch(self):
        source = (
            ROOT / "scripts/evidence/install_pr94_preparation.template.sh"
        ).read_text(encoding="utf-8")
        body = source.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        tree = ast.parse(body)
        methods = {
            n.func.attr
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        self.assertTrue({"freeze", "inspect", "find_checkpoint"} <= methods)
        self.assertFalse(
            {"submit", "run", "root_child", "guidance_child", "capture", "optimize"}
            & methods
        )
        self.assertNotIn("sbatch ", source)

    def test_freeze_and_inspect_import_no_solver_or_torch(self):
        stage = self.base / ("pr94-preparation-" + "a" * 12)
        source = stage / "source"
        source.mkdir(parents=True)
        package = source / "docs/research/solver-seed-extension-v1"
        package.mkdir(parents=True)
        (package / "manifest.json").write_bytes(b"immutable-package")
        (source / "code.py").write_bytes(b"source")
        parents, config = (
            [],
            {"parents": {}, "checkpoint_path": str(self.base / "checkpoint")},
        )
        Path(config["checkpoint_path"]).write_bytes(b"frozen-weights")
        for i, parent in enumerate(flow.PARENTS):
            path = self.base / ("model-" + str(i))
            path.write_bytes(parent.encode())
            config["parents"][parent] = str(path)
            parents.append({"parent": parent, "model_sha256": flow.file_sha(path)})
        config_path = self.base / "inputs.json"
        flow.write_once(config_path, config)
        derived = {
            "new-artifact-bindings.json": {"parents": parents},
            "preparation-contract.json": {},
            "reservation-budget.json": {},
        }
        with (
            patch.object(flow, "host"),
            patch.object(flow, "SOURCE", source),
            patch.object(flow, "DATA", self.base),
            patch.object(flow, "EVIDENCE", self.base),
            patch.object(
                flow, "CHECKPOINT", flow.file_sha(Path(config["checkpoint_path"]))
            ),
            patch.object(flow, "versions", return_value=flow.VERSIONS),
            patch.object(flow, "compile_plan", return_value=derived),
            patch.object(flow, "storage", return_value={"checked": True}),
            patch.object(
                flow,
                "source_snapshot",
                return_value={"commit": "a" * 40, "sha256_lf": {"code.py": "a" * 64}},
            ),
            patch.dict(sys.modules, {"gurobipy": None, "torch": None}),
        ):
            frozen = flow.freeze(stage, config_path)
            self.assertEqual(frozen["new_scientific_calls"], 0)
            result = flow.inspect(stage)
            self.assertTrue(Path(result["ARQUIVO_HPC"]).is_file())
            with self.assertRaisesRegex(ValueError, "already_frozen"):
                flow.freeze(stage, config_path)

    def test_lookup_uses_only_preselected_report_and_no_tensor_deserialization(self):
        folder = self.base / "models" / "prior-run"
        folder.mkdir(parents=True)
        checkpoint = folder / "weights.pt"
        checkpoint.write_bytes(b"frozen")
        report = {
            "outputs": {
                "checkpoint": {
                    "file_name": "weights.pt",
                    "sha256": flow.file_sha(checkpoint),
                }
            }
        }
        rp = folder / "gasse_training_report.json"
        flow.write_once(rp, report)
        with (
            patch.object(flow, "REPORT_SHA", flow.file_sha(rp)),
            patch.object(flow, "CHECKPOINT", flow.file_sha(checkpoint)),
            patch.dict(sys.modules, {"torch": None, "gurobipy": None}),
        ):
            result, receipt = flow.find_checkpoint(self.base)
            self.assertEqual(result, checkpoint)
            self.assertEqual(receipt["tensor_deserialization_calls"], 0)
            with self.assertRaisesRegex(ValueError, "checkpoint_lookup_entries"):
                flow.find_checkpoint(self.base, entries_limit=0)
        with self.assertRaisesRegex(ValueError, "selected_checkpoint_not"):
            flow.find_checkpoint(self.base)

    def test_storage_shortfall_stops_before_any_model_load(self):
        with (
            patch.object(
                flow.shutil,
                "disk_usage",
                return_value=SimpleNamespace(free=15 * flow.GIB),
            ),
            self.assertRaisesRegex(ValueError, "free_space"),
        ):
            flow.storage(self.stage)

    def test_write_once_and_durable_claim_cannot_be_replayed(self):
        sha = flow.write_once(self.base / "immutable.json", {"a": 1})
        with self.assertRaises(FileExistsError):
            flow.write_once(self.base / "immutable.json", {"a": 2})
        self.assertEqual(flow.file_sha(self.base / "immutable.json"), sha)
        flow.claim(self.stage, "optimize", flow.PARENTS[0])
        with self.assertRaises(FileExistsError):
            flow.claim(self.stage, "optimize", flow.PARENTS[0])

    def test_duplicate_or_nonfinite_metadata_rejected(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
            p = self.base / "bad.json"
            p.write_text(raw, encoding="utf-8")
            with self.assertRaises(ValueError):
                flow.read(p)

    def test_paths_do_not_escape_private_data_scope(self):
        inside = self.base / "data"
        inside.mkdir()
        p = inside / "model"
        p.write_bytes(b"x")
        self.assertEqual(flow.safe_file(p, inside), p)
        with self.assertRaisesRegex(ValueError, "private_path"):
            flow.safe_file(self.mip, inside)

    def test_affinity_counts_physical_cores_not_SMT_threads(self):
        def topology(cpu):
            return (0, cpu // 2)

        self.assertEqual(flow.physical_mask({0, 1, 2, 3}, topology, 2), (0, 2))
        with self.assertRaisesRegex(ValueError, "physical_core_count"):
            flow.physical_mask({0, 1}, topology, 2)

    def test_accounting_keeps_empty_final_MaxRSS_and_all_steps(self):
        lines = "\n".join(
            f"123{suffix}|COMPLETED|0:0|12|00:00:01|2|64G||"
            for suffix in ("", ".batch", ".extern")
        )
        result = flow.parse_accounting(lines, "123")
        self.assertTrue(result["terminal"])
        self.assertTrue(all(r["MaxRSS"] == "" for r in result["rows"]))
        with self.assertRaisesRegex(ValueError, "accounting_steps"):
            flow.parse_accounting(lines.splitlines()[0], "123")

    def test_accounting_foreign_duplicate_or_running_step_is_not_terminal(self):
        base = "123|COMPLETED|0:0|12|00:00:01|2|64G|"
        batch = "123.batch|RUNNING|0:0|12|00:00:01|2||"
        extern = "123.extern|COMPLETED|0:0|12|00:00:01|2||"
        self.assertFalse(
            flow.parse_accounting("\n".join((base, batch, extern)), "123")["terminal"]
        )
        with self.assertRaisesRegex(ValueError, "duplicate_accounting"):
            flow.parse_accounting("\n".join((base, batch, extern, base)), "123")
        with self.assertRaisesRegex(ValueError, "accounting_ID"):
            flow.parse_accounting(
                "\n".join((base, batch, extern, base.replace("123|", "999|"))), "123"
            )

    def profile(self, kind):
        cores, time = (1, "02:00:00") if kind == "roots" else (4, "01:00:00")
        gpu = "" if kind == "roots" else ",gres/gpu=1"
        return (
            f"JobId=123 JobState=PENDING Reason=JobHeldUser Partition=batch Requeue=0 "
            f"Restarts=0 NumTasks=1 CPUs/Task={cores} TimeLimit={time} NumNodes=1-1 "
            f"NumCPUs={2 * cores} MinMemoryNode=64G TRES=cpu={2 * cores},mem=64G,node=1{gpu}"
        )

    def test_held_profiles_reject_GPU_or_resource_drift(self):
        flow.held_profile(self.profile("roots"), "123", "roots")
        flow.held_profile(self.profile("guidance"), "123", "guidance")
        for old, new in (
            ("Requeue=0", "Requeue=1"),
            ("MinMemoryNode=64G", "MinMemoryNode=128G"),
            ("TimeLimit=02:00:00", "TimeLimit=03:00:00"),
            ("Reason=JobHeldUser", "Reason=Dependency"),
        ):
            with self.assertRaises(ValueError):
                flow.held_profile(
                    self.profile("roots").replace(old, new), "123", "roots"
                )
        with self.assertRaisesRegex(ValueError, "held_GPU"):
            flow.held_profile(
                self.profile("guidance").replace(",gres/gpu=1", ""), "123", "guidance"
            )

    def test_ambiguous_submission_preserves_campaign_claim_and_is_not_retried(self):
        with (
            patch.object(flow, "host"),
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "private_inputs"),
            patch.object(flow, "storage"),
            patch.object(flow, "EVIDENCE", self.base),
            patch.object(flow, "command", return_value="unknown") as cmd,
        ):
            with self.assertRaisesRegex(ValueError, "ambiguous_submission"):
                flow.submit(
                    self.stage, "roots", flow.file_sha(self.stage / "plan.json")
                )
            self.assertTrue((self.base / "pr94-six-medium-roots.claim.json").exists())
            with self.assertRaises(FileExistsError):
                flow.submit(
                    self.stage, "roots", flow.file_sha(self.stage / "plan.json")
                )
            self.assertEqual(cmd.call_count, 1)

    def test_wrong_plan_hash_never_claims_or_submits(self):
        with (
            patch.object(flow, "host"),
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "EVIDENCE", self.base),
            patch.object(flow, "command") as cmd,
        ):
            with self.assertRaisesRegex(ValueError, "approved_plan_hash"):
                flow.submit(self.stage, "roots", "f" * 64)
            cmd.assert_not_called()
            self.assertFalse((self.base / "pr94-six-medium-roots.claim.json").exists())

    def test_bad_held_profile_never_releases_job_and_preserves_identity(self):
        answers = iter(("123", self.profile("roots").replace("Requeue=0", "Requeue=1")))
        with (
            patch.object(flow, "host"),
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "private_inputs"),
            patch.object(flow, "storage"),
            patch.object(flow, "EVIDENCE", self.base),
            patch.object(
                flow, "command", side_effect=lambda *a, **k: next(answers)
            ) as cmd,
        ):
            with self.assertRaises(ValueError):
                flow.submit(
                    self.stage, "roots", flow.file_sha(self.stage / "plan.json")
                )
            self.assertEqual(cmd.call_count, 2)
            self.assertEqual(
                flow.read(self.stage / "roots-submission.json")["job_id"], "123"
            )

    def test_guidance_cannot_be_submitted_without_root_review(self):
        with (
            patch.object(flow, "host"),
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "private_inputs"),
            patch.object(flow, "storage"),
            patch.object(flow, "EVIDENCE", self.base),
            patch.object(flow, "command") as cmd,
        ):
            with self.assertRaises(FileNotFoundError):
                flow.submit(
                    self.stage, "guidance", flow.file_sha(self.stage / "plan.json")
                )
            cmd.assert_not_called()

    def test_missing_approval_precedes_root_science(self):
        with (
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "allocation") as allocation,
        ):
            with self.assertRaises(FileNotFoundError):
                flow.root_child(self.stage, 0)
            allocation.assert_not_called()

    def test_public_export_contains_no_private_path_map(self):
        import zipfile

        out = flow.export_metadata(
            self.stage, {"inspection.json": flow.encoded({"complete": True})}
        )
        with zipfile.ZipFile(out["ARQUIVO_HPC"]) as z:
            self.assertEqual(set(z.namelist()), {"inspection.json", "manifest.json"})
            self.assertNotIn("never_export", z.read("inspection.json").decode())
            m = json.loads(z.read("manifest.json"))
            self.assertEqual(
                m["sha256"]["inspection.json"],
                flow.file_sha(self._export_bytes(z.read("inspection.json"))),
            )

    def _export_bytes(self, raw):
        p = self.base / "member"
        p.write_bytes(raw)
        return p

    def test_active_job_cannot_be_collected(self):
        with (
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "accounting", return_value={"terminal": False}),
        ):
            with self.assertRaisesRegex(ValueError, "not_terminal"):
                flow.collect(self.stage, "roots")
            self.assertFalse((self.stage / "roots-public-return.json").exists())

    def test_failed_closed_job_exports_incomplete_receipt_not_ready(self):
        state = {
            "terminal": True,
            "job_id": "123",
            "rows": [{"State": "FAILED", "ExitCode": "2:0"}],
        }
        flow.claim(self.stage, "optimize", flow.PARENTS[0])
        with (
            patch.object(flow, "load", return_value=self.plan),
            patch.object(flow, "accounting", return_value=state),
        ):
            flow.collect(self.stage, "roots")
        self.assertFalse(
            flow.read(self.stage / "roots-public-return.json")["ready_for_review"]
        )
        receipt = flow.read(self.stage / "roots-public-return.json")
        self.assertEqual(len(receipt["durable_call_intents"]), 1)
        self.assertTrue(receipt["intent_is_not_proof_of_completed_call"])

    def starts(self, abstain=False):
        from copy import deepcopy

        rows = [] if abstain else [{"variable_name": "x0", "value": 1}]
        g = dict(
            assignments=rows,
            abstained=abstain,
            binary_variables=4,
            selected_support=len(rows),
            positive_assignments=len(rows),
            assignment_sha256=flow.canonical_sha(rows),
        )
        return g, deepcopy(g)

    def test_abstention_is_preserved_without_forcing_a_Start(self):
        g, r = self.starts(True)
        flow.validate_starts(g, r, 4)
        r["abstained"] = False
        with self.assertRaisesRegex(ValueError, "abstention"):
            flow.validate_starts(g, r, 4)

    def test_Start_hash_or_match_drift_is_rejected(self):
        g, r = self.starts()
        flow.validate_starts(g, r, 4)
        r["assignment_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "Start_hash"):
            flow.validate_starts(g, r, 4)
        g, r = self.starts()
        r["positive_assignments"] = 0
        with self.assertRaises(ValueError):
            flow.validate_starts(g, r, 4)

    def test_root_round_trip_requires_the_same_vector_order_and_parameters(self):
        root = {
            "source_mip_sha256": "a" * 64,
            "effective_objective_sense": "MINIMIZE",
            "capture_method": "first_optimal_root_gurobi_mipnode",
            "solver_parameter_map": {**flow.ROOT_PARAMETERS, "ModelSense": 1},
            "variable_names": ["x0", "x1"],
            "relaxation_vector": [0.25, 0.75],
            "variable_count": 2,
            "mathematical_signature_sha256": "b" * 64,
        }
        root["variable_order_sha256"] = flow.canonical_sha(root["variable_names"])
        root["vector_sha256"] = flow.canonical_sha(root["relaxation_vector"])
        root["solver_parameter_sha256"] = flow.canonical_sha(
            root["solver_parameter_map"]
        )
        p = self.base / "root.gz"
        with gzip.open(p, "wb") as stream:
            stream.write(flow.encoded(root))
        target = {
            **root,
            "model_sha256": root["source_mip_sha256"],
            "root_sha256": flow.file_sha(p),
        }
        self.assertEqual(flow.read_root(p, target), root)
        target["vector_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "root_hash_binding"):
            flow.read_root(p, target)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.mip = self.folder / "m.lp"
        self.mip.write_bytes(b"fake_MIP")
        self.closed = self.optimized = self.node_reads = self.claimed = 0
        self.status, self.node, self.values, self.signature_changes = (
            11,
            0,
            [0.25, 0.75],
            False,
        )
        self.cb_status = 2
        self.names = ["x0", "x1"]

    def runtime(self):
        parent = self

        class Model:
            Params = SimpleNamespace()
            NumQNZs = NumQConstrs = NumGenConstrs = NumSOS = SolCount = NumStart = 0
            ModelSense = 1

            @property
            def Status(self):
                return parent.status

            def update(self):
                pass

            def getVars(self):
                return [SimpleNamespace(VarName=n) for n in parent.names]

            def optimize(self, observer):
                parent.optimized += 1
                observer(self, 4)
                observer(self, 4)

            def cbGet(self, key):
                return {1: parent.cb_status, 2: parent.node, 3: 1.0}[key]

            def cbGetNodeRel(self, variables):
                parent.node_reads += 1
                return parent.values

            def terminate(self):
                pass

        class Backend:
            original_sense = "MAXIMIZE"

            def __init__(self, *args):
                self.model = Model()

            def close(self):
                parent.closed += 1

        gp = SimpleNamespace(
            gurobi=SimpleNamespace(version=lambda: (13, 0, 1)),
            GRB=SimpleNamespace(
                MINIMIZE=1,
                OPTIMAL=2,
                Callback=SimpleNamespace(
                    MIPNODE=4, MIPNODE_STATUS=1, MIPNODE_NODCNT=2, MIPNODE_OBJBND=3
                ),
            ),
        )
        return SimpleNamespace(
            gp=gp,
            NativeModel=Backend,
            signature=lambda model: (
                "changed"
                if parent.signature_changes and parent.optimized
                else "original"
            ),
        )

    def intent(self):
        self.claimed += 1

    def capture(self):
        return science.capture(
            self.mip, flow.file_sha(self.mip), self.folder, self.intent, self.runtime()
        )

    def test_first_optimal_node_zero_observation_and_single_call(self):
        root = self.capture()
        self.assertEqual(root["relaxation_vector"], self.values)
        self.assertEqual(
            (self.optimized, self.node_reads, self.claimed, self.closed), (1, 1, 1, 1)
        )
        self.assertEqual(root["effective_objective_sense"], "MINIMIZE")

    def test_nonroot_or_nonoptimal_callback_has_no_relaxation_fallback(self):
        self.node = 1
        with self.assertRaisesRegex(ValueError, "optimal_root_missing"):
            self.capture()
        self.assertEqual((self.node_reads, self.optimized, self.closed), (0, 1, 1))

    def test_nonfinite_callback_is_failure_not_zero_vector(self):
        self.values = [float("nan"), 1.0]
        with self.assertRaisesRegex(ValueError, "optimal_root_missing"):
            self.capture()
        self.assertEqual((self.optimized, self.closed), (1, 1))

    def test_soft_memory_stop_or_changed_model_is_not_qualified(self):
        self.status = 17
        with self.assertRaisesRegex(ValueError, "optimal_root_missing"):
            self.capture()
        self.assertEqual(self.closed, 1)

    def test_changed_signature_preserves_failure_and_closes_model(self):
        self.signature_changes = True
        with self.assertRaisesRegex(ValueError, "model_changed"):
            self.capture()
        self.assertEqual(self.closed, 1)

    def test_duplicate_variables_fail_before_claim_or_solve(self):
        self.names = ["x0", "x0"]
        with self.assertRaisesRegex(ValueError, "variable_order"):
            self.capture()
        self.assertEqual((self.claimed, self.optimized, self.closed), (0, 0, 1))

    def test_failed_intent_never_calls_optimize(self):
        def blocked():
            raise FileExistsError("preserved_claim")

        with self.assertRaises(FileExistsError):
            science.capture(
                self.mip, flow.file_sha(self.mip), self.folder, blocked, self.runtime()
            )
        self.assertEqual((self.optimized, self.closed), (0, 1))


if __name__ == "__main__":
    unittest.main()
