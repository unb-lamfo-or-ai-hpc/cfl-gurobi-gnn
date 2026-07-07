"""
Phase 2: Clustering and Dimensionality Reduction (PCA & UMAP)
=============================================================
Extracts macro-topological features and performance metrics from the 
generated bipartite graphs to visualize difficulty clusters.
"""

# Requirement: pip install umap-learn seaborn scikit-learn
import os
import glob
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import umap

def extract_macro_features(pt_file):
    """Extracts a vector of condensed features from a PyG HeteroData graph."""
    try:
        # Fixed: weights_only=False for PyTorch 2.0+ compatibility
        data = torch.load(pt_file, map_location='cpu', weights_only=False)
        
        num_vars = data['variable'].x.shape[0]
        num_constrs = data['constraint'].x.shape[0]
        # Number of non-zeros (NNZ) in the constraint matrix
        num_edges = data['variable', 'rev_coef', 'constraint'].edge_index.shape[1]
        
        # Density of the bipartite graph
        density = num_edges / (num_vars * num_constrs) if (num_vars * num_constrs) > 0 else 0
        
        # Fixed: Column index bug (4 = Binary, 5 = Integer)
        is_bin = (data['variable'].x[:, 4] == 1.0).sum().item()
        is_int = (data['variable'].x[:, 5] == 1.0).sum().item()
        prop_discrete = (is_bin + is_int) / num_vars if num_vars > 0 else 0
        
        # Performance metrics
        exec_time = getattr(data, 'exec_time', getattr(data['instance'], 'exec_time', 0.0))
        mip_gap = getattr(data, 'mip_gap', getattr(data['instance'], 'mip_gap', 0.0))
        
        return [num_vars, num_constrs, density, prop_discrete, exec_time, mip_gap]
        
    except Exception as e:
        print(f"Error processing {pt_file}: {e}")
        return None

def main():
    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    data_records = []
    
    print("=== Starting Dimensionality Reduction Analysis ===")
    
    for category in categories:
        processed_dir = os.path.join(base_dir, category, "processed")
        pt_files = glob.glob(os.path.join(processed_dir, "data_*.pt"))
        
        for pt_file in pt_files:
            features = extract_macro_features(pt_file)
            if features:
                data_records.append(features + [category.replace("CFL_", "").replace("_instance", "").capitalize()])
                
    # Create DataFrame
    df = pd.DataFrame(data_records, columns=['Vars', 'Constrs', 'Density', 'Prop_Discrete', 'Time', 'Gap', 'Category'])
    
    # Preprocessing
    features = ['Vars', 'Constrs', 'Density', 'Prop_Discrete', 'Time', 'Gap']
    X = df[features].values
    X_scaled = StandardScaler().fit_transform(X)
    
    # PCA
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)
    df['PCA1'], df['PCA2'] = X_pca[:, 0], X_pca[:, 1]
    
    # UMAP
    reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
    X_umap = reducer.fit_transform(X_scaled)
    df['UMAP1'], df['UMAP2'] = X_umap[:, 0], X_umap[:, 1]
    
    # --- Generation of Academic Combined Plot ---
    print("Generating clustering plots...")
    sns.set_theme(style="whitegrid", font_scale=1.2)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    # PCA Plot
    sns.scatterplot(ax=axes[0], data=df, x='PCA1', y='PCA2', hue='Category', 
                    palette={'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'},
                    alpha=0.8, edgecolor='w', s=50)
    axes[0].set_title('Principal Component Analysis (PCA)', fontsize=16, weight='bold')
    axes[0].set_xlabel('Principal Component 1')
    axes[0].set_ylabel('Principal Component 2')
    axes[0].legend(title='Difficulty')
    
    # UMAP Plot
    sns.scatterplot(ax=axes[1], data=df, x='UMAP1', y='UMAP2', hue='Category', 
                    palette={'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'},
                    alpha=0.8, edgecolor='w', s=50)
    axes[1].set_title('Uniform Manifold Approximation (UMAP)', fontsize=16, weight='bold')
    axes[1].set_xlabel('UMAP Dimension 1')
    axes[1].set_ylabel('UMAP Dimension 2')
    axes[1].legend(title='Difficulty')
    
    plt.tight_layout()
    plt.savefig("plot_pca_vs_umap_v2.jpg", dpi=300)
    print("Analysis complete. Figures saved.")

if __name__ == "__main__":
    main()