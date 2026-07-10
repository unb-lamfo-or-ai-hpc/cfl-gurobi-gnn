"""
Data X-Ray: Diagnóstico Profundo de Tensores y Parquets
=======================================================
Inspecciona un archivo .pt generado para buscar anomalías en las dimensiones
(broadcasting errors), distribuciones de etiquetas y límites de LP.
También cruza los datos con los parquets de metadatos y soluciones.
"""

import os
import torch
import pandas as pd
import numpy as np

def x_ray_pt_file(pt_path):
    print(f"\n{'='*60}")
    print(f" 1. RADIOGRAFÍA DEL GRAFO (.pt)")
    print(f" Archivo: {pt_path}")
    print(f"{'='*60}")
    
    if not os.path.exists(pt_path):
        print(f"[ERROR] No se encontró el archivo: {pt_path}")
        return None

    # Cargar el grafo
    data = torch.load(pt_path, map_location='cpu', weights_only=False)
    
    # 1.1 Metadatos Generales
    print("\n--- ATRIBUTOS A NIVEL DE GRAFO ---")
    for key in data.keys():
        if key not in ['variable', 'constraint'] and not isinstance(key, tuple):
            val = getattr(data, key, "N/A")
            print(f" -> {key}: {val}")

    # 1.2 Análisis del Tensor 'x' (Características)
    var_x = data['variable'].x
    print("\n--- TENSOR DE CARACTERÍSTICAS (variable.x) ---")
    print(f" -> Shape: {var_x.shape}")
    
    if var_x.shape[1] >= 7:
        print(" -> Desglose por columnas:")
        print(f"    Col 0 (Obj Coef) : Min={var_x[:, 0].min():.4f}, Max={var_x[:, 0].max():.4f}")
        print(f"    Col 1 (LB log)   : Min={var_x[:, 1].min():.4f}, Max={var_x[:, 1].max():.4f}")
        print(f"    Col 2 (UB log)   : Min={var_x[:, 2].min():.4f}, Max={var_x[:, 2].max():.4f}")
        print(f"    Col 3 (Is Cont)  : 1.0s = {(var_x[:, 3] == 1.0).sum().item()}")
        print(f"    Col 4 (Is Bin)   : 1.0s = {(var_x[:, 4] == 1.0).sum().item()}")
        print(f"    Col 5 (Is Int)   : 1.0s = {(var_x[:, 5] == 1.0).sum().item()}")
        print(f"    Col 6 (LP raw)   : Min={var_x[:, 6].min():.4f}, Max={var_x[:, 6].max():.4f}")
        
        # Validación matemática de las cotas LP vs UB
        # Revertimos el logaritmo del UB (expm1) para compararlo con el LP crudo
        ub_raw = torch.expm1(var_x[:, 2])
        lp_raw = var_x[:, 6]
        violaciones = (lp_raw > ub_raw + 1e-4).sum().item()
        print(f"\n    [Validación de Cotas] LP > UB real: {violaciones} violaciones detectadas.")

    # 1.3 Análisis del Tensor 'y' (Etiquetas/Target)
    if 'y' in data['variable']:
        var_y = data['variable'].y
        print("\n--- TENSOR DE ETIQUETAS (variable.y) ---")
        print(f" -> Shape: {var_y.shape}")
        
        # Conteo exacto de valores para cazar el bug de "1 Billón de etiquetas"
        ceros = (var_y == 0.0).sum().item()
        unos = (var_y == 1.0).sum().item()
        fraccionales = var_y.numel() - ceros - unos
        
        print(f" -> Valores exactos a 0.0: {ceros}")
        print(f" -> Valores exactos a 1.0: {unos}")
        print(f" -> Valores fraccionales/otros: {fraccionales}")
        print(f" -> Valores NaN: {torch.isnan(var_y).sum().item()}")
    else:
        print("\n--- TENSOR DE ETIQUETAS (variable.y) NO ENCONTRADO ---")

    # 1.4 Análisis de Topología Bipartita
    edge_idx = data['variable', 'rev_coef', 'constraint'].edge_index
    print("\n--- TOPOLOGÍA DEL GRAFO ---")
    print(f" -> Restricciones (constraint.x shape): {data['constraint'].x.shape}")
    print(f" -> Aristas (edge_index shape): {edge_idx.shape}")
    
    return getattr(data, 'instance', None)  # Retornar el nombre de la instancia si existe


def x_ray_transformer_parquet(parquet_path):
    print(f"\n{'='*60}")
    print(f" 2. AUDITORÍA DEL METADATA ORIGINAL (transformer_v2.py)")
    print(f" Archivo: {parquet_path}")
    print(f"{'='*60}")
    
    if not os.path.exists(parquet_path):
        print(f"[ERROR] No se encontró el archivo: {parquet_path}")
        return
        
    df = pd.read_parquet(parquet_path)
    print(f" -> Total de instancias en el parquet: {len(df)}")
    print("\n -> Primeras 3 filas del metadata estructural:")
    print(df.head(3).to_string())
    
    print("\n -> Resumen estadístico:")
    print(df.describe().to_string())


def x_ray_incumbents_parquet(instance_dir):
    print(f"\n{'='*60}")
    print(f" 3. AUDITORÍA DEL POOL DE SOLUCIONES (Paso 1)")
    print(f" Directorio: {instance_dir}")
    print(f"{'='*60}")
    
    parquet_path = os.path.join(instance_dir, "incumbents.parquet")
    
    if not os.path.exists(parquet_path):
        print(f"[ERROR] No se encontró el archivo de soluciones: {parquet_path}")
        return
        
    df = pd.read_parquet(parquet_path)
    print(f" -> Total de soluciones incumbentes (filas): {len(df)}")
    
    if len(df) > 0:
        print("\n -> Detalles de las primeras 3 soluciones encontradas:")
        cols_to_show = ['node', 'objective', 'bound', 'mip_gap', 'time']
        print(df[cols_to_show].head(3).to_string())
        
        # Verificar la dimensión del vector de solución
        sol_vec_0 = df.iloc[0]['solution_vector']
        print(f"\n -> Dimensión del solution_vector (debería coincidir con NumVars): {len(sol_vec_0)}")
        print(f" -> Primeros 5 valores de Y en la solución 0: {sol_vec_0[:5]}")


def main():
    # === RUTAS A EVALUAR (Modifique según sea necesario) ===
    # Apuntamos a un grafo de la categoría "Easy" que sabemos que generó la alerta roja
    pt_file = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset/CFL_easy_instance/processed/data_0.pt"
    
    # Parquet generado por transformer_v2.py
    metadata_parquet = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/metadata/CFL_easy_instance_metadata.parquet"
    
    # === EJECUCIÓN ===
    instance_name = x_ray_pt_file(pt_file)
    x_ray_transformer_parquet(metadata_parquet)
    
    # Si el grafo guarda el nombre de la instancia, buscamos su pool de soluciones real
    if instance_name:
        # Asumimos la ruta del generador de datos v4/v5
        raw_instance_dir = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps/CFL_easy_instance/{instance_name}"
        x_ray_incumbents_parquet(raw_instance_dir)
    else:
        print("\n[AVISO] El archivo .pt no contiene el atributo 'instance' para buscar su pool original.")

if __name__ == "__main__":
    main()