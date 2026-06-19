"""
Entrenamiento Serial (Single-GPU) para Neural Diving.
Ejecución 100% en FP32 (Precisión Simple NATIVA).
Cero riesgos de desbordamiento por suma de aristas.
"""
import sys
import os
import argparse
import torch
import torch.nn as nn
from torch_geometric.loader import DataLoader
import matplotlib.pyplot as plt

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN
from src.data_transformation.milp_dataset import NeuralDivingDataset

def train_loop(model, loader, optimizer, mse_fn, l1_fn, device, clear_cache):
    model.train()
    total_mse, total_mae, total_exact_acc = 0.0, 0.0, 0.0
    
    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        binary_mask = is_bin | is_int

        # FORWARD PASS: 100% FP32 Nativo. 
        # Cero riesgo de que _scatter_sum desborde.
        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=binary_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        targets = batch['variable'].y[binary_mask]
        
        # Pérdida directa sin necesidad de cast manual
        loss = mse_fn(preds, targets)
        
        # Backward Pass clásico (Sin Scaler)
        loss.backward()
        optimizer.step()
        
        with torch.no_grad():
            mae = l1_fn(preds, targets)
            rounded_preds = torch.round(preds)
            exact_matches = (rounded_preds == targets).float()
            exact_acc = exact_matches.mean()
            
            total_mse += loss.item()
            total_mae += mae.item()
            total_exact_acc += exact_acc.item()
            
        if clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    num_batches = len(loader)
    return total_mse / num_batches, total_mae / num_batches, total_exact_acc / num_batches

def main():
    parser = argparse.ArgumentParser(description="Neural Diving GNN Training (FP32 Puro)")
    parser.add_argument('--hidden_dim', type=int, default=64)
    parser.add_argument('--clear_cache', action='store_true')
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Iniciando Entrenamiento Neural Diving en {device} (FP32) ===")
    print(f"Parámetros: Hidden Dim = {args.hidden_dim} | Clear Cache = {args.clear_cache}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    os.makedirs(output_dir, exist_ok=True)

    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    dataset = NeuralDivingDataset(root=dataset_root)
    
    loader = DataLoader(dataset, batch_size=1, shuffle=True)
    print(f"Dataset cargado con {len(dataset)} instancias masivas.")

    model = GasseGNN(
        var_in_dim=7,     
        cons_in_dim=5,    
        edge_dim=1,       
        hidden_dim=args.hidden_dim,
        num_layers=2
    ).to(device)
    
    print("Ajustando capas Prenorm en FP32...")
    sample = next(iter(loader)).to(device)
    
    # Prenorm directo, sin autocast
    model.fit_prenorm(
        x_var=sample['variable'].x,
        x_cons=sample['constraint'].x,
        edge_v2c=sample['variable', 'rev_coef', 'constraint'].edge_index,
        edge_attr=sample['variable', 'rev_coef', 'constraint'].edge_attr
    )
    
    if args.clear_cache:
        del sample
        torch.cuda.empty_cache()

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    mse_fn = nn.MSELoss()
    l1_fn = nn.L1Loss()
    
    epochs = 100
    hist_mse, hist_mae = [], []

    print("-" * 60)
    print(f"{'Epoch':<10} | {'MSE Loss':<12} | {'MAE':<12} | {'Exact Acc (%)':<15}")
    print("-" * 60)
    
    log_file_path = os.path.join(output_dir, "training_log.txt")

    with open(log_file_path, "w") as log_file:
        log_file.write("Epoch,MSE,MAE,Exact_Acc\n")
        
        for epoch in range(epochs):
            avg_mse, avg_mae, avg_acc = train_loop(model, loader, optimizer, mse_fn, l1_fn, device, args.clear_cache)
            
            hist_mse.append(avg_mse)
            hist_mae.append(avg_mae)
            
            log_str = f"Epoch {epoch+1:<6} | {avg_mse:<12.4f} | {avg_mae:<12.4f} | {avg_acc * 100:<13.2f}%"
            print(log_str)
            
            log_file.write(f"{epoch+1},{avg_mse},{avg_mae},{avg_acc*100}\n")
            log_file.flush()
            
            if (epoch + 1) % 10 == 0:
                torch.save(model.state_dict(), os.path.join(output_dir, f"neural_diving_epoch_{epoch+1}.pt"))
    
    torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_final.pt"))

    plt.figure(figsize=(10, 6))
    plt.plot(range(1, epochs + 1), hist_mse, label='MSE (Loss)')
    plt.plot(range(1, epochs + 1), hist_mae, label='MAE')
    plt.xlabel('Epochs')
    plt.ylabel('Error')
    plt.title('Curva de Convergencia - Neural Diving (FP32)')
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, "loss_curve.png"))
    plt.close()

    print(f"\n¡Entrenamiento finalizado! Resultados guardados en: {output_dir}")

if __name__ == "__main__":
    main()