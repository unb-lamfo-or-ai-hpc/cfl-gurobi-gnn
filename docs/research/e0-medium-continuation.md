# E0: continuación focalizada para M13/M26

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
