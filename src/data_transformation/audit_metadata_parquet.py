import pandas as pd

def audit_parquet(file_path):
    print("="*60)
    print(f"AUDITORÍA DE PARQUET: {file_path}")
    print("="*60)
    
    try:
        # Cargar el archivo Parquet
        df = pd.read_parquet(file_path)
        
        # 1. Dimensiones básicas
        print(f"\n[1] DIMENSIONES: {df.shape[0]} instancias x {df.shape[1]} características")
        
        # 2. Tipos de datos y valores nulos
        print("\n[2] COLUMNAS Y VALORES NULOS:")
        info_df = pd.DataFrame({
            'Tipo': df.dtypes,
            'Nulos': df.isna().sum(),
            '% Nulos': (df.isna().sum() / len(df)) * 100
        })
        print(info_df)
        
        # 3. Estadísticas descriptivas de las columnas numéricas
        print("\n[3] ESTADÍSTICAS DESCRIPTIVAS BÁSICAS:")
        print(df.describe().T[['mean', 'std', 'min', 'max']])
        
        # 4. Muestra rápida (primeras filas)
        print("\n[4] MUESTRA DE DATOS (Head):")
        print(df.head())
        
    except Exception as e:
        print(f"[ERROR] No se pudo leer o procesar el archivo: {e}")

if __name__ == "__main__":
    target_parquet = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/metadata/CFL_easy_instance_metadata.parquet"
    audit_parquet(target_parquet)