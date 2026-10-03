"""Canonical public API for original-parent solution collection.

Both solver-specific CLIs delegate to this shared contract.  The implementation
currently lives in the historical ``scip_parent_solutions`` module so existing
imports and serialized research artifacts remain readable.
"""

from cfl_gnn.pipelines.scip_parent_solutions import (
    DEFAULT_CONFIG,
    INCUMBENTS_NAME,
    PLAN_NAME,
    REPORT_NAME,
    SCHEMA_VERSION,
    SOLUTION_NAME,
    VARIABLE_ORDER_NAME,
    ParentSolveError,
    ParentSolvePlan,
    ScipParentSolveError,
    build_parser,
    build_plan,
    evaluate_solution,
    main,
    plan_name,
    report_name,
    run,
    worker_request,
)

__all__ = [
    "DEFAULT_CONFIG",
    "INCUMBENTS_NAME",
    "PLAN_NAME",
    "REPORT_NAME",
    "SCHEMA_VERSION",
    "SOLUTION_NAME",
    "VARIABLE_ORDER_NAME",
    "ParentSolveError",
    "ParentSolvePlan",
    "ScipParentSolveError",
    "build_parser",
    "build_plan",
    "evaluate_solution",
    "main",
    "plan_name",
    "report_name",
    "run",
    "worker_request",
]
