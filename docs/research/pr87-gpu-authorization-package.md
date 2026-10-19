# PR87 — paquete GPU separado para autorización

Revisión19/10/2026 conforme D1–D6 dePR88. **Preparación aprobada; ejecución
pendiente de una nueva autorización específica.** Esta entrada sustituye la
liberación anterior del bloque CLI; no altera una campaña histórica ni cancela
jobs que el autor pudiera haber enviado por su cuenta. No se recibió aquí un
retorno de entrenamiento instaladoPR87 que permita afirmar que ya terminó.

## Presupuesto y trabajo

Solo seed42, un entrenamiento serial sinDDP en1V100 y otroDDP en4V100.
100épocas,34updates/época,136presentaciones/época,13.600presentaciones y
3.400updates por brazo. Batchglobal4, inicialización y buffers iguales,
normalización train-only, mismo sampler/orden/hash, Adam/lr/loss/clip y criterio
de selección. 54padres originales, roles34/10/10; test expuesto históricamente.
No reutilizar este nuevo modelo para atribuirle los solvesM2 ya terminados.

| Recurso | Serial1GPU | DDP4 | Techo pareja |
|---|---:|---:|---:|
| Entrenamientos/jobs |1|1|2 secuenciales|
| V10032GB |1|4|Nunca simultáneos entre jobs|
| Núcleos físicos |4|16|Afinidad disjunta por rank|
| RAMhost |128GiB|128GiB|No RAMGPU|
| Wall máximo |12h|12h|24h sin colas|
| ReservaGPU-h |12|48|60|
| Reserva núcleo-horas físicas |48|192|240|

Nodo único, batch, sin exclusivo/requeue/retry/resume/extensión. Stophost112GiB,
RAMkernel128GiB, fallo de observación uOOM detiene y preserva. Mantener
tfm_env sin actualización; duración/memoria del protocolo completo no probadas.
El segundo job valida artefactos del primero y depende deafterok. El orden
serial→DDP es fijo: caché/contención y aumentoCPU acompañante son limitaciones.

## Aceptación y métricas

Dos retornos completos con mismo estado inicial/schedule,100épocas y3.400updates;
evaluación rank0 sin colectivosDDP desiguales; prueba de gradientes CPU/Gloo
en CI no equivale a cualificación NCCL/V100. Registrar versiones reales, hashes
de seleccionados/terminales y calidadmacro/micro por padre/clase.

S=Tserial/TDDP4; E=S/4. Reportar lazo sincronizado, entrenamiento+validación+
checkpoint, proceso y job por separado; GPUs×ElapsedRaw/3600 sonGPU-h asignadas,
no tiempoGPU activo medido. GPU-h reservadas son techo, no consumo. TotalCPU
es contabilidad lógica, distinto de reserva física. RSS,cgroup,SlurmMaxRSS,
allocatorGPU y nvidia-smi son alcances diferentes. Muestras ausentes no son0.
No atribuir energía ni comunicación a una descomposición no instrumentada.

F1 yPR-AUC macroDDP−serial, margen descriptivo absoluto0,02; no es test de
no-inferioridad. S<1 o pérdida de calidad son resultados aceptables, no motivo
de tuning/repetición. Una pareja no estima robustez entre inicializaciones.
No se exige igualdad bitabit de trayectorias entrenadas.

## Frontera de autorización

Plan y configuración mantienen `resource_budget_approved=false`. Submit requiere
un recibo GPU nuevo, separado, vinculado aplan/source/bindings/budget y al
registro de aprobación del investigador; un SHA de plan por sí solo ya no basta.
El paqueteCPU dePR88 no puede autorizar este operador. No se crea aquí ningún
recibo real con aprobacióntrue. El recibo registra decisión humana, no demuestra
identidad mediante firma criptográfica. Validarlo antes del envío, en el launch
asignado y en la revisión independiente protege fronteras distintas.

Después de autorización específica y CI final: entregar un único bloque CLI
fijado al commit. Sin frases largas, sin repetirprepare/submit y sin comandos
de ejecución liberados por esta revisión. La aprobación deGPU no liberaCPU.
