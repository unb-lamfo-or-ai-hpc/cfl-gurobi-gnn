import os
import glob
import gzip
import pickle
import argparse
import re
import numpy as np
import scipy.sparse as sp
import torch
from torch_geometric.data import HeteroData
from tqdm import tqdm

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

@dataclass
class ModelFeatures:
    num_vars: int
    num_constrs: int
    num_binary: int
    num_integer: int
    num_continuous: int
    num_nonzeros: int
    var_types: np.ndarray
    var_obj_coeffs: np.ndarray
    var_lb: np.ndarray
    var_ub: np.ndarray
    var_names: List[str]
    constr_senses: np.ndarray
    constr_rhs: np.ndarray
    constr_names: List[str]
    constraint_matrix: Dict[str, np.ndarray]
    
    def to_dict(self):
        return {k: v.tolist() if isinstance(v, np.ndarray) else v 
                for k, v in asdict(self).items() if k != 'constraint_matrix'}

@dataclass
class SolutionFeatures:
    objective_value: float
    mip_gap: float
    node_count: int
    solution_time: float
    solution_vector: np.ndarray
    is_feasible: bool
    is_optimal: bool
    integrality_gap: Optional[float] = None
    bound: Optional[float] = None

def sanitize_array(arr, name="Feature", apply_log_scale=True, max_val=1e6):
    arr = np.array(arr, dtype=np.float64) 
    arr = np.clip(arr, -max_val, max_val)
    if np.isnan(arr).any():
        arr = np.nan_to_num(arr, nan=0.0)
    if apply_log_scale:
        arr = np.sign(arr) * np.log1p(np.abs(arr))
    return arr.astype(np.float32)

def calculate_cosine_similarity(constraint_matrix, obj_coeffs):
    num_constrs = np.max(constraint_matrix['row']) + 1
    num_vars = len(obj_coeffs)
    A = sp.csr_matrix((constraint_matrix['data'], 
                       (constraint_matrix['row'], constraint_matrix['col'])), 
                      shape=(num_constrs, num_vars))
    dot_product = A.dot(obj_coeffs)
    norm_c = np.linalg.norm(obj_coeffs)
    norm_A = np.sqrt(np.array(A.power(2).sum(axis=1)).flatten())
    denom = norm_A * norm_c
    denom[denom == 0] = 1.0  
    cos_sim = dot_product / denom
    return np.nan_to_num(cos_sim, nan=0.0)

def process_instance_to_pyg(instance_dir, output_file):
    features_path = os.path.join(instance_dir, "original_features.pickle.gz")
    solutions_path = os.path.join(instance_dir, "solutions.pickle.gz")
    
    if not os.path.exists(features_path) or not os.path.exists(solutions_path):
        return False
        
    with gzip.open(features_path, 'rb') as f:
        feat_dict = pickle.load(f)['model_features']
    with gzip.open(solutions_path, 'rb') as f:
        sol_dict = pickle.load(f)
        
    if not sol_dict.get('final_solution'): return False
    if not sol_dict.get('node_relaxations'): return False

    target_vector = np.array(sol_dict['final_solution'].solution_vector)
    target_clean = sanitize_array(target_vector, "Target", apply_log_scale=False)
    
    lp_vector = np.array(sol_dict['node_relaxations'][0]['relaxation_vector'])
    lp_clean = sanitize_array(lp_vector, "LP_Vector", apply_log_scale=True)
    
    data = HeteroData()
    
    var_types = np.array(feat_dict.var_types)
    is_cont = sanitize_array((var_types == 'C').astype(float), apply_log_scale=False)
    is_bin = sanitize_array((var_types == 'B').astype(float), apply_log_scale=False)
    is_int = sanitize_array((var_types == 'I').astype(float), apply_log_scale=False)

    obj_coeffs = sanitize_array(feat_dict.var_obj_coeffs, "Obj_Coeffs", apply_log_scale=True)
    lb = sanitize_array(feat_dict.var_lb, "LB", apply_log_scale=True)
    ub = sanitize_array(feat_dict.var_ub, "UB", apply_log_scale=True)
    
    var_features = np.column_stack([obj_coeffs, lb, ub, is_bin, is_int, is_cont, lp_clean])
    data['variable'].x = torch.tensor(var_features, dtype=torch.float32)
    data['variable'].y = torch.tensor(target_clean, dtype=torch.float32) 
    
    senses = np.array(feat_dict.constr_senses)
    is_less = sanitize_array((senses == '<').astype(float), apply_log_scale=False)
    is_eq = sanitize_array((senses == '=').astype(float), apply_log_scale=False)
    is_greater = sanitize_array((senses == '>').astype(float), apply_log_scale=False)
    
    rhs = sanitize_array(feat_dict.constr_rhs, "RHS", apply_log_scale=True)
    cos_sim = calculate_cosine_similarity(feat_dict.constraint_matrix, feat_dict.var_obj_coeffs)
    cos_sim = sanitize_array(cos_sim, "Cos_Sim", apply_log_scale=False)

    constr_features = np.column_stack([rhs, is_less, is_eq, is_greater, cos_sim])
    data['constraint'].x = torch.tensor(constr_features, dtype=torch.float32)
    
    row = torch.tensor(feat_dict.constraint_matrix['row'], dtype=torch.long)
    col = torch.tensor(feat_dict.constraint_matrix['col'], dtype=torch.long)

    edge_clean = sanitize_array(feat_dict.constraint_matrix['data'], "Edge_Weights", apply_log_scale=True)
    edge_attr = torch.tensor(edge_clean, dtype=torch.float32).unsqueeze(-1)

    data['constraint', 'coef', 'variable'].edge_index = torch.stack([row, col], dim=0)
    data['constraint', 'coef', 'variable'].edge_attr = edge_attr
    
    data['variable', 'rev_coef', 'constraint'].edge_index = torch.stack([col, row], dim=0)
    data['variable', 'rev_coef', 'constraint'].edge_attr = edge_attr

    torch.save(data, output_file)
    return True

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--categories', nargs='+', default=["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"])
    parser.add_argument('--num_instances', type=int, default=30, help="Instancias máximas a procesar por categoría")
    args = parser.parse_args()

    input_base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps"
    output_base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    all_raw_dirs = [d for d in glob.glob(os.path.join(input_base_dir, "*")) if os.path.isdir(d)]

    for category in args.categories:
        print(f"\n=== Procesando Categoría: {category} ===")
        category_out_dir = os.path.join(output_base_dir, category, "processed")
        os.makedirs(category_out_dir, exist_ok=True)
        
        # Filtrar solo las carpetas que pertenecen a esta categoría
        category_dirs = [d for d in all_raw_dirs if category in os.path.basename(d)]
        category_dirs.sort(key=natural_sort_key)
        
        # Cortar a la cantidad solicitada
        selected_dirs = category_dirs[:args.num_instances]
        print(f"Encontradas {len(category_dirs)} instancias. Generando {len(selected_dirs)} grafos...")
        
        success_count = 0
        for i, instance_dir in enumerate(tqdm(selected_dirs)):
            output_file = os.path.join(category_out_dir, f"data_{i}.pt")
            if process_instance_to_pyg(instance_dir, output_file):
                success_count += 1

        print(f"¡Éxito! {success_count} grafos guardados en: {category_out_dir}")

if __name__ == "__main__":
    main()