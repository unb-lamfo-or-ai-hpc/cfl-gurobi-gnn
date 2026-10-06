"""Read-only binding to job3485 and exact installed memory-guard bytes."""

from pathlib import Path

import isolated_attempt_worker as old

QUALIFICATION_SHA = "71591edbffe32de84792d6b75d38661618291057e95f2fce6812729bed70a63c"
QUALIFICATION_PATH = "docs/evidence/pr78/job3485/qualification.json"
GUARDS = {
    "paired_memory_guard.py": "8f99b5bdaa8c4722618787b4409af56b95f25c8df2f1b284074fef860ec12186",
    "paired_memory_guard_v2.py": "faadff7e998d213497237e56c9f373ece0f5fd256a60bb266e4ad279557a238e",
    "paired_memory_guard_v3.py": "2726b80752f63106f8914d9073d852bc346bce4058a7aa4784e50e854d6daff1",
}


def review(source):
    source = Path(source)
    raw = old.read_bytes(source / QUALIFICATION_PATH)
    old.require(old.contract.sha(raw) == QUALIFICATION_SHA)
    value = old.strict_payload(raw)
    old.require(value["candidate_qualified_in_this_allocation"] is True)
    old.require(value["candidate_integrated_into_executor"] is False)
    old.require(value["mode"] == "allocated")
    old.require(value["environment"]["SLURM_JOB_ID"] == "3485")
    old.require(value["scientific_reporting_eligible"] is False)
    old.require(value["optimization_runs_added"] == 0)
    for name, sha in GUARDS.items():
        old.require(
            old.contract.sha(old.read_bytes(source / "scripts/evidence" / name)) == sha
        )
    return value
