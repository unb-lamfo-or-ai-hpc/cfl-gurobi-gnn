"""
Neural Diving — Parallel Training Script (DDP Multi-GPU) v5
===========================================================
Multi-graph paradigm: each incumbent solution is an independent training graph.

V5 Updates:
  - Global F1, Precision, Recall mapped safely via DDP all_reduce.
  - Dynamic directories via --experiment_name to avoid overwriting.
  - Training loop fully self-contained.
"""

import os
import argparse
import logging
import random
import json

import numpy as np
import torch
import torch.nn as nn
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import random_split, ConcatDataset
from torch.utils.data.distributed import DistributedSampler
from torch_geometric.loader import DataLoader
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cfl_gnn.graph.dataset import NeuralDivingDataset
from cfl_gnn.models.gasse import GasseGNN
from cfl_gnn.training.binary_contract import binary_targets
from cfl_gnn.paths import PROJECT_ROOT

project_root = str(PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s — %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

def set_global_seed(seed: int = 42):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

set_global_seed(42)

def compute_pos_weight(loader: DataLoader, device: torch.device, is_master: bool) -> torch.Tensor:
    total_pos = torch.tensor([0.0], device=device)
    total_neg = torch.tensor([0.0], device=device)
    for batch in loader:
        batch  = batch.to(device)
        mask   = batch['variable'].is_discrete.bool()
        mask, labels = binary_targets(batch)
        total_pos += (labels > 0.5).sum().float()
        total_neg += (labels <= 0.5).sum().float()

    dist.all_reduce(total_pos, op=dist.ReduceOp.SUM)
    dist.all_reduce(total_neg, op=dist.ReduceOp.SUM)

    n_pos, n_neg = total_pos.item(), total_neg.item()
    if n_pos == 0:
        if is_master: logger.warning("No positive labels — defaulting pos_weight=1.0")
        return torch.tensor([1.0], device=device)

    w = n_neg / n_pos
    if is_master: logger.info(f"Computed pos_weight = {w:.2f} (N_neg={n_neg:,}, N_pos={n_pos:,})")
    return torch.tensor([w], device=device)

def calc_metrics(tp, tn, fp, fn):
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    return acc, prec, rec, f1

def train_loop(model, loader, optimizer, loss_fn, device, args):
    model.train()
    local_loss, local_valid_batches = 0.0, 0.0

    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        target_mask = batch['variable'].is_discrete.bool()
        if target_mask.sum() == 0: continue
        local_valid_batches += 1

        preds = model(
            x_var=batch['variable'].x, x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=target_mask, edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        target_mask, targets = binary_targets(batch)
        
        loss = loss_fn(preds, targets)
        loss.backward()
        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)
        optimizer.step()

        local_loss += loss.item()
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()

    metrics = torch.tensor([local_loss, local_valid_batches], device=device)
    dist.all_reduce(metrics, op=dist.ReduceOp.SUM)
    gbatches = metrics[1].item()
    return metrics[0].item() / gbatches if gbatches > 0 else float('inf')

@torch.no_grad()
def eval_loop(model, loader, loss_fn, device, args):
    model.eval()
    local_loss, local_valid_batches = 0.0, 0.0
    local_tp, local_tn, local_fp, local_fn = 0.0, 0.0, 0.0, 0.0

    for batch in loader:
        batch = batch.to(device)
        target_mask = batch['variable'].is_discrete.bool()
        if target_mask.sum() == 0: continue
        local_valid_batches += 1

        preds = model(
            x_var=batch['variable'].x, x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=target_mask, edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        target_mask, targets = binary_targets(batch)
        loss = loss_fn(preds, targets)
        preds_bin = (preds > 0).float()

        local_tp += ((preds_bin == 1) & (targets == 1)).sum().item()
        local_tn += ((preds_bin == 0) & (targets == 0)).sum().item()
        local_fp += ((preds_bin == 1) & (targets == 0)).sum().item()
        local_fn += ((preds_bin == 0) & (targets == 1)).sum().item()
        local_loss += loss.item()

        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()

    metrics = torch.tensor([local_loss, local_tp, local_tn, local_fp, local_fn, local_valid_batches], device=device)
    dist.all_reduce(metrics, op=dist.ReduceOp.SUM)
    gbatches = metrics[5].item()
    
    if gbatches == 0: return float('inf'), 0, 0, 0, 0
    return (metrics[0].item() / gbatches, metrics[1].item(), metrics[2].item(), metrics[3].item(), metrics[4].item())

def assemble_datasets(config, base_root, generator, is_master):
    train_ds, val_ds, test_ds = [], [], []
    for cat, (n_train, n_val, n_test) in config.items():
        total_req = n_train + n_val + n_test
        if total_req == 0: continue
        
        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)
        
        if len(ds) < total_req:
            if is_master: logger.error(f"Category '{cat}' has {len(ds)} graphs but {total_req} requested.")
            sys.exit(1)
            
        unused = len(ds) - total_req
        d_tr, d_va, d_te, _ = random_split(ds, [n_train, n_val, n_test, unused], generator=generator)
        
        if n_train > 0: train_ds.append(d_tr)
        if n_val > 0: val_ds.append(d_va)
        if n_test > 0: test_ds.append(d_te)
    return train_ds, val_ds, test_ds

def main():
    dist.init_process_group(backend="nccl")
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    torch.cuda.set_device(local_rank)
    device, is_master = torch.device(f"cuda:{local_rank}"), (local_rank == 0)

    parser = argparse.ArgumentParser(description="Neural Diving — Parallel DDP Training")
    parser.add_argument('--experiment_name', type=str, default="run_01_ddp", help="Output directory name.")
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

    output_dir = os.path.join(project_root, "data", "models", args.experiment_name)
    if is_master:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"=== Parallel DDP Training | Output: {output_dir} ===")
    dist.barrier()

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    config = {'CFL_easy_instance': args.easy_split, 'CFL_medium_instance': args.medium_split, 'CFL_hard_instance': args.hard_split}
    generator = torch.Generator().manual_seed(42)
    
    train_ds_list, val_ds_list, test_ds_list = assemble_datasets(config, base_root, generator, is_master)
    train_data = ConcatDataset(train_ds_list) if train_ds_list else None
    val_data = ConcatDataset(val_ds_list) if val_ds_list else None

    if train_data is None:
        if is_master: logger.error("Training set is empty.")
        sys.exit(1)

    train_sampler = DistributedSampler(train_data, shuffle=True)
    train_loader = DataLoader(train_data, batch_size=1, sampler=train_sampler)
    val_sampler = DistributedSampler(val_data, shuffle=False) if val_data else None
    val_loader = DataLoader(val_data, batch_size=1, sampler=val_sampler) if val_data else None

    model = GasseGNN(var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2).to(device)
    
    if is_master: logger.info("Fitting prenorm layers...")
    for sample in train_loader:
        sample = sample.to(device)
        if sample['variable'].is_discrete.bool().sum() > 0:
            model.fit_prenorm(
                x_var=sample['variable'].x, x_cons=sample['constraint'].x,
                edge_v2c=sample['variable', 'rev_coef', 'constraint'].edge_index,
                edge_attr=sample['variable', 'rev_coef', 'constraint'].edge_attr
            )
            break

    # =======================================================
    # WARM-START DDP (Reinitiate from checkpoint before DDP)
    # =======================================================
    model_checkpoint = os.path.join(output_dir, "best_model.pt")
    if os.path.exists(model_checkpoint):
        if is_master: logger.info(f"Checkpoint encontrado en {model_checkpoint}. Cargando pesos...")
        # Nota: Los modelos DDP guardados usan el prefijo 'module.'. Al cargarlos 
        # en el modelo base antes de DDP, limpiamos las llaves por seguridad:
        state_dict = torch.load(model_checkpoint, map_location=device, weights_only=True)
        clean_state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}
        model.load_state_dict(clean_state_dict)
    else:
        if is_master: logger.info("No se encontró checkpoint previo. Iniciando desde cero.")
    # ====================================================================

    model = DDP(model, device_ids=[local_rank])
    dist.barrier()

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    pos_weight = compute_pos_weight(train_loader, device, is_master)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    best_val_loss = float('inf')
    best_epoch_info = {}
    patience_counter = 0

    if is_master:
        hist_train_loss, hist_val_loss = [], []
        hist_acc, hist_f1, hist_prec, hist_rec = [], [], [], []
        
        # Preparar el log CSV
        log_path = os.path.join(output_dir, "training_log_parallel.csv")
        log_file = open(log_path, 'w')
        log_file.write("epoch,train_loss,val_loss,acc,f1,prec,rec\n")
        
        header = f"{'Ep':<4} | {'T.Loss':<8} | {'V.Loss':<8} | {'Acc%':<7} | {'F1':<6} | {'Prec':<6} | {'Rec':<6}"
        logger.info("-" * len(header))
        logger.info(header)
        logger.info("-" * len(header))

    for epoch in range(args.epochs):
        train_sampler.set_epoch(epoch)
        train_loss = train_loop(model, train_loader, optimizer, loss_fn, device, args)
        
        val_loss, tp, tn, fp, fn = float('inf'), 0, 0, 0, 0
        if val_loader:
            val_loss, tp, tn, fp, fn = eval_loop(model, val_loader, loss_fn, device, args)

        should_stop = torch.tensor([0], device=device)

        if is_master:
            acc, prec, rec, f1 = calc_metrics(tp, tn, fp, fn)
            
            # Guardar históricos
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
                torch.save(model.module.state_dict(), os.path.join(output_dir, "best_model.pt"))
                marker = " -> Best"
                
                # Actualizar información de la mejor época para el JSON
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
                logger.info(f"[Early Stopping] Triggered at epoch {epoch+1}.")
                should_stop = torch.tensor([1], device=device)

        dist.broadcast(should_stop, src=0)
        if should_stop.item() == 1: break

    if is_master:
        log_file.close()
        
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
            import json
            json.dump(summary, f, indent=4)
        
        logger.info(f"Dashboard y JSON de resumen guardados en: {output_dir}")
        logger.info("Parallel training complete.")

    dist.barrier()
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
