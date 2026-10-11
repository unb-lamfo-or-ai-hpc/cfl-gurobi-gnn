"""Bind ten historical starts without solver, inference, training or submission."""

import argparse
import gzip
import json
import re
from pathlib import Path

import collect_pr85_private_context as lexical
import plan_pr86_comparison as proposal
import prepare_e0_easy_starts as existing

require = proposal.review.require
PROTOCOL = "pr86_ten_historical_start_bindings_v1"
MERGED_PR85 = "bb3f28f8078abde5ed4d95461f04fe675be2f37e"
ZERO = (
    "optimization_runs_added",
    "training_runs_added",
    "forwards_added",
    "scheduler_queries",
    "submissions_added",
)
FALSE = (
    "solver_execution_admitted",
    "resource_budget_approved",
    "scientific_reporting_eligible",
    "prospective_preparation_costs_qualified",
    "raw_predictions_exported",
)
ROW_FIELDS = set(
    (
        "parent role cohort prediction_sha256 selected_support binary_variables "
        "mip_sha256 root_sha256 effective_objective_sense binary_identity_verified "
        "start_feasibility_qualified root_precomputation_seconds positive_assignments "
        "private_starts_sha256 gnn_assignment_sha256 lp_assignment_sha256"
    ).split()
)


def domain(lines, tick=lambda: None):
    """Inspect only explicit binary declarations; not an economic LP parser."""
    section, names, expanded = None, set(), 0
    for raw in lines:
        tick()
        expanded += len(raw)
        require(expanded <= 2 * 1024**3, "lp_expanded_limit")
        text = raw.strip()
        if not text or text.startswith("\\"):
            continue
        header = lexical.HEADERS.get(text.lower())
        if header is not None:
            section = header
            continue
        if section == "binary":
            for name in text.split():
                require(re.fullmatch(lexical.NAME, name) is not None, "binary_name")
                require(name not in names, "duplicate_binary_name")
                names.add(name)
    require(section == "end" and bool(names), "incomplete_binary_domain")
    return names


def bind(payload, row, root, binary):
    names = [p["variable_name"] for p in payload["predictions"]]
    require(len(names) == len(set(names)) and set(names) == binary, "binary_identity")
    require(root["effective_objective_sense"] == "MINIMIZE", "root_sense")
    require(
        root["capture_method"] == "first_optimal_root_gurobi_mipnode", "root_policy"
    )
    require(
        proposal.digest(existing.flow.meta.canonical(root["variable_names"]))
        == root["variable_order_sha256"],
        "root_order_hash",
    )
    require(
        proposal.digest(existing.flow.meta.canonical(root["relaxation_vector"]))
        == root["vector_sha256"],
        "root_vector_hash",
    )
    # Preserve the six-easy implementation and its historical dependency hashes.
    # None of the ten reviewed mixed rows abstained; unexpected abstention stops
    # this binding instead of silently removing the parent from the matrix.
    return existing.assignments(payload, row, root)


def validate(raw, expected_sha):
    require(proposal.digest(raw) == expected_sha, "binding_hash")
    value = existing.flow.meta.strict_json(raw)
    require(
        set(value)
        == {
            "protocol_id",
            "source_inference_sha256",
            "merged_pr85_commit",
            "source_commit",
            "parents",
            "existing_starts_recomputed_and_bound",
            *ZERO,
            *FALSE,
        },
        "public_schema",
    )
    require(value["protocol_id"] == PROTOCOL, "binding_protocol")
    require(value["source_inference_sha256"] == existing.review.SHA, "inference")
    require(value["merged_pr85_commit"] == MERGED_PR85, "audit_merge")
    require(re.fullmatch(r"[0-9a-f]{40}", value["source_commit"]), "source_commit")
    for field in ZERO:
        require(type(value[field]) is int and value[field] == 0, field)
    for field in FALSE:
        require(value[field] is False, field)
    _, rows = existing.review.reviewed()
    sources = {r["parent"]: r for r in rows if r["cohort"] == "mixed"}
    selected = proposal.numeric.selected_parents(proposal.numeric.source_receipt())
    parents = value["parents"]
    require(
        len(parents) == 10
        and [r["parent"] for r in parents] == list(existing.flow.CASES),
        "ten_parents_order",
    )
    for row in parents:
        require(set(row) == ROW_FIELDS, "parent_schema")
        parent = row["parent"]
        source, record = sources[parent], selected[parent]
        for key, expected in {
            "role": "test",
            "cohort": "mixed",
            "prediction_sha256": source["prediction_sha256"],
            "selected_support": source["selected_support"],
            "binary_variables": source["n_targets"],
            "mip_sha256": record["mip_sha256_declared"],
            "root_sha256": record["root"]["sha256"],
            "effective_objective_sense": "MINIMIZE",
            "binary_identity_verified": True,
            "start_feasibility_qualified": False,
            "root_precomputation_seconds": None,
        }.items():
            require(row[key] == expected, "parent_" + key)
        require(
            type(row["positive_assignments"]) is int
            and row["positive_assignments"]
            == min(source["tp"] + source["fp"], source["selected_support"]),
            "positive_support",
        )
        require(
            row["binary_identity_verified"] is True
            and row["start_feasibility_qualified"] is False,
            "parent_flags",
        )
        for key in (
            "private_starts_sha256",
            "gnn_assignment_sha256",
            "lp_assignment_sha256",
        ):
            require(existing.flow.meta.HASH.fullmatch(row[key]), "start_hash")
    require(value["existing_starts_recomputed_and_bound"] is True, "selection")
    return value


def prepare(data_root, inference_stage, output, source_commit):
    require(re.fullmatch(r"[0-9a-f]{40}", source_commit), "source_commit")
    value, all_rows = existing.review.reviewed()
    require(
        proposal.digest((inference_stage / "public_return.json").read_bytes())
        == existing.review.SHA,
        "installed_inference_return",
    )
    output.mkdir(parents=True, exist_ok=False)
    private = output / "private"
    private.mkdir(mode=0o700)
    reader = existing.Reader(data_root, seconds=600, max_bytes=4 * 1024**3)
    reader.scan()
    paths = {
        proposal.digest(p.relative_to(reader.root).as_posix().encode()): p
        for p in reader.files
    }
    admitted = proposal.numeric.selected_parents(proposal.numeric.source_receipt())
    inference = existing.flow.meta.strict_json(
        value["members"]["inference.json"]["text"]
    )
    sources = {r["parent"]: r for r in inference["cases"] if r["cohort"] == "mixed"}
    predictions = existing.Reader(inference_stage, seconds=600, max_bytes=2 * 1024**3)
    public, private_rows = [], []
    for parent in existing.flow.CASES:
        reader.tick()
        row = next(
            r for r in all_rows if r["cohort"] == "mixed" and r["parent"] == parent
        )
        record = admitted[parent]
        filename = f"mixed-{parent}.json"
        require(sources[parent]["prediction_file"] == filename, "prediction_filename")
        pred = inference_stage / "run/predictions" / filename
        predictions.verify(pred, row["prediction_sha256"])
        require(pred.stat().st_size <= 128 * 1024**2, "prediction_size")
        with pred.open("rb") as stream:
            raw = stream.read(128 * 1024**2 + 1)
        require(len(raw) <= 128 * 1024**2, "prediction_size")
        require(proposal.digest(raw) == row["prediction_sha256"], "prediction_changed")
        payload = existing.flow.meta.strict_json(raw)
        del raw
        difficulty = parent.split("_")[1]
        mip, status = existing.originals.original_model(
            reader.root / "raw/MILPBench/CFL", difficulty, int(parent.rsplit("_", 1)[1])
        )
        require(status == "source_discovered", "mip_missing_or_ambiguous")
        reader.verify(mip, record["mip_sha256_declared"])
        opener = gzip.open if mip.suffix == ".gz" else open
        with opener(mip, "rt", encoding="utf-8") as stream:
            binary = domain(lexical.bounded_lines(stream), reader.tick)
        reader.verify(mip, record["mip_sha256_declared"])
        root_path = paths[record["root"]["artifact_id"]]
        reader.verify(root_path, record["root"]["sha256"])
        root = proposal.numeric.bounded_json_gzip(root_path)
        reader.verify(root_path, record["root"]["sha256"])
        require(root["source_mip_sha256"] == record["mip_sha256_declared"], "root_mip")
        gnn, lp = bind(payload, row, root, binary)
        reader.tick()
        starts_sha = existing.flow.legacy.write(
            private / f"{parent}.json", {"gnn": gnn, "root_lp": lp}
        )
        public.append(
            {
                "parent": parent,
                "role": "test",
                "cohort": "mixed",
                "mip_sha256": record["mip_sha256_declared"],
                "root_sha256": record["root"]["sha256"],
                "prediction_sha256": row["prediction_sha256"],
                "private_starts_sha256": starts_sha,
                "gnn_assignment_sha256": gnn["assignment_sha256"],
                "lp_assignment_sha256": lp["assignment_sha256"],
                "binary_variables": len(binary),
                "selected_support": gnn["selected_support"],
                "positive_assignments": gnn["positive_assignments"],
                "binary_identity_verified": True,
                "effective_objective_sense": "MINIMIZE",
                "start_feasibility_qualified": False,
                "root_precomputation_seconds": None,
            }
        )
        private_rows.append(
            {"parent": parent, "mip_path": str(mip), "starts_file": parent + ".json"}
        )
        del payload, root, gnn, lp, binary
    existing.flow.legacy.write(private / "input_paths.json", private_rows)
    receipt = {
        "protocol_id": PROTOCOL,
        "source_commit": source_commit,
        "merged_pr85_commit": MERGED_PR85,
        "source_inference_sha256": existing.review.SHA,
        "parents": public,
        "existing_starts_recomputed_and_bound": True,
        **dict.fromkeys(ZERO, 0),
        **dict.fromkeys(FALSE, False),
    }
    raw = proposal.encoded(receipt)
    validate(raw, proposal.digest(raw))
    sha = existing.flow.legacy.write(output / "binding.json", receipt)
    public_directory = output / "public"
    public_directory.mkdir()
    public_bytes = (output / "binding.json").read_bytes()
    (public_directory / "binding.json").write_bytes(public_bytes)
    (public_directory / "SHA256SUMS.txt").write_text(
        f"{sha}  binding.json\n", encoding="ascii", newline="\n"
    )
    print(
        json.dumps(
            {
                "receipt_sha256": sha,
                "parents": 10,
                "output": str(public_directory),
                "solver_execution_admitted": False,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare_parser = sub.add_parser("prepare")
    for name in ("data-root", "inference-stage", "output"):
        prepare_parser.add_argument("--" + name, type=Path, required=True)
    prepare_parser.add_argument("--source-commit", required=True)
    review_parser = sub.add_parser("review")
    review_parser.add_argument("--receipt", type=Path, required=True)
    review_parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.data_root, args.inference_stage, args.output, args.source_commit)
    else:
        require(args.receipt.stat().st_size <= 1024**2, "receipt_size")
        result = validate(args.receipt.read_bytes(), args.expected_sha256)
        print(
            json.dumps(
                {"parents": len(result["parents"]), "solver_execution_admitted": False}
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "state": "stopped_preserve_output",
                    "exception_type": type(exc).__name__,
                }
            )
        )
        raise SystemExit(2) from None
