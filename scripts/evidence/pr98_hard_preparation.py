"""Prepare five additional hard parents once, reusing H25's completed pilot.

The author operates Slurm. This adapter has no evaluation or training path.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

import pr94_isolated_preparation as flow
import pr98_hard_inputs as inputs
import pr98_hard_pilot as pilot
import pr98_pilot_deadline_recovery as prior
import pr98_pilot_license_recovery as licensing

need = inputs.require
NEW = ("H0", "H5", "H10", "H15", "H20")
ALL = (*NEW, "H25")
H25_STAGE = inputs.EVIDENCE / "pr98-hard.PMt7bKui"
H25_PREFLIGHT = "497530c4c9eba832756fe45bd7a09354e92a71b09e3e73a021e28b5ceec33d36"
CLAIM = "pr98-hard-five-preparation.claim.json"
REFERENCE = inputs.ROOT / "docs/evidence/pr98/h0-reference-20261118/reference.json"
BUDGET = {
    "new_parents": list(NEW),
    "new_root_calls_maximum": 5,
    "root_solver_seconds": 600,
    "new_forward_calls_maximum": 5,
    "training_calls": 0,
    "evaluation_calls": 0,
    "physical_cores": 4,
    "memory_GiB": 64,
    "V100s": 1,
    "job_wall_seconds": 10800,
    "per_parent_deadline_seconds": 1440,
    "automatic_retry": False,
}
RESULT_HASHES = {
    "c1-M0": "b8ed5f2556247659d2822ab5933840363f7dbc4538b6602e809b0fd3d39b709e",
    "c1-M1": "f344695fbdb483d3db706b3a5446fa5e3e7919ccea785c4585e0141b4ff739e6",
    "c1-M2": "cfc5465a5d84b5efe1d923e7268febd885599e39a477e80988f65078e12b3254",
    "c2-M0": "a8ddeb61513956c35fbfd889dce731d77d77882f252ecc3de03ced4333ac7a6f",
    "c2-M1": "cf865a111c9bdcca0bd8f3e86affa9d7e06fb46ccda430f5ce2a4d6471f5e123",
    "c2-M2": "d0a7b9f96943d863a183e46aac91bc74e3dd80a5b683f46cc37dc680443c4aa9",
}


def h25_review(fresh=False):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    need(
        flow.command(
            ["git", "-C", str(H25_STAGE / "source"), "rev-parse", "HEAD"], env=env
        )
        == "072b7a78f1d404bd9360640b6950e3b430c07bb5",
        "H25_source",
    )
    need(
        not flow.command(
            [
                "git",
                "-C",
                str(H25_STAGE / "source"),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            env=env,
        ),
        "H25_dirty",
    )
    need(inputs.digest(H25_STAGE / "preflight.json") == H25_PREFLIGHT, "H25_preflight")
    approval = inputs.read(H25_STAGE / "deadline-recovery.json")
    need(
        approval == inputs.read(inputs.EVIDENCE / prior.CLAIM)
        and approval["budget"] == prior.BUDGET,
        "H25_approval",
    )
    need(
        inputs.read(H25_STAGE / "pilot-submission.json")["job_id"] == "3906", "H25_job"
    )
    row = inputs.read(H25_STAGE / "inputs.private.json")["models"]["H25"]
    prep = H25_STAGE / "run/pilot/preparation"
    receipt, _ = pilot.verify_artifacts(prep, row)
    need(
        all(receipt[k] == v for k, v in prior.ARTIFACT_HASHES.items()), "H25_artifacts"
    )
    need(
        inputs.read(H25_STAGE / "run/pilot/complete.json")["job_id"] == "3906",
        "H25_complete",
    )
    for key, digest in RESULT_HASHES.items():
        path = H25_STAGE / "run/pilot" / key / "result.private.json"
        need(inputs.digest(path) == digest, "H25_result_seal")
        result = inputs.read(path)
        need(
            result["gate_status"] == "passed"
            and result["independent_feasibility"]["valid"],
            "H25_result_gate",
        )
    if fresh:
        a = flow.accounting(H25_STAGE, "pilot")
        need(
            a["terminal"]
            and a["job_id"] == "3906"
            and all(
                r["State"] == "COMPLETED" and r["ExitCode"] == "0:0" for r in a["rows"]
            ),
            "H25_accounting",
        )
    return {
        "job_id": "3906",
        "source": "072b7a78f1d404bd9360640b6950e3b430c07bb5",
        "preflight_sha256": H25_PREFLIGHT,
        "artifacts": prior.ARTIFACT_HASHES,
        "result_sha256": RESULT_HASHES,
        "approval_sha256": inputs.digest(H25_STAGE / "deadline-recovery.json"),
    }


def workspace_environment(stage, create=False):
    root = stage / "runtime"
    names = ("tmp", "cache", "cuda", "torch", "extensions", "matplotlib")
    if create:
        root.mkdir()
        for name in names:
            (root / name).mkdir()
    need(root.is_dir() and not root.is_symlink(), "runtime_directory")
    for name in names:
        path = root / name
        need(
            path.is_dir()
            and not path.is_symlink()
            and path.resolve().is_relative_to(stage.resolve()),
            "runtime_cache_path",
        )
    value = {
        "TMPDIR": str(root / "tmp"),
        "TMP": str(root / "tmp"),
        "TEMP": str(root / "tmp"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "CUDA_CACHE_PATH": str(root / "cuda"),
        "TORCH_HOME": str(root / "torch"),
        "TORCH_EXTENSIONS_DIR": str(root / "extensions"),
        "MPLCONFIGDIR": str(root / "matplotlib"),
    }
    os.environ.update(value)
    return value


def admitted(stage, expected, alias=None):
    need(inputs.digest(stage / "plan.json") == expected, "plan_hash")
    plan = inputs.read(stage / "plan.json")
    need(
        plan["runtime_environment"] == workspace_environment(stage),
        "runtime_environment",
    )
    need(
        plan["source_commit"] == inputs.source_commit()
        and plan["budget"] == BUDGET
        and plan["versions"] == flow.versions()
        and plan["license"] == licensing.license_binding()
        and plan["reference_sha256"] == inputs.digest(REFERENCE),
        "plan_drift",
    )
    need(
        plan["private_inputs_sha256"] == inputs.digest(stage / "inputs.private.json"),
        "private_inputs",
    )
    config = inputs.read(stage / "inputs.private.json")
    if alias is None:
        return plan, config
    need(alias in ALL, "hard_alias")
    row = config["models"][alias]
    model = inputs.data_file(Path(row["model"]), inputs.DATA)
    checkpoint = inputs.data_file(Path(config["checkpoint"]), inputs.DATA)
    need(
        inputs.digest(model) == row["model_sha256"]
        and (row["decoded_bytes"], row["decoded_sha256"]) == inputs.LP_REFERENCE[alias]
        and inputs.digest(checkpoint) == inputs.CHECKPOINT,
        "frozen_inputs",
    )
    return row, model, checkpoint


def freeze(stage, preflight):
    need(inputs.digest(stage / "preflight.json") == preflight, "preflight_hash")
    returned = inputs.read(stage / "preflight.json")
    config = inputs.read(stage / "inputs.private.json")
    reference = inputs.read(REFERENCE)
    need(
        reference["decoded_sha256"] == inputs.LP_REFERENCE["H0"][1]
        and reference["official_directory_exact_match"]
        and reference["crc_verified"],
        "H0_reference",
    )
    need(
        returned["source_commit"] == inputs.source_commit()
        and set(config["models"]) == set(ALL)
        and returned["private_inputs_sha256"]
        == inputs.digest(stage / "inputs.private.json"),
        "six_hard_inputs",
    )
    for alias in ALL:
        need(
            returned["rows"][alias]["status"]
            in {"PaScal_LP_bytes_matched", "MILPBench_LP_bytes_matched"},
            "hard_reference",
        )
    flow.storage(stage, admission=True)
    plan = {
        "protocol": "pr98_five_hard_preparation_v1",
        "runtime_environment": workspace_environment(stage, create=True),
        "source_commit": inputs.source_commit(),
        "private_inputs_sha256": inputs.digest(stage / "inputs.private.json"),
        "preflight_sha256": preflight,
        "budget": BUDGET,
        "versions": flow.versions(),
        "license": licensing.license_binding(),
        "reference_sha256": inputs.digest(REFERENCE),
        "H25": h25_review(fresh=True),
        "scientific_reporting_eligible": False,
    }
    inputs.write_once(stage / "plan.json", plan)
    print("PR98_HARD_PLAN_SHA256=" + inputs.digest(stage / "plan.json"))


def submit(stage, expected, decision):
    need(
        decision == "AUTORIZO PREPARACAO CINCO HARD PR98",
        "specific_preparation_decision",
    )
    plan, config = admitted(stage, expected)
    need(plan["H25"] == h25_review(fresh=True), "H25_evidence_changed")
    flow.storage(stage, admission=True)
    approval = {"plan_sha256": expected, "budget": BUDGET, "decision": decision}
    inputs.write_once(inputs.EVIDENCE / CLAIM, approval)
    inputs.write_once(stage / "hard-preparation-approval.json", approval)
    target = stage / "run/H25/preparation"
    target.mkdir(parents=True)
    source = H25_STAGE / "run/pilot/preparation"
    for name in (*pilot.ARTIFACTS.values(), "artifact-receipt.json"):
        with (source / name).open("rb") as r, (target / name).open("xb") as w:
            shutil.copyfileobj(r, w, 1024**2)
            w.flush()
            os.fsync(w.fileno())
    pilot.verify_artifacts(target, config["models"]["H25"])
    wrapped = shlex.join(
        [
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "batch",
            str(stage),
            expected,
        ]
    )
    raw = flow.command(
        [
            "sbatch",
            "--parsable",
            "--hold",
            "--no-requeue",
            "--partition=batch",
            "--nodes=1-1",
            "--ntasks=1",
            "--cpus-per-task=4",
            "--hint=nomultithread",
            "--mem=64G",
            "--gres=gpu:1",
            "--time=03:00:00",
            "--job-name=cfl_pr98_hardprep",
            "--export=ALL,GRB_LICENSE_FILE=" + str(licensing.LICENSE_PATH),
            "--chdir=" + str(inputs.ROOT),
            "--output=" + str(stage / "hardprep-%j.private.out"),
            "--error=" + str(stage / "hardprep-%j.private.err"),
            "--wrap=" + wrapped,
        ],
        env=pilot.clean_env(),
    )
    inputs.write_once(stage / "hardprep-sbatch.private.json", {"raw": raw})
    job = raw.split(";", 1)[0]
    need(re.fullmatch("[0-9]+", job), "ambiguous_submission_preserve_claim")
    inputs.write_once(
        stage / "hardprep-submission.json", {"job_id": job, "plan_sha256": expected}
    )
    text = flow.command(["scontrol", "show", "job", job, "-o"])
    fields = dict(p.split("=", 1) for p in text.split() if "=" in p)
    need(fields.get("TimeLimit") == "03:00:00", "held_time")
    # Reuse the existing exact four-core/64-GiB/one-GPU held checks.
    checked = flow.held_profile(
        text.replace("TimeLimit=03:00:00", "TimeLimit=01:00:00"), job, "guidance"
    )
    inputs.write_once(
        stage / "hardprep-held-profile.private.json",
        {**checked, "TimeLimit": "03:00:00"},
    )
    flow.command(["scontrol", "release", job])
    print(json.dumps({"job_id": job, "plan_sha256": expected, "new_parents": NEW}))


def runtime(stage, expected):
    plan, _ = admitted(stage, expected)
    approval = inputs.read(stage / "hard-preparation-approval.json")
    need(
        approval == inputs.read(inputs.EVIDENCE / CLAIM)
        and approval["budget"] == BUDGET
        and approval["plan_sha256"] == expected,
        "approval",
    )
    job, gate, allocation = flow.allocation("guidance", stage)
    need(
        inputs.read(stage / "hardprep-submission.json")
        == {"job_id": job, "plan_sha256": expected},
        "job_identity",
    )
    return plan, job, gate, allocation


def batch(stage, expected):
    import resource

    from paired_memory_runtime_v2 import supervise

    _, job, gate, allocation = runtime(stage, expected)
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * inputs.CHUNK, 512 * inputs.CHUNK))
    inputs.write_once(
        stage / "run/batch.json", {"job_id": job, "allocation": allocation}
    )
    for alias in NEW:
        folder = stage / "run" / alias
        folder.mkdir()
        observed = supervise(
            [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "child",
                str(stage),
                expected,
                "--alias",
                alias,
            ],
            folder / "console.private.log",
            1440,
            gate,
        )
        inputs.write_once(folder / "supervision.private.json", observed)
        need(
            observed["guard_stop"] is None and observed["child_exit_code"] == 0,
            "hard_preparation_failed_preserve_evidence",
        )
    inputs.write_once(
        stage / "run/complete.json", {"job_id": job, "plan_sha256": expected}
    )


def child(stage, expected, alias):
    need(alias in NEW, "new_parent")
    _, _, gate, _ = runtime(stage, expected)
    row, model, checkpoint = admitted(stage, expected, alias)
    folder = stage / "run" / alias / "preparation"
    folder.mkdir()
    pilot.prepare(folder, model, row, checkpoint, gate)
    pilot.verify_artifacts(folder, row)


def collect(stage, expected):
    plan, config = admitted(stage, expected)
    accounting = flow.accounting(stage, "hardprep")
    need(accounting["terminal"], "not_terminal")
    rows = {}
    for alias in ALL:
        folder = stage / "run" / alias / "preparation"
        receipt = None
        if (folder / "artifact-receipt.json").exists():
            receipt, _ = pilot.verify_artifacts(folder, config["models"][alias])
        supervision = stage / "run" / alias / "supervision.private.json"
        rows[alias] = {
            "receipt": receipt,
            "reused_from_job": "3906" if alias == "H25" else None,
            "supervision": inputs.read(supervision) if supervision.exists() else None,
            "root_intent": (folder / "root.intent.json").exists(),
            "forward_intent": (folder / "forward.intent.json").exists(),
        }
    ready = (
        (stage / "run/complete.json").exists()
        and all(
            r["State"] == "COMPLETED" and r["ExitCode"] == "0:0"
            for r in accounting["rows"]
        )
        and all(v["receipt"] is not None for v in rows.values())
        and all(
            rows[a]["supervision"]["child_exit_code"] == 0
            and rows[a]["supervision"]["guard_stop"] is None
            for a in NEW
        )
    )
    report = {
        "plan_sha256": expected,
        "accounting": accounting,
        "rows": rows,
        "ready_for_review": ready,
        "scope": "preparation_only_no_evaluations",
        "root_intents": sum(rows[a]["root_intent"] for a in NEW),
        "forward_intents": sum(rows[a]["forward_intent"] for a in NEW),
        "source_commit": plan["source_commit"],
    }
    path = stage / "hard-preparation-return.json"
    if path.exists():
        previous = inputs.read(path)
        need(previous["plan_sha256"] == expected, "existing_return_plan")
        report = previous
    else:
        inputs.write_once(path, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    print("PR98_HARD_RETURN_SHA256=" + inputs.digest(path))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("freeze", "submit", "batch", "child", "collect"))
    p.add_argument("stage", type=Path)
    p.add_argument("expected_sha256")
    p.add_argument("--decision")
    p.add_argument("--alias")
    a = p.parse_args()
    os.umask(0o077)
    stage = inputs.site_stage(a.stage)
    if a.command == "freeze":
        freeze(stage, a.expected_sha256)
    elif a.command == "submit":
        submit(stage, a.expected_sha256, a.decision)
    elif a.command == "batch":
        batch(stage, a.expected_sha256)
    elif a.command == "child":
        child(stage, a.expected_sha256, a.alias)
    else:
        collect(stage, a.expected_sha256)


if __name__ == "__main__":
    main()
