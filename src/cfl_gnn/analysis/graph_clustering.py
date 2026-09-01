"""
Phase 2: PyG Clustering and Dimensionality Reduction (PCA & UMAP)
=================================================================
Extracts relative macro-topological features and performance metrics 
from the generated PyG bipartite graphs to visualize difficulty clusters
without scale-distortion.

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
    """Extracts a vector of relative features and class imbalance from a PyG HeteroData graph."""
    try:
        data = torch.load(pt_file, map_location='cpu', weights_only=False)
        
        num_vars = data['variable'].x.shape[0]
        num_constrs = data['constraint'].x.shape[0]
        num_edges = data['variable', 'rev_coef', 'constraint'].edge_index.shape[1]
        
        # --- RELATIVE TOPOLOGICAL FEATURES ---
        # 1. Graph Density
        density = num_edges / (num_vars * num_constrs) if (num_vars * num_constrs) > 0 else 0
        
        # 2. Ratio of Constraints to Variables
        ratio_c_v = num_constrs / num_vars if num_vars > 0 else 0
        
        # 3. Proportion of Discrete Variables
        is_bin = (data['variable'].x[:, 4] == 1.0).sum().item()
        is_int = (data['variable'].x[:, 5] == 1.0).sum().item()
        prop_discrete = (is_bin + is_int) / num_vars if num_vars > 0 else 0
        
        # --- CLASS IMBALANCE (TARGET 'y') ---
        # Calculate the percentage of ones (active facilities) in the solution
        y_tensor = data['variable'].y
        n_ones = (y_tensor == 1.0).sum().item()
        pct_ones = (n_ones / num_vars) * 100.0 if num_vars > 0 else 0.0

        # --- PERFORMANCE METRICS ---
        exec_time = float(getattr(data, 'exec_time', 0.0))
        mip_gap = float(getattr(data, 'mip_gap', 1.0))
        
        if np.isinf(mip_gap) or np.isnan(mip_gap) or mip_gap > 1.0:
            mip_gap = 1.0
            
        return {
            'Vars': num_vars,
            'Constrs': num_constrs,
            'Density': density,
            'Prop_Discrete': prop_discrete,
            'Ratio_C_V': ratio_c_v,
            'Pct_Ones': pct_ones,
            'Time': exec_time,
            'Gap': mip_gap
        }
        
    except Exception as e:
        print(f"  [WARN] Skipping corrupted file {os.path.basename(pt_file)}: {e}")
        return None

def main():
    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    output_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis/step2"
    os.makedirs(output_dir, exist_ok=True)
    
    print("=== Starting Relative Feature Extraction for PyG Clustering ===")
    
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
        
    print(f"\nTotal valid PyG graphs processed: {len(df)}")
    
    # --- Matrix for Dimensionality Reduction (STRICTLY RELATIVE FEATURES) ---
    feature_cols = ['Density', 'Prop_Discrete', 'Ratio_C_V']
    X = df[feature_cols].values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # PCA
    print("Computing PCA...")
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    df['PCA1'] = X_pca[:, 0]
    df['PCA2'] = X_pca[:, 1]
    var_exp = pca.explained_variance_ratio_ * 100
    pca_title = f"PCA (Explained Var: PC1={var_exp[0]:.1f}%, PC2={var_exp[1]:.1f}%)"
    
    # UMAP
    print("Computing UMAP...")
    n_neighbors = min(15, max(2, len(X_scaled) - 1))
    reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=n_neighbors, min_dist=0.1)
    X_umap = reducer.fit_transform(X_scaled)
    df['UMAP1'] = X_umap[:, 0]
    df['UMAP2'] = X_umap[:, 1]
    
    # --- Generate Unified 2x2 Dashboard ---
    print("Generating comprehensive clustering & empirical dashboard...")
    sns.set_theme(style="whitegrid")
    
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    palette = {'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'}
    
    # 1. PCA Plot
    sns.scatterplot(ax=axes[0, 0], data=df, x='PCA1', y='PCA2', hue='Category', 
                    palette=palette, alpha=0.8, edgecolor='w', s=60)
    axes[0, 0].set_title(pca_title, fontsize=14, weight='bold')
    axes[0, 0].set_xlabel('Principal Component 1')
    axes[0, 0].set_ylabel('Principal Component 2')
    
    # 2. UMAP Plot
    sns.scatterplot(ax=axes[0, 1], data=df, x='UMAP1', y='UMAP2', hue='Category', 
                    palette=palette, alpha=0.8, edgecolor='w', s=60)
    axes[0, 1].set_title('Uniform Manifold Approximation (UMAP)', fontsize=14, weight='bold')
    axes[0, 1].set_xlabel('UMAP Dimension 1')
    axes[0, 1].set_ylabel('UMAP Dimension 2')
    
    # 3. Time vs Gap (Empirical Performance)
    sns.scatterplot(ax=axes[1, 0], data=df, x='Time', y='Gap', hue='Category', 
                    palette=palette, alpha=0.7, edgecolor=None, s=60)
    axes[1, 0].set_title('Empirical Performance: Time vs Final MIP Gap', fontsize=14, weight='bold')
    axes[1, 0].set_xlabel('Solve Time (s)')
    axes[1, 0].set_ylabel('MIP Gap (Capped at 100%)')
    
    # 4. Class Imbalance Boxplot (Target 'y')
    sns.boxplot(ax=axes[1, 1], data=df, x='Category', y='Pct_Ones', hue='Category', 
                palette=palette, dodge=False, legend=False)
    axes[1, 1].set_title('Target Class Imbalance (Distribution of Ones)', fontsize=14, weight='bold')
    axes[1, 1].set_ylabel('% of Active Variables (y = 1.0)')
    axes[1, 1].set_xlabel('Difficulty Category')

    plt.tight_layout()
    dashboard_path = os.path.join(output_dir, "pyg_clustering_dashboard.png")
    plt.savefig(dashboard_path, dpi=300)
    plt.close()
    
    print(f"=== Analysis Complete. Dashboard saved to: {dashboard_path} ===")

if __name__ == "__main__":
    main()