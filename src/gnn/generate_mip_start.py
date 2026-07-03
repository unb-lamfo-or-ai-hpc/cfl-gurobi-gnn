"""
Paso 4: Inferencia CPU y Generación de Warm-Start (.mst)
========================================================
Lee un archivo .lp, ejecuta la inferencia de la GNN exclusivamente en CPU,
y exporta las predicciones de alta confianza como un archivo MIP Start (.mst)
para acelerar ejecuciones futuras de Gurobi.
"""

import os
import sys
import argparse
import time
import numpy as np
import torch
from torch_geometric.data import HeteroData
import gurobipy as gp
from gurobipy import GRB

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.gnn.models.gasse import GasseGNN

def sanitize_array(arr, apply_log_scale=False):
    arr = np.nan_to_num(arr, nan=0.0, posinf=60000.0, neginf=-60000.0)
    arr = np.clip(arr, -60000.0, 60000.0)
    if apply_log_scale:
        arr = np.sign(arr) * np.log1p(np.abs(arr))
    return torch.FloatTensor(arr).unsqueeze(-1)

def build_graph_from_gurobi(model_gp, lp_vector):
    vars = model_gp.getVars()
    constrs = model_gp.getConstrs()
    
    var_types = np.array([v.VType for v in vars])
    var_obj = np.array([v.Obj for v in vars])
    var_lb = np.array([v.LB for v in vars])
    var_ub = np.array([v.UB for v in vars])
    constr_senses = np.array([c.Sense for c in constrs])
    constr_rhs = np.array([c.RHS for c in constrs])
    
    rows, cols, vals = [], [], []
    for i, constr in enumerate(constrs):
        row = model_gp.getRow(constr)
        for j in range(row.size()):
            rows.append(i)
            cols.append(row.getVar(j).index)
            vals.append(row.getCoeff(j))
            
    obj_tensor = sanitize_array(var_obj, apply_log_scale=True)
    lb_tensor = sanitize_array(var_lb, apply_log_scale=True)
    ub_tensor = sanitize_array(var_ub, apply_log_scale=True)
    lp_tensor = sanitize_array(lp_vector, apply_log_scale=False)
    
    is_cont = torch.FloatTensor((var_types == GRB.CONTINUOUS).astype(float)).unsqueeze(-1)
    is_bin = torch.FloatTensor((var_types == GRB.BINARY).astype(float)).unsqueeze(-1)
    is_int = torch.FloatTensor((var_types == GRB.INTEGER).astype(float)).unsqueeze(-1)
    v_features = torch.cat([obj_tensor, lb_tensor, ub_tensor, is_cont, is_bin, is_int, lp_tensor], dim=1)
    
    rhs_tensor = sanitize_array(constr_rhs, apply_log_scale=True)
    sense_less = torch.FloatTensor((constr_senses == GRB.LESS_EQUAL).astype(float)).unsqueeze(-1)
    sense_equal = torch.FloatTensor((constr_senses == GRB.EQUAL).astype(float)).unsqueeze(-1)
    sense_greater = torch.FloatTensor((constr_senses == GRB.GREATER_EQUAL).astype(float)).unsqueeze(-1)
    c_dummy = torch.ones_like(rhs_tensor)
    c_features = torch.cat([rhs_tensor, sense_less, sense_equal, sense_greater, c_dummy], dim=1)
    
    edge_weight = sanitize_array(np.array(vals), apply_log_scale=True)
    rows_t = torch.LongTensor(rows)
    cols_t = torch.LongTensor(cols)
    edge_index_v2c = torch.stack([cols_t, rows_t], dim=0)
    edge_index_c2v = torch.stack([rows_t, cols_t], dim=0)
    
    data = HeteroData()
    data['variable'].x = v_features
    data['constraint'].x = c_features
    data['variable', 'rev_coef', 'constraint'].edge_index = edge_index_v2c
    data['variable', 'rev_coef', 'constraint'].edge_attr = edge_weight
    data['constraint', 'coef', 'variable'].edge_index = edge_index_c2v
    data['constraint', 'coef', 'variable'].edge_attr = edge_weight
    
    return data, [v.VarName for v in vars]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lp_file', type=str, required=True)
    parser.add_argument('--model_path', type=str, required=True)
    parser.add_argument('--hidden_dim', type=int, default=32)
    parser.add_argument('--confidence', type=float, default=0.90, 
                        help="Umbral de confianza para inyectar en MIP Start (0.0 a 1.0)")
    args = parser.parse_args()

    # Forzar ejecución en CPU para emular entorno final HPC
    device = torch.device("cpu")
    print(f"=== Generador de MIP Start (Inferencia en {device}) ===")
    
    # 1. Resolver Relajación Continua
    print("1. Calculando Relajación (LP) con Gurobi...")
    env = gp.Env(empty=True)
    env.setParam("LogToConsole", 0)
    env.start()
    
    model_gp = gp.read(args.lp_file, env=env)
    relaxed_model = model_gp.relax()
    relaxed_model.optimize()
    lp_vector = np.array([v.X for v in relaxed_model.getVars()])
    
    # 2. Construir Grafo
    print("2. Ensamblando el Grafo PyG...")
    graph, var_names = build_graph_from_gurobi(model_gp, lp_vector)
    
    # 3. Cargar Modelo en CPU
    print(f"3. Cargando pesos de la red en CPU...")
    gnn = GasseGNN(var_in_dim=7, cons_in_dim=5, edge_dim=1, hidden_dim=args.hidden_dim, num_layers=2)
    # map_location='cpu' es el puente crítico para cargar modelos entrenados en GPU
    gnn.load_state_dict(torch.load(args.model_path, map_location=device))
    gnn.eval()
    
    is_bin = graph['variable'].x[:, 3] == 1.0
    is_int = graph['variable'].x[:, 4] == 1.0
    target_mask = is_bin | is_int
    
    with torch.no_grad():
        logits = gnn(
            x_var=graph['variable'].x,
            x_cons=graph['constraint'].x,
            edge_v2c=graph['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask=target_mask,
            edge_attr=graph['variable', 'rev_coef', 'constraint'].edge_attr
        )
        probabilidades = torch.sigmoid(logits).numpy()
        
    # 4. Generación del Archivo .mst
    instance_name = os.path.basename(args.lp_file).replace('.lp.gz', '').replace('.lp', '')
    output_dir = os.path.join(project_root, "data", "mip_starts")
    os.makedirs(output_dir, exist_ok=True)
    mst_path = os.path.join(output_dir, f"{instance_name}_gnn_start.mst")
    
    indices_discretos = torch.where(target_mask)[0].numpy()
    
    lower_bound_threshold = 1.0 - args.confidence
    upper_bound_threshold = args.confidence
    
    vars_inyectadas = 0
    
    with open(mst_path, 'w') as f:
        for idx, prob in zip(indices_discretos, probabilidades):
            # Filtro de Alta Confianza (MIP Start Parcial)
            if prob >= upper_bound_threshold:
                f.write(f"{var_names[idx]} 1\n")
                vars_inyectadas += 1
            elif prob <= lower_bound_threshold:
                f.write(f"{var_names[idx]} 0\n")
                vars_inyectadas += 1

    print("\n" + "="*70)
    print(f" ARCHIVO MIP START GENERADO CON ÉXITO")
    print("="*70)
    print(f"Ruta: {mst_path}")
    print(f"Variables Discretas Totales: {len(probabilidades)}")
    print(f"Variables Inyectadas (Umbral > {args.confidence*100}%): {vars_inyectadas}")
    print("="*70)

if __name__ == "__main__":
    main()