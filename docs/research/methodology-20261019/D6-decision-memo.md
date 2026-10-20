# D6 — Executive Decision Memo

20/10/2026 · Actualización tras integración PR87 · PR88

## 1. Cambio metodológico

El objetivo sigue siendo evaluar orientación GNN de Gurobi, no demostrar una
superioridad asumida. La matriz principal queda en150resoluciones seed42;
las60adicionales43/44 y sus figuras se conservan como histórico, fuera de las
conclusiones principales. La unidad experimental es el padre. Se preservan
MINIMIZE, formulación, particiones, checkpoints y recibos originales.

Se distinguen M0sin inicio externo, M1relajación emparejada y M2GNN congelada.
M1 depende de la preparaciónM2; no es una heurística LP independiente. El
speedup nuevo usa T0/T2 (>1favoreceM2), sin renombrar razones históricas.
Censura, calidad terminal y certificación numérica no son intercambiables.

## 2. Evidencia suficiente y límites

PR86 está integrada:210registros preservados. La vista principal contiene
90observaciones fáciles y60medias, de diez padres históricamente expuestos.
Hay97llegadas al criterio terminal reportadas por solver y53censuras, no97
óptimos exactos certificados. M4/M12 mantienen30observaciones sensibles en la
vista principal, excluidas del speedup certificado. Los resultados heterogéneos
y los costes de preparación no sustentan una mejora uniforme de laGNN.

La auditoría de54padres, el binding de starts y la trazabilidad permiten
redactar metodología, límites y análisis CPU disponible. El histórico no
justifica generalización independiente o robustez entre seeds.

## 3. Lagunas y dos paquetes independientes

GPU — PR87 ya completada y merged en develop a32be9821, desde el HEAD exacto
337ff5dd autorizado. Jobs3673/3674, seed42,100épocas, batchglobal4,
13.600presentaciones y3.400actualizaciones por brazo. Gassev2/54grafos,
estados iniciales y schedule coinciden por hash. Lazo1724,128→795,637s:
speedup2,167x, eficiencia54,17%. Job2021→1104s:1,831x.
GPU-h asignadas0,5614→1,2267; no ahorro de capacidad asignada ni medida de energía.
F1macro seleccionado0,723065→0,690597: pérdida0,032468, superior al margen
descriptivo0,02. PR-AUCmacro0,783809→0,769959. No calidad preservada ni
no-inferioridad; F1 cae en10/10padres. Una seed y orden fijo;4→16núcleos CPU
acompañan a1→4GPU, sin causalidadGPU aislada. Causa de divergencia no probada.
No reemplazar checkpointsM2 de PR86 con los recién entrenados ni inferir su
beneficio para solver. Recibos fallidos3671/3672 y flags originales se preservan.

CPU — D2 propone60resoluciones nuevas:4medios×3métodos×5caps,seed42.
TimeLimit12h ywall13h porjob,64GiB, sinGPU, sin concurrencia entrejobs:
720hsolver,780hreserva secuencial y4.836núcleo-horas reservadas.
No son consumos observados ni una extensión de los solves antiguos.
Se necesitan gates vigentes de partición/afinidad/memoria, integridad,
alcance numérico, presupuesto y calendario. Más tiempo no corrige M4/M12.
Instrumentar cruces10/5/1/0,01% y horizontes1/4/8/12h sin interpolación.

## 4. Calendario y decisiones

Se mantienen D26/10–13/11, E09/11–20/11 yF16/11–11/12, con hitos15/11,
15/12 y31/12. CPU puede ocupar32,5d máximos, más filas: riesgo crítico para
15/11 yE. No prometer esa fecha basándose en tiempos pasados ni recortar
selectivamente la matriz. Si no cabe, decidir otra propuesta antes de ejecutarla.

La redacción y figuras de datos existentes avanzan en paralelo. La figuraBCE
comparativa y resultadosGPU ya están incorporados; la evoluciónCPU12h sigue
pendiente, sin rellenar. La sincronización
develop/main se pospone hasta revisar el artículo.

Solo el paqueteCPU sigue pendiente de decisión independiente; la autorización
GPU utilizada no libera más entrenamientos. Esta integración documental y
editorial no autoriza jobs, inferencias, upgrades, retries ni mergePR88.
Puede continuar autónomamente la preparación/revisión con evidencia existente.
No se ejecutó HPC en esta entrega; main sigue reservado para la revisión final.
