# D1 — Revised Experimental Protocol

## Qué, cómo y por qué

Evaluar cuándo la orientación neural beneficia o perjudica a Gurobi, separando
calidad, tiempo y coste. No presuponer superioridad ni atribuir causalmente el
resultado a class-aware sin una ablación que lo aísle. Cambiar la presentación
analítica y preparar nuevos presupuestos no cambia ninguna observación previa.

Se acepta la formulación CFL MILPBench, con una única corrección congelada:
forzar MINIMIZE, preservando originales, coeficientes, restricciones, dominios
y límites. MAXIMIZE es un error del benchmark para este estudio de costes.
La decisión no se convierte en una nueva prueba experimental ni exige generador.

M0 = Gurobi sin inicio externo. M1 = inicio parcial de valores binarios derivados
de la relajación raíz, calculada por Gurobi. M2 = inicio parcial de la GNN
congelada. M1 empareja el tamaño y número de unos del inicio M2: depende de esa
preparación, no es un baseline LP completamente independiente. La relajación
es entrada de la red y del comparador, no una solución fraccionaria que se envía
como si fuera una solución entera. Los valores Start son binarios y el resto
queda indefinido; no se fijan bounds ni se reduce la región factible.

## Población, procedencia e interpretación

54 padres auditados (30F+24M), partición34/10/10; train18F+16M,
validación6F+4M, test6F+4M. Mantener identidades/hash de grafos, LP, etiquetas,
checkpoint, buffers de normalización train-only, umbral y starts. No usar test
para seleccionar. Los diez padres de test ya fueron expuestos históricamente:
comparación retrospectiva controlada, no nueva generalización independiente.
Los seis medios históricos no se confunden con los cuatro medios de PR86.

PR86 conserva210 filas. Análisis principal MVP2: solo150 seed42 (90F,60M).
Las60 filas43/44 y sus figuras permanecen como histórico, no respaldan
repetibilidad, incertidumbre entre seeds ni conclusiones principales.
M4/M12:30 filas principales sensibles, tolerancias originales versus copia
redondeada no equivalentes; no declarar óptimo exacto o speedup certificado.
PR86 registra97 llegadas terminales reportadas por solver y53 censuras en seed42;
97 no significa97 certificados científicos o soluciones exactas.

Padre = unidad experimental. Método, límite de hilos y miles de binarias del
mismo padre son observaciones relacionadas. Presentar distribuciones por padre
y tamaños efectivos; con cuatro medios no inferir efectos poblacionales robustos.
No hacer tests confirmatorios con150 observaciones supuestamente independientes.

## Diccionario de métricas

| Métrica | Fórmula / unidad | Cómo leerla y cuándo es válida |
|---|---|---|
| Solver runtime | Reloj Runtime de optimize, s | No incluye toda la preparación; terminal no es cruce exacto |
| Preparación LP/grafo | Duraciones de etapas delimitadas, s | Por padre/hash; reutilización explícita, sin contarla dos veces |
| Inferencia | Forward medido con sincronización del dispositivo, s | No confundir con entrenamiento o tiempo de job |
| Construcción del inicio | Selección, mapeo y asignación Start, s | Desglosar solo si está instrumentado; ausente no es cero |
| End-to-end acotado | Preparación atribuible + intento supervisado, s | Enumerar etapas/frontera; no llamarlo coste total si omite cola/entrenamiento |
| Job wall | Slurm ElapsedRaw, s | Incluye overhead del job, no necesariamente la cola |
| Cola | Inicio−envío, s | Solo con ambos timestamps, separada del solver |
| Speedup_M2_M0 | T_M0 / T_M2, adimensional | >1 favoreceM2; mismo padre, seed, hilos y objetivo común alcanzado |
| Razón histórica M2/M0 | T_M2 / T_M0 | <1 favoreceM2; preservar nombre y valores históricos |
| Speedup_CPU(r) | T_m(1)/T_m(r) | Mismo método y criterio comparable; no es beneficio neural |
| Efficiency_CPU(r) | Speedup_CPU(r)/r | Fracción; no usar AllocCPUS lógico como r físico |
| Speedup_GPU | T_serial1/T_DDP4 | Trabajo equivalente; especificar lazo, proceso o job |
| Efficiency_GPU | Speedup_GPU/4 | Descriptiva de GPU+CPU, no causalidad GPU aislada |
| Primal zP | Objetivo del mejor incumbente, unidades del modelo | En MINIMIZE menor es mejor; factibilidad reportada y auditada son distintas |
| Dual zD | Mejor límite inferior del solver | En MINIMIZE mayor cierra la brecha; no mezclar campañas/objetivos |
| Gap absoluto | abs(zP−zD), unidades del modelo | Requiere ambos valores finitos |
| Gap relativo | abs(zP−zD)/abs(zP), fracción | Si zP=0:0 si ambos0, infinito si difieren; datos ausentes separados |
| Diferencia de gap |100(g_M2−g_M0), puntos porcentuales | Negativa favoreceM2; no es speedup |
| Estado terminal | Estado/código y tolerancias | OPTIMAL significa según tolerancias, no aritmética exacta |
| Primer cruce observado | min timestamp con gap≤alvo, s | No instante continuo exacto; censura y falta de observación distintas |
| Calidad a horizonte H | zP,zD,g,status con timestamp real | No interpolar ni sustituir por un terminal de tiempo distinto |
| CPU time | TotalCPU de Slurm, CPU-s/3600 | Contabilidad de procesadores lógicos; no reserva física medida |
| Reserva núcleo-h | r físico×wall reservado, h | Capacidad solicitada, no consumo real |
| GPU-h asignadas | GPUs×ElapsedRaw/3600 | Ocupación asignada, no utilización activa medida |
| Reserva GPU-h | GPUs×wall solicitado/3600 | Techo previo, no observación |
| Uso GPU | Muestras de utilización por GPU, % | Informar cobertura/cadencia; no inventar GPU-time activo o energía |
| RSS | Residente del proceso, bytes/GiB | Diferente de cgroup y memoria de GPU |
| cgroup RAM | Uso agregado bajo ancla job, bytes/GiB | Incluye hermanos/caché según controlador; muestreo no pico continuo |
| Slurm MaxRSS | Máximo reportado por step, unidad explícita | No sumarlo ni equipararlo a cgroup/RSS/GPU |
| Memoria GPU | Pico allocated/reserved y telemetría, bytes | Allocator y nvidia-smi tienen alcances distintos |
| F1 | 2TP/(2TP+FP+FN) | Umbral de validación; macro por padre ≠ micro por binarias |
| PR-AUC / AP | Trapecios PR / suma ponderada de precisiones | Métricas distintas; no renombrar PR-AUC como AP |
| BCE / Brier | Pérdida logarítmica / media(p−y)² | Definir peso positivo, población y agregación |

## Censura, horizontes y aceptación prospectiva

Campaña CPU propuesta D2: nueva experiencia, no resume ni extensión de PR86.
Seed42, mismos cinco caps, tres métodos, MIPGap=0,0001, TimeLimit43200s.
Preservar todos los demás parámetros mediante diff del manifiesto antes del envío.
Reutilizar solo los artefactos ya cualificados; un artefacto ausente detiene la
preparación, no autoriza recalcular raíz/inferencia ni etiquetas automáticamente.

Registrar cruces observados10%,5%,1%,0,01%. Alvo no alcanzado al terminar:
right-censored a su seguimiento observado; dato perdido: unavailable; vector
no cualificado: numerically_unqualified. Ninguno se reemplaza por un tiempo
de resolución certificado. Comparar speedup solo si ambos alcanzan el mismo
objetivo con elegibilidad numérica suficiente; informar la selección de pares.
El análisis de casos completos no representa los pares censurados.

Horizontes1h/4h/8h/12h: guardar timestamp, estado y zP/zD/g efectivamente
observados, staleness y observaciones que delimitanH si existen. Una muestra
cercana no es una medición exacta enH. Si termina antes, etiquetar
terminated_before_horizon y su valor terminal, no fingir ejecución hastaH.
Indicar factibilidad solver-reported frente a vector independientemente auditado.
El callback histórico se conserva; instrumentar un adaptador prospectivo
versionado y probar estos estados antes de pedir autorización de ejecución.

Aceptación técnica: manifiestos/recursos íntegros, matriz sin duplicados, no
retry, salidas reproducibles y censura explícita. Aceptación científica por
métrica, incluyendo evidencia negativa. Un jobCOMPLETED o CI verde no
certifica resultados. DDP se revisa aparte con su propio paquete GPU.
