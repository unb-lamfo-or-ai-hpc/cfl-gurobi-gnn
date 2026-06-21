"""
CFL GNN Data Generator - Refactored Version (Multi-Task Edition)
================================================================
Extrae la trayectoria completa de soluciones (incumbents) y relajaciones LP
para permitir el entrenamiento Multi-Grafo (Multi-Task Learning).
"""

import os
import glob
import re
import argparse
import json
import pickle
import numpy as np
import pandas as pd
import gurobipy as gp
from gurobipy import GRB
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import time
import gzip


# ==========================================
# DATA CLASSES FOR STRUCTURED STORAGE
# ==========================================

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
# FEATURE EXTRACTION FUNCTIONS
# ==========================================

def extract_model_features(model: gp.Model) -> ModelFeatures:
    vars = model.getVars()
    constrs = model.getConstrs()
    
    var_types = np.array([v.VType for v in vars])
    var_obj_coeffs = np.array([v.Obj for v in vars])
    var_lb = np.array([v.LB for v in vars])
    var_ub = np.array([v.UB for v in vars])
    var_names = [v.VarName for v in vars]
    
    num_binary = sum(1 for v in vars if v.VType == GRB.BINARY)
    num_integer = sum(1 for v in vars if v.VType == GRB.INTEGER)
    num_continuous = sum(1 for v in vars if v.VType == GRB.CONTINUOUS)
    
    constr_senses = np.array([c.Sense for c in constrs])
    constr_rhs = np.array([c.RHS for c in constrs])
    constr_names = [c.ConstrName for c in constrs]
    
    rows, cols, vals = [], [], []
    for i, constr in enumerate(constrs):
        row = model.getRow(constr)
        for j in range(row.size()):
            rows.append(i)
            cols.append(row.getVar(j).index)
            vals.append(row.getCoeff(j))
    
    constraint_matrix = {
        'row': np.array(rows),
        'col': np.array(cols),
        'data': np.array(vals)
    }
    
    return ModelFeatures(
        num_vars=len(vars), num_constrs=len(constrs),
        num_binary=num_binary, num_integer=num_integer,
        num_continuous=num_continuous, num_nonzeros=len(vals),
        var_types=var_types, var_obj_coeffs=var_obj_coeffs,
        var_lb=var_lb, var_ub=var_ub, var_names=var_names,
        constr_senses=constr_senses, constr_rhs=constr_rhs,
        constr_names=constr_names, constraint_matrix=constraint_matrix
    )


def extract_solution_features(model: gp.Model, node_count: int = 0, 
                              solve_time: float = 0.0) -> Optional[SolutionFeatures]:
    try:
        if model.SolCount == 0:
            return None
            
        vars = model.getVars()
        solution_vector = np.array([v.X for v in vars])
        
        obj_val = model.ObjVal
        
        try: mip_gap = model.MIPGap
        except: mip_gap = 0.0
            
        try: bound = model.ObjBound
        except: bound = None
            
        is_optimal = (model.Status == GRB.OPTIMAL)
        is_feasible = (model.Status in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.SOLUTION_LIMIT])
        
        integrality_gap = None
        if bound is not None and abs(obj_val) > 1e-6:
            integrality_gap = abs(obj_val - bound) / abs(obj_val)
        
        return SolutionFeatures(
            objective_value=obj_val, mip_gap=mip_gap,
            node_count=node_count, solution_time=solve_time,
            solution_vector=solution_vector, is_feasible=is_feasible,
            is_optimal=is_optimal, integrality_gap=integrality_gap,
            bound=bound
        )
    except Exception as e:
        print(f"  [WARNING] Could not extract solution features: {e}")
        return None


def read_existing_pickle(pickle_path: str) -> Optional[Tuple[Dict, float]]:
    if not os.path.exists(pickle_path):
        return None
        
    try:
        if pickle_path.endswith('.gz'):
            with gzip.open(pickle_path, 'rb') as f:
                data = pickle.load(f)
        else:
            with open(pickle_path, 'rb') as f:
                data = pickle.load(f)
        
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return data[0], data[1]
        else:
            print(f"  [WARNING] Unexpected pickle format: {type(data)}")
            return None
    except Exception as e:
        print(f"  [ERROR] Could not read pickle file {pickle_path}: {e}")
        return None


# ==========================================
# CALLBACK HANDLER
# ==========================================

class DataCollectionCallback:
    def __init__(self, model: gp.Model):
        self.model = model
        self.vars = model.getVars()
        self.incumbent_solutions = [] 
        self.node_relaxations = []
        self.start_time = time.time()
        
    def __call__(self, model, where):
        current_time = time.time() - self.start_time
        
        if where == GRB.Callback.MIPSOL:
            sol_count = model.cbGet(GRB.Callback.MIPSOL_SOLCNT)
            obj_val = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            node_count = model.cbGet(GRB.Callback.MIPSOL_NODCNT)
            obj_bnd = model.cbGet(GRB.Callback.MIPSOL_OBJBND)
            
            if abs(obj_val) > 1e-10:
                mip_gap = abs(obj_val - obj_bnd) / abs(obj_val)
            else:
                mip_gap = 0.0

            sol_vals = model.cbGetSolution(self.vars)
            
            self.incumbent_solutions.append({
                'node': int(node_count),
                'solution_count': int(sol_count),
                'objective': float(obj_val),
                'bound': float(obj_bnd),
                'mip_gap': float(mip_gap),
                'solution_vector': np.array(sol_vals),
                'time': current_time
            })
            
        elif where == GRB.Callback.MIPNODE:
            status = model.cbGet(GRB.Callback.MIPNODE_STATUS)
            node_count = model.cbGet(GRB.Callback.MIPNODE_NODCNT)
            
            if status == GRB.OPTIMAL:
                obj_bnd = model.cbGet(GRB.Callback.MIPNODE_OBJBND)
                try:
                    rel_vals = model.cbGetNodeRel(self.vars)
                    fractional_count = sum(
                        1 for i, v in enumerate(self.vars) 
                        if v.VType in [GRB.BINARY, GRB.INTEGER] 
                        and 1e-5 < abs(rel_vals[i] - round(rel_vals[i])) < 1 - 1e-5
                    )

                    self.node_relaxations.append({
                        'node': int(node_count),
                        'bound': float(obj_bnd),
                        'fractional_vars': fractional_count,
                        'relaxation_vector': np.array(rel_vals),
                        'time': current_time
                    })
                except:
                    pass


# ==========================================
# MAIN PROCESSING LOGIC
# ==========================================

def process_single_instance(lp_file_path: str, output_dir: str, 
                           env: gp.Env, time_limit: int,
                           use_existing_pickle: bool = True) -> bool:
                           
    instance_name = os.path.basename(lp_file_path).replace('.lp.gz', '').replace('.lp', '')
    instance_dir = os.path.join(output_dir, instance_name)
    os.makedirs(instance_dir, exist_ok=True)
    
    print(f"--- Processing: {instance_name} ---")
    
    try:
        print("  [1/7] Reading model...")
        model = gp.read(lp_file_path, env=env)
        
        print("  [2/7] Extracting original model features...")
        original_features = extract_model_features(model)
        
        with gzip.open(os.path.join(instance_dir, "original_features.pickle.gz"), 'wb') as f:
            pickle.dump({
                'model_features': original_features,
                'timestamp': time.time()
            }, f)
        
        print("  [3/7] Checking for existing solution...")
        existing_solution = None
        if use_existing_pickle:
            pickle_dir = os.path.dirname(os.path.dirname(lp_file_path))
            pickle_path = os.path.join(pickle_dir, 'Pickle', instance_name + '.pickle.gz')
            if not os.path.exists(pickle_path):
                pickle_path = os.path.join(pickle_dir, 'Pickle', instance_name + '.pickle')

            existing_solution = read_existing_pickle(pickle_path)
            if existing_solution:
                print(f"    Found existing solution with gap: {existing_solution[1]}")
            else:
                print(f"    [WARN] No se encontró el histórico en: {pickle_path}")
        
        print("  [4/7] Configurando modelo (Inhibiendo Presolve)...")
        model_to_solve = model.copy()
        model_to_solve.setParam('Presolve', 0)
        
        presolved_features = extract_model_features(model_to_solve)
        presolved_lp_path = os.path.join(instance_dir, "presolved.lp")
        model_to_solve.write(presolved_lp_path)
        
        with gzip.open(os.path.join(instance_dir, "presolved_features.pickle.gz"), 'wb') as f:
            pickle.dump({
                'model_features': presolved_features,
                'timestamp': time.time()
            }, f)
        
        print(f"  [5/7] Solving with time limit {time_limit}s...")
        callback = DataCollectionCallback(model_to_solve)
        model_to_solve.setParam('TimeLimit', time_limit)
        
        start_time = time.time()
        model_to_solve.optimize(callback)
        solve_time = time.time() - start_time

        print("  [6/7] Extracting solution pool...")
        solution_pool = []
        if model_to_solve.SolCount > 0:
            for i in range(min(model_to_solve.SolCount, model_to_solve.Params.PoolSolutions)):
                try:
                    model_to_solve.setParam("SolutionNumber", i)
                    pool_obj = model_to_solve.PoolObjVal
                    pool_solution = np.array([v.Xn for v in model_to_solve.getVars()])
                    
                    solution_pool.append({
                        'pool_index': i,
                        'objective': float(pool_obj),
                        'solution_vector': pool_solution
                    })
                except:
                    break
        
        print("  [7/7] Saving results...")
        final_solution = extract_solution_features(model_to_solve, 
                                                   model_to_solve.NodeCount,
                                                   solve_time)
        
        solution_data = {
            'final_solution': final_solution,
            'incumbent_solutions': callback.incumbent_solutions,
            'node_relaxations': callback.node_relaxations,
            'solution_pool': solution_pool,
            'existing_benchmark_solution': existing_solution
        }
        
        with gzip.open(os.path.join(instance_dir, "solutions.pickle.gz"), 'wb') as f:
            pickle.dump(solution_data, f)
        
        metadata = {
            'instance': instance_name,
            'status': model_to_solve.Status,
            'status_name': {
                1: 'LOADED', 2: 'OPTIMAL', 3: 'INFEASIBLE', 
                4: 'INF_OR_UNBD', 5: 'UNBOUNDED', 9: 'TIME_LIMIT'
            }.get(model_to_solve.Status, 'UNKNOWN'),
            'runtime': solve_time,
            'mip_gap': getattr(model_to_solve, 'MIPGap', 0.0),
            'node_count': getattr(model_to_solve, 'NodeCount', 0),
            'num_solutions_found': model_to_solve.SolCount,
            'num_incumbents_collected': len(callback.incumbent_solutions),
            'num_nodes_collected': len(callback.node_relaxations),
            'pool_solutions_found': len(solution_pool)
        }
        
        if final_solution:
            metadata['objective_value'] = final_solution.objective_value
            metadata['is_optimal'] = final_solution.is_optimal
        
        with open(os.path.join(instance_dir, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # --- AQUI ESTABA EL BLOQUEO: INCLUIMOS LOS VECTORES COMPLETOS ---
        if callback.incumbent_solutions:
            df_incumbents = pd.DataFrame([
                {
                    'node': sol['node'],
                    'solution_count': sol['solution_count'],
                    'objective': sol['objective'],
                    'bound': sol['bound'],
                    'mip_gap': sol['mip_gap'],
                    'time': sol['time'],
                    'solution_vector': sol['solution_vector'].tolist() # <- Conservado y serializable
                }
                for sol in callback.incumbent_solutions
            ])
            df_incumbents.to_parquet(
                os.path.join(instance_dir, "incumbents.parquet"), 
                engine="pyarrow"
            )

        if callback.node_relaxations:
            df_nodes = pd.DataFrame([
                {
                    'node': node['node'],
                    'bound': node['bound'],
                    'fractional_vars': node['fractional_vars'],
                    'time': node['time'],
                    'relaxation_vector': node['relaxation_vector'].tolist() # <- Conservado y serializable
                }
                for node in callback.node_relaxations
            ])
            df_nodes.to_parquet(
                os.path.join(instance_dir, "node_relaxations.parquet"), 
                engine="pyarrow"
            ) 
        # ----------------------------------------------------------------

        model_to_solve.dispose()
        model.dispose()
        
        print(f"  ✓ Successfully processed {instance_name}")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to process {instance_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ==========================================
# COMMAND LINE INTERFACE
# ==========================================

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def main():
    parser = argparse.ArgumentParser(description="CFL GNN Data Generator")
    parser.add_argument('--categories', nargs='+', default=["CFL_easy_instance"])
    parser.add_argument('--start_idx', type=int, default=0)
    parser.add_argument('--end_idx', type=int, default=30)
    parser.add_argument('--time_limit', type=int, default=60)
    parser.add_argument('--input_dir', type=str, default="/home/vrcelestino/discodatos/cfl-gurobi-gnn/data/raw/MILPBench/CFL")
    parser.add_argument('--output_dir', type=str, default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps")
    parser.add_argument('--threads', type=int, default=None)
    args = parser.parse_args()
    
    print("=" * 60)
    print("CFL GNN Data Generator v4.0 (Multi-Task)")
    print("=" * 60)
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    file_paths = []
    for category in args.categories:
        pattern = os.path.join(args.input_dir, category, "LP", "*.lp.gz")
        category_files = glob.glob(pattern)
        if not category_files:
            pattern = os.path.join(args.input_dir, category, "LP", "*.lp")
            category_files = glob.glob(pattern)
        
        category_files.sort(key=natural_sort_key)
        sliced_files = category_files[args.start_idx:args.end_idx]
        file_paths.extend(sliced_files)
        
    if len(file_paths) == 0:
        print("[WARNING] No files found matching criteria.")
        return
    
    env = gp.Env(empty=True)
    if "WLSACCESSID" in os.environ: env.setParam("WLSACCESSID", os.environ.get("WLSACCESSID"))
    if "WLSSECRET" in os.environ: env.setParam("WLSSECRET", os.environ.get("WLSSECRET"))
    if "LICENSEID" in os.environ: env.setParam("LICENSEID", int(os.environ.get("LICENSEID")))

    num_threads = args.threads if args.threads is not None else int(os.environ.get("SLURM_CPUS_PER_TASK", 1))
    env.setParam("Threads", num_threads)
    env.setParam("TimeLimit", args.time_limit)
    env.setParam("LogToConsole", 0)
    env.setParam("PoolSearchMode", 2)
    env.setParam("PoolSolutions", 10)
    env.start()
    
    success_count = 0
    failure_count = 0
    
    for i, file_path in enumerate(file_paths, 1):
        print(f"\n[{i}/{len(file_paths)}]")
        success = process_single_instance(file_path, args.output_dir, env, args.time_limit, use_existing_pickle=True)
        if success: success_count += 1
        else: failure_count += 1
    
    print("\n" + "=" * 60)
    print(f"Successfully processed: {success_count}/{len(file_paths)}")
    print("=" * 60)
    env.dispose()

if __name__ == "__main__":
    main()