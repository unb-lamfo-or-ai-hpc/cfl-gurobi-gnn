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
        "solution_source": "independent_pyscipopt_optimization",
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
        "mip_gap_relative": 0.0,
        "mip_gap_percent": 0.0,
        "execution_time_seconds": 0.1,
        "reading_time_seconds": 0.01,
        "presolving_time_seconds": 0.02,
        "nodes_current_run": 1,
        "nodes_total": 1,
        "best_incumbent_discovery_time_seconds": 0.05,
        "incumbent_trace": [
            {
                "incumbent_index": 0,
                "incumbent_objective": 3.5,
                "incumbent_discovery_time_seconds": 0.05,
                "incumbent_mip_gap_relative_at_discovery": None,
                "incumbent_mip_gap_percent_at_discovery": None,
                "mip_gap_at_discovery_availability": (
                    audit.INCUMBENT_GAP_AVAILABILITY
                ),
                "observation_method": (
                    "postsolve_stored_solution_reconstruction"
                ),
            }
        ],
        "incumbent_trace_error_count": 0,
        "incumbent_trace_audit": {
            "incumbent_trace_present": True,
            "incumbent_times_monotonic": True,
            "incumbent_objectives_monotonic": True,
            "final_incumbent_objective_matches": True,
            "final_incumbent_discovery_time_matches": True,
            "incumbent_gap_semantics_explicit": True,
            "incumbent_trace_consistent": True,
        },
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
    assert first.to_summary()["schema_version"] == 3
    assert [path.name for path in first.node_mips] == sorted(path.name for path in nodes)
    serialized = json.dumps(first.to_summary())
    assert str(tmp_path) not in serialized
    assert first.to_summary()["solve_contract"]["fresh_process_per_candidate"] is True
    assert first.to_summary()["solve_contract"]["warm_start_supplied"] is False
    assert first.to_summary()["solve_contract"]["max_parallel_candidates"] == 4
    assert first.to_summary()["performance_feature_tags"] == (
        audit.PERFORMANCE_FEATURE_TAGS
    )
    assert first.to_summary()["performance_feature_availability"][
        "incumbent_mip_gap_at_discovery"
    ] == audit.INCUMBENT_GAP_AVAILABILITY
    assert first.to_summary()["eligibility"]["dataset_eligible"] is False


def test_incumbent_trace_is_reconstructed_from_postsolve_solutions() -> None:
    observations = [
        {"source_index": 0, "objective": 8.0, "discovery_time_seconds": 4.0},
        {"source_index": 1, "objective": 10.0, "discovery_time_seconds": 1.0},
        {"source_index": 2, "objective": 9.0, "discovery_time_seconds": 2.0},
        {"source_index": 3, "objective": 9.5, "discovery_time_seconds": 3.0},
        {"source_index": 4, "objective": 8.0, "discovery_time_seconds": 5.0},
    ]

    trace = audit.reconstruct_incumbent_trace(
        observations,
        objective_sense="minimize",
    )

    assert [record["incumbent_objective"] for record in trace] == [10.0, 9.0, 8.0]
    assert [record["incumbent_discovery_time_seconds"] for record in trace] == [
        1.0,
        2.0,
        4.0,
    ]
    assert all(
        record["incumbent_mip_gap_relative_at_discovery"] is None
        and record["incumbent_mip_gap_percent_at_discovery"] is None
        and record["mip_gap_at_discovery_availability"]
        == audit.INCUMBENT_GAP_AVAILABILITY
        for record in trace
    )


def test_incumbent_trace_audit_requires_final_solution_match() -> None:
    trace = audit.reconstruct_incumbent_trace(
        [
            {"source_index": 0, "objective": 5.0, "discovery_time_seconds": 1.0},
            {"source_index": 1, "objective": 4.0, "discovery_time_seconds": 2.0},
        ],
        objective_sense="minimize",
    )

    passed = audit.validate_incumbent_trace(
        trace,
        objective_sense="minimize",
        final_objective=4.0,
        final_discovery_time=2.0,
        tolerance=1e-8,
    )
    failed = audit.validate_incumbent_trace(
        trace,
        objective_sense="minimize",
        final_objective=3.0,
        final_discovery_time=2.0,
        tolerance=1e-8,
    )

    assert passed["incumbent_trace_consistent"] is True
    assert failed["final_incumbent_objective_matches"] is False
    assert failed["incumbent_trace_consistent"] is False


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
    assert result["gate_status"] == "passed"
    assert result["solution_evidence_status"] == "validated_feasible"
    assert result["optimality_status"] == "proven_optimal"
    assert result["dataset_eligible"] is False
    assert result["scientific_reporting_eligible"] is False
    assert result["reason_code"] == "independent_optimal_label_validated"
    assert result["performance_features"]["instance"] == {
        "execution_time_seconds": 0.1,
        "mip_gap_relative": 0.0,
        "mip_gap_percent": 0.0,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pre_solve_solution_count", 1),
        ("warm_start_supplied", True),
        ("parent_incumbent_consumed", True),
        ("solve_status", "timelimit"),
        ("mip_gap_relative", 0.1),
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


def test_candidate_fails_closed_for_inconsistent_incumbent_trace() -> None:
    payload = _worker_payload()
    payload["incumbent_trace_audit"] = {
        **payload["incumbent_trace_audit"],
        "final_incumbent_objective_matches": False,
        "incumbent_trace_consistent": False,
    }
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

    assert result["checks"]["incumbent_trace_consistent"] is False
    assert result["feasible_solution_evidence"] is False
    assert result["label_eligible"] is False
    assert result["gate_status"] == "failed"


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


def test_feasible_time_limit_is_inconclusive_not_execution_failure() -> None:
    payload = _worker_payload()
    payload.update(
        {
            "solve_status": "timelimit",
            "mip_gap_relative": 25.0,
            "mip_gap_percent": 2500.0,
            "execution_time_seconds": 3600.0,
        }
    )
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

    assert result["execution_status"] == "completed"
    assert result["solution_evidence_status"] == "validated_feasible"
    assert result["feasible_solution_evidence"] is True
    assert result["optimality_status"] == "not_proven_timelimit"
    assert result["gate_status"] == "inconclusive"
    assert result["label_eligible"] is False
    assert result["label_source"] is None
    assert result["reason_code"] == "feasible_nonoptimal_timelimit"
    assert result["performance_features"]["instance"]["mip_gap_percent"] == 2500.0


def test_overall_gate_classifies_all_feasible_nonoptimal_as_inconclusive() -> None:
    record = {
        "execution_status": "completed",
        "feasible_solution_evidence": True,
        "label_eligible": False,
        "gate_status": "inconclusive",
        "checks": {
            "optimal_status": False,
            "solver_feasibility_check": True,
            "candidate_domain_subset_of_root": True,
            "strict_domain_restriction": True,
        },
    }

    summary = audit.summarize_candidate_results([record, record])

    assert summary["gate_status"] == "inconclusive"
    assert summary["candidate_execution_completed"] == 2
    assert summary["feasible_solution_evidence"] == 2
    assert summary["labels_validated"] == 0
    assert summary["gate_passed"] is False


def test_completed_worker_artifact_is_reused_only_for_exact_contract(
    tmp_path: Path,
) -> None:
    root, nodes, report = _artifacts(tmp_path)
    plan = audit.build_audit_plan(
        root_mip=root,
        node_mips=nodes,
        graph_audit_report=report,
        output_dir=tmp_path / "output",
    )
    solution = tmp_path / "candidate.solution.json.gz"
    payload = {
        "schema_version": audit.SCHEMA_VERSION,
        "contract_sha256": plan.contract_sha256,
        "candidate_file_name": nodes[0].name,
        "candidate_sha256": sha256_file(nodes[0]),
        "fresh_process": True,
    }
    audit._write_gzip_json(solution, payload)

    assert audit._load_reusable_worker_payload(solution, nodes[0], plan) == payload
    payload["contract_sha256"] = "f" * 64
    audit._write_gzip_json(solution, payload)
    assert audit._load_reusable_worker_payload(solution, nodes[0], plan) is None


def test_run_audit_uses_parallel_orchestration_and_deterministic_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, nodes, graph_report = _artifacts(tmp_path)
    plan = audit.build_audit_plan(
        root_mip=root,
        node_mips=nodes,
        graph_audit_report=graph_report,
        output_dir=tmp_path / "output",
        max_parallel=2,
    )
    monkeypatch.setattr(audit, "_model_domain_records", lambda _path: [])

    def fake_candidate(index: int, candidate: Path, *_args: object, **_kwargs: object):
        return index, {
            "candidate_file_name": candidate.name,
            "execution_status": "completed",
            "feasible_solution_evidence": True,
            "label_eligible": False,
            "gate_status": "inconclusive",
            "worker_result_reused": index == 0,
            "checks": {
                "optimal_status": False,
                "solver_feasibility_check": True,
                "candidate_domain_subset_of_root": True,
                "strict_domain_restriction": True,
            },
        }

    monkeypatch.setattr(audit, "_solve_and_evaluate_candidate", fake_candidate)

    result = audit.run_audit(plan)

    assert result["execution"] == {
        "status": "completed",
        "mode": "parallel_fresh_processes",
        "max_parallel_candidates": 2,
        "workers_used": 2,
        "worker_results_reused": 1,
        "worker_results_executed": 1,
    }
    assert result["gate_status"] == "inconclusive"
    rows = (plan.output_dir / audit.PER_CANDIDATE_NAME).read_text(
        encoding="utf-8"
    ).splitlines()
    assert [json.loads(row)["candidate_file_name"] for row in rows] == [
        node.name for node in nodes
    ]


def test_inconclusive_completed_probe_returns_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, nodes, graph_report = _artifacts(tmp_path)
    output = tmp_path / "output"
    monkeypatch.setattr(
        audit,
        "run_audit",
        lambda *_args, **_kwargs: {
            "gate_status": "inconclusive",
            "summary": {"labels_validated": 0, "candidates_audited": 2},
        },
    )

    result = audit.main(
        [
            "--root_mip",
            str(root),
            "--node_mips",
            *(str(node) for node in nodes),
            "--graph_audit_report",
            str(graph_report),
            "--output_dir",
            str(output),
        ]
    )

    assert result == 0
    assert json.loads((output / audit.REPORT_NAME).read_text())["gate_status"] == (
        "inconclusive"
    )


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
    assert "BESTSOLFOUND" not in source
    assert "attachEventHandlerCallback" not in source
