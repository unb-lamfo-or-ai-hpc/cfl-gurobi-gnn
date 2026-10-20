# CPU12h — ejecución prospectiva y preparación instalada

20/10/2026 · Próxima entrega tras PR88 merged (`e5804a8c`).

**Decisión posterior del autor,20/10:** aprobado el paquete CPU completo descrito
abajo (respuesta explícita: «Aprovar o pacote CPU completo»). Sujeto a preflight
instalado y CI del HEAD exacto. La preparación sigue creando un plan con flag
false; la autorización separada se registra solamente al ejecutar el bloque
aprobado. No se ha sometido ningún job desde Codex.

## Qué y por qué

Implementar D1/D2 de la revisión19/10: cuatro padres medios expuestos
M0/M4/M7/M12 × M0/M1/M2 ×1/2/4/8/16núcleos físicos, seed42. Son60
experimentos frescos, no60 reintentos ni continuación temporal de PR86.
El mayor horizonte permite observar calidad y censura donde1h fue insuficiente;
no garantiza convergencia ni superioridadGNN. InstanciaM0 y métodoM0 son campos
distintos. M4/M12 conservan límites numéricos y no aportan speedup certificado.

Reutilizar LP, raíz, grafo, checkpoint, predicciones y starts ya revisados en
PR86. No usar los nuevos checkpoints de PR87, no rehacer inferencia/raíces,
no cambiar variables, bounds, coeficientes o tolerancias. MINIMIZE obligatorio.
M1 sigue emparejado en soporte/número de unos conM2, y carga sus costes.
Los60 IDs locales se distinguen del histórico mediante el protocolo/plan nuevo.

## Cómo: ingeniería acotada

- Un núcleo de resolución: `pr86_solver.py` conserva su comportamiento histórico
  por defecto y recibe opcionalmente una política prospectiva versionada. Se
  reutilizan carga, Start parcial, auditoría matemática y exportación privada.
  No se copia otra implementación del solver ni se reescriben los recibos.
- `pr89_cpu_contract.py` verifica la matriz y el orden de métodos de D2;
  fija todos los parámetros reportados por el histórico3522, cambiando solo
  TimeLimit a43200 y el cap deThreads de cada celda. MIPGap1e-4, seed42,
  SoftMemLimit48GB decimales. Checkpoint original de PR86 por hash.
- `pr89_cpu_temporal.py` registra cada primer cruce observado10/5/1/0,01%
  con el punto anterior y reloj monotónico desde optimize. No es el cruce
  continuo exacto. Horizontes1/4/8/12h guardan observaciones antes/después,
  staleness y estado; no interpolan. Terminación temprana se conserva como
  `terminated_before_horizon`. No se inventa una trayectoria hasta12h.
  Los resúmenes no convierten factibilidad reportada en certificación exacta.
- La trayectoria nueva se muestrea cada30s más terminal; los cruces/horizontes
  se actualizan en cada callback, antes del muestreo. Evita crecimiento por
  cada incumbente durante12h sin alterar el registro histórico.
- `pr89_cpu_workflow.py`: prepare/authorize/submit/run/status/collect/review,
  un solve por job. Un operador admite cualquier prefijo nuevo1..60, sin crear
  una nueva implementación/PR por cada onda. Una onda enviada no se reintenta.
  `afterok` más validación del resultado/recibo anterior; fallo bloquea la cadena.
  Las consultas son puntuales, no bucles que bloqueen la terminal del usuario.
- `operate_pr89_cpu.sh` resuelve desde stage/source también en la copia Slurm;
  no repite el defecto del launcher GPU. Variables SBATCH/SLURM/SRUN heredadas
  se eliminan al enviar. Memoria/CPU/identidad se verifican en cada asignación.
  El lanzador separa prepare/authorize/submit/status/collect/batch. La ejecución
  aprobada verifica el preflight antes de registrar autorización o enviar jobs.

## Recursos y autoridad

| Concepto | Techo, no consumo ni duración pronosticada |
|---|---:|
| Jobs / optimize |60 /60; uno por job, máximo uno activo|
| Optimize / wall por job |12h /13h|
| RAM / GPU |64GiB /0|
| Solver acumulado |720h|
| Reserva secuencial |780h =32,5d, más colas|
| Capacidad solver física |4464núcleo-h|
| Reserva física |4836núcleo-h|

Una hora de margen total: carga previa≤15min, watchdog45.000s desde despacho
(12h30min) y otros30min para revisión/teardown del padre. Si la carga consume
su reserva, falla antes de optimize; no acorta silenciosamente12h ni extiende el
job. Exportación/auditoría excedida produce evidencia incompleta, sin retry.
CPU batch, un nodo `nodes=1-1`, ntasks1, sin GPU/exclusivo/requeue. Un lógico por
núcleo físico; AllocCPUS puede contabilizar SMT y no es el cap experimental.

Guard existente: kernel≤64GiB, uso job-scoped agregado muestreado≤56GiB,
SoftMemLimit48GB decimales. Pérdida de observabilidad/afinidad para el hijo.
La memoria futura no se declara cualificada por el contexto antiguo o CI.
tfm_env sin modificaciones, mismos Python/NumPy/Gurobi que la preparación.
La carga real del modelo confirma licencia antes del único optimize.

**Aprobación CPU específica recibida20/10**, incluido riesgo de32,5d más colas.
No se deduce de la autorización GPU gastada ni de avanzar en software.
La aprobación se vincula al plan/commit/
presupuesto, y se comprueba al enviar y en la ejecución. No puede aprobarse
automáticamente desde `prepare`. Ningún job se ha ejecutado en esta entrega.

## Siguiente intervención: una preparación útil, sin job

El bloque publicado con el SHA exacto crea un stage nuevo y ejecuta `prepare`:
verifica las cuatro cadenas privadas existentes, versiones y el MaxTime actual
de batch; exporta `preflight.json` y el SHA del plan. No importa Gurobi para
resolver, no deserializa checkpoints, no entrena ni consulta GPUs. Un único SCP
descarga el recibo; la contraseña solo se solicita una vez para esa transferencia.
No repetir prepare si ya existe salida; conservarla y revisar cualquier fallo.

Este preflight no demuestra permisos de envío/afinidad/cgroup/licencia futuros:
estos gates se verifican en la reserva held y en cada asignación autorizada.
El bloque de ejecución se libera después de CI del HEAD exacto. La aprobación
CPU está recibida; el bloque primero valida el preflight instalado y detiene
todo ante cualquier fallo. Se puede encolar una onda amplia hasta60jobs secuenciales
con un comando, si el sitio permite esa cantidad; no se aumenta concurrencia.
Límite administrativo de jobs/ambigüedad de sbatch conserva los claims y todos
los jobs ya creados held; no reenvía ni borra evidencia automáticamente.

## Validación y aceptación

T1: reloj/horizontes, censura/ausencia, infinito/cero, matriz/arithmetic, órdenes,
parámetros, autorización CPU≠GPU, single-optimize con backend simulado.
T2: regresión del executor/recursos/costes anteriores; held/dependencias,
env heredado, release inverso, envío ambiguo/duplicado y pérdida de afinidad.
T3/CI: suite existente en Linux/Windows3.10/3.12, lint/format fijados y sintaxis
shell; no llamada a solver real/HPC. Las pruebas sintéticas no certifican gates
instalados. Ready requiere revisión y resultados/limitaciones según alcance.

Revisión local estabilizada20/10:83tests T1/T2 en49,525s, un skip POSIX en
Windows;30tests propios incluidos. Ruff0.16.8check/format de202archivos y
parser PowerShell correctos. El backend de solver de pruebas es simulado.
El CI completo del HEAD publicado se registra en la PR, sin atribuirle ejecución
HPC. Una ejecución local anterior se repitió después de estabilizar los bytes:
un test de identidad detectó una edición concurrente durante la propia prueba;
no fue un fallo experimental ni se modificó evidencia histórica para pasarlo.

Cada retorno conserva plan, autorización, contabilidad, resultados, supervisión
y hashes; recibo fallido puede transferirse, sin llamarlo solve cualificado.
Logs, vectores y rutas privadas quedan en HPC. Revisión por métrica antes de
crear figuras de calidad temporal y ratios por pares con objetivo común.
No usar censura como tiempo exacto ni mezclar1h+12h como una sola ejecución.
Las evidenciasPR86/87/88 y sus flags permanecen intactos.

Continúan en paralelo tablas/figuras de datos existentes y revisión de coautores.
El techo de calendario amenaza15/11; cualquier reducción de matriz/concurrencia
necesita una decisión prospectiva, no selección por resultados favorables.
Sin sincronización develop/main antes de revisión final del artículo.
