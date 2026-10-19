# D3 — Scientific Figures Revision

## Fuentes y cambios

El archivo original `docs/evidence/pr86/final-210/` se conserva, incluidos los
gráficos multiseed y manifiestos. Es un archivo histórico inmutable, no el
directorio de figuras principales revisadas. El índice siguiente distingue lo
regenerado de lo pendiente. No trasladar archivos rompiendo hashes o enlaces.

Las tablas seed42 nuevas están en `docs/evidence/methodology-20261019/`.
`seed42_main.csv` conserva los valores originales de150 filas; sus columnas de
coste amortizado histórico siguen siendo/7, no se reinterpretan. El nuevo
`seed42_cost_scenarios.csv` explicita el escenario/5 para cinco usos por método
en la matriz principal. No es una medición nueva ni el coste de la campaña12h.

| Figura | Pregunta y especificación | Evidencia disponible / límite |
|---|---|---|
|1 — Mecanismo|MILP→raíz/grafo→GNN→selección class-aware→Start→Gurobi; ramasM0/M1, costes compartidos|Diagrama metodológico; M1 recibe presupuesto de soporte/unos deM2, no baseline independiente|
|2 — Efecto warm start|Tiempo por padre y speedup T0/T2,T1/T2; fáciles/medias separados|Tabla `seed42_paired_speedups.csv`, pares elegibles; no convertir censura en barra de speedup|
|3 — Calidad temporal|Primal,dual,gap a1/4/8/12h, timestamp real y estado|Pendiente campaña larga y adaptador; terminal histórico no es trayectoria ni valor exacto a1h|
|4 — CPU|Tres paneles separados: T_m(r),T_m(1)/T_m(r),eficiencia/r|`seed42_cpu_scaling.csv`; mismo método y objetivo común, n por panel|
|5 — End-to-end|Raíz,grafo,inferencia,construcciónStart,solver; shared/reuse separados|`seed42_cost_scenarios.csv` acotado; componentes sin timer no se inventan, no barra de E2E total|
|6 — Recursos|cgroup muestreado,TotalCPU,MaxRSS por alcance|cgroup disponible en150filas; CPU por job en contabilidad original filtrada por IDs42; no mezclar memoriaGPU|
|GPU adicional|Serial1/DDP4:tiempo, S,S/4, GPU-h y calidad por padre|PendientePR87; no dibujar speedup esperado como observado|

Se regeneran además paneles descriptivos seed42 de warm-start/CPU y memoria
con el script `plot_pr88_methodology.py`. No hay intervalos multiseed. Los
medios censurados/sensibles se identifican mediante la tabla, no mediante un
speedup terminal ficticio. Cada figura debe declarar denominador, unidad, alcance
y restricción numérica. La figura6 de memoria muestreada no demuestra consumoCPU.

## Tablas para el artículo

T1 población/roles/exposición y hash de checkpoint; T2 hiperparámetros y trabajo
igual1/4GPU; T3 elegibilidad y censura por padre/método/cap; T4 speedups por pares
con igual objetivo; T5 tiempos/componentes/costes de escenario; T6 CPU/RAM/GPU
por alcance; T7 presupuesto y ejecución realmente consumida separados.
Las tablas grandes van a material suplementario con manifiesto, no escondidas
tras medias globales. Las60 filas43/44 no forman la muestra principal.

## Control editorial

No presentar97 llegadas reportadas como97 óptimos certificados. No comparar
M4/M12 con certificados exactos. Mantener razónM2/M0 histórica con su dirección;
la nueva dirección speedup>1 se etiqueta T0/T2 explícitamente. No usar150como
n independiente, ni afirmar superioridad global por un promedio favorable.
Describir heterogeneidad y sensibilidad a preparación antes de discutir utilidad.
La actualización del manuscrito distingue claramente el estudio histórico de
seis medios y el análisis principal MVP2 de diez padres expuestos.
