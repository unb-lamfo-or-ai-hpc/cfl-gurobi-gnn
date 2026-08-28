"""
Toy example: synthetic bipartite MILP graphs → GasseGNN / LiangBiGNN.

Run from the repo root:
    conda run -n cfl-gnn python sandbox/toy_bipartite.py
"""

import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"),
)

import torch
from sklearn.metrics import accuracy_score
from torch_geometric.data import HeteroData
from torch_geometric.loader import DataLoader

from cfl_gnn.models import GasseGNN, LiangBiGNN
from cfl_gnn.training.toy_scheme import train_model, test_sklearn, test_torch

# ── Config ────────────────────────────────────────────────────────────────────

EDGE_TYPE = ("var", "to", "cons")

VAR_DIM = 4  # variable node features (fixed dim, homogeneous across graphs)
CONS_DIM = 3  # constraint node features (fixed dim, homogeneous across graphs)
EDGE_DIM = 2  # edge features (e.g. constraint coefficient, normalised)
HIDDEN = 64
LAYERS = 2

# Per-graph size ranges. Each synthetic instance draws its own counts, so the
# dataset mixes problem sizes the way real MILP instances do. Only the *counts*
# vary - the feature dims above stay fixed (the GNNs are size-agnostic).
N_VAR_RANGE = (8, 16)  # variables per graph (inclusive)
N_CONS_RANGE = (5, 10)  # constraints per graph (inclusive)
BINARY_FRAC = 0.6  # fraction of variables that are binary (predicted on)
EDGE_FACTOR = 3  # edges ≈ EDGE_FACTOR * n_var

N_TRAIN, N_VAL, N_TEST = 80, 20, 20
BATCH_SIZE = 16
EPOCHS = 500
PATIENCE = 50
LR = 1e-3

# If True, up-weight the positive class in the loss using the train balance
# (pos_weight = n_negatives / n_positives). Useful when few variables activate;
# on this balanced toy it is ≈ 1 and changes nothing.
USE_POS_WEIGHT = False

# Where train_model saves the loss curve (.png) and the best weights (.pt),
# one file per model. The directory is created automatically.
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "toy_outputs")

# ── Synthetic data ─────────────────────────────────────────────────────────────


def make_graph(seed=None):
    """Single synthetic bipartite graph with a toy binary classification target.

    Sizes (n_var, n_cons, n_binary, n_edges) are sampled per graph from the
    *_RANGE config so the dataset mixes problem sizes; passing a seed makes the
    sampled sizes (and everything else) reproducible for that graph.
    """
    if seed is not None:
        torch.manual_seed(seed)

    n_var = int(torch.randint(N_VAR_RANGE[0], N_VAR_RANGE[1] + 1, (1,)))
    n_cons = int(torch.randint(N_CONS_RANGE[0], N_CONS_RANGE[1] + 1, (1,)))
    n_binary = max(1, round(BINARY_FRAC * n_var))
    n_edges = EDGE_FACTOR * n_var

    data = HeteroData()

    data["var"].x = torch.randn(n_var, VAR_DIM)
    data["cons"].x = torch.randn(n_cons, CONS_DIM)

    # Case A: the graph holds all variables, but only the first n_binary are
    # binary (the ones we predict on). The rest are "continuous": they stay in
    # the graph to inform message passing but are masked out of the output.
    data["var"].binary_mask = torch.zeros(n_var, dtype=torch.bool)
    data["var"].binary_mask[:n_binary] = True

    # Edges: random variable -> constraint connections with 2-dim features
    src = torch.randint(0, n_var, (n_edges,))
    dst = torch.randint(0, n_cons, (n_edges,))
    data[EDGE_TYPE].edge_index = torch.stack([src, dst])
    data[EDGE_TYPE].edge_attr = torch.randn(n_edges, EDGE_DIM)

    # Target: one label per variable node - "should this variable activate?"
    # Toy rule: a variable activates iff its first feature is positive. Labels
    # exist for all variables; _target masks them to the binary ones at train
    # time. Float (not bool/long) because that is what BCEWithLogitsLoss expects.
    data["var"].y = (data["var"].x[:, 0] > 0).float()

    return data


# ── Metric ──────────────────────────────────────────────────────────────────────


def accuracy(y_true, y_logits):
    """Fraction of variable nodes whose predicted activation matches the target.

    The model emits logits, so logit > 0 <-> sigmoid(logit) > 0.5 <-> "activate".
    """
    return accuracy_score(y_true, (y_logits > 0).astype(float))


# ── Training helper ────────────────────────────────────────────────────────────


def compute_pos_weight(dataset, device):
    """pos_weight = n_negatives / n_positives over the predicted (binary) nodes."""
    all_y = torch.cat([g["var"].y[g["var"].binary_mask] for g in dataset])
    n_pos = all_y.sum()
    n_neg = all_y.numel() - n_pos
    return (n_neg / n_pos).to(device)


def run(model, label, loaders, pos_weight, device):
    train_loader, val_loader, test_loader = loaders

    model = model.to(device)
    model.reset_parameters()

    # Fit prenorm statistics from one representative batch
    if hasattr(model, "fit_prenorm"):
        sample = next(iter(train_loader)).to(device)
        model.fit_prenorm(
            x_var=sample["var"].x,
            x_cons=sample["cons"].x,
            edge_v2c=sample[EDGE_TYPE].edge_index,
            edge_attr=sample[EDGE_TYPE].edge_attr,
        )

    # Binary classification per variable node: model outputs logits,
    # BCEWithLogitsLoss applies the sigmoid internally (numerically stable).
    # pos_weight (when enabled) up-weights the positive class; None disables it.
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    # File-safe name from the label (e.g. "LiangBiGNN (no attention)" -> ...).
    slug = "".join(c if c.isalnum() else "_" for c in label).strip("_")
    best = train_model(
        original_model=model,
        train_data_loader=train_loader,
        val_data_loader=val_loader,
        optimizer_cls=torch.optim.Adam,
        loss_fn=loss_fn,
        lr=LR,
        epochs=EPOCHS,
        early_stopping_steps=PATIENCE,
        results_file=os.path.join(OUT_DIR, f"{slug}_loss.png"),
        model_file=os.path.join(OUT_DIR, f"{slug}.pt"),
    )

    test_loss = test_torch(best, test_loader, loss_fn)
    test_acc = test_sklearn(best, test_loader, accuracy)
    print(f"{label} -> test BCE: {test_loss:.4f}  |  test accuracy: {test_acc:.3f}\n")


# ── Entry point ──────────────────────────────────────────────────────────────────


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    dataset = [make_graph(seed=i) for i in range(N_TRAIN + N_VAL + N_TEST)]
    train_ds = dataset[:N_TRAIN]
    val_ds = dataset[N_TRAIN : N_TRAIN + N_VAL]
    test_ds = dataset[N_TRAIN + N_VAL :]

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE)
    loaders = (train_loader, val_loader, test_loader)

    pos_weight = compute_pos_weight(train_ds, device) if USE_POS_WEIGHT else None
    if pos_weight is not None:
        print(f"pos_weight (train balance): {pos_weight.item():.3f}")

    print("\n=== GasseGNN ===")
    run(
        GasseGNN(
            VAR_DIM, CONS_DIM, edge_dim=EDGE_DIM, hidden_dim=HIDDEN, num_layers=LAYERS
        ),
        "GasseGNN",
        loaders,
        pos_weight,
        device,
    )

    exit()

    print("=== LiangBiGNN (no attention) ===")
    run(
        LiangBiGNN(
            VAR_DIM, CONS_DIM, edge_dim=EDGE_DIM, hidden_dim=HIDDEN, num_layers=LAYERS
        ),
        "LiangBiGNN",
        loaders,
        pos_weight,
        device,
    )

    print("=== LiangBiGNN+ATT ===")
    run(
        LiangBiGNN(
            VAR_DIM,
            CONS_DIM,
            edge_dim=EDGE_DIM,
            hidden_dim=HIDDEN,
            num_layers=LAYERS,
            use_attention=True,
        ),
        "LiangBiGNN+ATT",
        loaders,
        pos_weight,
        device,
    )


if __name__ == "__main__":
    main()
