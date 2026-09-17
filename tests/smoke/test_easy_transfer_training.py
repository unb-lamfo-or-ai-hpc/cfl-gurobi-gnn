"""Fail-closed cohort and provenance tests for easy-to-medium transfer."""
import json

import pytest

from cfl_gnn.pipelines import easy_transfer_training as t
from cfl_gnn.pipelines.confirmation_execution import descriptor


def seal(plan):
    ignored = {"contract_sha256", *t.READY}
    plan["contract_sha256"] = t.canonical_sha256({k: v for k, v in plan.items() if k not in ignored})
    return plan


@pytest.fixture
def source(tmp_path):
    graph, labels = tmp_path / "graphs", tmp_path / "labels"
    rows = []
    for entry in t.read_manifest(t.MANIFEST):
        if entry.difficulty != "easy":
            continue
        identity = entry.source_instance_id
        row = {"sample_id": identity, "parent_instance_id": identity, "source_instance_id": identity,
            "category": entry.category, "difficulty": "easy", "fold": entry.fold,
            "role": t.role_for_fold(entry.fold, 0), "sampling_strategy": "original",
            "graph_authority": "gurobi", "label_solver": "gurobi",
            "label_source": "independently_audited_gurobi_confirmation_label",
            "label_mip_gap_relative": 0., "mip_sha256": t.canonical_sha256(identity),
            "label_run_relative_path": identity, "label_file_name": "solution.json.gz"}
        for name, root, relative in (("graph", graph, f"graphs/{identity}.pt"),
                                     ("root", graph, f"roots/{identity}.json.gz"),
                                     ("label", labels, f"{identity}/solution.json.gz")):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{identity}:{name}")
            row[f"{name}_sha256"] = t.sha256_file(path)
            if name != "label":
                row[f"{name}_relative_path"] = relative
        receipt = {"source_instance_id": identity, "fold": row["fold"], "role": row["role"],
            "mip_sha256": row["mip_sha256"],
            "graph": {"relative_path": row["graph_relative_path"], "sha256": row["graph_sha256"]},
            "root": {"relative_path": row["root_relative_path"], "sha256": row["root_sha256"]},
            "source_label": {"sha256": row["label_sha256"]},
            "audit": {"roundtrip_readable": True, "label_variable_identity_match": True,
                "root_lp_feature_exactly_encoded": True, "effective_objective_sense": "MINIMIZE",
                "independent_label_feasibility": {"valid": True}}}
        path = graph / "receipts" / f"{identity}.json"
        t.write_json(path, receipt)
        row["receipt"] = descriptor(graph, path)
        rows.append(row)
    # No medium artifacts exist: planning must not try to load them.
    rows.append({"source_instance_id": "CFL_medium_instance_0", "difficulty": "medium"})
    plan = seal({"dataset_variant": "approved_39_parent_development_v1", "graph_authority": "gurobi",
        "label_solver": "gurobi", "records": rows, "graph_dataset_contract_sha256": "a"*64,
        "source_collection_contract_sha256": "b"*64, "graph_report_sha256": "c"*64})
    path = tmp_path / "source.json"
    t.write_json(path, plan)
    return dict(source_training_plan=path, graph_root=graph, label_root=labels)


def mutate(source, function):
    path = source["source_training_plan"]
    plan = t.read_json(path)
    function(plan)
    t.write_json(path, seal(plan))


def test_plan_has_only_canonical_easy_and_fixed_protocol(source, tmp_path):
    plan = t.build_plan(**source)
    t.validate_training_plan(plan)
    assert plan["partition_counts"] == {"train": 18, "validation": 6, "test": 6}
    assert len(plan["records"]) == 30
    assert all(r["difficulty"] == "easy" for r in plan["records"])
    assert plan["protocol"]["optimization"]["epochs"] == 100
    assert plan["protocol"]["optimization"]["seed"] == 42
    assert plan["initialization"] == "fresh_seed42_no_pretrained_checkpoint"
    assert plan["scientific_reporting_eligible"] is False
    assert str(tmp_path) not in json.dumps(plan)
    assert t.build_plan(**source) == plan


@pytest.mark.parametrize("field,value", [
    ("role", "wrong"), ("fold", 99), ("difficulty", "medium"),
    ("sampling_strategy", "incumbent_local_branching"), ("label_solver", "scip"),
    ("label_mip_gap_relative", .10001), ("label_mip_gap_relative", -1),
    ("label_mip_gap_relative", True), ("label_source", "legacy_unverified"),
])
def test_resealed_ineligible_record_rejected(source, field, value):
    mutate(source, lambda plan: plan["records"][0].update({field: value}))
    with pytest.raises(ValueError):
        t.build_plan(**source)


def test_missing_and_duplicate_parents_rejected(source):
    original = t.read_json(source["source_training_plan"])
    for rows in (original["records"][1:], original["records"] + [original["records"][0]]):
        t.write_json(source["source_training_plan"], seal({**original, "records": rows}))
        with pytest.raises(ValueError):
            t.build_plan(**source)


@pytest.mark.parametrize("artifact", ["graph", "root", "label", "receipt"])
def test_artifact_mutation_rejected(source, artifact):
    row = t.read_json(source["source_training_plan"])["records"][0]
    if artifact == "label":
        path = source["label_root"] / row["label_run_relative_path"] / row["label_file_name"]
    else:
        relative = row["receipt"]["relative_path"] if artifact == "receipt" else row[f"{artifact}_relative_path"]
        path = source["graph_root"] / relative
    path.write_text("changed")
    with pytest.raises(ValueError, match="artifact missing or changed"):
        t.build_plan(**source)


def test_failed_mathematical_receipt_rejected_even_with_resealed_hash(source):
    plan = t.read_json(source["source_training_plan"])
    row = plan["records"][0]
    path = source["graph_root"] / row["receipt"]["relative_path"]
    receipt = t.read_json(path)
    receipt["audit"]["independent_label_feasibility"]["valid"] = False
    t.write_json(path, receipt)
    row["receipt"] = descriptor(source["graph_root"], path)
    t.write_json(source["source_training_plan"], seal(plan))
    with pytest.raises(ValueError, match="does not certify"):
        t.build_plan(**source)


def test_contract_mismatch_blocks_training_before_output(source, tmp_path, monkeypatch):
    monkeypatch.setattr(t, "run_serial_training", lambda *a, **kw: pytest.fail("must not train"))
    output = tmp_path / "training"
    with pytest.raises(ValueError, match="preflight contract changed"):
        t.execute(**source, output_dir=output, expected_contract="wrong")
    assert not output.exists()


def test_no_overwrite_of_training_output(source, tmp_path):
    plan = t.build_plan(**source)
    output = tmp_path / "training"
    output.mkdir()
    with pytest.raises(FileExistsError):
        t.execute(**source, output_dir=output, expected_contract=plan["contract_sha256"])


def test_launcher_is_lf_only_and_does_not_submit_or_resolve_models():
    payload = (t.PROJECT_ROOT / "scripts/slurm/dasci/submit_easy_transfer_training.sbs").read_bytes()
    assert b"\r" not in payload
    assert b"set -euo pipefail" in payload
    assert b"--expected_contract" in payload
    assert b"sbatch" not in payload and b"--overwrite" not in payload


def test_training_passes_only_easy_to_backend(source, tmp_path, monkeypatch):
    plan = t.build_plan(**source)
    calls = []
    def fake_train(actual, **kwargs):
        calls.append(actual)
        report = {"test_graphs_loaded": 0, "checkpoint_selection": "minimum_validation_weighted_bce",
                  "threshold_source": "maximum_validation_f1"}
        t.write_json(kwargs["output_dir"] / t.TRAINING_REPORT_NAME, report)
        return report
    monkeypatch.setattr(t, "run_serial_training", fake_train)
    monkeypatch.setattr(t, "validate_training_receipt", lambda report, output: None)
    result = t.execute(**source, output_dir=tmp_path / "train", expected_contract=plan["contract_sha256"])
    assert len(calls) == 1 and len(calls[0]["records"]) == 30
    assert result["medium_graphs_loaded"] == 0
    assert result["next_gate"] == "paired_medium_partial_start_engineering_pilot"
