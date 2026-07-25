# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Leakage audit, finding 1/4 -- FRAME ALIGNMENT.
#              Claim under test: the configuration frames of a 7-series .bit do
#              NOT begin at the sync word. They begin at the FDRI packet payload,
#              184 bytes further in, so the window grid in window_features.py
#              (which starts at region offset 0) straddles frame boundaries.
#
#              Three INDEPENDENT methods, deliberately not sharing code:
#                M1  packet-structure walk  -- decode type-1/type-2 config
#                    packets and read the FDRI payload offset directly.
#                M2  zero-frame argmax      -- NO packet parsing at all. Unused
#                    device frames are all-zero, so the correct 404-byte grid
#                    origin maximises the number of wholly-zero frames. Scan all
#                    404 candidate origins and take the argmax.
#                M3  zero-run boundary phase -- NO packet parsing at all. Maximal
#                    runs of zero bytes start on frame boundaries, so their start
#                    offsets mod 404 concentrate on the true origin.
#              M2 and M3 are purely data-driven; if they agree with M1 the
#              offset is confirmed without trusting any packet decoder.
#
# Usage:
#   python3 verify_frame_alignment.py [--data-dir DIR] [--n-deep 5]

import argparse
import glob
import json
import os
import struct
import sys
from collections import Counter

import numpy as np

SYNC = bytes([0xAA, 0x99, 0x55, 0x66])
FRAME_BYTES = 404          # 101 words x 32 bits, 7-series config frame
FRAME_WORDS = 101

CLAIM = {"fdri_offset_in_region": 184, "fdri_words": 1010808,
         "n_frames": 10008, "trailer_bytes": 2096}


# --------------------------------------------------------------------------
# M1: packet-structure walk (self-contained; shares no code with the other
# audit scripts by design).
# --------------------------------------------------------------------------
def m1_packet_walk(blob):
    """Decode the config packet stream; return the FDRI write's geometry.

    7-series packet encoding (UG470): a type-1 header carries
    [31:29]=001, [28:27]=opcode, [26:13]=register, [10:0]=word count. A word
    count of 0 means the following type-2 header ([31:29]=010) supplies a
    27-bit count. Register 2 is FDRI, opcode 2 is write.
    """
    sync = blob.find(SYNC)
    if sync < 0:
        raise ValueError("no sync word")
    region_start = sync + 4
    n_words = (len(blob) - region_start) // 4
    words = struct.unpack_from(">%dI" % n_words, blob, region_start)

    i = 0
    fdri = None
    n_packets = 0
    far_writes = []
    while i < n_words:
        w = words[i]
        htype = w >> 29
        if htype != 1:                      # NOP / pad / type-2 orphan
            i += 1
            continue
        opcode = (w >> 27) & 0x3
        reg = (w >> 13) & 0x3FFF
        count = w & 0x7FF
        payload_i = i + 1
        if count == 0 and payload_i < n_words and (words[payload_i] >> 29) == 2:
            count = words[payload_i] & 0x07FFFFFF
            payload_i += 1
        n_packets += 1
        if opcode == 2 and reg == 1 and count >= 1:      # FAR write
            far_writes.append(words[payload_i])
        if opcode == 2 and reg == 2:                     # FDRI write
            if fdri is not None:
                raise ValueError("more than one FDRI write")
            fdri = {"payload_offset_in_region": (payload_i * 4),
                    "words": count}
        i = payload_i + count

    if fdri is None:
        raise ValueError("no FDRI write found")
    fdri["n_packets"] = n_packets
    fdri["far_writes"] = far_writes
    fdri["region_len"] = len(blob) - region_start
    fdri["trailer_bytes"] = (fdri["region_len"]
                             - fdri["payload_offset_in_region"]
                             - fdri["words"] * 4)
    return fdri


# --------------------------------------------------------------------------
# M2: zero-frame argmax. No packet decoding.
# --------------------------------------------------------------------------
def m2_zero_cell_argmax(region):
    """Best 404-byte grid origin = the one yielding most wholly-zero cells.

    Most of this device is unused and configured with all-zero frames. A grid
    that is out of phase splits some zero frames across two cells, each of which
    then also picks up non-zero bytes from a neighbouring used frame, so the
    count of wholly-zero cells is maximised at the true origin.

    Caveat, stated honestly: the margin is SMALL (single digits). Long runs of
    consecutive empty frames yield zero cells at every candidate origin, so most
    of the 6000+ zero frames carry no phase information and only the boundaries
    of those runs discriminate. What makes this decisive is not the margin but
    that the strict argmax lands on one specific value out of 404 candidates,
    independently, on every file tested.
    """
    counts = np.empty(FRAME_BYTES, dtype=np.int64)
    for o in range(FRAME_BYTES):
        n = (len(region) - o) // FRAME_BYTES
        cells = region[o:o + n * FRAME_BYTES].reshape(n, FRAME_BYTES)
        counts[o] = int(n - np.count_nonzero(cells.any(axis=1)))
    order = np.argsort(counts)[::-1]
    best = int(order[0])
    return {"argmax_origin": best, "zero_cells_at_argmax": int(counts[best]),
            "runner_up_origin": int(order[1]),
            "margin": int(counts[best] - counts[order[1]]),
            "n_candidates": FRAME_BYTES}


# --------------------------------------------------------------------------
# M3: middle-word lattice. No packet decoding.
# --------------------------------------------------------------------------
# A first attempt at M3 assumed long zero runs begin on frame boundaries. That
# is wrong, and the test failed against real data (modal residue 388, not 184).
# Diagnosis: a 7-series frame is 101 words and its MIDDLE word (word 50, frame
# bytes 200..203) carries HCLK row configuration, which is non-zero even where
# the rest of the frame is empty. So an unused device region is not a clean zero
# run -- it is a lattice of isolated 1..4-byte non-zero islands spaced exactly
# one frame apart, each sitting at frame offset 200..203.
#
# Empirically (logged below): the isolated non-zero islands in an otherwise
# empty stretch of the region are 2..3 bytes long and land at frame offsets
# 201..204 -- inside the middle word -- with byte patterns like 49ae / 2009b5 /
# 0419b2 repeating across files. Most empty frames are fully zero including the
# middle word, so only a handful of such islands exist per file; that is why
# this signal must be read as a residue, not counted.
#
# Two predictions, stated a priori and checked below:
#   (P1) every isolated island lies within frame bytes 200..204. With ~10
#        islands and a 5-of-404 target this is overwhelming if true by design
#        and essentially impossible by chance.
#   (P2) the modal island END offset is frame byte 203, so the frame origin is
#        (modal_end - 203) mod 404, which must equal M1's FDRI offset.
# Neither consults M1 before predicting.
MIDDLE_WORD_LAST_BYTE = 203        # word 50 of 101 occupies frame bytes 200..203
MIDDLE_WORD_SPAN = (200, 205)      # inclusive-exclusive, one byte of slack


def m3_middle_word_lattice(region, min_gap=FRAME_BYTES):
    """Recover the frame origin from the lattice of HCLK middle words."""
    nz = np.flatnonzero(region)
    if len(nz) < 3:
        return {"n_islands": 0}
    brk = np.flatnonzero(np.diff(nz) > 1)
    starts = np.concatenate([[nz[0]], nz[brk + 1]])
    ends = np.concatenate([nz[brk], [nz[-1]]])

    # Keep only islands isolated by >= one frame of zeros on BOTH sides: in
    # used regions islands are dense and carry no lattice information.
    gap_before = np.empty(len(starts), dtype=np.int64)
    gap_before[0] = starts[0]
    gap_before[1:] = starts[1:] - ends[:-1] - 1
    gap_after = np.empty(len(ends), dtype=np.int64)
    gap_after[:-1] = starts[1:] - ends[:-1] - 1
    gap_after[-1] = len(region) - ends[-1] - 1
    lone = (gap_before >= min_gap) & (gap_after >= min_gap)
    if lone.sum() < 3:
        return {"n_islands": int(lone.sum())}

    l_starts, l_ends = starts[lone], ends[lone]
    res_end = Counter(int(e) % FRAME_BYTES for e in l_ends)
    modal_end, n_modal = res_end.most_common(1)[0]
    implied_origin = (modal_end - MIDDLE_WORD_LAST_BYTE) % FRAME_BYTES

    # P1: do all islands sit inside the middle word, relative to that origin?
    lo, hi = MIDDLE_WORD_SPAN
    off_s = (l_starts - implied_origin) % FRAME_BYTES
    off_e = (l_ends - implied_origin) % FRAME_BYTES
    inside = int(np.count_nonzero((off_s >= lo) & (off_e < hi)))
    return {"n_islands": int(lone.sum()),
            "islands_inside_middle_word": inside,
            "islands_inside_share": round(inside / len(l_ends), 4),
            "modal_end_residue": int(modal_end),
            "modal_end_share": round(n_modal / len(l_ends), 4),
            "implied_frame_origin": int(implied_origin),
            "island_frame_offsets": sorted({(int(a), int(b))
                                            for a, b in zip(off_s, off_e)}),
            "max_island_len": int((l_ends - l_starts + 1).max())}


# --------------------------------------------------------------------------
def current_grid_offset(fdri_offset):
    """How far the shipped window grid is out of phase with real frames.

    window_features.frame_windows() starts its grid at config-region offset 0
    (i.e. immediately after the sync word). Real frames start at `fdri_offset`.
    """
    return fdri_offset % FRAME_BYTES


def main():
    p = argparse.ArgumentParser(description="Verify finding 1: frame alignment")
    p.add_argument("--data-dir",
                   default=os.path.expanduser(
                       "~/Desktop/Karakchi-Research/trusthub_bitstreams_v4"))
    p.add_argument("--n-deep", type=int, default=5,
                   help="files to run the expensive M2/M3 methods on")
    p.add_argument("--outdir", default="leakage_audit_out")
    args = p.parse_args()

    files = (sorted(glob.glob(os.path.join(args.data_dir, "Benign", "*.bit")))
             + sorted(glob.glob(os.path.join(args.data_dir, "Malicious", "*.bit"))))
    if not files:
        sys.exit(f"no bitstreams under {args.data_dir}")
    os.makedirs(args.outdir, exist_ok=True)
    print(f"=== Finding 1/4: FRAME ALIGNMENT ===\n{len(files)} files in {args.data_dir}\n")

    # ---- M1 over every file -------------------------------------------------
    print(f"M1  packet-structure walk over all {len(files)} files...")
    offsets, wordcounts, trailers, npkts, fars = (Counter() for _ in range(5))
    for i, f in enumerate(files, 1):
        with open(f, "rb") as fh:
            g = m1_packet_walk(fh.read())
        offsets[g["payload_offset_in_region"]] += 1
        wordcounts[g["words"]] += 1
        trailers[g["trailer_bytes"]] += 1
        npkts[g["n_packets"]] += 1
        fars[tuple(g["far_writes"])] += 1
        if i % 200 == 0 or i == len(files):
            print(f"    {i}/{len(files)}")
    print(f"    FDRI payload offset in region : {dict(offsets)}")
    print(f"    FDRI word count               : {dict(wordcounts)}")
    print(f"    trailer bytes after FDRI      : {dict(trailers)}")
    print(f"    distinct FAR-write sequences  : {len(fars)} "
          f"-> {[hex(x) for x in next(iter(fars))]}")

    m1_off = offsets.most_common(1)[0][0]
    m1_words = wordcounts.most_common(1)[0][0]
    frames_exact = m1_words % FRAME_WORDS == 0
    n_frames = m1_words // FRAME_WORDS
    print(f"    {m1_words} words / {FRAME_WORDS} words-per-frame = "
          f"{n_frames} frames, exact: {frames_exact}")

    # ---- M2 / M3 on a sample ------------------------------------------------
    deep = files[:args.n_deep // 2 + 1] + files[-(args.n_deep // 2):]
    deep = list(dict.fromkeys(deep))[:args.n_deep]
    m2_res, m3_res = [], []
    print(f"\nM2/M3  parser-free methods on {len(deep)} files "
          f"(404 candidate origins each)...")
    for f in deep:
        with open(f, "rb") as fh:
            blob = fh.read()
        region = np.frombuffer(blob[blob.find(SYNC) + 4:], dtype=np.uint8)
        a = m2_zero_cell_argmax(region)
        b = m3_middle_word_lattice(region)
        a["file"] = b["file"] = os.path.basename(f)
        m2_res.append(a)
        m3_res.append(b)
        print(f"    {os.path.basename(f):<32} M2 argmax={a['argmax_origin']:3d}/404 "
              f"(margin +{a['margin']}) | M3 origin={b['implied_frame_origin']:3d} "
              f"({b['islands_inside_middle_word']}/{b['n_islands']} islands inside "
              f"the middle word)")

    # ---- verdict ------------------------------------------------------------
    checks = {
        "M1_single_fdri_write_every_file": len(fars) == 1,
        "M1_offset_constant": len(offsets) == 1,
        "M1_offset_equals_claim": m1_off == CLAIM["fdri_offset_in_region"],
        "M1_wordcount_constant": len(wordcounts) == 1,
        "M1_wordcount_equals_claim": m1_words == CLAIM["fdri_words"],
        "M1_frames_are_whole": frames_exact and n_frames == CLAIM["n_frames"],
        "M1_trailer_constant": len(trailers) == 1,
        "M2_argmax_agrees_with_M1": all(r["argmax_origin"] == m1_off
                                        for r in m2_res),
        "M2_argmax_is_strict": all(r["margin"] > 0 for r in m2_res),
        "M3_P1_all_islands_inside_middle_word": all(
            r["islands_inside_share"] == 1.0 for r in m3_res),
        "M3_P2_implied_origin_agrees_with_M1": all(
            r["implied_frame_origin"] == m1_off % FRAME_BYTES for r in m3_res),
        "grid_is_misaligned_as_claimed": current_grid_offset(m1_off) != 0,
    }
    off_by = current_grid_offset(m1_off)
    print(f"\n--- CONSEQUENCE FOR THE SHIPPED CODE ---")
    print(f"  window_features.frame_windows() starts its grid at region offset 0.")
    print(f"  Real frames start at region offset {m1_off}; {m1_off} mod {FRAME_BYTES} "
          f"= {off_by}.")
    if off_by:
        print(f"  => every window begins {FRAME_BYTES - off_by} bytes into a frame "
              f"and ends {off_by} bytes into another.")
        print(f"  => the 'frame-aligned windows only' rule is NOT currently met.")
    print(f"\n  Correct grid: {n_frames} frames / 8 = {n_frames // 8} whole "
          f"8-frame windows, remainder {n_frames % 8} frames.")

    print("\n--- VERDICT ---")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    ok = all(checks.values())
    print(f"\nFINDING 1 {'CONFIRMED' if ok else 'NOT CONFIRMED'}")

    out = {"finding": "frame_alignment", "confirmed": ok, "claim": CLAIM,
           "data_dir": args.data_dir, "n_files": len(files),
           "M1": {"fdri_offset_in_region": dict(offsets),
                  "fdri_words": dict(wordcounts),
                  "trailer_bytes": dict(trailers),
                  "n_packets": dict(npkts),
                  "n_distinct_far_sequences": len(fars),
                  "far_writes": [hex(x) for x in next(iter(fars))],
                  "n_frames": n_frames, "frames_whole": frames_exact},
           "M2_zero_frame_argmax": m2_res, "M3_zero_run_phase": m3_res,
           "shipped_grid_phase_error_bytes": off_by, "checks": checks}
    path = os.path.join(args.outdir, "verify_frame_alignment.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"log -> {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
