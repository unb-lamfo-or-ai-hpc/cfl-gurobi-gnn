"""Read original linear model attributes without optimization or solution labels.

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import statistics
import time
from collections import Counter
from pathlib import Path

from collect_computational_ledger import digest, regular, write_csv, write_json
from publish_mvp2_baseline import PRIVATE

LICENSE = "/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic"
ATTRIBUTES = (
    "NumVars",
    "NumConstrs",
    "DNumNZs",
    "NumBinVars",
    "NumIntVars",
    "NumQConstrs",
    "NumGenConstrs",
    "NumSOS",
    "NumQNZs",
    "MinCoeff",
    "MaxCoeff",
    "MinObjCoeff",
    "MaxObjCoeff",
    "MinRHS",
    "MaxRHS",
)
FIELDS = (
    "variables",
    "constraints",
    "nonzeros",
    "binary_variables",
    "integer_variables",
    "continuous_variables",
    "semicontinuous_variables",
    "semiinteger_variables",
    "constraint_equalities",
    "constraint_less_equal",
    "constraint_greater_equal",
    "density",
    "mean_variable_degree",
    "mean_constraint_degree",
    "min_nonzero_abs_coefficient",
    "max_abs_coefficient",
    "min_nonzero_abs_objective_coefficient",
    "max_abs_objective_coefficient",
    "min_nonzero_abs_rhs",
    "max_abs_rhs",
)
FILES = {
    "class_instance_statistics.csv",
    "class_descriptive_statistics.csv",
    "class_statistics_report.json",
}


def model_statistics(model):
    """No optimize/presolve call. Avoid materializing a second constraint matrix."""
    values = {name: model.getAttr(name) for name in ATTRIBUTES}
    if any(
        values[name] != 0
        for name in ("NumQConstrs", "NumGenConstrs", "NumSOS", "NumQNZs")
    ):
        raise ValueError("nonlinear_or_extended_model_not_supported")
    types = Counter(model.getAttr("VType"))
    senses = Counter(model.getAttr("Sense"))
    if set(types) - {"B", "I", "C", "S", "N"} or set(senses) - {"<", ">", "="}:
        raise ValueError("unknown_variable_type_or_constraint_sense")
    n, m, nz = int(values["NumVars"]), int(values["NumConstrs"]), int(values["DNumNZs"])
    if sum(types.values()) != n or sum(senses.values()) != m or nz < 0 or nz > n * m:
        raise ValueError("inconsistent_model_attributes")
    source_sense = "MINIMIZE" if model.ModelSense == 1 else "MAXIMIZE"
    model.ModelSense = 1
    model.update()
    result = {
        "variables": n,
        "constraints": m,
        "nonzeros": nz,
        "binary_variables": types["B"],
        "integer_variables": types["I"],
        "continuous_variables": types["C"],
        "semicontinuous_variables": types["S"],
        "semiinteger_variables": types["N"],
        "constraint_equalities": senses["="],
        "constraint_less_equal": senses["<"],
        "constraint_greater_equal": senses[">"],
        "density": nz / (m * n) if m and n else None,
        "mean_variable_degree": nz / n if n else None,
        "mean_constraint_degree": nz / m if m else None,
        "source_objective_sense": source_sense,
        "effective_objective_sense": "MINIMIZE",
    }
    for field, attribute in zip(FIELDS[-6:], ATTRIBUTES[-6:]):
        value = values[attribute]
        result[field] = value if math.isfinite(value) else None
    return result


class ModelReader:
    """Exactly the authorized local license; no fallback or credential output."""

    def __init__(self):
        if (
            os.environ.get("GRB_LICENSE_FILE", LICENSE) != LICENSE
            or not Path(LICENSE).is_file()
        ):
            raise ValueError("authorized_license_file_required")
        if any(
            os.environ.get(key)
            for key in ("GRB_WLSACCESSID", "GRB_WLSSECRET", "GRB_LICENSEID")
        ):
            raise ValueError("external_license_credentials_not_allowed")
        os.environ["GRB_LICENSE_FILE"] = LICENSE
        import gurobipy as gp

        self.gp = gp
        self.env = gp.Env(empty=True)
        try:
            self.env.setParam("OutputFlag", 0)
            self.env.setParam("LogFile", "")
            self.env.start()
        except Exception:
            self.env.dispose()
            raise
        self.version = list(gp.gurobi.version())

    def __call__(self, path):
        with self.gp.read(str(path), env=self.env) as model:
            return model_statistics(model)

    def close(self):
        self.env.dispose()


def summarize(rows):
    summaries = []
    for difficulty in ("easy", "medium", "hard"):
        group = [r for r in rows if r["difficulty"] == difficulty]
        for field in FIELDS:
            values = [r[field] for r in group if isinstance(r[field], (int, float))]
            summaries.append(
                {
                    "difficulty": difficulty,
                    "feature": field,
                    "expected_parents": 30,
                    "observed_parents": len(values),
                    "missing_parents": 30 - len(values),
                    "minimum": min(values) if values else None,
                    "median": statistics.median(values) if values else None,
                    "mean": statistics.mean(values) if values else None,
                    "sample_standard_deviation": statistics.stdev(values)
                    if len(values) > 1
                    else None,
                    "maximum": max(values) if values else None,
                }
            )
    return summaries


def original_model(raw_root, difficulty, index):
    """Select one canonical stored LP; never guess between duplicate sources."""
    stem = raw_root / f"CFL_{difficulty}_instance/LP/CFL_{difficulty}_instance_{index}"
    candidates = [Path(str(stem) + suffix) for suffix in (".lp", ".lp.gz")]
    present = [path for path in candidates if path.exists() or path.is_symlink()]
    if not present:
        return None, "missing_lp"
    if len(present) != 1:
        return None, "ambiguous_lp_sources"
    if not regular(present[0], raw_root):
        return None, "unsafe_lp_source"
    return present[0], "source_discovered"


def preflight(raw_root):
    """Require 90 unambiguous originals before submitting a model-reading job."""
    raw_root = Path(raw_root).resolve(strict=True)
    statuses = Counter(
        original_model(raw_root, difficulty, index)[1]
        for difficulty in ("easy", "medium", "hard")
        for index in range(30)
    )
    if statuses["source_discovered"] != 90:
        raise ValueError(
            "original_model_discovery_incomplete: "
            + ", ".join(
                f"{status}={count}" for status, count in sorted(statuses.items())
            )
        )
    return statuses["source_discovered"]


def collect(raw_root, output, reader=None):
    raw_root, output = Path(raw_root).resolve(), Path(output).resolve()
    if (
        not raw_root.is_dir()
        or output.exists()
        or output.is_relative_to(raw_root)
        or raw_root.is_relative_to(output)
    ):
        raise ValueError("use_fresh_output_outside_raw_inputs")
    output.mkdir(parents=True)
    owned = None
    if reader is None:
        owned = ModelReader()
        reader = owned
    rows = []
    try:
        for difficulty in ("easy", "medium", "hard"):
            for i in range(30):
                name = f"CFL_{difficulty}_instance_{i}"
                path, source_status = original_model(raw_root, difficulty, i)
                row = {
                    "source_instance_id": name,
                    "difficulty": difficulty,
                    "original_lp_sha256": None,
                    "source_file_format": None,
                    "status": source_status,
                    "error_type": None,
                    "model_read_wall_seconds": None,
                    "source_objective_sense": None,
                    "effective_objective_sense": None,
                    **dict.fromkeys(FIELDS),
                }
                if path is not None:
                    row["source_file_format"] = (
                        "lp.gz" if path.suffix == ".gz" else "lp"
                    )
                    print(f"PR65_READING_MODEL={name}", flush=True)
                    started = time.perf_counter()
                    try:
                        row["original_lp_sha256"] = digest(path)
                        row.update(reader(path))
                        if digest(path) != row["original_lp_sha256"]:
                            raise ValueError("source_changed_during_read")
                        row["status"] = "model_attributes_observed"
                    except Exception as error:
                        row.update(dict.fromkeys(FIELDS))
                        row.update(
                            status="model_read_failed", error_type=type(error).__name__
                        )
                    row["model_read_wall_seconds"] = time.perf_counter() - started
                rows.append(row)
    finally:
        if owned:
            owned.close()
    write_csv(output / "class_instance_statistics.csv", rows, list(rows[0]))
    summary = summarize(rows)
    write_csv(output / "class_descriptive_statistics.csv", summary, list(summary[0]))
    good = sum(r["status"] == "model_attributes_observed" for r in rows)
    write_json(
        output / "class_statistics_report.json",
        {
            "schema_version": 1,
            "expected_parents": 90,
            "observed_parents": good,
            "missing_or_failed_parents": 90 - good,
            "source_status_counts": dict(Counter(r["status"] for r in rows)),
            "source_format_counts": dict(
                Counter(
                    r["source_file_format"] for r in rows if r["source_file_format"]
                )
            ),
            "source_hash_semantics": "original_stored_file_bytes_including_compression",
            "gate_status": "complete_model_read"
            if good == 90
            else "incomplete_model_read",
            "scope": "label_free_original_linear_model_attributes",
            "reader_version": owned.version if owned else "injected_test_reader",
            "degree_semantics": "mean_degrees_of_original_variable_constraint_incidence_graph",
            "degree_distributions_and_pca_umap_computed": False,
            "optimization_runs": 0,
            "training_runs": 0,
            "raw_inputs_copied": False,
            "original_files_modified": False,
            "scientific_reporting_eligible": False,
            "collector_sha256": digest(Path(__file__)),
        },
    )
    verify(output, True)
    return rows


def verify(output, create=False):
    output = Path(output)
    lines = []
    for name in sorted(FILES):
        if not regular(output / name, output) or PRIVATE.search(
            (output / name).read_text(encoding="utf-8")
        ):
            raise ValueError("class_artifact_missing_or_private_marker_detected")
        lines.append(
            f"{hashlib.sha256((output / name).read_bytes()).hexdigest()}  {name}\n"
        )
    payload = "".join(lines).encode()
    if create:
        if (output / "SHA256SUMS.txt").exists():
            raise ValueError("manifest_already_exists")
        (output / "SHA256SUMS.txt").write_bytes(payload)
    elif (output / "SHA256SUMS.txt").read_bytes() != payload:
        raise ValueError("manifest_mismatch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("collect", "verify", "preflight"))
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "preflight":
        if args.raw_root is None:
            parser.error("--raw-root required for preflight")
        count = preflight(args.raw_root)
        print(f"PR65_ORIGINAL_MODEL_DISCOVERY_OK | parents={count} | solver_runs=0")
        raise SystemExit(0)
    if args.output is None:
        parser.error("--output required for collect or verify")
    if args.action == "collect":
        if args.raw_root is None:
            parser.error("--raw-root required for collection")
        rows = collect(args.raw_root, args.output)
    else:
        verify(args.output)
    print("PR65_CLASS_STATISTICS_HASHES_OK")
    print("PR65_CLASS_STATISTICS_DECLARED_TEXT_SANITIZATION_OK")
    if args.action == "collect" and any(
        row["status"] != "model_attributes_observed" for row in rows
    ):
        raise SystemExit(
            "PR65_CLASS_STATISTICS_INCOMPLETE: preserve diagnostic outputs"
        )
