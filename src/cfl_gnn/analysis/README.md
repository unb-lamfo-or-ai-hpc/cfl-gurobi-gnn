# Descriptive analysis and audits

[parent_collection_audit.py](parent_collection_audit.py) reports parent coverage,
solver gaps, four timing regions, and incumbent trajectories.
[graph_statistics.py](graph_statistics.py) and
[graph_clustering.py](graph_clustering.py) consume hash-bound graph manifests.

Graph projections use outcome-free encoded descriptors, not learned GNN
embeddings. Labels and solve outcomes must not enter PCA/clustering inputs or
select partitions. Rank deficiency and degenerate projections must be disclosed;
a parseable SVG is not evidence of meaningful separation.

Node-state feasibility probes and historical MVP output modules remain separate
research artifacts. Their gates have bounded meanings. In particular, the old
[collection_audit.py](collection_audit.py) computes summary statistics from
legacy trajectories; its minimum recorded callback gap must not automatically
be interpreted as a terminal solver gap. Current paired reporting uses the
versioned parent collection audit.

All publication summaries require reviewed cohort counts, units, missingness,
censoring, and sanitization, in addition to hash checks.

