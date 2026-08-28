"""Build the PyG dataset from collected artifacts.

The schema names are re-exported in ``__main__`` so pickles written by the
legacy script remain loadable during the repository-layout transition.
"""

from cfl_gnn.graph.build_dataset import (
    ConstraintFeatures,
    ModelFeatures,
    VariableFeatures,
    main,
)

__all__ = ["ConstraintFeatures", "ModelFeatures", "VariableFeatures", "main"]


if __name__ == "__main__":
    main()
