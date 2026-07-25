# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Leakage audit, finding 3/4 -- DUPLICATE LEAKAGE ACROSS SPLITS.
#              Claim under test: grouped_split_indices() correctly keeps design
#              KEYS disjoint, but byte-identical configurations are shared across
#              different design keys, so a large fraction of every grouped test
#              set is an exact copy of a training file. The grouping is sound;
#              the equivalence class is the wrong one.
#
#              Method:
#                E1  build payload equivalence classes WITHOUT hashing -- bucket
#                    by a cheap structural key, then resolve each bucket by exact
#                    byte comparison (sort-and-compare). Independent of the
#                    BLAKE2b clustering in verify_payload_dedup.py.
#                E2  re-assert what the shipped split DOES guarantee: design keys
#                    disjoint across train/val/test (so the bug is located
#                    precisely, not attributed to grouped_split_indices).
#                E3  for each seed, count test files whose exact payload also
#                    occurs in train, and how many design groups a single payload
#                    spans.
#                E4  control -- repeat for leave-one-family-out, which should
#                    show zero exact-duplicate contamination.
#
# Usage:
#   python3 verify_split_leakage.py [--data-dir DIR] [--seeds 5]

import argparse
import glob
import json
import os
import struct
import sys
from collections import Counter, defaultdict

import numpy as np

from split_utils import assert_disjoint, design_name, grouped_split_indices

SYNC = bytes([0xAA, 0x99, 0x55, 0x66])
EXPECT_OFFSET, EXPECT_WORDS = 184, 1010808

CLAIM = {"grouped_test_duplicate_share_range": [0.51, 0.72],
         "lofo_duplicate_share": 0.0}

FAMILY_MAPPING = {
    "CRYPTO": ["AES", "BasicRSA"],
    "COMMS": ["RS232", "EthernetMAC10GE"],
    "MCU/CPU": ["PIC16F84"],
    "BUS/DISPLAY": ["wb_conmax", "vga_lcd"],
    "ITC99": ["b15", "b19"],
    "ISCAS89": ["s15850", "s35932", "s38417", "s38584"],
    "ISCAS85": ["c1355", "c1908", "c2670", "c3540", "c432", "c499", "c5315",
                "c6288", "c7552", "c880"],
}


def family_of(path):
    base = os.path.basename(path)
    for fam, prefixes in FAMILY_MAPPING.items():
        if base.startswith(tuple(prefixes)):
            return fam
    return "UNKNOWN"


def payload_span(blob):
    """(start, nbytes) of the FDRI payload, re-derived and asserted.

    Third independent derivation in this audit: walk type-1 headers only far
    enough to reach the FDRI write, then check the geometry.
    """
    sync = blob.find(SYNC)
    region_start = sync + 4
    n_words = (len(blob) - region_start) // 4
    words = struct.unpack_from(">%dI" % n_words, blob, region_start)
    i = 0
    while i < n_words:
        w = words[i]
        if (w >> 29) != 1:
            i += 1
            continue
        count = w & 0x7FF
        j = i + 1
        if count == 0 and j < n_words and (words[j] >> 29) == 2:
            count = words[j] & 0x07FFFFFF
            j += 1
        if ((w >> 27) & 3) == 2 and ((w >> 13) & 0x3FFF) == 2:
            assert (j * 4) == EXPECT_OFFSET and count == EXPECT_WORDS, \
                f"unexpected FDRI geometry: offset={j * 4} words={count}"
            return region_start + j * 4, count * 4
        i = j + count
    raise ValueError("no FDRI write")


def equivalence_classes(files, spans):
    """Exact payload equivalence classes, resolved by byte comparison.

    Two-stage and hash-free: bucket by a cheap structural key (a sparse byte
    sample), then within each bucket sort the full payloads and group adjacent
    equal ones. Only buckets with >1 member are ever fully materialised.
    """
    buckets = defaultdict(list)
    for i, f in enumerate(files):
        s, nb = spans[i]
        with open(f, "rb") as fh:
            fh.seek(s)
            head = fh.read(4096)
            fh.seek(s + nb // 2)
            mid = fh.read(4096)
            fh.seek(s + nb - 4096)
            tail = fh.read(4096)
        buckets[(nb, head, mid, tail)].append(i)

    cls = np.full(len(files), -1, dtype=int)
    next_id = 0
    for members in buckets.values():
        if len(members) == 1:
            cls[members[0]] = next_id
            next_id += 1
            continue
        payloads = []
        for i in members:
            s, nb = spans[i]
            with open(files[i], "rb") as fh:
                fh.seek(s)
                payloads.append((fh.read(nb), i))
        payloads.sort(key=lambda t: t[0])
        cls[payloads[0][1]] = next_id
        for a, b in zip(payloads, payloads[1:]):
            if b[0] != a[0]:
                next_id += 1
            cls[b[1]] = next_id
        next_id += 1
    return cls, next_id


def main():
    p = argparse.ArgumentParser(description="Verify finding 3: split leakage")
    p.add_argument("--data-dir",
                   default=os.path.expanduser(
                       "~/Desktop/Karakchi-Research/trusthub_bitstreams_v4"))
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--outdir", default="leakage_audit_out")
    args = p.parse_args()

    benign = sorted(glob.glob(os.path.join(args.data_dir, "Benign", "*.bit")))
    mal = sorted(glob.glob(os.path.join(args.data_dir, "Malicious", "*.bit")))
    files = benign + mal
    y = np.array([0] * len(benign) + [1] * len(mal))
    if not files:
        sys.exit(f"no bitstreams under {args.data_dir}")
    os.makedirs(args.outdir, exist_ok=True)
    print(f"=== Finding 3/4: DUPLICATE LEAKAGE ACROSS SPLITS ===")
    print(f"{len(files)} files, {args.seeds} seeds\n")

    print("E1  building exact payload equivalence classes (hash-free)...")
    spans = []
    for i, f in enumerate(files, 1):
        with open(f, "rb") as fh:
            spans.append(payload_span(fh.read()))
        if i % 300 == 0 or i == len(files):
            print(f"    geometry {i}/{len(files)}")
    cls, n_cls = equivalence_classes(files, spans)
    print(f"    {n_cls} distinct payloads among {len(files)} files")

    groups = np.array([design_name(f) for f in files])
    fams = np.array([family_of(f) for f in files])

    # ---- how far does one payload reach across design keys? ----------------
    span_groups = defaultdict(set)
    for c, g in zip(cls, groups):
        span_groups[c].add(g)
    multi = {c: gs for c, gs in span_groups.items() if len(gs) > 1}
    worst = max(span_groups.items(), key=lambda kv: len(kv[1]))
    print(f"    payloads spanning >1 design key: {len(multi)} / {n_cls}")
    print(f"    worst payload spans {len(worst[1])} design keys, e.g. "
          f"{sorted(worst[1])[:6]}")

    # cross-family reach (relevant to the LOFO control)
    span_fams = defaultdict(set)
    for c, fm in zip(cls, fams):
        span_fams[c].add(fm)
    cross_fam = [c for c, s in span_fams.items() if len(s) > 1]
    print(f"    payloads spanning >1 family    : {len(cross_fam)} / {n_cls}")

    # ---- E2/E3: grouped split ---------------------------------------------
    print(f"\nE2/E3  grouped split: design-key disjointness AND payload overlap")
    per_seed = []
    for seed in range(args.seeds):
        it, iv, ite = grouped_split_indices(files, y, seed)
        itr = np.concatenate([it, iv])
        # E2: what the shipped split guarantees -- keys disjoint. Must pass.
        keys_ok = True
        try:
            assert_disjoint(groups, itr, ite, "train+val", "test")
        except AssertionError:
            keys_ok = False
        # E3: what it does not guarantee -- payload disjointness.
        train_cls = set(cls[itr])
        dup = [i for i in ite if cls[i] in train_cls]
        train_lab = defaultdict(set)
        for i in itr:
            train_lab[cls[i]].add(int(y[i]))
        contra = sum(1 for i in dup if int(y[i]) not in train_lab[cls[i]])
        share = len(dup) / len(ite)
        per_seed.append({"seed": seed, "n_test": int(len(ite)),
                         "n_test_exact_dup_of_train": len(dup),
                         "share": round(share, 4),
                         "label_contradicts_train_copy": contra,
                         "design_keys_disjoint": keys_ok})
        print(f"    seed {seed}: test n={len(ite):4d} | design keys disjoint: "
              f"{'yes' if keys_ok else 'NO'} | exact-duplicate-of-train "
              f"{len(dup):4d} ({share:6.1%}) | label contradicts: {contra}")

    shares = [r["share"] for r in per_seed]

    # ---- E4: LOFO control --------------------------------------------------
    print(f"\nE4  control -- leave-one-family-out (expected: no duplicate leakage)")
    lofo = []
    all_idx = np.arange(len(files))
    for fam in sorted(set(fams)):
        ite = all_idx[fams == fam]
        itr = all_idx[fams != fam]
        if len(ite) == 0:
            continue
        train_cls = set(cls[itr])
        dup = [i for i in ite if cls[i] in train_cls]
        lofo.append({"family": fam, "n_test": int(len(ite)),
                     "n_test_exact_dup_of_train": len(dup),
                     "share": round(len(dup) / len(ite), 4)})
        print(f"    held out {fam:<12} test n={len(ite):4d} | "
              f"exact-duplicate-of-train {len(dup):4d} "
              f"({len(dup) / len(ite):6.1%})")

    lo, hi = CLAIM["grouped_test_duplicate_share_range"]
    checks = {
        "E1_classes_fewer_than_files": n_cls < len(files),
        "E2_design_keys_disjoint_all_seeds": all(r["design_keys_disjoint"]
                                                 for r in per_seed),
        "E3_payloads_span_multiple_design_keys": len(multi) > 0,
        "E3_every_seed_leaks_duplicates": all(r["n_test_exact_dup_of_train"] > 0
                                              for r in per_seed),
        "E3_share_in_claimed_range": all(lo <= s <= hi for s in shares),
        "E4_lofo_has_no_duplicate_leakage": all(r["n_test_exact_dup_of_train"] == 0
                                                for r in lofo),
    }
    print(f"\n--- SUMMARY ---")
    print(f"  grouped test sets that are exact copies of training files: "
          f"{min(shares):.1%} - {max(shares):.1%} (mean {np.mean(shares):.1%})")
    print(f"  leave-one-family-out contamination: "
          f"{max(r['share'] for r in lofo):.1%}")
    print(f"  => the design-key grouping is correctly implemented; the")
    print(f"     equivalence class it enforces is not the one that matters.")

    print("\n--- VERDICT ---")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    ok = all(checks.values())
    print(f"\nFINDING 3 {'CONFIRMED' if ok else 'NOT CONFIRMED'}")

    out = {"finding": "duplicate_leakage_across_splits", "confirmed": ok,
           "claim": CLAIM, "data_dir": args.data_dir, "n_files": len(files),
           "n_payload_classes": int(n_cls),
           "payloads_spanning_multiple_design_keys": len(multi),
           "max_design_keys_per_payload": len(worst[1]),
           "payloads_spanning_multiple_families": len(cross_fam),
           "grouped_per_seed": per_seed, "lofo_control": lofo,
           "checks": checks}
    path = os.path.join(args.outdir, "verify_split_leakage.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"log -> {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
