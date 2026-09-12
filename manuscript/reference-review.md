# Reference selection and Zotero collection

Review date: 12 September 2026. The user supplied 41 bibliography entries exported
from Zotero. Selection below is based on relevance to the actual study, supplied
metadata, and public primary publication/author pages for cited works. This was
not a systematic search or an exhaustive full-text appraisal. No Zotero attachment
or private full text was retrieved.

The Zotero skill status helper encountered a profile-access error, but subsequent
read-only searches and selected BibTeX exports succeeded. `references.bib`
contains the eight works actually cited, with publisher/arXiv metadata taking
precedence over incomplete local exports. It is not an unmodified library export.
At the initial review no library record was changed. The subsequent authorized
collection update is recorded below. Citation keys in that file are manuscript-local
and must not be mistaken for Zotero item keys.
Accented names use TeX escapes in BibTeX so the template's classic BibTeX engine
does not split UTF-8 characters when abbreviating initials. The rendered names
retain their diacritics in both formats.

| Manuscript key | Existing Zotero item key | Reconciliation |
|:--|:--|:--|
| gasse2019 | QQCGJX5N | Imported after DOI/title search; mandatory arXiv v3 URL and complete five-author list |
| cappart2021 | VJW42H7B | Imported after DOI/title search; IJCAI DOI, pages and complete six-author list |
| ding2020 | JDRQIY4P | Matched title/authors/year; publisher supplies pages |
| khalil2022 | BUGJ8ZVY | Matched DOI; publisher supplies complete journal metadata |
| canturk2024 | FZ979RLZ | Matched title/authors/year |
| fischetti2003 | CE68X9VZ | Matched DOI; local conference-paper type differs from publisher journal record |
| nair2020 | CP86X653 | Matched arXiv v3; local export has only three authors; full authorship and first-submission/revision dates restored from arXiv in manuscript only |
| gurobi2026 | 7R3T72H3 | Existing reference manual reused; manuscript cites the specific variable-attribute documentation section |

Gasse and Cappart were not returned by targeted DOI/title/author searches in
My Library before import. This is not a claim about every group library.

## Cited subset

| Key | Source and verification | Role in the article |
|:--|:--|:--|
| gasse2019 | [arXiv v3](https://arxiv.org/abs/1906.01629v3), authors, title, DOI and version checked | Mandatory architectural reference; learning-to-branch is distinguished from assignment prediction |
| cappart2021 | [IJCAI](https://www.ijcai.org/proceedings/2021/595), publisher metadata and abstract | GNN/optimization context |
| ding2020 | [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/5503), publisher metadata and abstract | Solution prediction and local branching |
| khalil2022 | [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/21262), publisher metadata and abstract | Variable biases and solver guidance |
| canturk2024 | [Authors' repository](https://github.com/furkancanturk/gnn4co), title, authors, journal, pages and DOI | Closely related GNN-based primal-heuristic study; no performance numbers imported |
| fischetti2003 | [Springer](https://link.springer.com/article/10.1007/s10107-003-0395-5), publisher metadata and abstract | Added foundational source for local branching |
| nair2020 | [arXiv v3](https://arxiv.org/abs/2012.13349v3), metadata and abstract | Added source distinguishing Neural Diving from nonbinding hints; first-submission year retained with revision date |
| gurobi2026 | [Official variable attributes](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html) | Added software documentation for hints versus starts; access date recorded, no invented DOI |

Gasse, Cappart, Ding, Khalil and Canturk are from the supplied list. Fischetti,
Nair and the official Gurobi documentation are targeted additions needed to
support the actual operator and intervention semantics. We do not import those
papers' speedups or generalization claims as results of this project.

## Remaining supplied entries

All entries below remain uncited in this first focused draft, not rejected as
scientifically unsound. Reconsider them only when a specific claim needs them.

| Supplied entry | Reason for deferral |
|:--|:--|
| Cai et al. (2025), neuro-symbolic motion planning | Different application and constraint setting |
| Cardillo et al. (2025), MILP-SAT-GNN | SAT prediction is outside the experiment |
| Chen, T. et al. (2022), learning-to-optimize primer | Broad background already covered by the focused survey |
| Chen, X. et al. (2024), branching capacity | Branching expressivity is not tested here |
| Chen, X., Liu and Yin (2024), tutorial | Incomplete publication metadata and overlapping background |
| Chen, Z. et al. (2024), quadratic programs | Quadratic models are outside this linear study |
| Chen, Z. et al. (2023), representing LPs | No expressivity theorem is asserted by this draft |
| Chuang and Qiu (2025), general LPs | Continuous LP solver substitution is not evaluated |
| Dai et al. (2017), graph combinatorial algorithms | Broad antecedent rather than the implemented MILP intervention |
| Ding, T. et al. (2024), small GNNs for LP | Distinct from Ding, J.-Y. et al. (2020); not interchangeable |
| Du et al. (2021), taxonomy categorization | Different prediction task |
| Falkner et al. (2022), neural LNS | Potential extension; incomplete supplied identifier and no learned LNS policy here |
| Gupta et al. (2020), hybrid branching | No branching-policy experiment |
| Gupta et al. (2022), lookback branching | No lookback branching experiment |
| Hadou and Ribeiro (2025), unrolled GNNs | No unrolled optimization architecture |
| Han et al. (2025), ILP feature augmentation | No local-uniqueness result is claimed |
| Huang et al. (2022), problem reduction | Related exploratory intervention, not needed for the primary hint comparison |
| Jegelka (2022), GNN theory | No new representation theorem |
| Jegelka et al. (2024), approximation algorithms | No approximation-ratio claim |
| Kapoor (2025), EV route optimization | Different application and explanation target |
| Khemani et al. (2024), GNN review | Duplicates broad background |
| Koyama and Tatebe (2022), distributed training | Distributed scaling is not an empirical claim of this article |
| Labassi et al. (2022), node comparison | No learned node-selection policy |
| Li et al. (2025), explainability survey | Structural EDA is not an explanation method |
| Liu et al. (2022), benchmark taxonomy | No graph-benchmark taxonomy contribution |
| Longa et al. (2025), explainers | No explainer comparison |
| Nandan et al. (2025), GraphXAI | No XAI experiment |
| Scavuzzo et al. (2024), objective prediction | Targets are binary assignments, not optimal objective values |
| Shafi and Kadioglu (2025), FORGE | No foundation-model experiment |
| Shen et al. (2021), primal heuristics | Relevant reserve reference; current related-work discussion already supported |
| Stoll et al. (2025), GraphBench | No benchmark-suite construction or cross-suite comparison |
| Tang et al. (2025), MINLP | Nonlinear optimization is outside scope |
| Turner et al. (2023), adaptive cut selection | No learned cut selection |
| Wu et al. (2021), GNN survey | Broad background duplication |
| Zhou et al. (2020), GNN review | Broad background duplication; supplied year/DOI would need publication-level reconciliation if cited |
| Zhou et al. (2025), subgraph branching | No subgraph branching-policy claim |

## Authorized collection update, 12 September 2026

The user created **CFL-GNN - Manuscript - Cited References** in My Library and
authorized its population. Destination key: `NNPXWSYK` (local library1,
collection72). Six existing items were linked using Zotero's client API;
their bibliographic metadata and prior collection memberships were preserved.
Only Gasse and Cappart were imported through the connector after verifying the
selected destination. Read-back through the local API confirmed exactly eight
regular items in the collection, matching the table above.

The local `/api/` is read-only; membership writes used the supported Run
JavaScript interface, and the two imports used the connector. No attachments,
notes or unrelated collections were imported, deleted or reorganized. Existing
metadata discrepancies remain explicit; the manuscript bibliography is not a
blind export of those records. Future citations require a corresponding reviewed
collection update, rather than importing the entire supplied reading list.
