"""Pinned medium metadata inspection never interprets hashes as solver admission."""

import ast
import gzip
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/evidence"))
import inspect_e0_medium_artifacts as module  # noqa: E402


class InspectionTests(unittest.TestCase):
    def root_payload(self, sha):
        names, values = ["x", "y"], [0.0, 0.5]
        return {
            "variable_names": names,
            "relaxation_vector": values,
            "variable_count": 2,
            "source_mip_sha256": sha,
            "node_count": 0,
            "authority": "gurobi",
            "capture_method": "first_optimal_root_gurobi_mipnode",
            "effective_objective_sense": "MINIMIZE",
            "variable_order_sha256": module.meta.digest(module.meta.canonical(names)),
            "vector_sha256": module.meta.digest(module.meta.canonical(values)),
        }

    def test_root_consistency_not_inference_admission(self):
        value = self.root_payload("a" * 64)
        profile = module.profile(value, module.inventory.PARENTS[0], "a" * 64)
        self.assertTrue(profile["root_self_consistent_candidate"])
        self.assertFalse(profile["content_admitted_for_inference"])
        self.assertFalse(profile["root_model_variable_order_rechecked"])
        for key, replacement in (
            ("source_mip_sha256", "b" * 64),
            ("node_count", 1),
            ("relaxation_vector", [0, float("inf")]),
        ):
            bad = {**value, key: replacement}
            self.assertFalse(
                module.profile(bad, module.inventory.PARENTS[0], "a" * 64)[
                    "root_self_consistent_candidate"
                ]
            )

    def test_free_text_and_label_values_never_exported(self):
        value = {
            "source_instance_id": module.inventory.PARENTS[0],
            "license": "secret",
            "path": "/private",
            "variables": [{"name": "private_name", "value": 42}],
            "status": "private exception",
            "runtime": 2.0,
            "parameters": {"Threads": 1, "TokenServer": "secret"},
        }
        public = module.profile(value, module.inventory.PARENTS[0], "a" * 64)
        text = json.dumps(public)
        self.assertNotIn("secret", text)
        self.assertNotIn("private", text)
        self.assertNotIn("42", text)
        self.assertEqual(public["array_lengths_only"], {"variables": 1})
        self.assertEqual(public["sections"]["parameters"], {"Threads": 1})

    def setup_files(self, folder, stack):
        folder = Path(folder)
        root, stage, repo = folder / "data", folder / "inventory", folder / "repo"
        for group in module.meta.GROUPS:
            (root / group).mkdir(parents=True)
        for parent in module.inventory.PARENTS:
            original = root / f"raw/MILPBench/CFL/CFL_medium_instance/LP/{parent}.lp"
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_bytes(parent.encode())
            directory = root / "analysis" / parent
            directory.mkdir()
            for i in range(4):
                (directory / f"record{i}.json").write_text(
                    json.dumps(
                        {
                            "source_instance_id": parent,
                            "runtime": i,
                            "secret": "never export",
                        }
                    )
                )
        with redirect_stdout(io.StringIO()):
            module.inventory.collect(root, stage)
        target = repo / "docs/evidence/e0/medium-inventory.json"
        target.parent.mkdir(parents=True)
        shutil.copyfile(stage / "inventory.json", target)
        stack.enter_context(patch.object(module, "ROOT", repo))
        stack.enter_context(
            patch.object(module, "SHA", module.meta.digest(target.read_bytes()))
        )
        for parent in module.inventory.PARENTS:
            directory = root / "analysis" / parent
            # These were missed by the old filename-only inventory. Discover as siblings.
            (directory / "label_free_graph.pt").write_bytes(
                b"opaque graph, never deserialize"
            )
            with gzip.open(directory / "root_features.json.gz", "wb") as stream:
                stream.write(
                    json.dumps(
                        self.root_payload(module.meta.digest(parent.encode()))
                    ).encode()
                )
        return root, stage, folder / "result"

    def test_integrated_pins_siblings_no_rescan(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            ExitStack() as stack,
            redirect_stdout(io.StringIO()),
        ):
            root, stage, output = self.setup_files(folder, stack)
            stack.enter_context(
                patch.object(
                    module.Reader, "scan", side_effect=AssertionError("no rescan")
                )
            )
            value = module.collect(root, stage, output)
            self.assertEqual(value["state"], "scoped_inspection_complete")
            self.assertEqual(len(value["profiles"]), 10)
            self.assertEqual(len(value["opaque_caches"]), 2)
            self.assertEqual(
                sum(p["root_self_consistent_candidate"] for p in value["profiles"]), 2
            )
            data = (output / "inspection.json").read_bytes()
            self.assertEqual(module.validate(data, module.meta.digest(data)), value)
            self.assertNotIn(str(root).encode(), data)
            with self.assertRaisesRegex(ValueError, "fresh_output"):
                module.collect(root, stage, output)

    def test_changed_pinned_bytes_stop_before_inspection(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root, stage, output = self.setup_files(folder, stack)
            (
                root / "analysis" / module.inventory.PARENTS[0] / "record0.json"
            ).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
                module.collect(root, stage, output)
            self.assertFalse(output.exists())

    def test_private_index_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root, stage, output = self.setup_files(folder, stack)
            index = json.loads((stage / "private_paths.json").read_bytes())
            index[next(iter(index))] = str(Path(folder) / "outside.json")
            (stage / "private_paths.json").write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError, "outside_data_root"):
                module.collect(root, stage, output)

    def test_corrupt_cached_gzip_partial_not_retry(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            ExitStack() as stack,
            redirect_stdout(io.StringIO()),
        ):
            root, stage, output = self.setup_files(folder, stack)
            (
                root
                / "analysis"
                / module.inventory.PARENTS[0]
                / "root_features.json.gz"
            ).write_bytes(b"bad")
            value = module.collect(root, stage, output)
            self.assertEqual(value["state"], "partial")
            self.assertFalse(value["inference_admitted"])
            self.assertTrue(
                all(not f["private_text_included"] for f in value["failures"])
            )

    def test_rehash_content_before_decoding(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            ExitStack() as stack,
            redirect_stdout(io.StringIO()),
        ):
            root, stage, output = self.setup_files(folder, stack)
            real_read = module.Reader.read

            def changed_read(reader, path, *, content=False):
                data = real_read(reader, path, content=content)
                return data + b" " if content and path.name == "record0.json" else data

            stack.enter_context(patch.object(module.Reader, "read", changed_read))
            value = module.collect(root, stage, output)
            self.assertEqual(value["state"], "partial")
            self.assertEqual(len(value["failures"]), 2)
            self.assertEqual(
                sum(p["origin"] == "pinned_inventory" for p in value["profiles"]), 6
            )

    def test_actual_installed_receipt_and_no_solver_calls(self):
        data = (module.ROOT / "docs/evidence/e0/medium-inventory.json").read_bytes()
        value = module.inventory.validate(data, module.SHA)
        self.assertEqual(len(value["candidates"]), 10)
        self.assertEqual(
            sum(r["bytes"] for r in value["candidates"]), value["bytes_read"]
        )
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(
                    node.func.attr, {"optimize", "backward", "Popen", "system", "load"}
                )


if __name__ == "__main__":
    unittest.main()
