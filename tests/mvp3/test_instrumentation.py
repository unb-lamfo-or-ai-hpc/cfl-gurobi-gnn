"""Offline adversarial instrumentation tests, all native calls are API doubles."""
# ruff: noqa: E402 -- repository-source bootstrap, no installed project required

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fake_native import fake_api
from fixtures import model, run, start

from cfl_gnn.mvp3.audit import AuditPolicy, audit_point
from cfl_gnn.mvp3.collection import collect_attempt
from cfl_gnn.mvp3.contract import ContractError, approved_contract, digest, load_json
from cfl_gnn.mvp3.identity import model_identity
from cfl_gnn.mvp3.journal import AttemptStore, file_sha256, read_vector, scan_journal
from cfl_gnn.mvp3.matrix import DescriptionMatrix, NativeMatrix, streamed_identity
from cfl_gnn.mvp3.native import NativePermit, NativeSession, parameter_inventory
from cfl_gnn.mvp3.observer import NativeObserver
from cfl_gnn.mvp3.records import validate_audit


class InstrumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.input = self.folder / "tiny.mps"
        self.input.write_text("invented test input; not a real MPS", encoding="ascii")
        self.binding = {
            "source_commit": "a" * 40,
            "mode": "technical_qualification",
            "input_sha256": file_sha256(self.input),
            "key": {
                "parent_id": "QUAL_TINY",
                "stage": "incumbent",
                "method": None,
                "seed": 42,
                "attempt": "synthetic-1",
            },
            "root_artifact_sha256": "7" * 64,
            "frozen_start_policy_sha256": "9" * 64,
            "predictor_sha256": "8" * 64,
        }

    def store(self, **changes):
        store = AttemptStore(
            self.folder / "attempt",
            self.binding,
            **{
                "event_limit": 100,
                "artifact_bytes_limit": 100000,
                "candidate_limit": 10,
                **changes,
            },
        )
        self.addCleanup(lambda: store.stream.close() if store.stream else None)
        return store

    def session(self, store, api):
        permit = NativePermit(
            self.binding["source_commit"],
            self.binding["input_sha256"],
            "synthetic-test-authority-not-a-real-release",
            self.binding["mode"],
        )
        profile = {
            **approved_contract()["solver"]["profiles"][self.binding["key"]["stage"]],
            "Threads": 1,
            "TimeLimit": 1,
        }
        return NativeSession(api, self.input, permit, store, profile, AuditPolicy())

    def test_streaming_hash_matches_sealed_identity(self):
        description = model()
        self.assertEqual(
            streamed_identity(DescriptionMatrix(description)),
            model_identity(description),
        )
        description["rows"][0]["terms"].reverse()
        self.assertEqual(
            streamed_identity(DescriptionMatrix(description)),
            model_identity(description),
        )

    def test_streaming_rejects_duplicate_rows_and_nonfinite_coefficients(self):
        description = model()
        description["rows"].append(copy.deepcopy(description["rows"][0]))
        with self.assertRaises(ContractError):
            streamed_identity(DescriptionMatrix(description))
        description["rows"].pop()
        description["rows"][0]["terms"][0][1] = float("nan")
        with self.assertRaises(ContractError):
            streamed_identity(DescriptionMatrix(description))

    def test_rounding_is_explicit_and_reaudited(self):
        result = audit_point(
            DescriptionMatrix(model()),
            [1 - 1e-7] * 20,
            AuditPolicy(),
            native_objective=20,
        )
        self.assertEqual(result["status"], "qualified")
        self.assertEqual(result["rounding"]["changed_count"], 20)
        self.assertNotEqual(
            result["raw_vector_sha256"], result["canonical_vector_sha256"]
        )
        self.assertEqual(result["audit"]["vector_sha256"], digest([1.0] * 20))
        self.assertFalse(result["exact_rational_certificate"])

    def test_rounded_point_row_violation_is_not_hidden(self):
        description = model()
        description["rows"][0].update(sense="<=", rhs=20 - 1e-5)
        result = audit_point(
            DescriptionMatrix(description),
            [1 - 1e-6] * 20,
            AuditPolicy(),
            native_objective=20,
        )
        self.assertEqual(result["status"], "unqualified")
        self.assertGreater(result["audit"]["row_max_violation"]["value"], 1e-6)

    def test_root_feasibility_does_not_equate_bound_and_vector_objective(self):
        description = model()
        description["rows"][0]["rhs"] = 10
        result = audit_point(
            DescriptionMatrix(description), [0.5] * 20, AuditPolicy(), continuous=True
        )
        self.assertEqual(result["status"], "qualified")
        self.assertIsNone(result["audit"]["objective_residual"]["value"])
        validate_audit(
            result["audit"],
            result["audit"]["model_sha256"],
            result["audit"]["vector_sha256"],
            continuous=True,
        )
        with self.assertRaises(ContractError):
            validate_audit(
                result["audit"],
                result["audit"]["model_sha256"],
                result["audit"]["vector_sha256"],
            )

    def test_fractional_or_incomplete_incumbents_fail(self):
        result = audit_point(
            DescriptionMatrix(model()), [0.5] * 20, AuditPolicy(), native_objective=10
        )
        self.assertEqual(result["status"], "unqualified")
        with self.assertRaises(ContractError):
            audit_point(
                DescriptionMatrix(model()), [1], AuditPolicy(), native_objective=1
            )
        with self.assertRaises(ContractError):
            audit_point(DescriptionMatrix(model()), [1] * 20, AuditPolicy())

    def test_binary_relaxation_retains_implicit_bounds(self):
        description = model()
        for variable in description["variables"]:
            variable["lower"] = variable["upper"] = None
        result = audit_point(
            DescriptionMatrix(description), [2] * 20, AuditPolicy(), continuous=True
        )
        self.assertEqual(result["status"], "unqualified")

    def test_parameter_inventory_never_queries_auth_values(self):
        api, native, _ = fake_api()
        result = parameter_inventory(api, native)
        self.assertIn("WLSSecret", result["excluded_auth_transport_names_not_queried"])
        self.assertNotIn("WLSSecret", result["effective"])
        self.assertEqual(result["effective"], native.defaults)

    def test_vector_roundtrip_tampering_and_path_traversal(self):
        store = self.store()
        store.reserve_final_vectors(20)
        descriptor = store.put_vector([1] * 20)
        self.assertEqual(read_vector(store.folder, descriptor), [1.0] * 20)
        with self.assertRaises(ContractError):
            read_vector(store.folder, {"sha256": "../attempt", "count": 20})
        path = store.folder / "artifacts" / f"{descriptor['sha256']}.json"
        path.write_text("[]")
        with self.assertRaises(ContractError):
            read_vector(store.folder, descriptor)

    def test_versioned_audit_policy_matches_implementation(self):
        policy = load_json(ROOT / "configs/mvp3/instrumentation/v1.json")
        self.assertEqual(policy["audit"], AuditPolicy().tolerances())
        self.assertFalse(policy["scientific_execution_authorized"])
        self.assertFalse(policy["primary_campaign"]["released"])

    def test_candidate_cap_reserves_final_points(self):
        store = self.store(candidate_limit=1)
        store.reserve_final_vectors(20)
        self.assertIsNotNone(store.put_vector([0] * 20)["sha256"])
        self.assertEqual(
            store.put_vector([0.5] * 20)["reason"], "candidate_capture_limit"
        )
        self.assertIsNotNone(store.put_vector([1] * 20, final=True)["sha256"])

    def test_small_storage_rejects_before_intent(self):
        store = self.store(artifact_bytes_limit=100)
        with self.assertRaises(ContractError):
            store.reserve_final_vectors(20)
        self.assertFalse((store.folder / "optimize.intent.json").exists())

    def test_intent_is_exclusive_and_not_a_completed_call(self):
        store = self.store()
        store.optimize_intent("synthetic-only")
        with self.assertRaises(FileExistsError):
            store.optimize_intent("another")
        store.close("interrupted")
        result = collect_attempt(store.folder)
        self.assertEqual(result["state"], "intent_without_native_return")
        self.assertEqual(result["observed_native_returns"], 0)

    def test_torn_tail_preserves_complete_prefix(self):
        store = self.store()
        store.append({"kind": "one"}, critical=True)
        store.stream.write(b'{"torn":')
        store.stream.flush()
        result = scan_journal(store.folder)
        self.assertTrue(result["truncated_tail"])
        self.assertEqual(len(result["frames"]), 1)

    def test_sealed_journal_tampering_is_rejected(self):
        store = self.store()
        store.append({"kind": "one"}, critical=True)
        store.close("offline")
        with (store.folder / "native-events.jsonl").open("ab") as stream:
            stream.write(b"broken")
        with self.assertRaises(ContractError):
            collect_attempt(store.folder)

    def test_noncanonical_duplicate_journal_fields_are_rejected(self):
        store = self.store()
        store.append({"kind": "one"}, critical=True)
        store.stream.close()
        store.stream = None
        path = store.folder / "native-events.jsonl"
        path.write_bytes(
            path.read_bytes().replace(b'"ordinal":1', b'"ordinal":1,"ordinal":1')
        )
        with self.assertRaises(ContractError):
            scan_journal(store.folder)

    def test_observer_keeps_candidate_objective_separate_from_best(self):
        store = self.store()
        api, native, _ = fake_api()
        native.ModelSense = 1
        observer = NativeObserver(
            api, NativeMatrix(native, "MAXIMIZE"), store, "incumbent"
        )
        observer(native, "MIPSOL")
        frame = scan_journal(store.folder)["frames"][0]
        self.assertEqual(frame["candidate_objective"]["value"], 20)
        self.assertEqual(frame["OBJBST"]["value"], 21)
        self.assertEqual(frame["SOLCNT"]["value"], 0)

    def test_polling_never_queries_callback_fields(self):
        store = self.store()
        api, native, _ = fake_api()
        native.ModelSense = 1
        observer = NativeObserver(
            api, NativeMatrix(native, "MAXIMIZE"), store, "incumbent"
        )
        native.cbGet = lambda code: self.fail("POLLING has no cbGet context")
        observer(native, "POLLING")
        self.assertEqual(observer.callback_ordinal, 0)

    def test_root_counts_nonoptimal_pass_and_captures_later_provenance(self):
        store = self.store()
        api, native, _ = fake_api()
        native.ModelSense = 1
        observer = NativeObserver(
            api, NativeMatrix(native, "MAXIMIZE"), store, "root_relaxation"
        )
        native.values["MIPNODE_STATUS"] = 3
        observer(native, "MIPNODE")
        self.assertIsNone(observer.captured_root)
        native.values["MIPNODE_STATUS"] = 2
        observer(native, "MIPNODE")
        self.assertEqual(
            observer.captured_root["root_event"],
            {"ordinal": 2, "cut_state": "later_cut_pass", "cut_pass": 1},
        )
        self.assertTrue(native.terminated)

    def test_native_session_is_fresh_one_call_and_closes_resources(self):
        store = self.store()
        api, native, env = fake_api()
        with self.session(store, api) as session:
            result = session.optimize_once()
            self.assertEqual(result["final_audit"]["status"], "qualified")
            with self.assertRaises(ContractError):
                session.optimize_once()
        store.close("returned")
        self.assertEqual(native.calls, 1)
        self.assertTrue(native.closed and env.closed)
        collected = collect_attempt(
            store.folder, matrix=DescriptionMatrix(model()), policy=AuditPolicy()
        )
        self.assertEqual(collected["observed_native_returns"], 1)
        self.assertEqual(
            collected["replayed_candidate_audits"][0]["audit"]["status"], "qualified"
        )

    def test_input_change_and_prior_solution_abort_admission(self):
        store = self.store()
        api, native, env = fake_api()
        native.SolCount = 1
        with self.assertRaises(ContractError), self.session(store, api):
            self.fail("Prior model solution admitted")
        self.assertTrue(native.closed and env.closed)

    def test_model_drift_is_detected_using_fresh_geometry(self):
        store = self.store()
        api, native, _ = fake_api()
        with self.session(store, api) as session:
            native.variables[0].UB = 0
            with self.assertRaises(ContractError):
                session.optimize_once()
        self.assertTrue((store.folder / "native-return.json").exists())
        self.assertFalse((store.folder / "native-result.json").exists())

    def test_changed_stored_input_rejected_without_environment_start(self):
        store = self.store()
        api, native, env = fake_api()
        self.input.write_text("changed")
        with self.assertRaises(ContractError):
            self.session(store, api).__enter__()
        self.assertFalse(env.started)
        self.assertEqual(native.calls, 0)

    def test_default_drift_rejected_before_optimize(self):
        store = self.store()
        api, native, env = fake_api()
        native.parameters["Cuts"] = 0
        with self.assertRaises(ContractError):
            self.session(store, api).__enter__()
        self.assertTrue(native.closed and env.closed)
        self.assertFalse((store.folder / "optimize.intent.json").exists())

    def test_primary_mode_requires_sealed_population_admission(self):
        self.binding["mode"] = "primary"
        store = self.store()
        api, native, env = fake_api()
        with self.assertRaises(ContractError):
            self.session(store, api).__enter__()
        self.assertFalse(env.started)
        self.assertEqual(native.calls, 0)

    def test_sealed_native_result_tampering_is_rejected(self):
        store = self.store()
        api, _, _ = fake_api()
        with self.session(store, api) as session:
            session.optimize_once()
        store.close("returned")
        path = store.folder / "native-result.json"
        path.write_bytes(
            path.read_bytes().replace(b'"native_status":2', b'"native_status":9')
        )
        with self.assertRaises(ContractError):
            collect_attempt(store.folder)

    def test_G_requires_released_predictor_hash(self):
        self.binding["key"].update(stage="evaluation", method="G")
        store = self.store()
        api, _, _ = fake_api()
        with self.session(store, api) as session:
            record = start(run("G"))
            record["key"] = copy.deepcopy(self.binding["key"])
            record["predictor_sha256"] = "0" * 64
            with self.assertRaises(ContractError):
                session.install_start(record)

    def test_empty_B_start_writes_no_native_Start_attribute(self):
        self.binding["key"].update(stage="evaluation", method="B")
        store = self.store()
        api, native, _ = fake_api()
        with self.session(store, api) as session:
            record = start(run("B"))
            record["key"] = copy.deepcopy(self.binding["key"])
            session.install_start(record)
            self.assertFalse(any(hasattr(var, "Start") for var in native.variables))
            with self.assertRaises(ContractError):
                session.install_start(record)

    def test_partial_R_start_only_assigns_selected_binaries(self):
        self.binding["key"].update(stage="evaluation", method="R")
        store = self.store()
        api, native, _ = fake_api()
        with self.session(store, api) as session:
            record = start(run("R"))
            record["key"] = copy.deepcopy(self.binding["key"])
            session.install_start(record)
            self.assertEqual([var.Start for var in native.variables[:2]], [0, 1])
            self.assertTrue(
                all(var.Start == api.GRB.UNDEFINED for var in native.variables[2:])
            )

    def test_evaluation_requires_explicit_start_even_for_B(self):
        self.binding["key"].update(stage="evaluation", method="B")
        store = self.store()
        api, native, _ = fake_api()
        with self.session(store, api) as session, self.assertRaises(ContractError):
            session.optimize_once()
        self.assertEqual(native.calls, 0)

    def test_callback_failure_is_explicit_and_does_not_leak_exception_values(self):
        store = self.store()
        api, native, _ = fake_api()
        native.ModelSense = 1
        observer = NativeObserver(
            api, NativeMatrix(native, "MAXIMIZE"), store, "incumbent"
        )
        native.cbGetSolution = lambda variables: (_ for _ in ()).throw(
            RuntimeError("private-test-value")
        )
        observer(native, "MIPSOL")
        self.assertTrue(native.terminated)
        self.assertNotIn("private-test-value", str(observer.summary()))


if __name__ == "__main__":
    unittest.main()
