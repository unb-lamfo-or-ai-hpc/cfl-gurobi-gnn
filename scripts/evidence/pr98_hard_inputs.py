#!/usr/bin/env python3
"""Read-only MILPBench input inspection for the six PR98 hard parents."""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

DATA = Path("/raid/vrcelestino/data")
EVIDENCE = DATA / "cfl-mvp2-evidence"
ROOT = Path(__file__).resolve().parents[2]
PREPARATION = EVIDENCE / "pr94-preparation-c623fe858f62"
CHECKPOINT = "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028"
GIB = 1024**3
CHUNK = 1024**2
PILOT = "H25"
ARCHIVE = {
    "H0": None,
    "H5": (
        135846967,
        "7f0b9a9d11ed28eae8ec295035c507e00477387114b510c984811131873d9454",
    ),
    "H10": (
        135812992,
        "af80d09064bd9ed9c497ef37b43afad7b3e4b7ea97c7a6553997d1b0075d32f8",
    ),
    "H15": (
        135836613,
        "4b4302ee25c63ae92d105087f33b614aa35acc08f300775390e5e4942655ec57",
    ),
    "H20": (
        135823234,
        "9f95036756be3ce65eb93a5ed6f629d168c0e45a504deca8308650ab29e6b4e1",
    ),
    "H25": (
        135856517,
        "d615e368236abf98cf8bc0a7deb1dddb50b764d263e099b7174a267b900c292c",
    ),
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def write_once(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def read(path):
    require(path.is_file() and not path.is_symlink(), "regular_json_required")
    return json.loads(path.read_text(encoding="utf-8"))


def source_commit():
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(ROOT), *args], text=True, timeout=30
        ).strip()

    require(not git("status", "--porcelain", "--untracked-files=all"), "source_changed")
    return git("rev-parse", "HEAD")


def site_stage(stage):
    import pwd

    require(socket.gethostname().split(".")[0] == "dgx-dasci", "host")
    require(pwd.getpwuid(os.getuid()).pw_name == "vrcelestino", "user")
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "environment")
    root = stage.resolve(strict=True)
    require(
        not stage.is_symlink()
        and root.parent == EVIDENCE.resolve()
        and root.name.startswith("pr98-hard.")
        and ROOT.resolve() == root / "source",
        "isolated_stage",
    )
    return root


def data_file(path, data):
    resolved = path.resolve(strict=True)
    require(
        not path.is_symlink()
        and resolved.is_relative_to(data.resolve())
        and resolved.is_file(),
        "file_outside_data_or_not_regular",
    )
    return resolved


def model_candidates(data, parent):
    files = []
    for layout in ("raw/MILPBench/CFL", "cfl-gurobi-gnn/data/raw/MILPBench/CFL"):
        for suffix in (".lp.gz", ".lp"):
            path = data / layout / "CFL_hard_instance/LP" / (parent + suffix)
            if path.exists() or path.is_symlink():
                resolved = data_file(path, data)
                if resolved not in files:
                    files.append(resolved)
    return files


def model_identity(path, deadline):
    before = path.stat()
    require(0 < before.st_size <= GIB, "model_file_size")
    compressed = path.name.endswith(".lp.gz")
    sha = digest(path)
    total, prefix, tail = 0, b"", b""
    checksum = hashlib.sha256()
    opener = gzip.open if compressed else open
    with opener(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            total += len(chunk)
            require(total <= 2 * GIB, "decoded_size_limit")
            require(time.monotonic() < deadline, "inspection_time_limit")
            checksum.update(chunk)
            if not prefix:
                prefix = chunk[:65536]
            tail = (tail + chunk[-8192:])[-8192:]
    sense = next(
        (
            line.strip().lower()
            for line in prefix.splitlines()
            if line.strip() and not line.lstrip().startswith(b"\\")
        ),
        b"",
    )
    require(
        sense in (b"minimize", b"maximize")
        and tail.rstrip().splitlines()[-1].strip().lower() == b"end",
        "unsupported_or_incomplete_LP",
    )
    after = path.stat()
    require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "model_changed_during_inspection",
    )
    return {
        "bytes": before.st_size,
        "sha256": sha,
        "decoded_bytes": total,
        "decoded_sha256": checksum.hexdigest(),
        "original_objective_sense": sense.decode().upper(),
        "format": "lp.gz" if compressed else "lp",
    }


def inspect_models(data, deadline):
    rows, bindings = {}, {}
    for alias, archived in ARCHIVE.items():
        parent = "CFL_hard_instance_" + alias[1:]
        row = {
            "parent": parent,
            "archived_gzip_sha256": archived[1] if archived else None,
            "status": "model_missing",
        }
        rows[alias] = row
        try:
            candidates = [
                (p, model_identity(p, deadline)) for p in model_candidates(data, parent)
            ]
            row["candidates"] = [value for _, value in candidates]
            if not candidates:
                continue
            if len({value["decoded_sha256"] for _, value in candidates}) != 1:
                row["status"] = "conflicting_LP_bytes"
                continue
            matches = [
                (p, value)
                for p, value in candidates
                if archived
                and value["format"] == "lp.gz"
                and (value["bytes"], value["sha256"]) == archived
            ]
            if not matches:
                row["status"] = (
                    "independent_LP_reference_required"
                    if archived is None
                    else "PaScal_gzip_digest_not_matched"
                )
                continue
            path, identity = matches[0]
            row["status"] = "PaScal_model_bytes_matched"
            bindings[alias] = {
                "parent": parent,
                "model": str(path),
                "model_sha256": identity["sha256"],
            }
        except (OSError, EOFError, ValueError, IndexError) as exc:
            row["status"] = "inspection_failed"
            row["issue"] = str(exc) if type(exc) is ValueError else type(exc).__name__
    return rows, bindings


def inspect(stage, expected_commit):
    require(source_commit() == expected_commit, "source_commit")
    require(
        not (stage / "preflight.json").exists()
        and not (stage / "inputs.private.json").exists(),
        "preserve_existing_stage",
    )
    rows, models = inspect_models(DATA, time.monotonic() + 540)
    # Reuse the exact selected checkpoint from the already reviewed PR94 preparation.
    config = read(PREPARATION / "inputs.private.json")
    checkpoint = data_file(Path(config["checkpoint_path"]), DATA)
    require(
        checkpoint.stat().st_size <= 64 * CHUNK and digest(checkpoint) == CHECKPOINT,
        "frozen_checkpoint_bytes",
    )
    write_once(
        stage / "inputs.private.json", {"models": models, "checkpoint": str(checkpoint)}
    )
    report = {
        "source_commit": expected_commit,
        "rows": rows,
        "checkpoint_sha256": CHECKPOINT,
        "private_inputs_sha256": digest(stage / "inputs.private.json"),
        "free_storage_bytes": shutil.disk_usage(stage).free,
        "python": sys.version.split()[0],
        "pilot_input_matched": PILOT in models,
        "root_graph_predictions_and_starts_qualified": False,
        "solver_calls": 0,
        "inference_calls": 0,
        "slurm_submissions": 0,
    }
    write_once(stage / "preflight.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    print("PR98_PREFLIGHT_SHA256=" + digest(stage / "preflight.json"))
    print("PR98_STAGE=" + str(stage))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path)
    parser.add_argument("source_commit")
    args = parser.parse_args()
    os.umask(0o077)
    inspect(site_stage(args.stage), args.source_commit)


if __name__ == "__main__":
    main()
