"""
Construcción de Grafos PyG (Multi-Task Learning)
================================================
Genera MÚLTIPLES grafos bipartitos por instancia MILP, uno por cada solución 
incumbente encontrada por Gurobi. 

Target a nivel de Nodo: El vector de solución de la incumbente.
Target a nivel de Grafo: MIP Gap, Tiempo de ejecución, e Is_Optimal.
"""

import os
import sys
import argparse
import glob
import pickle
import gzip
import numpy as np
import pandas as pd
import torch
from torch_geometric.data import HeteroData
from tqdm import tqdm

def sanitize_array(arr, name="Array", apply_log_scale=False):
    """
    Limpia los arrays para evitar NaNs e Infinitos.
    Si apply_log_scale es True, aplica una compresión logarítmica signada
    vital para coeficientes Big-M, pero destructiva para el LP vector.
    """
    arr = np.nan_to_num(arr, nan=0.0, posinf=60000.0, neginf=-60000.0)
    arr = np.clip(arr, -60000.0, 60000.0)
    
    if apply_log_scale:
        # Transformación: x = sign(x) * ln(1 + |x|)
        arr = np.sign(arr) * np.log1p(np.abs(arr))
        
    return torch.FloatTensor(arr).unsqueeze(-1)

def build_heterodata_for_instance(instance_dir, global_idx_start, processed_dir):
    """
    Lee los parquets de una instancia y genera un grafo PyG por cada incumbente.
    Retorna la cantidad de grafos generados exitosamente.
    """
    features_path = os.path.join(instance_dir, "original_features.pickle.gz")
    incumbents_path = os.path.join(instance_dir, "incumbents.parquet")
    relaxations_path = os.path.join(instance_dir, "node_relaxations.parquet")
    
    # 1. Verificamos que todos los archivos necesarios existan
    if not (os.path.exists(features_path) and os.path.exists(incumbents_path)):
        return 0
        
    try:
        # 2. Cargar Características del Modelo
        with gzip.open(features_path, 'rb') as f:
            data = pickle.load(f)
            model_features = data['model_features']
            
        # 3. Cargar Incumbentes y Relajaciones
        df_incumbents = pd.read_parquet(incumbents_path)
        
        # Extraer el LP vector del nodo raíz (o un vector de ceros si falla)
        lp_vector_root = np.zeros(model_features.num_vars)
        if os.path.exists(relaxations_path):
            df_relax = pd.read_parquet(relaxations_path)
            # Buscar el nodo 0 (Raíz)
            root_relax = df_relax[df_relax['node'] == 0]
            if not root_relax.empty:
                lp_vector_root = np.array(root_relax.iloc[0]['relaxation_vector'])
            elif not df_relax.empty:
                # Fallback: primera relajación disponible
                lp_vector_root = np.array(df_relax.iloc[0]['relaxation_vector'])

        # --- A. CONSTRUIR LA TOPOLOGÍA Y CARACTERÍSTICAS DE ENTRADA (X) ---
        # Estas características son idénticas para todos los grafos de esta instancia
        
        # A.1. Características de Variables (V)
        # Log-Scale SÍ
        obj_tensor = sanitize_array(model_features.var_obj_coeffs, apply_log_scale=True)
        lb_tensor = sanitize_array(model_features.var_lb, apply_log_scale=True)
        ub_tensor = sanitize_array(model_features.var_ub, apply_log_scale=True)
        
        # Log-Scale NO (¡El LP vector viaja puro!)
        lp_tensor = sanitize_array(lp_vector_root, apply_log_scale=False)
        
        # One-Hot Encoding de tipos de variables
        is_cont = torch.FloatTensor((model_features.var_types == 0).astype(float)).unsqueeze(-1)
        is_bin = torch.FloatTensor((model_features.var_types == 1).astype(float)).unsqueeze(-1)
        is_int = torch.FloatTensor((model_features.var_types == 2).astype(float)).unsqueeze(-1)
        
        # Dimensión V: [num_vars, 7]
        v_features = torch.cat([obj_tensor, lb_tensor, ub_tensor, is_cont, is_bin, is_int, lp_tensor], dim=1)
        
        # A.2. Características de Restricciones (C)
        # Log-Scale SÍ
        rhs_tensor = sanitize_array(model_features.constr_rhs, apply_log_scale=True)
        
        # One-Hot Senses (<, >, =)
        # En Gurobi: '<' es 60, '>' es 62, '=' es 61
        sense_less = torch.FloatTensor((model_features.constr_senses == 60).astype(float)).unsqueeze(-1)
        sense_equal = torch.FloatTensor((model_features.constr_senses == 61).astype(float)).unsqueeze(-1)
        sense_greater = torch.FloatTensor((model_features.constr_senses == 62).astype(float)).unsqueeze(-1)
        
        # Dummy feature extra para rellenar la dimensión 5 (opcional, como en el paper)
        c_dummy = torch.ones_like(rhs_tensor) 
        
        # Dimensión C: [num_constrs, 5]
        c_features = torch.cat([rhs_tensor, sense_less, sense_equal, sense_greater, c_dummy], dim=1)
        
        # A.3. Matriz Bipartita (Edges)
        rows = torch.LongTensor(model_features.constraint_matrix['row'])
        cols = torch.LongTensor(model_features.constraint_matrix['col'])
        # Log-Scale SÍ a los coeficientes de la matriz A
        edge_weight = sanitize_array(model_features.constraint_matrix['data'], apply_log_scale=True)
        
        # Bipartite Edge Indices
        edge_index_v2c = torch.stack([cols, rows], dim=0) # Variable -> Restricción
        edge_index_c2v = torch.stack([rows, cols], dim=0) # Restricción -> Variable

        # Creamos el grafo "Plantilla"
        template_data = HeteroData()
        template_data['variable'].x = v_features
        template_data['constraint'].x = c_features
        template_data['variable', 'rev_coef', 'constraint'].edge_index = edge_index_v2c
        template_data['variable', 'rev_coef', 'constraint'].edge_attr = edge_weight
        template_data['constraint', 'coef', 'variable'].edge_index = edge_index_c2v
        template_data['constraint', 'coef', 'variable'].edge_attr = edge_weight
        
        # --- B. MULTI-GRAFO: UN GRAFO POR INCUMBENTE ---
        graphs_generated = 0
        current_global_idx = global_idx_start
        
        for _, row in df_incumbents.iterrows():
            graph_data = template_data.clone()
            
            # Target (Y): El vector de solución
            sol_vector = np.array(row['solution_vector'])
            graph_data['variable'].y = torch.FloatTensor(sol_vector)
            
            # Multi-Task Labels a nivel de grafo
            graph_data.mip_gap = float(row['mip_gap'])
            graph_data.exec_time = float(row['time'])
            
            # Asumimos que un MIP gap menor al 0.01% es óptimo
            graph_data.is_optimal = bool(row['mip_gap'] <= 1e-4) 
            
            # Metadatos para trazabilidad
            graph_data.instance_name = os.path.basename(instance_dir)
            graph_data.incumbent_node = int(row['node'])
            
            # Guardamos el archivo .pt en el disco
            out_file = os.path.join(processed_dir, f"data_{current_global_idx}.pt")
            torch.save(graph_data, out_file)
            
            current_global_idx += 1
            graphs_generated += 1
            
        return graphs_generated
        
    except Exception as e:
        print(f"  [Error] Fallo en instancia {os.path.basename(instance_dir)}: {str(e)}")
        return 0

def main():
    parser = argparse.ArgumentParser(description="PyG Dataset Builder Multi-Task (Sin Log en LP)")
    parser.add_argument('--categories', nargs='+', default=["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"])
    args = parser.parse_args()

    base_raw_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps"
    base_pyg_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    print("=== Iniciando ETL Multi-Task (PyG) ===")
    
    for category in args.categories:
        cat_raw_dir = os.path.join(base_raw_dir, category)
        cat_pyg_dir = os.path.join(base_pyg_dir, category)
        processed_dir = os.path.join(cat_pyg_dir, "processed")
        
        os.makedirs(processed_dir, exist_ok=True)
        
        instance_dirs = glob.glob(os.path.join(cat_raw_dir, "*"))
        # Filtrar solo directorios
        instance_dirs = [d for d in instance_dirs if os.path.isdir(d)]
        
        print(f"\n=== Procesando Categoría: {category} ===")
        print(f"Encontradas {len(instance_dirs)} instancias. Extrayendo trayectoria de incumbentes...")
        
        global_graph_counter = 0
        
        # Limpiar el directorio processed antiguo si lo hubiera
        old_files = glob.glob(os.path.join(processed_dir, "data_*.pt"))
        for f in old_files:
            os.remove(f)
            
        for inst_dir in tqdm(instance_dirs):
            num_generated = build_heterodata_for_instance(inst_dir, global_graph_counter, processed_dir)
            global_graph_counter += num_generated
            
        print(f"¡Éxito! {global_graph_counter} grafos generados a partir de {len(instance_dirs)} instancias.")
        print(f"Guardados en: {processed_dir}")

if __name__ == "__main__":
    main()