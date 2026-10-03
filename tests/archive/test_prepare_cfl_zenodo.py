"""Small synthetic tests; no HPC data or solver is read or executed."""
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("collector", Path(__file__).resolve().parents[2] / "scripts/archive/prepare_cfl_zenodo.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.data = self.base / "data"
        self.repo = self.base / "repo"
        self.out = self.base / "staging"
        self.data.mkdir()
        self.repo.mkdir()
        self.out.mkdir()
        (self.repo / "LICENSE").write_text("MIT test fixture", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, name, content):
        path = self.data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_discovery_excludes_credentials_and_bootstrap(self):
        self.make("analysis/study/report.json", b'{"gap": 0.1}')
        self.make("analysis/tools/helper.py", b"skip")
        self.make("models/secrets/gurobi.lic", b"secret")
        files, excluded, totals = m.discover(self.data)
        self.assertEqual(len(files), 1)
        self.assertEqual(len(excluded), 2)
        self.assertEqual(totals["analysis"]["files"], 1)

    def test_inventory_is_read_only(self):
        p = self.make("intermediate/report.json", b'{"gap": 0.1}')
        before = p.read_bytes()
        _, _, report = m.write_inventory(self.data, self.out)
        self.assertFalse(report["upload_performed"])
        self.assertFalse(report["publication_authorized_by_this_inventory"])
        self.assertEqual(p.read_bytes(), before)

    def test_json_redaction_preserves_syntax_and_source(self):
        p = self.make("analysis/run.json", json.dumps({"path": "/raid/private/run", "gap": 0.2}).encode())
        data, reason = m.public_text(p, self.data, self.repo)
        self.assertIsNone(reason)
        self.assertEqual(json.loads(data)["path"], "[REDACTED_LOCAL_PATH]")
        self.assertIn(b"/raid/", p.read_bytes())

    def test_windows_json_redaction(self):
        p = self.make("analysis/windows.json", json.dumps({"path": "C:\\Users\\alice\\result.csv"}).encode())
        data, reason = m.public_text(p, self.data, self.repo)
        self.assertIsNone(reason)
        self.assertEqual(json.loads(data)["path"], "[REDACTED_LOCAL_PATH]")

    def test_credentials_are_withheld(self):
        p = self.make("analysis/bad.json", b'{"WLSSecret":"not-a-real-secret"}')
        _, reason = m.public_text(p, self.data, self.repo)
        self.assertIsNotNone(reason)

    def test_solver_banner_is_redacted(self):
        p = self.make("analysis/gurobi.log", b"Set parameter WLSSecret\nAcademic license registered to private@example.org\ngap=0.2\n")
        data, reason = m.public_text(p, self.data, self.repo)
        self.assertIsNone(reason)
        self.assertNotIn(b"private@example.org", data)
        self.assertIn(b"gap=0.2", data)

    def test_opaque_binary_paths_are_flagged_without_loading(self):
        p = self.make("bipartite_graphs/graph.pt", b"not-a-pickle\0/raid/private/graph\0")
        _, suspect = m.inspect_binary(p)
        self.assertTrue(suspect)

    def test_quota_failure_before_archiving(self):
        self.make("models/file.bin", b"12345")
        with self.assertRaisesRegex(ValueError, "quota"):
            m.package(self.data, self.repo, self.out, quota=4, chunk=10)
        self.assertFalse((self.out / "upload").exists())

    def test_package_hashes_originals_and_adverse_outcomes(self):
        p = self.make("analysis/outcomes.json", b'{"gap": 0.4, "status": "timelimit", "path": "/home/private/run"}')
        self.make("bipartite_graphs/test.pt", b"opaque-nonsensitive-fixture")
        self.make("analysis/secret.json", b'{"password": "not-a-real-password"}')
        before = m.digest(p)
        m.package(self.data, self.repo, self.out, quota=1_000_000, chunk=500)
        m.verify(self.out)
        report = json.loads((self.out / "package_report.json").read_text())
        self.assertEqual(report["included_files"], 2)
        self.assertEqual(report["withheld_entries"], 1)
        self.assertEqual(report["transformed_text_files"], 1)
        self.assertFalse(report["publication_authorized"])
        self.assertEqual(before, m.digest(p))
        manifest = json.loads((self.out / "upload/manifest.json").read_text())
        row = next(x for x in manifest["files"] if x["relative_path"] == "analysis/outcomes.json")
        self.assertEqual(row["source_sha256"], before)
        self.assertNotEqual(row["public_sha256"], before)
        with tarfile.open(self.out / "upload" / row["archive"]) as archive:
            values = json.load(archive.extractfile(row["relative_path"]))
        self.assertEqual(values["gap"], 0.4)
        self.assertEqual(values["status"], "timelimit")
        with self.assertRaisesRegex(ValueError, "existing staging"):
            m.package(self.data, self.repo, self.out, quota=1_000_000, chunk=500)

    def test_changed_file_is_detected(self):
        p = self.make("analysis/live.json", b"{}")
        files, _, _ = m.discover(self.data)
        p.write_bytes(b"changed")
        self.assertFalse(m.unchanged(p, files[0]))

    def test_empty_and_malformed_json_are_reviewable_not_fatal(self):
        for content in (b"", b"not JSON", b'{"broken":'):
            p = self.make("analysis/invalid.json", content)
            payload, reason = m.public_text(p, self.data, self.repo)
            self.assertEqual(payload, content)
            self.assertEqual(reason, "invalid_source_json_requires_private_review")

    def test_bom_json_is_supported(self):
        p = self.make("analysis/bom.json", b'\xef\xbb\xbf{"gap":0.1}')
        payload, reason = m.public_text(p, self.data, self.repo)
        self.assertIsNone(reason)
        self.assertEqual(json.loads(payload)["gap"], 0.1)

    def test_malformed_jsonl_is_reviewable(self):
        p = self.make("analysis/bad.jsonl", b'{}\ninvalid\n')
        self.assertEqual(m.public_text(p, self.data, self.repo)[1], "invalid_source_json_requires_private_review")

    def test_private_archive_preserves_invalid_json_and_source_hash(self):
        p = self.make("analysis/incomplete.json", b"")
        self.make("bipartite_graphs/graph.pt", b"opaque\0/raid/internal/graph\0")
        m.package(self.data, self.repo, self.out, 1_000_000, 500, private_archive=True)
        report = json.loads((self.out / "package_report.json").read_text())
        self.assertTrue(report["private_archive"])
        self.assertFalse(report["upload_ready"])
        self.assertTrue(report["archival_coverage_complete_for_discovered_files"])
        self.assertEqual(report["included_files"], 2)
        self.assertEqual(len(report["invalid_structured_artifacts"]), 1)
        for archive in report["packages"]:
            for row in archive["members"]:
                self.assertEqual(row["source_sha256"], row["public_sha256"])
        self.assertEqual(p.read_bytes(), b"")

    def test_legacy_failure_without_journal_cannot_resume(self):
        (self.out / "upload").mkdir()
        with self.assertRaisesRegex(ValueError, "no verified resume journal"):
            m.package(self.data, self.repo, self.out, 1_000_000, 500, resume=True)

    def test_resume_reuses_only_completed_parts(self):
        self.make("analysis/a.json", b"{}")
        self.make("analysis/b.json", b"{}")
        original = tarfile.TarFile.addfile
        calls = []
        def fail_second(tar, member, stream=None):
            calls.append(member.name)
            if len(calls) == 2:
                raise OSError("synthetic interruption")
            return original(tar, member, stream)
        with patch.object(tarfile.TarFile, "addfile", fail_second):
            with self.assertRaises(OSError):
                m.package(self.data, self.repo, self.out, 1_000_000, 2)
        first = self.out / "upload/cfl-analysis-part001.tar.gz"
        checksum = m.digest(first)
        m.package(self.data, self.repo, self.out, 1_000_000, 2, resume=True)
        self.assertEqual(m.digest(first), checksum)
        report = json.loads((self.out / "package_report.json").read_text())
        self.assertEqual(report["included_files"], 2)
        self.assertEqual(len(report["packages"]), 2)
        self.assertEqual(len(list((self.out / "upload").glob("*.incomplete-*"))), 1)

    def test_extra_archive_member_fails_verification(self):
        self.make("analysis/good.json", b"{}")
        m.package(self.data, self.repo, self.out, 1_000_000, 500)
        report = json.loads((self.out / "package_report.json").read_text())
        archive = self.out / "upload" / report["packages"][0]["file"]
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo("unexpected")
            tar.addfile(info)
        report["packages"][0]["sha256"] = m.digest(archive)
        m.dump(self.out / "package_report.json", report)
        with self.assertRaisesRegex(ValueError, "unexpected"):
            m.verify(self.out)


if __name__ == "__main__":
    unittest.main()
