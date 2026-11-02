# D2 — Extended HPC Budget: paquete CPU independiente

Actualización20/10 tras PR88 merged: el autor aprobó explícitamente el paquete
CPU completo, sujeto a preflight y CI del HEAD exacto. [Decisión registrada](../../evidence/pr89/cpu_author_decision.json)
y [operador prospectivo](../pr89-cpu12h.md). No hay jobs ni resultados nuevos.
El JSON/CSV propuestos abajo conservan sus bytes/flagsfalse: no eran autorización
runtime. Los ocho gates siguen comprobándose en las fronteras correspondientes.
Las referencias siguientes a «no autorizado» describen la propuesta original.

**Propuesta, ejecución no autorizada.** No se entrega un comando sbatch.
El [JSON de autorización propuesto](../../evidence/methodology-20261019/cpu_authorization_package.json)
y la [matriz completa](../../evidence/methodology-20261019/cpu_60_jobs_proposed.csv)
son la referencia verificable. No contienen aprobación ni IDs de jobs.

## Matriz y límites

Cuatro padres expuestosM0/M4/M7/M12 × cinco caps1/2/4/8/16 × tres métodos
M0/M1/M2 =60 resoluciones frescas seed42. AliasM0 de instancia y métodoM0 son
campos distintos. Un solve por job, 60 jobs, máximo uno activo, orden de métodos
rotado predeterminadamente en cada bloque padre/cap. Ningún padre fácil repetido.

| Concepto | Techo solicitado propuesto | Naturaleza |
|---|---:|---|
| TimeLimit por optimize |43.200s (12h)|No duración pronosticada|
| Solver total |720h|60×12|
| Horas-cap físicas de solver |4.464|4×3×(1+2+4+8+16)×12|
| Wall por job |46.800s (13h)|1h de margen para carga/exportación/auditoría|
| Reserva serial total |780h (32,5d)|No incluye espera en cola|
| Reserva núcleo-horas físicas |4.836|4×3×31×13|
| RAM por job |64GiB|No sumar como RAM simultánea|
| GPUs |0|CPU únicamente|

Nodo único dgx-dasci, batch, nodes=1-1,ntasks=1,un lógico por núcleo físico.
Sin exclusivo, requeue, retry, resume, ampliaciones automáticas o cambios de
tfm_env. MIPGap1e-4=0,01%; MINIMIZE obligatorio. Mantener seeds/checkpoints,
starts, parámetros restantes y log/result binding; no juntar tiempo1h+12h
como si fuera una ejecución continua. Los costes antiguos de preparación se
atribuyen según escenarios de reutilización, no como nuevas mediciones.

Memoria: SoftMemLimit48GB decimales; parada de supervisor56GiB; RAM kernel≤64GiB.
La pérdida de observabilidad, incumplimiento de afinidad/identidad o límite de
memoria detiene el hijo y bloquea la cadena. Watchdog del hijo debe dejar margen
real dentro de13h, sin truncar automáticamente los12h de optimize prometidos.
OOM/timeout/fallo produce evidencia parcial: no repetir. La cadena debe comprobar
recibos del predecesor además de dependencia Slurm. Un límite numérico ya
declarado no es fallo operativo ni autorización de tuning.

## Ocho gates previos al envío

1. Partición: consultar wall máximo y permisos vigentes; el inventario de6/10
   no demuestra configuración actual ni que13h sea admitido.
2. CPU: comprobar16 núcleos físicos distintos y afinidad real; AllocCPUS32 puede
   contabilizar SMT, no cambia el cap físico.
3. Memoria: jerarquía job y límites efectivos; guards y stop/exportación probados
   offline. La lectura antigua no certifica una futura asignación.
4. M4/M12: conservar sensibilidad de tolerancias; definir elegibilidad por métrica.
   Más tiempo no corrige redondeo ni certifica óptimo exacto.
5. Integridad: hashes LP/raíces/grafos/checkpoints/starts y alineación de columnas.
   Reutilizar preparación admitida, sin nuevas inferencias implícitas.
6. Presupuesto: aprobación específica de60jobs,720hsolver,780hreserva y4.836core-h.
7. Calendario:32,5d máximos secuenciales más filas amenazan15/11 y SprintE.
   El techo conservador no es una predicción ni justifica prometer el milestone.
8. Ambiente/permisos: tfm_env existente, licencia válida y recursos compartidos;
   no actualizar paquetes. Los datos privados y licencia quedan fuera de Git.

Los gates están pendientes, no se fabrican como true con CI. La aprobación del
presupuesto por sí sola no salta un gate ni libera un operador aún no cualificado.
El adaptador de cruces/horizontes será prospectivo; se conserva el histórico.

## Decisión y cronograma

No iniciar simultáneamente CPU y GPU bajo una autorización ambigua. Se pueden
aprobar por separado y ordenar según recursos reales. Si el calendario no
admite este techo, presentar prospectivamente otra matriz/budget para decisión,
antes de ver nuevos resultados. No elegir solo instancias favorables, subir
concurrencia o eliminar métodos silenciosamente. No prometer reducir censura:
esa es la hipótesis que la campaña intenta evaluar.
