import sys
import os
import torch
import torch.nn as nn
from torch_geometric.loader import DataLoader

# Asegurar que importamos desde su proyecto
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models import GasseGNN
from src.data_transformation.milp_dataset import NeuralDivingDataset

def train_loop(model, loader, optimizer, loss_fn, device):
    model.train()
    total_loss = 0
    
    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        
        # En nuestro dataset real, la dimensión 3 y 4 (índices 3 y 4) 
        # corresponden a is_bin e is_int respectivamente.
        # Creamos la máscara para predecir solo sobre variables discretas
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        binary_mask = is_bin | is_int
        
        # Forward pass (Note la estructura de llamadas que espera GasseGNN)
        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['constraint', 'coef', 'variable'].edge_index,
            binary_mask=binary_mask,
            edge_attr=batch['constraint', 'coef', 'variable'].edge_attr
        )
        
        # Calculamos la pérdida solo sobre las variables discretas (Neural Diving)
        targets = batch['variable'].y[binary_mask]
        
        loss = loss_fn(preds, targets)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        
    return total_loss / len(loader)

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Iniciando Entrenamiento Neural Diving en {device} ===")

    # 1. Cargar el Dataset Real
    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    dataset = NeuralDivingDataset(root=dataset_root)
    
    # BATCH SIZE = 1 es crítico para grafos de 5 millones de nodos
    loader = DataLoader(dataset, batch_size=1, shuffle=True)
    
    print(f"Dataset cargado con {len(dataset)} instancias masivas.")

    # 2. Inicializar Modelo con las dimensiones reales V3
    model = GasseGNN(
        var_in_dim=7,     # [obj_coeff, lb, ub, is_bin, is_int, is_cont, lp_value]
        cons_in_dim=5,    # [rhs, is_less, is_equal, is_greater, cosine_sim]
        edge_dim=1,       # [coeficiente_matriz]
        hidden_dim=64,
        num_layers=2
    ).to(device)
    
    # 3. Fit Prenorm (Requerido por la arquitectura de Gasse)
    print("Ajustando capas Prenorm con la primera instancia...")
    sample = next(iter(loader)).to(device)
    model.fit_prenorm(
        x_var=sample['variable'].x,
        x_cons=sample['constraint'].x,
        edge_v2c=sample['constraint', 'coef', 'variable'].edge_index,
        edge_attr=sample['constraint', 'coef', 'variable'].edge_attr
    )

    # 4. Configurar Entrenamiento (Regresión)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()  # Error Cuadrático Medio para adivinar los valores
    
    # Bucle de entrenamiento básico
    epochs = 10
    for epoch in range(epochs):
        loss = train_loop(model, loader, optimizer, loss_fn, device)
        print(f"Epoch {epoch+1:03d} | MSE Loss: {loss:.4f}")

if __name__ == "__main__":
    main()