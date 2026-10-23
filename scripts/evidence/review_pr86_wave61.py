"""Pinned jobs3645..3650: 201 collected cells, not blanket qualification."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pr86_wave61 as previous

q = previous.q
SHA = "4088a2d464ec1d1874b249b7aeed0e720a55bf36e35dfb329d859fb853b709d7"
COMMIT = "34e470752988ec938605ae22dcaab6b4a03b4395"
PLAN = "05685508e7dd657993028fa5948dc1453145f0bb8d3915a9b4eec9c354c2ba17"
DEST = q.ROOT / "docs/evidence/pr86/jobs3645-3650"


def review_wave(raw):
    q.require(q.digest(raw) == SHA, "wave61_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(frozen["source_commit"] == COMMIT, "wave61_source")
    q.require(
        value["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "wave61_plan"
    )
    original, cells = q.first.executor.proposal.build()
    q.require(len(frozen["groups"]) == 6, "six_groups")
    for group, expected in zip(frozen["groups"], original["groups"][61:67]):
        q.require(group["group"] == expected, "manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == expected["group_id"]],
            "manifest_cells",
        )
    q.require(
        frozen["first_review"]
        == previous.predecessor(q.read(previous.reviewed.DEST / "public_return.json")),
        "predecessor_review",
    )
    policy = SimpleNamespace(protocol=previous.POLICY.protocol, plan=lambda _: frozen)
    q.require(
        q.validate_return(raw, policy)["ready_for_independent_review"], "incomplete"
    )
    q.require(
        [r["accounting"]["job_id"] for r in value["returns"]]
        == [str(j) for j in range(3645, 3651)],
        "wave61_jobs",
    )
    return value


def review(raw):
    wave = review_wave(raw)
    rows, old = previous.reviewed.review(
        q.read(previous.reviewed.DEST / "public_return.json")
    )
    added = previous.reviewed.previous.audit.f0.rows_from_returns(
        wave["returns"], {str(j): SHA for j in range(3645, 3651)}
    )
    rows += added
    _, cells = q.first.executor.proposal.build()
    q.require(
        len(rows) == len({r["cell_id"] for r in rows}) == 201
        and {r["cell_id"] for r in rows} == {c["cell_id"] for c in cells[:201]},
        "collected_prefix201",
    )
    prior_wave = previous.reviewed.review_wave(
        q.read(previous.reviewed.DEST / "public_return.json")
    )
    observed = previous.reviewed.screen_records(
        prior_wave
    ) + previous.reviewed.screen_records(wave)
    new_findings = previous.reviewed.previous.audit.cross_run_findings(observed)
    # The previous review already screens all M4 records and retains its limitation.
    findings = old["cross_run_findings"] + [
        f for f in new_findings if f not in old["cross_run_findings"]
    ]
    new_parent_findings = [f for f in findings if not f["bound_cell"].startswith("M4-")]
    for row in rows:
        row["numerical_scope"] = (
            "M4_sensitive_no_optimality_or_speedup_qualification"
            if row["alias"] == "M4"
            else "M12_cross_run_numeric_qualification_pending"
            if row["alias"] == "M12"
            else "scoped_tolerance_and_identity_review_not_exact_certificate"
        )
    return rows, {
        "protocol_id": "pr86_wave61_collected201_scoped_review_v1",
        "input_return_sha256": old["input_return_sha256"] + [SHA],
        "numeric_audit_sha256": old["numeric_audit_sha256"],
        "author_decision": old["author_decision"],
        "completed_cells": 201,
        "completed_groups": 67,
        "remaining_cells": 9,
        "remaining_groups": 3,
        "distinct_historically_exposed_parents": len({r["parent"] for r in rows}),
        "completed_counts_scope": old["completed_counts_scope"],
        "scoped_review_non_M4_cells": 168,
        "new_parent_numeric_qualification_pending_cells": 12,
        "new_parent_numeric_qualification_pending": "CFL_medium_instance_12",
        "numerically_sensitive_cells": 21,
        "numerically_sensitive_parent": old["numerically_sensitive_parent"],
        "wave_scheduler_elapsed_sum_seconds": sum(
            r["accounting"]["rows"][0]["ElapsedRaw"] for r in wave["returns"]
        ),
        "reported_target_met_cells": sum(
            not r["right_censored"] and r["gap_fraction"] <= 1e-4 for r in rows
        ),
        "right_censored_cells": sum(r["right_censored"] for r in rows),
        "new_wave_censored_cells": sum(r["right_censored"] for r in added),
        "new_wave_accepted_starts": sum(r["start_status"] == "accepted" for r in added),
        "cross_run_findings": findings,
        "new_parent_cross_run_findings": new_parent_findings,
        "next_fixed_wave_review_passed": not new_parent_findings,
        "M4_exact_optimality_or_speedup_qualified": False,
        "M12_exact_optimality_or_speedup_qualified": False,
        "whole_job_cold_cost_qualified": False,
        "original_receipts_and_flags_unchanged": True,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
    }


def figure(rows, alias, metric):
    q.require(alias in ("M7", "M12") and metric in ("gap", "memory"), "figure_scope")
    # Reuse the tested renderer, with explicit observed caps and no imputation.
    selected = [r for r in rows if r["alias"] == alias and r["seed"] == 42]
    caps = (1, 2, 4, 8, 16) if alias == "M7" else (1, 2)
    q.require(
        len(selected) == len(caps) * 3
        and {(r["threads"], r["method"]) for r in selected}
        == {(c, m) for c in caps for m in ("M0", "M1", "M2")},
        "figure_cells",
    )
    gap = metric == "gap"
    maximum = (
        max(0.01, max(r["gap_fraction"] * 100 for r in selected) * 1.12) if gap else 64
    )
    title = "brecha final reportada (%)" if gap else "pico de RAM del cgroup (GiB)"
    note = (
        "M7: cinco limites completos; observaciones, no certificados exactos."
        if alias == "M7"
        else "M12: revision numerica pendiente; 4, 8 y 16 hilos sin observar."
    )
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="940" height="470" viewBox="0 0 940 470">',
        '<rect width="940" height="470" fill="white"/>',
        '<g font-family="sans-serif" fill="#182635">',
        f'<text x="55" y="30" font-size="20">Instancia {alias}: {title} (seed 42)</text>',
        f'<text x="55" y="57" font-size="14">{note}</text>',
        '<text x="55" y="80" font-size="12">M0/M1/M2: metodos. Puntos vacios: tiempo hasta objetivo censurado.</text>',
    ]
    for tick in range(5):
        y = 340 - tick * 55
        parts.append(
            f'<path d="M75 {y}H700" stroke="#dbe2e9"/><text x="15" y="{y + 4}" font-size="12">{maximum * tick / 4:.2f}</text>'
        )
    for method, color in (("M0", "#3457a6"), ("M1", "#b15a10"), ("M2", "#128064")):
        points = []
        for cap in caps:
            row = next(
                r for r in selected if r["method"] == method and r["threads"] == cap
            )
            value = (
                row["gap_fraction"] * 100
                if gap
                else row["sampled_cgroup_peak_bytes"] / 2**30
            )
            x, y = 100 + (1, 2, 4, 8, 16).index(cap) * 140, 340 - value / maximum * 220
            points.append(f"{x},{y:.2f}")
            fill = "white" if row["right_censored"] else color
            parts.append(
                f'<circle cx="{x}" cy="{y:.2f}" r="5" fill="{fill}" stroke="{color}" stroke-width="2"/>'
            )
        parts += [
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>',
            f'<text x="745" y="{150 + int(method[1]) * 25}" fill="{color}">{method}</text>',
        ]
    for i, cap in enumerate((1, 2, 4, 8, 16)):
        parts.append(f'<text x="{96 + i * 140}" y="368">{cap}</text>')
    parts += [
        '<text x="260" y="403">Limite de hilos / nucleos fisicos</text>',
        '<text x="55" y="432" font-size="12">Brecha terminal no es tiempo hasta objetivo; RAM muestreada no es Slurm MaxRSS.</text>',
        '<text x="55" y="453" font-size="12">Padres historicamente expuestos; semillas 43/44 disponibles en la tabla.</text>',
        "</g></svg>",
    ]
    return "\n".join(parts).encode()


def publish(directory):
    rows, summary = review(q.read(DEST / "public_return.json"))
    outputs = {
        "campaign_results.csv": previous.reviewed.previous.audit.f0.csv_bytes(rows),
        "review.json": q.encoded(summary),
        **{
            f"{alias.lower()}_{metric}_cpu.svg": figure(rows, alias, metric)
            for alias in ("M7", "M12")
            for metric in ("gap", "memory")
        },
    }
    outputs["manifest.json"] = q.encoded(
        {
            "inputs": summary["input_return_sha256"]
            + [summary["numeric_audit_sha256"]],
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(publish(parser.parse_args().output), indent=2))
