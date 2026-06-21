# Archivo: test_pyg_dataset.py
import os, sys
import argparse
from torch.utils.data import ConcatDataset

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.graph_transform.milp_dataset import NeuralDivingDataset

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--categories', nargs='+', default=["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"])
    args = parser.parse_args()

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    print("=== Inicializando Dataset PyTorch Geometric ===")
    datasets = []
    
    for cat in args.categories:
        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)
        print(f"[{cat}]: {len(ds)} grafos cargados.")
        if len(ds) > 0:
            datasets.append(ds)
            
    if not datasets:
        print("\n[AVISO] No se encontraron archivos .pt en ninguna categoría.")
        return

    # MAGIA DE PYTORCH: Unir todos en un solo Dataset
    full_dataset = ConcatDataset(datasets)
    print(f"\nTotal de grafos listos para el entrenamiento: {len(full_dataset)}")
    
    print("\n--- Inspeccionando el Grafo 0 ---")
    grafo = full_dataset[0]
    print(grafo)
    print(f"\nShape de Variables (x): {grafo['variable'].x.shape}")
    print(f"Shape de Target (y): {grafo['variable'].y.shape}")

if __name__ == "__main__":
    main()