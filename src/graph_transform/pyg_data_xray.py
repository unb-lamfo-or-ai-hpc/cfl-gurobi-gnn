"""
Data X-Ray: Diagnóstico Profundo de Tensores (PyG) y Trazabilidad
=================================================================
Inspecciona un archivo .pt generado para buscar anomalías en las dimensiones
(broadcasting errors), distribuciones de etiquetas y límites de LP.
También cruza los datos con el nuevo reporte de auditoría CSV de la Fase 1.
"""

import os
import torch
import pandas as pd
import numpy as np
import argparse

def inverse_log_scale(tensor: torch.Tensor) -> torch.Tensor:
    """Invierte la transformación log1p con signo."""
    return torch.sign(tensor) * (torch.exp(torch.abs(tensor)) - 1)

def x_ray_pt_file(pt_path):
    print(f"\n{'='*60}")
    print(f" 1. RADIOGRAFÍA DEL GRAFO PyG (.pt)")
    print(f" Archivo: {pt_path}")
    print(f"{'='*60}")
    
    if not os.path.exists(pt_path):
        print(f"[ERROR] No se encontró el archivo: {pt_path}")
        return None, None

    data = torch.load(pt_path, map_location='cpu', weights_only=False)
    
    # 1.1 Metadatos Generales
    print("\n--- ATRIBUTOS A NIVEL DE GRAFO ---")
    for key in data.keys():
        if key not in ['variable', 'constraint'] and not isinstance(key, tuple):
            val = getattr(data, key, "N/A")
            print(f" -> {key}: {val}")

    instance_name = getattr(data, 'instance_name', None)
    complexity_class = getattr(data, 'complexity_class', 'unknown')

    # 1.2 Análisis del Tensor 'x' (Características)
    var_x = data['variable'].x
    print("\n--- TENSOR DE CARACTERÍSTICAS (variable.x) ---")
    print(f" -> Shape: {var_x.shape}")
    
    if var_x.shape[1] >= 7:
        print(" -> Desglose por columnas:")
        print(f"    Col 0 (Obj Coef log) : Min={var_x[:, 0].min():.4f}, Max={var_x[:, 0].max():.4f}")
        print(f"    Col 1 (LB log)       : Min={var_x[:, 1].min():.4f}, Max={var_x[:, 1].max():.4f}")
        print(f"    Col 2 (UB log)       : Min={var_x[:, 2].min():.4f}, Max={var_x[:, 2].max():.4f}")
        print(f"    Col 3 (Is Cont)      : 1.0s = {(var_x[:, 3] == 1.0).sum().item()}")
        print(f"    Col 4 (Is Bin)       : 1.0s = {(var_x[:, 4] == 1.0).sum().item()}")
        print(f"    Col 5 (Is Int)       : 1.0s = {(var_x[:, 5] == 1.0).sum().item()}")
        print(f"    Col 6 (LP raw)       : Min={var_x[:, 6].min():.4f}, Max={var_x[:, 6].max():.4f}")
        
        # Validación de Cotas (Reverse log-scale for comparison)
        ub_raw = inverse_log_scale(var_x[:, 2])
        lp_raw = var_x[:, 6]
        violaciones = (lp_raw > ub_raw + 1e-4).sum().item()
        
        if violaciones > 0:
            print(f"\n    [RED ALERT] LP > UB real: {violaciones} violaciones de límites detectadas.")
        else:
            print(f"\n    [OK] Vector LP de relajación está estrictamente dentro de los límites UB.")

    # 1.3 Análisis del Tensor 'y' (Etiquetas/Target)
    if 'y' in data['variable']:
        var_y = data['variable'].y
        print("\n--- TENSOR DE ETIQUETAS (variable.y) ---")
        print(f" -> Shape: {var_y.shape}")
        
        ceros = (var_y == 0.0).sum().item()
        unos = (var_y == 1.0).sum().item()
        fraccionales = var_y.numel() - ceros - unos
        
        print(f" -> Valores a 0.0: {ceros}")
        print(f" -> Valores a 1.0: {unos}")
        print(f" -> Valores fraccionales: {fraccionales}")
        print(f" -> Valores NaN: {torch.isnan(var_y).sum().item()}")
    else:
        print("\n--- TENSOR DE ETIQUETAS (variable.y) NO ENCONTRADO ---")

    # 1.4 Análisis de Topología Bipartita
    edge_idx = data['variable', 'rev_coef', 'constraint'].edge_index
    print("\n--- TOPOLOGÍA DEL GRAFO ---")
    print(f" -> Restricciones (constraint.x shape): {data['constraint'].x.shape}")
    print(f" -> Aristas (edge_index shape): {edge_idx.shape}")
    
    return instance_name, complexity_class


def x_ray_audit_csv(csv_path, target_instance):
    print(f"\n{'='*60}")
    print(f" 2. AUDITORÍA DEL REPORTE FASE 1 (phase1_audit_report.csv)")
    print(f" Archivo: {csv_path}")
    print(f"{'='*60}")
    
    if not os.path.exists(csv_path):
        print(f"[WARN] No se encontró el reporte CSV en: {csv_path}")
        return
        
    df = pd.read_csv(csv_path)
    instance_data = df[df['instance'] == target_instance]
    
    if instance_data.empty:
        print(f"[WARN] La instancia {target_instance} no existe en el reporte CSV.")
    else:
        print(f" -> Registro encontrado para {target_instance}:")
        print(instance_data[['category', 'runtime_sec', 'n_incumbents', 'best_mip_gap_pct']].to_string(index=False))


def x_ray_incumbents_parquet(instance_dir):
    print(f"\n{'='*60}")
    print(f" 3. AUDITORÍA DEL POOL DE SOLUCIONES (Parquet Fase 1)")
    print(f" Directorio: {instance_dir}")
    print(f"{'='*60}")
    
    parquet_path = os.path.join(instance_dir, "incumbents.parquet")
    
    if not os.path.exists(parquet_path):
        print(f"[ERROR] No se encontró el archivo de soluciones: {parquet_path}")
        return
        
    df = pd.read_parquet(parquet_path)
    print(f" -> Total de soluciones almacenadas (filas): {len(df)}")
    
    if len(df) > 0:
        print("\n -> Resumen de las mejores 3 soluciones:")
        cols_to_show = ['node', 'objective', 'bound', 'mip_gap', 'time']
        print(df[cols_to_show].head(3).to_string())
        
        sol_vec_0 = df.iloc[0]['solution_vector']
        print(f"\n -> Dimensión del vector solución en disco: {len(sol_vec_0)}")


def main():
    parser = argparse.ArgumentParser(description="Data X-Ray for PyG Graphs")
    parser.add_argument('--category', type=str, default="CFL_medium_instance",
                        help='Category to inspect (e.g., CFL_medium_instance)')
    parser.add_argument('--data_idx', type=int, default=0,
                        help='Index of the data_X.pt file to inspect (default: 0)')
    args = parser.parse_args()

    pt_file = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset/{args.category}/processed/data_{args.data_idx}.pt"
    audit_csv = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis/phase1_audit_report_{args.category}.csv"
    
    instance_name, complexity = x_ray_pt_file(pt_file)
    
    if instance_name:
        x_ray_audit_csv(audit_csv, instance_name)
        
        # Rastrear hasta el directorio bruto
        raw_instance_dir = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps/{args.category}/{instance_name}"
        x_ray_incumbents_parquet(raw_instance_dir)
    else:
        print("\n[AVISO] El archivo .pt no se cargó correctamente o le faltan metadatos. Trazabilidad abortada.")

if __name__ == "__main__":
    main()