# PR87 — jobs3671/3672: fallo de entrada y recibo incompleto

20/10/2026. No nuevo job, retry, entrenamiento o merge autorizado por esta revisión.

## Hechos observados

El autor envió la pareja aprobada:3671FAILED(1:0,ElapsedRaw0,TotalCPU0,005s),
3672CANCELLED por la cadena dependiente. El recibo descargado tiene el SHA256
esperado `e65676eb6f84fe515de766f11b467ba5a2b2ba25715425bf813b1f4eea7cf033`.
Se conserva byte a byte en `docs/evidence/pr87/job3671/public_return.json`.
Plan/source/autorización/hashbindings/orçamento y contabilidad son coherentes.
Los dos resultados y los dos informes del supervisor están ausentes (`null`).
La transferencia no falló; la excepción local apareció después de comprobar
el hash, cuando el revisor intentó acceder a `value["state"]` con value=None.
No es evidencia de un fallo PyTorch, CUDA, NCCL o memoria.

## Defecto identificado y corrección

El wrapper calculaba SOURCE desde `${BASH_SOURCE[0]}` para todos los modos.
En ejecución por sbatch, Slurm ejecuta una copia del script en su spool;
su directorio deja de ser `source/scripts/evidence`. Por tanto el cálculo
de SOURCE y el `test SOURCE=STAGE/source` no localizan el checkout y pueden
terminar antes de invocar Python. El lanzador no tenía prueba de esta frontera:
`bash -n` valida sintaxis, no el cambio de ubicación realizado por Slurm.
Referencias primarias: [sbatch](https://slurm.schedmd.com/sbatch.html) y
[SlurmdSpoolDir](https://slurm.schedmd.com/slurm.conf.html#OPT_SlurmdSpoolDir).

Corrección mínima: solo `batch` toma SOURCE del stage que se grabó al enviar;
los modos interactivos mantienen la comprobación de ubicación del checkout.
Python conserva checks de host, sourcecommit, plan, autorización, bindings,
asignación/afinidad y guards antes del entrenamiento. No se modifica arquitectura,
datos,100épocas,seed42,batchglobal4,umbral,optimizer,memoria o presupuesto.
Se añaden códigos sanitizados de entrada y un marcador de despacho a Python.

La prueba Linux ejecuta una copia real del wrapper en una carpeta de spool
simulada con hostname/python3 controlados, sin scheduler, GPU o entrenamiento;
verifica que despacha al stage, y que un stage inválido no llega a Python.
La prueba se omite en Windows, no se sustituye por afirmar que Bash local corrió.

El defecto del source está demostrado en el código. Su atribución exacta al
job3671 queda pendiente de lectura privada de los artefactos; no se transforma
una reproducción sintética en trazabilidad histórica. Los informes ausentes
no prueban por sí solos el número exacto de instrucciones o updates ejecutados.

## Recepción y revisión

`validate_result(None)` ahora produce un error de dominio, no TypeError.
`inspect` verifica hash/envelope/plan/autorización y estados terminales antes
de clasificar una pareja fallida como evidencia íntegra pero incompleta.
El receptor usa inspect y no anuncia "matched work OK" cuando faltan resultados.
`review` sigue exigiendo dos entrenamientos completos y trabajo equivalente;
no se debilita la aceptación científica para evitar la excepción de transporte.

El retorno original y sus flags no se reescriben. La revisión derivada declara
`ready_for_independent_review=false`, `retry_authorized=false` y ningún nuevo
job/entrenamiento/solve. Los60solvesCPU dePR88 siguen sin autorización.

## Próximo paso

Diagnóstico privado exclusivamente en lectura: fingerprints/indicadores
allowlisted de stdout/stderr, presencia de artefactos y copia batch si Slurm
aún la conserva; no exportar texto privado ni lanzar batch/train. Conservar
claim, planes, autorizaciones eIDs antiguos. No usar la CLI anterior o crear
otro stage para eludir el stop. Cualquier reenvío de la pareja requiere una
decisión explícita aparte, con los consumos/IDs anteriores reconciliados.
