# PR87: comparación completa serial1GPU y DDP4, seed42

## Qué se hizo y por qué

Los jobs3673 y3674 completaron la pareja autorizada, tras conservar la primera
pareja fallida3671/3672 y corregir su lanzador. Se compara el tiempo y la calidad
de dos entrenamientos completos con el mismo trabajo global, no un benchmark
corto ni cuatro entrenamientos independientes. No se repitió el experimento
para obtener un resultado favorable. Esta revisión no añade jobs o soluciones.

El [retorno original](../evidence/pr87/jobs3673-3674/public_return.json) conserva
SHA256 `909f6ce85dfdd9541e1624f8774bb099f27752e21408270f695e81aba7d576ab`.
Fuente ejecutada: `a2fef6040c71cbbf63c29e9f712e868ba7bfa42b`.
Plan: `59011f69616fc277d74b6f2e62898da3c78a33636aaf6abba3d1bfa10cb1814e`.
Nueva autorización instalada: `74df18d2da3711598528864932ab3336ca13af92701374e126e7a0fa260953b5`,
vinculada a la [decisión explícita del autor](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/87#issuecomment-6292612875).
El hash del mapa privado de entradas coincide con el de la campaña anterior;
no se exportan rutas privadas. Los recibos antiguos no se sustituyen.

## Cómo se verificó la comparación

Se reconciliaron fuente/plan/autorización, dos resultados completos y sus
supervisores, finalización Slurm0:0,100épocas,3.400updates y13.600presentaciones
globales por brazo. Coinciden por hash el estado inicial sin ajustar, el estado
ajustado y el schedule. Se conserva batchglobal4, misma loss por grafo, Adam,
clipping, FP32 y normalización ajustada solo con los34padres de entrenamiento.
El protocolo y sus pruebas de gradientes siguen en
[protocolo completo](pr87-matched-gpu-protocol.md); no se modificó el entrenador.

Se reutilizan54padres,34/10/10. Validación selecciona checkpoint y umbral;
test no selecciona. Los10padres de test (6fáciles/4medios) tienen exposición
histórica: son evaluación retrospectiva, no prueba independiente de generalización.
Cada brazo evalúa los modelos seleccionado y terminal sobre esos mismos padres.
La auditoría verifica el mínimo de pérdida de validación y el primer empate,
conteos por padre, métricas de confusión, suma pooled y media ponderada de Brier.
PR-AUC y Brier se reconcilian con los informes; no se releen probabilidades ni
checkpoints privados para un rescoring independiente. Los hashes de modelos
son los registrados por el código fuente ejecutado, no una nueva lectura HPC.

La afinidad registrada tiene4núcleos físicos por rank, sin CPUs compartidas
entre ranks DDP. Slurm muestra8/32AllocCPUS lógicas; no son8/32núcleos físicos.
La comparación aumenta también CPU de4a16núcleos: es escalado del sistema de
entrenamiento GPU+CPU, no causalidad aislada de añadir GPUs.

## Resultados de tiempo y recursos

| Medida | Serial1GPU | DDP4 | Interpretación |
| --- | ---: | ---: | --- |
| Lazo de entrenamiento sincronizado |1724,128s|795,637s|Aceleración2,167x; eficiencia respecto a4GPUs54,17%|
| Entrenamiento+validación+checkpoint |1800,170s|873,230s|Aceleración2,062x|
| Proceso medido por rank0 |2018,813s|1098,545s|Aceleración1,838x; no incluye toda la terminación distribuida|
| Job Slurm completo |2021s (33min41s)|1104s (18min24s)|Aceleración1,831x; reducción wall45,37%|
| Preparación instrumentada |175,790s|176,269s|Sin mejora material; regiones no aditivas con los scopes inclusivos|
| GPU-h asignadas, GPUs×ElapsedRaw/3600 |0,5614|1,2267|DDP usa2,185x más GPU-h, aunque termina antes|
| Núcleo-horas físicas asignadas |2,2456|4,9067|Derivadas de4/16cores×ElapsedRaw; no CPU activa medida|
| SlurmTotalCPU |2929,888s|4935s|ContabilidadCPU observada, no horas físicas reservadas|
| Pico RAM host cgroup muestreado |5,731GiB|15,524GiB|Scope de job, incluye procesos hermanos|
| SlurmMaxRSS batch |5,267GiB|15,130GiB|No equivalente al pico cgroup|
| Utilización media de dispositivos muestreada |75,36%|73,33% (media de4GPUs)|400/218muestras cada5s, sin consultas ausentes|

La pareja suma1,7881GPU-h asignadas y52min05s de elapsed secuencial, por debajo
del techo aprobado de60GPU-h/24h. No confundir utilización, GPU-h asignadas y
techo de reserva. Las regiones de tiempo son anidadas: no sumarlas. La suma
de tiempos por época reproduce el tiempo del lazo, usando el máximo entre
ranks DDP, no la suma de los tiempos paralelos. No se inventa desglose de
comunicación o energía. El orden serial→DDP es fijo y no elimina caché,
contención o efectos térmicos. No hay replicas temporales para estimar ruido.

El máximo del alocador GPU asignado es aproximadamente5,79GiB por rank; el
reservado alcanza7,54GiB. Se recogió después de train/validación y antes del
test final: no llamarlo máximo continuo del job. La telemetría de dispositivos
muestrea hasta8508MiB en DDP; tiene otro scope y no prueba exclusividad.
No hubo parada del supervisor ni señal deOOM. Esto cualifica esta pareja,
no toda ejecución futura a128GiB ni el límite de swap.

## Calidad: la aceleración no preservó el F1 observado

Macro significa media por padre, con el mismo peso para cada uno; pooled
agrega todas las binarias y puede ponderar más los padres grandes. PR-AUC
es área trapezoidal bajo precisión-recall, no average precision. F1 resume
precisión y recall con el umbral elegido solamente en validación.

| Checkpoint y métrica | Serial | DDP4 | DDP4−serial |
| --- | ---: | ---: | ---: |
| Seleccionado: F1 macro10padres |0,723065|0,690597|−0,032468|
| Seleccionado: PR-AUC macro10padres |0,783809|0,769959|−0,013850|
| Seleccionado: F1 macro6fáciles |0,732496|0,701919|−0,030576|
| Seleccionado: F1 macro4medios |0,708919|0,673613|−0,035305|
| Seleccionado: PR-AUC macro4medios |0,748083|0,751344|+0,003260|
| Seleccionado: F1 pooled |0,719050|0,686491|−0,032559|
| Terminal: F1 macro10padres |0,690522|0,675941|−0,014581|
| Terminal: PR-AUC macro10padres |0,762967|0,744679|−0,018288|

El F1 seleccionado cae en10/10padres. La caída macro de0,032468 equivale a
3,247puntos porcentuales y supera el margen descriptivo previamente fijado
de0,02 (2puntos). La caída PR-AUCmacro no supera ese margen. La mejora media
de PR-AUC en los cuatro medios muestra que el resultado no es uniforme para
todas las métricas. No se elige el terminal ahora para ocultar el resultado
seleccionado: ambas vistas se publican como estaban previstas.

Los mejores checkpoints proceden de épocas99/92 y los umbrales seleccionados
son0,998544/0,997792. Las trayectorias y estados finales difieren aunque la
inicialización y el schedule coinciden. La causa concreta de la divergencia
no está probada: no atribuirla como hecho aNCCL, reducción flotante, sampler
o un defecto de modelo. La equivalencia matemática de la loss y los tests de
gradientes no prometían trayectorias GPU bit a bit iguales.

Hay fuerte desbalance:5.265positivos en5.536.400binarias de test (~0,0951%).
El pos_weight de entrenamiento es1132,9758. El Brier pooled seleccionado pasa
de0,003797 a0,003525, pero el Brier macro pasa de0,005843 a0,006152: denominadores
distintos. Las probabilidades deBCE ponderada no están aquí cualificadas como
calibradas; una métrica de calibración aislada no sustituye F1/PR-AUC/recall.

## Conclusión admisible y cierre

**Observado:** en este caso seed42, DDP4 completa el mismo trabajo global antes,
con mayor asignaciónGPU-h y peorF1 seleccionado. **No demostrado:** preservación
de calidad, no-inferioridad estadística, robustez entre seeds, causalidad aislada
deGPU, aceleración del solver o generalización independiente. El protocolo
considera la pérdida relevante un resultado a informar, no un fallo que exija
repetición o tuning. No se autoriza otro entrenamiento, presupuestoCPU o merge.

La [revisión derivada](../evidence/pr87/jobs3673-3674/review.json) cualifica
scopes descriptivos concretos. No cambia `scientific_reporting_eligible=false`
del recibo original ni convierteCI/fin de job en promoción científica global.
El paquete resuelve la comparaciónGPU obligatoria con su resultado negativo
de calidad explícito. PR88 puede integrar tablas/figuras y limitaciones; la
campañaCPU adicional sigue pendiente de decisión separada. Main/develop solo
se sincronizan después de la revisión del artículo y autorización de release.

## Tablas, figuras y reproducción sin HPC

[Inventario de activos y comandos](../evidence/pr87/jobs3673-3674/README.md).
SieteCSV contienen2resúmenes de brazo,5scopes de tiempo,40filas padre/checkpoint,
16agregados,200épocas,5ranks y40contrastes padre/métrica/checkpoint. Cuatro
figurasSVG/PDF/PNG muestran tiempo/coste, calidad, trayectorias y recursos.
Los manifiestos vinculan todos los hashes al retorno y generadores.
Matplotlib3.9.2 local existente se utilizó solo para dibujar, porque el runtime
bundled no lo incluye; no se instaló ni actualizó nada en tfm_env. Los PDFs
se renderizaron conPoppler y se revisaron visualmente.
