# Graph transformation and access

The strict [gurobi_graph_artifact.py](gurobi_graph_artifact.py) route reads the
mathematical MIP with Gurobi, independently checks the label, aligns variable
identity, and encodes the real root-MIPNODE relaxation. It rejects missing root
evidence; there is no zero fallback on this route.

The variable–constraint representation uses seven variable features, five
constraint features, and one coefficient feature per edge. A graph represents
an original or synthetic MIP; solver-specific label views do not change its
structural identity.

[build_dataset.py](build_dataset.py) retains low-level encoding and a historical
incumbent-conditioned entry point. Its permissive historical behavior is not the
strict confirmation contract. [build_instance_dataset.py](build_instance_dataset.py)
supports earlier parent-baseline artifacts; migration requires provenance and
mathematical validation, not a filename change.

Graph EDA is implemented in [analysis](../analysis/README.md). Pickle/PyG files
must come from trusted sources.

