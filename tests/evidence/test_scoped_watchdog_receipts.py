"""Test the frozen stop mechanism plus the new sanitized diagnostic envelope."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import paired_memory_runtime_v2 as memory  # noqa: E402


class WatchdogTests(unittest.TestCase):
    def simulate(self, error):
        gate = Mock(sample=Mock(side_effect=[1, error]))
        process = Mock(pid=12345, returncode=-15)
        process.poll.return_value = None
        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(memory.watchdog.subprocess, "Popen", return_value=process),
            patch.object(memory.watchdog, "stop_owned") as stop,
            patch.object(
                memory.watchdog.os,
                "killpg",
                side_effect=ProcessLookupError,
                create=True,
            ),
        ):
            result = memory.supervise(["synthetic"], Path(temp) / "console", 3780, gate)
            stop.assert_called_once_with(process)
        return result

    def test_qualified_diagnostic_survives_supervisor(self):
        detail = memory.qualified.failure(
            "usage_read_or_parse", FileNotFoundError(2, "PRIVATE"), 2
        )
        result = self.simulate(memory.qualified.MemoryObservationError(detail))
        self.assertEqual(result["guard_stop"], "memory_observation_lost")
        self.assertEqual(result["memory_failure_diagnostic"], detail)
        self.assertEqual(result["child_exit_code"], -15)
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_unexpected_exception_sanitized(self):
        result = self.simulate(RuntimeError("LICENSE-SECRET"))
        self.assertEqual(
            result["memory_failure_diagnostic"]["stage"], "supervisor_sample"
        )
        self.assertEqual(result["memory_failure_diagnostic"]["exception_type"], "other")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_no_diagnostic_without_observation_loss(self):
        result = {"guard_stop": None}
        with patch.object(memory.watchdog, "supervise", return_value=result):
            value = memory.supervise([], None, 1, Mock())
        self.assertIsNone(value["memory_failure_diagnostic"])

    def test_diagnostic_schema_rejects_leaks_and_false_types(self):
        good = memory.qualified.failure("hierarchy", ValueError("PRIVATE"), 0)
        memory.validate_diagnostic(good, "memory_observation_lost")
        for key, value in (
            ("path", "private"),
            ("stage", "private"),
            ("errno", True),
            ("depth_from_leaf", True),
            ("depth_from_leaf", 16),
            ("private_text_included", True),
            ("exception_type", "secret"),
        ):
            changed = copy.deepcopy(good)
            changed[key] = value
            with self.assertRaises((ValueError, TypeError)):
                memory.validate_diagnostic(changed, "memory_observation_lost")
        with self.assertRaises(ValueError):
            memory.validate_diagnostic(good, None)


if __name__ == "__main__":
    unittest.main()
