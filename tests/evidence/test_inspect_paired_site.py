"""Regression coverage for failed held submissions and current-site inventory."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import inspect_paired_site as inventory  # noqa: E402


class SiteInventoryTests(unittest.TestCase):
    def test_two_nodes_are_reported_as_a_difference_not_accepted(self):
        profile = {
            **inventory.EXPECTED,
            "JobId": "3481",
            "NumNodes": "2",
            "NumCPUs": "16",
            "MinMemoryNode": "64G",
            "TRES": {"cpu": "16", "mem": "64G", "node": "2"},
        }
        differences = inventory.held_differences(profile, "3481")
        self.assertEqual(
            {row["field"] for row in differences}, {"NumNodes", "TRES.node"}
        )
        self.assertEqual(differences[0]["observed"], "2")

    def test_allowlist_excludes_accounts_commands_licenses_and_duplicate_fields(self):
        value = inventory.fields(
            "JobId=3481 NumNodes=1 NumNodes=2 Account=PRIVATE Command=/secret "
            "TRES=cpu=16,node=2,license/private=1 Comment=SECRET",
            inventory.JOB_FIELDS,
        )
        self.assertEqual(
            value,
            {
                "JobId": "3481",
                "NumNodes": "duplicate_field",
                "TRES": {"cpu": "16", "node": "2"},
            },
        )
        self.assertNotIn("SECRET", str(value))

    def test_physical_cores_are_distinct_socket_core_pairs(self):
        value = inventory.topology(
            "# CPU,Core,Socket,Online\n0,0,0,Y\n1,0,0,Y\n2,0,1,Y\n3,1,1,N\n"
        )
        self.assertEqual(value["online_logical_cpus"], 3)
        self.assertEqual(value["online_physical_cores"], 2)
        self.assertEqual(value["online_sockets"], 2)

    def test_inventory_is_read_only_and_expired_job_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            state = directory / "operator-state/easy"
            state.mkdir(parents=True)
            (state / "submission.json").write_text('{"job_id":"3481"}')
            before = sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))

            def query(args):
                if args[:3] == ["scontrol", "show", "job"]:
                    return 1, ""
                if args[0] == "sacct":
                    return (
                        0,
                        "3481|CANCELLED by 123|0:0|0|Unknown|2026-10-06T12:00:00|2|1|16|16|64G|\n",
                    )
                return 0, ""

            with patch.object(inventory, "query", side_effect=query) as mock:
                result = inventory.inspect(directory, "3481")
            self.assertEqual(mock.call_count, 6)
            self.assertTrue(
                all(
                    call.args[0][0] in {"scontrol", "sacct", "lscpu"}
                    for call in mock.call_args_list
                )
            )
            self.assertEqual(result["query_results"]["job"]["returncode"], 1)
            self.assertIsNone(result["job_current_differences_from_held_contract"])
            self.assertEqual(result["accounting"][0]["State"], "CANCELLED")
            self.assertEqual(
                result["workflow_markers"]["released.json"]["state"], "absent"
            )
            self.assertNotIn("exact_optimization_call_count", result)
            self.assertEqual(
                before,
                sorted(str(p.relative_to(directory)) for p in directory.rglob("*")),
            )

    def test_timeout_does_not_expose_command_stderr_or_retry(self):
        import subprocess

        with patch.object(
            inventory.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("PRIVATE", 20),
        ) as run:
            self.assertEqual(inventory.query(["scontrol", "show", "config"]), (-1, ""))
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
