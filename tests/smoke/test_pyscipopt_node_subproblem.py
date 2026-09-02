"""Dependency-free tests for the PySCIPOpt node-subproblem prototype."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cfl_gnn.analysis import pyscipopt_node_subproblem as prototype


class _Variable:
    def __init__(
        self,
        name: str,
        variable_type: str,
        global_lb: float,
        global_ub: float,
        local_lb: float,
        local_ub: float,
        objective: float = 0.0,
    ) -> None:
        self.name = name
        self._type = variable_type
        self._global_lb = global_lb
        self._global_ub = global_ub
        self._local_lb = local_lb
        self._local_ub = local_ub
        self._objective = objective

    def vtype(self) -> str:
        return self._type

    def getLbGlobal(self) -> float:
        return self._global_lb

    def getUbGlobal(self) -> float:
        return self._global_ub

    def getLbLocal(self) -> float:
        return self._local_lb

    def getUbLocal(self) -> float:
        return self._local_ub

    def getLbOriginal(self) -> float:
        return self._local_lb

    def getUbOriginal(self) -> float:
        return self._local_ub

    def getObj(self) -> float:
        return self._objective


class _Constraint:
    def __init__(self, name: str) -> None:
        self.name = name

    def getConshdlrName(self) -> str:
        return "linear"


class _StringOnlyDirection:
    """Match PySCIPOpt 6.2 enums that stringify but reject int()."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


class _Node:
    def __init__(self, number: int, depth: int, parent: "_Node | None") -> None:
        self._number = number
        self._depth = depth
        self._parent = parent

    def getNumber(self) -> int:
        return self._number

    def getDepth(self) -> int:
        return self._depth

    def getParent(self) -> "_Node | None":
        return self._parent

    def getType(self) -> str:
        return "CHILD"

    def getLowerbound(self) -> float:
        return 1.5

    def getParentBranchings(self):
        if self._parent is None:
            return None
        variable = _Variable("x0", "BINARY", 0, 1, 0, 0)
        return [variable], [0.0], [_StringOnlyDirection("1")]

    def getAddedConss(self):
        return [_Constraint("local_cut")] if self._parent is not None else []

    def getNDomchg(self):
        return (1, 0, 0) if self._parent is not None else (0, 0, 0)


class _Event:
    def __init__(self, node: _Node) -> None:
        self._node = node

    def getNode(self) -> _Node:
        return self._node


class _Model:
    def __init__(
        self, variables: list[_Variable], current_node: _Node | None = None
    ) -> None:
        self.variables = variables
        self.current_node = current_node

    def getVars(self, transformed: bool = True):
        return list(self.variables)

    def getCurrentNode(self):
        return self.current_node

    def getConss(self, transformed: bool = True):
        return [_Constraint("local_cut")]

    def getObjectiveSense(self) -> str:
        return "minimize"

    def getStage(self) -> str:
        return "SOLVING"

    def writeMIP(self, filename: str, **_: object) -> None:
        Path(filename).write_text("MIP candidate\n", encoding="utf-8")

    def writeProblem(self, filename: str, **_: object) -> None:
        Path(filename).write_text("transformed candidate\n", encoding="utf-8")

    def getConsVars(self, constraint: _Constraint):
        assert constraint.name == "local_cut"
        return [self.variables[1]]

    def getConsVals(self, constraint: _Constraint):
        assert constraint.name == "local_cut"
        return [1.0]

    def getLhs(self, constraint: _Constraint) -> float:
        assert constraint.name == "local_cut"
        return 1.0

    def getRhs(self, constraint: _Constraint) -> float:
        assert constraint.name == "local_cut"
        return float("inf")


def _variables() -> list[_Variable]:
    return [
        _Variable("x1", "BINARY", 0, 1, 0, 1),
        _Variable("x0", "BINARY", 0, 1, 0, 0),
        _Variable("y", "CONTINUOUS", 0, 10, 0, 10),
    ]


def test_toy_plan_is_deterministic_and_path_sanitized(tmp_path: Path) -> None:
    first = prototype.build_probe_plan(output_dir=tmp_path / "one", toy=True)
    second = prototype.build_probe_plan(output_dir=tmp_path / "two", toy=True)

    assert first.contract_sha256 == second.contract_sha256
    assert first.source_sha256 == prototype._canonical_sha256(
        prototype.TOY_SPECIFICATION
    )
    serialized = json.dumps(first.to_summary())
    assert str(tmp_path) not in serialized
    assert first.to_summary()["eligibility"].startswith("experimental_ineligible")
    assert first.to_summary()["candidate_formats"] == {
        "writeMIP": "lp",
        "writeProblem_transformed": "cip",
    }
    assert first.to_summary()["schema_version"] == 3
    assert first.to_summary()["root_baseline"] == "writeMIP_at_root_LPSOLVED"


def test_plan_can_omit_transformed_controls(tmp_path: Path) -> None:
    plan = prototype.build_probe_plan(
        output_dir=tmp_path / "probe",
        toy=True,
        write_transformed_controls=False,
    )

    assert plan.to_summary()["candidate_writers"] == ["writeMIP"]
    assert plan.to_summary()["parameters"]["write_transformed_controls"] is False


def test_instance_plan_binds_original_bytes_without_path(tmp_path: Path) -> None:
    instance = tmp_path / "CFL_easy_instance_0.lp.gz"
    instance.write_bytes(b"compressed-placeholder")

    plan = prototype.build_probe_plan(
        output_dir=tmp_path / "output", instance_path=instance
    )

    assert plan.source_id == "CFL_easy_instance_0"
    assert plan.source_file_name == instance.name
    assert plan.source_sha256 == prototype.sha256_file(instance)
    assert str(tmp_path) not in json.dumps(plan.to_summary())


def test_capture_node_state_separates_semantic_and_structural_identity() -> None:
    root = _Node(1, 0, None)
    child = _Node(2, 1, root)
    state = prototype.capture_node_state(_Model(_variables()), child, "a" * 64)

    assert state["node_number"] == 2
    assert state["parent_number"] == 1
    assert state["ancestry"] == [1, 2]
    assert state["local_bound_change_count"] == 1
    assert state["local_bound_changes"][0]["name"] == "x0"
    assert state["parent_branchings"][0]["variable"] == "x0"
    assert state["branch_path"] == [
        {
            "at_node_number": 2,
            "parent_number": 1,
            "variable": "x0",
            "bound": 0.0,
            "bound_type": "upper",
        }
    ]
    assert state["added_constraints"] == [
        {
            "at_node_number": 2,
            "name": "local_cut",
            "handler": "linear",
            "linear_terms": [["x0", 1.0]],
            "representation": "linear_terms",
            "lhs": 1.0,
            "rhs": "+inf",
        }
    ]
    assert len(state["semantic_node_sha256"]) == 64


def test_root_none_parent_branchings_match_pyscipopt_contract() -> None:
    root = _Node(1, 0, None)

    assert root.getParentBranchings() is None
    assert prototype._node_branchings(root) == []


def test_semantic_hash_does_not_depend_on_variable_iteration_order() -> None:
    root = _Node(1, 0, None)
    child = _Node(2, 1, root)
    first = prototype.capture_node_state(_Model(_variables()), child, "b" * 64)
    second = prototype.capture_node_state(
        _Model(list(reversed(_variables()))), child, "b" * 64
    )

    assert first["local_bound_vector_sha256"] == second["local_bound_vector_sha256"]
    assert first["semantic_node_sha256"] == second["semantic_node_sha256"]


def test_observer_writes_bounded_candidates_without_promoting_them(
    tmp_path: Path,
) -> None:
    plan = prototype.build_probe_plan(
        output_dir=tmp_path / "probe", toy=True, max_samples=1
    )
    root = _Node(1, 0, None)
    child = _Node(2, 1, root)
    observer = prototype.NodeProbeObserver(plan)
    model = _Model(_variables(), current_node=child)

    observer.on_node_focused(model, _Event(child))
    observer.on_node_focused(model, _Event(child))
    observer.on_lp_solved(model, _Event(child))
    observer.on_lp_solved(model, _Event(child))

    summary = observer.summary()
    assert summary["nodefocused_events"] == 2
    assert summary["lp_solved_events"] == 2
    assert summary["samples_recorded"] == 1
    assert summary["candidate_files_written"] == 2
    assert len(observer.candidates) == 2
    assert observer.samples[0]["state_capture_event"] == "LPSOLVED"
    assert observer.samples[0]["focused_semantic_node_sha256"]
    assert all(
        export["status"] == "written"
        for export in observer.samples[0]["candidate_exports"]
    )
    exports = {
        export["writer"]: export
        for export in observer.samples[0]["candidate_exports"]
    }
    assert exports["writeMIP"]["file_name"].endswith("_mip.lp")
    assert exports["writeMIP"]["artifact_format"] == "lp"
    assert exports["writeProblem_transformed"]["file_name"].endswith(
        "_transformed.cip"
    )
    assert exports["writeProblem_transformed"]["artifact_format"] == "cip"
    assert len(observer.candidates[0]["expected_variable_domains"]) == 3


def test_observer_serializes_root_baseline_before_node_candidates(
    tmp_path: Path,
) -> None:
    plan = prototype.build_probe_plan(
        output_dir=tmp_path / "probe", toy=True, max_samples=1
    )
    root = _Node(1, 0, None)
    child = _Node(2, 1, root)
    observer = prototype.NodeProbeObserver(plan)
    model = _Model(_variables(), current_node=root)

    observer.on_lp_solved(model, _Event(root))
    model.current_node = child
    observer.on_node_focused(model, _Event(child))
    observer.on_lp_solved(model, _Event(child))

    assert observer.summary()["root_baseline_written"] is True
    assert observer.root_baseline is not None
    assert observer.root_baseline["export"]["file_name"] == "root_mip_baseline.lp"
    assert observer.root_baseline["export"]["writer_role"] == (
        "root_node_mip_baseline"
    )


def test_roundtrip_evaluation_remains_ineligible_after_mechanical_success() -> None:
    sample = {
        "sample_index": 0,
        "node_number": 2,
        "depth": 1,
        "parent_branchings": [{"variable": "x0"}],
        "branch_path": [
            {"variable": "x0", "bound": 0.0, "bound_type": "upper"}
        ],
        "local_bound_change_count": 1,
        "added_constraint_count": 0,
        "semantic_node_sha256": "c" * 64,
        "transformed_variable_types": {"BINARY": 3},
    }
    export = {
        "writer": "writeMIP",
        "writer_role": "node_mip_candidate",
        "file_name": "node.lp",
        "artifact_format": "lp",
        "sha256": "d" * 64,
    }
    inspection = {
        "status": "readable",
        "objective_sense": "minimize",
        "expected_local_bounds_match": True,
        "expected_local_constraints_match": True,
        "expected_branch_bounds_match": True,
        "expected_variable_domain_count": 3,
        "expected_variable_domains_match": True,
        "variable_domain_mismatch_count": 0,
        "variable_domain_mismatches": [],
        "signature": {"variable_types": {"BINARY": 3}},
    }

    audit = prototype.evaluate_roundtrip(sample, export, inspection)

    assert audit["roundtrip_status"] == "candidate_passed_mechanical_checks"
    assert audit["expected_variable_domain_count"] == 3
    assert audit["expected_variable_domains_match"] is True
    assert audit["variable_domain_mismatch_count"] == 0
    assert audit["variable_domain_mismatches"] == []
    assert audit["dataset_eligible"] is False
    assert audit["eligibility_reason"] == "prototype_requires_independent_scientific_review"


def test_parent_branching_cannot_pass_without_bound_materialization() -> None:
    sample = {
        "sample_index": 1,
        "node_number": 3,
        "depth": 1,
        "branch_path": [
            {"variable": "x0", "bound": 1.0, "bound_type": "lower"}
        ],
        "local_bound_change_count": 0,
        "added_constraint_count": 0,
        "semantic_node_sha256": "e" * 64,
        "transformed_variable_types": {"BINARY": 3},
    }
    export = {
        "writer": "writeMIP",
        "writer_role": "node_mip_candidate",
        "file_name": "node.lp",
        "artifact_format": "lp",
    }
    inspection = {
        "status": "readable",
        "objective_sense": "minimize",
        "expected_local_bounds_match": True,
        "expected_local_constraints_match": True,
        "expected_branch_bounds_match": False,
        "expected_variable_domains_match": True,
        "signature": {"variable_types": {"BINARY": 3}},
    }

    audit = prototype.evaluate_roundtrip(sample, export, inspection)

    assert audit["semantic_distinction_observed"] is True
    assert audit["expected_branch_bounds_match"] is False
    assert audit["roundtrip_status"] == "candidate_failed_or_incomplete"


def test_variable_domain_failure_is_explicit_in_roundtrip_audit() -> None:
    sample = {
        "sample_index": 2,
        "node_number": 4,
        "depth": 1,
        "branch_path": [
            {"variable": "x0", "bound": 0.0, "bound_type": "upper"}
        ],
        "local_bound_change_count": 1,
        "added_constraint_count": 0,
        "semantic_node_sha256": "a" * 64,
    }
    export = {
        "writer": "writeMIP",
        "writer_role": "node_mip_candidate",
        "file_name": "node.lp",
        "artifact_format": "lp",
    }
    inspection = {
        "status": "readable",
        "objective_sense": "minimize",
        "expected_local_bounds_match": True,
        "expected_local_constraints_match": True,
        "expected_branch_bounds_match": True,
        "expected_variable_domain_count": 1,
        "expected_variable_domains_match": False,
        "variable_domain_mismatch_count": 1,
        "variable_domain_mismatches": [
            {"name": "x0", "reason": "integrality_lost"}
        ],
        "signature": {"variable_types": {"CONTINUOUS": 1}},
    }

    audit = prototype.evaluate_roundtrip(sample, export, inspection)

    assert audit["integrality_preserved"] is False
    assert audit["expected_variable_domains_match"] is False
    assert audit["variable_domain_mismatch_count"] == 1
    assert audit["variable_domain_mismatches"] == [
        {"name": "x0", "reason": "integrality_lost"}
    ]
    assert audit["roundtrip_status"] == "candidate_failed_or_incomplete"


def test_transformed_problem_is_always_a_control() -> None:
    sample = {
        "sample_index": 0,
        "node_number": 2,
        "depth": 1,
        "branch_path": [{"variable": "x0"}],
        "local_bound_change_count": 1,
        "added_constraint_count": 0,
        "semantic_node_sha256": "f" * 64,
        "transformed_variable_types": {"BINARY": 3},
    }
    export = {
        "writer": "writeProblem_transformed",
        "writer_role": "transformed_problem_control",
        "file_name": "control.cip",
        "artifact_format": "cip",
    }
    inspection = {
        "status": "readable",
        "objective_sense": "minimize",
        "expected_local_bounds_match": True,
        "expected_local_constraints_match": True,
        "expected_branch_bounds_match": True,
        "expected_variable_domains_match": True,
        "signature": {"variable_types": {"BINARY": 3}},
    }

    audit = prototype.evaluate_roundtrip(sample, export, inspection)

    assert audit["roundtrip_status"] == "transformed_problem_control_only"
    assert audit["dataset_eligible"] is False


def test_root_relative_classification_detects_domain_only_distinctness() -> None:
    root = {
        "baseline_status": "root_baseline_passed_mechanical_checks",
        "artifact_sha256": "1" * 64,
        "candidate_signature": {"rows": 3, "columns": 3, "nonzeros": 7},
        "fingerprints": {
            "matrix_sha256": "a" * 64,
            "objective_sha256": "b" * 64,
            "domain_sha256": "c" * 64,
            "formulation_sha256": "d" * 64,
        },
    }
    candidate = {
        "writer_role": "node_mip_candidate",
        "artifact_sha256": "2" * 64,
        "roundtrip_status": "candidate_passed_mechanical_checks",
        "candidate_signature": {"rows": 3, "columns": 3, "nonzeros": 7},
        "fingerprints": {
            "matrix_sha256": "a" * 64,
            "objective_sha256": "b" * 64,
            "domain_sha256": "e" * 64,
            "formulation_sha256": "f" * 64,
        },
    }

    audit = prototype.apply_distinctness_audit(
        candidate, root, {"rows": 3, "columns": 3, "nonzeros": 7}
    )

    assert audit["root_signature_delta"] == {
        "rows": 0,
        "columns": 0,
        "nonzeros": 0,
    }
    assert audit["matrix_structurally_distinct"] is False
    assert audit["domain_distinct"] is True
    assert audit["dimensionally_distinct"] is False
    assert audit["node_mip_distinct_from_root"] is True
    assert audit["materialization_class"] == "domain_distinct_same_matrix"


def test_same_size_artifacts_are_distinguished_by_hash_not_dimensions() -> None:
    records = [
        {
            "writer_role": "node_mip_candidate",
            "artifact_sha256": "a" * 64,
            "semantic_node_sha256": "1" * 64,
            "fingerprints": {"formulation_sha256": "x" * 64},
            "roundtrip_status": "candidate_passed_mechanical_checks",
            "node_mip_distinct_from_root": True,
            "dimensionally_distinct": False,
            "matrix_structurally_distinct": False,
            "domain_distinct": True,
            "materialization_class": "domain_distinct_same_matrix",
        },
        {
            "writer_role": "node_mip_candidate",
            "artifact_sha256": "b" * 64,
            "semantic_node_sha256": "2" * 64,
            "fingerprints": {"formulation_sha256": "y" * 64},
            "roundtrip_status": "candidate_passed_mechanical_checks",
            "node_mip_distinct_from_root": True,
            "dimensionally_distinct": False,
            "matrix_structurally_distinct": False,
            "domain_distinct": True,
            "materialization_class": "domain_distinct_same_matrix",
        },
    ]

    summary = prototype.build_distinctness_summary(records)

    assert summary["node_mip_candidates"] == 2
    assert summary["unique_artifacts"] == 2
    assert summary["unique_formulations"] == 2
    assert summary["dimensionally_distinct_from_root"] == 0


def test_formulation_fingerprints_are_order_invariant_and_componentized() -> None:
    first = prototype.formulation_fingerprints(
        _Model(_variables()), transformed=False
    )
    reordered = prototype.formulation_fingerprints(
        _Model(list(reversed(_variables()))), transformed=False
    )
    objective_changed = prototype.formulation_fingerprints(
        _Model(
            [
                _Variable("x1", "BINARY", 0, 1, 0, 1),
                _Variable("x0", "BINARY", 0, 1, 0, 0, objective=1),
                _Variable("y", "CONTINUOUS", 0, 10, 0, 10),
            ]
        ),
        transformed=False,
    )

    assert first == reordered
    assert first["matrix_sha256"] == objective_changed["matrix_sha256"]
    assert first["domain_sha256"] == objective_changed["domain_sha256"]
    assert first["objective_sha256"] != objective_changed["objective_sha256"]
    assert first["formulation_sha256"] != objective_changed["formulation_sha256"]


def test_branch_bound_comparison_checks_direction() -> None:
    fixed_zero = _Variable("x0", "BINARY", 0, 1, 0, 0)
    fixed_one = _Variable("x1", "BINARY", 0, 1, 1, 1)

    assert prototype._branch_bound_matches(
        fixed_zero, {"bound": 0.0, "bound_type": "upper"}
    )
    assert prototype._branch_bound_matches(
        fixed_one, {"bound": 1.0, "bound_type": "lower"}
    )
    assert not prototype._branch_bound_matches(
        fixed_zero, {"bound": 1.0, "bound_type": "lower"}
    )


def test_binary_to_bounded_integer_preserves_exact_domain() -> None:
    serialized = _Variable("x", "INTEGER", 1, 1, 1, 1)

    matches, reason = prototype._variable_domain_matches(
        serialized,
        {"name": "x", "variable_type": "BINARY", "lb": 1.0, "ub": 1.0},
    )

    assert matches is True
    assert reason is None


def test_binary_to_continuous_or_wider_bounds_fails_domain_check() -> None:
    continuous = _Variable("x", "CONTINUOUS", 0, 1, 0, 1)
    wider_integer = _Variable("x", "INTEGER", 0, 2, 0, 2)
    expected = {
        "name": "x",
        "variable_type": "BINARY",
        "lb": 0.0,
        "ub": 1.0,
    }

    assert prototype._variable_domain_matches(continuous, expected) == (
        False,
        "integrality_lost",
    )
    assert prototype._variable_domain_matches(wider_integer, expected) == (
        False,
        "bounds_changed",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (_StringOnlyDirection("0"), "lower"),
        (_StringOnlyDirection("1"), "upper"),
        (_StringOnlyDirection("SCIP_BOUNDTYPE_LOWER"), "lower"),
        (_StringOnlyDirection("SCIP_BOUNDTYPE_UPPER"), "upper"),
    ],
)
def test_bound_type_normalization_accepts_string_only_enums(
    raw: object, expected: str
) -> None:
    assert prototype._normalized_bound_type(raw) == expected


def test_gate_reports_capture_failure_before_downstream_absence() -> None:
    status, reason = prototype.determine_gate_status(
        {"capture_error_count": 2, "samples_recorded": 0},
        {
            "writeMIP": {
                "candidates_audited": 0,
                "fresh_process_readable": 0,
                "mechanical_checks_passed": 0,
                "distinct_from_root": 0,
            }
        },
        None,
    )

    assert status == "failed"
    assert reason == "node_capture_failed"


def test_gate_passes_only_after_distinct_write_mip_and_root_baseline() -> None:
    status, reason = prototype.determine_gate_status(
        {
            "capture_error_count": 0,
            "samples_recorded": 2,
            "root_baseline_written": True,
        },
        {
            "writeMIP": {
                "candidates_audited": 2,
                "fresh_process_readable": 2,
                "mechanical_checks_passed": 1,
                "distinct_from_root": 1,
            }
        },
        {"baseline_status": "root_baseline_passed_mechanical_checks"},
    )

    assert status == "passed"
    assert reason == "write_mip_distinct_candidate_observed_pending_review"


def test_gate_rejects_mechanical_candidate_identical_to_root() -> None:
    status, reason = prototype.determine_gate_status(
        {
            "capture_error_count": 0,
            "samples_recorded": 1,
            "root_baseline_written": True,
        },
        {
            "writeMIP": {
                "candidates_audited": 1,
                "fresh_process_readable": 1,
                "mechanical_checks_passed": 1,
                "distinct_from_root": 0,
            }
        },
        {"baseline_status": "root_baseline_passed_mechanical_checks"},
    )

    assert status == "failed"
    assert reason == "write_mip_candidate_not_distinct_from_root"


def test_dry_run_does_not_import_pyscipopt(tmp_path: Path) -> None:
    output = tmp_path / "dry"
    result = prototype.main(["--toy", "--output_dir", str(output), "--dry_run"])

    assert result == 0
    assert (output / prototype.PLAN_NAME).is_file()
    assert not (output / prototype.REPORT_NAME).exists()
    assert "pyscipopt" not in prototype.__dict__


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"toy": True, "instance_path": "model.lp"},
        {"toy": True, "node_limit": 0},
        {"toy": True, "min_depth": 2, "max_depth": 1},
        {"toy": True, "presolve": "invalid"},
    ],
)
def test_invalid_probe_contracts_fail_closed(
    tmp_path: Path, arguments: dict[str, object]
) -> None:
    with pytest.raises((ValueError, FileNotFoundError)):
        prototype.build_probe_plan(output_dir=tmp_path, **arguments)


def test_source_has_no_pyomo_or_dataset_integration() -> None:
    source = Path(prototype.__file__).read_text(encoding="utf-8")
    assert "import pyomo" not in source
    assert "from pyomo" not in source
    assert "torch" not in source
    assert "HeteroData" not in source
    assert "import pyscipopt" in source[source.index("def run_probe") :]
    assert '"dataset_eligible": False' in source
