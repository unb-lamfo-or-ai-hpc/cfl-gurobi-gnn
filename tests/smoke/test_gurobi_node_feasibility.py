"""Dependency-free tests for the isolated Gurobi MIPNODE feasibility probe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.analysis import gurobi_node_feasibility as feasibility


class _CallbackCodes:
    MIPNODE = 5
    MIPNODE_STATUS = 5001
    MIPNODE_OBJBST = 5003
    MIPNODE_OBJBND = 5004
    MIPNODE_NODCNT = 5005
    MIPNODE_PHASE = 5008
    RUNTIME = 6002


class _FakeCallbackModel:
    def __init__(self, relaxation: list[float]) -> None:
        self.relaxation = relaxation
        self.node_count = 0

    def cbGet(self, code: int):
        values = {
            _CallbackCodes.MIPNODE_STATUS: 2,
            _CallbackCodes.MIPNODE_OBJBST: 10.0,
            _CallbackCodes.MIPNODE_OBJBND: 8.0,
            _CallbackCodes.MIPNODE_NODCNT: self.node_count,
            _CallbackCodes.MIPNODE_PHASE: 1,
            _CallbackCodes.RUNTIME: 1.25,
        }
        return values[code]

    def cbGetNodeRel(self, variables):
        assert len(variables) == len(self.relaxation)
        return list(self.relaxation)


def _observer(*, max_samples: int = 3) -> feasibility.NodeObserver:
    return feasibility.NodeObserver(
        [object(), object(), object()],
        [True, True, False],
        callback_codes=_CallbackCodes,
        optimal_status=2,
        max_samples=max_samples,
        integrality_tolerance=1e-6,
    )


def test_probe_plan_is_hash_bound_and_path_sanitized(tmp_path: Path) -> None:
    instance = tmp_path / "CFL_easy_instance_0.lp.gz"
    instance.write_bytes(b"compressed-model-placeholder")

    first = feasibility.build_probe_plan(instance)
    second = feasibility.build_probe_plan(instance)
    summary = first.to_summary()

    assert first.contract_sha256 == second.contract_sha256
    assert summary["source_instance"] == {
        "instance_id": "CFL_easy_instance_0",
        "file_name": "CFL_easy_instance_0.lp.gz",
        "sha256": feasibility.sha256_file(instance),
    }
    assert str(tmp_path) not in json.dumps(summary)
    assert summary["objective_sense_override"] == "MINIMIZE"
    assert summary["parameters"]["threads"] == 1
    assert summary["parameters"]["presolve"] == 0


def test_node_observer_records_repeated_root_cut_passes_without_node_ids() -> None:
    observer = _observer()
    model = _FakeCallbackModel([0.0, 0.25, 2.5])

    observer(model, _CallbackCodes.MIPNODE)
    model.relaxation = [0.0, 0.75, 2.0]
    observer(model, _CallbackCodes.MIPNODE)
    model.node_count = 1
    observer(model, _CallbackCodes.MIPNODE)

    summary = observer.summary()
    assert summary["mipnode_callback_calls"] == 3
    assert summary["samples_recorded"] == 3
    assert summary["sample_limit_reached"] is True
    assert summary["distinct_node_counts_observed"] == 2
    assert summary["root_node_samples"] == 2
    assert summary["repeated_node_count_callbacks"] == 1
    assert summary["samples"][1]["node_count_occurrence"] == 1
    assert summary["samples"][0]["fractional_discrete_count"] == 1
    assert "relaxation_vector" not in summary["samples"][0]
    assert len(summary["samples"][0]["relaxation_sha256"]) == 64


def test_node_observer_fails_closed_on_vector_length_mismatch() -> None:
    observer = _observer()
    model = _FakeCallbackModel([0.0, 1.0])

    observer(model, _CallbackCodes.MIPNODE)

    summary = observer.summary()
    assert summary["samples_recorded"] == 0
    assert summary["callback_error_count"] == 1
    assert summary["callback_errors"] == [
        {
            "callback_index": 0,
            "error_type": "AssertionError",
            "reason": "callback_query_failed",
        }
    ]


def test_node_observer_caps_repeated_samples_for_one_node_count() -> None:
    observer = _observer(max_samples=5)
    model = _FakeCallbackModel([0.0, 0.5, 1.0])

    for _ in range(5):
        observer(model, _CallbackCodes.MIPNODE)

    summary = observer.summary()
    assert summary["mipnode_callback_calls"] == 5
    assert summary["samples_recorded"] == feasibility.MAX_SAMPLES_PER_NODE_COUNT
    assert summary["root_node_samples"] == feasibility.MAX_SAMPLES_PER_NODE_COUNT
    assert summary["repeated_node_count_callbacks"] == 4


def test_capability_decision_never_promotes_relaxation_to_milp() -> None:
    capabilities = feasibility.capability_assessment(samples_recorded=2)
    decision = feasibility.feasibility_decision(
        samples_recorded=2, callback_errors=0
    )

    assert capabilities["node_relaxation"]["status"] == "observed"
    assert capabilities["local_variable_bounds"]["status"].startswith(
        "not_exposed"
    )
    assert capabilities["unique_node_identifier"]["status"].startswith(
        "not_exposed"
    )
    assert decision["runtime_probe_status"] == "mipnode_observed"
    assert decision["exact_subproblem_materialization"] is False
    assert decision["structurally_distinct_instance_created"] is False
    assert decision["eligible_as_new_milp_instance"] is False
    assert decision["next_solver_candidate"] == "SCIP"


def test_dry_run_writes_only_a_sanitized_plan(tmp_path: Path) -> None:
    instance = tmp_path / "CFL_easy_instance_1.lp.gz"
    instance.write_bytes(b"model")
    output = tmp_path / "report"

    result = feasibility.main(
        [
            "--instance",
            str(instance),
            "--output_dir",
            str(output),
            "--dry_run",
        ]
    )

    assert result == 0
    plan_path = output / feasibility.PLAN_NAME
    assert plan_path.is_file()
    assert not (output / feasibility.REPORT_NAME).exists()
    plan_text = plan_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in plan_text
    assert "gurobipy" not in feasibility.__dict__


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"time_limit": 0}, "time_limit"),
        ({"node_limit": 0}, "node_limit"),
        ({"max_samples": 0}, "max_samples"),
        ({"integrality_tolerance": 0.5}, "integrality_tolerance"),
        ({"seed": 0}, "seed"),
    ],
)
def test_probe_plan_rejects_invalid_contract_values(
    tmp_path: Path, kwargs: dict[str, object], message: str
) -> None:
    instance = tmp_path / "instance.lp"
    instance.write_text("Minimize\n obj: 0\nEnd\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        feasibility.build_probe_plan(instance, **kwargs)


def test_probe_source_contains_no_node_mutation_or_fake_materialization() -> None:
    source = Path(feasibility.__file__).read_text(encoding="utf-8")
    for forbidden in (
        ".cbCut(",
        ".cbLazy(",
        ".cbSetSolution(",
        ".fixed(",
        ".presolve(",
        ".write(",
    ):
        assert forbidden not in source
    assert "import gurobipy as gp" in source[source.index("def run_probe") :]
    assert '"eligible_as_new_milp_instance": False' in source
