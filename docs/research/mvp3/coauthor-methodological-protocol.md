# CFL-GNN MVP 3.0: methodological protocol for coauthor review

**Status:** detailed methodological proposal, not execution authority.  
**Mandate:** CFL-GNN-MVP3-SCI-2026-11-19 and Technical Gurobi Addendum 2026-02.  
**Prepared:** 19 November 2026. **Protocol milestone:** 3 December 2026.  
**Pause:** 19 December 2026–10 January 2027. **Target submission:** 18 March 2027.  
**Target journal:** Computers & Operations Research.

This protocol separates a concluded exploratory study from a new investigation. Historical CPU campaigns, the one-hour 144-cell comparison, the twelve-hour study, serial/DDP training, negative results, censures, numerical audits and all original receipts remain intact. They show conditional effects, not general superiority of neural guidance. The PR98 990-evaluation factorial and the subsequently considered 66/18 alternatives are discontinued. Existing execution approvals do not authorize this protocol's implementation or experiments.

## 1. Scientific question and scope

Under which conditions do graph-neural-network partial MIP Starts improve the quality and computational efficiency of solving the MILPBench CFL instances with native GurobiPy, especially on larger hard instances excluded from learning, after accounting for preparation and use?

The contribution claims are C2, conditional optimization benefits, and C3, computational economics. Reproducing the GNN-to-Start-to-MILP mechanism is a methodological obligation. The study is designed to detect benefit, no benefit and harm. It does not choose settings retrospectively to obtain a favorable effect.

Three mechanisms must remain separate: binary prediction, creation/completion of a partial Start, and subsequent primal/dual search. Better predictive F1 does not prove better solver utility, and a better incumbent need not close the dual gap sooner.

The reference interface is exclusively native gurobipy. Existing alternative-interface code is retained as history and is not a new comparison arm. Benders is a separate mathematical investigation with its own budget and approval.

## 2. Prospective decisions and unresolved decisions

The mandate establishes Seed=42, Threads=0, ConcurrentMIP=1, Method=-1, main-solver Presolve=-1, MIPFocus=0, documented default Heuristics, MINIMIZE, TimeLimit=28800 seconds and terminal MIPGap=0.0001. The four observed quality thresholds are 0.10, 0.05, 0.01 and 0.0001, corresponding to 10%, 5%, 1% and 0.01%.

A twelve-hour Slurm allocation is an operational envelope for one eight-hour solver call plus construction, audit and export. It is not twelve hours of native optimization, and cannot contain three worst-case eight-hour calls.

Coauthor decisions are still needed on:
1. The minimum admissible quality of a supervised incumbent and the disposition of missing or numerically invalid references.
2. The exact 42/9/9 parent split and its deterministic selection rule.
3. The equivalent-work serial/DDP schedule and the validation-only rule selecting the deployed predictor.
4. The externally qualified CPU, memory, SMT, affinity, license and concurrent-job envelope.
5. Whether characterization baselines can later be reused for particular evaluation metrics, or whether all B/R/G cells are executed contemporaneously.
6. The final partial-Start support/threshold/abstention policy, precommitted before test outcomes. Historical 10% support/20,000 cap is context, not automatic authority for a new trained predictor.

None of these decisions authorizes a hyperparameter search. Sensitivity, extra seeds, variable hints and retraining variants remain separately approved studies.

## 3. Model identity and numerical validity

Use all 90 original MILPBench CFL instances: 30 easy, 30 medium and 30 hard. Display aliases are E, M and H; original filenames and IDs remain in the identity table. Record compressed and decoded hashes where applicable, dimensions, variable domains, objective coefficients/constant and source provenance.

Preserve the approved mathematical formulation and original files. Force MINIMIZE at runtime and record the original declaration; do not rewrite coefficients, domains or constraints. Hash and signature checks establish identity, not a new semantic certification of the benchmark generator.

Every returned incumbent requires an independent check against the original model: finite and complete values, variable alignment, bound/domain/integrality residuals, constraint residuals, recalculated objective and explicit tolerances. Report both solver acceptance and independent audit scope. Rounding a near-integer coordinate is not an automatically validated repair. Preserve M4/M12 numerical qualifications and any other newly discovered inconsistency without automatic tolerance changes or retries.

Lower bounds and optimality statuses are floating-point solver evidence. They are not exact-arithmetic certificates. Infeasibility, lack of an incumbent, numerical failure and a time-limited nonzero gap are distinct dispositions.

## 4. Characterization of all 90 instances

Run B without an external Start, prospectively under the common main-solver contract. Record:
- Original and presolved model dimensions when exposed, structural descriptors and graph dimensions.
- First observed candidate/accepted incumbent with precise event semantics; improvements and final incumbent.
- Best dual bound, relative gap, Runtime, Work, nodes and terminal status.
- First qualifying observations at the four thresholds, including event, time, work, primal, dual, nodes and numerical eligibility.
- CPU, memory, logical/physical allocation, affinity and observed utilization.
- Exact source, versions, parameter/attribute maps, input/output hashes and job/step identities.

A callback is an observation mechanism. First-observed threshold times are not exact continuous crossing times. Do not interpolate missing observations. A final attribute may provide a terminal fallback, explicitly distinguished from an earlier callback observation.

A MIPSOL event can present a candidate that is not a strictly improving incumbent. The recorder must distinguish candidate objective, best incumbent and independently checked solution. A full vector for every non-improving event is not required: use bounded event metadata and a predeclared retention policy for reconstructible incumbent improvements. Final vectors and label references require durable checksums. Storage and callback overhead must be budgeted; do not claim measured low overhead before qualification.

The scientific table has one row per original instance and a linked detailed event table. Missing values carry reasons, not zeros. Original instances remain the observational units.

## 5. Dataset, labels and split

Only the 60 easy/medium parents may enter training, validation or training-related selection. All 30 hard are excluded from prenormalization fitting, class weighting, checkpoint/threshold selection and architectural or hyperparameter decisions.

The principal candidate split is:
| Role | Easy | Medium | Total |
|---|---:|---:|---:|
| Training |22|20|42|
| Validation |4|5|9|
| Test |4|5|9|

The balanced-training alternative uses 21E+21M, validation 4E+5M and test 5E+4M. Both satisfy 42/9/9 overall. The latter balances training classes; the former gives validation and test identical class counts. Choose using this design rationale and exposure records, not downstream test performance. Freeze identities and selection seed before learning; deterministic repeated graph presentations do not increase the number of independent parents.

An eight-hour target of 0.01% is not itself a complete label-admission policy. If a reference stops above that target, decide in advance whether its independently feasible incumbent is admissible at a documented gap or is ineligible. Do not silently revive the historical 10% cutoff, remove difficult parents or replace the proposed split after observing learning results. If insufficient parents qualify, retain the original population ledger and seek a specific scientific decision.


The label-quality decision should explicitly compare three policies: (i) the common 0.01% terminal target as a strict admission cutoff, with possible loss of difficult parents; (ii) a separately justified intermediate cutoff such as 1%, retaining the attained gap as metadata; and (iii) all independently feasible incumbents with quality-stratified reporting, accepting more heterogeneous supervision. These are review alternatives, not authorized label transformations or additional solves. The choice must precede model fitting and cannot depend on favorable test results.

Labels derive from qualified integer incumbents, not continuous root values. For binary coordinates, preserve a documented mapping and tolerances. Root relaxation is an inference feature. Label quality is global to the originating incumbent, not an individual-variable gap.

Fit numerical normalization and positive-class weights on training data only. Select checkpoints and probability thresholds on validation only. Never include incumbent-derived targets or target metadata in inference graphs.

Historical exposure must be disclosed. Some easy/medium and hard instances have already informed descriptive or technical studies. “Excluded from training” is defensible; “entirely unseen, independent generalization” is not automatically defensible. Freeze prospective policy before using hard characterization outcomes to avoid indirect tuning on the transfer cohort.

## 6. GNN and equivalent-work serial/DDP training

Initially retain the Gasse-inspired model: variable/constraint/edge inputs 7/5/1; two alternating bipartite convolutions; width 32; 26,753 trainable parameters; training-only prenormalization; weighted BCE; Adam. Appendix A.8 derives these operations and distinguishes the historical protocols. This preservation does not assert that existing weights represent the new split.

Compare one V100 with four V100s using:
- Identical admitted parents, initial parameter state and fitted buffers.
- The same complete ordered global batches and number of graph presentations.
- The same global-batch loss, optimizer updates, learning-rate schedule, precision, clipping, epochs and stopping policy.
- Equivalent checkpoint and threshold rules and evaluation populations.
- Explicit distributed sampling/padding/drop behavior; no rank duplicates masquerading as additional data.

Candidate continuity with the historical matched study is global batch four and 100 epochs, with four deterministic presentations per parent. If approved for 42 training parents, this means 168 presentations and 42 updates per epoch, hence 16,800 presentations and 4,200 updates per arm. These are conditional planning counts, not fixed new experimental settings or historical replacements.

Record parent-level precision, recall, F1, average precision and explicitly defined PR-AUC; distinguish average precision from trapezoidal integration. Report pooled metrics only with their weighting stated. Record selected and terminal checkpoint quality, training-loop and complete-job time, GPU-hours, physical core-hours and allocated/reserved GPU memory.

Speedup is serial time divided by DDP time for the same work and clock. Parallel efficiency divides that speedup by the GPU resource ratio. Report quality alongside time. The historical DDP F1 reduction is not a causal estimate of an intrinsic DDP penalty.

Before solver testing, freeze a validation-only deployment rule. Do not choose whichever predictor performs better on the nine test or 30 hard instances. Comparing solver effects of both separately trained predictors would require a separately approved expanded design.

## 7. Paired B/R/G evaluation

The test cohort is nine easy/medium test parents plus all 30 hard, totaling 39. Keep within-represented-class evaluation and transfer to hard separate.

- B: original model without external Start.
- G: partial Start from the selected frozen GNN.
- R: relaxation-ranked control with selected cardinality and number of ones matched to G. R is secondary and depends on G's preparation; it is not an independent relaxation-only deployment or a definitive isolation of learning.

Use fresh models and identical mathematical data, solver parameters, resources, time limits and numerical audits. Unselected variables retain undefined Start attributes and unchanged domains/bounds. No fixing, hints, repair-solve stage or new policy arm is implicitly included.

Specify the order/blocking policy before outcomes. Maintain comparable external concurrency across arms. R/G support counts are matched, not necessarily their variable identities. Distinguish Start submission, solver processing, completion/repair, acceptance as a feasible incumbent and later search. Missing messages are “unobserved”, not proof of rejection.

An empty or invalid Start must have an explicit disposition. An approved abstention may mean an unmodified baseline-equivalent solve, recorded as such; it is not silently deleted. The policy and whether such a call belongs in a particular paired contrast are predeclared.

No ConcurrentMIP>=2 arm and no seeds 43/44 arm belongs to the principal design. Scientific sensitivity requires separate approval.

## 8. Analysis, censoring and C2

For each common gap target tau, define speedups S_BG(tau)=T_B(tau)/T_G(tau) and S_RG(tau)=T_R(tau)/T_G(tau). Values above one favor G. This prospective speedup convention is the reciprocal of the historical T_G/T_B time ratio; original fields and historical receipts remain unchanged.

Calculate a numerical speedup only if both arms have observed, numerically eligible attainment of the same target and positive comparable times. Record exclusive attainment, neither-arm attainment and ineligible pairs separately. A TimeLimit is not an observed solution time. Avoid a geometric mean pooling heterogeneous targets, difficult instances and censored rows without explicit eligibility and denominators. Any geometric mean is specific to a target/cohort/clock and accompanied by per-instance results.

At the common time budget, compare feasible primal quality, dual bound and gap independently. Report feasible-solution availability and numerical status. For minimization, a smaller feasible objective and a stronger lower bound describe different progress. A smaller internal gap can be misleading when primal points or bounds are not comparably qualified.

Use an instance-level ledger with exclusions per metric, rather than a single “valid/invalid experiment” flag. Describe paired differences and distributions by class and structural difficulty. Seed 42-only observations characterize this solver configuration; they do not estimate seed robustness. No new significance requirement or repeated-seed campaign is imposed here.

For Pareto analysis within the same original instance and resource scope, specify minimization objectives such as elapsed end-to-end cost and independently qualified primal objective at a common scope; define dominance as no worse in every chosen dimension and strictly better in at least one. Missing/censored quality or incomparable scopes cannot be silently ordered. A speedup alone is not a Pareto frontier.

## 9. Computational economics and C3

Report native solver time separately from model load/build, root capture, graph construction/serialization, transfer, inference, Start assembly, independent validation and export. Identify nested timing regions before summing: a nested export or forward measurement must not be counted twice.

Distinguish computational performance (time, memory and attained quality), matched-work speedup, resource-normalized efficiency, strong scaling, weak scaling, problem-size scale-up and throughput. The principal fixed-policy solver evaluation can describe size effects and campaign throughput; it does not itself constitute a controlled strong- or weak-scaling experiment. The separate equivalent-work serial/DDP training comparison has its own resource ratio and quality assessment.

Cold-use accounting includes required preparation. Reuse scenarios state which artifacts are reusable, under which identical model/checkpoint/policy, and whether training is charged. Training, one-time preparation and per-use costs are separate.

A theoretical break-even for common attained quality may be evaluated only if a positive per-use saving is observed under the same clock and scope. With fixed extra preparation P and net per-use saving d>0, k>=P/d is the conditional algebraic threshold (integer uses require rounding up); if d<=0 there is no finite break-even under that model. Include recurring guidance costs in d. This is not an empirically demonstrated number of future uses. The historical seven-use scenario remains an amortization scenario unless its inputs and assumptions support the stated calculation.

## 10. Gurobi/HPC qualification and instrumentation

Records from the historical pilot identify Gurobi 13.0.1 and 40 physical/80 logical CPUs, not live infrastructure availability. Qualify actual Slurm topology, cpusets, physical sibling mapping, NUMA, memory, storage, license and environment.

The candidate is two jobs, each on 20 disjoint physical cores with SMT (approximately 40 logical CPUs). Threads=0 retains automatic selection; its usual 32-thread soft ceiling and any environment ThreadLimit must be recorded. Allocation, created native threads, active CPU use and solver thread ceilings are different quantities. Do not assume affinity alone makes every library honor the resource boundary.

Measure Runtime, Work, NodeCount and available event/phase fields with bounded callbacks; OS/cgroup sampling must not call the solver API from a background thread. Treat presolve, root, barrier, crossover, search and Start-processing observations as overlapping or partially observed where appropriate, rather than manufacturing additive phase durations. Work is complementary to seconds and has no fixed conversion. Keep TimeLimit; do not replace it with WorkLimit.

The full effective parameter map includes defaults and version, with the license at the canonical site path. Do not store license contents, secrets or private vectors in Git. Root-preparation parameters are a separate contract and remain to be explicitly specified for the new dataset; main-solver Threads/Presolve settings must not silently overwrite them.

No scientific solve or load test is authorized by this document. Future site qualification or telemetry-overhead checks need concrete scope and author CLI intervention.

## 11. Resource estimates and feasibility

The conservative principal-solve budget counts a fresh B/R/G evaluation, without assuming characterization B reuse. It excludes separately budgeted root-preparation solves:

| Stage | Solves | Nominal maximum solver-hours | Maximum Slurm job-hours |
|---|---:|---:|---:|
|90 characterization baselines|90|720|1,080|
|39 test parents x B/R/G|117|936|1,404|
|Total|207|1,656|2,484|

At the candidate 20 physical cores per job, these correspond to 33,120 nominal solver-core-hours and 49,680 reserved core-hours. These are reservation/nominal limits, not observed consumption or a promise of strict termination at TimeLimit. Multiplying a solver clock by allocated physical cores is a budget convention, not a measurement that every allocated core was active throughout.

With two continuously available jobs and twelve-hour envelopes, characterization takes at most 45 full waves (540 hours), and the separate 117-job evaluation stage 59 waves (708 hours): 1,248 hours, approximately 52 days, before queueing, preparation and training. With one slot, the aggregate reservation is 103.5 days. Easy instances may terminate earlier, but the schedule must not depend on that assumption.

An optional reuse scenario, only after scientific equivalence review, uses the 39 matching characterization B records and 78 fresh R/G solves: 168 total, 1,344 solver-hours and 2,016 job-hours, or 40,320 reserved physical core-hours. Two-slot phase estimates are 45 + 39 = 84 waves (1,008 hours / 42 days). Different execution periods and resource contention weaken contemporaneous pairing; no budget reduction is assumed until this decision is made.

Memory at 20 cores cannot be extrapolated from four-core pilots. If m GiB per job is qualified, total principal reservation is 2,484m GiB-hours, with two-job peak 2m. Graph/vector sizes and event-retention policy determine storage; compute it from the 90-instance inventory rather than inventing a constant. Baseline characterization needs no GPU. Root/graph preparation, dataset qualification, serial/DDP training, inference and Benders have separate line items not yet quantified by adequate evidence. The 207 principal solves are therefore not an upper bound on all Gurobi calls. If each of the 90 parents needs one separately captured root, that adds up to 90 preparation calls, each with its own approved cap and overhead. Do not silently obtain historical-style root features from the main auto-presolved baseline: preparation settings and feature identity must first be specified. Existing roots are reused only after equivalence review; a newly trained predictor also needs its own inference outputs.

For training wall caps h1 and h4, reserved GPU-hours are h1+4h4; do not use a historical speedup to predict the new dataset's duration. The protocol's resource table remains conditional until feasibility and scientific choices are approved.

## 12. Gates, provenance and editorial boundaries

1. Coauthor approval of the scientific protocol, label/split/deployment choices and budget.
2. Separately authorized implementation PRs, proportionate tests and independent review.
3. User-operated read-only site checks and any explicitly authorized technical qualification.
4. Exact-source CI, frozen identities, preflight and specific CLI release before jobs.
5. Collection, unique-cell reconciliation and metric-specific qualification.
6. Results/editorial integration only from qualified evidence; final audit and author approval before merge, public release or journal submission.

Failures preserve source, plan, logs, claims and partial artifacts. No automatic retry, requeue, parameter adjustment, instance replacement or budget renewal. All HPC/SSH/SCP remains operated by the author; RAID evidence directories are used, not home captures. No messages are sent to coauthors through this preparation.

Small public sources, sanitized receipts, manifests and derived tables belong in GitHub. The reviewed Zenodo plan governs redistributable archival artifacts; do not claim a new deposit or DOI. Raw models/vectors/checkpoints require explicit rights, size and privacy review. Temporary files stay in authorized local Codex scratch.

The architecture/Benders note is a design specification, not a prerequisite implementation secretly added to the main empirical study. Initial Benders is external and iterative, subject to domain/integrality and cut-validity proofs and a separate execution decision.

## 13. Delivery map and schedule

The existing approved Sprint/PR sequence remains the organizing plan; it is not expanded here. The closure and mathematical foundation cover E1/E10. This protocol covers E2–E7 and E11; the accompanying Gurobi adequacy/architecture note covers E8/E9. The machine-readable decision register identifies unresolved choices without duplicating the prose.

Protocol to coauthors by 3 December 2026; preparation and separately approved activities 4–18 December; pause 19 December–10 January; characterization/dataset in January; learning/evaluation in February; synthesis/review 1–10 March; target submission 18 March. The resource envelopes expose material schedule risk: 52 days at two continuous slots leaves limited time for queueing and training after the pause. If feasibility fails, report the impact and seek a specific scientific/editorial decision; do not reduce time limits, drop hard instances or alter the split silently.

## Technical sources

- [Gurobi13 parameter reference](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/parameters.html).
- [Model attributes including Runtime, Work and memory](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/attributes/model.html).
- [Callback codes and observation semantics](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/numericcodes/callbacks.html).
- [MIP Starts and hints](https://docs.gurobi.com/projects/optimizer/en/13.0/reference/attributes/variable.html).
- [Historical matched GPU contract](https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/blob/3700d90af6bdc1beab72a420cd7d0c965b7005bf/configs/experiments/pr87_matched_gpu_v1.json).
- [Appendix A mathematical foundation](../../../manuscript/supplement/gnn-mathematical-foundations.md).
