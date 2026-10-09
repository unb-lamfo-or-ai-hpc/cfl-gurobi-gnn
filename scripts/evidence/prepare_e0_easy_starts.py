"""Bind existing job3505 mixed starts to six original easy MILPs; no solver."""

import argparse
import json
import sys
from pathlib import Path

import audit_sprint_c_numeric as numeric
import collect_class_statistics as originals
import review_e0_job3505 as review
from verify_sprint_c_artifacts import Reader

flow = review.flow
PROTOCOL = "e0_six_easy_existing_start_binding_v1"


def assignments(payload, row, root):
    sys.path.insert(0, str(flow.c1.ROOT / "src"))
    from cfl_gnn.experiments.pr58_guidance import (
        class_aware_gnn_assignments,
        matched_root_lp_assignments,
    )

    model = flow.plan()["models"]["mixed"]
    for key, expected in {
        "parent": row["parent"],
        "role": "test",
        "cohort": "mixed",
        "checkpoint_sha256": model["checkpoint_sha256"],
        "threshold": model["threshold"],
        "submitted_to_solver": False,
        "target_labels_included": False,
    }.items():
        flow.c1.require(payload[key] == expected, "prediction_identity")
    predictions = payload["predictions"]
    flow.c1.require(len(predictions) == row["n_targets"], "prediction_count")
    flow.c1.require(
        all(
            p["predicted_value"] == int(p["probability"] >= model["threshold"])
            for p in predictions
        ),
        "frozen_threshold",
    )
    gnn = class_aware_gnn_assignments(predictions, fraction=0.1, absolute_cap=20000)
    flow.c1.require(gnn == payload["gnn_partial_start"], "gnn_selection_changed")
    flow.c1.require(
        not gnn["abstained"] and gnn["selected_support"] == row["selected_support"],
        "support",
    )
    names, vector = root["variable_names"], root["relaxation_vector"]
    flow.c1.require(len(names) == len(vector) == len(set(names)), "root_names")
    positions = dict(zip(names, vector))
    prediction_names = [p["variable_name"] for p in predictions]
    lp = matched_root_lp_assignments(
        prediction_names,
        [positions[n] for n in prediction_names],
        support=gnn["selected_support"],
        positive_assignments=gnn["positive_assignments"],
    )
    flow.c1.require(
        lp == payload["root_lp_matched_partial_start"], "lp_selection_changed"
    )
    return gnn, lp


def prepare(data_root, inference_stage, output):
    value, all_rows = review.reviewed()
    flow.c1.require(
        flow.meta.digest((inference_stage / "public_return.json").read_bytes())
        == review.SHA,
        "installed_job3505_return",
    )
    output.mkdir(parents=True, exist_ok=False)
    private = output / "private"
    private.mkdir()
    reader = Reader(data_root, seconds=240, max_bytes=4 * 1024**3)
    reader.scan()
    paths = {
        flow.meta.digest(p.relative_to(reader.root).as_posix().encode()): p
        for p in reader.files
    }
    admitted = numeric.selected_parents(numeric.source_receipt())
    inference = flow.meta.strict_json(value["members"]["inference.json"]["text"])
    source_rows = {r["parent"]: r for r in inference["cases"] if r["cohort"] == "mixed"}
    public, private_rows = [], []
    for parent in review.EASY:
        row = next(
            r for r in all_rows if r["cohort"] == "mixed" and r["parent"] == parent
        )
        record = admitted[parent]
        source = source_rows[parent]
        filename = f"mixed-{parent}.json"
        flow.c1.require(source["prediction_file"] == filename, "prediction_filename")
        pred = inference_stage / "run/predictions" / filename
        flow.c1.require(
            not any(p.is_symlink() for p in [pred, *pred.parents]), "prediction_symlink"
        )
        flow.c1.require(pred.stat().st_size <= 128 * 1024**2, "prediction_size")
        data = pred.read_bytes()
        flow.c1.require(
            flow.meta.digest(data) == row["prediction_sha256"], "prediction_hash"
        )
        payload = flow.meta.strict_json(data)
        mip, status = originals.original_model(
            reader.root / "raw/MILPBench/CFL", "easy", int(parent.rsplit("_", 1)[1])
        )
        flow.c1.require(status == "source_discovered", "mip_missing_or_ambiguous")
        reader.verify(mip, record["mip_sha256_declared"])
        root_path = paths[record["root"]["artifact_id"]]
        reader.verify(root_path, record["root"]["sha256"])
        root = numeric.bounded_json_gzip(root_path)
        flow.c1.require(
            root["source_mip_sha256"] == record["mip_sha256_declared"], "root_mip"
        )
        gnn, lp = assignments(payload, row, root)
        starts_sha = flow.legacy.write(
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
                "selected_support": gnn["selected_support"],
                "positive_assignments": gnn["positive_assignments"],
                "start_feasibility_qualified": False,
                "root_precomputation_seconds": None,
            }
        )
        private_rows.append(
            {"parent": parent, "mip_path": str(mip), "starts_file": f"{parent}.json"}
        )
        del data, payload, root, gnn, lp
    flow.legacy.write(private / "input_paths.json", private_rows)
    receipt = {
        "protocol_id": PROTOCOL,
        "source_inference_sha256": review.SHA,
        "proposal": review.proposal(),
        "parents": public,
        "existing_starts_recomputed_and_bound": True,
        "optimization_runs_added": 0,
        "training_runs_added": 0,
        "forwards_added": 0,
        "scheduler_queries": 0,
        "submissions_added": 0,
        "raw_predictions_exported": False,
        "solver_execution_admitted": False,
        "scientific_reporting_eligible": False,
    }
    sha = flow.legacy.write(output / "binding.json", receipt)
    print(f"E0_BINDING_SHA256={sha}\nE0_BINDING_OUTPUT={output}")


def validate(data, expected_sha):
    flow.c1.require(flow.meta.digest(data) == expected_sha, "binding_hash")
    value = flow.meta.strict_json(data)
    flow.c1.require(
        value["protocol_id"] == PROTOCOL
        and value["source_inference_sha256"] == review.SHA,
        "binding_identity",
    )
    flow.c1.require(value["proposal"] == review.proposal(), "proposal")
    flow.c1.require(value["existing_starts_recomputed_and_bound"] is True, "selection")
    for field in (
        "optimization_runs_added",
        "training_runs_added",
        "forwards_added",
        "scheduler_queries",
        "submissions_added",
    ):
        flow.c1.require(type(value[field]) is int and value[field] == 0, field)
    for field in (
        "raw_predictions_exported",
        "solver_execution_admitted",
        "scientific_reporting_eligible",
    ):
        flow.c1.require(value[field] is False, field)
    flow.c1.require(
        len(value["parents"]) == 6
        and {r["parent"] for r in value["parents"]} == set(review.EASY),
        "parents",
    )
    _, rows = review.reviewed()
    admitted = numeric.selected_parents(numeric.source_receipt())
    for row in value["parents"]:
        source = next(
            r for r in rows if r["cohort"] == "mixed" and r["parent"] == row["parent"]
        )
        flow.c1.require(
            row["prediction_sha256"] == source["prediction_sha256"]
            and row["selected_support"] == source["selected_support"],
            "prediction_binding",
        )
        flow.c1.require(
            row["mip_sha256"] == admitted[row["parent"]]["mip_sha256_declared"]
            and row["root_sha256"] == admitted[row["parent"]]["root"]["sha256"],
            "source_binding",
        )
        for field in (
            "private_starts_sha256",
            "gnn_assignment_sha256",
            "lp_assignment_sha256",
        ):
            flow.c1.require(
                flow.meta.HASH.fullmatch(row[field]) is not None, "start_hash"
            )
        flow.c1.require(
            row["role"] == "test"
            and row["cohort"] == "mixed"
            and row["start_feasibility_qualified"] is False
            and row["root_precomputation_seconds"] is None,
            "scope",
        )
        flow.c1.require(
            type(row["positive_assignments"]) is int
            and 0 < row["positive_assignments"] <= row["selected_support"],
            "positive_support",
        )
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "review"))
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--inference-stage", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.data_root, args.inference_stage, args.output)
    else:
        flow.c1.require(args.receipt.stat().st_size <= 1024**2, "binding_size")
        result = validate(args.receipt.read_bytes(), args.expected_sha256)
        print(
            json.dumps(
                {
                    "parents": len(result["parents"]),
                    "solver_execution_admitted": False,
                    "state": "bound_existing_starts_no_solver",
                }
            )
        )
