# MVP 2.0 delivery plan — 2026-10-06

## Objective and checkpoint

Finish a reproducible comparison of learning-assisted CFL optimization and
its computational costs. The delivery unit is a complete scientific or
operational outcome. Preparation, execution evidence, corrections and closure
belong in the same PR when they address that outcome. A new helper, receipt or
individual CI repair does not by itself require another PR.

The checkpoint was checked against the repository and received public evidence
on 2026-10-06. PRs 64–76 are merged into `develop`. PR77 head
`30f80577fa7302348ed3807551e3b2c660779faf` passed four-arm CI and independent
review of its installed preview. The user authorized ready and merge of that
head. Authenticated publication is pending at this checkpoint; this document
does not claim that merge occurred. Later operational receipts determine the
actual state. All prospective PR numbers below are indicative, not reservations.

Main, Pages, the MVP 1.0 source/evidence and the unpublished Zenodo draft retain
their existing release boundary. Matrix resource approval remains separate
from PR77 merge authorization.

## What the completed work supports

| Work | Evidence already obtained | Remaining limit |
| --- | --- | --- |
| PR64–65, Sprint A foundations | Frozen MVP 1.0 evidence; successful structural collection of all 90 original models; 87 report observations across 36 parents and 77 Parquet table observations | Complete historical costs, unique feasible incumbent totals for the 54-parent cohort and actual derivative consumption are not established |
| PR66–67, first CPU screen | Job 3468: all ten attempts verified; easy reached the configured 10% gap target in all five arms; medium reached it in none; phase observations qualified for nine logs | Two fitting parents, one seed and a shared node; medium/16-thread phase observation remains unqualified; no larger-budget memory qualification |
| PR68, shared A/B foundation | Explicit artifact, attempt and allocation registries | Registries do not supply missing historical observations |
| PR69–74, bounded instrumentation | Comparison contract, callback adapter, isolated worker, nonblocking short workflow; job 3479 callback/terminal numeric audit; current Slurm context | Historical RSS measures are not reconciled; true continuous target crossings and root/tree CPU phase costs remain unqualified |
| PR75–77, paired execution infrastructure | Memory-stop executor, nonblocking two-job operator, explicit budget recorder; installed synthetic probes of 25, 28 and 18 tests respectively | The longer matrix has not run; synthetic probes do not establish actual allocation memory enforcement |

There were twelve increments from PR66 through PR77, including the shared
registry work. They enabled the experiment; they are not twelve completed
comparative studies. Sprint B remains open until the paired result, accounting
review and resource-profile decision are available.

Sources: [PR65 collection](pr65-computational-ledger.md),
[screen review](../evidence/pr66/job3468/screen_review.json),
[phase review](../evidence/pr67/job3468/phase_review.json),
[job3479 audit](../evidence/pr73/job3479/job3479_private_review.json),
[executor](../evidence/pr75-paired-matrix-executor.md),
[operator](../evidence/pr76-paired-matrix-workflow.md),
[budget recorder](../evidence/pr77-installed-operator-budget.md).

The independently verified PR77 installed
[receipt](../evidence/pr77/installed-budget-30f80577fa73/pr77_installed_preview.json),
[false preview](../evidence/pr77/installed-budget-30f80577fa73/installed_false_preview.json)
and [manifest](../evidence/pr77/installed-budget-30f80577fa73/SHA256SUMS.txt)
are archived byte-identically. The receipt SHA256 is
`bdbb0f75358d6c15523a05bec9c97d72fb49c90c1ab08c4f72d2b275ce501286`;
the preview SHA256 is
`8d56ba84a9c40c495a8c3713475be114a67741204b75b017bc7c900bede4189e`.
They attest the original PR77 source, not another run at this planning commit.

## Sprint B: two remaining deliveries

### B1 — paired execution and evidence (prospective PR78)

This draft starts with the refreshed plan and analysis commitments, and closes
with the actual paired execution evidence. It reuses the installed PR76 flow.
Do not manufacture a replacement flow merely because develop has advanced.

The frozen scope is:

- Parents `CFL_easy_instance_17` and `CFL_medium_instance_1`, both fitting roles;
  seed 42; thread caps 1, 2, 4, 8 and 16 in the existing frozen order.
- Source `ad4800505bae78032e8fdbaa449a7afd2f12a080`;
  operator plan `c7f5aa69c775088e7d383a942d9ee66f2b053dfe656e5d123e80e546692f70a2`;
  matrix plan `b24dbe0924a2c6f03f7f162cf2f85bfd327f4a0bd99048b98200b6f22e5a575b`.
- At most two sequential parent jobs and ten optimize calls, 3,600 seconds
  each. Easy stops at 1% gap; medium at 10%. Gurobi 13.0.1 defaults and the
  effective MINIMIZE convention remain those of the frozen contract.
- One task, 16 physical cores, 64 GiB and 330 minutes per parent; CPU only,
  shared node, no requeue or automatic retry. Memory and affinity gates stay
  mandatory before model access.

The solver ceiling is ten hours. The two allocation ceilings total eleven
hours, excluding queue time and the review between jobs. At sixteen physical
cores this corresponds to at most 176 requested physical-core reservation
hours; accounting that charges 32 logical CPUs could report 352 logical
CPU-hours at those same ceilings. These are prospective ceilings, not measured
consumption. Actual costs come from the returned allocations and are counted
once per parent job.

Operational sequence:

1. Finish the authorized PR77 merge and retain its actual receipt.
2. Present and record the separate explicit frozen budget in the existing
   flow, using the qualified recorder and preserving original false records.
3. Submit easy once. The allocation validates the actual cgroup, memory and
   affinity before solver access. Status returns after one query.
4. Collect after terminal state and independently review the public package,
   accounting, callback observations and private-log hash binding.
5. Record the qualified easy review; only then submit medium once. Collect
   and review it under the same contract.
6. Archive the sanitized returns, their provenance, all interruptions and the
   bounded execution/accounting summary in this same PR.

No extra no-solver qualification campaign is planned. A demonstrated defect
may require a targeted correction and renewed validation of affected bytes;
that exception is driven by evidence, not an assumed need for another layer.
A failed allocation or memory gate preserves its state and stops execution.
It cannot be reported as a completed paired pilot or automatically retried.

Acceptance: both parent returns independently validated with all attempts and
cost scopes accounted for; alternatively, a documented interruption and an
explicit unresolved gate. A time limit above the target is a valid censored
outcome. A memory/worker failure remains a different outcome. An interrupted
delivery can preserve useful evidence but does not close Sprint B.

### B2 — paired analysis and CPU-profile decision (prospective PR79)

Implement the analysis from the commitments below, add meaningful synthetic
tests for censoring and allocation double counting, and then apply it to the
sealed returns. Close this PR with tables, figures, interpretation and a
traceable profile choice for subsequent development experiments.

Precommitted reporting rules:

1. Keep one row per parent, seed and thread cap, retaining failures and missing
   observations. Report terminal status, primal, dual, gap, solver runtime,
   observed target attainment and its observation semantics.
2. Compare caps within a parent. The easy/medium targets and stopping rules
   differ; do not pool their solve times as a common target experiment. A
   terminal gap measured after early target stopping is not a measurement of
   quality at the full 3,600-second horizon.
3. Report first observed target times and their sampling resolution. A target
   not observed by termination remains censored. Preserve the distinction
   between the actual first crossing and its first recorded observation.
4. Compute target-time speedup `T(1)/T(t)` only when both arms reached the same
   target with comparable valid observations; efficiency is that ratio divided
   by `t`. Provide the denominator/coverage for every aggregate. Do not replace
   missing target times by the time limit to create a measured speedup.
5. Keep solver/process CPU, scheduler TotalCPU, allocated logical CPU-hours,
   physical-core reservations, worker RSS and sampled cgroup memory in their
   own scopes. Account for each allocation once, retaining overhead and
   failed execution costs. Root/tree costs remain unavailable unless the new
   evidence actually qualifies them.
6. Present per-parent time/quality/cost/memory trade-offs and non-dominated
   resource profiles. Predeclare any practical tie tolerance before examining
   the long-run results. Choose a development profile only from resource-valid
   evidence; a choice may differ by class and need not prefer more threads.
7. Make descriptive development claims only: two parents and one seed cannot
   establish population-wide scaling, generalization or statistical significance.
   The PR66 short screen and the new budget are separate experiments and costs.

Sprint B closes when there is a valid paired report, a justified usable CPU
profile and explicit remaining limitations. An adverse performance result is
acceptable. A missing resource-valid comparison is an unresolved gate.
No expansion to extra parents/seeds is implied by closure.

## Remaining sprints and integrated historical audit

| Sprint | Planned complete PR deliveries | Acceptance / dependency |
| --- | --- | --- |
| A carry-over + C1 | One data/provenance and graph-representation delivery | Close the historical audit with qualified coverage and explicit missingness; validate every label/role used by new training; define feature transforms and prevent leakage |
| C2 | One matched easy-only versus mixed training delivery | Frozen splits, architecture, learning policy and validation-only checkpoint selection; complete curves, per-parent predictions and compute receipts |
| C3 | One serial/DDP scaling delivery | Qualify 1 then 2 GPUs, then conditionally 4/8; matched global batch, data mass and optimizer updates; time, communication, utilization and memory evidence |
| D1 | One derived-MILP generation and independent labelling delivery | Fitting parents only; model identities, feasibility/label audits, accepted/rejected derivatives and parent-linked roles |
| D2 | One matched augmentation ablation delivery | Original-only, Gurobi-derived, SCIP-derived and combined arms where qualified; equal parent mass and reproducible sampling; explicit missing arms |
| E1 | One frozen warm-start comparison delivery | Held-out/transfer cohorts, paired seeds, resource profile, three method arms and start-coverage policy fixed before execution |
| E2 | One comparative execution and statistical analysis delivery | Complete evidence, paired per-parent effects, appropriate uncertainty, censoring, negative outcomes and preparation/inference/solve costs |
| F1 | One scientific synthesis delivery | Reproducible manuscript tables/figures, contribution and limitations, resource-cost interpretation and coauthor review |
| F2 | One release delivery | Approved promotion to main, Pages and rights-reviewed deposit; verified actual DOI; MVP 1.0 remains recoverable |

Together with B1/B2, this is eleven planned remaining PR deliveries. It is a
scope map, not a target to inflate PR count. Adjacent compatible outcomes may
share a PR; a demonstrated contract change may require another. Each delivery
includes its implementation, necessary tests, runbook, evidence and closure.

### C: data, representation and training

Integrate the pending Sprint A audit into C1. Attempt/job attribution and
unique feasible vectors must retain their qualification and coverage. Missing
historical GPU telemetry, historical full-cohort costs or derivative usage may
remain unavailable with a documented reason; new jobs cannot reconstruct them.
Before using a label in new training, its model, variable order, feasibility,
gap evidence and role must satisfy the data contract. A historical aggregate
count is not a substitute for that admission check.

C1 also covers bipartite variable/constraint graphs, numerical scaling and
the representation study. Fit learned transforms on fitting parents only.
Evaluate whether PCA/UMAP and the supplied Vargas-Pérez work are applicable;
their use is not already established. Document the method, out-of-sample rule,
computational cost and planned ablation before training. Descriptive
visualization and GNN input transformation are separate uses.

C2 retains the existing two-layer, hidden-size-32 model as a reproducible
baseline. Architecture or dimensionality ablations must be declared before
their runs. Easy-only uses the 30 easy originals with disjoint roles (the
existing 18/6/6 split is the starting contract), rather than fitting all thirty.
The mixed historical cohort has 54 admitted parents, of which 34 supplied
fitting updates, ten validation and ten predictive testing. Newly matched
training must verify those roles and the admitted data, retain at least 100
epochs and use validation only for checkpoint/policy choice.

Report AP, F1/precision-recall, calibration and prevalence-aware baselines
per parent, plus graph preparation, cold inference and training costs.
C3 controls data membership and effective optimizer work; speed and predictive
quality are separate outcomes. Moving to four or eight GPUs requires successful
lower-count qualification and a separate bounded resource decision. It is not
an unconditional escalation to the maximum hardware count.

### D: augmentation with independent experimental units

New incumbents of an unchanged MILP are additional targets, not independent
graphs. Derived MILPs must actually change the model, preserve parent-disjoint
roles, receive independent labels and pass feasibility checks. Keep solver
source, duplicate counts, label yield and actual fitting consumption in the
lineage. Equalize parent sampling mass when comparing the admitted arms. No
advantage is assumed from correlated oversampling. Full four-arm comparison
requires all four qualified arms; otherwise report the attainable comparison
and the missing arm explicitly.

### E: optimization outcomes and transfer

E1 freezes unguided, root-LP-guided and GNN-guided arms with matched starts'
coverage/completion policy, resource caps, seeds and method order. Preserve the
legacy at-most-10%-of-binaries / 20,000-variable rule as a documented comparator;
justify or predeclare any ablation rather than changing it after results.
State exactly which integer/continuous values each arm supplies and account
for relaxation, representation and inference costs.

Easy-only may treat medium/hard as external transfer populations. Mixed-model
analysis must separate previously fitted parents from held-out parents. The
historically inspected six-parent medium test is development evidence. The
parent is the independent unit; seeds and descendants are nested observations.
Plan confidence intervals/inference for the eventual cohort size in E1.

E2 executes the authorized cohorts and retains all outcomes. Start with a
bounded structurally chosen hard subset; broader expansion requires its own
qualification and budget. There is no standalone hard-label campaign.
Report gap/objective/bound movement, valid target times, acceptance/completion
of starts, cold total cost and amortized reusable cost. The compared solve
budget starts at 3,600 seconds; any sensitivity is declared prospectively.

### F: manuscript and release

Manuscript planning and table/figure templates can progress while experiments
run. Final scientific claims follow the evidence, including adverse effects,
limited cohorts and unavailable telemetry. Journal fit is argued through the
optimization question, learning contribution and measured computational trade-offs.
Neither pipeline test counts nor availability of a DGX is itself a scientific
contribution. Coauthor approval, main/Pages promotion and public data rights
remain release decisions; an unpublished deposit ID is not a verified DOI.

## Sequencing and operator handoff

The critical path is PR77 merge → separate matrix budget → easy result/review
→ medium result/review → B2 profile decision → controlled comparisons.
C1's historical/data audit and representation specification may proceed while
the CPU matrix runs. C2/C3 and D are scheduled with their data/resource gates;
E uses the validated models, roles and resource profile. This plan grants no
new HPC budget.

Every operator handoff names its shell and host. Windows PowerShell commands
use Windows paths and the `&` invocation operator. Bash commands run on
`dgx-dasci` and use physical RAID paths. `service0` is not the contracted CFL
execution host. Never paste a PowerShell command into Bash or install this
project into the unrelated current repository there.

Provide preparation, one-shot status, terminal collection and local receipt
verification together whenever their inputs are already fixed. Keep all
execution evidence on physical RAID, preserve failed attempts and request a
merge only after the PR is complete and ready. An authorization already given
for the same reviewed head is reused without another confirmation.
