"""
Phase 1 Exploratory Data Analysis (EDA) & Audit - PRODUCTION FINAL
==================================================================
Validates the raw outputs from Phase 1, extracts topological metadata,
and generates JSON, CSV, and Plot reports STRICTLY isolated by category.

All outputs are saved to the central 'analysis' directory.
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
# NAMEDTUPLE DEFINITIONS
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


def process_category(cat, base_dir, analysis_dir):
    """
    Procesa una única categoría y genera su JSON, CSV y Plots correspondientes.
    """
    print(f"\n{'#'*70}")
    print(f"PROCESSING CATEGORY: {cat}")
    print(f"{'#'*70}")
    
    cat_dir = os.path.join(base_dir, cat)
    if not os.path.exists(cat_dir):
        print(f"[WARN] Category directory not found: {cat_dir}")
        return

    instance_dirs = glob.glob(os.path.join(cat_dir, f"{cat}_*"))
    print(f"Scanning {len(instance_dirs)} instances found in {cat_dir}...")
    
    cat_metadata_list = []
    report = []
    failed_instances = []
    
    # 1. EXTRACCIÓN DE DATOS
    for inst_dir in sorted(instance_dirs):
        inst_name = os.path.basename(inst_dir)
        meta_path = os.path.join(inst_dir, "metadata.json")
        inc_path  = os.path.join(inst_dir, "incumbents.parquet")
        feat_path = os.path.join(inst_dir, "original_features.pickle.gz")
        
        if not os.path.exists(meta_path) or not os.path.exists(inc_path):
            failed_instances.append((inst_name, "Missing critical files (.json or .parquet)"))
            continue
            
        try:
            # Metadata base
            with open(meta_path) as f:
                meta = json.load(f)
            
            # Incumbents y Gap
            df_inc = pd.read_parquet(inc_path)
            if len(df_inc) == 0:
                failed_instances.append((inst_name, "Empty incumbents.parquet"))
                continue
                
            sol_0 = np.array(df_inc.iloc[0]['solution_vector'])
            n_ones = (sol_0 == 1.0).sum()
            pct_ones = 100.0 * n_ones / len(sol_0)
            
            best_mip_gap = df_inc['mip_gap'].min() * 100.0 if 'mip_gap' in df_inc else np.nan
            median_mip_gap = df_inc['mip_gap'].median() * 100.0 if 'mip_gap' in df_inc else np.nan
            
            # Topología
            num_constrs, nnz, num_binary, num_integer = np.nan, np.nan, np.nan, np.nan
            if os.path.exists(feat_path):
                with gzip.open(feat_path, 'rb') as f:
                    orig = pickle.load(f)
                num_constrs = orig['model_features'].num_constrs
                num_binary  = orig['model_features'].num_binary
                num_integer = orig['model_features'].num_integer
                nnz         = len(orig['edge_features'])

            # Enriquecer JSON metadata
            meta['topological_features'] = {
                'num_vars': int(len(sol_0)),
                'num_constrs': int(num_constrs) if not np.isnan(num_constrs) else None,
                'nnz': int(nnz) if not np.isnan(nnz) else None,
                'num_binary': int(num_binary) if not np.isnan(num_binary) else None,
                'num_integer': int(num_integer) if not np.isnan(num_integer) else None
            }
            meta['empirical_metrics'] = {
                'best_mip_gap_pct': float(best_mip_gap) if not np.isnan(best_mip_gap) else None,
                'pct_ones': float(pct_ones)
            }
            cat_metadata_list.append(meta)

            # Enriquecer reporte CSV
            report.append({
                'category': cat,
                'instance': inst_name,
                'runtime_sec': meta.get('runtime', 0.0),
                'n_incumbents': len(df_inc),
                'best_mip_gap_pct': best_mip_gap,
                'n_vars': len(sol_0),
                'num_constrs': num_constrs,
                'nnz': nnz,
                'num_binary': num_binary,
                'num_integer': num_integer,
                'pct_ones': pct_ones
            })
        except Exception as e:
            failed_instances.append((inst_name, str(e)))

    if not report:
        print(f"[ERROR] No valid instances processed for {cat}.")
        return

    df_report = pd.DataFrame(report)

    # 2. GUARDAR JSON
    summary_path = os.path.join(analysis_dir, f"generation_summary_{cat}.json")
    category_stats = {
        'total_instances_processed': len(cat_metadata_list),
        'avg_runtime_sec': float(df_report['runtime_sec'].mean()),
        'max_best_mip_gap_pct': float(df_report['best_mip_gap_pct'].max()) if not df_report['best_mip_gap_pct'].isna().all() else None,
        'avg_pct_ones': float(df_report['pct_ones'].mean()),
        'avg_incumbents': float(df_report['n_incumbents'].mean())
    }
    with open(summary_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'category': cat,
            'category_statistics': category_stats,
            'metadata': cat_metadata_list
        }, f, indent=2)
    print(f"  [+] JSON Summary saved   -> {summary_path}")

    # 3. GUARDAR CSV
    csv_path = os.path.join(analysis_dir, f"phase1_audit_report_{cat}.csv")
    df_report.to_csv(csv_path, index=False)
    print(f"  [+] CSV Report saved     -> {csv_path}")

    # 4. GENERAR PLOTS LIMPIOS
    generate_category_plots(df_report, cat, analysis_dir)
    
    if failed_instances:
        print(f"  [!] Failed instances ({len(failed_instances)}):")
        for inst, reason in failed_instances[:5]:
            print(f"      - {inst}: {reason}")


def generate_category_plots(df, cat, analysis_dir):
    """Generates an 8-panel clean dashboard for a single category."""
    try:
        df['num_continuous'] = df['n_vars'] - df['num_binary'] - df['num_integer']
        N_inst = len(df)
        N_inc = int(df['n_incumbents'].sum())

        sns.set_theme(style="whitegrid")
        fig, axes = plt.subplots(4, 2, figsize=(16, 24))
        fig.suptitle(f'EDA Audit Dashboard: {cat}', fontsize=22, fontweight='bold', y=0.92)

        # 1. Time Dist
        sns.histplot(data=df, x='runtime_sec', kde=True, ax=axes[0, 0], color='skyblue', bins=10)
        axes[0, 0].set_title(f'Resolution Time Distribution (N = {N_inst} Instances)')
        axes[0, 0].set_xlabel('Time (s)')

        # 2. Incumbents Dist
        sns.histplot(data=df, x='n_incumbents', kde=True, ax=axes[0, 1], color='salmon', bins=10)
        axes[0, 1].set_title(f'Collected Incumbent Solutions (Total N = {N_inc:,})')
        axes[0, 1].set_xlabel('Number of Incumbents')

        # 3. Scatter Time vs Incumbents
        sns.scatterplot(data=df, x='runtime_sec', y='n_incumbents', ax=axes[1, 0], color='purple', s=100, alpha=0.7)
        axes[1, 0].set_title('Relationship: Resolution Time vs. Incumbents')

        # 4. Pct Ones Boxplot (No hue needed here, simple color)
        sns.boxplot(y=df['pct_ones'], ax=axes[1, 1], color='lightgreen')
        axes[1, 1].set_title('Active Variables Distribution (pct_ones)')
        axes[1, 1].set_ylabel('% of Variables at 1.0')

        # 5. Topology (Rows, Cols, NNZ) - Fix warnings with hue and set_xticks
        df_dims = df.melt(id_vars=['instance'], value_vars=['num_constrs', 'n_vars', 'nnz'], 
                          var_name='Dimension', value_name='Count')
        sns.boxplot(data=df_dims, x='Dimension', y='Count', hue='Dimension', legend=False, ax=axes[2, 0], palette='Set1')
        axes[2, 0].set_yscale('log')
        axes[2, 0].set_title('Instance Topology (Log Scale)')
        axes[2, 0].set_xticks(range(3))
        axes[2, 0].set_xticklabels(['Rows', 'Cols', 'Non-Zeros'])
        axes[2, 0].set_xlabel('')

        # 6. Var Types - Fix warnings with hue and set_xticks
        df_vars = df.melt(id_vars=['instance'], value_vars=['num_binary', 'num_integer', 'num_continuous'], 
                          var_name='Var_Type', value_name='Count')
        sns.boxplot(data=df_vars, x='Var_Type', y='Count', hue='Var_Type', legend=False, ax=axes[2, 1], palette='pastel')
        axes[2, 1].set_yscale('log')
        axes[2, 1].set_title('Variable Types Distribution (Log Scale)')
        axes[2, 1].set_xticks(range(3))
        axes[2, 1].set_xticklabels(['Binary', 'Integer', 'Continuous'])
        axes[2, 1].set_xlabel('')

        # 7. Best MIP Gap Boxplot
        sns.boxplot(y=df['best_mip_gap_pct'], ax=axes[3, 0], color='coral')
        axes[3, 0].set_title('Final Best MIP Gap Reached (%)')
        axes[3, 0].set_ylabel('MIP Gap (%)')

        # 8. Scatter Time vs MIP Gap
        sns.scatterplot(data=df, x='runtime_sec', y='best_mip_gap_pct', ax=axes[3, 1], color='teal', s=100, alpha=0.7)
        axes[3, 1].set_title('Resolution Time vs. Final MIP Gap')
        axes[3, 1].set_ylabel('MIP Gap (%)')

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plot_path = os.path.join(analysis_dir, f"phase1_audit_report_{cat}_plots.png")
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  [+] Plots Dashboard saved -> {plot_path}")

    except Exception as e:
        print(f"  [ERROR] Plot generation failed: {e}")


def main():
    # Rutas absolutas fijas según la estructura de tu clúster
    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps"
    analysis_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis"
    os.makedirs(analysis_dir, exist_ok=True)
    
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    print("="*70)
    print("PHASE 1 AUDIT: ISOLATED METRICS PIPELINE (JSON, CSV, PLOTS)")
    print("="*70)
    
    for cat in categories:
        process_category(cat, base_dir, analysis_dir)

    print("\n" + "="*70)
    print("AUDIT FULLY COMPLETE")
    print("="*70)
    print("Check ./data/analysis/ for the specific JSON, CSV and PNGs of each category.")

if __name__ == "__main__":
    main()