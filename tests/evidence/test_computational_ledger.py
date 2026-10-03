"""Synthetic reconciliation checks; no licensed runtime or cluster required."""

import gzip
import hashlib
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import collect_class_statistics as classes
import collect_computational_ledger as ledger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        (self.data / "intermediate/run").mkdir(parents=True)
        self.output = self.root / "output"

    def put(self, name, value):
        path = self.data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps(value).encode())
        return path

    def report(self):
        params = {
            "Threads": 1,
            "TimeLimit": 28800,
            "Method": 2,
            "WLSSecret": "not-for-publication",
        }
        return {
            "parent": {
                "source_instance_id": "CFL_medium_instance_0",
                "role": "test",
                "sha256": "a" * 64,
            },
            "solve": {
                "objective_sense": "minimize",
                "solve_status": "timelimit",
                "solution_objective": 10,
                "best_bound": 9,
                "mip_gap_relative": 0.1,
                "solution_count": 3,
            },
            "solver_parameter_map": params,
            "solver_parameter_sha256": hashlib.sha256(
                ledger.canonical(params).encode()
            ).hexdigest(),
            "online_incumbent_capture": {"events_recorded": 3, "vectors_streamed": 3},
            "solver_versions": {"gurobi": [13, 0, 2]},
            "eligibility": {"label_eligible": True},
        }

    def test_attempt_is_hash_bound_but_does_not_certify_solutions(self):
        path = self.put(
            "intermediate/run/gurobi_parent_solve_report.json", self.report()
        )
        original = path.read_bytes()
        result = ledger.collect(self.data, self.output)
        self.assertEqual(result["supported_attempt_reports"], 1)
        self.assertIsNone(
            result["complete_gurobi_54_parent_unique_feasible_incumbents"]
        )
        self.assertEqual(path.read_bytes(), original)
        self.assertNotIn(
            "WLSSecret", (self.output / "parent_solver_ledger.csv").read_text()
        )
        self.assertEqual(ledger.verify(self.output), 7)

    def test_raw_and_operational_directories_are_not_read(self):
        for part in (
            "raw",
            "intermediate/secrets",
            "models/bootstrap",
            "analysis/tools",
        ):
            self.put(part + "/gurobi_parent_solve_report.json", self.report())
        self.assertEqual(list(ledger.discover(self.data)), [])

    def test_invalid_json_preserved_and_reported(self):
        path = self.put("models/broken.json", {})
        path.write_bytes(b"")
        result = ledger.collect(self.data, self.output)
        self.assertEqual(result["issues"], 1)
        self.assertEqual(path.read_bytes(), b"")

    def test_nonfinite_json_rejected(self):
        path = self.put("analysis/bad.json", {})
        path.write_bytes(b'{"value": NaN}')
        with self.assertRaises(ValueError):
            ledger.read_json(path)

    def test_safe_identity_range_and_boolean_counts(self):
        self.assertIsNone(ledger.identity("CFL_hard_instance_30"))
        self.assertIsNone(ledger.identity("CFL_hard_instance_01"))
        self.assertIsNone(ledger.count(True))
        self.assertIsNone(ledger.number(float("inf")))

    def test_two_attempts_remain_separate_without_summing_events(self):
        for name in ("a", "b"):
            self.put(
                f"intermediate/{name}/gurobi_parent_solve_report.json", self.report()
            )
        result = ledger.collect(self.data, self.output)
        self.assertEqual(result["supported_attempt_reports"], 2)
        self.assertEqual(result["supported_parents"], 1)
        self.assertNotIn("total_events", result)

    def test_footer_rows_not_unique_feasible_incumbents(self):
        path = self.data / "intermediate/run/incumbents.parquet"
        path.write_bytes(b"synthetic-footer")
        result = ledger.collect(
            self.data,
            self.output,
            footer_reader=lambda _: {"parquet_rows": 7, "column_names": "[]"},
        )
        self.assertEqual(result["parquet_tables_observed"], 1)
        self.assertIsNone(result["complete_scip_54_parent_unique_feasible_incumbents"])

    def test_unavailable_footer_is_missing_not_zero(self):
        (self.data / "intermediate/run/incumbents.parquet").write_bytes(b"invalid")

        def unavailable(_):
            raise ImportError()

        result = ledger.collect(self.data, self.output, footer_reader=unavailable)
        self.assertEqual(result["issues"], 1)
        self.assertIn(
            ",,,", (self.output / "incumbent_table_inventory.csv").read_text()
        )

    def test_artifact_reference_cannot_escape(self):
        path = self.put(
            "intermediate/run/gurobi_parent_solve_report.json", self.report()
        )
        value = self.report()
        value["artifacts"] = {
            "solution": {"file_name": "../solution.json", "sha256": "a" * 64}
        }
        self.assertFalse(ledger.references(path, value, self.data))

    def test_existing_output_or_nested_output_refused(self):
        with self.assertRaises(ValueError):
            ledger.collect(self.data, self.data / "new")
        self.output.mkdir()
        with self.assertRaises(ValueError):
            ledger.collect(self.data, self.output)

    def test_manifest_tamper_rejected(self):
        ledger.collect(self.data, self.output)
        (self.output / "parent_solver_ledger.csv").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            ledger.verify(self.output)

    def test_public_private_marker_rejected(self):
        ledger.collect(self.data, self.output)
        (self.output / "parent_solver_ledger.csv").write_bytes(b"/raid/private")
        with self.assertRaises(ValueError):
            ledger.verify(self.output)

    def test_membership_role_leakage_refused(self):
        records = [
            {"source_instance_id": "CFL_easy_instance_0", "role": role}
            for role in ("train", "test")
        ]
        with self.assertRaises(ValueError):
            ledger.memberships({"records": records}, "source", "hash")

    def test_roles_are_plan_specific_not_guessed_from_paths(self):
        records = [
            {
                "source_instance_id": "CFL_easy_instance_0",
                "role": "test",
                "sampling_strategy": "original",
            }
        ]
        result = ledger.memberships({"records": records}, "source", "hash")
        self.assertEqual(result[0]["role"], "test")
        self.assertFalse(result[0]["checkpoint_training_execution_verified"])

    def test_slurm_steps_not_summed_and_unknown_gpu_not_zero(self):
        header = "JobID|JobName|State|ExitCode|ElapsedRaw|TotalCPU|AllocCPUS|AllocTRES|MaxRSS|ReqMem"
        text = (
            header
            + "\n3422|training|TIMEOUT|0:0|86418||8|cpu=8,gres/gpu=1||64G\n3422.0|python|CANCELLED|0:15|86418||8||4802556K|\n"
        )
        result = ledger.hardware(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["allocated_gpus"], 1)
        self.assertIsNone(result[1]["allocated_gpus"])
        with self.assertRaises(ValueError):
            ledger.hardware(text + text.splitlines()[1] + "\n")


class FakeModel:
    ModelSense = -1

    def getAttr(self, name):
        return {
            "NumVars": 3,
            "NumConstrs": 2,
            "DNumNZs": 4,
            "NumBinVars": 2,
            "NumIntVars": 2,
            "VType": ["B", "B", "C"],
            "Sense": ["<", "="],
            "MinCoeff": 1,
            "MaxCoeff": 4,
            "MinObjCoeff": 1,
            "MaxObjCoeff": 10,
            "MinRHS": 1,
            "MaxRHS": 8,
        }.get(name, 0)

    def update(self):
        pass

    def optimize(self):
        raise AssertionError("Optimization is forbidden")


class ClassTests(unittest.TestCase):
    def test_cli_incomplete_collection_retains_report_but_exits_nonzero(self):
        fake_env = SimpleNamespace(
            setParam=lambda *_: None, start=lambda: None, dispose=lambda: None
        )
        fake_gp = SimpleNamespace(
            Env=lambda **_: fake_env,
            gurobi=SimpleNamespace(version=lambda: (13, 0, 1)),
            read=lambda *_args, **_kwargs: self.fail("No source should be read"),
        )
        original_is_file = Path.is_file
        with tempfile.TemporaryDirectory() as directory:
            raw, output = Path(directory) / "raw", Path(directory) / "output"
            raw.mkdir()
            with (
                patch.dict("os.environ", {}, clear=True),
                patch.dict(sys.modules, {"gurobipy": fake_gp}),
                patch.object(
                    Path,
                    "is_file",
                    lambda path: (
                        True
                        if path.as_posix() == classes.LICENSE
                        else original_is_file(path)
                    ),
                ),
                patch.object(
                    sys,
                    "argv",
                    [
                        classes.__file__,
                        "collect",
                        "--raw-root",
                        str(raw),
                        "--output",
                        str(output),
                    ],
                ),
                self.assertRaisesRegex(SystemExit, "PR65_CLASS_STATISTICS_INCOMPLETE"),
            ):
                runpy.run_path(classes.__file__, run_name="__main__")
            report = json.loads((output / "class_statistics_report.json").read_text())
            self.assertEqual(report["observed_parents"], 0)
            classes.verify(output)

    def test_gzip_source_passed_directly_and_stored_bytes_hash_bound(self):
        self.check_gzip_source(canonical_alias=False)

    def test_gzip_source_resolved_alias_keeps_file_identity_and_stored_hash(self):
        self.check_gzip_source(canonical_alias=True)

    def check_gzip_source(self, canonical_alias):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            if canonical_alias:
                # Exercise path normalization on every OS without symlink privileges.
                # Windows runner temp paths may also resolve from short-name aliases.
                (root / "alias").mkdir()
                raw = root / "alias" / ".." / "raw"
            path = raw / "CFL_medium_instance/LP/CFL_medium_instance_0.lp.gz"
            path.parent.mkdir(parents=True)
            payload = gzip.compress(b"synthetic LP", mtime=0)
            path.write_bytes(payload)
            seen = []

            def reader(selected):
                seen.append(selected)
                return classes.model_statistics(FakeModel())

            with patch.object(classes, "ModelReader") as licensed:
                rows = classes.collect(raw, root / "out", reader=reader)
                licensed.assert_not_called()
            # Assert outside collect's read-error handler so fixture failures surface.
            self.assertEqual(seen, [path.resolve()])
            self.assertTrue(seen[0].samefile(path))
            self.assertEqual(seen[0].suffix, ".gz")
            self.assertFalse(path.with_suffix("").exists())
            if canonical_alias:
                self.assertNotEqual(path, seen[0])
            row = rows[30]
            self.assertEqual(
                row["status"], "model_attributes_observed", row["error_type"]
            )
            self.assertEqual(row["source_file_format"], "lp.gz")
            self.assertEqual(
                row["original_lp_sha256"], hashlib.sha256(payload).hexdigest()
            )
            self.assertEqual(path.read_bytes(), payload)

    def test_two_stored_formats_are_ambiguous_not_silently_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            path = raw / "CFL_easy_instance/LP/CFL_easy_instance_0.lp"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"plain")
            Path(str(path) + ".gz").write_bytes(b"compressed")
            self.assertEqual(
                classes.original_model(raw, "easy", 0), (None, "ambiguous_lp_sources")
            )

    def test_directory_named_like_lp_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "CFL_easy_instance/LP/CFL_easy_instance_0.lp.gz").mkdir(parents=True)
            self.assertEqual(
                classes.original_model(raw, "easy", 0), (None, "unsafe_lp_source")
            )

    def test_discovery_preflight_requires_all_ninety_without_reader(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(classes, "ModelReader") as licensed,
        ):
            raw = Path(directory)
            with self.assertRaisesRegex(ValueError, "missing_lp=90"):
                classes.preflight(raw)
            for difficulty in ("easy", "medium", "hard"):
                for index in range(30):
                    suffix = ".lp.gz" if index % 2 else ".lp"
                    path = (
                        raw
                        / f"CFL_{difficulty}_instance/LP/CFL_{difficulty}_instance_{index}{suffix}"
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"fixture")
            self.assertEqual(classes.preflight(raw), 90)
            licensed.assert_not_called()

    def test_other_license_or_external_credentials_refused_before_import(self):
        for environment in (
            {"GRB_LICENSE_FILE": "/some/other/license"},
            {"GRB_WLSSECRET": "must-not-be-used"},
        ):
            with (
                patch.dict("os.environ", environment, clear=True),
                patch.object(Path, "is_file", return_value=True),
                self.assertRaises(ValueError),
            ):
                classes.ModelReader()

    def test_types_senses_density_without_optimization(self):
        model = FakeModel()
        result = classes.model_statistics(model)
        self.assertEqual(result["binary_variables"], 2)
        self.assertEqual(result["density"], 4 / 6)
        self.assertEqual(result["mean_variable_degree"], 4 / 3)
        self.assertEqual(result["source_objective_sense"], "MAXIMIZE")
        self.assertEqual(model.ModelSense, 1)

    def test_class_missingness_not_filled_with_zero(self):
        rows = [{"difficulty": "easy", **dict.fromkeys(classes.FIELDS)}]
        summary = classes.summarize(rows)
        self.assertEqual(summary[0]["observed_parents"], 0)
        self.assertIsNone(summary[0]["mean"])

    def test_all_ninety_parents_and_source_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            path = raw / "CFL_easy_instance/LP/CFL_easy_instance_0.lp"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"synthetic LP")
            output = root / "statistics"
            rows = classes.collect(
                raw, output, reader=lambda _: classes.model_statistics(FakeModel())
            )
            self.assertEqual(len(rows), 90)
            self.assertEqual(
                sum(r["status"] == "model_attributes_observed" for r in rows), 1
            )
            self.assertEqual(rows[0]["original_lp_sha256"], ledger.digest(path))
            classes.verify(output)
            self.assertEqual(path.read_bytes(), b"synthetic LP")

    def test_failed_model_keeps_no_numeric_features(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            path = raw / "CFL_hard_instance/LP/CFL_hard_instance_0.lp"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"bad LP")

            def failure(_):
                raise ValueError("/raid/private information must not escape")

            rows = classes.collect(raw, root / "output", reader=failure)
            row = next(
                r for r in rows if r["source_instance_id"] == "CFL_hard_instance_0"
            )
            self.assertEqual(row["status"], "model_read_failed")
            self.assertIsNone(row["variables"])


if __name__ == "__main__":
    unittest.main()
