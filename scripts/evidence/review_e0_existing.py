"""Reproduce descriptive historical comparisons; never admit new matched controls."""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import reconcile_e0_coverage as coverage
from review_pr80_job3503 import require, write_csv

SHA = "ab949fc05dbab53c3aca48f3d78962006b44d624bc62a21a301f321278601c9b"
SOURCE = coverage.ROOT / "docs/evidence/e0/coverage.json"


def review():
    data = SOURCE.read_bytes()
    require(coverage.digest(data) == SHA, "receipt_hash")
    receipt = coverage.strict_json(data)
    coverage_rows = coverage.coverage(receipt)
    require(receipt["recognized_metadata_scan_complete"] is True, "scan_incomplete")
    require(not receipt["failures"], "scan_failures")
    plans = {
        p["contract_sha256"]: p
        for p in receipt["plans"]
        if p["contract_digest_matches"]
    }
    selected, excluded = [], []
    for row in receipt["candidates"]:
        if row["kind"] != "method":
            continue
        if row["contract_sha256"] not in plans:
            excluded.append(
                {
                    "parent": row["parent"],
                    "method": row["method"],
                    "sha256": row["sha256"],
                    "reason": "no_matching_guidance_plan_observed",
                }
            )
            continue
        require(
            all(
                row[k] is True
                for k in (
                    "gate_passed_declared",
                    "parameter_digest_matches",
                    "fresh_model_declared",
                    "model_unchanged_declared",
                    "independent_feasibility_declared",
                )
            ),
            "method_declarations",
        )
        selected.append(row)
    require(len(selected) == 24 and len(excluded) == 1, "historical_counts")
    with (coverage.ROOT / "manuscript/results/current/table_solver_outcomes.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        published = {
            (r["source_instance_id"], r["method"]): r for r in csv.DictReader(stream)
        }
    grouped = defaultdict(list)
    rows, effects = [], []
    strata = {r["parent"]: r["evaluation_stratum"] for r in coverage_rows}
    for item in selected:
        grouped[item["parent"]].append(item)
        original = published[item["parent"], item["method"]]
        for key in ("primal", "dual", "terminal_mip_gap_relative"):
            require(
                math.isclose(
                    float(original[key]),
                    item["outcomes"][key],
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ),
                "published_value_mismatch",
            )
        rows.append(
            {
                "parent": item["parent"],
                "stratum": strata[item["parent"]],
                "method": item["method"],
                "contract_sha256": item["contract_sha256"],
                "method_sha256": item["sha256"],
                "checkpoint_sha256": plans[item["contract_sha256"]][
                    "checkpoint_sha256"
                ],
                "threads": item["parameters"]["Threads"],
                "time_limit_seconds": item["parameters"]["TimeLimit"],
                "primal": item["outcomes"]["primal"],
                "dual": item["outcomes"]["dual"],
                "gap_fraction": item["outcomes"]["terminal_mip_gap_relative"],
                "optimize_seconds": item["timing"]["model_optimize_wall_time_seconds"],
                "method_wall_seconds": item["timing"]["total_wall_time_seconds"],
                "right_censored": item["right_censored"],
                "start_status": item["start_status"],
                "preparation_cost_included": False,
                "new_control_admitted": False,
            }
        )
    for parent, items in grouped.items():
        require({r["method"] for r in items} == set(coverage.METHODS), "method_trio")
        for key in (
            "contract_sha256",
            "mip_sha256",
            "mathematical_signature_sha256",
            "parameter_sha256",
        ):
            require(
                len({r[key] for r in items}) == 1 and items[0][key] is not None,
                "pair_metadata",
            )
        control = next(r for r in items if r["method"] == coverage.METHODS[0])
        for guided in items:
            if guided is control:
                continue
            effects.append(
                {
                    "parent": parent,
                    "stratum": strata[parent],
                    "method": guided["method"],
                    "gap_difference_percentage_points": 100
                    * (
                        guided["outcomes"]["terminal_mip_gap_relative"]
                        - control["outcomes"]["terminal_mip_gap_relative"]
                    ),
                    "optimize_time_difference_seconds": guided["timing"][
                        "model_optimize_wall_time_seconds"
                    ]
                    - control["timing"]["model_optimize_wall_time_seconds"],
                    "unbiased_speedup_claimed": False,
                }
            )
    return (
        receipt,
        coverage_rows,
        sorted(rows, key=lambda r: (r["parent"], r["method"])),
        sorted(effects, key=lambda r: (r["parent"], r["method"])),
        excluded,
    )


def produce(output, figures=False):
    receipt, cells, rows, effects, excluded = review()
    output.mkdir(parents=True, exist_ok=False)
    for name, items in (
        ("coverage.csv", cells),
        ("historical_methods.csv", rows),
        ("historical_effects.csv", effects),
        ("excluded_control.csv", excluded),
    ):
        write_csv(output / name, items)
    summary = {
        "receipt_sha256": SHA,
        "candidate_rows": len(receipt["candidates"]),
        "method_records": 25,
        "aggregate_records": 25,
        "paired_historical_methods": 24,
        "distinct_plan_bytes": len({p["sha256"] for p in receipt["plans"]}),
        "pairs": 8,
        "missing_cells_in_recognized_scope": 24,
        "scientific_reporting_eligible": False,
        "scope": "historical_metadata_and_published_numeric_parity_not_new_solution_revalidation",
        "limitations": [
            "solver_version_not_exported_by_v1_collector",
            "preparation_and_root_cost_not_exported",
            "solution_bytes_not_reverified",
            "no_new_matched_control_admission",
        ],
    }
    (output / "review.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    if figures:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(9, 5.5))
        order = [0, 4, 7, 12, 5, 6, 9, 20]
        for method, marker, color, label in (
            (coverage.METHODS[1], "s", "#cd7f32", "Inicio LP"),
            (coverage.METHODS[2], "o", "#176f85", "Inicio GNN mixta"),
        ):
            mapping = {r["parent"]: r for r in effects if r["method"] == method}
            ax.scatter(
                [
                    mapping[f"CFL_medium_instance_{i}"][
                        "gap_difference_percentage_points"
                    ]
                    for i in order
                ],
                range(8),
                marker=marker,
                color=color,
                label=label,
                s=65,
            )
        ax.set_yticks(range(8), [f"M{i}" for i in order])
        ax.invert_yaxis()
        ax.axvline(0, color="#777777", linewidth=1)
        ax.axhline(3.5, color="#999999", linestyle="--", linewidth=1)
        ax.set_xlabel("Brecha final guiada − control (puntos porcentuales)")
        ax.set_title(
            "Resultados históricos: menor es mejor\nArriba: prueba predictiva; abajo: excluidas del aprendizaje"
        )
        ax.legend(loc="upper left")
        ax.grid(axis="x", alpha=0.15)
        fig.text(
            0.07,
            0.02,
            "Un hilo, semilla 42, límite 3.600 s. Distintos tiempos de parada.\nComparación descriptiva; no mide aceleración ni generalización nueva.",
            fontsize=9,
        )
        fig.tight_layout(rect=(0, 0.09, 1, 1))
        for suffix in ("svg", "pdf", "png"):
            fig.savefig(output / ("historical_gap." + suffix), dpi=160)
        plt.close(fig)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figures", action="store_true")
    args = parser.parse_args()
    print(json.dumps(produce(args.output, args.figures)))
