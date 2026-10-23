"""Exercise historical CFL objective normalization without a licensed solve.

SPDX-License-Identifier: MIT
"""

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr66_thread_pilot as pilot  # noqa: E402
import test_pr66_thread_pilot as fixtures  # noqa: E402


class OriginalModel:
    def __init__(self):
        self.ModelSense = -1
        self.NumIntVars = 2
        self.NumObj = 1
        self.NumVars = 3
        self.NumConstrs = 1
        self.DNumNZs = 3
        self.ObjCon = 7
        self.NumQNZs = self.NumQConstrs = self.NumGenConstrs = self.NumSOS = 0
        self.objective_coefficients = [4, 5, 6]
        self.constraints = [[1, 1, 1]]
        self.calls = []
        self.params = {}
        self.SolCount = 1
        self.MIPGap = 0.2
        self.Status = 9
        self.ObjVal = 100
        self.ObjBound = 80
        self.Runtime = 300
        self.NodeCount = 8

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def update(self):
        self.calls.append("update")

    def resetParams(self):
        self.params = {}

    def getParamInfo(self, name):
        default = float("inf") if name == "NodeLimit" else 1
        return (name, float, self.params.get(name, default), 0, 100, default)

    def setParam(self, key, value):
        self.params[key] = value

    def optimize(self):
        if self.ModelSense != 1:
            raise AssertionError("optimization preceded minimization qualification")
        self.calls.append("optimize")


class Environment:
    def __init__(self, **_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def setParam(self, *_):
        pass

    def start(self):
        pass


class ObjectivePolicyTests(unittest.TestCase):
    def config(self):
        return pilot.strict_json(pilot.BASE_CONFIG)

    def test_normalization_preserves_coefficients_constant_and_constraints(self):
        model = OriginalModel()
        before = copy.deepcopy(model.__dict__)
        receipt = pilot.prepare_original_model(model, self.config())
        self.assertEqual(model.ModelSense, 1)
        self.assertEqual(model.calls, ["update"])
        for key in before.keys() - {"ModelSense", "calls"}:
            self.assertEqual(model.__dict__[key], before[key])
        self.assertEqual(receipt["source_objective_sense"], "MAXIMIZE")
        self.assertEqual(receipt["effective_objective_sense"], "MINIMIZE")
        self.assertIs(receipt["objective_sense_override_applied"], True)

    def test_unexpected_source_sense_is_not_silently_accepted(self):
        for sense in (1, 0, 2):
            with self.subTest(sense=sense):
                model = OriginalModel()
                model.ModelSense = sense
                with self.assertRaisesRegex(ValueError, "source_objective_sense"):
                    pilot.prepare_original_model(model, self.config())
                self.assertEqual(model.ModelSense, sense)
                self.assertEqual(model.calls, [])

    def test_missing_or_changed_policy_is_refused_before_model_change(self):
        for key in (
            "objective_sense_policy",
            "source_objective_sense",
            "effective_objective_sense",
        ):
            with self.subTest(key=key):
                config = self.config()
                config.pop(key)
                model = OriginalModel()
                with self.assertRaisesRegex(ValueError, "unqualified_objective"):
                    pilot.prepare_original_model(model, config)
                self.assertEqual(model.ModelSense, -1)

    def test_continuous_model_is_refused_without_normalization(self):
        model = OriginalModel()
        model.NumIntVars = 0
        with self.assertRaisesRegex(ValueError, "discrete_variables"):
            pilot.prepare_original_model(model, self.config())
        self.assertEqual(model.calls, [])

    def test_extended_or_multiple_objectives_are_refused(self):
        for key, value in (
            ("NumQNZs", 1),
            ("NumQConstrs", 1),
            ("NumGenConstrs", 1),
            ("NumSOS", 1),
            ("NumObj", 2),
        ):
            with self.subTest(key=key):
                model = OriginalModel()
                setattr(model, key, value)
                with self.assertRaisesRegex(ValueError, "single_objective_linear"):
                    pilot.prepare_original_model(model, self.config())
                self.assertEqual(model.ModelSense, -1)

    def test_failed_update_is_detected_without_optimization(self):
        model = OriginalModel()
        model.update = lambda: setattr(model, "ModelSense", -1)
        with self.assertRaisesRegex(ValueError, "normalization_failed"):
            pilot.prepare_original_model(model, self.config())
        self.assertNotIn("optimize", model.calls)

    def runtime(self, models):
        return SimpleNamespace(
            Env=Environment,
            read=lambda *_, **__: models.pop(0),
            gurobi=SimpleNamespace(version=lambda: (13, 0, 1)),
        )

    def test_preflight_reads_both_maximize_sources_without_optimizing(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, plan, sha = fixtures.PilotTests().simulated_plan(Path(tmp))
            models = [OriginalModel(), OriginalModel()]
            observed = models.copy()
            hashes = [pilot.digest(p) for p in raw.rglob("*.lp")]
            with patch.object(
                pilot, "licensed_runtime", return_value=self.runtime(models)
            ):
                pilot.preflight(plan, sha, raw)
            self.assertEqual(models, [])
            self.assertTrue(all(model.ModelSense == 1 for model in observed))
            self.assertTrue(all(model.calls == ["update"] for model in observed))
            self.assertEqual(hashes, [pilot.digest(p) for p in raw.rglob("*.lp")])

    def test_attempt_normalizes_before_optimize_and_records_both_senses(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, plan, sha = fixtures.PilotTests().simulated_plan(Path(tmp))
            model = OriginalModel()
            resource = SimpleNamespace(
                RUSAGE_SELF=0, getrusage=lambda _: SimpleNamespace(ru_maxrss=1000)
            )
            with (
                patch.object(
                    pilot, "licensed_runtime", return_value=self.runtime([model])
                ),
                patch.object(
                    pilot, "qualify_affinity", return_value={"physical_cores": 16}
                ),
                patch.object(
                    pilot.os, "getloadavg", return_value=(0, 0, 0), create=True
                ),
                patch.dict(pilot.os.environ, {"SLURM_JOB_ID": "123"}),
                patch.dict(sys.modules, {"resource": resource}),
            ):
                pilot.attempt(plan, sha, raw, 1, "easy")
            report = pilot.strict_json(plan / "easy-threads1/attempt_report.json")
            self.assertEqual(model.calls, ["update", "optimize"])
            self.assertEqual(report["source_objective_sense"], "MAXIMIZE")
            self.assertEqual(report["effective_objective_sense"], "MINIMIZE")
            self.assertIs(report["objective_sense_override_applied"], True)
            self.assertIs(report["model_unchanged_after_execution"], True)
            self.assertEqual(report["parameters"]["Threads"], 1)
            self.assertNotIn("Method", report["parameters"])

    def test_unbounded_version_default_survives_strict_json_roundtrip(self):
        model = OriginalModel()
        parameters, observed = pilot.configure_model(model, self.config(), threads=1)
        self.assertEqual(parameters["Threads"], 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "defaults.json"
            pilot.write_json(path, observed)
            receipt = pilot.strict_json(path)
        self.assertEqual(
            receipt["NodeLimit"],
            {"effective": "positive_infinity", "version_default": "positive_infinity"},
        )

    def test_unbounded_default_does_not_hide_a_changed_effective_limit(self):
        model = OriginalModel()
        original = model.getParamInfo

        def altered(name):
            if name == "NodeLimit":
                return (name, float, 1000, 0, float("inf"), float("inf"))
            return original(name)

        model.getParamInfo = altered
        with self.assertRaisesRegex(ValueError, "algorithm_parameter_not_default"):
            pilot.configure_model(model, self.config(), threads=1)
        self.assertEqual(model.params, {})

    def test_nan_default_and_invalid_parameter_types_are_refused(self):
        for value in (float("nan"), None, True, "inf"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pilot.parameter_receipt_value(value)


if __name__ == "__main__":
    unittest.main()
