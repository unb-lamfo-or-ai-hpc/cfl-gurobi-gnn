"""Pinned jobs3625..3630; preserve M4 sensitivity in the 183-cell ledger."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pr86_wave55 as previous

q = previous.q
SHA = "2cf7240c097f2b3c850c3b4be58ea4c63390ff98718da41c692f29854238d26a"
COMMIT = "48b22795518201447780667ca725191c481b7f86"
PLAN = "f2c5cb99ff8970f9aef6476e5bf4ad91cae43afc48b711765ed9a9f7fcffb11c"
DEST = q.ROOT / "docs/evidence/pr86/jobs3625-3630"


def review_wave(raw):
    q.require(q.digest(raw) == SHA, "wave55_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(frozen["source_commit"] == COMMIT, "wave55_source")
    q.require(
        value["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "wave55_plan"
    )
    original, cells = q.first.executor.proposal.build()
    q.require(len(frozen["groups"]) == 6, "six_groups")
    for group, expected in zip(frozen["groups"], original["groups"][55:61]):
        q.require(group["group"] == expected, "manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == expected["group_id"]],
            "manifest_cells",
        )
    # Bind the prior review to its pinned receipts, without rebuilding old
    # dependency hashes on the new source tree.
    q.require(
        frozen["first_review"]
        == previous.predecessor(
            q.read(previous.audit.DEST / "public_return.json"),
            q.read(previous.reviewed.DEST / "numeric_audit.json"),
        ),
        "predecessor_review",
    )
    policy = SimpleNamespace(protocol=previous.POLICY.protocol, plan=lambda _: frozen)
    q.require(
        q.validate_return(raw, policy)["ready_for_independent_review"], "incomplete"
    )
    q.require(
        [r["accounting"]["job_id"] for r in value["returns"]]
        == [str(j) for j in range(3625, 3631)],
        "wave55_jobs",
    )
    return value


def screen_records(wave):
    records = []
    for returned in wave["returns"]:
        for i, cell in enumerate(returned["plan"]["cells"]):
            result = previous.audit.f0.member(returned, f"run/attempt-{i}/child.json")[
                "result"
            ]
            records.append(
                {
                    "parent": cell["parent"],
                    "cell_id": cell["cell_id"],
                    "model_sha256": result["mip_sha256"],
                    "mathematical_signature_sha256": result[
                        "mathematical_signature_sha256"
                    ],
                    "model_fingerprint": result["model_fingerprint"],
                    "primal": result["solve"]["primal"],
                    "dual": result["solve"]["dual"],
                }
            )
    return records


def review(raw):
    wave = review_wave(raw)
    rows, old = previous.reviewed.campaign()
    rows += previous.audit.f0.rows_from_returns(
        wave["returns"], {str(j): SHA for j in range(3625, 3631)}
    )
    _, cells = q.first.executor.proposal.build()
    q.require(
        len(rows) == len({r["cell_id"] for r in rows}) == 183
        and {r["cell_id"] for r in rows} == {c["cell_id"] for c in cells[:183]},
        "collected_prefix183",
    )
    observed = screen_records(wave) + previous.audit.records(
        previous.audit.load_wave(q.read(previous.audit.DEST / "public_return.json"))
    )
    findings = previous.audit.cross_run_findings(observed)
    m4_ids = {r["cell_id"] for r in observed if r["parent"] == "CFL_medium_instance_4"}
    new_parent_conflicts = [f for f in findings if f["bound_cell"] not in m4_ids]
    for row in rows:
        row["numerical_scope"] = (
            "M4_sensitive_no_optimality_or_speedup_qualification"
            if row["alias"] == "M4"
            else "scoped_tolerance_and_identity_review_not_exact_certificate"
        )
    return rows, {
        "protocol_id": "pr86_wave55_collected183_scoped_review_v1",
        "input_return_sha256": old["input_return_sha256"] + [SHA],
        "numeric_audit_sha256": old["numeric_audit_sha256"],
        "author_decision": old["author_decision"],
        "completed_cells": 183,
        "completed_groups": 61,
        "remaining_cells": 27,
        "remaining_groups": 9,
        "completed_counts_scope": "structurally_collected_not_blanket_scientific_qualification",
        "scoped_review_non_M4_cells": 162,
        "numerically_sensitive_cells": 21,
        "numerically_sensitive_parent": "CFL_medium_instance_4",
        "wave_scheduler_elapsed_sum_seconds": sum(
            r["accounting"]["rows"][0]["ElapsedRaw"] for r in wave["returns"]
        ),
        "reported_target_met_cells": sum(
            not r["right_censored"] and r["gap_fraction"] <= 1e-4 for r in rows
        ),
        "right_censored_cells": sum(r["right_censored"] for r in rows),
        "cross_run_findings": findings,
        "new_parent_cross_run_findings": new_parent_conflicts,
        "next_fixed_wave_review_passed": not new_parent_conflicts,
        "M4_exact_optimality_or_speedup_qualified": False,
        "whole_job_cold_cost_qualified": False,
        "original_receipts_and_flags_unchanged": True,
        "scientific_reporting_eligible": False,
        "optimization_runs_added": 0,
    }


def figure(rows, alias, metric):
    q.require(alias in ("M4", "M7") and metric in ("gap", "memory"), "figure_scope")
    selected = [r for r in rows if r["alias"] == alias and r["seed"] == 42]
    caps = (1, 2, 4, 8, 16) if alias == "M4" else (1, 2, 4)
    q.require(len(selected) == len(caps) * 3, "figure_cells")
    gap = metric == "gap"
    maximum = max(r["gap_fraction"] * 100 for r in selected) * 1.12 if gap else 64
    maximum = max(maximum, 0.01)
    title = "brecha final reportada (%)" if gap else "pico de RAM del cgroup (GiB)"
    warning = (
        "M4: sensibilidad numerica; no certifica optimo ni aceleracion."
        if alias == "M4"
        else "M7 parcial: 8 y 16 hilos pendientes; sin interpolacion."
    )
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="940" height="470" viewBox="0 0 940 470">',
        '<rect width="940" height="470" fill="white"/>',
        '<g font-family="sans-serif" fill="#182635">',
        f'<text x="55" y="30" font-size="20">Instancia {alias}: {title} (seed 42)</text>',
        f'<text x="55" y="57" font-size="14">{warning}</text>',
        '<text x="55" y="80" font-size="12">M0/M1/M2 son metodos. Puntos vacios: observaciones, no certificados.</text>',
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
            parts.append(
                f'<circle cx="{x}" cy="{y:.2f}" r="5" fill="white" stroke="{color}" stroke-width="2"/>'
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
        "campaign_results.csv": previous.audit.f0.csv_bytes(rows),
        "review.json": q.encoded(summary),
        **{
            f"{alias.lower()}_{metric}_cpu.svg": figure(rows, alias, metric)
            for alias in ("M4", "M7")
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
