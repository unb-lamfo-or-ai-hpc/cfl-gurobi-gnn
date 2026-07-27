"""
Phase 1 Exploratory Data Analysis (EDA) & Audit - v3
====================================================
Validates the raw outputs from cfl_gnn_data_generator.py to isolate
whether the pipeline bugs originate in Phase 1 (Data Generation) or 
Phase 2 (PyG ETL).

V3 Updates:
- Extracts topological statistics (rows, columns, nnz, var types).
- Compiles and saves 'generation_summary_{category}.json' robustly.
- Analyzes MIP Gap distributions to inform ETL quality filters.
- Generates a 4x2 visual dashboard with sample sizes (N) and dynamic legends.
"""

import os
import glob
import json
import gzip
import pickle
from datetime import datetime
import pandas as pd
import numpy as np

import argparse

import matplotlib.pyplot as plt
import seaborn as sns

from collections import namedtuple

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


def generate_full_report_and_json(base_dir, categories, output_path):
    """Aggregates statistics and centrally generates the JSON summary for ETL."""
    print(f"\n{'='*60}")
    print(f"STEP 2 & 4: DATASET AGGREGATION & JSON CREATION")
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
        
        cat_metadata_list = [] # List to hold metadata for JSON generation
        
        for inst_dir in sorted(instance_dirs):
            inst_name = os.path.basename(inst_dir)
            meta_path = os.path.join(inst_dir, "metadata.json")
            inc_path  = os.path.join(inst_dir, "incumbents.parquet")
            feat_path = os.path.join(inst_dir, "original_features.pickle.gz")
            
            if not os.path.exists(meta_path):
                failed_instances.append((inst_name, "missing metadata.json"))
                continue
                
            if not os.path.exists(inc_path):
                failed_instances.append((inst_name, "missing incumbents.parquet"))
                continue
            
            try:
                # 1. Process Metadata
                with open(meta_path) as f:
                    meta = json.load(f)
                
                cat_metadata_list.append(meta) # Append to category list for JSON
                
                # 2. Process Incumbents & MIP Gap
                df_inc = pd.read_parquet(inc_path)
                if len(df_inc) == 0:
                    failed_instances.append((inst_name, "empty incumbents.parquet"))
                    continue
                    
                sol_0 = np.array(df_inc.iloc[0]['solution_vector'])
                n_ones = (sol_0 == 1.0).sum()
                
                # Extract MIP Gap info (multiplying by 100 for percentage)
                best_mip_gap = df_inc['mip_gap'].min() * 100.0 if 'mip_gap' in df_inc else np.nan
                median_mip_gap = df_inc['mip_gap'].median() * 100.0 if 'mip_gap' in df_inc else np.nan
                
                # 3. Extract Topological Features
                num_constrs, nnz, num_binary, num_integer = np.nan, np.nan, np.nan, np.nan
                if os.path.exists(feat_path):
                    with gzip.open(feat_path, 'rb') as f:
                        orig = pickle.load(f)
                    num_constrs = orig['model_features'].num_constrs
                    num_binary  = orig['model_features'].num_binary
                    num_integer = orig['model_features'].num_integer
                    nnz         = len(orig['edge_features'])

                report.append({
                    'category': cat,
                    'instance': inst_name,
                    'complexity': meta.get('complexity_class', 'unknown'),
                    'presolve': meta.get('presolve_setting', -999),
                    'runtime_sec': meta.get('runtime', 0.0),
                    'status': meta.get('status', -1),
                    'n_incumbents': len(df_inc),
                    'best_mip_gap_pct': best_mip_gap,
                    'median_mip_gap_pct': median_mip_gap,
                    'n_vars': len(sol_0),
                    'num_constrs': num_constrs,
                    'nnz': nnz,
                    'num_binary': num_binary,
                    'num_integer': num_integer,
                    'best_obj': df_inc['objective'].min(),
                    'worst_obj': df_inc['objective'].max(),
                    'pct_ones': 100.0 * n_ones / len(sol_0)
                })
            except Exception as e:
                failed_instances.append((inst_name, str(e)))

        # --- GENERATE SUMMARY JSON FOR THIS CATEGORY ---
        if cat_metadata_list:
            summary_path = os.path.join(base_dir, f"generation_summary_{cat}.json")
            with open(summary_path, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'category': cat,
                    'instances_processed': len(cat_metadata_list),
                    'metadata': cat_metadata_list
                }, f, indent=2)
            print(f"[OK] Summary JSON strictly generated for ETL: {summary_path}")

    if not report:
        print("\n[CRITICAL ERROR] No valid instances found in any category!")
        print("Cannot generate CSV report.")
        return
    
    df_report = pd.DataFrame(report)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_report.to_csv(output_path, index=False)
    
    print(f"\n[OK] Saved aggregate CSV report to: {output_path}")
    print(f"Total instances processed: {len(report)}")
    print(f"Failed instances: {len(failed_instances)}")
    
    if failed_instances:
        print("\n--- FAILED INSTANCES ---")
        for inst, reason in failed_instances[:10]:
            print(f"  {inst}: {reason}")
        if len(failed_instances) > 10:
            print(f"  ... and {len(failed_instances) - 10} more")
    
    print("\n" + "="*60)
    print("AGGREGATE STATISTICS BY CATEGORY")
    print("="*60)
    
    summary = df_report.groupby('category').agg({
        'n_incumbents': ['count', 'mean'],
        'best_mip_gap_pct': ['min', 'mean', 'max'],
        'n_vars': ['mean'],
        'num_constrs': ['mean'],
        'pct_ones': ['mean']
    }).round(2)
    
    print(summary.to_string())

def plot_audit_metrics(csv_path):
    """
    Reads the Phase 1 audit CSV report and generates a visual dashboard
    (4x2 grid), saving it as a high-resolution PNG file.
    """
    if not os.path.exists(csv_path):
        print(f"\n[WARN] Cannot generate plots, file not found: {csv_path}")
        return

    try:
        df = pd.read_csv(csv_path)
        
        if len(df) == 0:
            print("\n[WARN] The CSV is empty. Skipping plot generation.")
            return

        df['num_continuous'] = df['n_vars'] - df['num_binary'] - df['num_integer']
        total_instances = len(df)
        total_incumbents = int(df['n_incumbents'].sum())

        sns.set_theme(style="whitegrid")
        # Expanded to 4x2 grid
        fig, axes = plt.subplots(4, 2, figsize=(16, 24))

        # 1. Execution time distribution
        sns.histplot(data=df, x='runtime_sec', hue='category', kde=True, ax=axes[0, 0], bins=15, multiple="stack")
        axes[0, 0].set_title(f'Resolution Time Distribution (N = {total_instances} Instances)')
        axes[0, 0].set_xlabel('Time (s)')
        axes[0, 0].set_ylabel('Frequency')

        # 2. Number of incumbents collected
        sns.histplot(data=df, x='n_incumbents', hue='category', kde=True, ax=axes[0, 1], bins=15, multiple="stack")
        axes[0, 1].set_title(f'Collected Incumbent Solutions (Total N = {total_incumbents:,})')
        axes[0, 1].set_xlabel('Number of Incumbents')
        axes[0, 1].set_ylabel('Frequency')

        # 3. Scatter plot: Time vs Incumbents
        sns.scatterplot(data=df, x='runtime_sec', y='n_incumbents', hue='category', ax=axes[1, 0], s=100, alpha=0.7)
        axes[1, 0].set_title('Relationship: Resolution Time vs. Incumbents')
        axes[1, 0].set_xlabel('Resolution Time (s)')
        axes[1, 0].set_ylabel('Number of Incumbents')

        # 4. Boxplot of active variables (pct_ones)
        sns.boxplot(data=df, x='category', y='pct_ones', ax=axes[1, 1], palette='Set2')
        axes[1, 1].set_title('Active Variables Distribution (pct_ones)')
        axes[1, 1].set_ylabel('% of Variables at 1.0')

        # 5. Model Dimensions (Rows, Columns, NNZ)
        df_dims = df.melt(id_vars=['instance', 'category'], 
                          value_vars=['num_constrs', 'n_vars', 'nnz'], 
                          var_name='Dimension', value_name='Count')
        
        sns.boxplot(data=df_dims, x='Dimension', y='Count', hue='category', ax=axes[2, 0], palette='Set1')
        axes[2, 0].set_yscale('log')
        axes[2, 0].set_title('Instance Topology: Rows, Columns, and Non-Zeros (Log Scale)')
        axes[2, 0].set_xticklabels(['Rows (num_constrs)', 'Cols (n_vars)', 'Non-Zeros (nnz)'])

        # 6. Variable Types Distribution
        df_vars = df.melt(id_vars=['instance', 'category'], 
                          value_vars=['num_binary', 'num_integer', 'num_continuous'], 
                          var_name='Var_Type', value_name='Count')
        
        sns.boxplot(data=df_vars, x='Var_Type', y='Count', hue='category', ax=axes[2, 1], palette='pastel')
        axes[2, 1].set_yscale('log')
        axes[2, 1].set_title('Variable Types Distribution (Log Scale)')
        axes[2, 1].set_xticklabels(['Binary', 'Integer', 'Continuous'])

        # 7. MIP Gap Boxplot
        sns.boxplot(data=df, x='category', y='best_mip_gap_pct', ax=axes[3, 0], palette='rocket')
        axes[3, 0].set_title('Best MIP Gap Reached per Category (%)')
        axes[3, 0].set_ylabel('MIP Gap (%)')

        # 8. Scatter: Time vs MIP Gap
        sns.scatterplot(data=df, x='runtime_sec', y='best_mip_gap_pct', hue='category', ax=axes[3, 1], s=100, alpha=0.7)
        axes[3, 1].set_title('Resolution Time vs. Final MIP Gap')
        axes[3, 1].set_xlabel('Resolution Time (s)')
        axes[3, 1].set_ylabel('MIP Gap (%)')

        plt.tight_layout()
        
        plot_path = csv_path.replace('.csv', '_plots.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"\n[OK] Plots successfully generated and saved to: {plot_path}")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to generate plots: {e}")


def main():
    parser = argparse.ArgumentParser(description='Audit Phase 1 Data')
    parser.add_argument('--instance', type=str, default="CFL_easy_instance_0",
                        help='Name of the specific instance to deep dive (e.g., CFL_easy_instance_0)')
    args = parser.parse_args()
    
    target_instance_name = args.instance
    category_name = target_instance_name.rsplit('_', 1)[0]

    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps"
    output_report = f"/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis/phase1_audit_report_{category_name}.csv"
    
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    print("="*60)
    print("PHASE 1 AUDIT: RAW DATA VALIDATION")
    print("="*60)
    print(f"Base directory: {base_dir}")
    print(f"Output report:  {output_report}")
    
    target_instance_path = os.path.join(base_dir, category_name, target_instance_name)

    if os.path.exists(target_instance_path):
        audit_single_instance(target_instance_path)
    else:
        print(f"\n[WARN] Target instance not found: {target_instance_path}")
        print("Proceeding to aggregate report only...")

    generate_full_report_and_json(base_dir, categories, output_report)
    plot_audit_metrics(output_report)
    
    print("\n" + "="*60)
    print("AUDIT COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Review the generated plots to find the optimal MAX_MIP_GAP.")
    print("2. Proceed to Phase 2 (ETL) ensuring PyG filters align with audit metrics.")

if __name__ == "__main__":
    main()
