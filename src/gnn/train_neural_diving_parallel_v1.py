"""
Entrenamiento Paralelo (DDP Multi-GPU) con Split (Train/Val/Test).
Formulación de Clasificación Binaria (BCE Loss + Exact Accuracy).
Evalúa y guarda el mejor modelo basado en Validation Loss global.
"""
import sys
import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import random_split
from torch_geometric.loader import DataLoader
import matplotlib.pyplot as plt

# Librerías DDP
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data.distributed import DistributedSampler

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
        
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        binary_mask = is_bin | is_int
        
        if binary_mask.sum() == 0: continue
        local_valid_batches += 1

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=binary_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        if torch.isnan(preds).any():
            print(f"\n[ERROR CRÍTICO Rank {dist.get_rank()}] NaN en PREDICCIONES (Train).")
            sys.exit(1)
            
        targets = torch.clamp(batch['variable'].y[binary_mask], min=0.0, max=1.0)
        loss = loss_fn(preds, targets)
        
        if torch.isnan(loss):
            print(f"\n[ERROR CRÍTICO Rank {dist.get_rank()}] NaN en la PÉRDIDA (Train).")
            sys.exit(1)
        
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
            
    # Reducción Global
    metrics_tensor = torch.tensor([local_loss, local_acc, local_valid_batches], device=device)
    dist.all_reduce(metrics_tensor, op=dist.ReduceOp.SUM)
    
    global_loss = metrics_tensor[0].item()
    global_acc = metrics_tensor[1].item()
    global_batches = metrics_tensor[2].item()
    
    if global_batches == 0: return float('inf'), 0.0
    return global_loss / global_batches, global_acc / global_batches

@torch.no_grad()
def eval_loop(model, loader, loss_fn, device, args):
    model.eval()
    local_loss, local_acc, local_valid_batches = 0.0, 0.0, 0.0
    
    for batch in loader:
        batch = batch.to(device)
        
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        binary_mask = is_bin | is_int
        
        if binary_mask.sum() == 0: continue
        local_valid_batches += 1

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=binary_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        targets = torch.clamp(batch['variable'].y[binary_mask], min=0.0, max=1.0)
        loss = loss_fn(preds, targets)
        
        acc = ((preds > 0).float() == targets).float().mean()
        local_loss += loss.item()
        local_acc += acc.item()
        
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    # Reducción Global para Validación/Test
    metrics_tensor = torch.tensor([local_loss, local_acc, local_valid_batches], device=device)
    dist.all_reduce(metrics_tensor, op=dist.ReduceOp.SUM)
    
    global_loss = metrics_tensor[0].item()
    global_acc = metrics_tensor[1].item()
    global_batches = metrics_tensor[2].item()
    
    if global_batches == 0: return float('inf'), 0.0
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
    
    parser.add_argument('--train_frac', type=float, default=0.8)
    parser.add_argument('--val_frac', type=float, default=0.1)
    parser.add_argument('--test_frac', type=float, default=0.1)
    args = parser.parse_args()

    assert abs((args.train_frac + args.val_frac + args.test_frac) - 1.0) < 1e-5, "Sum of fractions must be 1.0"

    if is_master:
        print(f"=== Entrenamiento Neural Diving DDP (Split Train/Val/Test) ===")
        print(f"GPUs sincronizadas: {dist.get_world_size()}")
        print(f"Parámetros: Hidden={args.hidden_dim} | LR={args.lr} | Clip={args.grad_clip}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    if is_master: os.makedirs(output_dir, exist_ok=True)

    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    full_dataset = NeuralDivingDataset(root=dataset_root)
    
    dataset_size = len(full_dataset)
    train_size = int(args.train_frac * dataset_size)
    val_size = int(args.val_frac * dataset_size)
    test_size = dataset_size - train_size - val_size
    
    if is_master:
        print(f"Dataset total: {dataset_size} grafos.")
        print(f"Split -> Train: {train_size} | Val: {val_size} | Test: {test_size}")
    
    # CRÍTICO EN DDP: Usar una semilla fija para que todas las GPUs hagan la misma partición
    generator = torch.Generator().manual_seed(42)
    train_data, val_data, test_data = random_split(full_dataset, [train_size, val_size, test_size], generator=generator)
    
    # Samplers independientes para cada subconjunto
    train_sampler = DistributedSampler(train_data, shuffle=True)
    train_loader = DataLoader(train_data, batch_size=1, sampler=train_sampler)
    
    if val_size > 0:
        val_sampler = DistributedSampler(val_data, shuffle=False)
        val_loader = DataLoader(val_data, batch_size=1, sampler=val_sampler)
        
    if test_size > 0:
        test_sampler = DistributedSampler(test_data, shuffle=False)
        test_loader = DataLoader(test_data, batch_size=1, sampler=test_sampler)
    
    model = GasseGNN(
        var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2
    ).to(device)
    
    # Prenorm usando solo datos de entrenamiento locales a esta GPU
    for sample in train_loader:
        sample = sample.to(device)
        if ((sample['variable'].x[:, 3] == 1.0) | (sample['variable'].x[:, 4] == 1.0)).sum() > 0:
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
        
        if val_size > 0:
            val_loss, val_acc = eval_loop(model, val_loader, loss_fn, device, args)
        else:
            val_loss, val_acc = float('inf'), 0.0
            
        if is_master:
            hist_train_loss.append(train_loss)
            hist_val_loss.append(val_loss)
            
            log_str = f"Epoch {epoch+1:<6} | {train_loss:<12.4f} | {val_loss:<12.4f} | {val_acc * 100:<10.2f}%"
            
            if val_loss < best_val_loss and val_size > 0:
                best_val_loss = val_loss
                torch.save(model.module.state_dict(), os.path.join(output_dir, "neural_diving_best_parallel.pt"))
                log_str += "  --> ¡Mejor Val Loss guardado!"
                
            print(log_str)
            log_file.write(f"{epoch+1},{train_loss},{val_loss},{val_acc*100}\n")
            log_file.flush()
            
            # Live-Plotting con dos curvas
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.set_xlabel('Epochs')
            ax.set_ylabel('BCE Loss')
            ax.plot(range(1, len(hist_train_loss) + 1), hist_train_loss, color='tab:red', label='Train Loss')
            if val_size > 0:
                ax.plot(range(1, len(hist_val_loss) + 1), hist_val_loss, color='tab:orange', linestyle='dashed', label='Validation Loss')
            ax.legend()
            plt.title('Curva de Aprendizaje - Neural Diving (DDP)')
            fig.tight_layout()
            plt.savefig(os.path.join(output_dir, "loss_curve_split_parallel.png"))
            plt.close(fig)

    if is_master:
        torch.save(model.module.state_dict(), os.path.join(output_dir, "neural_diving_final_parallel.pt"))
        log_file.close()

    # Evaluación Final Sincronizada en Test Set
    if test_size > 0:
        dist.barrier() # Esperar a que el maestro guarde el modelo
        model.module.load_state_dict(torch.load(os.path.join(output_dir, "neural_diving_best_parallel.pt"), map_location=device))
        
        test_loss, test_acc = eval_loop(model, test_loader, loss_fn, device, args)
        
        if is_master:
            print("\n=== Evaluación Final en Test Set ===")
            print(f"Test Loss: {test_loss:.4f} | Test Accuracy: {test_acc * 100:.2f}%")
            print(f"\n¡Entrenamiento Multi-GPU finalizado! Gráfica en: {output_dir}")

    dist.barrier()
    dist.destroy_process_group()

if __name__ == "__main__":
    main()