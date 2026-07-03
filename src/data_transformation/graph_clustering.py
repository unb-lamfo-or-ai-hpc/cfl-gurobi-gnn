"""
Paso 2: Clustering y Reducción de Dimensionalidad (PCA & UMAP)
==============================================================
Extrae macro-características topológicas y de desempeño de los 
1500 grafos bipartitos generados y genera plots 2D de clústeres.
"""

# Verificar pip install umap-learn seaborn scikit-learn

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
    """Extrae un vector de características condensadas de un grafo PyG."""
    try:
        data = torch.load(pt_file, map_location='cpu')
        
        num_vars = data['variable'].x.shape[0]
        num_constrs = data['constraint'].x.shape[0]
        num_edges = data['variable', 'rev_coef', 'constraint'].edge_index.shape[1]
        
        # Densidad del grafo bipartito (Edges / (Vars * Constrs))
        density = num_edges / (num_vars * num_constrs) if (num_vars * num_constrs) > 0 else 0
        
        # Proporción de variables enteras/binarias
        is_bin = (data['variable'].x[:, 3] == 1.0).sum().item()
        is_int = (data['variable'].x[:, 4] == 1.0).sum().item()
        prop_discrete = (is_bin + is_int) / num_vars if num_vars > 0 else 0
        
        # Desempeño
        exec_time = getattr(data, 'exec_time', 0.0)
        mip_gap = getattr(data, 'mip_gap', 1.0)
        if mip_gap == float('inf') or mip_gap > 1.0:
            mip_gap = 1.0
            
        return {
            'Vars': num_vars,
            'Constrs': num_constrs,
            'Density': density,
            'Prop_Discrete': prop_discrete,
            'Exec_Time': exec_time,
            'MIP_Gap': mip_gap
        }
    except Exception as e:
        return None

def main():
    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    print("=== Iniciando Extracción de Macro-Características para Clustering ===")
    
    records = []
    
    for category in categories:
        cat_clean = category.replace('CFL_', '').replace('_instance', '').capitalize()
        processed_dir = os.path.join(base_dir, category, "processed")
        pt_files = glob.glob(os.path.join(processed_dir, "data_*.pt"))
        
        for pt_file in pt_files:
            features = extract_macro_features(pt_file)
            if features:
                features['Category'] = cat_clean
                records.append(features)

    df = pd.DataFrame(records)
    if df.empty:
        print("[Error] No hay datos para plotear.")
        return
        
    # --- 1. Gráfico Directo: Tiempo vs MIP Gap ---
    print("Generando plot empírico (Tiempo vs MIP Gap)...")
    output_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/analysis"
    os.makedirs(output_dir, exist_ok=True)
    
    sns.set_theme(style="whitegrid", palette="deep")
    plt.figure(figsize=(8, 6))
    sns.scatterplot(data=df, x='Exec_Time', y='MIP_Gap', hue='Category', 
                    palette={'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'},
                    alpha=0.7, edgecolor=None)
    plt.title('Desempeño Computacional de Gurobi por Dificultad')
    plt.xlabel('Tiempo de Ejecución (s)')
    plt.ylabel('MIP Gap (Normalizado al 100%)')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "plot_time_vs_gap.png"), dpi=300)
    plt.close()

    # --- Preparación de la Matriz de Reducción ---
    # Usamos topología y desempeño para agrupar los grafos
    feature_cols = ['Vars', 'Constrs', 'Density', 'Prop_Discrete', 'Exec_Time', 'MIP_Gap']
    X = df[feature_cols].values
    y = df['Category'].values
    
    # Estandarización obligatoria para PCA y UMAP
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # --- 2. Reducción PCA ---
    print("Aplicando Reducción Lineal (PCA)...")
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    df['PCA1'] = X_pca[:, 0]
    df['PCA2'] = X_pca[:, 1]
    
    var_exp = pca.explained_variance_ratio_ * 100
    pca_title = f"PCA (Var. Explicada: PC1={var_exp[0]:.1f}%, PC2={var_exp[1]:.1f}%)"

    # --- 3. Reducción UMAP ---
    print("Aplicando Reducción Topológica No Lineal (UMAP)...")
    reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
    X_umap = reducer.fit_transform(X_scaled)
    df['UMAP1'] = X_umap[:, 0]
    df['UMAP2'] = X_umap[:, 1]

    # --- 4. Generación del Gráfico Combinado Académico ---
    print("Generando gráficos de Clustering...")
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    # Subplot 1: PCA
    sns.scatterplot(ax=axes[0], data=df, x='PCA1', y='PCA2', hue='Category', 
                    palette={'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'},
                    alpha=0.8, edgecolor='w', s=50)
    axes[0].set_title(pca_title, fontsize=14, pad=10)
    axes[0].set_xlabel('Componente Principal 1')
    axes[0].set_ylabel('Componente Principal 2')
    axes[0].legend(title='Dificultad')

    # Subplot 2: UMAP
    sns.scatterplot(ax=axes[1], data=df, x='UMAP1', y='UMAP2', hue='Category', 
                    palette={'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'},
                    alpha=0.8, edgecolor='w', s=50)
    axes[1].set_title('UMAP Manifold Projection', fontsize=14, pad=10)
    axes[1].set_xlabel('UMAP Dimensión 1')
    axes[1].set_ylabel('UMAP Dimensión 2')
    axes[1].legend(title='Dificultad')

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "plot_pca_vs_umap.png"), dpi=300)
    plt.close()
    
    print(f"=== Proceso Finalizado. Gráficos generados en: {output_dir} ===")

if __name__ == "__main__":
    main()