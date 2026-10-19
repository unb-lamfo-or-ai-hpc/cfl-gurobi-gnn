# PR87 — entrenamiento serial en 1 GPU frente a DDP en 4 GPUs

## Decisión y objetivo

Contrato final de preparación, 19/10/2026. El autor descartó variar la seed:
**solo seed42, una pareja de entrenamientos completos**, sin búsqueda ni nuevas
arquitecturas. Dos configuraciones: serial real sin DDP y PyTorch DDP con cuatro
procesos, uno por GPU. Esta revisión sustituye las propuestas de tres parejas
y el plan histórico de cinco brazos de `mvp2_gpu_comparison_v1.json`, que se
conserva como antecedente, no como instrucción de ejecución.

Pregunta: ¿qué cambio de tiempo/recursos y de calidad predictiva se observa al
distribuir el mismo trabajo de aprendizaje? Una pareja permite un estudio de
caso medido, no incertidumbre entre seeds, no inferioridad estadística ni
garantía de speedup. Un resultado negativo es válido y no da permiso para
ajustar hiperparámetros o repetir el entrenamiento.

PR86 está merged en develop, commit3ac1883d081684acb36ba3855cd634e057a11c66.
No se repite su comparación CPU. PR87 trabaja sobre esa base y no cambia sus
recibos, MINIMIZE o resultados numéricamente sensibles.

## Datos y arquitectura reutilizados

Se reutilizan los grafos internos por hash de PR80, auditados54/54; no se
generan nuevos grafos, etiquetas o soluciones. Coorte mixta30F+24M: train34
(18F+16M), validación10(6F+4M), test10(6F+4M). Test históricamente expuesto,
no generalización independiente. Particiones por padre, sin fragmentos que
crucen roles. M13/M26 y difíciles no se incorporan.

Formulación MILPBench aceptada por decisión congelada del autor, excepto
MAXIMIZE erróneo: MINIMIZE obligatorio; originales, coeficientes, restricciones,
límites y dominios inalterados. Esta entrega no carga Gurobi ni optimiza.

Se reutilizan `gasse_calibrated.GasseGNN`, el fitter streaming train-only y el
muestreador determinista por padre existentes. Atributos7/5/1, dos capas,
dimensión32; Adam(lr0,001, betas0,9/0,999, eps1e-8, weight_decay0), clipping
de norma1. FP32, sin AMP ni TF32, sin compilation, mismo criterio de validación.
No se invoca el CLI antiguo con random_split por grafo o reanudación automática.
`tfm_env` se conserva; registrar versiones reales, sin actualizar paquetes.

## Equivalencia del trabajo y de la función objetivo

| Magnitud | Serial 1 GPU | DDP 4 GPUs |
|---|---|---|
| Épocas |100|100|
| Presentaciones por padre/época |4|4 en total, no cuatro por rank|
| Presentaciones globales/época |136|136|
| Batch global |4 grafos, acumulados secuencialmente|1 grafo por rank ×4|
| Actualizaciones/época |34|34|
| Total presentaciones/actualizaciones |13.600 /3.400|13.600 /3.400|
| Clip y optimizer.step |Una vez por batch global|Una vez por batch global|

Los cuatro grafos de cada batch son exactamente los mismos y en el mismo
orden global. Rank r recibe la posición r de cada grupo.136 es divisible por4:
no padding, omisiones o repeticiones del DistributedSampler. Cada padre tiene
el mismo peso de muestreo. El hash de las100secuencias queda registrado.

Para grafos con distinto número de binarias, la pérdida es:

`L_batch = (L_grafo1 + L_grafo2 + L_grafo3 + L_grafo4)/4`.

Cada L_grafo es la media de BCE binaria ponderada dentro de ese grafo. Así no
se pondera inadvertidamente más un padre por tener más variables. En serial
se retropropaga cada L_grafo/4; DDP promedia los cuatro gradientes locales y
por tanto **no se divide otra vez por4**. Clip después de acumular/sincronizar,
antes de Adam. El peso positivo se calcula una sola vez sobre los34padres de
entrenamiento, sin validación/test; no por rank. No se escala el learning rate.
Este batch4 difiere del serial histórico batch1: no es replay del checkpoint.
Los modelos nuevos de esta pareja no sustituyen los checkpoints congelados
usados por M2 en PR86. Su evaluación es predictiva y de coste de entrenamiento;
no se atribuyen a DDP los resultados solver ya obtenidos con otros checkpoints.
No se añaden nuevas resoluciones downstream a este presupuesto.

La documentación/código primario de [DDP en PyTorch2.1.2](https://github.com/pytorch/pytorch/blob/v2.1.2/torch/nn/parallel/distributed.py)
explica el promedio de gradientes; [torchrun2.1.2](https://github.com/pytorch/pytorch/blob/v2.1.2/torch/distributed/run.py)
define el lanzamiento por procesos. Se comprueba offline con pérdidas de tamaños
distintos y DDP CPU/Gloo real de cuatro ranks; no sustituye evidencia NCCL/V100.

## Inicialización, normalización y evaluación

Cada brazo comienza de nuevo, seed42, sin cargar un modelo entrenado. Rank0
ajusta los buffers de prenorm en CPU con los mismos34grafos de entrenamiento
y cuatro hilos, usando el fitter existente. Se registra el hash del estado
sin ajustar y del estado ajustado. Antes del entrenamiento DDP se difunden
explícitamente los buffers; DDP sincroniza los parámetros. Todos los ranks
comprueban el estado inicial. El segundo brazo debe coincidir con el estado,
pos_weight y schedule del serial antes de realizar su primera actualización.

100épocas fijas, sin early stopping y sin resume. Cada época evalúa exactamente
los10padres de validación en rank0 con el módulo **sin envolver**, mientras los
demás esperan; no se hacen forwards DDP desiguales. Selección: mínimo de la
media por padre de BCE ponderada, primer epoch en empate. Umbral: máximo F1
agrupado de validación con la regla de desempate ya existente. Ninguna decisión
utiliza test. El modelo terminal y el seleccionado se evalúan cada uno una vez
en los mismos10padres de test, con sus propios umbrales de validación.

Se guardan checkpoints, hashes,100filas de historia, métricas por padre y
pooled: precisión, recall, F1, PR-AUC trapezoidal y Brier. PR-AUC trapezoidal no
es average precision. Las métricas macro dan igual peso a cada padre; micro
agrega binarias. Las predicciones completas quedan privadas/no se exportan.
No se transforma el número de decisiones correlacionadas en tamaño muestral.

## Presupuesto exacto y riesgos aceptados

El autor autoriza avanzar solo con seed42 y el presupuesto necesario. Se fija
un techo operativo acotado de12h/job, no una estimación de duración garantizada:

| Recurso máximo | Serial | DDP4 | Pareja |
|---|---:|---:|---:|
| Jobs /entrenamientos |1|1|2|
| GPUs V100-SXM2 32GB |1|4|Nunca simultáneos entre jobs|
| Núcleos físicos |4|16|No sumar como uso simultáneo|
| RAM host por job |128GiB|128GiB|Teto común|
| Reserva wall |12h|12h|24h secuenciales|
| Reserva GPU-h |12|48|60|
| Reserva núcleo-horas físicas |48|192|240|

Nodo único dgx-dasci, partición batch, una tarea Slurm que lanza los procesos
locales, `--nodes=1-1`, `--hint=nomultithread`, sin exclusivo ni requeue. Un
procesador lógico por núcleo físico; cuatro núcleos disjuntos por rank. Es una
comparación del sistema GPU+CPU, no causalidad aislada de aumentar GPUs.
El orden es fijo, serial y después DDP: la caché de archivos y el estado del
nodo pueden favorecer al segundo. No se vacía la caché del sistema ni se promete
aislamiento térmico o ausencia de contención. Es una limitación del caso pareado,
no algo que se resuelva atribuyendo los tiempos solo a la cantidad de GPUs.

Parada host muestreada a112GiB, límite kernel de RAM de128GiB por job; reutilizar
el resolvedor de jerarquía/montajes cualificado con parámetros explícitos nuevos,
sin atribuirle cualificación histórica a128GiB. Fallo/pérdida de observación
de memoria detiene el proceso. OOM GPU detiene el entrenamiento; no reducir
batch, grafo o precisión en silencio. Sin garantía sobre swap. Watchdog hasta
11h50min deja reserva dentro del wall12h. Utilización/memoria/potencia GPU se
muestrean cada5s; ausencia de telemetría se declara, no se convierte en cero.

La duración y RAM del protocolo exacto no están probadas por tiempos de inferencia
o por los registros legacy. Este es el riesgo acotado aceptado, no motivo para
una campaña extra de pilotos. Si no termina, conservar ejecución incompleta,
sin retry, extensión, más semillas, epochs reducidos ni benchmark corto sustituto.
El presupuesto máximo no es consumo medido.

Los dos jobs se encolan juntos y ejecutan serialmente: DDP depende de afterok
y valida también los artefactos del serial. Si el serial falla, el dependiente
se cancela por dependencia inválida; no lanza una repetición. La reclamación
de envío se crea antes de sbatch: incertidumbre/parcialidad conserva IDs y
bloquea repetir submit. Ambos perfiles retenidos deben pasar antes de liberar.

## Medidas y criterios de aceptación

**Validez técnica, obligatoria:** hashes/roles correctos; mismo estado inicial,
loss, secuencia y trabajo;100épocas/3.400updates/13.600draws en ambos; dos
retornos completos; evaluación sin duplicaciones; recursos/afinidad registrados;
ningún solver ni cambio de entorno, retry o uso de test para seleccionar.

**Medición:** tiempo sincronizado del lazo de entrenamiento (incluye carga/transfer
de sus batches), región entrenamiento+validación+checkpoint, preparación y
tiempo de proceso, separados del elapsed Slurm del job completo. En DDP se usa
el máximo entre ranks de cada época; no sumar tiempos paralelos como wall.
Registrar throughput de draws/updates, `S=T_serial/T_DDP4`, eficiencia=S/4,
TotalCPU, GPU-h asignadas/medidas según alcance, cgroupRAM y peaks del alocador
por GPU. S del lazo y S del job son resultados distintos. Sin descomposición
inventada de comunicación, energía o ausencia de contención del nodo.

**Calidad:** diferencia DDP4−serial de F1 macro y PR-AUC macro de test, más
resultados por padre/clase y pooled. Margen descriptivo congelado de pérdida
0,02 absoluta: excederlo se informa como degradación relevante, no como fallo
que autorice repetir/tunear ni prueba de no inferioridad. S<1 también se acepta
como resultado negativo. Una seed no permite estimar variabilidad de entrenamiento.
Inicialización igual no garantiza trayectorias/checkpoints bit a bit iguales.

**Cierre científico:** revisión por métrica, tabla pareada de tiempo/calidad/coste,
figuras1/4GPU, limitaciones, recibos públicos y manifestos; ninguna promoción
global por acabar el job. No marcar Ready ni pedir merge antes de esa revisión.

## Ingeniería, operación y siguiente paso

T1 de contrato/operador → T2 de gradientes colectivos con tensores sintéticos
→ estabilización → T3 cuatro entornos de evidencia y job CPU-tensor adicional
en el HEAD exacto → CLI para el autor. El job tensor comprueba semántica no
cubierta por la suite sin torch; no duplica la regresión integral ni usa HPC.
Conservar caché pip; no ampliar el CI indiscriminadamente.

Preparación, envío, consulta y recogida están en
`scripts/evidence/operate_pr87_training.sh`; consulta/recogida no esperan en bucle.
El runbook fijará el commit publicado y las rutas de la campaña. La ejecución
explícita del comando de envío registra el presupuesto aprobado por el autor;
no pide una frase de confirmación ni aprobación para cada corrección técnica.
En el momento de publicar este protocolo aún no se ejecutó ningún entrenamiento
real de PR87. No confundir tests sintéticos CPU con cualificación instalada.

El manuscrito puede avanzar en paralelo. Sincronización develop/main solo
después de revisión del artículo y autorización separada; diciembre2026 sigue
siendo la prioridad. No ampliar dataset, arquitecturas, seeds o GPUs2/8.
