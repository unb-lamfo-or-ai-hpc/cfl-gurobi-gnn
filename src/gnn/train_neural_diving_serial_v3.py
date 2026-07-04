"""
Entrenamiento Serial (Single-GPU) - Paradigma Multi-Grafo (Incumbentes)
=======================================================================
1. Usa el LP vector puro (sin log-scale) directamente del disco.
2. Entrena sobre múltiples incumbentes por instancia.
3. Imprime el MIP Gap promedio evaluado para auditar la dificultad.
"""
import sys
import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import random_split, ConcatDataset
from torch_geometric.loader import DataLoader
import matplotlib.pyplot as plt

import random
import numpy as np

def set_global_seed(seed=42):
    """Fija todas las semillas estocásticas para garantizar reproducibilidad."""
    # 1. Semillas de Python estándar
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    
    # 2. Semillas de Numpy
    np.random.seed(seed)
    
    # 3. Semillas de PyTorch (CPU y GPU)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    
    # 4. Forzar determinismo en algoritmos de CuDNN (Opcional pero recomendado)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# --- LLAMADA AL INICIO DEL SCRIPT ---
set_global_seed(42)

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN
from src.graph_transform.milp_dataset import NeuralDivingDataset

def train_loop(model, loader, optimizer, device, args):
    model.train()
    total_loss, total_acc = 0.0, 0.0
    valid_batches = 0
    
    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        
        # 1. Identificamos variables discretas
        is_bin = batch['variable'].x[:, 4] == 1.0
        is_int = batch['variable'].x[:, 5] == 1.0
        is_discrete = is_bin | is_int
        
        # 2. Extraemos el LP (Columna 6).
        lp_real = batch['variable'].x[:, 6]
        target_mask = is_discrete
        
        if target_mask.sum() == 0: 
            continue
            
        valid_batches += 1

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=target_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
            
        # Target (Y) es la solución de la incumbente específica
        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)
        
        # PESOS DINÁMICOS: Penalizar duramente si falla en adivinar un "1"
        num_zeros = (targets == 0).sum().item()
        num_ones = (targets == 1).sum().item()
        peso_clase_1 = num_zeros / max(1.0, float(num_ones))
        pos_weight = torch.tensor([peso_clase_1], device=device)
        
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        loss = loss_fn(preds, targets)
        loss.backward()
        
        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)
        
        optimizer.step()
        
        with torch.no_grad():
            acc = ((preds > 0).float() == targets).float().mean()
            total_loss += loss.item()
            total_acc += acc.item()
            
    if valid_batches == 0: return float('inf'), 0.0
    return total_loss / valid_batches, total_acc / valid_batches

@torch.no_grad()
def eval_loop(model, loader, device, args):
    model.eval()
    total_loss, total_acc = 0.0, 0.0
    valid_batches = 0
    tp, tn, fp, fn = 0, 0, 0, 0
    total_vars = 0
    
    # Auditoría Multi-Tarea
    avg_mip_gap = 0.0
    
    for batch in loader:
        batch = batch.to(device)
        
        is_bin = batch['variable'].x[:, 4] == 1.0
        is_int = batch['variable'].x[:, 5] == 1.0
        is_discrete = is_bin | is_int
        
        lp_real = batch['variable'].x[:, 6]
        target_mask = is_discrete
        
        if target_mask.sum() == 0: 
            continue
            
        valid_batches += 1
        total_vars += target_mask.sum().item()

        # Leemos el MIP Gap de esta incumbente para la consola
        if hasattr(batch, 'mip_gap'):
            avg_mip_gap += batch.mip_gap.mean().item()

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=target_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)
        
        num_zeros = (targets == 0).sum().item()
        num_ones = (targets == 1).sum().item()
        peso_clase_1 = num_zeros / max(1.0, float(num_ones))
        pos_weight = torch.tensor([peso_clase_1], device=device)
        
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        loss = loss_fn(preds, targets)
        
        preds_bin = (preds > 0).float()
        acc = (preds_bin == targets).float().mean()
        
        tp += ((preds_bin == 1) & (targets == 1)).sum().item()
        tn += ((preds_bin == 0) & (targets == 0)).sum().item()
        fp += ((preds_bin == 1) & (targets == 0)).sum().item()
        fn += ((preds_bin == 0) & (targets == 1)).sum().item()
        
        total_loss += loss.item()
        total_acc += acc.item()
            
    if valid_batches == 0: return float('inf'), 0.0, 0, 0, 0, 0, 0, 0.0
    return (total_loss / valid_batches, total_acc / valid_batches, 
            tp, tn, fp, fn, total_vars // valid_batches, avg_mip_gap / valid_batches)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--grad_clip', type=float, default=1.0)
    
    # ATENCIÓN: Ahora estos números son GRAFOS (Incumbentes), no instancias.
    parser.add_argument('--easy_split', type=int, nargs=3, default=[0,0,0])
    parser.add_argument('--medium_split', type=int, nargs=3, default=[0,0,0])
    parser.add_argument('--hard_split', type=int, nargs=3, default=[0,0,0])
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Entrenamiento Neural Diving (Serial V4 - Multi-Grafo) en {device} ===")
    print(f"Parámetros: Hidden={args.hidden_dim} | LR={args.lr} | Clip={args.grad_clip}")
    print(f"Grafos Easy   (Train/Val/Test): {args.easy_split}")
    print(f"Grafos Medium (Train/Val/Test): {args.medium_split}")
    print(f"Grafos Hard   (Train/Val/Test): {args.hard_split}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    os.makedirs(output_dir, exist_ok=True)

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    config = {
        'CFL_easy_instance': args.easy_split,
        'CFL_medium_instance': args.medium_split,
        'CFL_hard_instance': args.hard_split
    }
    
    train_datasets, val_datasets, test_datasets = [], [], []
    generator = torch.Generator().manual_seed(42)
    
    for cat, (n_train, n_val, n_test) in config.items():
        total_req = n_train + n_val + n_test
        if total_req == 0: continue
            
        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)
        
        if len(ds) < total_req:
            print(f"\n[ERROR] '{cat}' solo tiene {len(ds)} grafos, pero pediste {total_req}.")
            sys.exit(1)
            
        unused = len(ds) - total_req
        ds_train, ds_val, ds_test, _ = random_split(ds, [n_train, n_val, n_test, unused], generator=generator)
        
        if n_train > 0: train_datasets.append(ds_train)
        if n_val > 0: val_datasets.append(ds_val)
        if n_test > 0: test_datasets.append(ds_test)
        
    train_data = ConcatDataset(train_datasets) if train_datasets else None
    val_data = ConcatDataset(val_datasets) if val_datasets else None
    test_data = ConcatDataset(test_datasets) if test_datasets else None
    
    if not train_data:
        print("\n[ERROR] Conjunto de entrenamiento vacío.")
        sys.exit(1)

    train_loader = DataLoader(train_data, batch_size=1, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=1, shuffle=False) if val_data else None
    test_loader = DataLoader(test_data, batch_size=1, shuffle=False) if test_data else None

    model = GasseGNN(
        var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2
    ).to(device)
    
    print("\nAjustando capas Prenorm...")
    for sample in train_loader:
        sample = sample.to(device)
        is_bin = sample['variable'].x[:, 4] == 1.0
        is_int = sample['variable'].x[:, 5] == 1.0
        is_discrete = is_bin | is_int
        
        lp_real = sample['variable'].x[:, 6]
        target_mask = is_discrete
        
        if target_mask.sum() > 0:
            model.fit_prenorm(
                x_var=sample['variable'].x, x_cons=sample['constraint'].x,
                edge_v2c=sample['variable', 'rev_coef', 'constraint'].edge_index,
                edge_attr=sample['variable', 'rev_coef', 'constraint'].edge_attr
            )
            break
            
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    
    epochs = 100
    best_val_loss = float('inf')

    print("-" * 115)
    print(f"{'Epoch':<6} | {'T.Loss':<8} | {'V.Loss':<8} | {'Acc (%)':<8} | {'TP':<5} {'TN':<5} {'FP':<4} {'FN':<4} | {'Vars/Grf':<8} | {'Avg. Gap':<8}")
    print("-" * 115)

    # --- NUEVO: Inicialización de variables para la gráfica y log ---
    hist_train_loss, hist_val_loss = [], []
    log_file = open(os.path.join(output_dir, "training_log_serial.txt"), "w")
    log_file.write("Epoch,Train_Loss,Val_Loss,Val_Accuracy\n")
    # ---------------------------------------------------------------
    
    for epoch in range(epochs):
        train_loss, _ = train_loop(model, train_loader, optimizer, device, args)
        
        if val_data:
            val_loss, val_acc, tp, tn, fp, fn, avg_vars, avg_gap = eval_loop(model, val_loader, device, args)
            
            log_str = f"Ep {epoch+1:<3} | {train_loss:<8.4f} | {val_loss:<8.4f} | {val_acc*100:<8.2f} | {tp:<5} {tn:<5} {fp:<4} {fn:<4} | {avg_vars:<8} | {avg_gap*100:.2f}%"
            
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_best_serial.pt"))
                log_str += " -> Best!"
            print(log_str)
        else:
            print(f"Epoch {epoch+1:<6} | Train Loss: {train_loss:.4f}")

        # --- NUEVO: Generación de Gráfica y escritura de Log ---
        hist_train_loss.append(train_loss)
        if val_data:
            hist_val_loss.append(val_loss)
            log_file.write(f"{epoch+1},{train_loss},{val_loss},{val_acc*100}\n")
        else:
            hist_val_loss.append(train_loss)
            log_file.write(f"{epoch+1},{train_loss},inf,0.0\n")
        log_file.flush()

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.set_xlabel('Epochs')
        ax.set_ylabel('BCE Loss')
        ax.plot(range(1, len(hist_train_loss) + 1), hist_train_loss, color='tab:red', label='Train Loss')
        if val_data:
            ax.plot(range(1, len(hist_val_loss) + 1), hist_val_loss, color='tab:orange', linestyle='dashed', label='Validation Loss')
        ax.legend()
        plt.title('Curva de Aprendizaje - Neural Diving (Serial)')
        fig.tight_layout()
        plt.savefig(os.path.join(output_dir, "loss_curve_split_serial.png"))
        plt.close(fig)
        # -------------------------------------------------------

    # --- NUEVO: Cerrar archivo al terminar las épocas ---
    log_file.close()

if __name__ == "__main__":
    main()