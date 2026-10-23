"""Resolve the installed M13/M26 metadata and nearby caches without optimization."""

import argparse
import gzip
import io
import json
import math
from pathlib import Path

import inventory_e0_medium as inventory

meta, require, Reader = inventory.meta, inventory.require, inventory.Reader
SHA = "9e73c05c776b12dc2b8132c8904cc462b9ce90735e4ebea74101d15537ad08b9"
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = "e0_medium_pinned_semantic_inspection_v1"
NEIGHBORS = (
    "preparation.json",
    "root_features.json.gz",
    "label_free_graph.pt",
    "predictions.json.gz",
)
NUMERIC = {
    "schema_version",
    "status",
    "runtime",
    "node_count",
    "variable_count",
    "num_vars",
    "num_constrs",
    "num_binary",
    "num_integer",
    "num_continuous",
    "num_nonzeros",
    "solution_count",
    "num_solutions_found",
    "num_incumbents_collected",
    "num_nodes_collected",
    "execution_time_seconds",
    "preparation_wall_time_seconds",
    "root_objective_bound",
    "Threads",
    "Seed",
    "Presolve",
    "NodeLimit",
    "TimeLimit",
}
BOOLEANS = {
    "target_labels_loaded",
    "warm_start_supplied",
    "fresh_process",
    "root_lp_feature_exactly_encoded",
    "valid",
}
HASHES = {
    "source_mip_sha256",
    "mip_sha256",
    "candidate_sha256",
    "checkpoint_sha256",
    "contract_sha256",
    "vector_sha256",
    "variable_order_sha256",
    "solver_parameter_sha256",
}
ENUMS = {
    "capture_method": {"first_optimal_root_gurobi_mipnode"},
    "authority": {"gurobi", "scip"},
    "objective_sense": {"MINIMIZE", "MAXIMIZE", "minimize", "maximize"},
    "original_objective_sense": {"MINIMIZE", "MAXIMIZE", "minimize", "maximize"},
    "effective_objective_sense": {"MINIMIZE", "MAXIMIZE", "minimize", "maximize"},
    "solve_status": {"OPTIMAL", "TIME_LIMIT", "INFEASIBLE", "INTERRUPTED", "MEM_LIMIT"},
    "gate_status": {"passed", "failed", "inconclusive"},
}
SECTIONS = (
    "model",
    "solve",
    "parameters",
    "solver_parameter_map",
    "feature_audit",
    "summary",
    "metadata",
)
ARRAYS = (
    "variables",
    "variable_names",
    "relaxation_vector",
    "predictions",
    "assignments",
    "named_variables",
    "records",
)


def scalars(value):
    """No free text, names, paths, target assignments or unknown keys leave HPC."""
    result = {}
    for key, item in value.items():
        if key in NUMERIC and type(item) in (int, float) and math.isfinite(item):
            result[key] = item
        elif key in BOOLEANS and type(item) is bool:
            result[key] = item
        elif key in HASHES and isinstance(item, str) and meta.HASH.fullmatch(item):
            result[key] = item
        elif key in ENUMS and isinstance(item, str) and item in ENUMS[key]:
            result[key] = item
    return result


def profile(value, parent, mip_sha):
    require(isinstance(value, dict), "json_object_required")
    names, vector = value.get("variable_names"), value.get("relaxation_vector")
    root_checks = None
    if names is not None or vector is not None or "capture_method" in value:
        names_ok = (
            isinstance(names, list)
            and bool(names)
            and all(isinstance(n, str) and n for n in names)
            and len(set(names)) == len(names)
        )
        vector_ok = (
            isinstance(vector, list)
            and bool(vector)
            and all(type(v) in (int, float) and math.isfinite(v) for v in vector)
        )
        root_checks = {
            "source_mip_matches": value.get("source_mip_sha256") == mip_sha,
            "capture_method_matches": value.get("capture_method")
            == "first_optimal_root_gurobi_mipnode",
            "minimize_declared": value.get("effective_objective_sense") == "MINIMIZE",
            "authority_gurobi": value.get("authority") == "gurobi",
            "unique_names_and_finite_vector": bool(names_ok and vector_ok),
            "length_matches": bool(
                names_ok
                and vector_ok
                and len(names) == len(vector) == value.get("variable_count")
            ),
            "names_hash_matches": bool(
                names_ok
                and meta.digest(meta.canonical(names))
                == value.get("variable_order_sha256")
            ),
            "vector_hash_matches": bool(
                vector_ok
                and meta.digest(meta.canonical(vector)) == value.get("vector_sha256")
            ),
            "root_node_zero": type(value.get("node_count")) in (int, float)
            and value["node_count"] == 0,
        }
    identities = [
        value[k]
        for k in ("source_instance_id", "parent_instance_id", "instance")
        if k in value
    ]
    return {
        "top_level_fields_count": len(value),
        "declared_parent_matches": all(v == parent for v in identities)
        if identities
        else None,
        "scalars": scalars(value),
        "sections": {
            k: scalars(value[k]) for k in SECTIONS if isinstance(value.get(k), dict)
        },
        "array_lengths_only": {
            k: len(value[k]) for k in ARRAYS if isinstance(value.get(k), (list, dict))
        },
        "root_checks": root_checks,
        "root_self_consistent_candidate": bool(
            root_checks and all(root_checks.values())
        ),
        "root_model_variable_order_rechecked": False,
        "content_admitted_for_inference": False,
    }


def collect(data_root, inventory_directory, output):
    source = ROOT / "docs/evidence/e0/medium-inventory.json"
    frozen = inventory.validate(source.read_bytes(), SHA)
    require(
        frozen["state"] == "bounded_inventory_complete"
        and len(frozen["candidates"]) == 10,
        "reviewed_inventory",
    )
    stage = Path(inventory_directory)
    require(
        not any(p.is_symlink() for p in [stage, *stage.parents]), "inventory_symlink"
    )
    require(
        meta.digest((stage / "inventory.json").read_bytes()) == SHA,
        "installed_inventory_changed",
    )
    index_path = stage / "private_paths.json"
    require(
        not index_path.is_symlink() and index_path.stat().st_size < 65536,
        "private_index",
    )
    paths = meta.strict_json(index_path.read_bytes())
    require(
        isinstance(paths, dict)
        and set(paths) == {r["artifact_id"] for r in frozen["candidates"]},
        "private_index_members",
    )
    reader = Reader(data_root, seconds=180, max_bytes=256 * 1024**2)
    output = Path(output).resolve()
    require(
        not output.exists()
        and not output.is_relative_to(reader.root)
        and not reader.root.is_relative_to(output),
        "fresh_output_outside_data",
    )
    pinned_paths, originals = {}, {}
    for row in frozen["candidates"]:
        path = reader.safe(Path(paths[row["artifact_id"]]))
        require(
            meta.digest(path.relative_to(reader.root).as_posix().encode())
            == row["artifact_id"],
            "private_index_binding",
        )
        reader.verify(path, row["sha256"])
        require(path.stat().st_size == row["bytes"], "pinned_size")
        pinned_paths[row["artifact_id"]] = path
        if row["kind"] == "original_milp_bytes":
            originals[row["parent"]] = row["sha256"]
    require(set(originals) == set(inventory.PARENTS), "two_originals")
    profiles, caches, failures, private = [], [], [], {}
    decoded_total = 0

    def inspect(parent, path, origin):
        nonlocal decoded_total
        reader.safe(path)
        artifact_id = meta.digest(path.relative_to(reader.root).as_posix().encode())
        key = parent + ":" + artifact_id
        if key in private:
            return
        require(len(private) < 64, "candidate_limit")
        sha = reader.read(path)
        private[key] = str(path)
        item = {
            "parent": parent,
            "artifact_id": artifact_id,
            "sha256": sha,
            "bytes": path.stat().st_size,
            "origin": origin,
        }
        if path.name == "label_free_graph.pt":
            caches.append(
                {**item, "kind": "label_free_graph_bytes_only", "deserialized": False}
            )
            return
        raw = reader.read(path, content=True)
        require(meta.digest(raw) == sha, "artifact_changed_before_decode")
        if path.name.endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as zipped:
                raw = zipped.read(64 * 1024**2 + 1)
        decoded_total += len(raw)
        require(
            len(raw) <= 64 * 1024**2 and decoded_total <= 128 * 1024**2,
            "decoded_byte_limit",
        )
        value = meta.strict_json(raw)
        profiles.append({**item, **profile(value, parent, originals[parent])})

    # No repeat traversal: inspect the eight pinned JSONs and four known sibling names.
    for row in frozen["candidates"]:
        if row["kind"] == "original_milp_bytes":
            continue
        path = pinned_paths[row["artifact_id"]]
        candidates = [(path, "pinned_inventory")]
        candidates.extend(
            (path.parent / name, "known_sibling")
            for name in NEIGHBORS
            if (path.parent / name).exists() or (path.parent / name).is_symlink()
        )
        for candidate, origin in candidates:
            try:
                inspect(row["parent"], candidate, origin)
            except (ValueError, OSError, EOFError) as error:
                failures.append(
                    {
                        "parent": row["parent"],
                        "origin": origin,
                        "exception_type": type(error).__name__,
                        "private_text_included": False,
                    }
                )
    value = {
        "protocol_id": PROTOCOL,
        "source_inventory_sha256": SHA,
        "collector_sha256_lf": meta.digest(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ),
        "state": "partial" if failures else "scoped_inspection_complete",
        "pinned_files_hash_verified": 10,
        "profiles": profiles,
        "opaque_caches": caches,
        "failures": failures,
        "bytes_read": reader.bytes_read,
        "decoded_bytes": decoded_total,
        "no_dataset_rescan": True,
        "absence_proven": False,
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "forwards_added": 0,
        "scheduler_queries": 0,
        "submissions_added": 0,
        "label_values_used_for_start_selection": False,
        "solver_execution_admitted": False,
        "inference_admitted": False,
        "raw_paths_included": False,
        "raw_content_included": False,
        "scientific_reporting_eligible": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "private_bindings.json").write_bytes(meta.canonical(private) + b"\n")
    data = (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    (output / "inspection.json").write_bytes(data)
    print("E0_MEDIUM_INSPECTION_SHA256=" + meta.digest(data))
    print("E0_MEDIUM_INSPECTION_OUTPUT=" + str(output))
    print(
        json.dumps(
            {
                "state": value["state"],
                "profiles": len(profiles),
                "root_self_consistent_candidates": sum(
                    p["root_self_consistent_candidate"] for p in profiles
                ),
                "optimization_runs_added": 0,
            }
        )
    )
    return value


def validate(data, expected):
    require(meta.digest(data) == expected, "receipt_hash")
    value = meta.strict_json(data)
    require(
        value["protocol_id"] == PROTOCOL and value["source_inventory_sha256"] == SHA,
        "identity",
    )
    require(
        value["state"] in ("partial", "scoped_inspection_complete")
        and value["pinned_files_hash_verified"] == 10,
        "state",
    )
    for k in (
        "optimization_runs_added",
        "training_runs_added",
        "forwards_added",
        "scheduler_queries",
        "submissions_added",
    ):
        require(type(value[k]) is int and value[k] == 0, "execution_scope")
    for k in (
        "solver_execution_admitted",
        "inference_admitted",
        "raw_paths_included",
        "raw_content_included",
        "scientific_reporting_eligible",
        "absence_proven",
        "label_values_used_for_start_selection",
    ):
        require(value[k] is False, "scope")
    require(
        len(value["profiles"]) + len(value["opaque_caches"]) <= 64, "candidate_limit"
    )
    for row in value["profiles"]:
        require(
            row["parent"] in inventory.PARENTS
            and row["content_admitted_for_inference"] is False,
            "profile_scope",
        )
        require(scalars(row["scalars"]) == row["scalars"], "scalar_allowlist")
        require(
            set(row["sections"]) <= set(SECTIONS)
            and all(scalars(s) == s for s in row["sections"].values()),
            "section_allowlist",
        )
        require(set(row["array_lengths_only"]) <= set(ARRAYS), "arrays")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    col = sub.add_parser("collect")
    for name in ("data-root", "inventory-directory", "output"):
        col.add_argument("--" + name, type=Path, required=True)
    rev = sub.add_parser("review")
    rev.add_argument("--receipt", type=Path, required=True)
    rev.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    if args.command == "collect":
        value = collect(args.data_root, args.inventory_directory, args.output)
    else:
        value = validate(args.receipt.read_bytes(), args.expected_sha256)
        print(
            json.dumps(
                {
                    "state": value["state"],
                    "profiles": len(value["profiles"]),
                    "solver_execution_admitted": False,
                }
            )
        )
        return 0  # A valid partial receipt is retained, not a failed download.
    return 0 if value["state"] == "scoped_inspection_complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
