# PR87 — operación de una pareja seed42, sin espera interactiva

Consultar primero el [protocolo final](pr87-matched-gpu-protocol.md).
Solo dos entrenamientos: serial1GPU y DDP4, seed42. El autor excluyó las demás
seeds. No hay optimización, nueva etiqueta, upgrade o cambio de hiperparámetros.
Techo24h secuenciales,60GPU-h y240núcleo-horas físicas reservadas.

El primer CI comprobó correctamente la equivalencia serial/DDP4 y detectó
una dependencia ausente del entorno de prueba: el import del paquete models
también importa Liang y requiere PyG. El job CPU de CI instala ahora
torch-geometric2.7.0, la versión existente en tfm_env. No modifica el entorno
HPC ni la arquitectura o el protocolo; el forward/backward Gasse real sigue
siendo obligatorio, sin sustituirlo por un mock o eliminar la comprobación.

## Inicio por el autor en dgx-dasci

El bloque de entrega del chat fija el SHA completo publicado después de pasar
los cuatro checks de evidencia y el check `matched-step` en ese mismo HEAD.
No sustituirlo por el HEAD móvil de la branch. El agente puede publicar y
comprobar CI, pero no inicia jobs ni hace merge por esta entrega.

1. Activar el `tfm_env` existente. No instalar paquetes.
2. `git fetch` de la branchPR87 en el repositorio existente y verificar el SHA
   exacto; no hacer pull/reset/checkout sobre el trabajo del usuario.
3. Crear un stage nuevo `/raid/vrcelestino/data/cfl-mvp2-evidence/pr87/training-SHA12`
   y un checkout `source` independiente con `git worktree add --detach`.
4. Ejecutar `prepare`: resolver y verificar bytes de los54grafos/raíces/etiquetas
   ya admitidos. No entrenar, cargar Gurobi ni crear un job de prueba.
5. Ejecutar una sola vez `submit` con el SHA256 del plan recién generado.
   Esa intervención registra el presupuesto ya aprobado y encola los dos jobs
   retenidos, verifica sus recursos y los libera con dependencia serial.

No escribir manualmente una frase de aprobación ni modificar JSON a mano.
`resource_budget_approved=false` del plan conserva su carácter de propuesta;
la autorización separada en `approval.json` queda ligada al hash del plan y
al mapa privado de entradas. La confirmación viene del contrato del autor y
de ejecutar explícitamente el comando, no de reescribir el plan.

`prepare` y `submit` no se repiten. Una reclamación de envío persiste incluso
si sbatch/SSH devuelve un error incierto. `submission-0.json` y similares
preservan los IDs; `status` puede leer envíos parciales. No crear un nuevo
stage para esquivar la reclamación. Tras fallo se diagnostica, no se reintenta.

## Consulta y recogida

Usar el mismo stage y source del bloque inicial:

```bash
bash "$PR87_STAGE/source/scripts/evidence/operate_pr87_training.sh" status "$PR87_STAGE"
```

Hace una sola consulta a sacct, sin bucle ni espera. Cuando ambos jobs sean
terminales:

```bash
bash "$PR87_STAGE/source/scripts/evidence/operate_pr87_training.sh" collect "$PR87_STAGE"
```

Se genera `public_return.json` con plan, autorización, estados y contabilidad,
resultados, memoria/telemetría y revisión de trabajo pareado. Si un entrenamiento
no terminó, el paquete sigue siendo evidencia incompleta y se preserva; no se
inventan epochs o métricas. El hash que se muestra es SHA256 de64caracteres,
no el commit Git de40caracteres. No repetir una recogida contra datos distintos
para sobreescribir el primer retorno. Una devolución ya idéntica puede leerse.

El receptor `scripts/evidence/receive_pr87_training.ps1` toma el commit y el
SHA256 de retorno: una sola conexión SCP, un solo archivo, destino nuevo.
No descarga console, stderr, checkpoints ni mapas privados. No solicita una
contraseña por cada archivo. La verificación local comprueba identidad del plan,
conteos, estado inicial, schedule, métricas y contabilidad; no equivale a aprobar
las conclusiones científicas o a cualificar el sistema por CI.

## Interpretación y cierre

Dos jobs completos y pareados dan una observación por configuración, no una
distribución de tiempos entre seeds. Reportar velocidades del lazo y job completo
por separado, eficienciaS/4, calidad por padre y macro/micro, costes y límites.
S<1 o degradación >0,02 son resultados, no autorización para repetir/tunear.
Memoria/recursos/contención e inicialización quedan documentados con su alcance.
Después de los retornos: revisión, figuras/tablas, checkpoint y Ready; merge
solo tras autorización específica. develop/main se sincronizan después del artículo.
