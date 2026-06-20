"""
Entrenamiento Serial (Single-GPU) con Diagnóstico de NaNs.
Formulación como Clasificación Binaria (Estilo Gasse et al. original).
Optimizado para ahorrar espacio en disco (Solo guarda el Mejor Modelo).
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
        
        if binary_mask.sum() == 0:
            print(f"  [AVISO] Batch {batch_idx}: No hay variables discretas. Saltando...")
            continue

        valid_batches += 1

        preds = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=binary_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        if torch.isnan(preds).any():
            print(f"\n[ERROR CRÍTICO] ¡NaN detectado en PREDICCIONES en el batch {batch_idx}!")
            sys.exit(1)
            
        targets = batch['variable'].y[binary_mask]
        targets = torch.clamp(targets, min=0.0, max=1.0)
        
        loss = loss_fn(preds, targets)
        
        if torch.isnan(loss):
            print(f"\n[ERROR CRÍTICO] ¡NaN detectado al calcular la PÉRDIDA en el batch {batch_idx}!")
            sys.exit(1)
        
        loss.backward()
        
        if args.grad_clip > 0.0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)
        
        optimizer.step()
        
        with torch.no_grad():
            predicted_classes = (preds > 0).float()
            acc = (predicted_classes == targets).float().mean()
            
            total_loss += loss.item()
            total_acc += acc.item()
            
        if args.clear_cache:
            del batch, preds, targets, loss
            torch.cuda.empty_cache()
            
    if valid_batches == 0: return 0.0, 0.0
    return total_loss / valid_batches, total_acc / valid_batches

def main():
    parser = argparse.ArgumentParser(description="Neural Diving GNN Training (Clasificación)")
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--grad_clip', type=float, default=1.0)
    parser.add_argument('--clear_cache', action='store_true')
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Entrenamiento Neural Diving (BCE & Accuracy) ===")
    print(f"Hardware  : {device}")
    print(f"Parámetros: Hidden={args.hidden_dim} | LR={args.lr} | Clip={args.grad_clip} | ClearCache={args.clear_cache}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    os.makedirs(output_dir, exist_ok=True)

    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    dataset = NeuralDivingDataset(root=dataset_root)
    
    loader = DataLoader(dataset, batch_size=1, shuffle=True)
    
    model = GasseGNN(
        var_in_dim=7,     
        cons_in_dim=5,    
        edge_dim=1,       
        hidden_dim=args.hidden_dim,
        num_layers=2
    ).to(device)
    
    print("Ajustando capas Prenorm...")
    # Bucle para encontrar el primer grafo válido para inicializar
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

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.BCEWithLogitsLoss()
    
    epochs = 100
    hist_loss, hist_acc = [], []
    best_acc = 0.0  # Rastreador del mejor modelo

    print("-" * 55)
    print(f"{'Epoch':<10} | {'BCE Loss':<15} | {'Accuracy (%)':<15}")
    print("-" * 55)
    
    log_file_path = os.path.join(output_dir, "training_log.txt")

    with open(log_file_path, "w") as log_file:
        log_file.write("Epoch,BCE_Loss,Accuracy\n")
        
        for epoch in range(epochs):
            avg_loss, avg_acc = train_loop(model, loader, optimizer, loss_fn, device, args)
            
            hist_loss.append(avg_loss)
            hist_acc.append(avg_acc * 100)
            
            log_str = f"Epoch {epoch+1:<6} | {avg_loss:<15.4f} | {avg_acc * 100:<13.2f}%"
            
            # Guardar SOLO si es el mejor modelo (Ahorra muchísimo disco)
            if avg_acc > best_acc and avg_acc > 0:
                best_acc = avg_acc
                torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_best.pt"))
                log_str += "  --> ¡Mejor modelo guardado!"
                
            print(log_str)
            
            log_file.write(f"{epoch+1},{avg_loss},{avg_acc*100}\n")
            log_file.flush()
    
    torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_final.pt"))

    # Dibujar el gráfico usando la memoria RAM (No necesita leer los archivos .pt)
    fig, ax1 = plt.subplots(figsize=(10, 6))
    color = 'tab:red'
    ax1.set_xlabel('Epochs')
    ax1.set_ylabel('BCE Loss', color=color)
    ax1.plot(range(1, epochs + 1), hist_loss, color=color, label='Loss')
    ax1.tick_params(axis='y', labelcolor=color)
    
    ax2 = ax1.twinx()
    color = 'tab:blue'
    ax2.set_ylabel('Accuracy (%)', color=color)
    ax2.plot(range(1, epochs + 1), hist_acc, color=color, label='Accuracy')
    ax2.tick_params(axis='y', labelcolor=color)
    
    plt.title('Convergencia Neural Diving (Clasificación)')
    fig.tight_layout()
    plt.savefig(os.path.join(output_dir, "loss_curve.png"))
    plt.close()

    print(f"\n¡Entrenamiento finalizado! Resultados guardados en: {output_dir}")

if __name__ == "__main__":
    main()