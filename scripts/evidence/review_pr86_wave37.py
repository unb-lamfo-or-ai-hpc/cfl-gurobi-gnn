"""Pinned jobs3592..3597 and a 129-cell descriptive ledger; no solver."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import review_pr86_f0 as f0
import review_pr86_wave31 as prior

q = prior.q
SHA = "fca3de37c0122955c6df593b5f11f7fef81a1dd2af3754de92c45cb60fb4cc94"
COMMIT = "880399c098d5ce0a6b46956f9c5cb85c473e3f66"
PLAN = "f45b286f9e44fb17cf2bb5fec26897baf33b67c7ea4dd8f595c0c28287824fa4"
DEST = q.ROOT / "docs/evidence/pr86/jobs3592-3597"


def review_wave(raw):
    # The original validator passed before edits. Never rebuild historical pins.
    q.require(q.digest(raw) == SHA, "wave37_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(frozen["source_commit"] == COMMIT, "wave37_source")
    q.require(
        value["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "wave37_plan"
    )
    original, cells = q.first.executor.proposal.build()
    q.require(len(frozen["groups"]) == 6, "six_groups")
    for group, expected in zip(frozen["groups"], original["groups"][37:43]):
        q.require(group["group"] == expected, "manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == expected["group_id"]],
            "manifest_cells",
        )
    policy = SimpleNamespace(
        protocol="pr86_frozen_groups37_42_v1", plan=lambda _: frozen
    )
    q.require(
        q.validate_return(raw, policy)["ready_for_independent_review"], "incomplete"
    )
    q.require(
        [r["accounting"]["job_id"] for r in value["returns"]]
        == [str(j) for j in range(3592, 3598)],
        "wave37_jobs",
    )
    return value


def review(raw):
    rows, previous = prior.review(q.read(prior.DEST / "public_return.json"))
    wave = review_wave(raw)
    rows += f0.rows_from_returns(
        wave["returns"], {str(j): SHA for j in range(3592, 3598)}
    )
    original, cells = q.first.executor.proposal.build()
    groups = {g["group_id"] for g in original["groups"][:43]}
    expected = {c["cell_id"] for c in cells if c["group_id"] in groups}
    q.require(
        len(rows) == len(expected) == 129 and {r["cell_id"] for r in rows} == expected,
        "prefix129",
    )
    return rows, {
        "protocol_id": "pr86_fortythree_group_descriptive_review_v1",
        "input_return_sha256": previous["input_return_sha256"] + [SHA],
        "completed_cells": 129,
        "completed_groups": 43,
        "remaining_cells": 81,
        "remaining_groups": 27,
        "distinct_historically_exposed_parents": 7,
        "complete_five_cap_parents": ["F0", "F3", "F6", "F14", "F27", "F29"],
        "M0_pending_caps": [2, 4, 8, 16],
        "M0_pending_one_thread_seeds": [43, 44],
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


def medium_quality_figure(rows):
    """Terminal quality at the fixed budget, never a time-to-target curve."""
    q.require(
        len(rows) == 3 and all(r["threads"] == 1 and r["seed"] == 42 for r in rows),
        "medium_figure_scope",
    )
    maximum = max(r["gap_fraction"] * 100 for r in rows) * 1.18
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="460" viewBox="0 0 900 460">',
        '<rect width="900" height="460" fill="white"/>',
        '<g font-family="sans-serif" fill="#182635">',
        '<text x="65" y="28" font-size="20">Instancia M0: calidad al límite de 3.600 s (1 hilo, seed 42)</text>',
        '<text x="65" y="52" font-size="13">Tres tiempos censurados; no se alcanzó el objetivo de brecha del 0,01 %.</text>',
        '<text x="65" y="74" font-size="12">M0/M1/M2 son métodos; M0 en el título es el identificador de la instancia media.</text>',
    ]
    for tick in range(5):
        y = 330 - tick * 50
        parts.append(
            f'<path d="M70 {y}H650" stroke="#dbe2e9"/><text x="12" y="{y + 4}" font-size="12">{maximum * tick / 4:.1f} %</text>'
        )
    for i, (method, color) in enumerate(
        (("M0", "#3457a6"), ("M1", "#b15a10"), ("M2", "#128064"))
    ):
        row = next(r for r in rows if r["method"] == method)
        q.require(row["right_censored"], "medium_censoring")
        x, h = 110 + i * 190, row["gap_fraction"] * 100 / maximum * 200
        parts += [
            f'<rect x="{x}" y="{330 - h:.2f}" width="100" height="{h:.2f}" fill="{color}"/>',
            f'<text x="{x + 12}" y="{320 - h:.2f}" font-size="14">{row["gap_fraction"] * 100:.4f} %</text>',
            f'<text x="{x + 35}" y="352" font-size="14">{method}</text>',
            f'<text x="{x - 12}" y="376" font-size="12">Objetivo: {row["primal"]:.6f}</text>',
            f'<text x="{x - 12}" y="396" font-size="12">Cota dual: {row["dual"]:.6f}</text>',
        ]
    parts += [
        '<text x="685" y="140" font-size="12">Brecha menor:</text>',
        '<text x="685" y="160" font-size="12">mejor certificación.</text>',
        '<text x="685" y="195" font-size="12">Objetivo menor:</text>',
        '<text x="685" y="215" font-size="12">mejor solución (MIN).</text>',
        '<text x="65" y="435" font-size="12">Un grupo expuesto; sin generalización. No confundir menor brecha con mejor incumbente.</text>',
        "</g></svg>",
    ]
    return "\n".join(parts).encode()


def publish(directory):
    rows, summary = review(q.read(DEST / "public_return.json"))
    outputs = {
        "campaign_results.csv": f0.csv_bytes(rows),
        "review.json": q.encoded(summary),
        "f29_cpu.svg": f0.figure([r for r in rows if r["alias"] == "F29"], "F29"),
        "m0_quality_partial.svg": medium_quality_figure(
            [r for r in rows if r["alias"] == "M0"]
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
