# Synthetic MIP augmentation

[local_branching.py](local_branching.py) defines explicit neighborhoods around
audited incumbent centers. [solver_backends.py](solver_backends.py) materializes
the operator through supported native interfaces.

A center vector is not a new instance. The resulting modified MIP has its own
hash, radius, provenance, independent label, and graph. Descendants inherit the
parent fold and remain train-only. The symmetric operator does not imply equal
labels or identical solve trajectories across solvers.

MIP gap and execution time belong to the source incumbent and the derived solve
as separate measurements. Do not substitute one for the other.

