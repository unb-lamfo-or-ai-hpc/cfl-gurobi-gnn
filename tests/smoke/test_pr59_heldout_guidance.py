from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from cfl_gnn.pipelines import pr59_heldout_guidance as pipeline
from cfl_gnn.pipelines.pr58_validation_guidance import _split_sets, prepare_parent


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pr59_policy_is_the_frozen_complete_medium_test_fold():
    policy = json.loads(
        (PROJECT_ROOT / "configs/experiments/pr59_heldout_guidance_v1.json").read_text()
    )
    validation, test = _split_sets()
    assert policy["benchmark_partition"] == "test"
    assert policy["benchmark_parent_ids"] == [
        "CFL_medium_instance_0",
        "CFL_medium_instance_4",
        "CFL_medium_instance_7",
        "CFL_medium_instance_9",
        "CFL_medium_instance_12",
        "CFL_medium_instance_20",
    ]
    assert test == sorted(policy["benchmark_parent_ids"])
    assert validation == sorted(policy["qualification_parent_ids"])
    assert set(test).isdisjoint(validation)
    assert policy["test_outcomes_may_select_or_modify_policy"] is False
    assert policy["analysis_policy"]["favorable_outcome_required_for_completion"] is False
    assert policy["analysis_policy"]["policy_reselection_after_test"] is False


def test_pr59_launchers_are_lf_only_and_use_only_the_canonical_license():
    paths = [
        PROJECT_ROOT / "scripts/slurm/dasci/launch_pr59_heldout_guidance.sh",
        PROJECT_ROOT / "scripts/slurm/dasci/submit_pr59_heldout_guidance.sbs",
        PROJECT_ROOT / "scripts/slurm/dasci/submit_pr59_heldout_guidance_audit.sbs",
    ]
    for path in paths:
        payload = path.read_bytes()
        assert payload.startswith(b"#!/bin/bash\n")
        assert b"\r" not in payload
    combined = "\n".join(path.read_text() for path in paths)
    canonical = "/home/vrcelestino/discodatos/cfl-gurobi-gnn/secrets/gurobi.lic"
    assert canonical in paths[0].read_text()
    assert canonical in paths[1].read_text()
    assert "${EXEC_DIR}/secrets/gurobi.lic" not in combined
    assert "GRB_LICENSE_FILE:-" not in combined
    assert "run_pr59_heldout_guidance" in combined
    assert "run_pr57_training train" not in combined
    assert "--array=0-5%2" in paths[1].read_text()


def test_shared_preparation_propagates_the_frozen_target_role():
    source = inspect.getsource(prepare_parent)
    assert '"role": target["role"]' in source
    assert '"target_labels_loaded": False' in source
    assert '"test_outcomes_loaded": False' in source


def test_validation_authorization_requires_the_exact_qualified_cohort(
    tmp_path: Path, monkeypatch
):
    rows = [
        {
            "source_instance_id": identity,
            "role": "validation",
            "method": method,
        }
        for identity in sorted(pipeline.EXPECTED_VALIDATION_PARENTS)
        for method in pipeline.METHODS
    ]
    payloads = {
        "paired_effects.csv": "source_instance_id\n",
        "paired_effects.json": json.dumps({"records": []}),
        "per_method_outcomes.csv": "source_instance_id\n",
        "per_method_outcomes.json": json.dumps({"records": rows}),
        "per_method_status.json": json.dumps({"records": []}),
    }
    for name, payload in payloads.items():
        (tmp_path / name).write_text(payload)
    hashes = {name: _sha(tmp_path / name) for name in payloads}
    monkeypatch.setattr(pipeline, "EXPECTED_VALIDATION_OUTPUTS", hashes)
    report = {
        "contract_sha256": pipeline.EXPECTED_VALIDATION_CONTRACT,
        "gate_status": "passed",
        "probe_completed": True,
        "failures": [],
        "qualification_checks": {"frozen_gate": True},
        "eligibility": {
            "test_benchmark_authorized": True,
            "development_only": True,
            "scientific_reporting_eligible": False,
        },
        "decision": {
            "next_gate": "held_out_six_medium_paired_benchmark",
            "test_parent_ids": sorted(pipeline.EXPECTED_TEST_PARENTS),
        },
        "summary": {
            "planned_validation_parents": 6,
            "valid_validation_parents": 6,
            "planned_method_runs": 18,
            "valid_method_runs": 18,
            "gnn_gap_wins_vs_control": 4,
            "gnn_large_gap_regressions": 1,
            "gnn_median_gap_difference_guided_minus_control": -0.012235269305291743,
        },
        "outputs": {
            name: {"relative_path": name, "sha256": digest}
            for name, digest in hashes.items()
        },
    }
    (tmp_path / "pr58_validation_guidance_report.json").write_text(json.dumps(report))
    validated, descriptors = pipeline._validation_authorization(tmp_path)
    assert validated == report
    assert set(descriptors) == {
        "pr58_validation_guidance_report.json",
        *payloads,
    }


def test_pr59_source_uses_integrity_not_favorable_outcomes_as_completion_gate():
    source = inspect.getsource(pipeline.audit)
    assert "complete = all(integrity_checks.values())" in source
    assert '"favorable_outcome_required_for_completion": False' in source
    assert '"policy_change_authorized_by_test_outcomes": False' in source


def test_pr59_allows_unlabelled_test_parents_but_rejects_training_roles():
    source = inspect.getsource(pipeline.build_plan)
    assert 'trained_record is not None and trained_record.get("role") != "test"' in source
    assert '"was_present_in_training_plan": trained_record is not None' in source
    assert 'None if trained_record is None else trained_record["role"]' in source


def test_pr59_verifier_checks_hashes_and_sanitization():
    source = inspect.getsource(pipeline.verify_audit)
    assert "checked(output_dir, declared[name])" in source
    assert '"/raid/"' in source
    assert '"/home/"' in source
    assert '"gurobi.lic"' in source
