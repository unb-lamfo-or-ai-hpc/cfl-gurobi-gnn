# Versioned experiment configuration

Configurations are research inputs, not convenience defaults to change after
observing test results.

- [splits](splits): the canonical [90-parent fold manifest](splits/cfl_90_seed42_folds.csv)
  fixes parent identity across partial inventories.
- [training](training): model versions, optimizer budgets, checkpoint selection,
  and sampling. [gasse_confirmation_v2.json](training/gasse_confirmation_v2.json)
  specifies corrected prenormalization, seed 42, and 100 epochs.
- [experiments](experiments): cohort, augmentation, and native guidance policies.
- [evaluation](evaluation): evaluation contracts and settings.
- [audits](audits): static recovery and methodological checks.

The current chain uses `gasse_pr57_54_v1.json` for training,
`pr58_validation_guidance_v1.json` for validation-only method selection,
`pr59_heldout_guidance_v1.json` for the frozen test benchmark, and
`pr60_scientific_evidence_v1.json` for synthesis. A later stage must verify the
hash of its upstream report and must not reinterpret an earlier configuration.

A file's presence is not evidence that its campaign has run. Record effective
configuration and source hashes in each plan. Preserve old budgets in separate
run directories; never edit a historical report to match a changed configuration.

