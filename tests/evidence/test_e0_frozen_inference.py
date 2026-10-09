"""Offline E0 receipt, historical reuse and bounded inference workflow checks."""

import ast
import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import e0_frozen_inference as flow  # noqa: E402
import review_e0_existing as historical  # noqa: E402


class E0FrozenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = flow.plan()
        cls.c1 = flow.c1.read_package(
            flow.c1.ROOT / "docs/evidence/pr80-job3503-return.json"
        )

    def fixture(self):
        inference = flow.meta.strict_json(self.c1["members"]["inference.json"]["text"])
        numerical = flow.meta.strict_json(
            self.c1["members"]["numeric/numeric.json"]["text"]
        )
        selected = flow.c1.audit.selected_parents(flow.c1.audit.source_receipt())
        template = inference["cases"][0]
        inference["protocol_id"] = flow.PROTOCOL
        inference["cases"] = []
        for cohort in ("easy", "mixed"):
            for parent in flow.CASES:
                row = copy.deepcopy(template)
                rep = numerical["parents"][parent]["representation"]
                n, p = rep["discrete_targets"], rep["positive_discrete_targets"]
                row.update(
                    cohort=cohort,
                    parent=parent,
                    role="test",
                    lp_start_source="original_root_json_values",
                    graph_sha256=selected[parent]["graph"]["sha256"],
                    root_sha256=selected[parent]["root"]["sha256"],
                    selected_support=min(20000, n // 10),
                    abstained=False,
                )
                row["metrics"].update(
                    tp=p,
                    tn=n - p,
                    fp=0,
                    fn=0,
                    n_targets=n,
                    n_positive=p,
                    precision=1.0,
                    recall=1.0,
                    f1_score=1.0,
                    accuracy=1.0,
                )
                inference["cases"].append(row)
        return inference

    def receipt(self, inference=None, **overrides):
        contents = {
            "plan.json": self.plan,
            "runtime.json": {"packages_modified": False},
            "inference.json": self.fixture() if inference is None else inference,
        }
        members = {}
        for name, value in contents.items():
            text = json.dumps(value)
            members[name] = {"text": text, "sha256": flow.meta.digest(text.encode())}
        value = {
            "protocol_id": flow.PROTOCOL,
            "members": members,
            "job_id": "123",
            "accounting": "JobID|State|ExitCode\n123|COMPLETED|0:0\n",
            "optimization_runs_added": 0,
            "training_runs_added": 0,
            "scientific_reporting_eligible": False,
            "raw_logs_included": False,
            "raw_predictions_exported": False,
            **overrides,
        }
        data = json.dumps(value).encode()
        return data, flow.meta.digest(data)

    def test_exact_population_and_frozen_models(self):
        self.assertEqual(len(flow.CASES), 10)
        self.assertEqual(sum("easy" in p for p in flow.CASES), 6)
        for parent in flow.CASES:
            self.assertEqual(flow.c1.audit.split_for(parent)[1], "test")
        self.assertEqual(self.plan["maximum_forwards"], 20)
        self.assertFalse(self.plan["solver_execution_admitted"])
        self.assertEqual(
            self.plan["models"]["mixed"]["checkpoint_sha256"],
            "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028",
        )

    def test_twenty_returns(self):
        self.assertEqual(len(flow.validate_return(*self.receipt())), 20)

    def test_tampered_outer(self):
        data, _ = self.receipt()
        with self.assertRaises(ValueError):
            flow.validate_return(data, "0" * 64)

    def test_duplicate_or_missing_case(self):
        inference = self.fixture()
        inference["cases"][-1] = inference["cases"][0]
        with self.assertRaises(ValueError):
            flow.validate_return(*self.receipt(inference))

    def test_changed_model_or_threshold_rejected(self):
        inference = self.fixture()
        inference["models"]["easy"]["threshold"] = 0.5
        with self.assertRaises(ValueError):
            flow.validate_return(*self.receipt(inference))

    def test_metric_hash_role_and_timing_rejected(self):
        for field, value in (
            ("role", "validation"),
            ("graph_sha256", "0" * 64),
            ("lp_start_source", "graph_float32_feature"),
            ("forward_seconds", -1),
            ("selected_support", 20001),
        ):
            with self.subTest(field=field):
                inference = self.fixture()
                inference["cases"][0][field] = value
                with self.assertRaises(ValueError):
                    flow.validate_return(*self.receipt(inference))
        inference = self.fixture()
        inference["cases"][0]["metrics"]["f1_score"] = 0.7
        with self.assertRaises(ValueError):
            flow.validate_return(*self.receipt(inference))

    def test_failed_job_not_promoted(self):
        with self.assertRaises(ValueError):
            flow.validate_return(
                *self.receipt(accounting="JobID|State|ExitCode\n123|FAILED|2:0\n")
            )

    def test_scope_flags(self):
        for field in (
            "optimization_runs_added",
            "training_runs_added",
            "raw_logs_included",
            "raw_predictions_exported",
            "scientific_reporting_eligible",
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                flow.validate_return(*self.receipt(**{field: 1}))

    def test_run_reuses_numerical_member_no_audit(self):
        env = {
            "SLURM_JOB_NUM_NODES": "1",
            "SLURM_CPUS_PER_TASK": "4",
            "SLURM_MEM_PER_NODE": "32768",
            "SLURM_RESTART_COUNT": "0",
        }
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(flow.os.environ, env),
            patch.object(flow.legacy, "infer", return_value=self.fixture()) as infer,
        ):
            output = Path(folder) / "run"
            self.assertEqual(flow.run(Path(folder), output), 0)
            self.assertEqual(
                (output / "numeric/numeric.json").read_bytes(),
                self.c1["members"]["numeric/numeric.json"]["text"].encode(),
            )
            self.assertEqual(infer.call_args.kwargs["cases"], flow.CASES)
            self.assertTrue(infer.call_args.kwargs["original_root_values"])
            with self.assertRaises(FileExistsError):
                flow.run(Path(folder), output)

    def test_wrong_allocation(self):
        with patch.dict(flow.os.environ, {}, clear=True), self.assertRaises(ValueError):
            flow.run(Path("."), Path("uncreated"))

    def test_operator_one_submission_and_nonblocking(self):
        text = (Path(flow.__file__).parent / "operate_e0_inference.sh").read_text()
        self.assertEqual(text.count("sbatch --parsable"), 1)
        for flag in (
            "--gres=gpu:1",
            "--mem=32G",
            "--nodes=1-1",
            "--no-requeue",
            "--time=00:40:00",
        ):
            self.assertIn(flag, text)
        self.assertLess(
            text.index('mkdir "$STAGE/submission.started"'),
            text.index("sbatch --parsable"),
        )
        for forbidden in ("while ", "sleep ", "pip install", "conda create"):
            self.assertNotIn(forbidden, text)

    def test_no_solver_training_calls(self):
        for module in (flow, flow.legacy):
            tree = ast.parse(Path(module.__file__).read_text())
            for call in (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            ):
                self.assertNotIn(
                    call.func.attr,
                    {"optimize", "optimizeAsync", "backward", "step", "fit_prenorm"},
                )

    def test_historical_review_counts_and_unpaired_control(self):
        receipt, cells, rows, effects, excluded = historical.review()
        self.assertEqual(
            (len(cells), len(rows), len(effects), len(excluded)), (48, 24, 16, 1)
        )
        self.assertEqual(len({p["sha256"] for p in receipt["plans"]}), 3)
        self.assertEqual(excluded[0]["parent"], "CFL_medium_instance_0")
        self.assertFalse(any(r["new_control_admitted"] for r in rows))

    def test_historical_tables_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "review"
            historical.produce(output)
            for path in output.glob("*.csv"):
                self.assertEqual(
                    path.read_bytes(),
                    (historical.SOURCE.parent / "results" / path.name).read_bytes(),
                )

    def test_package_preserves_and_excludes_predictions(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            stage = Path(folder)
            (stage / "run").mkdir()
            (stage / "run/predictions.json").write_text("PRIVATE")
            (stage / "run/plan.json").write_text("{}")
            (stage / "job_id.txt").write_text("123")
            (stage / "source_commit.txt").write_text("a" * 40)
            (stage / "accounting.txt").write_text(
                "JobID|State|ExitCode\n123|FAILED|2:0\n"
            )
            flow.package(stage)
            data = (stage / "public_return.json").read_bytes()
            self.assertNotIn(b"PRIVATE", data)
            flow.package(stage)
            self.assertEqual(data, (stage / "public_return.json").read_bytes())
            (stage / "run/plan.json").write_text('{"changed":true}')
            with self.assertRaises(ValueError):
                flow.package(stage)


if __name__ == "__main__":
    unittest.main()
