# BLADE-I Research Plan: Trojan Localization

Approved 2026-07-18. Amended 2026-07-25 after the leakage audit (see below).
Governing rules (see project instructions): grouped splits only,
frame-aligned windows (404-byte 7-series config frames), no SMOTE on raw bytes,
every experiment logs split/seed/window/model config, global and windowed pipelines
stay side by side, Claude never commits.

> **2026-07-25 — LOCALIZATION IS GATED.** An independent four-part audit
> (`LEAKAGE_AUDIT.md`, logs in `leakage_audit_out/`) confirmed that the benchmark
> as currently used does not support the experiments in Phases 2–4. The 1,383
> files hold **431 distinct configurations** (36 benign); **51–71% of every
> grouped test set is byte-identical to a training file**; **20% of malicious
> bitstreams are byte-identical to a benign build**; and the shipped window grid
> is **misaligned from real configuration frames by 184 bytes**. Phase 0.5 below
> is a prerequisite for Phases 2–4, not an optional cleanup. No localization
> result produced before Phase 0.5 completes should be reported.

Standing decisions:
- **Tail bytes** form a partial final window, flagged with its true byte count in
  window metadata — never zero-padded, never dropped.
- **Clean-variant differential** comparison (trojaned build vs. clean P&R variants of
  the same design) is exploratory/diagnostic only. P&R noise between variants makes it
  unsuitable as localization ground truth; Phase 2 pinned placement is the ground truth.
- **Per-benchmark grouping is the default split** and supports "detection on known
  host designs" claims only. Any generalization-to-unseen-designs claim must use the
  leave-one-family-out split: benchmarks within a family share the same host design
  (AES_T100 vs AES_T400), so a per-benchmark split still exposes the host circuit to
  training. Build-directive tokens (`_d<k>`) are P&R variants of the same design and
  always group with their parent benchmark (confirmed 2026-07-19).
  **SUPERSEDED 2026-07-25:** per-benchmark grouping is necessary but not
  sufficient. Design keys are disjoint on every seed (verified), yet 56 payloads
  span more than one design key — one spans 25 — so 51–71% of each grouped test
  set is an exact copy of a training file. The default split becomes the
  **payload-aware grouping** defined in Phase 0.5.
- **The unit of data is a distinct configuration, not a file** (2026-07-25).
  Report N as unique payloads. This checkout holds 431 (140 excluding ISCAS85),
  against 1,383 filenames.

## Phase 0 — Split audit

Verify — don't assume — that splitting is group-wise on the real dataset.

- [x] Code read: `grouped_split_indices` (split_utils.py) groups by `design_name()`
      via `StratifiedGroupKFold` with hard disjointness asserts on train/val/test
      (verified 2026-07-18).
- [x] `test_splits.py` includes a no-design-on-both-sides test across 5 seeds
      (synthetic filenames).
- [x] Audit `design_name()` against the *real* Trust-Hub filename list
      (2026-07-19, `audit_design_groups.py`, log in
      `split_audit_out/design_group_audit.json`). The old `split("_")[0]`
      fallback misfired on every real name (real layout is
      `<design>_T<nnn>[_d<k>][_v<k>][_Trojan]` with `_Trojan`/`_v<k>` in either
      order); fixed: design key = everything up to and including the `_T<nnn>`
      benchmark token, regex tested on real filenames in `test_splits.py`.
      Result: 1089 files, 85 groups, no singletons, every key present in both
      Benign and Malicious. Sizes: 78×10, 4×20 (EthernetMAC10GE `_d2` builds),
      2×110 (`b19_T100`/`b19_T200`: builds `_d2`–`_d11` × 5 P&R variants × 2
      classes — same design rebuilt under different directives, correctly one
      group), 1×9 (`b15_T300`: one malicious variant missing from the dataset).
- Note: `b15_T300` is missing one malicious P&R variant in this checkout
  (545 benign vs 544 malicious files) — dataset gap to reconcile with the team.
- [x] Dataset manifest logged to `split_audit_out/dataset_manifest.json`
      (2026-07-19, per-family file counts + SHA-256 checksums). This checkout
      holds 1,089 files vs. 1,383 in the paper — reconcile with the team.
      Per-family: CRYPTO 290, COMMS 330, MCU/CPU 40, BUS/DISPLAY 40, ITC99 289,
      ISCAS89 100, **ISCAS85 0 — the entire family is missing from this
      checkout**, which plausibly accounts for most of the 294-file gap.
      Consequence: leave-one-family-out currently covers 6 families, and no
      ISCAS85 generalization claim can be made from this checkout.
- [x] Split-regime comparison, measurement only (2026-07-19,
      `split_comparison.py`; results + 40 per-run split logs in
      `split_comparison_out/`). Existing statistical classifiers
      (stat_baseline config: RF + LogReg on the 278 global features, features
      via train_model's original code path) under three regimes, seeds 0–4.
      **PRE-AUDIT NUMBERS — PRE-DEDUP, HEADER-CONTAMINATED (2026-07-25):**
      features were computed over the whole file including the label-correlated
      ASCII header, and grouped test sets contained 51–71% byte-identical
      copies of training files. Retained only for the Phase 0.5 delta
      comparison; not citable as performance.
      | regime | RF Bal.Acc | LogReg Bal.Acc |
      |---|---|---|
      | naive per-file 80/20 (old) | 0.871 ± 0.010 | 0.877 ± 0.017 |
      | grouped per-benchmark | 0.916 ± 0.036 | 0.899 ± 0.027 |
      | leave-one-family-out (6 fams) | 0.473 ± 0.102 | 0.584 ± 0.140 |
      Findings: (1) LOFO collapses to ~chance — per-family balanced accuracy is
      0.50 for most held-out families, with the model predicting one class for
      the whole family. No generalization-to-unseen-designs claim is supportable
      from the statistical features; consistent with the standing decision.
      (2) ~~Grouped is not worse than naive here (slightly higher, overlapping
      spreads) — file-level leakage does not inflate the *statistical* classifier
      on this data~~ **RETRACTED 2026-07-25.** This inference does not hold. Both
      regimes leak at comparable rates (naive by construction; grouped at
      51–71% exact-duplicate contamination, Finding 3), so their agreement is
      not evidence that leakage is absent. LOFO is the only regime measured that
      is free of exact-duplicate contamination (0.0% on all 7 held-out families)
      — which reframes its ~chance result as the only clean number in the table,
      not as the pessimistic outlier.
      Real-data disjointness held across all grouped seeds (hard asserts in
      `grouped_split_indices` passed) — and still holds; the asserts are correct,
      the equivalence class they enforce is not the one that matters.
      (3) All Phase 0 accuracy numbers, statistical and CNN, are additionally
      subject to a Bayes ceiling of **0.9166** imposed by label contradictions
      (Finding 4). The reported grouped RF figure of 0.916 sits at that ceiling.
- [x] Hybrid-CNN split-regime comparison (`cnn_split_comparison.py`, summary in
      `split_comparison_out/cnn_summary.txt`, 5 seeds). **Same pre-audit
      caveats as the table above — pre-dedup, header-contaminated:**
      naive 0.8954 ± 0.0214, grouped 0.8532 ± 0.0817, lofo 0.5579 ± 0.0932.
      Consistent with the statistical classifiers: grouped ≈ naive (both
      leaked), LOFO near chance (the only uncontaminated regime).
- [x] Pre-audit output directories labeled on disk (2026-07-25):
      `PRE_AUDIT_NOTE.md` placed in `split_comparison_out/` and
      `cnn_experiments_out/` so the logs cannot be mistaken for
      leakage-controlled results.

## Dataset provenance (standardized 2026-07-19)

- **Canonical dataset**: `trusthub_bitstreams.tar.gz.enc` from the BLADE-I GitHub
  v4.0.0 release (sha256 `be7f831d8ee4fa78615439501823618915c3ea49b610372d1f785891a4af613f`,
  verified against the GitHub asset digest), decrypted and extracted to
  `~/Desktop/Karakchi-Research/trusthub_bitstreams_v4/` — **1,383 bitstreams,
  matching the paper**. Config (`audit_design_groups.FALLBACK_DATA_DIRS`) and the
  invariant test now resolve to this path only; `--data-dir`/`BLADEI_DATA_DIR`
  remain as explicit overrides for lab machines.
- **Before/after**: the previously used copy (`.../trusthub_bitstreams/`, extracted
  Feb 2026, predating the Apr 2026 release) is a strict subset — all 1,089 files
  bit-identical to their V4 counterparts (SHA-256 verified), zero files unique to
  it. V4 adds exactly **294 ISCAS85 malicious bitstreams** (TRIT-style names,
  `c1355-CS320.bit` … across hosts c432–c7552), with **no benign ISCAS85
  counterparts and no P&R variants** (one file per trojan insertion).
  `b15_T300`'s missing malicious variant exists in the canonical archive too —
  an upstream gap, not a local loss. Old manifest preserved as
  `split_audit_out/dataset_manifest_pre_v4.json`; canonical manifest regenerated.
- **Consequences for the Phase 0 rerun** (not yet executed): ISCAS85 becomes a
  malicious-only, variant-less family — 294 singleton design groups, a
  benign/malicious imbalance (545/838), a naming convention `design_name()`
  handles via its fallback (full stem = one group per file, host-design sharing
  within ISCAS85 only captured at the family level), and a family whose
  leave-one-family-out split has no benign test files (recall-only evaluation).
  All Phase 0 numbers (audit, split comparisons incl. the CNN run) predate this
  change and are tagged to the pre-V4 manifest.

## Phase 0.5 — Leakage-controlled protocol (PREREQUISITE for Phases 2–4)

Added 2026-07-25. Rationale and evidence: `LEAKAGE_AUDIT.md`. Nothing in
Phases 2–4 may be reported until every box here is ticked.

**STATUS (2026-07-25): Phase 0.5A COMPLETE — the GATE REMAINS OPEN.**
Phase 0.5A (everything ticked below: leakage-controlled extraction, corpus
indexing, deduplication, quarantine, corrected splitting, remeasurement) is
done. Phases 2–4 stay gated pending Phase 0.5B:
1. ~~independent header/metadata-leak verification to the audit standard~~ —
   done 2026-07-25 (Finding 5, CONFIRMED; see checklist below);
2. a successful controlled rebuild pilot (matched benign/malicious builds,
   trojan retention verified, distinct FDRI payloads under supported
   implementation settings) — **prepared but BLOCKED 2026-07-25**: no local
   Vivado (macOS), and both build hosts (higgs, meson) have TCP/22 filtered
   from the current network, so Vivado 2023.2 could not be confirmed and no
   build was attempted (no version substitution permitted). Design
   selection, procedure, success criteria, and the environment-capture
   script are ready in `rebuild_pilot/` (see `REBUILD_PILOT_REPORT.md`);
   unblocking requires campus network/VPN access;
3. a plan for expanding matched, trace-bearing configurations to a corpus
   size that supports estimable grouped splits (the pilot's diversity
   measurement is the evidence-gathering step for this plan).

- [x] Independent verification of all four findings, one self-contained script
      per finding, each deriving and asserting the bitstream geometry itself
      rather than sharing a parser; equality decided by exact byte comparison,
      never by a hash. `verify_frame_alignment.py`, `verify_payload_dedup.py`,
      `verify_split_leakage.py`, `verify_label_contradictions.py`; logs in
      `leakage_audit_out/`. **All four CONFIRMED** (2026-07-25).
- [x] **Extract from the FDRI payload** (2026-07-25, `bitstream_io.py`).
      General packet-derived parser (derives offsets/counts/blocks/FAR, assumes
      nothing) + strict `ZYNQ7020_V4` canonical profile that the controlled
      path validates against and fails on deviation; V4 constants live only in
      the profile so partial bitstreams stay supportable. Corrected extractors
      (`extract_statistical_features_fdri`, `extract_byte_sequence_fdri`)
      consume the payload only; 278-dim layout kept for schema stability
      (`fdri_stat_278_v1`) — shape/API compatibility only, never
      checkpoint/scaler compatibility. `window_features.payload_region()` now
      returns the profile-validated payload (offset 0 = frame 0 byte 0).
      **Decision A: `train_model.py` and `deploy_model.py` are FROZEN**
      pre-audit reference implementations — deliberately not patched, so the
      pre/post delta stays reproducible. Tests: `test_bitstream_io.py`
      (synthetic parser ground truth, profile accept/reject,
      payload-only feature isolation, frozen-semantics equivalence,
      fail-closed caches), `test_window_features.py` (real-file alignment:
      10,008 frames, 1,251 full windows, zero partial).
- [x] **Payload-aware grouping** (2026-07-25, `split_utils.py`).
      `payload_aware_grouped_split_indices(...)` — explicit corrected path,
      schema `payload_component_v1`; legacy `grouped_split_indices` unchanged
      for pre-audit reproduction. Components = connected components of
      (shared design key ∨ shared exact payload), payload ids precomputed by
      the corpus index (no hashing in split logic). Asserts per side pair:
      design, payload class, alias, and component disjointness; refuses
      quarantined inputs. `log_split_v2` records schema/seed/physical/unique/
      component/class/family counts + exclusions + manifest id. Tests in
      `test_splits.py` include the cross-design shared-payload case.
- [x] **Corpus index — one distinct configuration payload is the primary
      sample unit** (2026-07-25, `corpus_index.py` →
      `corpus_out/corpus_index.json`, manifest `e680fc728129d5d2`).
      Doubles as the all-corpus profile audit (all 1,383 files conform);
      digest clusters confirmed by exact byte comparison (952 comparisons, 0
      mismatches); aliases tracked per payload class; one canonical sample
      per unique payload; totals cross-checked against the independently
      verified audit (431 unique = 36 B / 395 M; 306 components) — build
      aborts on disagreement. Primary metrics are computed over unique
      payloads; file-weighted numbers are secondary by decree.
- [x] **Quarantine the 169 contradictory malicious files** (2026-07-25,
      `leakage_audit_out/quarantine_contradictory.json`). All 11 contradictory
      classes with full membership (367 files), every quarantined malicious
      alias with its benign twin(s) and retained benign representative,
      exclusion reason `no_bitstream_trace` — reported as a dataset finding,
      history preserved, nothing silently deleted. The corrected split path
      refuses quarantined inputs; run logs record exclusion counts.
- [x] **Decide ISCAS85** (2026-07-25): **excluded from the primary Phase 0.5
      supervised table**, explicitly logged in every run (not silently
      skipped). Reasons: no benign counterpart in this checkout, built under
      Vivado 2025.2 vs 2023.2 for everything else, and single-class hold-out
      accuracy is not a comparable result. ISCAS85 stays in the corpus index,
      manifest, and audits. A matched benign/malicious rebuild under the
      canonical Vivado version is required before it enters the primary table.
- [x] **Independently verify the header/metadata leak** (2026-07-25,
      `verify_header_leak.py` → `rebuild_pilot/header_leak_verification.json`;
      LEAKAGE_AUDIT.md Finding 5 addendum). CONFIRMED: label determined by
      header length/file size for 544 files, by tool-version for all 294
      ISCAS85, by design-name field for 250; legacy whole-file features
      differ on byte-identical payloads (10–17 dims) while corrected FDRI
      features are exactly identical. Exploitability under the
      duplicate-safe component split: size-only 0.635 full corpus,
      ≈ chance excl. ISCAS85 — the earlier exploratory 0.774/0.751 were
      measured under the duplicate-leaked design-grouped split and are
      superseded.
- [x] **Re-run Phase 0 under the corrected protocol** (2026-07-25,
      `phase05_stat_comparison.py` → `phase05_out/stat_results.csv`,
      per-run logs in `phase05_out/runs/`, seeds 0–4, all 90 runs valid).
      Ablation isolating the sources of inflation (RF / LogReg bal. acc.):
      | regime | population | split | RF | LogReg |
      |---|---|---|---|---|
      | A pre-audit naive (frozen) | 1,089 files, whole-file feats | per-file | 0.871 ± 0.010 | 0.877 ± 0.017 |
      | A pre-audit grouped (frozen) | 1,089 files, whole-file feats | design-key | 0.916 ± 0.036 | 0.899 ± 0.027 |
      | B FDRI feats (diagnostic) | 1,089 files | naive per-file | 0.848 ± 0.021 | 0.817 ± 0.014 |
      | C FDRI feats (secondary, file-weighted) | 920 files post-quarantine | payload-component | 0.543 ± 0.073 | 0.631 ± 0.183 |
      | **D FDRI feats (PRIMARY)** | **140 unique payloads (36 B/104 M)** | **payload-component** | **NOT ESTIMABLE — insufficient valid payload-component folds** (2/5 seeds valid, test n=3 and 8; raw 0.500 observations retained in `phase05_out/stat_results.csv`, not presented as an estimate) | NOT ESTIMABLE (same folds) |
      | **E FDRI feats (PRIMARY generalization)** | 140 unique payloads | LOFO per eligible family | RF per family: BUS/DISPLAY 0.667, CRYPTO 0.559, COMMS 0.533, ITC99 0.500, MCU/CPU 0.500 → **macro avg 0.552 ± 0.062 over 5 family means** | LogReg 0.500 per family → macro 0.500 |
      E is reported per held-out family first, then as a macro average across
      eligible family means — valid seed × family runs are never pooled as
      though they were independent datasets. All family means sit at or near
      chance; BUS/DISPLAY's 0.667 is a 4-sample test set.
      Components are computed over the FULL corpus graph (design ∨ payload
      edges, aliases included) and passed into subset splits — recomputing on
      a deduplicated subset silently drops alias-carried design bridges
      (caught mid-run 2026-07-25, fixed, regression test
      `test_subset_split_honors_full_corpus_components`; an earlier D of
      ≈0.64 under the finer, leakier grouping was discarded).
      Reading: **removing build metadata produces a modest reduction
      (A-naive → B, ~2–6 points, both duplicate-leaked), while eliminating
      exact-payload contamination collapses performance and makes the
      grouped known-host estimate structurally infeasible** — the honest
      component structure has only 15 non-ISCAS85 components, the largest
      (CRYPTO/AES) holding 61 of 140 canonical samples (44%), so 3/5 seeds
      yield single-class test folds (logged INVALID, never forced) and the
      remaining folds test on 3–8 samples. E, the only structurally valid
      regime, is at or near chance for every eligible family, consistent
      with Phase 0's LOFO finding. Exclusions logged per run: ISCAS85
      (policy), ISCAS89 from E (4 B / 0 M unique payloads after quarantine).
- [x] **Corrected hybrid CNN** (2026-07-25, `phase05_cnn_comparison.py` →
      `phase05_out/cnn_results.csv`, device mps, frozen train_model harness
      + runtime shims, fresh weights/scalers, regimes D and E only —
      contaminated diagnostics deliberately not reproduced):
      | regime | pre-audit (frozen) | corrected |
      |---|---|---|
      | naive | 0.8954 ± 0.0214 | — (diagnostic not rerun) |
      | grouped / D | 0.8532 ± 0.0818 | **NOT ESTIMABLE — insufficient valid payload-component folds** (1/5 seeds valid; raw 0.500 observation retained in `phase05_out/cnn_results.csv`, not an estimate) |
      | LOFO / E | 0.5579 ± 0.0932 | per family: BUS/DISPLAY 0.500 (5/5 valid), CRYPTO 0.526 (3/5), ITC99 0.482 (4/5), COMMS 0.333 (1/5), MCU/CPU 0.500 (1/5) → **macro avg 0.468 ± 0.069 over 5 family means** |
      E is reported per family first, then as a macro average of family
      means; valid seed × family runs are not pooled. The CNN needs a
      three-way both-class split (early stopping on val), so even more seeds
      are structurally invalid than for the classical models — every
      invalidity logged with its exact reason, never forced. The corrected
      CNN confirms the statistical table: at or near chance wherever the
      split is valid. Pre-audit CNN numbers were read from the frozen logs,
      never recomputed.
- [ ] **Rebuild genuine variants.** 36 unique benign configurations is the
      binding constraint on the whole programme. The `-directive` sweep in
      `deployment_pipeline/run_random_build.tcl` mostly produced identical
      bitstreams; distinctness must be verified by payload hash before any
      file joins the corpus. **Do not assume `place_design -seed` exists** —
      the pilot may only use options documented by the installed Vivado
      2023.2 (`rebuild_pilot/capture_vivado_env.tcl` captures them).
      Status 2026-07-25: pilot designed (PIC16F84-T100 / b15-T200 /
      AES-T1000, three families, small/medium/large, all trace-bearing) and
      **blocked on build-host access** — see `rebuild_pilot/REBUILD_PILOT_REPORT.md`.

## Phase 1 — Windowed extractor + invariant test

Frame-aligned per-window feature extraction alongside (not replacing) the global
pipeline. Window = N × 404-byte frames, N parameterized, default 8.

- [x] `window_features.py`: `config_region()` (sync-word logic reused from
      `train_model`), `frame_windows()`, `window_feature_matrix()` — per-window
      raw-count 256-bin histogram + 10 stats (entropy, mean, std, min, max, median,
      zero-ratio, 0xFF-ratio, transition rate, mean |transition|), metadata with
      `window_index`, `start_byte`, `n_bytes`, `is_partial`.
- [x] `test_window_features.py`: invariant test — summed per-window histograms
      exactly equal the global histogram of the same region; coverage test — byte
      counts sum to region length, starts frame-aligned, only the last window may be
      partial; edge cases (exact multiple, shorter than one window, empty).
- [x] Cross-check against the original global pipeline on a real bitstream
      (2026-07-19): header counts + summed window counts exactly reproduce
      `train_model.extract_statistical_features`'s whole-file histogram, and the
      config-region boundary sits immediately after a sync word in the raw
      bytes — so a `config_region()` bug cannot cancel out of the invariant.
      **QUALIFIED 2026-07-25:** this cross-check is sound but weaker than it
      reads. It asserts the region starts after a *sync word*; it never asserts
      the region starts on a *frame boundary*, and the synthetic invariant tests
      feed the same array to both sides, so a wrong region origin cancels out.
      Both were blind to the 184-byte phase error (Finding 1).
- [x] **Alignment corrected** (2026-07-25): `window_features.payload_region()`
      windows the profile-validated FDRI payload; offset 0 = first byte of
      frame 0. 10,008 / 8 = 1,251 whole 8-frame windows, zero remainder — the
      partial-tail path is never exercised on this device; the policy and its
      synthetic tests stay (required for other window sizes / device profiles).
- [x] Alignment invariant added to `test_window_features.py`
      (`test_real_bitstream_frame_alignment`): window 0 starts at the first
      configuration frame (checked against the parsed FDRI file offset), and
      `n_frames % window_frames` is asserted explicitly (0 on this device).
- [x] Full-corpus extraction/invariant audit (2026-07-25,
      `audit_window_extraction.py` → `phase05_out/window_extraction_audit.json`):
      all 1,383 files pass profile validation, 10,008-frame coverage, 1,251
      full windows each (1,730,133 windows total), zero partial windows, and
      the summed-histogram invariant; extraction config logged.

## Phase 2 — Localization ground truth via controlled placement

**Gated on Phase 0.5.** Two audit results bear directly on this phase:
frame index → byte offset is now *solved* (single uncompressed FDRI block,
one FAR write with auto-increment, `frame = fdri_offset // 404`, exact), so the
remaining unknown is frame sequence index → FAR, which needs the device column
layout and is not yet sourced. Separately, the uncontrolled trojan-vs-benign
frame diff is 3,756/10,008 frames against a clean-variant noise floor of
3,720 and a different-design baseline of 3,918 — confirming the standing
decision that clean-variant differential cannot serve as ground truth.

- [ ] Source and validate the frame-index → FAR mapping (candidates: Project
      X-Ray `xc7z020` part database; Vivado partial-reconfiguration bitstreams,
      which emit authoritative FAR+FDRI pairs per contiguous frame run; the
      `.ll` logic-location file). Validation invariant: the reconstructed FAR
      sequence must sum to exactly 10,008 frames.
- [ ] Select a small set of designs; rebuild with trojan logic pinned via
      pblock/LOC constraints so occupied frame address ranges are known.
- [ ] Map frame addresses (FAR) to config-region byte offsets; derive window-level
      trojan/clean labels from the pinned ranges.
- [ ] Keep the clean-variant differential as an exploratory diagnostic only
      (explicitly not ground truth); quantify P&R noise floor between clean variants.
- [ ] Log build constraints, frame ranges, and label derivation per design.

## Phase 3 — Windowed CNN / MIL models

**Gated on Phase 0.5 and Phase 2.** Note for this phase: the 169 contradictory
malicious files (Finding 4) must be excluded before any MIL training — each one
asserts bag = malicious while every window in it is genuinely clean, which is
label noise that MIL aggregation cannot absorb.

- [ ] Extend the MIL-bag approach in `train_cnn_experiments.py` to emit per-window
      scores (e.g. attention-based MIL) instead of only bag-level predictions.
- [ ] Evaluate window-level localization (ROC / IoU against Phase 2 labels) alongside
      file-level detection; grouped splits and leave-one-family-out throughout.
- [ ] Class imbalance via class weights / file-level sampling only (no SMOTE).
- [ ] Log split composition, seed, window size, and model config per experiment.

## Phase 4 — Hardware integration

- [ ] Port windowed inference into the PYNQ deployment path
      (`deploy_model.py` / `deployment_pipeline`) for on-board per-window scoring.
- [ ] Report suspicious window/frame ranges on-device; measure runtime and memory
      against the global-feature pipeline.
