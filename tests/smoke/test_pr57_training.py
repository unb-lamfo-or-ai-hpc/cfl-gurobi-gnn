import gzip
import json
from pathlib import Path

from cfl_gnn.pipelines import pr57_training as p
from cfl_gnn.training.gasse_reconnected import load_protocol


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_pr57_frozen_population_contract():
    assert p.EXPECTED_COUNTS == {"train": 34, "validation": 10, "test": 10}
    assert p.EXPECTED_DIFFICULTY == {"easy": 30, "medium": 24}
    assert p.EXPECTED_LABEL_FORMATS == {
        "confirmation_solution_json": 39,
        "gurobi_parent_solution_json": 15,
    }
    assert len(p.EXPECTED_NEW_PARENTS) == 15
    assert len(set(p.EXPECTED_NEW_PARENTS)) == 15
    assert all(item.startswith("CFL_medium_instance_") for item in p.EXPECTED_NEW_PARENTS)


def test_pr57_protocol_is_fresh_100_epoch_seed42_contract():
    protocol = load_protocol(p.PROTOCOL_PATH)
    assert protocol["protocol_id"] == "gasse_pr57_54_parent_development_v1"
    assert protocol["optimization"] == {
        "epochs": 100,
        "patience": 100,
        "learning_rate": 0.001,
        "gradient_clip_norm": 1.0,
        "seed": 42,
    }
    assert protocol["sampling"] == {
        "method": "deterministic_parent_balanced_cycle_v1",
        "draws_per_parent_per_epoch": 4,
        "maximum_label_mip_gap_relative": 0.1,
    }
    assert protocol["checkpoint_selection"]["test_partition_access"] == "held_out_evaluation_only"
    assert protocol["threshold_selection"]["method"] == "maximum_validation_f1"


def test_pr57_evidence_package_hash_is_pinned():
    assert p.EVIDENCE_PACKAGE_SHA256 == (
        "9ced8340fb1bbd19bc02dcfab704a1663f90d097d6d3464d903a1c9f18d8e31f"
    )



def test_pr57_confirmation_preflight_is_variable_container_agnostic(tmp_path):
    identity = "CFL_easy_instance_0"
    mip_path = tmp_path / "parent.lp.gz"
    solution_path = tmp_path / "confirmation_solution.json.gz"
    report_path = tmp_path / "confirmation_source_report.json"

    mip_path.write_bytes(b"dummy-mip")
    solution = {
        "solution_source": "independently_audited_gurobi_confirmation_label",
        "source_instance_id": identity,
        "source_mip_sha256": p._sha256(mip_path),
        "mathematical_audit": {"valid": True},
        "mip_gap_relative": 0.0,
        "solution_objective": 1.0,
        "execution_time_seconds": 1.0,
        # Historical confirmation payloads need not encode variables as a mapping.
        "variables": [{"name": "x", "value": 1.0}],
    }
    with gzip.open(solution_path, "wt", encoding="utf-8") as stream:
        json.dump(solution, stream)

    report = {
        "gate_status": "passed",
        "label_eligible": True,
        "source_instance_id": identity,
        "mip_sha256": p._sha256(mip_path),
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    row = {
        "category": "CFL_easy_instance",
        "difficulty": "easy",
        "execution_time_seconds": 1.0,
        "fold": 0,
        "label_format": "confirmation_solution_json",
        "mip": {
            "relative_path": mip_path.relative_to(tmp_path).as_posix(),
            "sha256": p._sha256(mip_path),
        },
        "mip_gap_relative": 0.0,
        "report": {
            "relative_path": report_path.relative_to(tmp_path).as_posix(),
            "sha256": p._sha256(report_path),
        },
        "role": "test",
        "solution": {
            "relative_path": solution_path.relative_to(tmp_path).as_posix(),
            "sha256": p._sha256(solution_path),
        },
        "source_instance_id": identity,
    }

    checked = p._validate_index_row(tmp_path, row)
    assert checked["identity"] == identity
    assert checked["solution"]["variables"] == [{"name": "x", "value": 1.0}]

def test_pr57_gurobi_parent_accepts_case_normalized_minimize(tmp_path):
    identity = "CFL_medium_instance_3"
    mip_path = tmp_path / "parent.lp.gz"
    solution_path = tmp_path / "parent_solution.json.gz"
    report_path = tmp_path / "gurobi_expansion_task_report.json"

    mip_path.write_bytes(b"dummy-medium-mip")
    mip_sha = p._sha256(mip_path)

    solution = {
        "solution_source": "independent_gurobi_optimization",
        "effective_objective_sense": "minimize",
        "warm_start_supplied": False,
        "parent_incumbent_consumed": False,
        "fresh_process": True,
        "mip_gap_relative": 0.083,
        "solution_objective": 5.7,
        "variables": [{"name": "x", "value": 1.0}],
    }
    with gzip.open(solution_path, "wt", encoding="utf-8") as stream:
        json.dump(solution, stream)

    report = {
        "execution_valid": True,
        "label_eligible": True,
        "mathematical_audit": {"valid": True},
        "source_instance_id": identity,
        "mip_sha256": mip_sha,
        "checks": {"independent_solution_valid": True, "no_warm_start": True},
        "solve": {"mip_gap_relative": 0.083},
        "artifacts": {
            "parent_solution.json.gz": {
                "relative_path": "parent_solution.json.gz",
                "sha256": p._sha256(solution_path),
            }
        },
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    row = {
        "category": "CFL_medium_instance",
        "difficulty": "medium",
        "execution_time_seconds": 28800.0,
        "fold": 3,
        "label_format": "gurobi_parent_solution_json",
        "mip": {
            "relative_path": mip_path.relative_to(tmp_path).as_posix(),
            "sha256": mip_sha,
        },
        "mip_gap_relative": 0.083,
        "report": {
            "relative_path": report_path.relative_to(tmp_path).as_posix(),
            "sha256": p._sha256(report_path),
        },
        "role": "train",
        "solution": {
            "relative_path": solution_path.relative_to(tmp_path).as_posix(),
            "sha256": p._sha256(solution_path),
        },
        "source_instance_id": identity,
    }

    checked = p._validate_index_row(tmp_path, row)
    assert checked["identity"] == identity
    assert p._normalized_objective_sense("minimize") == "MINIMIZE"
    assert p._normalized_objective_sense(" MINIMIZE ") == "MINIMIZE"
    assert p._normalized_objective_sense("maximize") == "MAXIMIZE"
def test_pr57_pr54_nested_task_receipt_lineage_is_accepted(tmp_path):
    identity = "CFL_medium_instance_7"
    mip_path = tmp_path / "parent.lp.gz"
    solution_path = tmp_path / "parent_solution.json.gz"
    report_path = tmp_path / "gurobi_expansion_campaign_task_report.json"

    mip_path.write_bytes(b"dummy-pr54-medium-mip")
    mip_sha = p._sha256(mip_path)

    solution = {
        "solution_source": "independent_gurobi_optimization",
        "effective_objective_sense": "minimize",
        "warm_start_supplied": False,
        "parent_incumbent_consumed": False,
        "fresh_process": True,
        "mip_gap_relative": 0.031186630905388292,
        "solution_objective": 5.428377599678637,
        "variables": [{"name": "x", "value": 1.0}],
    }
    with gzip.open(solution_path, "wt", encoding="utf-8") as stream:
        json.dump(solution, stream)

    report = {
        "execution_valid": True,
        "label_eligible": True,
        "mathematical_audit": {"valid": True},
        "task": {
            "source_instance_id": identity,
            "category": "CFL_medium_instance",
            "difficulty": "medium",
            "fold": 0,
            "role": "test",
            "mip": {
                "relative_path": "parent.lp.gz",
                "sha256": mip_sha,
            },
        },
        "checks": {
            "fresh_process": True,
            "independent_solution_valid": True,
            "no_warm_start": True,
            "objective_minimize": True,
            "parent_sha256_match": True,
        },
        "solve": {"mip_gap_relative": 0.031186630905388292},
        "artifacts": {
            "parent_solution.json.gz": {
                "relative_path": "parent_solution.json.gz",
                "sha256": p._sha256(solution_path),
            }
        },
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    row = {
        "category": "CFL_medium_instance",
        "difficulty": "medium",
        "execution_time_seconds": 28800.621973991394,
        "fold": 0,
        "label_format": "gurobi_parent_solution_json",
        "mip": {"relative_path": "parent.lp.gz", "sha256": mip_sha},
        "mip_gap_relative": 0.031186630905388292,
        "report": {
            "relative_path": report_path.name,
            "sha256": p._sha256(report_path),
        },
        "role": "test",
        "solution": {
            "relative_path": solution_path.name,
            "sha256": p._sha256(solution_path),
        },
        "source_instance_id": identity,
    }

    checked = p._validate_index_row(tmp_path, row)
    assert checked["identity"] == identity


def test_pr57_pr54_nested_task_receipt_rejects_wrong_mip_lineage(tmp_path):
    identity = "CFL_medium_instance_7"
    mip_path = tmp_path / "parent.lp.gz"
    solution_path = tmp_path / "parent_solution.json.gz"
    report_path = tmp_path / "gurobi_expansion_campaign_task_report.json"

    mip_path.write_bytes(b"dummy-pr54-medium-mip")
    mip_sha = p._sha256(mip_path)

    solution = {
        "solution_source": "independent_gurobi_optimization",
        "effective_objective_sense": "minimize",
        "warm_start_supplied": False,
        "parent_incumbent_consumed": False,
        "fresh_process": True,
        "mip_gap_relative": 0.031,
        "solution_objective": 5.4,
        "variables": [{"name": "x", "value": 1.0}],
    }
    with gzip.open(solution_path, "wt", encoding="utf-8") as stream:
        json.dump(solution, stream)

    report = {
        "execution_valid": True,
        "label_eligible": True,
        "mathematical_audit": {"valid": True},
        "task": {
            "source_instance_id": identity,
            "category": "CFL_medium_instance",
            "difficulty": "medium",
            "fold": 0,
            "role": "test",
            "mip": {"relative_path": "parent.lp.gz", "sha256": "wrong-sha"},
        },
        "checks": {"independent_solution_valid": True},
        "solve": {"mip_gap_relative": 0.031},
        "artifacts": {
            "parent_solution.json.gz": {
                "relative_path": "parent_solution.json.gz",
                "sha256": p._sha256(solution_path),
            }
        },
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    row = {
        "category": "CFL_medium_instance",
        "difficulty": "medium",
        "execution_time_seconds": 28800.0,
        "fold": 0,
        "label_format": "gurobi_parent_solution_json",
        "mip": {"relative_path": "parent.lp.gz", "sha256": mip_sha},
        "mip_gap_relative": 0.031,
        "report": {
            "relative_path": report_path.name,
            "sha256": p._sha256(report_path),
        },
        "role": "test",
        "solution": {
            "relative_path": solution_path.name,
            "sha256": p._sha256(solution_path),
        },
        "source_instance_id": identity,
    }

    import pytest
    with pytest.raises(ValueError, match="task_mip_sha256"):
        p._validate_index_row(tmp_path, row)


def test_pr57_evaluation_recovery_is_evaluation_only_and_lf_clean():
    launcher = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "launch_pr57_54_evaluation_recovery.sh"
    )
    worker = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_pr57_54_evaluation_recovery.sbs"
    )
    audit = (
        PROJECT_ROOT
        / "scripts"
        / "slurm"
        / "dasci"
        / "submit_pr57_54_training_audit.sbs"
    )

    for path in (launcher, worker, audit):
        assert b"\r" not in path.read_bytes()

    launcher_text = launcher.read_text(encoding="utf-8")
    worker_text = worker.read_text(encoding="utf-8")
    audit_text = audit.read_text(encoding="utf-8")

    assert "afterok:${EVALUATION_JOB}" in launcher_text
    assert "evaluation_recovery" in launcher_text
    assert "evaluate_gasse_reconnected" in worker_text
    assert "run_pr57_training train" not in worker_text
    assert "recovery_scope=evaluation_only_no_retraining" in worker_text
    assert "PR57_EVALUATION_DIR" in audit_text
