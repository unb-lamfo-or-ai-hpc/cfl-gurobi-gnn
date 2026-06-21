"""
Entrenamiento Serial (Single-GPU) con Split (Train/Val/Test).
Ensamblaje Modular de Datasets por Dificultad (OOD Generalization).
Formulación como Clasificación Binaria (Estilo Gasse et al.).
Evalúa el mejor modelo basado estrictamente en el Validation Loss.
"""
import sys
import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import random_split, ConcatDataset
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
        
        # 1. Identificamos variables discretas
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        is_discrete = is_bin | is_int

        # 2. Extraemos el LP (Columna 6)
        lp_values = batch['variable'].x[:, 6]
        
        # 3. MÁSCARA FRACCIONAL (Ignorar los 0.0 y 1.0 claros)
        is_fractional = (lp_values > 1e-4) & (lp_values < 1.0 - 1e-4)
        
        # 4. Combinamos: Solo discretas que el solver dejó ambiguas
        target_mask = is_discrete & is_fractional
        
        if target_mask.sum() == 0: continue
        #if binary_mask.sum() == 0: continue
        valid_batches += 1

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

@torch.no_grad()
def eval_loop(model, loader, loss_fn, device, args):
    model.eval()
    total_loss, total_acc = 0.0, 0.0
    valid_batches = 0
    
    for batch in loader:
        batch = batch.to(device)
        
        # 1. Identificamos variables discretas
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        is_discrete = is_bin | is_int

        # 2. Extraemos el LP (Columna 6)
        lp_values = batch['variable'].x[:, 6]
        
        # 3. MÁSCARA FRACCIONAL
        is_fractional = (lp_values > 1e-4) & (lp_values < 1.0 - 1e-4)
        
        # 4. Combinamos
        target_mask = is_discrete & is_fractional
        
        if target_mask.sum() == 0: 
            continue
        #if binary_mask.sum() == 0: continue
        
        valid_batches += 1

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
    parser = argparse.ArgumentParser(description="Neural Diving GNN Training (Serial OOD Split)")
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--grad_clip', type=float, default=1.0)
    parser.add_argument('--clear_cache', action='store_true')
    
    # Parámetros modulares de partición: [Train, Validation, Test]
    parser.add_argument('--easy_split', type=int, nargs=3, default=[0,0,0], help="Cantidades Easy: Train Val Test")
    parser.add_argument('--medium_split', type=int, nargs=3, default=[0,0,0], help="Cantidades Medium: Train Val Test")
    parser.add_argument('--hard_split', type=int, nargs=3, default=[0,0,0], help="Cantidades Hard: Train Val Test")
    
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Entrenamiento Neural Diving (Serial Modular) en {device} ===")
    print(f"Parámetros: Hidden={args.hidden_dim} | LR={args.lr} | Clip={args.grad_clip}")
    print(f"Easy   (Train/Val/Test): {args.easy_split}")
    print(f"Medium (Train/Val/Test): {args.medium_split}")
    print(f"Hard   (Train/Val/Test): {args.hard_split}")

    output_dir = os.path.join(project_root, "data", "real_train_output")
    os.makedirs(output_dir, exist_ok=True)

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    # === ENSAMBLAJE MODULAR DEL DATASET ===
    config = {
        'CFL_easy_instance': args.easy_split,
        'CFL_medium_instance': args.medium_split,
        'CFL_hard_instance': args.hard_split
    }
    
    train_datasets, val_datasets, test_datasets = [], [], []
    generator = torch.Generator().manual_seed(42) # Semilla fija para consistencia
    
    for cat, (n_train, n_val, n_test) in config.items():
        total_req = n_train + n_val + n_test
        if total_req == 0: continue
            
        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)
        
        if len(ds) < total_req:
            print(f"\n[ERROR] '{cat}' solo tiene {len(ds)} grafos listos, pero pediste {total_req}.")
            sys.exit(1)
            
        unused = len(ds) - total_req
        ds_train, ds_val, ds_test, _ = random_split(ds, [n_train, n_val, n_test, unused], generator=generator)
        
        if n_train > 0: train_datasets.append(ds_train)
        if n_val > 0: val_datasets.append(ds_val)
        if n_test > 0: test_datasets.append(ds_test)
        
    train_data = ConcatDataset(train_datasets) if train_datasets else None
    val_data = ConcatDataset(val_datasets) if val_datasets else None
    test_data = ConcatDataset(test_datasets) if test_datasets else None
    
    if not train_data:
        print("\n[ERROR] El conjunto de entrenamiento está vacío. Ajusta los parámetros.")
        sys.exit(1)

    # Loaders Seriales (Sin DistributedSampler)
    train_loader = DataLoader(train_data, batch_size=1, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=1, shuffle=False) if val_data else None
    test_loader = DataLoader(test_data, batch_size=1, shuffle=False) if test_data else None

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
    
    log_file_path = os.path.join(output_dir, "training_log_serial.txt")

    with open(log_file_path, "w") as log_file:
        log_file.write("Epoch,Train_Loss,Val_Loss,Val_Accuracy\n")
        
        for epoch in range(epochs):
            train_loss, _ = train_loop(model, train_loader, optimizer, loss_fn, device, args)
            
            if val_data:
                val_loss, val_acc = eval_loop(model, val_loader, loss_fn, device, args)
            else:
                val_loss, val_acc = float('inf'), 0.0
            
            hist_train_loss.append(train_loss)
            hist_val_loss.append(val_loss if val_data else train_loss)
            
            log_str = f"Epoch {epoch+1:<6} | {train_loss:<12.4f} | {val_loss:<12.4f} | {val_acc * 100:<10.2f}%"
            
            if val_loss < best_val_loss and val_data:
                best_val_loss = val_loss
                torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_best_serial.pt"))
                log_str += "  --> ¡Mejor Val Loss guardado!"
                
            print(log_str)
            log_file.write(f"{epoch+1},{train_loss},{val_loss},{val_acc*100}\n")
            log_file.flush()
            
            # Live-Plotting
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.set_xlabel('Epochs')
            ax.set_ylabel('BCE Loss')
            ax.plot(range(1, len(hist_train_loss) + 1), hist_train_loss, color='tab:red', label='Train Loss')
            if val_data:
                ax.plot(range(1, len(hist_val_loss) + 1), hist_val_loss, color='tab:orange', linestyle='dashed', label='Validation Loss')
            ax.legend()
            plt.title('Curva de Aprendizaje - Neural Diving (Serial)')
            fig.tight_layout()
            plt.savefig(os.path.join(output_dir, "loss_curve_split_serial.png"))
            plt.close(fig)
    
    torch.save(model.state_dict(), os.path.join(output_dir, "neural_diving_final_serial.pt"))

    # Evaluación Final en Test Set
    if test_data:
        print("\n=== Evaluación Final en Test Set ===")
        best_model_path = os.path.join(output_dir, "neural_diving_best_serial.pt")
        if os.path.exists(best_model_path):
            model.load_state_dict(torch.load(best_model_path, map_location=device))
            
        test_loss, test_acc = eval_loop(model, test_loader, loss_fn, device, args)
        print(f"Test Loss: {test_loss:.4f} | Test Accuracy: {test_acc * 100:.2f}%")

    print(f"\n¡Entrenamiento Serial finalizado! Gráfica en: {output_dir}")

if __name__ == "__main__":
    main()