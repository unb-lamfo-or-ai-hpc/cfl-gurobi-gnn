"""Offline callback/preflight regressions; fake API only, no licensed solve.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import cpu_comparison_contract as contract  # noqa: E402
import gurobi_callback_adapter as adapter  # noqa: E402


def api():
    symbols = SimpleNamespace(**{name: i + 1 for i, name in enumerate(adapter.SYMBOLS)})
    return SimpleNamespace(
        GRB=SimpleNamespace(Callback=symbols, INFINITY=1e100),
        gurobi=SimpleNamespace(version=lambda: (13, 0, 1)),
    )


class Model:
    def __init__(self, gp, runtime=1, primal=100, dual=91, gap=0.09, status=2, count=1):
        self.values = {gp.GRB.Callback.RUNTIME: runtime}
        for prefix in ("MIP", "MIPSOL"):
            for suffix, value in (("OBJBST", primal), ("OBJBND", dual), ("NODCNT", 1)):
                self.values[getattr(gp.GRB.Callback, prefix + "_" + suffix)] = value
        self.queries = []
        self.terminated = 0
        self.SolCount, self.Status, self.Runtime = count, status, runtime
        self.ObjVal, self.ObjBound, self.MIPGap, self.NodeCount = primal, dual, gap, 1

    def cbGet(self, what):
        self.queries.append(what)
        return self.values[what]

    def terminate(self):
        self.terminated += 1


class CallbackTests(unittest.TestCase):
    def make(self, budget=3600, gap=0.1, max_samples=10000):
        gp = api()
        telemetry = contract.Telemetry(budget, gap, max_samples)
        callback = adapter.GurobiCallbackAdapter(gp, telemetry)
        return gp, telemetry, callback

    def test_normalizes_infinity_and_sentinel_not_nan_or_bool(self):
        for value in (math.inf, -math.inf, 1e100, -1e100, 2e100):
            self.assertIsNone(adapter.finite_bound(value, 1e100))
        self.assertEqual(adapter.finite_bound(-5, 1e100), -5)
        for value in (math.nan, True, "1", None):
            with self.assertRaises(ValueError):
                adapter.finite_bound(value, 1e100)

    def test_gap_missing_zero_negative_objectives(self):
        self.assertEqual(adapter.relative_gap(None, 5)[1], "no_finite_incumbent")
        self.assertEqual(adapter.relative_gap(5, None)[1], "no_finite_bound")
        for dual in (0, 1):
            self.assertEqual(
                adapter.relative_gap(0, dual), (None, "zero_objective_unqualified")
            )
        self.assertAlmostEqual(adapter.relative_gap(-100, -110)[0], 0.1)
        self.assertEqual(adapter.relative_gap(100, -100)[0], 2)

    def test_symbol_contract_rejects_missing_bool_duplicates_infinity(self):
        for mutation in (
            lambda gp: setattr(gp.GRB.Callback, "MIP", True),
            lambda gp: setattr(gp.GRB.Callback, "MIP", gp.GRB.Callback.MIPSOL),
            lambda gp: setattr(gp.GRB, "INFINITY", 0),
        ):
            gp = api()
            mutation(gp)
            with self.assertRaises(ValueError):
                adapter.callback_symbols(gp)
        gp = api()
        del gp.GRB.Callback.MIP
        with self.assertRaises(AttributeError):
            adapter.callback_symbols(gp)

    def test_requires_telemetry_and_ignores_other_phases(self):
        with self.assertRaises(ValueError):
            adapter.GurobiCallbackAdapter(api(), object())
        gp, t, cb = self.make()
        m = Model(gp)
        for where in (0, -1, 999):
            cb(m, where)
        self.assertFalse(m.queries)
        self.assertFalse(t.samples)

    def test_regular_rate_and_mipsol_events_use_best_not_candidate(self):
        gp, t, cb = self.make()
        m = Model(gp)
        cb(m, gp.GRB.Callback.MIP)
        m.values[gp.GRB.Callback.RUNTIME] = 1.5
        cb(m, gp.GRB.Callback.MIP)
        cb(m, gp.GRB.Callback.MIPSOL)
        cb(m, gp.GRB.Callback.MIPSOL)
        m.values[gp.GRB.Callback.RUNTIME] = 2
        cb(m, gp.GRB.Callback.MIP)
        self.assertEqual(len(t.samples), 4)
        self.assertEqual(cb.counters["rate_skipped"], 1)
        self.assertEqual(cb.counters["regular_samples"], 2)
        self.assertEqual(cb.counters["mipsol_samples"], 2)
        self.assertEqual(t.crossings[0.1]["solver_runtime_seconds"], 1)
        self.assertIn(gp.GRB.Callback.MIPSOL_OBJBST, m.queries)
        self.assertFalse(cb.failed)

    def test_no_incumbent_never_becomes_zero_gap(self):
        gp, t, cb = self.make()
        m = Model(gp, primal=1e100, gap=1e100, count=0, status=9)
        cb(m, gp.GRB.Callback.MIPSOL)
        result = cb.finish_model(m)
        self.assertIsNone(result["terminal"]["primal"])
        self.assertIsNone(result["terminal"]["gap_relative"])
        self.assertEqual(
            result["first_sampled_gap_observations"][0]["state"], "right_censored"
        )

    def test_zero_objective_conservatively_unqualified_even_at_zero_bound(self):
        gp, t, cb = self.make()
        m = Model(gp, primal=0, dual=0, gap=0)
        cb(m, gp.GRB.Callback.MIP)
        result = cb.finish_model(m)
        self.assertFalse(t.crossings)
        self.assertIsNone(result["terminal"]["gap_relative"])
        self.assertEqual(result["gurobi_callback"]["terminal_mip_gap_attribute"], 0)
        self.assertEqual(
            result["gurobi_callback"]["counters"]["zero_objective_samples"], 1
        )

    def test_missing_bound_is_missing_gap(self):
        gp, t, cb = self.make()
        m = Model(gp, dual=-1e100, gap=math.inf, status=9)
        cb(m, gp.GRB.Callback.MIP)
        self.assertIsNone(t.samples[0]["dual"])
        self.assertIsNone(cb.finish_model(m)["terminal"]["gap_relative"])

    def test_callback_exception_stops_and_never_exports_message(self):
        gp, t, cb = self.make()
        m = Model(gp, status=11)
        with patch.object(
            m, "cbGet", side_effect=RuntimeError("/home/private LICENSEID=secret")
        ):
            cb(m, gp.GRB.Callback.MIP)
        self.assertEqual(m.terminated, 1)
        result = cb.finish_model(m)
        self.assertEqual(result["stop"], "worker_failure")
        self.assertNotIn("secret", contract.encoded(result).decode())
        self.assertEqual(
            result["gurobi_callback"]["failure_code"], "callback_observation_failure"
        )

    def test_termination_failure_is_recorded_not_retried(self):
        gp, t, cb = self.make()
        m = Model(gp, runtime=-1, status=11)
        with patch.object(m, "terminate", side_effect=RuntimeError("private")):
            cb(m, gp.GRB.Callback.MIP)
        self.assertTrue(cb.failed)
        self.assertFalse(cb.termination_requested)
        m.Runtime = 1
        result = cb.finish_model(m)
        self.assertEqual(result["stop"], "worker_failure")
        cb(m, gp.GRB.Callback.MIP)
        self.assertEqual(cb.counters["mip_calls"], 0)

    def test_backwards_runtime_fails_even_on_rate_skipped_call(self):
        gp, t, cb = self.make()
        m = Model(gp, runtime=1)
        cb(m, gp.GRB.Callback.MIP)
        m.values[gp.GRB.Callback.RUNTIME] = 0.9
        cb(m, gp.GRB.Callback.MIP)
        self.assertTrue(cb.failed)
        self.assertEqual(m.terminated, 1)

    def test_clock_failure_at_start_or_end_requests_stop(self):
        gp, t, cb = self.make()
        m = Model(gp)
        cb.wall_clock = lambda: -1
        cb(m, gp.GRB.Callback.MIP)
        self.assertEqual(cb.failure_code, "callback_clock_failure")
        gp, t, cb = self.make()
        m = Model(gp)
        times = iter((10, 9))
        cb.wall_clock = lambda: next(times)
        cb(m, gp.GRB.Callback.MIP)
        self.assertEqual(cb.failure_code, "callback_clock_failure")

    def test_callback_overhead_is_separate_and_not_subtracted(self):
        gp, t, cb = self.make()
        wall, cpu = iter((10, 10.25)), iter((2, 2.125))
        cb.wall_clock, cb.cpu_clock = lambda: next(wall), lambda: next(cpu)
        m = Model(gp)
        cb(m, gp.GRB.Callback.MIP)
        result = cb.finish_model(m)
        self.assertEqual(result["terminal"]["solver_runtime_seconds"], 1)
        self.assertEqual(
            result["gurobi_callback"]["callback_external_wall_seconds"], 0.25
        )
        self.assertEqual(
            result["gurobi_callback"]["callback_current_process_cpu_seconds"], 0.125
        )

    def test_storage_cap_does_not_stop_observing_crossings(self):
        gp, t, cb = self.make(max_samples=1)
        m = Model(gp, dual=0, gap=1)
        cb(m, gp.GRB.Callback.MIP)
        m.values[gp.GRB.Callback.RUNTIME] = 2
        m.values[gp.GRB.Callback.MIPSOL_OBJBND] = 91
        cb(m, gp.GRB.Callback.MIPSOL)
        m.Runtime, m.ObjBound, m.MIPGap = 2.1, 91, 0.09
        result = cb.finish_model(m)
        self.assertEqual(len(result["samples"]), 1)
        self.assertEqual(result["dropped_sample_count"], 2)
        self.assertEqual(
            result["first_sampled_gap_observations"][0]["solver_runtime_seconds"], 2
        )

    def test_terminal_only_late_crossing_overshoot(self):
        gp, t, cb = self.make(budget=300)
        result = cb.finish_model(Model(gp, runtime=300.2, status=9))
        first = result["first_sampled_gap_observations"][0]
        self.assertEqual(first["state"], "observed")
        self.assertFalse(first["observed_within_budget"])
        self.assertAlmostEqual(result["time_limit_overshoot_seconds"], 0.2)

    def test_planned_stop_does_not_impute_stricter_targets(self):
        gp, t, cb = self.make()
        result = cb.finish_model(Model(gp))
        self.assertEqual(result["stop"], "gap_target")
        self.assertEqual(
            result["first_sampled_gap_observations"][1]["state"],
            "not_observed_before_planned_gap_stop",
        )

    def test_memory_and_other_status_remain_distinct(self):
        for status, expected in (
            (17, "memory_limit"),
            (3, "other_stop"),
            (11, "other_stop"),
        ):
            gp, t, cb = self.make()
            self.assertEqual(
                cb.finish_model(Model(gp, status=status, dual=0, gap=1))["stop"],
                expected,
            )

    def test_terminal_bound_formula_mismatch_and_invalid_fields_fail(self):
        for updates in (
            {"MIPGap": -0.1},
            {"MIPGap": 0.5},
            {"SolCount": True},
            {"Status": True},
            {"Runtime": -1},
        ):
            gp, t, cb = self.make()
            m = Model(gp)
            for k, v in updates.items():
                setattr(m, k, v)
            with self.assertRaises(ValueError):
                cb.finish_model(m)

    def test_terminal_runtime_cannot_precede_callback(self):
        gp, t, cb = self.make()
        m = Model(gp, runtime=2)
        cb(m, gp.GRB.Callback.MIP)
        m.Runtime = 1
        with self.assertRaises(ValueError):
            cb.finish_model(m)

    def test_finalize_once_and_reject_late_callback(self):
        gp, t, cb = self.make()
        m = Model(gp)
        cb.finish_model(m)
        with self.assertRaises(ValueError):
            cb.finish_model(m)
        cb(m, gp.GRB.Callback.MIP)
        self.assertTrue(cb.failed)
        self.assertEqual(cb.failure_code, "callback_after_finalization")


class PreflightTests(unittest.TestCase):
    def runtime_fixture(self):
        gp = api()
        events = []

        class Env:
            def __init__(self, empty):
                self.params = {}
                self.started = False
                events.append(("environment_created", empty))

            def __enter__(self):
                return self

            def __exit__(self, *args):
                events.append(("environment_closed", self.params.copy()))

            def setParam(self, name, value):
                self.params[name] = value

            def start(self):
                assert self.params == {"OutputFlag": 0, "ThreadLimit": 16}
                self.started = True

        class ReadModel(Model):
            ModelSense = -1
            NumIntVars = 5
            NumObj = 1
            NumQNZs = NumQConstrs = NumGenConstrs = NumSOS = 0
            NumVars, NumConstrs, DNumNZs, ObjCon = 100, 50, 500, 0

            def __init__(self):
                super().__init__(gp)
                names = contract.compile_proposal()["controls"][
                    "default_parameters_observed"
                ]
                self.defaults = {name: 0 for name in names}
                self.defaults["NodeLimit"] = math.inf
                self.resetParams()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                events.append(("model_closed", self.ModelSense))

            def update(self):
                pass

            def resetParams(self):
                self.params = self.defaults.copy()

            def getParamInfo(self, name):
                return (
                    name,
                    float,
                    self.params[name],
                    0,
                    math.inf,
                    self.defaults.get(name, 0),
                )

            def setParam(self, name, value):
                self.params[name] = value

            def cbGet(self, what):
                raise AssertionError("no callback query outside optimization")

            def optimize(self, *args):
                raise AssertionError("no optimization allowed in preflight")

        def read(path, env):
            assert env.started
            events.append(("model_read", path))
            return ReadModel()

        gp.Env, gp.read = Env, read
        return gp, events

    def test_runtime_preflight_reads_two_models_checks_ten_controls_without_solving(
        self,
    ):
        gp, events = self.runtime_fixture()
        rows = json.loads(contract.original.public_receipts()["pilot_plan.json"])[
            "models"
        ]
        with (
            patch.object(
                adapter.screen, "frozen_source", return_value=Path("fake_original.lp")
            ) as source,
            patch.object(
                adapter.screen,
                "digest",
                side_effect=[r["original_lp_sha256"] for r in rows],
            ),
        ):
            result = adapter.runtime_preflight(
                gp, contract.compile_proposal(), Path("unused")
            )
        self.assertEqual(source.call_count, 2)
        self.assertEqual(sum(event[0] == "model_read" for event in events), 2)
        self.assertEqual(sum(event[0] == "model_closed" for event in events), 2)
        self.assertEqual(sum(event[0] == "environment_closed" for event in events), 2)
        self.assertEqual(result["optimization_runs"], 0)
        self.assertEqual(result["parameter_configurations_checked"], 10)
        for row in result["models"]:
            self.assertTrue(row["objective_sense_override_applied"])
            self.assertEqual(
                sorted(
                    r["effective_parameters"]["Threads"]
                    for r in row["configured_attempts"]
                ),
                [1, 2, 4, 8, 16],
            )
            self.assertEqual(
                row["configured_attempts"][0]["algorithm_defaults"]["NodeLimit"][
                    "effective"
                ],
                "positive_infinity",
            )

    def test_runtime_preflight_detects_source_change_after_closing_model(self):
        gp, events = self.runtime_fixture()
        with (
            patch.object(
                adapter.screen, "frozen_source", return_value=Path("fake_original.lp")
            ),
            patch.object(adapter.screen, "digest", return_value="0" * 64),
            self.assertRaisesRegex(ValueError, "source_changed_during_preflight"),
        ):
            adapter.runtime_preflight(gp, contract.compile_proposal(), Path("unused"))
        self.assertTrue(any(e[0] == "environment_closed" for e in events))

    def test_maps_proposal_to_controls_without_mutation(self):
        p = contract.compile_proposal()
        before = contract.encoded(p)
        config = adapter.source_config(p, p["attempts"][0])
        self.assertEqual(config["seed"], 42)
        self.assertEqual(config["time_limit_seconds"], 3600)
        self.assertEqual(config["mip_gap_relative"], 0.01)
        self.assertEqual(contract.encoded(p), before)
        self.assertFalse(p["execution_enabled"])

    def test_version_mismatch_before_model_read(self):
        gp = api()
        gp.gurobi.version = lambda: (13, 0, 2)
        with self.assertRaises(ValueError):
            adapter.runtime_preflight(gp, contract.compile_proposal(), Path("unused"))

    def test_no_optimize_or_scheduler_call_exists(self):
        tree = ast.parse(Path(adapter.__file__).read_text())
        forbidden = {
            "optimize",
            "optimizeAsync",
            "cbGetSolution",
            "cbGetNodeRel",
            "cbSetSolution",
            "cbCut",
            "cbLazy",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, forbidden)

    def test_platform_gate_rejects_local_execution(self):
        with (
            patch.object(adapter.sys, "platform", "win32"),
            self.assertRaisesRegex(ValueError, "canonical_dasci_host_required"),
        ):
            adapter.qualify_host("0" * 40, Path("unused"))

    def test_preflight_success_and_failure_export_sanitized_receipts(self):
        for success in (True, False):
            with tempfile.TemporaryDirectory() as root:
                output = Path(root) / "fresh"
                fake = {"optimization_runs": 0, "models_read": 2}
                with (
                    patch.object(adapter, "qualify_host", return_value=output),
                    patch.object(
                        adapter.screen, "licensed_runtime", return_value=api()
                    ),
                    patch.object(
                        adapter,
                        "runtime_preflight",
                        return_value=fake if success else None,
                        side_effect=None
                        if success
                        else RuntimeError("LICENSEID=private /home/private"),
                    ),
                ):
                    receipt = adapter.preflight("0" * 40, output)
                self.assertEqual(
                    receipt["status"], "passed_no_optimization" if success else "failed"
                )
                self.assertEqual(receipt["optimization_runs"], 0)
                self.assertFalse(receipt["installed_callback_execution_qualified"])
                raw = (output / "preflight_receipt.json").read_bytes()
                self.assertNotIn(b"LICENSEID", raw)
                self.assertNotIn(b"/home/", raw)
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(),
                    (output / "SHA256SUMS.txt").read_text().split()[0],
                )
                self.assertEqual(json.loads(raw), receipt)
                with (
                    self.assertRaises(FileExistsError),
                    patch.object(adapter, "qualify_host", return_value=output),
                ):
                    adapter.preflight("0" * 40, output)


if __name__ == "__main__":
    unittest.main()
