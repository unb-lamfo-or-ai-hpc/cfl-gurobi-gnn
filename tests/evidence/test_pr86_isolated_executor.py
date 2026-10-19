"""Offline integration: real orchestration/receipt code, fake solver and Slurm."""

import copy
import itertools
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import pr86_isolated_executor as executor  # noqa: E402
import pr86_solver as solver  # noqa: E402
from test_pr86_prospective_executor import cell, successful_result  # noqa: E402


class Integrated(unittest.TestCase):
    def test_dispatch_child_claim_log_binding_and_costs(self):
        for method in ("M0", "M1", "M2"):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / "attempt"
                item = cell(method)
                chosen = [{"variable_name": "x", "value": 1}]
                assignment_sha = executor.canonical_sha256(chosen)
                binding = {
                    "M1_assignment_sha256": assignment_sha,
                    "M2_assignment_sha256": assignment_sha,
                    "selected_support": 1,
                    "positive_assignments": 1,
                }
                bundle = {
                    "cell": item,
                    "context": {
                        "source_commit": "b" * 40,
                        "plan_sha256": "c" * 64,
                        "binding_sha256": "d" * 64,
                    },
                    "allocation_threads": 1,
                    "start_binding": binding,
                    "preparation_seconds": dict.fromkeys(executor.costs.PREPARATION, 2),
                }
                result = successful_result(item)
                result.update(
                    model_fingerprint=1,
                    mathematical_signature_sha256="f" * 64,
                    original_objective_sense="MAXIMIZE",
                    python_version="3.10.20",
                    parameter_sha256="a" * 64,
                    independent_feasibility=None,
                    callback_errors=[],
                    trajectory=[],
                )
                result["start"] = {
                    "solver_messages": [],
                    "submitted_assignments": 0 if method == "M0" else 1,
                    "positive_assignments": 0 if method == "M0" else 1,
                    "status": "not_submitted" if method == "M0" else "accepted",
                    "assignment_sha256": assignment_sha,
                }
                gate = SimpleNamespace(sample=lambda: 1)

                def solve(*args, **kwargs):
                    kwargs["before_optimize"]()
                    kwargs["private_log_path"].write_bytes(b"synthetic private log")
                    return copy.deepcopy(result)

                def supervise(command, console, deadline, observed_gate):
                    self.assertEqual(deadline, 3780)
                    self.assertIs(observed_gate, gate)
                    self.assertIn("child", command)
                    executor.child(Path(temp) / "bundle.json", "e" * 64, output)
                    console.write_bytes(b"synthetic console")
                    return {
                        "supervisor_wall_seconds": 0.5,
                        "child_exit_code": 0,
                        "guard_stop": None,
                    }

                original = executor.metered.observe_attempt
                ticks = itertools.count()
                with ExitStack() as stack:
                    load = stack.enter_context(
                        patch.object(executor, "load_bundle", return_value=bundle)
                    )
                    stack.enter_context(
                        patch.object(
                            executor, "allocation", return_value=("synthetic", gate)
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            executor,
                            "assignments",
                            return_value=(
                                Path("synthetic"),
                                None if method == "M0" else chosen,
                            ),
                        )
                    )
                    stack.enter_context(
                        patch.object(executor, "sha256_file", return_value="a" * 64)
                    )
                    stack.enter_context(
                        patch.object(solver, "solve", side_effect=solve)
                    )
                    stack.enter_context(
                        patch.object(
                            executor.memory, "supervise", side_effect=supervise
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            executor.metered,
                            "observe_attempt",
                            side_effect=lambda *a, **kw: original(
                                *a, **kw, clock=lambda: next(ticks)
                            ),
                        )
                    )
                    report = executor.run_attempt(
                        Path(temp) / "bundle.json", "e" * 64, output
                    )
                self.assertFalse(report["pause_remaining_matrix"])
                self.assertEqual(load.call_count, 3)
                self.assertEqual(report["exact_optimization_call_count"], 1)
                executor.metered.validate_timing_files(output)
                costs = executor.existing.parsed(output / "prepared_costs.json")
                self.assertEqual(
                    costs["measurement"]["cold_attempt_seconds"],
                    0.5 if method == "M0" else 10.5 if method == "M1" else 8.5,
                )
                self.assertFalse(costs["whole_job_end_to_end_qualified"])
                child = executor.existing.parsed(output / "child.json")
                (output / "gurobi.private.log").write_bytes(b"altered")
                with self.assertRaisesRegex(ValueError, "solver_log_changed"):
                    executor.validate_child(bundle, child, output)

    def test_stop_never_creates_completed_cost(self):
        with tempfile.TemporaryDirectory() as temp:
            item = cell()
            bundle = {
                "cell": item,
                "context": {
                    "source_commit": "b" * 40,
                    "plan_sha256": "c" * 64,
                    "binding_sha256": "d" * 64,
                },
                "allocation_threads": 1,
            }

            def stop(command, console, deadline, gate):
                console.write_bytes(b"stopped")
                return {
                    "supervisor_wall_seconds": 0.001,
                    "child_exit_code": -9,
                    "guard_stop": "memory_observation_lost",
                }

            with (
                patch.object(executor, "load_bundle", return_value=bundle),
                patch.object(executor, "allocation", return_value=("1", None)),
                patch.object(executor, "assignments"),
                patch.object(executor.memory, "supervise", side_effect=stop),
            ):
                output = Path(temp) / "attempt"
                report = executor.run_attempt(Path(temp) / "bundle", "e" * 64, output)
            self.assertTrue(report["pause_remaining_matrix"])
            self.assertFalse((output / "prepared_costs.json").exists())

    def test_invalid_bundle_hash_never_reaches_allocation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bundle.json"
            path.write_bytes(b"{}")
            with (
                patch.object(executor, "allocation") as allocate,
                self.assertRaisesRegex(ValueError, "execution_bundle_hash"),
            ):
                executor.run_attempt(path, "0" * 64, Path(temp) / "attempt")
            allocate.assert_not_called()

    def test_missing_or_false_approval_never_imports_solver(self):
        plan, cells = executor.proposal.build()
        item = cells[0]
        for bad_gate in executor.GATES:
            with self.subTest(gate=bad_gate), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                binding = dict.fromkeys(
                    (
                        "model_sha256",
                        "root_sha256",
                        "graph_sha256",
                        "prediction_sha256",
                        "private_starts_sha256",
                        "M1_assignment_sha256",
                        "M2_assignment_sha256",
                    ),
                    "a" * 64,
                )
                binding["checkpoint_sha256"] = executor.proposal.CHECKPOINT
                preparation = dict.fromkeys(executor.costs.PREPARATION, 2)
                context = {
                    "source_commit": "b" * 40,
                    "plan_sha256": executor.proposal.digest(
                        executor.proposal.encoded(plan)
                    ),
                    "binding_sha256": executor.metered.digest(
                        executor.metered.encoded(binding)
                    ),
                }
                bundle = {
                    "protocol_id": executor.PROTOCOL,
                    "formulation_contract": dict(executor.FORMULATION_CONTRACT),
                    "automatic_retry": False,
                    "scientific_reporting_eligible": False,
                    "source_sha256_lf": {},
                    "context": context,
                    "cell": item,
                    "start_binding": binding,
                    "preparation_seconds": preparation,
                }
                for key in executor.GATES:
                    value = {
                        "accepted": key != bad_gate,
                        "context": {
                            k: context[k] for k in ("source_commit", "plan_sha256")
                        },
                        "accepted_parent_bindings": {
                            item["parent"]: context["binding_sha256"]
                        },
                        "preparation_seconds_by_parent": {item["parent"]: preparation},
                        "versions": {
                            "python": "3.10.20",
                            "numpy": "1.26.4",
                            "gurobipy": "13.0.1",
                        },
                    }
                    name = key + ".json"
                    sha = executor.metered.write_once(root / name, value)
                    bundle[key] = {"file": name, "sha256": sha}
                sha = executor.metered.write_once(root / "bundle.json", bundle)
                with (
                    patch.object(executor.existing, "dependencies", return_value={}),
                    patch.object(
                        executor.subprocess,
                        "run",
                        return_value=SimpleNamespace(stdout="b" * 40),
                    ),
                    patch.object(
                        executor.platform, "python_version", return_value="3.10.20"
                    ),
                    patch.object(
                        executor.importlib.metadata,
                        "version",
                        side_effect=lambda name: {
                            "numpy": "1.26.4",
                            "gurobipy": "13.0.1",
                        }[name],
                    ),
                    patch.object(executor, "allocation") as allocation,
                    self.assertRaisesRegex(ValueError, bad_gate + "_not_accepted"),
                ):
                    executor.run_attempt(root / "bundle.json", sha, root / "attempt")
                allocation.assert_not_called()

    def test_physical_mask_keeps_one_sibling_per_core(self):
        for cap in (1, 2, 4, 8, 16):
            selected = executor.physical_mask(
                range(cap * 2), lambda cpu: (0, cpu // 2), required=cap
            )
            self.assertEqual(selected, list(range(0, cap * 2, 2)))
        with self.assertRaises(ValueError):
            executor.physical_mask(range(16), lambda cpu: (0, cpu // 2), required=16)

    def test_group_order_failure_stop_and_no_overwrite(self):
        _, cells = executor.proposal.build()
        selected = cells[:3]
        bundles = [
            {"cell": c, "context": {}, "start_binding": {}, "preparation_seconds": {}}
            for c in selected
        ]
        requests = [(Path(str(i)), str(i) * 64) for i in range(3)]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "group"

            def attempt(path, sha, folder):
                folder.mkdir()
                value = {
                    "stop_code": "memory_guard_stop",
                    "pause_remaining_matrix": True,
                }
                executor.metered.write_once(folder / "attempt.json", value)
                return value

            with (
                patch.object(
                    executor,
                    "load_bundle",
                    side_effect=lambda p, s: bundles[int(str(p))],
                ),
                patch.object(executor, "run_attempt", side_effect=attempt) as run,
            ):
                result = executor.run_group(requests, output)
                self.assertEqual(run.call_count, 1)
                self.assertFalse(result["complete"])
                self.assertTrue(result["pause_remaining_matrix"])
                with self.assertRaises(FileExistsError):
                    executor.run_group(requests, output)
                with self.assertRaisesRegex(ValueError, "frozen_group_order"):
                    executor.run_group(list(reversed(requests)), Path(temp) / "other")


if __name__ == "__main__":
    unittest.main()
