# TR-01 — Editorial and Release Readiness

**Updated:** 23 November 2026. **PR:** #101, Draft, targeting develop.

## Problem and resulting behavior

Quarto's TinyTeX release lookup previously returned HTTP 403 during editorial setup. This PR passes the workflow's existing GitHub token to that setup step as GH_TOKEN. Existing read-only contents permissions are retained. The change does not expose the token, alter mathematical/scientific sources or modify an HPC environment.

The previous exact-head Manuscript run [44735083952](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/actions/runs/44735083952) passed. That is a historical result for the earlier revision; new documentary commits require their own applicable CI status. The Manuscript workflow performs publication rendering in CI. It does not start a solver, model training or an HPC campaign.

## Transition record

TR-01 is the publication-readiness Sprint. The [transition Sprint register in PR #102](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/pull/102) separately tracks TR-02 runtime qualification, TR-03 data preservation/reconciliation, TR-04 NPAD data admission/checkout and TR-05 methodological approval. These names do not rename the scientific Sprints S1–S6.

The requested #97/#98-only synchronization and Pages deployment were completed on 20 November at commit 61ba422c147c3a3d9ae04b49f1607ed5fca4d0e1. Both branch refs were still at that commit when checked on 23 November. The #101 token fix, #99 methodological draft and #102 operational transition are not represented as already integrated.

## Review and release sequence

1. Review #101 against develop and check the applicable exact-revision/combined-tree CI.
2. Obtain specific author approval before merging into develop; keep the PR Draft meanwhile.
3. Reconcile other separately approved develop work before a later main synchronization.
4. Obtain the release decision through the agreed branch-synchronization flow. Do not merge an ordinary research PR directly into main.
5. After an authorized publication, verify the deploy and the article/supplement PDF, HTML and TeX links, editable LaTeX project, mathematical Appendix A.8 and GitHub/Zenodo planning reference.

The existing Pages deploy condition is restricted to main outside pull-request events. This update neither moves main/develop nor dispatches a publication. No Zenodo upload, DOI claim, new PDF delivery or scientific execution is authorized here.

## Language and scope

Repository documentation, PR descriptions and material shared with coauthors are English. Discussion with the researcher may remain PT-BR. Historical author decisions are retained as history; the current release instructions above supersede earlier comments proposing a direct merge into main. PR #99 remains Draft for the researcher's methodological review.
