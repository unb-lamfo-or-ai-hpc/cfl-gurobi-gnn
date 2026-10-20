"""Frozen PR87 inputs, source binding and full-run review; no solver imports."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

import audit_sprint_c_numeric as admitted

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs/experiments/pr87_matched_gpu_v1.json"
BASE = Path("/raid/vrcelestino/data/cfl-mvp2-evidence/pr87")
DATA_ROOT = Path("/raid/vrcelestino/data/cfl-gurobi-gnn/data")
MERGED_BASE = "3ac1883d081684acb36ba3855cd634e057a11c66"


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(raw)
    return sha(raw)


def source():
    result = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    commit = result.stdout.strip()
    require(len(commit) == 40, "source_commit")
    result = subprocess.run(
        ["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=True,
    )
    require(not result.stdout.strip(), "dirty_source")
    return commit


def records():
    selected = admitted.selected_parents(admitted.source_receipt())
    with (REPO / "docs/evidence/e0/pr85/parents.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        audited = {
            r["parent"]: r for r in csv.DictReader(stream) if r["admitted"] == "True"
        }
    require(
        set(selected) == set(audited) and len(selected) == 54,
        "admitted_parent_identity",
    )
    result = []
    for parent, row in sorted(selected.items()):
        fold, role = admitted.split_for(parent)
        require(role == row["role"] == audited[parent]["role"], "partition_identity")
        result.append(
            {
                "parent": parent,
                "role": role,
                "fold": fold,
                "graph": row["graph"],
                "root": row["root"],
                "label": row["label"],
                "objective_sense": "MINIMIZE",
            }
        )
    require(
        Counter(r["role"] for r in result)
        == {"train": 34, "validation": 10, "test": 10},
        "partition_counts",
    )
    return result


def plan(commit):
    config = read(CONFIG)
    require(config["seeds"] == [42] and config["global_batch"] == 4, "frozen_config")
    require(
        config["budget"]
        == {
            "maximum_jobs": 2,
            "maximum_training_runs": 2,
            "sequential_reserved_hours": 24,
            "gpu_hours": 60,
            "physical_core_reserved_hours": 240,
            "optimization_calls": 0,
        },
        "budget",
    )
    return {
        "protocol": config,
        "source_commit": commit,
        "base_merge": MERGED_BASE,
        "records": records(),
        "resource_budget_approved": False,
        "automatic_retry": False,
        "scientific_reporting_eligible": False,
    }


def validate_authorization(value, frozen, plan_sha, bindings_sha):
    """Bind a separately recorded author decision, not a plan or a CPU approval.

    This receipt is an audit record, not cryptographic proof of human identity.
    No prepare/submit action is allowed to invent the researcher's decision.
    """
    require(
        set(value)
        == {
            "package_id",
            "execution_authorized",
            "plan_sha256",
            "bindings_sha256",
            "source_commit",
            "budget",
            "seed",
            "decision_reference",
            "approved_at_utc",
            "automatic_retry",
        },
        "authorization_schema",
    )
    require(
        value["package_id"] == "pr87_gpu_seed42_authorization_v2",
        "gpu_authorization_only",
    )
    require(value["execution_authorized"] is True, "execution_not_authorized")
    require(
        value["automatic_retry"] is False and value["seed"] == 42, "authorization_scope"
    )
    require(
        value["plan_sha256"] == plan_sha and value["bindings_sha256"] == bindings_sha,
        "authorization_plan_or_bindings",
    )
    require(
        value["source_commit"] == frozen["source_commit"]
        and value["budget"] == frozen["protocol"]["budget"],
        "authorization_source_or_budget",
    )
    require(
        isinstance(value["decision_reference"], str)
        and 8 <= len(value["decision_reference"]) <= 500,
        "author_decision_reference",
    )
    approved = datetime.fromisoformat(value["approved_at_utc"].replace("Z", "+00:00"))
    require(
        approved.utcoffset() is not None and approved.utcoffset().total_seconds() == 0,
        "approval_timestamp_utc",
    )
    return value


def validate_result(value, frozen, index):
    require(isinstance(value, dict), "training_result_absent")
    seed, world = frozen["protocol"]["pair_order"][index]
    require(value["state"] == "complete", "incomplete_training")
    require(value["seed"] == seed and value["world_size"] == world, "run_identity")
    require(value["source_commit"] == frozen["source_commit"], "run_source")
    require(
        value["plan_sha256"]
        == sha(
            (
                json.dumps(frozen, sort_keys=True, indent=2, allow_nan=False) + "\n"
            ).encode()
        ),
        "run_plan",
    )
    require(
        value["epochs_completed"] == 100
        and value["optimizer_updates"] == 3400
        and value["global_graph_draws"] == 13600,
        "learning_work",
    )
    require(
        value["validation_parents"] == 10 and value["test_parents"] == 10,
        "evaluation_population",
    )
    require(
        value["optimization_runs_added"] == 0
        and value["scientific_reporting_eligible"] is False,
        "report_scope",
    )
    for key in (
        "initial_state_sha256",
        "schedule_sha256",
        "selected_state_sha256",
        "terminal_state_sha256",
    ):
        require(
            len(value[key]) == 64 and all(c in "0123456789abcdef" for c in value[key]),
            "state_identity",
        )
    for key in (
        "training_loop_seconds",
        "training_validation_checkpoint_seconds",
        "process_wall_seconds",
    ):
        require(
            type(value[key]) in (int, float)
            and math.isfinite(value[key])
            and value[key] > 0,
            "timing",
        )
    require(
        len(value["history"]) == 100
        and [r["epoch"] for r in value["history"]] == list(range(1, 101)),
        "history",
    )
    require(
        all(
            r["optimizer_updates"] == 34
            and r["global_draws"] == 136
            and math.isfinite(r["train_loss"])
            and math.isfinite(r["validation_loss"])
            and r["train_loss"] >= 0
            and r["validation_loss"] >= 0
            for r in value["history"]
        ),
        "epoch_work_or_loss",
    )
    require(
        type(value["best_epoch"]) is int and 1 <= value["best_epoch"] <= 100,
        "best_epoch",
    )
    for which in ("selected", "terminal"):
        threshold = value[which + "_threshold"]
        require(
            type(threshold) in (int, float)
            and math.isfinite(threshold)
            and 0 <= threshold <= 1,
            "threshold",
        )
    for which in ("selected", "terminal"):
        require(
            {r["parent"] for r in value["test"][which]}
            == {r["parent"] for r in frozen["records"] if r["role"] == "test"}
            and len(value["test"][which]) == 10,
            "test_parents_once",
        )
        for row in [*value["test"][which], value["test_pooled"][which]]:
            counts = [row[k] for k in ("tp", "tn", "fp", "fn")]
            require(all(type(n) is int and n >= 0 for n in counts), "confusion_counts")
            tp, tn, fp, fn = counts
            require(
                tp + tn + fp + fn == row["n_targets"] > 0
                and tp + fn == row["n_positive"],
                "target_counts",
            )
            expected = {
                "precision": tp / (tp + fp) if tp + fp else 0,
                "recall": tp / (tp + fn) if tp + fn else 0,
                "f1_score": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
            }
            require(
                all(
                    math.isclose(row[k], x, rel_tol=1e-12, abs_tol=1e-12)
                    for k, x in expected.items()
                ),
                "predictive_metric",
            )
            require(
                row["pr_auc"] is None
                or math.isfinite(row["pr_auc"])
                and 0 <= row["pr_auc"] <= 1,
                "pr_auc",
            )
        require(
            all(
                value["test_pooled"][which][key]
                == sum(r[key] for r in value["test"][which])
                for key in ("tp", "tn", "fp", "fn", "n_targets", "n_positive")
            ),
            "pooled_counts",
        )
    return value
