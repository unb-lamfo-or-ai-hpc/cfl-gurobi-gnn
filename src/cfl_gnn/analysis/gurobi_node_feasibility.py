"""Audit what Gurobi exposes at MIPNODE without materializing fake instances."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import struct
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cfl_gnn.graph.instance_provenance import sha256_file


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1
DATASET_VARIANT = "gurobi_incumbent_node_feasibility"
REPORT_NAME = "gurobi_node_capability_report.json"
PLAN_NAME = "gurobi_node_feasibility_plan.json"
MAX_RECORDED_CALLBACK_ERRORS = 10
MAX_SAMPLES_PER_NODE_COUNT = 3
SUPPORTED_MODEL_SUFFIXES = (".lp", ".lp.gz", ".mps", ".mps.gz", ".rew", ".rew.gz")
OFFICIAL_REFERENCES = (
    "https://docs.gurobi.com/projects/optimizer/en/current/reference/"
    "numericcodes/callbacks.html",
    "https://docs.gurobi.com/projects/optimizer/en/current/reference/python/"
    "model.html",
    "https://support.gurobi.com/hc/en-us/community/posts/"
    "37586816119569-Getting-the-decision-variable-s-local-bounds-within-the-B-B-tree",
    "https://docs.gurobi.com/projects/remoteservices/en/current/content/"
    "programming-with-remote-services/callbacks.html",
)


class FeasibilityProbeError(RuntimeError):
    """Raised when a node-feasibility probe cannot satisfy its contract."""


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    normalized = int(value)
    if normalized != value or normalized <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return normalized


def _positive_finite(value: Any, name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return normalized


def _instance_id(path: Path) -> str:
    lowered = path.name.lower()
    for suffix in sorted(SUPPORTED_MODEL_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(suffix):
            return path.name[: -len(suffix)]
    raise ValueError(
        "instance must be a Gurobi-readable LP, MPS, or REW file, "
        "optionally gzip-compressed"
    )


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


@dataclass(frozen=True, slots=True)
class ProbePlan:
    """Path-sanitized and hash-bound contract for one Gurobi feasibility probe."""

    instance_path: Path
    instance_id: str
    instance_sha256: str
    time_limit: float
    node_limit: int
    max_samples: int
    integrality_tolerance: float
    seed: int

    @property
    def contract_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "dataset_variant": DATASET_VARIANT,
            "source_instance": {
                "instance_id": self.instance_id,
                "file_name": self.instance_path.name,
                "sha256": self.instance_sha256,
            },
            "objective_sense_override": "MINIMIZE",
            "parameters": {
                "time_limit": self.time_limit,
                "node_limit": self.node_limit,
                "max_samples": self.max_samples,
                "integrality_tolerance": self.integrality_tolerance,
                "max_samples_per_node_count": MAX_SAMPLES_PER_NODE_COUNT,
                "threads": 1,
                "presolve": 0,
                "seed": self.seed,
            },
            "callback_mode": "passive_mipnode_observer",
        }

    @property
    def contract_sha256(self) -> str:
        return _canonical_sha256(self.contract_payload)

    def to_summary(self) -> dict[str, Any]:
        return {
            **self.contract_payload,
            "contract_sha256": self.contract_sha256,
            "planned_outputs": [REPORT_NAME],
        }


def build_probe_plan(
    instance_path: str | Path,
    *,
    time_limit: float = 60.0,
    node_limit: int = 100,
    max_samples: int = 20,
    integrality_tolerance: float = 1e-6,
    seed: int = 42,
) -> ProbePlan:
    """Validate and bind a feasibility experiment to the original model bytes."""

    instance = Path(instance_path).resolve()
    if not instance.is_file() or instance.stat().st_size == 0:
        raise FileNotFoundError(f"missing or empty instance: {instance}")
    instance_id = _instance_id(instance)
    tolerance = _positive_finite(integrality_tolerance, "integrality_tolerance")
    if tolerance >= 0.5:
        raise ValueError("integrality_tolerance must be smaller than 0.5")
    return ProbePlan(
        instance_path=instance,
        instance_id=instance_id,
        instance_sha256=sha256_file(instance),
        time_limit=_positive_finite(time_limit, "time_limit"),
        node_limit=_positive_int(node_limit, "node_limit"),
        max_samples=_positive_int(max_samples, "max_samples"),
        integrality_tolerance=tolerance,
        seed=_positive_int(seed, "seed"),
    )


def _relaxation_sha256(values: Sequence[float]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<d", float(value)))
    return digest.hexdigest()


def _finite_or_none(value: Any) -> float | None:
    normalized = float(value)
    return normalized if math.isfinite(normalized) and abs(normalized) < 1e99 else None


class NodeObserver:
    """Passive, bounded observer for callback-visible MIPNODE information."""

    def __init__(
        self,
        variables: Sequence[Any],
        discrete_mask: Sequence[bool],
        *,
        callback_codes: Any,
        optimal_status: int,
        max_samples: int,
        integrality_tolerance: float,
    ) -> None:
        if len(variables) != len(discrete_mask):
            raise ValueError("variables and discrete_mask must have equal length")
        self.variables = list(variables)
        self.discrete_mask = tuple(bool(value) for value in discrete_mask)
        self.codes = callback_codes
        self.optimal_status = optimal_status
        self.max_samples = _positive_int(max_samples, "max_samples")
        self.integrality_tolerance = _positive_finite(
            integrality_tolerance, "integrality_tolerance"
        )
        self.callback_calls = 0
        self.optimal_callback_calls = 0
        self.status_counts: Counter[int] = Counter()
        self.node_count_occurrences: Counter[int] = Counter()
        self.samples: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self.callback_error_count = 0
        self.callbacks_after_sample_limit = 0

    def __call__(self, model: Any, where: int) -> None:
        if where != self.codes.MIPNODE:
            return
        self.callback_calls += 1
        if len(self.samples) >= self.max_samples:
            self.callbacks_after_sample_limit += 1
            return
        try:
            status = int(model.cbGet(self.codes.MIPNODE_STATUS))
            self.status_counts[status] += 1
            if status != self.optimal_status:
                return
            self.optimal_callback_calls += 1
            relaxation = [float(value) for value in model.cbGetNodeRel(self.variables)]
            if len(relaxation) != len(self.variables):
                raise FeasibilityProbeError(
                    "MIPNODE relaxation length disagrees with the user model"
                )
            if any(
                not math.isfinite(value) or abs(value) >= 1e99
                for value in relaxation
            ):
                raise FeasibilityProbeError(
                    "MIPNODE relaxation contains a non-finite or sentinel value"
                )
            node_count = int(model.cbGet(self.codes.MIPNODE_NODCNT))
            occurrence = self.node_count_occurrences[node_count]
            self.node_count_occurrences[node_count] += 1
            if occurrence >= MAX_SAMPLES_PER_NODE_COUNT:
                return
            discrete_values = [
                value
                for value, is_discrete in zip(relaxation, self.discrete_mask)
                if is_discrete
            ]
            fractional_count = sum(
                abs(value - round(value)) > self.integrality_tolerance
                for value in discrete_values
            )
            self.samples.append(
                {
                    "sample_index": len(self.samples),
                    "node_count": node_count,
                    "node_count_occurrence": occurrence,
                    "root_node_sample": node_count == 0,
                    "phase": int(model.cbGet(self.codes.MIPNODE_PHASE)),
                    "best_objective": _finite_or_none(
                        model.cbGet(self.codes.MIPNODE_OBJBST)
                    ),
                    "best_bound": _finite_or_none(
                        model.cbGet(self.codes.MIPNODE_OBJBND)
                    ),
                    "runtime": float(model.cbGet(self.codes.RUNTIME)),
                    "relaxation_dimension": len(relaxation),
                    "discrete_variable_count": len(discrete_values),
                    "fractional_discrete_count": fractional_count,
                    "relaxation_min": min(relaxation) if relaxation else None,
                    "relaxation_max": max(relaxation) if relaxation else None,
                    "relaxation_sha256": _relaxation_sha256(relaxation),
                }
            )
        except Exception as error:  # callbacks must not obscure solver cleanup
            self.callback_error_count += 1
            if len(self.errors) < MAX_RECORDED_CALLBACK_ERRORS:
                self.errors.append(
                    {
                        "callback_index": self.callback_calls - 1,
                        "error_type": type(error).__name__,
                        "reason": "callback_query_failed",
                    }
                )
            if self.callback_error_count == 1:
                LOGGER.exception("MIPNODE feasibility probe callback failed")
            elif self.callback_error_count == MAX_RECORDED_CALLBACK_ERRORS + 1:
                LOGGER.error("additional MIPNODE callback errors are suppressed")

    def summary(self) -> dict[str, Any]:
        distinct = sorted(self.node_count_occurrences)
        return {
            "mipnode_callback_calls": self.callback_calls,
            "optimal_mipnode_callback_calls": self.optimal_callback_calls,
            "samples_recorded": len(self.samples),
            "sample_limit_reached": len(self.samples) == self.max_samples,
            "callbacks_after_sample_limit": self.callbacks_after_sample_limit,
            "distinct_node_counts_observed": len(distinct),
            "observed_node_counts": distinct,
            "root_node_samples": sum(
                bool(sample["root_node_sample"]) for sample in self.samples
            ),
            "repeated_node_count_callbacks": sum(
                count - 1 for count in self.node_count_occurrences.values()
            ),
            "status_counts": {
                str(status): count
                for status, count in sorted(self.status_counts.items())
            },
            "callback_error_count": self.callback_error_count,
            "callback_errors": list(self.errors),
            "samples": list(self.samples),
        }


def capability_assessment(*, samples_recorded: int) -> dict[str, Any]:
    """State the documented boundary between observations and node models."""

    relaxation_status = "observed" if samples_recorded > 0 else "not_observed"
    return {
        "node_relaxation": {
            "status": relaxation_status,
            "basis": "cbGetNodeRel at an optimal MIPNODE callback",
        },
        "global_objective_bound_and_progress": {
            "status": relaxation_status,
            "basis": "documented MIPNODE callback query codes",
        },
        "local_variable_bounds": {
            "status": "not_exposed_by_documented_gurobi_api"
        },
        "branch_path": {"status": "not_exposed_by_documented_gurobi_api"},
        "unique_node_identifier": {
            "status": "not_exposed_by_documented_gurobi_api",
            "note": "MIPNODE_NODCNT is an explored-node count, not a node id",
        },
        "parent_child_relationship": {
            "status": "not_exposed_by_documented_gurobi_api"
        },
        "node_model_serialization": {
            "status": "not_exposed_by_documented_gurobi_api"
        },
    }


def feasibility_decision(
    *, samples_recorded: int, callback_errors: int
) -> dict[str, Any]:
    """Return a fail-closed decision that never relabels relaxations as MILPs."""

    runtime_status = (
        "callback_error"
        if callback_errors
        else "mipnode_observed"
        if samples_recorded
        else "inconclusive_no_mipnode_events"
    )
    return {
        "runtime_probe_status": runtime_status,
        "exact_subproblem_materialization": False,
        "structurally_distinct_instance_created": False,
        "eligible_as_new_milp_instance": False,
        "reason_code": "gurobi_does_not_expose_node_local_branch_state",
        "next_solver_candidate": "SCIP",
        "important_boundary": (
            "an incumbent or node-relaxation vector is not an exact serialized "
            "branch-and-bound subproblem"
        ),
    }


def _model_signature(model: Any, grb: Any) -> dict[str, Any]:
    variables = model.getVars()
    return {
        "rows": int(model.NumConstrs),
        "columns": int(model.NumVars),
        "nonzeros": int(model.NumNZs),
        "binary_variables": sum(variable.VType == grb.BINARY for variable in variables),
        "integer_variables": sum(
            variable.VType == grb.INTEGER for variable in variables
        ),
        "continuous_variables": sum(
            variable.VType == grb.CONTINUOUS for variable in variables
        ),
    }


def _status_name(status: int, grb: Any) -> str:
    names = {
        grb.OPTIMAL: "OPTIMAL",
        grb.INFEASIBLE: "INFEASIBLE",
        grb.INF_OR_UNBD: "INF_OR_UNBD",
        grb.UNBOUNDED: "UNBOUNDED",
        grb.TIME_LIMIT: "TIME_LIMIT",
        grb.NODE_LIMIT: "NODE_LIMIT",
        grb.INTERRUPTED: "INTERRUPTED",
    }
    return names.get(status, f"STATUS_{status}")


def _create_environment(gp: Any) -> Any:
    env = gp.Env(empty=True)
    env.setParam("OutputFlag", 0)
    for variable in ("WLSACCESSID", "WLSSECRET", "LICENSEID"):
        value = os.environ.get(variable)
        if value:
            env.setParam(variable, int(value) if variable == "LICENSEID" else value)
    env.start()
    return env


def run_probe(plan: ProbePlan) -> dict[str, Any]:
    """Run the licensed probe. Heavy solver imports stay outside dry-run paths."""

    import gurobipy as gp
    from gurobipy import GRB

    environment = None
    model = None
    started_at = datetime.now(timezone.utc)
    try:
        environment = _create_environment(gp)
        model = gp.read(str(plan.instance_path), env=environment)
        model.update()
        original_sense = (
            "MINIMIZE" if model.ModelSense == GRB.MINIMIZE else "MAXIMIZE"
        )
        model.ModelSense = GRB.MINIMIZE
        before = _model_signature(model, GRB)
        variables = model.getVars()
        discrete_mask = [
            variable.VType in (GRB.BINARY, GRB.INTEGER, GRB.SEMIINT)
            for variable in variables
        ]
        observer = NodeObserver(
            variables,
            discrete_mask,
            callback_codes=GRB.Callback,
            optimal_status=GRB.OPTIMAL,
            max_samples=plan.max_samples,
            integrality_tolerance=plan.integrality_tolerance,
        )

        model.Params.TimeLimit = plan.time_limit
        model.Params.NodeLimit = plan.node_limit
        model.Params.Threads = 1
        model.Params.Presolve = 0
        model.Params.Seed = plan.seed
        model.Params.OutputFlag = 1
        model.optimize(observer)

        observations = observer.summary()
        after = _model_signature(model, GRB)
        solution_count = int(model.SolCount)
        solve = {
            "status_code": int(model.Status),
            "status": _status_name(int(model.Status), GRB),
            "runtime": float(model.Runtime),
            "node_count": int(model.NodeCount),
            "solution_count": solution_count,
            "best_objective": float(model.ObjVal) if solution_count else None,
            "best_bound": _finite_or_none(model.ObjBound),
        }
        report = {
            **plan.to_summary(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "gurobi_version": list(gp.gurobi.version()),
            "source_model": {
                "original_objective_sense": original_sense,
                "effective_objective_sense": "MINIMIZE",
                "signature_before_solve": before,
                "user_model_signature_after_solve": after,
                "user_model_signature_unchanged": before == after,
            },
            "solve": solve,
            "observations": observations,
            "capabilities": capability_assessment(
                samples_recorded=observations["samples_recorded"]
            ),
            "decision": feasibility_decision(
                samples_recorded=observations["samples_recorded"],
                callback_errors=observations["callback_error_count"],
            ),
            "official_references": list(OFFICIAL_REFERENCES),
            "elapsed_wall_seconds": (
                datetime.now(timezone.utc) - started_at
            ).total_seconds(),
        }
        return report
    finally:
        if model is not None:
            model.dispose()
        if environment is not None:
            environment.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit callback-visible Gurobi MIPNODE state without claiming that "
            "node relaxations are new MILP instances."
        )
    )
    parser.add_argument("--instance", required=True, type=Path)
    parser.add_argument("--output_dir", required=True, type=Path)
    parser.add_argument("--time_limit", type=float, default=60.0)
    parser.add_argument("--node_limit", type=int, default=100)
    parser.add_argument("--max_samples", type=int, default=20)
    parser.add_argument("--integrality_tolerance", type=float, default=1e-6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = build_parser().parse_args(argv)
    plan = build_probe_plan(
        args.instance,
        time_limit=args.time_limit,
        node_limit=args.node_limit,
        max_samples=args.max_samples,
        integrality_tolerance=args.integrality_tolerance,
        seed=args.seed,
    )
    output_dir = args.output_dir.resolve()
    plan_path = output_dir / PLAN_NAME
    report_path = output_dir / REPORT_NAME
    if not args.overwrite and (
        report_path.exists() or (args.dry_run and plan_path.exists())
    ):
        raise FileExistsError(
            "probe output already exists; choose another output directory or "
            "pass --overwrite"
        )
    _write_json(plan_path, plan.to_summary())
    print(
        "[INFO] "
        f"instance={plan.instance_id} | contract={plan.contract_sha256} | "
        f"node_limit={plan.node_limit} | max_samples={plan.max_samples}"
    )
    print("[INFO] callback mode is passive; no cuts, lazy constraints, or hints")
    print(f"[INFO] Plan: {plan_path}")
    if args.dry_run:
        return 0

    report = run_probe(plan)
    _write_json(report_path, report)
    observations = report["observations"]
    print(
        "[INFO] "
        f"MIPNODE callbacks={observations['mipnode_callback_calls']} | "
        f"samples={observations['samples_recorded']} | "
        "exact_subproblem_materialization=false"
    )
    print(f"[INFO] Report: {report_path}")
    if observations["callback_error_count"]:
        raise FeasibilityProbeError("one or more MIPNODE callback queries failed")
    if observations["samples_recorded"] == 0:
        raise FeasibilityProbeError(
            "no optimal MIPNODE event was observed; repeat with another instance "
            "or verify that optimization is running locally"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
