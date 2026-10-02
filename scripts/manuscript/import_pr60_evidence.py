"""Import only the supplied, hash-bound publication evidence; never raw data.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "manuscript"
ARCHIVE_SHA = "792e35ddd0e01e2e0ffc393b308d3580a0dcf0e862aa7ec532be1e54b5ba4927"
CONTRACT = "1a22c76da1f5bc6be978ac6eb7ea340c10b067c5beae1f71aecb617ac09d6b96"
MANIFEST = "pr60_scientific_evidence_manifest.json"
REPORT = "pr60_scientific_evidence_report.json"
REPORT_SHA = "0f7065b6108d39bb8bd779955de7b8f06cc64c6ee147ca684393fc6f568cc338"
MANIFEST_SHA = "e6ae03cedb9338f1a06083e55ab5a502f5da77d95c43327fba39d94e35cf0a9e"
ARTIFACTS = {
    "figure_offline_online_pipeline.svg": "54e836227634f86b8bdad7f4a6fe578caccf9ba013d832a735462b0c80ae8b04",
    "figure_predictive_quality.svg": "63d5967a035b76daaa017f0ed73cc09c5d6ff57c5972b43a7a1f5e6e359216c6",
    "figure_time_to_ten_percent_gap.svg": "93ca7f4318441a463fef5f7d5f01f09e9dbf145b71c25ddcf830a2b4dabef161",
    "figure_training_validation_loss.svg": "ef550b0c856ecba049efdecf8842500021bcee4c620e9441911c7580b2f598b7",
    "figure_validation_test_gap_effects.svg": "8b3e94d70ab96a78228ca93d89d5c5077f6c227d3b063bbc65c3d3351949c797",
    "table_censoring_summary.csv": "67cdb7f8aefde043dab81c27faf8c34ba5900c93755dbb33bbb084d05f04a0d2",
    "table_heldout_influence_analysis.csv": "549eba3a48fce04faae601153804152455fef63d4821b4bb564c7bf88733b8c5",
    "table_paired_gap_effects.csv": "0f97c987ca21ec8d0693e4412392a099759d20564a0e8a7c4d81c0d0905437a5",
    "table_predictive_metrics.csv": "85c42b1e3910e80ed076be942a6787cd5ede7d6a8fa4c3ab2259b87e354559a2",
    "table_solver_outcomes.csv": "5b936dec45576eee6f8473fb22bd46ad616ef10bfed7044459e7bf4a957c6546",
    "table_training_epoch_metrics.csv": "0c098b631b3104fb36cc6668462581ef590954591827d0719aec760cc45ec383",
}
UNSAFE = re.compile(r"/raid/|/home/|(?<![\w])[A-Za-z]:[\\/]|WLSSecret|WLSAccessID|LicenseID|gurobi\.lic")


def verify_payload(payload: dict[str, bytes]) -> None:
    if set(payload) != set(ARTIFACTS) | {MANIFEST, REPORT}:
        raise ValueError("publication evidence file set changed")
    if (hashlib.sha256(payload[REPORT]).hexdigest() != REPORT_SHA
            or hashlib.sha256(payload[MANIFEST]).hexdigest() != MANIFEST_SHA):
        raise ValueError("report or manifest SHA256 mismatch")
    manifest = json.loads(payload[MANIFEST])
    report = json.loads(payload[REPORT])
    if manifest.get("contract_sha256") != CONTRACT or set(manifest.get("artifacts", {})) != set(ARTIFACTS):
        raise ValueError("manifest contract or scope mismatch")
    if (report.get("contract_sha256") != CONTRACT or report.get("gate_status") != "passed"
            or report.get("eligibility", {}).get("scientific_reporting_eligible") is not False
            or report.get("interpretation", {}).get("confirmatory_significance_claim_allowed") is not False):
        raise ValueError("report scope mismatch")
    for name, value in payload.items():
        if UNSAFE.search(value.decode("utf-8")):
            raise ValueError(f"private content: {name}")
        if name in ARTIFACTS:
            descriptor = manifest["artifacts"][name]
            digest = hashlib.sha256(value).hexdigest()
            if (digest != ARTIFACTS[name] or descriptor.get("sha256") != digest
                    or descriptor.get("relative_path") != name
                    or descriptor.get("size_bytes") != len(value)):
                raise ValueError(f"evidence hash, identity, or size mismatch: {name}")


def import_archive(archive: Path, root: Path = ROOT) -> None:
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("supplied archive SHA256 mismatch")
    payload = {}
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            if member.isdir() and member.name in (".", "./"):
                continue
            name = member.name.removeprefix("./")
            if (not member.isfile() or name not in set(ARTIFACTS) | {MANIFEST, REPORT}
                    or name in payload or member.size > 2_000_000):
                raise ValueError("unexpected, duplicate, linked, or oversized archive member")
            payload[name] = source.extractfile(member).read()
    verify_payload(payload)  # No destination writes until every input passes.
    destination = root / "results/current"
    destination.mkdir(parents=True, exist_ok=True)
    for name, value in payload.items():
        path = destination / name
        if path.exists() and path.read_bytes() != value:
            raise ValueError(f"refusing to replace different evidence: {name}")
    for name, value in payload.items():
        (destination / name).write_bytes(value)
    receipt = {"schema_version": 1, "archive_sha256": ARCHIVE_SHA, "contract_sha256": CONTRACT,
               "files": {name: hashlib.sha256(value).hexdigest() for name, value in sorted(payload.items())},
               "source": "author_supplied_PR60_shareable_evidence",
               "research_execution_performed": False, "development_only": True,
               "scientific_reporting_eligible": False}
    (destination / "import_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PR62_CURRENT_EVIDENCE_HASHES_AND_SANITIZATION_OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    import_archive(parser.parse_args().archive)
