# Versioned research evidence

Retain small public-safe JSON summaries, evidence inventories, bounded tables,
decisions and source hashes here. A commit or passing test is not proof that a
cluster experiment completed. Keep adverse and incomplete outcomes traceable.

Do not commit private host paths, raw logs, credentials, operational packages,
large tensors, LP collections or checkpoints. Raw MILPBench inputs are not
redistributed. Private research artifacts stay in hash-bound archival storage.
Each public summary has its own digest and references the private source digest;
its bytes are not claimed to equal the private source. Hash identity does not
establish scientific validity or binary privacy.

The [MVP 1.0 baseline](mvp1/README.md) summarizes the completed private freeze.
Subsequent experiment PRs should include bounded summaries after evidence gates
close. New work enters feature branches with PR base `develop`; main and public
Pages remain the experimental MVP 1.0 baseline until a later promotion decision.
