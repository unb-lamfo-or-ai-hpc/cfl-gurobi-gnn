# Independent mathematical validation

[mathematical.py](mathematical.py) checks named-variable coverage, finite values,
bounds, integrality, linear rows, and objective reconstruction, including the
objective constant. All CFL models use effective MINIMIZE while preserving
their original declaration.

Feasibility, optimality, and provenance are distinct. A feasible incumbent with
a nonzero gap is not a proven optimum; a zero gap field without trustworthy
solver provenance is not a certificate. Native and common gap definitions must
remain explicitly identified.

This module's implementation hash participates in experiment contracts. Even
comment edits require a new fingerprint; do not mutate the code behind an
active campaign.

