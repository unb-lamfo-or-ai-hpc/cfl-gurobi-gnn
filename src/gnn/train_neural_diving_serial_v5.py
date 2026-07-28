"""
Neural Diving — Serial Training Script (Single-GPU) v5
======================================================
Multi-graph paradigm: each incumbent solution is an independent training graph.

V5 Updates:
  - F1, Precision, Recall and Accuracy tracked comprehensively.
  - Output directories managed dynamically via --experiment_name.
  - Training loop fully self-contained (no external ml_scheme dependency).
"""

import sys
import os
import argparse
import logging
import random
import json

import numpy as np
import torch
import torch.nn as nn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from torch.utils.data import random_split, ConcatDataset
from torch_geometric.loader import DataLoader

# Project-root detection
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN
from src.graph_transform.milp_dataset_v2 import NeuralDivingDataset

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s — %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

def set_global_seed(seed: int = 42) -> None:
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

set_global_seed(42)

def compute_pos_weight(loader: DataLoader, device: torch.device) -> torch.Tensor:
    total_pos, total_neg = 0, 0
    for batch in loader:
        mask    = batch['variable'].is_discrete.bool()
        labels  = batch['variable'].y[mask]
        total_pos += (labels > 0.5).sum().item()
        total_neg += (labels <= 0.5).sum().item()

    if total_pos == 0:
        logger.warning("No positive labels found — defaulting pos_weight=1.0")
        return torch.tensor([1.0], device=device)

    w = total_neg / total_pos
    logger.info(f"Computed pos_weight = {w:.2f} (N_neg={total_neg:,}, N_pos={total_pos:,})")
    return torch.tensor([w], device=device)

def calc_metrics(tp, tn, fp, fn):
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    return acc, prec, rec, f1

def train_loop(model, loader, optimizer, loss_fn, device, args):
    model.train()
    total_loss, valid_batches = 0.0, 0

    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        target_mask = batch['variable'].is_discrete.bool()
        if target_mask.sum() == 0:
            continue
        valid_batches += 1

        preds = model(
            x_var=batch['variable'].x, x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=target_mask, edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)
        
        loss = loss_fn(preds, targets)
        loss.backward()
        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)
        optimizer.step()

        total_loss += loss.item()
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()

    return total_loss / valid_batches if valid_batches > 0 else float('inf')

@torch.no_grad()
def eval_loop(model, loader, loss_fn, device, args):
    model.eval()
    total_loss, valid_batches = 0.0, 0
    tp, tn, fp, fn = 0, 0, 0, 0

    for batch in loader:
        batch = batch.to(device)
        target_mask = batch['variable'].is_discrete.bool()
        if target_mask.sum() == 0:
            continue
        valid_batches += 1

        preds = model(
            x_var=batch['variable'].x, x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=target_mask, edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)
        
        loss = loss_fn(preds, targets)
        preds_bin = (preds > 0).float()
        
        tp += ((preds_bin == 1) & (targets == 1)).sum().item()
        tn += ((preds_bin == 0) & (targets == 0)).sum().item()
        fp += ((preds_bin == 1) & (targets == 0)).sum().item()
        fn += ((preds_bin == 0) & (targets == 1)).sum().item()
        total_loss += loss.item()

        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()

    avg_loss = total_loss / valid_batches if valid_batches > 0 else float('inf')
    return avg_loss, tp, tn, fp, fn

def assemble_datasets(config, base_root, generator):
    train_ds, val_ds, test_ds = [], [], []
    for cat, (n_train, n_val, n_test) in config.items():
        total_req = n_train + n_val + n_test
        if total_req == 0: continue
        
        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)
        
        if len(ds) < total_req:
            logger.error(f"Category '{cat}' has {len(ds)} graphs but {total_req} requested.")
            sys.exit(1)
            
        unused = len(ds) - total_req
        d_tr, d_va, d_te, _ = random_split(ds, [n_train, n_val, n_test, unused], generator=generator)
        
        if n_train > 0: train_ds.append(d_tr)
        if n_val > 0: val_ds.append(d_va)
        if n_test > 0: test_ds.append(d_te)
    return train_ds, val_ds, test_ds

def main():
    parser = argparse.ArgumentParser(description="Neural Diving — Serial Training")
    parser.add_argument('--experiment_name', type=str, default="run_01", help="Name for output directory.")
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--grad_clip', type=float, default=1.0)
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--patience', type=int, default=10)
    parser.add_argument('--clear_cache', action='store_true')
    parser.add_argument('--easy_split', type=int, nargs=3, default=[0, 0, 0])
    parser.add_argument('--medium_split', type=int, nargs=3, default=[0, 0, 0])
    parser.add_argument('--hard_split', type=int, nargs=3, default=[0, 0, 0])
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = os.path.join(project_root, "data", "models", args.experiment_name)
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"=== Serial Training | Output: {output_dir} ===")

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    config = {'CFL_easy_instance': args.easy_split, 'CFL_medium_instance': args.medium_split, 'CFL_hard_instance': args.hard_split}
    generator = torch.Generator().manual_seed(42)
    
    train_ds, val_ds, test_ds = assemble_datasets(config, base_root, generator)
    train_data = ConcatDataset(train_ds) if train_ds else None
    val_data = ConcatDataset(val_ds) if val_ds else None
    
    if not train_data:
        logger.error("Training set is empty.")
        sys.exit(1)

    train_loader = DataLoader(train_data, batch_size=1, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=1, shuffle=False) if val_data else None

    model = GasseGNN(var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2).to(device)
    
    # Fit prenorm
    for sample in train_loader:
        sample = sample.to(device)
        if sample['variable'].is_discrete.bool().sum() > 0:
            model.fit_prenorm(
                x_var=sample['variable'].x, x_cons=sample['constraint'].x,
                edge_v2c=sample['variable', 'rev_coef', 'constraint'].edge_index,
                edge_attr=sample['variable', 'rev_coef', 'constraint'].edge_attr
            )
            break

    # ==========================================
    # WARM-START (Reinitiate from checkpoint)
    # ==========================================
    model_checkpoint = os.path.join(output_dir, "best_model.pt")
    if os.path.exists(model_checkpoint):
        logger.info(f"Checkpoint encontrado en {model_checkpoint}. Cargando pesos para reanudar...")
        model.load_state_dict(torch.load(model_checkpoint, map_location=device, weights_only=True))
    else:
        logger.info("No se encontró checkpoint previo. Iniciando entrenamiento desde cero.")
    # ==========================================

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    pos_weight = compute_pos_weight(train_loader, device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    best_val_loss = float('inf')
    best_epoch_info = {}
    patience_counter = 0
    
    hist_train_loss, hist_val_loss = [], []
    hist_acc, hist_f1, hist_prec, hist_rec = [], [], [], []
    
    log_path = os.path.join(output_dir, "training_log_serial.csv")
    
    header = f"{'Ep':<4} | {'T.Loss':<8} | {'V.Loss':<8} | {'Acc%':<7} | {'F1':<6} | {'Prec':<6} | {'Rec':<6}"
    logger.info("-" * len(header))
    logger.info(header)
    logger.info("-" * len(header))

    with open(log_path, 'w') as log_file:
        log_file.write("epoch,train_loss,val_loss,acc,f1,prec,rec\n")

        for epoch in range(args.epochs):
            train_loss = train_loop(model, train_loader, optimizer, loss_fn, device, args)
            val_loss, tp, tn, fp, fn = float('inf'), 0, 0, 0, 0
            
            if val_loader:
                val_loss, tp, tn, fp, fn = eval_loop(model, val_loader, loss_fn, device, args)
            
            acc, prec, rec, f1 = calc_metrics(tp, tn, fp, fn)
            
            # Almacenar métricas
            hist_train_loss.append(train_loss)
            hist_val_loss.append(val_loss if val_loader else train_loss)
            hist_acc.append(acc)
            hist_f1.append(f1)
            hist_prec.append(prec)
            hist_rec.append(rec)

            marker = ""
            if val_loader and val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                torch.save(model.state_dict(), os.path.join(output_dir, "best_model.pt"))
                marker = " -> Best"
                
                best_epoch_info = {
                    "best_epoch": epoch + 1,
                    "val_loss": val_loss,
                    "accuracy": acc,
                    "f1_score": f1,
                    "precision": prec,
                    "recall": rec
                }
            elif val_loader:
                patience_counter += 1

            logger.info(f"{epoch+1:<4} | {train_loss:<8.4f} | {val_loss:<8.4f} | {acc*100:<7.2f} | {f1:<6.4f} | {prec:<6.4f} | {rec:<6.4f}{marker}")
            log_file.write(f"{epoch+1},{train_loss},{val_loss},{acc},{f1},{prec},{rec}\n")
            log_file.flush()

            # --- GENERACIÓN DEL DASHBOARD VISUAL (2x2) ---
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            epochs_range = range(1, len(hist_train_loss) + 1)
            
            # Subplot 1: Loss
            axes[0, 0].plot(epochs_range, hist_train_loss, color='tab:red', label='Train Loss', lw=2)
            if val_loader: 
                axes[0, 0].plot(epochs_range, hist_val_loss, color='tab:orange', linestyle='dashed', label='Val Loss', lw=2)
            axes[0, 0].set_title('BCE Loss', weight='bold')
            axes[0, 0].legend()
            axes[0, 0].grid(alpha=0.3)

            # Subplot 2: F1-Score
            if val_loader:
                axes[0, 1].plot(epochs_range, hist_f1, color='tab:purple', label='Val F1', lw=2)
            axes[0, 1].set_title('F1-Score Evolution', weight='bold')
            axes[0, 1].legend()
            axes[0, 1].grid(alpha=0.3)

            # Subplot 3: Precision vs Recall
            if val_loader:
                axes[1, 0].plot(epochs_range, hist_prec, color='tab:blue', label='Val Precision', lw=2)
                axes[1, 0].plot(epochs_range, hist_rec, color='tab:green', label='Val Recall', lw=2)
            axes[1, 0].set_title('Precision vs Recall', weight='bold')
            axes[1, 0].legend()
            axes[1, 0].grid(alpha=0.3)

            # Subplot 4: Accuracy
            if val_loader:
                axes[1, 1].plot(epochs_range, hist_acc, color='tab:cyan', label='Val Accuracy', lw=2)
            axes[1, 1].set_title('Accuracy', weight='bold')
            axes[1, 1].legend()
            axes[1, 1].grid(alpha=0.3)

            fig.tight_layout()
            plt.savefig(os.path.join(output_dir, "training_dashboard.png"), dpi=150)
            plt.close(fig)
            # ---------------------------------------------

            if val_loader and patience_counter >= args.patience:
                logger.info(f"[Early Stopping] Triggered at epoch {epoch+1}")
                break

    # --- GENERACIÓN DEL JSON DE RESUMEN ---
    summary = {
        "experiment_name": args.experiment_name,
        "hyperparameters": {
            "hidden_dim": args.hidden_dim,
            "learning_rate": args.lr,
            "pos_weight": pos_weight.item()
        },
        "best_epoch_results": best_epoch_info
    }
    with open(os.path.join(output_dir, "experiment_summary.json"), 'w') as f:
        json.dump(summary, f, indent=4)
        
    logger.info(f"Dashboard y JSON de resumen guardados en: {output_dir}")
    logger.info("Serial training complete.")

if __name__ == "__main__":
    main()