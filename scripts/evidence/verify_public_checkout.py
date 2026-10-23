"""Verify exact public evidence bytes; optionally repair proven CRLF-only drift.

SPDX-License-Identifier: MIT
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from verify_mvp1_closure_receipts import checksum_lines

PREFIX = "docs/evidence/mvp1/"
SUMMARIES = {
    "closure_verification.json",
    "hardware_allocations.json",
    "incumbent_inventory.json",
    "parent_coverage.json",
}


def git_reader(repository):
    """Pin one commit, read its binary blobs without shell/text conversion."""
    repository = Path(repository).resolve(strict=True)
    # Trust only the selected checkout, including on security-patched Git releases
    # that accept safe.directory in global config but not command-line config.
    # A subprocess-local temporary config never changes the user's global file.
    command = [
        "git",
        "-c",
        "safe.directory=" + repository.as_posix(),
        "-C",
        str(repository),
    ]

    def read_git(arguments):
        with tempfile.TemporaryDirectory(prefix="cfl-git-read-") as directory:
            configuration = Path(directory) / "config"
            configuration.write_text(
                "[safe]\n\tdirectory =\n\tdirectory = "
                + json.dumps(repository.as_posix(), ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update(
                GIT_CONFIG_GLOBAL=str(configuration),
                GIT_CONFIG_NOSYSTEM="1",
                GIT_CONFIG_COUNT="0",
                GIT_CONFIG_PARAMETERS="",
            )
            return subprocess.check_output(command + arguments, env=environment)

    commit = read_git(["rev-parse", "--verify", "HEAD"]).decode().strip()
    return lambda name: read_git(["show", commit + ":" + PREFIX + name])


def verify_checkout(repository, repair=False, committed_reader=None):
    read = committed_reader if committed_reader is not None else git_reader(repository)
    manifest = read("SHA256SUMS.txt")
    if b"\r" in manifest:
        raise ValueError("Committed checksum manifest is not canonical LF")
    checksums = checksum_lines(manifest)
    if set(checksums) != SUMMARIES:
        raise ValueError(
            "Committed manifest does not cover exactly the four public summaries"
        )
    changes = []
    for name in sorted(SUMMARIES | {"SHA256SUMS.txt"}):
        committed = read(name)
        if (
            name in SUMMARIES
            and hashlib.sha256(committed).hexdigest() != checksums[name]
        ):
            raise ValueError(
                "Committed summary does not match its declared hash: " + name
            )
        path = repository / PREFIX / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Public summary must be an existing regular file: " + name)
        current = path.read_bytes()
        if current == committed:
            continue
        if current.replace(b"\r\n", b"\n") != committed:
            raise ValueError("Non-EOL change detected; preserve it for review: " + name)
        changes.append((path, current, committed))
    # Preflight every file before writing anything. Never regenerate expected hashes.
    if changes and not repair:
        raise ValueError(
            "CRLF-only checkout drift detected; explicit repair is required"
        )
    for path, original, committed in changes:
        if path.read_bytes() != original:
            raise ValueError(
                "File changed after preflight; preserve it for review: " + path.name
            )
        path.write_bytes(committed)
        if path.read_bytes() != committed:
            raise ValueError("Public checkout repair verification failed: " + path.name)
    return len(changes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--repair-line-endings", action="store_true")
    args = parser.parse_args()
    count = verify_checkout(args.repository, args.repair_line_endings)
    print(
        f"PR64_PUBLIC_CHECKOUT_BYTES_OK | eol_repairs={count} | expected_hashes_unchanged=true"
    )
