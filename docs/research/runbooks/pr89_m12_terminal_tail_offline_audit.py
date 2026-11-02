"""Offline extension of the reviewed M12 exact-primal audit; no solver."""

import argparse
import gc, gzip, hashlib, importlib.util, io, json, math, sys, zipfile
from pathlib import Path
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tail", type=Path, required=True)
parser.add_argument("--reference-archive", type=Path, required=True)
parser.add_argument("--public-output", type=Path, required=True)
parser.add_argument("--private-output", type=Path, required=True)
args = parser.parse_args()
if args.public_output.exists() or args.private_output.exists():
    raise ValueError("PRESERVE_EXISTING_OUTPUT")
src = Path(__file__).with_name("pr89_m12_offline_audit.py")
spec = importlib.util.spec_from_file_location("m12_reviewed_arithmetic", src)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
TAIL = args.tail
REF = args.reference_archive
a.need(
    hashlib.sha256(TAIL.read_bytes()).hexdigest()
    == "12b07fce5b49dd7540bd5cd26be2a54cfad2cfccc5b42999373da5d7ae29f85f",
    "tail_digest",
)
a.need(hashlib.sha256(REF.read_bytes()).hexdigest() == a.SHA, "reference_digest")
solutions = {}
children = {}
rows = []
private = []
with zipfile.ZipFile(TAIL) as z, zipfile.ZipFile(REF) as original:
    manifest = json.loads(z.read("tail-manifest.json"))
    for name, h in manifest["sha256"].items():
        a.need(hashlib.sha256(z.read(name)).hexdigest() == h, "tail_member")
    original_manifest = json.loads(original.read("forensic-manifest.json"))
    a.need(
        hashlib.sha256(original.read("model.private.lp.gz")).hexdigest() == a.MODEL_SHA,
        "model_digest",
    )
    for i in range(54, 60):
        children[i] = json.loads(z.read(f"runs/{i}/child.json"))
        a.need(
            children[i]["gurobi_log"]["log_sha256"]
            == manifest["sha256"][f"runs/{i}/gurobi.private.log"],
            "closed_log_seal",
        )
        raw = gzip.decompress(z.read(f"runs/{i}/solution.private.json.gz"))
        a.need(len(raw) < 512 * 2**20, "vector_size")
        solution = json.loads(raw)
        a.need(
            solution["mip_sha256"] == a.MODEL_SHA
            and solution["objective_sense"] == "MINIMIZE",
            "solution_model",
        )
        a.need(
            solution["objective"] == children[i]["result"]["solve"]["primal"],
            "solution_objective",
        )
        a.need(
            len(solution["variables"]) == a.N
            and all(n == f"x{k}" for k, n in enumerate(solution["variables"])),
            "variables",
        )
        x = np.fromiter(solution["variables"].values(), dtype=np.float64, count=a.N)
        a.need(np.isfinite(x).all(), "finite")
        solutions[i] = x
        del solution, raw
        gc.collect()
    a.need(
        len({c["result"]["mathematical_signature_sha256"] for c in children.values()})
        == 1,
        "same_model",
    )
    active = np.logical_or.reduce([x != 0 for x in solutions.values()])
    with io.TextIOWrapper(
        gzip.GzipFile(fileobj=original.open("model.private.lp.gz"))
    ) as stream:
        model = a.parse_lp(stream, active)
    print("PARSED_ORIGINAL_MODEL_SIX_VECTORS", flush=True)
    for i, x in solutions.items():
        r = children[i]["result"]
        d, p = a.diagnostics(model, x, r["solve"]["primal"])
        logs = a.log_summary(z.read(f"runs/{i}/gurobi.private.log").decode())
        a.need(
            math.isclose(
                d["max_integrality_residual"],
                r["independent_feasibility"]["max_integrality_residual"],
                rel_tol=1e-12,
                abs_tol=1e-18,
            ),
            "integrality_parity",
        )
        a.need(
            math.isclose(
                d["stored"]["objective_exact_binary64_inputs"],
                r["solve"]["primal"],
                rel_tol=1e-12,
                abs_tol=1e-12,
            ),
            "objective_parity",
        )
        a.need(logs["nodes"] == r["solve"]["node_count"], "nodes_parity")
        rows.append(
            {
                "job_id": str(3675 + i),
                "method": children[i]["cell"]["method"],
                "threads": children[i]["cell"]["threads"],
                "child_sha256": manifest["sha256"][f"runs/{i}/child.json"],
                "solution_sha256_observed_at_collection": manifest["sha256"][
                    f"runs/{i}/solution.private.json.gz"
                ],
                "historically_sealed_log_sha256": manifest["sha256"][
                    f"runs/{i}/gurobi.private.log"
                ],
                "numeric_vector_binary64_sha256": hashlib.sha256(
                    x.astype("<f8", copy=False).tobytes()
                ).hexdigest(),
                "diagnostics": d,
                "log": logs,
            }
        )
        private.append({"job_id": str(3675 + i), "details": p})
        print(
            "AUDITED",
            3675 + i,
            "exact_primal",
            d["exact_integer_primal_feasible_decimal_lp_model"],
            "nonintegral",
            d["nonintegral_binary_count"],
            "round_residual",
            d["integer_rounded_copy"]["exact_decimal_lp_rows"]["max_row_residual"],
            flush=True,
        )
public = {
    "protocol": "pr89_m12_terminal_tail_exact_primal_arithmetic_v1",
    "date": "2026-11-01",
    "tail_archive_sha256": manifest and hashlib.sha256(TAIL.read_bytes()).hexdigest(),
    "original_model_reference_archive_sha256": a.SHA,
    "original_model_sha256": a.MODEL_SHA,
    "reviewed_arithmetic_source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
    "extension_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "offline_environment": {"python": sys.version.split()[0], "numpy": np.__version__},
    "scope": "all original rows/domains/objective for six stored vectors and diagnostic integer-rounded copies, decimal-LP and binary64 interpretations; no repair or dual proof",
    "rows": rows,
    "raw_variable_values_or_rows_exported": False,
    "exact_global_optimality_certified": False,
    "certified_speedup": False,
    "campaign_modified": False,
    "optimization_calls_added": 0,
}
args.public_output.write_text(
    json.dumps(public, indent=2, sort_keys=True, allow_nan=False) + "\n",
    encoding="utf-8",
)
args.private_output.write_text(
    json.dumps(private, indent=2, sort_keys=True, allow_nan=False) + "\n",
    encoding="utf-8",
)
