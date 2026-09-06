"""Solver integrations."""

from .gurobi_solution import (
    GurobiIncumbentCollector,
    solve_named_mip as solve_named_gurobi_mip,
)
from .pyscipopt_solution import (
    OnlineIncumbentCollector,
    audit_incumbent_trace,
    solve_named_mip,
)

solve_named_pyscipopt_mip = solve_named_mip

__all__ = (
    "GurobiIncumbentCollector",
    "OnlineIncumbentCollector",
    "audit_incumbent_trace",
    "solve_named_gurobi_mip",
    "solve_named_mip",
    "solve_named_pyscipopt_mip",
)

