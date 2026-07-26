"""
Phase 2: PyG Graph Construction (Multi-Task Neural Diving)
==========================================================
Generates one bipartite HeteroData graph per Gurobi incumbent solution.
This script encodes the MILP structure as a variable-constraint bipartite graph
and attaches multi-task labels for node-level (solution assignment) and
graph-level (MIP gap, solve time, optimality) prediction.

Architecture:
    Variable nodes  : [obj_coeff, lb, ub, is_cont, is_bin, is_int, lp_relax]  -> shape [N_v, 7]
    Constraint nodes: [rhs, sense_lt, sense_eq, sense_gt, dummy]               -> shape [N_c, 5]
    Edges (v->c)    : log-scaled constraint matrix coefficients                -> shape [nnz, 1]
    Edges (c->v)    : same coefficients, reversed direction                    -> shape [nnz, 1]

Key Design Decisions:
    - Log-scale (sign * ln(1 + |x|)) is applied to compress Big-M magnitudes.
    - LP relaxations remain unscaled to preserve the [0, 1] probability space.
    - Constraints use string comparison ('<', '=', '>') for numpy dtype safety.
    - Centralized metadata mapping ensures safe curriculum learning splits.
"""

import os
import sys
import json
import glob
import gzip
import pickle
import logging
import argparse
import traceback
import numpy as np
import pandas as pd
import torch
import gc
import pyarrow.parquet as pq
from torch_geometric.data import HeteroData
from tqdm import tqdm
from collections import namedtuple
from typing import Optional

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quality Filter
# ---------------------------------------------------------------------------
MAX_MIP_GAP = 0.10   # Discard B&B incumbents with a MIP gap strictly > 10%

# ---------------------------------------------------------------------------
# Data Definitions (Synchronized with Phase 1 Generator)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Feature Engineering Utilities
# ---------------------------------------------------------------------------

def sanitize_array(arr: np.ndarray, name: str = "array", apply_log_scale: bool = False) -> torch.Tensor:
    """
    Cleans a numpy array and optionally applies signed log-scale compression.
    Limits extreme Big-M values to +/- 60000 to maintain gradient stability.
    """
    arr = np.nan_to_num(arr, nan=0.0, posinf=60000.0, neginf=-60000.0)
    arr = np.clip(arr, -60000.0, 60000.0)

    if apply_log_scale:
        arr = np.sign(arr) * np.log1p(np.abs(arr))

    return torch.FloatTensor(arr).unsqueeze(-1)

# ---------------------------------------------------------------------------
# Graph Builder Core
# ---------------------------------------------------------------------------

def build_heterodata(
    model_features:    ModelFeatures,
    variable_features: VariableFeatures,
    constr_features:   ConstraintFeatures,
    edge_indices:      np.ndarray,
    edge_features:     np.ndarray,
    sol_vector:        np.ndarray,
    lp_vector_root:    np.ndarray,
    mip_gap:           float,
    exec_time:         float,
    is_optimal:        bool,
    incumbent_node:    int,
    instance_name:     str,
    metadata:          dict,
) -> Optional[HeteroData]:
    """
    Assembles a single PyTorch Geometric HeteroData bipartite graph encoding
    the Branch-and-Bound state and MILP topology.
    """
    try:
        graph_data = HeteroData()

        # 1. Variable Node Features Initialization [N_v, 7]
        obj_tensor = sanitize_array(variable_features.obj_coeffs, name="obj", apply_log_scale=True)
        lb_tensor  = sanitize_array(variable_features.lower_bounds, name="lb", apply_log_scale=True)
        ub_tensor  = sanitize_array(variable_features.upper_bounds, name="ub", apply_log_scale=True)

        is_cont = torch.FloatTensor((variable_features.types == 'C').astype(float)).unsqueeze(-1)
        is_bin  = torch.FloatTensor((variable_features.types == 'B').astype(float)).unsqueeze(-1)
        is_int  = torch.FloatTensor((variable_features.types == 'I').astype(float)).unsqueeze(-1)

        # Fallback to zero-vector if relaxation length mismatches due to presolve anomalies
        if len(lp_vector_root) != model_features.num_vars:
            lp_vector_root = np.zeros(model_features.num_vars)
            
        lp_tensor = sanitize_array(lp_vector_root, name="lp_relax", apply_log_scale=False)

        graph_data['variable'].x = torch.cat(
            [obj_tensor, lb_tensor, ub_tensor, is_cont, is_bin, is_int, lp_tensor], dim=1
        )

        # 2. Constraint Node Features Initialization [N_c, 5]
        rhs_tensor = sanitize_array(constr_features.rhs_values, name="rhs", apply_log_scale=True)
        sense_lt = torch.FloatTensor((constr_features.senses == '<').astype(float)).unsqueeze(-1)
        sense_eq = torch.FloatTensor((constr_features.senses == '=').astype(float)).unsqueeze(-1)
        sense_gt = torch.FloatTensor((constr_features.senses == '>').astype(float)).unsqueeze(-1)
        c_dummy = torch.ones_like(rhs_tensor)

        graph_data['constraint'].x = torch.cat(
            [rhs_tensor, sense_lt, sense_eq, sense_gt, c_dummy], dim=1
        )

        # 3. Bipartite Edge Indices and Attributes Mapping
        # Edge indices shape: (2, E) -> [0] represents constraints, [1] represents variables
        rows = torch.LongTensor(edge_indices[0])
        cols = torch.LongTensor(edge_indices[1])
        edge_weight = sanitize_array(edge_features, name="A", apply_log_scale=True)

        edge_index_v2c = torch.stack([cols, rows], dim=0)  
        edge_index_c2v = torch.stack([rows, cols], dim=0)  

        graph_data['variable', 'rev_coef', 'constraint'].edge_index = edge_index_v2c
        graph_data['variable', 'rev_coef', 'constraint'].edge_attr  = edge_weight
        graph_data['constraint', 'coef', 'variable'].edge_index = edge_index_c2v
        graph_data['constraint', 'coef', 'variable'].edge_attr  = edge_weight

        # 4. Node-Level Target Labels
        if len(sol_vector) != model_features.num_vars:
            logger.warning(f"[{instance_name}] Solution length mismatch. Skipping graph.")
            return None

        graph_data['variable'].y = torch.FloatTensor(sol_vector)
        # Identify discrete variables to compute localized loss during training
        graph_data['variable'].is_discrete = (is_bin + is_int).clamp(0.0, 1.0).squeeze(-1)

        # 5. Graph-Level Multi-Task Labels & Centralized Metadata
        graph_data.mip_gap        = float(mip_gap)
        graph_data.exec_time      = float(exec_time)
        graph_data.is_optimal     = bool(mip_gap <= 1e-4)
        graph_data.incumbent_node = int(incumbent_node)
        graph_data.instance_name  = str(instance_name)
        
        # Safe extraction from the master summary JSON
        graph_data.complexity_class  = metadata.get('complexity_class', 'unknown')
        graph_data.probe_node_count  = metadata.get('probe_node_count', -1)
        graph_data.presolve_used     = (metadata.get('presolve_setting', 0) == -1)

        return graph_data

    except Exception as e:
        logger.error(f"[{instance_name}] Graph construction failed: {e}\n{traceback.format_exc()}")
        return None

# ---------------------------------------------------------------------------
# Per-Instance ETL Processing
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Per-Instance ETL Processing (Memory Optimized)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Per-Instance ETL Processing (Extreme Memory Optimization via Streaming)
# ---------------------------------------------------------------------------

def process_instance(inst_dir: str,
                     global_idx_start: int,
                     processed_dir: str,
                     metadata: dict) -> int:
    """
    Reads a specific instance directory and generates PyG .pt files.
    Optimized via Base-Graph cloning AND Parquet batch-streaming to strictly
    prevent Out-Of-Memory (OOM) errors on large MILP instances.
    """
    features_path    = os.path.join(inst_dir, "original_features.pickle.gz")
    incumbents_path  = os.path.join(inst_dir, "incumbents.parquet")
    relaxations_path = os.path.join(inst_dir, "node_relaxations.parquet")
    instance_name    = os.path.basename(inst_dir)

    if not os.path.exists(features_path) or not os.path.exists(incumbents_path):
        logger.warning(f"[{instance_name}] Missing critical files. Skipping.")
        return 0

    try:
        # 1. Load static graph topology
        with gzip.open(features_path, 'rb') as fh:
            raw = pickle.load(fh)
            
        model_features      = raw['model_features']
        variable_features   = raw['variable_features']
        constraint_features = raw['constraint_features']
        edge_indices        = raw['edge_indices']
        edge_features       = raw['edge_features']

        # 2. Safely fetch LP relaxation ONLY for the root node
        # Using filters prevents loading the entire relaxation tree into RAM
        lp_vector_root = np.zeros(model_features.num_vars)
        if os.path.exists(relaxations_path):
            df_relax = pd.read_parquet(relaxations_path, filters=[('node', '==', 0)])
            if not df_relax.empty:
                lp_vector_root = np.array(df_relax.iloc[0]['relaxation_vector'])

        # 3. Build the Base Graph ONCE per instance
        dummy_sol = np.zeros(model_features.num_vars)
        base_graph = build_heterodata(
            model_features    = model_features,
            variable_features = variable_features,
            constr_features   = constraint_features,
            edge_indices      = edge_indices,
            edge_features     = edge_features,
            sol_vector        = dummy_sol,
            lp_vector_root    = lp_vector_root,
            mip_gap           = 1.0,
            exec_time         = 0.0,
            is_optimal        = False,
            incumbent_node    = -1,
            instance_name     = instance_name,
            metadata          = metadata,
        )

        if base_graph is None:
            return 0

        graphs_generated   = 0
        current_global_idx = global_idx_start

        # 4. STREAMING PARQUET (The Ultimate OOM Fix)
        # Instead of loading all solutions, we stream them 50 at a time.
        parquet_file = pq.ParquetFile(incumbents_path)
        
        for batch in parquet_file.iter_batches(batch_size=50):
            df_chunk = batch.to_pandas()
            
            for _, row in df_chunk.iterrows():
                try:
                    row_gap = float(row['mip_gap'])
                except (ValueError, KeyError):
                    row_gap = 1.0

                if row_gap > MAX_MIP_GAP:
                    continue

                sol_vector = np.array(row['solution_vector'])
                
                # Clone the base topology
                graph = base_graph.clone()
                
                # Inject solution-specific labels
                graph['variable'].y = torch.FloatTensor(sol_vector)
                graph.mip_gap       = float(row_gap)
                graph.exec_time     = float(row.get('time', 0.0))
                graph.is_optimal    = bool(row_gap <= 1e-4)
                graph.incumbent_node = int(row.get('node', -1))

                out_file = os.path.join(processed_dir, f"data_{current_global_idx}.pt")
                torch.save(graph, out_file)
                
                current_global_idx += 1
                graphs_generated   += 1
                
                # Clear individual graph tensor
                del graph
                
            # Force memory release for this chunk before loading the next 50 solutions
            del df_chunk
            gc.collect()

        # Final aggressive garbage collection
        del base_graph, raw, model_features, variable_features, constraint_features
        del edge_indices, edge_features
        gc.collect()

        return graphs_generated

    except Exception as e:
        logger.error(f"[{instance_name}] Processing failed: {e}\n{traceback.format_exc()}")
        return 0

# ---------------------------------------------------------------------------
# Main ETL Pipeline Logic
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 2: Build PyG HeteroData graphs from B&B incumbents"
    )
    parser.add_argument(
        '--categories', nargs='+',
        default=["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"],
        help="List of MILP instance categories to process."
    )
    parser.add_argument(
        '--base_raw_dir',
        default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps",
        help="Root directory containing raw instance subdirectories."
    )
    parser.add_argument(
        '--base_pyg_dir',
        default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset",
        help="Root directory where processed PyG .pt files will be saved."
    )
    parser.add_argument(
        '--clear_processed', action='store_true',
        help="If set, strictly purge existing data_*.pt files before rebuilding."
    )
    args = parser.parse_args()

    logger.info("=== Starting Multi-Task PyG ETL Pipeline ===")
    logger.info(f"MAX_MIP_GAP filter   : {MAX_MIP_GAP * 100:.1f}%")
    logger.info(f"Categories targeted  : {args.categories}")

    for category in args.categories:
        cat_raw_dir   = os.path.join(args.base_raw_dir, category)
        cat_pyg_dir   = os.path.join(args.base_pyg_dir, category)
        processed_dir = os.path.join(cat_pyg_dir, "processed")

        os.makedirs(processed_dir, exist_ok=True)

        if args.clear_processed:
            old_files = glob.glob(os.path.join(processed_dir, "data_*.pt"))
            logger.info(f"[{category}] Purging {len(old_files)} existing .pt tensors.")
            for f in old_files:
                os.remove(f)

        logger.info(f"\n=== Processing Category: {category} ===")

        # Centralized metadata loading from Phase 1 summary
        summary_path = os.path.join(args.base_raw_dir, f"generation_summary_{category}.json")
        category_metadata = {}
        
        if os.path.exists(summary_path):
            with open(summary_path, 'r') as f:
                summary_data = json.load(f)
                for meta in summary_data.get('metadata', []):
                    category_metadata[meta['instance']] = meta
            logger.info(f"[{category}] Central metadata successfully loaded.")
        else:
            logger.warning(f"[{category}] Summary JSON not found at: {summary_path}")

        instance_dirs = sorted([d for d in glob.glob(os.path.join(cat_raw_dir, "*")) if os.path.isdir(d)])
        logger.info(f"Target subdirectories found: {len(instance_dirs)}")

        global_graph_counter = 0

        for inst_dir in tqdm(instance_dirs, desc=f"  {category} ETL Progress"):
            instance_name = os.path.basename(inst_dir)
            inst_metadata = category_metadata.get(instance_name, {})
            
            num_generated = process_instance(
                inst_dir          = inst_dir,
                global_idx_start  = global_graph_counter,
                processed_dir     = processed_dir,
                metadata          = inst_metadata,
            )
            global_graph_counter += num_generated

        logger.info(f"[{category}] Phase 2 Completed: {global_graph_counter} graphs successfully materialized in {processed_dir}")

    logger.info("\n=== ETL Pipeline Fully Finalized ===")

if __name__ == "__main__":
    main()