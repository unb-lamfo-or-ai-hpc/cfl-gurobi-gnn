"""Load only the exact no-solver-qualified candidate and its frozen dependencies."""

import importlib.util
from pathlib import Path

import isolated_attempt_worker as old
import pr78_hierarchy_evidence as previous

QUALIFICATION_SHA = "c8bb9a0213f1067e8258cb0c0074a087e742e0c048cabb44f20960217942013e"
QUALIFICATION_PATH = "docs/evidence/pr78/job3491/qualification.json"
CANDIDATE_PATH = "docs/evidence/pr78/job3491/paired_memory_guard_v4.py"
CANDIDATE_SHA = "e66696aadeced1d7cbdbeed6a232bb380765b11887667747c85d5345d99a6695"
GUARDS = previous.GUARDS


def review(source):
    source = Path(source)
    previous.review(source)
    raw = old.read_bytes(source / QUALIFICATION_PATH)
    old.require(old.contract.sha(raw) == QUALIFICATION_SHA)
    value = old.strict_payload(raw)
    old.require(value["job_id"] == "3491" and value["mode"] == "allocated")
    old.require(value["candidate_qualified_in_this_allocation"] is True)
    old.require(value["candidate_integrated_into_executor"] is False)
    old.require(value["scientific_reporting_eligible"] is False)
    old.require(value["optimization_runs_added"] == 0)
    old.require(value["dependency_sha256"] == GUARDS)
    old.require(value["candidate_sha256"] == CANDIDATE_SHA)
    old.require(
        old.contract.sha(old.read_bytes(source / CANDIDATE_PATH)) == CANDIDATE_SHA
    )
    return value


def load_candidate():
    source = Path(__file__).resolve().parents[2]
    review(source)
    spec = importlib.util.spec_from_file_location(
        "pr78_exact_job3491_candidate", source / CANDIDATE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
