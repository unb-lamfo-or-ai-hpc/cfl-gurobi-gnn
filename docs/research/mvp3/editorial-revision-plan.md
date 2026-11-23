# Editorial reconciliation of the annotated protocol

The23 November 2026 revision incorporates62 annotation records from the researcher's 13-page PDF. The source-file digest and original annotation extraction are preserved locally. The [English disposition register](annotation-disposition-EN.csv) maps each record to the revision. Empty continuation highlights are linked to their associated paragraph treatment.

## Completed changes

The protocol now uses affirmative scholarly prose and explains the research pipeline in self-contained sections. It includes the scientific motivation for the new Gurobi 14 reference, independent feature/label runs, an independent R proposal, Start-processing evidence, conditional Benders, and a fully specified analysis pipeline. Tables and figures have introductory text and interpretation; the bibliography precedes the appendices, and manual/source URLs appear in footnotes or references.

The population is66, the learning split42/9/9, and final evaluation15parents/45cells. The full primary budget includes66 root-relaxation calls,66 incumbent calls and45 evaluation calls:177 calls,1,416 maximum solver-hours and2,124 reserved job-hours. Historical easy runtimes and matched training times support explicitly conditional working scenarios. The two-job/two-session ceiling and exclusive-node resources are stated separately from observed use.

S1-S6 now have explicit planned PR packages, acceptance artifacts and a working calendar. Temporary compatibility/migration results, incident commentary, chat references and release-status prose have been removed from the coauthor protocol. Those operational records remain in their separate dossier and machine handover.

## Scientific clarifications retained in the rewrite

- Presolve and cutting planes have distinct controls; root-event provenance identifies the captured relaxation.
- MIPFocus=1 and feasibility heuristics support incumbent discovery; the feature profile and main paired contract retain their own specified purposes.
- The recorded Intel node topology is32 physical cores/64 logical CPUs; the memory-class suffix denotes the node class.
- An unsuccessful Start message has multiple explanations; partial completion and main-solve benefit have separate evidence categories.
- The supplied Benders paper is verified as Haq, Chaerani and Triska(2025), resolving the later author/year shorthand in the annotations.
- Method time ratios use T_B/T_G and T_R/T_G, with values above one favouring G; training-system speedup retains T_serial/T_DDP and its separate resource-scaling scope.

## Review decisions

The [decision register](decisions-and-budget.json) makes the proposed label tier, balanced split allocation, training schedule, predictor selection, R/G support settings and conditional diagnostic budget explicit. Their presence in the revised plan is a proposal for coauthor review, not a claim that experiments have been released. PR #99 remains Draft. The revision executes no solver, training, inference or HPC commands.

## Final researcher-approved addendum

The researcher approved the methodological plan and requested a final expansion of Gurobi14 feasibility diagnostics. The revision explains the roles of MIPFocus, heuristic budgets, traditional/in-tree NoRel, PDHG-based incumbent search and partial-Start completion limits. GRBLogTools receives an explicit secondary offline role, field/clock reconciliation procedure and release-specific coverage record. Documentation URLs appear in footnotes. The accepted population,177-call primary budget,comparison profiles and S1-S6 sequence are unchanged. No parser installation or execution occurred.

## Version 3: time-ratio decision and presentation reconciliation

The researcher resolved slide 34 by adopting comparator/G speedup factors. Equations, examples, paired-outcome categories, end-to-end and reuse reporting, the evidence contract and handover now use that orientation. The presentation review covers all 42 slides; the separate reconciliation record supplies slide-level replacement guidance. StartNodeLimit is explained with its default inheritance. Break-even equality and positive-time eligibility are explicit. Scientific arms, budgets and execution gates are unchanged.
