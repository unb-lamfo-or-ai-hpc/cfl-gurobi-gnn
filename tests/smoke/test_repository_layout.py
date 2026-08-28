"""Dependency-free smoke tests for the repository contract."""

import importlib
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "cfl_gnn"


def test_lightweight_package_import() -> None:
    package = importlib.import_module("cfl_gnn")
    assert package.__version__ == "0.1.0"


def test_stable_cli_modules_exist() -> None:
    expected = {
        "audit_collection.py",
        "audit_dataset.py",
        "benchmark_gurobi.py",
        "build_dataset.py",
        "collect_incumbents.py",
        "evaluate.py",
        "generate_hints.py",
        "graph_clustering.py",
        "graph_statistics.py",
        "graph_xray.py",
        "train_distributed.py",
        "train_serial.py",
    }
    assert expected <= {path.name for path in (PACKAGE_ROOT / "cli").glob("*.py")}


def test_active_python_filenames_are_not_versioned() -> None:
    versioned = [
        path.relative_to(PACKAGE_ROOT)
        for path in PACKAGE_ROOT.rglob("*.py")
        if re.search(r"_v\d+$", path.stem)
    ]
    assert versioned == []


def test_slurm_scripts_do_not_reference_removed_source_tree() -> None:
    removed_fragments = (
        "src/data_transformation/",
        "src/graph_transform/",
        "src/gnn/",
        "src/gurobi_solver/",
    )
    for script in (PROJECT_ROOT / "scripts" / "slurm").rglob("*.sbs"):
        contents = script.read_text(encoding="utf-8")
        assert not any(fragment in contents for fragment in removed_fragments)


def test_cfl_minimization_override_is_preserved() -> None:
    collector = (PACKAGE_ROOT / "pipelines" / "gurobi_incumbents.py").read_text(
        encoding="utf-8"
    )
    assert "model.ModelSense = GRB.MINIMIZE" in collector


def test_build_cli_reexports_legacy_pickle_schema_names() -> None:
    entrypoint = (PACKAGE_ROOT / "cli" / "build_dataset.py").read_text(
        encoding="utf-8"
    )
    for schema_name in ("ConstraintFeatures", "ModelFeatures", "VariableFeatures"):
        assert schema_name in entrypoint
