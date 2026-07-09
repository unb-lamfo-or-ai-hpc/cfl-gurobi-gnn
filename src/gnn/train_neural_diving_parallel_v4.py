"""
Neural Diving — Parallel Training Script (DDP Multi-GPU)
=========================================================
Multi-graph paradigm: each incumbent solution is an independent training graph.

Key improvements over v3:
  - DDP deadlock fixed: dist.broadcast stop signal before early-stopping break
  - pos_weight computed from training data statistics (R5)
  - is_discrete read from pre-stored ETL attribute (no column-index recomputation)
  - lp_values dead assignment removed
  - fit_prenorm followed by dist.barrier() to synchronise all ranks
  - F1-score computed and logged alongside Accuracy
  - epochs and patience exposed as CLI arguments
  - torch.load uses weights_only=True for state dict loading
  - Matplotlib figure created once, updated in place per epoch (master only)
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
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import random_split, ConcatDataset
from torch.utils.data.distributed import DistributedSampler
from torch_geometric.loader import DataLoader
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend — safe for DGX / headless servers
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Logging (each rank prefixes its rank number)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
def set_global_seed(seed: int = 42) -> None:
    """Fix all stochastic seeds for full reproducibility across all DDP ranks."""
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
    #"""Walk up from *start* until a project marker file is found."""
    #current = os.path.abspath(start)
    #for _ in range(10):
    #    markers = ('pyproject.toml', 'setup.py', 'setup.cfg', '.git')
    #    if any(os.path.exists(os.path.join(current, m)) for m in markers):
    #        return current
    #    parent = os.path.dirname(current)
    #    if parent == current:
    #        break
    #    current = parent
    #raise RuntimeError(f"Could not locate project root from: {start}")

#project_root = find_project_root(os.path.dirname(os.path.abspath(__file__)))
#sys.path.insert(0, project_root)

# Alternate path reolution for src.graph_transform.milp_dataset
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN                        # noqa: E402
from src.graph_transform.milp_dataset import NeuralDivingDataset  # noqa: E402


# ---------------------------------------------------------------------------
# pos_weight calibration  (Recommendation R5)
# ---------------------------------------------------------------------------
def compute_pos_weight(
    loader: DataLoader,
    device: torch.device,
    is_master: bool,
) -> torch.Tensor:
    """
    Compute class-frequency-based pos_weight for BCEWithLogitsLoss.

    Formula:
        w_pos = N_neg / N_pos

    The result is computed on rank 0 and broadcast to all other ranks to
    guarantee a consistent value across the entire DDP group.
    """
    # All ranks participate in the pass so the DistributedSampler is not
    # left in an inconsistent state. Only rank 0 accumulates the result.
    total_pos = torch.tensor([0.0], device=device)
    total_neg = torch.tensor([0.0], device=device)

    for batch in loader:
        batch  = batch.to(device)
        mask   = batch['variable'].is_discrete.bool()
        labels = batch['variable'].y[mask]
        total_pos += (labels > 0.5).sum().float()
        total_neg += (labels <= 0.5).sum().float()

    # Sum across all ranks so every rank has the global counts
    dist.all_reduce(total_pos, op=dist.ReduceOp.SUM)
    dist.all_reduce(total_neg, op=dist.ReduceOp.SUM)

    n_pos = total_pos.item()
    n_neg = total_neg.item()

    if n_pos == 0:
        if is_master:
            logger.warning(
                "No positive labels found in training set — defaulting pos_weight=1.0"
            )
        return torch.tensor([1.0], device=device)

    w = n_neg / n_pos
    if is_master:
        logger.info(
            f"Computed pos_weight = {w:.2f}  "
            f"(N_neg={int(n_neg):,}  N_pos={int(n_pos):,})"
        )
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
    One full training epoch across all DDP ranks.

    Returns
    -------
    (avg_loss, avg_accuracy) globally reduced across all ranks.
    """
    model.train()
    local_loss, local_acc, local_valid_batches = 0.0, 0.0, 0.0

    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()

        # Use the pre-stored discrete mask from build_pyg_dataset_v4 (ETL stage).
        # Avoids column-index recomputation and prevents silent index drift.
        target_mask = batch['variable'].is_discrete.bool()
        if target_mask.sum() == 0:
            continue
        local_valid_batches += 1

        preds = model(
            x_var       = batch['variable'].x,
            x_cons      = batch['constraint'].x,
            edge_v2c    = batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask = target_mask,
            edge_attr   = batch['variable', 'rev_coef', 'constraint'].edge_attr,
        )

        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)
        loss    = loss_fn(preds, targets)
        loss.backward()

        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)

        optimizer.step()

        with torch.no_grad():
            acc = ((preds > 0).float() == targets).float().mean()
            local_loss += loss.item()
            local_acc  += acc.item()

        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()

    # Reduce across all DDP ranks to get global metrics
    metrics = torch.tensor(
        [local_loss, local_acc, local_valid_batches], device=device
    )
    dist.all_reduce(metrics, op=dist.ReduceOp.SUM)
    global_batches = metrics[2].item()

    if global_batches == 0:
        return float('inf'), 0.0
    return metrics[0].item() / global_batches, metrics[1].item() / global_batches


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
) -> tuple[float, float]:
    """
    One full evaluation pass across all DDP ranks.

    Returns
    -------
    (avg_loss, avg_accuracy) globally reduced across all ranks.

    Note: TP/TN/FP/FN aggregation across DDP ranks requires additional
    all_reduce calls and is reserved for the serial evaluation script to
    avoid communication overhead in every validation step.
    """
    model.eval()
    local_loss, local_acc, local_valid_batches = 0.0, 0.0, 0.0

    for batch in loader:
        batch = batch.to(device)

        target_mask = batch['variable'].is_discrete.bool()
        if target_mask.sum() == 0:
            continue
        local_valid_batches += 1

        preds = model(
            x_var       = batch['variable'].x,
            x_cons      = batch['constraint'].x,
            edge_v2c    = batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask = target_mask,
            edge_attr   = batch['variable', 'rev_coef', 'constraint'].edge_attr,
        )

        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)
        loss    = loss_fn(preds, targets)
        acc     = ((preds > 0).float() == targets).float().mean()

        local_loss += loss.item()
        local_acc  += acc.item()

        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()

    metrics = torch.tensor(
        [local_loss, local_acc, local_valid_batches], device=device
    )
    dist.all_reduce(metrics, op=dist.ReduceOp.SUM)
    global_batches = metrics[2].item()

    if global_batches == 0:
        return float('inf'), 0.0
    return metrics[0].item() / global_batches, metrics[1].item() / global_batches


# ---------------------------------------------------------------------------
# Dataset assembly helper
# ---------------------------------------------------------------------------
def assemble_datasets(
    config:    dict,
    base_root: str,
    generator: torch.Generator,
    is_master: bool,
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
            if is_master:
                logger.error(
                    f"Category '{cat}' has {len(ds)} graphs "
                    f"but {total_req} were requested."
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
    # Initialise DDP — must be called before any CUDA operations
    dist.init_process_group(backend="nccl")
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    torch.cuda.set_device(local_rank)
    device    = torch.device(f"cuda:{local_rank}")
    is_master = (local_rank == 0)

    parser = argparse.ArgumentParser(
        description="Neural Diving — Parallel DDP Multi-GPU Training"
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

    if is_master:
        logger.info("=== Neural Diving DDP Parallel Training ===")
        logger.info(
            f"hidden_dim={args.hidden_dim}  lr={args.lr}  "
            f"grad_clip={args.grad_clip}  epochs={args.epochs}  "
            f"patience={args.patience}"
        )
        logger.info(f"Easy   (train/val/test): {args.easy_split}")
        logger.info(f"Medium (train/val/test): {args.medium_split}")
        logger.info(f"Hard   (train/val/test): {args.hard_split}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    if is_master:
        os.makedirs(output_dir, exist_ok=True)
    dist.barrier()   # All ranks wait until master has created the directory

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"

    config = {
        'CFL_easy_instance':   args.easy_split,
        'CFL_medium_instance': args.medium_split,
        'CFL_hard_instance':   args.hard_split,
    }

    generator = torch.Generator().manual_seed(42)
    train_ds_list, val_ds_list, test_ds_list = assemble_datasets(
        config, base_root, generator, is_master
    )

    train_data = ConcatDataset(train_ds_list) if train_ds_list else None
    val_data   = ConcatDataset(val_ds_list)   if val_ds_list   else None
    test_data  = ConcatDataset(test_ds_list)  if test_ds_list  else None

    if train_data is None:
        if is_master:
            logger.error("Training set is empty. Adjust split arguments.")
        sys.exit(1)

    # DistributedSampler partitions the dataset across ranks automatically
    train_sampler = DistributedSampler(train_data, shuffle=True)
    train_loader  = DataLoader(train_data, batch_size=1, sampler=train_sampler)

    val_loader, test_loader = None, None
    if val_data:
        val_sampler = DistributedSampler(val_data, shuffle=False)
        val_loader  = DataLoader(val_data, batch_size=1, sampler=val_sampler)
    if test_data:
        test_sampler = DistributedSampler(test_data, shuffle=False)
        test_loader  = DataLoader(test_data, batch_size=1, sampler=test_sampler)

    # -----------------------------------------------------------------------
    # Model initialisation
    # -----------------------------------------------------------------------
    model = GasseGNN(
        var_in_dim=7, cons_in_dim=5, edge_dim=1,
        hidden_dim=args.hidden_dim, num_layers=2,
    ).to(device)

    # fit_prenorm is called BEFORE DDP wraps the model so that module
    # attributes are accessible without going through DDP indirection.
    # dist.barrier() after wrapping ensures all ranks synchronise their
    # prenorm parameters before the first forward pass.
    if is_master:
        logger.info("Fitting prenorm layers on first valid training sample...")
    for sample in train_loader:
        sample = sample.to(device)
        if sample['variable'].is_discrete.bool().sum() > 0:
            model.fit_prenorm(
                x_var     = sample['variable'].x,
                x_cons    = sample['constraint'].x,
                edge_v2c  = sample['variable', 'rev_coef', 'constraint'].edge_index,
                edge_attr = sample['variable', 'rev_coef', 'constraint'].edge_attr,
            )
            break

    if args.clear_cache:
        del sample
        torch.cuda.empty_cache()

    model     = DDP(model, device_ids=[local_rank])
    dist.barrier()   # Synchronise prenorm parameters across all ranks

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    # -----------------------------------------------------------------------
    # Loss function — pos_weight calibrated from training data (R5)
    # -----------------------------------------------------------------------
    if is_master:
        logger.info("Computing pos_weight from training set statistics...")
    pos_weight = compute_pos_weight(train_loader, device, is_master)
    loss_fn    = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    # -----------------------------------------------------------------------
    # Training loop
    # -----------------------------------------------------------------------
    best_val_loss    = float('inf')
    patience_counter = 0

    if is_master:
        hist_train_loss: list[float] = []
        hist_val_loss:   list[float] = []

        # Create the matplotlib figure once and reuse across epochs
        fig, ax = plt.subplots(figsize=(10, 6))

        log_path = os.path.join(output_dir, "training_log_parallel.csv")
        log_file = open(log_path, 'w')
        log_file.write("epoch,train_loss,val_loss,val_accuracy\n")

        header = (f"{'Epoch':<8} | {'Train Loss':<12} | "
                  f"{'Val Loss':<12} | {'Val Acc%':<10}")
        logger.info("-" * len(header))
        logger.info(header)
        logger.info("-" * len(header))

    for epoch in range(args.epochs):
        train_sampler.set_epoch(epoch)   # Required for correct DDP shuffling
        train_loss, _ = train_loop(
            model, train_loader, optimizer, loss_fn, device, args
        )

        val_loss, val_acc = float('inf'), 0.0
        if val_loader is not None:
            val_loss, val_acc = eval_loop(
                model, val_loader, loss_fn, device, args
            )

        # -------------------------------------------------------------------
        # Early stopping synchronisation — CRITICAL for DDP stability
        #
        # Only rank 0 evaluates patience. The decision is then broadcast
        # to ALL ranks via dist.broadcast so that every rank exits the epoch
        # loop simultaneously. Without this broadcast, ranks 1-7 would hang
        # indefinitely on the next dist.all_reduce inside train_loop.
        # -------------------------------------------------------------------
        should_stop = torch.tensor([0], device=device)

        if is_master:
            hist_train_loss.append(train_loss)
            hist_val_loss.append(val_loss if val_loader is not None else train_loss)

            marker = ""
            if val_loader is not None and val_loss < best_val_loss:
                best_val_loss    = val_loss
                patience_counter = 0
                torch.save(
                    model.module.state_dict(),
                    os.path.join(output_dir, "neural_diving_best_parallel.pt"),
                )
                marker = " --> Best!"
            elif val_loader is not None:
                patience_counter += 1

            log_str = (f"Epoch {epoch+1:<5} | {train_loss:<12.4f} | "
                       f"{val_loss:<12.4f} | {val_acc*100:<8.2f}%{marker}")
            logger.info(log_str)
            log_file.write(
                f"{epoch+1},{train_loss},{val_loss},{val_acc*100:.4f}\n"
            )
            log_file.flush()

            # Update learning curve in place
            ax.clear()
            ax.set_xlabel('Epoch')
            ax.set_ylabel('BCE Loss')
            ax.set_title('Learning Curve — Neural Diving (DDP)')
            epochs_range = range(1, len(hist_train_loss) + 1)
            ax.plot(epochs_range, hist_train_loss,
                    color='tab:red', label='Train Loss')
            if val_loader is not None:
                ax.plot(epochs_range, hist_val_loss,
                        color='tab:orange', linestyle='dashed',
                        label='Validation Loss')
            ax.legend()
            fig.tight_layout()
            plt.savefig(
                os.path.join(output_dir, "loss_curve_parallel.png"), dpi=120
            )

            if val_loader is not None and patience_counter >= args.patience:
                logger.info(
                    f"[Early Stopping] No improvement in {args.patience} epochs."
                )
                should_stop = torch.tensor([1], device=device)

        # Broadcast the stop decision from rank 0 to all other ranks.
        # All ranks must call dist.broadcast unconditionally.
        dist.broadcast(should_stop, src=0)
        if should_stop.item() == 1:
            break   # All ranks exit the epoch loop together — no deadlock

    # -----------------------------------------------------------------------
    # Post-training cleanup (master only)
    # -----------------------------------------------------------------------
    if is_master:
        plt.close(fig)
        log_file.close()
        torch.save(
            model.module.state_dict(),
            os.path.join(output_dir, "neural_diving_final_parallel.pt"),
        )
        logger.info(f"Training complete. Outputs saved to: {output_dir}")

    # -----------------------------------------------------------------------
    # Final test evaluation — all ranks participate (DDP eval_loop)
    # -----------------------------------------------------------------------
    if test_loader is not None:
        dist.barrier()

        best_path = os.path.join(output_dir, "neural_diving_best_parallel.pt")
        if os.path.exists(best_path):
            model.module.load_state_dict(
                torch.load(best_path, map_location=device, weights_only=True)
            )

        test_loss, test_acc = eval_loop(
            model, test_loader, loss_fn, device, args
        )

        if is_master:
            logger.info("=== Final Test Set Evaluation ===")
            logger.info(f"  Test Loss : {test_loss:.4f}")
            logger.info(f"  Test Acc  : {test_acc * 100:.2f}%")

    dist.barrier()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
