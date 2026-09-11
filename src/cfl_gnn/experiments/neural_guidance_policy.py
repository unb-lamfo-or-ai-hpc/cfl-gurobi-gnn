"""Auditable policy contract for solver-native neural guidance.

This module intentionally performs no MIP solve. It freezes the intervention
semantics that the paired benchmark must implement in a later execution gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 1
PLAN_NAME = "neural_guidance_policy_plan.json"
REPORT_NAME = "neural_guidance_policy_report.json"
METHODS = (
    "unguided_control",
    "gurobi_variable_hints",
    "partial_mip_start",
    "confidence_partial_fixing_with_recovery",
    "local_branching_trust_region_with_recovery",
)
DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "experiments"
    / "neural_guidance_policy_v1.json"
)


class NeuralGuidancePolicyError(ValueError):
    """Raised when the guidance policy is incomplete or internally inconsistent."""


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file() or source.stat().st_size == 0:
        raise NeuralGuidancePolicyError(f"missing policy configuration: {source}")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise NeuralGuidancePolicyError("policy configuration is unreadable") from error
    if not isinstance(value, dict):
        raise NeuralGuidancePolicyError("policy configuration must be a JSON object")
    return value


def _fractions(value: Any, *, field: str) -> tuple[float, ...]:
    if not isinstance(value, list) or not value:
        raise NeuralGuidancePolicyError(f"{field} must be a nonempty list")
    try:
        normalized = tuple(float(item) for item in value)
    except (TypeError, ValueError, OverflowError) as error:
        raise NeuralGuidancePolicyError(f"{field} contains an invalid value") from error
    if any(not math.isfinite(item) or not 0.0 < item <= 1.0 for item in normalized):
        raise NeuralGuidancePolicyError(f"{field} must be contained in (0, 1]")
    if tuple(sorted(set(normalized))) != normalized:
        raise NeuralGuidancePolicyError(f"{field} must be unique and increasing")
    return normalized


def validate_policy(config: Mapping[str, Any]) -> dict[str, bool]:
    """Validate the precommitted hierarchy and return its named audit checks."""
    methods = config.get("methods")
    tiers = config.get("method_tiers")
    controls = config.get("selection_controls")
    if not isinstance(methods, Mapping) or set(methods) != set(METHODS):
        raise NeuralGuidancePolicyError("the required method inventory is incomplete")
    if not isinstance(tiers, Mapping) or not isinstance(controls, Mapping):
        raise NeuralGuidancePolicyError(
            "method tiers or selection controls are missing"
        )

    coverage = _fractions(
        methods["partial_mip_start"].get("coverage_fractions"),
        field="partial-start coverage fractions",
    )
    fixing_coverage = _fractions(
        methods["confidence_partial_fixing_with_recovery"].get(
            "coverage_fractions"
        ),
        field="partial-fixing coverage fractions",
    )
    radii = _fractions(
        methods["local_branching_trust_region_with_recovery"].get(
            "radius_fractions"
        ),
        field="local-branching radius fractions",
    )
    budgets = tuple(config.get("time_limits_seconds", ()))
    time_regions = tuple(config.get("time_regions", ()))
    primary = tuple(tiers.get("primary", ()))
    exploratory = tuple(tiers.get("exploratory_recovery", ()))

    checks = {
        "schema_supported": config.get("schema_version") == SCHEMA_VERSION,
        "gurobi_is_priority_solver": config.get("priority_solver") == "gurobi",
        "scip_is_comparison_only": config.get("comparison_solver") == "scip",
        "gurobi_is_graph_authority": config.get("graph_authority") == "gurobi",
        "seed_is_42": config.get("seed") == 42,
        "time_budgets_precommitted": budgets == (3600, 14400),
        "four_time_regions_recorded": time_regions
        == (
            "total_wall_time_seconds",
            "data_read_wall_time_seconds",
            "model_build_wall_time_seconds",
            "model_optimize_wall_time_seconds",
        ),
        "primary_outcomes_are_gap_and_optimize_time": tuple(
            config.get("primary_outcomes", ())
        )
        == (
            "terminal_mip_gap_relative",
            "model_optimize_wall_time_seconds",
        ),
        "primary_method_is_nonbinding_gurobi_hint": primary
        == ("unguided_control", "gurobi_variable_hints"),
        "hard_fixing_is_not_primary": (
            "confidence_partial_fixing_with_recovery" not in primary
        ),
        "all_binding_methods_have_recovery": all(
            methods[name].get("changes_feasible_region") is True
            and methods[name].get("recovery_phase_always_executed") is True
            for name in exploratory
        ),
        "coverage_sensitivity_is_symmetric": coverage == fixing_coverage,
        "coverage_sensitivity_reaches_10_percent": coverage[-1] == 0.1,
        "local_branching_sensitivity_precommitted": radii
        == (0.001, 0.005, 0.01),
        "test_cannot_select_policy": controls.get(
            "test_may_select_method_coverage_or_radius"
        )
        is False,
        "right_censoring_is_retained": config.get("censoring_policy")
        == "retain_and_flag_no_naive_inference",
        "development_only": config.get("development_only") is True,
        "scientific_reporting_disabled": config.get(
            "scientific_reporting_eligible"
        )
        is False,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise NeuralGuidancePolicyError(f"policy checks failed: {failed}")
    return checks


def _normalized_prediction(row: Mapping[str, Any]) -> dict[str, Any]:
    forbidden = {"target", "label", "ground_truth"}
    if forbidden.intersection(row):
        raise NeuralGuidancePolicyError("prediction rows must not contain test labels")
    name = str(row.get("variable_name", ""))
    predicted = row.get("predicted_value")
    try:
        probability = float(row.get("probability"))
        confidence = float(row.get("confidence"))
        priority = int(row.get("priority"))
    except (TypeError, ValueError, OverflowError) as error:
        raise NeuralGuidancePolicyError("invalid prediction row") from error
    if (
        not name
        or predicted not in (0, 1)
        or not math.isfinite(probability)
        or not math.isfinite(confidence)
        or not 0.0 <= probability <= 1.0
        or not 0.0 <= confidence <= 1.0
        or not 0 <= priority <= 100
    ):
        raise NeuralGuidancePolicyError("invalid prediction row")
    return {
        "variable_name": name,
        "predicted_value": int(predicted),
        "probability": probability,
        "confidence": confidence,
        "priority": priority,
    }


def rank_predictions(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return label-free predictions in deterministic confidence order."""
    normalized = [_normalized_prediction(row) for row in rows]
    names = [row["variable_name"] for row in normalized]
    if not normalized or len(names) != len(set(names)):
        raise NeuralGuidancePolicyError("predictions must be nonempty and unique")
    return sorted(
        normalized,
        key=lambda row: (
            -row["priority"],
            -row["confidence"],
            row["variable_name"],
        ),
    )


def select_coverage(
    rows: Sequence[Mapping[str, Any]], fraction: float
) -> list[dict[str, Any]]:
    """Select a deterministic top-confidence partial assignment."""
    coverage = _fractions([fraction], field="coverage fraction")[0]
    ranked = rank_predictions(rows)
    count = max(1, int(math.floor(len(ranked) * coverage)))
    return ranked[:count]


def guidance_directives(
    rows: Sequence[Mapping[str, Any]],
    *,
    method: str,
    fraction: float | None = None,
    radius_fraction: float | None = None,
) -> dict[str, Any]:
    """Translate predictions into solver-neutral, audited intervention data."""
    if method not in METHODS or method == "unguided_control":
        if method == "unguided_control":
            return {"method": method, "assignments": [], "binding": False}
        raise NeuralGuidancePolicyError("unknown guidance method")
    ranked = rank_predictions(rows)
    local_branching = method == "local_branching_trust_region_with_recovery"
    if local_branching and (radius_fraction is None or fraction is not None):
        raise NeuralGuidancePolicyError("LB requires radius_fraction, not coverage")
    selected = ranked if method == "gurobi_variable_hints" or local_branching else select_coverage(
        ranked,
        0.1 if fraction is None else fraction,
    )
    assignments = [
        {
            "variable_name": row["variable_name"],
            "value": row["predicted_value"],
            "confidence": row["confidence"],
            "priority": row["priority"],
        }
        for row in selected
    ]
    binding = method in {
        "confidence_partial_fixing_with_recovery",
        "local_branching_trust_region_with_recovery",
    }
    directive = {
        "method": method,
        "assignments": assignments,
        "assignment_sha256": canonical_sha256(assignments),
        "binding_during_restricted_phase": binding,
        "recovery_required": binding,
    }
    if local_branching:
        radius = _fractions([radius_fraction], field="LB radius fraction")[0]
        if radius not in (0.001, 0.005, 0.01):
            raise NeuralGuidancePolicyError("LB radius is not precommitted")
        directive.update({"support": "all_canonical_binary_variables",
                          "binary_variable_count": len(ranked),
                          "radius_fraction": radius,
                          "radius": min(len(ranked), max(1, math.ceil(radius*len(ranked))))})
    if binding:
        directive["restricted_phase_budget_fraction"] = 0.2
        directive["recovery_phase_always_executed"] = True
    return directive


def build_plan(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _read_json(config_path)
    checks = validate_policy(config)
    contract = {
        "schema_version": SCHEMA_VERSION,
        "dataset_variant": "neural_guidance_policy_without_solver_execution",
        "policy": config,
        "policy_config_sha256": sha256_file(config_path),
        "checks": checks,
        "methodological_boundaries": {
            "variable_hints_change_feasible_region": False,
            "partial_mip_starts_change_feasible_region": False,
            "partial_fixing_changes_feasible_region_during_restricted_phase": True,
            "local_branching_changes_feasible_region_during_restricted_phase": True,
            "binding_methods_require_full_model_recovery": True,
            "hard_fixing_equivalent_to_variable_hints": False,
        },
        "development_only": True,
        "scientific_reporting_eligible": False,
    }
    return {
        **contract,
        "contract_sha256": canonical_sha256(contract),
        "contract_valid": True,
        "decision": {
            "primary_method": "gurobi_variable_hints",
            "next_gate": "paired_neural_guidance_benchmark_execution",
            "reason_code": "guidance_semantics_precommitted_without_test_selection",
        },
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit and freeze the literature-backed neural-guidance policy."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    outputs = (output_dir / PLAN_NAME, output_dir / REPORT_NAME)
    if not args.overwrite and any(path.exists() for path in outputs):
        raise FileExistsError("policy outputs exist; pass --overwrite explicitly")
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = build_plan(args.config)
    _write_json(output_dir / PLAN_NAME, plan)
    report = {
        **plan,
        "probe_completed": True,
        "gate_status": "passed",
        "execution": {
            "solver_runs_executed": 0,
            "dry_run": bool(args.dry_run),
        },
    }
    _write_json(output_dir / REPORT_NAME, report)
    print(
        "[INFO] "
        f"contract={plan['contract_sha256']} | methods={len(METHODS)} | "
        "primary=gurobi_variable_hints"
    )
    print("[INFO] solver runs executed=0; execution belongs to the next gate")
    print(f"[INFO] Plan: {output_dir / PLAN_NAME}")
    print(f"[INFO] Report: {output_dir / REPORT_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
