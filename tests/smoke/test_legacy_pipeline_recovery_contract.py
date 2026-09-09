"""Smoke tests for the PR #41 legacy recovery contract."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    PROJECT_ROOT
    / "configs"
    / "audits"
    / "legacy_pipeline_recovery_v1.json"
)
DIAGNOSTIC_PATH = (
    PROJECT_ROOT
    / "tools"
    / "diagnostics"
    / "audit_legacy_pipeline_recovery.py"
)


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _diagnostic_module():
    specification = importlib.util.spec_from_file_location(
        "audit_legacy_pipeline_recovery",
        DIAGNOSTIC_PATH,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_contract_pins_the_reviewed_snapshots() -> None:
    contract = _contract()
    assert contract["pinned_commits"] == {
        "legacy": "9903c1dc66f65e9497d7faa2d8d4f3ee414a0f42",
        "current": "9f7da7d206129fcd72c72d1a8d682bf3cf413fde",
    }


def test_contract_encodes_gurobi_first_graph_authority() -> None:
    contract = _contract()
    boundary = contract["scientific_boundary"]
    labels = contract["label_contract"]
    root_lp = contract["root_lp_feature_contract"]

    assert boundary["graph_authority_solver"] == "gurobi"
    assert boundary["comparison_solvers"] == ["gurobi", "scip"]
    assert boundary["graph_unit"] == "mathematical_mip"
    assert boundary["incumbent_graph_policy"] == "prohibited"
    assert labels["original_mip_graph_count_per_parent"] == 1
    assert labels["synthetic_mip_graph_count_per_artifact"] == 1
    assert labels["graph_features_independent_of_label_solver"] is True
    assert root_lp["authority_solver"] == "gurobi"
    assert root_lp["zero_ablation_allowed"] is False
    assert root_lp["missing_value_policy"] == "fail_closed"


def test_contract_excludes_hard_fixing_from_primary_path() -> None:
    contract = _contract()
    guidance = contract["guidance_contract"]

    assert guidance["primary"] == "gurobi_variable_hints"
    assert guidance["secondary"] == "gurobi_partial_mip_start"
    assert guidance["scip_role"] == "comparison_only"
    assert guidance["hard_domain_fixing_primary_allowed"] is False
    assert guidance["pr37_evidence_classification"] == (
        "historical_engineering_only"
    )
    assert guidance["held_out_test_method_selection_allowed"] is False


def test_contract_maps_all_preserved_baseline_components() -> None:
    contract = _contract()
    components = contract["components"]
    expected_ids = {
        "gurobi_parent_collection",
        "phase1_descriptive_audit",
        "bipartite_graph_builder",
        "graph_dataset_audit",
        "graph_statistics",
        "graph_clustering",
        "gasse_model",
        "serial_trainer",
        "distributed_trainer",
        "model_evaluator",
        "gurobi_variable_hints",
        "gurobi_benchmark",
    }

    assert {component["id"] for component in components} == expected_ids
    assert len(components) == len(expected_ids)
    assert all(component["legacy_path"] for component in components)
    assert all(component["current_path"] for component in components)
    assert all(component["required_action"] for component in components)


def test_static_diagnostic_passes_without_requiring_git_history() -> None:
    module = _diagnostic_module()
    report = module.audit_contract(
        CONTRACT_PATH,
        PROJECT_ROOT,
        history_mode="skip",
    )

    assert report["gate_status"] == "passed"
    assert report["errors"] == []
    assert len(report["components"]) == 12
    assert all(report["checks"].values())
    assert report["decision"]["pipeline_behavior_changed"] is False
    assert report["decision"]["next_gate"].startswith("pr42_")


def test_diagnostic_cli_writes_a_sanitized_report(tmp_path: Path) -> None:
    output = tmp_path / "recovery_audit.json"
    result = subprocess.run(
        [
            sys.executable,
            str(DIAGNOSTIC_PATH),
            "--repo-root",
            str(PROJECT_ROOT),
            "--contract",
            str(CONTRACT_PATH),
            "--history-mode",
            "skip",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    serialized = output.read_text(encoding="utf-8")
    assert report["gate_status"] == "passed"
    assert "pipeline_behavior_changed" in serialized
    assert str(PROJECT_ROOT) not in serialized
    assert "secrets/" not in serialized
    assert "gurobi.lic" not in serialized


def test_recovery_documents_record_the_methodological_boundary() -> None:
    audit = (
        PROJECT_ROOT / "docs" / "research" / "legacy-current-pipeline-audit.md"
    ).read_text(encoding="utf-8")
    methods = (
        PROJECT_ROOT / "docs" / "research" / "neural-guidance-methods-review.md"
    ).read_text(encoding="utf-8")
    decision = (
        PROJECT_ROOT
        / "docs"
        / "decisions"
        / "0013-gurobi-first-legacy-recovery.md"
    ).read_text(encoding="utf-8")

    for text in (audit, decision):
        assert "Gurobi" in text
        assert "one graph" in text.lower()
        assert "root-LP" in text
        assert "Pyomo" in text
    assert "VarHintVal" in methods
    assert "partial MIP start" in methods
    assert "restricted sub-MIP" in methods
    assert "https://arxiv.org/abs/2012.13349" in methods
    assert "held-out test" in methods

