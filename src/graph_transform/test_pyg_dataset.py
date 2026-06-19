# Archivo: test_pyg.py
from milp_dataset import NeuralDivingDataset

def main():
    # ATENCIÓN: El root es la carpeta PADRE de 'processed'
    # PyG automáticamente le añade el '/processed' al final internamente.
    dataset_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    print("=== Inicializando Dataset PyTorch Geometric ===")
    ds = NeuralDivingDataset(root=dataset_root)
    
    print(f"Total de grafos encontrados: {len(ds)}")
    
    if len(ds) > 0:
        print("\n--- Inspeccionando el Grafo 0 ---")
        grafo = ds[0]
        print(grafo)
        
        # Validar las dimensiones que diseñamos (7 features para vars, 5 para cons)
        print(f"\nShape de Variables (x): {grafo['variable'].x.shape}")
        print(f"Shape de Target (y): {grafo['variable'].y.shape}")
        print(f"Shape de Restricciones (x): {grafo['constraint'].x.shape}")
        print(f"Shape de Aristas (edge_index): {grafo['constraint', 'coef', 'variable'].edge_index.shape}")
    else:
        print("\n[AVISO] No se encontraron archivos .pt en la carpeta processed.")

if __name__ == "__main__":
    main()