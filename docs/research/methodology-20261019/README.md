# Consolidación metodológica — PR88, 19 de octubre de 2026

Actualización20/10: PR87 completada y merged por autorización específica;
PR88 incorpora sus resultados y curvasBCE, **sin jobs, entrenamientos,
resoluciones nuevas ni mergePR88**. Esta revisión sustituye propuestas anteriores para el trabajo
futuro; no modifica contratos ni bytes de campañas terminadas.

| Entrega | Contenido |
|---|---|
| [D1](D1-protocol.md) | Protocolo y diccionario de métricas |
| [D2](D2-cpu-budget.md) | Paquete CPU separado, 60 jobs propuestos y gates |
| [D3](D3-figures.md) | Figuras/tablas principales seed42 e inventario histórico |
| [D4](D4-related-work.md) | Comparación bibliográfica dirigida, sin nueva revisión |
| [D5](D5-contributions.md) | Afirmaciones, evidencia, límites y trabajo pendiente |
| [D6](D6-decision-memo.md) | Memorando ejecutivo breve para decisión |

Los [productos derivados](../../evidence/methodology-20261019/) se regeneran sin
solver mediante `python scripts/evidence/build_pr88_methodology.py`; `--check`
verifica bytes y hashes. El CSV original de 210 filas permanece inalterado.
La unidad experimental es el padre, no cada fila de método/hilo/variable.

GPU: la [PR87](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/87)
ya integrada aporta la pareja3673/3674 y la [revisión acotada](../pr88-gpu-integration.md).
Trabajo igual no implica calidad preservada: informar pérdidaF1 junto al speedup.
CPU: el JSON y la matriz de D2 son propuestas, no instrucciones de envío.
Las dos autorizaciones son independientes; aprobar una no libera la otra.
