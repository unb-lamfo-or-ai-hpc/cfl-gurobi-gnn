"""Exact Git-source portable bundle; existing remote checkouts are never changed."""

import hashlib
import io
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

from ..contract import canonical_bytes, load_json, require
from ..journal import durable_json, file_sha256
from . import VERSION

PREFIXES = ("src/cfl_gnn/mvp3/", "scripts/mvp3/", "configs/mvp3/")
ROOT_FILE = "src/cfl_gnn/__init__.py"


def selected(path):
    return path == ROOT_FILE or any(path.startswith(prefix) for prefix in PREFIXES)


def prepare(repository, output, source_commit, ci_receipt, local_license_file):
    require(
        re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None,
        "Exact reviewed source required",
    )
    repository, output = Path(repository).resolve(), Path(output).resolve()
    require(
        not output.is_relative_to(repository),
        "Private bundle output must be outside checkout",
    )
    require(
        Path(local_license_file).is_file(),
        "Existing Windows license path is unavailable; contents must not be opened",
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    require(head == source_commit, "Source head changed")
    require(
        not subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=repository,
            text=True,
        ),
        "Clean checkout required",
    )
    ci = load_json(ci_receipt)
    require(
        ci.get("head") == source_commit
        and len(ci.get("jobs", [])) == 9
        and len({job.get("id") for job in ci.get("jobs", [])}) == 9
        and all(
            job.get("conclusion") == "success" and job.get("status") == "completed"
            for job in ci["jobs"]
        ),
        "Nine exact-source successful CI jobs required",
    )
    paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", source_commit],
        cwd=repository,
        text=True,
    ).splitlines()
    files = {}
    for path in paths:
        if selected(path):
            mode = subprocess.check_output(
                ["git", "ls-tree", source_commit, "--", path], cwd=repository, text=True
            ).split()[0]
            require(
                mode in ("100644", "100755"),
                "Bundle cannot contain Git links or submodules",
            )
            files[path] = subprocess.check_output(
                ["git", "show", f"{source_commit}:{path}"], cwd=repository
            )
    require(
        "scripts/mvp3/qualify_production.py" in files and ROOT_FILE in files,
        "Production entry/root missing from exact source",
    )
    require(
        sum(len(raw) for raw in files.values()) <= 5 * 1024 * 1024,
        "Portable source bundle exceeds five MiB",
    )
    manifest = {
        "schema_version": VERSION,
        "source_commit": source_commit,
        "CI": ci,
        "scientific_execution_authorized": False,
        "files": {
            path: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
            for path, raw in sorted(files.items())
        },
    }
    manifest_bytes = canonical_bytes(manifest) + b"\n"
    output.mkdir(parents=True, exist_ok=False)
    archive = output / "s2-production-qualification.tar"
    with tarfile.open(archive, mode="x", format=tarfile.PAX_FORMAT) as tar:
        for path, raw in sorted(
            {**files, "bundle-manifest.json": manifest_bytes}.items()
        ):
            info = tarfile.TarInfo(path)
            info.size, info.mode, info.mtime = len(raw), 0o600, 0
            tar.addfile(info, io.BytesIO(raw))
    result = {
        "schema_version": VERSION,
        "source_commit": source_commit,
        "archive_sha256": file_sha256(archive),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "file_count": len(files),
        "local_GRB_LICENSE_FILE": str(Path(local_license_file).resolve()),
        "license_contents_read_copied_or_hashed": False,
        "native_calls": 0,
        "HPC_access": False,
        "instructions": "Author manually transfers archive, verifies archive SHA256, extracts into a new private ASCII scratch folder and runs discover with the manifest SHA256. Never overwrite the installed home checkout.",
    }
    durable_json(output / "prepared.json", result)
    return result


def verify_bundle(root, expected_manifest_sha256):
    root = Path(root).resolve()
    require(
        re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is not None,
        "External manifest SHA256 required",
    )
    path = root / "bundle-manifest.json"
    require(
        file_sha256(path) == expected_manifest_sha256, "Source bundle manifest changed"
    )
    manifest = load_json(path)
    require(
        manifest["schema_version"] == VERSION
        and manifest["scientific_execution_authorized"] is False,
        "Invalid bundle authority",
    )
    members = list(root.rglob("*"))
    require(not any(p.is_symlink() for p in members), "Bundle symlinks are forbidden")
    require(
        re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]) is not None,
        "Invalid source identity",
    )
    actual = {p.relative_to(root).as_posix() for p in members if p.is_file()}
    require(
        actual == set(manifest["files"]) | {"bundle-manifest.json"},
        "Bundle file set changed; outputs must be outside bundle",
    )
    for name, expected in manifest["files"].items():
        relative = PurePosixPath(name)
        require(
            selected(name)
            and not relative.is_absolute()
            and ".." not in relative.parts,
            "Unsafe bundle member",
        )
        path = root / name
        require(
            not path.is_symlink() and path.resolve().is_relative_to(root),
            "Bundle links are forbidden",
        )
        require(
            path.stat().st_size == expected["bytes"]
            and file_sha256(path) == expected["sha256"],
            "Source bundle file changed",
        )
    return manifest
