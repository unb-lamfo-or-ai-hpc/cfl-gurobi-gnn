# Research hypotheses and evidential interpretation

These propositions formalise the questions already in the approved protocol. Scientific acceptance depends on valid evidence and scoped interpretation, including neutral or adverse outcomes; it does not require G to outperform its comparators.

## H1. C2

Neural guidance can reduce time to a specified quality target relative to native baseline B on some evaluated instances.

Reference: S_B/G = 1 means equal elapsed time; S_B/G > 1 favours G.

Evidence: Qualified paired target times and G-only/B-only attainment counts at 10%, 5%, 1% and 0.01%.

Interpretation: Conditional within the 15 selected original parents and single prescribed seed/configuration; no universal-superiority requirement. Protocol sections: 6.2-6.3.

## H2. C2

Neural guidance can add computational value relative to the independent relaxation-based comparator R.

Reference: S_R/G = 1 means equal elapsed time; S_R/G > 1 favours G.

Evidence: Qualified R/G target times, attainment, support and Start-processing evidence under the same MILP contract.

Interpretation: R is generated independently of G; this comparison examines the complete guidance procedures and does not isolate a unique causal learning effect. Protocol sections: 2.4, 6.2-6.3.

## H3. C2

The relative ordering of B/R/G can vary with the gap target and with primal versus dual progress.

Reference: Stable ordering across targets is a descriptive reference, not an assumed law.

Evidence: Within-parent four-target trajectories, qualified incumbents, bounds, presolve/root work and search effort.

Interpretation: Association-based explanation; targets are repeated views of the same run rather than independent solver replications. Protocol sections: 5.2, 6.3.

## H4. C3

A solver-time benefit can be offset by preparation, while reusable artifacts can make a conditional elapsed-time saving possible.

Reference: C_G(k) = C_B(k) or C_R(k) is break-even; comparator/G cost factor > 1 favours G.

Evidence: Nested timing ledger, reusable preparation, recurring per-use costs and explicit reuse assumptions.

Interpretation: An accounting proposition under a stated scenario; theoretical break-even is not observed deployment evidence. Protocol sections: 6.4.

## H5. Learning system

Four-GPU DDP can shorten training elapsed time relative to serial training when global work is held equivalent.

Reference: T_serial/T_DDP = 1 means equal elapsed time; values > 1 favour DDP.

Evidence: Matched 4200-update returns, parent-level validation/predictive measures, clocks, GPU-hours and memory.

Interpretation: One controlled training pair; no new non-inferiority margin, repeated training campaign or causal quality-loss assertion. Protocol sections: 2.3, 6.5.

## Shared analysis boundary

The original instance is the inferential unit. The four gap targets and B/R/G runs are paired/nested observations. A single prescribed solver seed and one matched training pair do not provide independent random replications. Report per-instance trajectories, target-specific attainment, eligible paired factors and resource/cost scopes. The preparation adds no statistical test or population-level significance claim. Any later extension requires an explicit methodological revision.
