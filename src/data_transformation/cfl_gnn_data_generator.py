import os
import glob
import re
import argparse
import json
import pandas as pd
import numpy as np
import gurobipy as gp
from gurobipy import GRB
import torch
from torch_geometric.data import Data

# ==========================================
# 0. PARSER DE ARGUMENTOS DE LÍNEA DE COMANDOS
# ==========================================
parser = argparse.ArgumentParser(description="Pipeline de Extracción MILP/GNN con Control de Instancias.")
parser.add_argument('--categories', nargs='+', default=["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"],
                    help="Categorías a procesar (espacio separado). Ejemplo: --categories CFL_hard_instance")
parser.add_argument('--start_idx', type=int, default=0, help="Índice inicial del archivo a procesar (inclusive)")
parser.add_argument('--end_idx', type=int, default=30, help="Índice final del archivo a procesar (exclusive)")
parser.add_argument('--time_limit', type=int, default=60, help="Tiempo límite de Gurobi por instancia en segundos")

args = parser.parse_args()

# ==========================================
# 1. PARAMETRIZACIÓN DE DIRECTORIOS
# ==========================================

EXEC_DIR = "/raid/vrcelestino/data"
EXTRACT_DIR = os.path.expanduser("/home/vrcelestino/discodatos/cfl-gurobi-gnn/data/raw/MILPBench/CFL")
DB_DIR = os.path.join(EXEC_DIR, "gnn_milp_database")  

os.makedirs(DB_DIR, exist_ok=True)

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def configurar_gurobi():
    os.environ["GRB_LICENSE_FILE"] = EXEC_DIR
    env = gp.Env(empty=True)
    if "WLSACCESSID" in os.environ: env.setParam("WLSACCESSID", os.environ.get("WLSACCESSID"))
    if "WLSSECRET" in os.environ: env.setParam("WLSSECRET", os.environ.get("WLSSECRET"))
    if "LICENSEID" in os.environ: env.setParam("LICENSEID", int(os.environ.get("LICENSEID")))
    
    slurm_threads = int(os.environ.get("SLURM_CPUS_PER_TASK", 1))
    env.setParam("Threads", slurm_threads)
    env.setParam("LogToConsole", 0)
    
    # Configuración de Solution Pool
    env.setParam("PoolSearchMode", 2)  
    env.setParam("PoolSolutions", 10)  
    
    env.start()
    return env

# ==========================================
# 2. DEFINICIÓN DEL CALLBACK (MIPNODE & MIPSOL)
# ==========================================
def gurobi_callback(model, where):
    if where == GRB.Callback.MIPSOL:
        sol_count = model.cbGet(GRB.Callback.MIPSOL_SOLCNT)
        obj_val = model.cbGet(GRB.Callback.MIPSOL_OBJ)
        node_count = model.cbGet(GRB.Callback.MIPSOL_NODCNT)
        sol_vals = model.cbGetSolution(model._vars)
        
        incumbent_data = {
            "node": int(node_count),
            "objective": float(obj_val),
            "solution_vector": sol_vals
        }
        model._incumbents.append(incumbent_data)
        
    elif where == GRB.Callback.MIPNODE:
        status = model.cbGet(GRB.Callback.MIPNODE_STATUS)
        node_count = model.cbGet(GRB.Callback.MIPNODE_NODCNT)
        
        if status == GRB.OPTIMAL:
            obj_bnd = model.cbGet(GRB.Callback.MIPNODE_OBJBND)
            rel_vals = model.cbGetNodeRel(model._vars)
            
            node_data = {
                "node": int(node_count),
                "obj_bound": float(obj_bnd),
                "relaxation_vector": rel_vals
            }
            model._nodes.append(node_data)

# ==========================================
# 3. ORQUESTACIÓN Y SOLUCIÓN
# ==========================================
def process_instances(file_paths_to_process, time_limit_sec):
    env = configurar_gurobi()
    
    for file_path in file_paths_to_process:
        instance_name = os.path.basename(file_path).replace('.lp.gz', '')
        instance_dir = os.path.join(DB_DIR, instance_name)
        os.makedirs(instance_dir, exist_ok=True)
        
        print(f"--- Procesando: {instance_name} ---")

        try:
            m = gp.read(file_path, env=env)
        except gp.GurobiError as e:
            print(f"  [ERROR] Lectura: {e}")
            continue

        original_lp_path = os.path.join(instance_dir, "original.lp")
        m.write(original_lp_path)

        try:
            m_presolved = m.presolve()
            presolved_lp_path = os.path.join(instance_dir, "presolved.lp")
            m_presolved.write(presolved_lp_path)
            
            m_presolved._vars = m_presolved.getVars()
            m_presolved._incumbents = []
            m_presolved._nodes = []
            
            # Aquí aplicamos el límite de tiempo que viene de Slurm
            m_presolved.setParam('TimeLimit', time_limit_sec)
            
            m_presolved.optimize(gurobi_callback)
            
            # --------------------------------------------------
            # EXTRACCIÓN DEL SOLUTION POOL (BLINDADO)
            # --------------------------------------------------
            solution_pool_data = []
            if m_presolved.SolCount > 0:
                # Comprobamos si el modelo sigue siendo un MIP después del presolve
                if m_presolved.IsMIP == 1:
                    try:
                        for i in range(m_presolved.SolCount):
                            m_presolved.setParam("SolutionNumber", i)
                            sol_obj = m_presolved.PoolObjVal
                            sol_vec = [v.Xn for v in m_presolved._vars]
                            solution_pool_data.append({
                                "pool_index": i,
                                "objective": sol_obj,
                                "vector": sol_vec
                            })
                    except AttributeError:
                        # Si es MIP pero se resolvió sin inicializar el Pool (caso trivial)
                        solution_pool_data.append({
                            "pool_index": 0,
                            "objective": m_presolved.ObjVal,
                            "vector": [v.X for v in m_presolved._vars]
                        })
                else:
                    # El presolve eliminó todas las variables enteras (modelo continuo LP)
                    solution_pool_data.append({
                        "pool_index": 0,
                        "objective": m_presolved.ObjVal,
                        "vector": [v.X for v in m_presolved._vars]
                    })

#            solution_pool_data = []
#            if m_presolved.SolCount > 0:
#                for i in range(m_presolved.SolCount):
#                    m_presolved.setParam("SolutionNumber", i)
#                    sol_obj = m_presolved.PoolObjVal
#                    sol_vec = [v.Xn for v in m_presolved._vars]
#                    solution_pool_data.append({
#                        "pool_index": i,
#                        "objective": sol_obj,
#                        "vector": sol_vec
#                    })

            # --------------------------------------------------
            # PERSISTENCIA DE METADATOS Y ESTADOS (BLINDADO)
            # --------------------------------------------------
            
            # 1. Extracción segura del MIP Gap
            try:
                safe_mip_gap = m_presolved.MIPGap
            except AttributeError:
                # Si no existe el gap (ej. se resolvió en presolve), el gap es 0.0 si es óptimo
                safe_mip_gap = 0.0 if m_presolved.Status == GRB.OPTIMAL else 1.0
                
            # 2. Extracción segura del conteo de nodos
            try:
                safe_node_count = m_presolved.NodeCount
            except AttributeError:
                # Si no hubo árbol de ramificación, se exploraron 0 nodos
                safe_node_count = 0


            metadata = {
                "instance": instance_name,
                "status": m_presolved.Status,
                "runtime": m_presolved.Runtime,
                #"mip_gap": m_presolved.MIPGap if m_presolved.SolCount > 0 else 1.0,
                "mip_gap": safe_mip_gap,
                #"node_count": m_presolved.NodeCount,
                "node_count": safe_node_count,
                "presolved_vars": m_presolved.NumVars,
                "presolved_constrs": m_presolved.NumConstrs,
                "pool_solutions_found": len(solution_pool_data)
            }
            
            with open(os.path.join(instance_dir, "metadata.json"), "w") as f:
                json.dump(metadata, f, indent=4)
                
            if m_presolved._nodes:
                df_nodes = pd.DataFrame(m_presolved._nodes)
                df_nodes.to_parquet(os.path.join(instance_dir, "mip_nodes.parquet"), engine="pyarrow")
                
            if m_presolved._incumbents:
                df_incumbents = pd.DataFrame(m_presolved._incumbents)
                df_incumbents.to_parquet(os.path.join(instance_dir, "mipsol_incumbents.parquet"), engine="pyarrow")
                
            if solution_pool_data:
                df_pool = pd.DataFrame(solution_pool_data)
                df_pool.to_parquet(os.path.join(instance_dir, "solution_pool.parquet"), engine="pyarrow")

            m_presolved.dispose()
            m.dispose()

        except gp.GurobiError as e:
            print(f"  [ERROR] Durante resolución/callbacks: {e}")

    print("\n[ÉXITO] Construcción de la base de datos GNN finalizada para este lote.")

# ==========================================
# 4. EJECUCIÓN PRINCIPAL
# ==========================================
if __name__ == "__main__":
    print("=== Configuración de Ejecución Seleccionada ===")
    print(f"Categorías: {args.categories}")
    print(f"Rango de instancias en lista: [{args.start_idx} : {args.end_idx}]")
    print(f"Tiempo límite de Gurobi: {args.time_limit}s\n")

    # Mapeo y filtrado selectivo de archivos
    file_paths = []
    for cat in args.categories:
        # CORRECCIÓN: .lp.gz aplicado directamente a la búsqueda que se ejecuta
        pattern = os.path.join(EXTRACT_DIR, cat, "LP", "*.lp.gz")
        
        print(f"  [DEBUG] Buscando archivos en: {pattern}")

        cat_files = glob.glob(pattern)
        cat_files.sort(key=natural_sort_key)
        
        sliced_files = cat_files[args.start_idx:args.end_idx]
        file_paths.extend(sliced_files)
        print(f"  > {cat}: Mapeadas {len(sliced_files)} instancias en el rango especificado.")

    print(f"\nTotal global de instancias a procesar en este Job: {len(file_paths)}")
    
    if len(file_paths) == 0:
        print("[AVISO] No se localizaron archivos en el rango parametrizado. Abortando.")
        exit(0)

    # CORRECCIÓN: Llamada a la función pasándole los archivos encontrados y el límite de tiempo
    process_instances(file_paths, args.time_limit)