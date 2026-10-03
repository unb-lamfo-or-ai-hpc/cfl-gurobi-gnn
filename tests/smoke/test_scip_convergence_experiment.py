from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from cfl_gnn.analysis import scip_convergence_experiment as experiment
from cfl_gnn.analysis import scip_derived_label_audit as label_audit
from cfl_gnn.graph.instance_provenance import sha256_file


def _artifacts(tmp_path: Path) -> tuple[Path, list[Path], Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "root_mip_baseline.lp"
    nodes = [tmp_path / "node_000_2_mip.lp", tmp_path / "node_001_4_mip.lp"]
    root.write_text("root", encoding="utf-8")
    for index, node in enumerate(nodes):
        node.write_text(f"node-{index}", encoding="utf-8")
    graph_report = tmp_path / "scip_domain_graph_observability_report.json"
    graph_report.write_text(
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
    baseline = label_audit.build_audit_plan(
        root_mip=root,
        node_mips=nodes,
        graph_audit_report=graph_report,
        output_dir=tmp_path / "baseline-output",
    )
    baseline_plan = tmp_path / label_audit.PLAN_NAME
    baseline_plan.write_text(
        json.dumps(baseline.to_summary()),
        encoding="utf-8",
    )
    baseline_report = tmp_path / label_audit.REPORT_NAME
    baseline_report.write_text(
        json.dumps(
            {
                "schema_version": label_audit.SCHEMA_VERSION,
                "contract_sha256": baseline.contract_sha256,
                "probe_completed": True,
                "execution": {"status": "completed"},
                "gate_status": "inconclusive",
                "summary": {"all_feasible": True},
            }
        ),
        encoding="utf-8",
    )
    return root, nodes, graph_report, baseline_plan, baseline_report


def _plan(tmp_path: Path) -> experiment.ConvergencePlan:
    root, nodes, graph_report, baseline_plan, baseline_report = _artifacts(tmp_path)
    return experiment.build_experiment_plan(
        parent_instance_id="CFL_easy_instance_0",
        root_mip=root,
        node_mips=nodes,
        graph_audit_report=graph_report,
        baseline_plan=baseline_plan,
        baseline_report=baseline_report,
        output_dir=tmp_path / "output",
    )


def _record(candidate: str, profile: str, gap: float) -> dict[str, object]:
    return {
        "candidate_file_name": candidate,
        "profile_id": profile,
        "parent_instance_id": "CFL_easy_instance_0",
        "seed": 42,
        "gate_status": "inconclusive",
        "feasible_solution_evidence": True,
        "label_eligible": False,
        "solver_parameter_sha256": profile[0] * 64,
        "worker_result_reused": False,
        "checks": {"solver_parameter_fingerprint": True},
        "solve": {
            "mip_gap_relative": gap,
            "objective": 10.0 - gap,
            "best_bound": 9.0 + gap,
            "execution_time_seconds": 300.0,
        },
        "censoring": {
            "right_censored": True,
            "time_to_proven_optimality_seconds": None,
            "censoring_time_limit_seconds": 300.0,
        },
    }


def test_plan_is_deterministic_sanitized_and_precommits_profiles(tmp_path: Path) -> None:
    first = _plan(tmp_path)
    root, nodes, graph_report, baseline_plan, baseline_report = _artifacts(
        tmp_path / "second"
    )
    second = experiment.build_experiment_plan(
        parent_instance_id="CFL_easy_instance_0",
        root_mip=root,
        node_mips=list(reversed(nodes)),
        graph_audit_report=graph_report,
        baseline_plan=baseline_plan,
        baseline_report=baseline_report,
        output_dir=tmp_path / "other-output",
    )

    assert first.contract_sha256 == second.contract_sha256
    summary = first.to_summary()
    assert [profile["profile_id"] for profile in summary["profiles"]] == [
        "default",
        "feasibility",
        "optimality",
    ]
    assert summary["locked_controls"]["threads_per_scip"] == 1
    assert summary["locked_controls"]["warm_start_supplied"] is False
    assert summary["eligibility"]["profile_selection_eligible"] is False
    assert str(tmp_path) not in json.dumps(summary)


def test_plan_rejects_baseline_contract_mismatch(tmp_path: Path) -> None:
    root, nodes, graph_report, baseline_plan, baseline_report = _artifacts(tmp_path)
    payload = json.loads(baseline_report.read_text(encoding="utf-8"))
    payload["contract_sha256"] = "f" * 64
    baseline_report.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(experiment.ConvergenceExperimentError, match="mismatch"):
        experiment.build_experiment_plan(
            parent_instance_id="CFL_easy_instance_0",
            root_mip=root,
            node_mips=nodes,
            graph_audit_report=graph_report,
            baseline_plan=baseline_plan,
            baseline_report=baseline_report,
            output_dir=tmp_path / "output",
        )


def test_plan_rejects_path_like_parent_identifier(tmp_path: Path) -> None:
    root, nodes, graph_report, baseline_plan, baseline_report = _artifacts(tmp_path)
    with pytest.raises(ValueError, match="path-free"):
        experiment.build_experiment_plan(
            parent_instance_id="../parent",
            root_mip=root,
            node_mips=nodes,
            graph_audit_report=graph_report,
            baseline_plan=baseline_plan,
            baseline_report=baseline_report,
            output_dir=tmp_path / "output",
        )


def test_solver_profiles_use_only_precommitted_emphasis(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    fake_module = SimpleNamespace(
        SCIP_PARAMEMPHASIS=SimpleNamespace(
            FEASIBILITY="feasibility-enum",
            OPTIMALITY="optimality-enum",
        )
    )
    monkeypatch.setitem(sys.modules, "pyscipopt", fake_module)
    model = SimpleNamespace(setEmphasis=calls.append)

    label_audit.apply_solver_profile(model, "default")
    label_audit.apply_solver_profile(model, "feasibility")
    label_audit.apply_solver_profile(model, "optimality")

    assert calls == ["feasibility-enum", "optimality-enum"]
    with pytest.raises(ValueError, match="unsupported"):
        label_audit.apply_solver_profile(model, "adaptive")


def test_paired_comparison_uses_default_as_control_and_preserves_censoring() -> None:
    records = [
        _record("node.lp", "default", 0.10),
        _record("node.lp", "feasibility", 0.08),
        _record("node.lp", "optimality", 0.05),
    ]

    comparisons = experiment.paired_comparisons(records)

    assert [row["treatment_profile_id"] for row in comparisons] == [
        "feasibility",
        "optimality",
    ]
    assert comparisons[0]["terminal_gap_difference"] == pytest.approx(-0.02)
    assert comparisons[0]["terminal_gap_ratio"] == pytest.approx(0.8)
    assert comparisons[0]["time_to_optimality_difference_seconds"] is None
    assert comparisons[0]["control_right_censored"] is True


def test_profile_summary_does_not_promote_feasible_runs_to_labels() -> None:
    records = [
        _record(candidate, profile, 0.1)
        for profile in experiment.PROFILE_IDS
        for candidate in ("node-a.lp", "node-b.lp")
    ]

    summary = experiment.summarize_profiles(records)

    assert summary["default"]["feasible_runs"] == 2
    assert summary["default"]["optimal_runs"] == 0
    assert summary["default"]["right_censored_runs"] == 2


def test_run_experiment_uses_all_profile_candidate_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path)
    monkeypatch.setattr(label_audit, "_model_domain_records", lambda _path: [])

    def fake_solve(
        index: int,
        profile: str,
        candidate: Path,
        *_args: object,
        **_kwargs: object,
    ) -> tuple[int, dict[str, object]]:
        return index, _record(candidate.name, profile, 0.1)

    monkeypatch.setattr(experiment, "_solve_one", fake_solve)

    report = experiment.run_experiment(plan)

    assert report["gate_status"] == "passed"
    assert report["execution"]["planned_runs"] == 6
    assert report["execution"]["completed_runs"] == 6
    assert report["paired_comparisons"] == 4
    assert report["eligibility"]["profile_selection_eligible"] is False
    assert report["eligibility"]["dataset_eligible"] is False


def test_run_experiment_rejects_identical_parameter_maps_across_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path)
    monkeypatch.setattr(label_audit, "_model_domain_records", lambda _path: [])

    def fake_solve(
        index: int,
        profile: str,
        candidate: Path,
        *_args: object,
        **_kwargs: object,
    ) -> tuple[int, dict[str, object]]:
        record = _record(candidate.name, profile, 0.1)
        record["solver_parameter_sha256"] = "a" * 64
        return index, record

    monkeypatch.setattr(experiment, "_solve_one", fake_solve)

    report = experiment.run_experiment(plan)

    assert report["gate_status"] == "failed"
    assert report["checks"]["parameter_maps_distinct_across_profiles"] is False


def test_dry_run_does_not_import_pyscipopt(tmp_path: Path) -> None:
    root, nodes, graph_report, baseline_plan, baseline_report = _artifacts(tmp_path)
    output = tmp_path / "output"
    result = experiment.main(
        [
            "--parent_instance_id",
            "CFL_easy_instance_0",
            "--root_mip",
            str(root),
            "--node_mips",
            *(str(node) for node in nodes),
            "--graph_audit_report",
            str(graph_report),
            "--baseline_plan",
            str(baseline_plan),
            "--baseline_report",
            str(baseline_report),
            "--output_dir",
            str(output),
            "--dry_run",
        ]
    )

    assert result == 0
    assert (output / experiment.PLAN_NAME).is_file()
    assert "pyscipopt" not in experiment.__dict__
    assert not (output / experiment.REPORT_NAME).exists()


def test_source_excludes_pyomo_dataset_writes_and_adaptive_profiles() -> None:
    source = Path(experiment.__file__).read_text(encoding="utf-8")
    assert "import pyomo" not in source
    assert "from pyomo" not in source
    assert "torch.save" not in source
    assert "adaptive" not in source
    assert '"dataset_eligible": False' in source
    assert '"profile_selection_eligible": False' in source
