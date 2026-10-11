# E0: cierre documental de M13/M26

Actualizado: 2026-10-10. Alcance final de PR83: inventario e inspección de
artefactos existentes, **sin nuevos experimentos**. Este cierre sustituye la
continuación de inferencia y resolución propuesta anteriormente. Las secciones
históricas al final se conservan para trazabilidad y **no son instrucciones
vigentes de ejecución**.

## Resultado final de la inspección instalada

La [inspección instalada](../evidence/e0/medium-inspection.json), SHA256
`11ce18870f44759afc51cfa12b4f26a684fdf246ef6e720b42d7340a49546af0`, fue
ejecutada con el código `2b94cae424e9854102241d55064a772e2c40c584`.
Verificó los diez hashes fijados por el
[inventario](../evidence/e0/medium-inventory.json), SHA256
`9e73c05c776b12dc2b8132c8904cc462b9ce90735e4ebea74101d15537ad08b9`.
Clasificó ocho perfiles, cuatro por padre, sin fallos registrados, y encontró
**cero candidatos de raíz autoconsistentes**. Leyó 71 131 815 bytes y decodificó
28 560 750 bytes, sin repetir la exploración del dataset.

En cada padre se identificó un índice con 1 281 600 nombres de variables y
un hash del MILP candidato coincidente con el original inventariado. Un índice
de nombres **no es** un vector de solución de la relajación raíz. Los informes
históricos declaran `TimeLimit=28800`, `Seed=42`, `Threads=1`,
`NodeLimit=1000000`, `solution_count=10` y `gate_status=inconclusive`.
Registran 28 800,598922 s para M13 y 28 800,126546 s para M26. Son metadatos
históricos, no nuevas resoluciones ni diez etiquetas o incumbentes validados
por esta inspección.

## Qué, cómo y por qué termina aquí

Se inspeccionaron los ocho JSON fijados y los vecinos conocidos descritos en
el registro histórico siguiente. No se deserializaron grafos ni se usaron
etiquetas para seleccionar inicios. No se identificó en este alcance una
captura de raíz autoconsistente que permita vincular características, orden
de variables y preparación reutilizable. Los indicadores de raíz falsos en
un índice sin esos campos no prueban inviabilidad matemática ni un error de
la relajación. Tampoco se prueba ausencia universal de artefactos
(`absence_proven=false`). `declared_parent_matches=null` significa identidad
declarada no establecida, no una discrepancia demostrada. La lista vacía de
cachés opacas tampoco demuestra su inexistencia fuera del alcance inspeccionado.

La decisión aprobada es documentar la cobertura no cualificada y continuar
con las evidencias disponibles, sin recalcular raíces, inferir, entrenar,
resolver ni ampliar búsquedas para M13/M26. No se requiere una resolución
exitosa de ambos padres para cerrar este alcance documental.

M13/M26 tienen rol canónico `train`, pero quedaron fuera de los 54 padres
admitidos. No se añaden retroactivamente al entrenamiento ni al test. Fueron
expuestos históricamente: no constituyen un test independiente nuevo. Las
declaraciones históricas `maximize` y `minimize` no prueban equivalencia
matemática: PR85 deberá comprobar formulación y transformación del objetivo.
Los costes ausentes siguen ausentes, no se sustituyen por cero.

## Validación y checkpoint de cierre

El recibo importado conserva sus bytes originales. Se comprueban SHA256,
identidad del inventario fuente, diez hashes verificados, ocho perfiles,
cero candidatos de raíz y todos los contadores de nuevas operaciones a cero.
Se conservan colectores, tests, recibos e historia experimental. No se admite
inferencia ni solver y `scientific_reporting_eligible=false` permanece intacto.

No se añade ninguna optimización, inferencia, entrenamiento, consulta Slurm
o job. No hay CLI pendiente ni retry. PR83 y PR84 se mantienen independientes,
sin merge autorizado. El contrato general se consolida en PR84; PR85 requiere
aprobación de alcance antes de implementación. La sincronización de `main`
es una decisión de publicación separada.

## Registro histórico — propuestas retiradas, no ejecutar

Lo siguiente documenta el estado anterior a recibir la inspección y a aprobar
el cierre del 10/10/2026. Sus tareas pendientes, condición de merge y CLI
quedan sustituidas por el cierre anterior.

## Estado actual: inventario instalado revisado

El retorno [`medium-inventory.json`](../evidence/e0/medium-inventory.json), SHA256
`9e73c05c776b12dc2b8132c8904cc462b9ce90735e4ebea74101d15537ad08b9`, coincide
con los bytes descargados. Colector `0f60a0776bb1`, siete pruebas instaladas
aprobadas, 9391 entradas observadas, 65 302 364 bytes leídos, sin advertencias,
sin solver, inferencia, entrenamiento o consultas al planificador.

| Padre | Original LP | JSON candidatos | Estado semántico |
| --- | ---: | ---: | --- |
| M13 | 29 742 026 bytes | 4 | Pendiente de inspección del contenido |
| M26 | 29 730 887 bytes | 4 | Pendiente de inspección del contenido |

Son diez **archivos candidatos**, no diez ejecuciones, grafos o soluciones
válidas. Los ocho JSON suman 5 829 451 bytes. El inventario prueba lectura y
hashes dentro de su alcance, no compatibilidad para inferencia ni inexistencia
de otros artefactos.

Se identificó una limitación del filtro anterior: al excluir nombres con
`label`, también omite `label_free_graph.pt`. Por ello no se deduce que falten
grafos a partir de esa lista. Se conserva el colector histórico y su recibo;
la continuación inspecciona explícitamente ese nombre, `root_features.json.gz`,
`predictions.json.gz` y `preparation.json` en las carpetas de los ocho JSON.
No se repite la exploración completa del dataset.

`inspect_e0_medium_artifacts.py` verifica los diez hashes y el índice privado,
lee los ocho JSON fijados y los vecinos conocidos presentes, y genera dos
salidas: perfiles públicos saneados y un índice privado para la preparación.
Solo salen escalares permitidos, hashes, cantidades y resultados booleanos;
no nombres de variables, etiquetas, asignaciones, rutas ni textos libres.
Los grafos se identifican por bytes sin deserialización. Si un JSON contiene
resultados históricos, se inspecciona su estructura, pero sus valores de
etiqueta no se usan para seleccionar inicios ni entrenar modelos.

Para una raíz existente se verifican origen MILP, método MIPNODE, minimización,
nodo cero, longitudes, valores finitos y hashes de nombres/vector. Esto establece
un **candidato autoconsistente**, no sustituye la comparación del orden de
variables con el modelo ni admite inferencia. No se recalcula una raíz ausente.
Los costes históricos desconocidos continúan ausentes, no se convierten en cero.

Límites de esta continuación: 64 artefactos, 256 MiB leídos, JSON comprimido
de hasta 8 MiB, 64 MiB descomprimidos por JSON y 128 MiB acumulados; 180 segundos
comprobados entre operaciones de E/S. Fallos de formato se conservan como
resultado parcial. Cambios en bytes fijados detienen la inspección antes de
producir un resultado nuevo. No hay retry, consulta Slurm ni nueva optimización.

La siguiente CLI usa un snapshot nuevo pero el **mismo inventario instalado**.
No vuelva a ejecutar el colector del bloque histórico al final de esta página.
Después del retorno se decide la preparación mínima reutilizable; no se cambia
el checkpoint, la normalización ni el umbral por resultados de M13/M26.

## Qué, cómo y por qué

PR82 está integrada en `develop` mediante `91630762bf0b86ec153e2882c42dc83161eebe4a`.
El [bloque de seis fáciles](e0-job3506-review.md) está concluido: 18 resoluciones,
tablas y figuras, sin mejora uniforme de los inicios. No se repite job3506.

M13/M26 son los dos padres medios pendientes de la cobertura E0 original.
Su rol canónico es `train`, pero no fueron admitidos entre los 54 padres del
aprendizaje. Fueron expuestos históricamente: no son un test intacto nuevo.
No cambia la partición 34/10/10 ni se amplía retroactivamente el entrenamiento.

La primera operación de esta entrega lee los bytes de sus dos MILP originales
y busca archivos existentes que nombren exactamente estos padres en los grupos
`analysis`, `models`, `bipartite_graphs` e `intermediate`. Reutiliza el lector
acotado de PR80. No importa Torch ni Gurobi, no deserializa grafos, no lee
etiquetas para preparar inicios, no consulta Slurm y no presenta un job.
Los nombres solo clasifican candidatos, nunca prueban su validez matemática.

Se producen `inventory.json` público (identificadores opacos, tamaños, hashes,
límites y estado) y `private_paths.json` que **permanece en el HPC** para enlazar
los candidatos durante la preparación posterior. No se transfieren contenidos,
rutas, predicciones, soluciones ni logs. Solo se descarga el primer archivo.

Límites: 20 000 entradas, 64 candidatos, 4 GiB leídos y 180 segundos comprobados
entre operaciones de E/S. No es un timeout duro ante E/S bloqueada. Los enlaces
simbólicos no se siguen. Un límite o error produce un recibo parcial, sin retry.
La búsqueda es por nombres y grupos conocidos: ausencia de candidato no prueba
inexistencia universal. Hash correcto tampoco acredita semántica compatible.

## Continuación dentro de esta misma entrega

1. Revisar el inventario y vincular originales, raíz, representación y modelo
   congelado; aprovechar todo artefacto compatible existente.
2. Preparar características/inferencia sin usar etiquetas de M13/M26 y sin
   volver a ajustar normalización, umbral ni checkpoint. Si falta la raíz,
   explicitar y medir ese coste antes de su cálculo, no esconderlo como cero.
3. Publicar el manifiesto mínimo de los tres métodos, controles emparejados,
   presupuesto y operador no bloqueante antes de cualquier resolución.
4. Revisar retornos y añadir tablas/figuras, manteniendo este estrato separado
   de los fáciles y del test predictivo. Cerrar la cobertura E0 o documentar
   concretamente una limitación; no convertir cada helper en otra PR.

Esta PR no está lista para merge por tener un inventario únicamente. No admite
todavía solver, entrenamiento, nuevas relajaciones ni inferencia. El contrato
C2/C3, D, E1/E2 (1/2/4/8/16 hilos) y F sigue vigente. La sincronización de `main`
queda reservada al final de Sprint C.

## CLI después de instalar el snapshot publicado

```bash
conda activate tfm_env
python3 -B "$E0_MEDIUM_STAGE/source/scripts/evidence/inventory_e0_medium.py" collect \
  --data-root /raid/vrcelestino/data/cfl-gurobi-gnn/data \
  --output "$E0_MEDIUM_STAGE/run"
```

El bloque de instalación entregado en el chat fija el commit exacto y crea un
directorio nuevo bajo `/raid/vrcelestino/data/cfl-mvp2-evidence/e0`.
Si hay recibo parcial, conservarlo y devolverlo; no repetir la colección.
La descarga PowerShell usa una única conexión SCP y verifica SHA256 y alcance.
