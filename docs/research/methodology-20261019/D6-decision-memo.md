# D6 — Executive Decision Memo

19/10/2026 · Memorando breve de decisión · PR88 / PR87

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

GPU — PR87 propone una pareja seed42, serial1GPU/DDP4,100épocas,
batchglobal4,13.600presentaciones y3.400actualizaciones por brazo. Reutiliza
Gassev2 y54grafos. Dos jobs secuenciales de hasta12h,128GiB,4/16núcleos,
1/4V100: techo24hwall,60GPU-h y240núcleo-horas físicas. Los tests de gradientes
y CI no sustituyen evidencia real NCCL/V100. La diferencia de calidad macro
se informa junto al tiempo; margen0,02 descriptivo, no no-inferioridad estadística.

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

La redacción y figuras de datos existentes avanzan en paralelo. La figuraGPU
y la evolución12h siguen pendientes; no se rellenan. La sincronización
develop/main se pospone hasta revisar el artículo.

Se solicitan decisiones separadas de autorización GPU yCPU. Aprobar este
planeamiento no autoriza jobs, nuevas inferencias, paquetes, retries o merge.
La preparación documental/software puede continuar autónomamente. La próxima
frontera operativa es el permiso explícito y la CLI del autor, no otra frase
larga ni sucesivos permisos para fixtures. No se ejecutó HPC en esta entrega.
