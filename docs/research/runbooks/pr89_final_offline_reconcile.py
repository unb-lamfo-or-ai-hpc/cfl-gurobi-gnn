"""Read-only reconciliation of a sealed PR89 partial export. No solver/HPC imports."""

import argparse
import ast, collections, csv, datetime as dt, hashlib, io, json, math, statistics, types, zipfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--work-dir", type=Path, required=True)
parser.add_argument("--tail", type=Path, required=True)
parser.add_argument("--baseline", type=Path, required=True)
parser.add_argument("--delta", type=Path, required=True)
parser.add_argument("--previous-public", type=Path, required=True)
parser.add_argument("--reference-dir", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--exact-audit", type=Path, action="append", default=[])
args = parser.parse_args()
BASE = args.work_dir
ZIP = args.tail
EXPECTED = "12b07fce5b49dd7540bd5cd26be2a54cfad2cfccc5b42999373da5d7ae29f85f"
HEAD = "9ab7823c6886d19e9ec865141a1cd35b3c3c16e5"


def require(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(v):
    return (json.dumps(v, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def canonical(v):
    return sha(
        json.dumps(
            v, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    )


def load_arithmetic(filename, env):
    raw = (args.reference_dir / filename).read_text(encoding="utf-8")
    tree = ast.parse(raw)
    # Execute only the reviewed arithmetic functions/constants, never imports or CLI.
    body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))]
    exec(compile(ast.Module(body=body, type_ignores=[]), filename, "exec"), env)
    return env, sha(raw.encode())


costs, hash_costs = load_arithmetic("pr86_cost_accounting.py", {"math": math})
supervised, hash_supervised = load_arithmetic(
    "pr86_supervised_costs.py", {"math": math, "costs": types.SimpleNamespace(**costs)}
)
temporal, hash_temporal = load_arithmetic(
    "pr89_cpu_temporal.py", {"math": math, "require": require}
)
raw = ZIP.read_bytes()
require(sha(raw) == EXPECTED, "ZIP_SHA")
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    infos = z.infolist()
    names = [v.filename for v in infos]
    require(len(names) == len(set(names)), "DUPLICATE_MEMBERS")
    require(
        all(not n.startswith(("/", "\\")) and ".." not in Path(n).parts for n in names),
        "UNSAFE_MEMBER",
    )
    require(z.testzip() is None, "ZIP_CRC")
    members = {n: z.read(n) for n in names}
manifest = json.loads(members["tail-manifest.json"])
require(set(members) == set(manifest["sha256"]) | {"tail-manifest.json"}, "MEMBER_SET")
for n, digest in manifest["sha256"].items():
    require(sha(members[n]) == digest, "MEMBER_SHA:" + n)
plan = json.loads(members["plan.json"])
auth = json.loads(members["authorization.json"])
preflight = json.loads(members["preflight.json"])
plan_sha = sha(members["plan.json"])
for ref, digest in {
    "pr86_cost_accounting.py": hash_costs,
    "pr86_supervised_costs.py": hash_supervised,
    "pr89_cpu_temporal.py": hash_temporal,
}.items():
    require(
        plan["source_sha256_lf"]["scripts/evidence/" + ref] == digest,
        "REFERENCE_SOURCE_SEAL:" + ref,
    )
require(
    plan_sha == "48fca37e2cc698f4d35e4850fdd48d8115b36d7f64b97438ded3b9e17dea3dd1",
    "PLAN_SHA",
)
require(
    sha(members["preflight.json"])
    == "b31d5ac2e80a3ae76c3904e197851ce8b42c1bbc92a955212dc277c4cbb252c0",
    "PREFLIGHT_SHA",
)
require(sha(encoded(plan)) == plan_sha, "PLAN_CANONICAL_BYTES")
require(plan["source_commit"] == HEAD and len(plan["cells"]) == 60, "PLAN_SCOPE")
require(
    auth["source_commit"] == HEAD
    and auth["plan_sha256"] == plan_sha
    and auth["explicit_user_authorization"] is True,
    "AUTH_BINDING",
)
require(
    auth["budget"] == plan["budget"]
    and auth["author_decision_sha256"] == plan["author_decision_sha256"]
    and auth["automatic_retry"] is False,
    "AUTH_SCOPE",
)
require(
    preflight["plan_sha256"] == plan_sha and preflight["source_commit"] == HEAD,
    "PREFLIGHT_BINDING",
)
require(
    manifest["scientific_reporting_eligible"] is False
    and manifest["final_campaign_return"] is False,
    "PARTIAL_SCOPE",
)
mapping = json.loads(members["job-cell-map.json"])
snapshot = json.loads(members["scheduler-snapshot.json"])
require(
    [x["job_id"] for x in mapping] == [str(j) for j in range(3675, 3735)], "JOB_SET"
)
require([x["index"] for x in mapping] == list(range(60)), "INDEX_SET")
require([x["cell"] for x in mapping] == plan["cells"], "CELL_MAP")
states = {x["job_id"]: x for x in snapshot["jobs"]}
require(len(states) == 60, "ACCOUNTING_SET")
for i, cell in enumerate(plan["cells"]):
    require(
        cell["parent"] in plan["parents"]
        and cell["seed"] == 42
        and cell["time_limit_seconds"] == 43200
        and cell["threads"] in (1, 2, 4, 8, 16),
        "CELL_PROTOCOL",
    )
require(
    len({(c["parent"], c["threads"], c["method"]) for c in plan["cells"]}) == 60,
    "MATRIX",
)
expected_parameters = {
    "Cuts": -1,
    "FeasibilityTol": 1e-6,
    "Heuristics": 0.05,
    "IntFeasTol": 1e-5,
    "MIPFocus": 0,
    "MIPGap": 0.0001,
    "MIPGapAbs": 1e-10,
    "Method": -1,
    "Presolve": -1,
    "Seed": 42,
    "SoftMemLimit": 48.0,
    "StartNodeLimit": -1,
    "SubMIPNodes": 500,
    "Threads": None,
    "TimeLimit": 43200.0,
}
flat = []
threshold_rows = []
horizon_rows = []
objects = {}
signature = collections.defaultdict(set)
for item in mapping:
    i, job, cell = item["index"], item["job_id"], item["cell"]
    if job not in manifest["collected_job_ids"]:
        continue
    folder = f"runs/{i}/"
    sub, child, supervision, checked, cost = [
        json.loads(members[folder + n])
        for n in (
            "submission.json",
            "child.json",
            "supervision.json",
            "checked.json",
            "costs.json",
        )
    ]
    state = states[job]
    roots = [r for r in state["rows"] if r["JobID"] == job]
    require(len(roots) == 1, "ROOT_ACCOUNTING")
    scheduler = roots[0]
    require(
        state["state"] == scheduler["State"] == "COMPLETED"
        and scheduler["ExitCode"] == "0:0",
        "JOB_SUCCESS",
    )
    require(
        sub == {"index": i, "job_id": job, "plan_sha256": plan_sha}, "SUBMISSION_SEAL"
    )
    require(child["cell"] == cell and child["plan_sha256"] == plan_sha, "CHILD_BINDING")
    require(
        checked
        == {
            "child_sha256": sha(members[folder + "child.json"]),
            "costs_sha256": sha(members[folder + "costs.json"]),
            "supervision_sha256": sha(members[folder + "supervision.json"]),
            "complete": True,
            "index": i,
            "plan_sha256": plan_sha,
            "scientific_reporting_eligible": False,
        },
        "NESTED_SEALS",
    )
    require(
        supervision["job_id"] == job
        and supervision["observation"]["guard_stop"] is None
        and supervision["observation"]["child_exit_code"] == 0,
        "SUPERVISION",
    )
    r = child["result"]
    s = r["solve"]
    obs = r["temporal_evidence"]
    require(
        r["method"] == cell["method"]
        and r["mip_sha256"] == cell["model_sha256"]
        and r["solver_version"] == [13, 0, 1],
        "RESULT_IDENTITY",
    )
    require(
        r["optimization_calls"] == 1
        and r["gate_status"] == "passed"
        and not r["callback_errors"]
        and r["scientific_reporting_eligible"] is False,
        "RESULT_GATES",
    )
    require(
        r["fresh_model"] is True
        and r["mathematical_model_unchanged"] is True
        and r["effective_objective_sense"]
        == cell["effective_objective_sense"]
        == "MINIMIZE",
        "MODEL",
    )
    require(
        r["parameters"] == {**expected_parameters, "Threads": cell["threads"]},
        "PARAMETERS",
    )
    require(r["parameter_sha256"] == canonical(r["parameters"]), "PARAMETER_HASH")
    require(
        r["python_version"] == plan["parents"][cell["parent"]]["environment"]["python"],
        "PYTHON_VERSION",
    )
    signature[cell["alias"]].add(
        (r["mip_sha256"], r["mathematical_signature_sha256"], r["model_fingerprint"])
    )
    feas = r["independent_feasibility"]
    require(
        s["feasible_solution"] is True
        and feas["valid"] is True
        and all(feas["checks"].values()),
        "FEASIBILITY_REPORT",
    )
    require(
        math.isclose(
            feas["recomputed_objective"], s["primal"], rel_tol=1e-12, abs_tol=1e-12
        ),
        "RECOMPUTED_OBJECTIVE",
    )
    require(
        feas["max_bound_residual"] <= feas["feasibility_tolerance"]
        and feas["max_row_residual"] <= feas["feasibility_tolerance"]
        and feas["max_integrality_residual"] <= feas["integrality_tolerance"],
        "RESIDUALS",
    )
    start = r["start"]
    binding = plan["parents"][cell["parent"]]["start_binding"]
    if cell["method"] == "M0":
        require(
            start["submitted_assignments"] == 0 and start["status"] == "not_submitted",
            "BASELINE_START",
        )
    else:
        require(
            start["assignment_sha256"] == binding[cell["method"] + "_assignment_sha256"]
            and start["submitted_assignments"] == binding["selected_support"]
            and start["positive_assignments"] == binding["positive_assignments"],
            "START_BINDING",
        )
        require(
            cell["checkpoint_sha256"]
            == "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028",
            "CHECKPOINT",
        )
    require(s["solve_status_code"] in (2, 9), "EXPECTED_STOP")
    require(s["right_censored"] == (s["solve_status_code"] == 9), "TERMINAL_CENSOR")
    gap = abs(s["primal"] - s["dual"]) / abs(s["primal"])
    require(
        math.isclose(gap, s["common_mip_gap_relative"], rel_tol=1e-10, abs_tol=1e-14),
        "COMMON_GAP",
    )
    if s["solve_status_code"] == 2:
        require(gap <= 0.0001 + 1e-14, "TARGET_GAP")
    temporal["validate"](obs)
    require(
        obs["terminal"]["primal"] == s["primal"]
        and obs["terminal"]["dual"] == s["dual"],
        "TERMINAL_PARITY",
    )
    measurement = supervised["reconcile"](
        supervision["observation"],
        r,
        cell["method"],
        preparation=plan["parents"][cell["parent"]]["preparation_seconds"],
        uses=5,
    )
    require(
        cost
        == {
            "measurement": measurement,
            "scenario": "PR86_observed_preparation_allocated_over_five_new_caps_not_new_cold_measurement",
            "whole_job_end_to_end_qualified": False,
        },
        "COST_RECONCILIATION",
    )
    trajectory = r["trajectory"]
    require(
        all(
            trajectory[k]["seconds"] <= trajectory[k + 1]["seconds"]
            for k in range(len(trajectory) - 1)
        ),
        "TRAJECTORY_ORDER",
    )
    require(
        trajectory[-1]["event"] == "terminal"
        and trajectory[-1]["primal"] == s["primal"]
        and trajectory[-1]["dual"] == s["dual"],
        "TRAJECTORY_TERMINAL",
    )
    for key, value in obs["first_observed_thresholds"].items():
        crossing = value["crossing"]
        threshold_rows.append(
            {
                "job_id": job,
                "alias": cell["alias"],
                "threads": cell["threads"],
                "method": cell["method"],
                "threshold": float(key),
                "state": value["state"],
                "observed_seconds": None
                if crossing is None
                else crossing["first_observed"]["seconds"],
                "previous_seconds": None
                if crossing is None or crossing["previous_observation"] is None
                else crossing["previous_observation"]["seconds"],
                "followup_seconds": value["followup_seconds"],
                "numerically_sensitive": cell["alias"] in ("M4", "M12"),
            }
        )
    for key, value in obs["horizons"].items():

        def field(p, k):
            return None if p is None else p[k]

        horizon_rows.append(
            {
                "job_id": job,
                "alias": cell["alias"],
                "threads": cell["threads"],
                "method": cell["method"],
                "horizon": int(key),
                "state": value["state"],
                "before_seconds": field(value["before"], "seconds"),
                "before_gap": field(value["before"], "gap_fraction"),
                "before_primal": field(value["before"], "primal"),
                "before_dual": field(value["before"], "dual"),
                "after_seconds": field(value["after"], "seconds"),
                "after_gap": field(value["after"], "gap_fraction"),
                "staleness_seconds": value["staleness_seconds"],
            }
        )
    batch = next((x for x in state["rows"] if x["JobID"] == job + ".batch"), {})
    f = {
        "index": i,
        "job_id": job,
        "parent": cell["parent"],
        "alias": cell["alias"],
        "threads": cell["threads"],
        "method": cell["method"],
        "presentation": {"M0": "B", "M1": "R", "M2": "G"}[cell["method"]],
        "scheduler_state": state["state"],
        "status": s["solve_status_code"],
        "right_censored": s["right_censored"],
        "runtime_seconds": s["solver_runtime_seconds"],
        "primal": s["primal"],
        "dual": s["dual"],
        "gap_fraction": gap,
        "node_count": s["node_count"],
        "first_feasible_seconds": s["first_observed_feasible_seconds"],
        "independent_feasibility_reported": feas["valid"],
        "start_status": start["status"],
        "slurm_elapsed_seconds": int(scheduler["ElapsedRaw"]),
        "slurm_total_cpu": scheduler["TotalCPU"],
        "allocated_logical_cpus": int(scheduler["AllocCPUS"]),
        "batch_max_rss": batch.get("MaxRSS"),
        "supervised_seconds": measurement["supervisor_wall_seconds"],
        "preparation_seconds": measurement["preparation_seconds"],
        "cold_scenario_seconds": measurement["cold_attempt_seconds"],
        "amortized5_scenario_seconds": measurement["amortized_attempt_seconds"],
        "optimize_wall_seconds": r["timing"]["model_optimize_wall_time_seconds"],
        "model_build_seconds": r["timing"]["model_build_wall_time_seconds"],
        "audit_seconds": r["timing"]["independent_audit_wall_time_seconds"],
        "slurm_minus_solver_seconds": int(scheduler["ElapsedRaw"])
        - s["solver_runtime_seconds"],
        "sampled_cgroup_peak_bytes": supervision["observation"][
            "sampled_cgroup_peak_bytes"
        ],
        "numerically_sensitive": cell["alias"] in ("M4", "M12"),
        "scientific_reporting_eligible": False,
    }
    flat.append(f)
    objects[job] = {"child": child, "costs": cost, "supervision": supervision}
require(
    len(flat) == manifest["terminal_jobs"] == 6 and not manifest["missing_files"],
    "COLLECTION_COUNT",
)
require(all(len(v) == 1 for v in signature.values()), "PAIRED_MODEL_SIGNATURE")
require(
    {f["job_id"] for f in flat} == set(manifest["collected_job_ids"]), "COLLECTION_IDS"
)


# Extend the sealed54-cell review; old scientific audits are not repeated.
old_dir = args.previous_public
old_manifest_raw = (old_dir / "manifest.json").read_bytes()
require(
    sha(old_manifest_raw)
    == "67916124db1d6b422cfc5a01399863b9de7e430902e9a6e4521bfac041b7d6fb",
    "PREVIOUS_REVIEW_SEAL",
)
old_manifest = json.loads(old_manifest_raw)
for name, digest in old_manifest["files"].items():
    require(
        sha((old_dir / name).read_bytes()) == digest, "PREVIOUS_REVIEW_FILE:" + name
    )
for archive_name, expected_zip in [
    (args.baseline, "111ca062008ff92896a22c8266050ba544f7ad5fb5c048c1d1b0a4539038d0ab"),
    (args.delta, "a43ed259666bf3f29306891192c061a54db157bd314561c23641aecd2066bae9"),
]:
    require(sha(archive_name.read_bytes()) == expected_zip, "PRIOR_ARCHIVE_SEAL")
    with zipfile.ZipFile(archive_name) as previous:
        for control in ("plan.json", "preflight.json", "authorization.json"):
            require(
                previous.read(control) == members[control], "CONTROL_CHAIN:" + control
            )
require(
    manifest["kind"] == "PR89_terminal_tail_private_export_v1"
    and manifest["campaign_terminal_jobs_observed"] == 60
    and manifest["optimization_calls_added"] == 0
    and not manifest["campaign_modified"],
    "TAIL_SCOPE",
)
require(
    manifest["collected_job_ids"] == [str(j) for j in range(3729, 3735)]
    and not manifest["non_success_accounting_job_ids"],
    "TAIL_COMPLETENESS",
)
for item in states.values():
    require(
        item["state"] == "COMPLETED"
        and all(
            r["State"] == "COMPLETED" and r["ExitCode"] == "0:0" for r in item["rows"]
        ),
        "FULL_ACCOUNTING_TERMINAL",
    )


def read_rows(name):
    return list(
        csv.DictReader(
            io.StringIO((old_dir / name).read_text(encoding="utf-8"), newline="")
        )
    )


new_flat = flat
flat = sorted(read_rows("cells.csv") + new_flat, key=lambda r: int(r["index"]))
threshold_rows = read_rows("thresholds.csv") + threshold_rows
horizon_rows = read_rows("horizons.csv") + horizon_rows
require([r["job_id"] for r in flat] == [str(j) for j in range(3675, 3735)], "FULL_IDS")
require(
    len({(r["alias"], int(r["threads"]), r["method"]) for r in flat}) == 60,
    "FULL_MATRIX",
)
require(len(threshold_rows) == len(horizon_rows) == 240, "TEMPORAL_UNION")
for row in flat:
    main = next(x for x in states[row["job_id"]]["rows"] if x["JobID"] == row["job_id"])
    require(
        int(main["ElapsedRaw"]) == int(row["slurm_elapsed_seconds"])
        and main["State"] == "COMPLETED"
        and main["ExitCode"] == "0:0",
        "PRIOR_ACCOUNTING_PARITY",
    )
    require(
        int(main["AllocCPUS"]) == 2 * int(row["threads"]),
        "LOGICAL_PHYSICAL_OBSERVED_RATIO",
    )


def truth(value):
    return str(value).lower() == "true"


summary = {}
for alias in ("M0", "M4", "M7", "M12"):
    group = [r for r in flat if r["alias"] == alias]
    best = min(group, key=lambda r: float(r["primal"]))
    largest = max(group, key=lambda r: float(r["dual"]))
    excess = max(0.0, float(largest["dual"]) - float(best["primal"]))
    summary[alias] = {
        "received": len(group),
        "reported_target": sum(int(x["status"]) == 2 for x in group),
        "time_limit": sum(int(x["status"]) == 9 for x in group),
        "runtime_hours": sum(float(x["runtime_seconds"]) for x in group) / 3600,
        "primal_min": float(best["primal"]),
        "primal_min_job": best["job_id"],
        "primal_max": max(float(x["primal"]) for x in group),
        "maximum_reported_dual": float(largest["dual"]),
        "maximum_dual_job": largest["job_id"],
        "cross_run_bound_excess": excess,
        "cross_run_excess_percent": 100 * excess / abs(float(best["primal"])),
    }
comparisons = []
for alias in ("M0", "M4", "M7", "M12"):
    for cap in (1, 2, 4, 8, 16):
        group = {
            r["presentation"]: r
            for r in flat
            if r["alias"] == alias and int(r["threads"]) == cap
        }
        b, r, g = [group[x] for x in ("B", "R", "G")]
        comparisons.append(
            {
                "alias": alias,
                "threads": cap,
                "B_job": b["job_id"],
                "R_job": r["job_id"],
                "G_job": g["job_id"],
                "B_runtime_seconds": float(b["runtime_seconds"]),
                "R_runtime_seconds": float(r["runtime_seconds"]),
                "G_runtime_seconds": float(g["runtime_seconds"]),
                "B_over_G_runtime_quotient": float(b["runtime_seconds"])
                / float(g["runtime_seconds"]),
                "R_over_G_runtime_quotient": float(r["runtime_seconds"])
                / float(g["runtime_seconds"]),
                "B_final_gap_percent": 100 * float(b["gap_fraction"]),
                "R_final_gap_percent": 100 * float(r["gap_fraction"]),
                "G_final_gap_percent": 100 * float(g["gap_fraction"]),
                "any_terminal_censoring": any(
                    truth(x["right_censored"]) for x in group.values()
                ),
                "numerical_restriction": alias in ("M4", "M12"),
                "certified_speedup": False,
            }
        )
exact_lookup = {}
exact_audit_hashes = {}
for audit_path in args.exact_audit:
    audit_raw = audit_path.read_bytes()
    audit_value = json.loads(audit_raw)
    require(
        audit_value["optimization_calls_added"] == 0
        and not audit_value["campaign_modified"],
        "EXACT_AUDIT_SCOPE",
    )
    exact_audit_hashes[audit_path.name] = sha(audit_raw)
    for audit_row in audit_value["rows"]:
        job = audit_row["job_id"]
        require(
            job in {str(j) for j in range(3720, 3735)} and job not in exact_lookup,
            "EXACT_AUDIT_JOB",
        )
        exact_lookup[job] = (
            "exact_primal_feasible_in_decimal_and_binary64_audits_not_global"
            if audit_row["diagnostics"][
                "exact_integer_primal_feasible_decimal_lp_model"
            ]
            and audit_row["diagnostics"]["exact_integer_primal_feasible_binary64_model"]
            else "nonintegral_stored_binary_and_rounded_pattern_infeasible"
        )
# Every cell receives an explicit reporting disposition; raw flags remain false.
disposition = []
for row in flat:
    alias = row["alias"]
    censored = truth(row["right_censored"])
    disposition.append(
        {
            "job_id": row["job_id"],
            "index": row["index"],
            "alias": alias,
            "threads": row["threads"],
            "method": row["method"],
            "receipt": "received_seals_and_identity_checked",
            "scheduler": "COMPLETED_0:0",
            "solver_stop": "time_limit" if censored else "reported_target_attained",
            "terminal_censoring": censored,
            "numerical_stratum": alias + "_sensitive"
            if alias in ("M4", "M12")
            else "reported_precision_cross_run_bound_discrepancy"
            if alias == "M0"
            else "not_flagged_by_current_audit",
            "reported_primal_dual_gap": "descriptive_under_reported_tolerances",
            "time_to_reported_terminal_target": "right_censored_at_actual_followup"
            if censored
            else "observed_solver_reported_not_exact_optimality",
            "solver_runtime_and_work": "descriptive_observed_cost",
            "whole_job_cold_end_to_end": "not_qualified_historical_preparation_reused",
            "exact_primal_audit": exact_lookup.get(
                row["job_id"], "not_independently_checked"
            ),
            "exact_global_optimality": "not_proven",
            "certified_speedup": False,
            "raw_scientific_reporting_eligible": False,
            "final_integrated_audit": "pending",
        }
    )
review = {
    "kind": "complete_campaign_receipt_with_metric_specific_limits",
    "reconciler_source_sha256": sha(Path(__file__).read_bytes()),
    "exact_audits": exact_audit_hashes,
    "source_commit": HEAD,
    "plan_sha256": plan_sha,
    "received_cells": 60,
    "planned_cells": 60,
    "terminal_accounting_jobs": 60,
    "terminal_accounting_rows": sum(len(x["rows"]) for x in states.values()),
    "query_started_utc": snapshot["query_started_utc"],
    "query_finished_utc": snapshot["query_finished_utc"],
    "query_scope": snapshot["query_scope"],
    "input_archives": old_manifest["input_archives"]
    + [{"role": "terminal_tail6", "sha256": EXPECTED, "received": 6}],
    "previous_public_manifest_sha256": sha(old_manifest_raw),
    "prior54_review_reused": True,
    "new6_parameters_temporal_cost_and_nested_triplets_verified": True,
    "tail_members_hash_verified": len(manifest["sha256"]),
    "tail_nested_seals_verified": 18,
    "full_control_bytes_identical": True,
    "by_parent": summary,
    "solver_statuses": dict(collections.Counter(str(x["status"]) for x in flat)),
    "runtime_hours": sum(float(x["runtime_seconds"]) for x in flat) / 3600,
    "slurm_elapsed_hours": sum(float(x["slurm_elapsed_seconds"]) for x in flat) / 3600,
    "observed_physical_reserved_core_hours": sum(
        int(x["threads"]) * float(x["slurm_elapsed_seconds"]) for x in flat
    )
    / 3600,
    "observed_logical_AllocCPU_hours": sum(
        int(x["allocated_logical_cpus"]) * float(x["slurm_elapsed_seconds"])
        for x in flat
    )
    / 3600,
    "solver_runtime_hours_by_method": {
        m: sum(float(x["runtime_seconds"]) for x in flat if x["presentation"] == m)
        / 3600
        for m in ("B", "R", "G")
    },
    "job_minus_solver_seconds_range": [
        min(float(x["slurm_minus_solver_seconds"]) for x in flat),
        max(float(x["slurm_minus_solver_seconds"]) for x in flat),
    ],
    "m12_tail_job_minus_solver_seconds_range": [
        min(float(x["slurm_minus_solver_seconds"]) for x in new_flat),
        max(float(x["slurm_minus_solver_seconds"]) for x in new_flat),
    ],
    "start_statuses": dict(collections.Counter(x["start_status"] for x in flat)),
    "threshold_states": {
        str(t): dict(
            collections.Counter(
                x["state"] for x in threshold_rows if float(x["threshold"]) == t
            )
        )
        for t in (0.1, 0.05, 0.01, 0.0001)
    },
    "final_campaign_receipt_complete": True,
    "scientific_reporting_eligible": False,
    "exact_global_optimality_certified": False,
    "campaign_modified": False,
    "optimization_calls_added": 0,
    "offline_only": True,
    "allocation_hours_are_not_billing_or_measured_utilization": True,
}
destination = args.output
require(not destination.exists(), "OUTPUT_EXISTS_PRESERVE")
destination.mkdir()


def save_csv(name, rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    (destination / name).write_text(out.getvalue(), encoding="utf-8", newline="")


for name, rows in [
    ("cells.csv", flat),
    ("thresholds.csv", threshold_rows),
    ("horizons.csv", horizon_rows),
    ("disposition.csv", disposition),
    ("paired-observations.csv", comparisons),
]:
    save_csv(name, rows)
(destination / "review.json").write_bytes(encoded(review))
(destination / "scheduler-snapshot.json").write_bytes(encoded(snapshot))
output_manifest = {
    "schema_version": 3,
    "kind": "sealed_complete_campaign_descriptive_evidence",
    "source_commit": HEAD,
    "plan_sha256": plan_sha,
    "received_cells": 60,
    "planned_cells": 60,
    "scientific_reporting_eligible": False,
    "final_campaign_return": True,
    "final_campaign_return_scope": "all_receipts_reconciled_not_unrestricted_scientific_qualification",
    "previous_public_manifest_sha256": sha(old_manifest_raw),
    "input_archives": review["input_archives"],
    "files": {p.name: sha(p.read_bytes()) for p in destination.iterdir()},
    "raw_logs_vectors_models_or_private_paths_published": False,
}
(destination / "manifest.json").write_bytes(encoded(output_manifest))
print(
    json.dumps(
        {
            "review": review,
            "tail_records": new_flat,
            "paired_observations": comparisons,
            "output_manifest_sha256": sha(encoded(output_manifest)),
        },
        indent=2,
    )
)
