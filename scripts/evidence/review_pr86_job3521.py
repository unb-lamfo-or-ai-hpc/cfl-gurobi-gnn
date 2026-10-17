"""Pinned offline guidance review, preparation ledger and unapproved budget.

The source-tree validator passed before this module was added. Historical
dependency hashes are never rebuilt against a later source tree. This review
accepts exactly one immutable return and cross-checks it against job3520.
No private artifact is deserialized and no solver, GPU or scheduler is called.
"""

import argparse
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

import plan_pr86_comparison as proposal
import pr86_cost_accounting as costs
import pr86_guidance_preparation as guidance
import review_pr86_job3520 as roots
from review_pr86_installed_bindings import csv_bytes

SHA = "3a78942e349737c916ba717df7110bf867771e85613578a9f2256df2d6ea62f3"
COMMIT = "4209e959021b4e85d11cc5b9726702328462cc94"
PLAN = "ea921855f000158fc0adc9da554f73338c7ec6d3494fb2e2e5f3762eefd53eaa"
DESTINATION = proposal.ROOT / "docs/evidence/pr86/job3521"
require = guidance.require


def summarize(value, root_value, root_rows, root_report):
    """Reconcile measurements, not standalone-method or solver-speedup claims."""
    child, supervision = value["child"], value["supervision"]
    require(child["complete"] and child["failure_type"] is None, "incomplete")
    require(supervision["guard_stop"] is None, "memory_stop")
    require(supervision["child_exit_code"] == 0, "child_exit")
    require(value["accounting"]["state"] == "COMPLETED", "accounting_state")
    require(all(r["ExitCode"] == "0:0" for r in value["accounting"]["rows"]), "exit")
    require(
        [r["parent"] for r in child["rows"]] == [r["parent"] for r in root_rows],
        "parents",
    )
    require(len(child["rows"]) == 10, "ten_parents")
    rows = []
    for item, root, original in zip(
        child["rows"], root_rows, root_value["summary"]["rows"]
    ):
        require(item["root_sha256"] == root["root_sha256"], "root_identity")
        require(
            item["model_sha256"] == original["result"]["model_sha256"], "model_identity"
        )
        require(item["checkpoint_sha256"] == proposal.CHECKPOINT, "checkpoint")
        require(item["effective_objective_sense"] == "MINIMIZE", "sense")
        require(
            (item["forward_calls"], item["optimization_calls"], item["training_runs"])
            == (1, 0, 0),
            "calls",
        )
        require(item["scientific_reporting_eligible"] is False, "original_eligibility")
        n, k, positive = (
            item[key]
            for key in ("binary_variables", "selected_support", "positive_assignments")
        )
        require(all(type(v) is int for v in (n, k, positive)), "support_type")
        require(n > 0 and 0 < positive <= k <= n and not item["abstained"], "support")
        require(k == min(20000, max(1, n // 10)), "support_policy")
        require(set(item["regions_seconds"]) == set(guidance.REGIONS), "regions")
        times = {key: costs.seconds(v) for key, v in item["regions_seconds"].items()}
        forward = costs.seconds(item["forward_seconds_nested_in_inference"])
        require(forward <= times["inference"], "nested_forward")
        # The shared export writes both methods: do not invent a per-method split.
        # Root supervision includes root export and its measured process overhead.
        common = root["supervisor_wall_seconds"] + sum(
            times[key] for key in ("features", "inference", "assembly_gnn")
        )
        rows.append(
            {
                "parent": item["parent"],
                "alias": root["alias"],
                "binary_variables": n,
                "selected_support_per_method": k,
                "positive_assignments_per_method": positive,
                "coverage_fraction": k / n,
                "root_supervised_seconds": root["supervisor_wall_seconds"],
                **{key + "_seconds": v for key, v in times.items()},
                "forward_seconds_nested_in_inference": forward,
                "M1_scoped_dependency_seconds": common + times["assembly_lp"],
                "M2_scoped_dependency_seconds": common,
                "shared_private_export_seconds": times["private_export"],
                "guidance_regions_seconds": sum(times.values()),
                "gpu_peak_allocated_bytes": item["gpu_peak_allocated_bytes"],
                "gpu_peak_reserved_bytes": item["gpu_peak_reserved_bytes"],
                "root_sha256": item["root_sha256"],
                "private_starts_sha256": item["private_starts_sha256"],
                "guidance_return_sha256": SHA,
            }
        )
    region_totals = {
        key: sum(r[key + "_seconds"] for r in rows) for key in guidance.REGIONS
    }
    regions = sum(region_totals.values())
    setup = costs.seconds(child["shared_setup_seconds"])
    child_wall = costs.seconds(child["child_observed_wall_seconds"])
    supervisor_wall = costs.seconds(supervision["supervisor_wall_seconds"])
    require(
        child_wall >= setup + regions and supervisor_wall >= child_wall,
        "nested_intervals",
    )
    remainder = child_wall - setup - regions
    root_batch = root_report["batch_observed_wall_seconds"]
    root_residual = root_report["batch_outside_supervision_seconds"]
    combined = root_batch + supervisor_wall
    components = {
        "root_supervised": sum(r["root_supervised_seconds"] for r in rows),
        "root_batch_residual": root_residual,
        **region_totals,
        "shared_initialization": setup,
        "guidance_child_residual": remainder,
        "guidance_supervisor_residual": supervisor_wall - child_wall,
    }
    require(
        math.isclose(sum(components.values()), combined, abs_tol=1e-8), "ledger_balance"
    )
    # An explicit allocation sensitivity scenario, not newly observed cold runs.
    shared = root_residual + setup + remainder + supervisor_wall - child_wall
    for row in rows:
        overhead = shared / len(rows) + row["shared_private_export_seconds"]
        row["equal_parent_shared_overhead_scenario_seconds"] = overhead
        for method in ("M1", "M2"):
            assigned = row[method + "_scoped_dependency_seconds"] + overhead
            row[method + "_allocated_preparation_scenario_seconds"] = assigned
            row[method + "_allocated_scenario_per_seven_uses_seconds"] = assigned / 7
    report = {
        "protocol_id": "pr86_job3521_public_review_v1",
        "return_sha256": SHA,
        "source_commit": COMMIT,
        "plan_sha256": PLAN,
        "root_return_sha256": roots.SHA,
        "job_id": "3521",
        "parents": len(rows),
        "forward_calls": 10,
        "optimization_calls": 0,
        "training_runs": 0,
        "abstentions": 0,
        "guidance_region_totals_seconds": region_totals,
        "shared_setup_seconds": setup,
        "child_observed_wall_seconds": child_wall,
        "guidance_supervisor_wall_seconds": supervisor_wall,
        "scheduler_elapsed_seconds": value["accounting"]["rows"][0]["ElapsedRaw"],
        "combined_instrumented_preparation_seconds": combined,
        "disjoint_campaign_components_seconds": components,
        "sampled_job_cgroup_peak_bytes": supervision["sampled_cgroup_peak_bytes"],
        "gpu_peak_allocated_bytes": max(r["gpu_peak_allocated_bytes"] for r in rows),
        "gpu_peak_reserved_bytes": max(r["gpu_peak_reserved_bytes"] for r in rows),
        "runtime": child["runtime"],
        "qualified_scope": "pinned_public_preparation_identity_support_and_timing_observations",
        "allocation_scenario": "equal_parent_shared_overhead_and_full_coupled_export_to_each_guided_method",
        "allocation_is_modeled_not_observed_standalone_cold_cost": True,
        "M1_depends_on_gnn_assembly": True,
        "standalone_cold_preparation_measured": False,
        "whole_job_end_to_end_qualified": False,
        "private_artifacts_reopened": False,
        "solver_start_acceptance_observed": False,
        "main_comparison_admitted": False,
        "scientific_reporting_eligible": False,
        "optimization_runs_added_by_review": 0,
    }
    return rows, report


def review(raw):
    require(guidance.digest(raw) == SHA, "immutable_return_hash")
    value = guidance.roots.isolated.existing.review.flow.meta.strict_json(raw)
    require(value["plan_sha256"] == PLAN, "plan")
    require(guidance.digest(guidance.encoded(value["plan"])) == PLAN, "plan_bytes")
    require(value["plan"]["source_commit"] == COMMIT, "source")
    require(value["plan"]["root_return_sha256"] == roots.SHA, "root_return")
    require(value["child"]["job_id"] == value["accounting"]["job_id"] == "3521", "job")
    for key in (
        "scientific_reporting_eligible",
        "raw_logs_included",
        "raw_predictions_included",
    ):
        require(value[key] is False, "public_scope")
    root_value, root_rows, root_report = roots.review(
        (roots.DESTINATION / "public_return.json").read_bytes()
    )
    rows, report = summarize(value, root_value, root_rows, root_report)
    return value, rows, report


def budget(report):
    """Freeze a reviewable resource request; no installed admission is minted."""
    plan, cells = proposal.build()
    groups = plan["groups"]
    return {
        "protocol_id": "pr86_remaining_main_budget_request_v1",
        "matrix_plan_sha256": proposal.digest(proposal.encoded(plan)),
        "planned_cells_sha256": proposal.digest(proposal.encoded(cells)),
        "guidance_return_sha256": report["return_sha256"],
        "root_return_sha256": roots.SHA,
        "main_optimization_calls_maximum": len(cells),
        "new_root_calls": 0,
        "new_forwards": 0,
        "training_runs": 0,
        "submissions_maximum": len(groups),
        "concurrent_jobs_maximum": 1,
        "calls_per_job_maximum": 3,
        "job_wall_seconds_maximum": 14400,
        "child_deadline_seconds": 3780,
        "solver_seconds_maximum": sum(c["time_limit_seconds"] for c in cells),
        "sequential_reserved_wall_seconds_maximum": sum(
            g["job_wall_seconds"] for g in groups
        ),
        "reserved_physical_core_seconds_maximum": sum(
            g["threads"] * g["job_wall_seconds"] for g in groups
        ),
        "solver_capacity_physical_core_seconds_maximum": sum(
            c["threads"] * c["time_limit_seconds"] for c in cells
        ),
        "scheduler": plan["scheduler"],
        "memory": plan["memory"],
        "parameters": plan["parameters"],
        "groups": groups,
        "stop_policy": "stop_and_pause_on_failed_or_incomplete_group_no_replacement",
        "first_group_must_be_reviewed_before_remaining_dispatch": True,
        "first_group_is_part_of_210_not_additional_pilot": True,
        "automatic_retry": False,
        "queues_included": False,
        "execution_interface_included": False,
        "resource_budget_approved": False,
        "solver_execution_admitted": False,
        "approval_alone_does_not_bypass_final_source_and_installed_binding_checks": True,
    }


def figure(rows):
    """Dependency-free static figure of observed disjoint parent costs."""
    columns = [
        ("root_supervised_seconds", "Raíz supervisada", "#475569"),
        ("features_seconds", "Grafo y comprobaciones", "#0284c7"),
        ("inference_seconds", "Inferencia", "#16a34a"),
        ("assembly_gnn_seconds", "Montaje GNN", "#9333ea"),
        ("assembly_lp_seconds", "Montaje LP", "#db2777"),
        ("private_export_seconds", "Exportación conjunta", "#ea580c"),
    ]
    maximum = max(sum(r[k] for k, _, _ in columns) for r in rows)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="650" viewBox="0 0 1100 650" role="img">',
        "<title>Preparación observada por instancia: jobs 3520 y 3521</title>",
        '<rect width="1100" height="650" fill="white"/>',
        '<g font-family="sans-serif" fill="#0f172a">',
        '<text x="32" y="36" font-size="22">Preparación observada por instancia</text>',
    ]
    for i, row in enumerate(rows):
        y, x = 76 + i * 43, 95.0
        parts.append(
            f'<text x="32" y="{y + 20}" font-size="15">{escape(row["alias"])}</text>'
        )
        total = 0
        for key, label, color in columns:
            seconds = row[key]
            width = seconds / maximum * 810
            parts.append(
                f'<rect x="{x:.3f}" y="{y}" width="{width:.3f}" height="27" fill="{color}"><title>{escape(label)}: {seconds:.3f} s</title></rect>'
            )
            x += width
            total += seconds
        parts.append(
            f'<text x="{x + 9:.3f}" y="{y + 20}" font-size="14">{total:.2f} s</text>'
        )
    for i, (_, label, color) in enumerate(columns):
        x, y = 32 + (i % 3) * 350, 532 + (i // 3) * 30
        parts.append(
            f'<rect x="{x}" y="{y}" width="16" height="16" fill="{color}"/><text x="{x + 23}" y="{y + 14}" font-size="14">{escape(label)}</text>'
        )
    parts.extend(
        [
            '<text x="32" y="610" font-size="14">No incluye inicialización común ni residuos globales; véase el registro completo.</text>',
            '<text x="32" y="635" font-size="14">No es tiempo de resolución, speedup ni coste frío independiente por método.</text>',
            "</g></svg>\n",
        ]
    )
    return "".join(parts).encode()


def produce(receipt, output):
    raw = receipt.read_bytes()
    _, rows, report = review(raw)
    output.mkdir(parents=True, exist_ok=False)
    (output / "public_return.json").write_bytes(raw)
    (output / "preparation_costs.csv").write_bytes(csv_bytes(rows))
    (output / "preparation_observed.svg").write_bytes(figure(rows))
    guidance.write(output / "review.json", report)
    guidance.write(output / "remaining_budget_request.json", budget(report))
    guidance.write(
        output / "manifest.json",
        {
            "files": {
                p.name: guidance.digest(p.read_bytes())
                for p in sorted(output.iterdir())
            },
            "original_receipt_bytes_preserved": True,
        },
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(produce(args.receipt, args.output), indent=2))
