"""Successor operator workflow with Slurm 22.05 resource validation.

PR75 runtime bytes and existing protocols are unchanged. Public validation is
read-only and solver-free; prepare/status never access LPs or the license.
SPDX-License-Identifier: MIT
"""

import argparse
import os
import re
import sys
from pathlib import Path

import paired_matrix_executor_v2 as matrix

old, contract, require = matrix.old, matrix.contract, matrix.require
site = matrix.workflow
SOURCE = site.SOURCE
BATCH = "scripts/slurm/dasci/submit_paired_matrix_v3.sbs"
PROTOCOL = "paired_matrix_nonblocking_operator_v3"
PROBE_SHA = "ca2381d4a1396f3d40b76b653bd7f81f591b830b5f38df8d77dfc12ecc1f1602"
PROBE = "docs/evidence/pr75/fault-probe-c845ccd6b224/no_solver_fault_probe.json"


class ProfileError(ValueError):
    def __init__(self, field, expected, observed):
        super().__init__("scheduler_profile_mismatch")
        self.detail = {
            "field": field,
            "expected": expected,
            "observed": observed
            if isinstance(observed, str)
            and re.fullmatch(r"[A-Za-z0-9_.,:/+*()=-]{1,160}", observed)
            else None,
        }


class SubmissionError(ValueError):
    def __init__(self, stage, job, cause):
        super().__init__("submission_stopped")
        self.report = {
            "error": "submission_stopped",
            "stage": stage,
            "job_id": job,
            "automatic_retry": False,
            "resource_difference": cause.detail
            if isinstance(cause, ProfileError)
            else None,
            "cause_type": type(cause).__name__,
            "instruction": "preserve_state_and_query_status; do_not_repeat_submit",
        }


def profile_require(value, field, expected, observed):
    if not value:
        raise ProfileError(field, expected, observed)


def singleton(value):
    """Slurm 22.05 prints equal lower/upper bounds as e.g. 1-1."""
    match = re.fullmatch(r"([0-9]+)(?:-([0-9]+))?", value or "")
    if not match or (match[2] is not None and int(match[1]) != int(match[2])):
        return None
    return int(match[1])


def selected_fields(text, names):
    values = {}
    for key, value in re.findall(
        r"(?:^|\s)([A-Za-z][A-Za-z0-9/:_]*)\s*=\s*(\S+)", text
    ):
        if key in names:
            profile_require(key not in values, key, "one_occurrence", "duplicate")
            values[key] = value
    return values


def site_profile():
    """Validate actual single-node consumable-core configuration before sbatch."""
    partition = selected_fields(
        site.command(["scontrol", "show", "partition", "batch", "--oneliner"]),
        {"PartitionName", "Nodes", "TotalNodes", "TotalCPUs", "OverSubscribe"},
    )
    for key, expected in {
        "PartitionName": "batch",
        "Nodes": "dgx-dasci",
        "TotalNodes": "1",
        "TotalCPUs": "80",
        "OverSubscribe": "NO",
    }.items():
        profile_require(
            partition.get(key) == expected,
            "partition." + key,
            expected,
            partition.get(key),
        )
    config = selected_fields(
        site.command(["scontrol", "show", "config"]),
        {"SelectType", "SelectTypeParameters", "TaskPlugin"},
    )
    profile_require(
        config.get("SelectType") == "select/cons_tres",
        "SelectType",
        "select/cons_tres",
        config.get("SelectType"),
    )
    profile_require(
        "CR_CORE_MEMORY" in config.get("SelectTypeParameters", "").split(","),
        "SelectTypeParameters",
        "CR_CORE_MEMORY",
        config.get("SelectTypeParameters"),
    )
    profile_require(
        {"affinity", "cgroup"} <= set(config.get("TaskPlugin", "").split(",")),
        "TaskPlugin",
        "affinity,cgroup",
        config.get("TaskPlugin"),
    )
    node = selected_fields(
        site.command(["scontrol", "show", "node", "dgx-dasci", "--oneliner"]),
        {
            "NodeName",
            "Sockets",
            "CoresPerSocket",
            "ThreadsPerCore",
            "CPUTot",
            "RealMemory",
        },
    )
    for key, expected in {
        "NodeName": "dgx-dasci",
        "Sockets": "2",
        "CoresPerSocket": "20",
        "ThreadsPerCore": "2",
        "CPUTot": "80",
    }.items():
        profile_require(
            node.get(key) == expected, "node." + key, expected, node.get(key)
        )
    profile_require(
        (singleton(node.get("RealMemory")) or 0) >= 65536,
        "RealMemory",
        ">=65536_MiB",
        node.get("RealMemory"),
    )
    return {
        "partition": partition,
        "configuration": config,
        "node": node,
        "physical_cores": 40,
        "logical_cpus": 80,
    }


PUBLIC = {
    "operator_plan.json",
    "operator_approval.json",
    "submission.json",
    "accounting.json",
    "SHA256SUMS.txt",
    "matrix.tar.gz",
}
PROFILE = {
    "partition": "batch",
    "nodes": 1,
    "tasks": 1,
    "cpus_per_task": 16,
    "memory_mib": 65536,
    "wall_seconds": 19800,
    "hint": "nomultithread",
    "gpus": 0,
    "exclusive": False,
    "requeue": False,
}


def digest(path):
    return matrix.adapter.screen.digest(path)


def load(path):
    return old.strict_payload(old.read_bytes(path))


def sync_dir(path):
    # Production is Linux; Windows skips directory fsync in offline fixtures.
    if sys.platform == "linux":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def write(path, value):
    old.write_json(path, value)
    sync_dir(Path(path).parent)


def mkdir(path):
    path.mkdir(mode=0o700, exist_ok=False)
    sync_dir(path.parent)


def reviewed_probe():
    raw = old.read_bytes(SOURCE / PROBE)
    require(contract.sha(raw) == PROBE_SHA)
    value = old.strict_payload(raw)
    require(value["tests_run"] == 25 and value["passed_no_solver_fault_probe"] is True)
    require(all(value[n] == 0 for n in ("errors", "failures", "skipped")))
    for name, sha in value["dependency_sha256"].items():
        path = (
            SOURCE / name
            if name.startswith("tests/")
            else SOURCE / "scripts/evidence" / name
        )
        require(digest(path) == sha)
    require(value["scientific_reporting_eligible"] is False)


def plan_for(head):
    execution = matrix.plan_for(head)
    value = {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "source_commit": head,
        "matrix_plan_sha256": execution["plan_sha256"],
        "installed_executor_probe_sha256": PROBE_SHA,
        "dependency_sha256": {
            **matrix.pins(),
            "paired_matrix_workflow_v3.py": digest(Path(__file__)),
            BATCH: digest(SOURCE / BATCH),
        },
        "scheduler": PROFILE,
        "parent_order": ["easy", "medium"],
        "maximum_submissions": 2,
        "predecessor_failed_job": "3482",
        "installed_hierarchical_qualification_sha256": matrix.evidence.QUALIFICATION_SHA,
        "historical_matrix_submission_ceiling_including_predecessors": 4,
        "prior_authorization_sha256": "ad80043db2f5ae46bd4e957f2a68ec6440736386a5ebb6e712b66380e58cfc9c",
        "maximum_optimization_calls": 10,
        "maximum_optimization_seconds": 36000,
        "concurrent_parent_jobs": 1,
        "held_id_before_release_required": True,
        "independent_easy_review_before_medium_required": True,
        "automatic_retry": False,
        "resource_budget_approved": False,
        "scientific_reporting_eligible": False,
    }
    value["operator_plan_sha256"] = contract.sha(contract.encoded(value))
    return value


def validate_plan(value):
    require(value == plan_for(value["source_commit"]))
    old.strict_payload(contract.encoded(value))
    return value


def approval_template(plan):
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        "source_commit": plan["source_commit"],
        "operator_plan_sha256": plan["operator_plan_sha256"],
        "matrix_approval_sha256": None,
        "maximum_submissions": 2,
        "maximum_optimization_calls": 10,
        "maximum_optimization_seconds": 36000,
        "explicit_resource_budget_and_submission_approved": False,
        "exact_head_four_ci_arms_reviewed": False,
        "scientific_reporting_eligible": False,
    }


def validate_approval(plan, approval, approval_sha, matrix_sha):
    expected = approval_template(plan)
    expected.update(
        matrix_approval_sha256=matrix_sha,
        explicit_resource_budget_and_submission_approved=True,
        exact_head_four_ci_arms_reviewed=True,
    )
    old.hexadecimal(matrix_sha)
    old.hexadecimal(approval_sha)
    require(contract.encoded(approval) == contract.encoded(expected))
    require(contract.sha(contract.encoded(approval)) == approval_sha)


def prepare(directory):
    site.host()
    reviewed_probe()
    execution = matrix.prepare(directory)
    directory = site.location(directory)
    value = plan_for(execution["source_commit"])
    write(directory / "operator_plan.json", value)
    write(directory / "operator_approval.json", approval_template(value))
    return value


def approved(directory, approval_sha):
    value = validate_plan(load(directory / "operator_plan.json"))
    approval = load(directory / "operator_approval.json")
    matrix_sha = digest(directory / "approval.json")
    validate_approval(value, approval, approval_sha, matrix_sha)
    execution = matrix.load_flow(directory, matrix_sha)
    require(execution["plan_sha256"] == value["matrix_plan_sha256"])
    require(value["source_commit"] == site.source_head())
    reviewed_probe()
    recovery = load(directory.parent / "recovery.json")
    require(recovery["successor_operator_plan_sha256"] == value["operator_plan_sha256"])
    require(recovery["successor_operator_approval_sha256"] == approval_sha)
    require(recovery["predecessor_failed_job"] == "3482")
    require(
        recovery["prior_authorization_sha256"] == value["prior_authorization_sha256"]
    )
    require(recovery["predecessor_runtime_not_entered_verified"] is True)
    require(
        recovery["installed_hierarchical_qualification_sha256"]
        == matrix.evidence.QUALIFICATION_SHA
    )
    require(recovery["successor_matrix_approval_sha256"] == matrix_sha)
    return value, matrix_sha


def root_for(sha):
    old.hexadecimal(sha)
    root = matrix.adapter.EVIDENCE_ROOT / "paired-matrix-submission-locks" / sha
    require(root.resolve() == root)
    return root


def binding(directory, plan, approval_sha, matrix_sha):
    return {
        "operator_plan_sha256": plan["operator_plan_sha256"],
        "operator_approval_sha256": approval_sha,
        "matrix_approval_sha256": matrix_sha,
        "directory_sha256": contract.sha(str(directory).encode()),
    }


def state_for(directory, parent):
    require(parent in matrix.PARENTS)
    path = directory / "operator-state" / parent
    require(path.resolve() == path)
    return path


def stop(root, code):
    require(code in {"submission_uncertain", "batch_failed", "collection_failed"})
    try:
        write(root / "STOP.json", {"code": code, "automatic_retry": False})
    except FileExistsError:
        pass


def live(root, matrix_sha):
    require(not (root / "STOP.json").exists())
    require(
        not (
            matrix.adapter.EVIDENCE_ROOT
            / "paired-matrix-locks"
            / matrix_sha
            / "STOP.json"
        ).exists()
    )


def held_profile(text, job):
    """Allowlisted Slurm 22.05 job fields only; never retain raw site text."""
    names = {
        "JobId",
        "JobState",
        "Reason",
        "Priority",
        "Partition",
        "Requeue",
        "Restarts",
        "BatchFlag",
        "NumNodes",
        "NumTasks",
        "NumCPUs",
        "CPUs/Task",
        "TimeLimit",
        "MinMemoryNode",
        "OverSubscribe",
        "TRES",
    }
    values = {}
    for name, value in re.findall(r"(?:^|\s)([A-Za-z][A-Za-z0-9/:_]*)=(\S+)", text):
        if name in names:
            profile_require(name not in values, name, "one_occurrence", "duplicate")
            values[name] = value
    for name in sorted(names - set(values)):
        raise ProfileError(name, "present", None)
    expected = {
        "JobId": job,
        "JobState": "PENDING",
        "Reason": "JobHeldUser",
        "Priority": "0",
        "Partition": "batch",
        "Requeue": "0",
        "Restarts": "0",
        "BatchFlag": "1",
        "NumTasks": "1",
        "CPUs/Task": "16",
        "TimeLimit": "05:30:00",
    }
    for key, value in expected.items():
        profile_require(values[key] == value, key, value, values[key])
    profile_require(
        singleton(values["NumNodes"]) == 1, "NumNodes", "1_or_1-1", values["NumNodes"]
    )
    profile_require(
        singleton(values["NumCPUs"]) in {16, 32},
        "NumCPUs",
        "16_or_32_singleton",
        values["NumCPUs"],
    )
    # Partition NO with CR_CORE_MEMORY allows jobs on disjoint cores of a node.
    # Whole-node allocation is excluded independently by the CPU count above.
    profile_require(
        values["OverSubscribe"] in {"OK", "NO"},
        "OverSubscribe",
        "OK_or_NO",
        values["OverSubscribe"],
    )
    profile_require(
        values["MinMemoryNode"] in {"64G", "65536M"},
        "MinMemoryNode",
        "64G_or_65536M",
        values["MinMemoryNode"],
    )
    tres = {}
    for entry in values["TRES"].split(","):
        key, value = entry.split("=")
        profile_require(
            key not in tres and key in {"cpu", "mem", "node", "billing"},
            "TRES",
            "unique_cpu_mem_node_billing_only",
            None,
        )
        tres[key] = value
    profile_require(
        singleton(tres.get("cpu")) == singleton(values["NumCPUs"]),
        "TRES.cpu",
        values["NumCPUs"],
        tres.get("cpu"),
    )
    profile_require(tres.get("node") == "1", "TRES.node", "1", tres.get("node"))
    profile_require(
        tres.get("mem") in {"64G", "65536M"},
        "TRES.mem",
        "64G_or_65536M",
        tres.get("mem"),
    )
    require("billing" not in tres or re.fullmatch(r"[0-9]+", tres["billing"]))
    values["TRES"] = dict(sorted(tres.items()))
    old.strict_payload(contract.encoded(values))
    return values


def validate_held(value, job):
    tokens = {**value, "TRES": ",".join(k + "=" + v for k, v in value["TRES"].items())}
    require(
        value == held_profile(" ".join(k + "=" + v for k, v in tokens.items()), job)
    )


def submission(directory, parent):
    value = load(state_for(directory, parent) / "submission.json")
    old.keys(
        value,
        "operator_plan_sha256 operator_approval_sha256 matrix_approval_sha256 directory_sha256 parent job_id easy_review_sha256",
    )
    plan, matrix_sha = approved(directory, value["operator_approval_sha256"])
    require(value["parent"] == parent and re.fullmatch(r"[0-9]{1,20}", value["job_id"]))
    expected = binding(directory, plan, value["operator_approval_sha256"], matrix_sha)
    require({k: value[k] for k in expected} == expected)
    root = root_for(value["operator_approval_sha256"])
    require(load(root / "binding.json") == expected)
    require(
        load(root / (parent + ".started"))
        == {"easy_review_sha256": value["easy_review_sha256"]}
    )
    if parent == "easy":
        require(value["easy_review_sha256"] is None)
    else:
        old.hexadecimal(value["easy_review_sha256"])
    return value, root


def easy_review(directory, plan, approval_sha, review_sha):
    old.hexadecimal(review_sha)
    raw = old.read_bytes(directory / "easy.review.json")
    require(contract.sha(raw) == review_sha)
    review = old.strict_payload(raw)
    receipt = validate_return(directory / "return-easy", review["return_sha256"])
    require(
        receipt["ready_for_independent_review"] is True and receipt["parent"] == "easy"
    )
    require(
        review
        == {
            "schema_version": 1,
            "operator_plan_sha256": plan["operator_plan_sha256"],
            "operator_approval_sha256": approval_sha,
            "job_id": receipt["accounting"]["job_id"],
            "return_sha256": review["return_sha256"],
            "independent_review_passed": True,
            "scientific_reporting_eligible": False,
        }
    )
    return review


def submit(directory, approval_sha, parent, review_sha=None):
    site.host()
    require(not os.environ.get("SLURM_JOB_ID"))
    directory = site.location(directory)
    plan, matrix_sha = approved(directory, approval_sha)
    require(parent in matrix.PARENTS)
    try:
        observed_site = site_profile()
    except Exception as exc:
        raise SubmissionError("site_preflight", None, exc) from exc
    root = root_for(approval_sha)
    expected = binding(directory, plan, approval_sha, matrix_sha)
    prior = None
    if parent == "easy":
        require(review_sha is None)
        root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(root.parent.resolve() == root.parent)
        mkdir(root)
        write(root / "binding.json", expected)
    else:
        require(load(root / "binding.json") == expected)
        prior = easy_review(directory, plan, approval_sha, review_sha)
        easy, _ = submission(directory, "easy")
        require(easy["job_id"] == prior["job_id"])
        require(clean_accounting(status(directory, "easy")))
    live(root, matrix_sha)
    write(root / (parent + ".started"), {"easy_review_sha256": review_sha})
    state = state_for(directory, parent)
    job, stage = None, "create_submission_state"
    try:
        state.parent.mkdir(mode=0o700, exist_ok=True)
        mkdir(state)
        write(state / "site_profile.json", observed_site)
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("SBATCH_", "SRUN_", "SLURM_"))
            and k not in {"BASH_ENV", "ENV"}
        }
        stage = "sbatch_held"
        job = site.command(
            [
                "sbatch",
                "--parsable",
                "--hold",
                "--no-requeue",
                "--partition=batch",
                "--nodes=1",
                "--ntasks=1",
                "--cpus-per-task=16",
                "--hint=nomultithread",
                "--mem=64G",
                "--time=05:30:00",
                "--job-name=cfl_paired_" + parent,
                "--chdir=" + str(SOURCE),
                "--output=" + str(state / "slurm-%j.private.out"),
                "--error=" + str(state / "slurm-%j.private.err"),
                str(SOURCE / BATCH),
                str(directory),
                approval_sha,
                parent,
            ],
            env=env,
        ).strip()
        require(re.fullmatch(r"[0-9]{1,20}", job))
        stage = "persist_job_id"
        record = {
            **expected,
            "parent": parent,
            "job_id": job,
            "easy_review_sha256": review_sha,
        }
        write(
            state / "submission.json", record
        )  # fsync file + directory before release.
        require(prior is None or job != prior["job_id"])
        stage = "validate_held_profile"
        profile = held_profile(
            site.command(["scontrol", "show", "job", "--oneliner", job]), job
        )
        write(state / "held_profile.json", profile)
        live(root, matrix_sha)
        write(state / "release.started", {"job_id": job})
        stage = "release_job"
        site.command(
            ["scontrol", "release", job]
        )  # Exactly one release; no recovery loop.
        write(state / "released.json", {"job_id": job})
        return {
            "job_id": job,
            "parent": parent,
            "submission": "released",
            "automatic_retry": False,
        }
    except BaseException as exc:
        stop(root, "submission_uncertain")
        safe_job = (
            job if isinstance(job, str) and re.fullmatch(r"[0-9]{1,20}", job) else None
        )
        error = SubmissionError(stage, safe_job, exc)
        if state.is_dir():
            write(state / "submission_failure.json", error.report)
        raise error from exc


def run(directory, approval_sha, parent):
    site.host()
    directory = site.location(directory)
    record, root = submission(directory, parent)
    require(record["operator_approval_sha256"] == approval_sha)
    require(record["job_id"] == os.environ.get("SLURM_JOB_ID"))
    state = state_for(directory, parent)
    require(load(state / "release.started") == {"job_id": record["job_id"]})
    validate_held(load(state / "held_profile.json"), record["job_id"])
    live(root, record["matrix_approval_sha256"])
    if parent == "medium":
        review = easy_review(
            directory,
            load(directory / "operator_plan.json"),
            approval_sha,
            record["easy_review_sha256"],
        )
        require(review["job_id"] != record["job_id"])
    write(state / "batch.started", {"job_id": record["job_id"]})
    try:
        report = matrix.run_parent(directory, record["matrix_approval_sha256"], parent)
        if not report["complete_parent"]:
            stop(root, "batch_failed")
        return report
    except BaseException:
        stop(root, "batch_failed")
        raise


def status(directory, parent):
    site.host()
    directory = site.location(directory)
    record, _ = submission(directory, parent)
    text = site.command(
        [
            "sacct",
            "--noheader",
            "--parsable2",
            "-j",
            record["job_id"],
            "--format=" + site.FIELDS,
        ]
    )
    return site.parse_accounting(text, record["job_id"])


def validate_accounting(value):
    old.keys(value, "job_id rows state terminal")
    require(isinstance(value["rows"], list))
    for row in value["rows"]:
        old.keys(row, site.FIELDS.replace(",", " "))
        old.integer(row["ElapsedRaw"])
        old.integer(row["AllocCPUS"])
    text = "\n".join(
        "|".join(str(row[n]) for n in site.FIELDS.split(",")) for row in value["rows"]
    )
    require(value == site.parse_accounting(text, value["job_id"]))
    require(value["terminal"] is True)


def clean_accounting(value):
    job = value["job_id"]
    ids = {row["JobID"] for row in value["rows"]}
    return {job, job + ".batch", job + ".0"}.issubset(ids) and all(
        row["State"] == "COMPLETED" and row["ExitCode"] == "0:0"
        for row in value["rows"]
    )


def validate_return(directory, expected_sha):
    """Read-only Windows/Linux validation; no extraction or private logs."""
    directory = Path(directory).absolute()
    require(directory.resolve() == directory and not directory.is_symlink())
    old.hexadecimal(expected_sha)
    files = {p.name for p in directory.iterdir()}
    require(files in (PUBLIC, PUBLIC - {"matrix.tar.gz"}))
    for name in files:
        require((directory / name).is_file() and not (directory / name).is_symlink())
    manifest = old.read_bytes(directory / "SHA256SUMS.txt", 2048)
    require(contract.sha(manifest) == expected_sha)
    raws = {
        n: old.read_bytes(
            directory / n, matrix.MAX_PACKAGE if n == "matrix.tar.gz" else old.MAX_JSON
        )
        for n in files - {"SHA256SUMS.txt"}
    }
    require(
        manifest
        == "".join(
            contract.sha(raws[n]) + "  " + n + "\n" for n in sorted(raws)
        ).encode()
    )
    plan = validate_plan(old.strict_payload(raws["operator_plan.json"]))
    approval = old.strict_payload(raws["operator_approval.json"])
    record = old.strict_payload(raws["submission.json"])
    old.keys(
        record,
        "operator_plan_sha256 operator_approval_sha256 matrix_approval_sha256 directory_sha256 parent job_id easy_review_sha256",
    )
    validate_approval(
        plan,
        approval,
        record["operator_approval_sha256"],
        record["matrix_approval_sha256"],
    )
    require(record["operator_plan_sha256"] == plan["operator_plan_sha256"])
    old.hexadecimal(record["directory_sha256"])
    require(record["parent"] in matrix.PARENTS)
    require(
        record["easy_review_sha256"] is None
        if record["parent"] == "easy"
        else bool(re.fullmatch(r"[0-9a-f]{64}", record["easy_review_sha256"]))
    )
    value = old.strict_payload(raws["accounting.json"])
    old.keys(
        value,
        "schema_version protocol_id operator_plan_sha256 operator_approval_sha256 matrix_approval_sha256 parent accounting held_profile release_receipt_present batch_start_receipt_present workflow_stop_present parent_evidence_state matrix_package_sha256 complete_parent completed_attempts_observed exact_optimization_call_count ready_for_independent_review pause_remaining_matrix raw_logs_included scientific_reporting_eligible",
    )
    require(
        old.integer(value["schema_version"]) == 1 and value["protocol_id"] == PROTOCOL
    )
    for name in (
        "operator_plan_sha256",
        "operator_approval_sha256",
        "matrix_approval_sha256",
        "parent",
    ):
        require(value[name] == record[name])
    validate_accounting(value["accounting"])
    require(value["accounting"]["job_id"] == record["job_id"])
    for name in (
        "release_receipt_present",
        "batch_start_receipt_present",
        "workflow_stop_present",
        "complete_parent",
        "ready_for_independent_review",
        "pause_remaining_matrix",
    ):
        require(type(value[name]) is bool)
    require(
        value["raw_logs_included"] is False
        and value["scientific_reporting_eligible"] is False
    )
    for name in ("completed_attempts_observed", "exact_optimization_call_count"):
        if value[name] is not None:
            old.integer(value[name], maximum=5)
    if value["held_profile"] is not None:
        validate_held(value["held_profile"], record["job_id"])
    if "matrix.tar.gz" in files:
        require(value["parent_evidence_state"] == "validated")
        require(value["matrix_package_sha256"] == contract.sha(raws["matrix.tar.gz"]))
        report = matrix.validate_package(
            directory / "matrix.tar.gz", value["matrix_package_sha256"]
        )
        require(
            report["parent"] == record["parent"]
            and report["job_id"] == record["job_id"]
        )
        require(report["approval_sha256"] == record["matrix_approval_sha256"])
        require(report["plan_sha256"] == plan["matrix_plan_sha256"])
        require(value["complete_parent"] is report["complete_parent"])
        require(
            value["completed_attempts_observed"]
            == len(report["attempt_receipt_sha256"])
        )
        require(
            value["exact_optimization_call_count"]
            == (5 if report["complete_parent"] else None)
        )
    else:
        require(value["parent_evidence_state"] in {"unavailable", "invalid"})
        require(
            value["matrix_package_sha256"] is None and value["complete_parent"] is False
        )
        require(
            value["completed_attempts_observed"] is None
            and value["exact_optimization_call_count"] is None
        )
        require(value["workflow_stop_present"] is True)
    eligible = (
        clean_accounting(value["accounting"])
        and value["complete_parent"]
        and value["held_profile"] is not None
        and value["release_receipt_present"]
        and value["batch_start_receipt_present"]
        and not value["workflow_stop_present"]
    )
    require(value["ready_for_independent_review"] is eligible)
    require(value["pause_remaining_matrix"] is not eligible)
    return value


def collection_summary(directory):
    sha = digest(directory / "SHA256SUMS.txt")
    value = validate_return(directory, sha)
    return {
        "parent": value["parent"],
        "job_id": value["accounting"]["job_id"],
        "return_sha256": sha,
        "ready_for_independent_review": value["ready_for_independent_review"],
        "scientific_reporting_eligible": False,
    }


def collect(directory, parent):
    site.host()
    directory = site.location(directory)
    record, root = submission(directory, parent)
    output = directory / ("return-" + parent)
    if output.exists():
        return collection_summary(output)  # Read-only idempotence; no new sacct query.
    accounting = status(directory, parent)  # Exactly one query; no wait/poll loop.
    if not accounting["terminal"]:
        return {
            "parent": parent,
            "job_id": record["job_id"],
            "terminal": False,
            "collected": False,
        }
    require(all(row["State"] in site.TERMINAL for row in accounting["rows"]))
    state = state_for(directory, parent)
    mkdir(state / "collection.started")
    report, package_sha, evidence_state = None, None, "unavailable"
    package = state / "sealed-matrix.tar.gz"
    try:
        if (directory / parent / "parent_receipt.json").exists():
            evidence_state = "invalid"
            package_sha = matrix.export_parent(
                directory, record["matrix_approval_sha256"], parent, package
            )
            report = matrix.validate_package(package, package_sha)
            require(report["job_id"] == record["job_id"])
            evidence_state = "validated"
    except Exception:
        report, package_sha = (
            None,
            None,
        )  # Retain suspect private evidence, never export it.
    profile = (
        load(state / "held_profile.json")
        if (state / "held_profile.json").exists()
        else None
    )
    if profile is not None:
        validate_held(profile, record["job_id"])
    released = (state / "released.json").exists()
    if released:
        require(load(state / "released.json") == {"job_id": record["job_id"]})
    batch_started = (state / "batch.started").exists()
    if batch_started:
        require(load(state / "batch.started") == {"job_id": record["job_id"]})
    complete = report is not None and report["complete_parent"]
    if (
        not clean_accounting(accounting)
        or not complete
        or profile is None
        or not released
        or not batch_started
    ):
        stop(root, "collection_failed")
    stopped = (root / "STOP.json").exists() or (
        matrix.adapter.EVIDENCE_ROOT
        / "paired-matrix-locks"
        / record["matrix_approval_sha256"]
        / "STOP.json"
    ).exists()
    ready = (
        clean_accounting(accounting)
        and complete
        and profile is not None
        and released
        and batch_started
        and not stopped
    )
    value = {
        "schema_version": 1,
        "protocol_id": PROTOCOL,
        **{
            n: record[n]
            for n in (
                "operator_plan_sha256",
                "operator_approval_sha256",
                "matrix_approval_sha256",
                "parent",
            )
        },
        "accounting": accounting,
        "held_profile": profile,
        "release_receipt_present": released,
        "batch_start_receipt_present": batch_started,
        "workflow_stop_present": stopped,
        "parent_evidence_state": evidence_state,
        "matrix_package_sha256": package_sha,
        "complete_parent": complete,
        "completed_attempts_observed": len(report["attempt_receipt_sha256"])
        if report
        else None,
        "exact_optimization_call_count": 5 if complete else None,
        "ready_for_independent_review": ready,
        "pause_remaining_matrix": not ready,
        "raw_logs_included": False,
        "scientific_reporting_eligible": False,
    }
    mkdir(output)
    for name, data in (
        ("operator_plan.json", load(directory / "operator_plan.json")),
        ("operator_approval.json", load(directory / "operator_approval.json")),
        ("submission.json", record),
        ("accounting.json", value),
    ):
        write(output / name, data)
    if package_sha is not None:
        with (output / "matrix.tar.gz").open("xb") as stream:
            stream.write(old.read_bytes(package, matrix.MAX_PACKAGE))
            stream.flush()
            os.fsync(stream.fileno())
    names = sorted(p.name for p in output.iterdir())
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write(
            "".join(digest(output / n) + "  " + n + "\n" for n in names).encode()
        )
        stream.flush()
        os.fsync(stream.fileno())
    sync_dir(output)
    return collection_summary(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("prepare", "submit", "run", "status", "collect", "validate-return"),
    )
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--parent", choices=matrix.PARENTS)
    parser.add_argument("--approval-sha")
    parser.add_argument("--easy-review-sha")
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action in {"prepare", "validate-return"}:
        require(
            args.parent is None
            and args.approval_sha is None
            and args.easy_review_sha is None
        )
        if args.action == "prepare":
            require(args.expected_sha is None)
            value = prepare(args.directory)
        else:
            require(args.expected_sha is not None)
            value = validate_return(args.directory, args.expected_sha)
    else:
        require(args.parent is not None and args.expected_sha is None)
        if args.action == "submit":
            require(args.approval_sha is not None)
            value = submit(
                args.directory, args.approval_sha, args.parent, args.easy_review_sha
            )
        elif args.action == "run":
            require(args.approval_sha is not None and args.easy_review_sha is None)
            value = run(args.directory, args.approval_sha, args.parent)
        else:
            require(args.approval_sha is None and args.easy_review_sha is None)
            value = globals()[args.action](args.directory, args.parent)
    print(contract.encoded(value).decode(), end="")


if __name__ == "__main__":
    try:
        main()
    except SubmissionError as exc:
        print(contract.encoded(exc.report).decode(), end="", file=sys.stderr)
        sys.exit(2)
    except (Exception, KeyboardInterrupt):
        print(
            "PAIRED_WORKFLOW_STOPPED_PRESERVE_EVIDENCE_NO_RETRY_NO_SUBMISSION_REPEAT",
            file=sys.stderr,
        )
        sys.exit(2)
