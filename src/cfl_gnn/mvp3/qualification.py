"""Prospective five-call local qualification. Never run merely by importing."""

import argparse
import os
import re
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from .audit import AuditPolicy
from .collection import collect_attempt
from .contract import approved_contract, digest, load_json, require
from .journal import AttemptStore, durable_json, file_sha256
from .logparse import parse_native_log
from .native import NativePermit, NativeSession
from .supervisor import supervise

REPOSITORY = Path(__file__).resolve().parents[3]
ENTRY = REPOSITORY / "scripts/mvp3/qualify_local.py"
CELLS = (
    ("root_relaxation", None),
    ("incumbent", None),
    ("evaluation", "B"),
    ("evaluation", "R"),
    ("evaluation", "G"),
)
TINY_LP = (
    "Maximize\n obj: "
    + " + ".join(f"x{i}" for i in range(20))
    + "\nSubject To\n capacity: "
    + " + ".join(f"x{i}" for i in range(20))
    + " >= 10.5\nBinary\n "
    + " ".join(f"x{i}" for i in range(20))
    + "\nEnd\n"
)


def check_source(expected, *, repository=REPOSITORY):
    require(
        re.fullmatch(r"[0-9a-f]{40}", expected) is not None,
        "Exact reviewed commit required",
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    require(head == expected, "CLI source differs from the reviewed commit")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repository,
        text=True,
    )
    require(
        not dirty, "Qualification requires a clean checkout including untracked files"
    )


def fixture_start(session):
    """Synthetic B/R/G wiring only; this is not a trained predictor or root policy."""
    key = session.store.binding["key"]
    method = key["method"]
    support = (
        []
        if method == "B"
        else [
            {
                "position": i,
                "variable_name": variable["name"],
                "value": 1,
                "lower_bound": variable["lower"],
                "upper_bound": variable["upper"],
            }
            for i, variable in enumerate(session.matrix.variables[:2])
        ]
    )
    assignments = [
        {name: item[name] for name in ("position", "variable_name", "value")}
        for item in support
    ]
    binding = session.store.binding
    return {
        "key": key,
        "model_sha256": session.identity["model_sha256"],
        "variable_order_sha256": session.identity["variable_order_sha256"],
        "binary_count": 20,
        "original_variable_count": 20,
        "support": support,
        "support_sha256": digest(assignments),
        "ones_count": len(support),
        "root_artifact_sha256": None
        if method == "B"
        else binding["root_artifact_sha256"],
        "frozen_policy_sha256": None
        if method == "B"
        else binding["frozen_start_policy_sha256"],
        "predictor_sha256": binding["predictor_sha256"] if method == "G" else None,
        "provenance": "invented_technical_fixture_no_learning_or_research_guidance",
    }


def explicit_license_path(path):
    require(
        isinstance(path, (str, Path)) and bool(str(path).strip()),
        "Explicit previously qualified local license path required",
    )
    result = Path(path).resolve()
    require(result.is_file(), "Previously qualified local license file is unavailable")
    return result


def configure_worker_license(path):
    """Worker-only routing; inspect existence, never open/hash the license file."""
    os.environ["GRB_LICENSE_FILE"] = str(explicit_license_path(path))


def safe_worker_error(error, phase, binding_sha256):
    code = getattr(error, "errno", None)
    return {
        "binding_sha256": binding_sha256,
        "phase": phase,
        "exception_type": type(error).__name__,
        "native_error_code": code if type(code) is int else None,
        "error_code_missing_reason": None
        if type(code) is int
        else "exception_has_no_numeric_code",
        "exception_message_copied": False,
        "automatic_retry": False,
    }


def worker(spec_path, spec_sha256):
    require(file_sha256(spec_path) == spec_sha256, "Worker specification changed")
    spec = load_json(spec_path)
    check_source(spec["binding"]["source_commit"])
    require(
        spec["binding"]["mode"] == "technical_qualification",
        "This worker cannot execute a primary campaign",
    )
    require(
        spec["input_sha256"] == file_sha256(spec["input_path"]),
        "Qualification input changed",
    )
    require(
        Path(spec["input_path"]).read_bytes() == TINY_LP.encode("ascii"),
        "Only the reviewed 20-variable technical fixture is allowed",
    )
    require(
        (spec["binding"]["key"]["stage"], spec["binding"]["key"]["method"]) in CELLS,
        "Unknown qualification cell",
    )
    store = AttemptStore(
        spec["attempt_folder"],
        spec["binding"],
        event_limit=1000,
        artifact_bytes_limit=8 * 1024 * 1024,
        candidate_limit=16,
    )
    outcome = "native_or_capture_failure"
    session = None
    try:
        configure_worker_license(spec["license_file"])
        # Deliberate native import is confined to the author-approved CLI worker.
        import gurobipy as gp

        permit = NativePermit(
            spec["binding"]["source_commit"],
            spec["input_sha256"],
            spec["approval_reference"],
            "technical_qualification",
        )
        profile = {
            **approved_contract()["solver"]["profiles"][
                spec["binding"]["key"]["stage"]
            ],
            "Threads": 1,
            "TimeLimit": 10,
        }
        session = NativeSession(
            gp, spec["input_path"], permit, store, profile, AuditPolicy()
        )
        with session:
            if spec["binding"]["key"]["stage"] == "evaluation":
                session.install_start(fixture_start(session))
            result = session.optimize_once()
            require(
                result["native"]["observer"]["failure"] is None,
                "Native observer failed",
            )
            outcome = "native_returned_pending_qualification"
    except Exception as error:
        durable_json(
            store.folder / "worker-error.json",
            safe_worker_error(
                error,
                session.phase
                if session is not None
                else "license_routing_or_API_import",
                store.binding_sha256,
            ),
        )
        raise
    finally:
        store.close(outcome)


def qualify(output, source_commit, approval_reference, *, license_file=None):
    check_source(source_commit)
    require(
        isinstance(approval_reference, str) and approval_reference.strip(),
        "Explicit author CLI approval reference required",
    )
    license_file = explicit_license_path(license_file)
    output = Path(output).resolve()
    require(
        not output.is_relative_to(REPOSITORY),
        "Private qualification output must be outside the clean checkout",
    )
    dependencies = {
        name: version(name)
        for name in ("gurobipy", "psutil", "gurobi-logtools", "jsonschema")
    }
    require(
        dependencies
        == {
            "gurobipy": "14.0.0",
            "psutil": "7.2.2",
            "gurobi-logtools": "4.0.1",
            "jsonschema": "4.26.0",
        },
        "Qualification dependency drift",
    )
    output.mkdir(parents=True, exist_ok=False)
    durable_json(
        output / "environment.json",
        {
            "python": sys.version,
            "platform": sys.platform,
            "dependencies": dependencies,
            "credential_or_environment_variable_values_collected": False,
            "license_routing": "explicit_existing_path_only_in_worker_GRB_LICENSE_FILE",
            "license_contents_read_or_hashed": False,
            "parent_environment_or_profiles_changed": False,
        },
    )
    input_path = output / "technical-fixture.lp"
    with input_path.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(TINY_LP)
    input_sha = file_sha256(input_path)
    durable_json(
        output / "qualification-intent.json",
        {
            "source_commit": source_commit,
            "approval_reference": approval_reference,
            "license_file": str(license_file),
            "maximum_native_calls": 5,
            "native_seconds_per_call": 10,
            "worker_wall_seconds_per_call": 30,
            "worker_observed_memory_bytes": 1024**3,
            "worker_observed_stdout_bytes": 16 * 1024 * 1024,
            "parallel_workers": 1,
            "scientific_calls": 0,
            "HPC_access": False,
            "automatic_retry": False,
            "input_sha256": input_sha,
            "synthetic_guidance_only": True,
        },
    )
    cells, failure = [], None
    for ordinal, (stage, method) in enumerate(CELLS, 1):
        name = f"{ordinal}-{stage}-{method or 'none'}"
        binding = {
            "source_commit": source_commit,
            "mode": "technical_qualification",
            "input_sha256": input_sha,
            "key": {
                "parent_id": "QUAL_TINY20",
                "stage": stage,
                "method": method,
                "seed": 42,
                "attempt": name,
            },
            "root_artifact_sha256": digest("technical_root_fixture_not_scientific"),
            "frozen_start_policy_sha256": digest(
                "technical_policy_fixture_not_frozen_research"
            ),
            "predictor_sha256": digest("technical_G_fixture_no_learned_weights"),
        }
        spec = {
            "binding": binding,
            "input_path": str(input_path),
            "input_sha256": input_sha,
            "attempt_folder": str(output / name),
            "license_file": str(license_file),
            "approval_reference": approval_reference,
        }
        spec_path = output / f"{name}.spec.json"
        spec_sha = durable_json(spec_path, spec)
        record = {"cell": name, "binding_sha256": digest(binding), "qualified": False}
        try:
            supervised = supervise(
                [
                    sys.executable,
                    "-B",
                    str(ENTRY),
                    "--worker",
                    str(spec_path),
                    "--spec-sha256",
                    spec_sha,
                ],
                output / f"{name}.supervision",
                cwd=REPOSITORY,
                wall_seconds=30,
                memory_bytes=1024**3,
                log_bytes=16 * 1024 * 1024,
                approval_reference=approval_reference,
            )
            record["supervision"] = supervised
            collected = None
            if (output / name / "attempt.json").is_file():
                collected = collect_attempt(output / name)
                durable_json(output / f"{name}.collection.json", collected)
                record["call_accounting"] = {
                    "state": collected["state"],
                    "budget_reserved_calls": collected["budget_reserved_calls"],
                    "observed_native_returns": collected["observed_native_returns"],
                    "worker_error": collected["worker_error"],
                }
            require(
                supervised["child_returncode"] == 0 and supervised["guard"] is None,
                "Qualification worker did not complete cleanly",
            )
            require(collected is not None, "Worker did not create an attempt")
            native = collected["native_result"]
            require(
                native is not None and collected["observed_native_returns"] == 1,
                "Missing native return",
            )
            require(
                native["parameters"]["effective"]["Threads"] == 1,
                "Native thread profile mismatch",
            )
            require(native["native"]["observer"]["failure"] is None, "Capture failure")
            if stage == "root_relaxation":
                require(
                    native["root_audit"] is not None
                    and native["root_audit"]["status"] == "qualified",
                    "Missing qualified continuous root point",
                )
            else:
                require(
                    native["native"]["native_status"] == 2
                    and native["final_audit"] is not None
                    and native["final_audit"]["status"] == "qualified",
                    "Missing audited optimal tiny incumbent",
                )
            parsed = parse_native_log(
                output / f"{name}.supervision/native.stdout.log",
                output / f"{name}.parsed",
                source_kind="author_cli_native_qualification",
                maximum_bytes=16 * 1024 * 1024,
            )
            require(
                any(
                    row["fields"]["Version"]["value"] == "14.0.0"
                    for row in parsed["summaries"]
                ),
                "Actual log did not identify Gurobi14.0.0",
            )
            record["qualified"] = True
            record["native_result_sha256"] = file_sha256(
                output / name / "native-result.json"
            )
        except Exception as error:
            failure = {
                "cell": name,
                "exception_type": type(error).__name__,
                "reason": "qualification_failed_review_preserved_private_artifacts_no_retry",
            }
            record["failure"] = failure
        cells.append(record)
        durable_json(output / f"{name}.qualification.json", record)
        if failure:
            break
    report = {
        "schema_version": "mvp3-s1b-local-qualification-v1",
        "source_commit": source_commit,
        "all_five_cells_qualified": len(cells) == 5
        and all(cell["qualified"] for cell in cells),
        "cells": cells,
        "failure": failure,
        "research_parent_population_qualified": False,
        "production_CPU_memory_profiles_qualified": False,
        "learned_predictor_or_start_policy_qualified": False,
        "automatic_retry": False,
        "private_raw_logs": True,
    }
    durable_json(output / "qualification-result.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output")
    parser.add_argument("--source-commit")
    parser.add_argument("--approval-reference")
    parser.add_argument(
        "--license-file",
        help="Previously qualified local license path; contents are never copied",
    )
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--spec-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.worker:
            require(args.spec_sha256 is not None, "Worker spec checksum required")
            worker(args.worker, args.spec_sha256)
            return 0
        require(
            all(
                (
                    args.output,
                    args.source_commit,
                    args.approval_reference,
                    args.license_file,
                )
            ),
            "Output, exact commit, author CLI reference and explicit local license path are required",
        )
        report = qualify(
            args.output,
            args.source_commit,
            args.approval_reference,
            license_file=args.license_file,
        )
        print(
            "MVP3_LOCAL_QUALIFICATION_OK"
            if report["all_five_cells_qualified"]
            else "MVP3_LOCAL_QUALIFICATION_FAILED"
        )
        return 0 if report["all_five_cells_qualified"] else 1
    except Exception as error:
        print(f"MVP3_LOCAL_QUALIFICATION_ABORTED:{type(error).__name__}")
        return 1
