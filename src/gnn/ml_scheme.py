import copy
import os
import time

import numpy as np
import torch
from matplotlib import pyplot as plt


def _device(model):
    """Return the device (cpu/cuda) where the model's parameters live."""
    return next(model.parameters()).device


# Bipartite CFL graph layout (HeteroData). All models share this forward
# signature and predict one logit per variable node; the target lives on the
# variable nodes. Centralised here so the training loop has a single, fixed
# way to call the model and read the labels.
_EDGE_TYPE = ("var", "to", "cons")


def _predict(model, batch):
    """Run the model on a batched bipartite graph and return its logits."""
    return model(
        x_var=batch["var"].x,
        x_cons=batch["cons"].x,
        edge_v2c=batch[_EDGE_TYPE].edge_index,
        binary_mask=batch["var"].binary_mask,
        edge_attr=batch[_EDGE_TYPE].edge_attr,
        var_batch=batch["var"].batch,
    )


def _target(batch):
    """Return the labels of the variable nodes the model predicts on.

    Indexed by `binary_mask` so it aligns with the model's output, which only
    covers the masked (binary/integer) variable nodes. Continuous variables
    stay in the graph as information for message passing but are not scored.
    """
    return batch["var"].y[batch["var"].binary_mask]


@torch.no_grad()
def test_torch(model, data_loader, loss_fn):
    """Evaluate the model with a torch loss, averaged per prediction.

    Returns the mean of `loss_fn` over all variable nodes in the loader.
    The per-batch loss is weighted by the number of predictions so the
    result is a true per-prediction mean even when graphs differ in size.
    """
    model.eval()
    device = _device(model)
    total_loss = 0.0
    total_count = 0

    for batch in data_loader:
        batch = batch.to(device)
        target = _target(batch)
        loss = loss_fn(_predict(model, batch), target).item()
        # Weight by number of predictions, not number of graphs, so the
        # reported loss is a true per-prediction mean when instances differ
        # in size (e.g. CFL easy vs hard).
        n = target.numel()
        total_loss += loss * n
        total_count += n

    return total_loss / total_count


@torch.no_grad()
def test_sklearn(model, data_loader, loss_fn):
    """Evaluate the model with an sklearn-style metric.

    Gathers all predictions and targets across the loader into two numpy
    arrays and calls `loss_fn(y_true, y_pred)` once (e.g. accuracy, F1).
    """
    model.eval()
    device = _device(model)
    y_true, y_pred = [], []

    for batch in data_loader:
        batch = batch.to(device)
        y_true.append(_target(batch).detach().cpu().numpy())
        y_pred.append(_predict(model, batch).detach().cpu().numpy())

    return loss_fn(np.concatenate(y_true), np.concatenate(y_pred))


def train_epoch(model, train_data_loader, optimizer, loss_fn):
    """Run one training pass over the loader and return the mean train loss.

    The loss is back-propagated per batch; the returned value is averaged
    per prediction (same weighting as `test_torch`).
    """
    total_loss = 0.0
    total_count = 0
    model.train()
    device = _device(model)

    for batch in train_data_loader:
        batch = batch.to(device)
        target = _target(batch)
        optimizer.zero_grad()
        loss = loss_fn(_predict(model, batch), target)
        loss.backward()
        optimizer.step()
        # Weight by number of predictions (see test_torch) for a per-prediction
        # mean across variable-sized instances.
        n = target.numel()
        total_loss += loss.item() * n
        total_count += n

    return total_loss / total_count


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
    """Train a copy of the model with early stopping on validation loss.

    Trains for up to `epochs`, keeping the model with the lowest validation
    loss seen so far, and stops early after `early_stopping_steps` epochs
    without improvement. The original model is left untouched (it is deep-
    copied first). Optionally saves the loss curve to `results_file` and the
    best weights to `model_file`.

    Parameters
    ----------
    original_model       : model to train (copied, not modified in place).
    train/val_data_loader: PyG loaders over the bipartite graphs.
    optimizer_cls        : optimizer class (e.g. torch.optim.Adam).
    loss_fn              : torch loss minimised during training.
    lr                   : learning rate passed to the optimizer.
    epochs               : maximum number of epochs.
    early_stopping_steps : epochs without val improvement before stopping.
    results_file         : if set, path to save the train/val loss plot.
    model_file           : if set, path to save the best model's state_dict.

    Returns the best model (lowest validation loss).
    """
    model = copy.deepcopy(original_model)
    optimizer = optimizer_cls(model.parameters(), lr=lr)

    best_model = None
    best_valid_loss = float("inf")
    no_improvement = 0
    train_losses, valid_losses = [], []

    print(f"Trainable parameters: {sum(p.numel() for p in model.parameters())}")

    initial_time = time.time()

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
                f"Epoch: {epoch:02d}, "
                f"Train: {train_loss:.4f}, "
                f"Valid: {valid_loss:.4f}"
            )

    print("Training time: ", time.time() - initial_time)

    if results_file is not None:
        os.makedirs(os.path.dirname(results_file), exist_ok=True)
        save_training_results(train_losses, valid_losses, results_file)

    if model_file is not None:
        os.makedirs(os.path.dirname(model_file), exist_ok=True)
        torch.save(best_model.state_dict(), model_file)
        print(f"Training ended for model {model_file}")

    return best_model


def save_training_results(train_losses, valid_losses, save_file):
    """Plot the train and validation loss curves and save them to `save_file`."""
    plt.clf()
    plt.plot(train_losses, label="Train")
    plt.plot(valid_losses, label="Validation")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.savefig(save_file)
