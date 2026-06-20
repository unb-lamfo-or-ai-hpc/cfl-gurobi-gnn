import os
import glob
import gzip
import pickle
import numpy as np
import scipy.sparse as sp
import torch
from torch_geometric.data import HeteroData
from tqdm import tqdm

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

@dataclass
class ModelFeatures:
    """Features extracted from a Gurobi model"""
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
                for k, v in asdict(self).items() 
                if k != 'constraint_matrix'}

@dataclass
class SolutionFeatures:
    """Features from a solution (incumbent or relaxation)"""
    objective_value: float
    mip_gap: float
    node_count: int
    solution_time: float
    solution_vector: np.ndarray
    is_feasible: bool
    is_optimal: bool
    integrality_gap: Optional[float] = None
    bound: Optional[float] = None

# ==========================================
# MOTOR DE SANEAMIENTO Y NORMALIZACIÓN
# ==========================================
def sanitize_array(arr, name="Feature", apply_log_scale=True, max_val=1e6):
    """
    1. Limita los Infinitos de Gurobi.
    2. Imputa NaNs con 0.0.
    3. (Opcional) Aplica Log-Scaling para comprimir distribuciones extremas.
    """
    arr = np.array(arr, dtype=np.float64) # Usamos float64 para cálculos seguros
    
    # 1. Clipping (Recortar los Big-M o infinitos de Gurobi)
    arr = np.clip(arr, -max_val, max_val)
    
    # 2. Imputación de NaNs
    if np.isnan(arr).any():
        print(f"    [AVISO] NaNs detectados en {name}. Imputando con 0.0.")
        arr = np.nan_to_num(arr, nan=0.0)
        
    # 3. Log-Scaling: Preserva el signo, pero suaviza la magnitud
    if apply_log_scale:
        arr = np.sign(arr) * np.log1p(np.abs(arr))
        
    return arr.astype(np.float32)

def calculate_cosine_similarity(constraint_matrix, obj_coeffs):
    """Calcula la similitud coseno entre cada restricción y la función objetivo."""
    num_constrs = np.max(constraint_matrix['row']) + 1
    num_vars = len(obj_coeffs)
    
    # Construir matriz dispersa para cálculo ultra-rápido
    A = sp.csr_matrix((constraint_matrix['data'], 
                       (constraint_matrix['row'], constraint_matrix['col'])), 
                      shape=(num_constrs, num_vars))
    
    dot_product = A.dot(obj_coeffs)
    norm_c = np.linalg.norm(obj_coeffs)
    # Norma de cada fila (restricción)
    norm_A = np.sqrt(np.array(A.power(2).sum(axis=1)).flatten())
    
    denom = norm_A * norm_c
    denom[denom == 0] = 1.0  # Evitar división por cero
    
    return dot_product / denom

def process_instance_to_pyg(instance_dir, output_file):
    features_path = os.path.join(instance_dir, "original_features.pickle.gz")
    solutions_path = os.path.join(instance_dir, "solutions.pickle.gz")
    
    if not os.path.exists(features_path) or not os.path.exists(solutions_path):
        return False
        
    with gzip.open(features_path, 'rb') as f:
        feat_dict = pickle.load(f)['model_features']
        
    with gzip.open(solutions_path, 'rb') as f:
        sol_dict = pickle.load(f)
        
    # Validar que tengamos el Target (Solución final) y el Input Dinámico (Relajación LP)
    if not sol_dict.get('final_solution'):
        print(f"  [Skip] {os.path.basename(instance_dir)}: No encontró solución entera (Target faltante).")
        return False
        
    if not sol_dict.get('node_relaxations'):
        print(f"  [Skip] {os.path.basename(instance_dir)}: No hay relajaciones de nodos (Presolve bloqueó B&B).")
        return False

    # El Target (Neural Diving): La mejor solución entera encontrada
    #target_vector = np.array(sol_dict['final_solution']['solution_vector'])
    target_vector = np.array(sol_dict['final_solution'].solution_vector)
    target_clean = sanitize_array(target_vector, "Target", apply_log_scale=False)
    
    # El Feature Dinámico: La relajación continua (LP) en el nodo raíz (índice 0)
    lp_vector = np.array(sol_dict['node_relaxations'][0]['relaxation_vector'])
    lp_clean = sanitize_array(lp_vector, "LP_Vector", apply_log_scale=True)
    
    data = HeteroData()
    
    # -----------------------------------------------------
    # 1. NODOS DE VARIABLES (7 Dimensiones)
    # [obj_coeff, lb, ub, is_binary, is_integer, is_continuous, lp_value]
    # -----------------------------------------------------
    var_types = np.array(feat_dict.var_types)

    #is_cont = (var_types == 0).astype(float)
    #is_bin = (var_types == 1).astype(float)
    #is_int = (var_types == 2).astype(float)
    is_cont = sanitize_array((var_types == 'C').astype(float), apply_log_scale=False)
    is_bin = sanitize_array((var_types == 'B').astype(float), apply_log_scale=False)
    is_int = sanitize_array((var_types == 'I').astype(float), apply_log_scale=False)

    obj_coeffs = sanitize_array(feat_dict.var_obj_coeffs, "Obj_Coeffs", apply_log_scale=True)
    lb = sanitize_array(feat_dict.var_lb, "LB", apply_log_scale=True)
    ub = sanitize_array(feat_dict.var_ub, "UB", apply_log_scale=True)
    
    #var_features = np.column_stack([
    #    feat_dict.var_obj_coeffs,
    #    feat_dict.var_lb,
    #    feat_dict.var_ub,
    #    is_bin,
    #    is_int,
    #    is_cont,
    #    lp_vector
    #])

    var_features = np.column_stack([obj_coeffs, lb, ub, is_bin, is_int, is_cont, lp_clean])

    data['variable'].x = torch.tensor(var_features, dtype=torch.float32)
    data['variable'].y = torch.tensor(target_clean, dtype=torch.float32) # NUESTRO TARGET
    
    # -----------------------------------------------------
    # 2. NODOS DE RESTRICCIONES (5 Dimensiones)
    # [rhs, is_less, is_equal, is_greater, cosine_sim]
    # -----------------------------------------------------
    senses = np.array(feat_dict.constr_senses)
    #is_less = (senses == '<').astype(float)
    #is_eq = (senses == '=').astype(float)
    #is_greater = (senses == '>').astype(float)
    is_less = sanitize_array((senses == '<').astype(float), apply_log_scale=False)
    is_eq = sanitize_array((senses == '=').astype(float), apply_log_scale=False)
    is_greater = sanitize_array((senses == '>').astype(float), apply_log_scale=False)
    
    #cos_sim = calculate_cosine_similarity(feat_dict.constraint_matrix, feat_dict.var_obj_coeffs)
    rhs = sanitize_array(feat_dict.constr_rhs, "RHS", apply_log_scale=True)
    cos_sim = calculate_cosine_similarity(feat_dict.constraint_matrix, feat_dict.var_obj_coeffs)
    cos_sim = sanitize_array(cos_sim, "Cos_Sim", apply_log_scale=False)

    #constr_features = np.column_stack([
    #    feat_dict.constr_rhs,
    #    is_less,
    #    is_eq,
    #    is_greater,
    #    cos_sim
    #])
    constr_features = np.column_stack([rhs, is_less, is_eq, is_greater, cos_sim])

    data['constraint'].x = torch.tensor(constr_features, dtype=torch.float32)
    
    # -----------------------------------------------------
    # 3. ARISTAS BIPARTITAS (Matriz A)
    # -----------------------------------------------------
    row = torch.tensor(feat_dict.constraint_matrix['row'], dtype=torch.long)
    col = torch.tensor(feat_dict.constraint_matrix['col'], dtype=torch.long)

    #edge_attr = torch.tensor(feat_dict.constraint_matrix['data'], dtype=torch.float32).unsqueeze(-1)
    edge_raw = feat_dict.constraint_matrix['data']
    edge_clean = sanitize_array(edge_raw, "Edge_Weights", apply_log_scale=True)
    edge_attr = torch.tensor(edge_clean, dtype=torch.float32).unsqueeze(-1)

    # Conexión: Restricción -> Variable
    data['constraint', 'coef', 'variable'].edge_index = torch.stack([row, col], dim=0)
    data['constraint', 'coef', 'variable'].edge_attr = edge_attr
    
    # Conexión: Variable -> Restricción (Crucial para el Message Passing bidireccional)
    data['variable', 'rev_coef', 'constraint'].edge_index = torch.stack([col, row], dim=0)
    data['variable', 'rev_coef', 'constraint'].edge_attr = edge_attr

    # Guardar en disco (Cero consumo de RAM residual)
    torch.save(data, output_file)
    return True

if __name__ == "__main__":
    input_base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps"
    # PyG requiere que los archivos estén dentro de una subcarpeta llamada "processed"
    output_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset/processed"
    os.makedirs(output_dir, exist_ok=True)

    instance_dirs = [d for d in glob.glob(os.path.join(input_base_dir, "*")) if os.path.isdir(d)]
    print(f"Transformando {len(instance_dirs)} instancias a formato PyG nativo (Neural Diving)...")
    
    success_count = 0
    for i, instance_dir in enumerate(tqdm(instance_dirs)):
        output_file = os.path.join(output_dir, f"data_{i}.pt")
        if process_instance_to_pyg(instance_dir, output_file):
            success_count += 1

    print(f"¡Éxito! {success_count} grafos HeteroData guardados en {output_dir}")