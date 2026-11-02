# Appendices to the article

The appendices accompany **Evaluating Graph Neural Network-Based Partial Warm Starts for Capacitated Facility Location Problems** as a **separate PDF**, with their own title, contents and references.

| Appendix | Content | Source |
| --- | --- | --- |
| A | Model, graph representation, learning and partial-start mechanisms | [Model and method details](gnn-methods-audit.md) |
| B | Earlier descriptive analyses, PCA, acquisition and predictor diagnostics, followed by the principal and historical optimization results | [Descriptive analyses and extended results](extended-results.md) |
| C | Inputs, hyperparameters, solver settings, determinism, gurobipy/Pyomo and SCIP/HiGHS context, environment and access | [Computational reproducibility](configuration-reference.md) |

The [document entry](index.qmd) assembles these three appendices. The article and appendices are distributed separately; no combined PDF is required.

The 39-instance development analysis, later 54-instance predictor, ten-instance CPU comparison and separate six-medium optimization study retain their own roles. The restored PCA uses stored structural descriptors, not learned GNN embeddings. Older PCA/UMAP illustrations remain linked with their provenance limitations.

Existing CPU/GPU claims are indexed in [claim-evidence.json](claim-evidence.json). The [historical appendix manifest](historical-appendix-manifest.json) identifies the nine frozen sources and six additional descriptive claim groups. Rendering their tables and stored projection coordinates does not rerun learning, inference or optimization.
