"""Pinned jobs3598..3603 and a 147-cell descriptive ledger; no solver."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import review_pr86_f0 as f0
import review_pr86_wave37 as prior

q = prior.q
SHA = "17503f14d5a49aca0e8cb71c591578db7e4191fd183a03edfb04650ebe4a29f6"
COMMIT = "33a5cb91d1225c8d5a63402a640f9800533b58bd"
PLAN = "e5787839233e4bc11c8712016c03df3874b92b76c345cd22eacb7cb5af1a3570"
DEST = q.ROOT / "docs/evidence/pr86/jobs3598-3603"


def review_wave(raw):
    # The original validator passed before edits. Never rebuild historical pins.
    q.require(q.digest(raw) == SHA, "wave43_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(frozen["source_commit"] == COMMIT, "wave43_source")
    q.require(
        value["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "wave43_plan"
    )
    original, cells = q.first.executor.proposal.build()
    q.require(len(frozen["groups"]) == 6, "six_groups")
    for group, expected in zip(frozen["groups"], original["groups"][43:49]):
        q.require(group["group"] == expected, "manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == expected["group_id"]],
            "manifest_cells",
        )
    policy = SimpleNamespace(
        protocol="pr86_frozen_groups43_48_v1", plan=lambda _: frozen
    )
    q.require(
        q.validate_return(raw, policy)["ready_for_independent_review"], "incomplete"
    )
    q.require(
        [r["accounting"]["job_id"] for r in value["returns"]]
        == [str(j) for j in range(3598, 3604)],
        "wave43_jobs",
    )
    return value


def review(raw):
    rows, previous = prior.review(q.read(prior.DEST / "public_return.json"))
    wave = review_wave(raw)
    rows += f0.rows_from_returns(
        wave["returns"], {str(j): SHA for j in range(3598, 3604)}
    )
    original, cells = q.first.executor.proposal.build()
    groups = {g["group_id"] for g in original["groups"][:49]}
    expected = {c["cell_id"] for c in cells if c["group_id"] in groups}
    q.require(
        len(rows) == len(expected) == 147 and {r["cell_id"] for r in rows} == expected,
        "prefix147",
    )
    return rows, {
        "protocol_id": "pr86_fortynine_group_descriptive_review_v1",
        "input_return_sha256": previous["input_return_sha256"] + [SHA],
        "completed_cells": 147,
        "completed_groups": 49,
        "remaining_cells": 63,
        "remaining_groups": 21,
        "distinct_historically_exposed_parents": 7,
        "complete_five_cap_parents": ["F0", "F3", "F6", "F14", "F27", "F29", "M0"],
        "M0_complete": True,
        "M4_unobserved": True,
        "target_met_cells": sum(
            not r["right_censored"] and r["gap_fraction"] <= 1e-4 for r in rows
        ),
        "right_censored_cells": sum(r["right_censored"] for r in rows),
        "easy_cells": sum(r["parent"].startswith("CFL_easy_") for r in rows),
        "medium_cells": sum(r["parent"].startswith("CFL_medium_") for r in rows),
        "wave_scheduler_elapsed_sum_seconds": sum(
            r["accounting"]["rows"][0]["ElapsedRaw"] for r in wave["returns"]
        ),
        "all_observed_target_gaps_met": all(
            not r["right_censored"] and r["gap_fraction"] <= 1e-4 for r in rows
        ),
        "qualified_scope": "pinned_descriptive_solver_and_scoped_attempt_measurements",
        "population_speedup_claim": False,
        "whole_job_cold_cost_qualified": False,
        "original_receipts_and_flags_unchanged": True,
        "optimization_runs_added": 0,
    }


def medium_figure(rows, metric):
    """Terminal gap or sampled job memory; never uncensored timeout timing."""
    q.require(metric in ("gap", "memory"), "figure_metric")
    q.require(
        len(rows) == 21 and all(r["alias"] == "M0" for r in rows), "medium_figure_scope"
    )
    selected = [r for r in rows if r["seed"] == 42]
    q.require(
        len(selected) == 15
        and len({(r["threads"], r["method"]) for r in selected}) == 15,
        "figure_cells",
    )
    gap = metric == "gap"
    maximum = max(r["gap_fraction"] * 100 for r in selected) * 1.12 if gap else 64
    title = "brecha final (%)" if gap else "pico de RAM del cgroup (GiB)"
    subtitle = (
        "Calidad al terminar: objetivo alcanzado o presupuesto agotado. No es tiempo hasta el objetivo."
        if gap
        else "Memoria del job muestreada; no es Slurm MaxRSS ni memoria interna del solver."
    )
    target = sum(not r["right_censored"] and r["gap_fraction"] <= 1e-4 for r in rows)
    censored = sum(r["right_censored"] for r in rows)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="940" height="500" viewBox="0 0 940 500">',
        '<rect width="940" height="500" fill="white"/>',
        '<g font-family="sans-serif" fill="#182635">',
        f'<text x="60" y="28" font-size="20">Instancia M0: {title} por límite de hilos (seed 42)</text>',
        f'<text x="60" y="52" font-size="12">{subtitle}</text>',
        '<text x="60" y="74" font-size="12">M0/M1/M2 son métodos; M0 en el título identifica la instancia media.</text>',
    ]
    for tick in range(5):
        y = 350 - tick * 55
        unit = "%" if gap else "GiB"
        parts.append(
            f'<path d="M70 {y}H690" stroke="#dbe2e9"/><text x="10" y="{y + 4}" font-size="12">{maximum * tick / 4:.1f} {unit}</text>'
        )
    if not gap:
        y = 350 - 56 / maximum * 220
        parts += [
            f'<path d="M70 {y:.2f}H690" stroke="#a63232" stroke-dasharray="6 4"/>',
            f'<text x="715" y="{y + 4:.2f}" font-size="12">Parada: 56 GiB</text>',
            '<text x="715" y="125" font-size="12">Límite RAM: 64 GiB</text>',
        ]
    for method, color in (("M0", "#3457a6"), ("M1", "#b15a10"), ("M2", "#128064")):
        points = []
        for i, cap in enumerate((1, 2, 4, 8, 16)):
            row = next(
                r for r in selected if r["method"] == method and r["threads"] == cap
            )
            value = (
                row["gap_fraction"] * 100
                if gap
                else row["sampled_cgroup_peak_bytes"] / 2**30
            )
            x, y = 100 + i * 140, 350 - value / maximum * 220
            points.append(f"{x},{y:.2f}")
            fill = "white" if row["right_censored"] else color
            parts.append(
                f'<circle cx="{x}" cy="{y:.2f}" r="5" fill="{fill}" stroke="{color}" stroke-width="2"/>'
            )
        parts += [
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>',
            f'<text x="730" y="{210 + int(method[1]) * 24}" fill="{color}">{method}</text>',
        ]
    for i, cap in enumerate((1, 2, 4, 8, 16)):
        parts.append(f'<text x="{96 + i * 140}" y="375">{cap}</text>')
    parts += [
        '<text x="280" y="405">Límite de hilos / núcleos físicos</text>',
        f'<text x="60" y="435" font-size="12">Matriz completa: {censored}/21 censurados y {target}/21 con objetivo alcanzado. Semillas 43/44 en la tabla.</text>',
        '<text x="60" y="458" font-size="12">Círculo vacío: tiempo censurado; lleno: objetivo alcanzado (M2/16, 3204,179 s, brecha cero).</text>',
        '<text x="60" y="481" font-size="12">Un padre expuesto; sin generalización. Las líneas conectan límites discretos, no nuevas observaciones.</text>',
        "</g></svg>",
    ]
    return "\n".join(parts).encode()


def publish(directory):
    rows, summary = review(q.read(DEST / "public_return.json"))
    outputs = {
        "campaign_results.csv": f0.csv_bytes(rows),
        "review.json": q.encoded(summary),
        "m0_gap_cpu.svg": medium_figure([r for r in rows if r["alias"] == "M0"], "gap"),
        "m0_memory_cpu.svg": medium_figure(
            [r for r in rows if r["alias"] == "M0"], "memory"
        ),
    }
    outputs["manifest.json"] = q.encoded(
        {
            "inputs": summary["input_return_sha256"],
            "outputs": {k: q.digest(v) for k, v in outputs.items()},
        }
    )
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        path = directory / name
        if path.exists():
            q.require(q.read(path) == raw, "preserve_output")
        else:
            with path.open("xb") as stream:
                stream.write(raw)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(publish(parser.parse_args().output), indent=2))


if __name__ == "__main__":
    main()
