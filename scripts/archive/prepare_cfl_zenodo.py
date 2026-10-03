"""Inventory and package CFL research outputs without modifying source files.

Uses the Python standard library only. Run inventory first; archive creation is
explicit and never uploads or publishes. Binary objects are not deserialized.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
from datetime import datetime, timezone

GROUPS = ("analysis", "intermediate", "bipartite_graphs", "models", "embeddings")
TEXT = {".json", ".jsonl", ".csv", ".tsv", ".txt", ".md", ".yaml", ".yml",
        ".svg", ".html", ".qmd", ".bib", ".tex", ".out", ".err", ".log", ".lp"}
OMIT_DIRS = {".git", ".svn", "__pycache__", "secrets", "bootstrap", "tools",
             "node_modules", ".ipynb_checkpoints", ".pr57-remaining-medium-queue"}
OMIT_NAMES = {".env", "credentials", "credentials.json", "id_rsa", "id_ed25519"}
SECRET = re.compile(rb"(?i)(?:WLSSecret|WLSAccessID|LicenseID|api[_-]?key|access[_-]?token|password)\s*[\"']?\s*[:=]\s*[\"']?[^\s,}\"']+")
LOCAL_PATH = re.compile(rb"/(?:home|raid)/|[A-Za-z]:(?:\\{1,2}|/)(?:Users|Downloads)(?:\\{1,2}|/)")
MAX_TEXT = 64 * 1024 * 1024
BLOCK = 4 * 1024 * 1024


def dump(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            h.update(block)
    return h.hexdigest()


def discover(data: Path):
    included, omitted, totals = [], [], {}
    for group in GROUPS:
        root = data / group
        totals[group] = {"exists": root.is_dir(), "files": 0, "bytes": 0}
        if root.is_symlink():
            omitted.append({"relative_path": group, "reason": "symlink_group_root"})
            continue
        if not root.is_dir():
            continue
        for current, directories, names in os.walk(root, followlinks=False):
            base = Path(current)
            for name in list(directories):
                candidate = base / name
                if name in OMIT_DIRS or candidate.is_symlink():
                    directories.remove(name)
                    omitted.append({"relative_path": candidate.relative_to(data).as_posix(),
                                    "reason": "private_operational_directory_or_symlink"})
            for name in sorted(names):
                path = base / name
                relative = path.relative_to(data).as_posix()
                if path.is_symlink() or name in OMIT_NAMES or path.suffix.lower() in {".lic", ".pem", ".key", ".pyc"}:
                    omitted.append({"relative_path": relative, "reason": "credential_name_or_symlink"})
                    continue
                stat = path.stat()
                included.append({"relative_path": relative, "group": group,
                                 "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
                totals[group]["files"] += 1
                totals[group]["bytes"] += stat.st_size
    return sorted(included, key=lambda row: row["relative_path"]), omitted, totals


def write_inventory(data: Path, output: Path):
    files, omitted, totals = discover(data)
    total = sum(row["bytes"] for row in files)
    free = shutil.disk_usage(output).free
    report = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "generated_research_outputs_not_raw_benchmark_or_repository_secrets",
              "groups": totals, "files": len(files), "uncompressed_bytes": total,
              "uncompressed_GB_decimal": round(total / 1e9, 3), "staging_free_bytes": free,
              "conservative_staging_requirement_bytes": total + max(1_000_000_000, total // 10),
              "zenodo_default_record_quota_bytes": 50_000_000_000,
              "zenodo_expanded_quota_requires_account_verification": True,
              "originals_modified": False, "solver_runs": 0, "upload_performed": False,
              "binary_content_privacy_certified": False,
              "publication_authorized_by_this_inventory": False}
    dump(output / "inventory_summary.json", report)
    dump(output / "inventory.json", {"files": files, "excluded": omitted})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("CFL_ZENODO_INVENTORY_OK")
    return files, omitted, report


def inspect_binary(path: Path):
    """Hash opaque bytes and flag obvious credentials/paths without unpickling."""
    h = hashlib.sha256()
    suspicious, tail = False, b""
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            h.update(block)
            probe = tail + block
            suspicious |= bool(SECRET.search(probe) or LOCAL_PATH.search(probe))
            tail = probe[-4096:]
    return h.hexdigest(), suspicious


def public_text(path: Path, data: Path, repo: Path):
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload, "non_utf8_text_requires_review"
    # Validate the original before redaction, identifying invalid source artifacts.
    suffix = path.suffix.lower()
    def validate(candidate):
        if suffix == ".json":
            json.loads(candidate)
        elif suffix == ".jsonl":
            for line in candidate.splitlines():
                if line.strip():
                    json.loads(line)
    try:
        validate(text)
    except (json.JSONDecodeError, RecursionError):
        return payload, "invalid_source_json_requires_private_review"
    # Plain solver log licence announcements are not research measurements.
    if path.suffix.lower() in {".out", ".err", ".log", ".txt"}:
        text = re.sub(r"(?im)^.*(?:Set parameter WLS|license.*registered|LicenseID to value|registered to).*$",
                      "[REDACTED_LICENSE_ANNOUNCEMENT]", text)
    if SECRET.search(text.encode("utf-8")):
        return payload, "possible_credential_requires_private_review"
    text = text.replace(str(data), "DATA_ROOT").replace(str(repo), "REPO_ROOT")
    text = re.sub(r"/(?:home|raid)/[^\s\"'<>]+", "[REDACTED_LOCAL_PATH]", text)
    text = re.sub(r"[A-Za-z]:(?:\\{1,2}|/)(?:Users|Downloads)(?:\\{1,2}|/)[^\s\"'<>]+",
                  "[REDACTED_LOCAL_PATH]", text)
    if LOCAL_PATH.search(text.encode("utf-8")):
        return payload, "local_path_requires_private_review"
    try:
        validate(text)
    except (json.JSONDecodeError, RecursionError) as error:
        raise ValueError("redaction changed valid JSON syntax: " + path.name) from error
    return text.encode("utf-8"), None


def unchanged(path: Path, entry) -> bool:
    stat = path.stat()
    return stat.st_size == entry["bytes"] and stat.st_mtime_ns == entry["mtime_ns"]


def verify(output: Path):
    report = json.loads((output / "package_report.json").read_text(encoding="utf-8"))
    if not report["packages"]:
        raise ValueError("no research archives to verify")
    for archive in report["packages"]:
        path = output / "upload" / archive["file"]
        if digest(path) != archive["sha256"]:
            raise ValueError("archive SHA256 mismatch: " + path.name)
        expected = {row["relative_path"]: row for row in archive["members"]}
        if len(expected) != len(archive["members"]):
            raise ValueError("duplicate manifest member")
        with tarfile.open(path, "r|gz") as tar:
            for member in tar:
                if member.name not in expected:
                    raise ValueError("unexpected or duplicate archive member")
                row = expected.pop(member.name)
                if not member.isfile() or member.size != row["public_bytes"]:
                    raise ValueError("invalid member metadata")
                stream = tar.extractfile(member)
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(BLOCK), b""):
                    h.update(block)
                if h.hexdigest() != row["public_sha256"]:
                    raise ValueError("member SHA256 mismatch")
        if expected:
            raise ValueError("missing archive members")
    for name, expected_hash in report.get("sidecar_sha256", {}).items():
        if digest(output / "upload" / name) != expected_hash:
            raise ValueError("sidecar SHA256 mismatch: " + name)
    print("CFL_ZENODO_ARCHIVE_AND_MEMBER_HASHES_OK")


def package(data: Path, repo: Path, output: Path, quota: int, chunk: int,
            private_archive: bool = False, resume: bool = False):
    if (output / "package_report.json").exists() or ((output / "upload").exists() and not resume):
        raise ValueError("preserve existing staging; use a fresh output directory")
    files, omitted, totals = discover(data)
    signature = hashlib.sha256(json.dumps({"files": files, "excluded": omitted,
        "private_archive": private_archive, "chunk": chunk, "quota": quota,
        "collector_sha256": digest(Path(__file__))}, sort_keys=True).encode()).hexdigest()
    journal_path = output / "completed_parts.json"
    previous = None
    if resume:
        if not journal_path.is_file():
            raise ValueError("no verified resume journal; preserve the earlier failed job and use fresh staging")
        previous = json.loads(journal_path.read_text(encoding="utf-8"))
        if previous["snapshot_sha256"] != signature:
            raise ValueError("source inventory or collector policy changed; resume refused")
    files, omitted, inventory = write_inventory(data, output)
    if inventory["staging_free_bytes"] < inventory["conservative_staging_requirement_bytes"]:
        raise ValueError("insufficient staging space; source files were not changed")
    # Stop before reading/packaging hundreds of GB if quota is obviously too small.
    if inventory["uncompressed_bytes"] > quota:
        raise ValueError("inventory exceeds declared quota; verify storage allocation or plan linked records first")
    upload = output / "upload"
    upload.mkdir(exist_ok=resume)
    packages = previous["packages"] if previous else []
    manifest = [row for archive in packages for row in archive["members"]]
    withheld = previous["withheld"] if previous else list(omitted)
    done = {row["relative_path"] for row in manifest} | {row["relative_path"] for row in withheld}
    # Parse small structured artifacts before the long archive pass. Originals stay intact.
    preflight = []
    for entry in files:
        path = data / entry["relative_path"]
        if path.suffix.lower() in {".json", ".jsonl"} and entry["bytes"] <= MAX_TEXT:
            _, reason = public_text(path, data, repo)
            if reason:
                preflight.append({"relative_path": entry["relative_path"], "reason": reason})
    dump(output / "text_preflight.json", {"issues": preflight, "originals_modified": False})
    print("CFL_TEXT_PREFLIGHT_COMPLETE | issues=" + str(len(preflight)), flush=True)
    tar, active, part = None, None, {}
    for archive in packages:
        if digest(upload / archive["file"]) != archive["sha256"]:
            raise ValueError("completed part changed; resume refused")
        part[archive["group"]] = max(part.get(archive["group"], 0), int(archive["file"].split("part")[-1].split(".")[0]))
    if resume:
        recorded = {row["file"] for row in packages}
        for path in upload.glob("*.tar.gz"):
            if path.name not in recorded:
                # Preserve unfinished parts; never append to or certify them.
                path.rename(path.with_name(path.name + ".incomplete-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")))
    def close_part():
        nonlocal tar, active
        if tar is None:
            return
        tar.close()
        tar = None
        path = upload / active["file"]
        active["sha256"], active["bytes"] = digest(path), path.stat().st_size
        packages.append(active)
        dump(journal_path, {"snapshot_sha256": signature, "packages": packages, "withheld": withheld})
        print("CFL_COMPLETED_PART=" + active["file"], flush=True)
        active = None
    current = None
    try:
        for entry in files:
            if entry["relative_path"] in done:
                continue
            current = entry["relative_path"]
            print("CFL_COLLECTING=" + current, flush=True)
            path = data / entry["relative_path"]
            if not unchanged(path, entry):
                raise ValueError("active/changed source; wait for writers: " + entry["relative_path"])
            payload = None
            if private_archive:
                # Freeze original bytes, including invalid/incomplete JSON. This is
                # a private evidence archive, never a sanitized Zenodo deposit.
                source_hash = digest(path)
                reason = None
                if path.suffix.lower() in TEXT and entry["bytes"] <= MAX_TEXT:
                    if SECRET.search(path.read_bytes()):
                        reason = "possible_credential_requires_private_review"
            elif path.suffix.lower() in TEXT and entry["bytes"] <= MAX_TEXT:
                payload, reason = public_text(path, data, repo)
                source_hash = digest(path)
            else:
                source_hash, suspect = inspect_binary(path)
                reason = "opaque_or_large_file_contains_path_or_credential_marker" if suspect else None
            if reason:
                withheld.append({"relative_path": entry["relative_path"], "reason": reason,
                                 "source_sha256": source_hash, "bytes": entry["bytes"]})
                continue
            public_size = len(payload) if payload is not None else entry["bytes"]
            if public_size > chunk:
                raise ValueError("single file exceeds archive target; increase --part-gb after reviewing it")
            if active is None or active["group"] != entry["group"] or active["payload_bytes"] + public_size > chunk:
                if tar:
                    close_part()
                group = entry["group"]
                part[group] = part.get(group, 0) + 1
                name = f"cfl-{group}-part{part[group]:03d}.tar.gz"
                active = {"file": name, "group": group, "payload_bytes": 0, "members": []}
                tar = tarfile.open(upload / name, "w:gz", compresslevel=1)
            public_hash = hashlib.sha256(payload).hexdigest() if payload is not None else source_hash
            info = tarfile.TarInfo(entry["relative_path"])
            info.size, info.mode, info.mtime = public_size, 0o644, 0
            info.uid = info.gid = 0
            if payload is not None:
                tar.addfile(info, io.BytesIO(payload))
            else:
                with path.open("rb") as stream:
                    tar.addfile(info, stream)
            if not unchanged(path, entry):
                raise ValueError("source changed during collection; archive is not publication-ready")
            row = {"relative_path": entry["relative_path"], "source_sha256": source_hash,
                   "public_sha256": public_hash, "public_bytes": public_size,
                   "transformed": public_hash != source_hash, "archive": active["file"]}
            active["members"].append(row)
            active["payload_bytes"] += public_size
            manifest.append(row)
        close_part()
    except Exception as error:
        dump(output / "collection_failure.json", {"relative_path": current,
            "error_type": type(error).__name__, "completed_parts": len(packages),
            "originals_modified": False, "resume_requires_unchanged_snapshot": True})
        raise
    finally:
        if tar:
            tar.close()
    if not packages:
        raise ValueError("no shareable research files collected")
    for archive in packages:
        path = upload / archive["file"]
        archive["sha256"], archive["bytes"] = digest(path), path.stat().st_size
        if archive["bytes"] > 49_000_000_000:
            raise ValueError("individual archive exceeds safe upload size")
    if any(not unchanged(data / row["relative_path"], row) for row in files):
        raise ValueError("source snapshot changed before finalization; preserve parts for review")
    dump(upload / "manifest.json", {"schema_version": 1, "files": manifest})
    dump(upload / "withheld_files.json", {"files": withheld})
    readme = """# CFL research archive\n\nIndependent tar.gz parts retain data-relative paths. Extract each part into the same empty directory (no cat/split reconstruction). manifest.json records SHA256 of source and public bytes. Text redactions do not overwrite the source dataset. Original contracts may retain source hashes: use the mapping, not a claim that transformed public bytes match original contract hashes.\n\nThis archive retains favorable, unfavorable and incomplete research outcomes; inclusion does not establish label eligibility, statistical significance or solver improvement. Binary objects were hashed and scanned for obvious path/credential markers, not deserialized or comprehensively certified. Never load untrusted PyTorch/pickle files. Withheld paths are listed explicitly; omissions prevent a claim of complete archival coverage until reviewed.\n\nProject-owned additions use the repository MIT License. Third-party benchmark-derived content retains applicable upstream rights and attribution; an MIT label does not replace them. Include upstream notices and review dataset redistribution rights before publication. No solver executable, licence file or raw benchmark pickle is intentionally included.\n\nNo upload or publication was performed by this collector. Review quota, manifests, licence provenance and privacy before uploading. Keep package_report.json and this script with the local provenance records.\n"""
    if private_archive:
        readme = "# Private MVP 1.0 evidence archive\n\nNOT FOR UPLOAD. Original evidence bytes are retained, including malformed JSON, local paths and opaque binary objects. Invalid structured artifacts are listed in package_report.json; their inclusion does not validate their contents. Raw benchmark inputs and credential-named files/directories are excluded. Binary privacy is not certified. Review withheld_files.json before claiming full coverage. SHA256SUMS.txt, manifest.json and the archive verification receipt identify the frozen bytes. No upload, publication, solver or training was performed. Retain adverse and incomplete results.\n"
    (upload / "README.md").write_text(readme, encoding="utf-8")
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (repo / name).is_file():
            shutil.copyfile(repo / name, upload / "PROJECT_LICENSE.txt")
            break
    sidecars = {p.name: digest(p) for p in upload.iterdir() if p.is_file() and not p.name.endswith(".tar.gz") and ".incomplete-" not in p.name}
    report = {"schema_version": 2, "packages": packages,
              "included_files": len(manifest), "withheld_entries": len(withheld),
              "transformed_text_files": sum(row["transformed"] for row in manifest),
              "binary_content_privacy_certified": False, "source_files_modified": False,
              "declared_quota_bytes": quota, "publication_authorized": False,
              "coverage": "review_withheld_files_before_claiming_complete",
              "upload_performed": False}
    report.update({"private_archive": private_archive,
        "upload_ready": False, "snapshot_sha256": signature,
        "invalid_structured_artifacts": preflight,
        "archival_coverage_complete_for_discovered_files": len(manifest) + sum("source_sha256" in r for r in withheld) == len(files) and not any("source_sha256" in r for r in withheld),
        "sidecar_sha256": sidecars})
    dump(output / "package_report.json", report)
    dump(upload / "package_report.json", report)
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (repo / name).is_file():
            shutil.copyfile(repo / name, upload / "PROJECT_LICENSE.txt")
            break
    # Flat list is directly compatible with Linux sha256sum -c.
    members = sorted(p for p in upload.iterdir() if p.is_file() and ".incomplete-" not in p.name)
    if sum(p.stat().st_size for p in members) > quota or len(members) + 1 > 100:
        raise ValueError("upload exceeds declared record quota or file-count limit; preserve packages")
    (upload / "SHA256SUMS.txt").write_text("".join(f"{digest(p)}  {p.name}\n" for p in members), encoding="utf-8")
    verify(output)
    dump(output / "archive_verification.json", {"archive_and_member_hashes_valid": True,
        "package_report_sha256": digest(output / "package_report.json"),
        "private_archive": private_archive, "upload_performed": False,
        "scientific_reporting_eligible": False})
    print("CFL_MVP_ARCHIVE_HASHES_OK", flush=True)
    print("CFL_ZENODO_PACKAGES_PREPARED_NOT_PUBLICATION_CERTIFIED")
    print("UPLOAD_DIRECTORY=" + str(upload))
    print("WITHHELD_ENTRIES=" + str(len(withheld)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inventory", "package", "verify"))
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quota-gb", type=int, default=50)
    parser.add_argument("--part-gb", type=int, default=8)
    parser.add_argument("--private-archive", action="store_true", help="freeze original evidence bytes; NOT upload-ready")
    parser.add_argument("--resume", action="store_true", help="resume only completed journaled parts under an unchanged snapshot")
    args = parser.parse_args()
    data, repo, output = args.data_root.resolve(), args.repo_root.resolve(), args.output.resolve()
    if not data.is_dir() or not repo.is_dir():
        parser.error("source data and repository must exist")
    if output == data or output.is_relative_to(data) or output == repo or output.is_relative_to(repo):
        parser.error("staging must be outside source data/repository")
    if args.quota_gb < 1 or not 1 <= args.part_gb <= 40:
        parser.error("positive quota and archive parts between 1 and 40 decimal GB required")
    output.mkdir(parents=True, exist_ok=True)
    if args.mode == "inventory":
        if (output / "inventory.json").exists():
            parser.error("preserve earlier inventory; use a fresh output directory")
        write_inventory(data, output)
    elif args.mode == "package":
        package(data, repo, output, args.quota_gb * 1_000_000_000, args.part_gb * 1_000_000_000,
                private_archive=args.private_archive, resume=args.resume)
    else:
        verify(output)


if __name__ == "__main__":
    main()
