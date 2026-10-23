"""Verify recovery receipts and recompute class summaries without extraction.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import tarfile
from collections import Counter
from pathlib import Path

from collect_class_statistics import FIELDS, FILES
from collect_computational_ledger import OUTPUTS
from publish_mvp2_baseline import PRIVATE

FIRST_SHA256 = "9028296e9574593d2a62be6e20f8ac976dd9519458b8401a87085270a1ded07c"
RECOVERY_SHA256 = "51c82520d8c343d14cd15ebbc425846541f76224fa08bf7fb07941a8ed456286"
CLASSES = ("easy", "medium", "hard")
BASE_MEMBERS = (
    {"source_commit.txt"}
    | {f"ledger/{name}" for name in OUTPUTS | {"SHA256SUMS.txt"}}
    | {f"classes/{name}" for name in FILES | {"SHA256SUMS.txt"}}
)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def read_package(path, expected, recovered):
    require(re.fullmatch(r"[0-9a-f]{64}", expected), "invalid_expected_digest")
    path = Path(path)
    require(path.stat().st_size <= 16 * 1024 * 1024, "package_size_limit")
    payload = path.read_bytes()
    require(sha(payload) == expected, "package_hash_mismatch")
    allowed = BASE_MEMBERS | ({"recovery_receipt.json"} if recovered else set())
    data = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive:
            require(member.name in allowed, "unexpected_archive_member")
            require(member.name not in data, "duplicate_archive_member")
            require(member.isfile(), "nonregular_archive_member")
            require(member.size <= 32 * 1024 * 1024, "member_size_limit")
            data[member.name] = archive.extractfile(member).read()
    require(set(data) == allowed, "incomplete_archive_membership")
    for content in data.values():
        require(not PRIVATE.search(content.decode("utf-8")), "private_text_marker")
    for group, names in (("ledger", OUTPUTS), ("classes", FILES)):
        checks = {}
        for line in data[f"{group}/SHA256SUMS.txt"].decode().splitlines():
            digest, name = line.split("  ", 1)
            require(re.fullmatch(r"[0-9a-f]{64}", digest), "invalid_member_digest")
            require(name not in checks, "duplicate_manifest_entry")
            checks[name] = digest
        require(set(checks) == names, "manifest_membership_mismatch")
        for name, digest in checks.items():
            require(sha(data[f"{group}/{name}"]) == digest, "member_hash_mismatch")
    return data


def load_json(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("nonfinite_json_constant")

    return json.loads(payload, object_pairs_hook=pairs, parse_constant=invalid_constant)


def rows(payload):
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    require(
        len(reader.fieldnames) == len(set(reader.fieldnames)), "duplicate_csv_column"
    )
    result = list(reader)
    require(
        all(None not in row and None not in row.values() for row in result),
        "ragged_csv",
    )
    return result


def number(value):
    result = float(value)
    require(math.isfinite(result) and result >= 0, "invalid_structural_value")
    return result


def close(value, expected):
    return math.isclose(number(value), expected, rel_tol=1e-12, abs_tol=1e-12)


def verify_classes(data):
    instances = rows(data["classes/class_instance_statistics.csv"])
    expected = {f"CFL_{c}_instance_{i}" for c in CLASSES for i in range(30)}
    require(len(instances) == 90, "incorrect_class_row_count")
    require(
        {r["source_instance_id"] for r in instances} == expected, "incorrect_parent_ids"
    )
    for row in instances:
        require(
            row["source_instance_id"].startswith(f"CFL_{row['difficulty']}_instance_"),
            "class_identity_mismatch",
        )
        require(
            row["status"] == "model_attributes_observed" and not row["error_type"],
            "failed_model_read",
        )
        require(row["source_file_format"] == "lp.gz", "incorrect_source_format")
        require(
            re.fullmatch(r"[0-9a-f]{64}", row["original_lp_sha256"]),
            "invalid_source_digest",
        )
        require(
            row["source_objective_sense"] in {"MINIMIZE", "MAXIMIZE"},
            "invalid_source_sense",
        )
        require(
            row["effective_objective_sense"] == "MINIMIZE", "invalid_effective_sense"
        )
        number(row["model_read_wall_seconds"])
        values = {field: number(row[field]) for field in FIELDS}
        require(
            all(values[f].is_integer() for f in FIELDS[:11]),
            "nonintegral_structural_count",
        )
        n, m, nz = (values[f] for f in FIELDS[:3])
        require(n > 0 and m > 0 and nz <= n * m, "invalid_matrix_dimensions")
        require(
            sum(values[f] for f in FIELDS[3:8]) == n, "variable_type_total_mismatch"
        )
        require(
            sum(values[f] for f in FIELDS[8:11]) == m, "constraint_sense_total_mismatch"
        )
        for field, target in (
            ("density", nz / (n * m)),
            ("mean_variable_degree", nz / n),
            ("mean_constraint_degree", nz / m),
        ):
            require(close(row[field], target), "matrix_derived_feature_mismatch")
        for minimum, maximum in zip(FIELDS[-6::2], FIELDS[-5::2]):
            require(values[minimum] <= values[maximum], "coefficient_range_mismatch")
    summaries = rows(data["classes/class_descriptive_statistics.csv"])
    keys = {(c, f) for c in CLASSES for f in FIELDS}
    require(
        len(summaries) == 60
        and {(r["difficulty"], r["feature"]) for r in summaries} == keys,
        "summary_membership_mismatch",
    )
    for row in summaries:
        values = sorted(
            number(r[row["feature"]])
            for r in instances
            if r["difficulty"] == row["difficulty"]
        )
        count = len(values)
        require(
            (row["expected_parents"], row["observed_parents"], row["missing_parents"])
            == ("30", "30", "0"),
            "summary_coverage_mismatch",
        )
        mean = math.fsum(values) / count
        # Independent arithmetic, not the collector's statistics/summarize function.
        targets = {
            "minimum": values[0],
            "maximum": values[-1],
            "median": (values[14] + values[15]) / 2,
            "mean": mean,
            "sample_standard_deviation": math.sqrt(
                math.fsum((x - mean) ** 2 for x in values) / (count - 1)
            ),
        }
        require(
            all(close(row[f], target) for f, target in targets.items()),
            "descriptive_summary_mismatch",
        )
    report = load_json(data["classes/class_statistics_report.json"])
    required = {
        "schema_version": 1,
        "expected_parents": 90,
        "observed_parents": 90,
        "missing_or_failed_parents": 0,
        "gate_status": "complete_model_read",
        "scope": "label_free_original_linear_model_attributes",
        "source_format_counts": {"lp.gz": 90},
        "source_status_counts": {"model_attributes_observed": 90},
        "source_hash_semantics": "original_stored_file_bytes_including_compression",
        "optimization_runs": 0,
        "training_runs": 0,
        "original_files_modified": False,
        "raw_inputs_copied": False,
        "scientific_reporting_eligible": False,
        "degree_distributions_and_pca_umap_computed": False,
    }
    require(
        all(
            type(report.get(k)) is type(v) and report[k] == v
            for k, v in required.items()
        ),
        "class_report_mismatch",
    )
    return instances


def verify_recovery(
    first, recovered, first_digest=FIRST_SHA256, recovery_digest=RECOVERY_SHA256
):
    old = read_package(first, first_digest, False)
    data = read_package(recovered, recovery_digest, True)
    require(
        all(data[name] == old[name] for name in data if name.startswith("ledger/")),
        "reused_ledger_changed",
    )
    receipt = load_json(data["recovery_receipt.json"])
    required = {
        "schema_version": 1,
        "scope": "class_only_recovery_reusing_unchanged_ledger",
        "ledger_source_commit": old["source_commit.txt"].decode().strip(),
        "classes_source_commit": data["source_commit.txt"].decode().strip(),
        "reused_ledger_report_sha256": sha(old["ledger/ledger_report.json"]),
        "superseded_class_report_sha256": sha(
            old["classes/class_statistics_report.json"]
        ),
        "optimization_runs": 0,
        "training_runs": 0,
    }
    require(
        set(receipt) == set(required)
        and all(
            type(receipt[k]) is type(v) and receipt[k] == v for k, v in required.items()
        ),
        "recovery_provenance_mismatch",
    )
    require(
        all(
            re.fullmatch(r"[0-9a-f]{40}", receipt[k])
            for k in ("ledger_source_commit", "classes_source_commit")
        ),
        "invalid_source_commit",
    )
    for group, script, report_name in (
        ("ledger", "collect_computational_ledger.py", "ledger_report.json"),
        ("classes", "collect_class_statistics.py", "class_statistics_report.json"),
    ):
        report = load_json(data[f"{group}/{report_name}"])
        require(
            report["collector_sha256"]
            == sha(Path(__file__).with_name(script).read_bytes()),
            "collector_source_mismatch",
        )
    instances = verify_classes(data)
    return {
        "schema_version": 1,
        "scope": "recovery_integrity_and_structural_coverage_not_scientific_certification",
        "package_sha256": recovery_digest,
        "first_package_sha256": first_digest,
        "members_verified": len(data),
        "declared_artifacts_verified": 10,
        "text_members_scanned": len(data),
        "unchanged_ledger_members_verified": 8,
        "descriptive_feature_rows_recomputed": 60,
        "descriptive_statistic_values_recomputed": 300,
        "recovery_receipt": receipt,
        "parent_counts": dict(Counter(r["difficulty"] for r in instances)),
        "source_objective_sense_counts": dict(
            Counter(r["source_objective_sense"] for r in instances)
        ),
        "optimization_runs": 0,
        "training_runs": 0,
        "scientific_reporting_eligible": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-package", required=True, type=Path)
    parser.add_argument("--recovered-package", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            verify_recovery(args.first_package, args.recovered_package), indent=2
        )
    )
    print("PR65_RECOVERY_PACKAGE_AND_MEMBER_HASHES_OK")
    print("PR65_RECOVERY_DECLARED_TEXT_SANITIZATION_OK")
    print("PR65_RECOVERY_UNCHANGED_LEDGER_AND_PROVENANCE_OK")
    print("PR65_RECOVERY_90_PARENTS_AND_60_SUMMARIES_OK")
