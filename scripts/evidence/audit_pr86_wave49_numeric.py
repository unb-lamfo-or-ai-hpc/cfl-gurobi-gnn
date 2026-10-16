"""Read-only M4 cross-run consistency and stored-solution audit; never optimize."""

import argparse
import gc
import gzip
import hashlib
import json
import math
import os
import platform
from pathlib import Path
from types import SimpleNamespace

import review_pr86_f0 as f0

q = f0.q
SHA = "ed87d2e280a1941228c7662ff234c24dd31a5906d8f0fe1d98962938fcdfdbe6"
COMMIT = "596c87bf004405f6148d381d2ba1764c650ca60c"
PLAN = "84bda69a51876564e09f22351d26be79d0e29d433e81085499b7308a7d6a23f9"
DEST = q.ROOT / "docs/evidence/pr86/jobs3609-3614"
STAGE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence/pr86/next-49-596c87bf0044")
MODEL = "9673147c6b0ca81086134a595d980d8eb5a462731a8f0336ae7a9a2dbefbe3c1"


def load_wave(raw):
    q.require(q.digest(raw) == SHA, "wave49_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = value["plan"]
    q.require(frozen["source_commit"] == COMMIT, "wave49_source")
    q.require(
        value["plan_sha256"] == q.digest(q.encoded(frozen)) == PLAN, "wave49_plan"
    )
    original, cells = q.first.executor.proposal.build()
    q.require(len(frozen["groups"]) == 6, "six_groups")
    for group, expected in zip(frozen["groups"], original["groups"][49:55]):
        q.require(group["group"] == expected, "manifest_group")
        q.require(
            group["cells"]
            == [c for c in cells if c["group_id"] == expected["group_id"]],
            "manifest_cells",
        )
    policy = SimpleNamespace(
        protocol="pr86_frozen_groups49_54_v1", plan=lambda _: frozen
    )
    q.require(
        q.validate_return(raw, policy)["ready_for_independent_review"], "incomplete"
    )
    q.require(
        [r["accounting"]["job_id"] for r in value["returns"]]
        == [str(j) for j in range(3609, 3615)],
        "wave49_jobs",
    )
    return value


def records(wave):
    result = []
    for group_index, returned in enumerate(wave["returns"]):
        for attempt_index, cell in enumerate(returned["plan"]["cells"]):
            ref = returned["members"][f"run/attempt-{attempt_index}/child.json"]
            child = f0.member(returned, f"run/attempt-{attempt_index}/child.json")
            value = child["result"]
            q.require(value["mip_sha256"] == MODEL, "model_identity")
            q.require(value["effective_objective_sense"] == "MINIMIZE", "sense")
            q.require(
                value["independent_feasibility"]["valid"], "tolerance_feasibility"
            )
            result.append(
                {
                    "cell_id": cell["cell_id"],
                    "parent": cell["parent"],
                    "method": cell["method"],
                    "threads": cell["threads"],
                    "seed": cell["seed"],
                    "group_index": group_index,
                    "attempt_index": attempt_index,
                    "job_id": returned["accounting"]["job_id"],
                    "model_sha256": value["mip_sha256"],
                    "mathematical_signature_sha256": value[
                        "mathematical_signature_sha256"
                    ],
                    "model_fingerprint": value["model_fingerprint"],
                    "child_sha256": ref["sha256"],
                    "primal": value["solve"]["primal"],
                    "dual": value["solve"]["dual"],
                    "status_code": value["solve"]["solve_status_code"],
                    "reported_gap_fraction": value["solve"][
                        "terminal_mip_gap_relative"
                    ],
                    "right_censored": value["solve"]["right_censored"],
                    "solver_seconds": value["solve"]["solver_runtime_seconds"],
                    "max_integrality_residual": value["independent_feasibility"][
                        "max_integrality_residual"
                    ],
                    "max_row_residual": value["independent_feasibility"][
                        "max_row_residual"
                    ],
                    "tolerance_feasible": True,
                }
            )
    q.require(
        len(result) == len({r["cell_id"] for r in result}) == 18,
        "eighteen_unique_cells",
    )
    return result


def cross_run_findings(rows):
    """Screen bounds against tolerance-feasible points, not exact feasibility proof."""
    findings = []
    for bound in rows:
        q.require(
            all(math.isfinite(bound[k]) for k in ("primal", "dual")), "finite_values"
        )
        for candidate in rows:
            identity = (
                "parent",
                "model_sha256",
                "mathematical_signature_sha256",
                "model_fingerprint",
            )
            if any(bound[k] != candidate[k] for k in identity):
                continue
            tolerance = max(1e-6, abs(candidate["primal"]) * 1e-8)
            if bound["dual"] > candidate["primal"] + tolerance:
                findings.append(
                    {
                        "bound_cell": bound["cell_id"],
                        "candidate_cell": candidate["cell_id"],
                        "reported_lower_bound": bound["dual"],
                        "tolerance_feasible_objective": candidate["primal"],
                        "absolute_difference": bound["dual"] - candidate["primal"],
                        "relative_difference": (bound["dual"] - candidate["primal"])
                        / abs(candidate["primal"]),
                        "screening_absolute_tolerance": tolerance,
                        "classification": "bound_above_tolerance_feasible_incumbent_requires_private_audit",
                        "exact_feasibility_proven": False,
                    }
                )
    return findings


def summary(wave, rows):
    findings = cross_run_findings(rows)
    return {
        "protocol_id": "pr86_wave49_cross_run_numeric_screen_v1",
        "return_sha256": SHA,
        "source_commit": COMMIT,
        "plan_sha256": PLAN,
        "structural_review_passed": True,
        "new_wave_cells_collected": 18,
        "campaign_cells_collected": 165,
        "previously_reviewed_cells": 147,
        "new_wave_numeric_qualification_pending": bool(findings),
        "remaining_unexecuted_cells": 45,
        "remaining_unexecuted_groups": 15,
        "reported_target_reaching_cells_in_wave": sum(
            not r["right_censored"] for r in rows
        ),
        "reported_censored_cells_in_wave": sum(r["right_censored"] for r in rows),
        "wave_scheduler_elapsed_sum_seconds": sum(
            r["accounting"]["rows"][0]["ElapsedRaw"] for r in wave["returns"]
        ),
        "findings": findings,
        "cause_proven": False,
        "rounded_solution_audit_available": False,
        "remaining_dispatch_admitted": False,
        "scientific_reporting_eligible": False,
        "historical_receipts_and_flags_unchanged": True,
        "optimization_runs_added": 0,
    }


def emit(path, value):
    raw = q.encoded(value)
    if path.exists():
        q.require(q.read(path) == raw, "preserve_output")
    else:
        with path.open("xb") as stream:
            stream.write(raw)
    return q.digest(raw)


def publish(directory):
    wave = load_wave(q.read(DEST / "public_return.json"))
    rows = records(wave)
    report = summary(wave, rows)
    directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "numeric_screen.json": q.encoded(report),
        "wave_results.csv": f0.csv_bytes(rows),
    }
    for name, raw in outputs.items():
        path = directory / name
        if path.exists():
            q.require(q.read(path) == raw, "preserve_output")
        else:
            with path.open("xb") as stream:
                stream.write(raw)
    emit(
        directory / "manifest.json",
        {"input_sha256": SHA, "outputs": {k: q.digest(v) for k, v in outputs.items()}},
    )
    return report


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scoped_regular_file(path, root):
    path, root = Path(path), Path(root)
    q.require(
        path.is_absolute()
        and not path.is_symlink()
        and path.is_file()
        and path.resolve() == path.absolute()
        and path.resolve().is_relative_to(root.resolve()),
        "scoped_regular_file",
    )
    return path


def installed_bundle(wave, row, stage=STAGE):
    group = stage / f"group-{row['group_index']}"
    path = scoped_regular_file(group / "requests.json", stage)
    requests = q.first.executor.existing.review.flow.meta.strict_json(q.read(path))
    started = f0.member(wave["returns"][row["group_index"]], "run/group.started.json")
    q.require(
        isinstance(requests, list)
        and len(requests) == len(started["bundle_sha256"]) == 3
        and all(
            isinstance(ref, dict)
            and set(ref) == {"file", "sha256"}
            and ref["file"] == f"bundle-{i}.json"
            and ref["sha256"] == started["bundle_sha256"][i]
            for i, ref in enumerate(requests)
        ),
        "historical_bundle_seals",
    )
    request = requests[row["attempt_index"]]
    path = scoped_regular_file(
        group / "admission" / request["file"], group / "admission"
    )
    raw = q.read(path)
    q.require(q.digest(raw) == request["sha256"], "installed_bundle_hash")
    bundle = q.first.executor.existing.review.flow.meta.strict_json(raw)
    frozen = wave["plan"]["groups"][row["group_index"]]
    q.require(
        bundle["cell"] == frozen["cells"][row["attempt_index"]]
        and bundle["context"] == frozen["context"],
        "installed_cell_and_context",
    )
    return bundle


def array_diagnostics(data, x, reported_objective):
    """Round only an in-memory copy; do not repair, solve or alter stored values."""
    import numpy as np

    from cfl_gnn.validation.mathematical import validate_linear_solution

    integer = np.asarray(data["types"]) != "C"
    rounded = x.copy()
    rounded[integer] = np.rint(rounded[integer])
    result = {}
    rows, columns, coefficients = (data[k] for k in ("rows", "columns", "coefficients"))
    row_scale = np.zeros(len(data["rhs"]))
    np.maximum.at(row_scale, rows, np.abs(coefficients))
    for label, values in (("stored", x), ("rounded_in_memory_only", rounded)):
        audit = validate_linear_solution(
            **data,
            values=values,
            reported_objective=reported_objective if label == "stored" else None,
        )
        activity = np.bincount(
            rows, weights=coefficients * values[columns], minlength=len(row_scale)
        )
        directions, rhs = np.asarray(data["senses"]), np.asarray(data["rhs"])
        violations = np.where(
            directions == "<",
            np.maximum(activity - rhs, 0),
            np.where(
                directions == ">", np.maximum(rhs - activity, 0), abs(activity - rhs)
            ),
        )
        scale = np.where(row_scale > 0, row_scale, 1)
        normalized = violations / scale
        audit["max_row_violation_divided_by_max_abs_row_coefficient"] = float(
            normalized.max(initial=0)
        )
        audit["rows_above_1e_minus6_after_row_normalization"] = int(
            (normalized > 1e-6).sum()
        )
        audit["row_normalization_is_diagnostic_not_new_acceptance_rule"] = True
        extended = np.longdouble
        high_activity = np.zeros(len(row_scale), dtype=extended)
        for start in range(0, len(coefficients), 65536):
            block = slice(start, start + 65536)
            np.add.at(
                high_activity,
                rows[block],
                coefficients[block].astype(extended)
                * values[columns[block]].astype(extended),
            )
        high_rhs = rhs.astype(extended)
        high_violation = np.where(
            directions == "<",
            np.maximum(high_activity - high_rhs, 0),
            np.where(
                directions == ">",
                np.maximum(high_rhs - high_activity, 0),
                abs(high_activity - high_rhs),
            ),
        )
        audit["extended_precision"] = {
            "mantissa_bits": int(np.finfo(extended).nmant),
            "recomputed_objective": float(
                np.sum(
                    np.asarray(data["objective"], dtype=extended)
                    * values.astype(extended),
                    dtype=extended,
                )
                + extended(data.get("objective_offset", 0))
            ),
            "max_row_residual": float(high_violation.max(initial=0)),
            "max_row_normalized_residual": float(
                (high_violation / scale.astype(extended)).max(initial=0)
            ),
            "exact_arithmetic_certificate": False,
        }
        result[label] = audit
    result["integer_values_changed_by_rounding"] = int(
        (x[integer] != rounded[integer]).sum()
    )
    result["rounded_objective_minus_stored_objective"] = (
        result["rounded_in_memory_only"]["recomputed_objective"]
        - result["stored"]["recomputed_objective"]
    )
    return result


def installed(directory):
    q.require(
        platform.system() == "Linux" and platform.node().split(".")[0] == "dgx-dasci",
        "execution_host",
    )
    q.require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env", "environment")
    q.require(
        not directory.exists() and directory.parent == q.BASE,
        "fresh_output_under_evidence",
    )
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (16 * 2**30, 16 * 2**30))
    wave = load_wave(q.read(STAGE / "public_return.json"))
    observed = records(wave)
    findings = cross_run_findings(observed)
    selected_ids = {v[k] for v in findings for k in ("bound_cell", "candidate_cell")}
    q.require(len(selected_ids) == 4, "four_scoped_solutions")
    directory.mkdir(mode=0o700)
    result = {
        "protocol_id": "pr86_wave49_stored_solution_numeric_audit_v1",
        "return_sha256": SHA,
        "source_commit": COMMIT,
        "source_commit_role": "historical_campaign_worker",
        "collector_source_commit": q.first.roots.head(),
        "collector_source_sha256_lf": q.digest(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ),
        "solutions": [],
        "optimization_runs_added": 0,
        "scheduler_queries": 0,
        "submissions_added": 0,
        "raw_logs_or_variable_values_included": False,
        "original_solution_hashes_were_not_exported_in_historical_return": True,
        "newly_observed_private_hashes_are_not_historical_seals": True,
        "mathematical_model_or_solver_parameters_changed": False,
        "rounded_values_persisted_or_used_as_start": False,
        "cause_proven": False,
        "remaining_dispatch_admitted": False,
        "scientific_reporting_eligible": False,
    }
    import gurobipy as gp
    import numpy as np

    from cfl_gnn.solvers.paired_partial_start import mathematical_signature

    q.require(list(gp.gurobi.version()) == [13, 0, 1], "gurobi_version")
    selected = [r for r in observed if r["cell_id"] in selected_ids]
    mip_paths = []
    for row in selected:
        bundle = installed_bundle(wave, row)
        mip_paths.append(
            scoped_regular_file(
                Path(bundle["private_mip_path"]), Path("/raid/vrcelestino/data")
            )
        )
    q.require(
        len(set(mip_paths)) == 1 and sha_file(mip_paths[0]) == MODEL, "installed_model"
    )
    with (
        gp.Env(params={"OutputFlag": 0}) as env,
        gp.read(str(mip_paths[0]), env=env) as model,
    ):
        model.ModelSense = gp.GRB.MINIMIZE
        model.update()
        q.require(
            mathematical_signature(model)
            == selected[0]["mathematical_signature_sha256"],
            "installed_formulation",
        )
        variables, constraints = model.getVars(), model.getConstrs()
        names = [v.VarName for v in variables]
        q.require(len(names) == len(set(names)), "unique_names")
        matrix = model.getA().tocoo()
        data = dict(
            lower=np.array([v.LB for v in variables]),
            upper=np.array([v.UB for v in variables]),
            types=np.array([v.VType for v in variables]),
            objective=np.array([v.Obj for v in variables]),
            objective_offset=float(model.ObjCon),
            rows=matrix.row,
            columns=matrix.col,
            coefficients=matrix.data,
            senses=np.array([c.Sense for c in constraints]),
            rhs=np.array([c.RHS for c in constraints]),
        )
        magnitudes = abs(matrix.data)
        result["model"] = {
            "sha256": MODEL,
            "mathematical_signature_sha256": mathematical_signature(model),
            "variables": len(variables),
            "constraints": len(constraints),
            "nonzeros": len(matrix.data),
            "min_nonzero_abs_coefficient": float(magnitudes[magnitudes > 0].min()),
            "max_abs_coefficient": float(magnitudes.max()),
            "coefficients_below_1e_minus9": int(
                ((magnitudes > 0) & (magnitudes < 1e-9)).sum()
            ),
        }
        for row in selected:
            folder = (
                STAGE
                / f"group-{row['group_index']}"
                / "run"
                / f"attempt-{row['attempt_index']}"
            )
            q.require(
                q.digest(q.read(scoped_regular_file(folder / "child.json", STAGE)))
                == row["child_sha256"],
                "installed_child",
            )
            child = json.loads(q.read(folder / "child.json"))
            log_raw = q.read(scoped_regular_file(folder / "gurobi.private.log", STAGE))
            q.require(
                q.digest(log_raw) == child["gurobi_log"]["log_sha256"],
                "sealed_solver_log",
            )
            log_text = log_raw.decode("utf-8", errors="replace").lower()
            flags = {
                name: phrase in log_text
                for name, phrase in {
                    "large_matrix_coefficient_range": "large matrix coefficient range",
                    "large_rhs": "large rhs",
                    "large_bounds": "large bounds",
                    "numerical_trouble": "numerical trouble",
                    "unscaled_primal_violation": "unscaled primal violation",
                    "unscaled_dual_violation": "unscaled dual violation",
                    "quad_precision": "quad precision",
                    "optimal_solution_found": "optimal solution found",
                }.items()
            }
            path = scoped_regular_file(folder / "solution.private.json.gz", STAGE)
            before = sha_file(path)
            with gzip.open(path, "rb") as stream:
                raw = stream.read(512 * 2**20 + 1)
            q.require(len(raw) <= 512 * 2**20, "solution_read_cap")
            solution = json.loads(raw)
            q.require(
                solution["mip_sha256"] == MODEL
                and solution["objective_sense"] == "MINIMIZE",
                "solution_identity",
            )
            q.require(solution["objective"] == row["primal"], "solution_objective")
            q.require(set(solution["variables"]) == set(names), "solution_names")
            x = np.array(
                [solution["variables"][name] for name in names], dtype=np.float64
            )
            diagnostics = array_diagnostics(data, x, row["primal"])
            q.require(diagnostics["stored"]["valid"], "stored_solution_parity")
            q.require(sha_file(path) == before, "solution_changed_during_read")
            result["solutions"].append(
                {
                    "cell_id": row["cell_id"],
                    "private_solution_sha256_observed_now": before,
                    "child_sha256": row["child_sha256"],
                    "reported_primal": row["primal"],
                    "reported_dual": row["dual"],
                    "sealed_log_sha256": child["gurobi_log"]["log_sha256"],
                    "allowlisted_log_flags": flags,
                    "diagnostics": diagnostics,
                }
            )
            emit(
                directory / f"solution-{len(result['solutions'])}.json",
                result["solutions"][-1],
            )
            del raw, solution, x
            gc.collect()
    q.require(sha_file(mip_paths[0]) == MODEL, "model_changed_during_read")
    digest = emit(directory / "numeric_audit.json", result)
    print_receipt(digest)


def print_receipt(digest):
    print(
        json.dumps(
            {
                "receipt_sha256": digest,
                "solutions_read": 4,
                "optimization_runs_added": 0,
                "remaining_dispatch_admitted": False,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--installed-output", type=Path)
    args = parser.parse_args()
    q.require((args.output is None) != (args.installed_output is None), "one_mode")
    if args.installed_output is not None:
        try:
            installed(args.installed_output)
        except Exception as error:
            allowed_codes = {
                "execution_host",
                "environment",
                "fresh_output_under_evidence",
                "four_scoped_solutions",
                "gurobi_version",
                "installed_bundle_hash",
                "historical_bundle_seals",
                "scoped_regular_file",
                "installed_cell_and_context",
                "installed_cell",
                "installed_model",
                "installed_formulation",
                "unique_names",
                "installed_child",
                "sealed_solver_log",
                "solution_read_cap",
                "solution_identity",
                "solution_objective",
                "solution_names",
                "stored_solution_parity",
                "solution_changed_during_read",
                "model_changed_during_read",
            }
            print(
                json.dumps(
                    {
                        "audit_stopped": True,
                        "exception_type": type(error).__name__,
                        "failure_code": str(error)
                        if str(error) in allowed_codes
                        else "unclassified_exception",
                        "private_exception_text_included": False,
                        "optimization_runs_added": 0,
                        "remaining_dispatch_admitted": False,
                    }
                )
            )
            return 2
    else:
        print(json.dumps(publish(args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
