"""Approval-bound, one-shot Slurm qualification workflow (not a comparison).

SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import argparse
import gzip
import io
import os
import re
import socket
import subprocess
import sys
import tarfile
from pathlib import Path

import isolated_attempt_worker as worker

contract = worker.contract
require = worker.require
SOURCE = Path(__file__).resolve().parents[2]
BATCH = "scripts/slurm/dasci/submit_callback_qualification.sbs"
FIELDS = "JobID,State,ExitCode,ElapsedRaw,TotalCPU,AllocCPUS,ReqMem,MaxRSS"
TERMINAL = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "TIMEOUT",
    "OUT_OF_MEMORY",
    "NODE_FAIL",
    "PREEMPTED",
    "BOOT_FAIL",
    "DEADLINE",
    "REVOKED",
}
STATES = TERMINAL | {
    "PENDING",
    "RUNNING",
    "SUSPENDED",
    "COMPLETING",
    "CONFIGURING",
    "RESIZING",
    "REQUEUED",
    "REQUEUE_FED",
    "REQUEUE_HOLD",
    "SPECIAL_EXIT",
}
PUBLIC = ("accounting.json", "attempt.tar.gz", "SHA256SUMS.txt")
LIMIT = 16 * 1024 * 1024


def command(args, timeout=20, env=None):
    """Bounded call; never print raw scheduler stderr or repeat a command."""
    result = subprocess.run(
        args, capture_output=True, timeout=timeout, check=False, env=env
    )
    require(result.returncode == 0 and len(result.stdout) <= 128 * 1024)
    return result.stdout.decode("utf-8", errors="strict")


def source_head():
    cmd = ["git", "-c", "safe.directory=" + str(SOURCE), "-C", str(SOURCE)]
    head = command([*cmd, "rev-parse", "HEAD"]).strip()
    worker.hexadecimal(head, 40)
    require(not command([*cmd, "status", "--porcelain", "--untracked-files=all"]))
    require(not (SOURCE / "gurobi.env").exists())
    return head


def host():
    require(sys.platform == "linux")
    require(socket.gethostname().split(".")[0] == "dgx-dasci")
    require(os.environ.get("CONDA_DEFAULT_ENV") == "tfm_env")
    require(SOURCE.is_relative_to(Path("/raid/vrcelestino/data")))


def location(directory):
    directory = Path(directory).absolute()
    root = worker.adapter.EVIDENCE_ROOT
    require(root.resolve(strict=True) == root)
    require(directory.resolve() == directory and not directory.is_symlink())
    require(directory.is_relative_to(root) and directory != root)
    require(
        not directory.is_relative_to(SOURCE) and not SOURCE.is_relative_to(directory)
    )
    return directory


def pins():
    return {
        **worker.dependency_hashes(),
        "qualification_workflow.py": worker.adapter.screen.digest(Path(__file__)),
        BATCH: worker.adapter.screen.digest(SOURCE / BATCH),
    }


def proposed_plan(head):
    value = {
        "schema_version": 1,
        "protocol_id": "single_attempt_nonblocking_workflow_v1",
        "source_commit": head,
        "dependency_sha256": pins(),
        "installed_preflight_receipt_sha256": worker.PREFLIGHT_SHA,
        "proposal_sha256": contract.compile_proposal()["proposal_sha256"],
        "attempt_id": "easy-seed42-threads1",
        "optimization_limit_seconds": 60,
        "child_deadline_seconds": 240,
        "scheduler": {
            "partition": "batch",
            "nodes": 1,
            "tasks": 1,
            "cpus_per_task": 16,
            "memory_mib": 65536,
            "wall_seconds": 600,
            "gpus": 0,
            "exclusive": False,
            "requeue": False,
            "hint": "nomultithread",
        },
        "maximum_submissions": 1,
        "maximum_optimization_calls": 1,
        "resource_budget_approved": False,
        "scientific_reporting_eligible": False,
    }
    value["plan_sha256"] = contract.sha(contract.encoded(value))
    return value


def load(path):
    return worker.strict_payload(worker.read_bytes(path))


def validate_plan(value):
    worker.hexadecimal(value.get("source_commit"), 40)
    require(
        contract.encoded(value)
        == contract.encoded(proposed_plan(value["source_commit"]))
    )
    return value


def check_preflight(path):
    raw = worker.read_bytes(path)
    require(contract.sha(raw) == worker.PREFLIGHT_SHA)
    receipt = worker.strict_payload(raw)
    require(receipt["status"] == "passed_no_optimization")
    require(
        type(receipt["optimization_runs"]) is int and receipt["optimization_runs"] == 0
    )
    require(
        receipt["dependency_sha256"]
        == {
            k: v
            for k, v in worker.dependency_hashes().items()
            if k in worker.adapter.DEPENDENCIES
        }
    )


def prepare(directory, preflight):
    host()
    directory = location(directory)
    head = source_head()
    check_preflight(preflight)  # Existing receipt only: no runtime/LP/license reads.
    require(not directory.exists())
    directory.mkdir(mode=0o700, parents=False)
    value = proposed_plan(head)
    worker.write_json(directory / "plan.json", value)
    worker.write_json(
        directory / "approval.json",
        {
            "schema_version": 1,
            "explicitly_approved": False,
            "plan_sha256": value["plan_sha256"],
            "maximum_submissions": 1,
            "maximum_optimization_calls": 1,
            "scientific_reporting_eligible": False,
        },
    )
    return value


def approved(directory, approval_sha):
    worker.hexadecimal(approval_sha)
    raw = worker.read_bytes(directory / "approval.json")
    require(contract.sha(raw) == approval_sha)
    approval = worker.strict_payload(raw)
    worker.keys(
        approval,
        "schema_version explicitly_approved plan_sha256 maximum_submissions maximum_optimization_calls scientific_reporting_eligible",
    )
    require(approval["explicitly_approved"] is True)
    require(approval["scientific_reporting_eligible"] is False)
    for name in ("schema_version", "maximum_submissions", "maximum_optimization_calls"):
        require(worker.integer(approval[name]) == 1)
    plan = validate_plan(load(directory / "plan.json"))
    require(approval["plan_sha256"] == plan["plan_sha256"])
    require(plan["source_commit"] == source_head())
    return plan


def request_for(plan, approval_sha):
    request = {
        key: plan[key]
        for key in (
            "source_commit",
            "proposal_sha256",
            "installed_preflight_receipt_sha256",
            "attempt_id",
            "optimization_limit_seconds",
            "child_deadline_seconds",
            "maximum_optimization_calls",
            "scientific_reporting_eligible",
        )
    }
    request.update(
        schema_version=1,
        protocol_id=worker.PROTOCOL,
        explicitly_approved=True,
        approval_record_sha256=approval_sha,
        dependency_sha256=worker.dependency_hashes(),
    )
    worker.validate_request(request)
    return request


def claim_path(approval_sha):
    return (
        worker.adapter.EVIDENCE_ROOT / "qualification-submission-locks" / approval_sha
    )


def claim_value(directory, plan, approval_sha):
    return {
        "plan_sha256": plan["plan_sha256"],
        "approval_sha256": approval_sha,
        "directory_sha256": contract.sha(str(directory).encode()),
    }


def submit(directory, approval_sha):
    host()
    directory = location(directory)
    plan = approved(directory, approval_sha)  # Before any scheduler mutation.
    require(not (directory / "submission.started").exists())
    require(not (directory / "request.json").exists())
    lock = claim_path(approval_sha)
    lock.parent.mkdir(mode=0o700, exist_ok=True)
    require(lock.parent.resolve() == lock.parent and not lock.parent.is_symlink())
    lock.mkdir(mode=0o700, exist_ok=False)  # Global durable no-resubmit claim.
    worker.write_json(lock / "claim.json", claim_value(directory, plan, approval_sha))
    (directory / "submission.started").mkdir(mode=0o700)
    worker.write_json(directory / "request.json", request_for(plan, approval_sha))
    # Remove SBATCH_* overrides; exact command-line resource ceilings also bind.
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("SBATCH_", "SRUN_"))
    }
    text = command(
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
            "--time=00:10:00",
            "--chdir=" + str(SOURCE),
            "--output=" + str(directory / "slurm-%j.private.out"),
            "--error=" + str(directory / "slurm-%j.private.err"),
            str(SOURCE / BATCH),
            str(directory),
            approval_sha,
        ],
        env=env,
    ).strip()
    require(re.fullmatch(r"[0-9]{1,20}", text))  # No federation/ambiguous ID.
    worker.write_json(
        directory / "submission.json",
        {
            **claim_value(directory, plan, approval_sha),
            "job_id": text,
        },
    )
    # Job cannot start before its ID is durably recorded. One release, no loop.
    command(["scontrol", "release", text])
    return {"job_id": text, "submission": "released", "no_automatic_retry": True}


def submission(directory):
    value = load(directory / "submission.json")
    worker.keys(value, "plan_sha256 approval_sha256 directory_sha256 job_id")
    require(re.fullmatch(r"[0-9]{1,20}", value["job_id"]))
    plan = approved(directory, value["approval_sha256"])
    require(
        {k: v for k, v in value.items() if k != "job_id"}
        == claim_value(directory, plan, value["approval_sha256"])
    )
    lock = claim_path(value["approval_sha256"])
    require(lock.resolve() == lock and not lock.is_symlink())
    require(
        load(lock / "claim.json")
        == claim_value(directory, plan, value["approval_sha256"])
    )
    require(
        load(directory / "request.json") == request_for(plan, value["approval_sha256"])
    )
    return value


def run(directory, approval_sha):
    host()
    directory = location(directory)
    record = submission(directory)
    require(record["approval_sha256"] == approval_sha)
    require(record["job_id"] == os.environ.get("SLURM_JOB_ID"))
    # The worker separately validates allocation/affinity/source/global claim.
    return worker.supervise_one(load(directory / "request.json"), directory / "attempt")


def parse_accounting(text, job):
    require(isinstance(job, str) and re.fullmatch(r"[0-9]{1,20}", job))
    rows = []
    for line in text.splitlines():
        parts = line.strip().split("|")
        require(len(parts) == 8)
        identity, state, exit_code, elapsed, cpu, cpus, mem, rss = parts
        require(
            re.fullmatch(re.escape(job) + r"(?:\.(?:batch|extern|[0-9]+))?", identity)
        )
        # sacct may append '+' or ' by UID'. Do not export that free text.
        state = state.split(" ")[0].rstrip("+")
        require(state in STATES)
        require(re.fullmatch(r"[0-9]+:[0-9]+", exit_code))
        require(re.fullmatch(r"[0-9]+", elapsed) and re.fullmatch(r"[0-9]+", cpus))
        require(
            not cpu
            or re.fullmatch(
                r"(?:[0-9]+-)?[0-9]+:[0-9]{2}(?::[0-9]{2})?(?:\.[0-9]+)?", cpu
            )
        )
        for value in (mem, rss):
            require(
                not value or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?[KMGTPE]?[cn]?", value)
            )
        rows.append(
            dict(
                zip(
                    FIELDS.split(","),
                    [
                        identity,
                        state,
                        exit_code,
                        int(elapsed),
                        cpu,
                        int(cpus),
                        mem,
                        rss,
                    ],
                )
            )
        )
    require(len(rows) <= 20 and len({r["JobID"] for r in rows}) == len(rows))
    roots = [r for r in rows if r["JobID"] == job]
    require(len(roots) <= 1)
    root = roots[0] if roots else None
    return {
        "job_id": job,
        "rows": rows,
        "state": root["State"] if root else "ACCOUNTING_UNAVAILABLE",
        "terminal": root is not None and root["State"] in TERMINAL,
    }


def status(directory):
    host()
    directory = location(directory)
    record = submission(directory)
    text = command(
        [
            "sacct",
            "--noheader",
            "--parsable2",
            "-j",
            record["job_id"],
            "--format=" + FIELDS,
        ]
    )
    return parse_accounting(text, record["job_id"])


def collect(directory):
    host()
    directory = location(directory)
    record = submission(directory)
    accounting = status(directory)  # Exactly one read; never wait for completion.
    require(accounting["terminal"])
    _, receipt = worker.validate_directory(directory / "attempt", private=True)
    child = receipt["child"]
    require(child is None or child["slurm_job_id"] == record["job_id"])
    root = next(r for r in accounting["rows"] if r["JobID"] == record["job_id"])
    clean = root["State"] == "COMPLETED" and root["ExitCode"] == "0:0"
    eligible = clean and receipt["status"] == "completed"
    output = directory / "return"
    require(not output.exists())
    output.mkdir(mode=0o700)
    # Intermediate worker export is sanitized too; no extraction of raw logs.
    worker.export_receipt(directory / "attempt", directory / "sealed")
    payloads = {
        "attempt.tar.gz": worker.read_bytes(
            directory / "sealed/isolated_attempt_evidence.tar.gz", LIMIT
        ),
        "accounting.json": contract.encoded(
            {
                "schema_version": 1,
                "plan_sha256": record["plan_sha256"],
                "approval_sha256": record["approval_sha256"],
                "accounting": accounting,
                "attempt_package_sha256": worker.adapter.screen.digest(
                    directory / "sealed/isolated_attempt_evidence.tar.gz"
                ),
                "ready_for_independent_review": eligible,
                "pause_remaining_matrix": not eligible,
                "raw_logs_included": False,
                "scientific_reporting_eligible": False,
            }
        ),
    }
    worker.strict_payload(payloads["accounting.json"])
    payloads["SHA256SUMS.txt"] = "".join(
        contract.sha(payloads[name]) + "  " + name + "\n" for name in PUBLIC[:2]
    ).encode()
    package = output / "qualification_package.tar.gz"
    with tarfile.open(package, "x:gz") as archive:
        for name in PUBLIC:
            info = tarfile.TarInfo(name)
            info.size = len(payloads[name])
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(payloads[name]))
    digest = worker.adapter.screen.digest(package)
    validate_archive(package, digest)
    with (output / "PACKAGE_SHA256.txt").open("xb") as stream:
        stream.write((digest + "  " + package.name + "\n").encode())
    return {
        "job_id": record["job_id"],
        "package_sha256": digest,
        "ready_for_independent_review": eligible,
        "scientific_reporting_eligible": False,
    }


def archive_payloads(raw, names, maximum):
    require(len(raw) <= LIMIT)
    decoded_limit = len(names) * maximum + 64 * 1024
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        decoded = stream.read(decoded_limit + 1)
    require(len(decoded) <= decoded_limit)
    payloads = {}
    end = 0
    with tarfile.open(fileobj=io.BytesIO(decoded), mode="r:") as archive:
        for member in archive:
            require(member.name in names and member.name not in payloads)
            require(member.isfile() and 0 <= member.size <= maximum)
            require(not member.sparse and not member.pax_headers)
            stream = archive.extractfile(member)
            require(stream is not None)
            payloads[member.name] = stream.read(maximum + 1)
            require(len(payloads[member.name]) == member.size)
            end = member.offset_data + ((member.size + 511) // 512) * 512
    require(len(decoded) >= end + 1024 and not any(decoded[end:]))
    require(set(payloads) == set(names))
    return payloads


def validate_archive(package, expected_sha):
    worker.hexadecimal(expected_sha)
    raw = worker.read_bytes(package, LIMIT)
    require(contract.sha(raw) == expected_sha)
    payloads = archive_payloads(raw, PUBLIC, LIMIT)
    require(set(payloads) == set(PUBLIC))
    require(
        payloads["SHA256SUMS.txt"]
        == "".join(
            contract.sha(payloads[name]) + "  " + name + "\n" for name in PUBLIC[:2]
        ).encode()
    )
    value = worker.strict_payload(payloads["accounting.json"])
    worker.keys(
        value,
        "schema_version plan_sha256 approval_sha256 accounting attempt_package_sha256 ready_for_independent_review pause_remaining_matrix raw_logs_included scientific_reporting_eligible",
    )
    require(worker.integer(value["schema_version"]) == 1)
    for name in ("plan_sha256", "approval_sha256", "attempt_package_sha256"):
        worker.hexadecimal(value[name])
    require(
        value["raw_logs_included"] is False
        and value["scientific_reporting_eligible"] is False
    )
    require(type(value["ready_for_independent_review"]) is bool)
    require(
        value["pause_remaining_matrix"] is not value["ready_for_independent_review"]
    )
    accounting = value["accounting"]
    worker.keys(accounting, "job_id rows state terminal")
    require(isinstance(accounting["rows"], list))
    for row in accounting["rows"]:
        worker.keys(row, FIELDS.replace(",", " "))
        worker.integer(row["ElapsedRaw"])
        worker.integer(row["AllocCPUS"])
    text = "\n".join(
        "|".join(str(row[name]) for name in FIELDS.split(","))
        for row in accounting["rows"]
    )
    require(accounting == parse_accounting(text, accounting["job_id"]))
    require(accounting["terminal"] is True)
    # Reuse the worker's bounded nested validator without filesystem extraction.
    require(contract.sha(payloads["attempt.tar.gz"]) == value["attempt_package_sha256"])
    nested = archive_payloads(
        payloads["attempt.tar.gz"], worker.PUBLIC, worker.MAX_JSON
    )
    worker.validate_public_payloads(nested)
    request = worker.strict_payload(nested["request.json"])
    receipt = worker.strict_payload(nested["attempt_receipt.json"])
    require(request["approval_record_sha256"] == value["approval_sha256"])
    child = receipt["child"]
    require(child is None or child["slurm_job_id"] == accounting["job_id"])
    root = next(r for r in accounting["rows"] if r["JobID"] == accounting["job_id"])
    eligible = (
        root["State"] == "COMPLETED"
        and root["ExitCode"] == "0:0"
        and receipt["status"] == "completed"
    )
    require(value["ready_for_independent_review"] is eligible)
    require(
        request
        == request_for(
            proposed_plan(request["source_commit"]), value["approval_sha256"]
        )
    )
    require(
        value["plan_sha256"] == proposed_plan(request["source_commit"])["plan_sha256"]
    )
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("prepare", "submit", "run", "status", "collect", "validate")
    )
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--approval-sha")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "validate":
        require(args.package is not None and args.expected_sha is not None)
        value = validate_archive(args.package, args.expected_sha)
    else:
        require(args.directory is not None)
        if args.action == "prepare":
            require(args.preflight is not None)
            value = prepare(args.directory, args.preflight)
        elif args.action in {"submit", "run"}:
            require(args.approval_sha is not None)
            value = globals()[args.action](args.directory, args.approval_sha)
        else:
            value = globals()[args.action](args.directory)
    print(contract.encoded(value).decode(), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "QUALIFICATION_STOPPED_PRESERVE_EVIDENCE_NO_RETRY_NO_MERGE", file=sys.stderr
        )
        sys.exit(2)
