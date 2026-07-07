"""
Gurobi HPC Parametric Runner v2
================================
Executes Gurobi on MILPBench CFL instances from a Slurm HPC environment.
Incorporates all Phase 1 architectural decisions:

  v2 changes vs v1 (gurobi_hpc_runner.py):
  -----------------------------------------
  1. PoolSearchMode=2 and PoolSolutions removed from environment level;
     set at model level as PoolSearchMode=1 (collect incumbents as B&B
     by-product, not exhaustive N-best enumeration).
  2. Adaptive presolve strategy:
       - Easy instances (probe_node_count <= complexity_threshold): Presolve=0
         to slow Gurobi down and generate more intermediate incumbents.
       - Hard instances (probe_node_count > complexity_threshold): Presolve=-1
         to let Gurobi use all reductions for tractability.
  3. Step 4 ("presolved_features" extraction) removed. Features are extracted
     from the original model BEFORE any solve, named original_features.
  4. Deprecated v.Xn migrated to v.PoolNX; setParam("SolutionNumber") 
     migrated to Params.SolutionNumber (Gurobi 13.0 canonical pattern).
  5. --warm_start (single file) replaced by --hint_dir (directory).
     The runner automatically finds <instance_name>_gnn_hint.hnt.
     model.read() natively handles both .hnt and .mst formats.
  6. MIP gap formula unified: max(abs(obj_val), 1e-10) denominator in
     both callback and extract_solution_features.
  7. MIPSOL_PHASE filter: only Phase 1 incumbents (true B&B tree solutions)
     are stored as training labels. Phase 0 (NoRel) and Phase 2 (post-opt)
     solutions are discarded.
  8. Symmetry=0 and DualReductions=0 added to model parameters.
  9. PoolGap=0.10 set at model level to filter low-quality pool solutions.
 10. Complexity metadata (presolve_setting, complexity_class, probe_node_count)
     logged to metadata.json for downstream dataset stratification.
 11. Bare except blocks replaced with gp.GurobiError where appropriate.
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
from typing import Dict, List, Optional
import time
import gzip

# ============================================================================
# DATA CLASSES FOR STRUCTURED STORAGE
# ============================================================================

@dataclass
class ModelFeatures:
    """Stores all structural features of a MILP model."""
    num_vars:         int
    num_constrs:      int
    num_binary:       int
    num_integer:      int
    num_continuous:   int
    num_nonzeros:     int
    var_types:        np.ndarray
    var_obj_coeffs:   np.ndarray
    var_lb:           np.ndarray
    var_ub:           np.ndarray
    var_names:        List[str]
    constr_senses:    np.ndarray
    constr_rhs:       np.ndarray
    constr_names:     List[str]
    constraint_matrix: Dict[str, np.ndarray]

    def to_dict(self):
        return {k: v.tolist() if isinstance(v, np.ndarray) else v
                for k, v in asdict(self).items()
                if k != 'constraint_matrix'}


@dataclass
class SolutionFeatures:
    """Stores the final solution state of an optimized model."""
    objective_value:  float
    mip_gap:          float
    node_count:       int
    solution_time:    float
    solution_vector:  np.ndarray
    is_feasible:      bool
    is_optimal:       bool
    integrality_gap:  Optional[float] = None
    bound:            Optional[float] = None


# ============================================================================
# FEATURE EXTRACTION FUNCTIONS
# ============================================================================

def extract_model_features(model: gp.Model) -> ModelFeatures:
    """
    Extracts all structural features from a Gurobi model.
    Must be called on the ORIGINAL model before any solve or presolve.

    Args:
        model: A gurobipy Model object (unsolved, not presolved).

    Returns:
        ModelFeatures dataclass.
    """
    vars_list = model.getVars()
    constrs   = model.getConstrs()

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

    # Sparse constraint matrix in COO format
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
        num_continuous=num_continuous,
        num_nonzeros=len(vals),
        var_types=var_types,       var_obj_coeffs=var_obj_coeffs,
        var_lb=var_lb,             var_ub=var_ub,
        var_names=var_names,
        constr_senses=constr_senses,
        constr_rhs=constr_rhs,     constr_names=constr_names,
        constraint_matrix=constraint_matrix
    )


def extract_solution_features(model:      gp.Model,
                               node_count: int   = 0,
                               solve_time: float = 0.0) -> Optional[SolutionFeatures]:
    """
    Extracts the best solution found after optimization.

    Args:
        model      : Optimized gurobipy Model.
        node_count : B&B nodes explored (from model.NodeCount).
        solve_time : Wall-clock solve time in seconds.

    Returns:
        SolutionFeatures or None if no solution was found.
    """
    try:
        if model.SolCount == 0:
            return None

        vars_list       = model.getVars()
        solution_vector = np.array([v.X for v in vars_list])
        obj_val         = model.ObjVal

        try:
            mip_gap = model.MIPGap
        except gp.GurobiError:
            mip_gap = 0.0

        try:
            bound = model.ObjBound
        except gp.GurobiError:
            bound = None

        is_optimal  = (model.Status == GRB.OPTIMAL)
        is_feasible = model.Status in [GRB.OPTIMAL, GRB.SUBOPTIMAL,
                                       GRB.SOLUTION_LIMIT]

        # Unified robust MIP gap formula
        integrality_gap = None
        if bound is not None:
            integrality_gap = abs(obj_val - bound) / max(abs(obj_val), 1e-10)

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
    except gp.GurobiError as e:
        print(f"  [WARNING] Gurobi error extracting solution features: {e}")
        return None


# ============================================================================
# ADAPTIVE PRESOLVE: COMPLEXITY CLASSIFIER
# ============================================================================

def classify_instance_complexity(model:               gp.Model,
                                  env:                 gp.Env,
                                  probe_time_limit:    float = 30.0,
                                  complexity_threshold: int   = 500) -> dict:
    """
    Probes an instance with a short time limit to determine its computational
    complexity, which in turn controls the Presolve setting for the main solve.

    Decision rule:
        probe_node_count <= complexity_threshold --> 'easy'
            --> Presolve=0  (slow Gurobi to generate more intermediate incumbents)
        probe_node_count >  complexity_threshold --> 'hard'
            --> Presolve=-1 (use all reductions for tractability)

    Args:
        model                : Original gurobipy Model (not modified).
        env                  : Active gurobipy Env.
        probe_time_limit     : Wall-clock seconds for the probe solve.
        complexity_threshold : Node count boundary between easy and hard.

    Returns:
        dict with keys: presolve_setting (int), complexity_class (str),
                        probe_node_count (int), probe_obj_val (float or None).
    """
    probe_model = model.copy()
    probe_model.setParam('TimeLimit',   probe_time_limit)
    probe_model.setParam('OutputFlag',  0)
    probe_model.setParam('LogToConsole', 0)
    probe_model.optimize()

    probe_node_count = int(probe_model.NodeCount)
    probe_obj_val    = probe_model.ObjVal if probe_model.SolCount > 0 else None
    probe_model.dispose()

    if probe_node_count <= complexity_threshold:
        return {
            'presolve_setting':  0,
            'complexity_class':  'easy',
            'probe_node_count':  probe_node_count,
            'probe_obj_val':     probe_obj_val
        }
    else:
        return {
            'presolve_setting':  -1,
            'complexity_class':  'hard',
            'probe_node_count':  probe_node_count,
            'probe_obj_val':     probe_obj_val
        }


# ============================================================================
# CALLBACK: DATA COLLECTION DURING B&B
# ============================================================================

class DataCollectionCallback:
    """
    Gurobi callback that collects intermediate incumbents and node relaxations
    during B&B search.

    MIPSOL_PHASE filter:
        Only Phase 1 solutions (true B&B tree) are stored.
        Phase 0 (NoRel heuristic) and Phase 2 (post-optimality improvement)
        are discarded to ensure GNN training labels reflect B&B topology.
    """

    def __init__(self, model: gp.Model):
        self.model                = model
        self.vars                 = model.getVars()
        self.incumbent_solutions  = []
        self.node_relaxations     = []
        self.start_time           = time.time()

    def __call__(self, model: gp.Model, where: int):
        current_time = time.time() - self.start_time

        if where == GRB.Callback.MIPSOL:
            # --- Phase filter: skip NoRel (0) and post-opt (2) solutions ---
            phase = model.cbGet(GRB.Callback.MIPSOL_PHASE)
            if phase != 1:
                return

            sol_count = model.cbGet(GRB.Callback.MIPSOL_SOLCNT)
            obj_val   = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            node_count= model.cbGet(GRB.Callback.MIPSOL_NODCNT)
            obj_bnd   = model.cbGet(GRB.Callback.MIPSOL_OBJBND)

            # Unified robust MIP gap formula
            mip_gap   = abs(obj_val - obj_bnd) / max(abs(obj_val), 1e-10)

            sol_vals  = model.cbGetSolution(self.vars)

            self.incumbent_solutions.append({
                'node':             int(node_count),
                'solution_count':   int(sol_count),
                'objective':        float(obj_val),
                'bound':            float(obj_bnd),
                'mip_gap':          float(mip_gap),
                'phase':            int(phase),
                'solution_vector':  np.array(sol_vals),
                'time':             current_time
            })

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
                    self.node_relaxations.append({
                        'node':               int(node_count),
                        'bound':              float(obj_bnd),
                        'fractional_vars':    fractional_count,
                        'relaxation_vector':  np.array(rel_vals),
                        'time':               current_time
                    })
                except gp.GurobiError:
                    pass


# ============================================================================
# MAIN INSTANCE PROCESSING LOGIC
# ============================================================================

def process_single_instance(lp_file_path: str,
                             output_dir:   str,
                             env:          gp.Env,
                             args:         argparse.Namespace) -> bool:
    """
    Full pipeline for a single CFL instance:
      1. Read model
      2. Extract original model features (BEFORE any solve)
      3. Classify complexity via probe solve
      4. Configure model-level parameters (adaptive presolve, pool, hints)
      5. Solve with callback
      6. Extract solution pool using v.PoolNX (Gurobi 13.0 canonical)
      7. Save all artifacts: pickle, parquet, metadata.json

    Args:
        lp_file_path : Path to .lp or .lp.gz instance.
        output_dir   : Base output directory for this instance's artifacts.
        env          : Active gurobipy Env.
        args         : Parsed CLI arguments.

    Returns:
        True on success, False on any failure.
    """
    instance_name = (os.path.basename(lp_file_path)
                     .replace('.lp.gz', '')
                     .replace('.lp',    ''))
    instance_dir = os.path.join(output_dir, instance_name)
    os.makedirs(instance_dir, exist_ok=True)

    print(f"--- Processing: {instance_name} ---")

    try:
        # ------------------------------------------------------------------
        # Step 1: Read original model
        # ------------------------------------------------------------------
        print("  [1/6] Reading model...")
        model = gp.read(lp_file_path, env=env)

        # ------------------------------------------------------------------
        # Step 2: Extract and save original model features
        # Feature extraction MUST happen before any copy, solve, or presolve
        # to guarantee variable index alignment with v.PoolNX solution vectors.
        # ------------------------------------------------------------------
        print("  [2/6] Extracting original model features...")
        original_features = extract_model_features(model)

        with gzip.open(os.path.join(instance_dir,
                                    "original_features.pickle.gz"), 'wb') as fh:
            pickle.dump({'model_features': original_features,
                         'timestamp': time.time()}, fh)

        # ------------------------------------------------------------------
        # Step 3: Adaptive presolve classification
        # ------------------------------------------------------------------
        print(f"  [3/6] Classifying instance complexity "
              f"(probe={args.probe_time}s, threshold={args.complexity_threshold} nodes)...")
        complexity_info = classify_instance_complexity(
            model,
            env,
            probe_time_limit     = args.probe_time,
            complexity_threshold = args.complexity_threshold
        )
        presolve_setting = complexity_info['presolve_setting']
        complexity_class = complexity_info['complexity_class']
        print(f"        --> {complexity_class.upper()}  "
              f"(nodes={complexity_info['probe_node_count']}, "
              f"Presolve={'OFF' if presolve_setting == 0 else 'AUTO'})")

        # ------------------------------------------------------------------
        # Step 4: Configure model for main solve
        # All pool/presolve parameters set at MODEL level (never environment).
        # ------------------------------------------------------------------
        print(f"  [4/6] Configuring solver "
              f"(Presolve={presolve_setting}, Method={args.method}, "
              f"MIPFocus={args.mipfocus})...")
        model_to_solve = model.copy()

        # --- Core solver parameters ---
        model_to_solve.setParam('Presolve',        presolve_setting)
        model_to_solve.setParam('Method',           args.method)
        model_to_solve.setParam('Heuristics',       args.heuristics)
        model_to_solve.setParam('MIPFocus',         args.mipfocus)
        model_to_solve.setParam('TimeLimit',        args.time_limit)
        model_to_solve.setParam('OutputFlag',       0)
        model_to_solve.setParam('LogToConsole',     0)

        # --- Solution pool: collect incumbents as B&B by-product ---
        model_to_solve.setParam('PoolSearchMode',   1)    # collect along the way
        model_to_solve.setParam('PoolSolutions',    args.pool_size)
        model_to_solve.setParam('PoolGap',          args.pool_gap)

        # --- Required for diverse pool: disable solution-space pruning ---
        model_to_solve.setParam('Symmetry',         0)
        model_to_solve.setParam('DualReductions',   0)

        # --- Variable Hints injection (directory-based lookup) ---
        if args.hint_dir:
            hint_path = os.path.join(args.hint_dir,
                                     f"{instance_name}_gnn_hint.hnt")
            if os.path.exists(hint_path):
                model_to_solve.read(hint_path)
                print(f"  [+] Loaded variable hints: {os.path.basename(hint_path)}")
            else:
                print(f"  [INFO] No hint file found for {instance_name} — "
                      f"running without hints.")

        # ------------------------------------------------------------------
        # Step 5: Solve with callback
        # ------------------------------------------------------------------
        print(f"  [5/6] Solving (TimeLimit={args.time_limit}s)...")
        callback   = DataCollectionCallback(model_to_solve)
        start_time = time.time()
        model_to_solve.optimize(callback)
        solve_time = time.time() - start_time

        # ------------------------------------------------------------------
        # Step 6: Extract solution pool — Gurobi 13.0 canonical pattern
        # v.PoolNX replaces deprecated v.Xn; Params.SolutionNumber replaces
        # setParam("SolutionNumber", i).
        # ------------------------------------------------------------------
        print("  [6/6] Extracting solution pool and saving artifacts...")
        solution_pool = []

        if model_to_solve.SolCount > 0:
            pool_vars = model_to_solve.getVars()
            num_pool_solutions = min(model_to_solve.SolCount,
                                     model_to_solve.Params.PoolSolutions)

            for n in range(num_pool_solutions):
                try:
                    model_to_solve.Params.SolutionNumber = n  # Canonical 13.0 pattern
                    pool_obj      = model_to_solve.PoolObjVal
                    pool_solution = np.array([v.PoolNX for v in pool_vars])

                    solution_pool.append({
                        'pool_index':      n,
                        'objective':       float(pool_obj),
                        'solution_vector': pool_solution
                    })
                except gp.GurobiError as e:
                    print(f"  [WARNING] Pool solution {n} unavailable: {e}")
                    break

        # ------------------------------------------------------------------
        # Persist artifacts
        # ------------------------------------------------------------------
        final_solution = extract_solution_features(
            model_to_solve, model_to_solve.NodeCount, solve_time
        )

        solution_data = {
            'final_solution':               final_solution,
            'incumbent_solutions':          callback.incumbent_solutions,
            'node_relaxations':             callback.node_relaxations,
            'solution_pool':                solution_pool,
        }

        with gzip.open(os.path.join(instance_dir,
                                    "solutions.pickle.gz"), 'wb') as fh:
            pickle.dump(solution_data, fh)

        # -- Metadata JSON: includes complexity classification for stratification --
        status_map = {1: 'LOADED', 2: 'OPTIMAL', 3: 'INFEASIBLE',
                      4: 'INF_OR_UNBD', 5: 'UNBOUNDED', 9: 'TIME_LIMIT'}
        metadata = {
            'instance':                  instance_name,
            'status':                    model_to_solve.Status,
            'status_name':               status_map.get(model_to_solve.Status, 'UNKNOWN'),
            'runtime':                   solve_time,
            'mip_gap':                   getattr(model_to_solve, 'MIPGap',   0.0),
            'node_count':                getattr(model_to_solve, 'NodeCount', 0),
            'num_solutions_found':       model_to_solve.SolCount,
            'num_incumbents_collected':  len(callback.incumbent_solutions),
            'num_nodes_collected':       len(callback.node_relaxations),
            'pool_solutions_found':      len(solution_pool),
            # Complexity metadata for dataset stratification (R4)
            'presolve_setting':          presolve_setting,
            'complexity_class':          complexity_class,
            'probe_node_count':          complexity_info['probe_node_count'],
            'probe_obj_val':             complexity_info['probe_obj_val'],
        }

        if final_solution:
            metadata['objective_value'] = final_solution.objective_value
            metadata['is_optimal']      = final_solution.is_optimal

        with open(os.path.join(instance_dir, "metadata.json"), 'w') as fh:
            json.dump(metadata, fh, indent=2)

        # -- Incumbents parquet (Phase 1 B&B solutions only, per MIPSOL_PHASE filter) --
        if callback.incumbent_solutions:
            df_incumbents = pd.DataFrame([
                {
                    'node':             sol['node'],
                    'solution_count':   sol['solution_count'],
                    'objective':        sol['objective'],
                    'bound':            sol['bound'],
                    'mip_gap':          sol['mip_gap'],
                    'phase':            sol['phase'],
                    'time':             sol['time'],
                    'solution_vector':  sol['solution_vector'].tolist()
                }
                for sol in callback.incumbent_solutions
            ])
            df_incumbents.to_parquet(
                os.path.join(instance_dir, "incumbents.parquet"),
                engine="pyarrow"
            )

        # -- Node relaxations parquet --
        if callback.node_relaxations:
            df_nodes = pd.DataFrame([
                {
                    'node':              node['node'],
                    'bound':             node['bound'],
                    'fractional_vars':   node['fractional_vars'],
                    'time':              node['time'],
                    'relaxation_vector': node['relaxation_vector'].tolist()
                }
                for node in callback.node_relaxations
            ])
            df_nodes.to_parquet(
                os.path.join(instance_dir, "node_relaxations.parquet"),
                engine="pyarrow"
            )

        model_to_solve.dispose()
        model.dispose()

        print(f"  OK  {instance_name} | status={metadata['status_name']} | "
              f"incumbents={len(callback.incumbent_solutions)} | "
              f"pool={len(solution_pool)} | {solve_time:.1f}s")
        return True

    except gp.GurobiError as e:
        print(f"  [GUROBI ERROR] {instance_name}: {e}")
        return False
    except Exception as e:
        print(f"  [ERROR] {instance_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def natural_sort_key(s: str):
    """Natural sort for filenames with numeric suffixes."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]


def main():
    parser = argparse.ArgumentParser(
        description="Gurobi HPC Parametric Runner v2 — Neural Diving Pipeline"
    )

    # --- Instance selection ---
    parser.add_argument('--categories',  nargs='+',
                        default=["CFL_easy_instance"],
                        help="MILPBench category subdirectories to process.")
    parser.add_argument('--start_idx',   type=int, default=0,
                        help="Start index within sorted file list (inclusive).")
    parser.add_argument('--end_idx',     type=int, default=30,
                        help="End index within sorted file list (exclusive).")

    # --- I/O paths ---
    parser.add_argument('--input_dir',   type=str,
                        default="/home/vrcelestino/discodatos/cfl-gurobi-gnn/data/raw/MILPBench/CFL",
                        help="Root directory containing category subdirectories.")
    parser.add_argument('--output_dir',  type=str,
                        default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps",
                        help="Root directory for output artifacts.")

    # --- Warm start / hints ---
    parser.add_argument('--hint_dir',    type=str, default=None,
                        help="Directory containing <instance_name>_gnn_hint.hnt files. "
                             "The runner automatically matches by instance name. "
                             "Supports both .hnt (Variable Hints) and .mst (MIP Start) "
                             "formats via model.read().")

    # --- Solver parameters ---
    parser.add_argument('--time_limit',  type=int,   default=60,
                        help="Main solve time limit in seconds.")
    parser.add_argument('--threads',     type=int,   default=None,
                        help="Number of threads. None reads SLURM_CPUS_PER_TASK.")
    parser.add_argument('--method',      type=int,   default=-1,
                        help="-1: Auto, 0: Primal Simplex, 1: Dual Simplex, "
                             "2: Barrier, 3: Concurrent.")
    parser.add_argument('--heuristics',  type=float, default=0.05,
                        help="Fraction of time for Gurobi heuristics [0.0, 1.0].")
    parser.add_argument('--mipfocus',    type=int,   default=0,
                        help="0: Balanced, 1: Feasibility, 2: Optimality, 3: Bound.")

    # --- Adaptive presolve / complexity ---
    parser.add_argument('--probe_time',            type=float, default=30.0,
                        help="Probe solve time limit (seconds) for complexity "
                             "classification.")
    parser.add_argument('--complexity_threshold',  type=int,   default=500,
                        help="Node count boundary: below=easy (Presolve=0), "
                             "above=hard (Presolve=-1).")

    # --- Solution pool ---
    parser.add_argument('--pool_size',   type=int,   default=20,
                        help="Maximum number of solutions to retain in pool "
                             "(PoolSolutions parameter).")
    parser.add_argument('--pool_gap',    type=float, default=0.10,
                        help="PoolGap: discard solutions more than this fraction "
                             "worse than the best bound. Default 0.10 = 10%.")

    args = parser.parse_args()

    print("=" * 70)
    print(" Gurobi HPC Parametric Runner v2  |  Neural Diving Pipeline")
    print("=" * 70)
    print(f"  Categories     : {args.categories}")
    print(f"  Index range    : [{args.start_idx}, {args.end_idx})")
    print(f"  Time limit     : {args.time_limit}s  |  Pool size: {args.pool_size}")
    print(f"  Probe time     : {args.probe_time}s  |  Threshold: {args.complexity_threshold} nodes")
    print(f"  Pool gap filter: {args.pool_gap*100:.0f}%")
    print(f"  Hint directory : {args.hint_dir or 'None (running without hints)'}")
    print("=" * 70)

    os.makedirs(args.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Collect file paths
    # ------------------------------------------------------------------
    file_paths = []
    for category in args.categories:
        for ext in ('*.lp.gz', '*.lp'):
            pattern = os.path.join(args.input_dir, category, "LP", ext)
            category_files = glob.glob(pattern)
            if category_files:
                break
        category_files.sort(key=natural_sort_key)
        sliced = category_files[args.start_idx:args.end_idx]
        for f in sliced:
            file_paths.append((category, f))

    if not file_paths:
        print("[WARNING] No files found matching the specified criteria.")
        return

    print(f"\nTotal instances to process: {len(file_paths)}\n")

    # ------------------------------------------------------------------
    # Create Gurobi environment — WLS credentials from environment variables
    # PoolSearchMode and PoolSolutions are NOT set here (model level only)
    # ------------------------------------------------------------------
    with gp.Env(empty=True) as env:
        if "WLSACCESSID" in os.environ:
            env.setParam("WLSACCESSID", os.environ["WLSACCESSID"])
        if "WLSSECRET"   in os.environ:
            env.setParam("WLSSECRET",   os.environ["WLSSECRET"])
        if "LICENSEID"   in os.environ:
            env.setParam("LICENSEID",   int(os.environ["LICENSEID"]))

        num_threads = (args.threads if args.threads is not None
                       else int(os.environ.get("SLURM_CPUS_PER_TASK", 1)))
        env.setParam("Threads",      num_threads)
        env.setParam("LogToConsole", 0)
        env.start()

        print(f"Gurobi environment started — {num_threads} thread(s)\n")

        success_count = 0
        failure_count = 0

        for i, (category, file_path) in enumerate(file_paths, 1):
            print(f"\n[{i}/{len(file_paths)}] Category: {category}")
            category_out_dir = os.path.join(args.output_dir, category)
            success = process_single_instance(
                file_path, category_out_dir, env, args
            )
            if success: success_count += 1
            else:       failure_count += 1

    print("\n" + "=" * 70)
    print(f"  Run complete: {success_count} succeeded, "
          f"{failure_count} failed  "
          f"(total: {len(file_paths)})")
    print("=" * 70)


if __name__ == "__main__":
    main()
