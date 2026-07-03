"""
Paso 1: Estadística Descriptiva del Dataset de Grafos Bipartitos
================================================================
Analiza los archivos .pt generados y extrae métricas estructurales 
(variables, restricciones, densidad) y métricas de desempeño 
(tiempo, MIP gap) por cada categoría.
"""

import os
import glob
import torch
import numpy as np
import pandas as pd

def compute_95_ci(data):
    """Calcula el margen de error para el Intervalo de Confianza del 95%."""
    n = len(data)
    if n < 2:
        return 0.0
    std = np.std(data, ddof=1)
    # Usamos 1.96 como valor Z para 95% de confianza (para n > 30)
    margin = 1.96 * (std / np.sqrt(n))
    return margin

def main():
    base_dir = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    categories = ["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"]
    
    print("=== Iniciando Análisis Estadístico del Dataset ===")
    
    all_records = []
    
    for category in categories:
        processed_dir = os.path.join(base_dir, category, "processed")
        pt_files = glob.glob(os.path.join(processed_dir, "data_*.pt"))
        
        print(f"Analizando {len(pt_files)} grafos en {category}...")
        
        for pt_file in pt_files:
            try:
                data = torch.load(pt_file, map_location='cpu')
                
                # Tamaño Estructural
                num_vars = data['variable'].x.shape[0]
                num_constrs = data['constraint'].x.shape[0]
                num_nnz = data['variable', 'rev_coef', 'constraint'].edge_index.shape[1]
                
                # Desempeño
                exec_time = getattr(data, 'exec_time', np.nan)
                mip_gap = getattr(data, 'mip_gap', np.nan)
                
                # Tratamiento de Gaps infinitos/gigantes para que las medias tengan sentido
                if mip_gap == float('inf') or mip_gap > 1.0:
                    mip_gap = 1.0
                    
                all_records.append({
                    'Category': category.replace('CFL_', '').replace('_instance', '').capitalize(),
                    'Vars (Cols)': num_vars,
                    'Constrs (Rows)': num_constrs,
                    'Non-Zeros': num_nnz,
                    'Exec Time (s)': exec_time,
                    'MIP Gap': mip_gap
                })
            except Exception as e:
                print(f"  [Aviso] Error leyendo {pt_file}: {e}")

    # Convertir a DataFrame
    df = pd.DataFrame(all_records)
    
    if df.empty:
        print("\n[Error] No se encontraron datos para analizar.")
        return

    # Construir el Reporte Final
    report_rows = []
    
    for cat in df['Category'].unique():
        cat_df = df[df['Category'] == cat]
        
        # Cálculos de Estructura (Tamaño)
        v_mean, v_std = cat_df['Vars (Cols)'].mean(), cat_df['Vars (Cols)'].std()
        c_mean, c_std = cat_df['Constrs (Rows)'].mean(), cat_df['Constrs (Rows)'].std()
        nnz_mean, nnz_std = cat_df['Non-Zeros'].mean(), cat_df['Non-Zeros'].std()
        
        # Cálculos de Desempeño (Time & Gap)
        time_data = cat_df['Exec Time (s)'].dropna()
        t_mean, t_std = time_data.mean(), time_data.std()
        t_min, t_max = time_data.min(), time_data.max()
        t_ci = compute_95_ci(time_data)
        
        gap_data = cat_df['MIP Gap'].dropna()
        g_mean, g_std = gap_data.mean(), gap_data.std()
        g_min, g_max = gap_data.min(), gap_data.max()
        g_ci = compute_95_ci(gap_data)
        
        report_rows.append({
            'Category': f"{cat} (N={len(cat_df)})",
            # Estructura
            'Vars (Mean ± SD)': f"{v_mean:.1f} ± {v_std:.1f}",
            'Rows (Mean ± SD)': f"{c_mean:.1f} ± {c_std:.1f}",
            'NNZ (Mean ± SD)': f"{nnz_mean:.1f} ± {nnz_std:.1f}",
            # Tiempo
            'Time Mean ± SD': f"{t_mean:.2f}s ± {t_std:.2f}s",
            'Time Range [Min, Max]': f"[{t_min:.2f}s, {t_max:.2f}s]",
            'Time 95% CI': f"± {t_ci:.3f}s",
            # MIP Gap
            'Gap Mean ± SD': f"{g_mean*100:.2f}% ± {g_std*100:.2f}%",
            'Gap Range [Min, Max]': f"[{g_min*100:.2f}%, {g_max*100:.2f}%]",
            'Gap 95% CI': f"± {g_ci*100:.3f}%"
        })
        
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
    print(f"\nReporte guardado exitosamente en: {out_csv}")

if __name__ == "__main__":
    main()