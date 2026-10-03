# Artifact schemas

[schemas.py](schemas.py) defines persisted feature structures and compatibility
contracts. Keep graph structure, root context, labels, solver trajectories,
and provenance distinguishable.

Names and serialized field keys are APIs, not prose to translate. Incompatible
schema changes require explicit versioning; comments must not disguise a
semantic change. Never reinterpret an old zero-ablation graph as a strict
real-root graph merely because its tensor dimensions match.

