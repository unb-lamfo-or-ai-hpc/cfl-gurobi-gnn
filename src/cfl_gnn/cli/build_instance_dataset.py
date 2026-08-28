"""Build the Gurobi one-parent-instance baseline dataset.

Schema names are re-exported in ``__main__`` for legacy pickle compatibility.
"""

from cfl_gnn.artifacts.schemas import (
    ConstraintFeatures,
    ModelFeatures,
    VariableFeatures,
)
from cfl_gnn.graph.build_instance_dataset import main

__all__ = ["ConstraintFeatures", "ModelFeatures", "VariableFeatures", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
