"""
CFL GNN Data Generator - Refactored Version
============================================
This script processes MILP instances from MILPBench benchmark and generates
comprehensive datasets for GNN training, including:
- LP files (original and presolved)
- Pickle files with model features
- Intermediate solution data from callbacks
- Performance metrics
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
    # Problem characteristics
    num_vars: int
    num_constrs: int
    num_binary: int
    num_integer: int
    num_continuous: int
    num_nonzeros: int
    
    # Variable features
    var_types: np.ndarray  # Variable types (0=continuous, 1=binary, 2=integer)
    var_obj_coeffs: np.ndarray  # Objective coefficients
    var_lb: np.ndarray  # Lower bounds
    var_ub: np.ndarray  # Upper bounds
    var_names: List[str]  # Variable names
    
    # Constraint features
    constr_senses: np.ndarray  # Constraint senses (<, >, =)
    constr_rhs: np.ndarray  # Right-hand side values
    constr_names: List[str]  # Constraint names
    
    # Constraint matrix (sparse representation)
    constraint_matrix: Dict[str, np.ndarray]  # {'row': [], 'col': [], 'data': []}
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
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
    solution_vector: np.ndarray  # Variable values
    is_feasible: bool
    is_optimal: bool
    
    # Additional solution quality metrics
    integrality_gap: Optional[float] = None
    bound: Optional[float] = None


# ==========================================
# FEATURE EXTRACTION FUNCTIONS
# ==========================================

def extract_model_features(model: gp.Model) -> ModelFeatures:
    """
    Extract comprehensive features from a Gurobi model
    
    Args:
        model: Gurobi model instance
        
    Returns:
        ModelFeatures object containing all extracted features
    """
    # Get all variables and constraints
    vars = model.getVars()
    constrs = model.getConstrs()
    
    # Variable features
    var_types = np.array([v.VType for v in vars])
    var_obj_coeffs = np.array([v.Obj for v in vars])
    var_lb = np.array([v.LB for v in vars])
    var_ub = np.array([v.UB for v in vars])
    var_names = [v.VarName for v in vars]
    
    # Count variable types
    num_binary = sum(1 for v in vars if v.VType == GRB.BINARY)
    num_integer = sum(1 for v in vars if v.VType == GRB.INTEGER)
    num_continuous = sum(1 for v in vars if v.VType == GRB.CONTINUOUS)
    
    # Constraint features
    constr_senses = np.array([c.Sense for c in constrs])
    constr_rhs = np.array([c.RHS for c in constrs])
    constr_names = [c.ConstrName for c in constrs]
    
    # Extract constraint matrix in sparse format
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
        num_vars=len(vars),
        num_constrs=len(constrs),
        num_binary=num_binary,
        num_integer=num_integer,
        num_continuous=num_continuous,
        num_nonzeros=len(vals),
        var_types=var_types,
        var_obj_coeffs=var_obj_coeffs,
        var_lb=var_lb,
        var_ub=var_ub,
        var_names=var_names,
        constr_senses=constr_senses,
        constr_rhs=constr_rhs,
        constr_names=constr_names,
        constraint_matrix=constraint_matrix
    )


def extract_solution_features(model: gp.Model, node_count: int = 0, 
                              solve_time: float = 0.0) -> Optional[SolutionFeatures]:
    """
    Extract features from current model solution
    
    Args:
        model: Gurobi model instance
        node_count: Current node count in B&B tree
        solve_time: Time spent solving
        
    Returns:
        SolutionFeatures object or None if no solution available
    """
    try:
        # Check if solution is available
        if model.SolCount == 0:
            return None
            
        vars = model.getVars()
        solution_vector = np.array([v.X for v in vars])
        
        # Get objective value
        obj_val = model.ObjVal
        
        # Get MIP gap if applicable
        try:
            mip_gap = model.MIPGap
        except:
            mip_gap = 0.0
            
        # Get bound if available
        try:
            bound = model.ObjBound
        except:
            bound = None
            
        is_optimal = (model.Status == GRB.OPTIMAL)
        is_feasible = (model.Status in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.SOLUTION_LIMIT])
        
        # Calculate integrality gap if bound is available
        integrality_gap = None
        if bound is not None and abs(obj_val) > 1e-6:
            integrality_gap = abs(obj_val - bound) / abs(obj_val)
        
        return SolutionFeatures(
            objective_value=obj_val,
            mip_gap=mip_gap,
            node_count=node_count,
            solution_time=solve_time,
            solution_vector=solution_vector,
            is_feasible=is_feasible,
            is_optimal=is_optimal,
            integrality_gap=integrality_gap,
            bound=bound
        )
    except Exception as e:
        print(f"  [WARNING] Could not extract solution features: {e}")
        return None


def read_existing_pickle(pickle_path: str) -> Optional[Tuple[Dict, float]]:
    """
    Read existing pickle file from MILPBench format
    
    Args:
        pickle_path: Path to pickle file
        
    Returns:
        Tuple of (solution_dict, mip_gap) or None if file doesn't exist
    """
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
    """Callback handler to collect data during optimization"""
    
    def __init__(self, model: gp.Model):
        self.model = model
        self.vars = model.getVars()
        
        # Storage for intermediate data
        self.incumbent_solutions = []  # List of (node, obj, solution_vector, time)
        self.node_relaxations = []  # List of (node, bound, relaxation_vector, time)
        self.node_times = {}  # Track time at each node
        self.start_time = time.time()
        
    def __call__(self, model, where):
        """Callback function called by Gurobi during optimization"""
        current_time = time.time() - self.start_time
        
        if where == GRB.Callback.MIPSOL:
            # New incumbent solution found
            sol_count = model.cbGet(GRB.Callback.MIPSOL_SOLCNT)
            obj_val = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            node_count = model.cbGet(GRB.Callback.MIPSOL_NODCNT)
            
            # NUEVO: Capturar la cota (bound) en este nodo exacto
            obj_bnd = model.cbGet(GRB.Callback.MIPSOL_OBJBND)
            
            # NUEVO: Calcular el MIP Gap en tiempo real
            # Usamos abs() y un epsilon (1e-10) para evitar la división por cero
            if abs(obj_val) > 1e-10:
                mip_gap = abs(obj_val - obj_bnd) / abs(obj_val)
            else:
                mip_gap = 0.0

            # Get solution values
            sol_vals = model.cbGetSolution(self.vars)
            
            self.incumbent_solutions.append({
                'node': int(node_count),
                'solution_count': int(sol_count),
                'objective': float(obj_val),
                'bound': float(obj_bnd),       # Se añade a la tabla
                'mip_gap': float(mip_gap),     # Se añade a la tabla
                'solution_vector': np.array(sol_vals),
                'time': current_time
            })
            
        elif where == GRB.Callback.MIPNODE:
            # At a node in the B&B tree
            status = model.cbGet(GRB.Callback.MIPNODE_STATUS)
            node_count = model.cbGet(GRB.Callback.MIPNODE_NODCNT)
            
            if status == GRB.OPTIMAL:
                # Node LP relaxation is optimal
                obj_bnd = model.cbGet(GRB.Callback.MIPNODE_OBJBND)
                
                # Get relaxation values
                try:
                    rel_vals = model.cbGetNodeRel(self.vars)
                    
                    # NUEVO: Contar variables fraccionales (espacio de ramificación "activo")
                    # Tolerancia de 1e-5 para descartar errores numéricos de punto flotante
                    fractional_count = sum(
                        1 for i, v in enumerate(self.vars) 
                        if v.VType in [GRB.BINARY, GRB.INTEGER] 
                        and 1e-5 < abs(rel_vals[i] - round(rel_vals[i])) < 1 - 1e-5
                    )

                    self.node_relaxations.append({
                        'node': int(node_count),
                        'bound': float(obj_bnd),
                        'fractional_vars': fractional_count, # <-- NUEVA MÉTRICA
                        'relaxation_vector': np.array(rel_vals),
                        'time': current_time
                    })
                except:
                    pass  # Sometimes relaxation values are not available


# ==========================================
# MAIN PROCESSING LOGIC
# ==========================================

def configure_gurobi_env(time_limit: int, threads: int = None) -> gp.Env:
    """
    Configure Gurobi environment with appropriate settings
    
    Args:
        time_limit: Time limit in seconds
        threads: Number of threads (defaults to SLURM_CPUS_PER_TASK or 1)
        
    Returns:
        Configured Gurobi environment
    """
    env = gp.Env(empty=True)
    
    # WLS credentials if available
    if "WLSACCESSID" in os.environ:
        env.setParam("WLSACCESSID", os.environ["WLSACCESSID"])
    if "WLSSECRET" in os.environ:
        env.setParam("WLSSECRET", os.environ["WLSSECRET"])
    if "LICENSEID" in os.environ:
        env.setParam("LICENSEID", int(os.environ["LICENSEID"]))
    
    # Set threads
    if threads is None:
        threads = int(os.environ.get("SLURM_CPUS_PER_TASK", 1))
    env.setParam("Threads", threads)
    
    # Solution pool settings
    env.setParam("PoolSearchMode", 2)  # Systematic search for diverse solutions
    env.setParam("PoolSolutions", 10)  # Keep up to 10 solutions
    
    # Logging
    env.setParam("LogToConsole", 0)
    
    env.start()
    return env


def process_single_instance(lp_file_path: str, output_dir: str, 
                           env: gp.Env, time_limit: int,
                           use_existing_pickle: bool = True) -> bool:
                           #read_existing_pickle: bool = True) -> bool:
    """
    Process a single MILP instance
    
    Args:
        lp_file_path: Path to .lp or .lp.gz file
        output_dir: Output directory for this instance
        env: Gurobi environment
        time_limit: Time limit in seconds
        read_existing_pickle: Whether to read existing pickle files
        
    Returns:
        True if processing was successful, False otherwise
    """
    instance_name = os.path.basename(lp_file_path).replace('.lp.gz', '').replace('.lp', '')
    instance_dir = os.path.join(output_dir, instance_name)
    os.makedirs(instance_dir, exist_ok=True)
    
    print(f"--- Processing: {instance_name} ---")
    
    try:
        # Step 1: Read model
        print("  [1/7] Reading model...")
        model = gp.read(lp_file_path, env=env)
        
        # Step 2: Extract and save original model features
        print("  [2/7] Extracting original model features...")
        original_features = extract_model_features(model)
        
        ## Save original LP file
        #original_lp_path = os.path.join(instance_dir, "original.lp")
        #model.write(original_lp_path)
        
        ## Save original features as pickle
        #with open(os.path.join(instance_dir, "original_features.pkl"), 'wb') as f:
        #    pickle.dump({
        #        'model_features': original_features,
        #        'timestamp': time.time()
        #    }, f)

        # Save original features as COMPRESSED pickle
        with gzip.open(os.path.join(instance_dir, "original_features.pickle.gz"), 'wb') as f:
            pickle.dump({
                'model_features': original_features,
                'timestamp': time.time()
            }, f)
        
        # Step 3: Read existing solution pickle if available
        print("  [3/7] Checking for existing solution...")
        existing_solution = None
        if use_existing_pickle:
            pickle_dir = os.path.dirname(os.path.dirname(lp_file_path))

            pickle_path = os.path.join(pickle_dir, 'Pickle', 
                                      instance_name + '.pickle.gz')
            if not os.path.exists(pickle_path):
                pickle_path = os.path.join(pickle_dir, 'Pickle', 
                                      instance_name + '.pickle')

            existing_solution = read_existing_pickle(pickle_path)
            if existing_solution:
                print(f"    Found existing solution with gap: {existing_solution[1]}")
            else:
                print(f"    [WARN] No se encontró el histórico en: {pickle_path}")
        
        ## Step 4: Presolve
        #print("  [4/7] Presolving model...")
        #model_to_solve = model.presolve()
        
        #if model_to_solve is None:
        #    print("  [WARNING] Presolve eliminated entire model (trivial problem)")
        #    # Save metadata for trivial case
        #    metadata = {
        #        'instance': instance_name,
        #        'status': 'TRIVIAL',
        #        'is_trivial': True,
        #        'original_vars': original_features.num_vars,
        #        'original_constrs': original_features.num_constrs
        #    }
        #    with open(os.path.join(instance_dir, "metadata.json"), 'w') as f:
        #        json.dump(metadata, f, indent=2)
        #    return True
        
        ## Extract presolved features
        #presolved_features = extract_model_features(model_to_solve)
        #presolved_lp_path = os.path.join(instance_dir, "presolved.lp")
        #model_to_solve.write(presolved_lp_path)
        
        ## Save presolved features
        #with open(os.path.join(instance_dir, "presolved_features.pkl"), 'wb') as f:
        #    pickle.dump({
        #        'model_features': presolved_features,
        #        'timestamp': time.time()
        #    }, f)
        
        # Step 4: Forzar el árbol de ramificación (Inhibir Presolve)
        print("  [4/7] Configurando modelo (Inhibiendo Presolve)...")
        
        # Clonamos el modelo original para no alterar el objeto base
        model_to_solve = model.copy()
        
        # PARÁMETRO CRÍTICO: Desactivar Presolve para forzar Branch & Bound
        model_to_solve.setParam('Presolve', 0)
        
        # Extraemos las características. Al no haber presolve, serán idénticas a 
        # las originales, pero mantenemos la estructura de datos que espera su pipeline.
        presolved_features = extract_model_features(model_to_solve)
        presolved_lp_path = os.path.join(instance_dir, "presolved.lp")
        model_to_solve.write(presolved_lp_path)
        
        ## Save presolved features
        #with open(os.path.join(instance_dir, "presolved_features.pkl"), 'wb') as f:
        #    pickle.dump({
        #        'model_features': presolved_features,
        #        'timestamp': time.time()
        #    }, f)

        # Save presolved features as COMPRESSED pickle
        with gzip.open(os.path.join(instance_dir, "presolved_features.pickle.gz"), 'wb') as f:
            pickle.dump({
                'model_features': presolved_features,
                'timestamp': time.time()
            }, f)
        
        # Step 5: Set up callback and solve
        print(f"  [5/7] Solving with time limit {time_limit}s...")
        callback = DataCollectionCallback(model_to_solve)
        
        model_to_solve.setParam('TimeLimit', time_limit)
        
        start_time = time.time()
        model_to_solve.optimize(callback)
        solve_time = time.time() - start_time

        
        # Step 6: Extract solution pool
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
        
        # Step 7: Save all results
        print("  [7/7] Saving results...")
        
        # Extract final solution features
        final_solution = extract_solution_features(model_to_solve, 
                                                   model_to_solve.NodeCount,
                                                   solve_time)
        
        # Save comprehensive solution pickle
        solution_data = {
            'final_solution': final_solution,
            'incumbent_solutions': callback.incumbent_solutions,
            'node_relaxations': callback.node_relaxations,
            'solution_pool': solution_pool,
            'existing_benchmark_solution': existing_solution
        }
        
        #with open(os.path.join(instance_dir, "solutions.pkl"), 'wb') as f:
        #    pickle.dump(solution_data, f)

        with gzip.open(os.path.join(instance_dir, "solutions.pickle.gz"), 'wb') as f:
            pickle.dump(solution_data, f)
        
        # Save metadata
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
            'pool_solutions_found': len(solution_pool),
            'original_problem': {
                'vars': original_features.num_vars,
                'constrs': original_features.num_constrs,
                'nonzeros': original_features.num_nonzeros,
                'binary': original_features.num_binary,
                'integer': original_features.num_integer,
                'continuous': original_features.num_continuous
            },
            'presolved_problem': {
                'vars': presolved_features.num_vars,
                'constrs': presolved_features.num_constrs,
                'nonzeros': presolved_features.num_nonzeros
            }
        }
        
        if final_solution:
            metadata['objective_value'] = final_solution.objective_value
            metadata['is_optimal'] = final_solution.is_optimal
        
        with open(os.path.join(instance_dir, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save dataframes for easy analysis
        if callback.incumbent_solutions:
            df_incumbents = pd.DataFrame([
                {k: v for k, v in sol.items() if k != 'solution_vector'}
                for sol in callback.incumbent_solutions
            ])
            
            #df_incumbents.to_csv(os.path.join(instance_dir, "incumbents.csv"), index=False)
        
            # Cambiamos to_csv por to_parquet
            df_incumbents.to_parquet(
                os.path.join(instance_dir, "incumbents.parquet"), 
                engine="pyarrow"
            )

        if callback.node_relaxations:
            df_nodes = pd.DataFrame([
                {k: v for k, v in node.items() if k != 'relaxation_vector'}
                for node in callback.node_relaxations
            ])
            
            #df_nodes.to_csv(os.path.join(instance_dir, "node_relaxations.csv"), index=False)

           # Cambiamos to_csv por to_parquet
            df_nodes.to_parquet(
                os.path.join(instance_dir, "node_relaxations.parquet"), 
                engine="pyarrow"
            ) 

        # Cleanup
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
    """Natural sorting key for filenames"""
    return [int(text) if text.isdigit() else text.lower() 
            for text in re.split('([0-9]+)', s)]
    #return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]


def main():
    parser = argparse.ArgumentParser(
        description="CFL GNN Data Generator - Extraer features y soluciones de instancias MILP"
    )
    
    parser.add_argument(
        '--categories', 
        nargs='+', 
        default=["CFL_easy_instance"], #"CFL_medium_instance", "CFL_hard_instance"],
        help="Categorías a procesar (separadas por espacios)"
    )
    
    parser.add_argument(
        '--start_idx', 
        type=int, 
        default=0,
        help="Índice inicial (inclusivo)"
    )
    
    parser.add_argument(
        '--end_idx', 
        type=int, 
        default=30,
        help="Índice final (exclusivo)"
    )
    
    parser.add_argument(
        '--time_limit', 
        type=int, 
        default=60,
        help="Tiempo límite"
    )
    
    parser.add_argument(
        '--input_dir',
        type=str,
        default="/home/vrcelestino/discodatos/cfl-gurobi-gnn/data/raw/MILPBench/CFL",
        help="Directorio de entrada con archivos LP"
    )
    
    parser.add_argument(
        '--output_dir',
        type=str,
        #default="/raid/vrcelestino/data/gnn_milp_database",
        default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps",
        help="Directorio de salida con datos generados"
    )
    
    parser.add_argument(
        '--threads',
        type=int,
        default=None,
        help="Number of threads (defaults to SLURM_CPUS_PER_TASK or 1)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("CFL GNN Data Generator v2.0")
    print("=" * 60)
    print(f"Categorias: {args.categories}")
    print(f"Rango de Instancias: [{args.start_idx}, {args.end_idx})")
    print(f"Tiempo límite: {args.time_limit}s")
    print(f"Directorio de entrada: {args.input_dir}")
    print(f"Directorio de salida: {args.output_dir}")
    print("=" * 60)
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Collect all files to process
    file_paths = []
    for category in args.categories:
        pattern = os.path.join(args.input_dir, category, "LP", "*.lp.gz")
        category_files = glob.glob(pattern)
        
        if not category_files:
            # Try without .gz extension
            pattern = os.path.join(args.input_dir, category, "LP", "*.lp")
            category_files = glob.glob(pattern)
        
        category_files.sort(key=natural_sort_key)
        sliced_files = category_files[args.start_idx:args.end_idx]
        file_paths.extend(sliced_files)
        
        print(f"  {category}: {len(sliced_files)} instances")
    
    print(f"\nTotal instances to process: {len(file_paths)}")
    
    if len(file_paths) == 0:
        print("[WARNING] No files found matching criteria. Exiting.")
        return
    
    # Configure Gurobi environment
    print("\n Configurando el entorno Gurobi...")

    # Nota: El script de Slurm ya exporta GRB_LICENSE_FILE correctamente, 
    # por lo que no necesitamos sobrescribirlo aquí.
    #os.environ["GRB_LICENSE_FILE"] = os.path.join(args.output_dir, "gurobi.lic")

    env = gp.Env(empty=True)
    if "WLSACCESSID" in os.environ: env.setParam("WLSACCESSID", os.environ.get("WLSACCESSID"))
    if "WLSSECRET" in os.environ: env.setParam("WLSSECRET", os.environ.get("WLSSECRET"))
    if "LICENSEID" in os.environ: env.setParam("LICENSEID", int(os.environ.get("LICENSEID")))

    num_threads = args.threads if args.threads is not None else int(os.environ.get("SLURM_CPUS_PER_TASK", 1))
    env.setParam("Threads", num_threads)
    env.setParam("TimeLimit", args.time_limit)
    env.setParam("LogToConsole", 0)

    # Configuración de Solution Pool (Recomendado por Gurobot para sacar más datos)
    env.setParam("PoolSearchMode", 2)
    env.setParam("PoolSolutions", 10)

    env.start()
    
    # Process all instances
    print("\nProcessing instances...")
    print("=" * 60)
    
    success_count = 0
    failure_count = 0
    
    for i, file_path in enumerate(file_paths, 1):
        print(f"\n[{i}/{len(file_paths)}]")
        
        success = process_single_instance(
            file_path, 
            args.output_dir,
            env,
            args.time_limit,
            use_existing_pickle=True
        )
        
        if success:
            success_count += 1
        else:
            failure_count += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Successfully processed: {success_count}/{len(file_paths)}")
    print(f"Failed: {failure_count}/{len(file_paths)}")
    print(f"Output directory: {args.output_dir}")
    print("=" * 60)
    
    # Cleanup
    env.dispose()


if __name__ == "__main__":
    main()