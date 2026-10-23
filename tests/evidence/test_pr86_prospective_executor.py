"""Synthetic prospective instrumentation tests: no Gurobi, Slurm or GPU calls."""

import itertools
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import pr86_attempt_instrumentation as metered  # noqa: E402
import pr86_solver as solver  # noqa: E402


def cell(method="M0", threads=1, seed=42):
    return dict(
        parent="CFL_easy_instance_0",
        method=method,
        threads=threads,
        seed=seed,
        cell_id=f"F0-threads{threads}-seed{seed}-{method}",
        model_sha256="a" * 64,
        effective_objective_sense="MINIMIZE",
        time_limit_seconds=3600,
        mip_gap_fraction=1e-4,
    )


def successful_result(item):
    return dict(
        method=item["method"],
        mip_sha256=item["model_sha256"],
        effective_objective_sense="MINIMIZE",
        fresh_model=True,
        mathematical_model_unchanged=True,
        solver_version=[13, 0, 1],
        parameters=metered.parameters(item),
        gate_status="passed",
        solve={"solve_status_code": 9},
        optimization_calls=1,
        scientific_reporting_eligible=False,
        timing=dict(
            total_wall_time_seconds=0.25,
            data_read_wall_time_seconds=0.01,
            model_build_wall_time_seconds=0.02,
            model_optimize_wall_time_seconds=0.1,
            independent_audit_wall_time_seconds=0.03,
            solution_export_wall_time_seconds=0.04,
            other_wall_time_seconds=0.09,
        ),
    )


class MeterTests(unittest.TestCase):
    def setUp(self):
        self.cell = cell()
        self.context = dict(
            source_commit="b" * 40, plan_sha256="c" * 64, binding_sha256="d" * 64
        )
        self.supervision = dict(
            supervisor_wall_seconds=0.5, child_exit_code=0, guard_stop=None
        )

    def dispatch(self, output, claim):
        claim()
        return self.supervision, successful_result(self.cell)

    def record(self, output, dispatch=None):
        ticks = itertools.count()
        return metered.observe_attempt(
            output,
            self.cell,
            self.context,
            dispatch=dispatch or self.dispatch,
            clock=lambda: next(ticks),
        )

    def test_all_210_proposal_cells_have_explicit_supported_parameters(self):
        import plan_pr86_comparison as proposal

        _, cells = proposal.build()
        self.assertEqual(len(cells), 210)
        for item in cells:
            params = metered.parameters(item)
            self.assertEqual(params["Threads"], item["threads"])
            self.assertEqual(params["Seed"], item["seed"])
            self.assertEqual(params["SoftMemLimit"], 48)

    def test_invalid_parameters_never_dispatch(self):
        for key, value in (
            ("threads", True),
            ("threads", 3),
            ("seed", False),
            ("seed", 45),
            ("effective_objective_sense", "MAXIMIZE"),
            ("parent", "CFL_medium_instance_13"),
            ("time_limit_seconds", 30),
            ("mip_gap_fraction", 0.1),
            ("model_sha256", "bad"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                metered.parameters({**cell(), key: value})
        with self.assertRaisesRegex(ValueError, "unplanned_repeat"):
            metered.parameters(cell(threads=16, seed=43))

    def test_no_default_execution_adapter(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "not-created"
            with self.assertRaisesRegex(ValueError, "not_admitted"):
                metered.observe_attempt(output, self.cell, self.context)
            self.assertFalse(output.exists())

    def test_disjoint_export_tail_and_no_whole_job_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            value = self.record(output)
            report, tail = metered.validate_timing_files(output)
            self.assertEqual(report, value)
            self.assertEqual(report["dispatch_wall_seconds"], 1)
            self.assertEqual(report["attempt_before_receipt_export_seconds"], 3)
            self.assertEqual(tail["attempt_receipt_export_seconds"], 1)
            self.assertEqual(tail["observed_attempt_through_receipt_export_seconds"], 6)
            self.assertEqual(report["exact_optimization_call_count"], 1)
            self.assertFalse(report["pause_remaining_matrix"])
            self.assertFalse(report["whole_job_end_to_end_qualified"])
            self.assertAlmostEqual(report["measurement"]["cold_attempt_seconds"], 0.5)
            before = (output / "attempt.json").read_bytes()
            with self.assertRaises(FileExistsError):
                self.record(output)
            self.assertEqual((output / "attempt.json").read_bytes(), before)

    def test_receipt_tamper_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            self.record(output)
            with (output / "attempt.json").open("ab") as stream:
                stream.write(b" ")
            with self.assertRaisesRegex(ValueError, "attempt_hash"):
                metered.validate_timing_files(output)

    def test_memory_stops_preserve_cost_not_completed_performance(self):
        result = successful_result(self.cell)
        result["solve"]["solve_status_code"] = 17
        reason, measurement = metered.reconcile(self.cell, self.supervision, result)
        self.assertEqual(reason, "solver_soft_memory_stop")
        self.assertFalse(measurement["complete_attempt"])
        self.assertEqual(measurement["supervisor_wall_seconds"], 0.5)
        self.assertIsNone(measurement["cold_attempt_seconds"])
        for stop in metered.STOPS:
            reason, measurement = metered.reconcile(
                self.cell, {**self.supervision, "guard_stop": stop}, result
            )
            self.assertEqual(reason, stop)
            self.assertFalse(measurement["complete_attempt"])

    def test_failed_exit_missing_child_and_invalid_timing(self):
        reason, value = metered.reconcile(
            self.cell, {**self.supervision, "child_exit_code": 2}, None
        )
        self.assertEqual(reason, "child_failed")
        self.assertIsNone(value["cold_attempt_seconds"])
        for bad in (-1, float("nan"), True):
            with self.assertRaises(ValueError):
                metered.reconcile(
                    self.cell,
                    {**self.supervision, "supervisor_wall_seconds": bad},
                    None,
                )

    def test_wrong_identity_or_parameters_rejected(self):
        for key, value in (
            ("method", "M2"),
            ("mip_sha256", "b" * 64),
            ("solver_version", [12, 0, 0]),
            ("effective_objective_sense", "MAXIMIZE"),
            ("fresh_model", False),
            ("optimization_calls", True),
            ("scientific_reporting_eligible", True),
        ):
            result = successful_result(self.cell)
            result[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                metered.reconcile(self.cell, self.supervision, result)
        result = successful_result(self.cell)
        result["parameters"]["Threads"] = 16
        with self.assertRaisesRegex(ValueError, "result_parameters"):
            metered.reconcile(self.cell, self.supervision, result)

    def test_dispatch_failure_and_interrupt_are_durable_and_sanitized(self):
        for exc in (
            RuntimeError("/private/path SECRET"),
            KeyboardInterrupt(),
            SystemExit(2),
        ):

            def fail(output, claim):
                raise exc

            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "attempt"
                value = self.record(output, fail)
                self.assertTrue(value["pause_remaining_matrix"])
                self.assertEqual(value["dispatch_wall_seconds"], 1)
                self.assertIsNone(value["exact_optimization_call_count"])
                self.assertNotIn("SECRET", (output / "attempt.json").read_text())
                metered.validate_timing_files(output)

    def test_second_optimize_intent_stops_without_retry(self):
        def duplicate(output, claim):
            claim()
            claim()

        with tempfile.TemporaryDirectory() as temp:
            value = self.record(Path(temp) / "attempt", duplicate)
            self.assertTrue(value["optimization_intent_present"])
            self.assertTrue(value["pause_remaining_matrix"])
            self.assertIsNone(value["exact_optimization_call_count"])

    def test_unclaimed_return_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.record(
                Path(temp) / "attempt",
                lambda output, claim: (self.supervision, successful_result(self.cell)),
            )
            self.assertTrue(result["pause_remaining_matrix"])
            self.assertEqual(result["exception_type"], "ValueError")

    def test_guided_preparation_stays_unknown(self):
        self.cell = cell("M1")
        with tempfile.TemporaryDirectory() as temp:
            result = self.record(Path(temp) / "attempt")
            self.assertIsNone(result["measurement"]["cold_attempt_seconds"])
            self.assertFalse(result["measurement"]["preparation_costs_qualified"])

    def test_dispatch_cannot_replace_frozen_identity(self):
        original = dict(self.context)

        def mutate(output, claim):
            claim()
            self.context["source_commit"] = "e" * 40
            return self.supervision, successful_result(self.cell)

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            report = self.record(output, mutate)
            self.assertEqual(report["context"], original)
            self.assertTrue(report["pause_remaining_matrix"])
            self.assertIsNone(report["exact_optimization_call_count"])
            metered.validate_timing_files(output)


class ContextObject(SimpleNamespace):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SyntheticSolverTests(unittest.TestCase):
    def call_fake(self, item, claim=None, version=(13, 0, 1)):
        events = []
        self.events = events
        params = SimpleNamespace(
            **dict.fromkeys(
                (
                    "Threads Seed TimeLimit MIPGap MIPGapAbs Presolve Heuristics Cuts MIPFocus Method StartNodeLimit SubMIPNodes FeasibilityTol IntFeasTol"
                ).split(),
                0,
            )
        )
        variables = {"x": SimpleNamespace(Start=1e101)}
        model = ContextObject(
            Params=params,
            ModelSense=1,
            NumQNZs=0,
            NumQConstrs=0,
            NumGenConstrs=0,
            NumSOS=0,
            Fingerprint=7,
            SolCount=0,
            NumStart=0,
            Status=9,
            ObjBound=1,
            NodeCount=1,
            Runtime=0.01,
        )
        model.update = lambda: None
        model.optimize = lambda callback: events.append(
            ("optimize", params.Threads, params.Seed)
        )
        backend = SimpleNamespace(
            model=model,
            binary={"x"},
            variables=variables,
            bounds={"x": (0, 1)},
            original_sense="MAXIMIZE",
            close=lambda: events.append("close"),
        )

        def apply(directive):
            for row in directive["assignments"]:
                variables[row["variable_name"]].Start = row["value"]
            model.NumStart = int(bool(directive["assignments"]))

        backend.apply = apply
        fake_gp = SimpleNamespace(
            gurobi=SimpleNamespace(version=lambda: version),
            GRB=SimpleNamespace(MINIMIZE=1, UNDEFINED=1e101),
            Env=lambda **kw: ContextObject(),
            read=lambda *a, **kw: model,
        )
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {"gurobipy": fake_gp}))
            stack.enter_context(
                patch.object(solver, "NativeModel", return_value=backend)
            )
            stack.enter_context(
                patch.object(solver, "mathematical_signature", return_value="e" * 64)
            )
            stack.enter_context(
                patch.object(solver, "sha256_file", return_value="a" * 64)
            )
            result = solver.solve(
                Path("synthetic.lp"),
                "a" * 64,
                [],
                "unguided_control" if item["method"] == "M0" else "partial_mip_start",
                preselected_assignments=None
                if item["method"] == "M0"
                else [{"variable_name": "x", "value": 1}],
                reported_method=item["method"],
                cell=item,
                before_optimize=claim or (lambda: events.append("claim")),
            )
        self.assertEqual(events[0], "claim")
        self.assertEqual(events[1], ("optimize", item["threads"], item["seed"]))
        self.assertEqual(events[2], "close")
        return result

    def test_all_caps_and_repeat_seeds_reach_model_before_single_optimize(self):
        for threads in (1, 2, 4, 8, 16):
            for seed in (42, 43, 44) if threads == 1 else (42,):
                for method in ("M0", "M1", "M2"):
                    item = cell(method, threads, seed)
                    result = self.call_fake(item)
                    metered.validate_result(item, result)
                    self.assertEqual(result["optimization_calls"], 1)
                    self.assertEqual(result["original_objective_sense"], "MAXIMIZE")
                    self.assertEqual(
                        result["start"]["submitted_assignments"],
                        0 if method == "M0" else 1,
                    )
                    regions = metered.costs.execution_costs(result["timing"])
                    self.assertAlmostEqual(
                        sum(regions.values()),
                        result["timing"]["total_wall_time_seconds"],
                    )

    def test_version_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "installed_solver_version"):
            self.call_fake(cell(), version=(12, 0, 0))

    def test_claim_failure_prevents_optimize(self):
        def fail():
            raise RuntimeError("already_claimed")

        with self.assertRaisesRegex(RuntimeError, "already_claimed"):
            self.call_fake(cell(), claim=fail)
        self.assertEqual(self.events, ["close"])

    def test_model_binding_and_missing_claim_fail_before_import(self):
        with self.assertRaisesRegex(ValueError, "cell_model_binding"):
            solver.solve(
                None, "bad", [], "unguided_control", cell=cell(), before_optimize=None
            )
        with self.assertRaisesRegex(ValueError, "durable_optimize_claim"):
            solver.solve(
                None,
                "a" * 64,
                [],
                "unguided_control",
                cell=cell(),
                before_optimize=None,
            )


if __name__ == "__main__":
    unittest.main()
