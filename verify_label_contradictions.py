# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Leakage audit, finding 4/4 -- IDENTICAL BENIGN/MALICIOUS PAYLOADS.
#              Claim under test: a substantial share of "Malicious" bitstreams are
#              byte-identical in configuration data to a "Benign" build. For those
#              files the trojan left no trace in the bitstream (synthesis stripped
#              dormant/unconnected logic), so the label cannot be recovered from
#              the bytes by ANY model. This bounds achievable accuracy and is
#              fatal to window-level MIL supervision, where such a file asserts
#              bag=malicious while every window is genuinely clean.
#
#              Method:
#                C1  memory-mapped exact comparison. Every benign x malicious
#                    candidate pair that survives a cheap prefilter is compared
#                    byte-for-byte via mmap -- no hashing anywhere in the
#                    contradiction decision.
#                C2  per-host-design breakdown of the affected files.
#                C3  Bayes ceiling: the best balanced accuracy any deterministic
#                    function of the bytes can reach, given the contradictions.
#                C4  spot-check -- re-open a sample of contradictory pairs and
#                    report the exact byte ranges compared.
#
# Usage:
#   python3 verify_label_contradictions.py [--data-dir DIR]

import argparse
import glob
import json
import mmap
import os
import struct
import sys
from collections import Counter, defaultdict

CLAIM = {"malicious_identical_to_benign": 169,
         "malicious_total": 838,
         "contradictory_clusters": 11,
         "files_in_contradictory_clusters": 367,
         "bayes_ceiling_balanced_accuracy": 0.9166}

SYNC = bytes([0xAA, 0x99, 0x55, 0x66])
EXPECT_OFFSET, EXPECT_WORDS = 184, 1010808


def payload_span(blob_head, filesize):
    """(start, nbytes) of the FDRI payload from the file's first 4 KiB only.

    Fourth independent derivation: the config preamble is short, so the FDRI
    header always lies within the first few hundred bytes. Read a small head
    buffer, decode it, and assert the geometry.
    """
    sync = blob_head.find(SYNC)
    if sync < 0:
        raise ValueError("no sync word in head")
    region_start = sync + 4
    n = (len(blob_head) - region_start) // 4
    words = struct.unpack_from(">%dI" % n, blob_head, region_start)
    i = 0
    while i < n - 1:
        w = words[i]
        if (w >> 29) != 1:
            i += 1
            continue
        count = w & 0x7FF
        j = i + 1
        if count == 0 and (words[j] >> 29) == 2:
            count = words[j] & 0x07FFFFFF
            j += 1
        if ((w >> 27) & 3) == 2 and ((w >> 13) & 0x3FFF) == 2:
            assert (j * 4) == EXPECT_OFFSET and count == EXPECT_WORDS, \
                f"unexpected FDRI geometry: offset={j * 4} words={count}"
            assert region_start + j * 4 + count * 4 <= filesize
            return region_start + j * 4, count * 4
        i = j + count
    raise ValueError("no FDRI header in head buffer")


def prefilter_key(path, start, nbytes):
    """Cheap key that identical payloads must share (never decides equality)."""
    with open(path, "rb") as fh:
        fh.seek(start)
        a = fh.read(2048)
        fh.seek(start + nbytes - 2048)
        b = fh.read(2048)
    return (nbytes, a, b)


def payload_equal(pa, sa, pb, sb, nbytes):
    """Exact comparison of two payloads via mmap; no hashing."""
    with open(pa, "rb") as fa, open(pb, "rb") as fb:
        ma = mmap.mmap(fa.fileno(), 0, access=mmap.ACCESS_READ)
        mb = mmap.mmap(fb.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            step = 1 << 20
            for o in range(0, nbytes, step):
                k = min(step, nbytes - o)
                if ma[sa + o:sa + o + k] != mb[sb + o:sb + o + k]:
                    return False
            return True
        finally:
            ma.close()
            mb.close()


def main():
    p = argparse.ArgumentParser(description="Verify finding 4: label contradictions")
    p.add_argument("--data-dir",
                   default=os.path.expanduser(
                       "~/Desktop/Karakchi-Research/trusthub_bitstreams_v4"))
    p.add_argument("--outdir", default="leakage_audit_out")
    p.add_argument("--spot-check", type=int, default=5)
    args = p.parse_args()

    benign = sorted(glob.glob(os.path.join(args.data_dir, "Benign", "*.bit")))
    mal = sorted(glob.glob(os.path.join(args.data_dir, "Malicious", "*.bit")))
    files = benign + mal
    y = [0] * len(benign) + [1] * len(mal)
    if not files:
        sys.exit(f"no bitstreams under {args.data_dir}")
    os.makedirs(args.outdir, exist_ok=True)
    print(f"=== Finding 4/4: IDENTICAL BENIGN/MALICIOUS PAYLOADS ===")
    print(f"{len(benign)} benign, {len(mal)} malicious\n")

    print("C1  locating payloads and prefiltering candidate pairs...")
    spans = []
    for i, f in enumerate(files, 1):
        with open(f, "rb") as fh:
            head = fh.read(4096)
        spans.append(payload_span(head, os.path.getsize(f)))
        if i % 300 == 0 or i == len(files):
            print(f"    {i}/{len(files)}")

    keys = [prefilter_key(f, s, nb) for f, (s, nb) in zip(files, spans)]
    buckets = defaultdict(list)
    for i, k in enumerate(keys):
        buckets[k].append(i)
    print(f"    {len(buckets)} prefilter buckets")

    # Resolve each bucket into exact classes using mmap comparisons only.
    print("\n    resolving buckets by exact mmap comparison (no hashing)...")
    cls = [-1] * len(files)
    reps = []          # (file_index) of each class representative
    n_cmp = 0
    for members in buckets.values():
        local = []     # class ids created inside this bucket
        for i in members:
            placed = False
            for cid in local:
                r = reps[cid]
                n_cmp += 1
                if payload_equal(files[i], spans[i][0], files[r], spans[r][0],
                                 spans[i][1]):
                    cls[i] = cid
                    placed = True
                    break
            if not placed:
                cls[i] = len(reps)
                local.append(len(reps))
                reps.append(i)
    print(f"    {len(reps)} exact classes, {n_cmp} full-payload comparisons")

    members_of = defaultdict(list)
    for i, c in enumerate(cls):
        members_of[c].append(i)

    contradictory = [c for c, ms in members_of.items()
                     if len({y[i] for i in ms}) > 1]
    files_in_contra = sum(len(members_of[c]) for c in contradictory)
    benign_classes = {c for c, ms in members_of.items() if any(y[i] == 0 for i in ms)}
    ghosts = [i for i in range(len(files))
              if y[i] == 1 and cls[i] in benign_classes]

    print(f"\n--- C2  BREAKDOWN ---")
    print(f"  contradictory classes (same bytes, both labels): {len(contradictory)}")
    print(f"  files inside them                              : {files_in_contra} "
          f"({100 * files_in_contra / len(files):.1f}%)")
    print(f"  malicious files identical to a benign build    : {len(ghosts)} / "
          f"{len(mal)} ({100 * len(ghosts) / len(mal):.1f}%)")
    by_host = Counter(os.path.basename(files[i]).split("_T")[0] for i in ghosts)
    print(f"  by host design: {dict(sorted(by_host.items()))}")

    # ---- C3: Bayes ceiling -------------------------------------------------
    tot_b, tot_m = len(benign), len(mal)
    wrong_b = wrong_m = 0
    for c in contradictory:
        ms = members_of[c]
        nb = sum(1 for i in ms if y[i] == 0)
        nm = len(ms) - nb
        # Any deterministic f(bytes) must give one answer for the whole class;
        # the minority side is unavoidably wrong.
        if nb >= nm:
            wrong_m += nm
        else:
            wrong_b += nb
    ceiling = 0.5 * ((tot_b - wrong_b) / tot_b + (tot_m - wrong_m) / tot_m)
    print(f"\n--- C3  BAYES CEILING ---")
    print(f"  unavoidable benign errors    : {wrong_b} / {tot_b}")
    print(f"  unavoidable malicious errors : {wrong_m} / {tot_m}")
    print(f"  best achievable balanced accuracy: {ceiling:.4f}")
    print(f"  (reported grouped RF balanced accuracy was 0.916)")

    # ---- C4: spot-check ----------------------------------------------------
    print(f"\n--- C4  SPOT-CHECK (re-opened and re-compared) ---")
    spot = []
    for i in ghosts[:args.spot_check]:
        peer = next(j for j in members_of[cls[i]] if y[j] == 0)
        eq = payload_equal(files[i], spans[i][0], files[peer], spans[peer][0],
                           spans[i][1])
        rec = {"malicious": os.path.basename(files[i]),
               "benign": os.path.basename(files[peer]),
               "malicious_payload_range": [spans[i][0], spans[i][0] + spans[i][1]],
               "benign_payload_range": [spans[peer][0], spans[peer][0] + spans[peer][1]],
               "bytes_compared": spans[i][1], "identical": eq}
        spot.append(rec)
        print(f"  {rec['malicious']:<38} == {rec['benign']:<26} "
              f"[{rec['bytes_compared']} bytes] -> {eq}")

    checks = {
        "C1_exact_comparisons_only": n_cmp > 0,
        "C2_ghost_count_matches_claim":
            len(ghosts) == CLAIM["malicious_identical_to_benign"],
        "C2_contradictory_clusters_match_claim":
            len(contradictory) == CLAIM["contradictory_clusters"],
        "C2_files_in_clusters_match_claim":
            files_in_contra == CLAIM["files_in_contradictory_clusters"],
        "C3_ceiling_matches_claim":
            abs(ceiling - CLAIM["bayes_ceiling_balanced_accuracy"]) < 5e-4,
        "C3_ceiling_below_one": ceiling < 1.0,
        "C4_spot_checks_all_identical": all(r["identical"] for r in spot),
    }
    print("\n--- VERDICT ---")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    ok = all(checks.values())
    print(f"\nFINDING 4 {'CONFIRMED' if ok else 'NOT CONFIRMED'}")

    out = {"finding": "identical_benign_malicious_payloads", "confirmed": ok,
           "claim": CLAIM, "data_dir": args.data_dir,
           "n_benign": tot_b, "n_malicious": tot_m,
           "n_exact_classes": len(reps),
           "full_payload_comparisons": n_cmp,
           "contradictory_classes": len(contradictory),
           "files_in_contradictory_classes": files_in_contra,
           "malicious_identical_to_benign": len(ghosts),
           "ghosts_by_host_design": dict(sorted(by_host.items())),
           "unavoidable_benign_errors": wrong_b,
           "unavoidable_malicious_errors": wrong_m,
           "bayes_ceiling_balanced_accuracy": round(ceiling, 6),
           "spot_check": spot, "checks": checks}
    path = os.path.join(args.outdir, "verify_label_contradictions.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"log -> {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
