# D4 — Related Work Update dirigida

No es una nueva revisión bibliográfica. Se mantienen las tres subsecciones del
manuscrito. Las fuentes primarias indicadas por los investigadores se consultaron
para acotar el contraste, sin incorporar nuevas familias experimentales.

| Trabajo y fuente primaria | Objeto / interfaz relevante | Límite de nuestra afirmación |
|---|---|---|
|[Gasse2019](https://arxiv.org/abs/1906.01629)|Grafo bipartido y branching aprendido|Representación heredada, no originalidad del grafo|
|[Nair2020, Neural Diving](https://arxiv.org/html/2012.13349v3)|Asignaciones parciales y sub-MIPs|No equiparar solución de subproblemas con Start del modelo sin restringir|
|[Khalil,Morris,Lodi2022](https://doi.org/10.1609/aaai.v36i9.21262)|MIP-GNN orienta solver y ya incluye warm-starting|No reclamar primera integración GNN–MIP o primer warm start neural|
|[Han2023, ICLR](https://arxiv.org/html/2302.05636v2)|Búsqueda en región de confianza alrededor de predicciones|Una vecindad restringida no es nuestro Start nativo sin cambio de región|
|[Cantürk2024](https://doi.org/10.1613/jair.1.14972)|Incertidumbre, reducción iterativa de subproblemas y búsqueda guiada|Class-aware prioriza unos/ceros bajo soporte acotado; no modifica bounds ni demuestra una ventaja causal frente a su algoritmo|
|[Scavuzzo et al., survey](https://doi.org/10.1007/s10107-024-02130-y)|Síntesis de aprendizaje en componentes de branch-and-bound|Online2024, volumen217(2026); no confundir con el trabajo de predicción de objetivos ya citado como scavuzzo2024|
|[Qu2026](https://doi.org/10.1016/j.cor.2025.107290)|Restricciones aprendidas|Contraste ya seleccionado por el mandato; aquí no se añaden restricciones aprendidas|

La contribución pretendida es evaluar selección class-aware de binarias raras
mediante starts parciales nativos, su efecto empírico y sus costes. No son
comparaciones ejecutadas contra estos artículos; no se trasladan sus porcentajes
de mejora a CFL. Tampoco se demuestra causalidad del selector sin ablación.
El Related Work añadido es breve para preservar el presupuesto editorial.

Se añaden claves distintas `han2023` y `scavuzzo2026survey`. Se conservan las
referencias anteriores. El acceso local a Zotero no estaba disponible; no se
abrió/reinició la aplicación ni se atribuyó una verificación a su biblioteca.
