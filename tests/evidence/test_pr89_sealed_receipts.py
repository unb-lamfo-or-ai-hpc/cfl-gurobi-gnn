"""Byte identities and metric boundaries for the three immutable PR89 returns."""

import csv
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = {
    "partial-20261031": (
        "d8f8e3fe7b95ad688cc6ab8e6218bdf133b16df88e28f39882dcb822426eec2b",
        50,
    ),
    "partial-20261101": (
        "67916124db1d6b422cfc5a01399863b9de7e430902e9a6e4521bfac041b7d6fb",
        54,
    ),
    "final-20261101": (
        "6fb1728509eb6a140618882f78aa87300367db549c49adbf42393652f71c6941",
        60,
    ),
}


def verify(directory, expected):
    raw = (directory / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("manifest_bytes")
    manifest = json.loads(raw)
    for name, digest in manifest["files"].items():
        if (
            Path(name).name != name
            or hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest
        ):
            raise ValueError("member_bytes:" + name)
    return manifest


def rows(path):
    return list(
        csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"), newline=""))
    )


class SealedPr89Tests(unittest.TestCase):
    def test_three_original_manifest_and_member_byte_seals(self):
        for name, (digest, count) in SNAPSHOTS.items():
            directory = ROOT / "docs/evidence/pr89" / name
            value = verify(directory, digest)
            self.assertEqual(len(rows(directory / "cells.csv")), count)
            self.assertIs(value["scientific_reporting_eligible"], False)
            self.assertEqual(
                value["source_commit"], "9ab7823c6886d19e9ec865141a1cd35b3c3c16e5"
            )

    def test_prior_rows_are_preserved_in_complete_matrix(self):
        base = ROOT / "docs/evidence/pr89"
        complete = rows(base / "final-20261101/cells.csv")
        for name, (_, count) in SNAPSHOTS.items():
            self.assertEqual(rows(base / name / "cells.csv"), complete[:count])
        self.assertEqual(
            [r["job_id"] for r in complete], [str(j) for j in range(3675, 3735)]
        )
        self.assertEqual(
            len({(r["parent"], r["threads"], r["method"]) for r in complete}), 60
        )
        censored = [r for r in complete if r["status"] == "9"]
        self.assertEqual(len(censored), 13)
        self.assertEqual({r["alias"] for r in censored}, {"M7"})
        self.assertTrue(
            all(r["scientific_reporting_eligible"] == "False" for r in complete)
        )

    def test_all_metric_dispositions_keep_scientific_limits(self):
        value = rows(ROOT / "docs/evidence/pr89/final-20261101/disposition.csv")
        self.assertEqual(len(value), 60)
        self.assertEqual(sum(r["terminal_censoring"] == "True" for r in value), 13)
        for row in value:
            self.assertEqual(row["certified_speedup"], "False")
            self.assertEqual(row["exact_global_optimality"], "not_proven")
            self.assertEqual(row["raw_scientific_reporting_eligible"], "False")

    def test_newline_conversion_is_not_a_valid_seal(self):
        raw = (ROOT / "docs/evidence/pr89/final-20261101/manifest.json").read_bytes()
        self.assertNotIn(b"\r\n", raw)
        converted = raw.replace(b"\n", b"\r\n")
        self.assertEqual(
            hashlib.sha256(converted).hexdigest(),
            "b515050287280d58666fed66c8c9ce47957db4d1e7a7f29dbd40c8570a95bc01",
        )
        self.assertNotEqual(
            hashlib.sha256(converted).hexdigest(), SNAPSHOTS["final-20261101"][0]
        )

    def test_changed_cell_bytes_fail_without_relaxing_integrity(self):
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "receipt"
            shutil.copytree(ROOT / "docs/evidence/pr89/final-20261101", copied)
            with (copied / "cells.csv").open("ab") as stream:
                stream.write(b"\n")
            with self.assertRaisesRegex(ValueError, "member_bytes:cells.csv"):
                verify(copied, SNAPSHOTS["final-20261101"][0])


if __name__ == "__main__":
    unittest.main()
