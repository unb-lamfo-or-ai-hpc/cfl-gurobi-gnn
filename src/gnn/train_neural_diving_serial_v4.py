"""
Neural Diving — Serial Training Script (Single-GPU)
====================================================
Multi-graph paradigm: each incumbent solution is an independent training graph.

Key improvements over v3:
  - loss_fn instantiated once outside all loops (not per batch)
  - pos_weight computed from training data statistics (R5)
  - is_discrete read from pre-stored ETL attribute (no column-index recomputation)
  - lp_values dead assignment removed
  - F1-score computed and logged alongside Accuracy
  - epochs and patience exposed as CLI arguments
  - --clear_cache flag added for low-VRAM environments
  - val_acc / val_loss guarded against UnboundLocalError when val_data is None
  - Matplotlib figure created once, updated in place per epoch
  - All user-facing strings in English
  - Robust project-root detection (no hardcoded directory depth)
"""

import sys
import os
import argparse
import logging
import random

import numpy as np
import torch
import torch.nn as nn
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend — safe for DGX / headless servers
import matplotlib.pyplot as plt
from torch.utils.data import random_split, ConcatDataset
from torch_geometric.loader import DataLoader

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
def set_global_seed(seed: int = 42) -> None:
    """Fix all stochastic seeds for full reproducibility."""
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


set_global_seed(42)


# ---------------------------------------------------------------------------
# Project-root detection (robust, no hardcoded directory depth)
# ---------------------------------------------------------------------------
#def find_project_root(start: str) -> str:
#    """Walk up from *start* until a project marker file is found."""
#    current = os.path.abspath(start)
#    for _ in range(10):
#        markers = ('pyproject.toml', 'setup.py', 'setup.cfg', '.git')
#        if any(os.path.exists(os.path.join(current, m)) for m in markers):
#            return current
#        parent = os.path.dirname(current)
#        if parent == current:
#            break
#        current = parent
#    raise RuntimeError(f"Could not locate project root from: {start}")

#project_root = find_project_root(os.path.dirname(os.path.abspath(__file__)))
#sys.path.insert(0, project_root)

# Alternate path reolution for src.graph_transform.milp_dataset
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN          # noqa: E402
from src.graph_transform.milp_dataset_v2 import NeuralDivingDataset  # noqa: E402


# ---------------------------------------------------------------------------
# pos_weight calibration  (Recommendation R5)
# ---------------------------------------------------------------------------
def compute_pos_weight(loader: DataLoader, device: torch.device) -> torch.Tensor:
    """
    Compute class-frequency-based pos_weight for BCEWithLogitsLoss.

    Formula:
        w_pos = N_neg / N_pos

    Only discrete variables (stored in graph['variable'].is_discrete) are
    counted, matching the exact subset used during training.
    """
    total_pos, total_neg = 0, 0
    for batch in loader:
        mask    = batch['variable'].is_discrete.bool()
        labels  = batch['variable'].y[mask]
        total_pos += (labels > 0.5).sum().item()
        total_neg += (labels <= 0.5).sum().item()

    if total_pos == 0:
        logger.warning("No positive labels found in training set — defaulting pos_weight=1.0")
        return torch.tensor([1.0], device=device)

    w = total_neg / total_pos
    logger.info(f"Computed pos_weight = {w:.2f}  "
                f"(N_neg={total_neg:,}  N_pos={total_pos:,})")
    return torch.tensor([w], device=device)


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------
def train_loop(
    model:     nn.Module,
    loader:    DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_fn:   nn.Module,
    device:    torch.device,
    args:      argparse.Namespace,
) -> tuple[float, float]:
    """
    One full training epoch.

    Returns
    -------
    (avg_loss, avg_accuracy) over all valid batches.
    """
    model.train()
    total_loss, total_acc, valid_batches = 0.0, 0.0, 0

    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()

        # Use the pre-stored discrete mask from build_pyg_dataset_v4 (ETL stage).
        # This avoids column-index recomputation and prevents silent index drift.
        target_mask = batch['variable'].is_discrete.bool()
        if target_mask.sum() == 0:
            continue
        valid_batches += 1

        preds = model(
            x_var    = batch['variable'].x,
            x_cons   = batch['constraint'].x,
            edge_v2c = batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask = target_mask,
            edge_attr   = batch['variable', 'rev_coef', 'constraint'].edge_attr,
        )

        # Clamp targets to [0, 1] — handles any residual float precision noise
        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)

        loss = loss_fn(preds, targets)
        loss.backward()

        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)

        optimizer.step()

        with torch.no_grad():
            acc = ((preds > 0).float() == targets).float().mean()
            total_loss += loss.item()
            total_acc  += acc.item()

        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()

    if valid_batches == 0:
        return float('inf'), 0.0
    return total_loss / valid_batches, total_acc / valid_batches


# ---------------------------------------------------------------------------
# Evaluation loop
# ---------------------------------------------------------------------------
@torch.no_grad()
def eval_loop(
    model:   nn.Module,
    loader:  DataLoader,
    loss_fn: nn.Module,
    device:  torch.device,
    args:    argparse.Namespace,
) -> tuple[float, float, int, int, int, int, int, float]:
    """
    One full evaluation pass.

    Returns
    -------
    (avg_loss, avg_accuracy, TP, TN, FP, FN, avg_vars_per_graph, avg_mip_gap)
    """
    model.eval()
    total_loss, total_acc = 0.0, 0.0
    valid_batches = 0
    tp, tn, fp, fn = 0, 0, 0, 0
    total_vars  = 0
    avg_mip_gap = 0.0

    for batch in loader:
        batch = batch.to(device)

        target_mask = batch['variable'].is_discrete.bool()
        if target_mask.sum() == 0:
            continue
        valid_batches += 1
        total_vars += target_mask.sum().item()

        # Read the pre-stored MIP gap if available
        if hasattr(batch, 'mip_gap'):
            avg_mip_gap += float(batch.mip_gap.mean().item())

        preds = model(
            x_var    = batch['variable'].x,
            x_cons   = batch['constraint'].x,
            edge_v2c = batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask = target_mask,
            edge_attr   = batch['variable', 'rev_coef', 'constraint'].edge_attr,
        )

        targets  = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)
        loss     = loss_fn(preds, targets)
        preds_bin = (preds > 0).float()
        acc      = (preds_bin == targets).float().mean()

        tp += ((preds_bin == 1) & (targets == 1)).sum().item()
        tn += ((preds_bin == 0) & (targets == 0)).sum().item()
        fp += ((preds_bin == 1) & (targets == 0)).sum().item()
        fn += ((preds_bin == 0) & (targets == 1)).sum().item()

        total_loss += loss.item()
        total_acc  += acc.item()

        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()

    if valid_batches == 0:
        return float('inf'), 0.0, 0, 0, 0, 0, 0, 0.0

    return (
        total_loss / valid_batches,
        total_acc  / valid_batches,
        tp, tn, fp, fn,
        total_vars // valid_batches,
        avg_mip_gap / valid_batches,
    )


# ---------------------------------------------------------------------------
# F1-score helper
# ---------------------------------------------------------------------------
def f1_score(tp: int, fp: int, fn: int) -> float:
    """Binary F1-score from confusion matrix counts."""
    denom = 2 * tp + fp + fn
    return (2 * tp / denom) if denom > 0 else 0.0


# ---------------------------------------------------------------------------
# Dataset assembly helper
# ---------------------------------------------------------------------------
def assemble_datasets(
    config:   dict,
    base_root: str,
    generator: torch.Generator,
) -> tuple:
    """
    Split each difficulty category into train / val / test subsets.

    Returns
    -------
    (train_datasets, val_datasets, test_datasets)  — lists of Subset objects
    """
    train_datasets, val_datasets, test_datasets = [], [], []

    for cat, (n_train, n_val, n_test) in config.items():
        total_req = n_train + n_val + n_test
        if total_req == 0:
            continue

        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)

        if len(ds) < total_req:
            logger.error(
                f"Category '{cat}' has {len(ds)} graphs but {total_req} were requested."
            )
            sys.exit(1)

        unused = len(ds) - total_req
        ds_train, ds_val, ds_test, _ = random_split(
            ds, [n_train, n_val, n_test, unused], generator=generator
        )

        if n_train > 0:
            train_datasets.append(ds_train)
        if n_val > 0:
            val_datasets.append(ds_val)
        if n_test > 0:
            test_datasets.append(ds_test)

    return train_datasets, val_datasets, test_datasets


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Neural Diving — Serial Single-GPU Training"
    )
    parser.add_argument('--hidden_dim',  type=int,   default=32)
    parser.add_argument('--lr',          type=float, default=1e-3)
    parser.add_argument('--grad_clip',   type=float, default=1.0)
    parser.add_argument('--epochs',      type=int,   default=100,
                        help="Maximum number of training epochs.")
    parser.add_argument('--patience',    type=int,   default=10,
                        help="Early stopping patience (epochs without val improvement).")
    parser.add_argument('--clear_cache', action='store_true',
                        help="Call torch.cuda.empty_cache() after each batch.")

    # Dataset split arguments — values are (n_train, n_val, n_test) graph counts
    parser.add_argument('--easy_split',   type=int, nargs=3, default=[0, 0, 0],
                        metavar=('TRAIN', 'VAL', 'TEST'))
    parser.add_argument('--medium_split', type=int, nargs=3, default=[0, 0, 0],
                        metavar=('TRAIN', 'VAL', 'TEST'))
    parser.add_argument('--hard_split',   type=int, nargs=3, default=[0, 0, 0],
                        metavar=('TRAIN', 'VAL', 'TEST'))
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"=== Neural Diving Serial Training  |  device={device} ===")
    logger.info(f"hidden_dim={args.hidden_dim}  lr={args.lr}  "
                f"grad_clip={args.grad_clip}  epochs={args.epochs}  "
                f"patience={args.patience}")
    logger.info(f"Easy   (train/val/test): {args.easy_split}")
    logger.info(f"Medium (train/val/test): {args.medium_split}")
    logger.info(f"Hard   (train/val/test): {args.hard_split}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    os.makedirs(output_dir, exist_ok=True)

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"

    config = {
        'CFL_easy_instance':   args.easy_split,
        'CFL_medium_instance': args.medium_split,
        'CFL_hard_instance':   args.hard_split,
    }

    generator = torch.Generator().manual_seed(42)
    train_ds_list, val_ds_list, test_ds_list = assemble_datasets(
        config, base_root, generator
    )

    train_data = ConcatDataset(train_ds_list) if train_ds_list else None
    val_data   = ConcatDataset(val_ds_list)   if val_ds_list   else None
    test_data  = ConcatDataset(test_ds_list)  if test_ds_list  else None

    if train_data is None:
        logger.error("Training set is empty. Adjust split arguments.")
        sys.exit(1)

    train_loader = DataLoader(train_data, batch_size=1, shuffle=True)
    val_loader   = DataLoader(val_data,   batch_size=1, shuffle=False) if val_data   else None
    test_loader  = DataLoader(test_data,  batch_size=1, shuffle=False) if test_data  else None

    # -----------------------------------------------------------------------
    # Model initialisation
    # -----------------------------------------------------------------------
    model = GasseGNN(
        var_in_dim=7, cons_in_dim=5, edge_dim=1,
        hidden_dim=args.hidden_dim, num_layers=2,
    ).to(device)

    logger.info("Fitting prenorm layers on first valid training sample...")
    for sample in train_loader:
        sample = sample.to(device)
        if sample['variable'].is_discrete.bool().sum() > 0:
            model.fit_prenorm(
                x_var    = sample['variable'].x,
                x_cons   = sample['constraint'].x,
                edge_v2c = sample['variable', 'rev_coef', 'constraint'].edge_index,
                edge_attr = sample['variable', 'rev_coef', 'constraint'].edge_attr,
            )
            break

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    # -----------------------------------------------------------------------
    # Loss function — pos_weight calibrated from training data (R5)
    # -----------------------------------------------------------------------
    logger.info("Computing pos_weight from training set statistics...")
    pos_weight = compute_pos_weight(train_loader, device)
    loss_fn    = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    # -----------------------------------------------------------------------
    # Training loop
    # -----------------------------------------------------------------------
    best_val_loss    = float('inf')
    patience_counter = 0

    hist_train_loss: list[float] = []
    hist_val_loss:   list[float] = []

    # Create the matplotlib figure once and reuse it across epochs
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlabel('Epoch')
    ax.set_ylabel('BCE Loss')
    ax.set_title('Learning Curve — Neural Diving (Serial)')

    header = (f"{'Epoch':<6} | {'T.Loss':<8} | {'V.Loss':<8} | "
              f"{'Acc%':<7} | {'F1':<6} | "
              f"{'TP':<5} {'TN':<5} {'FP':<4} {'FN':<4} | "
              f"{'Vars/G':<7} | {'Gap%':<7}")
    logger.info("-" * len(header))
    logger.info(header)
    logger.info("-" * len(header))

    log_path = os.path.join(output_dir, "training_log_serial.csv")
    with open(log_path, 'w') as log_file:
        log_file.write("epoch,train_loss,val_loss,val_accuracy,val_f1\n")

        for epoch in range(args.epochs):
            train_loss, _ = train_loop(model, train_loader, optimizer,
                                       loss_fn, device, args)

            # Default values used when val_data is absent
            val_loss = float('inf')
            val_acc  = 0.0
            val_f1   = 0.0
            tp = tn = fp = fn = avg_vars = 0
            avg_gap = 0.0

            if val_loader is not None:
                (val_loss, val_acc,
                 tp, tn, fp, fn,
                 avg_vars, avg_gap) = eval_loop(model, val_loader,
                                                loss_fn, device, args)
                val_f1 = f1_score(tp, fp, fn)

            hist_train_loss.append(train_loss)
            hist_val_loss.append(val_loss if val_loader is not None else train_loss)

            # Best model checkpoint
            marker = ""
            if val_loader is not None and val_loss < best_val_loss:
                best_val_loss    = val_loss
                patience_counter = 0
                torch.save(
                    model.state_dict(),
                    os.path.join(output_dir, "neural_diving_best_serial.pt"),
                )
                marker = " --> Best!"
            elif val_loader is not None:
                patience_counter += 1

            log_str = (f"Ep {epoch+1:<3} | {train_loss:<8.4f} | {val_loss:<8.4f} | "
                       f"{val_acc*100:<7.2f} | {val_f1:<6.4f} | "
                       f"{tp:<5} {tn:<5} {fp:<4} {fn:<4} | "
                       f"{avg_vars:<7} | {avg_gap*100:<6.2f}%{marker}")
            logger.info(log_str)
            log_file.write(
                f"{epoch+1},{train_loss},{val_loss},{val_acc*100:.4f},{val_f1:.4f}\n"
            )
            log_file.flush()

            # Update the pre-created figure in place (avoids per-epoch allocation)
            ax.clear()
            ax.set_xlabel('Epoch')
            ax.set_ylabel('BCE Loss')
            ax.set_title('Learning Curve — Neural Diving (Serial)')
            epochs_range = range(1, len(hist_train_loss) + 1)
            ax.plot(epochs_range, hist_train_loss,
                    color='tab:red', label='Train Loss')
            if val_loader is not None:
                ax.plot(epochs_range, hist_val_loss,
                        color='tab:orange', linestyle='dashed',
                        label='Validation Loss')
            ax.legend()
            fig.tight_layout()
            plt.savefig(os.path.join(output_dir, "loss_curve_serial.png"), dpi=120)

            # Early stopping check
            if val_loader is not None and patience_counter >= args.patience:
                logger.info(
                    f"[Early Stopping] No improvement in {args.patience} epochs. "
                    f"Stopping training."
                )
                break

    plt.close(fig)

    # Save final model
    torch.save(
        model.state_dict(),
        os.path.join(output_dir, "neural_diving_final_serial.pt"),
    )
    logger.info(f"Final model saved to: {output_dir}")

    # -----------------------------------------------------------------------
    # Final test evaluation
    # -----------------------------------------------------------------------
    if test_loader is not None:
        best_path = os.path.join(output_dir, "neural_diving_best_serial.pt")
        if os.path.exists(best_path):
            model.load_state_dict(
                torch.load(best_path, map_location=device, weights_only=True)
            )
            logger.info("Loaded best checkpoint for test evaluation.")

        (test_loss, test_acc,
         tp, tn, fp, fn,
         avg_vars, avg_gap) = eval_loop(model, test_loader, loss_fn, device, args)
        test_f1 = f1_score(tp, fp, fn)

        logger.info("=== Final Test Set Evaluation ===")
        logger.info(f"  Test Loss : {test_loss:.4f}")
        logger.info(f"  Test Acc  : {test_acc * 100:.2f}%")
        logger.info(f"  Test F1   : {test_f1:.4f}")
        logger.info(f"  TP={tp}  TN={tn}  FP={fp}  FN={fn}")

    logger.info("Serial training complete.")


if __name__ == "__main__":
    main()
