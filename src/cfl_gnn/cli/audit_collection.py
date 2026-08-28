"""Audit collected Gurobi artifacts.

The schema names are re-exported in ``__main__`` so pickles written by the
legacy collection script remain loadable during the repository transition.
"""

from cfl_gnn.analysis.collection_audit import (
    ConstraintFeatures,
    ModelFeatures,
    VariableFeatures,
    main,
)

__all__ = ["ConstraintFeatures", "ModelFeatures", "VariableFeatures", "main"]


if __name__ == "__main__":
    main()
