"""Dedicated production execution directory; never use the home root as a spool."""

from pathlib import Path

from ..contract import require
from .policy import ascii_path

DIRECTORY_NAME = "cfl-gurobi-gnn-mvp30"
DEFAULT_EXECUTION_ROOT = f"/home/vrrcelestino/{DIRECTORY_NAME}"


def execution_root(value):
    original = Path(value)
    require(
        original.is_absolute() and not original.is_symlink(),
        "Explicit nonsymlink execution directory required",
    )
    root = ascii_path(original)
    require(
        root.name == DIRECTORY_NAME and root != Path.home().resolve(),
        "Dedicated MVP3 execution directory required; home is not an execution root",
    )
    return root


def run_paths(root, *paths):
    root = execution_root(root)
    runs = root / "runs"
    require(not runs.is_symlink(), "Execution runs directory cannot be a symlink")
    require(
        all(Path(path).is_absolute() for path in paths),
        "Absolute runtime paths required",
    )
    resolved = [ascii_path(path) for path in paths]
    require(
        all(path != runs and path.is_relative_to(runs) for path in resolved),
        "Runtime source, plans and outputs must stay inside execution_root/runs",
    )
    return resolved


def plan_paths(plan, *extra):
    paths = [
        plan["bundle"],
        *(slot["output"] for slot in plan["slots"].values()),
        *extra,
    ]
    run_paths(plan["execution_root"], *paths)
