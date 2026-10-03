"""Byte-preservation regression tests for rebase checkout transitions.

SPDX-License-Identifier: MIT
"""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts' / 'evidence'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('verify_public_checkout', SCRIPTS / 'verify_public_checkout.py')
CHECKOUT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CHECKOUT)


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / CHECKOUT.PREFIX
        self.output.mkdir(parents=True)
        self.blobs = {name: b'{\n  "value": 1\n}\n' for name in CHECKOUT.SUMMARIES}
        self.blobs['SHA256SUMS.txt'] = ''.join(
            hashlib.sha256(self.blobs[name]).hexdigest() + '  ' + name + '\n'
            for name in sorted(CHECKOUT.SUMMARIES)).encode()
        for name, payload in self.blobs.items():
            (self.output / name).write_bytes(payload)

    def verify(self, repair=False):
        return CHECKOUT.verify_checkout(self.root, repair, self.blobs.__getitem__)

    def test_canonical_checkout_needs_no_repair(self):
        self.assertEqual(self.verify(), 0)

    def test_check_only_preserves_crlf_drift(self):
        path = self.output / 'closure_verification.json'
        drift = self.blobs[path.name].replace(b'\n', b'\r\n')
        path.write_bytes(drift)
        with self.assertRaisesRegex(ValueError, 'explicit repair'):
            self.verify()
        self.assertEqual(path.read_bytes(), drift)

    def test_repair_restores_all_bytes_without_changing_hashes(self):
        for name, blob in self.blobs.items():
            (self.output / name).write_bytes(blob.replace(b'\n', b'\r\n'))
        self.assertEqual(self.verify(repair=True), 5)
        for name, blob in self.blobs.items():
            self.assertEqual((self.output / name).read_bytes(), blob)
        self.assertEqual(self.verify(repair=True), 0)

    def test_content_change_blocks_all_repairs(self):
        first = self.output / 'closure_verification.json'
        drift = self.blobs[first.name].replace(b'\n', b'\r\n')
        first.write_bytes(drift)
        changed = self.output / 'parent_coverage.json'
        changed.write_bytes(b'{"value": 2}\n')
        with self.assertRaisesRegex(ValueError, 'Non-EOL'):
            self.verify(repair=True)
        self.assertEqual(first.read_bytes(), drift)
        self.assertEqual(changed.read_bytes(), b'{"value": 2}\n')

    def test_wrong_committed_hash_is_not_recomputed(self):
        name = 'closure_verification.json'
        self.blobs[name] = b'{"value": 3}\n'
        with self.assertRaisesRegex(ValueError, 'declared hash'):
            self.verify(repair=True)

    def test_missing_file_is_not_silently_recreated(self):
        (self.output / 'parent_coverage.json').unlink()
        with self.assertRaisesRegex(ValueError, 'existing regular file'):
            self.verify(repair=True)


if __name__ == '__main__':
    unittest.main()
