"""One technical qualification; synthetic training and one license-check MILP.

Importing this module performs no scientific work. Production entry requires
the reviewed environment, a Slurm allocation and one V100. No package install,
repository clone, real graph, historical checkpoint or DDP run is performed.
"""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import importlib.metadata as md
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

SOURCE_COMMIT = "16c2b29f97356e9ece7d72bbf12c3bf3fbcc289f"
SOURCES = {
    "gasse.py": "e4cfb67cf9f62d0ed7c6f05acd79454541a8d12c9db5ba62643cf7a7f6a9c81f",
    "gasse_calibrated.py": "9ad688b085a28c6a0e5cdd063fbaac60214a3214e2cbf10394b82608a9265eab",
    "matched_gpu.py": "5c1c00c3a5a4d0041b6a9f10808c8dc6acd4e09b218ebea6b58b79e0713ffc87",
}
TARGET_INVENTORY = "dafe3bf6020249096a4b8f31574b7a192cb3f3d45175f893e916aedd605dd82d"
ORIGINAL_INVENTORY = "94e163438088c2e35743c3858e35c60dbfd3b1c8fd05ec1b7ff6a54dce3bc750"
ARCHITECTURE = {
    "var_in_dim": 7,
    "cons_in_dim": 5,
    "edge_dim": 1,
    "hidden_dim": 32,
    "num_layers": 2,
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory_hash():
    values = sorted((d.metadata.get("Name", ""), d.version) for d in md.distributions())
    return digest(json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode())


def verify_sources(directory):
    for name, expected in SOURCES.items():
        file = directory / name
        if file.is_symlink() or digest(file.read_bytes()) != expected:
            raise ValueError("PROJECT_SOURCE_IDENTITY_CHANGED:" + name)


def load_training_parts(directory):
    """Load byte-identical model modules; extract the unchanged serial primitive.

    A temporary namespace avoids installing CFL or importing its data pipeline.
    Only serial_step is compiled from matched_gpu; its scheduling dependencies
    and the complete research training driver are intentionally not imported.
    """
    verify_sources(directory)
    if any(k == "cfl_gnn" or k.startswith("cfl_gnn.") for k in sys.modules):
        raise ValueError("UNEXPECTED_CFL_IMPORT_BEFORE_ISOLATED_SOURCE_TEST")
    for name in ("cfl_gnn", "cfl_gnn.models"):
        module = types.ModuleType(name)
        module.__path__ = [str(directory)]
        sys.modules[name] = module
    for leaf in ("gasse", "gasse_calibrated"):
        name = "cfl_gnn.models." + leaf
        spec = importlib.util.spec_from_file_location(name, directory / (leaf + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    text = (directory / "matched_gpu.py").read_text(encoding="utf-8")
    nodes = [
        n
        for n in ast.parse(text).body
        if isinstance(n, ast.FunctionDef) and n.name == "serial_step"
    ]
    if len(nodes) != 1:
        raise ValueError("SERIAL_STEP_IDENTITY_MISSING")
    namespace = {}
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), "matched_gpu.py", "exec"),
        namespace,
    )
    return sys.modules["cfl_gnn.models.gasse_calibrated"], namespace["serial_step"]


def train_synthetic(stage, device):
    """Three Adam updates over four own synthetic graphs; no research outcome."""
    import torch
    from torch_geometric.data import HeteroData

    calibrated, serial_step = load_training_parts(stage / "source")
    torch.manual_seed(42)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(42)
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    generator = torch.Generator().manual_seed(42)
    graphs = []
    for position in range(4):
        nv, nc = 8 + position, 5 + position
        graph = HeteroData()
        graph["variable"].x = torch.randn(nv, 7, generator=generator) * 0.1
        graph["constraint"].x = torch.randn(nc, 5, generator=generator) * 0.1
        var = torch.arange(nv).repeat_interleave(2)
        con = (var + torch.arange(len(var))) % nc
        edge = graph["variable", "rev_coef", "constraint"]
        edge.edge_index = torch.stack([var, con])
        edge.edge_attr = torch.randn(len(var), 1, generator=generator) * 0.1
        graph["variable"].binary_mask = torch.ones(nv, dtype=torch.bool)
        graph["variable"].y = (torch.arange(nv) % 2).float()
        graphs.append(graph.to(device))
    network = calibrated.GasseGNN(**ARCHITECTURE).to(device)
    prenorm = calibrated.fit_training_prenorm(network, graphs, device)
    if not all(bool(torch.isfinite(v).all()) for v in network.state_dict().values()):
        raise ValueError("NONFINITE_FITTED_STATE")
    initial = [p.detach().clone() for p in network.parameters()]
    optimizer = torch.optim.Adam(network.parameters(), lr=0.001)

    def loss(current, graph):
        edge = graph["variable", "rev_coef", "constraint"]
        prediction = current(
            graph["variable"].x,
            graph["constraint"].x,
            edge.edge_index,
            graph["variable"].binary_mask,
            edge.edge_attr,
        )
        return torch.nn.functional.binary_cross_entropy_with_logits(
            prediction,
            graph["variable"].y,
        )

    losses = []
    network.train()
    for _ in range(3):
        losses.append(serial_step(network, graphs, optimizer, loss))
        if not all(
            p.grad is not None and bool(torch.isfinite(p.grad).all())
            for p in network.parameters()
        ):
            raise ValueError("NONFINITE_OR_MISSING_GRADIENT")
    if not any(not torch.equal(a, b) for a, b in zip(initial, network.parameters())):
        raise ValueError("NO_PARAMETER_UPDATE")
    checkpoint = stage / "own-synthetic-training-state.pt"
    with checkpoint.open("xb") as stream:
        torch.save(
            {"model": network.state_dict(), "optimizer": optimizer.state_dict()}, stream
        )
    saved = torch.load(checkpoint, map_location=device, weights_only=True)
    restored = calibrated.GasseGNN(**ARCHITECTURE).to(device)
    restored.load_state_dict(saved["model"], strict=True)
    restored_optimizer = torch.optim.Adam(restored.parameters(), lr=0.001)
    restored_optimizer.load_state_dict(saved["optimizer"])
    if not all(
        torch.equal(v, saved["model"][k]) for k, v in restored.state_dict().items()
    ):
        raise ValueError("OWN_CHECKPOINT_ROUNDTRIP_FAILED")
    if device.type == "cuda":
        torch.cuda.synchronize()
    return {
        "compatibility": "PASS",
        "model_version": calibrated.MODEL_VERSION,
        "source_commit": SOURCE_COMMIT,
        "source_sha256": SOURCES,
        "architecture": ARCHITECTURE,
        "synthetic_graphs": 4,
        "optimizer_updates": 3,
        "training_graph_draws": 12,
        "seed": 42,
        "optimizer": "Adam",
        "learning_rate": 0.001,
        "gradient_clip_norm": 1.0,
        "losses_diagnostic_only": losses,
        "prenorm": prenorm,
        "finite_gradients": True,
        "parameters_changed": True,
        "own_model_optimizer_roundtrip": True,
        "historical_checkpoint_loaded": False,
        "real_data_loaded": False,
        "full_research_training_driver_tested": False,
        "DDP_tested": False,
        "predictive_quality_or_performance_claimed": False,
    }


def license_test(stage):
    """One trivial MILP above the bundled restricted license's variable limit."""
    import gurobipy as gp

    license_file = Path(os.environ["GRB_LICENSE_FILE"])
    if not license_file.is_file() or not os.access(license_file, os.R_OK):
        raise ValueError("CONFIGURED_LICENSE_NOT_READABLE")
    if gp.gurobi.version()[:2] != (14, 0):
        raise ValueError("GUROBI_RUNTIME_VERSION_CHANGED")
    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag", 0)
        env.start()
        with gp.Model("technical_license_check", env=env) as model:
            variables = model.addVars(2501, vtype=gp.GRB.BINARY)
            total = gp.quicksum(variables.values())
            model.addConstr(total >= 1)
            model.setObjective(total, gp.GRB.MINIMIZE)
            model.Params.Threads = 1
            model.Params.TimeLimit = 30
            model.update()
            intent = {
                "scope": "one_technical_license_check_not_CFL_evidence",
                "variables": 2501,
            }
            with (stage / "license-optimize.intent.json").open("x") as stream:
                json.dump(intent, stream)
            model.optimize()
            if model.Status != gp.GRB.OPTIMAL or model.SolCount < 1:
                raise ValueError("TECHNICAL_MILP_DID_NOT_RETURN_OPTIMAL")
            if abs(model.ObjVal - 1.0) > 1e-8 or abs(model.ObjBound - 1.0) > 1e-8:
                raise ValueError("TECHNICAL_MILP_OBJECTIVE_MISMATCH")
            return {
                "compatibility": "PASS",
                "license_initialized": True,
                "configured_file_used_without_copy": True,
                "above_bundled_restricted_variable_limit": True,
                "variables": model.NumVars,
                "constraints": model.NumConstrs,
                "status": model.Status,
                "solution_count": model.SolCount,
                "primal": model.ObjVal,
                "dual": model.ObjBound,
                "gap": model.MIPGap,
                "runtime_seconds": model.Runtime,
                "Threads": model.Params.Threads,
                "TimeLimit": model.Params.TimeLimit,
                "optimization_calls": 1,
                "CFL_instance_tested": False,
                "license_contents_or_ID_in_result": False,
                "native_version": list(gp.gurobi.version()),
            }


def main():
    stage = Path(sys.argv[1]).resolve(strict=True)
    result = {
        "scope": "synthetic_CFL_model_training_and_native_license_qualification_only",
        "cluster": "ufrn",
        "job_id": os.environ["SLURM_JOB_ID"],
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "compatibility": "FAIL",
        "automatic_retry": False,
    }
    expected_prefix = "/home/" + os.environ["USER"] + "/venv313_g14"
    if (
        sys.version_info[:3] != (3, 13, 15)
        or inventory_hash() != TARGET_INVENTORY
        or sys.prefix != expected_prefix
    ):
        raise ValueError("ENVIRONMENT_IDENTITY_CHANGED")
    if os.environ.get("GRB_LICENSE_FILE") != (
        "/home/" + os.environ["USER"] + "/model-agrologistic/secrets/gurobi.lic"
    ):
        raise ValueError("TEMPORARY_LICENSE_LOCATION_CHANGED")
    if os.environ.get("SLURM_JOB_PARTITION") != "gpu-8-v100":
        raise ValueError("PARTITION_CHANGED")
    if (
        os.environ.get("SLURM_NTASKS") != "1"
        or os.environ.get("SLURM_RESTART_COUNT", "0") != "0"
    ):
        raise ValueError("ALLOCATION_OR_RESTART_CHANGED")
    import torch

    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise ValueError("ONE_CUDA_DEVICE_REQUIRED_NO_CPU_FALLBACK")
    if "V100" not in torch.cuda.get_device_name(0):
        raise ValueError("GPU_FAMILY_CHANGED")
    result.update(
        python=sys.version.split()[0],
        inventory_sha256=inventory_hash(),
        gpu_name=torch.cuda.get_device_name(0),
        torch=torch.__version__,
        cpu_affinity_logical=sorted(os.sched_getaffinity(0)),
    )
    for name, operation in (
        ("gurobi_license", lambda: license_test(stage)),
        ("synthetic_training", lambda: train_synthetic(stage, torch.device("cuda:0"))),
    ):
        try:
            result[name] = operation()
        except Exception as error:
            # Native console and details remain private; public result has no raw error text.
            result[name] = {"compatibility": "FAIL", "error_type": type(error).__name__}
            number = getattr(error, "errno", None)
            if isinstance(number, int):
                result[name]["error_code"] = number
    result["compatibility"] = (
        "PASS"
        if all(
            result[name]["compatibility"] == "PASS"
            for name in ("gurobi_license", "synthetic_training")
        )
        else "FAIL"
    )
    result["ended_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    with (stage / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["compatibility"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
