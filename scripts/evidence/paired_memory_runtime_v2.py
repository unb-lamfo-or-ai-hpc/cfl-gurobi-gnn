"""Exact qualified gate plus sanitized watchdog failure receipt; no new policy."""

import paired_memory_guard as watchdog
import paired_memory_runtime as previous
import pr78_scoped_evidence as evidence

qualified = evidence.load_candidate()
MemoryGate = qualified.MemoryGate
POLICY = dict(watchdog.POLICY)
GIB = watchdog.GIB
PROTOCOL = "job_scoped_hierarchical_ram_v2_candidate"
require = previous.require
STAGES = {
    "initial_policy_or_resolution",
    "path_identity",
    "hierarchy",
    "limit_read",
    "limit_parse",
    "membership_read",
    "membership_changed",
    "mount_baseline",
    "mount_read",
    "mount_resolution",
    "memory_mount_changed",
    "limit_changed",
    "usage_read_or_parse",
    "supervisor_sample",
}


def validate_public(value):
    normalized = dict(value)
    require(
        normalized.pop("mount_validation_scope")
        == "memory_controller_and_job_path_covering_mounts"
    )
    require(normalized.pop("sanitized_failure_diagnostics") is True)
    require(normalized["memory_gate_protocol"] == PROTOCOL)
    normalized["memory_gate_protocol"] = previous.PROTOCOL
    previous.validate_public(normalized)


def validate_diagnostic(value, stop):
    if stop != "memory_observation_lost":
        require(value is None)
        return
    previous.old.keys(
        value, "stage exception_type errno depth_from_leaf private_text_included"
    )
    require(value["stage"] in STAGES)
    require(
        value["exception_type"]
        in {
            "FileNotFoundError",
            "PermissionError",
            "OSError",
            "UnicodeError",
            "ValueError",
            "other",
        }
    )
    require(
        value["errno"] is None
        or (type(value["errno"]) is int and value["errno"] in {1, 2, 5, 13})
    )
    require(
        value["depth_from_leaf"] is None
        or (
            type(value["depth_from_leaf"]) is int
            and 0 <= value["depth_from_leaf"] <= 15
        )
    )
    require(value["private_text_included"] is False)


def supervise(command, console, deadline, gate):
    class ObservedGate:
        diagnostic = None

        def sample(self):
            try:
                return gate.sample()
            except Exception as exc:
                self.diagnostic = (
                    exc.diagnostic
                    if isinstance(exc, qualified.MemoryObservationError)
                    else qualified.failure("supervisor_sample", exc)
                )
                raise

    observed = ObservedGate()
    result = watchdog.supervise(command, console, deadline, observed)
    result["memory_failure_diagnostic"] = (
        observed.diagnostic
        if result["guard_stop"] == "memory_observation_lost"
        else None
    )
    validate_diagnostic(result["memory_failure_diagnostic"], result["guard_stop"])
    return result
