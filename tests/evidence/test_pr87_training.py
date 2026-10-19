"""PR87 offline protocol/operator tests: no torch, training, solver or Slurm."""

import copy
import json
import os
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
sys.path.insert(0, str(ROOT / "src"))
import pr87_contract as c  # noqa: E402
import pr87_workflow as w  # noqa: E402

from cfl_gnn.training.matched_gpu import epoch_batches, schedule_hash  # noqa: E402


def profile(job="123", world=1):
    return (
        f"JobId={job} JobState=PENDING NumNodes=1-1 NumTasks=1 CPUs/Task={4 * world} "
        f"MinMemoryNode=128G Requeue=0 Restarts=0 TimeLimit=12:00:00 Partition=batch "
        f"TRES=cpu={4 * world},mem=128G,node=1,gres/gpu={world}"
    )


def approval_fixture(stage, frozen, plan_sha):
    # Synthetic decision for offline tests only; never authorizes a real job.
    value = {
        "package_id": "pr87_gpu_seed42_authorization_v2",
        "execution_authorized": True,
        "plan_sha256": plan_sha,
        "bindings_sha256": c.sha((stage / "private_bindings.json").read_bytes()),
        "source_commit": frozen["source_commit"],
        "budget": frozen["protocol"]["budget"],
        "seed": 42,
        "decision_reference": "OFFLINE_SYNTHETIC_FIXTURE_ONLY",
        "approved_at_utc": "2026-10-19T00:00:00Z",
        "automatic_retry": False,
    }
    path = stage / "fixture_authorization.json"
    return path, c.write(path, value)


class PR87Tests(unittest.TestCase):
    def complete_result(self, frozen, index):
        row = {
            "tp": 1,
            "tn": 0,
            "fp": 0,
            "fn": 0,
            "n_targets": 1,
            "n_positive": 1,
            "precision": 1.0,
            "recall": 1.0,
            "f1_score": 1.0,
            "pr_auc": 1.0,
        }
        parents = [r["parent"] for r in frozen["records"] if r["role"] == "test"]
        rows = [{"parent": p, **row} for p in parents]
        return {
            "state": "complete",
            "seed": 42,
            "world_size": index * 3 + 1,
            "source_commit": frozen["source_commit"],
            "plan_sha256": c.sha(
                (json.dumps(frozen, sort_keys=True, indent=2) + "\n").encode()
            ),
            "epochs_completed": 100,
            "optimizer_updates": 3400,
            "global_graph_draws": 13600,
            "validation_parents": 10,
            "test_parents": 10,
            "optimization_runs_added": 0,
            "scientific_reporting_eligible": False,
            **{
                k: "a" * 64
                for k in (
                    "initial_state_sha256",
                    "schedule_sha256",
                    "selected_state_sha256",
                    "terminal_state_sha256",
                    "unfitted_state_sha256",
                )
            },
            "training_loop_seconds": 100,
            "training_validation_checkpoint_seconds": 150,
            "process_wall_seconds": 200,
            "history": [
                {
                    "epoch": e,
                    "optimizer_updates": 34,
                    "global_draws": 136,
                    "train_loss": 1,
                    "validation_loss": 1,
                }
                for e in range(1, 101)
            ],
            "test": {"selected": rows, "terminal": rows},
            "test_pooled": {
                "selected": {**row, "tp": 10, "n_targets": 10, "n_positive": 10},
                "terminal": {**row, "tp": 10, "n_targets": 10, "n_positive": 10},
            },
            "selected_threshold": 0.5,
            "terminal_threshold": 0.5,
            "best_epoch": 1,
            "pos_weight": 2.0,
        }

    def test_complete_result_rejects_changed_work_counts_and_metrics(self):
        frozen = c.plan("a" * 40)
        value = self.complete_result(frozen, 0)
        self.assertEqual(c.validate_result(value, frozen, 0), value)
        for key, new in (
            ("global_graph_draws", 13604),
            ("optimizer_updates", 13600),
            ("seed", 43),
            ("selected_threshold", float("nan")),
        ):
            changed = copy.deepcopy(value)
            changed[key] = new
            with self.assertRaises(ValueError):
                c.validate_result(changed, frozen, 0)
        changed = copy.deepcopy(value)
        changed["test"]["selected"][0]["f1_score"] = 0.5
        with self.assertRaises(ValueError):
            c.validate_result(changed, frozen, 0)

    def test_128_memory_parameterization_keeps_original_policy(self):
        from types import SimpleNamespace

        import paired_memory_guard as historical
        import pr87_resources as resources

        old = dict(historical.POLICY)

        class ExistingGate:
            def read_limits(self):
                return (2**63 - 4096, 128 * 1024**3)

            def sample(self):
                return 1024

        candidate = SimpleNamespace(
            MemoryGate=ExistingGate,
            original=SimpleNamespace(bounded_text=lambda _: "membership"),
            prior=SimpleNamespace(
                resolve_cgroup=lambda *args: (
                    "v1",
                    Path("/sys/fs/cgroup/job_123/step"),
                    Path("memory.limit_in_bytes"),
                    Path("memory.usage_in_bytes"),
                )
            ),
            job_chain=lambda _: (Path("leaf"), Path("job_123")),
        )
        # job_chain receives leaf and job, as in the reviewed inherited gate.
        candidate.job_chain = lambda *args: (Path("leaf"), Path("job_123"))
        with patch.object(resources.scoped, "load_candidate", return_value=candidate):
            gate = resources.gate_class()("123")
            self.assertEqual(gate.job_limit, 128 * 1024**3)
            self.assertEqual(gate.sample(), 1024)
        self.assertEqual(historical.POLICY, old)

    def test_frozen_work_and_budget(self):
        plan = c.plan("a" * 40)
        config = plan["protocol"]
        self.assertEqual(config["seeds"], [42])
        self.assertEqual(config["pair_order"], [[42, 1], [42, 4]])
        self.assertEqual(config["budget"]["maximum_training_runs"], 2)
        self.assertEqual(config["budget"]["gpu_hours"], 12 * 5)
        self.assertEqual(config["budget"]["physical_core_reserved_hours"], 12 * 20)
        self.assertFalse(plan["resource_budget_approved"])
        self.assertFalse(config["automatic_retry"])
        self.assertFalse(config["early_stopping"])
        self.assertEqual(
            Counter(r["role"] for r in plan["records"]),
            {"train": 34, "validation": 10, "test": 10},
        )
        self.assertTrue(
            all(r["objective_sense"] == "MINIMIZE" for r in plan["records"])
        )

    def test_global_schedule_and_no_padding(self):
        parents = [r["parent"] for r in c.records() if r["role"] == "train"]
        for epoch in range(100):
            batches = epoch_batches(parents, 42, epoch)
            self.assertEqual(len(batches), 34)
            serial = [parent for batch in batches for parent in batch]
            ddp = [[batch[rank] for batch in batches] for rank in range(4)]
            self.assertEqual([ddp[r][i] for i in range(34) for r in range(4)], serial)
            self.assertEqual(Counter(serial), Counter({p: 4 for p in parents}))
        self.assertEqual(schedule_hash(parents, 42), schedule_hash(parents, 42))

    def test_no_added_seed_or_population(self):
        parents = [str(i) for i in range(34)]
        for seed, epoch, rows in [
            (43, 0, parents),
            (42, 100, parents),
            (42, 0, parents[:33]),
        ]:
            with self.assertRaises(ValueError):
                epoch_batches(rows, seed, epoch)

    def test_profile_single_node_and_gpu(self):
        self.assertEqual(w.profile(profile(), "123", 1)["NumNodes"], "1-1")
        self.assertEqual(w.profile(profile(world=4), "123", 4)["CPUs/Task"], "16")
        for old, new in [
            ("NumNodes=1-1", "NumNodes=2"),
            ("gres/gpu=1", "gres/gpu=8"),
            ("Requeue=0", "Requeue=1"),
            ("MinMemoryNode=128G", "MinMemoryNode=64G"),
            ("CPUs/Task=4", "CPUs/Task=16"),
            ("TimeLimit=12:00:00", "TimeLimit=24:00:00"),
        ]:
            with self.assertRaises(ValueError):
                w.profile(profile().replace(old, new), "123", 1)

    def test_two_jobs_only_after_both_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve()
            frozen = c.plan("a" * 40)
            plan_sha = c.write(stage / "plan.json", frozen)
            c.write(stage / "private_bindings.json", {})
            auth, auth_sha = approval_fixture(stage, frozen, plan_sha)
            calls = []

            def fake(args):
                calls.append(args)
                if args[0] == "sbatch":
                    return (
                        "123\n"
                        if not (stage / "submission-0.json").exists()
                        else "124\n"
                    )
                if args[:3] == ["scontrol", "show", "job"]:
                    return profile(args[-1], 1 if args[-1] == "123" else 4)
                return ""

            with (
                patch.object(w, "checked", return_value=frozen),
                patch.object(w, "command", side_effect=fake),
            ):
                w.submit(stage, plan_sha, auth, auth_sha)
                self.assertEqual(
                    [args[-1] for args in calls if args[:2] == ["scontrol", "release"]],
                    ["123", "124"],
                )
                submits = [args for args in calls if args[0] == "sbatch"]
                self.assertEqual(len(submits), 2)
                self.assertIn("--dependency=afterok:123", submits[1])
                self.assertTrue(
                    all("--nodes=1-1" in a and "--no-requeue" in a for a in submits)
                )
                previous = len(calls)
                with self.assertRaises(FileExistsError):
                    w.submit(stage, plan_sha, auth, auth_sha)
                self.assertEqual(previous, len(calls))

    def test_partial_submission_never_repeats_or_releases(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve()
            frozen = c.plan("a" * 40)
            plan_sha = c.write(stage / "plan.json", frozen)
            c.write(stage / "private_bindings.json", {})
            auth, auth_sha = approval_fixture(stage, frozen, plan_sha)
            calls = []

            def fake(args):
                calls.append(args)
                if args[0] == "sbatch":
                    return "123\n"
                return profile().replace("NumNodes=1-1", "NumNodes=2")

            with (
                patch.object(w, "checked", return_value=frozen),
                patch.object(w, "command", side_effect=fake),
            ):
                with self.assertRaises(ValueError):
                    w.submit(stage, plan_sha, auth, auth_sha)
                self.assertTrue((stage / "submission.claim").is_file())
                self.assertTrue((stage / "submission-0.json").is_file())
                self.assertFalse(any(a[:2] == ["scontrol", "release"] for a in calls))

    def test_status_filters_accounting_rows_and_is_one_query(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve()
            c.write(stage / "jobs.json", {"job_ids": ["123", "124"]})
            text = "123|COMPLETED|0:0|90|00:01:00|8|128G|\n123.batch|COMPLETED|0:0|90|00:01:00|8||1M\n124|PENDING|0:0|0|00:00:00|16|128G|\n"
            with (
                patch.object(w, "checked"),
                patch.object(w, "command", return_value=text) as command,
            ):
                value = w.status(stage)
                self.assertFalse(value["terminal"])
                self.assertEqual(value["jobs"][0]["job_id"], "123")
                self.assertEqual(len(value["jobs"][0]["rows"]), 2)
                command.assert_called_once()

    def test_bad_approval_never_submits(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve()
            c.write(stage / "plan.json", {})
            with (
                patch.object(w, "checked", return_value={}),
                patch.object(w, "command") as command,
            ):
                with self.assertRaises(ValueError):
                    w.submit(stage, "b" * 64)
                command.assert_not_called()
                self.assertFalse((stage / "submission.claim").exists())

    def test_plain_import_never_imports_torch(self):
        # The separate subprocess avoids unrelated tests' optional modules.
        import subprocess

        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        code = "import sys; import cfl_gnn.training.matched_gpu; assert 'torch' not in sys.modules"
        subprocess.run([sys.executable, "-c", code], env=env, check=True, timeout=30)

    def test_plan_hash_alone_is_not_authorization(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve()
            frozen = c.plan("a" * 40)
            plan_sha = c.write(stage / "plan.json", frozen)
            with (
                patch.object(w, "checked", return_value=frozen),
                patch.object(w, "command") as command,
            ):
                with self.assertRaisesRegex(ValueError, "separate_gpu_execution"):
                    w.submit(stage, plan_sha)
                command.assert_not_called()
                self.assertFalse((stage / "submission.claim").exists())

    def test_false_cpu_wrong_budget_or_source_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve()
            frozen = c.plan("a" * 40)
            plan_sha = c.write(stage / "plan.json", frozen)
            c.write(stage / "private_bindings.json", {})
            path, _ = approval_fixture(stage, frozen, plan_sha)
            value = c.read(path)
            for key, bad in (
                ("execution_authorized", False),
                ("package_id", "pr88_cpu_medium12h_seed42_proposal_v1"),
                ("source_commit", "b" * 40),
                ("budget", {}),
                ("plan_sha256", "b" * 64),
                ("bindings_sha256", "b" * 64),
            ):
                changed = copy.deepcopy(value)
                changed[key] = bad
                with self.assertRaises(ValueError):
                    c.validate_authorization(
                        changed, frozen, plan_sha, value["bindings_sha256"]
                    )

    def test_authorization_hash_before_claim_or_scheduler(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve()
            frozen = c.plan("a" * 40)
            plan_sha = c.write(stage / "plan.json", frozen)
            c.write(stage / "private_bindings.json", {})
            auth, _ = approval_fixture(stage, frozen, plan_sha)
            with (
                patch.object(w, "checked", return_value=frozen),
                patch.object(w, "command") as command,
            ):
                with self.assertRaisesRegex(ValueError, "authorization_file_hash"):
                    w.submit(stage, plan_sha, auth, "b" * 64)
                command.assert_not_called()
                self.assertFalse((stage / "submission.claim").exists())

    def test_independent_review_rechecks_authorization_and_identity(self):
        frozen = c.plan("a" * 40)
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp).resolve()
            plan_sha = c.write(stage / "plan.json", frozen)
            c.write(stage / "private_bindings.json", {})
            auth, auth_sha = approval_fixture(stage, frozen, plan_sha)
            decision = c.read(auth)
            value = {
                "protocol_id": "pr87_matched_parent_training_v2",
                "plan": frozen,
                "raw_logs_included": False,
                "private_paths_included": False,
                "authorization_json": auth.read_bytes().decode(),
                "approval": {
                    "authorization_sha256": auth_sha,
                    "explicitly_approved": True,
                    "plan_sha256": plan_sha,
                    "bindings_sha256": decision["bindings_sha256"],
                    "budget": decision["budget"],
                    "seed": 42,
                    "automatic_retry": False,
                    "decision_reference": decision["decision_reference"],
                },
                "results": [self.complete_result(frozen, i) for i in (0, 1)],
                "supervisors": [{"child_exit_code": 0, "guard_stop": None}] * 2,
                "accounting": {
                    "terminal": True,
                    "jobs": [
                        {
                            "job_id": str(i),
                            "state": "COMPLETED",
                            "rows": [{"JobID": str(i), "ExitCode": "0:0"}],
                        }
                        for i in (0, 1)
                    ],
                },
            }
            for i, result in enumerate(value["results"]):
                result["job_id"] = str(i)
            self.assertEqual(w.review(value)["seed"], 42)
            changed = copy.deepcopy(value)
            changed["authorization_json"] += " "
            with self.assertRaisesRegex(ValueError, "review_authorization_hash"):
                w.review(changed)
            changed = copy.deepcopy(value)
            changed["approval"]["budget"] = {}
            with self.assertRaisesRegex(ValueError, "review_approval_scope"):
                w.review(changed)

    def test_curve_metrics_match_existing_semantics(self):
        import train_pr87 as trainer

        from cfl_gnn.evaluation.gasse_reconnected import binary_curve_rows

        y, p = [0, 1, 0, 1, 1], [0.2, 0.4, 0.4, 0.9, 0.8]
        scores = trainer.curve_score(y, p, 0.5)
        self.assertAlmostEqual(scores["pr_auc"], binary_curve_rows(y, p)[3])
        self.assertEqual(scores["tp"], 2)
        self.assertEqual(scores["fn"], 1)

    def test_failed_return_is_not_complete(self):
        value = {
            "protocol_id": "pr87_matched_parent_training_v2",
            "plan": c.plan("a" * 40),
            "results": [None, None],
            "raw_logs_included": False,
            "private_paths_included": False,
            "accounting": {"terminal": True},
        }
        with self.assertRaises((ValueError, TypeError, KeyError)):
            w.review(value)
        broken = copy.deepcopy(value)
        broken["private_paths_included"] = True
        with self.assertRaises(ValueError):
            w.review(broken)

    def test_shell_syntax(self):
        import shutil
        import subprocess

        if sys.platform == "win32":
            self.skipTest("POSIX subprocess; shell syntax also checked in CI Bash step")
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash unavailable; covered by Linux CI")
        subprocess.run(
            [bash, "-n", str(ROOT / "scripts/evidence/operate_pr87_training.sh")],
            check=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
