"""Recovery verification regressions using synthetic, unlicensed inputs."""

import csv
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import collect_class_statistics as classes
import collect_computational_ledger as ledger
import verify_pr65_recovery as recovery


def csv_bytes(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def manifests(data):
    for group, names in (("ledger", ledger.OUTPUTS), ("classes", classes.FILES)):
        data[f"{group}/SHA256SUMS.txt"] = "".join(
            f"{recovery.sha(data[f'{group}/{name}'])}  {name}\n"
            for name in sorted(names)
        ).encode()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = {name: b"{}" for name in recovery.BASE_MEMBERS}
        self.old["source_commit.txt"] = ("a" * 40 + "\n").encode()
        self.old["ledger/ledger_report.json"] = json.dumps(
            {"collector_sha256": recovery.sha(Path(ledger.__file__).read_bytes())}
        ).encode()
        manifests(self.old)
        self.data = dict(self.old)
        self.data["source_commit.txt"] = ("b" * 40 + "\n").encode()
        self.instances = []
        for c in recovery.CLASSES:
            for i in range(30):
                self.instances.append(
                    {
                        "source_instance_id": f"CFL_{c}_instance_{i}",
                        "difficulty": c,
                        "original_lp_sha256": recovery.sha(f"{c}{i}".encode()),
                        "source_file_format": "lp.gz",
                        "status": "model_attributes_observed",
                        "error_type": "",
                        "model_read_wall_seconds": 1,
                        "source_objective_sense": "MAXIMIZE",
                        "effective_objective_sense": "MINIMIZE",
                        **dict.fromkeys(classes.FIELDS, 1),
                        "variables": 5,
                        "constraints": 3,
                        "nonzeros": 6,
                        "density": 0.4,
                        "mean_variable_degree": 1.2,
                        "mean_constraint_degree": 2,
                    }
                )
        self.data["classes/class_instance_statistics.csv"] = csv_bytes(self.instances)
        self.data["classes/class_descriptive_statistics.csv"] = csv_bytes(
            classes.summarize(self.instances)
        )
        self.report = {
            "schema_version": 1,
            "expected_parents": 90,
            "observed_parents": 90,
            "missing_or_failed_parents": 0,
            "gate_status": "complete_model_read",
            "scope": "label_free_original_linear_model_attributes",
            "source_format_counts": {"lp.gz": 90},
            "source_status_counts": {"model_attributes_observed": 90},
            "source_hash_semantics": "original_stored_file_bytes_including_compression",
            "optimization_runs": 0,
            "training_runs": 0,
            "original_files_modified": False,
            "raw_inputs_copied": False,
            "scientific_reporting_eligible": False,
            "degree_distributions_and_pca_umap_computed": False,
            "collector_sha256": recovery.sha(Path(classes.__file__).read_bytes()),
        }
        self.data["classes/class_statistics_report.json"] = json.dumps(
            self.report
        ).encode()
        self.receipt = {
            "schema_version": 1,
            "scope": "class_only_recovery_reusing_unchanged_ledger",
            "ledger_source_commit": "a" * 40,
            "classes_source_commit": "b" * 40,
            "reused_ledger_report_sha256": recovery.sha(
                self.old["ledger/ledger_report.json"]
            ),
            "superseded_class_report_sha256": recovery.sha(
                self.old["classes/class_statistics_report.json"]
            ),
            "optimization_runs": 0,
            "training_runs": 0,
        }
        self.data["recovery_receipt.json"] = json.dumps(self.receipt).encode()
        manifests(self.data)

    def package(self, name, data, extra=None):
        path = self.root / name
        with tarfile.open(path, "w:gz") as archive:
            for key, value in data.items():
                member = tarfile.TarInfo(key)
                member.size = len(value)
                archive.addfile(member, io.BytesIO(value))
            if extra:
                archive.addfile(extra, io.BytesIO(b"x" * extra.size))
        return path

    def verify(self):
        first = self.package("first.tar.gz", self.old)
        recovered = self.package("recovered.tar.gz", self.data)
        return recovery.verify_recovery(
            first,
            recovered,
            recovery.sha(first.read_bytes()),
            recovery.sha(recovered.read_bytes()),
        )

    def test_complete_recovery_recomputes_summaries_without_claiming_science(self):
        result = self.verify()
        self.assertEqual(result["parent_counts"], {c: 30 for c in recovery.CLASSES})
        self.assertEqual(result["descriptive_statistic_values_recomputed"], 300)
        self.assertFalse(result["scientific_reporting_eligible"])

    def test_wrong_hash_is_rejected_before_tar_read(self):
        package = self.package("wrong.tar.gz", self.data)
        with patch.object(recovery.tarfile, "open") as opened:
            with self.assertRaisesRegex(ValueError, "package_hash_mismatch"):
                recovery.read_package(package, "0" * 64, True)
            opened.assert_not_called()

    def test_duplicate_member_is_rejected(self):
        duplicate = tarfile.TarInfo("source_commit.txt")
        package = self.package("duplicate.tar.gz", self.data, duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate_archive_member"):
            recovery.read_package(package, recovery.sha(package.read_bytes()), True)

    def test_link_is_rejected(self):
        link = tarfile.TarInfo("recovery_receipt.json")
        link.type = tarfile.SYMTYPE
        link.linkname = "other"
        data = {k: v for k, v in self.data.items() if k != link.name}
        package = self.package("linked.tar.gz", data, link)
        with self.assertRaisesRegex(ValueError, "nonregular_archive_member"):
            recovery.read_package(package, recovery.sha(package.read_bytes()), True)

    def test_changed_ledger_is_rejected_even_with_updated_manifest(self):
        self.data["ledger/missing_evidence.json"] = b'{"altered": true}'
        manifests(self.data)
        with self.assertRaisesRegex(ValueError, "reused_ledger_changed"):
            self.verify()

    def test_wrong_provenance_is_rejected(self):
        self.receipt["classes_source_commit"] = "c" * 40
        self.data["recovery_receipt.json"] = json.dumps(self.receipt).encode()
        with self.assertRaisesRegex(ValueError, "recovery_provenance_mismatch"):
            self.verify()

    def test_tampered_member_does_not_regenerate_expected_hashes(self):
        self.data["classes/class_instance_statistics.csv"] += b"changed"
        with self.assertRaisesRegex(ValueError, "member_hash_mismatch"):
            self.verify()

    def test_duplicate_parent_is_rejected(self):
        self.instances[1] = dict(self.instances[0])
        self.data["classes/class_instance_statistics.csv"] = csv_bytes(self.instances)
        manifests(self.data)
        with self.assertRaisesRegex(ValueError, "incorrect_parent_ids"):
            self.verify()

    def test_inconsistent_matrix_feature_is_rejected(self):
        self.instances[0]["density"] = 0.3
        self.data["classes/class_instance_statistics.csv"] = csv_bytes(self.instances)
        manifests(self.data)
        with self.assertRaisesRegex(ValueError, "matrix_derived_feature_mismatch"):
            self.verify()

    def test_changed_summary_is_rejected(self):
        summaries = classes.summarize(self.instances)
        summaries[0]["mean"] = 6
        self.data["classes/class_descriptive_statistics.csv"] = csv_bytes(summaries)
        manifests(self.data)
        with self.assertRaisesRegex(ValueError, "descriptive_summary_mismatch"):
            self.verify()

    def test_nonfinite_value_is_rejected(self):
        self.instances[0]["density"] = "NaN"
        self.data["classes/class_instance_statistics.csv"] = csv_bytes(self.instances)
        manifests(self.data)
        with self.assertRaisesRegex(ValueError, "invalid_structural_value"):
            self.verify()

    def test_private_marker_is_rejected(self):
        self.data["source_commit.txt"] = b"/raid/private/source"
        with self.assertRaisesRegex(ValueError, "private_text_marker"):
            self.verify()

    def test_duplicate_and_nonfinite_json_are_rejected(self):
        for value in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                recovery.load_json(value)

    def test_collector_source_mismatch_is_rejected(self):
        self.report["collector_sha256"] = "0" * 64
        self.data["classes/class_statistics_report.json"] = json.dumps(
            self.report
        ).encode()
        manifests(self.data)
        with self.assertRaisesRegex(ValueError, "collector_source_mismatch"):
            self.verify()

    def test_incomplete_report_cannot_qualify_complete_rows(self):
        self.report["observed_parents"] = 0
        self.data["classes/class_statistics_report.json"] = json.dumps(
            self.report
        ).encode()
        manifests(self.data)
        with self.assertRaisesRegex(ValueError, "class_report_mismatch"):
            self.verify()

    def test_public_history_preserves_failed_attempt_and_unknown_totals(self):
        docs = Path(__file__).resolve().parents[2] / "docs/evidence/pr65"
        first = recovery.load_json(
            (docs / "first_collection_verification.json").read_bytes()
        )
        received = recovery.load_json(
            (docs / "recovered_collection_verification.json").read_bytes()
        )
        summary = recovery.load_json(
            (docs / "structural_class_summary.json").read_bytes()
        )
        self.assertEqual(first["classes"]["observed_parents"], 0)
        self.assertEqual(received["classes"]["observed_parents"], 90)
        self.assertEqual(received["package_sha256"], recovery.RECOVERY_SHA256)
        self.assertEqual(first["package_sha256"], recovery.FIRST_SHA256)
        self.assertIsNone(received["ledger"]["complete_unique_feasible_incumbents"])
        self.assertFalse(received["ledger"]["historical_compute_cost_complete"])
        self.assertFalse(received["scientific_reporting_eligible"])
        self.assertEqual(
            summary["source_csv_sha256"],
            received["class_artifact_sha256"]["class_instance_statistics.csv"],
        )
        for c in recovery.CLASSES:
            row = summary["classes"][c]
            self.assertEqual(row["parents"], 30)
            self.assertAlmostEqual(
                row["density"],
                row["nonzeros"] / (row["variables"] * row["constraints"]),
            )

    def test_optimized_python_cannot_bypass_hash_check(self):
        code = "import verify_pr65_recovery as r; r.require(False, 'not_bypassed')"
        result = subprocess.run(
            [sys.executable, "-O", "-c", code],
            cwd=Path(recovery.__file__).parent,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(
            "not_bypassed" in result.stderr
            or "requires Python assertion checks enabled" in result.stderr
        )
