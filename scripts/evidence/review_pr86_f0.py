"""Pinned F0 review: seven groups, 21 cells, descriptive CPU curves only."""

import argparse
import base64
import json
from pathlib import Path

import pr86_six_job_queue as q
from review_pr86_installed_bindings import csv_bytes

SHA = "55b5b60e835cde8af5ab11e9735b052c0c53fa13cdd222f912d192eac65c1024"
COMMIT = "1db558bda60f5d6e08a8deb88808cf8c78301406"
PLAN = "a809e745a4944aed77bc6e8cb18527bfbbb4309870fa6bd3d9d7b4b1c934e498"
DEST = q.ROOT / "docs/evidence/pr86/jobs3523-3528"


def review_wave(raw):
    # The source-tree validator passed before edits. Never rebuild old source pins.
    q.require(q.digest(raw) == SHA, "f0_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(
        frozen["source_commit"] == COMMIT and value["plan_sha256"] == PLAN,
        "f0_identity",
    )
    q.require(q.digest(q.encoded(frozen)) == PLAN, "f0_plan_hash")
    original, cells = q.first.executor.proposal.build()
    q.require(len(value["returns"]) == len(value["launch"]) == 6, "six_groups")
    for i, (returned, launch) in enumerate(zip(value["returns"], value["launch"])):
        group = frozen["groups"][i]
        q.require(group["group"] == original["groups"][i + 1], "f0_manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == group["group"]["group_id"]],
            "f0_manifest_cells",
        )
        q.require(
            q.first.validate_return(q.encoded(returned), expected_plan=group),
            "f0_incomplete",
        )
        job = str(3523 + i)
        q.require(returned["accounting"]["job_id"] == launch["job_id"] == job, "f0_job")
        held = launch["held_profile"]
        text = " ".join(k + "=" + v for k, v in held["resources"].items())
        if held["dependency"] is not None:
            text += " Dependency=" + held["dependency"]
        q.require(
            q.profile(
                text, job, group["group"]["threads"], str(3522 + i) if i else None
            )
            == held,
            "f0_launch",
        )
    q.require(
        not value["raw_logs_included"] and not value["scientific_reporting_eligible"],
        "f0_scope",
    )
    return value


def member(returned, name):
    ref = returned["members"][name]
    raw = base64.b64decode(ref["base64"], validate=True)
    q.require(q.digest(raw) == ref["sha256"], "member_hash")
    return json.loads(raw)


def rows_from_returns(returns, receipt_shas):
    """Extract named descriptive metrics after independent nested validation."""
    rows = []
    for returned in returns:
        job = returned["accounting"]["job_id"]
        for i, cell in enumerate(returned["plan"]["cells"]):
            result = member(returned, f"run/attempt-{i}/child.json")["result"]
            solve = result["solve"]
            cost = member(returned, f"run/attempt-{i}/prepared_costs.json")[
                "measurement"
            ]
            supervision = member(returned, f"run/attempt-{i}/supervision.json")[
                "observation"
            ]
            q.require(result["independent_feasibility"]["valid"], "feasibility")
            q.require(result["effective_objective_sense"] == "MINIMIZE", "sense")
            q.require(
                supervision["guard_stop"] is None and not result["callback_errors"],
                "stop",
            )
            rows.append(
                {
                    "parent": cell["parent"],
                    "alias": cell["alias"],
                    "cell_id": cell["cell_id"],
                    "threads": cell["threads"],
                    "seed": cell["seed"],
                    "method": cell["method"],
                    "method_order_position": cell["method_order_position"],
                    "job_id": job,
                    "solver_seconds": solve["solver_runtime_seconds"],
                    "gap_fraction": solve["terminal_mip_gap_relative"],
                    "primal": solve["primal"],
                    "dual": solve["dual"],
                    "right_censored": solve["right_censored"],
                    "start_status": result["start"]["status"],
                    "supervised_attempt_seconds": cost["supervisor_wall_seconds"],
                    "scoped_preparation_seconds": cost["preparation_seconds"],
                    "scoped_cold_cost_scenario_seconds": cost["cold_attempt_seconds"],
                    "scoped_amortized_cost_scenario_seconds": cost[
                        "amortized_attempt_seconds"
                    ],
                    "sampled_cgroup_peak_bytes": supervision[
                        "sampled_cgroup_peak_bytes"
                    ],
                    "receipt_sha256": receipt_shas[job],
                    "child_sha256": returned["members"][f"run/attempt-{i}/child.json"][
                        "sha256"
                    ],
                }
            )
    return rows


def review(raw):
    wave = review_wave(raw)
    original = q.read(q.RECEIPT)
    q.review_first(original)
    returns = [json.loads(original), *wave["returns"]]
    rows = rows_from_returns(
        returns,
        {
            r["accounting"]["job_id"]: q.FIRST_SHA if i == 0 else SHA
            for i, r in enumerate(returns)
        },
    )
    q.require(len(rows) == len({r["cell_id"] for r in rows}) == 21, "twenty_one_cells")
    q.require({r["parent"] for r in rows} == {"CFL_easy_instance_0"}, "one_parent")
    q.require(
        all(not r["right_censored"] and r["gap_fraction"] <= 1e-4 for r in rows),
        "target",
    )
    summary = {
        "protocol_id": "pr86_f0_seven_groups_review_v1",
        "first_return_sha256": q.FIRST_SHA,
        "wave_return_sha256": SHA,
        "completed_cells": 21,
        "completed_groups": 7,
        "independent_parents": 1,
        "remaining_cells": 189,
        "remaining_groups": 63,
        "wave_scheduler_elapsed_sum_seconds": sum(
            r["accounting"]["rows"][0]["ElapsedRaw"] for r in wave["returns"]
        ),
        "all_target_gaps_met": True,
        "optimization_runs_added": 0,
        "qualified_scope": "pinned_F0_descriptive_solver_and_scoped_attempt_observations",
        "population_speedup_claim": False,
        "whole_job_cold_cost_qualified": False,
        "raw_eligibility_flags_unchanged": True,
    }
    return rows, summary


def figure(rows, alias="F0", caps=(1, 2, 4, 8, 16), subtitle=None):
    selected = [r for r in rows if r["seed"] == 42]
    maximum = max(r["solver_seconds"] for r in selected) * 1.12
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="820" height="430" viewBox="0 0 820 430">',
        '<rect width="820" height="430" fill="white"/>',
        '<g font-family="sans-serif" fill="#182635">',
        f'<text x="60" y="28" font-size="20">{alias}: tiempo del solver por límite de hilos (seed 42)</text>',
        '<text x="60" y="52" font-size="12">'
        + (
            subtitle
            or "Un solo padre; observación descriptiva, sin generalización ni coste de preparación."
        )
        + "</text>",
    ]
    for tick in range(5):
        y = 350 - tick * 65
        parts.append(
            f'<path d="M70 {y}H690" stroke="#dbe2e9"/><text x="15" y="{y + 4}" font-size="12">{maximum * tick / 4:.0f} s</text>'
        )
    for method, color in (("M0", "#3457a6"), ("M1", "#b15a10"), ("M2", "#128064")):
        points = []
        for i, cap in enumerate(caps):
            row = next(
                r for r in selected if r["method"] == method and r["threads"] == cap
            )
            x, y = 90 + i * 140, 350 - row["solver_seconds"] / maximum * 260
            points.append(f"{x},{y:.2f}")
            parts.append(f'<circle cx="{x}" cy="{y:.2f}" r="4" fill="{color}"/>')
        parts.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="710" y="{100 + int(method[1]) * 24}" fill="{color}">{method}</text>'
        )
    for i, cap in enumerate(caps):
        parts.append(f'<text x="{86 + i * 140}" y="375">{cap}</text>')
    parts += [
        '<text x="290" y="403">Límite de hilos / núcleos físicos</text>',
        "</g></svg>",
    ]
    return "\n".join(parts).encode()


def publish(directory):
    rows, summary = review(q.read(DEST / "public_return.json"))
    outputs = {
        "f0_results.csv": csv_bytes(rows),
        "review.json": q.encoded(summary),
        "f0_cpu.svg": figure(rows),
    }
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        path = directory / name
        if path.exists():
            q.require(q.read(path) == raw, "preserve_output")
        else:
            with path.open("xb") as stream:
                stream.write(raw)
    manifest = {
        "inputs": [q.FIRST_SHA, SHA],
        "outputs": {k: q.digest(v) for k, v in outputs.items()},
    }
    path = directory / "manifest.json"
    if path.exists():
        q.require(q.parsed(path) == manifest, "manifest_changed")
    else:
        q.write(path, manifest)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.output), indent=2))


if __name__ == "__main__":
    main()
