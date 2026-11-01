"""Offline negative tests for PR94 provenance and reservation accounting."""

import ast
import csv
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs/research/solver-seed-extension-v1"
SPEC = importlib.util.spec_from_file_location(
    "pr94_plan", ROOT / "scripts/evidence/plan_pr94_preparation.py"
)
PLAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLAN)


class PreparationPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name) / "package"
        shutil.copytree(PACKAGE, self.package)

    def json_change(self, name, change):
        path = self.package / name
        value = json.loads(path.read_text(encoding="utf-8"))
        change(value)
        path.write_text(json.dumps(value), encoding="utf-8")
        self.reseal(name)

    def reseal(self, name):
        path = self.package / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if name in manifest["artifacts"]:
            manifest["artifacts"][name] = hashlib.sha256(
                (self.package / name).read_bytes()
            ).hexdigest()
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def cell_change(self, change):
        path = self.package / "planned-cells.csv"
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
        change(rows)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=list(rows[0]), lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        self.reseal(path.name)

    def test_complete_but_unreleased_preparation(self):
        output = PLAN.compile_plan(self.package)
        self.assertEqual(output["new-artifact-bindings.json"]["generated_artifacts"], 0)
        new = output["new-artifact-bindings.json"]["parents"]
        self.assertEqual(len(new), 6)
        self.assertTrue(all(not r["generated"] for r in new))
        self.assertTrue(
            all(v is None for row in new for v in row["artifacts"].values())
        )
        self.assertFalse(output["preparation-contract.json"]["execution_authorized"])
        groups = output["preparation-contract.json"]["ordered_evaluation_groups"]
        self.assertEqual(len(groups), 18)
        self.assertEqual(sum(len(g["cells"]) for g in groups), 54)

    def test_committed_metadata_reproduces_the_offline_compiler(self):
        generated = PLAN.compile_plan(self.package)
        for name, value in generated.items():
            self.assertEqual(value, PLAN.read_json(self.package / name))

    def test_reservation_and_optimizer_time_have_different_denominators(self):
        value = PLAN.budget()
        self.assertEqual(value["optimizer_hours_ceiling"], 55)
        self.assertEqual(value["serial_job_wall_hours_ceiling"], 75)
        self.assertEqual(value["reserved_physical_core_hours_ceiling"], 78)
        self.assertEqual(value["reserved_gpu_hours_ceiling"], 1)
        self.assertEqual(value["reserved_memory_gib_hours_ceiling"], 4800)
        self.assertEqual(value["optimization_calls_ceiling"], 60)
        self.assertEqual(value["jobs_ceiling"], 20)
        for stage in value["stages"]:
            self.assertLess(
                stage["children_per_job"] * stage["child_deadline_seconds"],
                stage["wall_seconds_each"],
            )

    def test_modified_package_bytes_fail_before_compilation(self):
        with (self.package / "cohort.csv").open("a", encoding="utf-8") as stream:
            stream.write("tampered")
        with self.assertRaisesRegex(ValueError, "artifact_bytes"):
            PLAN.compile_plan(self.package)

    def test_missing_or_changed_original_hash_blocks_preparation(self):
        self.cell_change(
            lambda rows: next(r for r in rows if r["parent"] in PLAN.PARENTS).update(
                model_sha256="f" * 64
            )
        )
        with self.assertRaisesRegex(ValueError, "input_hash"):
            PLAN.compile_plan(self.package)

    def test_checkpoint_cannot_be_replaced_by_gpu_training_weights(self):
        self.json_change(
            "manifest.json",
            lambda value: value["learning"].update(checkpoint_sha256="f" * 64),
        )
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            PLAN.compile_plan(self.package)

    def test_attempted_release_or_assigned_job_is_rejected(self):
        self.cell_change(lambda rows: rows[-1].update(assigned_job_id="9999"))
        with self.assertRaisesRegex(ValueError, "execution_flag"):
            PLAN.compile_plan(self.package)

    def test_duplicate_method_cannot_hide_a_missing_arm(self):
        def change(rows):
            group = [
                r
                for r in rows
                if r["parent"] == PLAN.PARENTS[0] and r["solver_seed"] == "42"
            ]
            group[-1]["method"] = group[0]["method"]

        self.cell_change(change)
        with self.assertRaisesRegex(ValueError, "methods"):
            PLAN.compile_plan(self.package)

    def test_readonly_receipt_cannot_include_an_optimization(self):
        self.json_change(
            "preflight-return-20261101.json",
            lambda value: value["report"].update(optimization_calls_added=1),
        )
        with self.assertRaisesRegex(ValueError, "readonly_receipt"):
            PLAN.compile_plan(self.package)

    def test_incomplete_input_is_not_an_empty_success(self):
        self.json_change(
            "preflight-return-20261101.json",
            lambda value: value["report"]["rows"][0].update(issues=["missing"]),
        )
        with self.assertRaisesRegex(ValueError, "preflight"):
            PLAN.compile_plan(self.package)

    def test_unsafe_or_duplicate_source_reference_is_rejected(self):
        self.json_change(
            "source-bindings.json",
            lambda value: value["sources"][0].update(path="../other.py"),
        )
        with self.assertRaisesRegex(ValueError, "source_path"):
            PLAN.compile_plan(self.package)

    def test_label_free_encoder_is_a_required_dependency(self):
        self.json_change(
            "source-bindings.json",
            lambda value: value.update(
                sources=[
                    x
                    for x in value["sources"]
                    if not x["path"].endswith("label_free_gurobi.py")
                ]
            ),
        )
        with self.assertRaisesRegex(ValueError, "source_coverage"):
            PLAN.compile_plan(self.package)

    def test_source_hashes_are_checked_without_importing_their_code(self):
        self.assertIsNone(
            PLAN.verify_sources(
                PLAN.read_json(self.package / "source-bindings.json"), ROOT
            )
        )
        fake_source = Path(self.temp.name) / "source"
        first = PLAN.read_json(self.package / "source-bindings.json")["sources"][0]
        dest = fake_source / first["path"]
        dest.parent.mkdir(parents=True)
        dest.write_text("changed source", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source_bytes"):
            PLAN.verify_sources(
                PLAN.read_json(self.package / "source-bindings.json"), fake_source
            )

    def test_historical_artifact_chains_are_preserved_separately(self):
        value = PLAN.read_json(self.package / "historical-artifact-bindings.json")
        self.assertEqual(len(value["parents"]), 10)
        self.assertTrue(
            all(
                len(row[key]) == 64
                for row in value["parents"]
                for key in PLAN.ARTIFACT_KEYS
            )
        )

    def test_planner_contains_no_model_or_scheduler_execution_api(self):
        tree = ast.parse(Path(PLAN.__file__).read_text(encoding="utf-8"))
        modules = {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        modules |= {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertEqual(
            modules, {"argparse", "csv", "hashlib", "json", "re", "pathlib"}
        )
        self.assertNotIn(".optimize(", ast.unparse(tree))
        self.assertNotIn("subprocess", ast.unparse(tree))


if __name__ == "__main__":
    unittest.main()
