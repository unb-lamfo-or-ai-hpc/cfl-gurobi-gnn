"""
Script de Auditoría para el Dataset PyG Multi-Tarea
===================================================
Verifica que los grafos se hayan generado correctamente con las 
nuevas etiquetas de incumbentes (MIP Gap, Tiempo, etc.) y que 
el vector LP no tenga la compresión logarítmica.
"""
import sys
import os
import argparse
import torch
from torch.utils.data import ConcatDataset

# Parche de Rutas para importar src
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.graph_transform.milp_dataset import NeuralDivingDataset

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--categories', nargs='+', default=["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"])
    args = parser.parse_args()

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    print("=== Iniciando Auditoría del Dataset PyG (Multi-Tarea) ===")
    datasets = []
    
    for cat in args.categories:
        cat_root = os.path.join(base_root, cat)
        ds = NeuralDivingDataset(root=cat_root)
        print(f"[{cat}]: {len(ds)} grafos de incumbentes cargados.")
        if len(ds) > 0:
            datasets.append(ds)
            
    if not datasets:
        print("\n[AVISO] No se encontraron archivos .pt. ¿Ya terminó el script de ETL?")
        return

    full_dataset = ConcatDataset(datasets)
    print(f"\nTotal de grafos (incumbentes) listos para entrenar: {len(full_dataset)}")
    
    print("\n--- Rayos X al Grafo 0 (Auditoría Multi-Tarea) ---")
    grafo = full_dataset[0]
    print(grafo)
    
    print("\n[Dimensiones]")
    print(f" -> Variables (Nodos V): {grafo['variable'].x.shape}")
    print(f" -> Restricciones (Nodos C): {grafo['constraint'].x.shape}")
    print(f" -> Aristas (V -> C): {grafo['variable', 'rev_coef', 'constraint'].edge_index.shape}")
    
    print("\n[Etiquetas Multi-Tarea (Targets)]")
    # Verificamos que las nuevas etiquetas existan
    try:
        print(f" -> Instancia Origen: {getattr(grafo, 'instance_name', 'Desconocida')}")
        print(f" -> Nodo del B&B: {getattr(grafo, 'incumbent_node', -1)}")
        print(f" -> MIP Gap: {grafo.mip_gap * 100:.4f}%")
        print(f" -> Tiempo de Ejecución: {grafo.exec_time:.2f} segundos")
        print(f" -> ¿Es la solución Óptima?: {grafo.is_optimal}")
        
        # Analizamos el balance de la solución (Target Y)
        num_unos = (grafo['variable'].y == 1).sum().item()
        num_ceros = (grafo['variable'].y == 0).sum().item()
        print(f" -> Balance del Target Y: {num_unos} variables abiertas (1) vs {num_ceros} cerradas (0)")
        
    except AttributeError as e:
        print(f" [ERROR] Faltan etiquetas Multi-Tarea: {e}")

    print("\n[Auditoría del Vector LP (Columna 6)]")
    # Extraemos la columna 6 (el LP) para verificar que no esté en Log-Scale
    lp_vector = grafo['variable'].x[:, 6]
    print(f" -> Valor Mínimo del LP: {lp_vector.min().item():.4f} (Debería ser >= 0.0)")
    print(f" -> Valor Máximo del LP: {lp_vector.max().item():.4f} (Debería ser <= 1.0)")
    
    # Contamos cuántas fracciones reales hay
    fracciones = ((lp_vector > 1e-4) & (lp_vector < 1.0 - 1e-4)).sum().item()
    print(f" -> Variables estrictamente fraccionales en la raíz: {fracciones}")
    if lp_vector.max().item() > 1.1:
        print(" [ALERTA ROJA] El LP Max es mayor a 1. ¡La compresión Log-Scale sigue activa!")
    else:
        print(" [ÉXITO] El LP Vector está puro y listo para la Máscara Fraccional.")

if __name__ == "__main__":
    main()