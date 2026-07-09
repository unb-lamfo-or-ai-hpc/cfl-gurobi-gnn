"""
Phase 1: Dataset Statistical Analysis
=====================================
Analyzes generated .pt files to extract structural metrics (variables, 
constraints, non-zeros) and performance metrics (solve time, MIP gap) 
per instance category.
"""

import os
import glob
import torch
import numpy as np
import pandas as pd

def compute_95_ci(data):
    """Calculates the margin of error for the 95% Confidence Interval."""
    n = len(data)
    if n < 2:
        return 0.0
    std = np.std(data, ddof=1)
    # Using 1.96 as Z-score for 95% confidence
    margin = 1.96 * (std / np.sqrt(n))
    return margin

def main():
    # Base directory for bipartite graphs
    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    print("=== Starting Dataset Statistical Analysis ===")
    
    report_rows = []
    
    for cat in categories:
        processed_dir = os.path.join(base_dir, cat, "processed")
        pt_files = glob.glob(os.path.join(processed_dir, "data_*.pt"))
        
        if not pt_files:
            print(f"No files found in {processed_dir}")
            continue
            
        metrics = {'vars': [], 'rows': [], 'nnz': [], 'time': [], 'gap': []}
        
        for pt_file in pt_files:
            # Fixed: weights_only=False required for PyG HeteroData objects
            data = torch.load(pt_file, map_location='cpu', weights_only=False)
            
            # Structural metrics
            metrics['vars'].append(data['variable'].x.shape[0])
            metrics['rows'].append(data['constraint'].x.shape[0])
            # NNZ calculation: number of edges in the bipartite constraint-variable graph
            nnz = data['variable', 'rev_coef', 'constraint'].edge_index.shape[1]
            metrics['nnz'].append(nnz)
            
            # Performance metrics: Fallback to instance-level attributes if necessary
            exec_time = getattr(data, 'exec_time', getattr(data['instance'], 'exec_time', 0.0))
            mip_gap = getattr(data, 'mip_gap', getattr(data['instance'], 'mip_gap', 0.0))
            
            metrics['time'].append(float(exec_time))
            metrics['gap'].append(float(mip_gap))
            
        # Statistical aggregation
        v_mean, v_std = np.mean(metrics['vars']), np.std(metrics['vars'])
        c_mean, c_std = np.mean(metrics['rows']), np.std(metrics['rows'])
        n_mean, n_std = np.mean(metrics['nnz']), np.std(metrics['nnz'])
        t_mean, t_std = np.mean(metrics['time']), np.std(metrics['time'])
        t_ci = compute_95_ci(metrics['time'])
        g_mean, g_std = np.mean(metrics['gap']), np.std(metrics['gap'])
        g_ci = compute_95_ci(metrics['gap'])
        
        t_min, t_max = np.min(metrics['time']), np.max(metrics['time'])
        g_min, g_max = np.min(metrics['gap']), np.max(metrics['gap'])
        
        report_rows.append({
            'Category': f"{cat} (N={len(pt_files)})",
            'Vars (Mean ± SD)': f"{v_mean:.1f} ± {v_std:.1f}",
            'Rows (Mean ± SD)': f"{c_mean:.1f} ± {c_std:.1f}",
            'NNZ (Mean ± SD)': f"{n_mean:.1f} ± {n_std:.1f}",
            'Time Mean ± SD': f"{t_mean:.2f}s ± {t_std:.2f}s",
            'Time Range [Min, Max]': f"[{t_min:.2f}s, {t_max:.2f}s]",
            'Time 95% CI': f"± {t_ci:.3f}s",
            'Gap Mean ± SD': f"{g_mean*100:.2f}% ± {g_std*100:.2f}%",
            'Gap Range [Min, Max]': f"[{g_min*100:.2f}%, {g_max*100:.2f}%]",
            'Gap 95% CI': f"± {g_ci*100:.3f}%"
        })
        
    #report_df = pd.DataFrame(report_rows)
    #report_df.to_csv("dataset_statistics_report_v2.csv", index=False)
    #print("Report saved successfully to dataset_statistics_report_v2.csv")

    report_df = pd.DataFrame(report_rows)
    
    # Mostrar resultados en consola de forma limpia
    print("\n" + "="*120)
    print(" REPORTE ESTADÍSTICO DEL DATASET (LPs Intermedios)")
    print("="*120)
    print(report_df.to_string(index=False))
    print("="*120)
    
    # Guardar en disco para incluir en el paper
    output_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis"
    os.makedirs(output_dir, exist_ok=True)
    
    out_csv = os.path.join(output_dir, "dataset_statistics_report.csv")
    report_df.to_csv(out_csv, index=False)
    print(f"\nReport saved successfully to: {out_csv}")

if __name__ == "__main__":
    main()