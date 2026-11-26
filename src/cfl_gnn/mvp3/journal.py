"""Exclusive attempts, append-only chained events and immutable artifacts."""

import copy
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .contract import canonical_bytes, digest, load_json, require
from .matrix import real_value


def file_sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def durable_json(path, value):
    """An existing receipt is never truncated, normalized or replaced."""
    raw = canonical_bytes(value) + b"\n"
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if os.name == "posix":
        descriptor = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return file_sha256(path)


class AttemptStore:
    """No subprocess or solver invocation is exposed by the evidence store."""

    def __init__(
        self,
        folder,
        binding,
        *,
        event_limit,
        artifact_bytes_limit,
        candidate_limit,
        sync_every=16,
    ):
        require(
            type(event_limit) is int and 0 < event_limit <= 1000000,
            "Bounded positive event cap required",
        )
        require(
            type(artifact_bytes_limit) is int and artifact_bytes_limit > 0,
            "Positive storage cap required",
        )
        require(
            type(candidate_limit) is int and candidate_limit > 0,
            "Positive candidate cap required",
        )
        require(
            type(sync_every) is int and sync_every > 0,
            "Positive flush interval required",
        )
        require(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", binding["key"]["attempt"])
            is not None,
            "Invalid attempt token",
        )
        self.folder = Path(folder).resolve()
        self.folder.mkdir(parents=True, exist_ok=False)
        (self.folder / "artifacts").mkdir()
        self.binding = copy.deepcopy(binding)
        self.binding_sha256 = digest(binding)
        self.event_limit = event_limit
        self.artifact_bytes_limit = artifact_bytes_limit
        self.candidate_limit = candidate_limit
        self.sync_every = sync_every
        self.events = self.artifact_bytes = self.candidates = self.unsynced = 0
        self.previous = "0" * 64
        self.dropped = {"events": 0, "candidates": 0}
        self.final_reserve = 0
        self.stream = None
        durable_json(
            self.folder / "attempt.json",
            {
                "schema_version": "mvp3-s1b-attempt-v1",
                "binding": binding,
                "binding_sha256": self.binding_sha256,
                "measurement_limits": {
                    "events": event_limit,
                    "artifact_bytes": artifact_bytes_limit,
                    "candidate_vectors": candidate_limit,
                    "sync_every": sync_every,
                },
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "execution_authority": "external_concrete_author_CLI_release_required",
            },
        )
        self.stream = (self.folder / "native-events.jsonl").open("xb")

    def reserve_final_vectors(self, variable_count):
        require(
            self.artifact_bytes == 0
            and not (self.folder / "optimize.intent.json").exists(),
            "Reserve final evidence before optimisation",
        )
        require(
            type(variable_count) is int and variable_count > 0,
            "Invalid original vector count",
        )
        # Two float64 JSON representations: raw final point and canonical point.
        reserve = 2 * (32 * variable_count + 2)
        require(
            reserve + 32 * variable_count + 2 <= self.artifact_bytes_limit,
            "Storage envelope cannot retain a captured point and mandatory final evidence",
        )
        durable_json(
            self.folder / "measurement-admission.json",
            {
                "variable_count": variable_count,
                "reserved_final_bytes": reserve,
                "binding_sha256": self.binding_sha256,
            },
        )
        self.final_reserve = reserve

    def append(self, payload, *, critical=False):
        require(self.stream is not None, "Journal is closed")
        if self.events >= self.event_limit:
            self.dropped["events"] += 1
            return None
        frame = {
            "ordinal": self.events + 1,
            "previous_sha256": self.previous,
            "payload": payload,
        }
        checksum = digest(frame)
        raw = canonical_bytes({**frame, "frame_sha256": checksum}) + b"\n"
        require(len(raw) <= 1024 * 1024, "Journal frame exceeds the one-MiB envelope")
        self.stream.write(raw)
        self.events += 1
        self.unsynced += 1
        self.previous = checksum
        if critical or self.unsynced >= self.sync_every:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.unsynced = 0
        return checksum

    def put_vector(self, values, *, final=False):
        """Reserve a separate mandatory final point; never evict an earlier point."""
        if not final and self.candidates >= self.candidate_limit:
            self.dropped["candidates"] += 1
            return {
                "sha256": None,
                "reason": "candidate_capture_limit",
                "count": len(values),
            }
        checksum = hashlib.sha256()
        count = size = 0
        checksum.update(b"[")
        size += 1
        for index, value in enumerate(values):
            raw = canonical_bytes(real_value(value))
            if index:
                checksum.update(b",")
                size += 1
            checksum.update(raw)
            size += len(raw)
            count += 1
        checksum.update(b"]")
        size += 1
        identity = checksum.hexdigest()
        path = self.folder / "artifacts" / f"{identity}.json"
        if path.exists():
            require(
                file_sha256(path) == identity,
                "Corrupt existing vector must be preserved",
            )
            return {"sha256": identity, "reason": None, "count": count}
        available = (
            self.artifact_bytes_limit
            if final
            else self.artifact_bytes_limit - self.final_reserve
        )
        if self.artifact_bytes + size > available:
            self.dropped["candidates"] += 1
            return {"sha256": None, "reason": "artifact_byte_limit", "count": count}
        with path.open("xb") as stream:
            stream.write(b"[")
            for index, value in enumerate(values):
                if index:
                    stream.write(b",")
                stream.write(canonical_bytes(real_value(value)))
            stream.write(b"]")
            stream.flush()
            os.fsync(stream.fileno())
        require(file_sha256(path) == identity, "Vector changed during persistence")
        self.artifact_bytes += size
        if not final:
            self.candidates += 1
        return {"sha256": identity, "reason": None, "count": count}

    def optimize_intent(self, approval_reference):
        require(
            isinstance(approval_reference, str) and bool(approval_reference.strip()),
            "Concrete external approval reference required",
        )
        return durable_json(
            self.folder / "optimize.intent.json",
            {
                "binding_sha256": self.binding_sha256,
                "approval_reference": approval_reference,
                "approval_reference_authentication": "external_author_CLI_not_a_machine_signature",
                "maximum_native_calls": 1,
                "budget_reserved_on_intent": 1,
                "intent_does_not_prove_native_call_completion": True,
            },
        )

    def native_returned(self, status):
        return durable_json(
            self.folder / "native-return.json",
            {
                "binding_sha256": self.binding_sha256,
                "native_status": status,
                "native_call_returned": True,
            },
        )

    def close(self, outcome):
        if self.stream is not None:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.stream.close()
            self.stream = None
        return durable_json(
            self.folder / "worker-terminal.json",
            {
                "binding_sha256": self.binding_sha256,
                "attempt_sha256": file_sha256(self.folder / "attempt.json"),
                "receipt_sha256": {
                    name: file_sha256(self.folder / name)
                    for name in (
                        "measurement-admission.json",
                        "optimize.intent.json",
                        "native-return.json",
                        "native-result.json",
                    )
                    if (self.folder / name).is_file()
                },
                "outcome": outcome,
                "complete_frames": self.events,
                "last_frame_sha256": self.previous,
                "journal_sha256": file_sha256(self.folder / "native-events.jsonl"),
                "dropped": self.dropped,
                "artifact_bytes": self.artifact_bytes,
                "native_intent": (self.folder / "optimize.intent.json").is_file(),
                "native_returned": (self.folder / "native-return.json").is_file(),
                "automatic_retry": False,
            },
        )


def read_vector(folder, descriptor):
    require(descriptor["sha256"] is not None, "Unavailable vector cannot be audited")
    require(
        re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is not None,
        "Invalid vector hash",
    )
    path = Path(folder) / "artifacts" / f"{descriptor['sha256']}.json"
    require(
        file_sha256(path) == descriptor["sha256"],
        "Retained vector byte identity mismatch",
    )
    result = load_json(path)
    require(
        isinstance(result, list) and len(result) == descriptor["count"],
        "Retained vector shape mismatch",
    )
    return result


def scan_journal(folder):
    """Preserve a torn last frame; never silently accept tampering in the prefix."""
    import json

    path = Path(folder) / "native-events.jsonl"
    limit = load_json(Path(folder) / "attempt.json")["measurement_limits"]["events"]
    require(
        type(limit) is int and 0 < limit <= 1000000, "Invalid retained-event envelope"
    )
    previous = "0" * 64
    frames = []
    truncated = False
    with path.open("rb") as stream:
        while raw := stream.readline(1024 * 1024 + 1):
            require(len(raw) <= 1024 * 1024, "Oversized journal frame")
            if not raw.endswith(b"\n"):
                truncated = True
                break
            frame = json.loads(raw)
            require(canonical_bytes(frame) + b"\n" == raw, "Noncanonical journal JSON")
            require(len(frames) < limit, "Journal exceeds its declared event cap")
            checksum = frame.pop("frame_sha256")
            require(
                set(frame) == {"ordinal", "previous_sha256", "payload"},
                "Invalid journal frame",
            )
            require(
                frame["ordinal"] == len(frames) + 1
                and frame["previous_sha256"] == previous,
                "Broken journal ordinal/hash chain",
            )
            require(digest(frame) == checksum, "Journal frame was altered")
            previous = checksum
            frames.append(frame["payload"])
    return {
        "frames": frames,
        "truncated_tail": truncated,
        "last_frame_sha256": previous,
        "journal_sha256": file_sha256(path),
    }
