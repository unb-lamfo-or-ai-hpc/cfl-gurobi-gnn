"""Training helpers for the synthetic bipartite GNN smoke test.

The production training pipelines use their own dataset schema.  The sandbox
toy intentionally keeps the original ``var -> cons`` schema that was used to
exercise :class:`GasseGNN` before real CFL artifacts were available.
"""

import copy
import os
import time

import numpy as np
import torch
from matplotlib import pyplot as plt


EDGE_TYPE = ("var", "to", "cons")


def _device(model):
    """Return the device where the model parameters live."""
    return next(model.parameters()).device


def _predict(model, batch):
    """Run the model on a batched toy graph and return its logits."""
    return model(
        x_var=batch["var"].x,
        x_cons=batch["cons"].x,
        edge_v2c=batch[EDGE_TYPE].edge_index,
        binary_mask=batch["var"].binary_mask,
        edge_attr=batch[EDGE_TYPE].edge_attr,
        var_batch=batch["var"].batch,
    )


def _target(batch):
    """Return labels only for the variables selected by the binary mask."""
    return batch["var"].y[batch["var"].binary_mask]


@torch.no_grad()
def test_torch(model, data_loader, loss_fn):
    """Evaluate a torch loss, weighted by the number of predictions."""
    model.eval()
    device = _device(model)
    total_loss = 0.0
    total_count = 0

    for batch in data_loader:
        batch = batch.to(device)
        target = _target(batch)
        count = target.numel()
        if count == 0:
            continue
        total_loss += loss_fn(_predict(model, batch), target).item() * count
        total_count += count

    return total_loss / total_count if total_count else 0.0


@torch.no_grad()
def test_sklearn(model, data_loader, metric_fn):
    """Evaluate an sklearn-style metric over all toy predictions."""
    model.eval()
    device = _device(model)
    y_true = []
    y_pred = []

    for batch in data_loader:
        batch = batch.to(device)
        y_true.append(_target(batch).detach().cpu().numpy())
        y_pred.append(_predict(model, batch).detach().cpu().numpy())

    if not y_true:
        return 0.0
    return metric_fn(np.concatenate(y_true), np.concatenate(y_pred))


def train_epoch(model, train_data_loader, optimizer, loss_fn):
    """Run one training epoch and return mean loss per prediction."""
    model.train()
    device = _device(model)
    total_loss = 0.0
    total_count = 0

    for batch in train_data_loader:
        batch = batch.to(device)
        target = _target(batch)
        count = target.numel()
        if count == 0:
            continue

        optimizer.zero_grad()
        loss = loss_fn(_predict(model, batch), target)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * count
        total_count += count

    return total_loss / total_count if total_count else 0.0


def train_model(
    original_model,
    train_data_loader,
    val_data_loader,
    optimizer_cls,
    loss_fn,
    lr,
    epochs,
    early_stopping_steps,
    results_file=None,
    model_file=None,
):
    """Train a copy of the toy model with validation-loss early stopping."""
    model = copy.deepcopy(original_model)
    optimizer = optimizer_cls(model.parameters(), lr=lr)
    best_model = None
    best_valid_loss = float("inf")
    no_improvement = 0
    train_losses = []
    valid_losses = []

    print(f"Trainable parameters: {sum(p.numel() for p in model.parameters())}")
    started_at = time.time()

    for epoch in range(epochs):
        train_loss = train_epoch(model, train_data_loader, optimizer, loss_fn)
        valid_loss = test_torch(model, val_data_loader, loss_fn)
        train_losses.append(train_loss)
        valid_losses.append(valid_loss)

        if valid_loss < best_valid_loss:
            best_valid_loss = valid_loss
            best_model = copy.deepcopy(model)
            no_improvement = 0
        else:
            no_improvement += 1
            if no_improvement >= early_stopping_steps:
                print(f"Early stopping! (epoch: {epoch})")
                break

        if epoch % 100 == 0:
            print(
                f"Epoch: {epoch:02d}, Train: {train_loss:.4f}, "
                f"Valid: {valid_loss:.4f}"
            )

    print("Training time: ", time.time() - started_at)

    if results_file is not None:
        os.makedirs(os.path.dirname(results_file), exist_ok=True)
        _save_training_results(train_losses, valid_losses, results_file)

    if model_file is not None and best_model is not None:
        os.makedirs(os.path.dirname(model_file), exist_ok=True)
        torch.save(best_model.state_dict(), model_file)
        print(f"Training ended for model {model_file}")

    return best_model


def _save_training_results(train_losses, valid_losses, save_file):
    """Save the training and validation loss curves."""
    plt.clf()
    plt.plot(train_losses, label="Train")
    plt.plot(valid_losses, label="Validation")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.savefig(save_file)
