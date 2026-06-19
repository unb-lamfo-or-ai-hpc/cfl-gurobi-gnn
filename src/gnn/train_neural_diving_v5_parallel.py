import sys
import os
import argparse
import torch
import torch.nn as nn
from torch_geometric.loader import DataLoader
from torch.cuda.amp import autocast, GradScaler
import matplotlib.pyplot as plt
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data.distributed import DistributedSampler

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN
from src.data_transformation.milp_dataset import NeuralDivingDataset

def train_loop(model, loader, optimizer, mse_fn, l1_fn, device, scaler, clear_cache):
    model.train()
    total_mse, total_mae, total_exact_acc = 0.0, 0.0, 0.0
    
    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        binary_mask = is_bin | is_int
        
        safe_x_var = torch.clamp(batch['variable'].x, min=-60000.0, max=60000.0)
        safe_x_cons = torch.clamp(batch['constraint'].x, min=-60000.0, max=60000.0)
        safe_edge_attr = torch.clamp(batch['variable', 'rev_coef', 'constraint'].edge_attr, min=-60000.0, max=60000.0)
        
        with autocast():
            preds = model(
                x_var=safe_x_var,
                x_cons=safe_x_cons,
                edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
                binary_mask=binary_mask,
                edge_attr=safe_edge_attr
            )
            
            targets = batch['variable'].y[binary_mask]
            targets = torch.clamp(targets, min=-60000.0, max=60000.0)
            loss = mse_fn(preds, targets)
        
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        
        with torch.no_grad():
            mae = l1_fn(preds, targets)
            rounded_preds = torch.round(preds)
            exact_matches = (rounded_preds == targets).float()
            exact_acc = exact_matches.mean()
            
            total_mse += loss.item()
            total_mae += mae.item()
            total_exact_acc += exact_acc.item()
            
        if clear_cache:
            del batch, preds, targets, loss, safe_x_var, safe_x_cons, safe_edge_attr
            torch.cuda.empty_cache()
            
    num_batches = len(loader)
    # Evitar división por cero si una GPU se queda sin grafos en la última ronda
    if num_batches == 0:
        return 0.0, 0.0, 0.0
    return total_mse / num_batches, total_mae / num_batches, total_exact_acc / num_batches

def main():
    # 1. INICIALIZAR EL ENTORNO DISTRIBUIDO (DDP)
    dist.init_process_group(backend="nccl")
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    torch.cuda.set_device(local_rank)
    device = torch.device(f"cuda:{local_rank}")
    is_master = local_rank == 0  # Solo la GPU 0 será el "Maestro"

    parser = argparse.ArgumentParser(description="Neural Diving GNN Training (Multi-GPU)")
    parser.add_argument('--hidden_dim', type=int, default=64)
    parser.add_argument('--clear_cache', action='store_true')
    args = parser.parse_args()

    if is_master:
        print(f"=== Iniciando Entrenamiento Neural Diving DDP ===")
        print(f"GPUs detectadas: {dist.get_world_size()}")
        print(f"Parámetros: Hidden Dim = {args.hidden_dim} | Clear Cache = {args.clear_cache}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    if is_master:
        os.makedirs(output_dir, exist_ok=True)

    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    dataset = NeuralDivingDataset(root=dataset_root)
    
    # 2. EL REPARTIDOR DE CARTAS (DistributedSampler)
    sampler = DistributedSampler(dataset)
    # shuffle=False porque el sampler ya se encarga de barajar los datos
    loader = DataLoader(dataset, batch_size=1, sampler=sampler, shuffle=False)
    
    if is_master:
        print(f"Dataset cargado con {len(dataset)} instancias masivas.")

    # 3. CREAR EL MODELO Y ENVOLVERLO EN DDP
    model = GasseGNN(var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2).to(device)
    
    sample = next(iter(loader)).to(device)
    with autocast():
        model.fit_prenorm(
            x_var=torch.clamp(sample['variable'].x, -60000.0, 60000.0),
            x_cons=torch.clamp(sample['constraint'].x, -60000.0, 60000.0),
            edge_v2c=sample['variable', 'rev_coef', 'constraint'].edge_index,
            edge_attr=torch.clamp(sample['variable', 'rev_coef', 'constraint'].edge_attr, -60000.0, 60000.0)
        )
    
    # DDP: Envuelve el modelo para sincronizar los gradientes entre las GPUs
    model = DDP(model, device_ids=[local_rank])

    if args.clear_cache:
        del sample
        torch.cuda.empty_cache()

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    mse_fn = nn.MSELoss()
    l1_fn = nn.L1Loss()
    scaler = GradScaler()
    
    epochs = 100
    hist_mse, hist_mae = [], []
    
    if is_master:
        print("-" * 60)
        print(f"{'Epoch':<10} | {'MSE Loss':<12} | {'MAE':<12} | {'Exact Acc (%)':<15}")
        print("-" * 60)
        log_file = open(os.path.join(output_dir, "training_log.txt"), "w")
        log_file.write("Epoch,MSE,MAE,Exact_Acc\n")
        
    for epoch in range(epochs):
        # MUY IMPORTANTE: Asegura que el orden cambie en cada época
        sampler.set_epoch(epoch)
        
        avg_mse, avg_mae, avg_acc = train_loop(model, loader, optimizer, mse_fn, l1_fn, device, scaler, args.clear_cache)
        
        # 4. SOLO EL MAESTRO IMPRIME Y GUARDA
        if is_master:
            hist_mse.append(avg_mse)
            hist_mae.append(avg_mae)
            
            log_str = f"Epoch {epoch+1:<6} | {avg_mse:<12.4f} | {avg_mae:<12.4f} | {avg_acc * 100:<13.2f}%"
            print(log_str)
            
            log_file.write(f"{epoch+1},{avg_mse},{avg_mae},{avg_acc*100}\n")
            log_file.flush()
            
            if (epoch + 1) % 10 == 0:
                torch.save(model.module.state_dict(), os.path.join(output_dir, f"neural_diving_epoch_{epoch+1}.pt"))
    
    if is_master:
        torch.save(model.module.state_dict(), os.path.join(output_dir, "neural_diving_final.pt"))
        log_file.close()
        
        plt.figure(figsize=(10, 6))
        plt.plot(range(1, epochs + 1), hist_mse, label='MSE (Loss)')
        plt.plot(range(1, epochs + 1), hist_mae, label='MAE')
        plt.xlabel('Epochs')
        plt.ylabel('Error')
        plt.title('Curva de Convergencia - Neural Diving (8 GPUs)')
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, "loss_curve.png"))
        plt.close()
        
        print(f"\n¡Entrenamiento finalizado! Gráfico y modelos guardados en: {output_dir}")

    # Cierra los procesos de comunicación
    dist.destroy_process_group()

if __name__ == "__main__":
    main()