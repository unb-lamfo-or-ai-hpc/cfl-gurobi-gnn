# PR87: activos de la pareja seed42, jobs3673/3674

Revisión e interpretación: [informe científico](../../../research/pr87-completed-pair-review.md).
El recibo original mantiene SHA256
`909f6ce85dfdd9541e1624f8774bb099f27752e21408270f695e81aba7d576ab`.
No se modifica su flag de elegibilidad. La revisión derivada delimita las métricas
descriptivas; no afirma preservación de calidad ni generalización independiente.

## Tablas machine-readable

| Archivo | Unidad de fila | Filas |
| --- | --- | ---: |
| summary.csv | Brazo/entrenamiento |2|
| timings.csv | Región de tiempo anidada |5|
| quality.csv | Brazo/checkpoint/padre |40|
| aggregates.csv | Brazo/checkpoint/cohorte/ponderación |16|
| history.csv | Brazo/época |200|
| ranks.csv | Brazo/rank |5|
| deltas.csv | Checkpoint/métrica/padre |40|

Valores numéricos, unidades explícitas, sin convertir ausencias en0. LosCSV son
derivados reproducibles del JSON, no lecturas nuevas de checkpoints o probabilidades.
`manifest.json` fija los hashes de recibo, revisión y tablas.
`figures_manifest.json` liga sus entradas y los12archivos de las cuatro figuras.

## Figuras

- [Tiempo y GPU-h asignadas](training_time_cost.pdf).
- [Calidad por padre y agregación](predictive_quality.pdf).
- [Trayectorias train/validación](learning_curves.pdf).
- [Memoria y utilización, scopes separados](resource_memory.pdf).

También disponibles con los mismos nombres enSVG yPNG. Ninguna banda de
incertidumbre entre entrenamientos: solo una seed. Las figuras distinguen
seleccionados y terminales, margen descriptivo de0,02 y mediciones de memoria.

## Reproducir offline desde la raíz del repositorio

```bash
python -B scripts/evidence/review_pr87_training_pair.py \
  --receipt docs/evidence/pr87/jobs3673-3674/public_return.json
python -B scripts/evidence/plot_pr87_training_pair.py
python -B -m unittest discover -s tests/evidence -p 'test_pr87_pair_review.py' -v
```

El revisor usa la biblioteca estándar y módulos existentes, sin torch/Gurobi.
El generador gráfico requiereMatplotlib3.9.2 para reproducir estos mismos bytes;
no es requisito del ambienteHPC ni motivo para actualizarlo. Se rechaza
sobrescribir un activo diferente. Para otra versión deMatplotlib use `--directory`
en un directorio de salida nuevo con las mismas tablas/manifiesto verificados.
No sustituir activos publicados o sus manifiestos por una variante silenciosa.

La pareja fallida anterior permanece en `../job3671/`; no se mezcla con los
dos entrenamientos completos ni desaparece del historial de intentos.
