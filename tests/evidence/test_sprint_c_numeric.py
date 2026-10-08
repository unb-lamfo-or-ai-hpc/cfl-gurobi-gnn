"""C1 numerical checks with synthetic arrays, never a licensed optimization."""

import ast
import copy
import gzip
import json
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

    def test_historical_lowercase_minimization_is_semantically_identical(self):
        expected = audit.align_vectors(self.names, self.root, self.label, self.record)
        self.label["effective_objective_sense"] = "minimize"
        self.assertEqual(
            audit.align_vectors(self.names, self.root, self.label, self.record),
            expected,
        )
        for invalid in ("maximize", "MAXIMIZE", None, "", 1, "unknown"):
            self.label["effective_objective_sense"] = invalid
            with self.assertRaisesRegex(audit.AuditStop, "label_objective_sense"):
                audit.align_vectors(self.names, self.root, self.label, self.record)

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

    def test_no_optimization_and_explicit_historical_loader(self):
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
        self.assertFalse(
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

    def test_historical_32_mib_limit_is_not_reimposed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json.gz"
            raw = b'{"payload":"' + b"x" * (32 * 1024**2) + b'"}'
            path.write_bytes(gzip.compress(raw))
            sizes = {}
            value = audit.bounded_json_gzip(path, observations=sizes, kind="root")
            self.assertEqual(len(value["payload"]), 32 * 1024**2)
            self.assertEqual(sizes["root"]["expanded_bytes_observed"], len(raw))
            self.assertTrue(sizes["root"]["complete"])
            self.assertEqual(sizes["root"]["limit_bytes"], 512 * 1024**2)

    def test_expansion_cap_still_fails_closed_and_reports_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json.gz"
            raw = b'{"x":"1234567890"}'
            path.write_bytes(gzip.compress(raw))
            self.assertEqual(
                audit.bounded_json_gzip(path, maximum=len(raw)), {"x": "1234567890"}
            )
            sizes = {}
            with self.assertRaisesRegex(audit.AuditStop, "expanded_json_limit"):
                audit.bounded_json_gzip(
                    path, maximum=10, observations=sizes, kind="label"
                )
            self.assertEqual(sizes["label"]["expanded_bytes_observed"], 11)
            self.assertFalse(sizes["label"]["complete"])

    def test_reviewed_job3501_reuse_and_mutation_rejection(self):
        path = audit.REPO / "docs/evidence/pr80-job3501-return.json"
        reused = audit.reuse_job3501(path)
        self.assertEqual(len(reused), 30)
        self.assertTrue(all(p.startswith("CFL_easy_") for p in reused))
        with tempfile.TemporaryDirectory() as folder:
            tampered = Path(folder) / "return.json"
            tampered.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(audit.AuditStop, "prior_return_hash"):
                audit.reuse_job3501(tampered)

    def test_continuation_runs_only_24_medium_parents(self):
        prior = audit.REPO / "docs/evidence/pr80-job3501-return.json"
        self.check_continuation(prior, 24, 30)

    def test_job3502_continuation_runs_only_15_unqualified_parents(self):
        prior = audit.REPO / "docs/evidence/pr80-job3502-return.json"
        reused = audit.reuse_reviewed_return(prior)
        self.assertEqual(sum("_medium_" in p for p in reused), 9)
        old = audit.reuse_job3501(audit.REPO / "docs/evidence/pr80-job3501-return.json")
        for parent, row in old.items():
            self.assertEqual(reused[parent], row)
        with tempfile.TemporaryDirectory() as folder:
            changed = Path(folder) / "changed.json"
            changed.write_bytes(prior.read_bytes() + b"\n")
            with self.assertRaisesRegex(audit.AuditStop, "prior_return_hash"):
                audit.reuse_reviewed_return(changed)
        self.check_continuation(prior, 15, 39)

    def check_continuation(self, prior, attempts, reused_count):
        original = audit.reuse_reviewed_return(prior)
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            data = base / "data"
            data.mkdir()
            calls = []

            def child(command, **kwargs):
                parent = command[-1]
                calls.append(parent)
                target = Path(command[command.index("--output") + 1])
                target.write_text(
                    json.dumps(
                        {
                            "parent": parent,
                            "state": "unqualified",
                            "stage": "numerical_representation",
                            "optimization_runs_added": 0,
                        }
                    )
                )
                return SimpleNamespace(returncode=0)

            with (
                patch.object(audit.sys, "platform", "linux"),
                patch.object(audit.subprocess, "run", child),
            ):
                result = audit.collect(data, base / "numeric", prior_return=prior)
            self.assertEqual(len(calls), attempts)
            self.assertFalse(set(calls) & set(original))
            self.assertTrue(all(p.startswith("CFL_medium_") for p in calls))
            self.assertEqual(result["new_parent_attempts"], attempts)
            self.assertEqual(len(result["reused_parent_observations"]), reused_count)
            self.assertEqual(
                result["prior_return_sha256"], audit.metadata.digest(prior.read_bytes())
            )
            self.assertEqual(
                result["prior_numeric_sha256"],
                json.loads(prior.read_bytes())["members"]["numeric/numeric.json"][
                    "sha256"
                ],
            )
            for parent, row in original.items():
                self.assertEqual(result["parents"][parent], row)

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

    def test_old_operator_is_withdrawn_without_installation(self):
        script = (SCRIPTS / "operate_pr80_numeric.sh").read_text()
        self.assertIn("PR80_OLD_OPERATOR_WITHDRAWN", script)
        self.assertNotIn("pip ", script)
        self.assertNotIn("sbatch", script)
        self.assertNotIn("venv", script)


if __name__ == "__main__":
    unittest.main()
