readme_content = """# Data Transformation: Gurobi to GNN Pipeline (V3)

Este directorio contiene los scripts para la **transformación y extracción de datos** desde instancias de programación entera mixta (MILP) utilizando Gurobi. El objetivo es generar un *dataset* rico en características estructurales y trayectorias de optimización, diseñado específicamente para entrenar Redes Neuronales de Grafos (GNNs) mediante *Imitation Learning* (ej. paradigma *learn2branch*).

> **Nota:** Este módulo abarca exclusivamente la etapa de **extracción y persistencia de datos**. La construcción de los grafos bipartitos y el entrenamiento en PyTorch Geometric se desarrollarán en módulos posteriores.

---

## 🚀 Arquitectura V3 (Híbrida y Blindada)

La versión actual (V3) ha sido diseñada específicamente para ejecutarse en entornos de alto rendimiento (HPC) como el clúster **DGX-DASCI**, mitigando problemas comunes de almacenamiento, límites de GitHub y atajos del *solver*.

### 1. Inhibición del Presolve para *Imitation Learning*
Para poder capturar la verdadera toma de decisiones del algoritmo *Branch & Bound*, **el algoritmo de Presolve ha sido desactivado (`Presolve=0`)**. Esto fuerza a Gurobi a explorar el árbol de ramificación en lugar de resolver la instancia matemáticamente en una "caja negra", permitiéndonos capturar las relajaciones continuas (`MIPNODE`) y las soluciones incumbentes (`MIPSOL`).

### 2. MLOps: Almacenamiento Híbrido (Pickle.gz + Parquet)
Para cumplir con los límites estrictos de GitHub (100MB por archivo) y maximizar la eficiencia de lectura en PyTorch:
* **Tensores y Grafos (`.pickle.gz`)**: La matriz dispersa de restricciones y los gigantescos vectores de soluciones se comprimen de forma nativa *al vuelo* mediante `gzip`.
* **Tablas de Trayectoria (`.parquet`)**: Los historiales de exploración de nodos y gaps se guardan usando `pyarrow`. Son 100x más rápidos de leer y ocupan un 90% menos que el CSV tradicional.
* **Metadatos (`.json`)**: Archivos de texto ligero para inspección rápida de cada instancia.

### 3. Captura Avanzada en Callbacks
* **MIP Gap en Tiempo Real**: Se captura la cota (*bound*) óptima en cada nuevo hallazgo de una solución incumbente (`MIPSOL`) para calcular el MIP Gap de manera instantánea.
* **Variables Fraccionales (Espacio Activo)**: En cada evaluación continua (`MIPNODE`), se cuantifican las variables binarias/enteras que mantienen valores fraccionales (tolerancia de `1e-5`), sirviendo como un indicador del tamaño efectivo del espacio de búsqueda.

---

## 📂 Archivos Generados por Instancia

Por cada instancia `.lp.gz` procesada, se crea una carpeta con los siguientes archivos:

| Archivo | Formato | Contenido |
| :--- | :--- | :--- |
| `original_features.pickle.gz` | Pickle (Gzip) | **El "ADN" del problema (Grafo Bipartito).** Tipos de variables, límites (Bounds), coeficientes objetivo y matriz dispersa de restricciones (Constraint Matrix). |
| `presolved_features.pickle.gz` | Pickle (Gzip) | *Nota: Al estar inhibido el presolve, este archivo replica la estructura original, pero mantiene la compatibilidad de lectura del pipeline.* |
| `solutions.pickle.gz` | Pickle (Gzip) | **La Trayectoria Completa.** Vectores exactos de las soluciones incumbentes, relajaciones continuas en los nodos, el *Solution Pool* y el *benchmark* histórico (si existe). |
| `incumbents.parquet` | Parquet | **Línea de tiempo de soluciones enteras.** Registra el Nodo, Tiempo, Función Objetivo, Cota y MIP Gap exacto en el momento del hallazgo. |
| `node_relaxations.parquet` | Parquet | **Línea de tiempo de relajaciones continuas.** Registra la evolución de la cota y la cantidad de variables fraccionales vivas en el árbol. |
| `metadata.json` | JSON | Resumen de alto nivel del proceso (Runtime, Status final, Soluciones encontradas, Tiempos). |

*(Los archivos `.lp` originales no se reescriben para evitar la saturación del disco).*

---

## 🛠️ Ejecución en DGX-DASCI

El flujo principal está controlado por el sistema de colas **Slurm**, asegurando un control preciso de los recursos y evitando el colapso de las particiones.

### Requisitos Previos (Entorno)
Asegúrese de tener configurado el entorno `tfm_env` con las siguientes dependencias:
* `gurobipy` (con licencia válida configurada en la ruta absoluta).
* `pandas` y `pyarrow` (para exportación Parquet).
* `numpy`

### Lanzamiento de Lotes (Slurm)

El archivo `submit_cfl_data_generator_v3.sbs` controla la ejecución. 

1. **Configurar el lote:** Abra el script de Slurm y defina la categoría y el rango (ej. para procesar muestras controladas):

Saída de código:
Code executed successfully!
```bash
   CATEGORIA="CFL_easy_instance"
   INICIO=0
   FIN=3
   TIEMPO_GUROBI=3600

2. **Enviar a cola:**

sbatch submit_cfl_data_generator_v3.sbs

El script de Python cfl_gnn_data_generator_v3.py se encargará automáticamente de mapear las rutas locales absolutas, descomprimir los archivos .lp.gz originales y buscar históricos en los .pickle o .pickle.gz de MILPBench.

⚠️ Política de Repositorio (Código vs. Datos)
Para mantener la salud del repositorio en GitHub:

Solo el código fuente (este directorio) se sincroniza mediante git push.

Los datos de las instancias originales están en un Release y deven ser descomprimidos localmente tras un git clone.

Las carpetas de salida masivas en ./data están estrictamente bloqueadas en el .gitignore.

El dataset final (generado con las 3 muestras representativas) se mantiene en un entorno local en /data/intermediate_lps.

El dataset final debe distribuirse a través de plataformas diseñadas para MLOps (ej. Zenodo o Hugging Face Datasets) o compartirse comprimido en .tar.gz para su uso en los posteriores procesos de entrenamiento de GNN.
