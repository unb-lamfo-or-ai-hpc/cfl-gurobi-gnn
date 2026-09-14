# Parent-level partitions

[instance_folds.py](instance_folds.py) and
[instance_partitions.py](instance_partitions.py) maintain the canonical five-fold
parent assignment. Partial inventories retain those assignments.

The current frozen 42-parent confirmation at rotation 0 has 24 training,
10 validation, and 8 test parents. Synthetic descendants inherit the parent's
fold and are train-only. Randomly splitting incumbent observations or descendant
graphs can leak parent information across roles and is not accepted here.

