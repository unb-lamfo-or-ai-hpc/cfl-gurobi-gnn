# PR88 — Integración de evidencia GPU y BCE por época

## Qué, cómo y por qué

El20/10 se integró PR87 en develop mediante32be98219d2d962c7d75402b9716744a582f2998,
desde el HEAD337ff5dd728beff2779f98652564eead4509c027 autorizado, con cinco
checks aprobados. PR88 combina D1–D6 con esa evidencia, no añade experimentos.
Preserva el [recibo original](../evidence/pr87/jobs3673-3674/public_return.json)
SHA256909f6ce85dfdd9541e1624f8774bb099f27752e21408270f695e81aba7d576ab,
los fallos3671/3672, las siete tablas y cuatro figuras de PR87 sin reescritura.
La [revisión previa](pr87-completed-pair-review.md) detalla sus alcances.

## Comparación observada, no efecto universal

| Medida | Serial1V100 | DDP4V100 | Lectura |
|---|---:|---:|---|
|Trabajo por brazo|100épocas;13.600presentaciones;3.400updates|Igual|Batchglobal4,seed42, mismo estado inicial/schedule por hash|
|Lazo de entrenamiento(s)|1724,128|795,637|Speedup2,167; eficienciaS/4=54,17%|
|JobSlurm(s)|2021|1104|Speedup1,831; no es el mismo alcance que el lazo|
|GPU-h asignadas|0,5614|1,2267|Mayor capacidad-tiempo asignada; no energía ni GPU-tiempo activo|
|Época elegida por validación|99|92|Ambos completaron100épocas; no early stopping|
|BCE mínima de validación|0,045286|0,048772|Pérdida ponderada, no F1|
|F1macro seleccionado|0,723065|0,690597|DDP−serial=−0,032468; cae en10/10padres|
|PR-AUCmacro seleccionada|0,783809|0,769959|DDP−serial=−0,013850; no confundir conAP|

La pérdidaF1 supera el margen descriptivo previamente fijado0,02. Es un
resultado negativo reportable, no permiso para tuning, otra seed o repetir.
PR-AUC dentro del margen no rescata una afirmación de calidad preservada.
La tabla[aggregates.csv](../evidence/pr87/jobs3673-3674/aggregates.csv) retiene
seleccionado y terminal, macro por padre y pooled por binarias, estratos F/M.
Seleccionado por validación es el análisis principal; no sustituirlo por el
terminal después de ver resultados. Los nuevos checkpoints no sustituyen M2
en los solvesPR86 y no demuestran beneficio downstream de solver.

## Figura nueva y guía de lectura

[PDF español](../evidence/pr88/gpu/gpu_bce_by_epoch_es.pdf),
[PNG](../evidence/pr88/gpu/gpu_bce_by_epoch_es.png) y
[SVG](../evidence/pr88/gpu/gpu_bce_by_epoch_es.svg).
La versión inglesa está incluida en el manuscrito. Dos paneles distinguen
entrenamiento y validación. Ambos ejes verticales tienen la misma escala
logarítmica: distancias iguales representan razones, no diferencias aditivas.
Se dibujan cuatro curvas de100valores (200filas de época,400valoresBCE),
sin suavizado ni interpolación. Los círculos
señalan los mínimos de validación en99/92, no mínimos de entrenamiento/test.

BCE es la entropía cruzada binaria ponderada, con peso positivo
1132,975830078125 ajustado solo con train. La pérdida por grafo promedia sus
binarias. Train es la media de136presentaciones durante las actualizaciones de
cada época; validación promedia diez padres después de la época con pesos
fijos. Por ello no son exactamente la misma evaluación de la red. Una época
del protocolo incluye cuatro presentaciones por padre de train, no una sola
pasada por los34padres. Menor BCE no equivale automáticamente a mayor F1:
F1 depende de las decisiones al umbral elegido por validación y su población.
La figura no muestra ni recalcula métricas de test por época.

`python scripts/evidence/plot_pr88_gpu_bce.py` genera las versiones ES/EN con
Matplotlib3.9.2 preexistente, sin torch, solver o HPC. Primero reconstruye y
verifica los productos auditados de PR87; después registra curvas y hashes de
fuentes/salidas en[manifest.json](../evidence/pr88/gpu/manifest.json).
Una regeneración en otro runtime gráfico puede variar bytes: no sobrescribir
el manifiesto publicado para ocultarlo; los valores de datos deben coincidir.

## Límites y siguiente frontera

Una pareja, seed42; diez padres de test históricamente expuestos, no
generalización independiente ni incertidumbre entre seeds. Orden serial→DDP
fijo y CPU4→16 junto con GPU1→4: no causalidad GPU aislada. Misma inicialización
y trabajo no prometen trayectorias idénticas; la causa concreta no se ha probado.
BCE ponderada no certifica calibración probabilística. Las diferencias entre
agregaciones macro y pooled son visibles, no intercambiables.

PyTorch2.1.2+cu121, CUDA del build12.1, driver550.90.07, NCCL2.18.6,
Python3.10.20, NumPy1.26.4, PyG2.7.0 y SciPy1.15.3: sin actualizar tfm_env.
RAM Slurm/cgroup y allocator/telemetríaGPU conservan sus distintos alcances;
no afirmar energía ahorrada ni pico continuo de todo el job a partir de muestras.
El flag original scientific_reporting_eligible=false permanece inalterado;
la revisión habilita solo los alcances descriptivos indicados, no promoción global.

El paquete CPU12h permanece propuesto, no aprobado; sus horizontes no se llenan
con extrapolaciones. Esta entrega no ejecuta HPC ni modifica métodos científicos.
PR88 requiere revisión editorial/CI antes de Ready y autorización propia antes
de merge. La sincronización develop/main queda para después de revisar el artículo.

## Verificación de esta entrega

106tests locales T1/T2 (31PR87,12PR88,43manuscrito,20archivo), dos skipsPOSIX;
Ruff0.16.8 check/format de198archivos. CI usaNumPy1.26.4; el entorno local3.13
conNumPy más reciente no expone np.trapz del código heredado, por lo que la
regresión relacionada se ejecutó conPython3.10 compatible, sin cambiar tfm_env.
No se atribuye ejecuciónBash al hostWindows. La figura se verificó por datos,
hashes y render visual; manuscrito23páginas, referencias desde20, checksPDF
aprobados. El [registro editorial](../../manuscript/validation.md) identifica
los hashesPDF/ZIP y límites. El T3 final enCI debe completarse antes deReady.
