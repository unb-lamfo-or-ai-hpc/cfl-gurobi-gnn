"""
Entrenamiento Paralelo (DDP Multi-GPU) con Split (Train/Val/Test)..
Ensamblaje Modular de Datasets por Dificultad (OOD Generalization).
Formulación de Clasificación Binaria (BCE Loss + Exact Accuracy).
Evalúa y guarda el mejor modelo basado en Validation Loss global.
"""
import sys
import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import random_split, ConcatDataset
from torch_geometric.loader import DataLoader
import matplotlib.pyplot as plt

# Librerías DDP
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data.distributed import DistributedSampler

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

def train_loop(model, loader, optimizer, loss_fn, device, args):
    model.train()
    local_loss, local_acc, local_valid_batches = 0.0, 0.0, 0.0
    
    for batch_idx, batch in enumerate(loader):
        batch = batch.to(device)
        optimizer.zero_grad()

        # 1. Identificamos variables discretas
        is_bin = batch['variable'].x[:, 4] == 1.0
        is_int = batch['variable'].x[:, 5] == 1.0
        is_discrete = is_bin | is_int

        # 2. Extraemos el LP (Columna 6)
        lp_values = batch['variable'].x[:, 6]
        target_mask = is_discrete
        
        if target_mask.sum() == 0: continue
        #if binary_mask.sum() == 0: continue
        local_valid_batches += 1

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            #binary_mask=binary_mask,
            binary_mask=target_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
            
        #targets = torch.clamp(batch['variable'].y[binary_mask], min=0.0, max=1.0)
        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)        

        # --- Opcional: PESOS DINÁMICOS PARA DESBALANCE DE CLASES ---
        # Descomentar estas líneas si la red predice todo '0'
        # num_zeros = (targets == 0).sum().item()
        # num_ones = (targets == 1).sum().item()
        # peso_clase_1 = num_zeros / max(1.0, float(num_ones))
        # pos_weight = torch.tensor([peso_clase_1], device=device)
        # dynamic_loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        # loss = dynamic_loss_fn(preds, targets)
        # -----------------------------------------------------------   

        loss = loss_fn(preds, targets)
        loss.backward()
        
        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)
        
        optimizer.step()
        
        with torch.no_grad():
            acc = ((preds > 0).float() == targets).float().mean()
            local_loss += loss.item()
            local_acc += acc.item()
            
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    metrics_tensor = torch.tensor([local_loss, local_acc, local_valid_batches], device=device)
    dist.all_reduce(metrics_tensor, op=dist.ReduceOp.SUM)
    
    global_loss = metrics_tensor[0].item()
    global_acc = metrics_tensor[1].item()
    global_batches = metrics_tensor[2].item()
    
    if global_batches == 0: return float('inf'), 0.0
    #return metrics_tensor[0].item() / global_batches, metrics_tensor[1].item() / global_batches
    return global_loss / global_batches, global_acc / global_batches

@torch.no_grad()
def eval_loop(model, loader, loss_fn, device, args):
    model.eval()
    local_loss, local_acc, local_valid_batches = 0.0, 0.0, 0.0
    
    for batch in loader:
        batch = batch.to(device)
        
        # 1. Identificamos variables discretas
        is_bin = batch['variable'].x[:, 4] == 1.0
        is_int = batch['variable'].x[:, 5] == 1.0
        is_discrete = is_bin | is_int

        # 2. Extraemos el LP (Columna 6)
        lp_values = batch['variable'].x[:, 6]
        target_mask = is_discrete
        
        if target_mask.sum() == 0: 
            continue
        #if binary_mask.sum() == 0: continue
        
        local_valid_batches += 1

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            #binary_mask=binary_mask,
            binary_mask=target_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        #targets = torch.clamp(batch['variable'].y[binary_mask], min=0.0, max=1.0)
        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0)

        # --- Opcional: PESOS DINÁMICOS PARA DESBALANCE DE CLASES ---
        # Descomentar estas líneas si la red predice todo '0'
        # num_zeros = (targets == 0).sum().item()
        # num_ones = (targets == 1).sum().item()
        # peso_clase_1 = num_zeros / max(1.0, float(num_ones))
        # pos_weight = torch.tensor([peso_clase_1], device=device)
        # dynamic_loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        # loss = dynamic_loss_fn(preds, targets)
        # -----------------------------------------------------------


        loss = loss_fn(preds, targets)
        
        acc = ((preds > 0).float() == targets).float().mean()
        local_loss += loss.item()
        local_acc += acc.item()
        
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    metrics_tensor = torch.tensor([local_loss, local_acc, local_valid_batches], device=device)
    dist.all_reduce(metrics_tensor, op=dist.ReduceOp.SUM)
    
    global_loss = metrics_tensor[0].item()
    global_acc = metrics_tensor[1].item()
    global_batches = metrics_tensor[2].item()

    if global_batches == 0: return float('inf'), 0.0
    #return metrics_tensor[0].item() / global_batches, metrics_tensor[1].item() / global_batches
    return global_loss / global_batches, global_acc / global_batches

def main():
    dist.init_process_group(backend="nccl")
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    torch.cuda.set_device(local_rank)
    device = torch.device(f"cuda:{local_rank}")
    is_master = (local_rank == 0)

    parser = argparse.ArgumentParser()
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--grad_clip', type=float, default=1.0)
    parser.add_argument('--clear_cache', action='store_true')
    
    # Nuevos parámetros modulares: [Train, Validation, Test]
    parser.add_argument('--easy_split', type=int, nargs=3, default=[0,0,0], help="Cantidades para Easy: Train Val Test")
    parser.add_argument('--medium_split', type=int, nargs=3, default=[0,0,0], help="Cantidades para Medium: Train Val Test")
    parser.add_argument('--hard_split', type=int, nargs=3, default=[0,0,0], help="Cantidades para Hard: Train Val Test")
    
    args = parser.parse_args()

    if is_master:
        print(f"=== Entrenamiento Neural Diving DDP (Modular Split) ===")
        print(f"Parámetros: Hidden={args.hidden_dim} | LR={args.lr} | Clip={args.grad_clip}")
        print(f"Easy   (Train/Val/Test): {args.easy_split}")
        print(f"Medium (Train/Val/Test): {args.medium_split}")
        print(f"Hard   (Train/Val/Test): {args.hard_split}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    if is_master: os.makedirs(output_dir, exist_ok=True)

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    # === ENSAMBLAJE MODULAR DEL DATASET ===
    config = {
        'CFL_easy_instance': args.easy_split,
        'CFL_medium_instance': args.medium_split,
        'CFL_hard_instance': args.hard_split
    }
    
    train_datasets, val_datasets, test_datasets = [], [], []
    generator = torch.Generator().manual_seed(42) # Semilla fija para evitar fugas de datos
    
    for cat, (n_train, n_val, n_test) in config.items():
        total_req = n_train + n_val + n_test
        if total_req == 0: continue
            
        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)
        
        if len(ds) < total_req:
            if is_master: print(f"\n[ERROR] '{cat}' solo tiene {len(ds)} grafos listos, pero pediste {total_req}.")
            sys.exit(1)
            
        unused = len(ds) - total_req
        # Dividir limpiamente esta categoría sin solapamientos
        ds_train, ds_val, ds_test, _ = random_split(ds, [n_train, n_val, n_test, unused], generator=generator)
        
        if n_train > 0: train_datasets.append(ds_train)
        if n_val > 0: val_datasets.append(ds_val)
        if n_test > 0: test_datasets.append(ds_test)
        
    train_data = ConcatDataset(train_datasets) if train_datasets else None
    val_data = ConcatDataset(val_datasets) if val_datasets else None
    test_data = ConcatDataset(test_datasets) if test_datasets else None
    
    if not train_data:
        if is_master: print("\n[ERROR] El conjunto de entrenamiento está vacío. Ajusta los parámetros.")
        sys.exit(1)

    # Samplers y Loaders
    train_sampler = DistributedSampler(train_data, shuffle=True)
    train_loader = DataLoader(train_data, batch_size=1, sampler=train_sampler)
    
    val_loader, test_loader = None, None
    if val_data:
        val_sampler = DistributedSampler(val_data, shuffle=False)
        val_loader = DataLoader(val_data, batch_size=1, sampler=val_sampler)
    if test_data:
        test_sampler = DistributedSampler(test_data, shuffle=False)
        test_loader = DataLoader(test_data, batch_size=1, sampler=test_sampler)
    
    model = GasseGNN(
        var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2
    ).to(device)
    
    # Prenorm
    for sample in train_loader:
        sample = sample.to(device)
        if ((sample['variable'].x[:, 4] == 1.0) | (sample['variable'].x[:, 5] == 1.0)).sum() > 0:
            model.fit_prenorm(
                x_var=sample['variable'].x,
                x_cons=sample['constraint'].x,
                edge_v2c=sample['variable', 'rev_coef', 'constraint'].edge_index,
                edge_attr=sample['variable', 'rev_coef', 'constraint'].edge_attr
            )
            break
            
    if args.clear_cache:
        del sample
        torch.cuda.empty_cache()

    model = DDP(model, device_ids=[local_rank])
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.BCEWithLogitsLoss()
    
    epochs = 100
    best_val_loss = float('inf')
    
    if is_master:
        hist_train_loss, hist_val_loss = [], []
        print("-" * 75)
        print(f"{'Epoch':<8} | {'Train Loss':<12} | {'Val Loss':<12} | {'Val Acc (%)':<12}")
        print("-" * 75)
        log_file = open(os.path.join(output_dir, "training_log_parallel.txt"), "w")
        log_file.write("Epoch,Train_Loss,Val_Loss,Val_Accuracy\n")
        
    for epoch in range(epochs):
        train_sampler.set_epoch(epoch)
        train_loss, _ = train_loop(model, train_loader, optimizer, loss_fn, device, args)
        
        if val_data:
            val_loss, val_acc = eval_loop(model, val_loader, loss_fn, device, args)
        else:
            val_loss, val_acc = float('inf'), 0.0
            
        if is_master:
            hist_train_loss.append(train_loss)
            hist_val_loss.append(val_loss if val_data else train_loss) # Fallback para el plot
            
            log_str = f"Epoch {epoch+1:<6} | {train_loss:<12.4f} | {val_loss:<12.4f} | {val_acc * 100:<10.2f}%"
            
            if val_loss < best_val_loss and val_data:
                best_val_loss = val_loss
                torch.save(model.module.state_dict(), os.path.join(output_dir, "neural_diving_best_parallel.pt"))
                log_str += "  --> ¡Mejor Val Loss guardado!"
                
            print(log_str)
            log_file.write(f"{epoch+1},{train_loss},{val_loss},{val_acc*100}\n")
            log_file.flush()
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.set_xlabel('Epochs')
            ax.set_ylabel('BCE Loss')
            ax.plot(range(1, len(hist_train_loss) + 1), hist_train_loss, color='tab:red', label='Train Loss')
            if val_data:
                ax.plot(range(1, len(hist_val_loss) + 1), hist_val_loss, color='tab:orange', linestyle='dashed', label='Validation Loss')
            ax.legend()
            plt.title('Curva de Aprendizaje - Neural Diving (DDP)')
            fig.tight_layout()
            plt.savefig(os.path.join(output_dir, "loss_curve_split_parallel.png"))
            plt.close(fig)

    if is_master:
        torch.save(model.module.state_dict(), os.path.join(output_dir, "neural_diving_final_parallel.pt"))
        log_file.close()

    # Evaluación Final
    if test_data:
        dist.barrier()
        # Cargamos el modelo ganador para el test final
        best_model_path = os.path.join(output_dir, "neural_diving_best_parallel.pt")
        if os.path.exists(best_model_path):
            model.module.load_state_dict(torch.load(best_model_path, map_location=device))
        
        test_loss, test_acc = eval_loop(model, test_loader, loss_fn, device, args)
        
        if is_master:
            print("\n=== Evaluación Final en Test Set ===")
            print(f"Test Loss: {test_loss:.4f} | Test Accuracy: {test_acc * 100:.2f}%")

    if is_master: print(f"\n¡Entrenamiento Multi-GPU finalizado! Gráfica en: {output_dir}")
    dist.barrier()
    dist.destroy_process_group()

if __name__ == "__main__":
    main()