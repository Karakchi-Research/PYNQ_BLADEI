# PRE-AUDIT RESULTS — PRE-DEDUP, HEADER-CONTAMINATED

Every result in this directory (`results.csv`, `summary.txt`, `cnn_results.csv`,
`cnn_summary.txt`, all `split_*.json` logs, and both feature caches) predates
the 2026-07-25 leakage audit (`../LEAKAGE_AUDIT.md`) and is subject to it:

- **Features are header-contaminated.** `features_cache.npz` and
  `sequences_cache.npz` were extracted from the whole file / sync-relative
  region, including the label-correlated `.bit` ASCII header, not from the
  FDRI configuration payload. Do not reuse these caches.
- **Grouped splits are duplicate-leaked.** 51–71% of each grouped test set is
  byte-identical (in configuration payload) to a training file. The `naive`
  and `grouped` rows are therefore not evidence of detection performance.
- **The `lofo` rows are the only uncontaminated regime** (0.0% exact-duplicate
  contamination, verified in `../leakage_audit_out/verify_split_leakage.json`).
- All figures sit under a Bayes ceiling of 0.9166 imposed by the 367 files
  whose identical payloads carry both labels.

These logs are retained deliberately: the Phase 0.5 rerun publishes its delta
against them. They must not be cited as performance results.
