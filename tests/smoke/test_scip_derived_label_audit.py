from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.analysis import scip_derived_label_audit as audit
from cfl_gnn.graph.instance_provenance import sha256_file


def _artifacts(tmp_path: Path) -> tuple[Path, list[Path], Path]:
    root = tmp_path / "root_mip_baseline.lp"
    nodes = [tmp_path / "node_000_2_mip.lp", tmp_path / "node_001_4_mip.lp"]
    root.write_text("root", encoding="utf-8")
    for index, node in enumerate(nodes):
        node.write_text(f"node-{index}", encoding="utf-8")
    report = tmp_path / "scip_domain_graph_observability_report.json"
    report.write_text(
        json.dumps(
            {
                "contract_sha256": "a" * 64,
                "gate_status": "passed",
                "root_mip": {
                    "file_name": root.name,
                    "sha256": sha256_file(root),
                },
                "node_mips": [
                    {"file_name": node.name, "sha256": sha256_file(node)}
                    for node in nodes
                ],
                "decision": {"graph_observability_proven": True},
            }
        ),
        encoding="utf-8",
    )
    return root, nodes, report


def _root_domains() -> list[dict[str, object]]:
    return [
        {
            "name": "x0",
            "raw_type": "I",
            "canonical_type": "B",
            "lb": 0.0,
            "ub": 1.0,
        },
        {
            "name": "y",
            "raw_type": "C",
            "canonical_type": "C",
            "lb": 0.0,
            "ub": 10.0,
        },
    ]


def _candidate_variables() -> list[dict[str, object]]:
    return [
        {"name": "x0", "raw_type": "INTEGER", "lb": 1.0, "ub": 1.0, "value": 1.0},
        {"name": "y", "raw_type": "CONTINUOUS", "lb": 0.0, "ub": 10.0, "value": 2.5},
    ]


def _worker_payload() -> dict[str, object]:
    return {
        "candidate_file_name": "node_000_2_mip.lp",
        "candidate_sha256": "b" * 64,
        "label_source": "independent_pyscipopt_optimization",
        "fresh_process": True,
        "pre_solve_solution_count": 0,
        "warm_start_supplied": False,
        "parent_incumbent_consumed": False,
        "objective_sense": "minimize",
        "solve_status": "optimal",
        "solution_count": 1,
        "objective": 3.5,
        "solution_objective": 3.5,
        "best_bound": 3.5,
        "mip_gap": 0.0,
        "runtime": 0.1,
        "node_count": 1,
        "solver_feasibility_check": True,
    }


def test_plan_binds_exact_passed_graph_audit_and_is_path_sanitized(
    tmp_path: Path,
) -> None:
    root, nodes, report = _artifacts(tmp_path)
    first = audit.build_audit_plan(
        root_mip=root,
        node_mips=list(reversed(nodes)),
        graph_audit_report=report,
        output_dir=tmp_path / "one",
    )
    second = audit.build_audit_plan(
        root_mip=root,
        node_mips=nodes,
        graph_audit_report=report,
        output_dir=tmp_path / "two",
    )

    assert first.contract_sha256 == second.contract_sha256
    assert [path.name for path in first.node_mips] == sorted(path.name for path in nodes)
    serialized = json.dumps(first.to_summary())
    assert str(tmp_path) not in serialized
    assert first.to_summary()["solve_contract"]["fresh_process_per_candidate"] is True
    assert first.to_summary()["solve_contract"]["warm_start_supplied"] is False
    assert first.to_summary()["eligibility"]["dataset_eligible"] is False


def test_plan_rejects_artifact_not_approved_by_graph_audit(tmp_path: Path) -> None:
    root, nodes, report = _artifacts(tmp_path)
    nodes[0].write_text("changed-after-audit", encoding="utf-8")

    with pytest.raises(audit.DerivedLabelAuditError, match="exactly match"):
        audit.build_audit_plan(
            root_mip=root,
            node_mips=nodes,
            graph_audit_report=report,
            output_dir=tmp_path / "output",
        )


def test_plan_rejects_unpassed_graph_audit(tmp_path: Path) -> None:
    root, nodes, report = _artifacts(tmp_path)
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["gate_status"] = "failed"
    report.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(audit.DerivedLabelAuditError, match="did not pass"):
        audit.build_audit_plan(
            root_mip=root,
            node_mips=nodes,
            graph_audit_report=report,
            output_dir=tmp_path / "output",
        )


@pytest.mark.parametrize(
    ("raw", "lower", "upper", "expected"),
    [
        ("BINARY", 0.0, 1.0, "B"),
        ("INTEGER", 0.0, 1.0, "B"),
        ("INTEGER", 1.0, 1.0, "B"),
        ("INTEGER", 0.0, 2.0, "I"),
        ("CONTINUOUS", 0.0, 1.0, "C"),
    ],
)
def test_canonical_root_type(
    raw: str, lower: float, upper: float, expected: str
) -> None:
    assert audit.canonical_root_type(raw, lower, upper) == expected


def test_solution_vector_validates_domain_restriction_and_binary_semantics() -> None:
    candidate = _candidate_variables()
    result = audit.validate_solution_vector(
        _root_domains(), candidate, tolerance=1e-6
    )

    assert result["variable_sets_match"] is True
    assert result["canonical_types_preserved"] is True
    assert result["candidate_domain_subset_of_root"] is True
    assert result["strict_domain_restriction_count"] == 1
    assert result["solution_within_candidate_bounds"] is True
    assert result["integrality_preserved"] is True
    assert candidate[0]["canonical_type"] == "B"


def test_solution_vector_rejects_parent_domain_expansion_and_fractional_integer() -> None:
    candidate = _candidate_variables()
    candidate[0].update({"lb": -1.0, "ub": 2.0, "value": 0.5})

    result = audit.validate_solution_vector(
        _root_domains(), candidate, tolerance=1e-6
    )

    assert result["candidate_domain_subset_of_root"] is False
    assert result["integrality_preserved"] is False
    assert result["mismatch_count"] >= 2


def test_solution_vector_rejects_missing_variable() -> None:
    result = audit.validate_solution_vector(
        _root_domains(), _candidate_variables()[:1], tolerance=1e-6
    )

    assert result["variable_sets_match"] is False
    assert any(
        mismatch["reason_code"] == "missing_candidate_variable"
        for mismatch in result["mismatches"]
    )


def test_candidate_becomes_label_eligible_only_when_all_checks_pass() -> None:
    domain = audit.validate_solution_vector(
        _root_domains(), _candidate_variables(), tolerance=1e-6
    )
    result = audit.evaluate_candidate_label(
        _worker_payload(),
        domain,
        solution_file_name="node.solution.json.gz",
        solution_sha256="c" * 64,
        optimality_tolerance=1e-8,
    )

    assert all(result["checks"].values())
    assert result["label_eligible"] is True
    assert result["dataset_eligible"] is False
    assert result["scientific_reporting_eligible"] is False
    assert result["reason_code"] == "independent_optimal_label_validated"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pre_solve_solution_count", 1),
        ("warm_start_supplied", True),
        ("parent_incumbent_consumed", True),
        ("solve_status", "timelimit"),
        ("mip_gap", 0.1),
        ("solver_feasibility_check", False),
    ],
)
def test_candidate_fails_closed_when_independence_or_optimality_fails(
    field: str, value: object
) -> None:
    payload = _worker_payload()
    payload[field] = value
    domain = audit.validate_solution_vector(
        _root_domains(), _candidate_variables(), tolerance=1e-6
    )

    result = audit.evaluate_candidate_label(
        payload,
        domain,
        solution_file_name="node.solution.json.gz",
        solution_sha256="c" * 64,
        optimality_tolerance=1e-8,
    )

    assert result["label_eligible"] is False
    assert result["dataset_eligible"] is False


def test_overall_gate_requires_every_candidate_label() -> None:
    passed = {
        "label_eligible": True,
        "checks": {
            "optimal_status": True,
            "solver_feasibility_check": True,
            "candidate_domain_subset_of_root": True,
            "strict_domain_restriction": True,
        },
    }
    failed = {
        "label_eligible": False,
        "checks": {
            "optimal_status": False,
            "solver_feasibility_check": True,
            "candidate_domain_subset_of_root": True,
            "strict_domain_restriction": True,
        },
    }

    assert audit.summarize_candidate_results([passed, passed])["gate_passed"] is True
    assert audit.summarize_candidate_results([passed, failed])["gate_passed"] is False


def test_dry_run_does_not_import_pyscipopt(tmp_path: Path) -> None:
    root, nodes, report = _artifacts(tmp_path)
    output = tmp_path / "output"

    result = audit.main(
        [
            "--root_mip",
            str(root),
            "--node_mips",
            *(str(node) for node in nodes),
            "--graph_audit_report",
            str(report),
            "--output_dir",
            str(output),
            "--dry_run",
        ]
    )

    assert result == 0
    assert (output / audit.PLAN_NAME).is_file()
    assert "pyscipopt" not in audit.__dict__
    assert not (output / audit.REPORT_NAME).exists()


def test_source_excludes_pyomo_parent_labels_and_dataset_writes() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8")
    assert "import pyomo" not in source
    assert "from pyomo" not in source
    assert "torch.save" not in source
    assert "solutions.pickle" not in source
    assert "incumbents.parquet" not in source
    assert '"parent_incumbent_consumed": False' in source
    assert '"dataset_eligible": False' in source
