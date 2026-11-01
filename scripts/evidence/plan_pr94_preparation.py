"""Compile PR94 preparation metadata offline; no scientific execution or release."""

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

CHECKPOINT = "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028"
THRESHOLD = "0.9991843104362488"
PARENTS = tuple("CFL_medium_instance_" + str(i) for i in (5, 6, 9, 13, 20, 26))
ROOT_PARAMETERS = dict(
    Threads=1,
    Seed=42,
    Presolve=0,
    NodeLimit=1,
    TimeLimit=600,
    SoftMemLimit=48,
    OutputFlag=1,
    LogToConsole=0,
)
ARTIFACT_KEYS = (
    "root_sha256",
    "variable_order_sha256",
    "vector_sha256",
    "mathematical_signature_sha256",
    "graph_sha256",
    "prediction_sha256",
    "private_starts_sha256",
    "M1_assignment_sha256",
    "M2_assignment_sha256",
)


def require(value, code):
    if not value:
        raise ValueError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    def reject_constant(value):
        raise ValueError("nonfinite_json_" + value)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_constant,
        object_pairs_hook=unique,
    )


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def hash_value(value):
    require(isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value), "hash")
    return value


def verify_sources(binding, source_root):
    seen = set()
    for item in binding["sources"]:
        relative = Path(item["path"])
        require(
            not relative.is_absolute() and ".." not in relative.parts,
            "source_path",
        )
        require(item["path"] not in seen, "duplicate_source")
        seen.add(item["path"])
        if source_root is not None:
            data = (source_root / relative).read_bytes().replace(b"\r\n", b"\n")
            require(digest(data) == item["sha256_lf"], "source_bytes")
    require(
        {
            "scripts/evidence/pr86_root_preparation.py",
            "src/cfl_gnn/graph/label_free_gurobi.py",
            "src/cfl_gnn/graph/build_dataset.py",
            "src/cfl_gnn/experiments/pr58_guidance.py",
        }
        <= seen,
        "source_coverage",
    )


def budget():
    """Reservation ceilings, not measured consumption, billing or an ETA."""
    stages = [
        dict(
            stage="roots",
            jobs=1,
            wall_seconds_each=7200,
            physical_cores_each=1,
            gpus_each=0,
            memory_mib_each=65536,
            optimization_calls=6,
            optimizer_seconds=3600,
            forward_calls=0,
            children_per_job=6,
            child_deadline_seconds=1140,
        ),
        dict(
            stage="guidance",
            jobs=1,
            wall_seconds_each=3600,
            physical_cores_each=4,
            gpus_each=1,
            memory_mib_each=65536,
            optimization_calls=0,
            optimizer_seconds=0,
            forward_calls=6,
            children_per_job=1,
            child_deadline_seconds=3540,
        ),
        dict(
            stage="evaluation",
            jobs=18,
            wall_seconds_each=14400,
            physical_cores_each=1,
            gpus_each=0,
            memory_mib_each=65536,
            optimization_calls=54,
            optimizer_seconds=194400,
            forward_calls=0,
            children_per_job=3,
            child_deadline_seconds=3780,
        ),
    ]
    wall = sum(s["jobs"] * s["wall_seconds_each"] for s in stages)
    cores = sum(
        s["jobs"] * s["wall_seconds_each"] * s["physical_cores_each"] for s in stages
    )
    return {
        "status": "complete_conditional_reservation_proposal_not_execution_release",
        "stages": stages,
        "jobs_ceiling": sum(s["jobs"] for s in stages),
        "optimization_calls_ceiling": sum(s["optimization_calls"] for s in stages),
        "optimizer_hours_ceiling": sum(s["optimizer_seconds"] for s in stages) / 3600,
        "serial_job_wall_hours_ceiling": wall / 3600,
        "reserved_physical_core_hours_ceiling": cores / 3600,
        "reserved_gpu_hours_ceiling": 1,
        "memory_gib_per_job": 64,
        "reserved_memory_gib_hours_ceiling": wall / 3600 * 64,
        "logical_AllocCPU_hours_if_two_per_physical_core": cores / 1800,
        "logical_AllocCPU_scenario_is_not_verified_billing": True,
        "soft_memory_decimal_GB": 48,
        "cgroup_sampled_interrupt_GiB": 56,
        "job_cgroup_limit_GiB": 64,
        "gpu_device_proposal": "one_Tesla_V100_32GB_same_historical_guidance_class",
        "concurrent_jobs": 1,
        "automatic_retries": 0,
        "training_calls": 0,
        "auxiliary_optimization_calls": 0,
        "private_working_storage_allowance_GiB": 64,
        "free_space_admission_required_GiB": 80,
        "storage_is_proposed_not_reserved_or_installed_guard": True,
        "reuse_of_90_cells_required": True,
        "queue_time_included": False,
        "human_review_time_included": False,
        "financial_or_energy_estimate": None,
        "execution_authorized": False,
    }


def compile_plan(package, source_root=None):
    manifest = read_json(package / "manifest.json")
    require(manifest["execution_authorized"] is False, "unreleased")
    for name, expected in manifest["artifacts"].items():
        require(Path(name).name == name, "artifact_name")
        require(digest((package / name).read_bytes()) == expected, "artifact_bytes")
    require(manifest["learning"]["checkpoint_sha256"] == CHECKPOINT, "checkpoint")
    require(str(manifest["learning"]["threshold"]) == THRESHOLD, "threshold")
    require(manifest["learning"]["split"] == [34, 10, 10], "learning_split")
    source = read_json(package / "source-bindings.json")
    verify_sources(source, source_root)
    receipt = read_json(package / "preflight-return-20261101.json")
    report = receipt["report"]
    require(
        all(
            report[key] == 0
            for key in (
                "optimization_calls_added",
                "inference_calls_added",
                "training_calls_added",
                "scheduler_mutations",
            )
        ),
        "readonly_receipt",
    )
    rows = report["rows"]
    require(
        len(rows) == 6 and {r["parent"] for r in rows} == set(PARENTS),
        "preflight_parents",
    )
    original = {r["parent"]: r for r in rows}
    for row in rows:
        hash_value(row["sha256"])
        require(row["readonly_preflight_complete"] and not row["issues"], "preflight")
        if row["expected_historical_sha256"]:
            require(row["historical_digest_match"] is True, "historical_hash")
    cells = read_csv(package / "planned-cells.csv")
    require(len(cells) == 144, "cell_count")
    require(len({r["evaluation_unit_id"] for r in cells}) == 144, "duplicate_cell")
    require(
        all(
            r["execution_authorized"] == "false" and not r["assigned_job_id"]
            for r in cells
        ),
        "execution_flag",
    )
    require(
        sum(r["identity_compatibility_verified"] == "true" for r in cells) == 90,
        "historical_identity_scope",
    )
    new = [r for r in cells if r["parent"] in original]
    require(len(new) == 54, "new_cell_count")
    groups = {}
    for row in new:
        require(row["model_sha256"] == original[row["parent"]]["sha256"], "input_hash")
        require(
            row["checkpoint_context_sha256"] == CHECKPOINT
            and row["threshold_context"] == THRESHOLD,
            "learning_binding",
        )
        require(
            row["physical_thread_cap"] == "1" and row["solver_limit_seconds"] == "3600",
            "solver_profile",
        )
        require(row["identity_compatibility_verified"] == "false", "new_identity_scope")
        key = (row["parent"], int(row["solver_seed"]))
        groups.setdefault(key, []).append(row)
    require(
        set(groups) == {(parent, seed) for parent in PARENTS for seed in (42, 43, 44)},
        "groups",
    )
    ordered = []
    for (parent, seed), group in groups.items():
        require({r["method"] for r in group} == {"M0", "M1", "M2"}, "methods")
        require(len(group) == 3, "method_count")
        ordered.append(
            dict(
                parent=parent,
                solver_seed=seed,
                methods=[r["method"] for r in group],
                cells=[r["evaluation_unit_id"] for r in group],
            )
        )
    pending = []
    for parent in PARENTS:
        pending.append(
            {
                "parent": parent,
                "model_sha256": original[parent]["sha256"],
                "checkpoint_sha256": CHECKPOINT,
                "threshold": THRESHOLD,
                "binding_state": "original_identified_preparation_not_run",
                "generated": False,
                "execution_admitted": False,
                "artifacts": dict.fromkeys(ARTIFACT_KEYS),
                "same_start_for_solver_seeds": [42, 43, 44],
            }
        )
    contract = {
        "protocol_id": "pr94_preparation_contract_v1",
        "source_binding_sha256": digest(
            (package / "source-bindings.json").read_bytes()
        ),
        "new_source_execution_commit": None,
        "execution_authorized": False,
        "scientific_reporting_eligible": False,
        "root": {
            "maximum_calls": 6,
            "parameters": ROOT_PARAMETERS,
            "effective_objective_sense": "MINIMIZE",
            "capture": "first_OPTIMAL_MIPNODE_with_node_count_zero_then_terminate",
            "relax_or_zero_fallback": False,
            "preserve_model_and_variable_order": True,
        },
        "graph": {
            "implementation": "cfl_gnn.graph.label_free_gurobi.build_features",
            "variable_features": 7,
            "constraint_features": 5,
            "edge_features": 1,
            "root_channel": 6,
            "labels_loaded": False,
            "remove_encoder_placeholder_targets_before_serialization": True,
            "existing_encoder_no_new_normalization_fit": True,
            "new_adapter_feature_and_order_parity_tests_pending": True,
        },
        "inference": {
            "maximum_forwards": 6,
            "checkpoint_sha256": CHECKPOINT,
            "threshold": THRESHOLD,
            "device": "one_V100_32GB_proposal",
            "hidden_dim": 32,
            "num_layers": 2,
            "model_version": "gasse_v2_alternating_prenorm",
            "eval_mode": True,
            "gradients": False,
            "training": False,
            "load_once_process_six_graphs_serially": True,
            "runtime_policy": {
                "torch_seed": 42,
                "torch_num_threads": 1,
                "cudnn_benchmark": False,
                "cudnn_deterministic": True,
                "cuda_matmul_allow_tf32": False,
                "bitwise_reproducibility_claimed": False,
            },
            "module_prefix_handling": "same_as_historical_qualified_loader",
            "no_CPU_fallback": True,
        },
        "Start": {
            "historical_methods": {"B": "M0", "R": "M1", "G": "M2"},
            "support_fraction": 0.1,
            "absolute_cap": 20000,
            "control_R_matches_G_support_and_positive_count": True,
            "preserve_abstention": True,
            "unselected_values": "undefined",
            "variable_fixing": False,
            "seed_specific_reselection": False,
        },
        "ordered_evaluation_groups": ordered,
        "shared_preparation_counted_once_per_parent": True,
        "method_counterfactual_amortization_uses": 3,
        "no_automatic_retry_or_parent_replacement": True,
        "stop_on_failed_or_unqualified_dependency": True,
        "pr89_source_or_artifacts_modified": False,
    }
    return {
        "preparation-contract.json": contract,
        "new-artifact-bindings.json": {"parents": pending, "generated_artifacts": 0},
        "reservation-budget.json": budget(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            compile_plan(args.package, args.source_root), sort_keys=True, indent=2
        )
    )


if __name__ == "__main__":
    main()
