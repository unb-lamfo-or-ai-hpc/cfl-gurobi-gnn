# Deferred manuscript revision requirements

Status: approved requirements, retained for execution **after** the easy-only
training, paired solver experiment and evidence-consolidation sprints. This file
does not revise the manuscript or assert that those experiments have run.

## Audience, question and contribution

- Write entirely in academic scientific English for an external reader.
- Introduce CFL/MILP, the computational bottleneck, Learning to Optimize and the
  intended solver assistance before pipeline internals or numerical results.
- State one main research question: whether easy-trained GNN predictions improve
  Gurobi on unseen-in-fitting medium instances through partial MIP starts.
- Explain binary prediction targets and their mapping to model variables. Do
  not invent a textbook facility interpretation for unmapped benchmark columns.
- Distinguish intended contribution, implemented software, observed predictive
  results and measured optimization effects. No positive result is guaranteed.
- Describe the forced MINIMIZE convention, preserving original input sense and
  provenance. Do not silently change objectives or claim external corrections
  beyond the documented study convention.

## Structure and explanatory figure

Use problem/motivation/objective; related work; method and pipeline; experimental
design; results; discussion/limitations; conclusion/future work. Add a high-level
pipeline figure before implementation or detailed equations. Separate offline
collection/graph construction/training from online feature extraction/inference/
partial start/fresh solver/independent validation. Show outputs and data roles,
not PR numbers or private machine paths. Explain variants before referring to
them. Audit contracts and exhaustive artifact listings mostly belong in the
supplementary reproducibility documentation, not the main narrative.

## Literature and terminology

Develop substantive paragraphs on relevant L2O, GNN and primal-guidance studies
before explaining similarities and differences. Gasse et al. (2019), Exact
Combinatorial Optimization with Graph Convolutional Neural Networks, is required:
our binary-assignment task is not their strong-branching imitation experiment.
Differentiate Start, variable hints, bound fixing and local-branching restrictions.
Differentiate an incumbent solution, an original instance, a synthetic instance
and a serialized search-node subproblem. One incumbent does not automatically
create one independent training instance or one graph.

## Evidence and figures

Use reconciled Sprint C outputs: training/validation losses together; held-out
prediction metrics with prevalence and calibration; paired solver gap and time;
all four timing regions plus preprocessing/inference costs; target-gap censoring;
coverage, exclusions and failures. Preserve unfavourable results. A falling loss,
high ROC AUC, valid engineering gate or large target count is not proof of solver
acceleration. Keep parent-level and pooled metrics distinct.

Explain the historical39cohort and revised42admitted labels as different dated
evidence, not a retrospective rewrite of the old experiment. Do not treat newly
admitted test parents as training data. Selection based on label quality,
previously observed medium outcomes, one seed, limited family coverage and
unfinished hard experiments constrain generalisation. Record remaining runtime
and dataset objectives as unachieved when appropriate.

## Reproducibility and publication

- Retain the current Quarto/template workflow; do not build a new manuscript
  system. Target at most20main-text pages plus references, subject to the eventual
  journal's current author instructions.
- Preserve author order, names, emails and ORCID links using LaTeX orcidlink,
  not ORCIDs written out in prose.
- Add Department of Computer Science and Artificial Intelligence, University of
  Granada, Granada, Spain as an additional affiliation for Victor Alejandro
  Vargas-Perez and Oscar Cordon Garcia, alongside their DaSCI affiliation;
  preserve accents in final author metadata.
- Describe actual DGX-DaSCI resources used, solver/software versions, seeds,
  budgets, preprocessing costs and immutable artifact availability. Distinguish
  machine capacity from resources allocated to each experiment.
- Preserve the approved generative-AI disclosure immediately before References;
  verify factual tool/model names and author review before submission.
- Code licensing is MIT. Do not imply that this relicenses third-party MILPBench
  data. Zenodo dataset deposition needs provenance, redistribution-rights review,
  versioning and measured deposited contents; a draft is not a published dataset.
- Journal candidates remain European Journal of Operational Research,
  Computers & Operations Research, and Expert Systems with Applications. Select
  according to demonstrated contribution and evidence, not a predetermined claim
  of solver superiority. Recheck current scope and submission rules at selection.
- Retain the relevant cited references in the existing Zotero manuscript
  collection; check every citation against its source. Do not expose private
  meeting transcripts, annotated drafts or researcher emails in the public repo.

## Explicit future work

After the focused MVP: expansion to90originals with budget/resource studies;
independent synthetic-instance augmentation and matched SCIP comparisons;
replication across seeds/families; curated Zenodo intermediate/graph/embedding
data; and network-science methods for bipartite representation/visualisation
beyond PCA/UMAP. These are not parallel deliverables on the current critical path
and must not appear as completed experiments.
