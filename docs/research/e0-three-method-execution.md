# E0: ejecución de los tres métodos con insumos existentes

## Qué, cómo y por qué

El manifiesto instalado SHA256
`f7d4be22fd3105506e0dcde22db249d507744b4d5ab464e9b6625dd7e9f848c4`
vincula seis MILPs fáciles originales con las predicciones del job3505, sus
relajaciones almacenadas y los inicios parciales GNN/LP. La revisión independiente
confirmó seis padres, sin inferencia, entrenamiento ni optimización adicionales.
El manifiesto se preserva en `docs/evidence/e0/easy-start-binding.json`.

La nueva entrega responde a la pregunta pendiente: ¿mejoran estos inicios la
calidad o el tiempo del Gurobi frente al mismo problema sin inicio externo?
No se reconstruyen grafos ni se entrenan modelos. Reutilizamos el solver
`paired_partial_start.solve`, su auditoría matemática independiente y el
watchdog de memoria cualificado durante la Sprint B. Tres argumentos opcionales
añaden el límite blando de memoria, el log privado y una marca previa al solve;
los consumidores históricos conservan el comportamiento por defecto.

La PR81 todavía está abierta. Por petición del operador, esta nueva PR depende
de `feature/e0-existing-evidence`; no incorpora ni autoriza su merge. Tras el
merge autorizado de PR81 en `develop`, se cambiará la base de esta PR a
`develop`, se comprobará el diff y se repetirá el CI del head vigente. Ninguna
de estas operaciones modifica `main`.

## Contrato previo a ejecución

| Elemento | Valor |
| --- | --- |
| Padres, orden fijo | F0, F3, F6, F14, F27, F29 |
| Métodos dentro de cada padre | Sin inicio; LP emparejado; GNN mixta |
| Modelo | Checkpoint mixto histórico PR58, no seleccionado por el resultado del test |
| Inicios | Hasta 10% y 20000 binarias; LP y GNN con igual soporte y número de unos |
| Solver | Gurobi 13.0.1, minimización explícita del original, semilla 42 |
| Presupuesto de cada método | Threads=1; TimeLimit=3600 s; MIPGap=0.0001 |
| Máximo total | 18 llamadas; 64800 segundos de solver; un job secuencial de hasta 20 h |
| Slurm | batch; 1 nodo; 1 tarea; 1 núcleo solicitado; 64 GiB; sin GPU/exclusive/requeue |
| Afinidad | Un procesador lógico permitido por la asignación, un núcleo físico utilizado |
| Memoria | SoftMemLimit=48 GB decimales; parada muestreada a 56 GiB; límite kernel <=64 GiB |
| Plazo del proceso hijo | 3780 s, incluyendo preparación, solve, auditoría y exportación |

El MIPGap histórico es **0.01%**, no 1% ni el 10% del piloto CPU. No se mezclan
sus controles: esta entrega produce tres resoluciones nuevas por padre bajo
el mismo contrato. Los límites 1,2,4,8,16 siguen reservados para E1/E2, no se
multiplica ahora el presupuesto por cinco ni por dos modelos.

Ejecutar manualmente `submit` autoriza únicamente este presupuesto explícito;
no se pide una frase adicional. Este documento o el manifiesto por sí solos no
ejecutan nada. La preparación anterior con `solver_execution_admitted=false`
se conserva intacta; no se cambia retrospectivamente su estado.

## Flujo y protección de las evidencias

1. Instalar un snapshot del head exacto después de sus cuatro checks. `submit`
   congela el plan, comprueba la licencia existente y crea una marca exclusiva
   antes de una única llamada a `sbatch`. Devuelve inmediatamente el job ID.
2. El batch toma la ruta de código exportada, no la copia temporal de Slurm.
   Antes de leer el modelo comprueba asignación, afinidad y cgroup de memoria.
3. Cada método usa un proceso nuevo y verifica los hashes del MILP y del inicio.
   Solo se asignan valores `Start` a binarias seleccionadas; no se fijan cotas,
   no se guían continuas y el control no recibe inicio. Se conserva la firma
   matemática y se audita independientemente la factibilidad del incumbente.
4. Un error, pérdida de observación, plazo excedido o SoftMemLimit detiene toda
   la secuencia. Un TIME_LIMIT ordinario a 3600 s es un resultado censurado,
   no un error que autorice retry. No se reducen hilos ni se amplía presupuesto.
5. `status` consulta una sola vez. `collect` requiere estado terminal, incluso
   si falló, comprueba la vinculación de logs cerrados y produce un retorno
   sanitizado único. Un fallo anterior al ledger puede tener `matrix=null`:
   no se confunde con una matriz completa.
6. Una conexión SCP descarga el retorno. Los logs, soluciones y predicciones
   permanecen privados en el HPC; solo viajan métricas y hashes.

Los resultados llevan parámetros efectivos, sentido fuente/efectivo,
primal/dual/gap, estados, tiempos observados a objetivos, aceptación del inicio,
tiempos de carga/solve/auditoría, trayectoria y memoria muestreada. La marca de
intención anterior a `optimize` no prueba por sí sola que el solve haya terminado.
Una caída sin retorno hijo deja el número exacto de llamadas sin acreditar.

Los tiempos a objetivo son primeras **observaciones**, no cruces exactos. El
coste histórico de la relajación es desconocido, no cero. Los resultados nuevos
no respaldarán coste total end-to-end hasta resolver o declarar esa ausencia.
Slurm MaxRSS y memoria cgroup tienen distintos ámbitos. No se hace una afirmación
de aceleración CPU/GPU con este bloque de un hilo.

## Salidas y cierre

Después de revisar el retorno: tabla por padre/método con diferencias pareadas,
curvas de gap/tiempo, aceptación de inicios y costes con valores ausentes
explícitos; CSV/JSON y figuras SVG/PDF/PNG con procedencia. M13/M26, excluidas
de las 54 muestras etiquetadas, siguen pendientes de preparación separada sin
etiquetas; no se presentan como parte de estos seis ni como test intacto.
La PR permanece draft hasta revisar evidencia y resultados, después ready y
solicitud explícita de merge. No se fuerza un resultado positivo.

Para la posterior sincronización al final de la Sprint C, véase
[el plan de ramas protegidas](sprint-c-protected-release.md).
