# Scientific and editorial revision

Target: **Computers & Operations Research**. The alternatives considered were
**European Journal of Operational Research** and **Expert Systems with Applications**.
Journal suitability is an editorial judgment, not an acceptance prediction.

The article addresses whether supervised bipartite GNN predictions produce
useful nonbinding partial MIP starts for medium CFL instances. It distinguishes
offline learning from online solver application, predictive evaluation from
optimization evaluation, and descriptive evidence from confirmatory inference.
It is written for external readers, without development-history narration.

## Organization

1. Problem, motivation, and a precise research question.
2. Parsimonious L2O, graph-learning, and primal-guidance positioning.
3. Mathematical model convention, graph features, supervised prediction,
   and class-aware partial-start construction; an offline/online diagram.
4. Parent-level splits, distinct populations, validation qualification,
   comparators, budget, information boundaries, and censoring.
5. Actual training/validation curves together, pooled and parent-macro
   predictive metrics, all solver-test outcomes, influence, and timing scope.
6. Regressions, negative pilot, uncertain labels, selection bias, and
   incomplete objectives; controlled follow-up experiments.
7. Reproducibility, availability, template rights, and the agreed AI declaration.

## Additional reference positioning

- Bengio, Lodi, and Prouvost (2021), DOI
  [10.1016/j.ejor.2020.07.063](https://doi.org/10.1016/j.ejor.2020.07.063):
  hybrid learning/optimization and distributional generalization.
- Qu, Dong, Wei, and Shang (2026), DOI
  [10.1016/j.cor.2025.107290](https://doi.org/10.1016/j.cor.2025.107290):
  autoencoder-derived restrictions, distinct from nonbinding starts.
- Goerigk and Kurtz (2025), DOI
  [10.1016/j.cor.2024.106886](https://doi.org/10.1016/j.cor.2024.106886):
  learned scenario initialization, not variable-value prediction.
- Zhang, Chen, Yang, and Zeng (2026), DOI
  [10.1016/j.eswa.2025.129924](https://doi.org/10.1016/j.eswa.2025.129924):
  structured cut selection, not supervised assignment prediction.

Metadata were checked against publisher/Crossref records; positioning uses
public abstracts and available author versions. No inaccessible full text
is claimed to have been reviewed. These citations are selected for relevance,
not merely journal membership. Gasse et al. (2019), arXiv version 3, remains
the required architectural reference; its branching task is not described
as our assignment-prediction experiment.

## Evidence boundary

Current sources comprise 13 immutable publication files, imported from the
author-supplied archive. The selected checkpoint is epoch 34, not epoch 100.
The 54-parent predictor has 34/10/10 graph partitions; optimization validation
and test each use six medium parents. Medium 9 and 20 lack admitted graph-test
labels, but retain their frozen optimization-test role. No descendant can
cross its parent's split. Millions of variable targets do not enlarge the
six-parent optimization sample.

The favorable median (-1.164 percentage points) is the primary descriptive
summary. Influence diagnostics accompany the mean, without replacing the
frozen cohort. Matched synthetic augmentation, hard generalization, additional
seeds, full 90-parent coverage, and network-science visualization remain
future work. Missing online-cost components remain unavailable in the
transferred publication evidence.
