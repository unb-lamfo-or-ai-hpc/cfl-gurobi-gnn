"""Read only fixed job3482 markers; no solver, scheduler, license or log text."""

import hashlib
import json
from pathlib import Path

ROOT = Path("/raid/vrcelestino/data/cfl-mvp2-evidence")
FLOW = ROOT / "pr78/recovery-job3481-v2/flow"
OP = (
    ROOT
    / "paired-matrix-submission-locks/6b81cd2d9ec6459e85e9da257883653c64d7ff8c2fb29fb3b32cffe55f6c8313"
)
MATRIX = (
    ROOT
    / "paired-matrix-locks/d17184004a1d22b425452d70d76d04722642914377bd002cbd2a6cbd9c449519"
)


def marker(path):
    if path.is_symlink():
        return {"state": "symlink_not_read"}
    if not path.exists():
        return {"state": "absent"}
    if path.is_dir():
        return {"state": "directory"}
    with path.open("rb") as stream:
        data = stream.read(65537)
    result = {"state": "file", "size": path.stat().st_size}
    if len(data) <= 65536:
        result["sha256"] = hashlib.sha256(data).hexdigest()
        if path.name == "STOP.json":
            value = json.loads(data)
            code = value.get("code", value.get("stop_code"))
            allowed = {
                "batch_failed",
                "collection_incomplete",
                "validation_failed",
                "memory_guard_stop",
                "memory_observation_lost",
                "child_deadline_exceeded",
                "unexpected_process_group_survivor",
                "child_process_failed",
                "worker_or_resource_stop",
                "parent_deadline_reserve",
                "submission_uncertain",
            }
            result["stop_code"] = code if code in allowed else "other_redacted"
    return result


paths = {
    "operator_stop": OP / "STOP.json",
    "matrix_claim": MATRIX,
    "matrix_started": MATRIX / "easy.started",
    "matrix_stop": MATRIX / "STOP.json",
    "parent_directory": FLOW / "easy",
    "parent_receipt": FLOW / "easy/parent_receipt.json",
    "batch_started": FLOW / "operator-state/easy/batch.started",
    "stderr_fingerprint_only": FLOW / "operator-state/easy/slurm-3482.private.err",
    "stdout_fingerprint_only": FLOW / "operator-state/easy/slurm-3482.private.out",
}
print(
    json.dumps(
        {
            "job_id": "3482",
            "markers": {k: marker(v) for k, v in paths.items()},
            "optimization_runs_added": 0,
            "scheduler_queries": 0,
            "raw_log_text_included": False,
            "historical_optimization_count": None,
        },
        indent=2,
    )
)
