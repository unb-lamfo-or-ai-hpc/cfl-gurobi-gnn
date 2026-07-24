"""
Phase 2: PyG Graph Construction (Multi-Task Neural Diving)
==========================================================
Generates one bipartite HeteroData graph per Gurobi incumbent solution,
encoding the MILP structure as a variable-constraint bipartite graph and
attaching multi-task labels for node-level (solution assignment) and
graph-level (MIP gap, solve time, optimality) prediction.

Architecture:
    Variable nodes  : [obj_coeff, lb, ub, is_cont, is_bin, is_int, lp_relax]  -> shape [N_v, 7]
    Constraint nodes: [rhs, sense_lt, sense_eq, sense_gt, dummy]               -> shape [N_c, 5]
    Edges (v->c)    : log-scaled constraint matrix coefficients                 -> shape [nnz, 1]
    Edges (c->v)    : same coefficients, reversed direction                    -> shape [nnz, 1]

Key Design Decisions:
    - Log-scale (sign * ln(1 + |x|)) is applied to obj, lb, ub, rhs, and A
      coefficients to compress Big-M magnitudes while preserving sign.
    - The LP relaxation vector is stored WITHOUT log-scale to preserve the
      [0, 1] range of fractional binary variables.
    - Constraint senses are compared as Python strings ('<', '=', '>'),
      NOT as ASCII integers (60, 61, 62), which is dtype-fragile.
    - MAX_MIP_GAP = 0.10 matches the PoolGap set in cfl_gnn_data_generator_v4.py.
      This post-hoc filter acts as a defensive second layer.
    - Complexity metadata (complexity_class, probe_node_count, presolve_used)
      is propagated from metadata.json into each PyG Data object to enable
      stratified training splits and curriculum learning.
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
from torch_geometric.data import HeteroData
from tqdm import tqdm
from dataclasses import dataclass
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quality Filter — must match PoolGap in cfl_gnn_data_generator_v4.py
# ---------------------------------------------------------------------------
MAX_MIP_GAP = 0.10   # Discard incumbents with MIP gap > 10%

# ---------------------------------------------------------------------------
# Data Classes (must match the definitions in cfl_gnn_data_generator_v4.py
# so that pickle can deserialise the stored ModelFeatures objects)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Data Definitions (Matched with Phase 1 Generator v7)
# ---------------------------------------------------------------------------
from collections import namedtuple

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

def sanitize_array(arr: np.ndarray,
                   name: str = "array",
                   apply_log_scale: bool = False) -> torch.Tensor:
    """
    Cleans a numpy array and optionally applies signed log-scale compression.

    Steps:
        1. Replace NaN, +Inf, -Inf with bounded finite values.
        2. Clip to [-60000, 60000] to guard against extreme Big-M coefficients.
        3. Optionally apply: x -> sign(x) * ln(1 + |x|)

    The log-scale transform is appropriate for objective coefficients, bounds,
    RHS values, and constraint matrix entries. It must NOT be applied to the
    LP relaxation vector, which must remain in its natural [0, 1] range for
    binary variables.

    Args:
        arr (np.ndarray): 1-D input array.
        name (str): Name used in debug messages.
        apply_log_scale (bool): Whether to apply signed log compression.

    Returns:
        torch.Tensor: Shape [len(arr), 1], dtype float32.
    """
    arr = np.nan_to_num(arr, nan=0.0, posinf=60000.0, neginf=-60000.0)
    arr = np.clip(arr, -60000.0, 60000.0)

    if apply_log_scale:
        # Signed log: preserves sign, compresses magnitude.
        # Maps 0 -> 0, avoids discontinuity at origin.
        arr = np.sign(arr) * np.log1p(np.abs(arr))

    return torch.FloatTensor(arr).unsqueeze(-1)


# ---------------------------------------------------------------------------
# Graph Builder
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
    Assembles a single HeteroData bipartite graph for one incumbent solution.
    """
    try:
        graph_data = HeteroData()

        # 1. Variable Node Features
        obj_tensor = sanitize_array(variable_features.obj_coeffs, name="obj", apply_log_scale=True)
        lb_tensor  = sanitize_array(variable_features.lower_bounds, name="lb", apply_log_scale=True)
        ub_tensor  = sanitize_array(variable_features.upper_bounds, name="ub", apply_log_scale=True)

        is_cont = torch.FloatTensor((variable_features.types == 'C').astype(float)).unsqueeze(-1)
        is_bin  = torch.FloatTensor((variable_features.types == 'B').astype(float)).unsqueeze(-1)
        is_int  = torch.FloatTensor((variable_features.types == 'I').astype(float)).unsqueeze(-1)

        if len(lp_vector_root) != model_features.num_vars:
            lp_vector_root = np.zeros(model_features.num_vars)
            
        lp_tensor = sanitize_array(lp_vector_root, name="lp_relax", apply_log_scale=False)

        graph_data['variable'].x = torch.cat(
            [obj_tensor, lb_tensor, ub_tensor, is_cont, is_bin, is_int, lp_tensor], dim=1
        )

        # 2. Constraint Node Features
        rhs_tensor = sanitize_array(constr_features.rhs_values, name="rhs", apply_log_scale=True)
        sense_lt = torch.FloatTensor((constr_features.senses == '<').astype(float)).unsqueeze(-1)
        sense_eq = torch.FloatTensor((constr_features.senses == '=').astype(float)).unsqueeze(-1)
        sense_gt = torch.FloatTensor((constr_features.senses == '>').astype(float)).unsqueeze(-1)
        c_dummy = torch.ones_like(rhs_tensor)

        graph_data['constraint'].x = torch.cat(
            [rhs_tensor, sense_lt, sense_eq, sense_gt, c_dummy], dim=1
        )

        # 3. Bipartite Edge Indices and Attributes
        # edge_indices shape is (2, E) where [0] is rows (constraints) and [1] is cols (variables)
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
            return None

        graph_data['variable'].y = torch.FloatTensor(sol_vector)
        graph_data['variable'].is_discrete = (is_bin + is_int).clamp(0.0, 1.0).squeeze(-1)

        # 5. Graph-Level Multi-Task Labels & Metadata
        graph_data.mip_gap      = float(mip_gap)
        graph_data.exec_time    = float(exec_time)
        graph_data.is_optimal   = bool(mip_gap <= 1e-4)
        graph_data.incumbent_node = int(incumbent_node)
        graph_data.instance_name  = str(instance_name)
        
        graph_data.complexity_class  = metadata.get('complexity_class', 'unknown')
        graph_data.probe_node_count  = metadata.get('probe_node_count', -1)
        graph_data.presolve_used     = (metadata.get('presolve_setting', 0) == -1)

        return graph_data

    except Exception as e:
        logger.error(f"[{instance_name}] Graph construction failed: {e}\n{traceback.format_exc()}")
        return None

# ---------------------------------------------------------------------------
# Per-Instance ETL
# ---------------------------------------------------------------------------

def process_instance(inst_dir: str,
                     global_idx_start: int,
                     processed_dir: str,
                     metadata: dict) -> int: # <-- AÑADIR metadata AQUÍ
                     
    # ... código de paths e incumbents existente ...
    # Eliminar la lectura de metadata.json individual
    
    try:
        # Load model features from the new tuple structure
        with gzip.open(features_path, 'rb') as fh:
            raw = pickle.load(fh)
            
        model_features = raw['model_features']
        variable_features = raw['variable_features']
        constraint_features = raw['constraint_features']
        edge_indices = raw['edge_indices']
        edge_features = raw['edge_features']

        # ... código para df_incumbents y df_relax existente ...

        # En el bucle de incumbents, actualizar la llamada a build_heterodata:
        for _, row in df_incumbents.iterrows():
            # ... validación de row_gap existente ...

            graph = build_heterodata(
                model_features    = model_features,
                variable_features = variable_features,
                constr_features   = constraint_features,
                edge_indices      = edge_indices,
                edge_features     = edge_features,
                sol_vector        = sol_vector,
                lp_vector_root    = lp_vector_root,
                mip_gap           = row_gap,
                exec_time         = float(row.get('time', 0.0)),
                is_optimal        = bool(row_gap <= 1e-4),
                incumbent_node    = int(row.get('node', -1)),
                instance_name     = instance_name,
                metadata          = metadata,
            )
            # ... guardado de graph existente ...

# ---------------------------------------------------------------------------
# Main ETL Pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 2: Build PyG HeteroData graphs from Gurobi incumbents"
    )
    parser.add_argument(
        '--categories', nargs='+',
        default=["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"],
        help="List of instance categories to process."
    )
    parser.add_argument(
        '--base_raw_dir',
        default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps",
        help="Root directory containing raw instance subdirectories."
    )
    parser.add_argument(
        '--base_pyg_dir',
        default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset",
        help="Root directory where processed .pt files will be written."
    )
    parser.add_argument(
        '--clear_processed', action='store_true',
        help="If set, delete existing data_*.pt files before rebuilding."
    )
    args = parser.parse_args()

    logger.info("=== Starting Multi-Task PyG ETL Pipeline ===")
    logger.info(f"MAX_MIP_GAP filter   : {MAX_MIP_GAP * 100:.1f}%")
    logger.info(f"Categories           : {args.categories}")

    for category in args.categories:
        cat_raw_dir   = os.path.join(args.base_raw_dir, category)
        cat_pyg_dir   = os.path.join(args.base_pyg_dir, category)
        processed_dir = os.path.join(cat_pyg_dir, "processed")

        os.makedirs(processed_dir, exist_ok=True)

        # Optionally clean stale .pt files from a previous run.
        if args.clear_processed:
            old_files = glob.glob(os.path.join(processed_dir, "data_*.pt"))
            logger.info(
                f"[{category}] Removing {len(old_files)} existing .pt files."
            )
            for f in old_files:
                os.remove(f)

        instance_dirs = sorted([
            d for d in glob.glob(os.path.join(cat_raw_dir, "*"))
            if os.path.isdir(d)
        ])

        logger.info(f"\n=== Category: {category} ===")

        # Load category metadata summary
        summary_path = os.path.join(args.base_raw_dir, f"generation_summary_{category}.json")
        category_metadata = {}
        if os.path.exists(summary_path):
            with open(summary_path, 'r') as f:
                summary_data = json.load(f)
                for meta in summary_data.get('metadata', []):
                    category_metadata[meta['instance']] = meta
        else:
            logger.warning(f"[{category}] Summary JSON not found: {summary_path}")

        instance_dirs = sorted([d for d in glob.glob(os.path.join(cat_raw_dir, "*")) if os.path.isdir(d)])
        logger.info(f"Instances found: {len(instance_dirs)}")

        global_graph_counter = 0

        for inst_dir in tqdm(instance_dirs, desc=f"  {category}"):
            instance_name = os.path.basename(inst_dir)
            inst_metadata = category_metadata.get(instance_name, {})
            
            num_generated = process_instance(
                inst_dir          = inst_dir,
                global_idx_start  = global_graph_counter,
                processed_dir     = processed_dir,
                metadata          = inst_metadata,  # <-- Pasar la metadata aquí
            )
            global_graph_counter += num_generated

        logger.info(
            f"[{category}] Done: {global_graph_counter} graphs saved to "
            f"{processed_dir}"
        )

    logger.info("\n=== ETL Pipeline Finished ===")


if __name__ == "__main__":
    main()
