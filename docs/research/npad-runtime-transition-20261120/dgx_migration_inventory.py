"""Metadata-only inventory before cleanup/migration; no deletion or data export."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import socket
import stat
import subprocess
import time
import uuid
import zipfile
from pathlib import Path

ROOT_NAMES = (
    "CFL",
    "cfl-gurobi-gnn",
    "cfl-gurobi-gnn-archive",
    "cfl-gurobi-gnn-pr57_54",
    "cfl-gurobi-gnn-quarantine",
    "cfl-gurobi-gnn-worktrees",
    "cfl-mvp2-evidence",
    "cfl-zenodo-staging",
)
INPUT_TREES = (
    "data/bipartite_graphs",
    "data/intermediate_lps",
    "data/raw/MILPBench/CFL",
    "data/real_train_output",
    "data/metadata",
)


def sensitive(name):
    low = name.lower()
    return low in {
        "secrets",
        ".ssh",
        ".aws",
        ".env",
        ".envrc",
        ".netrc",
        ".pypirc",
    } or (
        low.endswith((".lic", ".pem", ".key"))
        or low.startswith("id_rsa")
        or low.startswith("id_ed25519")
        or low.startswith(".env.")
    )


def inventory(root, deadline, entry_limit=250000):
    """Do not follow links, mount boundaries, Git objects or credential entries."""
    rows, links, issues, repositories = [], [], [], []
    totals = collections.Counter()
    root_device = root.stat().st_dev
    stack = [(root, "")]
    complete = True
    while stack:
        if time.monotonic() > deadline or len(rows) + len(links) >= entry_limit:
            complete = False
            issues.append({"code": "BOUNDED_INVENTORY_INCOMPLETE"})
            break
        directory, relative = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if (
                        time.monotonic() > deadline
                        or len(rows) + len(links) >= entry_limit
                    ):
                        complete = False
                        issues.append({"code": "BOUNDED_INVENTORY_INCOMPLETE"})
                        stack.clear()
                        break
                    if sensitive(entry.name):
                        totals["sensitive_entries_excluded"] += 1
                        continue
                    rel = str(Path(relative) / entry.name)
                    if entry.name == ".git":
                        repositories.append(str(directory))
                        totals["git_entries_excluded"] += 1
                        continue
                    try:
                        # DirEntry.stat can expose zero device/inode fields on Windows.
                        info = os.stat(entry.path, follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode):
                            links.append(
                                {
                                    "path": rel,
                                    "target": os.readlink(entry.path),
                                    "followed": False,
                                }
                            )
                        elif info.st_dev != root_device:
                            issues.append(
                                {"path": rel, "code": "OTHER_DEVICE_NOT_FOLLOWED"}
                            )
                            complete = False
                        elif stat.S_ISDIR(info.st_mode):
                            totals["directories"] += 1
                            stack.append((Path(entry.path), rel))
                        elif stat.S_ISREG(info.st_mode):
                            rows.append(
                                {
                                    "path": rel,
                                    "bytes": info.st_size,
                                    "mtime_ns": info.st_mtime_ns,
                                    "device": info.st_dev,
                                    "inode": info.st_ino,
                                    "nlink": info.st_nlink,
                                }
                            )
                            totals["regular_files"] += 1
                            totals["regular_logical_bytes"] += info.st_size
                            totals["allocated_bytes"] += (
                                getattr(info, "st_blocks", 0) * 512
                            )
                        else:
                            totals["special_entries_not_read"] += 1
                    except OSError as error:
                        complete = False
                        issues.append({"path": rel, "code": type(error).__name__})
        except OSError as error:
            complete = False
            issues.append({"path": relative, "code": type(error).__name__})
    return {
        "complete": complete,
        "totals": dict(totals),
        "files": rows,
        "symlinks_not_followed": links,
        "issues": issues,
        "repository_paths": sorted(set(repositories)),
    }


def git_metadata(root):
    """Read-only Git queries; do not persist raw remote URLs or file contents."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")

    def call(*arguments):
        return subprocess.run(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-C",
                str(root),
                *arguments,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        ).stdout

    try:
        head = call("rev-parse", "HEAD").strip()
        branch = call("symbolic-ref", "--short", "-q", "HEAD").strip()
    except subprocess.CalledProcessError:
        try:
            head = call("rev-parse", "HEAD").strip()
            branch = "DETACHED"
        except (OSError, subprocess.SubprocessError):
            return {"readable": False}
    except (OSError, subprocess.SubprocessError):
        return {"readable": False}
    result = {"readable": True, "HEAD": head, "branch": branch}
    try:
        status = call("status", "--porcelain=v1", "--untracked-files=normal")
        result["status_counts"] = dict(
            collections.Counter(line[:2] for line in status.splitlines())
        )
        result["worktrees_private_metadata"] = call("worktree", "list", "--porcelain")
    except (OSError, subprocess.SubprocessError):
        result["status_query_incomplete"] = True
    return result


def build_report(base, alias):
    report = {
        "scope": "metadata_only_before_cleanup_and_migration",
        "host": socket.gethostname(),
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "base": str(base),
        "requested_alias": str(alias),
        "same_location": alias.resolve(strict=True) == base,
        "no_content_hashes_computed": True,
        "roots": {},
        "regular_byte_totals_may_double_count_hardlinks": True,
        "duplicate_content_or_safe_deletion_not_established": True,
        "cleanup_moves_or_deletions": 0,
        "solver_calls": 0,
        "training_calls": 0,
        "queue_mutations": 0,
    }
    deadline = time.monotonic() + 300
    for name in ROOT_NAMES:
        root = base / name
        if not root.exists() and not root.is_symlink():
            report["roots"][name] = {"status": "ABSENT"}
            continue
        resolved = root.resolve(strict=True)
        if root.is_symlink() and (base not in resolved.parents):
            report["roots"][name] = {
                "status": "EXTERNAL_SYMLINK_NOT_FOLLOWED",
                "resolved_private_target": str(resolved),
            }
            continue
        if not resolved.is_dir():
            report["roots"][name] = {"status": "NOT_A_DIRECTORY"}
            continue
        data = inventory(resolved, deadline)
        data["resolved_private_path"] = str(resolved)
        data["root_is_symlink"] = root.is_symlink()
        data["input_tree_presence"] = {p: (resolved / p).exists() for p in INPUT_TREES}
        data["git"] = {}
        for p in data["repository_paths"][:32]:
            if time.monotonic() > deadline:
                data["git_metadata_truncated"] = True
                break
            data["git"][p] = git_metadata(Path(p))
        if len(data["repository_paths"]) > 32:
            data["git_metadata_truncated"] = True
        if data.get("git_metadata_truncated") or any(
            not item.get("readable") or item.get("status_query_incomplete")
            for item in data["git"].values()
        ):
            data["complete"] = False
        report["roots"][name] = data
    try:
        report["own_queue_snapshot"] = subprocess.run(
            ["squeue", "-h", "-u", os.environ["USER"], "-o", "%i|%T|%j|%R"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        report["own_queue_snapshot"] = "QUERY_UNAVAILABLE"
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("alias", type=Path)
    args = parser.parse_args()
    base = args.base.resolve(strict=True)
    if socket.gethostname().split(".")[0] != "dgx-dasci":
        raise ValueError("WRONG_HOST")
    if str(base) != "/raid/" + os.environ["USER"] + "/data":
        raise ValueError("UNEXPECTED_CANONICAL_DATA_ROOT")
    if args.alias.resolve(strict=True) != base:
        raise ValueError("DISCODATOS_ALIAS_DIFFERS_PRESERVE_AND_DIAGNOSE")
    report = build_report(base, args.alias)
    destination = base / "cfl-mvp2-evidence"
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("EXISTING_EVIDENCE_DIRECTORY_REQUIRED")
    output = destination / (
        "dgx-migration-inventory-" + uuid.uuid4().hex + ".private.zip"
    )
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "inventory.private.json", json.dumps(report, ensure_ascii=True, indent=2)
        )
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    complete = all(
        x.get("complete", x.get("status") == "ABSENT") for x in report["roots"].values()
    )
    print("ARQUIVO_HPC=" + str(output))
    print("SHA256=" + checksum)
    print("RAIZES_SOLICITADAS=" + str(len(ROOT_NAMES)))
    print("INVENTARIO_METADATA_COMPLETO=" + str(complete).lower())
    print("CONTEUDOS_DE_DADOS_LIDOS=0")
    print("ARQUIVOS_REMOVIDOS_OU_MOVIDOS=0")
    print("BYTES_ZIP=" + str(output.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
