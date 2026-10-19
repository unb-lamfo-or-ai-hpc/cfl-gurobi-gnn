"""PR87 matched learning primitives; no torch import or execution at import time."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from cfl_gnn.training.mvp_arm import build_parent_balanced_epoch_indices


def digest_json(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def epoch_batches(parents, seed, epoch):
    """Identical ordered global batches; no rank padding or sample omission."""
    if len(parents) != 34 or len(set(parents)) != 34:
        raise ValueError("exactly_34_unique_training_parents_required")
    if seed != 42 or type(epoch) is not int or not 0 <= epoch < 100:
        raise ValueError("seed_or_epoch_outside_frozen_protocol")
    records = [{"parent_instance_id": p} for p in parents]
    schedule = build_parent_balanced_epoch_indices(
        records, seed=seed, epoch=epoch, draws_per_parent=4
    )
    if Counter(schedule) != Counter({i: 4 for i in range(34)}):
        raise ValueError("parent_mass_changed")
    return tuple(
        tuple(parents[i] for i in schedule[n : n + 4]) for n in range(0, 136, 4)
    )


def schedule_hash(parents, seed):
    return digest_json([epoch_batches(parents, seed, e) for e in range(100)])


def state_hash(model):
    """Tensor contents/shapes/types, not nondeterministic torch.save ZIP metadata."""
    result = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        tensor = value.detach().cpu().contiguous()
        result.update(
            json.dumps([name, str(tensor.dtype), list(tensor.shape)]).encode()
        )
        result.update(tensor.numpy().tobytes())
    return result.hexdigest()


def serial_step(model, items, optimizer, loss_for_item, clip=1.0):
    """Four independent forwards/backwards; one clip and Adam update."""
    import torch

    if len(items) != 4:
        raise ValueError("global_batch_four_required")
    optimizer.zero_grad(set_to_none=True)
    losses = []
    for item in items:
        loss = loss_for_item(model, item)
        if not bool(torch.isfinite(loss)):
            raise ValueError("nonfinite_loss")
        (loss / 4).backward()
        losses.append(float(loss.detach()))
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
    if not bool(torch.isfinite(norm)):
        raise ValueError("nonfinite_gradient")
    optimizer.step()
    return sum(losses) / 4


def ddp_step(model, item, optimizer, loss_for_item, clip=1.0):
    """DDP averages four per-graph gradients; do NOT divide this loss by four."""
    import torch
    import torch.distributed as dist

    if dist.get_world_size() != 4:
        raise ValueError("four_ranks_required")
    optimizer.zero_grad(set_to_none=True)
    loss = loss_for_item(model, item)
    if not bool(torch.isfinite(loss)):
        raise ValueError("nonfinite_loss")
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
    if not bool(torch.isfinite(norm)):
        raise ValueError("nonfinite_gradient")
    optimizer.step()
    return float(loss.detach())
