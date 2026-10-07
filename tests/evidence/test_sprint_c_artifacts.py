"""Selected graph/label byte audits remain distinct from training admission."""

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/evidence"
sys.path.insert(0, str(SCRIPTS))
import audit_sprint_c_inputs as metadata  # noqa: E402
import verify_sprint_c_artifacts as audit  # noqa: E402


class ArtifactTests(unittest.TestCase):
    def test_preserved_installed_receipt_and_selected_identities(self):
        archive = SCRIPTS.parents[1] / "docs/evidence/pr80-inputs-receipt.zip"
        with zipfile.ZipFile(archive) as stream:
            self.assertEqual(stream.namelist(), ["inputs.json"])
            raw = stream.read("inputs.json")
        self.assertEqual(metadata.digest(raw), audit.SOURCE_RECEIPT)
        receipt = metadata.strict_json(raw)
        self.assertEqual(len(receipt["plans"]), 17)
        self.assertEqual(len({p["sha256"] for p in receipt["plans"]}), 13)
        self.assertFalse(receipt["training_admitted"])
        for sha, _, counts in audit.SELECTION.values():
            copies = [p for p in receipt["plans"] if p["sha256"] == sha]
            self.assertTrue(copies)
            self.assertTrue(all(p["partition_counts"] == counts for p in copies))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "data"
        self.graph_root = self.root / "bipartite_graphs" / "old"
        self.graph_root.mkdir(parents=True)
        self.labels = self.root / "analysis" / "campaign" / "labels"
        self.labels.mkdir(parents=True)
        self.models = self.root / "models"
        self.models.mkdir()
        records = []
        for i, role in enumerate(("test", "validation", "train")):
            parent = f"CFL_easy_instance_{i}"
            row = {
                "sample_id": parent,
                "source_instance_id": parent,
                "parent_instance_id": parent,
                "role": role,
                "fold": i,
                "sampling_strategy": "original",
                "graph_authority": "gurobi",
                "label_solver": "gurobi",
                "mip_sha256": str(i + 1) * 64,
                "label_contract_sha256": "b" * 64,
                "label_mip_gap_relative": 0.01,
                "label_run_relative_path": "labels",
                "label_file_name": f"{i}.json.gz",
            }
            for kind in ("graph", "root", "label"):
                raw = f"never deserialize {kind} {i}".encode()
                path = (
                    self.labels / row["label_file_name"]
                    if kind == "label"
                    else self.graph_root / f"{kind}-{i}.bin"
                )
                path.write_bytes(raw)
                row[f"{kind}_sha256"] = metadata.digest(raw)
                if kind != "label":
                    row[f"{kind}_relative_path"] = path.name
            records.append(row)
        manifest = b"".join(metadata.canonical(r) + b"\n" for r in records)
        (self.graph_root / "confirmation_graph_manifest.jsonl").write_bytes(manifest)
        report = {
            "gate_status": "passed",
            "manifest": {
                "relative_path": "confirmation_graph_manifest.jsonl",
                "sha256": metadata.digest(manifest),
            },
        }
        raw_report = metadata.canonical(report)
        self.report_path = self.graph_root / "confirmation_graph_report.json"
        self.report_path.write_bytes(raw_report)
        self.plan = {
            "schema_version": 1,
            "dataset_variant": "easy_only_medium_transfer_v1",
            "graph_report_sha256": metadata.digest(raw_report),
            "records": records,
            "partition_counts": dict.fromkeys(metadata.ROLES, 1),
        }
        self.refresh_plan()

    def refresh_plan(self):
        self.plan["contract_sha256"] = metadata.digest(
            metadata.canonical(
                {k: v for k, v in self.plan.items() if k not in metadata.IGNORED}
            )
        )
        raw = metadata.canonical(self.plan)
        (self.models / "gasse_training_plan.json").write_bytes(raw)
        self.selection = {
            "easy": (
                metadata.digest(raw),
                self.plan["dataset_variant"],
                dict.fromkeys(metadata.ROLES, 1),
            )
        }

    def collect(self, **kwargs):
        return audit.collect(self.root, selection=self.selection, **kwargs)

    def test_selected_bytes_not_training_admission(self):
        result = self.collect()
        self.assertTrue(result["cohorts"]["easy"]["selected_artifact_bytes_verified"])
        self.assertEqual(len(result["cohorts"]["easy"]["parents"]), 3)
        self.assertFalse(result["training_admitted"])
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_changed_graph(self):
        (self.graph_root / "graph-0.bin").write_bytes(b"changed")
        result = self.collect()["cohorts"]["easy"]
        self.assertEqual(result["state"], "artifact_hash_mismatch")
        self.assertFalse(result["selected_artifact_bytes_verified"])

    def test_changed_label(self):
        (self.labels / "0.json.gz").write_bytes(b"changed")
        self.assertEqual(
            self.collect()["cohorts"]["easy"]["state"], "artifact_hash_mismatch"
        )

    def test_identical_plan_copies_do_not_duplicate_parents(self):
        copy = self.models / "copy"
        copy.mkdir()
        (copy / "gasse_training_plan.json").write_bytes(
            (self.models / "gasse_training_plan.json").read_bytes()
        )
        result = self.collect()["cohorts"]["easy"]
        self.assertEqual(result["identical_plan_copies"], 2)
        self.assertEqual(len(result["parents"]), 3)

    def test_ambiguous_report_not_guessed(self):
        (self.models / "confirmation_graph_report.json").write_bytes(
            self.report_path.read_bytes()
        )
        self.assertEqual(
            self.collect()["cohorts"]["easy"]["state"],
            "graph_report_missing_or_ambiguous",
        )

    def test_split_mismatch(self):
        self.plan["records"][0]["fold"] = 2
        self.refresh_plan()
        self.assertEqual(
            self.collect()["cohorts"]["easy"]["state"],
            "canonical_split_or_identity_mismatch",
        )

    def test_path_traversal(self):
        reader = audit.Reader(self.root)
        for relative in (
            "../secrets/gurobi.lic",
            "/private",
            "C:/private",
            "..\\private",
            "secrets/gurobi.lic",
        ):
            with self.subTest(relative=relative), self.assertRaises(audit.AuditStop):
                reader.reference(self.root, relative)

    def test_budget_limits(self):
        with self.assertRaises(audit.AuditStop):
            self.collect(seconds=-1)
        with self.assertRaises(audit.AuditStop):
            self.collect(max_bytes=1)

    def test_cached_file_mutation_rejected(self):
        reader = audit.Reader(self.root)
        path = self.graph_root / "graph-0.bin"
        reader.read(path)
        path.write_bytes(b"changed size")
        with self.assertRaises(audit.AuditStop):
            reader.read(path)

    def test_real_cli_keeps_false_admission_and_no_overwrite(self):
        output = self.base / "return.json"
        command = [
            sys.executable,
            "-B",
            str(SCRIPTS / "verify_sprint_c_artifacts.py"),
            "--data-root",
            str(self.root),
            "--output",
            str(output),
        ]
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(
            json.loads(process.stdout)["receipt_sha256"],
            metadata.digest(output.read_bytes()),
        )
        result = json.loads(output.read_bytes())
        self.assertFalse(result["training_admitted"])
        self.assertTrue(
            all(
                v["state"] == "selected_plan_missing"
                for v in result["cohorts"].values()
            )
        )
        repeated = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(repeated.returncode, 2)


if __name__ == "__main__":
    unittest.main()
