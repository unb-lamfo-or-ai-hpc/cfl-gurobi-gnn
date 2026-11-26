"""Read-only recovery of complete and partial attempts; no synthetic outcomes."""

from pathlib import Path

from .audit import audit_point
from .contract import digest, load_json, require
from .journal import file_sha256, read_vector, scan_journal


def collect_attempt(folder, *, matrix=None, policy=None):
    folder = Path(folder)
    attempt = load_json(folder / "attempt.json")
    binding = attempt["binding"]
    checksum = digest(binding)
    require(attempt["binding_sha256"] == checksum, "Attempt binding was altered")
    journal = scan_journal(folder)
    receipts = {}
    for name in (
        "measurement-admission",
        "optimize.intent",
        "native-return",
        "native-result",
        "worker-terminal",
    ):
        path = folder / f"{name}.json"
        if path.exists():
            value = load_json(path)
            require(value["binding_sha256"] == checksum, "Cross-attempt receipt")
            receipts[name] = value
    terminal = receipts.get("worker-terminal")
    if terminal:
        require(
            terminal["attempt_sha256"] == file_sha256(folder / "attempt.json"),
            "Sealed attempt metadata was altered",
        )
        actual_receipts = {
            f"{name}.json" for name in receipts if name != "worker-terminal"
        }
        require(
            set(terminal["receipt_sha256"]) == actual_receipts,
            "Sealed receipt set was altered",
        )
        for name, checksum in terminal["receipt_sha256"].items():
            require(
                file_sha256(folder / name) == checksum,
                "Sealed native receipt was altered",
            )
        require(
            not journal["truncated_tail"]
            and terminal["journal_sha256"] == journal["journal_sha256"]
            and terminal["last_frame_sha256"] == journal["last_frame_sha256"]
            and terminal["complete_frames"] == len(journal["frames"]),
            "Sealed journal was altered",
        )
        require(
            terminal["native_intent"] == ("optimize.intent" in receipts)
            and terminal["native_returned"] == ("native-return" in receipts),
            "Terminal call markers disagree",
        )
    intent, returned = "optimize.intent" in receipts, "native-return" in receipts
    require(not returned or intent, "Native return without a durable intent")
    require(
        "native-result" not in receipts or returned,
        "Native result without a return marker",
    )
    vectors, candidates = {}, []
    for frame in journal["frames"]:
        for name in ("root_vector", "candidate_vector"):
            descriptor = frame.get(name)
            if descriptor and descriptor["sha256"] is not None:
                vector = read_vector(folder, descriptor)
                vectors[descriptor["sha256"]] = descriptor["count"]
                if matrix is not None and policy is not None:
                    continuous = name == "root_vector"
                    objective = (
                        None if continuous else frame["candidate_objective"]["value"]
                    )
                    if continuous or objective is not None:
                        audited = audit_point(
                            matrix,
                            vector,
                            policy,
                            native_objective=objective,
                            continuous=continuous,
                        )
                        audited.pop("vector", None)
                        candidates.append(
                            {
                                "callback_ordinal": frame["callback_ordinal"],
                                "native_runtime": frame["native_runtime"],
                                "native_Work": frame["native_Work"],
                                "native_bound": frame.get("OBJBND"),
                                "audit": audited,
                            }
                        )
    result = receipts.get("native-result")
    if result:
        require(
            result["native"]["native_status"]
            == receipts["native-return"]["native_status"],
            "Native result/return status mismatch",
        )
        admissions = [
            frame
            for frame in journal["frames"]
            if frame.get("kind") == "native_admission"
        ]
        require(
            len(admissions) == 1
            and result["identity"] == admissions[0]["identity"]
            and result["parameters"] == admissions[0]["parameter_inventory"],
            "Result differs from native admission",
        )
        descriptor = result["native"].get("final_vector")
        if descriptor and descriptor["sha256"]:
            read_vector(folder, descriptor)
        audit = result.get("final_audit")
        if audit and audit.get("canonical_artifact", {}).get("sha256"):
            read_vector(folder, audit["canonical_artifact"])
            require(
                audit["canonical_artifact"]["sha256"]
                == audit["canonical_vector_sha256"]
                == audit["audit"]["vector_sha256"],
                "Canonical audit/artifact binding mismatch",
            )
    return {
        "schema_version": "mvp3-s1b-collection-v1",
        "binding": binding,
        "binding_sha256": checksum,
        "attempt_sha256": file_sha256(folder / "attempt.json"),
        "state": "native_returned"
        if returned
        else "intent_without_native_return"
        if intent
        else "no_native_intent",
        "budget_reserved_calls": int(intent),
        "observed_native_returns": int(returned),
        "worker_terminal_present": terminal is not None,
        "journal": {key: value for key, value in journal.items() if key != "frames"},
        "complete_frames": len(journal["frames"]),
        "verified_point_artifacts": vectors,
        "replayed_candidate_audits": candidates,
        "native_result": result,
        "scientific_qualification": "pending_full_run_record_resource_and_target_validation",
        "scheduler_state": None,
        "scheduler_missing_reason": "scheduler_accounting_is_separate_evidence",
        "automatic_retry": False,
    }
