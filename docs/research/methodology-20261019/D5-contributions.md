# D5 — Manuscript Contribution Matrix

| Dimensión / afirmación permitida | Evidencia verificable | Estado y limitación | Evidencia pendiente |
|---|---|---|---|
|Pipeline CFL con minimización y procedencia preservada|PR85, `docs/evidence/e0/pr85/`, PR80 auditoría54/54|Observado/auditado bajo tolerancias; la decisión del sentido es explícita|Identidad de artefactos antes de cada campaña, no otra certificación del generador|
|Selector class-aware para Start parcial nativo|Código E0/PR86, manifiestos raíz/inferencia/start|Implementado; mecanismo, no prueba de superioridad causal|No se exige nueva ablación enMVP2; declarar límite|
|Efectos computacionales heterogéneos con seed42|`docs/evidence/methodology-20261019/seed42_main.csv`, hash fuente enmanifest|150filas/10padres expuestos,97target reportado,53censuras; M4/M12 sensibles|No generalización externa o robustez multiseed|
|Speedup neural para pares comparables|`seed42_paired_speedups.csv` con elegibilidad|Descriptivo, T0/T2 oT1/T2; no speedup de timeouts ni óptimo exacto|Más horizonte para cuatro medios, presupuestoCPU pendiente|
|EscalabilidadCPU y recursos|`seed42_cpu_scaling.csv`, contabilidad PR86 porjob, cgroup muestreado|Unidades y frentes diferentes; no sumar memorias ni confundir core físico/SMT|Figuras finales de utilización con cobertura explícita|
|Costes de aplicación y amortización|`seed42_cost_scenarios.csv`, preparación3520/3521 y boundaries PR86|Escenarios acotados, no end-to-end independiente; M1 depende deM2|Ninguna medición ausente se llena con0; tiempos adicionales solo si se instrumentan|
|Efecto de ampliar horizonte a12h|D2, matriz60 y límites|Hipótesis y propuesta no ejecutada; no promesa de convergencia|AutorizaciónCPU, gates, adaptador prospectivo y resultados|
|Escalabilidad1GPU/DDP4 preservando trabajo|PR87 jobs3673/3674, recibo909f6ce85dfd, sieteCSV y manifiestos; figuraBCE PR88|Trabajo registrado igual; lazo2,167x, job1,831x;GPU-h0,5614→1,2267;F1macro−0,032468, sin calidad preservada|Interpretación y revisión de coautores; no otro entrenamiento ni nueva seed|
|Contribución pertinente aC&OR|Mecanismo+comparación controlada+coste reproducible|Argumento de encaje, no garantía editorial; resultados negativos son válidos|Redacción, revisión por coautores y materiales reproducibles|

Los resultados históricos de seis medios y las60filas43/44 permanecen
disponibles como antecedentes. No reemplazar las evidencias actuales por una
historia de mejora uniforme. Toda cifra del artículo debe enlazar su tabla,
manifest, scope de elegibilidad y población. La matriz es un registro de
afirmaciones, no una promoción global automática de todos los resultados.
