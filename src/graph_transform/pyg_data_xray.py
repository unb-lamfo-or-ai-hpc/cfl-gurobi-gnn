"""
Data X-Ray: Deep Tensor Diagnostic (PyG) and Traceability
=========================================================
Inspects a generated .pt file to search for dimensional anomalies
(broadcasting errors), label distributions, and LP bounds.
It also cross-references the data with the new Phase 1 CSV audit report.
"""

import os
import torch
import pandas as pd
import numpy as np
import argparse

def inverse_log_scale(tensor: torch.Tensor) -> torch.Tensor:
    """Reverses the signed log1p transformation."""
    return torch.sign(tensor) * (torch.exp(torch.abs(tensor)) - 1)

def x_ray_pt_file(pt_path):
    print(f"\n{'='*60}")
    print(f" 1. PyG GRAPH X-RAY (.pt)")
    print(f" File: {pt_path}")
    print(f"{'='*60}")
    
    if not os.path.exists(pt_path):
        print(f"[ERROR] File not found: {pt_path}")
        return None, None

    # Load the graph
    data = torch.load(pt_path, map_location='cpu', weights_only=False)
    
    # 1.1 General Metadata
    print("\n--- GRAPH-LEVEL ATTRIBUTES ---")
    for key in data.keys():
        if key not in ['variable', 'constraint'] and not isinstance(key, tuple):
            val = getattr(data, key, "N/A")
            print(f" -> {key}: {val}")

    instance_name = getattr(data, 'instance_name', None)
    complexity_class = getattr(data, 'complexity_class', 'unknown')

    # 1.2 Feature Tensor Analysis ('x')
    var_x = data['variable'].x
    print("\n--- FEATURE TENSOR (variable.x) ---")
    print(f" -> Shape: {var_x.shape}")
    
    if var_x.shape[1] >= 7:
        print(" -> Column breakdown:")
        print(f"    Col 0 (Obj Coef log) : Min={var_x[:, 0].min():.4f}, Max={var_x[:, 0].max():.4f}")
        print(f"    Col 1 (LB log)       : Min={var_x[:, 1].min():.4f}, Max={var_x[:, 1].max():.4f}")
        print(f"    Col 2 (UB log)       : Min={var_x[:, 2].min():.4f}, Max={var_x[:, 2].max():.4f}")
        print(f"    Col 3 (Is Cont)      : 1.0s = {(var_x[:, 3] == 1.0).sum().item()}")
        print(f"    Col 4 (Is Bin)       : 1.0s = {(var_x[:, 4] == 1.0).sum().item()}")
        print(f"    Col 5 (Is Int)       : 1.0s = {(var_x[:, 5] == 1.0).sum().item()}")
        print(f"    Col 6 (LP raw)       : Min={var_x[:, 6].min():.4f}, Max={var_x[:, 6].max():.4f}")
        
        # Bound Validation (Reverse log-scale for comparison)
        ub_raw = inverse_log_scale(var_x[:, 2])
        lp_raw = var_x[:, 6]
        violations = (lp_raw > ub_raw + 1e-4).sum().item()
        
        if violations > 0:
            print(f"\n    [RED ALERT] LP > real UB: {violations} bound violations detected.")
        else:
            print(f"\n    [OK] LP relaxation vector is strictly within UB bounds.")

    # 1.3 Target Tensor Analysis ('y')
    if 'y' in data['variable']:
        var_y = data['variable'].y
        print("\n--- TARGET TENSOR (variable.y) ---")
        print(f" -> Shape: {var_y.shape}")
        
        zeros = (var_y == 0.0).sum().item()
        ones = (var_y == 1.0).sum().item()
        fractionals = var_y.numel() - zeros - ones
        
        # Calculate mathematical weight for BCEWithLogitsLoss
        pos_weight = zeros / ones if ones > 0 else float('inf')
        
        print(f" -> Values at 0.0 (Majority Class) : {zeros}")
        print(f" -> Values at 1.0 (Minority Class) : {ones}")
        print(f" -> Fractional values              : {fractionals}")
        print(f" -> NaN values                     : {torch.isnan(var_y).sum().item()}")
        print(f"\n    [!] TRAINING RECOMMENDATION:")
        print(f"        Approximate 'pos_weight' for BCEWithLogitsLoss: {pos_weight:.2f}")
    else:
        print("\n--- TARGET TENSOR (variable.y) NOT FOUND ---")

    # 1.4 Bipartite Topology Analysis
    edge_idx = data['variable', 'rev_coef', 'constraint'].edge_index
    print("\n--- GRAPH TOPOLOGY ---")
    print(f" -> Constraints (constraint.x shape): {data['constraint'].x.shape}")
    print(f" -> Edges (edge_index shape): {edge_idx.shape}")
    
    return instance_name, complexity_class


def x_ray_audit_csv(csv_path, target_instance):
    print(f"\n{'='*60}")
    print(f" 2. PHASE 1 REPORT AUDIT (phase1_audit_report.csv)")
    print(f" File: {csv_path}")
    print(f"{'='*60}")
    
    if not os.path.exists(csv_path):
        print(f"[WARN] CSV report not found at: {csv_path}")
        return
        
    df = pd.read_csv(csv_path)
    instance_data = df[df['instance'] == target_instance]
    
    if instance_data.empty:
        print(f"[WARN] Instance {target_instance} does not exist in the CSV report.")
    else:
        print(f" -> Record found for {target_instance}:")
        print(instance_data[['category', 'runtime_sec', 'n_incumbents', 'best_mip_gap_pct']].to_string(index=False))


def x_ray_incumbents_parquet(instance_dir):
    print(f"\n{'='*60}")
    print(f" 3. SOLUTION POOL AUDIT (Phase 1 Parquet)")
    print(f" Directory: {instance_dir}")
    print(f"{'='*60}")
    
    parquet_path = os.path.join(instance_dir, "incumbents.parquet")
    
    if not os.path.exists(parquet_path):
        print(f"[ERROR] Solutions file not found: {parquet_path}")
        return
        
    df = pd.read_parquet(parquet_path)
    print(f" -> Total stored solutions (rows): {len(df)}")
    
    if len(df) > 0:
        print("\n -> Summary of the top 3 solutions:")
        cols_to_show = ['node', 'objective', 'bound', 'mip_gap', 'time']
        print(df[cols_to_show].head(3).to_string())
        
        sol_vec_0 = df.iloc[0]['solution_vector']
        print(f"\n -> Solution vector dimension on disk: {len(sol_vec_0)}")


def main():
    parser = argparse.ArgumentParser(description="Data X-Ray for PyG Graphs")
    parser.add_argument('--category', type=str, default="CFL_medium_instance",
                        help='Category to inspect (e.g., CFL_medium_instance)')
    parser.add_argument('--data_idx', type=int, default=0,
                        help='Index of the data_X.pt file to inspect (default: 0)')
    args = parser.parse_args()

    pt_file = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset/{args.category}/processed/data_{args.data_idx}.pt"
    audit_csv = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis/phase1_audit_report_{args.category}.csv"
    
    instance_name, complexity = x_ray_pt_file(pt_file)
    
    if instance_name:
        x_ray_audit_csv(audit_csv, instance_name)
        
        # Trace back to the raw directory
        raw_instance_dir = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps/{args.category}/{instance_name}"
        x_ray_incumbents_parquet(raw_instance_dir)
    else:
        print("\n[WARN] The .pt file did not load correctly or is missing metadata. Traceability aborted.")

if __name__ == "__main__":
    main()