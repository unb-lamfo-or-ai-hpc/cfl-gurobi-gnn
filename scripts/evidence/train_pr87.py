"""Full matched serial/DDP4 training on existing PR80 graphs; never optimize."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

import pr87_contract as c

sys.path.insert(0, str(c.REPO / "src"))
from cfl_gnn.training.matched_gpu import (  # noqa: E402
    ddp_step,
    epoch_batches,
    schedule_hash,
    serial_step,
    state_hash,
)


def curve_score(targets, probabilities, threshold):
    """Existing trapezoidal PR-AUC semantics without materializing curve dicts."""
    import numpy as np

    y = np.asarray(targets, dtype=np.float64) >= 0.5
    p = np.asarray(probabilities, dtype=np.float64)
    c.require(len(y) > 0 and p.shape == y.shape and np.isfinite(p).all(), "predictions")
    c.require(bool(((p >= 0) & (p <= 1)).all()), "probability_range")
    pred = p >= threshold
    tp, fp, fn = int((pred & y).sum()), int((pred & ~y).sum()), int((~pred & y).sum())
    tn = len(y) - tp - fp - fn
    order = np.argsort(-p, kind="stable")
    ys, ps = y[order], p[order]
    ends = np.flatnonzero(np.r_[ps[1:] != ps[:-1], True])
    positives = int(y.sum())
    tps = np.cumsum(ys)[ends]
    fps = ends + 1 - tps
    recall = np.r_[0.0, tps / max(1, positives), 1.0 if positives else 0.0]
    precision = np.r_[1.0, tps / (tps + fps), positives / len(y)]
    return {
        "n_targets": len(y),
        "n_positive": positives,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "f1_score": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "pr_auc": float(
            ((precision[1:] + precision[:-1]) * (recall[1:] - recall[:-1]) / 2).sum()
        )
        if positives
        else None,
        "brier": float(np.mean((p - y) ** 2)),
    }


class Graphs:
    """Hash-bound internal pickles only; cache CPU graphs, return clones."""

    def __init__(self, rows, bindings):
        self.rows = {r["parent"]: r for r in rows}
        self.bindings = bindings
        self.cache = {}
        self.allowed = {"train", "validation"}

    def get(self, parent):
        import torch
        from torch_geometric.data import HeteroData

        row = self.rows[parent]
        c.require(row["role"] in self.allowed, "test_access_before_selection")
        if parent not in self.cache:
            path = Path(self.bindings[parent]["graph"])
            # Hash and deserialize from the same open stream, never arbitrary pickles.
            with path.open("rb") as stream:
                value = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024**2), b""):
                    value.update(chunk)
                c.require(value.hexdigest() == row["graph"]["sha256"], "graph_hash")
                stream.seek(0)
                graph = torch.load(stream, map_location="cpu", weights_only=False)
            c.require(type(graph) is HeteroData, "graph_type")
            c.require(
                graph.sample_id
                == graph.source_instance_id
                == graph.parent_instance_id
                == parent,
                "graph_parent",
            )
            c.require(
                graph.role == row["role"]
                and int(graph.instance_fold) == row["fold"]
                and graph.objective_sense == "MINIMIZE"
                and graph.graph_authority == "gurobi",
                "graph_contract",
            )
            self.cache[parent] = graph
        return self.cache[parent].clone()


def rank_affinity(world, rank):
    from pr66_thread_pilot import physical_mask

    def topology(cpu):
        base = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        return tuple(
            int((base / k).read_text()) for k in ("physical_package_id", "core_id")
        )

    cores = physical_mask(os.sched_getaffinity(0), topology, required=4 * world)
    subset = cores[rank * 4 : rank * 4 + 4]
    os.sched_setaffinity(0, subset)
    c.require(set(os.sched_getaffinity(0)) == set(subset), "rank_affinity")
    return {"physical_cores": 4, "logical_cpu_ids": subset}


def run(stage, index):
    started = time.monotonic()
    frozen = c.read(stage / "plan.json")
    config = frozen["protocol"]
    seed, world = config["pair_order"][index]
    c.require(c.source() == frozen["source_commit"], "source_changed")
    c.require(
        os.environ.get("SLURM_JOB_NUM_NODES") == "1"
        and os.environ.get("SLURM_RESTART_COUNT", "0") == "0"
        and os.environ.get("SLURM_CPUS_PER_TASK") == str(world * 4)
        and os.environ.get("SLURM_MEM_PER_NODE") == "131072",
        "allocation",
    )
    rank = int(os.environ.get("RANK", "0"))
    local = int(os.environ.get("LOCAL_RANK", "0"))
    c.require(
        int(os.environ.get("WORLD_SIZE", "1")) == world and 0 <= rank < world,
        "rank_world",
    )
    affinity = rank_affinity(world, rank)
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    import numpy as np
    import torch
    import torch.distributed as dist
    from torch.nn.parallel import DistributedDataParallel

    from cfl_gnn.models.gasse_calibrated import fit_training_prenorm
    from cfl_gnn.models.versioning import model_class
    from cfl_gnn.training.binary_contract import binary_targets
    from cfl_gnn.training.gasse_reconnected import threshold_from_validation

    c.require(
        torch.cuda.is_available() and torch.cuda.device_count() == world,
        "allocated_gpus",
    )
    c.require(
        all("V100" in torch.cuda.get_device_name(i) for i in range(world)),
        "V100_required",
    )
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.cuda.set_device(local)
    device = torch.device("cuda", local)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    if world == 4:
        # CPU train-only fitting occurs on rank0 after initialization. Bound
        # collectives by the job watchdog, not an invented short fitting limit.
        dist.init_process_group("nccl", timeout=datetime.timedelta(seconds=42000))
    output = stage / "runs" / str(index)
    c.require(output.is_dir() and not (output / "result.json").exists(), "fresh_run")
    bindings_raw = (stage / "private_bindings.json").read_bytes()
    approval = c.read(stage / "approval.json")
    c.require(
        c.sha(bindings_raw) == approval["bindings_sha256"], "private_binding_changed"
    )
    data = Graphs(frozen["records"], json.loads(bindings_raw))
    by_role = {
        role: [r["parent"] for r in frozen["records"] if r["role"] == role]
        for role in ("train", "validation", "test")
    }
    training = by_role["train"]
    network = model_class(config["model_version"])(**config["architecture"])
    unfitted_hash = state_hash(network)
    prep_started = time.monotonic()
    prenorm = None
    positives, negatives = 0, 0
    if rank == 0:

        class TrainingView:
            def __len__(self):
                return len(training)

            def __getitem__(self, position):
                return data.get(training[position])

        # CPU fitting makes the initial fitted buffers identical across arms.
        # Reuse the existing streaming train-only fitter, never validation/test.
        prenorm = fit_training_prenorm(network, TrainingView(), torch.device("cpu"))
        for parent in training:
            _, labels = binary_targets(data.get(parent))
            pos = int(labels.sum())
            positives += pos
            negatives += len(labels) - pos
    network.to(device)
    if world == 4:
        for buffer in network.buffers():
            dist.broadcast(buffer, src=0)
    model = (
        DistributedDataParallel(network, device_ids=[local], broadcast_buffers=False)
        if world == 4
        else network
    )
    # Explicit buffer broadcast above; DDP synchronizes parameters at construction.
    weight = torch.tensor([negatives / positives if positives else 1.0], device=device)
    if world == 4:
        dist.broadcast(weight, src=0)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=weight)
    initial_hash = state_hash(network)
    if world == 4:
        hashes = [None] * world
        dist.all_gather_object(hashes, initial_hash)
        c.require(len(set(hashes)) == 1, "initial_state_rank_mismatch")
    if index == 1 and rank == 0:
        paired = c.read(stage / "runs/0/result.json")
        c.require(
            initial_hash == paired["initial_state_sha256"]
            and unfitted_hash == paired["unfitted_state_sha256"]
            and float(weight.item()) == paired["pos_weight"]
            and schedule_hash(training, seed) == paired["schedule_sha256"],
            "paired_initialization_mismatch_before_training",
        )
    torch.cuda.synchronize()
    prep_seconds = time.monotonic() - prep_started
    torch.cuda.reset_peak_memory_stats()
    optimizer = torch.optim.Adam(network.parameters(), lr=0.001)

    def logits(current, graph):
        mask, targets = binary_targets(graph)
        edge = graph["variable", "rev_coef", "constraint"]
        output_logits = current(
            x_var=graph["variable"].x,
            x_cons=graph["constraint"].x,
            edge_v2c=edge.edge_index,
            binary_mask=mask,
            edge_attr=edge.edge_attr,
        )
        return output_logits, targets

    def loss_item(current, parent):
        graph = data.get(parent).to(device)
        prediction, target = logits(current, graph)
        return loss_fn(prediction, target)

    def synchronize():
        torch.cuda.synchronize()
        if world == 4:
            dist.barrier()

    def broadcast(value):
        tensor = torch.tensor([value], device=device, dtype=torch.float64)
        if world == 4:
            dist.broadcast(tensor, src=0)
        return float(tensor.item())

    def validation_loss():
        network.eval()
        with torch.no_grad():
            return sum(float(loss_item(network, p)) for p in by_role["validation"]) / 10

    def predict(parents):
        network.eval()
        result = []
        with torch.no_grad():
            for parent in parents:
                prediction, target = logits(network, data.get(parent).to(device))
                result.append(
                    (
                        parent,
                        target.cpu().numpy(),
                        torch.sigmoid(prediction).cpu().numpy(),
                    )
                )
        return result

    def select_threshold():
        rows = predict(by_role["validation"])
        return threshold_from_validation(
            np.concatenate([r[1] for r in rows]), np.concatenate([r[2] for r in rows])
        )

    def test_metrics(threshold):
        predictions = predict(by_role["test"])
        rows = [
            {"parent": p, **curve_score(y, probabilities, threshold)}
            for p, y, probabilities in predictions
        ]
        pooled = curve_score(
            np.concatenate([r[1] for r in predictions]),
            np.concatenate([r[2] for r in predictions]),
            threshold,
        )
        return rows, pooled

    history, best_loss, best_epoch = [], float("inf"), 0
    total_train = 0.0
    synchronize()
    loop_started = time.monotonic()
    for epoch in range(100):
        model.train()
        synchronize()
        epoch_start = time.monotonic()
        losses = []
        for batch in epoch_batches(training, seed, epoch):
            if world == 1:
                loss = serial_step(model, batch, optimizer, loss_item)
            else:
                loss = ddp_step(model, batch[rank], optimizer, loss_item)
            losses.append(loss)
        torch.cuda.synchronize()
        seconds = torch.tensor(
            [time.monotonic() - epoch_start], device=device, dtype=torch.float64
        )
        mean_loss = torch.tensor(
            [sum(losses) / len(losses)], device=device, dtype=torch.float64
        )
        if world == 4:
            dist.all_reduce(seconds, op=dist.ReduceOp.MAX)
            dist.all_reduce(mean_loss, op=dist.ReduceOp.SUM)
            mean_loss /= world
        total_train += float(seconds.item())
        val = validation_loss() if rank == 0 else 0.0
        val = broadcast(val)
        c.require(
            np.isfinite(val) and np.isfinite(float(mean_loss.item())), "nonfinite_epoch"
        )
        if rank == 0:
            history.append(
                {
                    "epoch": epoch + 1,
                    "train_loss": float(mean_loss.item()),
                    "validation_loss": val,
                    "training_seconds": float(seconds.item()),
                    "global_draws": 136,
                    "optimizer_updates": 34,
                }
            )
            if val < best_loss:
                best_loss, best_epoch = val, epoch + 1
                torch.save(network.state_dict(), output / "best_model.pt")
            print(json.dumps({"epoch": epoch + 1, "validation_loss": val}), flush=True)
        synchronize()
    training_validation_seconds = time.monotonic() - loop_started
    rank_resources = {
        "rank": rank,
        "affinity": affinity,
        "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "gpu_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
    }
    resources = [rank_resources]
    if world == 4:
        resources = [None] * world
        dist.all_gather_object(resources, rank_resources)
    if rank == 0:
        terminal_hash = state_hash(network)
        torch.save(network.state_dict(), output / "terminal_model.pt")
        terminal_threshold = select_threshold()
        data.allowed.add("test")
        terminal_test, terminal_pooled = test_metrics(terminal_threshold)
        network.load_state_dict(
            torch.load(output / "best_model.pt", map_location=device, weights_only=True)
        )
        selected_hash = state_hash(network)
        selected_threshold = select_threshold()
        selected_test, selected_pooled = test_metrics(selected_threshold)
        import sprint_c_runtime

        result = {
            "state": "complete",
            "source_commit": frozen["source_commit"],
            "plan_sha256": c.sha((stage / "plan.json").read_bytes()),
            "seed": seed,
            "world_size": world,
            "job_id": os.environ["SLURM_JOB_ID"],
            "epochs_completed": 100,
            "optimizer_updates": 3400,
            "global_graph_draws": 13600,
            "unfitted_state_sha256": unfitted_hash,
            "initial_state_sha256": initial_hash,
            "schedule_sha256": schedule_hash(training, seed),
            "selected_state_sha256": selected_hash,
            "terminal_state_sha256": terminal_hash,
            "checkpoint_files_sha256": {
                name: c.sha((output / name).read_bytes())
                for name in ("best_model.pt", "terminal_model.pt")
            },
            "best_epoch": best_epoch,
            "best_validation_loss": best_loss,
            "selected_threshold": selected_threshold,
            "terminal_threshold": terminal_threshold,
            "pos_weight": float(weight.item()),
            "training_positive_targets": positives,
            "training_negative_targets": negatives,
            "prenorm": prenorm,
            "preparation_seconds": prep_seconds,
            "training_loop_seconds": total_train,
            "training_validation_checkpoint_seconds": training_validation_seconds,
            "process_wall_seconds": time.monotonic() - started,
            "rank_resources": resources,
            "validation_parents": 10,
            "test_parents": 10,
            "history": history,
            "test": {"selected": selected_test, "terminal": terminal_test},
            "test_pooled": {"selected": selected_pooled, "terminal": terminal_pooled},
            "runtime": sprint_c_runtime.observe(),
            "torch_cuda_build": torch.version.cuda,
            "gpu_type": torch.cuda.get_device_name(local),
            "nccl_version": list(torch.cuda.nccl.version())
            if isinstance(torch.cuda.nccl.version(), tuple)
            else torch.cuda.nccl.version(),
            "bitwise_reproducibility_claimed": False,
            "optimization_runs_added": 0,
            "scientific_reporting_eligible": False,
        }
        c.validate_result(result, frozen, index)
        c.write(output / "result.json", result)
    # Non-master waits while rank0 performs post-training evaluation, no DDP forward.
    synchronize()
    if world == 4:
        dist.destroy_process_group()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    args = parser.parse_args()
    try:
        run(args.stage, args.index)
        return 0
    except Exception as error:
        # Detailed tracebacks stay in the private batch console, not public JSON.
        print(
            json.dumps(
                {
                    "state": "training_stopped",
                    "exception_type": type(error).__name__,
                    "raw_text_included": False,
                    "automatic_retry": False,
                }
            ),
            flush=True,
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
