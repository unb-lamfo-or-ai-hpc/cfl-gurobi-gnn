# PR86 — cierre analítico de la matriz CPU, 19/10/2026

## Qué se entrega y por qué

Se recibieron las nueve resoluciones finales: jobs3662–3664, todos COMPLETED0:0.
El retorno original SHA256
`a3a219799291d2471a9329eda922aca2ac34b29a2dfa77dd63ec1dfe2351ebe7`
se conserva sin modificar. Fuente de ejecución:
`fff8215f57fd51bc6ea471e0999a5c28e095c284`; plano
`9f8d29dabb4c5742d49a7db05a6f873b0e92b936b2b93c0c9c24bccb8ae29c64`.

Esta entrega completa el inventario de **210 observaciones /70 grupos**, añade
análisis pareado, repetibilidad, incertidumbre exploratoria, sensibilidad de
costes y seis figuras reproducibles. No ejecuta optimización, inferencia,
entrenamiento, consultas al scheduler ni nuevos jobs. No cambia parámetros,
preparación, MINIMIZE, decisiones científicas o recibos históricos.

La [carpeta de resultados](../evidence/pr86/final-210/) contiene fuentes,
tablas, manifiestos y figuras SVG/PDF/PNG. La integridad y la elegibilidad por
métrica son conceptos distintos. `scientific_reporting_eligible=false` se
conserva en los recibos: no se promociona todo el estudio en bloque.

## Muestra y diseño

Los diez padres fueron históricamente expuestos: seis fáciles
F0/F3/F6/F14/F27/F29 y cuatro medios M0/M4/M7/M12. Son el test6F+4M de la
cohorte admitida54 (30F+24M), no un nuevo conjunto independiente. La selección
histórica por calidad de etiqueta tampoco equivale a muestreo aleatorio.

- Matriz principal:10padres ×3métodos ×5límites1/2/4/8/16, seed42 =150.
- Repeticiones:10 ×3 ×2seeds43/44, **solo con un hilo** =60.
- Cada padre aporta21observaciones; cada método70. Métodos/seeds/hilos del
  mismo padre no son unidades independientes.
- M0: Gurobi sin inicio externo; M1: inicio LP emparejado; M2: inicio GNN.
  M1 depende del soporte/presupuesto positivo del inicio GNN: no es una
  línea base LP completamente independiente. No se fijan variables.
- Presupuesto por resolución:3.600s y MIPGap0,0001 = **0,01%**. Las diez
  llamadas de preparación de raíz del job3520 no forman parte de estas210.

Se acepta la formulación MILPBench según la decisión congelada del autor:
corregir MAXIMIZE a MINIMIZE, sin cambiar coeficientes, restricciones o dominios.
La sensibilidad numérica no reabre una exigencia de generador ni cambia esa
premisa. La identidad de modelos/variables y recursos sigue siendo verificable.

## Terminación y censura: denominadores distintos

| Ámbito | Observaciones | Objetivo informado alcanzado | Censura temporal |
|---|---:|---:|---:|
| Fuera deM4/M12 |168|127|41|
| M4 sensible |21|1|20|
| M12 sensible |21|7|14|
| Total |210|135|75|

Son **135 términos en el objetivo según el solver**, no135 certificados de
óptimo exacto. La incertidumbre de cualificación M4/M12 no se convierte en
censura administrativa ni en valores ausentes: todos los resultados quedan.

El endpoint temporal es el tiempo terminal de retorno del solver bajo la regla
de parada, no el primer instante exacto de cruzamiento. Los callbacks guardaron
primeros cruces *observados* de1/5/6/10%, distintos del objetivo terminal0,01%.
`solve_details.csv` conserva esos registros con unidades explícitas; un campo
vacío es no observado, nunca cero. No se interpola un cruce no registrado.

Las ejecuciones limitadas por tiempo llegan a3622,27s por la comprobación de
parada del solver. Por ello los gaps presentados son **terminales**, no medidas
uniformes al instante exacto3600s. No dividimos runtimes de timeouts para afirmar
speedup de resolución, ni estimamos un tiempo de resolución no observado.

## Efectos pareados en las seis fáciles

Todos los pares fáciles cumplen el objetivo informado, lo que permite comparar
sus tiempos terminales bajo el mismo protocolo. La tabla es seed42; menor que1
favorece al numerador. La razón geométrica es exp(media de log(Ta/Tb)), dando
el mismo peso a cada padre, no a cada variable del grafo.

| Hilos |M1/M0|M2/M0|M2/M1| M2/M0: intervalo exploratorio95% |
|---:|---:|---:|---:|---:|
|1|1,0094|1,1806|1,1696|[0,7664;1,9327]|
|2|0,9925|1,1643|1,1731|[0,7401;1,8927]|
|4|0,8096|0,7077|0,8741|[0,5567;0,9026]|
|8|1,0798|0,7056|0,6535|[0,5377;0,9912]|
|16|1,0469|0,8435|0,8057|[0,5426;1,3642]|

La orientación GNN es desfavorable en1/2hilos en este agregado y favorable en
4/8/16. Esto no demuestra superioridad general ni un óptimo de configuración.
Los intervalos M2/M1 abarcan1 en todos los límites; no debe omitirse ese control.
El escalado respecto al mismo método con un hilo es otra medida, T(1)/T(c),
publicada aparte; no equivale a M2/M0.

### Cómo se calculó la incertidumbre y qué significa

La elección de este estimador se documenta **después de observar los datos**:
es exploratoria, no un contraste confirmatorio preinscrito. Se enumeran las
6^6=46.656 remuestras ordenadas de seis padres completos con reemplazo. Las
comparaciones y sus seeds permanecen emparejadas dentro de cada padre. Se
aplican percentiles2,5/97,5 con cuantiles linealmente interpolados a las medias
logarítmicas, exponenciando los extremos. No hay aleatoriedad Monte Carlo.

Es un intervalo puntual bajo un modelo de padres intercambiables, no cobertura
de diseño para la población MILPBench ni un intervalo simultáneo para todos los
métodos/límites/costes. No se afirma significación a partir de que algún intervalo
no cruce1. Con seis padres expuestos su precisión y sus supuestos son limitados.
También se publican efectos individuales y sensibilidad leave-one-parent-out
(LOO): intervalo mínimo/máximo del agregado al retirar cada padre, no otro IC.
M2/M0 en1hilo/seed42 tiene LOO[0,9770;1,3656]; a16hilos,[0,6972;0,9733].

En1hilo se promedian primero los tres log-cocientes de seeds42/43/44 **dentro
de cada padre**, y luego los seis padres. M2/M0=**1,0912**, intervalo exploratorio
[0,8298;1,5454]; M2/M1=1,0618,[0,8137;1,4840]. La figura de puntos y la tabla
pareada preservan las variaciones de seed. No se remuestrean18padres ficticios,
ni se atribuye repetibilidad de seed a los límites2/4/8/16.

No se producen IC de speedup para los medios: hay censura y únicamente dos
padres fuera del estrato sensible. `paired_terminal_gap.csv` conserva diferencias
de gap en puntos porcentuales para cada padre/cap/seed y todos los comparadores;
no las convierte en un contraste poblacional ni en calidad al mismo horizonte.

## M4 y M12: cierre con limitaciones explícitas

Se mantienen las decisiones y las [auditorías anteriores](pr86-m12-audit-final-nine.md).
M4:cuatro vectores almacenados pasan las tolerancias originales, pero sus copias
con enteros redondeados fallan filas, incluida una con gap cero informado.
M12:cuatro vectores M2 auditados también pasan la copia diagnóstica; dos controles
M0/M1 fallan filas después del redondeo, aunque sus originales pasan las
tolerancias. **No son el mismo diagnóstico.**

Los tres nuevos vectores M2 no se han incluido en una nueva auditoría privada
de redondeo. Sus verificaciones flotantes registradas no equivalen a esa auditoría
ni a aritmética exacta. El screen M12 completo contiene14comparaciones: siete
límites frente a los mismos dos incumbentes, no14anomalías independientes.
M4 mantiene sus cuatro comparaciones históricas. No se demuestra la causa,
un defecto del solver, óptimo exacto o speedup certificado en esos dos padres.
No se reparan soluciones ni se cambian tolerancias para lograr aceptación.

## Costes: solver, tentativa y preparación no son lo mismo

Se conservan dos escenarios de preparación anteriores y se añade una sensibilidad
con el **reparto ampliado ya documentado** del overhead observado de preparación.
El reparto incluye setup/residual/exportación asignados por padre. Son escenarios
de contabilidad, no nuevas mediciones de trabajos fríos completos independientes.
La amortización entre siete usos es un supuesto explícito y no elimina la
preparación del gasto medido de campaña. M1 también paga la dependencia GNN.

En seis fáciles, seed42,16hilos, las razones M2/M0 son:

| Alcance |Razón|
|---|---:|
|Solo Runtime del solver|0,8435|
|Tentativa + preparación fría delimitada|1,0461|
|Tentativa + preparación fría con reparto ampliado|1,0692|
|Tentativa + preparación delimitada amortizada/7|0,8935|
|Tentativa + preparación ampliada amortizada/7|0,8969|

El beneficio observado en el solver puede desaparecer al contar la preparación.
No se suman asignaciones contrafactuales de los tres métodos como gasto de
preparación medido tres veces. Los componentes incluidos en otros tiempos
(por ejemplo forward dentro de inferencia) no se suman de nuevo.

Contabilidad de la campaña principal: suma Runtime=294253,252s (**81,74h**);
suma elapsed de los70jobs=301402s (**83,72h**); TotalCPU de esos70jobs contado
una vez por job=749533,491s (**208,20CPU-h lógicas contabilizadas**).
Son ámbitos diferentes, no núcleo-horas físicas intercambiables, no tiempo de
cola, y excluyen los jobs de preparación de raíz/GPU. Se preservan las filas
job/batch/extern en `scheduler_accounting.csv`, sin sumarlas duplicadamente.

La memoria del cgroup es máxima muestreada, distinta de MaxRSS y de memoriaGPU.
La duración de los métodos y sus estados terminales difieren: menor memoria
observada no demuestra ahorro causal bajo igual trabajo. La ausencia de
contención en el nodo compartido no fue certificada. AllocCPUS puede contabilizar
CPUs lógicas; no reemplaza el gate de afinidad física del executor.

## Figuras, trazabilidad y regeneración

| Figura |Pregunta y fuente|
|---|---|
|[Razones pareadas](../evidence/pr86/final-210/easy_paired_ratios.svg)|M1/M0,M2/M0,M2/M1; efectos individuales e intervalos puntuales; paired_uncertainty/paired_parent_effects.csv|
|[Escalado CPU](../evidence/pr86/final-210/easy_cpu_scaling.svg)|T1/Tc dentro de cada método; easy_cpu_scaling.csv|
|[Gap medios](../evidence/pr86/final-210/medium_terminal_gap.svg)|Cuatro padres separados; censura y sensibilidad; campaign_results.csv|
|[Memoria](../evidence/pr86/final-210/sampled_memory_cpu.svg)|Puntos por padre y medianas descriptivas; campaign_results.csv|
|[Sensibilidad de costes](../evidence/pr86/final-210/preparation_cost_sensitivity.svg)|Cinco alcances contables, tres comparadores; cost_scenarios/paired_uncertainty.csv|
|[Repetibilidad](../evidence/pr86/final-210/one_thread_repeatability.svg)|Tres seeds con un hilo; tiempo fácil y calidad media; campaign_results.csv|

Cada figura tiene SVG/PDF/PNG y un manifiesto de entradas/salidas. Renderizado
local Matplotlib3.9.2; no se instaló ni actualizó paquete HPC. Las seis páginas
PDF se renderizaron con Poppler y se inspeccionaron visualmente. El CI verifica
los hashes publicados y los cálculos; no se presenta como renderizado visual
en los cuatro entornos. El script de figuras es opcional para lectores que
quieran regenerarlas; el auditor numérico solo usa dependencias offline del CI.

Desde la raíz del repositorio, sin HPC:

```bash
python -B scripts/evidence/review_pr86_final.py
python -B scripts/evidence/plot_pr86_final.py
python -B -m unittest discover -s tests/evidence -p test_pr86_final.py -v
```

Los generadores aceptan archivos idénticos y rechazan sobreescribir distintos.
La revisión fija el retorno/plano/fuente históricos; no reconstruye sus hashes
de dependencias con el árbol analítico posterior. El manifiesto previo201,
la tabla de preparación y el retorno M12 previo se validan antes de usar sus
datos. Las210filas mantienen vínculos a recibo/child. El cierre analítico no
certifica todo por terminar jobs o por tener CI verde.

## Qué cierra esta PR y qué no

PR86 cierra la comparación CPU aprobada con todas las observaciones, estadística
exploratoria y limitaciones por métrica. No afirma superioridad general, test
independiente, óptimo exacto o coste frío completo certificado. No se requiere
otra campaña CPU para este cierre. Las correcciones pertenecen a la misma PR;
no se cambia ampliamente el CI ni se repiten experimentos.

Quedan **PR87:1GPU serial versus4GPU DDP**, con trabajo de aprendizaje comparable
y presupuesto exacto propio antes de ejecutar, y **PR88:manuscrito/revisión**.
Las frentes D/E de GPU y síntesis del artículo no están completas por este
cierre CPU. El manuscrito puede avanzar en paralelo. Sincronizar develop/main
solo después de la revisión del artículo y con aprobación separada. No se hace
merge en esta entrega; se solicita al autor únicamente cuando PR86 esté Ready
y el CI del HEAD final esté aprobado.
