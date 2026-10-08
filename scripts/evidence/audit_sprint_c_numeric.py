"""Read-only C1 numerical admission evidence; never optimize, train or submit."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import audit_sprint_c_inputs as metadata
from verify_sprint_c_artifacts import AuditStop, Reader

REPO = Path(__file__).resolve().parents[2]
RECEIPT_SHA = "e0b51fce0ad3e207c1f0a72b1b5678c89974f8fe856a1918a7b189b0ae981681"
PROTOCOL = "sprint_c_numeric_readonly_v1"
SECONDS = 900
CHILD_SECONDS = 90
ADDRESS_SPACE = 16 * 1024**3
EXPANDED_JSON_BYTES = 512 * 1024**2
JOB3501_RETURN_SHA = "be0b445bc170c947338304a193c7cedfb693ba5f1b6d905a176cbb8d0179b685"
JOB3501_NUMERIC_SHA = "3b1a806067c18a5302dd5212b2211dfd54d4a443f393e2311f84f72e8cdb18b1"


def require(condition, code):
    if not condition:
        raise AuditStop(code)


def source_receipt():
    with zipfile.ZipFile(REPO / "docs/evidence/pr80-artifacts-receipt.zip") as archive:
        require(archive.namelist() == ["artifacts.json"], "receipt_members")
        raw = archive.read("artifacts.json")
    require(metadata.digest(raw) == RECEIPT_SHA, "receipt_hash")
    return metadata.strict_json(raw)


def selected_parents(receipt):
    result = {}
    for cohort, expected in (("easy", 30), ("mixed", 54)):
        group = receipt["cohorts"][cohort]
        require(group["selected_artifact_bytes_verified"] is True, "prior_gate")
        require(len(group["parents"]) == expected, "parent_count")
        for row in group["parents"]:
            name = row["parent"]
            require(metadata.PARENT.fullmatch(name), "parent_identity")
            if name in result:
                previous = result[name]
                require(
                    all(
                        previous[k] == row[k]
                        for k in ("role", "mip_sha256_declared", "label_gap_declared")
                    )
                    and all(
                        previous[k]["sha256"] == row[k]["sha256"]
                        for k in ("graph", "root", "label")
                    ),
                    "shared_parent_conflict",
                )
            else:
                result[name] = row
    require(len(result) == 54, "unique_parent_count")
    return result


def split_for(parent):
    with (REPO / "configs/splits/cfl_90_seed42_folds.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = [r for r in csv.DictReader(stream) if r["source_instance_id"] == parent]
    require(len(rows) == 1, "canonical_parent_missing")
    fold = int(rows[0]["fold"])
    return fold, "test" if fold == 0 else "validation" if fold == 1 else "train"


def bounded_json_gzip(path, *, maximum=None, observations=None, kind=None):
    limit = EXPANDED_JSON_BYTES if maximum is None else maximum
    require(type(limit) is int and limit > 0, "invalid_expanded_json_limit")
    with gzip.open(path, "rb") as stream:
        raw = stream.read(limit + 1)
    if observations is not None:
        observations[kind] = {
            "expanded_bytes_observed": len(raw),
            "complete": len(raw) <= limit,
            "limit_bytes": limit,
        }
    require(len(raw) <= limit, "expanded_json_limit")
    return metadata.strict_json(raw)


def reuse_job3501(path):
    """Accept only the immutable reviewed return; retain its 30 passed rows."""
    require(Path(path).stat().st_size < 2 * 1024**2, "prior_return_size")
    raw = Path(path).read_bytes()
    require(metadata.digest(raw) == JOB3501_RETURN_SHA, "prior_return_hash")
    package = metadata.strict_json(raw)
    require(package["job_id"] == "3501", "prior_job_identity")
    for item in package["members"].values():
        require(
            metadata.digest(item["text"].encode()) == item["sha256"],
            "prior_member_hash",
        )
    member = package["members"]["numeric/numeric.json"]
    require(member["sha256"] == JOB3501_NUMERIC_SHA, "prior_numeric_hash")
    report = metadata.strict_json(member["text"])
    require(
        report["source_artifact_receipt_sha256"] == RECEIPT_SHA,
        "prior_artifact_selection",
    )
    parents = selected_parents(source_receipt())
    reused = {}
    for parent, row in report["parents"].items():
        if row["state"] != "numeric_checks_passed":
            continue
        require(parent.startswith("CFL_easy_") and parent in parents, "prior_parent")
        require(
            row["parent"] == parent
            and row["role"] == parents[parent]["role"]
            and row["model_sha256"] == parents[parent]["mip_sha256_declared"]
            and row["feasibility"]["valid"] is True
            and row["optimization_runs_added"] == 0,
            "prior_parent_contract",
        )
        reused[parent] = row
    require(len(reused) == 30, "prior_passed_count")
    return reused


def align_vectors(names, root, label, record):
    require(len(names) == len(set(names)), "duplicate_model_names")
    require(
        root.get("source_mip_sha256") == record["mip_sha256_declared"],
        "root_model_identity",
    )
    require(root.get("variable_names") == names, "root_variable_order")
    require(
        root.get("variable_order_sha256") == metadata.digest(metadata.canonical(names)),
        "root_order_hash",
    )
    vector = root["relaxation_vector"]
    require(
        len(vector) == len(names) and all(math.isfinite(x) for x in vector),
        "root_vector",
    )
    require(
        root.get("vector_sha256") == metadata.digest(metadata.canonical(vector)),
        "root_vector_hash",
    )
    require(
        root.get("effective_objective_sense") == "MINIMIZE"
        and root.get("capture_method") == "first_optimal_root_gurobi_mipnode",
        "root_policy",
    )
    require(
        label.get("effective_objective_sense") == "MINIMIZE", "label_objective_sense"
    )
    require(
        label.get("solution_source")
        in {
            "independently_audited_gurobi_confirmation_label",
            "independent_gurobi_optimization",
        },
        "label_source",
    )
    if "source_mip_sha256" in label:
        require(
            label["source_mip_sha256"] == record["mip_sha256_declared"],
            "label_model_identity",
        )
    gap = label["mip_gap_relative"]
    require(
        not isinstance(gap, bool)
        and math.isfinite(gap)
        and 0 <= gap <= 0.1
        and gap == record["label_gap_declared"],
        "label_gap",
    )
    values = {}
    for row in label["variables"]:
        require(
            isinstance(row["name"], str)
            and row["name"] not in values
            and math.isfinite(row["value"]),
            "label_variable_invalid",
        )
        values[row["name"]] = float(row["value"])
    require(set(values) == set(names), "label_variable_identity")
    objective = label.get("solution_objective", label.get("objective"))
    require(objective is not None and math.isfinite(objective), "label_objective")
    return values, vector, objective


def numeric_arrays(model, values, objective):
    """Reuse the production mathematical auditor, independently of solver status."""
    import numpy as np

    sys.path.insert(0, str(REPO / "src"))
    from cfl_gnn.validation.mathematical import validate_linear_solution

    require(
        not any(
            getattr(model, attr)
            for attr in ("NumQConstrs", "NumGenConstrs", "NumQNZs", "NumSOS")
        ),
        "unsupported_model",
    )
    variables, constraints = model.getVars(), model.getConstrs()
    require(all(model.getPWLObj(v) == [] for v in variables), "pwl_objective")
    matrix = model.getA().tocoo()
    arrays = dict(
        values=np.asarray([values[v.VarName] for v in variables]),
        lower=np.asarray([v.LB for v in variables]),
        upper=np.asarray([v.UB for v in variables]),
        types=np.asarray([v.VType for v in variables]),
        objective=np.asarray([v.Obj for v in variables]),
        rows=matrix.row,
        columns=matrix.col,
        coefficients=matrix.data,
        senses=np.asarray([c.Sense for c in constraints]),
        rhs=np.asarray([c.RHS for c in constraints]),
        objective_offset=float(model.ObjCon),
        reported_objective=objective,
    )
    audit = validate_linear_solution(**arrays)
    require(audit["valid"], "label_infeasible")
    return arrays, audit


def encoding(values, logarithmic=True):
    import numpy as np

    values = np.asarray(values, dtype=np.float64)
    require(not np.isnan(values).any(), "nan_source_feature")
    clipped = np.clip(
        np.nan_to_num(values, posinf=60000.0, neginf=-60000.0), -60000.0, 60000.0
    )
    if logarithmic:
        clipped = np.sign(clipped) * np.log1p(np.abs(clipped))
    return clipped.astype(np.float32)


def check_graph_arrays(graph, arrays, root):
    """Compare every encoded entry with its original model/root/label source."""
    import numpy as np

    def array(value):
        return value.detach().cpu().numpy()

    kinds, senses = arrays["types"], arrays["senses"]
    expected_v = np.column_stack(
        [encoding(arrays[k]) for k in ("objective", "lower", "upper")]
        + [(kinds == k).astype(np.float32) for k in ("C", "B", "I")]
        + [encoding(root, False)]
    )
    expected_c = np.column_stack(
        [encoding(arrays["rhs"])]
        + [(senses == s).astype(np.float32) for s in ("<", "=", ">")]
        + [np.ones(len(senses), dtype=np.float32)]
    )

    def same(actual, expected, code):
        require(
            actual.shape == expected.shape
            and np.isfinite(actual).all()
            and np.allclose(actual, expected, rtol=1e-6, atol=1e-6),
            code,
        )

    var, con = graph["variable"], graph["constraint"]
    same(array(var.x), expected_v, "variable_features")
    same(array(con.x), expected_c, "constraint_features")
    require(
        np.array_equal(array(var.x)[:, 6], np.asarray(root, dtype=np.float32)),
        "root_feature_exact",
    )
    same(array(var.y), arrays["values"].astype(np.float32), "graph_labels")
    same(array(var.is_discrete), (kinds != "C").astype(np.float32), "discrete_mask")
    expected_index = np.vstack([arrays["rows"], arrays["columns"]])
    order = np.lexsort((expected_index[1], expected_index[0]))
    expected_coefficients = encoding(arrays["coefficients"])[order]
    for edge_type, reverse in (
        (("constraint", "coef", "variable"), False),
        (("variable", "rev_coef", "constraint"), True),
    ):
        edge = graph[edge_type]
        index = array(edge.edge_index)
        if reverse:
            index = index[::-1]
        require(
            index.dtype.kind in "iu" and index.shape == expected_index.shape,
            "edge_shape",
        )
        actual_order = np.lexsort((index[1], index[0]))
        require(
            np.array_equal(index[:, actual_order], expected_index[:, order]),
            "edge_identity",
        )
        attr = array(edge.edge_attr)
        require(attr.shape == (len(order), 1), "edge_feature_shape")
        same(attr[:, 0][actual_order], expected_coefficients, "edge_coefficients")
    return {
        "variables": len(kinds),
        "constraints": len(senses),
        "nonzeros": len(order),
        "feature_dimensions": [7, 5, 1],
        "all_encoded_entries_compared": True,
        "feature_relative_tolerance": 1e-6,
        "feature_absolute_tolerance": 1e-6,
        "root_feature_exact_float32": True,
        "encoding": "clip_60000_signed_log1p_except_root_onehots_and_dummy",
        "clipped_or_infinite_source_entries": {
            k: int(np.count_nonzero(np.abs(arrays[k]) > 60000))
            for k in ("objective", "lower", "upper", "rhs", "coefficients")
        },
    }


def load_graph(path, expected_sha256):
    """Load only hash-bound internal historical artifacts; not a pickle sandbox."""
    import hashlib

    import torch
    from torch_geometric.data import HeteroData

    require(metadata.HASH.fullmatch(expected_sha256) is not None, "graph_hash_required")
    torch.set_num_threads(1)
    with Path(path).open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
        require(digest.hexdigest() == expected_sha256, "graph_hash_before_load")
        stream.seek(0)
        graph = torch.load(stream, map_location="cpu", weights_only=False)
    require(type(graph) is HeteroData, "unexpected_graph_type")
    return graph, str(torch.__version__)


def worker(data_root, parent):
    """One parent per isolated process, no optimization API call."""
    stage = "resource_limits"
    metadata_sizes = {}
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE, ADDRESS_SPACE))
        resource.setrlimit(resource.RLIMIT_CPU, (CHILD_SECONDS, CHILD_SECONDS))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
        stage = "source_selection"
        record = selected_parents(source_receipt())[parent]
        reader = Reader(data_root, seconds=CHILD_SECONDS, max_bytes=2 * 1024**3)
        reader.scan()
        by_id = {
            metadata.digest(p.relative_to(reader.root).as_posix().encode()): p
            for p in reader.files
        }
        paths = {}
        for kind in ("graph", "root", "label"):
            descriptor = record[kind]
            path = by_id[descriptor["artifact_id"]]
            require(
                reader.verify(path, descriptor["sha256"])["bytes"]
                == descriptor["bytes"],
                "artifact_size",
            )
            paths[kind] = path
        from collect_class_statistics import original_model

        difficulty, index = parent.split("_")[1], int(parent.rsplit("_", 1)[1])
        model_path, model_status = original_model(
            reader.root / "raw/MILPBench/CFL", difficulty, index
        )
        require(model_status == "source_discovered", "model_missing_or_ambiguous")
        reader.verify(model_path, record["mip_sha256_declared"])
        stage = "trusted_graph_load"
        graph, torch_version = load_graph(paths["graph"], record["graph"]["sha256"])
        stage = "compressed_metadata"
        root, label = (
            bounded_json_gzip(paths[k], observations=metadata_sizes, kind=k)
            for k in ("root", "label")
        )
        stage = "read_model_no_optimization"
        from collect_class_statistics import ModelReader

        reader_model = ModelReader()
        try:
            with reader_model.gp.read(str(model_path), env=reader_model.env) as model:
                stage = "variable_identity_and_label"
                values, vector, objective = align_vectors(
                    [v.VarName for v in model.getVars()], root, label, record
                )
                arrays, feasibility = numeric_arrays(model, values, objective)
                stage = "graph_identity"
                fold, role = split_for(parent)
                require(role == record["role"], "split_role")
                for key, expected in {
                    "sample_id": parent,
                    "source_instance_id": parent,
                    "parent_instance_id": parent,
                    "role": role,
                    "instance_fold": fold,
                    "graph_authority": "gurobi",
                    "label_source_solver": "gurobi",
                    "objective_sense": "MINIMIZE",
                    "root_lp_relaxation_vector_sha256": root["vector_sha256"],
                }.items():
                    require(getattr(graph, key, None) == expected, "graph_identity")
                require(
                    graph.mip_gap == record["label_gap_declared"], "graph_label_gap"
                )
                stage = "numerical_representation"
                features = check_graph_arrays(graph, arrays, vector)
                import numpy as np

                discrete = arrays["types"] != "C"
                features.update(
                    binary_variables=int(np.count_nonzero(arrays["types"] == "B")),
                    integer_variables=int(np.count_nonzero(arrays["types"] == "I")),
                    continuous_variables=int(np.count_nonzero(arrays["types"] == "C")),
                    discrete_targets=int(discrete.sum()),
                    positive_discrete_targets=int(
                        np.count_nonzero(arrays["values"][discrete] > 0.5)
                    ),
                    density=features["nonzeros"]
                    / max(1, features["variables"] * features["constraints"]),
                )
                source_sense = int(model.ModelSense)
        finally:
            reader_model.close()
        stage = "final_artifact_identity"
        for kind, path in paths.items():
            reader.verify(path, record[kind]["sha256"])
        reader.verify(model_path, record["mip_sha256_declared"])
        return {
            "parent": parent,
            "state": "numeric_checks_passed",
            "role": role,
            "feasibility": feasibility,
            "representation": features,
            "source_objective_sense": source_sense,
            "effective_objective_sense": "MINIMIZE",
            "torch_version": torch_version,
            "gurobi_version": reader_model.version,
            "label_gap_declared_not_resolved": record["label_gap_declared"],
            "model_sha256": record["mip_sha256_declared"],
            "bytes_hashed": reader.bytes_read,
            "metadata_sizes": metadata_sizes,
            "optimization_runs_added": 0,
        }
    except Exception as error:
        from sprint_c_runtime import versions

        return {
            "parent": parent,
            "state": "unqualified",
            "package_versions": versions(),
            "stage": stage,
            "metadata_sizes": metadata_sizes,
            "reason": str(error)
            if isinstance(error, AuditStop)
            else "dependency_or_data_check_failed",
            "exception_type": type(error).__name__,
            "private_text_included": False,
            "optimization_runs_added": 0,
        }


def collect(data_root, output, *, prior_return=None):
    require(sys.platform == "linux", "linux_operator_required")
    data_root, output = Path(data_root).resolve(strict=True), Path(output).resolve()
    require(
        not output.exists() and not output.is_relative_to(data_root),
        "unsafe_or_existing_output",
    )
    receipt = source_receipt()
    parents = selected_parents(receipt)
    output.mkdir()
    started = time.monotonic()
    results = reuse_job3501(prior_return) if prior_return is not None else {}
    reused_parents = sorted(results)
    environment = dict(
        os.environ,
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        PYTHONDONTWRITEBYTECODE="1",
    )
    for parent in sorted(parents):
        if parent in results:
            continue
        remaining = SECONDS - (time.monotonic() - started)
        if remaining <= 1:
            break
        target = output / (parent + ".json")
        command = [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "worker",
            "--data-root",
            str(data_root),
            "--output",
            str(target),
            "--parent",
            parent,
        ]
        try:
            result = subprocess.run(
                command,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=min(CHILD_SECONDS, remaining),
                check=False,
            )
            if (
                result.returncode
                or not target.is_file()
                or target.stat().st_size > 128 * 1024
            ):
                row = {
                    "parent": parent,
                    "state": "child_failed",
                    "returncode": result.returncode,
                }
            else:
                row = metadata.strict_json(target.read_bytes())
                require(
                    row["parent"] == parent and row["optimization_runs_added"] == 0,
                    "child_identity",
                )
        except subprocess.TimeoutExpired:
            row = {"parent": parent, "state": "child_timeout"}
        results[parent] = row
        print(json.dumps({"parent": parent, "state": row["state"]}), flush=True)
        # An unavailable runtime is not a reason to repeat 53 identical failures.
        if (
            row.get("stage")
            in {
                "resource_limits",
                "restricted_graph_load",
                "trusted_graph_load",
                "read_model_no_optimization",
            }
            and row["state"] != "numeric_checks_passed"
        ):
            break
    for parent in parents:
        results.setdefault(
            parent, {"parent": parent, "state": "not_attempted_after_stop"}
        )
    report = {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "graph_loading_policy": "hash_bound_internal_artifacts_historical_pickle",
        "minimum_torch_version_gate": False,
        "source_artifact_receipt_sha256": RECEIPT_SHA,
        "implementation_sha256": metadata.digest(Path(__file__).read_bytes()),
        "dependency_sha256": {
            name: metadata.digest((REPO / name).read_bytes())
            for name in (
                "scripts/evidence/audit_sprint_c_inputs.py",
                "scripts/evidence/verify_sprint_c_artifacts.py",
                "scripts/evidence/collect_class_statistics.py",
                "scripts/evidence/collect_computational_ledger.py",
                "scripts/evidence/publish_mvp2_baseline.py",
                "src/cfl_gnn/validation/mathematical.py",
                "configs/splits/cfl_90_seed42_folds.csv",
            )
        },
        "parents": results,
        "reused_parent_observations": reused_parents,
        "prior_return_sha256": JOB3501_RETURN_SHA if reused_parents else None,
        "prior_numeric_sha256": JOB3501_NUMERIC_SHA if reused_parents else None,
        "new_parent_attempts": sum(
            r["state"] != "not_attempted_after_stop"
            for p, r in results.items()
            if p not in reused_parents
        ),
        "cohorts": {
            name: {
                "numeric_checks_passed": all(
                    results[r["parent"]]["state"] == "numeric_checks_passed"
                    for r in cohort["parents"]
                ),
                "parents": len(cohort["parents"]),
            }
            for name, cohort in receipt["cohorts"].items()
        },
        "elapsed_seconds": time.monotonic() - started,
        "limits": {
            "wall_seconds": SECONDS,
            "child_seconds": CHILD_SECONDS,
            "child_address_space_bytes": ADDRESS_SPACE,
            "cpu_affinity_count": 1,
            "maximum_expanded_json_bytes_per_file": EXPANDED_JSON_BYTES,
        },
        "training_admitted": False,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "raw_logs_included": False,
        "limitations": [
            "declared_gap_not_new_optimality_certificate",
            "root_optimality_not_resolved",
            "historical_training_consumption_not_proven",
            "no_learned_normalization_fit",
            "review_required_before_training_admission",
        ],
    }
    raw = json.dumps(report, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    with (output / "numeric.json").open("xb") as stream:
        stream.write(raw)
    print(
        json.dumps(
            {
                "receipt_sha256": metadata.digest(raw),
                "cohorts": report["cohorts"],
                "training_admitted": False,
            }
        )
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "worker"))
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parent")
    args = parser.parse_args(argv)
    try:
        if args.command == "worker":
            require(
                args.parent in selected_parents(source_receipt()), "parent_not_selected"
            )
            value = worker(args.data_root, args.parent)
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, sort_keys=True, allow_nan=False)
        else:
            collect(args.data_root, args.output)
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "state": "collection_stopped",
                    "reason": str(error)
                    if isinstance(error, AuditStop)
                    else "read_or_contract_failure",
                    "private_text_included": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
