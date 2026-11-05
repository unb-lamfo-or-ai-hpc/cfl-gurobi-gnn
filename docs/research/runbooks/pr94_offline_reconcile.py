"""Reconcile the two sealed PR94 exports without a solver or scheduler.

Use the reviewed source tree at 81c829b66f6d, the original ZIPs, and an output
directory. Only the derived, allowlisted CSV and summary are for publication.
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import sys
import zipfile

SOURCE = "81c829b66f6dacf703da388e34501d9df0980f45"
PLAN = "92ac169c5ccb69962628dc0b91aab6afff183538da87f14e3ebf080b8cfe53fb"
TERMINAL = "99ba525f7977389342c2a09b58c363464c4e33b22e9ed565c1746097e4718dc0"
INSTALL = "703609030229554ba663242fdc183d788d43a7555ba35b0270357dc84e0a977d"
MATRIX = "7642f93d24215178c1433ccc604f7e0fa8823163288938d460de38c9584528cd"
METHOD = {"M0": "B", "M1": "R", "M2": "G"}
TARGETS = {"10": "0.1", "5": "0.05", "1": "0.01", "001": "0.0001"}
RESTRICTED = {"M4", "M12"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def load_archive(path, expected_hash, expected_size, name):
    raw = path.read_bytes()
    require(len(raw) == expected_size and sha(raw) == expected_hash, f"ZIP identity: {name}")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(sorted(archive.namelist()) == sorted([name, "manifest.json"]), f"ZIP members: {name}")
        require(archive.testzip() is None, f"ZIP CRC: {name}")
        member = archive.read(name)
        manifest = json.loads(archive.read("manifest.json"))
        require(manifest == {"sha256": {name: sha(member)}}, f"ZIP manifest: {name}")
    return json.loads(member), sha(member)


def exact_seal(seals, path, value):
    raw = encoded(value)
    require(seals[path] == {"sha256": sha(raw), "bytes": len(raw)}, f"artifact seal: {path}")


def reconcile(policy, returned, install):
    from pr86_supervised_costs import reconcile as reconcile_cost

    for record in (returned, install):
        require(record["source_commit"] == SOURCE and record["plan_sha256"] == PLAN, "installed identities")
        require(record["scientific_reporting_eligible"] is False, "original scope flag")
    require(install["bindings"] == returned["parent_bindings"] and len(install["bindings"]) == 16, "16 matched bindings")
    require(install["private_model_and_artifact_chains_verified"] == 16 and
            all(install[k] == 0 for k in ("optimization_calls", "forward_calls", "training_calls", "submissions")),
            "zero-call installation")
    validation = install["recovery_validation"]
    require(validation["FAILED"] == 4 and validation["CANCELLED"] == 44
            and validation["original_bytes_unchanged"] is True
            and validation["worker_evidence_absent"] is True, "preserved original attempt")
    require(returned["protocol_id"] == policy.PROTOCOL and returned["complete_campaign_accounting"] is True
            and returned["terminal_groups_collected"] == 48 and returned["expected"] == returned["received"] == 144
            and returned["raw_unqualified_reports"] == returned["invalid_record_count"] == 0, "complete collection")
    account = returned["accounting"]
    require(account["recorded_jobs"] == 48 and account["root_jobs_terminal"] is True
            and account["submission_complete"] is True and account["unconfirmed_submission_intents"] == 0
            and not account["missing_steps"], "accounting closure")
    expected_ids = {str(j) + suffix for j in range(3833, 3881) for suffix in ("", ".batch", ".extern")}
    accounting = {a["JobIDRaw"]: a for a in account["rows"]}
    require(len(account["rows"]) == len(expected_ids) and set(accounting) == expected_ids and
            all(a["State"] == "COMPLETED" and a["ExitCode"] == "0:0" for a in accounting.values()),
            "terminal Slurm IDs and steps")
    matrix, cells = policy.matrix()
    positions = {c: (i, order) for i, g in enumerate(matrix["groups"]) for order, c in enumerate(g["cells"], 1)}
    require(len(positions) == 144 and set(positions) == set(cells), "planned groups")
    actual = {row["cell"]["cell_id"]: row for row in returned["cells"]}
    require(len(returned["cells"]) == 144 and set(actual) == set(cells), "unique planned cells")
    seals = returned["closed_artifact_seals"]
    require(len(seals) == 1248, "closed artifact inventory")
    intents = {item["cell_id"]: item["sha256"] for item in returned["durable_optimize_intents"]}
    require(len(returned["durable_optimize_intents"]) == 144 and set(intents) == set(cells), "unique durable intents")
    rows = []
    for identity, cell in cells.items():
        row = actual[identity]
        require(row["cell"] == cell and row["received"] is True and row["group_accounting_closed"] is True
                and row["raw_unqualified_value"] is None and not row["invalid_records"], identity)
        value = row["value"]
        result = value["result"]
        binding = install["bindings"][cell["parent"]]
        policy.validate_result(cell, result, binding)
        require(result["parameters"] == policy.parameters(cell), f"full parameter map: {identity}")
        param_bytes = encoded(result["parameters"]).rstrip(b"\n")
        require(result["parameter_sha256"] == sha(param_bytes), f"parameter SHA: {identity}")
        require(value["cell"] == cell and value["plan_sha256"] == PLAN
                and value["frozen_Start_abstained"] == (cell["method"] != "M0" and binding["abstained"]), identity)
        require(intents[identity] == sha(encoded({"cell_id": identity, "maximum_calls": 1, "plan_sha256": PLAN})),
                f"intent seal: {identity}")
        folder = "run/" + identity
        supervision = row["supervision.json"]
        costs = row["costs.json"]
        for name, item in (("child.json", value), ("raw-result.json", value),
                           ("supervision.json", supervision), ("costs.json", costs)):
            exact_seal(seals, f"{folder}/{name}", item)
        require(supervision["child_exit_code"] == 0
                and all(supervision[k] is None for k in ("guard_stop", "affinity_failure", "storage_failure", "memory_failure_diagnostic"))
                and costs["complete_attempt"] is True, f"supervised completion: {identity}")
        require(costs == reconcile_cost(supervision, result, cell["method"], uses=3), f"supervision cost: {identity}")
        index, order = positions[identity]
        job = str(3833 + index)
        exact_seal(seals, f"{folder}/started.json", {"cell_id": identity, "job_id": job, "plan_sha256": PLAN})
        solution = result["solution_artifact"]
        require(solution["file_name"] == "solution.private.json.gz"
                and solution["sha256"] == seals[f"{folder}/solution.private.json.gz"]["sha256"], f"vector seal: {identity}")
        solve = result["solve"]
        audit = result["independent_feasibility"]
        require(audit["valid"] is True and all(audit["checks"].values())
                and solve["feasible_solution"] is True and solve["solve_status_code"] in (2, 9),
                f"terminal solver and feasibility: {identity}")
        require((solve["solve_status_code"] == 9) == solve["right_censored"], f"terminal censor flag: {identity}")
        temporal = result["temporal_evidence"]
        require(temporal["analysis_horizons_seconds"] == [3600] and
                temporal["later_horizons_are_outside_evaluation_budget"] is True, f"analysis horizon: {identity}")
        horizon = temporal["horizons"]["3600"]
        point = horizon["before"]
        require(point is not None and point["primal"] is not None and point["dual"] is not None
                and point["seconds"] <= 3600, f"one-hour outcome: {identity}")
        terminal = temporal["terminal"]
        require(terminal["primal"] == solve["primal"] and terminal["dual"] == solve["dual"]
                and terminal["gap_fraction"] == solve["common_mip_gap_relative"], f"terminal outcome: {identity}")
        inst = identity.split("--", 1)[1].split("-", 1)[0]
        method = METHOD[cell["method"]]
        clean = {
            "cell_id": identity, "job_id": job, "order": order, "instance": inst,
            "cohort": "easy" if inst.startswith("F") else "medium", "method": method,
            "seed": cell["seed"], "model_sha256": cell["model_sha256"],
            "parameter_sha256": result["parameter_sha256"],
            "start_sha256": result["start"]["assignment_sha256"],
            "start_status": result["start"]["status"],
            "numerical_scope": "descriptive_only" if inst in RESTRICTED else "reported_within_tolerances",
            "solver_status": "target_status" if solve["solve_status_code"] == 2 else "time_limit",
            "solver_runtime_s": solve["solver_runtime_seconds"], "supervised_attempt_s": costs["supervisor_wall_seconds"],
            "preparation_costs_qualified": costs["preparation_costs_qualified"],
            "observation_1h_s": point["seconds"], "primal_1h": point["primal"], "dual_1h": point["dual"],
            "gap_1h_fraction": point["gap_fraction"], "terminal_primal": terminal["primal"],
            "terminal_dual": terminal["dual"], "terminal_gap_fraction": terminal["gap_fraction"],
            "terminal_integrality_residual": audit["max_integrality_residual"],
            "terminal_row_residual": audit["max_row_residual"],
            "terminal_bound_residual": audit["max_bound_residual"],
        }
        for label, threshold in TARGETS.items():
            hit = temporal["first_observed_thresholds"][threshold]["crossing"]
            t = None if hit is None else hit["first_observed"]["seconds"]
            clean[f"target_{label}_s"] = t if t is not None and t <= 3600 else None
            clean[f"target_{label}_status"] = "observed" if clean[f"target_{label}_s"] is not None else "right_censored"
            clean[f"target_{label}_followup_s"] = (clean[f"target_{label}_s"]
                                                   if clean[f"target_{label}_s"] is not None else min(3600, terminal["seconds"]))
        rows.append(clean)
    return rows, accounting


def paired_summary(rows, left, right, target):
    field = f"target_{target}_s"
    lookup = {(r["instance"], r["seed"], r["method"]): r for r in rows}
    comparisons = []
    for a in rows:
        if a["method"] != left:
            continue
        b = lookup[a["instance"], a["seed"], right]
        time_a, time_b = a[field], b[field]
        comparisons.append({
            "instance": a["instance"], "seed": a["seed"],
            "left_hit": time_a is not None, "right_hit": time_b is not None,
            "time_ratio": time_b / time_a if time_a and time_b and a["instance"] not in RESTRICTED else None,
            "relative_primal_percent": 100 * (b["primal_1h"] - a["primal_1h"]) / abs(a["primal_1h"]),
            "relative_dual_percent": 100 * (b["dual_1h"] - a["dual_1h"]) / abs(a["dual_1h"]),
            "gap_difference_pp": 100 * (b["gap_1h_fraction"] - a["gap_1h_fraction"]),
            "attempt_ratio": b["supervised_attempt_s"] / a["supervised_attempt_s"],
        })
    result = {"pairs": len(comparisons), "target_percent": 0.01 if target == "001" else int(target)}
    for a, b, key in ((True, True, "both_hit"), (True, False, "left_only"),
                      (False, True, "right_only"), (False, False, "neither_hit")):
        result[key] = sum(c["left_hit"] == a and c["right_hit"] == b for c in comparisons)
    ratios = [c["time_ratio"] for c in comparisons if c["time_ratio"] is not None]
    result["time_ratio_pairs"] = len(ratios)
    result["paired_time_geomean_ratio"] = statistics.geometric_mean(ratios) if ratios else None
    result["paired_time_faster"] = sum(x < 1 for x in ratios)
    result["paired_time_slower"] = sum(x > 1 for x in ratios)
    result["per_instance"] = {}
    metrics = ("relative_primal_percent", "relative_dual_percent", "gap_difference_pp", "attempt_ratio", "time_ratio")
    for inst in sorted({c["instance"] for c in comparisons}):
        group = [c for c in comparisons if c["instance"] == inst]
        result["per_instance"][inst] = {
            metric: statistics.median(values) if (values := [c[metric] for c in group if c[metric] is not None]) else None
            for metric in metrics
        }
    for metric in metrics:
        values = [x[metric] for x in result["per_instance"].values() if x[metric] is not None]
        result[f"median_instance_{metric}"] = statistics.median(values) if values else None
        if metric in ("relative_primal_percent", "relative_dual_percent", "gap_difference_pp"):
            result[f"negative_instance_{metric}"] = sum(x < -1e-9 for x in values)
            result[f"positive_instance_{metric}"] = sum(x > 1e-9 for x in values)
    return result


def summarize(rows, accounting):
    summary = {"cells": len(rows), "blocks": 48, "targets": {}, "contrasts": {}, "instances": {}}
    for scope in ("easy", "medium", "medium_sensitivity"):
        subset = [r for r in rows if r["cohort"] == ("easy" if scope == "easy" else "medium")
                  and (scope != "medium_sensitivity" or r["instance"] not in RESTRICTED)]
        summary["targets"][scope] = {}
        for m in METHOD.values():
            group = [r for r in subset if r["method"] == m]
            summary["targets"][scope][m] = {
                "n": len(group),
                "time_limit": sum(r["solver_status"] == "time_limit" for r in group),
                "hits": {label: sum(r[f"target_{label}_s"] is not None for r in group) for label in TARGETS},
                "start_accepted": sum(r["start_status"] == "accepted" for r in group),
                "solver_hours": sum(r["solver_runtime_s"] for r in group) / 3600,
                "supervised_hours": sum(r["supervised_attempt_s"] for r in group) / 3600,
            }
        comparisons = (("B", "R"), ("B", "G"), ("R", "G"))
        summary["contrasts"][scope] = {
            target: {f"{right}/{left}": paired_summary(subset, left, right, target)
                     for left, right in comparisons}
            for target in ("10", "001")
        }
    for instance in sorted({r["instance"] for r in rows}):
        summary["instances"][instance] = {}
        for method in METHOD.values():
            group = [r for r in rows if r["instance"] == instance and r["method"] == method]
            summary["instances"][instance][method] = {
                "hits_001": sum(r["target_001_s"] is not None for r in group),
                "hits_10": sum(r["target_10_s"] is not None for r in group),
                "median_primal": statistics.median(r["primal_1h"] for r in group),
                "median_dual": statistics.median(r["dual_1h"] for r in group),
                "median_gap_percent": 100 * statistics.median(r["gap_1h_fraction"] for r in group),
                "median_target_001_s": statistics.median(hits) if (hits := [r["target_001_s"] for r in group if r["target_001_s"] is not None]) else None,
            }
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["instance"], r["seed"]].append(r)
    summary["cross_bound_flags"] = {}
    for horizon, primal, dual in (("one_hour", "primal_1h", "dual_1h"),
                                  ("terminal", "terminal_primal", "terminal_dual")):
        flags = []
        for (inst, seed), group in groups.items():
            low_primal = min(group, key=lambda r: r[primal])
            high_dual = max(group, key=lambda r: r[dual])
            excess = high_dual[dual] - low_primal[primal]
            if excess > 1e-9:
                flags.append({"instance": inst, "seed": seed, "excess": excess,
                              "high_dual": high_dual[dual], "dual_method": high_dual["method"],
                              "low_primal": low_primal[primal], "primal_method": low_primal["method"]})
        summary["cross_bound_flags"][horizon] = flags
    job_rows = [r for j, r in accounting.items() if "." not in j]
    events = [(dt.datetime.fromisoformat(r[k]), delta) for r in job_rows for k, delta in (("Start", 1), ("End", -1))]
    active = peak = 0
    for _, delta in sorted(events):
        active += delta
        peak = max(peak, active)
    summary["resources"] = {
        "summed_job_hours": sum(int(r["ElapsedRaw"]) for r in job_rows) / 3600,
        "allocated_logical_cpu_hours": sum(int(r["ElapsedRaw"]) * int(r["AllocCPUS"]) for r in job_rows) / 3600,
        "solver_hours": sum(r["solver_runtime_s"] for r in rows) / 3600,
        "supervised_hours": sum(r["supervised_attempt_s"] for r in rows) / 3600,
        "peak_concurrent_jobs": peak,
        "campaign_span_hours_excluding_prelaunch": (max(t for t, _ in events) - min(t for t, _ in events)).total_seconds() / 3600,
        "guided_preparation_qualified": sum(r["preparation_costs_qualified"] for r in rows if r["method"] != "B"),
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--terminal", type=Path, required=True)
    parser.add_argument("--installation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source / "scripts/evidence"))
    import pr94_evaluation_contract as policy

    require(sha((policy.PACKAGE / "plan.json").read_bytes()) == MATRIX, "public matrix identity")
    returned, member_sha = load_archive(args.terminal, TERMINAL, 396640, "evaluation-public-return.json")
    install, install_member_sha = load_archive(args.installation, INSTALL, 7496, "installation-review.json")
    rows, accounting = reconcile(policy, returned, install)
    summary = summarize(rows, accounting)
    summary["provenance"] = {
        "source_commit": SOURCE, "installed_plan_sha256": PLAN, "matrix_sha256": MATRIX,
        "terminal_zip_sha256": TERMINAL, "terminal_member_sha256": member_sha,
        "installation_zip_sha256": INSTALL, "installation_member_sha256": install_member_sha,
        "accounting_query_utc": returned["accounting"]["query_utc"],
        "terminal_archive_cells": len(rows), "closed_artifact_seals": len(returned["closed_artifact_seals"]),
        "scope": "Metadata audit and scoped solver-reported comparisons. Private vectors, logs and original models not replayed.",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "cells.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "summary.json").write_bytes(encoded(summary))


if __name__ == "__main__":
    main()
