#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capacitated Facility Location (CFL) Data Generator v7 - PRODUCTION FINAL
==========================================================================

CRITICAL FIX IN v7: MILPBench Objective Sense Correction
---------------------------------------------------------
MILPBench .lp files for CFL problems contain "Maximize" directive with positive
cost coefficients. This is mathematically incorrect for facility location problems,
which are cost MINIMIZATION problems. Without correction, Gurobi opens all 
facilities (99.9% ones), creating trivial solutions unsuitable for GNN training.

v7 forces ModelSense = MINIMIZE immediately after reading each .lp file.

**v7_fixed: Added WLS credential injection (missed in original v7 refactor)**

Version History:
----------------
v7_fixed: Fixed WLS license credential injection bug
v7: Added ModelSense = MINIMIZE fix (THE critical fix for 99.9% ones problem)
v6_enhanced: Added node validation, progress tracking, post-write validation
v6: Replaced CSV with PyArrow ParquetWriter, dynamic variable fetching
v5: Added incremental buffer flushing to prevent OOM on hard instances
v1-v4: Initial development and probe-based adaptive presolve

Author: Gurobi Intelligence Hub (Gurobot)
Date: 2026-07-23
Python: 3.8+
Gurobi: 13.0.2
Dependencies: gurobipy, pandas, pyarrow, numpy

Usage:
------
python3 cfl_gnn_data_generator_v7_fixed.py \\
    --categories CFL_easy_instance CFL_medium_instance CFL_hard_instance \\
    --start_idx 0 --end_idx 30 \\
    --time_limit 600 --threads 8

Output Structure (per instance):
---------------------------------
data/intermediate_lps/{category}/{instance_name}/
├── metadata.json                      # Solve statistics and complexity class
├── incumbents.parquet                 # Incumbent solutions (GNN training labels)
├── node_relaxations.parquet           # LP relaxation vectors at B&B nodes
├── original_features.pickle.gz        # Bipartite graph features (for ETL)
└── solutions.pickle.gz                # Solution pool (verification/audit)
"""

import os
import sys
import json
import time
import pickle
import gzip
import logging
import argparse
import gc
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import gurobipy as gp
from gurobipy import GRB

# ================================================================
# GLOBAL NAMEDTUPLE DEFINITIONS (for pickle compatibility)
# ================================================================
from collections import namedtuple
    
# Named tuples for structured feature storage
ModelFeatures = namedtuple('ModelFeatures', [
        'num_vars', 'num_constrs', 'num_binary', 'num_integer', 
        'num_continuous', 'obj_sense', 'obj_offset'
])
    
VariableFeatures = namedtuple('VariableFeatures', [
        'types', 'lower_bounds', 'upper_bounds', 'obj_coeffs'
])
    
ConstraintFeatures = namedtuple('ConstraintFeatures', [
        'senses', 'rhs_values', 'row_norms'
])

# ============================================================
# PHASE 1 STEP 1: DATA COLLECTION CALLBACK (MEMORY-SAFE)
# ============================================================

class DataCollectionCallback:
    """
    Gurobi callback for capturing incumbent solutions and node relaxations
    during Branch-and-Bound search.
    
    MEMORY SAFETY FEATURES (v5+):
    - Incremental parquet writing (no CSV intermediate)
    - Buffer size limit (default: 500 entries)
    - Dynamic variable fetching to prevent stale pointers
    
    VALIDATION FEATURES (v6_enhanced+):
    - Vector length validation on every write
    - Trivial incumbent detection (warns if >95% ones)
    - Post-write parquet validation
    - Real-time progress tracking
    
    GUROBI 13.0 API COMPLIANCE (v6_enhanced_fixed+):
    - Uses v.PoolNX for solution pool extraction
    - MIPSOL_PHASE == 1 filter (only B&B search solutions)
    """
    
    BUFFER_LIMIT = 50  # Flush to disk when buffer reaches this size (reduced from 500 to 50)
    
    def __init__(self, model: gp.Model, instance_dir: str):
        """
        Initialize callback with model reference and output directory.
        
        Args:
            model: Gurobi model being solved
            instance_dir: Directory to write parquet files
        """
        self.instance_dir = instance_dir
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Store expected variable count for validation
        self.num_vars = len(model.getVars())
        
        # Output file paths
        self.incumbents_parquet = os.path.join(instance_dir, "incumbents.parquet")
        self.node_relaxations_parquet = os.path.join(instance_dir, "node_relaxations.parquet")
        
        # In-memory buffers (flushed when reaching BUFFER_LIMIT)
        self.incumbent_buffer: List[Dict[str, Any]] = []
        self.node_buffer: List[Dict[str, Any]] = []
        
        # PyArrow writers (opened on first flush, closed in finalize())
        self.inc_writer: Optional[pq.ParquetWriter] = None
        self.node_writer: Optional[pq.ParquetWriter] = None
        
        # Counters for progress tracking
        self.total_incumbents_written = 0
        self.total_nodes_written = 0
        
        self.logger.info(f"Callback initialized: {self.num_vars} variables, buffer limit: {self.BUFFER_LIMIT}")
    
    def __call__(self, model: gp.Model, where: int):
        """
        Gurobi callback entry point. Captures data at MIPSOL and MIPNODE events.
        
        Args:
            model: Gurobi model (passed by Gurobi at callback invocation)
            where: Callback location code (GRB.Callback.MIPSOL or MIPNODE)
        """
        try:
            if where == GRB.Callback.MIPSOL:
                self._capture_incumbent(model)
            elif where == GRB.Callback.MIPNODE:
                self._capture_node_relaxation(model)
        except Exception as e:
            self.logger.error(f"Callback error at where={where}: {e}", exc_info=True)
    
    def _capture_incumbent(self, model: gp.Model):
        """
        Capture incumbent solution when MIPSOL callback fires.
        
        CRITICAL: Only captures solutions from Phase 1 (standard MIP search).
        Phase 0 (NoRel heuristic) solutions are filtered out as they are not
        true Branch-and-Bound search solutions.
        """
        # Filter: only Phase 1 (standard MIP search)
        phase = model.cbGet(GRB.Callback.MIPSOL_PHASE)
        if phase != 1:
            return
        
        # Fetch fresh variable list (prevents stale pointer bugs in Gurobi 13.0)
        vars_list = model.getVars()
        
        # Extract solution values using callback-safe method
        sol_vals = model.cbGetSolution(vars_list)
        sol_array = np.array(sol_vals, dtype=np.float64)
        
        # Validate vector length
        if len(sol_array) != self.num_vars:
            self.logger.error(
                f"  [CRITICAL] Incumbent solution length mismatch: "
                f"expected {self.num_vars}, got {len(sol_array)}. SKIPPING."
            )
            return
        
        # Sanity check: detect trivial incumbent (all variables at upper bound)
        n_zeros = (sol_array == 0.0).sum()
        n_ones = (sol_array == 1.0).sum()
        n_frac = len(sol_array) - n_zeros - n_ones
        pct_ones = 100.0 * n_ones / len(sol_array)
        
        if pct_ones > 95.0:
            self.logger.warning(
                f"  [WARN] Suspicious incumbent: {pct_ones:.1f}% ones "
                f"(possible trivial solution or wrong objective sense)"
            )
        
        # Extract solve state
        obj_val = model.cbGet(GRB.Callback.MIPSOL_OBJ)
        bnd_val = model.cbGet(GRB.Callback.MIPSOL_OBJBND)
        node_count = model.cbGet(GRB.Callback.MIPSOL_NODCNT)
        sol_count = model.cbGet(GRB.Callback.MIPSOL_SOLCNT)
        mip_gap = abs(obj_val - bnd_val) / (abs(obj_val) + 1e-10)
        timestamp = time.time()
        
        # Log with real-time progress tracking
        self.logger.info(
            f"  [INCUMBENT {int(sol_count)}] Buffered (total flushed: {self.total_incumbents_written}) | "
            f"obj={obj_val:.4f}, gap={mip_gap*100:.2f}%, node={int(node_count)} | "
            f"vec: {n_zeros}×0 + {n_ones}×1 + {n_frac}×frac = {len(sol_array)} total"
        )
        
        # Store in buffer
        self.incumbent_buffer.append({
            'node': int(node_count),
            'solution_count': int(sol_count),
            'objective': float(obj_val),
            'bound': float(bnd_val),
            'mip_gap': float(mip_gap),
            'time': float(timestamp),
            'solution_vector': sol_array  # numpy array
        })
        
        # Flush to disk if buffer is full
        if len(self.incumbent_buffer) >= self.BUFFER_LIMIT:
            self._flush_incumbent_buffer()
    
    def _flush_incumbent_buffer(self):
        """
        Write incumbent buffer to parquet file using PyArrow streaming writer.
        """
        if not self.incumbent_buffer:
            return
        
        # Validate all entries before write
        valid_incumbents = []
        for idx, inc in enumerate(self.incumbent_buffer):
            if len(inc['solution_vector']) != self.num_vars:
                self.logger.error(
                    f"  [CRITICAL] Incumbent {idx} length mismatch: "
                    f"expected {self.num_vars}, got {len(inc['solution_vector'])}. SKIPPING."
                )
                continue
            valid_incumbents.append(inc)
        
        if len(valid_incumbents) != len(self.incumbent_buffer):
            self.logger.warning(
                f"  [WARN] Filtered out {len(self.incumbent_buffer) - len(valid_incumbents)} corrupted incumbents"
            )
        
        if not valid_incumbents:
            self.incumbent_buffer.clear()
            return
        
        # Convert to PyArrow table
        df = pd.DataFrame(valid_incumbents)
        table = pa.Table.from_pandas(df, preserve_index=False)
        
        # Write using streaming ParquetWriter (opened once, reused across flushes)
        if self.inc_writer is None:
            self.inc_writer = pq.ParquetWriter(
                self.incumbents_parquet, 
                table.schema, 
                compression='snappy'
            )
        
        self.inc_writer.write_table(table)
        
        # Update counters and clear buffer
        self.total_incumbents_written += len(valid_incumbents)
        self.logger.info(f"  [FLUSH] Wrote {len(valid_incumbents)} incumbents to parquet (total: {self.total_incumbents_written})")
        self.incumbent_buffer.clear()
    
    def _capture_node_relaxation(self, model: gp.Model):
        """
        Capture LP relaxation solution at MIPNODE callback.
        
        Only captures at nodes with status OPTIMAL (relaxation solved successfully).
        """
        status = model.cbGet(GRB.Callback.MIPNODE_STATUS)
        if status != GRB.OPTIMAL:
            return
        
        # Fetch fresh variable list
        vars_list = model.getVars()
        
        # Extract relaxation values
        rel_vals = model.cbGetNodeRel(vars_list)
        rel_array = np.array(rel_vals, dtype=np.float64)
        
        # Validate vector length
        if len(rel_array) != self.num_vars:
            self.logger.error(
                f"  [CRITICAL] Node relaxation length mismatch: "
                f"expected {self.num_vars}, got {len(rel_array)}. SKIPPING."
            )
            return
        
        # Extract solve state
        obj_val = model.cbGet(GRB.Callback.MIPNODE_OBJBST)
        bnd_val = model.cbGet(GRB.Callback.MIPNODE_OBJBND)
        node_count = model.cbGet(GRB.Callback.MIPNODE_NODCNT)
        timestamp = time.time()
        
        # Store in buffer
        self.node_buffer.append({
            'node': int(node_count),
            'best_objective': float(obj_val),
            'best_bound': float(bnd_val),
            'time': float(timestamp),
            'relaxation_vector': rel_array  # numpy array
        })
        
        # Flush to disk if buffer is full
        if len(self.node_buffer) >= self.BUFFER_LIMIT:
            self._flush_node_buffer()
    
    def _flush_node_buffer(self):
        """
        Write node relaxation buffer to parquet file using PyArrow streaming writer.
        """
        if not self.node_buffer:
            return
        
        # Validate all entries before write
        valid_nodes = []
        for idx, node_rec in enumerate(self.node_buffer):
            if len(node_rec['relaxation_vector']) != self.num_vars:
                self.logger.error(
                    f"  [CRITICAL] Node relaxation {idx} length mismatch: "
                    f"expected {self.num_vars}, got {len(node_rec['relaxation_vector'])}. SKIPPING."
                )
                continue
            valid_nodes.append(node_rec)
        
        if len(valid_nodes) != len(self.node_buffer):
            self.logger.warning(
                f"  [WARN] Filtered out {len(self.node_buffer) - len(valid_nodes)} corrupted node entries"
            )
        
        if not valid_nodes:
            self.node_buffer.clear()
            return
        
        # Convert to PyArrow table
        df = pd.DataFrame(valid_nodes)
        table = pa.Table.from_pandas(df, preserve_index=False)
        
        # Write using streaming ParquetWriter
        if self.node_writer is None:
            self.node_writer = pq.ParquetWriter(
                self.node_relaxations_parquet, 
                table.schema, 
                compression='snappy'
            )
        
        self.node_writer.write_table(table)
        
        # Update counters and clear buffer
        self.total_nodes_written += len(valid_nodes)
        self.logger.info(f"  [FLUSH] Wrote {len(valid_nodes)} node relaxations to parquet (total: {self.total_nodes_written})")
        self.node_buffer.clear()
    
    def finalize(self):
        """
        Flush remaining buffers, close writers, and validate parquet outputs.
        
        Called after Gurobi optimize() completes to ensure all data is written.
        """
        # Flush any remaining data
        self._flush_incumbent_buffer()
        self._flush_node_buffer()
        
        # Close writers and validate outputs
        if self.inc_writer is not None:
            self.inc_writer.close()
            self._validate_parquet(self.incumbents_parquet, self.total_incumbents_written, "Incumbents")
            self.inc_writer = None
        
        if self.node_writer is not None:
            self.node_writer.close()
            self._validate_parquet(self.node_relaxations_parquet, self.total_nodes_written, "Node Relaxations")
            self.node_writer = None
    
    def _validate_parquet(self, filepath: str, expected_rows: int, label: str):
        """
        Validate that the written parquet file is readable and has correct row count.
        
        Args:
            filepath: Path to parquet file
            expected_rows: Expected number of rows
            label: Human-readable label for logging
        """
        try:
            df = pd.read_parquet(filepath)
            actual_rows = len(df)
            if actual_rows != expected_rows:
                self.logger.error(
                    f"  [ERROR] {label} parquet row count mismatch: "
                    f"expected {expected_rows}, got {actual_rows}"
                )
            else:
                self.logger.info(f"  [OK] {label} parquet validated: {actual_rows} rows")
        except Exception as e:
            self.logger.error(f"  [ERROR] Failed to validate {label} parquet: {e}")


# ============================================================
# PHASE 1 STEP 2: ADAPTIVE PRESOLVE CLASSIFIER
# ============================================================

def run_probe_solve(model: gp.Model, time_limit: int, logger: logging.Logger) -> Tuple[int, float]:
    """
    Run a short probe solve to classify instance complexity.
    
    Returns:
        (node_count, runtime): Number of B&B nodes explored and solve time
    """
    logger.info(f"  Running probe solve (time limit: {time_limit}s)...")
    
    # Configure probe: minimal parameters, silent
    model.Params.TimeLimit = time_limit
    model.Params.OutputFlag = 0
    model.Params.Threads = 1
    
    start_time = time.time()
    model.optimize()
    runtime = time.time() - start_time
    
    node_count = int(model.NodeCount)
    logger.info(f"  Probe complete: {node_count} nodes, {runtime:.2f}s")
    
    return node_count, runtime


def classify_complexity(node_count: int, threshold: int) -> Tuple[str, int]:
    """
    Classify instance as easy/hard based on probe node count.
    
    Args:
        node_count: Nodes explored in probe solve
        threshold: Node count threshold (default: 500)
    
    Returns:
        (complexity_class, presolve_setting):
            - "easy" instances: presolve=0 (disabled to collect more training labels)
            - "hard" instances: presolve=-1 (automatic, to speed up solve)
    """
    if node_count <= threshold:
        return "easy", 0
    else:
        return "hard", -1


# ============================================================
# PHASE 1 STEP 3: BIPARTITE GRAPH FEATURE EXTRACTION
# ============================================================

def extract_bipartite_features(model: gp.Model) -> Dict[str, Any]:
    """
    Extract bipartite graph features for PyTorch Geometric ETL.
    
    Returns a dictionary with:
        - constraint_features: Constraint metadata (sense, RHS, etc.)
        - edge_indices: Variable-constraint incidence
        - edge_features: Constraint coefficients
        - variable_features: Variable metadata (type, bounds, obj coeff)
        - model_features: Global model metadata
    """

    # Moved to beginning - achieve global scope for named tuples
    #from collections import namedtuple
    
    ## Named tuples for structured feature storage
    #ModelFeatures = namedtuple('ModelFeatures', [
    #    'num_vars', 'num_constrs', 'num_binary', 'num_integer', 
    #    'num_continuous', 'obj_sense', 'obj_offset'
    #])
    
    #VariableFeatures = namedtuple('VariableFeatures', [
    #    'types', 'lower_bounds', 'upper_bounds', 'obj_coeffs'
    #])
    
    #ConstraintFeatures = namedtuple('ConstraintFeatures', [
    #    'senses', 'rhs_values', 'row_norms'
    #])

    
    
    # Extract variables
    vars_list = model.getVars()
    num_vars = len(vars_list)
    
    var_types = np.array([v.VType for v in vars_list], dtype='<U1')
    var_lb = np.array([v.LB for v in vars_list], dtype=np.float32)
    var_ub = np.array([v.UB for v in vars_list], dtype=np.float32)
    var_obj = np.array([v.Obj for v in vars_list], dtype=np.float32)
    
    num_binary = (var_types == 'B').sum()
    num_integer = (var_types == 'I').sum()
    num_continuous = (var_types == 'C').sum()
    
    # Extract constraints
    constrs_list = model.getConstrs()
    num_constrs = len(constrs_list)
    
    constr_senses = np.array([c.Sense for c in constrs_list], dtype='<U1')
    constr_rhs = np.array([c.RHS for c in constrs_list], dtype=np.float32)
    
    # Extract constraint matrix (sparse)
    edge_indices = []
    edge_features = []
    
    for c_idx, constr in enumerate(constrs_list):
        row = model.getRow(constr)
        for i in range(row.size()):
            var = row.getVar(i)
            coeff = row.getCoeff(i)
            var_idx = var.index
            
            edge_indices.append([var_idx, c_idx])
            edge_features.append(coeff)
    
    edge_indices = np.array(edge_indices, dtype=np.int32).T  # Shape: [2, num_edges]
    edge_features = np.array(edge_features, dtype=np.float32)
    
    # Compute constraint L2 norms
    constr_norms = np.zeros(num_constrs, dtype=np.float32)
    for c_idx in range(num_constrs):
        mask = edge_indices[1, :] == c_idx
        coeffs = edge_features[mask]
        constr_norms[c_idx] = np.linalg.norm(coeffs)
    
    # Pack into structured format
    return {
        'model_features': ModelFeatures(
            num_vars=num_vars,
            num_constrs=num_constrs,
            num_binary=int(num_binary),
            num_integer=int(num_integer),
            num_continuous=int(num_continuous),
            obj_sense=model.ModelSense,
            obj_offset=model.ObjCon
        ),
        'variable_features': VariableFeatures(
            types=var_types,
            lower_bounds=var_lb,
            upper_bounds=var_ub,
            obj_coeffs=var_obj
        ),
        'constraint_features': ConstraintFeatures(
            senses=constr_senses,
            rhs_values=constr_rhs,
            row_norms=constr_norms
        ),
        'edge_indices': edge_indices,
        'edge_features': edge_features
    }


# ============================================================
# PHASE 1 STEP 4: SOLUTION POOL EXTRACTION
# ============================================================

def extract_solution_pool(model: gp.Model, logger: logging.Logger) -> List[Dict[str, Any]]:
    """
    Extract solution pool after optimization.
    
    Uses Gurobi 13.0 API: v.PoolNX (not deprecated v.Xn).
    
    Returns:
        List of solution dictionaries with keys:
            - solution_vector: numpy array of variable values
            - objective: objective value
            - pool_index: index in pool (0 = best)
    """
    num_solutions = model.SolCount
    logger.info(f"  Extracting solution pool: {num_solutions} solutions")
    
    pool_vars = model.getVars()
    pool = []
    
    for i in range(num_solutions):
        model.Params.SolutionNumber = i
        
        # CRITICAL: Use v.PoolNX (Gurobi 13.0+), not v.Xn (deprecated)
        pool_solution = np.array([v.PoolNX for v in pool_vars], dtype=np.float64)
        pool_obj = model.PoolObjVal
        
        pool.append({
            'solution_vector': pool_solution,
            'objective': float(pool_obj),
            'pool_index': i
        })
    
    return pool


# ============================================================
# MAIN ORCHESTRATION: PROCESS SINGLE INSTANCE
# ============================================================

def process_single_instance(
    lp_file_path: str,
    output_dir: str,
    args: argparse.Namespace,
    env: gp.Env,  # ← Added this parameter
    logger: logging.Logger
) -> Dict[str, Any]:
    """
    Process a single CFL instance through the complete data generation pipeline.
    
    Pipeline Steps:
        1. Read model from .lp file
        2. **[v7 CRITICAL FIX]** Force ModelSense = MINIMIZE
        3. Run probe solve to classify complexity
        4. Configure Gurobi parameters (adaptive presolve)
        5. Extract bipartite graph features
        6. Run main solve with callback
        7. Extract solution pool
        8. Save all outputs and metadata
    
    Returns:
        metadata: Dictionary with solve statistics and complexity class
    """
    instance_name = Path(lp_file_path).stem.replace('.lp', '')
    instance_dir = os.path.join(output_dir, instance_name)
    os.makedirs(instance_dir, exist_ok=True)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {instance_name}")
    logger.info(f"{'='*60}")
    
    # ===================================================================
    # [v7_fixed] CREATE GUROBI ENVIRONMENT WITH WLS CREDENTIALS
    # ===================================================================
    # Transfered to main()

    #env = gp.Env(empty=True)
    #env.setParam('OutputFlag', 0)
    
    ## Inject WLS credentials from environment variables
    #for var in ["WLSACCESSID", "WLSSECRET", "LICENSEID"]:
    #    if var in os.environ:
    #        val = int(os.environ[var]) if var == "LICENSEID" else os.environ[var]
    #        env.setParam(var, val)
    #        logger.debug(f"  Injected {var} from environment")
    #
    #env.start()

    
    try:
        # ===================================================================
        # STEP 1: READ MODEL
        # ===================================================================
        logger.info("  [1/7] Reading model...")
        model = gp.read(lp_file_path, env=env)
        
        # ===================================================================
        # STEP 1.5: [v7 CRITICAL FIX] FORCE MINIMIZATION
        # ===================================================================
        # MILPBench .lp files contain "Maximize" directive with positive costs.
        # This is mathematically incorrect for CFL (a cost minimization problem).
        # Without this fix, Gurobi opens all facilities (99.9% ones in solution),
        # creating trivial solutions that are unsuitable for GNN training.
        #
        # Root cause identified: 2026-07-23 after 6 failed debugging iterations
        # targeting non-existent software bugs in callback/CSV/ParquetWriter.
        # ===================================================================
        original_sense = "MINIMIZE" if model.ModelSense == GRB.MINIMIZE else "MAXIMIZE"
        model.ModelSense = GRB.MINIMIZE
        logger.info(f"  [OVERRIDE] Forced ModelSense = MINIMIZE (file said: {original_sense})")
        
        # ===================================================================
        # STEP 2: PROBE SOLVE (COMPLEXITY CLASSIFICATION)
        # ===================================================================
        logger.info("  [2/7] Running probe solve...")
        probe_nodes, probe_time = run_probe_solve(
            model.copy(), 
            args.probe_time, 
            logger
        )
        complexity_class, presolve_setting = classify_complexity(
            probe_nodes, 
            args.complexity_threshold
        )
        logger.info(f"  Classification: {complexity_class} (presolve={presolve_setting})")
        
        # ===================================================================
        # STEP 3: CONFIGURE GUROBI PARAMETERS
        # ===================================================================
        logger.info("  [3/7] Configuring Gurobi parameters...")
        model.Params.TimeLimit = args.time_limit
        model.Params.Threads = args.threads
        model.Params.Presolve = presolve_setting
        model.Params.MIPFocus = args.mipfocus
        model.Params.Heuristics = args.heuristics
        model.Params.Method = args.method
        
        # Solution pool parameters
        model.Params.PoolSolutions = args.pool_size
        model.Params.PoolGap = args.pool_gap
        model.Params.PoolSearchMode = 1  # Collect as by-product of B&B
        
        # Enable callback output
        model.Params.OutputFlag = 1
        
        # ===================================================================
        # STEP 4: EXTRACT BIPARTITE GRAPH FEATURES
        # ===================================================================
        logger.info("  [4/7] Extracting bipartite graph features...")
        features = extract_bipartite_features(model)
        features_path = os.path.join(instance_dir, "original_features.pickle.gz")
        with gzip.open(features_path, 'wb') as f:
            pickle.dump(features, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"  Saved features: {features['model_features'].num_vars} vars, "
                   f"{features['model_features'].num_constrs} constrs")
        
        # ===================================================================
        # STEP 5: RUN MAIN SOLVE WITH CALLBACK
        # ===================================================================
        logger.info("  [5/7] Running main solve with data collection callback...")
        callback = DataCollectionCallback(model, instance_dir)
        
        start_time = time.time()
        model.optimize(callback)
        runtime = time.time() - start_time
        
        # Finalize callback (flush buffers, close writers, validate)
        callback.finalize()
        
        logger.info(f"  Solve complete: status={model.Status}, "
                   f"runtime={runtime:.2f}s, nodes={model.NodeCount}")
        
        # ===================================================================
        # STEP 6: EXTRACT SOLUTION POOL
        # ===================================================================
        logger.info("  [6/7] Extracting solution pool...")
        pool = extract_solution_pool(model, logger)
        pool_path = os.path.join(instance_dir, "solutions.pickle.gz")
        with gzip.open(pool_path, 'wb') as f:
            pickle.dump({'solution_pool': pool}, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # ===================================================================
        # STEP 7: SAVE METADATA
        # ===================================================================
        logger.info("  [7/7] Saving metadata...")
        metadata = {
            'instance': instance_name,
            'lp_file': lp_file_path,
            'probe_node_count': probe_nodes,
            'probe_runtime': probe_time,
            'complexity_class': complexity_class,
            'presolve_setting': presolve_setting,
            'status': model.Status,
            'runtime': runtime,
            'node_count': int(model.NodeCount),
            'num_solutions_found': model.SolCount,
            'pool_solutions_found': len(pool),
            'num_incumbents_collected': callback.total_incumbents_written,
            'num_nodes_collected': callback.total_nodes_written,
            'objective_sense_override': 'MINIMIZE',  # v7 fix marker
            'original_objective_sense': original_sense
        }
        
        if model.Status == GRB.OPTIMAL:
            metadata['best_objective'] = model.ObjVal
            metadata['mip_gap'] = 0.0
        elif model.SolCount > 0:
            metadata['best_objective'] = model.ObjVal
            metadata['best_bound'] = model.ObjBound
            metadata['mip_gap'] = model.MIPGap
        
        metadata_path = os.path.join(instance_dir, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"  [SUCCESS] Instance processed: {callback.total_incumbents_written} incumbents, "
                   f"{callback.total_nodes_written} nodes")

        # Liberate Gurobi internal memory and Python references
        model.dispose() # Free Gurobi internal memory
        del model
        del callback
        del features
        del pool
        gc.collect()    # Force Python to liberate RAM

        return metadata
    
    except Exception as e:
        logger.error(f"  [FAILED] {instance_name}: {e}", exc_info=True)
        return {'instance': instance_name, 'status': 'FAILED', 'error': str(e)}
    
    #finally:
    #    env.dispose()


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='CFL GNN Data Generator v7_fixed - Production Final',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single category, 10 instances
  python3 cfl_gnn_data_generator_v7_fixed.py --categories CFL_easy_instance --start_idx 0 --end_idx 10
  
  # All categories, full batch
  python3 cfl_gnn_data_generator_v7_fixed.py \\
      --categories CFL_easy_instance CFL_medium_instance CFL_hard_instance \\
      --start_idx 0 --end_idx 30 --time_limit 600 --threads 8
        """
    )
    
    # Instance selection
    parser.add_argument('--categories', nargs='+', required=True,
                       help='MILPBench categories to process')
    parser.add_argument('--start_idx', type=int, default=0,
                       help='Start index (inclusive)')
    parser.add_argument('--end_idx', type=int, default=10,
                       help='End index (exclusive)')
    
    # Paths
    parser.add_argument('--input_dir', type=str,
                       default='/home/vrcelestino/discodatos/cfl-gurobi-gnn/data/raw/MILPBench/CFL',
                       help='Directory containing MILPBench .lp.gz files')
    parser.add_argument('--output_dir', type=str,
                       default='/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps',
                       help='Output directory for processed instances')
    
    # Gurobi parameters
    parser.add_argument('--time_limit', type=int, default=300,
                       help='Main solve time limit (seconds)')
    parser.add_argument('--threads', type=int, default=8,
                       help='Gurobi thread count')
    parser.add_argument('--method', type=int, default=-1,
                       help='Gurobi method (-1=auto, 0=primal, 1=dual, 2=barrier)')
    parser.add_argument('--heuristics', type=float, default=0.05,
                       help='Heuristics effort (0.0-1.0)')
    parser.add_argument('--mipfocus', type=int, default=0,
                       help='MIPFocus (0=auto, 1=feasibility, 2=optimality, 3=bound)')
    
    # Adaptive presolve parameters
    parser.add_argument('--probe_time', type=int, default=30,
                       help='Probe solve time limit (seconds)')
    parser.add_argument('--complexity_threshold', type=int, default=500,
                       help='Node count threshold: easy vs. hard')
    
    # Solution pool parameters
    parser.add_argument('--pool_size', type=int, default=20,
                       help='Number of solutions to retain in pool')
    parser.add_argument('--pool_gap', type=float, default=0.10,
                       help='Pool quality filter (0.10 = keep solutions within 10% of best)')
    
    args = parser.parse_args()

    # Configure Gurobi environment
    os.environ["GRB_LICENSE_FILE"] = "/home/vrcelestino/discodatos/gurobi.lic"

    env = gp.Env(empty=True)
    env.setParam('OutputFlag', 0)

    wls_id = os.environ.get("WLSACCESSID")
    wls_secret = os.environ.get("WLSSECRET")
    license_id = os.environ.get("LICENSEID")
    
    if wls_id and wls_secret and license_id:
        env.setParam("WLSACCESSID", wls_id)
        env.setParam("WLSSECRET", wls_secret)
        env.setParam("LICENSEID", int(license_id))

    env.start()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    
    logger.info("="*70)
    logger.info("CFL GNN DATA GENERATOR v7_fixed - PRODUCTION FINAL")
    logger.info("="*70)
    logger.info(f"Categories: {args.categories}")
    logger.info(f"Index range: [{args.start_idx}, {args.end_idx})")
    logger.info(f"Time limit: {args.time_limit}s, Threads: {args.threads}")
    logger.info(f"Probe: {args.probe_time}s, Threshold: {args.complexity_threshold} nodes")
    logger.info(f"Output: {args.output_dir}")
    logger.info("="*70)
    
    # Process all instances
    all_metadata = []
    
    for category in args.categories:
        category_input_dir = os.path.join(args.input_dir, category, "LP")
        category_output_dir = os.path.join(args.output_dir, category)
        os.makedirs(category_output_dir, exist_ok=True)
        
        logger.info(f"\n{'#'*70}")
        logger.info(f"# CATEGORY: {category}")
        logger.info(f"{'#'*70}")
        
        for idx in range(args.start_idx, args.end_idx):
            lp_filename = f"{category}_{idx}.lp.gz"
            lp_path = os.path.join(category_input_dir, lp_filename)
            
            if not os.path.exists(lp_path):
                logger.warning(f"File not found: {lp_path}")
                continue
            
            metadata = process_single_instance(lp_path, category_output_dir, args, env, logger)
            all_metadata.append(metadata)
    
    # Save summary report
    #summary_path = os.path.join(args.output_dir, "generation_summary.json")

    # Transfered to audit_phase1_eda code
    ## Save summary report with dynamic name based on categories
    #categories_str = "_".join(args.categories)
    #dynamic_filename = f"generation_summary_{categories_str}.json"
    #summary_path = os.path.join(args.output_dir, dynamic_filename)

    #with open(summary_path, 'w') as f:
    #    json.dump({
    #        'timestamp': datetime.now().isoformat(),
    #        'arguments': vars(args),
    #        'instances_processed': len(all_metadata),
    #        'metadata': all_metadata
    #    }, f, indent=2)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"PIPELINE COMPLETE")
    logger.info(f"{'='*70}")
    logger.info(f"Instances processed: {len(all_metadata)}")
    logger.info(f"Summary saved to: {summary_path}")

    env.dispose()


if __name__ == '__main__':
    main()
