"""Offline production qualification tests. No Slurm, remote host or real Gurobi."""
# ruff: noqa: E402 -- checkout bootstrap

import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fake_native import fake_api

from cfl_gnn.mvp3.contract import ContractError, digest, load_json
from cfl_gnn.mvp3.journal import durable_json, file_sha256
from cfl_gnn.mvp3.production.allocation import (
    audit_allocation,
    cgroup_memory,
    expand_cpus,
)
from cfl_gnn.mvp3.production.collection import collect
from cfl_gnn.mvp3.production.inventory import (
    bounded_read,
    parse_inventory,
    read_commands,
    storage_inventory,
)
from cfl_gnn.mvp3.production.planning import load_plan, make_plan
from cfl_gnn.mvp3.production.policy import (
    candidate,
    policy,
    slurm_pairs,
    technical_parameters,
)
from cfl_gnn.mvp3.production.release import prepare, verify_bundle
from cfl_gnn.mvp3.production.worker import probe


def node(name="n256", memory="250000"):
    return {
        "NodeName": name,
        "Sockets": "2",
        "CoresPerSocket": "16",
        "ThreadsPerCore": "2",
        "CPUTot": "64",
        "RealMemory": memory,
        "Gres": "(null)",
        "State": "IDLE",
        "Partitions": "compute",
    }


def scheduler_outputs():
    return {
        "version": "slurm22.05.11",
        "nodes": "\n".join(
            " ".join(f"{key}={value}" for key, value in row.items())
            for row in (node(), node("n512", "500000"))
        ),
        "partitions": "PartitionName=compute State=UP Nodes=n[256,512] MaxTime=2-00:00:00 AllowAccounts=ALL",
        "config": "SelectType = select/cons_tres\nTaskPlugin = task/affinity,task/cgroup\nAuthInfo = private-test-do-not-copy\n",
        "own_jobs": "",
        "own_associations": "cluster|account||preempt,normal|preempt\n",
    }


def cpu():
    return {
        "logical_ids": list(range(64)),
        "vendors": ["GenuineIntel"],
        "mapping": [
            {
                "logical_id": i,
                "package_id": (i % 32) // 16,
                "core_id": i % 16,
                "siblings": [i % 32, i % 32 + 32],
            }
            for i in range(64)
        ],
    }


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def bundle(self):
        root = self.folder / "bundle"
        paths = ("src/cfl_gnn/__init__.py", "scripts/mvp3/qualify_production.py")
        files = {}
        for name in paths:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# invented source fixture\n")
            files[name] = {"sha256": file_sha256(path), "bytes": path.stat().st_size}
        manifest = {
            "schema_version": policy()["schema_version"],
            "source_commit": "a" * 40,
            "scientific_execution_authorized": False,
            "files": files,
        }
        checksum = durable_json(root / "bundle-manifest.json", manifest)
        return root, checksum, manifest

    def plan(self, python=None):
        bundle, checksum, manifest = self.bundle()
        python = python or self.folder / "python"
        license_file = self.folder / "fake.lic"
        license_file.write_text("invented-never-read")
        discovery = {
            "source_commit": "a" * 40,
            "inventory": parse_inventory(scheduler_outputs()),
            "commands_failed": {},
            "created_utc": "2026-11-26T12:00:00+00:00",
            "package_versions": {"gurobipy": "14.0.0"},
            "license_file_exists": True,
            "license_file_path": str(license_file.resolve()),
            "python_executable": str(python),
            "python_prefix": str(self.folder),
        }
        path = self.folder / "discovery.json"
        durable_json(path, discovery)
        proposal = make_plan(
            bundle,
            checksum,
            path,
            self.folder / "proposal",
            partition="compute",
            account="account",
            qos="preempt",
            nodes={"intel-256": "n256", "intel-512": "n512"},
            python=python,
            license_file=license_file,
            approval_reference="invented-offline-not-execution-authority",
        )
        plan_path = self.folder / "proposal/plan.json"
        return (
            load_plan(plan_path, proposal["plan_sha256"], manifest),
            proposal,
            plan_path,
        )

    def test_envelope_is_separate_from_primary_budget(self):
        self.assertEqual(policy()["maximum_technical_calls"], 2)
        self.assertEqual(policy()["job_seconds"], 300)
        self.assertEqual(policy()["primary_calls_released"], 0)
        self.assertEqual(technical_parameters()["Threads"], 0)
        self.assertEqual(technical_parameters()["TimeLimit"], 10)
        self.assertEqual(load_json(ROOT / "configs/mvp3/production/v1.json"), policy())

    def test_candidate_topology_and_memory_do_not_assert_vendor(self):
        self.assertTrue(candidate(node(), "intel-256"))
        self.assertFalse(candidate(node(), "intel-512"))
        self.assertTrue(candidate(node(memory="500000"), "intel-512"))
        for change in (
            {"CPUTot": "256"},
            {"Gres": "gpu:V100:8"},
            {"State": "IDLE+DRAIN"},
        ):
            self.assertFalse(candidate({**node(), **change}, "intel-256"))

    def test_readonly_inventory_strips_nonselected_config_fields(self):
        result = parse_inventory(scheduler_outputs())
        self.assertNotIn("private-test", json.dumps(result))
        self.assertEqual(
            result["candidate_nodes"], {"intel-256": ["n256"], "intel-512": ["n512"]}
        )
        self.assertFalse(
            any(
                word in " ".join(args)
                for args in read_commands("researcher").values()
                for word in ("sbatch", "scancel", "scontrol update")
            )
        )

    def test_storage_inventory_uses_only_names_sizes_and_filesystem_metadata(self):
        data = self.folder / "data"
        data.mkdir()
        (data / "invented.lp.gz").write_bytes(b"not-a-gzip")
        catalogue = {
            "parents": [{"original_id": "invented", "alias": "E0", "stored_bytes": 10}]
        }
        with (
            patch(
                "cfl_gnn.mvp3.production.inventory.os.statvfs",
                return_value=SimpleNamespace(
                    f_favail=100,
                    f_bavail=100,
                    f_bfree=200,
                    f_frsize=4096,
                    f_blocks=1000,
                ),
                create=True,
            ),
            patch.object(
                Path,
                "open",
                side_effect=AssertionError("Input contents must not be opened"),
            ),
        ):
            result = storage_inventory(data, self.folder, catalogue)
        self.assertTrue(result["all_expected_metadata_present"])
        self.assertFalse(result["input_contents_opened_hashed_or_decompressed"])
        self.assertFalse(result["S2_input_readiness_established"])

    def test_missing_qos_default_field_is_retained_as_empty_metadata(self):
        outputs = scheduler_outputs()
        outputs["own_associations"] = "cluster|account||preempt|\n"
        self.assertEqual(
            parse_inventory(outputs)["own_associations"][0]["default_qos"], ""
        )

    def test_scheduler_parser_preserves_spaces_but_rejects_duplicates(self):
        self.assertEqual(
            slurm_pairs("NodeName=n1 Reason=multi word reason State=IDLE")["Reason"],
            "multi word reason",
        )
        with self.assertRaises(ContractError):
            slurm_pairs("JobId=1 JobId=2")
        with self.assertRaises(ContractError):
            read_commands("user;touch-bad")

    def test_bounded_reader_runs_only_tiny_offline_child_and_rejects_overflow(self):
        self.assertEqual(
            bounded_read([sys.executable, "-c", "print('offline')"]).strip(), "offline"
        )
        with self.assertRaises(ValueError):
            bounded_read([sys.executable, "-c", "print('x'*100000)"], maximum_bytes=100)

    def test_effective_allocation_requires_every_scope(self):
        job = "JobId=42 UserId=researcher(1000) JobState=RUNNING NodeList=n256 NumNodes=1 NumTasks=1 NumCPUs=64 OverSubscribe=NO AllocTRES=cpu=64,mem=192G,node=1"
        memory = {
            "PID_membership_verified": True,
            "job_id": "42",
            "effective_process_memory_limit_bytes": 192 * 1024**3,
            "limit_chain_complete": True,
            "memory_mount_root_is_host_root": True,
            "kernel_hierarchy_consistent": True,
            "peak_job_bytes": 123,
        }
        kwargs = dict(
            uid=1000,
            job_id="42",
            node_name="n256",
            memtotal_bytes=250 * 1024**3,
            own_job_count=2,
        )
        result = audit_allocation(
            "intel-256",
            job,
            " ".join(f"{k}={v}" for k, v in node().items()),
            cpu(),
            memory,
            **kwargs,
        )
        self.assertTrue(result["allocation_qualified"])
        self.assertFalse(result["real_CFL_memory_adequacy_established"])
        for modified, cpus, mem in (
            (job.replace("OverSubscribe=NO", "OverSubscribe=YES"), cpu(), memory),
            (job + " Exclusive=NO", cpu(), memory),
            (job, {**cpu(), "vendors": ["AuthenticAMD"]}, memory),
            (job, cpu(), {**memory, "effective_process_memory_limit_bytes": None}),
            (job, cpu(), {**memory, "job_id": "420"}),
        ):
            self.assertFalse(
                audit_allocation(
                    "intel-256",
                    modified,
                    " ".join(f"{k}={v}" for k, v in node().items()),
                    cpus,
                    mem,
                    **kwargs,
                )["allocation_qualified"]
            )

    def cgroup(self, kind):
        proc = self.folder / "proc/self"
        proc.mkdir(parents=True)
        mount = self.folder / "memory"
        job = mount / "uid_1000/job_42"
        child = job / "step_0"
        child.mkdir(parents=True)
        limit = str(192 * 1024**3)
        for path in (mount, job.parent, child):
            (
                path / ("memory.max" if kind == "v2" else "memory.limit_in_bytes")
            ).write_text("max" if kind == "v2" else str(2**63 - 4096))
        if kind == "v2":
            (proc / "cgroup").write_text("0::/slurm/uid_1000/job_42/step_0\n")
            (proc / "mountinfo").write_text(
                f"1 0 0:1 /slurm {mount.as_posix()} rw - cgroup2 cgroup rw\n"
            )
            for name, value in (
                ("memory.current", "12"),
                ("memory.peak", "34"),
                ("memory.max", limit),
                ("memory.events", "oom 0\noom_kill 0\n"),
            ):
                (job / name).write_text(value)
        else:
            (proc / "cgroup").write_text("7:memory:/slurm/uid_1000/job_42/step_0\n")
            (child / "memory.stat").write_text(f"hierarchical_memory_limit {limit}\n")
            (proc / "mountinfo").write_text(
                f"1 0 0:1 /slurm {mount.as_posix()} rw - cgroup cgroup rw,memory\n"
            )
            for name, value in (
                ("memory.usage_in_bytes", "12"),
                ("memory.max_usage_in_bytes", "34"),
                ("memory.limit_in_bytes", limit),
                ("memory.failcnt", "0"),
                ("memory.oom_control", "under_oom 0\noom_kill 0\n"),
            ):
                (job / name).write_text(value)
        return proc

    def test_cgroup_v2_maps_mount_root_and_exact_job(self):
        self.cgroup("v2")
        result = cgroup_memory("42", proc=self.folder / "proc")
        self.assertEqual(result["version"], "v2")
        self.assertFalse(result["memory_mount_root_is_host_root"])
        self.assertEqual(result["peak_job_bytes"], 34)
        self.assertEqual(result["effective_process_memory_limit_bytes"], 192 * 1024**3)
        with self.assertRaises(ContractError):
            cgroup_memory("420", proc=self.folder / "proc")

    def test_cgroup_v1_preserves_peak_scope_and_limit(self):
        self.cgroup("v1")
        result = cgroup_memory("42", proc=self.folder / "proc")
        self.assertEqual(result["version"], "v1")
        self.assertEqual(result["current_job_bytes"], 12)
        self.assertEqual(result["events"]["failcnt"], 0)
        self.assertTrue(result["kernel_hierarchy_consistent"])

    def test_v1_disabled_hierarchy_cannot_imply_an_effective_ancestor_limit(self):
        self.cgroup("v1")
        (self.folder / "memory/uid_1000/job_42/step_0/memory.stat").write_text(
            f"hierarchical_memory_limit {2**63 - 4096}\n"
        )
        result = cgroup_memory("42", proc=self.folder / "proc")
        self.assertFalse(result["kernel_hierarchy_consistent"])

    def test_missing_ancestor_limit_is_explicit_and_ineligible(self):
        self.cgroup("v2")
        (self.folder / "memory/uid_1000/memory.max").unlink()
        result = cgroup_memory("42", proc=self.folder / "proc")
        self.assertFalse(result["limit_chain_complete"])
        self.assertEqual(len(result["unreadable_limit_scopes"]), 1)

    def test_cpu_range_parser_rejects_reversed_or_injected_ranges(self):
        self.assertEqual(expand_cpus("0-2,5"), [0, 1, 2, 5])
        for value in ("2-0", "0;bad", "0-100001"):
            with self.assertRaises(ContractError):
                expand_cpus(value)

    def test_portable_bundle_rejects_changed_bytes_extra_files_and_traversal(self):
        root, checksum, _ = self.bundle()
        verify_bundle(root, checksum)
        (root / "extra.py").write_text("bad")
        with self.assertRaises(ContractError):
            verify_bundle(root, checksum)
        (root / "extra.py").unlink()
        (root / "scripts/mvp3/qualify_production.py").write_text("changed")
        with self.assertRaises(ContractError):
            verify_bundle(root, checksum)

    def test_plan_is_immutable_two_bounded_proposals_not_submission(self):
        plan, proposal, path = self.plan()
        self.assertEqual(proposal["jobs_submitted"], 0)
        self.assertFalse(plan["scientific_release"])
        self.assertEqual(len(plan["slots"]), 2)
        script = (path.parent / "intel-256.sbs").read_text()
        for fragment in (
            "--cpus-per-task=64",
            "--threads-per-core=2",
            "--exclusive",
            "--mem=192G",
            "--time=00:05:00",
            "--no-requeue",
        ):
            self.assertIn(fragment, script)
        if os.name == "posix":
            for profile in plan["slots"]:
                subprocess.run(
                    ["bash", "-n", str(path.parent / f"{profile}.sbs")], check=True
                )
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ContractError):
            load_plan(path, proposal["plan_sha256"], {"source_commit": "a" * 40})

    def test_plan_rejects_other_bundle_even_with_same_source(self):
        plan, proposal, path = self.plan()
        with self.assertRaises(ContractError):
            load_plan(
                path,
                proposal["plan_sha256"],
                {"source_commit": "a" * 40},
                bundle=self.folder / "other",
                manifest_sha256=plan["manifest_sha256"],
            )

    @unittest.skipUnless(os.name == "posix", "Linux venv symlink regression")
    def test_plan_keeps_venv_python_symlink_instead_of_selecting_base(self):
        base = self.folder / "base-python"
        base.write_text("invented interpreter, never executed")
        venv_python = self.folder / "venv/bin/python"
        venv_python.parent.mkdir(parents=True)
        venv_python.symlink_to(base)
        plan, _, _ = self.plan(venv_python)
        self.assertEqual(plan["python"], str(venv_python))
        self.assertNotEqual(plan["python"], str(venv_python.resolve()))

    def test_source_packaging_uses_git_bytes_and_never_includes_license(self):
        repo = self.folder / "repository"
        repo.mkdir()
        subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
        for key, value in (
            ("commit.gpgsign", "false"),
            ("core.autocrlf", "false"),
            ("user.name", "Offline Test"),
            ("user.email", "test@example.invalid"),
        ):
            subprocess.run(["git", "config", key, value], cwd=repo, check=True)
        for name in ("src/cfl_gnn/__init__.py", "scripts/mvp3/qualify_production.py"):
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# fixture\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "fixture"], cwd=repo, check=True
        )
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        license_file = self.folder / "fake.lic"
        license_file.write_text("invented-private-sentinel")
        ci = self.folder / "ci.json"
        durable_json(
            ci,
            {
                "head": head,
                "jobs": [
                    {"status": "completed", "conclusion": "success", "id": i}
                    for i in range(9)
                ],
            },
        )
        result = prepare(repo, self.folder / "packed", head, ci, license_file)
        with tarfile.open(
            self.folder / "packed/s2-production-qualification.tar"
        ) as archive:
            self.assertFalse(
                any(".lic" in name or "secrets" in name for name in archive.getnames())
            )
            if sys.version_info >= (3, 12):
                archive.extractall(self.folder / "extracted", filter="data")
            else:
                archive.extractall(self.folder / "extracted")
        verify_bundle(self.folder / "extracted", result["manifest_sha256"])

    def test_probe_is_one_real_API_double_call_after_hardware_gate(self):
        plan, _, _ = self.plan()
        result, model, env = self.run_fake_probe(plan, "intel-256", "42")
        self.assertEqual(model.calls, 1)
        self.assertEqual(result["parameters"]["effective"]["Threads"], 0)
        self.assertEqual(result["root_audit"]["status"], "qualified")
        self.assertTrue(env.closed and model.closed)

    def run_fake_probe(self, plan, profile, job):
        folder = Path(plan["slots"][profile]["output"])
        folder.mkdir()
        durable_json(
            folder / "worker-admission.json",
            {
                "source_commit": "a" * 40,
                "plan_identity_sha256": digest(plan),
                "job_id": job,
            },
        )
        api, model, env = fake_api()
        model.constraints[0].RHS = 10.5
        model.solution = [1.0] * 10 + [0.5] + [0.0] * 9
        original = model.optimize

        def optimize(observer):
            model.values["MSG_STRING"] = (
                "Thread count: 32 physical cores, 64 logical processors, using up to 32 threads\n"
            )
            observer(model, "MESSAGE")
            original(observer)

        model.optimize = optimize
        with (
            patch(
                "cfl_gnn.mvp3.production.worker.os.environ",
                {**os.environ, "SLURM_JOB_ID": job},
            ),
            patch(
                "cfl_gnn.mvp3.production.worker.admission",
                return_value={"allocation_qualified": True},
            ),
            patch("cfl_gnn.mvp3.production.worker.cgroup_memory", return_value={}),
            patch("cfl_gnn.mvp3.production.worker.task_ticks", return_value={}),
        ):
            result = probe(plan, profile, "a" * 40, api=api)
        return result, model, env

    def returned_plan(self):
        plan, _, _ = self.plan()
        accounting = {}
        for profile, job, mem in (("intel-256", "42", 192), ("intel-512", "43", 384)):
            self.run_fake_probe(plan, profile, job)
            folder = Path(plan["slots"][profile]["output"])
            durable_json(
                folder / "allocation.json",
                {
                    "allocation_qualified": True,
                    "checks": {"invented_offline_gate": True},
                },
            )
            (folder / "native.stdout.log").write_text(
                "Thread count was 1 (of 64 available processors)\n"
            )
            durable_json(
                folder / "worker-terminal.json",
                {
                    "source_commit": plan["source_commit"],
                    "plan_identity_sha256": digest(plan),
                    "profile": profile,
                    "job_id": job,
                    "child_returncode": 0,
                    "guard": None,
                    "stdout_sha256": file_sha256(folder / "native.stdout.log"),
                    "admission_receipts": {
                        name: file_sha256(folder / name)
                        for name in ("allocation.json", "worker-admission.json")
                    },
                },
            )
            accounting[job] = (
                f"{job}|COMPLETED|0:0|2|cpu=64,mem={mem}G,node=1|{plan['slots'][profile]['node']}|123K\n"
            )
        return plan, lambda args: accounting[args[args.index("--jobs") + 1]]

    def test_collection_replays_both_roots_but_never_releases_S2(self):
        plan, runner = self.returned_plan()
        report = collect(plan, self.folder / "collection", runner)
        self.assertTrue(report["two_production_envelopes_technically_qualified"])
        self.assertFalse(report["scientific_S2_released"])
        self.assertFalse(report["real_CFL_memory_or_performance_qualified"])
        self.assertEqual(
            report["profiles"]["intel-256"]["native_actual_thread_messages"], [1]
        )

    def test_collection_rejects_scheduler_resource_drift(self):
        plan, runner = self.returned_plan()
        report = collect(
            plan,
            self.folder / "collection",
            lambda args: runner(args).replace("cpu=64", "cpu=32"),
        )
        self.assertFalse(report["two_production_envelopes_technically_qualified"])

    def test_collection_keeps_missing_accounting_ineligible_without_retry(self):
        plan, _ = self.returned_plan()
        report = collect(plan, self.folder / "collection", lambda args: "")
        self.assertFalse(report["automatic_retry"])
        self.assertTrue(
            all(
                not row["qualified"] and row["missing_reason"]
                for row in report["profiles"].values()
            )
        )

    def test_collection_rejects_altered_admission_receipt(self):
        plan, runner = self.returned_plan()
        folder = Path(plan["slots"]["intel-256"]["output"])
        (folder / "allocation.json").write_text("{}")
        report = collect(plan, self.folder / "collection", runner)
        self.assertFalse(report["profiles"]["intel-256"]["qualified"])

    def test_failed_allocation_never_starts_native_environment(self):
        plan, _, _ = self.plan()
        api, model, env = fake_api()
        with (
            patch(
                "cfl_gnn.mvp3.production.worker.admission",
                return_value={"allocation_qualified": False},
            ),
            self.assertRaises(ContractError),
        ):
            probe(plan, "intel-256", "a" * 40, api=api)
        self.assertFalse(env.started)
        self.assertEqual(model.calls, 0)


if __name__ == "__main__":
    unittest.main()
