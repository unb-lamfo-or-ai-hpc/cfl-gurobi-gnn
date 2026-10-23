"""Bounded read-only M12 audit: six stored vectors, no optimize or scheduler."""

import argparse
import gc
import gzip
import json
import math
import os
import platform
from pathlib import Path

import audit_pr86_wave49_numeric as old
import review_pr86_wave61 as review

q = review.q
SHA, COMMIT = review.SHA, review.COMMIT
STAGE = q.BASE / ("next-61-" + COMMIT[:12])
MODEL = "c93c8862e4819d1a2b62e721d907afe07b79039d12b953cdb881525c7d251801"
PROTOCOL = "pr86_wave61_m12_stored_solution_numeric_audit_v1"
EXPECTED = {
    "M12-threads1-seed42-M0",
    "M12-threads1-seed42-M1",
    "M12-threads1-seed42-M2",
    "M12-threads1-seed43-M2",
    "M12-threads1-seed44-M2",
    "M12-threads2-seed42-M2",
}
emit, sha_file, scoped_regular_file = old.emit, old.sha_file, old.scoped_regular_file
array_diagnostics = old.array_diagnostics


def records(wave):
    rows = []
    for group_index, returned in enumerate(wave["returns"]):
        for attempt_index, cell in enumerate(returned["plan"]["cells"]):
            if cell["parent"] != "CFL_medium_instance_12":
                continue
            name = f"run/attempt-{attempt_index}/child.json"
            value = old.f0.member(returned, name)["result"]
            q.require(
                value["mip_sha256"] == MODEL
                and value["effective_objective_sense"] == "MINIMIZE",
                "model_identity",
            )
            q.require(
                value["independent_feasibility"]["valid"], "tolerance_feasibility"
            )
            rows.append(
                {
                    "cell_id": cell["cell_id"],
                    "parent": cell["parent"],
                    "group_index": group_index,
                    "attempt_index": attempt_index,
                    "model_sha256": value["mip_sha256"],
                    "mathematical_signature_sha256": value[
                        "mathematical_signature_sha256"
                    ],
                    "model_fingerprint": value["model_fingerprint"],
                    "child_sha256": returned["members"][name]["sha256"],
                    "primal": value["solve"]["primal"],
                    "dual": value["solve"]["dual"],
                }
            )
    q.require(len(rows) == len({r["cell_id"] for r in rows}) == 12, "twelve_m12_cells")
    return rows


def selected_records(wave):
    rows = records(wave)
    findings = old.cross_run_findings(rows)
    ids = {f[k] for f in findings for k in ("bound_cell", "candidate_cell")}
    q.require(ids == EXPECTED and len(findings) == 8, "six_scoped_solutions")
    return [r for r in rows if r["cell_id"] in ids]


def validate_numeric(raw, expected_sha, collector):
    q.require(q.digest(raw) == expected_sha, "numeric_return_hash")
    value = q.first.executor.existing.review.flow.meta.strict_json(raw)
    q.require(
        value["protocol_id"] == PROTOCOL
        and value["source_commit"] == COMMIT
        and value["collector_source_commit"] == collector
        and value["return_sha256"] == SHA,
        "numeric_identity",
    )
    q.require(
        value["collector_source_sha256_lf"]
        == q.digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))
        and value["diagnostic_helper_sha256_lf"]
        == q.digest(Path(old.__file__).read_bytes().replace(b"\r\n", b"\n")),
        "collector_and_helper_bytes",
    )
    for key in ("optimization_runs_added", "scheduler_queries", "submissions_added"):
        q.require(type(value[key]) is int and value[key] == 0, "read_only_scope")
    for key in (
        "raw_logs_or_variable_values_included",
        "mathematical_model_or_solver_parameters_changed",
        "rounded_values_persisted_or_used_as_start",
        "cause_proven",
        "remaining_dispatch_admitted",
        "scientific_reporting_eligible",
    ):
        q.require(value[key] is False, "false_diagnostic_gates")
    q.require(
        value["original_solution_hashes_were_not_exported_in_historical_return"] is True
        and value["newly_observed_private_hashes_are_not_historical_seals"] is True,
        "historical_seal_limitation",
    )
    wave = review.review_wave(q.read(review.DEST / "public_return.json"))
    selected = selected_records(wave)
    q.require(
        len(value["solutions"]) == 6
        and {s["cell_id"] for s in value["solutions"]} == EXPECTED,
        "six_numeric_cells",
    )
    q.require(
        value["model"]["sha256"] == MODEL
        and all(
            value["model"]["mathematical_signature_sha256"]
            == r["mathematical_signature_sha256"]
            for r in selected
        ),
        "same_model_signature",
    )
    for solution in value["solutions"]:
        row = next(r for r in selected if r["cell_id"] == solution["cell_id"])
        child = old.f0.member(
            wave["returns"][row["group_index"]],
            f"run/attempt-{row['attempt_index']}/child.json",
        )
        q.require(
            solution["child_sha256"] == row["child_sha256"]
            and solution["reported_primal"] == row["primal"]
            and solution["reported_dual"] == row["dual"]
            and solution["sealed_log_sha256"] == child["gurobi_log"]["log_sha256"],
            "numeric_cell_and_sealed_log",
        )
        q.require(
            isinstance(solution["private_solution_sha256_observed_now"], str)
            and len(solution["private_solution_sha256_observed_now"]) == 64
            and all(
                c in "0123456789abcdef"
                for c in solution["private_solution_sha256_observed_now"]
            ),
            "private_hash_format",
        )
        diagnostics = solution["diagnostics"]
        q.require(
            diagnostics["stored"]["valid"] is True
            and all(v is True for v in diagnostics["stored"]["checks"].values()),
            "stored_solution_parity",
        )
        q.require(
            math.isclose(
                diagnostics["stored"]["recomputed_objective"],
                row["primal"],
                rel_tol=1e-8,
                abs_tol=1e-6,
            ),
            "recomputed_objective_parity",
        )
        for label in ("stored", "rounded_in_memory_only"):
            item = diagnostics[label]
            q.require(
                type(item["valid"]) is bool
                and item["feasibility_tolerance"] == 1e-6
                and item["integrality_tolerance"] == 1e-5
                and item["row_normalization_is_diagnostic_not_new_acceptance_rule"]
                is True
                and item["extended_precision"]["exact_arithmetic_certificate"] is False,
                "original_tolerances_and_diagnostic_scope",
            )
            q.require(
                all(
                    math.isfinite(item[k])
                    and math.isfinite(item["extended_precision"][k])
                    for k in ("recomputed_objective", "max_row_residual")
                ),
                "finite_diagnostics",
            )
            q.require(
                item["valid"] == all(item["checks"].values()), "diagnostic_checks"
            )
            q.require(
                all(type(v) is bool for v in item["checks"].values()), "boolean_checks"
            )
    return {
        "solutions_read": 6,
        "optimization_runs_added": 0,
        "remaining_dispatch_admitted": False,
        "scientific_reporting_eligible": False,
    }


# Installed implementation below reuses the prior tested array/bundle readers.


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
    wave = review.review_wave(q.read(STAGE / "public_return.json"))
    selected = selected_records(wave)
    directory.mkdir(mode=0o700)
    result = {
        "protocol_id": PROTOCOL,
        "return_sha256": SHA,
        "source_commit": COMMIT,
        "source_commit_role": "historical_campaign_worker",
        "collector_source_commit": q.first.roots.head(),
        "collector_source_sha256_lf": q.digest(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ),
        "diagnostic_helper_sha256_lf": q.digest(
            Path(old.__file__).read_bytes().replace(b"\r\n", b"\n")
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
    mip_paths = []
    for row in selected:
        bundle = old.installed_bundle(wave, row, stage=STAGE)
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
    print(
        json.dumps(
            {
                "receipt_sha256": digest,
                "solutions_read": 6,
                "optimization_runs_added": 0,
                "remaining_dispatch_admitted": False,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--collector-commit")
    args = parser.parse_args()
    try:
        q.require((args.installed_output is None) != (args.receipt is None), "one_mode")
        if args.installed_output is not None:
            installed(args.installed_output)
        else:
            print(
                json.dumps(
                    validate_numeric(
                        q.read(args.receipt),
                        args.expected_sha256,
                        args.collector_commit,
                    )
                )
            )
    except Exception as error:
        codes = {
            "execution_host",
            "environment",
            "fresh_output_under_evidence",
            "wave61_return_hash",
            "six_scoped_solutions",
            "gurobi_version",
            "historical_bundle_seals",
            "installed_bundle_hash",
            "installed_cell_and_context",
            "scoped_regular_file",
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
                    if str(error) in codes
                    else "unclassified_exception",
                    "private_exception_text_included": False,
                    "optimization_runs_added": 0,
                    "remaining_dispatch_admitted": False,
                }
            )
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
