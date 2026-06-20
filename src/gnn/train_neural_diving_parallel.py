"""
Entrenamiento Paralelo (DDP Multi-GPU) con Diagnóstico de NaNs.
Formulación de Clasificación Binaria (BCE Loss + Exact Accuracy).
Optimizado para rendimiento en clúster y bajo consumo de disco.
"""
import sys
import os
import argparse
import torch
import torch.nn as nn
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
        
        if binary_mask.sum() == 0:
            continue

        local_valid_batches += 1

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=binary_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        if torch.isnan(preds).any():
            print(f"\n[ERROR CRÍTICO Rank {dist.get_rank()}] NaN en PREDICCIONES.")
            sys.exit(1)
            
        targets = batch['variable'].y[binary_mask]
        targets = torch.clamp(targets, min=0.0, max=1.0)
        
        loss = loss_fn(preds, targets)
        
        if torch.isnan(loss):
            print(f"\n[ERROR CRÍTICO Rank {dist.get_rank()}] NaN en la PÉRDIDA.")
            sys.exit(1)
        
        loss.backward()
        
        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)
        
        optimizer.step()
        
        with torch.no_grad():
            predicted_classes = (preds > 0).float()
            acc = (predicted_classes == targets).float().mean()
            
            local_loss += loss.item()
            local_acc += acc.item()
            
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    # Reducción Global: Sincronizar las métricas de todas las GPUs
    metrics_tensor = torch.tensor([local_loss, local_acc, local_valid_batches], device=device)
    dist.all_reduce(metrics_tensor, op=dist.ReduceOp.SUM)
    
    global_loss = metrics_tensor[0].item()
    global_acc = metrics_tensor[1].item()
    global_batches = metrics_tensor[2].item()
    
    if global_batches == 0: 
        return 0.0, 0.0
    return global_loss / global_batches, global_acc / global_batches

def main():
    # 1. INICIALIZACIÓN DDP
    dist.init_process_group(backend="nccl")
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    torch.cuda.set_device(local_rank)
    device = torch.device(f"cuda:{local_rank}")
    is_master = (local_rank == 0)

    parser = argparse.ArgumentParser(description="Neural Diving GNN Training (DDP Clasificación)")
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--grad_clip', type=float, default=1.0)
    parser.add_argument('--clear_cache', action='store_true')
    args = parser.parse_args()

    if is_master:
        print(f"=== Entrenamiento Neural Diving (DDP Clasificación) ===")
        print(f"GPUs sincronizadas: {dist.get_world_size()}")
        print(f"Parámetros: Hidden={args.hidden_dim} | LR={args.lr} | Clip={args.grad_clip}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    if is_master: os.makedirs(output_dir, exist_ok=True)

    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    dataset = NeuralDivingDataset(root=dataset_root)
    
    # 2. SAMPLER DISTRIBUIDO (Reparte los grafos sin repetirlos)
    sampler = DistributedSampler(dataset)
    loader = DataLoader(dataset, batch_size=1, sampler=sampler, shuffle=False)
    
    model = GasseGNN(
        var_in_dim=7,     
        cons_in_dim=5,    
        edge_dim=1,       
        hidden_dim=args.hidden_dim,
        num_layers=2
    ).to(device)
    
    # Pre-Normalización (Buscando un grafo válido en el subset local de esta GPU)
    for sample in loader:
        sample = sample.to(device)
        is_bin = sample['variable'].x[:, 3] == 1.0
        is_int = sample['variable'].x[:, 4] == 1.0
        if (is_bin | is_int).sum() > 0:
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

    # 3. ENVOLVER EN DDP (Sincroniza los pesos y prenorms en todo el clúster automáticamente)
    model = DDP(model, device_ids=[local_rank])

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.BCEWithLogitsLoss()
    
    epochs = 100
    
    if is_master:
        hist_loss, hist_acc = [], []
        best_acc = 0.0
        print("-" * 55)
        print(f"{'Epoch':<10} | {'BCE Loss':<15} | {'Global Acc (%)':<15}")
        print("-" * 55)
        log_file = open(os.path.join(output_dir, "training_log_parallel.txt"), "w")
        log_file.write("Epoch,BCE_Loss,Accuracy\n")
        
    for epoch in range(epochs):
        # OBLIGATORIO EN DDP: Cambiar la semilla del repartidor en cada época
        sampler.set_epoch(epoch)
        
        avg_loss, avg_acc = train_loop(model, loader, optimizer, loss_fn, device, args)
        
        # 4. ESCRITURA EXCLUSIVA DEL NODO MAESTRO
        if is_master:
            hist_loss.append(avg_loss)
            hist_acc.append(avg_acc * 100)
            
            log_str = f"Epoch {epoch+1:<6} | {avg_loss:<15.4f} | {avg_acc * 100:<13.2f}%"
            
            # Guardado inteligente en disco
            if avg_acc > best_acc and avg_acc > 0:
                best_acc = avg_acc
                # .module es necesario al guardar modelos envueltos en DDP
                torch.save(model.module.state_dict(), os.path.join(output_dir, "neural_diving_best_parallel.pt"))
                log_str += "  --> ¡Mejor modelo guardado!"
                
            print(log_str)
            log_file.write(f"{epoch+1},{avg_loss},{avg_acc*100}\n")
            log_file.flush()
    
    if is_master:
        torch.save(model.module.state_dict(), os.path.join(output_dir, "neural_diving_final_parallel.pt"))
        log_file.close()
        
        # Gráfica
        fig, ax1 = plt.subplots(figsize=(10, 6))
        color = 'tab:red'
        ax1.set_xlabel('Epochs')
        ax1.set_ylabel('BCE Loss', color=color)
        ax1.plot(range(1, epochs + 1), hist_loss, color=color, label='Loss')
        ax1.tick_params(axis='y', labelcolor=color)
        
        ax2 = ax1.twinx()
        color = 'tab:blue'
        ax2.set_ylabel('Global Accuracy (%)', color=color)
        ax2.plot(range(1, epochs + 1), hist_acc, color=color, label='Accuracy')
        ax2.tick_params(axis='y', labelcolor=color)
        
        plt.title('Convergencia Neural Diving (DDP Multi-GPU)')
        fig.tight_layout()
        plt.savefig(os.path.join(output_dir, "loss_curve_parallel.png"))
        plt.close()
        print(f"\n¡Entrenamiento Multi-GPU finalizado! Gráfica en: {output_dir}")

    # Destruir grupo de sincronización limpiamente
    dist.barrier()
    dist.destroy_process_group()

if __name__ == "__main__":
    main()