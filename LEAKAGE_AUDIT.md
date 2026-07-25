# BLADE-I Leakage Audit — Methodology and Results

Audit run 2026-07-25 against the canonical dataset
`~/Desktop/Karakchi-Research/trusthub_bitstreams_v4/` (1,383 files: 545 Benign,
838 Malicious), the same checkout described under "Dataset provenance" in
`RESEARCH_PLAN.md`.

Four findings were checked. **All four are CONFIRMED.** Machine-readable logs
are in `leakage_audit_out/`; each script re-runs standalone and prints a
per-check PASS/FAIL verdict plus an overall CONFIRMED / NOT CONFIRMED line, and
exits non-zero if any check fails.

```bash
python3 verify_frame_alignment.py
python3 verify_payload_dedup.py
python3 verify_split_leakage.py
python3 verify_label_contradictions.py
```

## Design of the audit

The findings were first observed with a single exploratory script. That is not
evidence: one parser bug would have produced all four "findings" at once. So
each finding is re-checked by a **separate script that derives the bitstream
geometry itself**, using a different mechanism from the others:

| script | how it locates the FDRI configuration payload |
|---|---|
| `verify_frame_alignment.py` | sequential type-1/type-2 packet walk, decoding every register write |
| `verify_payload_dedup.py` | positional scan for the FDRI header word pattern, with the packet-framing check described below |
| `verify_split_leakage.py` | partial header walk, stopping at the first FDRI write |
| `verify_label_contradictions.py` | decode from the first 4 KiB of the file only |

Every script **asserts** the geometry it derives (offset 184, 1,010,808 words)
rather than assuming it, so a file deviating from the expected layout aborts the
run instead of being silently mis-parsed. No script imports the others. Where a
finding rests on equality of large byte ranges, the final decision is made by
**exact byte comparison, never by a hash** — hashes are used only to propose
candidate groupings that are then confirmed byte-for-byte.

## Finding 1 — Frame alignment (CONFIRMED)

**Claim.** Configuration frames do not begin at the sync word. They begin at the
FDRI packet payload, 184 bytes further into the config region. Because
`184 mod 404 ≠ 0`, the window grid in `window_features.py` — which starts at
region offset 0 — straddles frame boundaries.

**M1, packet-structure walk, all 1,383 files.** Every file is identical in
configuration layout:

| property | value | files |
|---|---|---|
| FDRI payload offset within config region | **184 bytes** | 1383/1383 |
| FDRI word count | **1,010,808** = 101 × **10,008 frames**, exact | 1383/1383 |
| trailer bytes after FDRI | 2,096 | 1383/1383 |
| FAR writes in the stream | `0x00000000`, then `0x03be0000` after the data | 1383/1383 |

A single uncompressed FDRI block with one leading FAR write and address
auto-increment. Frame index is therefore exactly `fdri_byte_offset // 404`, with
no remainder — a linear, gap-free frame grid.

**M2, zero-cell argmax — no packet parsing.** For each of the 404 candidate grid
origins, count wholly-zero 404-byte cells. Unused device frames are all-zero, so
an out-of-phase grid splits some of them and the count drops. The strict argmax
is **184 on 5/5 files**.

*Stated honestly:* the margin is small (+1 to +10 cells). Long runs of
consecutive empty frames yield zero cells at every origin and carry no phase
information; only run boundaries discriminate. The strength of this test is not
the margin but that the argmax selects one specific value out of 404 candidates,
independently, on every file.

**M3, middle-word lattice — no packet parsing.** In an otherwise-empty stretch
of the region, isolated non-zero islands are 2–3 bytes long and recur with byte
patterns `49ae`, `2009b5`, `0419b2`. Two predictions were stated before
comparing to M1:

- **P1** every isolated island lies within frame bytes 200–204 (the middle word,
  word 50 of 101) → **4/4 to 10/10 islands per file, on 5/5 files**
- **P2** the modal island end offset is frame byte 203, so the frame origin is
  `(modal_end − 203) mod 404` → **184 on 5/5 files**

**Consequence.** Real frames start at region offset 184.
`frame_windows()` starts at 0, so every window begins 220 bytes into one frame
and ends 184 bytes into another. **The "frame-aligned windows only" rule is not
currently met by the code that implements it.** The correct grid gives
10,008 / 8 = **1,251 whole 8-frame windows with zero remainder** — so the
partial-tail machinery, while correct in itself, is never exercised on this
device once alignment is fixed.

*Why the existing tests missed it:* `test_histogram_invariant` feeds the same
array to both sides, so a wrong region origin cancels out; the real-bitstream
cross-check asserts only that the region starts after a sync word, never that it
starts on a frame boundary.

**One method was mis-specified and is recorded here rather than quietly
dropped.** M3 originally predicted that long zero runs *start* on frame
boundaries. It failed: the modal start residue was 388, not 184. Diagnosis: zero
runs start 204 bytes into a frame, immediately after the non-zero middle word.
The test was rewritten around the middle-word structure, which yields the
sharper P1/P2 predictions above. The expected value was never adjusted to make a
failing test pass.

## Finding 2 — Payload deduplication (CONFIRMED)

**Claim.** The 1,383 files hold far fewer distinct configurations; many
"place-and-route variants" are byte-identical in configuration data.

**Method.** Locate the payload by positional header scan (S1); cluster
candidates with BLAKE2b, *not* SHA-256 (S2); then **re-read every member of
every multi-member cluster and compare it byte-for-byte against the cluster
representative** (S3). 952 exact comparisons, **0 mismatches** — no conclusion
depends on a hash being collision-free.

| | files | unique config payloads |
|---|---|---|
| Benign | 545 | **36** |
| Malicious | 838 | 406 |
| **Total** | **1,383** | **431** |
| Total excluding ISCAS85 | 1,089 | **140** |

- 1,050 files (75.9%) sit in a duplicate cluster; the largest holds 105 files.
- Cluster sizes: 333 singletons, and clusters of 105, 80, 78, 54, 50, 45, 30…

**Why the existing manifest missed this (S4).** Whole-file SHA-256 gives
**1,383 unique / 1,383 files**. The `.bit` ASCII header carries a per-build
timestamp, so every file differs somewhere even when the configuration data is
identical. `split_audit_out/dataset_manifest.json` is correct as written and
still blind to this.

## Finding 3 — Duplicate leakage across splits (CONFIRMED)

**Claim.** `grouped_split_indices()` keeps design *keys* disjoint correctly, but
byte-identical configurations are shared across different design keys, so much
of every grouped test set is an exact copy of a training file.

**Method.** Payload equivalence classes are built **without hashing** (E1):
bucket by a cheap structural key, then resolve each bucket by sorting the full
payloads and comparing adjacent entries. The shipped `grouped_split_indices` and
`assert_disjoint` are used as-is, since they are what is under test.

**E2 — what the shipped split does guarantee.** Design keys are disjoint across
train+val / test on **all 5 seeds**. The grouping is correctly implemented; this
is not a bug in `split_utils.py`.

**E3 — what it does not guarantee.**

| seed | test files | exact duplicate of a training file | label contradicts the training copy |
|---|---|---|---|
| 0 | 234 | 134 (57.3%) | 0 |
| 1 | 329 | 235 (71.4%) | 6 |
| 2 | 263 | 163 (62.0%) | 0 |
| 3 | 243 | 139 (57.2%) | 1 |
| 4 | 251 | 128 (51.0%) | 0 |

**51.0%–71.4% of every grouped test set is byte-identical to a training file**
(mean 59.8%). The cause: 56 of 431 payloads span more than one design key, and
one payload spans **25 design keys** (`AES_T100`, `AES_T1000`, `AES_T1100`, …) —
the trojan-free builds of different AES benchmarks are the same circuit and
therefore the same bitstream.

**E4 — control.** No payload spans more than one family, so leave-one-family-out
has **0.0% duplicate contamination on all 7 held-out families**.

**Interpretation.** The naive-vs-grouped comparison logged at
`RESEARCH_PLAN.md` Phase 0 is not evidence that leakage is absent: both regimes
leak at comparable rates, so they agree. LOFO is the only regime measured so far
that is free of exact-duplicate contamination.

## Finding 4 — Identical benign/malicious payloads (CONFIRMED)

**Claim.** A substantial share of "Malicious" bitstreams are byte-identical in
configuration data to a "Benign" build, so the trojan left no trace and the
label cannot be recovered from the bytes by any model.

**Method.** Exact `mmap` comparison throughout (C1) — no hashing anywhere in the
contradiction decision. The cheap prefilter collapsed to a single bucket,
because the first and last 2 KiB of every payload are zero-filled; the script
therefore fell back to near-exhaustive pairwise comparison, performing
**132,337 full 4,043,232-byte comparisons**. Slow, but stronger than intended.

- **contradictory classes** (same bytes, both labels): **11**
- **files inside them**: **367 (26.5%)**
- **malicious files byte-identical to a benign build**: **169 / 838 (20.2%)**

By host design: RS232 60, EthernetMAC10GE 38, s35932 15, s38417 15, s38584 15,
wb_conmax 10, BasicRSA 5, s15850 5, vga_lcd 5, AES 1.

**C3 — Bayes ceiling.** A deterministic function of the bytes must return one
answer per equivalence class, so the minority side of each contradictory class
is unavoidably wrong: 20/545 benign and 109/838 malicious. Best achievable
balanced accuracy = **0.9166**. The reported grouped RandomForest result was
0.916 — i.e. at the ceiling imposed by label contradictions.

**C4 — spot check.** Five contradictory pairs re-opened and re-compared over the
full 4,043,232-byte payload; all identical. Example:
`BasicRSA_T100_Trojan.bit` == `BasicRSA_T100.bit`.

**Interpretation.** The most likely mechanism is that synthesis stripped dormant
or unconnected trojan logic, so the trojaned build produced the same bitstream as
the benign one. These files are mislabeled *at the bitstream level*. They are
particularly damaging to MIL localization, where such a file asserts
bag = malicious while every window in it is genuinely clean.

## ~~Open item, not yet independently verified~~ → verified as Finding 5 (2026-07-25)

The fifth observation was originally recorded here as unverified (the text
below is kept as written). It has since been independently verified — see
**Finding 5** in the addendum, which also **supersedes the exploratory
classifier numbers quoted below**: they were measured under the design-grouped
split, which Finding 3 shows is duplicate-leaked, so they overstate the
exploitable channel.

> The `.bit` ASCII header appears to leak the label. `extract_statistical_features`
> reads the whole file, header included. Header length takes four values, and two
> of them (`aes_128`, `top_benign`, 151/154 bytes) are benign-only while the
> 163-byte Vivado-2025.2 header is malicious-only (all 294 ISCAS85 files) —
> 544/1383 files whose label is determined by file size alone. Exploratory
> measurements: RF on file size alone ≈ 0.774 balanced accuracy; RF on the header
> byte histogram alone ≈ 0.751.

## Addendum (2026-07-25) — Finding 5: header/metadata label leak (CONFIRMED)

Verified by `verify_header_leak.py` (log:
`rebuild_pilot/header_leak_verification.json`), a standalone script with its
own `.bit` container-field walker and its own sync search — independent of
`bitstream_io`. Nothing in Findings 1–4 above was altered.

**A — contingency tables (all 1,383 files).** Label is fully determined by:
header length / file size for **544 files** (matching the original
observation); the tool-version field for **294** (`2025.2+SW_CRC` is
malicious-only — all of ISCAS85); the design-name field for **250**
(`aes_128` and `top_benign` are benign-only). The `part` field is constant
(no leak).

**B1 — differential demonstration.** Five identical-payload pairs (proposed
by the corpus index, **re-confirmed byte-for-byte by the verifier's own sync
alignment**), each with differing headers: the frozen legacy whole-file
features differ on every pair (10–17 of 278 dims), while the corrected
FDRI-only features are exactly identical on every pair.

**B2 — exploitability under the duplicate-safe split** (RF, no FDRI bytes in
the input by construction, payload-component grouping, 5 seeds):

| input | full corpus | excl. ISCAS85 |
|---|---|---|
| file size only | **0.635 ± 0.016** | 0.500 ± 0.000 |
| header byte histogram | 0.538 ± 0.038 | 0.451 ± 0.020 |

**Reading.** The channel exists and the legacy path reads it (A + B1,
conclusive). Its *exploitable* strength under duplicate-safe evaluation is
concentrated in ISCAS85's tool-version marker; outside ISCAS85, deterministic
field–label associations exist but are not exploitable by these classifiers
when whole payload components are held out. **The earlier exploratory
numbers (0.774 / 0.751) were measured under the duplicate-leaked
design-grouped split and are superseded; do not cite them.** Limitations are
recorded in the JSON artifact.

## Limitations

- M2/M3 in Finding 1 run on 5 files (`--n-deep`); M1 runs on all 1,383.
- The Bayes ceiling is specific to this file population and label assignment;
  it is an upper bound for deterministic classifiers, not a target.
- The audit establishes that duplication and contradictions exist and how large
  they are. It does not by itself quantify how much of any previously reported
  accuracy is attributable to them — that requires re-running the classifiers
  under a leakage-controlled protocol, which is the Phase 0.5 work item.
