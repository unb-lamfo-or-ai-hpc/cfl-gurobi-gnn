"""Frozen 42-parent confirmation inventory and targeted repair campaign.

Inspection is read-only. Historical graphs are never overwritten. A complete
inventory is not the same as admissible labels or an executable training split.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from cfl_gnn.graph.instance_provenance import sha256_file
from cfl_gnn.splits.instance_folds import read_manifest, role_for_fold
from cfl_gnn.training.gasse_reconnected import canonical_sha256, write_json

COHORT = tuple([f"CFL_easy_instance_{i}" for i in range(30)] +
               [f"CFL_medium_instance_{i}" for i in [*range(7), *range(15, 20)]])


def audit_confirmation(*, graph_dir, parent_manifest, output_dir):
    root, output = Path(graph_dir).resolve(), Path(output_dir).resolve()
    if (output / "confirmation_inventory.json").exists():
        raise ValueError("inventory already exists; choose a new output directory")
    folds = {e.source_instance_id: e for e in read_manifest(parent_manifest)}
    if not set(COHORT).issubset(folds):
        raise ValueError("canonical manifest does not cover frozen 42-parent cohort")
    rows, manifest = [], []
    for identity in COHORT:
        entry = folds[identity]
        paths = list(root.glob(f"*/processed/{identity}.pt"))
        row = {"source_instance_id": identity, "difficulty": entry.difficulty,
               "fold": entry.fold, "role": role_for_fold(entry.fold, 0),
               "graph_found": len(paths) == 1, "label_admissible": False,
               "strict_root_evidence": False, "structural_audit_required": True}
        if len(paths) == 1:
            path = paths[0]
            row["graph_relative_path"] = path.relative_to(root).as_posix()
            row["graph_sha256"] = sha256_file(path)
            try:
                sidecar = path.with_suffix(".provenance.json")
                provenance = json.loads(sidecar.read_text(encoding="utf-8"))
                row["provenance_sha256"] = sha256_file(sidecar)
                row["graph_hash_matches"] = provenance.get("graph_sha256") == row["graph_sha256"]
                label = provenance.get("label_provenance", {})
                gap = label.get("mip_gap", label.get("mip_gap_relative"))
                gap = float(gap) if gap is not None else None
                row["label_mip_gap_relative"] = gap if gap is not None and math.isfinite(gap) else None
                row["label_admissible"] = bool(row["graph_hash_matches"] and gap is not None and math.isfinite(gap) and 0 <= gap <= .1)
                row["strict_root_evidence"] = provenance.get("context_provenance", {}).get("mode") == "root_node_relaxation"
                row["label_status"] = "admissible_gap_not_yet_independent_feasibility" if row["label_admissible"] else "requires_compatible_solution_or_rescue"
                manifest.append({"sample_id": identity, "source_instance_id": identity,
                                 "difficulty": entry.difficulty, "sampling_strategy": "original",
                                 "graph_relative_path": row["graph_relative_path"], "graph_sha256": row["graph_sha256"]})
            except (OSError, ValueError, TypeError):
                row["label_status"] = "invalid_or_missing_provenance"
        else:
            row["label_status"] = "missing_or_ambiguous_graph"
        rows.append(row)
    repair = [r["source_instance_id"] for r in rows if not r["label_admissible"]]
    payload = {"schema_version": 1, "cohort": list(COHORT), "seed": 42,
               "epochs": 100, "objective_sense": "MINIMIZE", "rotation": 0,
               "maximum_label_mip_gap_relative": .1, "rescue_budgets_seconds": [3600, 14400],
               "parent_manifest_sha256": sha256_file(parent_manifest), "records": rows}
    report = {**payload, "contract_sha256": canonical_sha256(payload),
              "gate_status": "passed" if all(r["graph_found"] for r in rows) else "failed",
              "counts": {"planned": 42, "discovered": sum(r["graph_found"] for r in rows),
                         "gap_admissible": sum(r["label_admissible"] for r in rows)},
              "repair_parent_ids": repair,
              "partition_population": {role: sum(r["role"] == role for r in rows) for role in ("train", "validation", "test")},
              "training_ready": False, "next_gate": "independent_source_label_and_root_graph_validation",
              "development_only": True, "scientific_reporting_eligible": False}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "confirmation_inventory.json", report)
    with (output / "existing_graph_analysis_manifest.jsonl").open("w", encoding="utf-8") as stream:
        for row in manifest:
            stream.write(json.dumps(row, sort_keys=True)+"\n")
    return report


def execute_repair_task(*, campaign_dir, source_dir, run_root, task_index):
    """Resume compatible solves; escalate only an inadmissible 3600-second label."""
    from cfl_gnn.pipelines.parent_collection_task import execute_parent_collection_task
    from cfl_gnn.pipelines.parent_population import DEFAULT_EXPERIMENT_CONFIG
    from cfl_gnn.pipelines.parent_solutions import report_name
    campaign = Path(campaign_dir)
    outcomes = []
    for budget in (3600, 14400):
        plan_dir = campaign / f"repair_{budget}s"
        plan = json.loads((plan_dir / "parent_collection_plan.json").read_text(encoding="utf-8"))
        tasks = [t for t in plan["tasks"] if t["solver"] == "gurobi"]
        if not 0 <= task_index < len(tasks):
            raise ValueError("repair task index outside frozen inventory")
        task = tasks[task_index]
        execute_parent_collection_task(plan_dir=plan_dir, solver="gurobi", task_index=task_index,
            base_source_dir=source_dir, run_root=run_root,
            experiment_config_path=DEFAULT_EXPERIMENT_CONFIG, resume=True, overwrite=False, dry_run=False)
        report_path = Path(run_root) / task["run_dir_relative_path"] / report_name("gurobi")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        accepted = report.get("eligibility", {}).get("label_eligible") is True
        outcomes.append({"budget": budget, "report_sha256": sha256_file(report_path), "label_eligible": accepted})
        if accepted:
            break
    result = {"source_instance_id": task["source_instance_id"], "outcomes": outcomes,
              "label_eligible": accepted, "scientific_reporting_eligible": False}
    write_json(Path(run_root) / f"repair_task_{task_index}.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph_dir", type=Path, required=True)
    parser.add_argument("--parent_manifest", type=Path, default=Path("configs/splits/cfl_90_seed42_folds.csv"))
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--descriptive_outputs", action="store_true")
    parser.add_argument("--source_dir", type=Path)
    parser.add_argument("--prepare_repair_plans", action="store_true")
    args = parser.parse_args(argv)
    report = audit_confirmation(graph_dir=args.graph_dir, parent_manifest=args.parent_manifest, output_dir=args.output_dir)
    if args.descriptive_outputs:
        from cfl_gnn.analysis.graph_statistics import analyze_graph_manifest
        from cfl_gnn.analysis.graph_clustering import cluster_graph_manifest
        manifest = args.output_dir / "existing_graph_analysis_manifest.jsonl"
        analyze_graph_manifest(manifest_path=manifest, graph_root=args.graph_dir, output_dir=args.output_dir / "statistics")
        cluster_graph_manifest(manifest_path=manifest, graph_root=args.graph_dir, output_dir=args.output_dir / "clustering")
    if args.prepare_repair_plans:
        from cfl_gnn.pipelines.parent_population import write_parent_collection_plan, DEFAULT_CAMPAIGN_CONFIG, DEFAULT_EXPERIMENT_CONFIG
        if args.source_dir is None:
            raise ValueError("source_dir is required to prepare hash-bound repair plans")
        if report["repair_parent_ids"]:
            for budget in (3600, 14400):
                write_parent_collection_plan(base_source_dir=args.source_dir,
                    output_dir=args.output_dir / f"repair_{budget}s", parent_manifest_path=args.parent_manifest,
                    campaign_config_path=DEFAULT_CAMPAIGN_CONFIG, experiment_config_path=DEFAULT_EXPERIMENT_CONFIG,
                    instances=report["repair_parent_ids"], time_limit=budget, overwrite=False)
    print(f"[INFO] cohort=42 | discovered={report['counts']['discovered']} | admissible_gap={report['counts']['gap_admissible']} | training_ready=false")
    return 0 if report["gate_status"] == "passed" else 1
