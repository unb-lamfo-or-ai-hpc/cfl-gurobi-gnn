"""C1 numerical checks with synthetic arrays, never a licensed optimization."""

import ast
import copy
import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
import audit_sprint_c_numeric as audit  # noqa: E402


class Tensor:
    def __init__(self, values):
        self.values = np.asarray(values)

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.values


class NumericTests(unittest.TestCase):
    def setUp(self):
        self.names = ["binary", "continuous"]
        self.root = {
            "source_mip_sha256": "a" * 64,
            "variable_names": self.names,
            "variable_order_sha256": audit.metadata.digest(
                audit.metadata.canonical(self.names)
            ),
            "relaxation_vector": [0.5, 0.25],
            "vector_sha256": audit.metadata.digest(
                audit.metadata.canonical([0.5, 0.25])
            ),
            "effective_objective_sense": "MINIMIZE",
            "capture_method": "first_optimal_root_gurobi_mipnode",
        }
        self.record = {"mip_sha256_declared": "a" * 64, "label_gap_declared": 0.05}
        self.label = {
            "effective_objective_sense": "MINIMIZE",
            "source_mip_sha256": "a" * 64,
            "solution_source": "independent_gurobi_optimization",
            "mip_gap_relative": 0.05,
            "variables": [
                {"name": "continuous", "value": 0.25},
                {"name": "binary", "value": 1.0},
            ],
            "solution_objective": 2.75,
        }
        self.arrays = {
            "values": np.array([1.0, 0.25]),
            "lower": np.array([0.0, 0.0]),
            "upper": np.array([1.0, float("inf")]),
            "types": np.array(["B", "C"]),
            "objective": np.array([2.0, 3.0]),
            "rows": np.array([0, 0]),
            "columns": np.array([0, 1]),
            "coefficients": np.array([1.0, 2.0]),
            "senses": np.array(["<"]),
            "rhs": np.array([2.0]),
        }
        log = np.log1p
        self.graph = {
            "variable": SimpleNamespace(
                x=Tensor(
                    np.array(
                        [
                            [log(2), 0, log(1), 0, 1, 0, 0.5],
                            [log(3), 0, log(60000), 1, 0, 0, 0.25],
                        ],
                        dtype=np.float32,
                    )
                ),
                y=Tensor(np.array([1.0, 0.25], dtype=np.float32)),
                is_discrete=Tensor(np.array([1.0, 0.0], dtype=np.float32)),
            ),
            "constraint": SimpleNamespace(
                x=Tensor(np.array([[log(2), 1, 0, 0, 1]], dtype=np.float32))
            ),
            ("constraint", "coef", "variable"): SimpleNamespace(
                edge_index=Tensor([[0, 0], [0, 1]]),
                edge_attr=Tensor(np.array([[log(1)], [log(2)]], dtype=np.float32)),
            ),
            ("variable", "rev_coef", "constraint"): SimpleNamespace(
                edge_index=Tensor([[0, 1], [0, 0]]),
                edge_attr=Tensor(np.array([[log(1)], [log(2)]], dtype=np.float32)),
            ),
        }

    def test_real_receipt_and_unique_parents(self):
        receipt = audit.source_receipt()
        parents = audit.selected_parents(receipt)
        self.assertEqual(len(parents), 54)
        self.assertEqual(sum(k.startswith("CFL_easy_") for k in parents), 30)
        self.assertEqual(receipt["bytes_read"], 4015070716)
        for parent, record in parents.items():
            self.assertEqual(audit.split_for(parent)[1], record["role"])

    def test_shared_parent_conflict(self):
        receipt = audit.source_receipt()
        receipt["cohorts"]["easy"]["parents"][0]["role"] = "bad"
        with self.assertRaisesRegex(audit.AuditStop, "shared_parent_conflict"):
            audit.selected_parents(receipt)

    def test_vectors_named_alignment(self):
        values, vector, obj = audit.align_vectors(
            self.names, self.root, self.label, self.record
        )
        self.assertEqual([values[n] for n in self.names], [1.0, 0.25])
        self.assertEqual(vector, [0.5, 0.25])
        self.assertEqual(obj, 2.75)

    def test_bad_root_and_label_contracts(self):
        for location, key, value in [
            ("root", "variable_names", list(reversed(self.names))),
            ("root", "variable_order_sha256", "0" * 64),
            ("root", "vector_sha256", "0" * 64),
            ("root", "relaxation_vector", [float("nan"), 0.25]),
            ("root", "source_mip_sha256", "0" * 64),
            ("root", "effective_objective_sense", "MAXIMIZE"),
            ("label", "effective_objective_sense", "MAXIMIZE"),
            ("label", "mip_gap_relative", 0.11),
            ("label", "source_mip_sha256", "0" * 64),
            ("label", "solution_objective", float("nan")),
            ("label", "solution_source", "unknown"),
            ("label", "variables", [{"name": "binary", "value": 1.0}] * 2),
        ]:
            with self.subTest(location=location, key=key):
                root, label = copy.deepcopy(self.root), copy.deepcopy(self.label)
                (root if location == "root" else label)[key] = value
                with self.assertRaises(audit.AuditStop):
                    audit.align_vectors(self.names, root, label, self.record)

    def test_all_features_and_edges(self):
        result = audit.check_graph_arrays(self.graph, self.arrays, [0.5, 0.25])
        self.assertEqual(result["feature_dimensions"], [7, 5, 1])
        self.assertEqual(result["clipped_or_infinite_source_entries"]["upper"], 1)

    def test_edge_order_not_mathematical_identity(self):
        for kind in [
            ("constraint", "coef", "variable"),
            ("variable", "rev_coef", "constraint"),
        ]:
            self.graph[kind].edge_index.values = self.graph[kind].edge_index.values[
                :, ::-1
            ]
            self.graph[kind].edge_attr.values = self.graph[kind].edge_attr.values[::-1]
        audit.check_graph_arrays(self.graph, self.arrays, [0.5, 0.25])

    def test_feature_tampering(self):
        for node, attr in [
            ("variable", "x"),
            ("constraint", "x"),
            ("variable", "y"),
            ("variable", "is_discrete"),
            (("constraint", "coef", "variable"), "edge_attr"),
            (("variable", "rev_coef", "constraint"), "edge_index"),
        ]:
            with self.subTest(node=node, attr=attr):
                graph = copy.deepcopy(self.graph)
                getattr(graph[node], attr).values.flat[0] += 1
                with self.assertRaises(audit.AuditStop):
                    audit.check_graph_arrays(graph, self.arrays, [0.5, 0.25])

    def test_root_requires_exact_float32(self):
        self.graph["variable"].x.values[0, 6] = np.nextafter(
            np.float32(0.5), np.float32(1)
        )
        with self.assertRaisesRegex(audit.AuditStop, "root_feature_exact"):
            audit.check_graph_arrays(self.graph, self.arrays, [0.5, 0.25])

    def test_nonfinite_graph_rejected(self):
        self.graph["variable"].x.values[0, 0] = float("nan")
        with self.assertRaises(audit.AuditStop):
            audit.check_graph_arrays(self.graph, self.arrays, [0.5, 0.25])

    def test_encoding_contract(self):
        np.testing.assert_array_equal(
            audit.encoding([1e10, float("inf")]),
            np.array([np.log1p(60000)] * 2, dtype=np.float32),
        )
        with self.assertRaises(audit.AuditStop):
            audit.encoding([float("nan")])

    def fake_model(self):
        rows = [SimpleNamespace(Sense="<", RHS=2.0)]
        vars_ = [
            SimpleNamespace(VarName=n, LB=0.0, UB=ub, VType=t, Obj=obj)
            for n, ub, t, obj in zip(
                self.names, [1.0, float("inf")], ["B", "C"], [2.0, 3.0]
            )
        ]
        coo = SimpleNamespace(
            row=np.array([0, 0]), col=np.array([0, 1]), data=np.array([1.0, 2.0])
        )
        return SimpleNamespace(
            NumQConstrs=0,
            NumGenConstrs=0,
            NumQNZs=0,
            NumSOS=0,
            ObjCon=0.0,
            getVars=lambda: vars_,
            getConstrs=lambda: rows,
            getPWLObj=lambda _: [],
            getA=lambda: SimpleNamespace(tocoo=lambda: coo),
        )

    def test_reuses_actual_mathematical_auditor(self):
        _, result = audit.numeric_arrays(
            self.fake_model(), {"binary": 1.0, "continuous": 0.25}, 2.75
        )
        self.assertTrue(result["valid"])
        for values, objective in [
            ({"binary": 0.5, "continuous": 0.25}, 1.75),
            ({"binary": 1.0, "continuous": 1.0}, 5.0),
            ({"binary": 1.0, "continuous": -0.1}, 1.7),
            ({"binary": 1.0, "continuous": 0.25}, 999.0),
        ]:
            with (
                self.subTest(values=values, objective=objective),
                self.assertRaisesRegex(audit.AuditStop, "label_infeasible"),
            ):
                audit.numeric_arrays(self.fake_model(), values, objective)

    def test_extended_model_rejected(self):
        model = self.fake_model()
        model.NumSOS = 1
        with self.assertRaisesRegex(audit.AuditStop, "unsupported_model"):
            audit.numeric_arrays(model, {}, 0.0)
        model.NumSOS = 0
        model.getPWLObj = lambda _: [(0.0, 1.0)]
        with self.assertRaisesRegex(audit.AuditStop, "pwl_objective"):
            audit.numeric_arrays(model, {}, 0.0)

    def test_no_optimization_or_unsafe_loader_call(self):
        tree = ast.parse(Path(audit.__file__).read_text())
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        self.assertFalse(
            any(
                isinstance(n.func, ast.Attribute)
                and n.func.attr in {"optimize", "optimizeAsync", "presolve", "relax"}
                for n in calls
            )
        )
        loads = [
            n
            for n in calls
            if isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "torch"
            and n.func.attr == "load"
        ]
        self.assertEqual(len(loads), 1)
        self.assertTrue(
            next(k.value.value for k in loads[0].keywords if k.arg == "weights_only")
        )

    def test_bounded_gzip_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.json.gz"
            path.write_bytes(gzip.compress(b'{"a":1}'))
            self.assertEqual(audit.bounded_json_gzip(path), {"a": 1})
            path.write_bytes(gzip.compress(b'{"a":1,"a":2}'))
            with self.assertRaises(ValueError):
                audit.bounded_json_gzip(path)

    def test_operator_preserves_partial_and_never_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            data = base / "data"
            data.mkdir()
            output = base / "output"
            calls = []

            def child(command, **kwargs):
                calls.append(command)
                self.assertTrue(kwargs["timeout"] <= audit.CHILD_SECONDS)
                self.assertEqual(kwargs["env"]["CUDA_VISIBLE_DEVICES"], "")
                target = Path(command[command.index("--output") + 1])
                parent = command[-1]
                target.write_text(
                    json.dumps(
                        {
                            "parent": parent,
                            "state": "unqualified",
                            "stage": "restricted_graph_load",
                            "optimization_runs_added": 0,
                        }
                    )
                )
                return SimpleNamespace(returncode=0)

            with (
                patch.object(audit.sys, "platform", "linux"),
                patch.object(audit.subprocess, "run", child),
            ):
                result = audit.collect(data, output)
                self.assertEqual(len(calls), 1)
                self.assertFalse(result["training_admitted"])
                self.assertFalse(result["cohorts"]["mixed"]["numeric_checks_passed"])
                self.assertEqual(
                    sum(
                        r["state"] == "not_attempted_after_stop"
                        for r in result["parents"].values()
                    ),
                    53,
                )
                with self.assertRaisesRegex(
                    audit.AuditStop, "unsafe_or_existing_output"
                ):
                    audit.collect(data, output)
                self.assertEqual(len(calls), 1)

    def test_real_cli_help_no_solver_import(self):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPTS / "audit_sprint_c_numeric.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("collect", result.stdout)

    def test_operator_spool_and_bounded_submission_contract(self):
        script = (SCRIPTS / "operate_pr80_numeric.sh").read_text()
        self.assertIn("SOURCE=${PR80_SOURCE:?missing frozen source}", script)
        self.assertIn("export PR80_PYTHON PR80_SOURCE", script)
        self.assertEqual(script.count("sbatch --parsable"), 1)
        for option in (
            "--nodes=1-1",
            "--ntasks=1",
            "--cpus-per-task=1",
            "--mem=16G",
            "--time=00:16:00",
            "--no-requeue",
        ):
            self.assertIn(option, script)
        self.assertLess(
            script.index('mkdir "$STAGE/submission.started"'),
            script.index("sbatch --parsable"),
        )
        self.assertNotIn("sleep ", script)
        self.assertNotIn("while ", script)
        self.assertNotRegex(script, r"(?m)^\s*rm\s")

    @unittest.skipUnless(sys.platform == "linux", "Linux shell operator fixture")
    def test_shell_submit_spool_status_collect_without_scheduler(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            stage = base / "numeric-fixture"
            source = stage / "source"
            evidence = source / "scripts/evidence"
            evidence.mkdir(parents=True)
            script = (
                (SCRIPTS / "operate_pr80_numeric.sh")
                .read_text()
                .replace(
                    "/raid/vrcelestino/data/cfl-mvp2-evidence/pr80/", str(base) + "/"
                )
            )
            operator = evidence / "operate_pr80_numeric.sh"
            operator.write_text(script)
            mocks = base / "bin"
            mocks.mkdir()
            commands = {
                "hostname": "#!/bin/sh\necho dgx-dasci\n",
                "sbatch": '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$PR80_SOURCE/../submitted.args"\necho 12345\n',
                "sacct": "#!/bin/sh\necho '12345|COMPLETED|0:0'\n",
            }
            for name, text in commands.items():
                path = mocks / name
                path.write_text(text)
                path.chmod(0o700)
            environment = dict(
                os.environ, PATH=str(mocks) + os.pathsep + os.environ["PATH"]
            )

            def run(action, path=operator, env=environment):
                return subprocess.run(
                    ["bash", str(path), action],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            interpreter = stage / "venv/bin/python3"
            interpreter.parent.mkdir(parents=True)
            interpreter.symlink_to(sys.executable)
            (evidence / "sprint_c_runtime.py").write_text("raise SystemExit(2)\n")
            self.assertNotEqual(run("submit").returncode, 0)
            self.assertFalse((stage / "submission.started").exists())
            self.assertFalse((stage / "submitted.args").exists())
            (evidence / "sprint_c_runtime.py").write_text(
                "import pathlib,sys\nif '--output' in sys.argv:\n p=pathlib.Path(sys.argv[sys.argv.index('--output')+1]); p.write_text('{}')\n"
            )
            first = run("submit")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual((stage / "job_id.txt").read_text().strip(), "12345")
            self.assertNotEqual(run("submit").returncode, 0)
            self.assertIn("--nodes=1-1", (stage / "submitted.args").read_text())
            # Slurm executes this copy outside SOURCE; PR80_SOURCE must survive.
            spool = base / "slurm_script"
            spool.write_text(script)
            (evidence / "audit_sprint_c_numeric.py").write_text(
                "import pathlib,sys\np=pathlib.Path(sys.argv[sys.argv.index('--output')+1]); p.mkdir(); (p/'numeric.json').write_text('{}')\n"
            )
            batch_env = dict(
                environment,
                PR80_SOURCE=str(source),
                PR80_PYTHON=str(interpreter),
                SLURM_JOB_NUM_NODES="1",
                SLURM_CPUS_PER_TASK="1",
                SLURM_MEM_PER_NODE="16384",
                SLURM_RESTART_COUNT="0",
                SLURM_JOB_GPUS="",
                SLURM_STEP_GPUS="",
            )
            result = run("batch", spool, batch_env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotEqual(run("batch", spool, batch_env).returncode, 0)
            self.assertEqual(run("status").returncode, 0)
            collected = run("collect")
            self.assertEqual(collected.returncode, 0, collected.stderr)
            self.assertIn("JOB_STATE=COMPLETED", collected.stdout)


if __name__ == "__main__":
    unittest.main()
