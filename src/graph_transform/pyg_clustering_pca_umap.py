"""
Phase 2: Clustering and Dimensionality Reduction (PCA & UMAP)
=============================================================
Extracts macro-topological features and performance metrics from the 
generated bipartite graphs to visualize difficulty clusters.

Outputs are saved to the defined analysis directory.
"""

import os
import glob
import torch
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import umap

# Suppress UMAP warning regarding n_jobs and random_state overrides in HPC
warnings.filterwarnings('ignore', category=UserWarning, module='umap')

def extract_macro_features(pt_file):
    """Extracts a vector of condensed features from a PyG HeteroData graph."""
    try:
        data = torch.load(pt_file, map_location='cpu', weights_only=False)
        
        num_vars = data['variable'].x.shape[0]
        num_constrs = data['constraint'].x.shape[0]
        num_edges = data['variable', 'rev_coef', 'constraint'].edge_index.shape[1]
        
        # Density of the bipartite graph
        density = num_edges / (num_vars * num_constrs) if (num_vars * num_constrs) > 0 else 0
        
        # Proportion of discrete variables (Columns 4=Binary, 5=Integer)
        is_bin = (data['variable'].x[:, 4] == 1.0).sum().item()
        is_int = (data['variable'].x[:, 5] == 1.0).sum().item()
        prop_discrete = (is_bin + is_int) / num_vars if num_vars > 0 else 0
        
        # Performance metrics
        exec_time = float(getattr(data, 'exec_time', 0.0))
        mip_gap = float(getattr(data, 'mip_gap', 1.0))
        
        # Cap MIP gap at 1.0 (100%) for visualization purposes
        if np.isinf(mip_gap) or np.isnan(mip_gap) or mip_gap > 1.0:
            mip_gap = 1.0
            
        return {
            'Vars': num_vars,
            'Constrs': num_constrs,
            'Density': density,
            'Prop_Discrete': prop_discrete,
            'Time': exec_time,
            'Gap': mip_gap
        }
        
    except Exception as e:
        print(f"  [WARN] Skipping corrupted file {os.path.basename(pt_file)}: {e}")
        return None

def main():
    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    output_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis"
    os.makedirs(output_dir, exist_ok=True)
    
    print("=== Starting Macro-Feature Extraction for PyG Clustering ===")
    
    data_records = []
    
    for category in categories:
        cat_clean = category.replace("CFL_", "").replace("_instance", "").capitalize()
        processed_dir = os.path.join(base_dir, category, "processed")
        pt_files = glob.glob(os.path.join(processed_dir, "data_*.pt"))
        
        if not pt_files:
            continue
            
        print(f"Scanning {category} ({len(pt_files)} graphs)...")
        for pt_file in pt_files:
            features = extract_macro_features(pt_file)
            if features is not None:
                features['Category'] = cat_clean
                data_records.append(features)
                
    df = pd.DataFrame(data_records)
    
    if df.empty:
        print(" [ERROR] No valid data could be extracted. Nothing to plot.")
        return
        
    print(f"\nTotal valid graphs processed: {len(df)}")
    
    # --- 1. Empirical Plot: Time vs MIP Gap ---
    print("Generating empirical plot (Time vs MIP Gap)...")
    sns.set_theme(style="whitegrid", palette="deep")
    plt.figure(figsize=(8, 6))
    
    sns.scatterplot(data=df, x='Time', y='Gap', hue='Category', 
                    palette={'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'},
                    alpha=0.7, edgecolor=None)
                    
    plt.title('PyG Graph Performance by Difficulty Class', fontsize=14, weight='bold')
    plt.xlabel('Solve Time (s)')
    plt.ylabel('MIP Gap (Capped at 100%)')
    plt.legend(title='Difficulty')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "pyg_plot_time_vs_gap.png"), dpi=300)
    plt.close()

    # --- Prepare matrix for Dimensionality Reduction ---
    feature_cols = ['Vars', 'Constrs', 'Density', 'Prop_Discrete', 'Time', 'Gap']
    X = df[feature_cols].values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # --- 2. PCA Reduction ---
    print("Computing PCA...")
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    df['PCA1'] = X_pca[:, 0]
    df['PCA2'] = X_pca[:, 1]
    
    var_exp = pca.explained_variance_ratio_ * 100
    pca_title = f"PCA (Explained Var: PC1={var_exp[0]:.1f}%, PC2={var_exp[1]:.1f}%)"
    
    # --- 3. UMAP Reduction ---
    print("Computing UMAP...")
    n_neighbors = min(15, max(2, len(X_scaled) - 1))
    reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=n_neighbors, min_dist=0.1)
    X_umap = reducer.fit_transform(X_scaled)
    df['UMAP1'] = X_umap[:, 0]
    df['UMAP2'] = X_umap[:, 1]
    
    # --- 4. Generation of Academic Combined Plot ---
    print("Generating clustering plots...")
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    sns.scatterplot(ax=axes[0], data=df, x='PCA1', y='PCA2', hue='Category', 
                    palette={'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'},
                    alpha=0.8, edgecolor='w', s=50)
    axes[0].set_title(pca_title, fontsize=14, pad=10, weight='bold')
    axes[0].set_xlabel('Principal Component 1')
    axes[0].set_ylabel('Principal Component 2')
    axes[0].legend(title='Difficulty')
    
    sns.scatterplot(ax=axes[1], data=df, x='UMAP1', y='UMAP2', hue='Category', 
                    palette={'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'},
                    alpha=0.8, edgecolor='w', s=50)
    axes[1].set_title('Uniform Manifold Approximation (UMAP)', fontsize=14, pad=10, weight='bold')
    axes[1].set_xlabel('UMAP Dimension 1')
    axes[1].set_ylabel('UMAP Dimension 2')
    axes[1].legend(title='Difficulty')
    
    plt.tight_layout()
    combined_plot_path = os.path.join(output_dir, "pyg_plot_pca_vs_umap.png")
    plt.savefig(combined_plot_path, dpi=300)
    plt.close()
    
    print(f"=== Analysis Complete. Figures saved to: {output_dir} ===")

if __name__ == "__main__":
    main()