"""
ml_scheme_v2.py
===============
Reusable training utilities for the Neural Diving GNN pipeline.

This module provides framework-agnostic helper functions that wrap the GNN
forward pass, loss evaluation, and training loop.  All functions are
intentionally kept free of dataset-specific logic so they can be reused
across serial and distributed training scripts.

Edge-type and attribute names are aligned with the HeteroData schema produced
by build_pyg_dataset_v4.py:
  - variable nodes  : 'variable'
  - constraint nodes: 'constraint'
  - v→c edges       : ('variable', 'rev_coef', 'constraint')

The  is_discrete  mask is read from the pre-stored graph attribute
(set at ETL time by build_pyg_dataset_v4.py) rather than being recomputed
from raw feature columns on every batch.
"""

import copy
import logging
import os
import time
from typing import Callable, Optional

import numpy as np
import torch
from matplotlib import pyplot as plt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HeteroData schema constants  (single source of truth for the whole pipeline)
# ---------------------------------------------------------------------------

# Variable nodes
_VAR_NODE       = "variable"
# Constraint nodes
_CONS_NODE      = "constraint"
# Directed edge: variable → constraint (used for message passing)
_EDGE_V2C       = (_VAR_NODE, "rev_coef", _CONS_NODE)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _device(model: torch.nn.Module) -> torch.device:
    """Return the device where the model's first parameter lives."""
    return next(model.parameters()).device


def _get_discrete_mask(batch) -> torch.BoolTensor:
    """
    Return the boolean mask selecting binary and integer variable nodes.

    Priority order:
      1. Pre-stored  batch['variable'].is_discrete  (ETL v4 — preferred).
      2. Column-index fallback for graphs built with ETL v3 (columns 4 and 5).

    The fallback emits a one-time warning so the developer knows to rebuild
    the dataset with build_pyg_dataset_v4.py.
    """
    if hasattr(batch[_VAR_NODE], "is_discrete"):
        return batch[_VAR_NODE].is_discrete.bool()

    logger.warning(
        "is_discrete attribute not found on graph — using column-index fallback "
        "(col 4 = is_binary, col 5 = is_integer). Rebuild dataset with "
        "build_pyg_dataset_v4.py to eliminate this overhead and risk."
    )
    x        = batch[_VAR_NODE].x
    is_bin   = x[:, 4] == 1.0   # column 4: is_binary
    is_int   = x[:, 5] == 1.0   # column 5: is_integer
    return is_bin | is_int


def _predict(model: torch.nn.Module, batch) -> torch.Tensor:
    """
    Run a forward pass and return one logit per discrete variable node.

    The discrete mask is obtained from  _get_discrete_mask  so the call-site
    does not need to know the feature-column layout.

    Parameters
    ----------
    model : GasseGNN (or any model sharing this forward signature).
    batch : PyG HeteroData batch produced by NeuralDivingDataset.

    Returns
    -------
    logits : Tensor of shape (M,), where M = number of discrete variables
             in the batch.
    """
    discrete_mask = _get_discrete_mask(batch)
    return model(
        x_var       = batch[_VAR_NODE].x,
        x_cons      = batch[_CONS_NODE].x,
        edge_v2c    = batch[_EDGE_V2C].edge_index,
        binary_mask = discrete_mask,
        edge_attr   = batch[_EDGE_V2C].edge_attr,
    )


def _target(batch) -> torch.Tensor:
    """
    Return the ground-truth labels for the discrete variable nodes.

    The label vector  batch['variable'].y  covers all variable nodes; we index
    it with the discrete mask to align with the model's output (which only
    scores discrete variables).

    Continuous variables remain in the graph as context for message passing
    but do not contribute to the loss or metrics.
    """
    discrete_mask = _get_discrete_mask(batch)
    return batch[_VAR_NODE].y[discrete_mask]


# ---------------------------------------------------------------------------
# Evaluation — torch loss
# ---------------------------------------------------------------------------

@torch.no_grad()
def test_torch(
    model:       torch.nn.Module,
    data_loader,
    loss_fn:     Callable,
) -> float:
    """
    Evaluate the model using a torch loss function.

    Returns the per-prediction mean loss over all variable nodes in the loader.
    Each batch is weighted by the number of discrete variables it contains so
    the result is a true per-prediction mean even when instances differ in size
    (e.g. CFL easy vs. hard).

    Parameters
    ----------
    model       : trained GNN.
    data_loader : PyG DataLoader.
    loss_fn     : torch loss (e.g. BCEWithLogitsLoss with reduction='sum').

    Returns
    -------
    float : per-prediction mean loss.
    """
    model.eval()
    device      = _device(model)
    total_loss  = 0.0
    total_count = 0

    for batch in data_loader:
        batch  = batch.to(device)
        target = _target(batch)
        n      = target.numel()
        if n == 0:
            continue
        loss        = loss_fn(_predict(model, batch), target).item()
        total_loss  += loss * n   # accumulate sum; divide once at the end
        total_count += n

    if total_count == 0:
        return 0.0
    return total_loss / total_count


# ---------------------------------------------------------------------------
# Evaluation — sklearn metric
# ---------------------------------------------------------------------------

@torch.no_grad()
def test_sklearn(
    model:       torch.nn.Module,
    data_loader,
    metric_fn:   Callable,
) -> float:
    """
    Evaluate the model with an sklearn-style metric (accuracy, F1, etc.).

    Gathers all predictions and targets across the entire loader into two numpy
    arrays and calls  metric_fn(y_true, y_pred)  once.

    Parameters
    ----------
    model       : trained GNN.
    data_loader : PyG DataLoader.
    metric_fn   : callable with signature  f(y_true, y_pred) -> float.

    Returns
    -------
    float : the metric value.
    """
    model.eval()
    device = _device(model)
    y_true, y_pred = [], []

    for batch in data_loader:
        batch = batch.to(device)
        y_true.append(_target(batch).detach().cpu().numpy())
        y_pred.append(_predict(model, batch).detach().cpu().numpy())

    if not y_true:
        return 0.0
    return metric_fn(np.concatenate(y_true), np.concatenate(y_pred))


# ---------------------------------------------------------------------------
# Training — one epoch
# ---------------------------------------------------------------------------

def train_epoch(
    model:             torch.nn.Module,
    train_data_loader,
    optimizer:         torch.optim.Optimizer,
    loss_fn:           Callable,
) -> float:
    """
    Run one full training pass over the loader.

    Returns the per-prediction mean training loss (same weighting convention
    as  test_torch  so train and validation losses are directly comparable).

    Parameters
    ----------
    model             : GNN to train (must be in  .train()  mode on entry).
    train_data_loader : PyG DataLoader.
    optimizer         : torch optimizer (e.g. Adam).
    loss_fn           : torch loss with reduction='sum' recommended for
                        correct per-prediction weighting.

    Returns
    -------
    float : per-prediction mean loss for this epoch.
    """
    model.train()
    device      = _device(model)
    total_loss  = 0.0
    total_count = 0

    for batch in train_data_loader:
        batch  = batch.to(device)
        target = _target(batch)
        n      = target.numel()
        if n == 0:
            continue

        optimizer.zero_grad()
        loss = loss_fn(_predict(model, batch), target)
        loss.backward()
        optimizer.step()

        total_loss  += loss.item() * n
        total_count += n

    if total_count == 0:
        return 0.0
    return total_loss / total_count


# ---------------------------------------------------------------------------
# Training loop with early stopping
# ---------------------------------------------------------------------------

def train_model(
    original_model:       torch.nn.Module,
    train_data_loader,
    val_data_loader,
    optimizer_cls,
    loss_fn:              Callable,
    lr:                   float,
    epochs:               int,
    early_stopping_steps: int,
    results_file:         Optional[str] = None,
    model_file:           Optional[str] = None,
    log_every:            int           = 10,
) -> torch.nn.Module:
    """
    Train a deep copy of  original_model  with early stopping on validation loss.

    The original model is **not** modified.  Training terminates when the
    validation loss has not improved for  early_stopping_steps  consecutive
    epochs.  The model with the lowest validation loss is returned.

    Optionally saves:
      - the train/val loss curve to  results_file  (PNG).
      - the best model state_dict to  model_file   (.pt).

    Parameters
    ----------
    original_model       : GNN to train.  A deep copy is made immediately.
    train_data_loader    : PyG DataLoader for the training split.
    val_data_loader      : PyG DataLoader for the validation split.
    optimizer_cls        : optimizer class (e.g. torch.optim.Adam).
    loss_fn              : torch loss passed to  train_epoch  and  test_torch.
                           Must use reduction='sum' for correct weighting.
    lr                   : learning rate.
    epochs               : maximum number of training epochs.
    early_stopping_steps : epochs without validation improvement before stop.
    results_file         : optional path to save the loss-curve PNG.
    model_file           : optional path to save the best model state_dict.
    log_every            : print training progress every N epochs.

    Returns
    -------
    torch.nn.Module : the best model (lowest validation loss).
    """
    model     = copy.deepcopy(original_model)
    optimizer = optimizer_cls(model.parameters(), lr=lr)

    best_model      = None
    best_valid_loss = float("inf")
    no_improvement  = 0
    train_losses:   list = []
    valid_losses:   list = []

    n_params = sum(p.numel() for p in model.parameters())
    logger.info("Trainable parameters: %d", n_params)

    t0 = time.time()

    for epoch in range(epochs):
        train_loss = train_epoch(model, train_data_loader, optimizer, loss_fn)
        valid_loss = test_torch(model, val_data_loader, loss_fn)

        train_losses.append(train_loss)
        valid_losses.append(valid_loss)

        if valid_loss < best_valid_loss:
            best_valid_loss = valid_loss
            best_model      = copy.deepcopy(model)
            no_improvement  = 0
        else:
            no_improvement += 1
            if no_improvement >= early_stopping_steps:
                logger.info("Early stopping triggered at epoch %d.", epoch)
                break

        if epoch % log_every == 0:
            logger.info(
                "Epoch %04d  |  train = %.6f  |  val = %.6f",
                epoch, train_loss, valid_loss,
            )

    elapsed = time.time() - t0
    logger.info("Training finished in %.1f s  (best val loss = %.6f).",
                elapsed, best_valid_loss)

    if results_file is not None:
        parent = os.path.dirname(results_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        _save_loss_curve(train_losses, valid_losses, results_file)

    if model_file is not None and best_model is not None:
        parent = os.path.dirname(model_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        torch.save(best_model.state_dict(), model_file)
        logger.info("Best model saved to: %s", model_file)

    return best_model


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _save_loss_curve(
    train_losses: list,
    valid_losses: list,
    save_file:    str,
) -> None:
    """
    Plot train and validation loss curves and save them to  save_file.

    Produces a publication-ready figure (300 dpi, tight layout, labelled axes)
    suitable for direct inclusion in a thesis document.
    """
    fig, ax = plt.subplots(figsize=(9, 5))
    epochs  = range(1, len(train_losses) + 1)

    ax.plot(epochs, train_losses, label="Train loss",      lw=2, color="steelblue")
    ax.plot(epochs, valid_losses, label="Validation loss", lw=2, color="darkorange")

    best_epoch = int(np.argmin(valid_losses)) + 1
    best_loss  = min(valid_losses)
    ax.axvline(best_epoch, color="green", linestyle="--", lw=1.5,
               label=f"Best model (epoch {best_epoch}, val = {best_loss:.4f})")

    ax.set_xlabel("Epoch",         fontsize=13)
    ax.set_ylabel("Loss",          fontsize=13)
    ax.set_title("Training Curve — Neural Diving GNN", fontsize=15)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_file, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Loss curve saved to: %s", save_file)
