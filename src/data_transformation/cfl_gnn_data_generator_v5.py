"""
CFL GNN Data Generator - Phase 1 Memory-Safe Version (v5)
==========================================================
Key changes from v4:
  - MEMORY-SAFE CALLBACK: callback buffers are flushed to CSV incrementally
    when they reach BUFFER_LIMIT (default 500 entries). This prevents OOM
    kills on hard instances with 10,000+ variables and 3,600-second solves.
  - MIPSOL_PHASE FILTER: only Phase 1 incumbents (standard MIP search) are
    collected. Phase 0 (NoRel heuristic) solutions are ignored as they do
    not represent B&B tree search behavior.
  - CSV-TO-PARQUET CONVERSION: intermediate results are written to CSV during
    the solve and converted to parquet at the end. CSV is deleted after
    conversion to save disk space.
  - All Phase 1 fixes from v4 remain active: adaptive presolve, PoolSearchMode=1,
    v.PoolNX API migration, MIP gap guard, metadata logging.
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
import csv


# ==========================================
# CONSTANTS
# ==========================================

# Probe solve budget (seconds). If Gurobi explores fewer than
# COMPLEXITY_NODE_THRESHOLD nodes within this budget, the instance is
# classified as 'easy' and Presolve is disabled for the main solve.
PROBE_TIME_LIMIT       = 30.0
COMPLEXITY_NODE_THRESHOLD = 500

# Pool quality filter: only retain solutions within 10% of the best bound.
POOL_GAP_FILTER = 0.10

# Callback buffer limit: flush to CSV when the buffer reaches this size.
# For instances with 10,000+ variables, 500 entries ≈ 40 MB in RAM.
BUFFER_LIMIT_INCUMBENTS = 500
BUFFER_LIMIT_NODES      = 500


# ==========================================
# DATA CLASSES FOR STRUCTURED STORAGE
# ==========================================

@dataclass
class ModelFeatures:
    """Features extracted from a Gurobi model."""
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
    """
    Extract topology and coefficient features from a Gurobi model.
    Always call this on the ORIGINAL model before any solve so that
    variable indices align with solution vectors returned by Gurobi
    (which are always mapped back to the original model space).
    """
    vars_list   = model.getVars()
    constrs     = model.getConstrs()

    var_types      = np.array([v.VType for v in vars_list])
    var_obj_coeffs = np.array([v.Obj   for v in vars_list])
    var_lb         = np.array([v.LB    for v in vars_list])
    var_ub         = np.array([v.UB    for v in vars_list])
    var_names      = [v.VarName for v in vars_list]

    num_binary     = int(np.sum(var_types == GRB.BINARY))
    num_integer    = int(np.sum(var_types == GRB.INTEGER))
    num_continuous = int(np.sum(var_types == GRB.CONTINUOUS))

    constr_senses = np.array([c.Sense      for c in constrs])
    constr_rhs    = np.array([c.RHS        for c in constrs])
    constr_names  = [c.ConstrName          for c in constrs]

    rows, cols, vals = [], [], []
    for i, constr in enumerate(constrs):
        row = model.getRow(constr)
        for j in range(row.size()):
            rows.append(i)
            cols.append(row.getVar(j).index)
            vals.append(row.getCoeff(j))

    constraint_matrix = {
        'row':  np.array(rows),
        'col':  np.array(cols),
        'data': np.array(vals)
    }

    return ModelFeatures(
        num_vars=len(vars_list),   num_constrs=len(constrs),
        num_binary=num_binary,     num_integer=num_integer,
        num_continuous=num_continuous, num_nonzeros=len(vals),
        var_types=var_types,       var_obj_coeffs=var_obj_coeffs,
        var_lb=var_lb,             var_ub=var_ub,
        var_names=var_names,       constr_senses=constr_senses,
        constr_rhs=constr_rhs,     constr_names=constr_names,
        constraint_matrix=constraint_matrix
    )


def extract_solution_features(model: gp.Model, node_count: int = 0,
                               solve_time: float = 0.0) -> Optional[SolutionFeatures]:
    """Extract the best solution found after model.optimize() has been called."""
    try:
        if model.SolCount == 0:
            return None

        vars_list        = model.getVars()
        solution_vector  = np.array([v.X for v in vars_list])
        obj_val          = float(model.ObjVal)

        try:
            mip_gap = float(model.MIPGap)
        except gp.GurobiError:
            mip_gap = 0.0

        try:
            bound = float(model.ObjBound)
        except gp.GurobiError:
            bound = None

        is_optimal  = (model.Status == GRB.OPTIMAL)
        is_feasible = (model.Status in [GRB.OPTIMAL, GRB.SUBOPTIMAL,
                                        GRB.SOLUTION_LIMIT])

        # Guard denominator: same convention used in MIPGap callback below.
        integrality_gap = None
        if bound is not None:
            denom = max(abs(obj_val), 1e-10)
            integrality_gap = abs(obj_val - bound) / denom

        return SolutionFeatures(
            objective_value=obj_val,    mip_gap=mip_gap,
            node_count=node_count,      solution_time=solve_time,
            solution_vector=solution_vector,
            is_feasible=is_feasible,    is_optimal=is_optimal,
            integrality_gap=integrality_gap, bound=bound
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
# ADAPTIVE PRESOLVE PROBE
# ==========================================

def classify_instance_complexity(model: gp.Model,
                                  env: gp.Env,
                                  probe_time: float = PROBE_TIME_LIMIT,
                                  node_threshold: int = COMPLEXITY_NODE_THRESHOLD
                                  ) -> Tuple[bool, int]:
    """
    Runs a short probe solve (with presolve enabled) to decide whether the
    instance is computationally 'hard' or 'easy'.

    Returns
    -------
    is_complex : bool
        True  -> instance is hard; use Presolve=-1 for the main solve so
                 Gurobi can reduce the search space and reach quality solutions.
        False -> instance is easy; use Presolve=0 for the main solve to slow
                 Gurobi down and capture more intermediate incumbents for the
                 GNN training labels.
    probe_node_count : int
        Number of B&B nodes explored during the probe. Stored in metadata.
    """
    probe_model = model.copy()
    try:
        probe_model.setParam('TimeLimit',    probe_time)
        probe_model.setParam('OutputFlag',   0)
        probe_model.setParam('Presolve',    -1)   # Automatic: let Gurobi reduce
        probe_model.setParam('Threads',      1)   # Keep probe cheap
        probe_model.optimize()
        probe_node_count = int(probe_model.NodeCount)
    except gp.GurobiError as e:
        print(f"  [WARNING] Probe solve failed: {e}. Defaulting to 'easy'.")
        probe_node_count = 0
    finally:
        probe_model.dispose()

    is_complex = (probe_node_count > node_threshold)
    return is_complex, probe_node_count


# ==========================================
# MEMORY-SAFE CALLBACK HANDLER
# ==========================================

class DataCollectionCallback:
    """
    Collects intermediate incumbents (MIPSOL) and node LP relaxations (MIPNODE)
    during the B&B solve. Data is buffered in memory and flushed to CSV files
    incrementally when the buffer reaches BUFFER_LIMIT entries.
    
    MIPSOL_PHASE filter: only Phase 1 (standard MIP search) incumbents are
    collected. Phase 0 (NoRel heuristic) and Phase 2 (solution improvement)
    are ignored because they do not represent B&B tree exploration behavior.
    """
    def __init__(self, model: gp.Model, instance_dir: str):
        self.model              = model
        self.vars               = model.getVars()
        self.instance_dir       = instance_dir
        self.start_time         = time.time()
        
        # In-memory buffers (cleared after each flush)
        self.incumbent_buffer: List[Dict] = []
        self.node_buffer:      List[Dict] = []
        
        # CSV file paths for incremental writing
        self.incumbents_csv = os.path.join(instance_dir, "incumbents_temp.csv")
        self.nodes_csv      = os.path.join(instance_dir, "nodes_temp.csv")
        
        # Total counters for statistics
        self.total_incumbents_written = 0
        self.total_nodes_written      = 0
        
        # Initialize CSV files with headers
        with open(self.incumbents_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['node', 'solution_count', 'objective', 'bound',
                           'mip_gap', 'time', 'solution_vector'])
        
        with open(self.nodes_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['node', 'bound', 'fractional_vars', 'time',
                           'relaxation_vector'])

    def _flush_incumbent_buffer(self):
        """Write incumbent buffer to CSV and clear the buffer."""
        if not self.incumbent_buffer:
            return
        
        with open(self.incumbents_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            for sol in self.incumbent_buffer:
                writer.writerow([
                    sol['node'],
                    sol['solution_count'],
                    sol['objective'],
                    sol['bound'],
                    sol['mip_gap'],
                    sol['time'],
                    json.dumps(sol['solution_vector'].tolist())  # Serialize as JSON
                ])
        
        self.total_incumbents_written += len(self.incumbent_buffer)
        self.incumbent_buffer.clear()
    
    def _flush_node_buffer(self):
        """Write node relaxation buffer to CSV and clear the buffer."""
        if not self.node_buffer:
            return
        
        with open(self.nodes_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            for node in self.node_buffer:
                writer.writerow([
                    node['node'],
                    node['bound'],
                    node['fractional_vars'],
                    node['time'],
                    json.dumps(node['relaxation_vector'].tolist())
                ])
        
        self.total_nodes_written += len(self.node_buffer)
        self.node_buffer.clear()

    def __call__(self, model, where):
        current_time = time.time() - self.start_time

        if where == GRB.Callback.MIPSOL:
            # CRITICAL FILTER: only collect Phase 1 (standard MIP search) incumbents.
            # Phase 0 = NoRel heuristic (before tree search starts)
            # Phase 1 = standard B&B tree exploration (this is what we want)
            # Phase 2 = solution improvement phase (local search after optimality)
            try:
                phase = model.cbGet(GRB.Callback.MIPSOL_PHASE)
                if phase != 1:
                    return  # Skip Phase 0 and Phase 2 solutions
            except gp.GurobiError:
                # If MIPSOL_PHASE is not available, collect the solution anyway
                # (defensive: older Gurobi versions may not expose this attribute)
                pass
            
            sol_count  = model.cbGet(GRB.Callback.MIPSOL_SOLCNT)
            obj_val    = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            node_count = model.cbGet(GRB.Callback.MIPSOL_NODCNT)
            obj_bnd    = model.cbGet(GRB.Callback.MIPSOL_OBJBND)

            # Guard denominator against division by zero when obj_val == 0.
            mip_gap = abs(obj_val - obj_bnd) / max(abs(obj_val), 1e-10)

            sol_vals = model.cbGetSolution(self.vars)

            self.incumbent_buffer.append({
                'node':             int(node_count),
                'solution_count':   int(sol_count),
                'objective':        float(obj_val),
                'bound':            float(obj_bnd),
                'mip_gap':          float(mip_gap),
                'solution_vector':  np.array(sol_vals),
                'time':             current_time
            })
            
            # Flush if buffer is full
            if len(self.incumbent_buffer) >= BUFFER_LIMIT_INCUMBENTS:
                self._flush_incumbent_buffer()

        elif where == GRB.Callback.MIPNODE:
            status     = model.cbGet(GRB.Callback.MIPNODE_STATUS)
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
                    self.node_buffer.append({
                        'node':               int(node_count),
                        'bound':              float(obj_bnd),
                        'fractional_vars':    fractional_count,
                        'relaxation_vector':  np.array(rel_vals),
                        'time':               current_time
                    })
                    
                    # Flush if buffer is full
                    if len(self.node_buffer) >= BUFFER_LIMIT_NODES:
                        self._flush_node_buffer()
                        
                except gp.GurobiError:
                    # Node relaxation data not available at this node; skip.
                    pass
    
    def finalize(self):
        """
        Flush any remaining buffered data, convert CSV to parquet, and clean up.
        This MUST be called after model.optimize() completes.
        """
        # Flush remaining buffers
        self._flush_incumbent_buffer()
        self._flush_node_buffer()
        
        # Convert incumbents CSV to parquet
        if os.path.exists(self.incumbents_csv):
            try:
                df = pd.read_csv(self.incumbents_csv)
                if len(df) > 0:
                    # Deserialize solution_vector from JSON string back to list
                    df['solution_vector'] = df['solution_vector'].apply(json.loads)
                    df.to_parquet(
                        os.path.join(self.instance_dir, "incumbents.parquet"),
                        engine="pyarrow"
                    )
                os.remove(self.incumbents_csv)  # Delete temporary CSV
            except Exception as e:
                print(f"  [WARNING] Could not convert incumbents CSV to parquet: {e}")
        
        # Convert nodes CSV to parquet
        if os.path.exists(self.nodes_csv):
            try:
                df = pd.read_csv(self.nodes_csv)
                if len(df) > 0:
                    df['relaxation_vector'] = df['relaxation_vector'].apply(json.loads)
                    df.to_parquet(
                        os.path.join(self.instance_dir, "node_relaxations.parquet"),
                        engine="pyarrow"
                    )
                os.remove(self.nodes_csv)
            except Exception as e:
                print(f"  [WARNING] Could not convert nodes CSV to parquet: {e}")


# ==========================================
# MAIN PROCESSING LOGIC
# ==========================================

def process_single_instance(lp_file_path: str, output_dir: str,
                             env: gp.Env, time_limit: int,
                             use_existing_pickle: bool = True) -> bool:

    instance_name = (os.path.basename(lp_file_path)
                     .replace('.lp.gz', '').replace('.lp', ''))
    instance_dir  = os.path.join(output_dir, instance_name)
    os.makedirs(instance_dir, exist_ok=True)

    print(f"--- Processing: {instance_name} ---")

    try:
        # ------------------------------------------------------------------
        # STEP 1 — Read the original model
        # ------------------------------------------------------------------
        print("  [1/7] Reading model...")
        model = gp.read(lp_file_path, env=env)

        # ------------------------------------------------------------------
        # STEP 2 — Extract features from the ORIGINAL model.
        # ------------------------------------------------------------------
        print("  [2/7] Extracting original model features...")
        original_features = extract_model_features(model)

        with gzip.open(os.path.join(instance_dir, "original_features.pickle.gz"),
                       'wb') as f:
            pickle.dump({'model_features': original_features,
                         'timestamp': time.time()}, f)

        # ------------------------------------------------------------------
        # STEP 3 — Check for pre-existing benchmark solution
        # ------------------------------------------------------------------
        print("  [3/7] Checking for existing solution...")
        existing_solution = None
        if use_existing_pickle:
            pickle_dir  = os.path.dirname(os.path.dirname(lp_file_path))
            pickle_path = os.path.join(pickle_dir, 'Pickle',
                                       instance_name + '.pickle.gz')
            if not os.path.exists(pickle_path):
                pickle_path = os.path.join(pickle_dir, 'Pickle',
                                           instance_name + '.pickle')
            existing_solution = read_existing_pickle(pickle_path)
            if existing_solution:
                print(f"    Found existing solution with gap: "
                      f"{existing_solution[1]:.4f}")
            else:
                print(f"    [WARN] No benchmark pickle found at: {pickle_path}")

        # ------------------------------------------------------------------
        # STEP 4 — Adaptive presolve: probe the instance complexity.
        # ------------------------------------------------------------------
        print("  [4/7] Classifying instance complexity (probe solve)...")
        is_complex, probe_node_count = classify_instance_complexity(model, env)
        complexity_class = 'hard' if is_complex else 'easy'
        presolve_setting = -1 if is_complex else 0
        print(f"    Probe nodes explored: {probe_node_count} "
              f"-> complexity: '{complexity_class}' "
              f"-> Presolve={presolve_setting}")

        # ------------------------------------------------------------------
        # STEP 5 — Configure and solve
        # ------------------------------------------------------------------
        print(f"  [5/7] Solving with time limit {time_limit}s "
              f"(Presolve={presolve_setting})...")
        model_to_solve = model.copy()
        model_to_solve.setParam('Presolve',        presolve_setting)
        model_to_solve.setParam('PoolSearchMode',  1)
        model_to_solve.setParam('PoolSolutions',   20)
        model_to_solve.setParam('PoolGap',         POOL_GAP_FILTER)
        model_to_solve.setParam('Symmetry',        0)
        model_to_solve.setParam('DualReductions',  0)
        model_to_solve.setParam('TimeLimit',       time_limit)

        callback   = DataCollectionCallback(model_to_solve, instance_dir)
        start_time = time.time()
        model_to_solve.optimize(callback)
        solve_time = time.time() - start_time
        
        # CRITICAL: finalize the callback to flush remaining buffers and
        # convert CSV to parquet. Without this call, data is lost.
        callback.finalize()

        # ------------------------------------------------------------------
        # STEP 6 — Extract solution pool
        # ------------------------------------------------------------------
        print("  [6/7] Extracting solution pool...")
        solution_pool = []
        if model_to_solve.SolCount > 0:
            pool_vars = model_to_solve.getVars()
            for n in range(model_to_solve.SolCount):
                try:
                    model_to_solve.Params.SolutionNumber = n
                    pool_obj      = float(model_to_solve.PoolObjVal)
                    pool_solution = np.array([v.PoolNX for v in pool_vars])
                    solution_pool.append({
                        'pool_index':      n,
                        'objective':       pool_obj,
                        'solution_vector': pool_solution
                    })
                except gp.GurobiError as e:
                    print(f"  [WARNING] Could not read pool solution {n}: {e}")
                    break

        # ------------------------------------------------------------------
        # STEP 7 — Persist results
        # ------------------------------------------------------------------
        print("  [7/7] Saving results...")
        final_solution = extract_solution_features(
            model_to_solve, int(model_to_solve.NodeCount), solve_time)

        solution_data = {
            'final_solution':               final_solution,
            'solution_pool':                solution_pool,
            'existing_benchmark_solution':  existing_solution
        }

        with gzip.open(os.path.join(instance_dir, "solutions.pickle.gz"),
                       'wb') as f:
            pickle.dump(solution_data, f)

        metadata = {
            'instance':                instance_name,
            'status':                  model_to_solve.Status,
            'status_name': {
                1: 'LOADED',      2: 'OPTIMAL',    3: 'INFEASIBLE',
                4: 'INF_OR_UNBD', 5: 'UNBOUNDED',  9: 'TIME_LIMIT'
            }.get(model_to_solve.Status, 'UNKNOWN'),
            'runtime':                 solve_time,
            'mip_gap':                 getattr(model_to_solve, 'MIPGap',    0.0),
            'node_count':              getattr(model_to_solve, 'NodeCount', 0),
            'num_solutions_found':     model_to_solve.SolCount,
            'num_incumbents_collected':callback.total_incumbents_written,
            'num_nodes_collected':     callback.total_nodes_written,
            'pool_solutions_found':    len(solution_pool),
            'presolve_setting':        presolve_setting,
            'complexity_class':        complexity_class,
            'probe_node_count':        probe_node_count,
        }

        if final_solution:
            metadata['objective_value'] = final_solution.objective_value
            metadata['is_optimal']      = final_solution.is_optimal

        with open(os.path.join(instance_dir, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)

        model_to_solve.dispose()
        model.dispose()

        print(f"  [OK] Successfully processed {instance_name} "
              f"({callback.total_incumbents_written} incumbents, "
              f"{len(solution_pool)} pool solutions)")
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
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'([0-9]+)', s)]


def main():
    parser = argparse.ArgumentParser(description="CFL GNN Data Generator v5")
    parser.add_argument('--categories',  nargs='+',
                        default=["CFL_easy_instance"])
    parser.add_argument('--start_idx',   type=int,   default=0)
    parser.add_argument('--end_idx',     type=int,   default=30)
    parser.add_argument('--time_limit',  type=int,   default=60)
    parser.add_argument('--input_dir',   type=str,
                        default="/home/vrcelestino/discodatos/cfl-gurobi-gnn"
                                "/data/raw/MILPBench/CFL")
    parser.add_argument('--output_dir',  type=str,
                        default="/raid/vrcelestino/data/cfl-gurobi-gnn"
                                "/data/intermediate_lps")
    parser.add_argument('--threads',     type=int,   default=None)
    parser.add_argument('--probe_time',  type=float,
                        default=PROBE_TIME_LIMIT,
                        help="Probe solve time budget in seconds (default: "
                             f"{PROBE_TIME_LIMIT})")
    parser.add_argument('--complexity_threshold', type=int,
                        default=COMPLEXITY_NODE_THRESHOLD,
                        help="B&B node count threshold separating easy/hard "
                             f"instances (default: {COMPLEXITY_NODE_THRESHOLD})")
    args = parser.parse_args()

    print("=" * 60)
    print("CFL GNN Data Generator v5 (Memory-Safe + MIPSOL_PHASE Filter)")
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
        for f in sliced_files:
            file_paths.append((category, f))

    if not file_paths:
        print("[WARNING] No files found matching criteria.")
        return

    env = gp.Env(empty=True)
    if "WLSACCESSID" in os.environ:
        env.setParam("WLSACCESSID", os.environ["WLSACCESSID"])
    if "WLSSECRET" in os.environ:
        env.setParam("WLSSECRET",   os.environ["WLSSECRET"])
    if "LICENSEID" in os.environ:
        env.setParam("LICENSEID",   int(os.environ["LICENSEID"]))

    num_threads = (args.threads
                   if args.threads is not None
                   else int(os.environ.get("SLURM_CPUS_PER_TASK", 1)))
    env.setParam("Threads",      num_threads)
    env.setParam("LogToConsole", 0)
    env.start()

    success_count = 0
    failure_count = 0

    for i, (category, file_path) in enumerate(file_paths, 1):
        print(f"\n[{i}/{len(file_paths)}] Category: {category}")
        category_out_dir = os.path.join(args.output_dir, category)
        success = process_single_instance(
            file_path, category_out_dir, env, args.time_limit,
            use_existing_pickle=True
        )
        if success:
            success_count += 1
        else:
            failure_count += 1

    print("\n" + "=" * 60)
    print(f"Completed: {success_count} succeeded, {failure_count} failed "
          f"(total: {len(file_paths)})")
    print("=" * 60)
    env.dispose()


if __name__ == "__main__":
    main()
