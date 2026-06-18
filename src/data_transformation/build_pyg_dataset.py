import os
import glob
import gzip
import pickle
import numpy as np
import scipy.sparse as sp
import torch
from torch_geometric.data import HeteroData
from tqdm import tqdm

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
    if not sol_dict.get('final_solution') or not sol_dict.get('node_relaxations'):
        return False
        
    # El Target (Neural Diving): La mejor solución entera encontrada
    target_vector = np.array(sol_dict['final_solution']['solution_vector'])
    
    # El Feature Dinámico: La relajación continua (LP) en el nodo raíz (índice 0)
    lp_vector = np.array(sol_dict['node_relaxations'][0]['relaxation_vector'])
    
    data = HeteroData()
    
    # -----------------------------------------------------
    # 1. NODOS DE VARIABLES (7 Dimensiones)
    # [obj_coeff, lb, ub, is_binary, is_integer, is_continuous, lp_value]
    # -----------------------------------------------------
    var_types = np.array(feat_dict.var_types)
    is_cont = (var_types == 0).astype(float)
    is_bin = (var_types == 1).astype(float)
    is_int = (var_types == 2).astype(float)
    
    var_features = np.column_stack([
        feat_dict.var_obj_coeffs,
        feat_dict.var_lb,
        feat_dict.var_ub,
        is_bin,
        is_int,
        is_cont,
        lp_vector
    ])
    data['variable'].x = torch.tensor(var_features, dtype=torch.float32)
    data['variable'].y = torch.tensor(target_vector, dtype=torch.float32) # NUESTRO TARGET
    
    # -----------------------------------------------------
    # 2. NODOS DE RESTRICCIONES (5 Dimensiones)
    # [rhs, is_less, is_equal, is_greater, cosine_sim]
    # -----------------------------------------------------
    senses = np.array(feat_dict.constr_senses)
    is_less = (senses == '<').astype(float)
    is_eq = (senses == '=').astype(float)
    is_greater = (senses == '>').astype(float)
    cos_sim = calculate_cosine_similarity(feat_dict.constraint_matrix, feat_dict.var_obj_coeffs)
    
    constr_features = np.column_stack([
        feat_dict.constr_rhs,
        is_less,
        is_eq,
        is_greater,
        cos_sim
    ])
    data['constraint'].x = torch.tensor(constr_features, dtype=torch.float32)
    
    # -----------------------------------------------------
    # 3. ARISTAS BIPARTITAS (Matriz A)
    # -----------------------------------------------------
    row = torch.tensor(feat_dict.constraint_matrix['row'], dtype=torch.long)
    col = torch.tensor(feat_dict.constraint_matrix['col'], dtype=torch.long)
    edge_attr = torch.tensor(feat_dict.constraint_matrix['data'], dtype=torch.float32).unsqueeze(-1)
    
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
    input_base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/raw/MILPBench/CFL"
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