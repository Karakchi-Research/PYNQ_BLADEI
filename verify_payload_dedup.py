# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Leakage audit, finding 2/4 -- PAYLOAD DEDUPLICATION.
#              Claim under test: the 1,383 .bit files hold far fewer distinct
#              configurations. Many "place-and-route variants" are byte-identical
#              in configuration data and differ only in the .bit ASCII header
#              (design name + build timestamp), which is why the SHA-256 manifest
#              in split_audit_out/ shows 1,383 unique files.
#
#              Method, independent of the other audit scripts:
#                S1  locate the FDRI payload with a pattern-matched header scan
#                    (NOT the packet walk used by verify_frame_alignment.py) and
#                    assert the geometry it finds.
#                S2  candidate clustering with BLAKE2b (not SHA-256).
#                S3  EXACT byte-for-byte confirmation of every candidate cluster
#                    against its representative -- no result depends on a hash
#                    being collision-free.
#                S4  whole-file SHA-256 for contrast, reproducing what the
#                    existing manifest sees and showing why it missed this.
#
# Usage:
#   python3 verify_payload_dedup.py [--data-dir DIR]

import argparse
import glob
import hashlib
import json
import os
import struct
import sys
from collections import Counter, defaultdict

SYNC = bytes([0xAA, 0x99, 0x55, 0x66])
FRAME_BYTES = 404
EXPECT_OFFSET, EXPECT_WORDS = 184, 1010808

CLAIM = {"n_files": 1383, "unique_payloads": 431,
         "unique_payloads_excl_iscas85": 140,
         "unique_benign_payloads": 36, "unique_malicious_payloads": 406}

ISCAS85_PREFIXES = ("c1355", "c1908", "c2670", "c3540", "c432", "c499",
                    "c5315", "c6288", "c7552", "c880")


def locate_fdri(blob):
    """Find the FDRI payload by scanning for its packet header pattern.

    Deliberately different from verify_frame_alignment.py's sequential walk:
    here we scan word-aligned positions in the config region for a type-1 FDRI
    write header (opcode=10, register=0x02, count=0) immediately followed by a
    type-2 header, then assert the geometry rather than assume it.
    """
    sync = blob.find(SYNC)
    if sync < 0:
        raise ValueError("no sync word")
    region_start = sync + 4
    n_words = (len(blob) - region_start) // 4
    words = struct.unpack_from(">%dI" % n_words, blob, region_start)
    hits = []
    for i in range(n_words - 1):
        w = words[i]
        # type-1 | write | register 0x02 (FDRI) | count 0  -> 0x30004000
        if w == 0x30004000 and (words[i + 1] >> 29) == 2:
            hits.append((i, words[i + 1] & 0x07FFFFFF))
    if not hits:
        raise ValueError("no FDRI write header found")

    # A positional scan cannot tell a real packet header from the same 8 bytes
    # occurring by chance inside frame data, so the earliest hit is the packet
    # (the FDRI write is the first bulk transfer in the stream) and every later
    # hit must fall INSIDE the payload it delimits -- asserted below. This is
    # what makes the scan safe without replicating the sequential walk used by
    # verify_frame_alignment.py.
    idx, count = hits[0]
    offset_in_region = (idx + 2) * 4
    if offset_in_region != EXPECT_OFFSET or count != EXPECT_WORDS:
        raise ValueError(f"unexpected geometry: offset={offset_in_region} "
                         f"words={count}")
    payload_first_word, payload_last_word = idx + 2, idx + 2 + count
    for j, _ in hits[1:]:
        if not (payload_first_word <= j < payload_last_word):
            raise ValueError(f"second FDRI-looking header at word {j} lies "
                             f"outside the payload -- not a data coincidence")
    start = region_start + offset_in_region
    return start, count * 4


def main():
    p = argparse.ArgumentParser(description="Verify finding 2: payload dedup")
    p.add_argument("--data-dir",
                   default=os.path.expanduser(
                       "~/Desktop/Karakchi-Research/trusthub_bitstreams_v4"))
    p.add_argument("--outdir", default="leakage_audit_out")
    args = p.parse_args()

    benign = sorted(glob.glob(os.path.join(args.data_dir, "Benign", "*.bit")))
    mal = sorted(glob.glob(os.path.join(args.data_dir, "Malicious", "*.bit")))
    files = benign + mal
    labels = [0] * len(benign) + [1] * len(mal)
    if not files:
        sys.exit(f"no bitstreams under {args.data_dir}")
    os.makedirs(args.outdir, exist_ok=True)
    print(f"=== Finding 2/4: PAYLOAD DEDUPLICATION ===")
    print(f"{len(files)} files ({len(benign)} benign, {len(mal)} malicious)\n")

    # ---- S1 + S2: locate payload, cluster by BLAKE2b -----------------------
    print("S1/S2  locating FDRI payload (pattern scan) + BLAKE2b clustering...")
    payload_key, whole_sha, spans = [], [], []
    for i, f in enumerate(files, 1):
        with open(f, "rb") as fh:
            blob = fh.read()
        start, nbytes = locate_fdri(blob)
        spans.append((start, nbytes))
        payload_key.append(hashlib.blake2b(blob[start:start + nbytes],
                                           digest_size=32).hexdigest())
        whole_sha.append(hashlib.sha256(blob).hexdigest())
        if i % 200 == 0 or i == len(files):
            print(f"    {i}/{len(files)}")

    clusters = defaultdict(list)
    for i, k in enumerate(payload_key):
        clusters[k].append(i)
    print(f"    {len(clusters)} candidate clusters from {len(files)} files")

    # ---- S3: exact byte-for-byte confirmation ------------------------------
    print("\nS3  exact byte-for-byte confirmation of every multi-member cluster")
    print("    (each member re-read and compared to its representative)...")
    multi = {k: v for k, v in clusters.items() if len(v) > 1}
    compared = mismatches = 0
    for n, (k, members) in enumerate(multi.items(), 1):
        rep = members[0]
        s, nb = spans[rep]
        with open(files[rep], "rb") as fh:
            fh.seek(s)
            ref = fh.read(nb)
        for j in members[1:]:
            s2, nb2 = spans[j]
            with open(files[j], "rb") as fh:
                fh.seek(s2)
                other = fh.read(nb2)
            compared += 1
            if other != ref:
                mismatches += 1
                print(f"    MISMATCH: {files[j]} vs {files[rep]}")
        if n % 20 == 0 or n == len(multi):
            print(f"    cluster {n}/{len(multi)}, {compared} exact comparisons")
    print(f"    {compared} byte-for-byte comparisons, {mismatches} mismatches")

    # ---- S4: whole-file hashing, for contrast ------------------------------
    n_whole = len(set(whole_sha))
    print(f"\nS4  whole-file SHA-256 (what the existing manifest computes):")
    print(f"    {n_whole} unique / {len(files)} files "
          f"-> the manifest cannot see this duplication")
    print(f"    reason: the .bit ASCII header carries a per-build timestamp")

    # ---- accounting --------------------------------------------------------
    def uniq(pred):
        return len({payload_key[i] for i in range(len(files)) if pred(i)})

    is_iscas85 = [os.path.basename(f).startswith(ISCAS85_PREFIXES) for f in files]
    n_uniq = len(clusters)
    n_uniq_b = uniq(lambda i: labels[i] == 0)
    n_uniq_m = uniq(lambda i: labels[i] == 1)
    n_uniq_no85 = uniq(lambda i: not is_iscas85[i])
    dup_files = sum(len(v) for v in multi.values())
    size_dist = Counter(len(v) for v in clusters.values())

    print(f"\n--- ACCOUNTING ---")
    print(f"  unique config payloads          : {n_uniq} / {len(files)} files")
    print(f"  files in a duplicate cluster    : {dup_files} "
          f"({100 * dup_files / len(files):.1f}%)")
    print(f"  unique benign payloads          : {n_uniq_b} / {len(benign)} files")
    print(f"  unique malicious payloads       : {n_uniq_m} / {len(mal)} files")
    print(f"  unique payloads excl. ISCAS85   : {n_uniq_no85} / "
          f"{sum(1 for x in is_iscas85 if not x)} files")
    print(f"  largest cluster                 : {max(size_dist)} files")
    print(f"  cluster-size distribution       : {dict(sorted(size_dist.items()))}")

    checks = {
        "S3_all_clusters_exact": mismatches == 0,
        "S3_confirmations_performed": compared > 0,
        "unique_payloads_matches_claim": n_uniq == CLAIM["unique_payloads"],
        "unique_benign_matches_claim": n_uniq_b == CLAIM["unique_benign_payloads"],
        "unique_malicious_matches_claim": n_uniq_m == CLAIM["unique_malicious_payloads"],
        "excl_iscas85_matches_claim": n_uniq_no85 == CLAIM["unique_payloads_excl_iscas85"],
        "whole_file_hash_sees_no_duplication": n_whole == len(files),
        "duplication_is_substantial": n_uniq < len(files) / 2,
    }
    print("\n--- VERDICT ---")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    ok = all(checks.values())
    print(f"\nFINDING 2 {'CONFIRMED' if ok else 'NOT CONFIRMED'}")

    out = {"finding": "payload_deduplication", "confirmed": ok, "claim": CLAIM,
           "data_dir": args.data_dir, "n_files": len(files),
           "n_benign": len(benign), "n_malicious": len(mal),
           "unique_payloads": n_uniq, "unique_benign": n_uniq_b,
           "unique_malicious": n_uniq_m, "unique_excl_iscas85": n_uniq_no85,
           "files_in_duplicate_clusters": dup_files,
           "cluster_size_distribution": {str(k): v for k, v in sorted(size_dist.items())},
           "exact_comparisons": compared, "exact_mismatches": mismatches,
           "whole_file_sha256_unique": n_whole, "checks": checks}
    path = os.path.join(args.outdir, "verify_payload_dedup.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"log -> {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
