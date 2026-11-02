<!-- Internal research record; excluded from article and journal supplements. -->

# Human–AI traceability: Appendix B decision for coauthor review

28 October 2026 · working material, not an approved journal appendix.
Read with the [accelerated plan](mvp2-20261028-accelerated-plan.md)
and [GNN audit](../../manuscript/supplement/gnn-methods-audit.md).

## Why document Human–AI collaboration here?

An AI assistant can propose code, interpretations or prose, but a plausible
proposal is not itself scientific evidence. A reader needs to know what was
checked, what the check established and who accepted the resulting claim.
Traceability connects those steps to records that can be inspected.

This is different from studying whether AI makes research faster or more
reliable. Such a study would need its own question, comparison design and
evidence. The present record concerns accountability within the CFL project;
it does not measure a causal benefit of Human–AI collaboration.

## Decision and scientific scope

**Adopt with reservations** as a description of how scientific decisions were
checked and retained. **Defer a full IIEA-S Appendix B** until the authors
confirm its definition, relevance, evidence and publication boundary.
The immediate deliverable is this compact decision/evidence register.
A short methodological note may be included after coauthor review; an
extensive collaboration study is not a prerequisite for CPU analysis.

The supplied assessments support transparent human responsibility and
traceability, not a new scientifically validated collaboration method.
Do not add IIEA-S to C1–C3 or claim productivity, accuracy or research-quality
improvements caused by AI. There is no controlled comparison, time-use
counterfactual or adequate independent set of collaboration episodes.
A merge, checksum, passing CI or generated explanation cannot establish
scientific acceptance.

The acronym and stages must be bound to an authoritative definition if used
in a publication. The supplied reports do not provide one unambiguous,
versioned six-stage definition; do not manufacture a mapping to P1–P6.
Refer to documented activities in plain language until that is resolved.
This is a scope decision for the draft, not a change to the agreed AI-use
declaration, authorship or responsibility statement.

## Evidence register to complete from existing records

Candidate episodes below were identified in the supplied October23 assessments.
They are review candidates, not four completed case studies.

| Episode | Existing primary repository evidence | What it may document | Missing acceptance / qualification |
| --- | --- | --- | --- |
| PR85 formulation and model bindings | [PR85 closure](pr85-closure.md), mathematical signatures and source/model receipts | Detection, diagnosis and explicit preservation of model identity under the human MINIMIZE decision | Link exact dated human decision and its scope before attributing the decision to a collaboration stage |
| PR86 M12 numerical sensitivity | [Final CPU analysis](pr86-final-analysis.md), original and diagnostic-vector audits | Distinction between solver acceptance, rounded-vector feasibility and scientific metric eligibility | Explicit author acceptance of the final bounded interpretation; do not reopen formulation certification |
| PR87 adverse GPU quality | [Completed-pair review](pr87-completed-pair-review.md), histories, matched loss and returned metrics | Faster training with lower selected F1 retained visibly | Evidence of scientific review, not merely CI or a merged implementation |
| PR88 methodological redirection | [D1 protocol](methodology-20261019/D1-protocol.md), [D5 contributions](methodology-20261019/D5-contributions.md), figure manifests | Separation of clocks, censoring, parent units and contribution limits | Bind the actual human decision that accepted each interpretation and show alternatives without rewriting history |

For an eventual appendix, each accepted row needs: date, trigger, original
question, existing artifact identity, AI-assisted proposal, independent check,
human decision with an accessible primary reference, and the consequence
for the article. Missing fields stay “not documented”. Do not export private
chat histories, credentials, licenses, paths or coauthor communications.
Public sanitized decisions can be referenced where already available.

## Four questions about validation

A passing software test answers a narrower question than a scientific review.
For example, a table can be generated correctly from a file while its comparison
still uses an inappropriate population or endpoint. Separating the following
questions helps make such gaps visible.

| Level | Required question | Evidence boundary |
| --- | --- | --- |
| V1 functional | Did the relevant implementation/check run as intended? | Source review, appropriate tests and receipts; not universal software correctness |
| V2 mathematical | Did the model/interface preserve the intended quantities and feasible region? | Signatures, explicit MINIMIZE convention and scoped numerical audits |
| V3 experimental | Are population, work, inputs, resources, clocks and outcomes comparable for the named analysis? | Existing protocol and returned evidence, including failures and censoring |
| V4 scientific sufficiency | Does that evidence support this exact claim and its limitations? | Specialist interpretation and coauthor decision; not inferred from V1–V3 |

An episode can satisfy one level while another remains partial or unavailable.
No aggregate “validated by IIEA-S” score is proposed. Validation levels do
not create a renewed benchmark-semantic gate or authorize another experiment.

## Candidate short note — not yet inserted in the manuscript

> AI-assisted code and manuscript work was reviewed through versioned source,
> experiment receipts and claim-specific checks. Functional tests, preservation
> of the mathematical model, experimental comparability and scientific
> interpretation were considered separately. Adverse findings and unresolved
> limitations were retained. Scientific decisions and responsibility remained
> with the authors. This process is documented for traceability; it is not
> evidence of a causal improvement in research productivity or validity.

The final wording must reflect actual author review. Do not claim that a
future review has already occurred. The existing journal AI declaration is
preserved verbatim in this PR.

## Inclusion criteria and disposition

Use a short methods note if it helps a reader understand evidence provenance
without displacing the optimization contribution. A detailed Appendix B
requires all of: an agreed source definition, completed primary-decision
links for the selected episodes, a precise purpose for COR readers, privacy/
rights clearance and coauthor approval of wording. If these remain absent,
retain the register as repository working material and omit the appendix
from the submission. No new empirical Human–AI research is needed for MVP2.

The full repository/article/appendix audit remains mandatory after PR89
collection and qualification. This register prepares that audit; it does
not certify the pending campaign or the final manuscript.
