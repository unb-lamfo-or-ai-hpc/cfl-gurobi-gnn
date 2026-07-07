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

@dataclass
class ModelFeatures:
    """Stores structural features of the original (unpresolved) MILP model."""
    num_vars:       int
    num_constrs:    int
    num_binary:     int
    num_integer:    int
    num_continuous: int
    num_nonzeros:   int
    var_types:       np.ndarray         # dtype object: 'C', 'B', or 'I'
    var_obj_coeffs:  np.ndarray         # objective coefficients
    var_lb:          np.ndarray         # lower bounds
    var_ub:          np.ndarray         # upper bounds
    var_names:       List[str]
    constr_senses:   np.ndarray         # dtype object: '<', '=', or '>'
    constr_rhs:      np.ndarray         # right-hand-side values
    constr_names:    List[str]
    constraint_matrix: Dict[str, np.ndarray]  # keys: 'row', 'col', 'data'


@dataclass
class SolutionFeatures:
    """Stores features of a single incumbent solution from the B&B tree."""
    objective_value: float
    mip_gap:         float
    node_count:      int
    solution_time:   float
    solution_vector: np.ndarray         # variable assignments (B&B incumbent)
    is_feasible:     bool
    is_optimal:      bool
    integrality_gap: Optional[float] = None
    bound:           Optional[float] = None


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
    original_features: ModelFeatures,
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

    The graph encodes the full MILP structure derived from the original
    (unpresolved) model, with the incumbent solution vector as the node-level
    prediction target and graph-level multi-task labels.

    Args:
        original_features: ModelFeatures extracted from the original MILP.
        sol_vector:        Incumbent solution vector from Gurobi (via PoolNX).
        lp_vector_root:    LP relaxation at the B&B root node (no log-scale).
        mip_gap:           MIP gap of this incumbent (fraction, e.g. 0.05).
        exec_time:         Wall-clock time when this incumbent was found (s).
        is_optimal:        True if mip_gap <= 1e-4.
        incumbent_node:    B&B node number where this incumbent was found.
        instance_name:     Filename of the source .lp instance.
        metadata:          Dict loaded from metadata.json (v4 generator).

    Returns:
        HeteroData if successful, None if a shape mismatch or error occurs.
    """
    try:
        graph_data = HeteroData()

        # ----------------------------------------------------------------
        # 1. Variable Node Features  [N_v, 7]
        #    Columns: [obj, lb, ub, is_cont, is_bin, is_int, lp_relax]
        #
        #    Log-scale IS applied to obj, lb, ub (Big-M can be 1e6+).
        #    Log-scale is NOT applied to lp_relax (must stay in [0, 1]).
        # ----------------------------------------------------------------
        obj_tensor = sanitize_array(original_features.var_obj_coeffs,
                                    name="obj", apply_log_scale=True)
        lb_tensor  = sanitize_array(original_features.var_lb,
                                    name="lb",  apply_log_scale=True)
        ub_tensor  = sanitize_array(original_features.var_ub,
                                    name="ub",  apply_log_scale=True)

        # One-hot encoding of variable type.
        # var_types stores string characters: 'C' (continuous), 'B' (binary),
        # 'I' (general integer). Comparison to string literals is robust
        # across all numpy dtype variants.
        is_cont = torch.FloatTensor(
            (original_features.var_types == 'C').astype(float)).unsqueeze(-1)
        is_bin  = torch.FloatTensor(
            (original_features.var_types == 'B').astype(float)).unsqueeze(-1)
        is_int  = torch.FloatTensor(
            (original_features.var_types == 'I').astype(float)).unsqueeze(-1)

        # LP relaxation vector: shape check against original model.
        # If the stored vector has the wrong length (e.g. from a partially
        # presolved model), fall back to zeros to avoid torch.cat crash.
        if len(lp_vector_root) != original_features.num_vars:
            logger.warning(
                f"[{instance_name}] LP vector length mismatch: "
                f"expected {original_features.num_vars}, "
                f"got {len(lp_vector_root)}. Padding with zeros."
            )
            lp_vector_root = np.zeros(original_features.num_vars)

        lp_tensor = sanitize_array(lp_vector_root,
                                   name="lp_relax", apply_log_scale=False)

        v_features = torch.cat(
            [obj_tensor, lb_tensor, ub_tensor,
             is_cont, is_bin, is_int, lp_tensor],
            dim=1
        )   # shape: [N_v, 7]

        graph_data['variable'].x = v_features

        # ----------------------------------------------------------------
        # 2. Constraint Node Features  [N_c, 5]
        #    Columns: [rhs, sense_lt, sense_eq, sense_gt, dummy]
        #
        #    constr_senses stores Python string characters from Gurobi's
        #    c.Sense attribute ('<', '=', '>').  String comparison is used
        #    here instead of ASCII integers (60, 61, 62), which is fragile
        #    and depends on the underlying numpy array dtype.
        # ----------------------------------------------------------------
        rhs_tensor = sanitize_array(original_features.constr_rhs,
                                    name="rhs", apply_log_scale=True)

        sense_lt = torch.FloatTensor(
            (original_features.constr_senses == '<').astype(float)).unsqueeze(-1)
        sense_eq = torch.FloatTensor(
            (original_features.constr_senses == '=').astype(float)).unsqueeze(-1)
        sense_gt = torch.FloatTensor(
            (original_features.constr_senses == '>').astype(float)).unsqueeze(-1)

        # Dummy feature column (ones): pads the constraint feature vector to
        # a consistent dimension, following the convention in Gasse et al.
        c_dummy = torch.ones_like(rhs_tensor)

        c_features = torch.cat(
            [rhs_tensor, sense_lt, sense_eq, sense_gt, c_dummy],
            dim=1
        )   # shape: [N_c, 5]

        graph_data['constraint'].x = c_features

        # ----------------------------------------------------------------
        # 3. Bipartite Edge Indices and Attributes
        #
        #    The constraint matrix A is stored in COO format with keys
        #    'row' (constraint index), 'col' (variable index), 'data' (coeff).
        #
        #    Two directed edge sets are created for heterogeneous message
        #    passing:
        #       v -> c  ('variable', 'rev_coef', 'constraint')
        #       c -> v  ('constraint', 'coef', 'variable')
        #
        #    Both edge sets share the same edge_attr (log-scaled A entries)
        #    because the coefficient value is symmetric across both directions.
        # ----------------------------------------------------------------
        rows        = torch.LongTensor(original_features.constraint_matrix['row'])
        cols        = torch.LongTensor(original_features.constraint_matrix['col'])
        edge_weight = sanitize_array(original_features.constraint_matrix['data'],
                                     name="A", apply_log_scale=True)

        # edge_index convention in PyG: shape [2, E], first row = source.
        edge_index_v2c = torch.stack([cols, rows], dim=0)  # variable -> constraint
        edge_index_c2v = torch.stack([rows, cols], dim=0)  # constraint -> variable

        graph_data['variable',   'rev_coef', 'constraint'].edge_index = edge_index_v2c
        graph_data['variable',   'rev_coef', 'constraint'].edge_attr  = edge_weight
        graph_data['constraint', 'coef',     'variable'  ].edge_index = edge_index_c2v
        graph_data['constraint', 'coef',     'variable'  ].edge_attr  = edge_weight

        # ----------------------------------------------------------------
        # 4. Node-Level Target Labels
        #    y: the incumbent solution vector (float), used with
        #       BCEWithLogitsLoss on discrete variables only.
        # ----------------------------------------------------------------
        if len(sol_vector) != original_features.num_vars:
            logger.warning(
                f"[{instance_name}] Solution vector length mismatch: "
                f"expected {original_features.num_vars}, "
                f"got {len(sol_vector)}. Skipping graph."
            )
            return None

        graph_data['variable'].y = torch.FloatTensor(sol_vector)

        # Discrete variable mask: True for binary and general integer variables.
        # This mask is used by the training loop to apply the loss only to
        # variables whose values the GNN must predict.
        is_discrete = (
            torch.FloatTensor((original_features.var_types == 'B').astype(float)) +
            torch.FloatTensor((original_features.var_types == 'I').astype(float))
        ).clamp(0.0, 1.0)
        graph_data['variable'].is_discrete = is_discrete   # shape: [N_v]

        # ----------------------------------------------------------------
        # 5. Graph-Level Multi-Task Labels
        # ----------------------------------------------------------------
        graph_data.mip_gap      = float(mip_gap)
        graph_data.exec_time    = float(exec_time)
        graph_data.is_optimal   = bool(mip_gap <= 1e-4)
        graph_data.incumbent_node = int(incumbent_node)
        graph_data.instance_name  = str(instance_name)

        # ----------------------------------------------------------------
        # 6. Complexity Metadata (from cfl_gnn_data_generator_v4.py)
        #    Propagated for stratified train/val/test splits and curriculum
        #    learning. Defaults guard against missing metadata.json.
        # ----------------------------------------------------------------
        graph_data.complexity_class  = metadata.get('complexity_class',  'unknown')
        graph_data.probe_node_count  = metadata.get('probe_node_count',  -1)
        graph_data.presolve_used     = metadata.get('presolve_used',     False)

        return graph_data

    except Exception as e:
        logger.error(
            f"[{instance_name}] Graph construction failed: {e}\n"
            f"{traceback.format_exc()}"
        )
        return None


# ---------------------------------------------------------------------------
# Per-Instance ETL
# ---------------------------------------------------------------------------

def process_instance(inst_dir: str,
                     global_idx_start: int,
                     processed_dir: str) -> int:
    """
    Reads one instance directory and generates one PyG .pt file per
    qualifying incumbent solution.

    File layout expected inside inst_dir:
        original_features.pickle.gz  — ModelFeatures dataclass (from v4)
        incumbents.parquet            — one row per incumbent (pool solutions)
        node_relaxations.parquet      — LP relaxation vectors (optional)
        metadata.json                 — complexity metadata (from v4)

    Args:
        inst_dir (str):        Path to the instance directory.
        global_idx_start (int): Starting graph index for naming output files.
        processed_dir (str):   Output directory for .pt files.

    Returns:
        int: Number of graphs successfully written to disk.
    """
    features_path    = os.path.join(inst_dir, "original_features.pickle.gz")
    incumbents_path  = os.path.join(inst_dir, "incumbents.parquet")
    relaxations_path = os.path.join(inst_dir, "node_relaxations.parquet")
    metadata_path    = os.path.join(inst_dir, "metadata.json")

    # Both the feature file and the incumbent file are required.
    if not os.path.exists(features_path):
        logger.warning(f"Missing original_features.pickle.gz in {inst_dir}")
        return 0
    if not os.path.exists(incumbents_path):
        logger.warning(f"Missing incumbents.parquet in {inst_dir}")
        return 0

    instance_name = os.path.basename(inst_dir)

    try:
        # ----------------------------------------------------------------
        # Load model features (original unpresolved model)
        # ----------------------------------------------------------------
        with gzip.open(features_path, 'rb') as fh:
            raw = pickle.load(fh)
        model_features: ModelFeatures = raw['model_features']

        # ----------------------------------------------------------------
        # Load incumbent solutions
        # ----------------------------------------------------------------
        df_incumbents = pd.read_parquet(incumbents_path)
        if df_incumbents.empty:
            logger.warning(f"[{instance_name}] No incumbents found. Skipping.")
            return 0

        # ----------------------------------------------------------------
        # Load LP relaxation vector (root node preferred, fallback to first)
        # ----------------------------------------------------------------
        lp_vector_root = np.zeros(model_features.num_vars)
        if os.path.exists(relaxations_path):
            df_relax = pd.read_parquet(relaxations_path)
            root_relax = df_relax[df_relax['node'] == 0]
            if not root_relax.empty:
                lp_vector_root = np.array(root_relax.iloc[0]['relaxation_vector'])
            elif not df_relax.empty:
                logger.warning(
                    f"[{instance_name}] Root node relaxation not found. "
                    f"Using first available relaxation as fallback."
                )
                lp_vector_root = np.array(df_relax.iloc[0]['relaxation_vector'])

        # ----------------------------------------------------------------
        # Load complexity metadata (generated by cfl_gnn_data_generator_v4)
        # ----------------------------------------------------------------
        metadata = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as mf:
                metadata = json.load(mf)
        else:
            logger.warning(
                f"[{instance_name}] metadata.json not found. "
                f"Complexity fields will default to 'unknown'."
            )

        # ----------------------------------------------------------------
        # Generate one graph per qualifying incumbent
        # ----------------------------------------------------------------
        graphs_generated  = 0
        current_global_idx = global_idx_start

        for _, row in df_incumbents.iterrows():

            # Defensive second-layer quality filter.
            # Primary filter is PoolGap=0.10 in cfl_gnn_data_generator_v4.py.
            # This ensures no degraded incumbents slip through if the
            # generator was run with a different PoolGap setting.
            try:
                row_gap = float(row['mip_gap'])
            except (ValueError, KeyError):
                row_gap = 1.0

            if row_gap > MAX_MIP_GAP:
                continue

            sol_vector = np.array(row['solution_vector'])

            graph = build_heterodata(
                original_features = model_features,
                sol_vector        = sol_vector,
                lp_vector_root    = lp_vector_root,
                mip_gap           = row_gap,
                exec_time         = float(row.get('time', 0.0)),
                is_optimal        = bool(row_gap <= 1e-4),
                incumbent_node    = int(row.get('node', -1)),
                instance_name     = instance_name,
                metadata          = metadata,
            )

            if graph is None:
                continue

            out_file = os.path.join(processed_dir, f"data_{current_global_idx}.pt")
            torch.save(graph, out_file)
            current_global_idx  += 1
            graphs_generated    += 1

        return graphs_generated

    except Exception as e:
        logger.error(
            f"[{instance_name}] Instance processing failed: {e}\n"
            f"{traceback.format_exc()}"
        )
        return 0


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
        logger.info(f"Instances found: {len(instance_dirs)}")

        global_graph_counter = 0

        for inst_dir in tqdm(instance_dirs, desc=f"  {category}"):
            num_generated = process_instance(
                inst_dir          = inst_dir,
                global_idx_start  = global_graph_counter,
                processed_dir     = processed_dir,
            )
            global_graph_counter += num_generated

        logger.info(
            f"[{category}] Done: {global_graph_counter} graphs saved to "
            f"{processed_dir}"
        )

    logger.info("\n=== ETL Pipeline Finished ===")


if __name__ == "__main__":
    main()
