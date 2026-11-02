"""Solver-free forensic arithmetic on existing private M12 artifacts.

Strict parser for the observed linear LP subset; unsupported syntax fails.
No optimize/import of solver or campaign modules, no result-vector repair.
"""
import argparse
import array
import collections
import gc
import gzip
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from fractions import Fraction as F
from pathlib import Path

import numpy as np

SHA = "bf5f13a9d6e34de77312c10e613f8b677e7b2548eec97e2a3c03cb9cae4105c2"
MODEL_SHA = "c93c8862e4819d1a2b62e721d907afe07b79039d12b953cdb881525c7d251801"
CHILD_SHA = {
    50: "d1705c90f7c7c1d1c350a201a1199ca506caff4c3e89deb966fe3cb6608dc09b",
    51: "ecefa1c2c925041ad703649fbb38359d65c231dcfe8c025e0b2de5c79b32f65a",
    52: "4c708a4c980a4269d5aea8e96bb419614cd382bde4541b7ac868e33bdbdb177e",
    53: "d23c4faefcaa89e66dfd5e69ff52ebac2cf98457fb2d04273219d51501f3f4b5",
}
N = 1281600
NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
TERM = re.compile(r"\s*([+-]?)\s*(?:(" + NUMBER + r")\s+)?x(\d+)\s*")
RELATION = re.compile(r"(<=|>=|=)\s*([+-]?" + NUMBER + r")\s*$")


def need(ok, label):
    if not ok:
        raise ValueError(label)


def terms(text):
    cursor = 0
    while cursor < len(text):
        m = TERM.match(text, cursor)
        need(m is not None, "unsupported_term:" + text[cursor:cursor + 70])
        sign, coefficient, index = m.groups()
        need(cursor == 0 or bool(sign), "missing_term_separator")
        token = ("-" if sign == "-" else "") + (coefficient or "1")
        index = int(index)
        need(index < N, "variable_index")
        yield index, float(token), token
        cursor = m.end()


def parse_lp(stream, active, expected_shape=(2400, 2561600, 1156800, 124800)):
    objective = np.zeros(N)
    obj_seen = np.zeros(N, dtype=bool)
    upper = np.ones(N) * np.inf
    binary = np.zeros(N, dtype=bool)
    row_ids, col_ids, values = array.array("i"), array.array("i"), array.array("d")
    tokens, cost_tokens, rhs, rhs_tokens, senses = [], {}, [], [], []
    cache = {}
    section, row, row_open, ended = None, -1, False, False
    bounds_count = 0
    for line in stream:
        s = line.strip()
        if not s or s.startswith("\\"):
            continue
        if s in ("Maximize", "Minimize", "Subject To", "Bounds", "Binaries", "End"):
            need(not row_open, "unclosed_row")
            section = s
            if s == "End":
                ended = True
            continue
        need(not ended, "content_after_end")
        if section in ("Maximize", "Minimize"):
            for index, value, token in terms(s):
                need(not obj_seen[index], "duplicate_objective_term")
                objective[index], obj_seen[index] = value, True
                if active[index]:
                    cost_tokens[index] = token
        elif section == "Subject To":
            label = re.match(r"R(\d+):\s*", s)
            if label:
                need(not row_open and int(label[1]) == row + 1, "row_sequence")
                row += 1
                row_open = True
                s = s[label.end():]
            need(row_open, "term_outside_row")
            relation = RELATION.search(s)
            expression = s if relation is None else s[:relation.start()].rstrip()
            if expression:
                for index, value, token in terms(expression):
                    row_ids.append(row)
                    col_ids.append(index)
                    values.append(value)
                    tokens.append(cache.setdefault(token, token))
            if relation:
                senses.append(relation[1])
                rhs.append(float(relation[2]))
                rhs_tokens.append(relation[2])
                row_open = False
        elif section == "Bounds":
            m = re.fullmatch(r"x(\d+)\s*<=\s*(" + NUMBER + r")", s)
            need(m is not None, "unsupported_bound")
            index, value = int(m[1]), float(m[2])
            need(index < N and np.isinf(upper[index]), "duplicate_or_invalid_bound")
            upper[index] = value
            bounds_count += 1
        elif section == "Binaries":
            for name in s.split():
                need(re.fullmatch(r"x\d+", name) is not None, "binary_name")
                index = int(name[1:])
                need(index < N and not binary[index], "duplicate_or_invalid_binary")
                binary[index] = True
        else:
            raise ValueError("unsupported_section")
    need(ended and not row_open, "LP_end")
    expected_rows, expected_nonzeros, expected_binary, expected_bounds = expected_shape
    need(obj_seen.all() and len(rhs) == expected_rows and len(values) == expected_nonzeros, "observed_model_dimensions")
    need(int(binary.sum()) == expected_binary and bounds_count == expected_bounds, "observed_variable_domains")
    upper[binary] = np.minimum(upper[binary], 1)
    need(np.isfinite(upper).all() and np.all(upper == 1), "observed_bounds")
    return dict(objective=objective, cost_tokens=cost_tokens, upper=upper, binary=binary,
                rows=np.asarray(row_ids), cols=np.asarray(col_ids), coefficients=np.asarray(values),
                tokens=tokens, rhs=np.array(rhs), rhs_tokens=rhs_tokens, senses=senses)


def exact_rows(model, x, decimal_coefficients=False):
    """All rows, omitting only exactly zero terms; no sampling or row scaling."""
    rows, cols, a = model["rows"], model["cols"], model["coefficients"]
    sums = [F(0) for _ in model["rhs"]]
    used = np.flatnonzero(x[cols] != 0)
    for k in used:
        c = F(model["tokens"][k]) if decimal_coefficients else F.from_float(float(a[k]))
        sums[int(rows[k])] += c * F.from_float(float(x[int(cols[k])]))
    violations = []
    for i, (activity, sense) in enumerate(zip(sums, model["senses"])):
        b = F(model["rhs_tokens"][i]) if decimal_coefficients else F.from_float(float(model["rhs"][i]))
        residual = activity - b
        violation = max(residual, F(0)) if sense == "<=" else max(-residual, F(0)) if sense == ">=" else abs(residual)
        if violation > 0:
            violations.append((i, violation))
    maximum = max((v for _, v in violations), default=F(0))
    return dict(rows_with_positive_exact_residual=len(violations),
                rows_exceeding_frozen_1e_minus6=sum(v > F("0.000001") for _, v in violations),
                max_row_residual=float(maximum), max_row_residual_rational=str(maximum),
                all_rows_exactly_satisfied=not violations), violations


def objective(model, x, decimal_coefficients=False):
    value = F(0)
    for i in np.flatnonzero(x):
        c = F(model["cost_tokens"][int(i)]) if decimal_coefficients else F.from_float(float(model["objective"][i]))
        value += c * F.from_float(float(x[i]))
    return value


def fixed_integer_row_obstruction(model, rounded, row):
    """Interval arithmetic, not a solve: can continuous bounds satisfy a row?"""
    low, high = F(0), F(0)
    for k in np.flatnonzero(model["rows"] == row):
        col = int(model["cols"][k])
        coefficient = F(model["tokens"][k])
        if model["binary"][col]:
            a = b = F.from_float(float(rounded[col]))
        else:
            a, b = F(0), F.from_float(float(model["upper"][col]))
        low += coefficient * (a if coefficient >= 0 else b)
        high += coefficient * (b if coefficient >= 0 else a)
    rhs = F(model["rhs_tokens"][row])
    sense = model["senses"][row]
    obstruction = low > rhs if sense == "<=" else high < rhs if sense == ">=" else not low <= rhs <= high
    margin = max(low-rhs, F(0)) if sense == "<=" else max(rhs-high, F(0)) if sense == ">=" else max(low-rhs, rhs-high, F(0))
    return {"continuous_completion_impossible_from_this_row": bool(obstruction),
            "violation_margin": float(margin), "violation_margin_rational_decimal_lp": str(margin)}


def diagnostics(model, x, reported):
    binary = model["binary"]
    rounded = x.copy()
    rounded[binary] = np.rint(rounded[binary])
    changed = np.flatnonzero(x != rounded)
    output = {"nonzero_values": int(np.count_nonzero(x)), "nonzero_continuous_values": int(np.count_nonzero(x[~binary])), "nonintegral_binary_count": int(len(changed)),
              "max_integrality_residual": float(np.max(np.abs(x[binary] - rounded[binary]))),
              "max_bound_residual": float(max(np.max(np.maximum(-x, 0)), np.max(np.maximum(x-model["upper"], 0))))}
    private = {}
    for label, point in (("stored", x), ("integer_rounded_copy", rounded)):
        binary64, violations = exact_rows(model, point)
        decimal_lp, decimal_violations = exact_rows(model, point, True)
        obj64, objdec = objective(model, point), objective(model, point, True)
        output[label] = {"exact_binary64_input_rows": binary64, "exact_decimal_lp_rows": decimal_lp,
                         "objective_exact_binary64_inputs": float(obj64), "objective_exact_decimal_lp_inputs": float(objdec),
                         "reported_objective_minus_exact_binary64": float(F.from_float(reported) - obj64),
                         "objective_rational_binary64": str(obj64), "objective_rational_decimal_lp": str(objdec)}
        private[label] = {"violated_rows": [(i, str(v)) for i, v in violations],
                          "decimal_lp_violated_rows": [(i, str(v)) for i, v in decimal_violations]}
        if label == "integer_rounded_copy":
            output["fixed_rounded_integer_pattern_row_obstructions"] = [fixed_integer_row_obstruction(model, rounded, i) for i, _ in decimal_violations]
    output["rounded_objective_minus_stored_exact"] = float(objective(model, rounded) - objective(model, x))
    output["exact_integer_primal_feasible_binary64_model"] = bool(len(changed) == 0 and output["max_bound_residual"] == 0 and output["stored"]["exact_binary64_input_rows"]["all_rows_exactly_satisfied"])
    output["exact_integer_primal_feasible_decimal_lp_model"] = bool(len(changed) == 0 and output["max_bound_residual"] == 0 and output["stored"]["exact_decimal_lp_rows"]["all_rows_exactly_satisfied"])
    private["fractional_binary_details"] = []
    for index in changed:
        involved = np.flatnonzero(model["cols"] == index)
        private["fractional_binary_details"].append({"variable": "x" + str(index), "stored": float(x[index]),
            "rounded": float(rounded[index]), "objective_coefficient": float(model["objective"][index]),
            "rows": [{"row": int(model["rows"][k]), "coefficient": model["tokens"][k],
                      "sense": model["senses"][model["rows"][k]], "rhs": model["rhs_tokens"][model["rows"][k]]} for k in involved]})
    return output, private


def log_summary(text):
    def one(pattern):
        found = re.findall(pattern, text, re.M)
        need(len(found) == 1, "unique_log_stat:" + pattern)
        return found[0]
    nodes, iterations, seconds, work = one(r"^Explored (\d+) nodes \((\d+) simplex iterations\) in ([\d.]+) seconds \(([\d.]+) work units\)")
    calls, callback_seconds = one(r"^User-callback calls (\d+), time in user-callback ([\d.]+) sec")
    rows, cols, nnz = one(r"^Presolved: (\d+) rows, (\d+) columns, (\d+) nonzeros")
    root_objective, root_iterations, root_seconds, root_work = one(r"^Root relaxation: objective ([\deE+.-]+), (\d+) iterations, ([\d.]+) seconds \(([\d.]+) work units\)")
    final_obj, final_bound, final_gap = one(r"^Best objective ([\deE+.-]+), best bound ([\deE+.-]+), gap ([\d.]+)%")
    start = re.findall(r"^Loaded user MIP start with objective ([\deE+.-]+)", text, re.M)
    start_time = re.findall(r"^Processed MIP start in ([\d.]+) seconds \(([\d.]+) work units\)", text, re.M)
    presolve_time = one(r"^Presolve time: ([\d.]+)s")
    concurrent = one(r"^(Deterministic concurrent LP optimizer: .*)$")
    winner = one(r"^Solved with (.*)$")
    cuts = {}
    block = text.split("Cutting planes:\n")[-1].split("\n\n")[0] if "Cutting planes:\n" in text else ""
    for kind, count in re.findall(r"^  ([A-Za-z -]+): (\d+)$", block, re.M):
        cuts[kind] = int(count)
    return dict(nodes=int(nodes), simplex_iterations=int(iterations), reported_seconds=float(seconds),
                printed_work_units=float(work), callback_calls=int(calls), callback_seconds=float(callback_seconds),
                presolved_rows=int(rows), presolved_columns=int(cols), presolved_nonzeros=int(nnz),
                root_objective_printed=float(root_objective), root_iterations=int(root_iterations), root_seconds=float(root_seconds),
                root_work_units_printed=float(root_work), loaded_start_objective_printed=float(start[0]) if start else None,
                start_processing_seconds_printed=float(start_time[0][0]) if start_time else None,
                presolve_seconds=float(presolve_time), root_concurrency=concurrent, root_winner=winner,
                final_objective_printed=float(final_obj), final_bound_printed=float(final_bound), final_gap_percent_printed=float(final_gap),
                cuts=cuts, numerical_warning_flags={key: phrase in text.lower() for key, phrase in {
                    "numerical_trouble":"numerical trouble", "unscaled_primal":"unscaled primal violation",
                    "unscaled_dual":"unscaled dual violation", "large_matrix":"large matrix coefficient range"}.items()})


def main(archive_path, public_output, private_output=None):
    raw = Path(archive_path).read_bytes()
    need(len(raw) == 32439807 and hashlib.sha256(raw).hexdigest() == SHA, "ZIP_identity")
    solutions, children = {}, {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        manifest = json.loads(z.read("forensic-manifest.json"))
        need(manifest["model_sha256"] == MODEL_SHA and manifest["sha256"]["model.private.lp.gz"] == MODEL_SHA, "original_model_hash")
        need(len(z.namelist()) == len(set(z.namelist())), "unique_archive_names")
        need(set(z.namelist()) == set(manifest["sha256"]) | {"forensic-manifest.json"}, "manifest_set")
        for name, expected in manifest["sha256"].items():
            need(hashlib.sha256(z.read(name)).hexdigest() == expected, "member_hash:" + name)
        for i in range(50, 54):
            child = json.loads(z.read(f"runs/{i}/child.json"))
            need(hashlib.sha256(z.read(f"runs/{i}/child.json")).hexdigest() == CHILD_SHA[i], "previously_received_child_seal")
            children[i] = child
            need(child["gurobi_log"]["log_sha256"] == manifest["sha256"][f"runs/{i}/gurobi.private.log"], "historical_log_seal")
            raw_solution = gzip.decompress(z.read(f"runs/{i}/solution.private.json.gz"))
            need(len(raw_solution) < 512 * 2**20, "solution_size")
            solution = json.loads(raw_solution)
            need(solution["mip_sha256"] == manifest["model_sha256"] and solution["objective_sense"] == "MINIMIZE", "solution_binding")
            need(solution["objective"] == child["result"]["solve"]["primal"], "solution_objective")
            names, values = solution["variables"].keys(), solution["variables"].values()
            need(len(solution["variables"]) == N and all(name == f"x{index}" for index, name in enumerate(names)), "exact_solution_names_and_order")
            x = np.fromiter(values, dtype=np.float64, count=N)
            need(np.isfinite(x).all(), "finite_vector")
            solutions[i] = x
            del solution, raw_solution
            gc.collect()
        need(len({c["result"]["mathematical_signature_sha256"] for c in children.values()}) == 1, "common_mathematical_signature")
        active = np.logical_or.reduce([x != 0 for x in solutions.values()])
        with io.TextIOWrapper(gzip.GzipFile(fileobj=z.open("model.private.lp.gz"))) as stream:
            model = parse_lp(stream, active)
        print("PARSED_MODEL_AND_FOUR_VECTORS", flush=True)
        rows, private_rows = [], []
        for i, x in solutions.items():
            r = children[i]["result"]
            diag, private = diagnostics(model, x, r["solve"]["primal"])
            need(math.isclose(diag["max_integrality_residual"], r["independent_feasibility"]["max_integrality_residual"], rel_tol=1e-12, abs_tol=1e-18), "integrality_summary_parity")
            need(math.isclose(diag["stored"]["objective_exact_binary64_inputs"], r["solve"]["primal"], rel_tol=1e-12, abs_tol=1e-12), "objective_summary_parity")
            logs = log_summary(z.read(f"runs/{i}/gurobi.private.log").decode())
            need(logs["nodes"] == r["solve"]["node_count"], "node_log_parity")
            rows.append({"job_id": str(3675+i), "method": children[i]["cell"]["method"], "threads": children[i]["cell"]["threads"],
                "child_sha256": manifest["sha256"][f"runs/{i}/child.json"], "solution_sha256_observed_at_collection": manifest["sha256"][f"runs/{i}/solution.private.json.gz"],
                "historically_sealed_log_sha256": manifest["sha256"][f"runs/{i}/gurobi.private.log"], "diagnostics": diag, "log": logs})
            private_rows.append({"job_id": str(3675+i), "details": private})
            print("AUDITED", rows[-1]["job_id"], "exact_primal", diag["exact_integer_primal_feasible_decimal_lp_model"], "rounded_max", diag["integer_rounded_copy"]["exact_decimal_lp_rows"]["max_row_residual"], flush=True)
        contrasts = []
        g = solutions[51]
        for index in (50, 52, 53):
            control = solutions[index]
            dg = objective(model, g) - objective(model, control)
            rounded = control.copy()
            rounded[model["binary"]] = np.rint(rounded[model["binary"]])
            contrasts.append({"control_job_id": str(index+3675), "G_minus_control_exact_binary64_objective": float(dg),
                "G_minus_control_percent": float(100 * dg / abs(objective(model, control))),
                "G_minus_rounded_control_objective": float(objective(model, g) - objective(model, rounded)),
                "different_coordinate_count": int(np.count_nonzero(g != control)),
                "different_rounded_binary_count": int(np.count_nonzero(g[model["binary"]] != rounded[model["binary"]])),
                "different_continuous_coordinate_count": int(np.count_nonzero(g[~model["binary"]] != control[~model["binary"]]))})
        public = {"protocol": "pr89_m12_existing_raw_vector_exact_arithmetic_v1", "date": "2026-11-01", "archive_sha256": SHA,
                  "auditor_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "offline_environment": {"python": sys.version.split()[0], "numpy": np.__version__, "arithmetic": "fractions.Fraction; exact integer ratios, not extended-precision approximation"},
                  "model_sha256": manifest["model_sha256"], "member_hashes_checked": len(manifest["sha256"]),
                  "model": {"variables": N, "rows": 2400, "nonzeros": len(model["coefficients"]), "binary_variables": int(model["binary"].sum()),
                            "continuous_variables": int((~model["binary"]).sum()), "original_file_sense": "MAXIMIZE", "runtime_contract_sense": "MINIMIZE",
                            "min_nonzero_abs_matrix_coefficient": float(np.min(np.abs(model["coefficients"]))), "max_abs_matrix_coefficient": float(np.max(np.abs(model["coefficients"])))},
                  "rows": rows, "objective_contrasts": contrasts, "B_two_and_four_thread_numeric_vectors_equal": bool(np.array_equal(solutions[50], solutions[52])), "raw_variable_values_or_rows_exported": False,
                  "no_solver_import_or_optimization": True, "optimization_calls_added": 0, "campaign_modified": False,
                  "scientific_reporting_eligible": False, "exact_optimality_certified": False,
                  "exact_arithmetic_scope": "all original rows, domains and objective for the four stored points and their in-memory integer-rounded copies; binary64 input and decimal LP coefficient interpretations; no dual proof"}
        Path(public_output).write_text(json.dumps(public, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
        if private_output is not None:
            Path(private_output).write_text(json.dumps(private_rows, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
        print("PUBLIC_SUMMARY_SAVED_PRIVATE_VALUES_RETAINED_LOCALLY", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path)
    args = parser.parse_args()
    need(not args.public_output.exists(), "preserve_existing_public_output")
    need(args.private_output is None or not args.private_output.exists(), "preserve_existing_private_output")
    main(args.archive, args.public_output, args.private_output)
