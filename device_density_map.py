# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L2 step 0 -- measured device occupancy map.
#
#              The L1b baseline showed that per-window set-bit density
#              (popcount) matches or beats every differential scorer, and that
#              normalising a differential by density collapses its ranking
#              tenfold. Occupancy is therefore the dominant confound in
#              bitstream localization.
#
#              To separate a genuine localization signal from that confound,
#              the L2 pinned builds must place the SAME trojan in regions of
#              DIFFERING density. This script measures the density landscape
#              from the existing AES-T1000 builds and, using the SLICE ->
#              frame-index correspondence recovered from the .ll files,
#              proposes concrete pblock SLICE regions spanning it.
#
#              Density is measured on the BENIGN builds: the pinned-build
#              experiment asks where the trojan can be placed within the host
#              design's own occupancy landscape, so the host (not the
#              trojan-bearing build) defines that landscape.
#
# Usage:
#   python3 device_density_map.py [--n-regions 6]

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from split_utils import FRAME_BYTES

SCHEMA = "device_density_map_v1"
FRAME_BITS = FRAME_BYTES * 8
WINDOW_FRAMES = 8

_BIT = re.compile(r"^Bit\s+(\d+)\s+0x([0-9a-fA-F]+)\s+(\d+)\s+(.*)$")
_BLOCK = re.compile(r"Block=(SLICE_X(\d+)Y(\d+))")


def slice_frame_map(ll_paths):
    """Empirical SLICE -> {frame_index} from .ll files.

    Vivado states the bit position, and
    frame_index = (bit_offset - frame_bit_offset) / 3232 is exact, so each
    memory cell reveals which frame configures its SLICE.
    """
    s2f = defaultdict(set)
    coords = {}
    for p in ll_paths:
        with open(p) as f:
            for line in f:
                m = _BIT.match(line)
                if not m:
                    continue
                delta = int(m.group(1)) - int(m.group(3))
                if delta % FRAME_BITS:
                    raise AssertionError(f"{p}: non-frame-aligned .ll line")
                b = _BLOCK.search(m.group(4))
                if not b:
                    continue
                name, x, y = b.group(1), int(b.group(2)), int(b.group(3))
                s2f[name].add(delta // FRAME_BITS)
                coords[name] = (x, y)
    return s2f, coords


def window_density(payload, window_frames=WINDOW_FRAMES):
    wb = window_frames * FRAME_BYTES
    n = len(payload) // wb
    W = payload[:n * wb].reshape(n, wb)
    return np.unpackbits(W, axis=1).sum(axis=1).astype(np.int64)


def main():
    p = argparse.ArgumentParser(description="Measured device density map")
    p.add_argument("--manifest",
                   default=os.path.join("localization_corpus",
                                        "localization_manifest.json"))
    p.add_argument("--n-regions", type=int, default=6)
    p.add_argument("--out", default=os.path.join("localization_corpus",
                                                 "device_density_map.json"))
    args = p.parse_args()

    with open(args.manifest) as f:
        man = json.load(f)
    benign = [b["TjFree"] for b in man["builds"] if "TjFree" in b]
    print(f"=== Device density map (AES-T1000, {len(benign)} benign builds) ===")

    # ---- per-window occupancy, averaged over benign builds -----------------
    dens = np.stack([window_density(fdri_payload(b["bit_file"], ZYNQ7020_V4))
                     for b in benign])
    mean_d = dens.mean(axis=0)
    n_win = len(mean_d)
    nonempty = mean_d > 0
    print(f"windows: {n_win} | non-empty: {int(nonempty.sum())} | "
          f"empty: {int((~nonempty).sum())}")
    q = {f"p{k}": float(np.percentile(mean_d[nonempty], k))
         for k in (10, 25, 50, 75, 90, 99)}
    print(f"non-empty density percentiles: "
          + ", ".join(f"{k} {v:.0f}" for k, v in q.items()))

    # ---- SLICE -> frame -> window ------------------------------------------
    s2f, coords = slice_frame_map([b["ll_file"] for b in benign])
    print(f"SLICEs observed in .ll: {len(s2f)}")

    slice_rows = []
    for name, frames in s2f.items():
        x, y = coords[name]
        wins = sorted({fi // WINDOW_FRAMES for fi in frames})
        d = float(np.mean([mean_d[w] for w in wins if w < n_win]))
        slice_rows.append({"slice": name, "x": x, "y": y,
                           "frames": sorted(frames), "windows": wins,
                           "mean_window_density": d})
    slice_rows.sort(key=lambda r: r["mean_window_density"])

    # ---- propose pblock regions spanning the density range -----------------
    # Group observed SLICEs into X-column bands (a pblock is a rectangle in
    # SLICE coordinates) and rank bands by the density of the windows they
    # configure. Then pick regions evenly across that ranking.
    band = defaultdict(list)
    for r in slice_rows:
        band[(r["x"] // 8) * 8].append(r)
    band_stats = []
    for x0, rows in band.items():
        ys = [r["y"] for r in rows]
        d = float(np.mean([r["mean_window_density"] for r in rows]))
        band_stats.append({"x0": x0, "x1": x0 + 7,
                           "y_min": min(ys), "y_max": max(ys),
                           "n_slices_observed": len(rows),
                           "mean_window_density": d,
                           "windows": sorted({w for r in rows
                                              for w in r["windows"]})})
    band_stats.sort(key=lambda b: b["mean_window_density"])

    k = min(args.n_regions, len(band_stats))
    picks = [band_stats[round(i * (len(band_stats) - 1) / max(1, k - 1))]
             for i in range(k)]
    # de-duplicate while preserving the density ordering
    seen, regions = set(), []
    for b in picks:
        if b["x0"] in seen:
            continue
        seen.add(b["x0"])
        y0 = max(0, b["y_min"])
        y1 = b["y_max"]
        regions.append({
            "region_id": f"R{len(regions)}",
            "slice_range": f"SLICE_X{b['x0']}Y{y0}:SLICE_X{b['x1']}Y{y1}",
            "mean_window_density": round(b["mean_window_density"], 1),
            "n_slices_observed": b["n_slices_observed"],
            "target_windows_observed": b["windows"][:12],
        })

    print(f"\nproposed pinned regions (density-ordered, sparse -> dense):")
    for r in regions:
        print(f"  {r['region_id']}  {r['slice_range']:<34} "
              f"mean window density {r['mean_window_density']:>8.1f} "
              f"({r['n_slices_observed']} slices observed)")

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "design": man["design"],
        "measured_on": "benign builds (the host defines the occupancy "
                       "landscape the trojan is placed into)",
        "n_windows": n_win,
        "n_windows_nonempty": int(nonempty.sum()),
        "density_percentiles_nonempty": q,
        "rationale": "L1b showed popcount matches/beats every differential "
                     "scorer and that density-normalising a differential "
                     "collapses its rank 37.5 -> 388.8. Pinning the same "
                     "trojan across differing-density regions is the control "
                     "that separates localization from occupancy.",
        "proposed_regions": regions,
        "n_slices_observed": len(s2f),
        "slice_density_extremes": {
            "sparsest": slice_rows[:5],
            "densest": slice_rows[-5:],
        },
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nmap -> {args.out}")


if __name__ == "__main__":
    main()
