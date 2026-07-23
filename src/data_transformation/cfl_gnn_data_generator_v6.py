"""
CFL GNN Data Generator - Enhanced Phase 1 with Full Validation (v6_enhanced_fixed)
====================================================================================
CRITICAL FIX: Gurobi 13.0 API compatibility - changed v.Xn to v.PoolNX (line 434)

Enhancements over v6:
  [E1] REAL-TIME PROGRESS TRACKING: Incumbent logging now shows total_incumbents_written
       to track buffer flush cycles during long solves (critical for 3600s hard instances).
  [E2] NODE RELAXATION VALIDATION: Filters out corrupted node relaxation vectors before
       parquet write, preventing LP bound violations in Phase 2 ETL.
  [E3] POST-WRITE VALIDATION: finalize() validates that written parquet files are readable
       and have the expected row count, catching ParquetWriter crashes immediately.

All v6 fixes preserved:
  - Direct PyArrow ParquetWriter (no CSV intermediate)
  - Dynamic variable fetching (prevents stale pointer bug)
  - Strict length validation before write
  - Trivial incumbent sanity checks (>95% ones warning)
  - MIPSOL_PHASE == 1 filter
  
API MIGRATION (Gurobi 12.x → 13.0):
  - v.Xn is DEPRECATED in Gurobi 13.0
  - Use v.PoolNX (pool solution by variable index)
"""

import os
import glob
import re
import argparse
import json
import pickle
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import gurobipy as gp
from gurobipy import GRB
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import time
import gzip
import logging

# ==========================================
# CONSTANTS
# ==========================================

PROBE_TIME_LIMIT          = 30.0
COMPLEXITY_NODE_THRESHOLD = 500
POOL_GAP_FILTER           = 0.10
BUFFER_LIMIT_INCUMBENTS   = 500
BUFFER_LIMIT_NODES        = 500


# ==========================================
# LOGGING CONFIGURATION
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# ==========================================
# DATA CLASSES
# ==========================================

@dataclass
class ModelFeatures:
    """Topology features extracted from the original MILP model before any solve."""
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
    """Features extracted from a feasible solution."""
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
    Extract topology features from the ORIGINAL model before any solve.
    This captures the problem structure independent of presolve or solve parameters.
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

    # Extract sparse constraint matrix (COO format)
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
        num_vars=len(vars_list),       num_constrs=len(constrs),
        num_binary=num_binary,         num_integer=num_integer,
        num_continuous=num_continuous, num_nonzeros=len(vals),
        var_types=var_types,           var_obj_coeffs=var_obj_coeffs,
        var_lb=var_lb,                 var_ub=var_ub,
        var_names=var_names,           constr_senses=constr_senses,
        constr_rhs=constr_rhs,         constr_names=constr_names,
        constraint_matrix=constraint_matrix
    )

def extract_solution_features(model: gp.Model, node_count: int = 0,
                               solve_time: float = 0.0) -> Optional[SolutionFeatures]:
    """
    Extract solution features from a solved model.
    Returns None if no feasible solution exists.
    """
    try:
        if model.SolCount == 0:
            return None
            
        vars_list = model.getVars()
        solution_vector = np.array([v.X for v in vars_list])
        obj_val = float(model.ObjVal)
        
        try:
            mip_gap = float(model.MIPGap)
        except gp.GurobiError:
            mip_gap = 0.0
            
        try:
            bound = float(model.ObjBound)
        except gp.GurobiError:
            bound = None
        
        is_optimal  = (model.Status == GRB.OPTIMAL)
        is_feasible = (model.Status in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.SOLUTION_LIMIT])
        
        integrality_gap = None
        if bound is not None:
            integrality_gap = abs(obj_val - bound) / max(abs(obj_val), 1e-10)

        return SolutionFeatures(
            objective_value=obj_val, mip_gap=mip_gap,
            node_count=node_count, solution_time=solve_time,
            solution_vector=solution_vector,
            is_feasible=is_feasible, is_optimal=is_optimal,
            integrality_gap=integrality_gap, bound=bound
        )
    except Exception as e:
        logging.warning(f"Could not extract solution features: {e}")
        return None


# ==========================================
# ADAPTIVE PRESOLVE PROBE
# ==========================================

def classify_instance_complexity(model: gp.Model, env: gp.Env,
                                  probe_time: float = PROBE_TIME_LIMIT,
                                  node_threshold: int = COMPLEXITY_NODE_THRESHOLD
                                  ) -> Tuple[bool, int]:
    """
    Runs a short probe solve to classify instance complexity.
    
    Returns:
        (is_complex, probe_node_count)
        
    If probe_node_count > node_threshold, the instance is classified as 'hard'
    and will be solved with Presolve=-1 (automatic). Otherwise, 'easy' with Presolve=0
    to collect more diverse training labels.
    """
    probe_model = model.copy()
    probe_node_count = 0
    
    try:
        probe_model.setParam('TimeLimit', probe_time)
        probe_model.setParam('OutputFlag', 0)
        probe_model.setParam('Presolve', -1)
        probe_model.setParam('Threads', 1)
        probe_model.optimize()
        probe_node_count = int(probe_model.NodeCount)
    except gp.GurobiError as e:
        logging.warning(f"Probe solve failed: {e}")
        probe_node_count = 0
    finally:
        probe_model.dispose()

    is_complex = (probe_node_count > node_threshold)
    return is_complex, probe_node_count


# ==========================================
# MEMORY-SAFE CALLBACK HANDLER (v6_enhanced)
# ==========================================

class DataCollectionCallback:
    """
    Memory-safe callback that collects incumbent solutions and node relaxations
    during Gurobi's Branch-and-Bound search.
    
    Key features (v6_enhanced):
      - Direct PyArrow ParquetWriter appending (no CSV intermediate)
      - Strict vector length validation before write
      - Real-time progress tracking (total flushed count)
      - Node relaxation validation with filtering
      - Post-write validation in finalize()
    """
    
    def __init__(self, model: gp.Model, instance_dir: str):
        self.model = model
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Store expected num_vars for strict validation
        self.num_vars = len(model.getVars())
        
        self.instance_dir = instance_dir
        self.start_time = time.time()
        
        # In-memory buffers
        self.incumbent_buffer: List[Dict] = []
        self.node_buffer:      List[Dict] = []
        
        # Parquet output paths
        self.incumbents_parquet        = os.path.join(instance_dir, "incumbents.parquet")
        self.node_relaxations_parquet  = os.path.join(instance_dir, "node_relaxations.parquet")
        
        # PyArrow ParquetWriters (initialized on first flush)
        self.inc_writer  = None
        self.node_writer = None
        
        # [E1] Progress counters for real-time tracking
        self.total_incumbents_written = 0
        self.total_nodes_written      = 0

    def _flush_incumbent_buffer(self):
        """
        Writes valid incumbent solutions to PyArrow Parquet writer.
        Validates vector length and discards corrupted entries.
        """
        if not self.incumbent_buffer:
            return
        
        # Strict validation: filter out corrupted solutions
        valid_sols = []
        for sol in self.incumbent_buffer:
            if len(sol['solution_vector']) != self.num_vars:
                self.logger.error(
                    f"  [CRITICAL] Incumbent solution length mismatch: "
                    f"expected {self.num_vars}, got {len(sol['solution_vector'])}. SKIPPING."
                )
                continue
            valid_sols.append(sol)
        
        if not valid_sols:
            self.incumbent_buffer.clear()
            return
        
        # Convert to pandas DataFrame then PyArrow Table
        df = pd.DataFrame(valid_sols)
        table = pa.Table.from_pandas(df)
        
        # Direct Parquet append via PyArrow (no CSV intermediate)
        if self.inc_writer is None:
            self.inc_writer = pq.ParquetWriter(
                self.incumbents_parquet,
                table.schema,
                compression='snappy'
            )
        self.inc_writer.write_table(table)
        
        # [E1] Update progress counter
        self.total_incumbents_written += len(valid_sols)
        self.incumbent_buffer.clear()
        
        self.logger.info(
            f"  [FLUSH] Wrote {len(valid_sols)} incumbents to parquet "
            f"(total written: {self.total_incumbents_written})"
        )
    
    def _flush_node_buffer(self):
        """
        [E2] ENHANCEMENT: Validates node relaxation vector lengths before write.
        Filters out corrupted entries to prevent LP bound violations in Phase 2.
        """
        if not self.node_buffer:
            return
        
        # [E2] Strict validation with filtering
        valid_nodes = []
        for idx, node_rec in enumerate(self.node_buffer):
            if len(node_rec['relaxation_vector']) != self.num_vars:
                self.logger.error(
                    f"  [CRITICAL] Node relaxation {idx} length mismatch: "
                    f"expected {self.num_vars}, got {len(node_rec['relaxation_vector'])}. SKIPPING."
                )
                continue  # Skip corrupted node data
            valid_nodes.append(node_rec)
        
        if len(valid_nodes) != len(self.node_buffer):
            self.logger.warning(
                f"  [WARN] Filtered out {len(self.node_buffer) - len(valid_nodes)} "
                f"corrupted node relaxation entries"
            )
        
        if not valid_nodes:
            self.node_buffer.clear()
            return
        
        df = pd.DataFrame(valid_nodes)
        table = pa.Table.from_pandas(df)
        
        if self.node_writer is None:
            self.node_writer = pq.ParquetWriter(
                self.node_relaxations_parquet,
                table.schema,
                compression='snappy'
            )
        self.node_writer.write_table(table)
        
        self.total_nodes_written += len(valid_nodes)
        self.node_buffer.clear()
        
        self.logger.info(
            f"  [FLUSH] Wrote {len(valid_nodes)} node relaxations to parquet "
            f"(total written: {self.total_nodes_written})"
        )

    def __call__(self, model, where):
        """
        Gurobi callback entry point.
        Captures incumbent solutions (MIPSOL) and node relaxations (MIPNODE).
        """
        current_time = time.time() - self.start_time

        if where == GRB.Callback.MIPSOL:
            # Filter: only collect Phase 1 incumbents (true B&B search solutions)
            try:
                phase = model.cbGet(GRB.Callback.MIPSOL_PHASE)
                if phase != 1:
                    return  # Skip Phase 0 (heuristics) and Phase 2 (post-processing)
            except gp.GurobiError:
                pass
            
            # Dynamic variable fetching: prevents stale pointer bug
            vars_list = model.getVars()
            sol_vals = model.cbGetSolution(vars_list)
            
            sol_count  = model.cbGet(GRB.Callback.MIPSOL_SOLCNT)
            obj_val    = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            node_count = model.cbGet(GRB.Callback.MIPSOL_NODCNT)
            obj_bnd    = model.cbGet(GRB.Callback.MIPSOL_OBJBND)
            mip_gap    = abs(obj_val - obj_bnd) / max(abs(obj_val), 1e-10)
            
            sol_array = np.array(sol_vals)
            n_zeros = (sol_array == 0.0).sum()
            n_ones  = (sol_array == 1.0).sum()
            n_frac  = len(sol_array) - n_zeros - n_ones
            
            # Sanity check: detect trivial incumbent (all 1.0s, upper bound capture bug)
            num_binary = sum(1 for v in vars_list if v.VType == GRB.BINARY)
            if num_binary > 0:
                pct_ones = 100.0 * n_ones / len(sol_array)
                if pct_ones > 95.0:
                    self.logger.warning(
                        f"  [WARN] Suspicious solution at node {int(node_count)}: "
                        f"{pct_ones:.1f}% ones (possible UB capture bug)"
                    )
            
            # [E1] ENHANCEMENT: Real-time progress logging with total flushed count
            self.logger.info(
                f"  [INCUMBENT {int(sol_count)}] Buffered (total flushed: {self.total_incumbents_written}) | "
                f"obj={obj_val:.4f}, gap={mip_gap*100:.2f}%, node={int(node_count)} | "
                f"vec: {n_zeros}×0 + {n_ones}×1 + {n_frac}×frac = {len(sol_array)} total"
            )

            self.incumbent_buffer.append({
                'node':             int(node_count),
                'solution_count':   int(sol_count),
                'objective':        float(obj_val),
                'bound':            float(obj_bnd),
                'mip_gap':          float(mip_gap),
                'solution_vector':  sol_array,
                'time':             current_time
            })
            
            # Flush when buffer limit is reached
            if len(self.incumbent_buffer) >= BUFFER_LIMIT_INCUMBENTS:
                self._flush_incumbent_buffer()

        elif where == GRB.Callback.MIPNODE:
            status = model.cbGet(GRB.Callback.MIPNODE_STATUS)
            if status == GRB.OPTIMAL:
                node_count = model.cbGet(GRB.Callback.MIPNODE_NODCNT)
                obj_bnd = model.cbGet(GRB.Callback.MIPNODE_OBJBND)
                
                try:
                    # Dynamic variable fetching (consistent with MIPSOL)
                    vars_list = model.getVars()
                    rel_vals = model.cbGetNodeRel(vars_list)
                    
                    # Count fractional discrete variables in the LP relaxation
                    fractional_count = sum(
                        1 for i, v in enumerate(vars_list)
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
                    
                    if len(self.node_buffer) >= BUFFER_LIMIT_NODES:
                        self._flush_node_buffer()
                        
                except gp.GurobiError:
                    pass

    def finalize(self):
        """
        [E3] ENHANCEMENT: Flushes remaining buffers, closes writers, and validates outputs.
        Validates that written parquet files are readable and have expected row counts.
        """
        self._flush_incumbent_buffer()
        self._flush_node_buffer()
        
        # Close ParquetWriters
        if self.inc_writer is not None:
            self.inc_writer.close()
            # [E3] Validate incumbents parquet
            self._validate_parquet(
                self.incumbents_parquet,
                self.total_incumbents_written,
                "Incumbents"
            )
            self.inc_writer = None
        
        if self.node_writer is not None:
            self.node_writer.close()
            # [E3] Validate node relaxations parquet
            self._validate_parquet(
                self.node_relaxations_parquet,
                self.total_nodes_written,
                "Node Relaxations"
            )
            self.node_writer = None

    def _validate_parquet(self, filepath: str, expected_rows: int, label: str):
        """
        [E3] ENHANCEMENT: Post-write validation.
        Verifies that the written parquet file is readable and has the correct row count.
        This catches ParquetWriter crashes (OOM, network failure) immediately.
        """
        if not os.path.exists(filepath):
            self.logger.error(f"  [ERROR] {label} parquet not found: {filepath}")
            return
        
        try:
            df = pd.read_parquet(filepath)
            actual_rows = len(df)
            
            if actual_rows != expected_rows:
                self.logger.error(
                    f"  [ERROR] {label} parquet row count mismatch: "
                    f"expected {expected_rows}, got {actual_rows}"
                )
            else:
                self.logger.info(
                    f"  [OK] {label} parquet validated: {actual_rows} rows"
                )
        except Exception as e:
            self.logger.error(
                f"  [ERROR] Failed to validate {label} parquet: {e}"
            )


# ==========================================
# MAIN PROCESSING LOGIC
# ==========================================

def process_single_instance(lp_file_path: str, output_dir: str,
                             env: gp.Env, time_limit: int) -> bool:
    """
    Process a single MILP instance through the complete 6-step pipeline:
      1. Read model from .lp/.lp.gz file
      2. Extract original topology features
      3. Classify complexity via probe solve
      4. Solve with adaptive parameters + callback data collection
      5. Extract solution pool
      6. Save all outputs (pickle, parquet, JSON metadata)
    
    Returns:
        True if successful, False on error
    """

    instance_name = (os.path.basename(lp_file_path)
                     .replace('.lp.gz', '').replace('.lp', ''))
    instance_dir  = os.path.join(output_dir, instance_name)
    os.makedirs(instance_dir, exist_ok=True)

    logger = logging.getLogger('process_single_instance')
    logger.info(f"--- Processing: {instance_name} ---")

    try:
        logger.info("  [1/6] Reading model...")
        model = gp.read(lp_file_path, env=env)

        logger.info("  [2/6] Extracting original model features...")
        original_features = extract_model_features(model)

        with gzip.open(os.path.join(instance_dir, "original_features.pickle.gz"), 'wb') as f:
            pickle.dump({
                'model_features': original_features,
                'timestamp': time.time()
            }, f)

        logger.info("  [3/6] Classifying instance complexity (probe solve)...")
        is_complex, probe_node_count = classify_instance_complexity(model, env)
        complexity_class = 'hard' if is_complex else 'easy'
        presolve_setting = -1 if is_complex else 0
        logger.info(
            f"    Probe nodes explored: {probe_node_count} -> "
            f"'{complexity_class}', Presolve={presolve_setting}"
        )

        logger.info(f"  [4/6] Solving with time limit {time_limit}s (Presolve={presolve_setting})...")
        model_to_solve = model.copy()
        
        # Adaptive presolve
        model_to_solve.setParam('Presolve',        presolve_setting)
        
        # Solution pool configuration
        model_to_solve.setParam('PoolSearchMode',  1)   # Collect during B&B
        model_to_solve.setParam('PoolSolutions',   20)
        model_to_solve.setParam('PoolGap',         POOL_GAP_FILTER)
        
        # Disable reductions for pool diversity
        model_to_solve.setParam('Symmetry',        0)
        model_to_solve.setParam('DualReductions',  0)
        
        # Time limit
        model_to_solve.setParam('TimeLimit',       time_limit)

        # Initialize callback and solve
        callback = DataCollectionCallback(model_to_solve, instance_dir)
        start_time = time.time()
        model_to_solve.optimize(callback)
        solve_time = time.time() - start_time
        
        # Finalize callback (flush remaining buffers + validation)
        callback.finalize()

        logger.info("  [5/6] Extracting solution pool...")
        solution_pool = []
        if model_to_solve.SolCount > 0:
            pool_vars = model_to_solve.getVars()
            for n in range(model_to_solve.SolCount):
                try:
                    model_to_solve.Params.SolutionNumber = n
                    pool_obj      = float(model_to_solve.PoolObjVal)
                    # CRITICAL FIX: Gurobi 13.0 API - v.Xn is DEPRECATED, use v.PoolNX
                    pool_solution = np.array([v.PoolNX for v in pool_vars])
                    solution_pool.append({
                        'pool_index':      n,
                        'objective':       pool_obj,
                        'solution_vector': pool_solution
                    })
                except gp.GurobiError:
                    break

        logger.info("  [6/6] Saving metadata...")
        final_solution = extract_solution_features(
            model_to_solve,
            int(model_to_solve.NodeCount),
            solve_time
        )

        solution_data = {
            'final_solution': final_solution,
            'solution_pool': solution_pool,
        }

        with gzip.open(os.path.join(instance_dir, "solutions.pickle.gz"), 'wb') as f:
            pickle.dump(solution_data, f)

        metadata = {
            'instance':                instance_name,
            'status':                  model_to_solve.Status,
            'status_name':             {
                1: 'LOADED',
                2: 'OPTIMAL',
                3: 'INFEASIBLE',
                4: 'INF_OR_UNBD',
                5: 'UNBOUNDED',
                9: 'TIME_LIMIT'
            }.get(model_to_solve.Status, f'STATUS_{model_to_solve.Status}'),
            'runtime':                 solve_time,
            'mip_gap':                 float(getattr(model_to_solve, 'MIPGap', 0.0)),
            'node_count':              int(getattr(model_to_solve, 'NodeCount', 0)),
            'num_solutions_found':     model_to_solve.SolCount,
            'num_incumbents_collected':callback.total_incumbents_written,
            'num_nodes_collected':     callback.total_nodes_written,
            'pool_solutions_found':    len(solution_pool),
            'presolve_setting':        presolve_setting,
            'complexity_class':        complexity_class,
            'probe_node_count':        probe_node_count,
        }

        with open(os.path.join(instance_dir, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)

        model_to_solve.dispose()
        model.dispose()

        logger.info(
            f"  [OK] Successfully processed {instance_name} "
            f"({callback.total_incumbents_written} incumbents, "
            f"{callback.total_nodes_written} nodes)"
        )
        return True

    except Exception as e:
        logger.error(f"  [ERROR] Failed to process {instance_name}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def natural_sort_key(s):
    """Natural sort: handles numeric suffixes correctly (e.g., instance_2 < instance_10)"""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'([0-9]+)', s)]

def main():
    parser = argparse.ArgumentParser(
        description="CFL GNN Data Generator v6_enhanced_fixed - Memory-safe with Gurobi 13.0 compatibility"
    )
    parser.add_argument('--categories',  nargs='+',
                        default=["CFL_easy_instance"],
                        help="MILPBench categories to process")
    parser.add_argument('--start_idx',   type=int, default=0,
                        help="Start index within each category")
    parser.add_argument('--end_idx',     type=int, default=30,
                        help="End index (exclusive) within each category")
    parser.add_argument('--time_limit',  type=int, default=60,
                        help="Gurobi time limit per instance (seconds)")
    parser.add_argument('--input_dir',   type=str,
                        default="/home/vrcelestino/discodatos/cfl-gurobi-gnn/data/raw/MILPBench/CFL",
                        help="Root directory containing MILPBench .lp files")
    parser.add_argument('--output_dir',  type=str,
                        default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps",
                        help="Output directory for processed instances")
    parser.add_argument('--threads',     type=int, default=None,
                        help="Gurobi thread count (default: SLURM_CPUS_PER_TASK or 1)")
    args = parser.parse_args()

    print("=" * 80)
    print("CFL GNN Data Generator v6_enhanced_fixed")
    print("Memory-Safe | Full Validation | Gurobi 13.0 Compatible")
    print("=" * 80)

    os.makedirs(args.output_dir, exist_ok=True)

    # Collect file paths for all requested categories
    file_paths = []
    for category in args.categories:
        for ext in ["*.lp.gz", "*.lp"]:
            pattern = os.path.join(args.input_dir, category, "LP", ext)
            category_files = glob.glob(pattern)
            if category_files:
                category_files.sort(key=natural_sort_key)
                selected = category_files[args.start_idx:args.end_idx]
                file_paths.extend([(category, f) for f in selected])
                logging.info(
                    f"Category {category}: found {len(category_files)} files, "
                    f"processing {len(selected)} (idx {args.start_idx}:{args.end_idx})"
                )
                break
        else:
            logging.warning(f"No .lp or .lp.gz files found for category {category}")

    if not file_paths:
        logging.error("No files to process. Exiting.")
        return

    # Configure Gurobi environment
    env = gp.Env(empty=True)
    
    # WLS license configuration
    for var in ["WLSACCESSID", "WLSSECRET", "LICENSEID"]:
        if var in os.environ:
            val = int(os.environ[var]) if var == "LICENSEID" else os.environ[var]
            env.setParam(var, val)
    
    # Thread configuration
    threads = args.threads or int(os.environ.get("SLURM_CPUS_PER_TASK", 1))
    env.setParam("Threads", threads)
    env.setParam("LogToConsole", 0)
    
    env.start()
    logging.info(f"Gurobi environment started with {threads} threads")

    # Process all instances
    success_count = 0
    failure_count = 0
    
    for i, (category, file_path) in enumerate(file_paths, 1):
        logging.info(f"\n[{i}/{len(file_paths)}] Category: {category}")
        category_output = os.path.join(args.output_dir, category)
        success = process_single_instance(file_path, category_output, env, args.time_limit)
        
        if success:
            success_count += 1
        else:
            failure_count += 1

    print("\n" + "=" * 80)
    print(f"Pipeline completed: {success_count} succeeded, {failure_count} failed")
    print("=" * 80)
    
    env.dispose()

if __name__ == "__main__":
    main()
