# Editorial revision plan for the MVP 3.0 methodological protocol

**Recorded:** 19 November 2026. **Status:** approved direction for documentary revision; PR99 remains Draft.

This plan records the author's latest review instructions before the pause. It reorganizes the existing methodological proposal into an academic document for human readers. It does not reopen the approved Sprint sequence, change the scientific mandate or authorize implementation, qualification runs, training or experiments. The PDFs generated during the formatting work are working previews; they are not the final revised packet.

## 1. Editorial objective and scientific boundaries

The protocol should explain the research problem, why the proposed comparisons answer it, and how observations will support qualified conclusions. Each section should develop an argument in connected prose: scientific purpose, methodological choice, operational consequence and limitation. Parameter names and audit labels should support that explanation rather than substitute for it.

The rewrite will distinguish historical observations, prospective design choices, unresolved decisions and future work. MVP 2.0 supports conditional findings, including unfavorable or numerically limited outcomes. It does not establish general superiority of G. The preparation of MVP 3.0 must retain that distinction.

The main text will describe the study in English for the coauthors. Operational instructions, source inventories, detailed defaults and evidence crosswalks belong in appendices or repository records. Sending the packet to coauthors remains a separate author action.

## 2. Proposed document structure

| Section | Reader's question | Planned content |
| --- | --- | --- |
| 1. Introduction and context | Why is a new study needed? | Closeout of MVP 2.0; what its evidence establishes and leaves unresolved; transition to MVP 3.0; research question and scope of C2/C3. |
| 2. Research methods and models | What mechanisms and models are being compared? | Original MILP and model identity; the frozen-design bipartite GNN; native Gurobi search; B/R/G; solver parallelism and partial Starts; conditional, separately budgeted Benders design. |
| 3. Experimental design | How will the comparisons answer the question? | The full pipeline, experimental units, controls, parent-level split, label admission, equivalent-work serial/DDP training, deployment selection, paired solver evaluation and resource feasibility. |
| 4. Data and collection | What will be observed and preserved? | The 90 original instances and their E/M/H aliases; structural descriptors; model/checkpoint/artifact provenance; event, solution and resource records; explicit missingness and termination dispositions. |
| 5. Data analysis and interpretation | Which conclusions can the observations support? | Reconciliation and audit; metric-specific eligibility; target attainment and censoring; paired B/G and secondary R/G contrasts; predictive versus solver quality; preparation/reuse economics; reproducible tables and figures. |
| Appendices | Where can a reader verify the details? | Mathematical notation, parameter inventory, cohort/split register, data dictionary, budgets, conditional Benders derivation, evidence crosswalk and unresolved decisions. |

Each table and figure will be introduced before it appears. A short paragraph immediately after it will explain what to read, the relevant comparison and any important qualification. Captions will identify the object concisely; methodological caveats belong in the surrounding text.

## 3. Research methods and models: the explanation to develop

Begin with the original optimization problem and the distinction between a feasible incumbent, a dual bound and an optimality gap. Explain how the variable–constraint graph is built, what information is available at inference, how the GNN produces probabilities and how selected binary predictions become a partial Start. Continuous root values are features, not integer training labels.

Retain the existing Gasse-inspired model and the approved architecture description. Do not introduce GCN, GAT, GraphSAGE variants, extra seeds, tuning or new predictors as additional study arms. A new training dataset does not mean the historical checkpoint already represents the proposed split.

Explain B as the original model without an external Start and G as the same model with a partial learned Start. Explain why R is retained as a secondary, support/cardinality-matched control and why its dependence on G's preparation limits causal interpretation. Distinguish submitting a Start, completing or repairing it, accepting an incumbent and changing the later search trajectory.

Describe internal solver parallelism, external job concurrency and algorithm selection as different mechanisms. Explain the role of the main-solver parameters and the limits of repeatability with automatic methods and wall-time termination. Keep native solver time, application time, resource reservation and observed utilization separate.

Present Benders as a conditional decomposition framework, not a built-in switch assumed to deliver exactness or lower memory. Explain master variables, recourse variables, feasibility and optimality cuts, valid global bounds and termination. The canonical continuous, fixed-recourse derivation is illustrative: the actual CFL partition and any integer recourse require their own proof. Benders remains a separate methodological investigation with separate approval and budget; it is not an additional authorized B/R/G arm.

## 4. Experimental planning and treatment of time/memory limits

Use a single pipeline diagram to connect instance admission, baseline characterization, label qualification, parent-level partition, graph preparation, equivalent-work training, validation-only deployment, artifact freezing, paired evaluation and analysis. Show the separate Benders investigation on a distinct conditional branch.

Preserve the current proposed population and principal counts: 90 characterization baselines; learning restricted to 60 easy/medium parents with a proposed 42/9/9 split; 39 evaluation parents consisting of nine easy/medium test parents plus 30 hard; 117 fresh B/R/G evaluation calls in the conservative budget. These are planning counts, not execution authority. The detailed decision and budget registers remain authoritative.

The protocol must distinguish four different uses of “partition”:

1. **Dataset partition:** splitting parent instances into training, validation and test sets. It prevents leakage; it does not reduce the mathematical difficulty of a solve.
2. **Training partition:** batching and distributing graph presentations across GPUs. Equivalent work and global updates must be maintained; this does not decompose the MILP.
3. **Operational partition:** arranging independent experimental cells into jobs and resource slots. It changes scheduling and peak aggregate resource demand, not the optimization model or its per-cell time budget.
4. **Mathematical decomposition:** a master/subproblem formulation such as Benders. It requires proof of equivalence, integrality and valid global bounds and may increase memory through additional models, cuts and worker states.

Discuss these mechanisms as ways to manage feasibility and understand limitations, without promising to eliminate censoring. State the clock and memory scope for each limit. The candidate two-job/20-physical-core allocation is not yet site-qualified. The 207 principal solves exclude root preparation and training, so preparation cannot disappear from the budget.

Predeclare what happens when a cell reaches a time limit, memory guard, numerical failure, missing incumbent or infrastructure failure. Preserve its population identity and evidence. Do not replace the elapsed limit with an observed solution time, split a difficult instance into easier fragments, drop hard instances, change the model or increase budgets silently. Any proposed decomposition or alternative resource envelope remains conditional on a specific scientific decision.

## 5. Collection and analysis pipelines

The collection section will identify the original instances, provenance, dimensions, variable domains, graph descriptors and compressed/decoded identities. Difficulty will be described using available structural and baseline observations, without claiming that the E/M/H labels alone are a validated complexity scale or using outcome-driven strata to favor G.

Define the observational units explicitly: parent instance, training run, solver execution and timestamped event. Repeated graph presentations and callback events are not independent instances. Explain a compact record in prose before giving the full schema in an appendix.

The analysis pipeline will be described in order:

1. Verify source/plan/artifact hashes and reconcile expected cells, received records, duplicates and absent returns.
2. Classify execution outcomes and independently audit returned solutions against the original model, retaining M4/M12 and any additional numerical qualifications.
3. Determine eligibility separately for primal quality, dual bound, gap, time-to-target, resource use and predictive quality.
4. Present per-instance and per-class paired comparisons at the same target, clock and resource scope. Keep the prospective B/G speedup convention and explain its reciprocal relationship to historical G/B time ratios without rewriting historical records.
5. Report common-target attainment, exclusive attainment, neither-arm attainment, censoring and numerical ineligibility with explicit denominators. Interpret early primal improvement separately from later dual closure.
6. Compare serial/DDP time and quality only for matched work. Separate performance, speedup, efficiency, scaling, size effects and throughput.
7. Account for cold-use and reuse costs. Derive any break-even only under stated fixed-cost and positive recurring-saving assumptions; distinguish the historical seven-use scenario from an observed threshold.
8. Generate traceable tables and figures from qualified records and document the scope of each claim.

No fixed-seed result will be presented as evidence of seed robustness. Exclusion from learning does not by itself establish wholly independent generalization to hard instances, because historical exposure must be disclosed.

## 6. Planned tables, figures and appendices

| Object | Purpose |
| --- | --- |
| Table 1. Models and comparison roles | Original MILP, GNN, B/R/G and the separate conditional Benders framework; what changes and what stays common. |
| Table 2. Instance population and roles | E/M/H population, proposed parent-level split and evaluation cohorts; admission choices still pending. |
| Table 3. Experimental stages and controls | Workload, solver/training controls, artifact dependencies, experimental unit and release gate. |
| Table 4. Observations and analysis eligibility | Recorded quantities, clock/provenance, valid comparison and treatment of missing/censored data. |
| Table 5. Resources and unresolved decisions | Principal solves, preparation/training exclusions, reservation versus use, feasibility assumptions and decisions needed. |
| Figure 1. Research pipeline | The main sequence, validation-only decisions, provenance and the separate conditional decomposition branch. |
| Figure 2. GNN-to-Start-to-search mechanism | Where prediction, completion/repair, accepted incumbents, dual progress and costs enter the analysis; no unsupported causal arrows. |

Appendices will carry a notation glossary and equations; complete native-Gurobi parameters and observation limits; instance/split provenance; event and solution data dictionaries; budget derivations; conditional Benders proof; and the decision/evidence crosswalk. Reuse existing material through precise references rather than copying contradictory versions.

The separate Technical Gurobi Note will receive the same narrative treatment. Its main text will explain the accepted mechanisms, qualifications and architectural boundaries; the DOC/CODE/OBS/DEC inventory can remain as a concise traceability appendix. The note will remain a separate PDF linked to the protocol.

## 7. Mathematical rendering and editorial acceptance

Use proper inline mathematics for symbols and independent display blocks for derivations, ratios and inequalities. Define every symbol at first use, state units and index domains, and distinguish proportions from percentages. Explain objective sense, signs, assumptions and applicability before presenting a formula.

Keep one canonical mathematical source. Check the Markdown rendering and the PDF independently: a formula that compiles in LaTeX is not automatically well displayed on GitHub. Give displayed equations stable identifiers where cross-references improve comprehension. Embed fonts, repeat table headers across pages and prevent detached captions or clipped equations. Use vector diagrams or legible equivalent exports; do not substitute code listings for explanatory figures.

Acceptance requires a full prose pass; consistency with the unchanged decision/budget/evidence registers; no unresolved rendering markers; correct links and references; and visual inspection of every final PDF page. The two final PDFs must identify the exact PR99 source revision and be opened in Codex tabs for author review. Working previews should not be mistaken for the revised deliverables.

## 8. Checkpoint and first action after the pause

Current PR99 remains a methodological draft. Mathematical/Markdown formatting corrections are recorded now; the substantive narrative reorganization described above has not yet been implemented. No final PDFs are released in this checkpoint.

After the pause, first write the revised Introduction and Research Methods sections, reconcile their terms with the approved registers, and then continue the experimental, collection and analysis narrative. The final PDF build and complete visual QA follow the integrated rewrite. No new Sprint plan, experiment, HPC command, merge, public release or coauthor communication is implied.
