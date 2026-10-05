"""Offline fake-runtime and process-supervision tests; never licensed solves.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import copy
import hashlib
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
import isolated_attempt_worker as worker  # noqa: E402


def request():
    proposal = worker.contract.compile_proposal()
    return {
        "schema_version": 1,
        "protocol_id": worker.PROTOCOL,
        "explicitly_approved": True,
        "approval_record_sha256": "1" * 64,
        "source_commit": "2" * 40,
        "dependency_sha256": worker.dependency_hashes(),
        "proposal_sha256": proposal["proposal_sha256"],
        "installed_preflight_receipt_sha256": worker.PREFLIGHT_SHA,
        "attempt_id": "medium-seed42-threads1",
        "optimization_limit_seconds": 30,
        "child_deadline_seconds": 210,
        "maximum_optimization_calls": 1,
        "scientific_reporting_eligible": False,
    }


def phase(name):
    return {
        "phase": name,
        "external_wall_seconds": 0.1,
        "process_cpu_seconds": 0.02,
        "call_failed": False,
    }


def affinity():
    return {
        "observed_cpu_ids": list(range(32)),
        "bound_cpu_ids": list(range(16)),
        "physical_cores": 16,
    }


def fake_resource():
    return SimpleNamespace(
        RUSAGE_SELF=0, getrusage=lambda _: SimpleNamespace(ru_maxrss=1024)
    )


def fake_api(output, status=9, count=1, gap=0.2, failure=None):
    events = []
    symbols = SimpleNamespace(
        **{name: i + 1 for i, name in enumerate(worker.adapter.SYMBOLS)}
    )

    class Env:
        def __init__(self, empty):
            self.empty = empty

        def __enter__(self):
            events.append("env_enter")
            return self

        def setParam(self, name, value):
            events.append((name, value))

        def start(self):
            events.append("env_start")

        def __exit__(self, *args):
            events.append("env_close")
            if failure == "cleanup":
                raise RuntimeError("LICENSEID private")

    class Model:
        def __init__(self):
            self.SolCount, self.Status, self.Runtime = count, status, 31
            self.ObjVal, self.ObjBound, self.MIPGap, self.NodeCount = (
                100,
                100 * (1 - gap),
                gap,
                1,
            )
            self.ModelSense, self.NumIntVars, self.NumObj = -1, 1, 1
            self.NumQNZs = self.NumQConstrs = self.NumGenConstrs = self.NumSOS = 0
            self.NumVars, self.NumConstrs, self.DNumNZs, self.ObjCon = 10, 4, 8, 0
            self.params = {}

        def __enter__(self):
            events.append("model_enter")
            return self

        def __exit__(self, *args):
            events.append("model_close")

        def update(self):
            pass

        def resetParams(self):
            events.append("reset")
            self.params = {}

        def getParamInfo(self, name):
            default = (
                float("inf") if name == "NodeLimit" else worker.DEFAULTS.get(name, -1)
            )
            return (name, float, self.params.get(name, default), None, None, default)

        def setParam(self, name, value):
            self.params[name] = value
            if name == "LogFile":
                Path(value).write_bytes(b"LICENSEID secret solver text\n")

        def cbGet(self, what):
            if failure == "callback":
                raise RuntimeError("LICENSEID secret")
            if what == symbols.RUNTIME:
                return 1
            if what in (symbols.MIP_OBJBST, symbols.MIPSOL_OBJBST):
                return 100 if count else 1e100
            if what in (symbols.MIP_OBJBND, symbols.MIPSOL_OBJBND):
                return 100 * (1 - gap)
            return 1

        def terminate(self):
            events.append("terminate")

        def optimize(self, callback):
            events.append("optimize")
            if failure == "optimize":
                raise RuntimeError("/home/private license error")
            callback(self, symbols.MIP)

    model = Model()

    def read(path, env):
        events.append("read")
        if failure == "read":
            raise RuntimeError("private")
        return model

    gp = SimpleNamespace(
        Env=Env,
        read=read,
        GRB=SimpleNamespace(Callback=symbols, INFINITY=1e100),
        gurobi=SimpleNamespace(version=lambda: (13, 0, 1)),
    )
    return gp, events, model


class WorkerTests(unittest.TestCase):
    def execute(self, output, **kwargs):
        gp, events, model = fake_api(output, **kwargs)
        req = request()
        (Path(output) / "child.started").write_bytes(
            worker.contract.sha(worker.contract.encoded(req)).encode()
        )
        with (
            patch.object(worker, "qualify_execution", return_value=Path(output)),
            patch.object(worker, "validate_claim"),
            patch.object(
                worker.adapter.screen, "qualify_affinity", return_value=affinity()
            ),
            patch.object(
                worker, "dependency_hashes", return_value=req["dependency_sha256"]
            ),
            patch.dict(sys.modules, {"resource": fake_resource()}),
            patch.dict(worker.os.environ, {"SLURM_JOB_ID": "123"}),
            patch.object(
                worker.adapter.screen,
                "frozen_source",
                return_value=Path(output) / "original.lp",
            ),
            patch.object(
                worker.adapter.screen,
                "digest",
                return_value="34d6773b78a2f7ea748b61e0f99a418f696e24f96d25886dd5c433549e8bbd4b",
            ),
            patch.object(worker.adapter.screen, "licensed_runtime", return_value=gp),
        ):
            worker.run_child(req, output)
        child = worker.strict_payload(
            (Path(output) / "child.private.json").read_bytes()
        )
        return req, child, events, model

    def test_exact_disabled_proposal_is_not_modified(self):
        before = worker.contract.compile_proposal()
        proposal, row = worker.validate_request(request())
        self.assertEqual(before, proposal)
        self.assertFalse(proposal["execution_enabled"])
        self.assertEqual(row["optimization_limit_seconds"], 3600)

    def test_budget_approval_head_dependency_and_protocol_guards(self):
        mutations = [
            ("explicitly_approved", False),
            ("optimization_limit_seconds", True),
            ("optimization_limit_seconds", 301),
            ("child_deadline_seconds", 999),
            ("maximum_optimization_calls", 2),
            ("installed_preflight_receipt_sha256", "0" * 64),
            ("approval_record_sha256", "0" * 64),
            ("source_commit", "garbage"),
            ("proposal_sha256", "0" * 64),
            ("attempt_id", "test-parent"),
            ("scientific_reporting_eligible", True),
            ("protocol_id", "comparison"),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                req = request()
                req[key] = value
                worker.validate_request(req)
        req = request()
        req["dependency_sha256"].pop("isolated_attempt_worker.py")
        with self.assertRaises(ValueError):
            worker.validate_request(req)
        req = request()
        req["new_field"] = "private"
        with self.assertRaises(ValueError):
            worker.validate_request(req)

    def test_strict_json_duplicate_nonfinite_noncanonical_and_private(self):
        for raw in (
            b'{"a":1,"a":2}',
            b'{"a":NaN}',
            b'{"a":1}',
            worker.contract.encoded({"secret": "LICENSEID=private"}),
        ):
            with self.assertRaises(ValueError):
                worker.strict_payload(raw)

    def test_bounded_read_symlink_size_and_write_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "value.json"
            worker.write_json(path, {"x": 1})
            self.assertEqual(worker.strict_payload(worker.read_bytes(path)), {"x": 1})
            with self.assertRaises(FileExistsError):
                worker.write_json(path, {"x": 2})
            with self.assertRaises(ValueError):
                worker.read_bytes(path, 1)
            with (
                patch.object(Path, "is_symlink", return_value=True),
                self.assertRaises(ValueError),
            ):
                worker.read_bytes(path)

    def test_phases_are_unique_ordered_disjoint_and_finite(self):
        worker.validate_phases([phase("read_setup"), phase("cleanup")])
        for phases in (
            [],
            [phase("optimization")],
            [phase("cleanup"), phase("read_setup")],
            [phase("cleanup"), phase("cleanup")],
        ):
            with self.assertRaises(ValueError):
                worker.validate_phases(phases)
        bad = phase("cleanup")
        bad["process_cpu_seconds"] = -1
        with self.assertRaises(ValueError):
            worker.validate_phases([bad])

    def test_one_model_callback_and_post_disposal_sealing(self):
        with tempfile.TemporaryDirectory() as tmp:
            req, child, events, model = self.execute(tmp)
            worker.validate_child(child, req)
            self.assertEqual(events.count("read"), 1)
            self.assertEqual(events.count("optimize"), 1)
            self.assertLess(events.index("model_close"), events.index("env_close"))
            self.assertEqual(child["optimization_calls"], 1)
            self.assertEqual(child["result"]["stop"], "time_limit")
            self.assertEqual(child["result"]["time_limit_overshoot_seconds"], 1)
            self.assertEqual(
                child["gurobi_log"]["log_sha256"],
                hashlib.sha256(
                    (Path(tmp) / "gurobi.private.log").read_bytes()
                ).hexdigest(),
            )
            self.assertNotIn("secret", worker.contract.encoded(child).decode())
            self.assertEqual(model.params["TimeLimit"], 30)
            self.assertEqual(model.params["Threads"], 1)
            self.assertEqual(
                [p["phase"] for p in child["phases"]],
                ["read_setup", "optimization", "cleanup"],
            )

    def test_zero_incumbent_keeps_gap_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            req, child, _, _ = self.execute(tmp, count=0)
            worker.validate_child(child, req)
            self.assertIsNone(child["result"]["terminal"]["primal"])
            self.assertIsNone(child["result"]["terminal"]["gap_relative"])
            self.assertEqual(
                child["result"]["first_sampled_gap_observations"][0]["state"],
                "right_censored",
            )

    def test_planned_gap_stop_and_memory_stop(self):
        for status, gap, stop in ((2, 0.09, "gap_target"), (17, 0.2, "memory_limit")):
            with tempfile.TemporaryDirectory() as tmp:
                req, child, _, _ = self.execute(tmp, status=status, gap=gap)
                worker.validate_child(child, req)
                self.assertEqual(child["result"]["stop"], stop)

    def test_callback_failure_is_preserved_no_private_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            req, child, events, _ = self.execute(tmp, failure="callback")
            worker.validate_child(child, req)
            self.assertIn("terminate", events)
            self.assertEqual(child["result"]["stop"], "worker_failure")
            self.assertEqual(
                child["result"]["gurobi_callback"]["failure_code"],
                "callback_observation_failure",
            )

    def test_read_optimize_and_cleanup_faults_preserve_fixed_codes(self):
        for failure, code, calls in (
            ("read", "worker_read_setup_failed", 0),
            ("optimize", "worker_optimization_failed", 1),
            ("cleanup", "worker_cleanup_failed", 1),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                req, child, events, _ = self.execute(tmp, failure=failure)
                worker.validate_child(child, req)
                self.assertEqual(child["failure_code"], code)
                self.assertEqual(child["optimization_calls"], calls)
                self.assertIn("env_close", events)
                if failure == "cleanup":
                    self.assertIsNone(child["gurobi_log"])

    def test_validator_rejects_first_targets_terminal_bounds_and_hidden_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            req, original, _, _ = self.execute(tmp)
            mutations = []
            q = copy.deepcopy(original)
            q["result"]["terminal"]["gap_relative"] = 0
            mutations.append(q)
            q = copy.deepcopy(original)
            q["result"]["first_sampled_gap_observations"][0]["state"] = "observed"
            mutations.append(q)
            q = copy.deepcopy(original)
            q["result"]["samples"][0]["dual"] = 100
            mutations.append(q)
            q = copy.deepcopy(original)
            q["result"]["dropped_sample_count"] = 1
            mutations.append(q)
            q = copy.deepcopy(original)
            q["result"]["scientific_reporting_eligible"] = True
            mutations.append(q)
            q = copy.deepcopy(original)
            q["affinity"]["physical_cores"] = 8
            mutations.append(q)
            q = copy.deepcopy(original)
            q["effective_parameters"]["Seed"] = 43
            mutations.append(q)
            q = copy.deepcopy(original)
            q["result"]["gurobi_callback"]["candidate_vectors_read"] = True
            mutations.append(q)
            q = copy.deepcopy(original)
            q["raw_log"] = "text"
            mutations.append(q)
            for q in mutations:
                with self.assertRaises(ValueError):
                    worker.validate_child(q, req)

    def test_log_seal_failure_and_source_change_do_not_claim_success(self):
        for fault in ("seal", "source"):
            with tempfile.TemporaryDirectory() as tmp:
                gp, _, _ = fake_api(tmp)
                req = request()
                (Path(tmp) / "child.started").write_bytes(
                    worker.contract.sha(worker.contract.encoded(req)).encode()
                )
                original_sha = (
                    "34d6773b78a2f7ea748b61e0f99a418f696e24f96d25886dd5c433549e8bbd4b"
                )
                with (
                    patch.object(worker, "qualify_execution", return_value=Path(tmp)),
                    patch.object(worker, "validate_claim"),
                    patch.object(
                        worker.adapter.screen,
                        "qualify_affinity",
                        return_value=affinity(),
                    ),
                    patch.object(
                        worker,
                        "dependency_hashes",
                        return_value=req["dependency_sha256"],
                    ),
                    patch.dict(sys.modules, {"resource": fake_resource()}),
                    patch.dict(worker.os.environ, {"SLURM_JOB_ID": "123"}),
                    patch.object(
                        worker.adapter.screen,
                        "frozen_source",
                        return_value=Path(tmp) / "original.lp",
                    ),
                    patch.object(
                        worker.adapter.screen, "licensed_runtime", return_value=gp
                    ),
                    patch.object(
                        worker.adapter.screen,
                        "digest",
                        return_value=original_sha if fault == "seal" else "0" * 64,
                    ),
                    patch.object(
                        worker.contract,
                        "seal_closed_log",
                        side_effect=ValueError("private"),
                    ),
                ):
                    worker.run_child(req, tmp)
                child = worker.strict_payload(
                    (Path(tmp) / "child.private.json").read_bytes()
                )
                self.assertEqual(
                    child["failure_code"],
                    "worker_log_seal_failed"
                    if fault == "seal"
                    else "worker_source_changed",
                )


class SupervisorTests(unittest.TestCase):
    def test_private_dispatch_claims_once_and_refuses_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            req = request()
            worker.write_json(out / "request.private.json", req)
            digest = worker.contract.sha(worker.contract.encoded(req))
            with (
                patch.object(worker, "qualify_execution", return_value=out),
                patch.object(worker, "validate_claim"),
                patch.object(worker, "run_child") as run,
            ):
                worker.internal_child(str(out), digest)
                run.assert_called_once_with(req, out)
                with self.assertRaises(SystemExit):
                    worker.internal_child(str(out), digest)
                run.assert_called_once()
            with self.assertRaises(SystemExit):
                worker.internal_child(str(out), "0" * 64)

    def test_worker_second_entry_refused_before_license_or_optimize(self):
        with tempfile.TemporaryDirectory() as tmp:
            req, _, _, _ = WorkerTests().execute(tmp)
            with (
                patch.object(worker, "qualify_execution", return_value=Path(tmp)),
                patch.object(worker, "validate_claim"),
                patch.object(worker.adapter.screen, "licensed_runtime") as licensed,
            ):
                with self.assertRaises(FileExistsError):
                    worker.run_child(req, tmp)
                licensed.assert_not_called()

    def test_python_interrupt_kills_and_reaps_child_without_export(self):
        proc = Mock(pid=4321)
        proc.wait.side_effect = [KeyboardInterrupt(), -9]
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(worker.subprocess, "Popen", return_value=proc),
            patch.object(worker.os, "killpg", create=True) as kill,
            patch.object(worker.signal, "SIGKILL", 9, create=True),
        ):
            with self.assertRaises(KeyboardInterrupt):
                worker.supervise_process(
                    ["child"], Path(tmp) / "console.private.log", 1
                )
            kill.assert_called_once_with(4321, 9)
            self.assertEqual(proc.wait.call_count, 2)

    def test_real_fresh_python_process_without_solver_or_hpc(self):
        with tempfile.TemporaryDirectory() as tmp:
            console = Path(tmp) / "console.private.log"
            code, timed_out = worker.supervise_process(
                [sys.executable, "-B", "-c", "print('synthetic-child-only')"],
                console,
                15,
            )
            self.assertEqual((code, timed_out), (0, False))
            self.assertEqual(console.read_text().strip(), "synthetic-child-only")

    @unittest.skipUnless(sys.platform == "linux", "POSIX process groups only")
    def test_real_posix_watchdog_no_solver_or_cluster(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, timed_out = worker.supervise_process(
                [sys.executable, "-B", "-c", "import time;time.sleep(60)"],
                Path(tmp) / "console.private.log",
                0.1,
            )
            self.assertTrue(timed_out)
            self.assertLess(code, 0)

    def test_archive_validated_without_extraction_wrong_hash_or_extra_members_rejected(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            out, _, original = self.run_fake(tmp)
            export = Path(tmp) / "public"
            worker.export_receipt(out, export)
            package = export / "isolated_attempt_evidence.tar.gz"
            digest = hashlib.sha256(package.read_bytes()).hexdigest()
            self.assertEqual(worker.validate_archive(package, digest), original)
            with self.assertRaises(ValueError):
                worker.validate_archive(package, "0" * 64)
            for member_name, kind in (
                ("../secret", tarfile.REGTYPE),
                ("request.json", tarfile.SYMTYPE),
                ("request.json", tarfile.REGTYPE),
            ):
                bad = Path(tmp) / "bad.tar.gz"
                with tarfile.open(bad, "w:gz") as stream:
                    for name in worker.PUBLIC:
                        info = tarfile.TarInfo(name)
                        raw = (out / name).read_bytes()
                        info.size = len(raw)
                        stream.addfile(info, io.BytesIO(raw))
                    info = tarfile.TarInfo(member_name)
                    info.type = kind
                    info.linkname = "/private" if kind == tarfile.SYMTYPE else ""
                    stream.addfile(info, io.BytesIO(b""))
                with self.assertRaises(ValueError):
                    worker.validate_archive(
                        bad, hashlib.sha256(bad.read_bytes()).hexdigest()
                    )

    def test_archive_decompressed_bound_and_trailing_hidden_data_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _, _ = self.run_fake(tmp)
            export = Path(tmp) / "public"
            worker.export_receipt(out, export)
            package = export / "isolated_attempt_evidence.tar.gz"
            with patch.object(worker, "MAX_JSON", 1), self.assertRaises(ValueError):
                worker.validate_archive(
                    package, hashlib.sha256(package.read_bytes()).hexdigest()
                )
            bomb = Path(tmp) / "bounded-gzip.tar.gz"
            bomb.write_bytes(worker.gzip.compress(b"x" * (65 * 1024 + 1)))
            with patch.object(worker, "MAX_JSON", 1), self.assertRaises(ValueError):
                worker.validate_archive(
                    bomb, hashlib.sha256(bomb.read_bytes()).hexdigest()
                )
            decoded = worker.gzip.decompress(package.read_bytes())
            bad = Path(tmp) / "trailing.tar.gz"
            bad.write_bytes(worker.gzip.compress(decoded + b"hidden text"))
            with self.assertRaises(ValueError):
                worker.validate_archive(
                    bad, hashlib.sha256(bad.read_bytes()).hexdigest()
                )

    def test_qualification_env_rejects_cpu_memory_gpu_node_or_conda_mismatch(self):
        baseline = {
            "CONDA_DEFAULT_ENV": "tfm_env",
            "SLURM_CPUS_PER_TASK": "16",
            "SLURM_MEM_PER_NODE": "65536",
            "SLURM_JOB_NUM_NODES": "1",
            "SLURM_JOB_ID": "123",
            "SLURM_JOB_GPUS": "",
            "SLURM_STEP_GPUS": "",
        }
        for key, value in (
            ("CONDA_DEFAULT_ENV", "wrong"),
            ("SLURM_CPUS_PER_TASK", "32"),
            ("SLURM_MEM_PER_NODE", "32768"),
            ("SLURM_JOB_GPUS", "0"),
            ("SLURM_JOB_NUM_NODES", "2"),
            ("SLURM_JOB_ID", "unknown"),
        ):
            env = {**baseline, key: value}
            with (
                patch.object(worker.sys, "platform", "linux"),
                patch.object(worker.socket, "gethostname", return_value="dgx-dasci"),
                patch.dict(worker.os.environ, env, clear=True),
                patch.object(worker.adapter.screen, "licensed_runtime") as licensed,
            ):
                with self.assertRaises(ValueError):
                    worker.qualify_execution(
                        request(),
                        Path("/raid/vrcelestino/data/cfl-mvp2-evidence/not-run"),
                        True,
                    )
                licensed.assert_not_called()

    def test_local_host_is_refused_before_output_or_subprocess(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(worker.subprocess, "Popen") as popen,
        ):
            path = Path(tmp) / "new"
            with self.assertRaises(ValueError):
                worker.supervise_one(request(), path)
            self.assertFalse(path.exists())
            popen.assert_not_called()

    def test_authorization_claim_is_global_persistent_and_no_overwrite(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            # Windows runners may expose TEMP through a drive junction.
            patch.object(worker.adapter, "EVIDENCE_ROOT", Path(tmp).resolve()),
        ):
            req = request()
            out = Path(tmp) / "attempt"
            claimed = worker.claim_authorization(req, out)
            worker.validate_claim(req, out)
            with self.assertRaises(ValueError):
                worker.validate_claim(req, Path(tmp) / "another")
            self.assertEqual(
                worker.strict_payload((claimed / "request.json").read_bytes()), req
            )
            with self.assertRaises(FileExistsError):
                worker.claim_authorization(req, out)
            req["optimization_limit_seconds"] = 10
            req["child_deadline_seconds"] = 190
            with self.assertRaises(FileExistsError):
                worker.claim_authorization(req, out)

    def test_watchdog_escalates_own_process_group_and_waits_for_exit(self):
        proc = Mock(pid=4321)
        proc.wait.side_effect = [
            subprocess.TimeoutExpired("child", 210),
            subprocess.TimeoutExpired("child", 10),
            -9,
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(worker.subprocess, "Popen", return_value=proc) as popen,
            patch.object(worker.os, "killpg", create=True) as kill,
            patch.object(worker.signal, "SIGKILL", 9, create=True),
        ):
            code, timeout = worker.supervise_process(
                ["fixed-child"], Path(tmp) / "console.private.log", 210
            )
            self.assertTrue(timeout)
            self.assertEqual(code, -9)
            self.assertEqual(
                [c.args for c in kill.call_args_list],
                [(4321, worker.signal.SIGTERM), (4321, worker.signal.SIGKILL)],
            )
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertTrue(popen.call_args.kwargs["stdout"].closed)

    def test_watchdog_term_exit_and_process_lookup_race(self):
        proc = Mock(pid=4321)
        proc.wait.side_effect = [subprocess.TimeoutExpired("child", 210), -15]
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(worker.subprocess, "Popen", return_value=proc),
            patch.object(
                worker.os, "killpg", side_effect=ProcessLookupError, create=True
            ),
        ):
            self.assertEqual(
                worker.supervise_process(
                    ["child"], Path(tmp) / "console.private.log", 210
                ),
                (-15, True),
            )

    def run_fake(
        self,
        root,
        status=9,
        count=1,
        gap=0.2,
        fault=None,
        timed_out=False,
        returncode=0,
    ):
        req = request()
        out = Path(root) / "attempt"

        def child(command, console, deadline):
            Path(console).write_bytes(b"LICENSEID secret console\n")
            if returncode == 0 and not timed_out:
                tests = WorkerTests()
                tests.execute(out, status=status, count=count, gap=gap, failure=fault)
            return returncode, timed_out

        with (
            patch.object(worker, "qualify_execution", return_value=out),
            patch.object(worker, "claim_authorization") as claim,
            patch.object(worker, "supervise_process", side_effect=child),
        ):
            value = worker.supervise_one(req, out)
            claim.assert_called_once_with(req, out)
        return out, req, value

    def test_fresh_process_and_closed_console_child_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, req, value = self.run_fake(tmp)
            self.assertEqual(value["status"], "completed")
            self.assertFalse(value["pause_remaining_matrix"])
            self.assertEqual(value["optimization_calls_known"], 1)
            worker.validate_directory(out, private=True)
            self.assertEqual(
                value["child_report_sha256"],
                hashlib.sha256((out / "child.private.json").read_bytes()).hexdigest(),
            )
            with (
                patch.object(worker, "qualify_execution", return_value=out),
                patch.object(worker, "claim_authorization"),
                self.assertRaises(FileExistsError),
            ):
                worker.supervise_one(req, out)

    def test_memory_and_callback_stops_pause_remaining_matrix(self):
        for status, fault in (
            (17, None),
            (9, "callback"),
            (9, "optimize"),
            (9, "cleanup"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                _, _, value = self.run_fake(tmp, status=status, fault=fault)
                self.assertEqual(value["status"], "worker_stopped")
                self.assertTrue(value["pause_remaining_matrix"])

    def test_watchdog_and_nonzero_exit_never_fabricate_zero_optimization(self):
        for timeout, code, state in (
            (True, -9, "watchdog_timeout"),
            (False, 2, "process_failure"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                out, req, value = self.run_fake(tmp, timed_out=timeout, returncode=code)
                self.assertEqual(value["status"], state)
                self.assertIsNone(value["optimization_calls_known"])
                self.assertIsNone(value["child"])
                worker.validate_directory(out, private=True)
                bad = copy.deepcopy(value)
                bad["optimization_calls_known"] = 0
                with self.assertRaises(ValueError):
                    worker.validate_receipt(bad, req)

    def test_launch_failure_fixed_code_and_unknown_call_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "attempt"
            with (
                patch.object(worker, "qualify_execution", return_value=out),
                patch.object(worker, "claim_authorization"),
                patch.object(
                    worker, "supervise_process", side_effect=OSError("LICENSEID secret")
                ),
            ):
                value = worker.supervise_one(request(), out)
            self.assertEqual(
                value["failure_code"], "supervisor_or_receipt_validation_failed"
            )
            self.assertIsNone(value["optimization_calls_known"])
            self.assertNotIn("secret", worker.contract.encoded(value).decode())

    def test_export_three_members_no_log_and_detects_post_receipt_log_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, _, value = self.run_fake(tmp)
            export = Path(tmp) / "public"
            worker.export_receipt(out, export)
            package = export / "isolated_attempt_evidence.tar.gz"
            with tarfile.open(package) as stream:
                self.assertEqual(stream.getnames(), list(worker.PUBLIC))
                for name in worker.PUBLIC:
                    self.assertEqual(
                        stream.extractfile(name).read(), (out / name).read_bytes()
                    )
            self.assertEqual(
                (export / "PACKAGE_SHA256.txt").read_text().split()[0],
                hashlib.sha256(package.read_bytes()).hexdigest(),
            )
            with self.assertRaises(ValueError):
                worker.export_receipt(out, export)
            (out / "gurobi.private.log").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                worker.export_receipt(out, Path(tmp) / "public2")
            self.assertFalse((Path(tmp) / "public2").exists())

    def test_manifest_receipt_request_and_child_tampering_rejected(self):
        for filename in (
            "request.json",
            "attempt_receipt.json",
            "SHA256SUMS.txt",
            "child.private.json",
        ):
            with tempfile.TemporaryDirectory() as tmp:
                out, _, _ = self.run_fake(tmp)
                path = out / filename
                path.write_bytes(path.read_bytes() + b" ")
                with self.assertRaises(ValueError):
                    worker.validate_directory(out, private=True)

    def test_public_cli_has_no_solve_or_submission_action(self):
        tree = ast.parse(Path(worker.__file__).read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        optimizers = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "optimize"
        ]
        self.assertEqual(len(optimizers), 1)
        self.assertEqual(ast.unparse(optimizers[0]), "model.optimize(callback)")
        source = Path(worker.__file__).read_text()
        self.assertIn('choices=("validate", "export")', source)
        self.assertNotIn('"sbatch"', source)


if __name__ == "__main__":
    unittest.main()
