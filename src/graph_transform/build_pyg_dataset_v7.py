"""
Phase 2: PyG Graph Construction (Multi-Task Neural Diving)
==========================================================
Generates one bipartite HeteroData graph per Gurobi incumbent solution.

V7 Updates:
- Edge Index Auto-Detection: Dynamically routes source/target mappings 
  to prevent GPU out-of-bounds asserts regardless of Phase 1 transpose state.
- Epoch Time Normalization: Corrects Gurobi Unix timestamps to relative seconds.
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

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

ModelFeatures = namedtuple('ModelFeatures', ['num_vars', 'num_constrs', 'num_binary', 'num_integer', 'num_continuous', 'obj_sense', 'obj_offset'])
VariableFeatures = namedtuple('VariableFeatures', ['types', 'lower_bounds', 'upper_bounds', 'obj_coeffs'])
ConstraintFeatures = namedtuple('ConstraintFeatures', ['senses', 'rhs_values', 'row_norms'])

def sanitize_array(arr: np.ndarray, name: str = "array", apply_log_scale: bool = False) -> torch.Tensor:
    arr = np.nan_to_num(arr, nan=0.0, posinf=60000.0, neginf=-60000.0)
    arr = np.clip(arr, -60000.0, 60000.0)
    if apply_log_scale:
        arr = np.sign(arr) * np.log1p(np.abs(arr))
    return torch.FloatTensor(arr).unsqueeze(-1)

def build_heterodata(
    model_features: ModelFeatures, variable_features: VariableFeatures, constr_features: ConstraintFeatures,
    edge_indices: np.ndarray, edge_features: np.ndarray, sol_vector: np.ndarray,
    lp_vector_root: np.ndarray, mip_gap: float, exec_time: float, is_optimal: bool,
    incumbent_node: int, instance_name: str, metadata: dict
) -> Optional[HeteroData]:
    try:
        graph_data = HeteroData()

        # 1. Variable Features
        obj_tensor = sanitize_array(variable_features.obj_coeffs, apply_log_scale=True)
        lb_tensor  = sanitize_array(variable_features.lower_bounds, apply_log_scale=True)
        ub_tensor  = sanitize_array(variable_features.upper_bounds, apply_log_scale=True)
        is_cont = torch.FloatTensor((variable_features.types == 'C').astype(float)).unsqueeze(-1)
        is_bin  = torch.FloatTensor((variable_features.types == 'B').astype(float)).unsqueeze(-1)
        is_int  = torch.FloatTensor((variable_features.types == 'I').astype(float)).unsqueeze(-1)

        if len(lp_vector_root) != model_features.num_vars:
            lp_vector_root = np.zeros(model_features.num_vars)
        lp_tensor = sanitize_array(lp_vector_root, apply_log_scale=False)

        graph_data['variable'].x = torch.cat([obj_tensor, lb_tensor, ub_tensor, is_cont, is_bin, is_int, lp_tensor], dim=1)

        # 2. Constraint Features
        rhs_tensor = sanitize_array(constr_features.rhs_values, apply_log_scale=True)
        sense_lt = torch.FloatTensor((constr_features.senses == '<').astype(float)).unsqueeze(-1)
        sense_eq = torch.FloatTensor((constr_features.senses == '=').astype(float)).unsqueeze(-1)
        sense_gt = torch.FloatTensor((constr_features.senses == '>').astype(float)).unsqueeze(-1)
        c_dummy = torch.ones_like(rhs_tensor)

        graph_data['constraint'].x = torch.cat([rhs_tensor, sense_lt, sense_eq, sense_gt, c_dummy], dim=1)

        # 3. Bipartite Edge Indices (V7: Robust Auto-Detection)
        idx_a = torch.LongTensor(edge_indices[0])
        idx_b = torch.LongTensor(edge_indices[1])
        edge_weight = sanitize_array(edge_features, apply_log_scale=True)

        if idx_a.max() < model_features.num_constrs and idx_b.max() < model_features.num_vars:
            cons_idx = idx_a
            var_idx  = idx_b
        elif idx_b.max() < model_features.num_constrs and idx_a.max() < model_features.num_vars:
            cons_idx = idx_b
            var_idx  = idx_a
        else:
            cons_idx = idx_a
            var_idx  = idx_b

        edge_index_v2c = torch.stack([var_idx, cons_idx], dim=0)  
        edge_index_c2v = torch.stack([cons_idx, var_idx], dim=0)  

        graph_data['variable', 'rev_coef', 'constraint'].edge_index = edge_index_v2c
        graph_data['variable', 'rev_coef', 'constraint'].edge_attr  = edge_weight
        graph_data['constraint', 'coef', 'variable'].edge_index = edge_index_c2v
        graph_data['constraint', 'coef', 'variable'].edge_attr  = edge_weight

        # 4. Labels & Context
        if len(sol_vector) != model_features.num_vars: return None
        graph_data['variable'].y = torch.FloatTensor(sol_vector)
        graph_data['variable'].is_discrete = (is_bin + is_int).clamp(0.0, 1.0).squeeze(-1)
        graph_data.mip_gap, graph_data.exec_time = float(mip_gap), float(exec_time)
        graph_data.is_optimal = bool(mip_gap <= 1e-4)
        graph_data.incumbent_node = int(incumbent_node)
        graph_data.instance_name = str(instance_name)
        graph_data.complexity_class = metadata.get('complexity_class', 'unknown')
        return graph_data

    except Exception as e:
        logger.error(f"[{instance_name}] Failed: {e}")
        return None

def process_instance(inst_dir, global_idx_start, processed_dir, metadata, max_mip_gap):
    feat_path = os.path.join(inst_dir, "original_features.pickle.gz")
    inc_path  = os.path.join(inst_dir, "incumbents.parquet")
    rel_path  = os.path.join(inst_dir, "node_relaxations.parquet")
    inst_name = os.path.basename(inst_dir)

    if not os.path.exists(feat_path) or not os.path.exists(inc_path): return 0

    try:
        with gzip.open(feat_path, 'rb') as fh: raw = pickle.load(fh)
        
        lp_vec = np.zeros(raw['model_features'].num_vars)
        if os.path.exists(rel_path):
            df_relax = pd.read_parquet(rel_path, filters=[('node', '==', 0)])
            if not df_relax.empty: lp_vec = np.array(df_relax.iloc[0]['relaxation_vector'])

        base_graph = build_heterodata(
            raw['model_features'], raw['variable_features'], raw['constraint_features'],
            raw['edge_indices'], raw['edge_features'], np.zeros(raw['model_features'].num_vars),
            lp_vec, 1.0, 0.0, False, -1, inst_name, metadata
        )
        if base_graph is None: return 0

        # V7: T0 Timestamp extraction
        try:
            t0 = pq.read_table(inc_path, columns=['time']).to_pandas()['time'].min()
        except:
            t0 = 0.0

        graphs_gen, current_idx = 0, global_idx_start
        stats = {'eval': 0, 'drop': 0, 'oom': 0, 'err': 0}

        # STREAMING PARQUET
        pq_file = pq.ParquetFile(inc_path)
        for batch in pq_file.iter_batches(batch_size=50):
            df_chunk = batch.to_pandas()
            for _, row in df_chunk.iterrows():
                stats['eval'] += 1
                row_gap = float(row.get('mip_gap', 1.0))
                if row_gap > max_mip_gap:
                    stats['drop'] += 1
                    continue

                try:
                    graph = base_graph.clone()
                    graph['variable'].y = torch.FloatTensor(np.array(row['solution_vector']))
                    
                    # V7: Time Normalization
                    raw_time = float(row.get('time', 0.0))
                    graph.exec_time = float(raw_time - t0) if raw_time > 1e8 else float(raw_time)
                    
                    graph.mip_gap = float(row_gap)
                    graph.is_optimal = bool(row_gap <= 1e-4)
                    graph.incumbent_node = int(row.get('node', -1))

                    torch.save(graph, os.path.join(processed_dir, f"data_{current_idx}.pt"))
                    current_idx += 1; graphs_gen += 1
                    del graph
                except MemoryError: stats['oom'] += 1
                except Exception: stats['err'] += 1
            del df_chunk; gc.collect()
            
        del base_graph, raw; gc.collect()
        logger.info(f"[{inst_name}] Eval: {stats['eval']} | Saved: {graphs_gen} | Drop(> {max_mip_gap*100}%): {stats['drop']} | Err: {stats['err']}")
        return graphs_gen

    except Exception as e:
        logger.error(f"[{inst_name}] Fatal Error: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--categories', nargs='+', default=["CFL_easy_instance", "CFL_medium_instance"])
    parser.add_argument('--gaps', nargs='+', type=float, default=[0.10, 0.85])
    parser.add_argument('--base_raw_dir', default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps")
    parser.add_argument('--base_pyg_dir', default="/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset")
    parser.add_argument('--clear_processed', action='store_true')
    parser.add_argument('--analysis_dir', default='/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis')
    args = parser.parse_args()

    if len(args.categories) != len(args.gaps):
        sys.exit(1)

    for cat, gap in zip(args.categories, args.gaps):
        cat_raw = os.path.join(args.base_raw_dir, cat)
        proc_dir = os.path.join(args.base_pyg_dir, cat, "processed")
        os.makedirs(proc_dir, exist_ok=True)

        if args.clear_processed:
            for f in glob.glob(os.path.join(proc_dir, "data_*.pt")): os.remove(f)

        logger.info(f"\n=== Processing {cat} (GAP <= {gap*100}%) ===")
        
        meta_dict = {}
        sum_path = os.path.join(args.analysis_dir, f"generation_summary_{cat}.json")
        if os.path.exists(sum_path):
            with open(sum_path) as f:
                meta_dict = {m['instance']: m for m in json.load(f).get('metadata', [])}

        inst_dirs = sorted([d for d in glob.glob(os.path.join(cat_raw, "*")) if os.path.isdir(d)])
        g_count = 0
        for inst in tqdm(inst_dirs, desc=f"ETL {cat}"):
            g_count += process_instance(inst, g_count, proc_dir, meta_dict.get(os.path.basename(inst), {}), gap)

if __name__ == "__main__":
    main()