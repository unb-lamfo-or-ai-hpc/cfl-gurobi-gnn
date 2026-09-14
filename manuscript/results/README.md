# Reviewed empirical evidence

The final delivery archive SHA256 is `8b517e30f8943420027e4c351cffb22b6ec53e30f38bd64193f7d8896b399935`. Its 62 manifest-listed files passed packaged-hash verification.

`confirmation_final.json` is the derived consistency audit. The epoch, per-parent, per-difficulty, calibration and graph CSV files are byte-preserving copies from that archive. `graph_clustering_report.json` records projection semantics. `source_evidence.json` preserves the earlier source-rejection extract, including its historical null training fields; current results are exclusively in the final audit and final CSV files.

The asset hashes in `../evidence-status.json` bind the publication inputs. Rendering produces measured figures from these files without training or optimization. No synthetic loss curves, inferred ROC/PR curves or unexecuted solver effects are included.

Scope is supplied-evidence consistency, not raw-artifact reexecution. Graph tensors, root vectors, labels, checkpoint binaries and predictions were not transferred for this audit. Full ROC and precision-recall CSV files exceeded the transfer size limit. Their area summaries remain receipt-reported values.

Original project-generated tables and figures use MIT within the authors' rights; upstream data rights are unchanged.
