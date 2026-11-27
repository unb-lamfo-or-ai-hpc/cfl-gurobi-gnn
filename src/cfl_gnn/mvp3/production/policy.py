"""Technical qualification envelope, separate from the 177 scientific cells."""

import re
from pathlib import Path

from ..contract import approved_contract, digest, require
from . import VERSION

PROFILES = {
    "intel-256": {"memory_GiB": 192, "families": ["easy", "medium"]},
    "intel-512": {"memory_GiB": 384, "families": ["hard"]},
}
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")


def token(value):
    require(
        isinstance(value, str) and TOKEN.fullmatch(value) is not None,
        "Invalid scheduler token",
    )
    return value


def ascii_path(value, *, resolve_links=True):
    # Resolving a venv's python symlink would silently select its base environment.
    path = Path(value).resolve() if resolve_links else Path(value).absolute()
    require(
        str(path).isascii() and not any(c.isspace() for c in str(path)),
        "ASCII path without whitespace required for the native/batch interface",
    )
    return path


def policy():
    return {
        "schema_version": VERSION,
        "scientific_execution_authorized": False,
        "dedicated_execution_directory": "cfl-gurobi-gnn-mvp30",
        "runtime_subdirectory": "runs",
        "transfer_subdirectory": "incoming",
        "home_root_outputs_allowed": False,
        "profiles": PROFILES,
        "tasks": 1,
        "logical_CPUs": 64,
        "physical_cores": 32,
        "sockets": 2,
        "cores_per_socket": 16,
        "threads_per_core": 2,
        "exclusive": True,
        "requested_GPUs": 0,
        "maximum_jobs": 2,
        "maximum_Gurobi_sessions_within_plan": 2,
        "maximum_technical_calls": 2,
        "maximum_native_calls_per_slot": 1,
        "native_seconds_per_call": 10,
        "worker_wall_seconds": 60,
        "job_seconds": 300,
        "automatic_retry": False,
        "primary_contract_sha256": digest(approved_contract()),
        "primary_calls_released": 0,
        "capacity_scope": "reservation_affinity_and_kernel_limit_not_memory_saturation_or_real_CFL_performance",
    }


def technical_parameters():
    return {
        **approved_contract()["solver"]["profiles"]["root_relaxation"],
        "TimeLimit": 10,
    }


def slurm_pairs(text):
    """scontrol -o fields may have spaces; select field boundaries, not words."""
    matches = list(re.finditer(r"(?:^|\s)([A-Za-z][A-Za-z0-9_/]*)=", text))
    result = {}
    for index, match in enumerate(matches):
        name = match.group(1)
        require(name not in result, "Duplicate scheduler field")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[name] = text[match.end() : end].strip()
    return result


def memory_bytes(value):
    match = re.fullmatch(r"([0-9]+)([KMGT]?)", value)
    require(match is not None, "Unknown Slurm memory quantity")
    # Slurm's unsuffixed memory quantities are MiB.
    return (
        int(match[1])
        * {"": 1024**2, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[match[2]]
    )


def candidate(node, profile):
    try:
        ram = int(node["RealMemory"]) * 1024**2
        topology = tuple(
            int(node[name])
            for name in ("Sockets", "CoresPerSocket", "ThreadsPerCore", "CPUTot")
        )
        return (
            topology == (2, 16, 2, 64)
            and ram >= PROFILES[profile]["memory_GiB"] * 1024**3
            and (profile == "intel-512" or ram < 384 * 1024**3)
            and node.get("Gres", "(null)") in ("(null)", "N/A", "None", "")
            and not any(
                flag in node.get("State", "")
                for flag in ("DOWN", "DRAIN", "FAIL", "INVAL")
            )
        )
    except (KeyError, ValueError):
        return False
