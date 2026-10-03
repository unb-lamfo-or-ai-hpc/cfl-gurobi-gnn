"""Audit the Gurobi-first legacy pipeline recovery contract.

This diagnostic is intentionally dependency-free.  It validates the static
research contract introduced by PR #41 and can optionally verify both pinned
Git snapshots without modifying the working tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


EXPECTED_LEGACY_COMMIT = "9903c1dc66f65e9497d7faa2d8d4f3ee414a0f42"
EXPECTED_CURRENT_COMMIT = "9f7da7d206129fcd72c72d1a8d682bf3cf413fde"
EXPECTED_COMPONENT_IDS = {
    "gurobi_parent_collection",
    "phase1_descriptive_audit",
    "bipartite_graph_builder",
    "graph_dataset_audit",
    "graph_statistics",
    "graph_clustering",
    "gasse_model",
    "serial_trainer",
    "distributed_trainer",
    "model_evaluator",
    "gurobi_variable_hints",
    "gurobi_benchmark",
}
EXPECTED_SEQUENCE = [
    "pr42_parent_collection_orchestration_and_phase1_eda",
    "pr43_gurobi_graph_authority_statistics_and_clustering",
    "pr44_gasse_training_and_evaluation_reconnection",
    "pr45_native_guidance_and_partial_mip_start_comparison",
    "pr46_partial_population_execution_and_outputs",
    "pr47_english_reproducibility_and_dependency_review",
]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}", value))


def _run_git(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=False,
        capture_output=True,
    )


def _git_commit_available(repo_root: Path, commit: str) -> bool:
    result = _run_git(repo_root, "cat-file", "-e", f"{commit}^{{commit}}")
    return result.returncode == 0


def _git_file(repo_root: Path, commit: str, path: str) -> bytes | None:
    result = _run_git(repo_root, "show", f"{commit}:{path}")
    if result.returncode != 0:
        return None
    return result.stdout


def _contract_errors(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    commits = contract.get("pinned_commits", {})
    boundary = contract.get("scientific_boundary", {})
    labels = contract.get("label_contract", {})
    root_lp = contract.get("root_lp_feature_contract", {})
    guidance = contract.get("guidance_contract", {})
    components = contract.get("components", [])

    if contract.get("schema_version") != 1:
        errors.append("unsupported_schema_version")
    if contract.get("contract_id") != "gurobi_first_legacy_pipeline_recovery_v1":
        errors.append("unexpected_contract_id")
    if commits.get("legacy") != EXPECTED_LEGACY_COMMIT:
        errors.append("legacy_commit_not_pinned")
    if commits.get("current") != EXPECTED_CURRENT_COMMIT:
        errors.append("current_commit_not_pinned")
    if not all(_is_sha(value) for value in commits.values()):
        errors.append("invalid_pinned_commit")

    required_boundary = {
        "pipeline_behavior_changes_authorized": False,
        "pyomo_allowed": False,
        "graph_authority_solver": "gurobi",
        "effective_objective_sense": "MINIMIZE",
        "graph_unit": "mathematical_mip",
        "incumbent_graph_policy": "prohibited",
        "derived_samples_train_only": True,
        "derived_samples_inherit_parent_fold": True,
    }
    for key, expected in required_boundary.items():
        if boundary.get(key) != expected:
            errors.append(f"scientific_boundary_mismatch:{key}")

    if boundary.get("comparison_solvers") != ["gurobi", "scip"]:
        errors.append("comparison_solver_order_mismatch")
    if labels.get("graph_features_independent_of_label_solver") is not True:
        errors.append("graph_label_separation_missing")
    if labels.get("original_mip_graph_count_per_parent") != 1:
        errors.append("original_graph_cardinality_mismatch")
    if labels.get("synthetic_mip_graph_count_per_artifact") != 1:
        errors.append("synthetic_graph_cardinality_mismatch")

    required_root_lp = {
        "authority_solver": "gurobi",
        "required": True,
        "zero_ablation_allowed": False,
        "missing_value_policy": "fail_closed",
        "legacy_candidate": "first_optimal_mipnode_at_root",
        "implementation_decision_gate": "legacy_parity_audit_before_builder_change",
    }
    for key, expected in required_root_lp.items():
        if root_lp.get(key) != expected:
            errors.append(f"root_lp_contract_mismatch:{key}")

    required_guidance = {
        "primary": "gurobi_variable_hints",
        "secondary": "gurobi_partial_mip_start",
        "scip_role": "comparison_only",
        "hard_domain_fixing_primary_allowed": False,
        "pr37_evidence_classification": "historical_engineering_only",
        "held_out_test_method_selection_allowed": False,
    }
    for key, expected in required_guidance.items():
        if guidance.get(key) != expected:
            errors.append(f"guidance_contract_mismatch:{key}")

    component_ids = [item.get("id") for item in components]
    if set(component_ids) != EXPECTED_COMPONENT_IDS:
        errors.append("component_inventory_mismatch")
    if len(component_ids) != len(set(component_ids)):
        errors.append("duplicate_component_id")
    for item in components:
        if not item.get("legacy_path") or not item.get("current_path"):
            errors.append(f"incomplete_component_path:{item.get('id')}")
        if not item.get("required_action"):
            errors.append(f"missing_required_action:{item.get('id')}")
    if contract.get("implementation_sequence") != EXPECTED_SEQUENCE:
        errors.append("implementation_sequence_mismatch")
    return errors


def audit_contract(
    contract_path: Path,
    repo_root: Path,
    history_mode: str = "auto",
) -> dict[str, Any]:
    """Return a sanitized audit report for the recovery contract."""

    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    errors = _contract_errors(contract)
    commits = contract["pinned_commits"]

    availability = {
        name: _git_commit_available(repo_root, commit)
        for name, commit in commits.items()
    }
    if history_mode == "required" and not all(availability.values()):
        errors.append("required_git_history_unavailable")

    verify_history = history_mode == "required" or (
        history_mode == "auto" and all(availability.values())
    )
    component_rows: list[dict[str, Any]] = []
    for component in contract["components"]:
        current_path = repo_root / component["current_path"]
        current_present = current_path.is_file()
        if not current_present:
            errors.append(f"current_path_missing:{component['id']}")

        row: dict[str, Any] = {
            "id": component["id"],
            "stage": component["stage"],
            "legacy_path": component["legacy_path"],
            "current_path": component["current_path"],
            "declared_relation": component["relation"],
            "required_action": component["required_action"],
            "current_worktree_present": current_present,
            "current_worktree_sha256": (
                _sha256(current_path.read_bytes()) if current_present else None
            ),
            "history_status": "not_requested",
        }
        if verify_history:
            legacy_bytes = _git_file(
                repo_root,
                commits["legacy"],
                component["legacy_path"],
            )
            current_bytes = _git_file(
                repo_root,
                commits["current"],
                component["current_path"],
            )
            if legacy_bytes is None or current_bytes is None:
                row["history_status"] = "pinned_path_missing"
                errors.append(f"pinned_path_missing:{component['id']}")
            else:
                identical = legacy_bytes == current_bytes
                row.update(
                    {
                        "history_status": "verified",
                        "legacy_sha256": _sha256(legacy_bytes),
                        "current_pinned_sha256": _sha256(current_bytes),
                        "byte_identical": identical,
                    }
                )
                if component["relation"] == "byte_identical" and not identical:
                    errors.append(f"byte_identity_mismatch:{component['id']}")

        component_rows.append(row)

    all_current = all(row["current_worktree_present"] for row in component_rows)
    history_verified = verify_history and all(
        row["history_status"] == "verified" for row in component_rows
    )
    report = {
        "schema_version": 1,
        "contract_id": contract["contract_id"],
        "contract_sha256": _sha256(contract_bytes),
        "pinned_commits": commits,
        "history_mode": history_mode,
        "history_commit_availability": availability,
        "components": component_rows,
        "checks": {
            "contract_fields_valid": not _contract_errors(contract),
            "component_inventory_complete": (
                {row["id"] for row in component_rows} == EXPECTED_COMPONENT_IDS
            ),
            "all_current_paths_present": all_current,
            "history_verified_when_requested": (
                history_verified if verify_history else True
            ),
            "gurobi_is_graph_authority": (
                contract["scientific_boundary"]["graph_authority_solver"]
                == "gurobi"
            ),
            "incumbent_graphs_prohibited": (
                contract["scientific_boundary"]["incumbent_graph_policy"]
                == "prohibited"
            ),
            "zero_root_lp_ablation_prohibited": (
                contract["root_lp_feature_contract"]["zero_ablation_allowed"]
                is False
            ),
            "hard_fixing_excluded_from_primary_path": (
                contract["guidance_contract"][
                    "hard_domain_fixing_primary_allowed"
                ]
                is False
            ),
            "production_behavior_unchanged": (
                contract["scientific_boundary"][
                    "pipeline_behavior_changes_authorized"
                ]
                is False
            ),
        },
        "errors": sorted(set(errors)),
    }
    report["gate_status"] = (
        "passed"
        if not report["errors"] and all(report["checks"].values())
        else "failed"
    )
    report["decision"] = {
        "next_gate": (
            "pr42_parent_collection_orchestration_and_phase1_eda"
            if report["gate_status"] == "passed"
            else "correct_recovery_contract"
        ),
        "pipeline_behavior_changed": False,
    }
    return report


def _parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        type=Path,
        default=(
            project_root
            / "configs"
            / "audits"
            / "legacy_pipeline_recovery_v1.json"
        ),
    )
    parser.add_argument("--repo-root", type=Path, default=project_root)
    parser.add_argument(
        "--history-mode",
        choices=("auto", "required", "skip"),
        default="auto",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = audit_contract(
        args.contract.resolve(),
        args.repo_root.resolve(),
        args.history_mode,
    )
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
        print(f"[INFO] Report: {args.output}")
    else:
        print(payload, end="")
    print(
        "[INFO] "
        f"gate={report['gate_status']} | "
        f"components={len(report['components'])} | "
        f"history_mode={report['history_mode']}"
    )
    return 0 if report["gate_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

