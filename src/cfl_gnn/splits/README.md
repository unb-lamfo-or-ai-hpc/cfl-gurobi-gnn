# Parent-level partitions

[instance_folds.py](instance_folds.py) and
[instance_partitions.py](instance_partitions.py) maintain the canonical five-fold
parent assignment. Partial inventories retain those assignments.

The current PR #57 graph cohort at rotation 0 has 34 training, 10 validation,
and 10 test parents. The online solver benchmark uses six validation parents
for policy qualification and six test parents frozen by that qualification.
Synthetic descendants inherit the parent's fold and are train-only. Randomly
splitting incumbent observations or descendant graphs can leak parent
information across roles and is not accepted here.

