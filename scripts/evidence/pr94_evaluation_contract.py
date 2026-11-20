"""Full-matrix evaluation identities and policy; no solver or scheduler calls."""

import base64
import csv
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import pr89_cpu_temporal as temporal

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs/research/solver-seed-extension-v2"
CHECKPOINT = "a1868134028694e0f807b5627100a77fcd1dc41e6c884b176290caee253a4028"
PROTOCOL = "pr94_full_matrix_evaluation_v2"
THRESHOLDS = temporal.THRESHOLDS
CHILD_DEADLINE = 3780
JOB_WALL = 14400
ALLOW_ABSTENTION = True
BASELINE_RECEIPT_SHA = (
    "dd1a553b453289b23dbed3d52bd4bd7e0ac93eb2b4283597b788e406fcab6825"
)


def need(value, code):
    if not value:
        raise ValueError(code)


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Recorder(temporal.Recorder):
    """Preserve the qualified recorder; qualify only the 1h horizon for this study."""

    def finish(self):
        value = super().finish()
        temporal.validate(value)
        value["analysis_horizons_seconds"] = [3600]
        value["later_horizons_are_outside_evaluation_budget"] = True
        return value


@lru_cache(maxsize=1)
def matrix():
    raw = (PACKAGE / "planned-cells.csv").read_bytes()
    plan = json.loads((PACKAGE / "plan.json").read_bytes())
    need(sha(raw) == plan["cells_sha256"], "full_matrix_csv_hash")
    rows = list(csv.DictReader(raw.decode().splitlines()))
    need(len(rows) == 144, "full_matrix_count")
    result = {}
    for row in rows:
        native = {
            "cell_id": row["cell_id"],
            "parent": row["parent"],
            "method": row["method"],
            "seed": int(row["seed"]),
            "threads": int(row["threads"]),
            "time_limit_seconds": int(row["time_limit_seconds"]),
            "mip_gap_fraction": 1e-4,
            "model_sha256": row["model_sha256"],
            "effective_objective_sense": "MINIMIZE",
        }
        need(row["checkpoint_sha256"] == CHECKPOINT, "matrix_checkpoint")
        need(row["new_solve"] == "True", "fresh_matrix_only")
        need(native["cell_id"] not in result, "duplicate_cell")
        result[native["cell_id"]] = native
    need(len(plan["groups"]) == 48, "group_count")
    need(
        {c for g in plan["groups"] for c in g["cells"]} == set(result),
        "group_cell_coverage",
    )
    return plan, result


@lru_cache(maxsize=1)
def baseline_parameters():
    raw = (ROOT / "docs/evidence/pr86/job3522/public_return.json").read_bytes()
    need(sha(raw) == BASELINE_RECEIPT_SHA, "baseline_receipt_hash")
    member = json.loads(raw)["members"]["run/attempt-0/child.json"]
    decoded = base64.b64decode(member["base64"], validate=True)
    need(sha(decoded) == member["sha256"], "baseline_parameter_member")
    return json.loads(decoded)["result"]["parameters"]


def parameters(cell):
    _, cells = matrix()
    need(cell == cells.get(cell.get("cell_id")), "cell_not_in_full_matrix")
    need(type(cell["threads"]) is int and type(cell["seed"]) is int, "typed_parameters")
    need(cell["threads"] == 1 and cell["seed"] in (42, 43, 44), "solver_policy")
    need(cell["time_limit_seconds"] == 3600, "solver_budget")
    return {
        **baseline_parameters(),
        "Threads": 1,
        "Seed": cell["seed"],
        "TimeLimit": 3600,
        "MIPGap": 1e-4,
        "SoftMemLimit": 48,
    }


def validate_start(binding, starts):
    """R/G may abstain together, but cannot silently change their frozen budget."""
    groups = []
    n = binding["binary_variables"]
    need(type(n) is int and n > 0, "binary_support_size")
    expected = 0 if binding["abstained"] else min(n, 20000, max(1, n // 10))
    need(binding["selected_support"] == expected, "selection_policy")
    for method, key in (("M1", "root_lp"), ("M2", "gnn")):
        selected = starts[key]["assignments"]
        need(isinstance(selected, list), "assignment_list")
        names = [a["variable_name"] for a in selected]
        need(len(names) == len(set(names)), "duplicate_variable")
        need(
            all(isinstance(n, str) and n for n in names)
            and all(type(a["value"]) is int and a["value"] in (0, 1) for a in selected),
            "binary_start",
        )
        canonical = json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()
        need(
            sha(canonical) == binding[method + "_assignment_sha256"], "assignment_hash"
        )
        need(len(selected) == binding["selected_support"], "support_count")
        need(
            sum(a["value"] for a in selected) == binding["positive_assignments"],
            "positive_count",
        )
        groups.append(set(names))
    # R ranks variables by the root LP, so its selected names may differ from G.
    # The historical matching contract fixes cardinality and positive count.
    need(len(groups[0]) == len(groups[1]), "R_G_support_cardinality_differs")
    need(type(binding["abstained"]) is bool, "abstention_type")
    need(
        binding["abstained"] == (binding["selected_support"] == 0), "abstention_support"
    )
    need(binding["abstained"] or binding["positive_assignments"] > 0, "guided_positive")


def validate_result(cell, result, binding):
    expected = parameters(cell)
    need(
        type(result["optimization_calls"]) is int and result["optimization_calls"] == 1,
        "optimization_count",
    )
    need(result["method"] == cell["method"], "result_method")
    need(result["mip_sha256"] == cell["model_sha256"], "result_model")
    need(result["solver_version"] == [13, 0, 1], "solver_version")
    need(result["effective_objective_sense"] == "MINIMIZE", "result_sense")
    need(
        result["fresh_model"] is True
        and result["mathematical_model_unchanged"] is True,
        "fresh_model",
    )
    need(
        all(result["parameters"][k] == v for k, v in expected.items()),
        "result_parameters",
    )
    need(result["scientific_reporting_eligible"] is False, "result_reporting")
    need(
        result["mathematical_signature_sha256"]
        == binding["mathematical_signature_sha256"],
        "model_signature",
    )
    need(result["gate_status"] == "passed", "result_gate")
    need(result["callback_errors"] == [], "callback_failure")
    status = result["solve"]["solve_status_code"]
    need(type(status) is int and status in (2, 3, 8, 9, 10, 16), "result_status")
    need(math.isfinite(result["solve"]["solver_runtime_seconds"]), "runtime")
    value = result["temporal_evidence"]
    stripped = {
        k: v
        for k, v in value.items()
        if k
        not in {
            "analysis_horizons_seconds",
            "later_horizons_are_outside_evaluation_budget",
        }
    }
    temporal.validate(stripped)
    start = result["start"]
    if cell["method"] == "M0":
        need(start["submitted_assignments"] == 0, "control_start")
    else:
        need(
            start["assignment_sha256"]
            == binding[cell["method"] + "_assignment_sha256"],
            "result_start_hash",
        )
        need(
            start["submitted_assignments"] == binding["selected_support"],
            "result_support",
        )
        need(
            start["positive_assignments"] == binding["positive_assignments"],
            "result_positives",
        )
