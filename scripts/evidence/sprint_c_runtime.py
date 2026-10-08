"""CPU-only audit compatibility check; no dataset, license or scheduler access."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import platform
import re
import sys
from pathlib import Path

EXPECTED = {
    "torch": "2.10.0+cpu",
    "torch-geometric": "2.7.0",
    "numpy": "1.26.4",
    "scipy": "1.15.3",
    "gurobipy": "13.0.1",
    "packaging": "26.0",
}


def versions():
    result = {}
    for name in EXPECTED:
        try:
            value = importlib.metadata.version(name)
            result[name] = (
                value
                if re.fullmatch(r"[A-Za-z0-9.+_-]{1,100}", value)
                else "redacted_nonstandard_version"
            )
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def require(condition, code):
    if not condition:
        raise ValueError(code)


def check_versions(actual, python):
    require(tuple(python[:2]) == (3, 10), "python_310_required")
    require(actual == EXPECTED, "exact_cpu_runtime_required")


def smoke():
    # Import only after exact distribution versions passed.
    import gurobipy
    import numpy as np
    import scipy.sparse
    import torch
    import torch_geometric
    from audit_sprint_c_numeric import load_graph
    from torch_geometric.data import HeteroData

    require(str(torch.__version__) == EXPECTED["torch"], "imported_torch_mismatch")
    require(torch_geometric.__version__ == "2.7.0", "imported_pyg_mismatch")
    require(torch.version.cuda is None, "cpu_build_required")
    require(gurobipy.gurobi.version() == (13, 0, 1), "gurobi_version_mismatch")
    torch.set_num_threads(1)
    graph = HeteroData()
    graph["variable"].x = torch.tensor([[1.0, 2.0]])
    graph["constraint"].x = torch.tensor([[3.0]])
    graph["constraint", "coef", "variable"].edge_index = torch.tensor([[0], [0]])
    graph["constraint", "coef", "variable"].edge_attr = torch.tensor([[4.0]])
    graph.source_instance_id = "synthetic_preflight_only"
    stream = io.BytesIO()
    torch.save(graph, stream)
    stream.seek(0)
    restored, _ = load_graph(stream)
    require(torch.equal(restored["variable"].x, graph["variable"].x), "roundtrip")
    require(restored.source_instance_id == graph.source_instance_id, "identity")
    require(
        np.array_equal(scipy.sparse.coo_matrix([[1.0]]).toarray(), np.array([[1.0]])),
        "numpy_scipy_interop",
    )


def probe():
    stage = "environment_metadata"
    report = {
        "schema_version": 1,
        "protocol_id": "sprint_c_cpu_runtime_preflight_v1",
        "passed": False,
        "python": platform.python_version(),
        "package_versions": versions(),
        "dataset_graph_loads": 0,
        "synthetic_graph_roundtrip_passed": False,
        "optimization_runs_added": 0,
        "submissions_added": 0,
        "training_admitted": False,
        "private_text_included": False,
    }
    try:
        check_versions(report["package_versions"], sys.version_info)
        stage = "synthetic_restricted_load_and_imports"
        smoke()
        report.update(passed=True, synthetic_graph_roundtrip_passed=True)
    except Exception as error:
        report.update(stage=stage, exception_type=type(error).__name__)
    return report


def package(stage):
    """Export only sanitized JSON receipts; installation reports stay private."""
    from audit_sprint_c_numeric import (
        PROTOCOL,
        RECEIPT_SHA,
        selected_parents,
        source_receipt,
    )

    stage = Path(stage)
    numeric_raw = (stage / "run/results/numeric.json").read_bytes()
    require(len(numeric_raw) <= 4 * 1024**2, "numeric_receipt_size")
    numeric = json.loads(numeric_raw)
    require(numeric["protocol_id"] == PROTOCOL, "numeric_protocol")
    require(
        numeric["source_artifact_receipt_sha256"] == RECEIPT_SHA, "artifact_identity"
    )
    require(
        set(numeric["parents"]) == set(selected_parents(source_receipt())), "parents"
    )
    require(
        numeric["implementation_sha256"]
        == hashlib.sha256(
            Path(__file__).with_name("audit_sprint_c_numeric.py").read_bytes()
        ).hexdigest(),
        "auditor_identity",
    )
    require(
        numeric["training_admitted"] is False
        and numeric["scientific_reporting_eligible"] is False
        and numeric["raw_logs_included"] is False
        and numeric["optimization_runs_added"] == 0,
        "numeric_scope",
    )
    runtime = {}
    for name in ("prepared", "presubmit", "batch"):
        raw = (stage / f"runtime-{name}.json").read_bytes()
        require(len(raw) <= 64 * 1024, "runtime_receipt_size")
        value = json.loads(raw)
        require(
            value["protocol_id"] == "sprint_c_cpu_runtime_preflight_v1",
            "runtime_protocol",
        )
        require(value["passed"] is True, "runtime_not_passed")
        check_versions(
            value["package_versions"], tuple(int(p) for p in value["python"].split("."))
        )
        runtime[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "receipt": value}
    result = {
        "protocol_id": "sprint_c_cpu_audit_return_v1",
        "numeric_sha256": hashlib.sha256(numeric_raw).hexdigest(),
        "numeric": numeric,
        "runtime": runtime,
        "environment_freeze_sha256": hashlib.sha256(
            (stage / "environment.freeze.txt").read_bytes()
        ).hexdigest(),
        "job_id": (stage / "job_id.txt").read_text().strip(),
        "training_admitted": False,
        "raw_logs_included": False,
    }
    require(re.fullmatch(r"[0-9]+", result["job_id"]), "job_identity")
    raw = json.dumps(result, sort_keys=True, indent=2).encode() + b"\n"
    target = stage / "audit-return.json"
    if target.exists():
        require(target.read_bytes() == raw, "existing_return_differs")
    else:
        with target.open("xb") as stream:
            stream.write(raw)
    print("AUDIT_RETURN_SHA256=" + hashlib.sha256(raw).hexdigest())
    print("AUDIT_RETURN=" + str(target))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--package", type=Path)
    args = parser.parse_args()
    if args.package:
        package(args.package)
        return 0
    report = probe()
    raw = json.dumps(report, sort_keys=True, indent=2).encode() + b"\n"
    with args.output.open("xb") as stream:
        stream.write(raw)
    print(json.dumps(report, sort_keys=True))
    print("RUNTIME_RECEIPT_SHA256=" + hashlib.sha256(raw).hexdigest())
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
