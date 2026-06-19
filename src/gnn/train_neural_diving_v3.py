import sys
import os
import argparse
import torch
import torch.nn as nn
from torch_geometric.loader import DataLoader
from torch.cuda.amp import autocast, GradScaler

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
        
        # Entrenamiento con Precisión Mixta (FP16)
        with autocast():
            preds = model(
                x_var=batch['variable'].x,
                x_cons=batch['constraint'].x,
                edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
                binary_mask=binary_mask,
                edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
            )
            
            targets = batch['variable'].y[binary_mask]
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
            
        # Vaciado de caché opcional (Solo si se pasa el flag por consola)
        if clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    num_batches = len(loader)
    return total_mse / num_batches, total_mae / num_batches, total_exact_acc / num_batches

def main():
    # 1. Configurar Argumentos de Consola
    parser = argparse.ArgumentParser(description="Neural Diving GNN Training")
    parser.add_argument('--hidden_dim', type=int, default=64, 
                        help='Dimensión oculta de la red (Gasse et al. usa 64). Bajar a 32 si hay OOM.')
    parser.add_argument('--clear_cache', action='store_true', 
                        help='Fuerza a vaciar la caché de la GPU en cada batch (Lento, pero ahorra RAM).')
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Iniciando Entrenamiento Neural Diving en {device} ===")
    print(f"Parámetros: Hidden Dim = {args.hidden_dim} | Clear Cache = {args.clear_cache}")

    # 2. Configurar Rutas
    output_dir = os.path.join(project_root, "data", "real_train_output")
    os.makedirs(output_dir, exist_ok=True)

    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    dataset = NeuralDivingDataset(root=dataset_root)
    
    loader = DataLoader(dataset, batch_size=1, shuffle=True)
    print(f"Dataset cargado con {len(dataset)} instancias masivas.")

    # 3. Inicializar Modelo con la dimensión parametrizada
    model = GasseGNN(
        var_in_dim=7,     
        cons_in_dim=5,    
        edge_dim=1,       
        hidden_dim=args.hidden_dim,
        num_layers=2
    ).to(device)
    
    print("Ajustando capas Prenorm...")
    sample = next(iter(loader)).to(device)
    
    with autocast():
        model.fit_prenorm(
            x_var=sample['variable'].x,
            x_cons=sample['constraint'].x,
            edge_v2c=sample['variable', 'rev_coef', 'constraint'].edge_index,
            edge_attr=sample['variable', 'rev_coef', 'constraint'].edge_attr
        )
    
    if args.clear_cache:
        del sample
        torch.cuda.empty_cache()

    # 4. Configurar Bucle
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    mse_fn = nn.MSELoss()
    l1_fn = nn.L1Loss()
    scaler = GradScaler()
    
    epochs = 100
    print("-" * 60)
    print(f"{'Epoch':<10} | {'MSE Loss':<12} | {'MAE':<12} | {'Exact Acc (%)':<15}")
    print("-" * 60)
    
    log_file_path = os.path.join(output_dir, "training_log.txt")
    with open(log_file_path, "w") as log_file:
        log_file.write("Epoch,MSE,MAE,Exact_Acc\n")
        
        for epoch in range(epochs):
            avg_mse, avg_mae, avg_acc = train_loop(model, loader, optimizer, mse_fn, l1_fn, device, scaler, args.clear_cache)
            
            log_str = f"Epoch {epoch+1:<6} | {avg_mse:<12.4f} | {avg_mae:<12.4f} | {avg_acc * 100:<13.2f}%"
            print(log_str)
            
            log_file.write(f"{epoch+1},{avg_mse},{avg_mae},{avg_acc*100}\n")
            log_file.flush() # Fuerza a escribir en disco inmediatamente
            
            if (epoch + 1) % 10 == 0:
                torch.save(model.state_dict(), os.path.join(output_dir, f"neural_diving_epoch_{epoch+1}.pt"))
    
    torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_final.pt"))
    print(f"\n¡Entrenamiento finalizado! Resultados guardados en: {output_dir}")

if __name__ == "__main__":
    main()