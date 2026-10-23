# PR86 final210 — índice de evidencias

Fecha:19/10/2026. [Revisión científica y método](../../../research/pr86-final-analysis.md).

- `public_return.json`: última onda original, SHA256 a3a219799291d2471a9329eda922aca2ac34b29a2dfa77dd63ec1dfe2351ebe7; tres grupos/nueve solves.
- `campaign_results.csv`:210filas acumuladas, conservando las201anteriores.
- `scope_and_censoring.csv`:168 observaciones fuera deM4/M12,21M4 y21M12;135 términos en objetivo informados,75censuras.
- `parent_method_quality.csv`: calidad terminal y recursos, siete escenarios distintos por padre/método; no siete réplicas idénticas.
- `paired_terminal_gap.csv`:210contrastes pareados en puntos porcentuales; diferencia terminal, no al horizonte exacto3600s.
- `paired_parent_effects.csv`:450efectos individuales de las seis fáciles, seed42, tres comparadores y cinco alcances de coste.
- `paired_uncertainty.csv`:90resúmenes; bootstrap de seis padres completos y LOO. Puntuales/exploratorios, sin cobertura de población ni corrección de multiplicidad.
- `paired_seed_repeatability.csv`:90efectos por padre/comparador/coste, tres seeds anidadas solo con un hilo.
- `easy_cpu_scaling.csv`:90puntos T1/Tc y eficiencia relativa, cada método con su propia referencia.
- `cost_scenarios.csv`:210filas con escenarios delimitados y reparto ampliado de preparación; no mediciones independientes de trabajo frío completo.
- `solve_details.csv`:210identidades, versiones, parámetros, nodos y tiempos de primer evento observado. Cruces callback1/5/6/10% distintos del objetivo terminal0,01%.
- `scheduler_accounting.csv`: registros de los70jobs y sus pasos; no sumar job+batch+extern como consumo independiente. Campos ausentes no son cero.
- `m12_cross_run_screen.json`:14comparaciones de7bounds frente a2incumbentes; no14errores independientes ni causa probada.
- `review.json`: elegibilidad analítica por métrica; conserva false en promoción científica global, certificado M4/M12 y coste frío completo.
- `manifest.json`: hashes de entradas y de tablas derivadas.
- `figure_manifest.json`: hashes de entradas y18assets de seis figuras, Matplotlib3.9.2.
- `claim_evidence.csv`: afirmaciones, fuentes y límites para el manuscrito.
- `publication_manifest.json`: hashes de todo el paquete y fuentes de los generadores/pruebas, sin incluirse a sí mismo.

Cada figura se publica enSVG/PDF/PNG: razones pareadas, escaladoCPU, gapsmedios,
RAMmuestreada, sensibilidaddecostes y repetibilidaden1hilo. Los archivos
originales anteriores no se reescriben ni cambian sus flags. Resultados
negativos/censurados/sensibles se mantienen; no se añadieron jobs ni solves.

La muestra es expuesta y no aleatoria. Seis padres fáciles, no126réplicas
independientes; cuatro medios, conM4/M12 separados. Los dos medios restantes
no permiten una inferencia poblacional robusta. Aceptación de inicio no es
beneficio; gapcero flotante no es certificado exacto. Pendiente obligatorio
del MVP2: comparación1GPU/DDP4 y manuscrito. Esta carpeta no los da por hechos.
