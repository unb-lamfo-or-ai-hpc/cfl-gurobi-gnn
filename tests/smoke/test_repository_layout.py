"""Dependency-free smoke tests for the repository contract."""

import ast
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
        "audit_instance_training_split.py",
        "benchmark_gurobi.py",
        "build_instance_dataset.py",
        "build_dataset.py",
        "collect_incumbents.py",
        "evaluate.py",
        "generate_hints.py",
        "graph_clustering.py",
        "graph_statistics.py",
        "graph_xray.py",
        "plan_instance_folds.py",
        "train_instance_serial.py",
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


def test_slurm_launchers_use_supported_cli_arguments() -> None:
    slurm_root = PROJECT_ROOT / "scripts" / "slurm" / "dasci"
    hint_launcher = (slurm_root / "submit_step7_miphints_generator.sbs").read_text(
        encoding="utf-8"
    )
    audit_launcher = (slurm_root / "submit_step2_audit_data_gen.sbs").read_text(
        encoding="utf-8"
    )
    assert "--confidence" not in hint_launcher
    assert "--min_priority" in hint_launcher
    assert "--instance" not in audit_launcher
    assert "--categories" in audit_launcher


def test_toy_gasse_training_helpers_are_preserved() -> None:
    toy = (PROJECT_ROOT / "sandbox" / "toy_bipartite.py").read_text(
        encoding="utf-8"
    )
    scheme = PACKAGE_ROOT / "training" / "toy_scheme.py"
    assert scheme.is_file()
    assert "from cfl_gnn.training.toy_scheme import" in toy
    for helper in ("def train_model(", "def test_torch(", "def test_sklearn("):
        assert helper in scheme.read_text(encoding="utf-8")


def test_documented_pipeline_flags_match_the_cli_contract() -> None:
    documentation = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "README.md", PROJECT_ROOT / "docs" / "pipeline.md")
    )
    assert "--workers" not in documentation
    assert "--confidence" not in documentation


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


def test_instance_build_cli_reexports_legacy_pickle_schema_names() -> None:
    entrypoint = (PACKAGE_ROOT / "cli" / "build_instance_dataset.py").read_text(
        encoding="utf-8"
    )
    for schema_name in ("ConstraintFeatures", "ModelFeatures", "VariableFeatures"):
        assert schema_name in entrypoint


def test_instance_builder_keeps_inventory_return_and_writable_label_copy() -> None:
    builder_path = PACKAGE_ROOT / "graph" / "build_instance_dataset.py"
    builder = builder_path.read_text(encoding="utf-8")
    syntax_tree = ast.parse(builder)
    availability = next(
        node
        for node in syntax_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_is_available"
    )
    assert any(isinstance(node, ast.Return) for node in ast.walk(availability))
    assert "np.array(selected.solution_vector, dtype=np.float64, copy=True)" in builder


def test_audit_cli_reexports_legacy_pickle_schema_names() -> None:
    entrypoint = (PACKAGE_ROOT / "cli" / "audit_collection.py").read_text(
        encoding="utf-8"
    )
    for schema_name in ("ConstraintFeatures", "ModelFeatures", "VariableFeatures"):
        assert schema_name in entrypoint


def test_artifact_schemas_keep_legacy_field_order() -> None:
    from cfl_gnn.artifacts.schemas import (
        ConstraintFeatures,
        ModelFeatures,
        VariableFeatures,
    )

    assert ModelFeatures._fields == (
        "num_vars",
        "num_constrs",
        "num_binary",
        "num_integer",
        "num_continuous",
        "obj_sense",
        "obj_offset",
    )
    assert VariableFeatures._fields == (
        "types",
        "lower_bounds",
        "upper_bounds",
        "obj_coeffs",
    )
    assert ConstraintFeatures._fields == ("senses", "rhs_values", "row_norms")

