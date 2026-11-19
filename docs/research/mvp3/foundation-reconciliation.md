# Integral mathematical foundation: reconciliation

Date: 19 November 2026. The author authorized Appendix A incorporation and integration of PR97 into develop after verification. This record is outside journal prose.

The original Portuguese file is preserved byte for byte in source/; foundation-reconciliation.json binds its SHA-256 and the English translation and maps all nine sections. All original scientific subsections, equations, numerical examples, seven tables, memory discussion, caveats and references are retained. Favicon artifacts and URL tracking are omitted from the rendered translation only; they remain in the original.

## Technical qualifications

- Matrix notation explicitly distinguishes batched rows from individual-column message weights; incidence operators are mathematical notation, not allocated dense matrices.
- The root channel follows numerical sanitization and is not logarithmically transformed.
- Sigmoid outputs trained with weighted BCE are scores; probability calibration is not established.
- Incumbent binary membership and solver bounds are subject to the qualified numerical scope. A zero reported gap is not an exact proof. M4/M12 restrictions remain unchanged.
- Root capture is the first qualified optimal MIPNODE at zero explored nodes; it is separate from the main solve and does not use supervised labels.
- Historical 34 parents x four presentations x 100 epochs gives 13,600 presentations. A batch-one serial schedule has 13,600 updates; the later paired GPU experiment uses global batch four and 3,400 updates per arm. No result or update count is transferred to a future dataset.
- The width-32, two-layer model count is 448 + 2 x 12,608 + 1,089 = 26,753. Prenormalization buffers are not trainable parameters.

## Verification scope

Code inspected at 3700d90: models/gasse.py and gasse_calibrated.py; graph/build_dataset.py and gurobi_graph_artifact.py; training/gasse_reconnected.py; configs/experiments/pr87_matched_gpu_v1.json. Publication checks and render verify composition and presentation; they do not certify scientific validity. No scientific source, checkpoint, partition, evidence receipt or experimental parameter is changed.

The retrospective manuscript retains its original experimental results and time-ratio conventions. The prospective MVP3 speedup convention and new training are specified separately. The current authorization supersedes the earlier instruction to keep PR97 in Draft after the author review.
