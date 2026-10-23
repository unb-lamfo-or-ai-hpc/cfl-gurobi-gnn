"""Offline matrix/fault/export tests. All solver runtimes are synthetic."""

import copy
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
sys.path.insert(0, str(Path(__file__).parent))
import paired_matrix_executor_v2 as matrix  # noqa: E402
from test_isolated_attempt_worker import affinity, fake_api, fake_resource  # noqa: E402

memory = matrix.memory


def gate_value():
    value = json.loads((ROOT / matrix.evidence.QUALIFICATION_PATH).read_bytes())
    receipt = value["candidate_memory_receipt"]
    receipt["current_max_job_scoped_usage_bytes"] = 1
    return receipt


def approved(plan):
    value = matrix.approval_template(plan)
    for field in (
        "exact_head_four_ci_arms_reviewed",
        "installed_no_solver_fault_probe_reviewed",
        "explicit_resource_budget_and_submission_approved",
    ):
        value[field] = True
    return value, matrix.contract.sha(matrix.contract.encoded(value))


class MatrixTests(unittest.TestCase):
    def setUp(self):
        self.plan = matrix.plan_for("2" * 40)
        self.approval, self.sha = approved(self.plan)

    def synthetic_child(self, output, row, **kwargs):
        request = matrix.request_for(self.plan, self.sha, row)
        gp, events, model = fake_api(output, **kwargs)
        gate = Mock(sample=Mock(return_value=1), public=Mock(return_value=gate_value()))
        with (
            patch.object(memory, "MemoryGate", return_value=gate),
            patch.object(
                matrix.adapter.screen, "qualify_affinity", return_value=affinity()
            ),
            patch.object(
                matrix.adapter.screen,
                "frozen_source",
                return_value=Path(output) / "source.lp",
            ),
            patch.object(
                matrix.adapter.screen, "digest", return_value=row["original_lp_sha256"]
            ),
            patch.object(matrix.adapter.screen, "licensed_runtime", return_value=gp),
            patch.dict(sys.modules, {"resource": fake_resource()}),
        ):
            matrix.run_child(request, Path(output), "99")
        child = json.loads((Path(output) / "child.private.json").read_bytes())
        return request, child, events, model

    def test_frozen_order_budget_and_old_protocol_remain(self):
        proposal = matrix.contract.compile_proposal()
        self.assertEqual(self.plan["attempts"], proposal["attempts"])
        self.assertEqual(self.plan["maximum_optimization_calls"], 10)
        self.assertEqual(self.plan["parent_deadline_seconds"], 19800)
        self.assertEqual(self.plan["child_deadline_seconds"], 3780)
        self.assertFalse(self.plan["resource_budget_approved"])
        self.assertEqual(
            matrix.old.PROTOCOL, "single_attempt_callback_qualification_v1"
        )
        self.assertFalse(proposal["execution_enabled"])
        matrix.validate_plan(self.plan)

    def test_every_plan_mutation_rejected(self):
        for field, value in (
            ("maximum_optimization_calls", 11),
            ("child_deadline_seconds", 4000),
            ("resource_budget_approved", True),
            ("concurrent_attempts", 2),
            ("dependency_sha256", {}),
            ("attempts", list(reversed(self.plan["attempts"]))),
        ):
            changed = copy.deepcopy(self.plan)
            changed[field] = value
            with self.assertRaises(ValueError):
                matrix.validate_plan(changed)

    def test_approval_requires_exact_all_gates_and_budget(self):
        matrix.validate_approval(self.plan, self.approval, self.sha)
        for field in self.approval:
            changed = copy.deepcopy(self.approval)
            changed[field] = None
            with self.assertRaises(ValueError):
                matrix.validate_approval(
                    self.plan,
                    changed,
                    matrix.contract.sha(matrix.contract.encoded(changed)),
                )
        unapproved = matrix.approval_template(self.plan)
        with self.assertRaises(ValueError):
            matrix.validate_approval(
                self.plan,
                unapproved,
                matrix.contract.sha(matrix.contract.encoded(unapproved)),
            )

    def test_reviewed_evidence_unchanged(self):
        matrix.reviewed_evidence()

    def test_synthetic_long_child_one_optimization_and_closed_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = matrix.rows_for(self.plan, "easy")[0]
            request, child, events, model = self.synthetic_child(tmp, row)
            matrix.validate_child(child, request, "99")
            self.assertEqual(events.count("optimize"), 1)
            self.assertEqual(model.params["TimeLimit"], 3600)
            self.assertEqual(model.params["SoftMemLimit"], 48)
            self.assertEqual(model.ModelSense, 1)
            self.assertLess(events.index("model_close"), events.index("env_close"))
            self.assertEqual(
                child["gurobi_log"],
                matrix.contract.seal_closed_log(Path(tmp) / "gurobi.private.log"),
            )
            self.assertNotIn(b"LICENSEID", matrix.contract.encoded(child))

    def test_callback_failure_memory_stop_cleanup_failure_retained(self):
        for kwargs, stop in (
            ({"status": 17}, "memory_limit"),
            ({"failure": "callback"}, "worker_failure"),
            ({"failure": "cleanup"}, None),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                _, child, _, _ = self.synthetic_child(
                    tmp, matrix.rows_for(self.plan, "easy")[0], **kwargs
                )
                if stop is not None:
                    self.assertEqual(child["result"]["stop"], stop)
                else:
                    self.assertEqual(child["failure_code"], "worker_cleanup_failed")
                    self.assertIsNone(child["gurobi_log"])

    def test_kernel_gate_fails_before_license_model_or_optimize(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(memory, "MemoryGate", side_effect=ValueError("unqualified")),
            patch.object(matrix.adapter.screen, "licensed_runtime") as runtime,
        ):
            with self.assertRaises(ValueError):
                matrix.run_child(
                    matrix.request_for(self.plan, self.sha, self.plan["attempts"][0]),
                    Path(tmp),
                    "99",
                )
            runtime.assert_not_called()

    def test_gate_schema_never_promotes_history_or_swap(self):
        matrix.validate_gate(gate_value())
        for field, value in (
            ("job_anchor_ram_limit_bytes", 56 * memory.GIB),
            ("job_anchor_ram_limit_bytes", 65 * memory.GIB),
            ("historical_rss_reconciled", True),
            ("current_max_job_scoped_usage_bytes", 56 * memory.GIB),
            ("swap_limit_qualified", True),
        ):
            gate = gate_value()
            gate[field] = value
            with self.assertRaises(ValueError):
                matrix.validate_gate(gate)

    def test_parent_claim_replay_and_different_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Windows CI may expose TEMP through an 8.3 alias. Production
            # intentionally rejects aliases; use a canonical synthetic root.
            root = Path(tmp).resolve()
            flow = root / "flow"
            flow.mkdir()
            with patch.object(matrix.adapter, "EVIDENCE_ROOT", root):
                matrix.claim_root(flow, self.plan, self.sha, "easy", "99")
                with self.assertRaises(FileExistsError):
                    matrix.claim_root(flow, self.plan, self.sha, "easy", "99")
                with self.assertRaises(ValueError):
                    matrix.claim_root(
                        root / "other", self.plan, self.sha, "medium", "100"
                    )

    def test_memory_stop_prevents_later_attempts_and_medium(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = Path(tmp) / "flow"
            flow.mkdir()
            root = Path(tmp) / "claim"
            root.mkdir()
            receipt = {"pause_remaining_matrix": True, "stop_code": "memory_guard_stop"}
            with (
                patch.object(matrix, "load_flow", return_value=self.plan),
                patch.object(matrix, "execution_host", return_value=(flow, "99")),
                patch.object(memory, "MemoryGate"),
                patch.object(matrix.adapter.screen, "qualify_affinity"),
                patch.object(matrix, "claim_root", return_value=root),
                patch.object(
                    matrix, "execute_attempt", return_value=receipt
                ) as execute,
                patch.object(matrix, "validate_parent_directory"),
            ):
                report = matrix.run_parent(flow, self.sha, "easy")
            self.assertEqual(execute.call_count, 1)
            self.assertTrue(report["pause_remaining_matrix"])
            self.assertTrue((root / "STOP.json").exists())

    def test_parent_deadline_reserves_whole_child_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = Path(tmp) / "flow"
            flow.mkdir()
            root = Path(tmp) / "claim"
            root.mkdir()
            with (
                patch.object(matrix, "load_flow", return_value=self.plan),
                patch.object(matrix, "execution_host", return_value=(flow, "99")),
                patch.object(memory, "MemoryGate"),
                patch.object(matrix.adapter.screen, "qualify_affinity"),
                patch.object(matrix, "claim_root", return_value=root),
                patch.object(matrix.time, "monotonic", side_effect=[0, 17000]),
                patch.object(matrix, "execute_attempt") as execute,
                patch.object(matrix, "validate_parent_directory"),
            ):
                report = matrix.run_parent(flow, self.sha, "easy")
            execute.assert_not_called()
            self.assertEqual(report["stop_code"], "parent_deadline_reserve")

    def test_full_parent_five_fresh_children_export_and_log_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = Path(tmp)
            matrix.old.write_json(flow / "plan.json", self.plan)
            matrix.old.write_json(flow / "approval.json", self.approval)
            output = flow / "easy"
            output.mkdir()
            receipts = {}
            gate = Mock(
                sample=Mock(return_value=1), public=Mock(return_value=gate_value())
            )
            events_all = []

            def simulate(command, console, deadline, _gate):
                self.assertEqual(deadline, 3780)
                attempt = Path(console).parent
                request = json.loads((attempt / "request.json").read_bytes())
                _, _, events, _ = self.synthetic_child(attempt, request["attempt"])
                events_all.append(events)
                Path(console).write_bytes(b"private console\n")
                return {
                    "child_exit_code": 0,
                    "guard_stop": None,
                    "sampled_cgroup_peak_bytes": 1,
                    "supervisor_wall_seconds": 1,
                    "peak_is_sampled_not_exact": True,
                }

            for row in matrix.rows_for(self.plan, "easy"):
                request = matrix.request_for(self.plan, self.sha, row)
                with (
                    patch.object(memory, "MemoryGate", return_value=gate),
                    patch.object(memory, "supervise", side_effect=simulate),
                ):
                    receipt = matrix.execute_attempt(
                        request, output / row["attempt_id"], "99"
                    )
                self.assertFalse(receipt["pause_remaining_matrix"])
                receipts[row["attempt_id"]] = matrix.contract.sha(
                    matrix.contract.encoded(receipt)
                )
            report = matrix.parent_report(
                self.plan, self.sha, "easy", "99", receipts, None
            )
            matrix.old.write_json(output / "parent_receipt.json", report)
            destination = flow / "public.tar.gz"
            sha = matrix.export_parent(flow, self.sha, "easy", destination)
            self.assertTrue(
                matrix.validate_package(destination, sha)["complete_parent"]
            )
            self.assertEqual([e.count("optimize") for e in events_all], [1] * 5)
            with tarfile.open(destination) as archive:
                self.assertEqual(len(archive.getnames()), 14)
                self.assertFalse(
                    any(
                        "private" in n or n.endswith(".log") for n in archive.getnames()
                    )
                )
            first = matrix.rows_for(self.plan, "easy")[0]["attempt_id"]
            (output / first / "console.private.log").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                matrix.export_parent(flow, self.sha, "easy", flow / "tampered.tar.gz")
            self.assertFalse((flow / "tampered.tar.gz").exists())

    def test_medium_requires_completed_easy_and_no_global_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp).resolve()
            flow = evidence / "flow"
            flow.mkdir()
            with patch.object(matrix.adapter, "EVIDENCE_ROOT", evidence):
                root = matrix.claim_root(flow, self.plan, self.sha, "easy", "99")
                with (
                    patch.object(
                        matrix,
                        "validate_parent_directory",
                        return_value={"complete_parent": False, "job_id": "99"},
                    ),
                    self.assertRaises(ValueError),
                ):
                    matrix.claim_root(flow, self.plan, self.sha, "medium", "100")
                matrix.old.write_json(
                    root / "STOP.json", {"stop_code": "memory_guard_stop"}
                )
                with (
                    patch.object(
                        matrix,
                        "validate_parent_directory",
                        return_value={"complete_parent": True, "job_id": "99"},
                    ),
                    self.assertRaises(ValueError),
                ):
                    matrix.claim_root(flow, self.plan, self.sha, "medium", "100")
                self.assertFalse((root / "medium.started").exists())

    def test_export_independent_validation_and_no_raw_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = Path(tmp)
            matrix.old.write_json(flow / "plan.json", self.plan)
            matrix.old.write_json(flow / "approval.json", self.approval)
            (flow / "easy").mkdir()
            report = matrix.parent_report(
                self.plan, self.sha, "easy", "99", {}, "parent_deadline_reserve"
            )
            matrix.old.write_json(flow / "easy/parent_receipt.json", report)
            dest = flow / "public.tar.gz"
            sha = matrix.export_parent(flow, self.sha, "easy", dest)
            self.assertEqual(matrix.validate_package(dest, sha), report)
            with tarfile.open(dest) as archive:
                self.assertEqual(
                    set(archive.getnames()),
                    {
                        "plan.json",
                        "approval.json",
                        "easy/parent_receipt.json",
                        "SHA256SUMS.txt",
                    },
                )
            with self.assertRaises(FileExistsError):
                matrix.export_parent(flow, self.sha, "easy", dest)
            with self.assertRaises(ValueError):
                matrix.validate_package(dest, "0" * 64)

    def test_archive_extra_member_duplicate_traversal_link_rejected(self):
        for name, kind in (
            ("../secret", None),
            ("gurobi.private.log", None),
            ("plan.json", tarfile.SYMTYPE),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "bad.tar.gz"
                with tarfile.open(dest, "w:gz") as archive:
                    item = tarfile.TarInfo(name)
                    if kind is not None:
                        item.type = kind
                    item.size = 1
                    archive.addfile(item, io.BytesIO(b"x"))
                with self.assertRaises(ValueError):
                    matrix.validate_package(dest, matrix.adapter.screen.digest(dest))


class IntegrationTests(unittest.TestCase):
    def test_exact_guard_and_receipt_binding(self):
        matrix.evidence.review(ROOT)
        pins = matrix.pins()
        for name, sha in matrix.evidence.GUARDS.items():
            self.assertEqual(pins[name], sha)
        self.assertIn("paired_matrix_executor_v2.py", pins)
        self.assertIn("paired_memory_runtime.py", pins)

    def test_new_gate_schema_rejects_legacy_or_unsafe_promotion(self):
        matrix.validate_gate(gate_value())
        for field, value in (
            ("job_scoped_min_ram_limit_bytes", 56 * memory.GIB),
            ("leaf_ram_limit_bytes", 55 * memory.GIB),
            ("leaf_ram_limit_bytes", None),
            ("validated_group_count", 0),
            ("job_anchor_depth_from_leaf", 0),
            ("usage_scope", "leaf_only"),
            ("ancestor_limits_rechecked_each_sample", False),
            ("hierarchy_rechecked_each_sample", False),
            ("membership_and_mounts_verified", 1),
        ):
            gate = gate_value()
            gate[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                matrix.validate_gate(gate)

    def test_child_command_imports_versioned_executor(self):
        gate = Mock(sample=Mock(return_value=1), public=Mock(return_value=gate_value()))
        plan = matrix.plan_for("2" * 40)
        _, sha = approved(plan)
        row = matrix.rows_for(plan, "easy")[0]

        def supervise(command, console, _deadline, _gate):
            self.assertIn("import paired_matrix_executor_v2 as m", command[3])
            Path(console).write_bytes(b"synthetic failed child")
            return {
                "child_exit_code": 2,
                "guard_stop": None,
                "sampled_cgroup_peak_bytes": 1,
                "supervisor_wall_seconds": 1,
                "peak_is_sampled_not_exact": True,
            }

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(memory, "MemoryGate", return_value=gate),
            patch.object(memory, "supervise", side_effect=supervise),
        ):
            result = matrix.execute_attempt(
                matrix.request_for(plan, sha, row), Path(tmp) / "attempt", "99"
            )
        self.assertTrue(result["pause_remaining_matrix"])


if __name__ == "__main__":
    unittest.main()
