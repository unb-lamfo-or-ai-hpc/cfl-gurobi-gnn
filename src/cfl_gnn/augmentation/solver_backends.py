"""Thin Gurobi and PySCIPOpt writers for canonical local branching forms."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .local_branching import (
    AugmentationError,
    LocalBranchingConstraint,
    VariableDomain,
)


@dataclass(frozen=True, slots=True)
class ParentInspection:
    variables: Sequence[VariableDomain]
    original_objective_sense: str


def _canonical_type(raw_type: str, lower_bound: float, upper_bound: float) -> str:
    normalized = raw_type.upper()
    if normalized in {"B", "BINARY"} or (
        normalized in {"I", "INTEGER"}
        and lower_bound >= -1e-9
        and upper_bound <= 1.0 + 1e-9
    ):
        return "BINARY"
    if normalized in {"I", "INTEGER", "IMPLINT", "IMPLICIT_INTEGER"}:
        return "INTEGER"
    return "CONTINUOUS"


class GurobiBackend:
    name = "gurobi"

    @staticmethod
    def _load(path: Path):
        try:
            import gurobipy as gp
        except ImportError as error:
            raise AugmentationError("gurobipy is required for the Gurobi arm") from error
        model = gp.read(str(path))
        return gp, model

    def inspect(self, path: Path) -> ParentInspection:
        _, model = self._load(path)
        variables = tuple(
            VariableDomain(
                name=str(variable.VarName),
                canonical_type=_canonical_type(
                    str(variable.VType), float(variable.LB), float(variable.UB)
                ),
                lower_bound=float(variable.LB),
                upper_bound=float(variable.UB),
            )
            for variable in model.getVars()
        )
        sense = "MAXIMIZE" if int(model.ModelSense) == -1 else "MINIMIZE"
        model.dispose()
        return ParentInspection(variables, sense)

    def write_variant(
        self,
        parent_path: Path,
        output_path: Path,
        constraint: LocalBranchingConstraint,
    ) -> dict[str, str]:
        gp, model = self._load(parent_path)
        parent_constraint_count = int(model.NumConstrs)
        variables = {str(variable.VarName): variable for variable in model.getVars()}
        missing = sorted(set(constraint.coefficients) - set(variables))
        if missing:
            model.dispose()
            raise AugmentationError("Gurobi parent variable names changed during writing")
        expression = gp.LinExpr()
        expression.addTerms(
            [constraint.coefficients[name] for name in constraint.coefficients],
            [variables[name] for name in constraint.coefficients],
        )
        model.ModelSense = 1
        model.addConstr(
            expression <= constraint.rhs,
            name=f"mvp_local_branching_r{constraint.radius}",
        )
        model.update()
        variant_constraint_count = int(model.NumConstrs)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model.write(str(output_path))
        version = ".".join(str(item) for item in gp.gurobi.version())
        model.dispose()
        return {
            "writer": "gurobipy.Model.write",
            "artifact_format": "lp",
            "solver_version": version,
            "effective_objective_sense": "MINIMIZE",
            "parent_constraint_count": parent_constraint_count,
            "variant_constraint_count": variant_constraint_count,
            "constraint_count_delta": variant_constraint_count - parent_constraint_count,
        }


class PyScipOptBackend:
    name = "scip"

    @staticmethod
    def _load(path: Path):
        try:
            import pyscipopt
            from pyscipopt import Model
        except ImportError as error:
            raise AugmentationError("pyscipopt is required for the SCIP arm") from error
        model = Model()
        model.hideOutput(True)
        model.readProblem(str(path))
        return pyscipopt, model

    def inspect(self, path: Path) -> ParentInspection:
        _, model = self._load(path)
        variables = tuple(
            VariableDomain(
                name=str(variable.name),
                canonical_type=_canonical_type(
                    str(variable.vtype()),
                    float(variable.getLbOriginal()),
                    float(variable.getUbOriginal()),
                ),
                lower_bound=float(variable.getLbOriginal()),
                upper_bound=float(variable.getUbOriginal()),
            )
            for variable in model.getVars(transformed=False)
        )
        sense = str(model.getObjectiveSense()).upper()
        model.freeProb()
        return ParentInspection(variables, sense)

    def write_variant(
        self,
        parent_path: Path,
        output_path: Path,
        constraint: LocalBranchingConstraint,
    ) -> dict[str, str]:
        pyscipopt, model = self._load(parent_path)
        parent_constraint_count = int(model.getNConss())
        variables = {
            str(variable.name): variable
            for variable in model.getVars(transformed=False)
        }
        missing = sorted(set(constraint.coefficients) - set(variables))
        if missing:
            model.freeProb()
            raise AugmentationError("SCIP parent variable names changed during writing")
        expression = pyscipopt.quicksum(
            coefficient * variables[name]
            for name, coefficient in constraint.coefficients.items()
        )
        model.setMinimize()
        model.addCons(
            expression <= constraint.rhs,
            name=f"mvp_local_branching_r{constraint.radius}",
        )
        variant_constraint_count = int(model.getNConss())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model.writeProblem(str(output_path), trans=False)
        version = str(getattr(pyscipopt, "__version__", "unknown"))
        model.freeProb()
        return {
            "writer": "pyscipopt.Model.writeProblem_original",
            "artifact_format": "lp",
            "solver_version": version,
            "effective_objective_sense": "MINIMIZE",
            "parent_constraint_count": parent_constraint_count,
            "variant_constraint_count": variant_constraint_count,
            "constraint_count_delta": variant_constraint_count - parent_constraint_count,
        }
