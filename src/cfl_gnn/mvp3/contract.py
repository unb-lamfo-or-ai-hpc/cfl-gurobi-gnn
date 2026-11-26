"""Offline scientific contract, deterministic parent partition and call ledger."""

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from . import CONTRACT_VERSION

HARD_IDS = (0, 5, 10, 15, 20, 25)
TARGETS = (0.1, 0.05, 0.01, 0.0001)
ROLES = {"easy": (21, 5, 4), "medium": (21, 4, 5)}
METHOD_ORDERS = (("B", "R", "G"), ("R", "G", "B"), ("G", "B", "R"))
SPLIT_ALGORITHM = "sha256-seed42-family-original-id-v1"
CATALOGUE_SHA256 = "1c1735e1f5cd2a5b0a407ca4928c3aef546374eebc4f0d402034e9313274e41a"
CLOCKS = {
    "native_runtime": "optimize_entry",
    "worker_elapsed": "worker_entry",
    "end_to_end": "pipeline_entry",
    "reuse_elapsed": "scenario_entry",
}


class ContractError(ValueError):
    """The supplied artifact does not satisfy the versioned contract."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def canonical_bytes(value):
    """UTF-8, sorted object keys, compact JSON; arrays preserve original order."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ContractError(f"Nonfinite JSON constant: {value}")

    def finite_float(value):
        parsed = float(value)
        require(math.isfinite(parsed), "Nonfinite JSON number")
        return parsed

    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"Invalid JSON: {path}: {error}") from error


def approved_contract():
    """The approved v3 constants, independent of the planning workbook."""
    common = {
        "Method": -1,
        "Threads": 0,
        "ConcurrentMIP": 1,
        "Seed": 42,
        "TimeLimit": 28800,
        "MIPFocus": 0,
    }
    return {
        "schema_version": CONTRACT_VERSION,
        "authority": {
            "protocol_version": 3,
            "protocol_approval_date": "2026-11-23",
            "protocol_pdf_sha256": (
                "3e55df74176b516154bd62bb37a6a28908179b0d59fed676fe3056c15531410e"
            ),
            "protocol_merge": "22d5089f59f7306d97f7d5410f248d6b45ebdc0b",
            "preparation_merge": "b14db3298c051107dc99b0f2087a90e60bbc6fd6",
            "scientific_execution_authorized": False,
        },
        "population": {"easy": 30, "medium": 30, "hard": 6, "total": 66},
        "learning": {
            "seed": 42,
            "split_algorithm": SPLIT_ALGORITHM,
            "train": {"easy": 21, "medium": 21},
            "validation": {"easy": 5, "medium": 4},
            "test": {"easy": 4, "medium": 5},
            "hard_role": "transfer_only",
            "label_tier": "audited_terminal_target",
            "label_gap_maximum": 0.0001,
            "coverage_decision_before_training": True,
            "epochs": 100,
            "presentations_per_parent_per_epoch": 4,
            "global_batch": 4,
            "updates_per_epoch": 42,
            "updates_per_arm": 4200,
            "presentations_per_arm": 16800,
            "serial_gpus": 1,
            "ddp_gpus": 4,
            "gpu_model": "V100-16GB",
            "job_limit_seconds_per_arm": 21600,
            "initial_state_and_global_batches": "identical_across_arms",
            "fitted_transforms_and_class_weights": "training_parents_only",
            "loss": "mean_of_per_graph_weighted_binary_cross_entropy",
            "optimizer": "Adam",
            "learning_rate": 0.001,
            "gradient_clip_norm": 1.0,
            "precision": "FP32",
            "checkpoint_selection": "minimum_mean_parent_validation_loss",
            "epoch_tie_break": "earliest_epoch",
            "predictor_tie_break": "serial_arm",
        },
        "mathematics": {
            "effective_objective_sense": "MINIMIZE",
            "preserve_declared_objective_sense": True,
            "preserve_objective_constant": True,
            "preserve_rows_bounds_domains_and_variable_order": True,
            "root_and_label_preparations": "independent_fresh_models",
            "main_models": "fresh_original_MILP_per_call",
            "external_treatment": "partial_Start_only",
            "root_vector": "complete_original_variable_order",
            "root_event": "root_MIPNODE_OPTIMAL_with_cut_pass_provenance",
            "unselected_Start_values": "UNDEFINED",
        },
        "solver": {
            "version": "14.0.0",
            "profiles": {
                "root_relaxation": {**common, "Presolve": 0, "Heuristics": 0},
                "incumbent": {
                    **common,
                    "Presolve": -1,
                    "Heuristics": 0.05,
                    "MIPGap": 0.0001,
                },
                "evaluation": {
                    **common,
                    "Presolve": -1,
                    "Heuristics": 0.05,
                    "MIPGap": 0.0001,
                },
            },
            "record_all_effective_parameters": True,
            "target_gaps": list(TARGETS),
        },
        "resources": {
            "maximum_jobs": 2,
            "maximum_Gurobi_sessions": 2,
            "maximum_active_calls_per_parent": 1,
            "solver_profiles": {
                family: {
                    "node_class": "intel-512" if family == "hard" else "intel-256",
                    "tasks": 1,
                    "logical_CPUs": 64,
                    "physical_cores": 32,
                    "memory_GiB": 384 if family == "hard" else 192,
                    "exclusive": True,
                    "requested_GPUs": 0,
                    "job_limit_seconds": 43200,
                }
                for family in ("easy", "medium", "hard")
            },
            "allocation_native_threads_and_activity": "separate_measurements",
        },
        "guidance": {
            "R_source": "independent_root_rounding_and_ranking",
            "G_source": "frozen_validation_selected_predictor",
            "confidence_tails": [0.1, 0.9],
            "maximum_binary_support_fraction": 0.1,
            "confidence_ranking": "descending_absolute_2v_minus_1",
            "tie_break": "original_variable_order",
            "production_policy_freeze": "S3_before_evaluation",
            "R_G_support_matching_required": False,
        },
        "evaluation": {
            "parents": 15,
            "cells": 45,
            "methods": ["B", "R", "G"],
            "blocked_rotating_orders": [list(row) for row in METHOD_ORDERS],
            "same_parent_overlap_permitted": False,
            "fresh_B_required": True,
        },
        "budget": {
            "root_relaxation_calls": 66,
            "incumbent_calls": 66,
            "evaluation_calls": 45,
            "primary_calls": 177,
            "maximum_solver_hours": 1416,
            "reserved_solver_job_hours": 2124,
            "artifact_CPU_job_hours": 24,
            "training_GPU_node_hours": 12,
            "training_model_GPU_hours": 30,
            "whole_8_GPU_node_slot_hours": 96,
            "conditional_hard_diagnostic_calls": 6,
            "conditional_diagnostic_separately_released": True,
            "Benders_standing_budget": None,
        },
        "measurement": {
            "clocks": CLOCKS,
            "time_unit": "seconds",
            "Work_unit": "native_Work",
            "ratio_numerator": "comparator_B_or_R",
            "ratio_denominator": "G",
            "above_one_favours": "G",
            "numeric_ratio_requires": "qualified_common_target_positive_same_clock",
            "signed_saving": "T_comparator_minus_T_G",
            "aggregate": "per_parent_factors_before_cohort_summary",
            "training_speedup": "T_serial_over_T_DDP",
            "GPU_efficiency": "training_speedup_divided_by_4",
            "missing": "null_with_nonempty_reason",
            "censoring": "actual_valid_followup_not_an_imputed_attainment_time",
        },
    }


def expected_population():
    rows = []
    for family, prefix, indices in (
        ("easy", "E", range(30)),
        ("medium", "M", range(30)),
        ("hard", "H", HARD_IDS),
    ):
        for index in indices:
            rows.append(
                {
                    "alias": f"{prefix}{index}",
                    "original_id": f"CFL_{family}_instance_{index}",
                    "family": family,
                }
            )
    return rows


def split_rank(parent):
    # Fixed encoding and separator make this independent of Python/NumPy RNG versions.
    payload = (
        f"cfl-gnn/mvp3/split/v1\0{42}\0{parent['family']}\0{parent['original_id']}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freeze_parents(catalogue):
    expected = expected_population()
    entries = catalogue["parents"]
    identities = [
        {key: parent[key] for key in ("alias", "original_id", "family")}
        for parent in entries
    ]
    require(len(identities) == 66, "Expected 66 distinct original parents")
    by_id = {parent["original_id"]: parent for parent in identities}
    require(len(by_id) == 66, "Duplicate original parent identity")
    require(
        by_id == {parent["original_id"]: parent for parent in expected},
        "Population/alias/family drift",
    )
    roles = {}
    for family, (train, validation, _) in ROLES.items():
        ordered = sorted(
            (parent for parent in expected if parent["family"] == family),
            key=lambda parent: (split_rank(parent), parent["original_id"]),
        )
        for index, parent in enumerate(ordered):
            roles[parent["original_id"]] = (
                "train"
                if index < train
                else "validation"
                if index < train + validation
                else "test"
            )
    return {
        "schema_version": CONTRACT_VERSION,
        "algorithm": SPLIT_ALGORITHM,
        "seed": 42,
        "catalogue_sha256": digest(catalogue),
        "selection_inputs": ["seed", "family", "original_id"],
        "coverage_changes_partition": False,
        "parents": [
            {
                **parent,
                "role": roles.get(parent["original_id"], "transfer_only"),
                "split_rank_sha256": (
                    split_rank(parent) if parent["family"] != "hard" else None
                ),
            }
            for parent in expected
        ],
    }


def build_primary_plan(parents, contract):
    cells = []
    for stage in ("root_relaxation", "incumbent"):
        for parent in parents["parents"]:
            cells.append(
                {
                    "cell_id": f"{stage}/{parent['alias']}",
                    "parent_id": parent["original_id"],
                    "alias": parent["alias"],
                    "stage": stage,
                    "method": None,
                    "seed": 42,
                    "solver_profile": stage,
                    "resource_profile": parent["family"],
                    "status": "PLANNED",
                }
            )
    evaluation = [
        parent
        for parent in parents["parents"]
        if parent["role"] in ("test", "transfer_only")
    ]
    for block, parent in enumerate(evaluation):
        for position, method in enumerate(METHOD_ORDERS[block % 3]):
            cells.append(
                {
                    "cell_id": f"evaluation/{parent['alias']}/{method}",
                    "parent_id": parent["original_id"],
                    "alias": parent["alias"],
                    "stage": "evaluation",
                    "method": method,
                    "seed": 42,
                    "solver_profile": "evaluation",
                    "resource_profile": parent["family"],
                    "block": block,
                    "position": position,
                    "status": "PLANNED",
                }
            )
    return {
        "schema_version": CONTRACT_VERSION,
        "contract_sha256": digest(contract),
        "parent_manifest_sha256": digest(parents),
        "scientific_execution_authorized": False,
        "cells": cells,
    }


def load_bundle(folder):
    """Validate sealed files and scientific invariants; never launch a worker."""
    folder = Path(folder).resolve()
    seal = load_json(folder / "bundle-manifest.json")
    expected_files = {
        "contract.json",
        "input-catalogue.json",
        "parent-manifest.json",
        "primary-plan.json",
        "evidence.schema.json",
    }
    require(seal.get("schema_version") == CONTRACT_VERSION, "Unknown bundle version")
    require(set(seal.get("files", {})) == expected_files, "Unexpected bundle files")
    for name, identity in seal["files"].items():
        path = (folder / name).resolve()
        require(path.parent == folder, "Bundle member escapes its directory")
        raw = path.read_bytes()
        require(len(raw) == identity["bytes"], f"File length mismatch: {name}")
        require(
            hashlib.sha256(raw).hexdigest() == identity["sha256"],
            f"File hash mismatch: {name}",
        )
    contract = load_json(folder / "contract.json")
    require(
        canonical_bytes(contract) == canonical_bytes(approved_contract()),
        "Approved scientific contract drift",
    )
    catalogue = load_json(folder / "input-catalogue.json")
    validate_catalogue(catalogue)
    parents = load_json(folder / "parent-manifest.json")
    require(parents == freeze_parents(catalogue), "Deterministic parent split drift")
    plan = load_json(folder / "primary-plan.json")
    require(plan == build_primary_plan(parents, contract), "Primary call ledger drift")
    from .records import check_schema

    schema = load_json(folder / "evidence.schema.json")
    check_schema(schema)
    return {
        "contract": contract,
        "catalogue": catalogue,
        "parents": parents,
        "plan": plan,
        "schema": schema,
    }


def validate_catalogue(catalogue):
    require(
        digest(catalogue) == CATALOGUE_SHA256, "Frozen stored-input catalogue drift"
    )
    require(
        set(catalogue) == {"schema_version", "provenance", "parents"}
        and catalogue["schema_version"] == CONTRACT_VERSION,
        "Invalid catalogue envelope",
    )
    provenance = catalogue["provenance"]
    require(
        provenance
        == {
            "stored_identity_scope": "NPAD_stored_gzip_bytes",
            "receipt_sha256": "048b823a865af4988088b9f80388e759a7d227ef1f45e8e796a653077170d83c",
            "decoded_identity_basis": "researcher_confirmed_common_MILPBench_origin",
            "independent_decoded_hash_verified": False,
            "decompression_required": False,
        },
        "Input provenance drift",
    )
    for parent in catalogue["parents"]:
        require(
            set(parent)
            == {"alias", "original_id", "family", "stored_sha256", "stored_bytes"},
            "Invalid input identity fields",
        )
        value = parent["stored_sha256"]
        require(
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value),
            "Invalid stored-file SHA256",
        )
        require(
            type(parent["stored_bytes"]) is int and parent["stored_bytes"] > 0,
            "Invalid stored size",
        )
    require(
        sum(parent["stored_bytes"] for parent in catalogue["parents"]) == 1810985584,
        "Stored catalogue byte total drift",
    )
    freeze_parents(catalogue)


def summary(bundle):
    return {
        "schema_version": CONTRACT_VERSION,
        "parents": len(bundle["parents"]["parents"]),
        "partition_counts": dict(
            Counter(parent["role"] for parent in bundle["parents"]["parents"])
        ),
        "primary_cells": len(bundle["plan"]["cells"]),
        "stage_counts": dict(
            Counter(cell["stage"] for cell in bundle["plan"]["cells"])
        ),
        "parent_manifest_sha256": digest(bundle["parents"]),
        "primary_plan_sha256": digest(bundle["plan"]),
        "scientific_execution_authorized": False,
    }
