"""
Phase 1 Exploratory Data Analysis (EDA) & Audit - v2
====================================================
Validates the raw outputs from cfl_gnn_data_generator_v5.py to isolate
whether the pipeline bugs originate in Phase 1 (Data Generation) or 
Phase 2 (PyG ETL).

This version includes safety checks for missing files and empty dataframes.
"""

import os
import glob
import json
import gzip
import pickle
import pandas as pd
import numpy as np

import argparse
import os

from collections import namedtuple  # ← Add this

# ================================================================
# NAMEDTUPLE DEFINITIONS (must match data generator)
# ================================================================
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


def audit_single_instance(instance_dir):
    """Deep dive into a single instance to verify tensor shapes and distributions."""
    print(f"\n{'='*60}")
    print(f"STEP 1 & 3: DEEP DIVE - {os.path.basename(instance_dir)}")
    print(f"{'='*60}")

    # 1. Metadata
    meta_path = os.path.join(instance_dir, "metadata.json")
    if not os.path.exists(meta_path):
        print(f"[ERROR] Missing metadata.json in {instance_dir}")
        return

    with open(meta_path) as f:
        meta = json.load(f)
    
    print(f"Complexity Class : {meta.get('complexity_class', 'N/A')}")
    print(f"Presolve Setting : {meta.get('presolve_setting', 'N/A')}")
    print(f"Incumbents Saved : {meta.get('num_incumbents_collected', 'N/A')}")
    print(f"Runtime (sec)    : {meta.get('runtime', 'N/A'):.2f}")
    print(f"Status           : {meta.get('status', 'N/A')}")

    # 2. Incumbents Parquet
    inc_path = os.path.join(instance_dir, "incumbents.parquet")
    if not os.path.exists(inc_path):
        print(f"[ERROR] Missing incumbents.parquet in {instance_dir}")
        return
    
    df_inc = pd.read_parquet(inc_path)
    
    if len(df_inc) == 0:
        print(f"[WARN] incumbents.parquet is empty")
        return
    
    print(f"\n--- INCUMBENTS PARQUET ---")
    print(f"Total rows       : {len(df_inc)}")
    print(f"Columns          : {list(df_inc.columns)}")
    
    sol_0 = np.array(df_inc.iloc[0]['solution_vector'])
    n_zeros = (sol_0 == 0.0).sum()
    n_ones  = (sol_0 == 1.0).sum()
    n_frac  = len(sol_0) - n_zeros - n_ones
    
    print(f"\n--- SOLUTION VECTOR (Best Incumbent) ---")
    print(f"Vector Length    : {len(sol_0)}")
    print(f"Zeroes (0.0)     : {n_zeros:,} ({100.0*n_zeros/len(sol_0):.1f}%)")
    print(f"Ones (1.0)       : {n_ones:,} ({100.0*n_ones/len(sol_0):.1f}%)")
    print(f"Fractional       : {n_frac:,}")
    
    # Critical check: For CFL, we expect 10-40% ones, not 90%+
    pct_ones = 100.0 * n_ones / len(sol_0)
    if pct_ones > 80.0:
        print(f"[RED ALERT] Trivial incumbent detected: {pct_ones:.1f}% ones (expected 10-40%)")
    elif pct_ones < 5.0:
        print(f"[WARN] Suspiciously few facilities open: {pct_ones:.1f}%")
    else:
        print(f"[OK] Variable distribution is reasonable")

    # 3. Cross-check with original_features.pickle.gz
    feat_path = os.path.join(instance_dir, "original_features.pickle.gz")
    if not os.path.exists(feat_path):
        print(f"[ERROR] Missing original_features.pickle.gz")
        return
        
    with gzip.open(feat_path, 'rb') as f:
        orig = pickle.load(f)
    
    num_vars = orig['model_features'].num_vars
    num_cons = orig['model_features'].num_constrs
    
    print(f"\n--- SANITY CHECKS ---")
    print(f"Original model: {num_vars} variables, {num_cons} constraints")
    print(f"Solution vector length: {len(sol_0)}")
    
    if num_vars == len(sol_0):
        print(f"[OK] Dimensions match")
    else:
        print(f"[ERROR] Dimension mismatch: {num_vars} != {len(sol_0)}")

    # 4. Compare Pool vs Incumbents (if pool exists)
    sol_path = os.path.join(instance_dir, "solutions.pickle.gz")
    if os.path.exists(sol_path):
        try:
            with gzip.open(sol_path, 'rb') as f:
                sol_data = pickle.load(f)
            
            if 'solution_pool' in sol_data and len(sol_data['solution_pool']) > 0:
                inc_best = df_inc['objective'].min()
                pool_best = min([p['objective'] for p in sol_data['solution_pool']])
                
                print(f"\n--- POOL CONSISTENCY ---")
                print(f"Best incumbent objective : {inc_best:.6f}")
                print(f"Best pool objective      : {pool_best:.6f}")
                print(f"Match (within 1e-6)      : {abs(inc_best - pool_best) < 1e-6}")
            else:
                print(f"[WARN] Solution pool is empty or missing 'solution_pool' key")
        except Exception as e:
            print(f"[WARN] Could not load solutions.pickle.gz: {e}")
    else:
        print(f"[WARN] solutions.pickle.gz not found (not critical for this audit)")


def generate_full_report(base_dir, categories, output_path):
    """Aggregates statistics across all instances in all categories."""
    print(f"\n{'='*60}")
    print(f"STEP 2 & 4: FULL DATASET AGGREGATION")
    print(f"{'='*60}")
    
    report = []
    failed_instances = []
    
    for cat in categories:
        cat_dir = os.path.join(base_dir, cat)
        if not os.path.exists(cat_dir):
            print(f"[WARN] Category directory not found: {cat_dir}")
            continue
            
        instance_dirs = glob.glob(os.path.join(cat_dir, f"{cat}_*"))
        print(f"\nScanning {cat}: {len(instance_dirs)} instances found")
        
        for inst_dir in sorted(instance_dirs):
            inst_name = os.path.basename(inst_dir)
            meta_path = os.path.join(inst_dir, "metadata.json")
            inc_path  = os.path.join(inst_dir, "incumbents.parquet")
            
            if not os.path.exists(meta_path):
                failed_instances.append((inst_name, "missing metadata.json"))
                continue
                
            if not os.path.exists(inc_path):
                failed_instances.append((inst_name, "missing incumbents.parquet"))
                continue
            
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                
                df_inc = pd.read_parquet(inc_path)
                
                if len(df_inc) == 0:
                    failed_instances.append((inst_name, "empty incumbents.parquet"))
                    continue
                    
                sol_0 = np.array(df_inc.iloc[0]['solution_vector'])
                n_ones = (sol_0 == 1.0).sum()
                
                report.append({
                    'category': cat,
                    'instance': inst_name,
                    'complexity': meta.get('complexity_class', 'unknown'),
                    'presolve': meta.get('presolve_setting', -999),
                    'runtime_sec': meta.get('runtime', 0.0),
                    'status': meta.get('status', -1),
                    'n_incumbents': len(df_inc),
                    'n_vars': len(sol_0),
                    'best_obj': df_inc['objective'].min(),
                    'worst_obj': df_inc['objective'].max(),
                    'pct_ones': 100.0 * n_ones / len(sol_0)
                })
            except Exception as e:
                failed_instances.append((inst_name, str(e)))

    if not report:
        print("\n[CRITICAL ERROR] No valid instances found in any category!")
        print("Cannot generate report.")
        return
    
    df_report = pd.DataFrame(report)
    
    # Save to disk
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_report.to_csv(output_path, index=False)
    
    print(f"\n[OK] Saved aggregate report to: {output_path}")
    print(f"Total instances processed: {len(report)}")
    print(f"Failed instances: {len(failed_instances)}")
    
    if failed_instances:
        print("\n--- FAILED INSTANCES ---")
        for inst, reason in failed_instances[:10]:  # Show first 10
            print(f"  {inst}: {reason}")
        if len(failed_instances) > 10:
            print(f"  ... and {len(failed_instances) - 10} more")
    
    # Print summary statistics to console
    print("\n" + "="*60)
    print("AGGREGATE STATISTICS BY CATEGORY")
    print("="*60)
    
    summary = df_report.groupby('category').agg({
        'n_incumbents': ['count', 'mean', 'std'],
        'n_vars': ['mean', 'std', 'min', 'max'],
        'pct_ones': ['mean', 'std', 'min', 'max']
    }).round(2)
    
    print(summary.to_string())
    
    # Flag problematic patterns
    print("\n" + "="*60)
    print("RED FLAGS CHECK")
    print("="*60)
    
    high_ones = df_report[df_report['pct_ones'] > 80.0]
    if len(high_ones) > 0:
        print(f"[RED ALERT] {len(high_ones)} instances have >80% ones (trivial incumbent problem)")
        print(high_ones[['instance', 'pct_ones', 'n_vars']].head(5).to_string(index=False))
    else:
        print("[OK] No trivial incumbent problems detected")
    
    low_incumbents = df_report[df_report['n_incumbents'] < 5]
    if len(low_incumbents) > 0:
        print(f"\n[WARN] {len(low_incumbents)} instances have <5 incumbents (insufficient training labels)")
    else:
        print("\n[OK] All instances have sufficient incumbents")
    
    var_variance = df_report.groupby('category')['n_vars'].std()
    if (var_variance > 100).any():
        print(f"\n[WARN] High variance in n_vars within categories (possible dimension mismatch)")
        print(var_variance)
    else:
        print("\n[OK] Variable counts are consistent within categories")


def main():

    parser = argparse.ArgumentParser(description='Audit Phase 1 Data')
    parser.add_argument('--instance', type=str, default="CFL_easy_instance_0",
                        help='Name of the specific instance to deep dive (e.g., CFL_easy_instance_0)')
    args = parser.parse_args()
    
    target_instance = args.instance

    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps"
    #output_report = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis/phase1_audit_report.csv"
    output_report = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis/phase1_audit_report_{target_instance_name}.csv"
    
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    print("="*60)
    print("PHASE 1 AUDIT: RAW DATA VALIDATION")
    print("="*60)
    print(f"Base directory: {base_dir}")
    print(f"Output report:  {output_report}")
    
    # Target one known instance for the deep dive
    target_instance = os.path.join(base_dir, "CFL_easy_instance", "CFL_easy_instance_0")
    
    if os.path.exists(target_instance):
        audit_single_instance(target_instance)
    else:
        print(f"\n[WARN] Target instance not found: {target_instance}")
        print("Proceeding to aggregate report only...")

    generate_full_report(base_dir, categories, output_report)
    
    print("\n" + "="*60)
    print("AUDIT COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Review the console output above")
    print("2. Open the CSV report for detailed per-instance analysis")
    print("3. If RED ALERTS appear, Phase 1 needs fixing (v5 → v6)")
    print("4. If all checks pass, the bug is in Phase 2 ETL (build_pyg_dataset_v4)")


if __name__ == "__main__":
    main()
