# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L1 -- localization label extraction from Vivado
#              logic-location (.ll) files. Produces frame- and window-level
#              labels for an admitted retention-positive host, with provenance.
#
#              KEY MECHANISM (verified, not assumed). A 7-series .ll line is
#                  Bit <bit_offset> 0x<FAR> <frame_bit_offset> <info>
#              and `bit_offset - frame_bit_offset` is an exact multiple of
#              3232 (= 404 bytes x 8) on every line of every file checked, so
#                  frame_index = (bit_offset - frame_bit_offset) / 3232
#              maps a named design object DIRECTLY onto the FDRI payload frame
#              grid this project already validated (10,008 frames, offset 184).
#              This sidesteps the unsolved frame-index -> FAR mapping entirely:
#              Vivado states the bit position itself. The extractor ASSERTS
#              the divisibility on every line and aborts if it ever fails.
#
#              WHAT THE LABELS MEAN -- read before using them.
#              A .ll file enumerates CONFIGURATION MEMORY CELLS ONLY: flip-flop
#              latches, LUTRAM/SRL, and block RAM. It does NOT enumerate LUT
#              truth tables or routing PIPs. Therefore:
#                TROJAN_CONFIRMED  a frame provably holding >=1 trojan-owned
#                                  memory-cell bit. HIGH PRECISION.
#                HOST_OCCUPIED     >=1 host-owned memory-cell bit, no trojan.
#                NO_LL_COVERAGE    no memory-cell bits; says NOTHING about
#                                  whether trojan LUT/routing config lives
#                                  there.
#              These are positive SEEDS, not the trojan's full extent. Recall
#              and IoU are NOT computable from them. See the report for the
#              scope of claims this supports.
#
# Usage:
#   python3 localization_labels.py --design AES-T1000 [--builds-dir ...]

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

from bitstream_io import ZYNQ7020_V4, fdri_payload_and_meta, payload_hash
from split_utils import FRAME_BYTES

SCHEMA = "localization_labels_v1"
FRAME_BITS = FRAME_BYTES * 8          # 3232
WINDOW_FRAMES = 8

TROJAN_CONFIRMED = "TROJAN_CONFIRMED"
HOST_OCCUPIED = "HOST_OCCUPIED"
NO_LL_COVERAGE = "NO_LL_COVERAGE"

_BIT = re.compile(r"^Bit\s+(\d+)\s+0x([0-9a-fA-F]+)\s+(\d+)\s+(.*)$")
_NET = re.compile(r"Net=(\S+)")
_BLOCK = re.compile(r"Block=(\S+)")


def load_trojan_patterns(path):
    """Discriminative trojan name patterns, one per line (`#` comments)."""
    pats = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                pats.append(line)
    return pats


def _pat_to_re(pat):
    """Vivado glob (`*Trojan*`) -> anchored regex."""
    return re.compile("^" + ".*".join(re.escape(p) for p in pat.split("*"))
                      + "$")


def parse_ll(path, trojan_res):
    """Frame-indexed .ll contents.

    Returns (frame -> {"trojan": n, "host": n}), plus per-net trojan detail
    and counters. Asserts frame-grid divisibility on every line.
    """
    frames = defaultdict(lambda: {"trojan": 0, "host": 0})
    trojan_bits, n_lines, bad = [], 0, 0
    with open(path) as f:
        for line in f:
            m = _BIT.match(line)
            if not m:
                continue
            n_lines += 1
            bit, far, foff, info = (int(m.group(1)), m.group(2),
                                    int(m.group(3)), m.group(4))
            delta = bit - foff
            if delta % FRAME_BITS:
                bad += 1
                continue
            fi = delta // FRAME_BITS
            net = (_NET.search(info) or [None, ""])[1] if _NET.search(info) \
                else ""
            is_tro = any(r.match(net) for r in trojan_res) if net else False
            frames[fi]["trojan" if is_tro else "host"] += 1
            if is_tro:
                blk = _BLOCK.search(info)
                trojan_bits.append({"frame": fi, "bit_offset": bit,
                                    "far": "0x" + far, "frame_bit": foff,
                                    "net": net,
                                    "block": blk.group(1) if blk else ""})
    if bad:
        raise AssertionError(
            f"{path}: {bad}/{n_lines} .ll lines are not frame-grid aligned "
            f"-- the frame_index derivation is invalid for this file")
    return frames, trojan_bits, n_lines


def label_frames(frames, n_frames):
    labels = []
    for fi in range(n_frames):
        c = frames.get(fi)
        if not c:
            labels.append(NO_LL_COVERAGE)
        elif c["trojan"]:
            labels.append(TROJAN_CONFIRMED)
        else:
            labels.append(HOST_OCCUPIED)
    return labels


def windows_from_frames(labels, window_frames=WINDOW_FRAMES):
    """Window label = TROJAN_CONFIRMED if any constituent frame is."""
    out = []
    for w0 in range(0, len(labels), window_frames):
        chunk = labels[w0:w0 + window_frames]
        if TROJAN_CONFIRMED in chunk:
            lab = TROJAN_CONFIRMED
        elif HOST_OCCUPIED in chunk:
            lab = HOST_OCCUPIED
        else:
            lab = NO_LL_COVERAGE
        out.append({"window_index": w0 // window_frames,
                    "first_frame": w0, "n_frames": len(chunk), "label": lab,
                    "n_trojan_frames": chunk.count(TROJAN_CONFIRMED)})
    return out


def frame_diff(pa, pb):
    """Indices of frames differing between two FDRI payloads."""
    import numpy as np
    a = fdri_payload_and_meta(pa, ZYNQ7020_V4)[0]
    b = fdri_payload_and_meta(pb, ZYNQ7020_V4)[0]
    n = len(a) // FRAME_BYTES
    A = a[:n * FRAME_BYTES].reshape(n, FRAME_BYTES)
    B = b[:n * FRAME_BYTES].reshape(n, FRAME_BYTES)
    return sorted(int(i) for i in np.flatnonzero((A != B).any(axis=1)))


def main():
    p = argparse.ArgumentParser(description="Extract localization labels from .ll")
    p.add_argument("--design", default="AES-T1000")
    p.add_argument("--builds-dir",
                   default="rebuild_pilot/pilot_artifacts/builds")
    p.add_argument("--patterns", default=None,
                   help="default: rebuild_pilot/trojan_patterns_<design>.txt")
    p.add_argument("--outdir", default="localization_corpus")
    p.add_argument("--malicious-label", default="TjIn")
    p.add_argument("--benign-label", default="TjFree")
    args = p.parse_args()

    pat_path = args.patterns or os.path.join(
        "rebuild_pilot", f"trojan_patterns_{args.design}.txt")
    patterns = load_trojan_patterns(pat_path)
    trojan_res = [_pat_to_re(x) for x in patterns]
    design_dir = os.path.join(args.builds_dir, args.design)
    if not os.path.isdir(design_dir):
        sys.exit(f"no builds for {args.design} under {args.builds_dir}")

    print(f"=== Localization label extraction: {args.design} ===")
    print(f"trojan patterns ({pat_path}): {patterns}")
    print(f"frame grid: {ZYNQ7020_V4.n_frames} frames x {FRAME_BYTES} B; "
          f"window = {WINDOW_FRAMES} frames\n")

    os.makedirs(os.path.join(args.outdir, "labels"), exist_ok=True)
    configs = sorted(os.listdir(os.path.join(design_dir,
                                             args.malicious_label)))
    entries, all_trojan_frames = [], set()

    for cfg in configs:
        rec = {"design": args.design, "config": cfg}
        for label in (args.malicious_label, args.benign_label):
            d = os.path.join(design_dir, label, cfg)
            ll = os.path.join(d, f"{args.design}_{label}_{cfg}.ll")
            bit = os.path.join(d, f"{args.design}_{label}_{cfg}.bit")
            if not (os.path.exists(ll) and os.path.exists(bit)):
                print(f"  ({label}/{cfg}: artifacts missing, skipped)")
                continue
            frames, tbits, n_lines = parse_ll(ll, trojan_res)
            labels = label_frames(frames, ZYNQ7020_V4.n_frames)
            wins = windows_from_frames(labels)
            tro_frames = sorted(i for i, l in enumerate(labels)
                                if l == TROJAN_CONFIRMED)
            tro_wins = sorted(w["window_index"] for w in wins
                              if w["label"] == TROJAN_CONFIRMED)
            digest = payload_hash(bit, ZYNQ7020_V4)

            tag = f"{args.design}_{label}_{cfg}"
            with open(os.path.join(args.outdir, "labels",
                                   f"{tag}_frames.csv"), "w",
                      newline="") as f:
                w = csv.writer(f)
                w.writerow(["frame_index", "label", "n_trojan_bits",
                            "n_host_bits"])
                for fi in range(ZYNQ7020_V4.n_frames):
                    c = frames.get(fi, {"trojan": 0, "host": 0})
                    w.writerow([fi, labels[fi], c["trojan"], c["host"]])
            with open(os.path.join(args.outdir, "labels",
                                   f"{tag}_windows.csv"), "w",
                      newline="") as f:
                w = csv.DictWriter(f, fieldnames=["window_index",
                                                  "first_frame", "n_frames",
                                                  "label", "n_trojan_frames"])
                w.writeheader()
                w.writerows(wins)

            side = {
                "label": label, "ll_file": ll, "bit_file": bit,
                "fdri_payload_digest": digest,
                "ll_bit_lines": n_lines,
                "ll_sha256": hashlib.sha256(
                    open(ll, "rb").read(1 << 20)).hexdigest()[:16] + "...(1MB prefix)",
                "frames_trojan_confirmed": tro_frames,
                "n_frames_trojan_confirmed": len(tro_frames),
                "n_frames_host_occupied": sum(1 for l in labels
                                              if l == HOST_OCCUPIED),
                "n_frames_no_ll_coverage": sum(1 for l in labels
                                               if l == NO_LL_COVERAGE),
                "windows_trojan_confirmed": tro_wins,
                "trojan_bits": tbits,
            }
            rec[label] = side
            if label == args.malicious_label:
                all_trojan_frames.update(tro_frames)
            print(f"  {label}/{cfg}: {n_lines:>9} .ll bits | trojan frames "
                  f"{tro_frames or '[]'} | windows {tro_wins or '[]'} | "
                  f"host-occupied {side['n_frames_host_occupied']}")

        # Matched-pair diff: DIAGNOSTIC ONLY, never a label.
        if args.malicious_label in rec and args.benign_label in rec:
            diff = frame_diff(rec[args.benign_label]["bit_file"],
                              rec[args.malicious_label]["bit_file"])
            tro = set(rec[args.malicious_label]["frames_trojan_confirmed"])
            rec["matched_pair_diff_diagnostic"] = {
                "n_frames_differing": len(diff),
                "trojan_confirmed_frames_inside_diff":
                    sorted(tro & set(diff)),
                "trojan_confirmed_frames_outside_diff":
                    sorted(tro - set(diff)),
                "note": "P&R displacement dominates this diff; it is NOT "
                        "localization ground truth (standing decision).",
            }
            print(f"    matched-pair diff: {len(diff)} frames "
                  f"(diagnostic); confirmed-trojan frames inside diff: "
                  f"{sorted(tro & set(diff))}")
        entries.append(rec)

    manifest = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "design": args.design,
        "host_admission": "ADMIT_LOCALIZATION (retention_screen.py)",
        "frame_grid": {"n_frames": ZYNQ7020_V4.n_frames,
                       "frame_bytes": FRAME_BYTES,
                       "frame_bits": FRAME_BITS,
                       "window_frames": WINDOW_FRAMES,
                       "n_windows": ZYNQ7020_V4.n_frames // WINDOW_FRAMES,
                       "fdri_offset_in_region":
                           ZYNQ7020_V4.fdri_offset_in_region},
        "frame_index_derivation": {
            "formula": "frame_index = (ll_bit_offset - ll_frame_bit_offset) "
                       "/ 3232",
            "validation": "divisibility asserted on EVERY .ll line of every "
                          "build; extraction aborts on any violation",
        },
        "trojan_patterns": patterns,
        "label_semantics": {
            TROJAN_CONFIRMED: "frame provably holds >=1 trojan-owned "
                              "configuration MEMORY-CELL bit (high "
                              "precision)",
            HOST_OCCUPIED: "holds host-owned memory-cell bits, no trojan",
            NO_LL_COVERAGE: "no memory-cell bits; silent about LUT/routing "
                            "configuration",
        },
        "coverage_limitation": (".ll enumerates flip-flop/LUTRAM/BRAM "
                                "configuration cells only -- not LUT truth "
                                "tables and not routing. Labels are positive "
                                "SEEDS, not the trojan's full extent; recall "
                                "and IoU are NOT computable from them."),
        "builds": entries,
        "union_trojan_frames_across_configs": sorted(all_trojan_frames),
    }
    mpath = os.path.join(args.outdir, "localization_manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nunion of confirmed-trojan frames across configs: "
          f"{sorted(all_trojan_frames)}")
    print(f"manifest -> {mpath}")
    print(f"labels   -> {os.path.join(args.outdir, 'labels')}/")


if __name__ == "__main__":
    main()
