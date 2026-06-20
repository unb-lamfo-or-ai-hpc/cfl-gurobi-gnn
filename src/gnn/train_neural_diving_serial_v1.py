"""
Entrenamiento Serial (Single-GPU) con Split (Train/Val/Test).
Formulación como Clasificación Binaria (Estilo Gasse et al.).
Evalúa el mejor modelo basado estrictamente en el Validation Loss.
"""
import sys
import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import random_split
from torch_geometric.loader import DataLoader
import matplotlib.pyplot as plt

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN
from src.graph_transform.milp_dataset import NeuralDivingDataset

def train_loop(model, loader, optimizer, loss_fn, device, args):
    model.train()
    total_loss, total_acc = 0.0, 0.0
    valid_batches = 0
    
    for batch_idx, batch in enumerate(loader):
        batch = batch.to(device)
        optimizer.zero_grad()
        
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        binary_mask = is_bin | is_int
        
        if binary_mask.sum() == 0: continue
        valid_batches += 1

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=binary_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
            
        targets = batch['variable'].y[binary_mask]
        targets = torch.clamp(targets, min=0.0, max=1.0)
        
        loss = loss_fn(preds, targets)
        loss.backward()
        
        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)
        
        optimizer.step()
        
        with torch.no_grad():
            acc = ((preds > 0).float() == targets).float().mean()
            total_loss += loss.item()
            total_acc += acc.item()
            
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    if valid_batches == 0: return float('inf'), 0.0
    return total_loss / valid_batches, total_acc / valid_batches

@torch.no_grad() # Crucial: Evita que la red aprenda durante la validación
def eval_loop(model, loader, loss_fn, device, args):
    model.eval()
    total_loss, total_acc = 0.0, 0.0
    valid_batches = 0
    
    for batch in loader:
        batch = batch.to(device)
        
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        binary_mask = is_bin | is_int
        
        if binary_mask.sum() == 0: continue
        valid_batches += 1

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
        total_loss += loss.item()
        total_acc += acc.item()
        
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    if valid_batches == 0: return float('inf'), 0.0
    return total_loss / valid_batches, total_acc / valid_batches

def main():
    parser = argparse.ArgumentParser(description="Neural Diving GNN Training con Split")
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--grad_clip', type=float, default=1.0)
    parser.add_argument('--clear_cache', action='store_true')
    
    # Nuevos hiperparámetros de partición
    parser.add_argument('--train_frac', type=float, default=0.8, help="Fracción para Entrenamiento")
    parser.add_argument('--val_frac', type=float, default=0.1, help="Fracción para Validación")
    parser.add_argument('--test_frac', type=float, default=0.1, help="Fracción para Testing")
    
    args = parser.parse_args()

    # Validar fracciones
    assert abs((args.train_frac + args.val_frac + args.test_frac) - 1.0) < 1e-5, "Las fracciones deben sumar 1.0"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Entrenamiento Neural Diving (Split Train/Val/Test) ===")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    os.makedirs(output_dir, exist_ok=True)

    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    full_dataset = NeuralDivingDataset(root=dataset_root)
    
    # Calcular tamaños absolutos
    dataset_size = len(full_dataset)
    train_size = int(args.train_frac * dataset_size)
    val_size = int(args.val_frac * dataset_size)
    test_size = dataset_size - train_size - val_size
    
    print(f"Dataset total: {dataset_size} grafos.")
    print(f"Split -> Train: {train_size} | Val: {val_size} | Test: {test_size}")
    
    # Partición aleatoria segura (fijar semilla manual si desea reproducibilidad)
    generator = torch.Generator().manual_seed(42)
    train_data, val_data, test_data = random_split(full_dataset, [train_size, val_size, test_size], generator=generator)
    
    train_loader = DataLoader(train_data, batch_size=1, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=1, shuffle=False)
    test_loader = DataLoader(test_data, batch_size=1, shuffle=False)

    model = GasseGNN(
        var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2
    ).to(device)
    
    print("Ajustando capas Prenorm (Solo usando datos de Entrenamiento)...")
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

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.BCEWithLogitsLoss()
    
    epochs = 100
    hist_train_loss, hist_val_loss = [], []
    best_val_loss = float('inf')

    print("-" * 75)
    print(f"{'Epoch':<8} | {'Train Loss':<12} | {'Val Loss':<12} | {'Val Acc (%)':<12}")
    print("-" * 75)
    
    log_file_path = os.path.join(output_dir, "training_log.txt")

    with open(log_file_path, "w") as log_file:
        log_file.write("Epoch,Train_Loss,Val_Loss,Val_Accuracy\n")
        
        for epoch in range(epochs):
            # Fase de Entrenamiento
            train_loss, _ = train_loop(model, train_loader, optimizer, loss_fn, device, args)
            
            # Fase de Validación (Si el set de validación no está vacío)
            if val_size > 0:
                val_loss, val_acc = eval_loop(model, val_loader, loss_fn, device, args)
            else:
                val_loss, val_acc = float('nan'), 0.0
            
            hist_train_loss.append(train_loss)
            hist_val_loss.append(val_loss)
            
            log_str = f"Epoch {epoch+1:<6} | {train_loss:<12.4f} | {val_loss:<12.4f} | {val_acc * 100:<10.2f}%"
            
            # Guardamos el modelo solo si mejora en DATOS NO VISTOS (Validation)
            if val_loss < best_val_loss and val_size > 0:
                best_val_loss = val_loss
                torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_best.pt"))
                log_str += "  --> ¡Mejor Val Loss guardado!"
                
            print(log_str)
            log_file.write(f"{epoch+1},{train_loss},{val_loss},{val_acc*100}\n")
            log_file.flush()
    
    # Evaluación Final en Test Set
    if test_size > 0:
        print("\n=== Evaluación Final en Test Set ===")
        # Cargamos el mejor modelo antes de testear
        model.load_state_dict(torch.load(os.path.join(output_dir, "neural_diving_best.pt")))
        test_loss, test_acc = eval_loop(model, test_loader, loss_fn, device, args)
        print(f"Test Loss: {test_loss:.4f} | Test Accuracy: {test_acc * 100:.2f}%")

    torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_final.pt"))

    # Dibujar gráfica doble (Train vs Validation)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlabel('Epochs')
    ax.set_ylabel('BCE Loss')
    ax.plot(range(1, epochs + 1), hist_train_loss, color='tab:red', label='Train Loss')
    if val_size > 0:
        ax.plot(range(1, epochs + 1), hist_val_loss, color='tab:orange', linestyle='dashed', label='Validation Loss')
    ax.legend()
    plt.title('Curva de Aprendizaje - Neural Diving')
    fig.tight_layout()
    plt.savefig(os.path.join(output_dir, "loss_curve_split.png"))
    plt.close()

if __name__ == "__main__":
    main()