# Presentation reconciliation against protocol version 3

Date: 23 November 2026. Source: CFL_GNN_MVP3_Protocolo_Coautores_ES_20261123.pdf, 42 slides. All slide text and rendered pages were inspected. The supplied presentation remains an unchanged source; this record gives the revisions to apply to its next edition. The English methodological protocol and its supporting contract implement the changes listed below.

## Resolved time convention

The researcher has selected speedup-style time factors: S_B/G = T_B/T_G and S_R/G = T_R/T_G. A value above one favours G, one indicates equal measured time and a value below one favours the named comparator. This decision supersedes the reciprocal convention in protocol version 2. It applies to comparable target-attainment times, end-to-end elapsed times and cumulative elapsed-time reuse costs. It changes representation, not the original observations or scientific conclusions.

Each reported factor identifies its quality target, clock, eligible cohort and denominator. Common qualified attainment and positive observed times are required. Censoring limits do not become observed solution times. A signed saving is T_comparator - T_G, so a positive saving favours G. Existing factors must be inverted individually and the summaries recomputed from paired times; an old arithmetic mean cannot simply be reciprocated.

## Slide-level findings

| Slide(s) | Finding | Revision for the next presentation | Protocol disposition |
| --- | --- | --- | --- |
| 34 | The presentation correctly identifies the reciprocal conventions, but the orientation is now decided. | Replace the pending-choice slide with the two approved factors, their direction and a matched-target example. Suggested replacement text follows below. | Section 6.2, equation 5, table 12 and examples revised. |
| 41-42 | The closing decision lists still describe ratio orientation as unresolved. | Mark the orientation as approved by the researcher. Retain coauthor scientific discussion, coverage decisions and concrete release gates as separate matters. | Approval record and handover retain the decision. |
| 35 | The paired-outcome table names only B and G. R/G needs the same attainment and censoring rules. | Use C for comparator, C in B/R, and show C/G. Retain a separate eligible cohort for each contrast. Include time-zero ineligibility without replacing the measured value. | Table 12 generalised; evidence contract expanded. |
| 37 | “Round to the next integer” can imply adding one when the quotient is already integral. The slide also lacks an explicit G-oriented cumulative factor. | Use the mathematical ceiling. State that equality is break-even and strict benefit requires G's cumulative cost to be smaller. Report C_B(k)/C_G(k) and C_R(k)/C_G(k) for positive comparable elapsed-time costs. | Section 6.4 clarifies the ceiling, equality and cumulative factors. The 600/100 example breaks even at six uses. |
| 38 | The training speedup T_1/T_4 is already oriented correctly. GPU efficiency has a different denominator. | Retain T_1/T_4 and speedup/4. Explain that speedup above one favours DDP; efficiency need not exceed one for DDP to be faster. These are training-system metrics, not B/G outcomes. | Section 6.5 clarifies the distinction and consistent orientation. |
| 24-25 | Slide 24 labels 64 CPUs as cores and presents capacity/planning envelopes as user quotas. Slide 25 correctly states 32 physical cores/64 logical CPUs. | Replace “2 nodes x 64 cores” with the declared planning envelope: at most two jobs, 32 physical cores/64 logical CPUs per selected Intel node. Keep hardware RAM, requested RAM and actual association/QoS quotas separate. The protocol's two-job/two-session ceiling is not proof of a scheduler entitlement. Use the requested 192/384 GiB envelopes for this programme. | Protocol sections 3.4 and 4 already distinguish topology, allocation and effective release checks. No migration narrative added to the coauthor protocol. |
| 28 | The 29.7-day solver scenario and 44.5-day reservation scenario use stage waves; the 19.9-day figure is an ideal two-slot lower bound. | Label 33+33+23=89 waves: 89 x 8/24=29.67 days; 89 x 12/24=44.5 days. Label 956.25/2/24=19.92 days as a lower bound before barriers, queues and ancillary work. | Arithmetic verified; no budget change. |
| 11 | Three diagnostic families are compressed together; StartNodeLimit appears without its inherited default. | Distinguish in-tree NoRel, traditional pre-root NoRel and PDHG incumbent search. State that StartNodeLimit=-1 inherits SubMIPNodes; completion time/work limits are separate. Keep all these explanations separate from the fixed principal solver profile. | Diagnostics subsection and manual footnote now include StartNodeLimit; existing v2 explanations and GRBLogTools coverage checks retained. |
| 18 | Thresholds appear immediately after a confidence score, which can obscure the quantity being thresholded. | State explicitly: select root values or neural probabilities <=0.1 or >=0.9, then rank by absolute 2v-1; keep at most 10% of eligible binaries. Preserve the declared independent R/G policies. | Existing section 2.4 already identifies values/probabilities, ranking and support. No new tuning rule introduced. |
| 33 | The gap formula is shown without its zero-primal or missing-incumbent cases. | Add a short note: zero primal and equal dual gives zero gap; zero primal and unequal dual follows the native infinite-gap convention; no incumbent is an availability category. | Existing section 6.1 already states these cases. |
| 7-8, 21, 36 | The presentation distinguishes observed root relaxation from a cut-free LP, conditional Benders from the main design, and primal progress from dual closure. | Retain those distinctions. Hard transfer is evidence on the six selected parents and does not establish population-wide generalisation. | Existing protocol provisions retained. |

The numerical study remains 66 characterisation instances, 60 learning parents, 42/9/9 split, 15 evaluation parents and 45 fresh B/R/G evaluation cells. The primary ledger remains 177 optimisation calls, at most 1,416 solver-hours and 2,124 reserved job-hours. Review of this presentation does not add an experimental arm, a new run or a resource release.

## Replacement copy for slide 34

**Title:** Time comparisons: a single speedup convention

**Baseline comparison:** S_B/G = T_B/T_G

**Relaxation comparison:** S_R/G = T_R/T_G

**Interpretation:** Above 1 favours G; 1 means equal measured time; below 1 favours B or R.

**Matched-target example:** B = 180 s, R = 150 s, G = 120 s gives S_B/G = 1.50 and S_R/G = 1.25.

**Reporting rule:** Use the same qualified target and clock. Report censored outcomes and attainment counts separately. Include preparation in an explicitly labelled end-to-end comparison.

## Documentary sources

- Protocol version 3, sections 2.2, 2.4, 3.4, 4 and 6; decision register and evidence contract.
- Gurobi 14 parameter manual, StartNodeLimit: https://docs.gurobi.com/projects/optimizer/en/14.0/reference/parameters.html#startnodelimit.
- Gurobi 14 parameter manual, StartTimeLimit and StartWorkLimit: https://docs.gurobi.com/projects/optimizer/en/14.0/reference/parameters.html#starttimelimit and https://docs.gurobi.com/projects/optimizer/en/14.0/reference/parameters.html#startworklimit.

No solver, training, parser installation, HPC command, merge or publication was executed in this documentary reconciliation.
