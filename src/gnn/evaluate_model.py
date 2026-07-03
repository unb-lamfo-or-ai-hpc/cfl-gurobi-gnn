"""
Paso 3: Evaluación Académica de la GNN (Test Set)
=================================================
Carga el modelo entrenado y el Test Set para generar artefactos 
visuales (Matriz de Confusión, ROC-AUC) y métricas formales 
(Precision, Recall, F1-Score) listos para publicación.
"""

"""
Al ejecutar sbatch submit_step3_evaluation.sbs, se generarán los siguientes archivos en la carpeta /data/analysis/:

classification_report.csv: Tabla tabulada ideal para insertar en LaTeX/Word que muestra la Precision, el Recall y el F1-Score.

confusion_matrix.png: Un mapa de calor (Heatmap) en tonos azules, con números grandes y etiquetas claras, listo para el documento.

roc_auc_curve.png: evaluar problemas desbalanceados con un número (el AUC) que indica la capacidad general de la red neuronal para separar las decisiones correctas de las incorrectas, independientemente de si hay más ceros que unos.
"""

import os
import sys
import argparse
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc
from torch.utils.data import random_split, ConcatDataset
from torch_geometric.loader import DataLoader

import random

def set_global_seed(seed=42):
    """Fija todas las semillas estocásticas para garantizar reproducibilidad."""
    # 1. Semillas de Python estándar
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    
    # 2. Semillas de Numpy
    np.random.seed(seed)
    
    # 3. Semillas de PyTorch (CPU y GPU)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    
    # 4. Forzar determinismo en algoritmos de CuDNN (Opcional pero recomendado)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# --- LLAMADA AL INICIO DEL SCRIPT ---
set_global_seed(42)

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN
from src.graph_transform.milp_dataset import NeuralDivingDataset

@torch.no_grad()
def collect_predictions(model, loader, device):
    """Ejecuta inferencia y recolecta las predicciones y etiquetas reales."""
    model.eval()
    all_targets = []
    all_probs = []
    
    for batch in loader:
        batch = batch.to(device)
        
        is_bin = batch['variable'].x[:, 3] == 1.0
        is_int = batch['variable'].x[:, 4] == 1.0
        target_mask = is_bin | is_int
        
        if target_mask.sum() == 0: 
            continue

        logits = model(
            x_var=batch['variable'].x,
            x_cons=batch['constraint'].x,
            edge_v2c=batch['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=target_mask,
            edge_attr=batch['variable', 'rev_coef', 'constraint'].edge_attr
        )
        
        probs = torch.sigmoid(logits).cpu().numpy()
        targets = torch.clamp(batch['variable'].y[target_mask], min=0.0, max=1.0).cpu().numpy()
        
        all_probs.extend(probs)
        all_targets.extend(targets)
        
    return np.array(all_targets), np.array(all_probs)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_path', type=str, required=True)
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--easy_split', type=int, nargs=3, default=[0,0,0])
    parser.add_argument('--medium_split', type=int, nargs=3, default=[0,0,0])
    parser.add_argument('--hard_split', type=int, nargs=3, default=[0,0,0])
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Evaluación Académica Neural Diving en {device} ===")

    output_dir = os.path.join(project_root, "data", "analysis")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Cargar Datos de Test
    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    config = {
        'CFL_easy_instance': args.easy_split,
        'CFL_medium_instance': args.medium_split,
        'CFL_hard_instance': args.hard_split
    }
    
    test_datasets = []
    generator = torch.Generator().manual_seed(42) # Misma semilla del entrenamiento
    
    for cat, splits in config.items():
        n_train, n_val, n_test = splits
        total_req = n_train + n_val + n_test
        if n_test == 0: continue
            
        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)
        unused = len(ds) - total_req
        _, _, ds_test, _ = random_split(ds, [n_train, n_val, n_test, unused], generator=generator)
        test_datasets.append(ds_test)
        
    if not test_datasets:
        print("[Error] No se configuraron grafos para Test.")
        return
        
    test_data = ConcatDataset(test_datasets)
    test_loader = DataLoader(test_data, batch_size=1, shuffle=False)
    
    # 2. Cargar Modelo
    print(f"Cargando modelo: {os.path.basename(args.model_path)}")
    model = GasseGNN(var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2)
    model.load_state_dict(torch.load(args.model_path, map_location=device))
    model.to(device)

    # 3. Recolectar Predicciones
    print(f"Evaluando {len(test_data)} grafos de Test...")
    y_true, y_probs = collect_predictions(model, test_loader, device)
    y_pred = (y_probs > 0.5).astype(int)

    # --- ARTEFACTOS PARA EL REPORTE ---
    
    # A. Reporte de Clasificación (Texto/CSV)
    print("\nGenerando Reporte de Clasificación...")
    report_dict = classification_report(y_true, y_pred, target_names=['Cerrar (0)', 'Abrir (1)'], output_dict=True)
    report_df = pd.DataFrame(report_dict).transpose()
    report_df.to_csv(os.path.join(output_dir, "classification_report.csv"))
    print(report_df)

    # B. Matriz de Confusión (Gráfico)
    print("Generando Matriz de Confusión (Heatmap)...")
    cm = confusion_matrix(y_true, y_pred)
    
    plt.figure(figsize=(7, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False,
                xticklabels=['Predicción: Cerrar', 'Predicción: Abrir'],
                yticklabels=['Real: Cerrar', 'Real: Abrir'],
                annot_kws={"size": 14})
    plt.title('Matriz de Confusión (Test Set)', fontsize=16, pad=15)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "confusion_matrix.png"), dpi=300)
    plt.close()

    # C. Curva ROC y AUC (Gráfico)
    print("Generando Curva ROC-AUC...")
    fpr, tpr, _ = roc_curve(y_true, y_probs)
    roc_auc = auc(fpr, tpr)

    plt.figure(figsize=(7, 5))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('Tasa de Falsos Positivos (FPR)')
    plt.ylabel('Tasa de Verdaderos Positivos (TPR)')
    plt.title('Curva ROC - Neural Diving', fontsize=16)
    plt.legend(loc="lower right", fontsize=12)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "roc_auc_curve.png"), dpi=300)
    plt.close()

    print(f"\n=== Evaluación Finalizada. Artefactos en: {output_dir} ===")

if __name__ == "__main__":
    main()