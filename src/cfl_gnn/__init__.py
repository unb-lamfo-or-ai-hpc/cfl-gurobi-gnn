"""CFL Neural Diving research package.

The top-level package deliberately avoids importing solver and deep-learning
dependencies.  This keeps repository tooling and lightweight diagnostics usable
on machines without Gurobi, CUDA, or PyTorch Geometric.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
