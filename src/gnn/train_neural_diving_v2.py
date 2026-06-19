import sys
import os
import torch
import torch.nn as nn
from torch_geometric.loader import DataLoader

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN
from src.data_transformation.milp_dataset import NeuralDivingDataset

def train_loop(model, loader, optimizer, mse_fn, l1_fn, device):
    model.train()
    
    total_mse = 0.0
    total_mae = 0.0
    total_exact_acc = 0.0
    
    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        binary_mask = is_bin | is_int
        
        # CORRECCIÓN DE CUDA: Usamos la arista de Variable -> Constraint
        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=binary_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        targets = batch['variable'].y[binary_mask]
        
        loss = mse_fn(preds, targets)
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
        
    num_batches = len(loader)
    return total_mse / num_batches, total_mae / num_batches, total_exact_acc / num_batches

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Iniciando Entrenamiento Neural Diving en {device} ===")

    # Preparar carpeta de outputs
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
        hidden_dim=64,
        num_layers=2
    ).to(device)
    
    print("Ajustando capas Prenorm...")
    sample = next(iter(loader)).to(device)
    
    # CORRECCIÓN DE CUDA: También aplicamos la arista inversa aquí
    model.fit_prenorm(
        x_var=sample['variable'].x,
        x_cons=sample['constraint'].x,
        edge_v2c=sample['variable', 'rev_coef', 'constraint'].edge_index,
        edge_attr=sample['variable', 'rev_coef', 'constraint'].edge_attr
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    mse_fn = nn.MSELoss()
    l1_fn = nn.L1Loss()
    
    epochs = 100
    print("-" * 60)
    print(f"{'Epoch':<10} | {'MSE Loss':<12} | {'MAE':<12} | {'Exact Acc (%)':<15}")
    print("-" * 60)
    
    # Archivo para guardar el historial de entrenamiento
    log_file_path = os.path.join(output_dir, "training_log.txt")
    with open(log_file_path, "w") as log_file:
        log_file.write("Epoch,MSE,MAE,Exact_Acc\n")
        
        for epoch in range(epochs):
            avg_mse, avg_mae, avg_acc = train_loop(model, loader, optimizer, mse_fn, l1_fn, device)
            
            log_str = f"Epoch {epoch+1:<6} | {avg_mse:<12.4f} | {avg_mae:<12.4f} | {avg_acc * 100:<13.2f}%"
            print(log_str)
            
            # Guardamos la época en el txt
            log_file.write(f"{epoch+1},{avg_mse},{avg_mae},{avg_acc*100}\n")
            
            # Guardamos los pesos del modelo cada 10 épocas
            if (epoch + 1) % 10 == 0:
                model_save_path = os.path.join(output_dir, f"neural_diving_epoch_{epoch+1}.pt")
                torch.save(model.state_dict(), model_save_path)
    
    # Guardamos el modelo final
    final_model_path = os.path.join(output_dir, "neural_diving_final.pt")
    torch.save(model.state_dict(), final_model_path)
    print(f"\n¡Entrenamiento finalizado! Resultados guardados en: {output_dir}")

if __name__ == "__main__":
    main()