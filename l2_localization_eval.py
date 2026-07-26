# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L2 evaluation -- the density-controlled localization
#              test the L1b baseline showed was necessary.
#
#              L1b finding: per-window set-bit density (popcount) matched or
#              beat every differential scorer, and density-normalising a
#              differential collapsed its rank 37.5 -> 388.8. Every apparent
#              localization success was explicable as "the trojan sits in the
#              densest region of the device".
#
#              L2 removes that confound by construction: the SAME trojan
#              netlist is pinned into regions of measured, widely differing
#              host density, so trojan position and local density are
#              decoupled. The question this script answers is:
#
#                  Does a scorer's ranking of the trojan windows HOLD UP when
#                  the trojan is moved into sparse regions, or does it only
#                  work where the device is already dense?
#
#              A scorer that localizes ranks the trojan windows well at every
#              region. A scorer reading occupancy ranks them well only in
#              dense regions, and its performance correlates with region
#              density. That correlation is the discriminator.
#
#              Ground truth is the MEASURED trojan frame set per build, taken
#              from each build's own .ll (Vivado states the bit position;
#              frame_index = (bit - frame_bit)/3232 is exact) -- not from the
#              pblock, which only partially contained the trojan because some
#              trojan LUTs are fused into MUXF8 macros with host logic.
#
# Usage:
#   python3 l2_localization_eval.py

import argparse
import csv
import glob
import json
import os
import re
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from split_utils import FRAME_BYTES

SCHEMA = "l2_localization_eval_v2"
WINDOW_FRAMES = 8
FRAME_BITS = FRAME_BYTES * 8

_BIT = re.compile(r"^Bit\s+(\d+)\s+0x([0-9a-fA-F]+)\s+(\d+)\s+(.*)$")
_NET = re.compile(r"Net=(\S+)")

# Per-design discriminative trojan net patterns (benign controls verified
# clean in retention_screen.py / localization_labels.py).
DESIGNS = {
    "AES-T1000": {
        "l2_dir": "rebuild_pilot/pilot_artifacts/l2",
        "benign_ref": ("rebuild_pilot/pilot_artifacts/builds/AES-T1000/"
                       "TjFree/C1/AES-T1000_TjFree_C1.bit"),
        "tro_re": re.compile(r"^(Trojan/|Tj_Trigger/)|/Trojan/|"
                             r"/Tj_Trigger/|lfsr|TSC"),
        "out_prefix": "l2",
    },
    "b15-T200": {
        "l2_dir": "rebuild_pilot/pilot_artifacts/l2_b15",
        "benign_ref": ("rebuild_pilot/pilot_artifacts/builds/b15-T200/"
                       "TjFree/C1/b15-T200_TjFree_C1.bit"),
        "tro_re": re.compile(r"UTj|_Tj\b|MUXed|_TjN"),
        "out_prefix": "l2_b15",
    },
}


def trojan_frames(ll_path, tro_re):
    fr = set()
    with open(ll_path) as f:
        for line in f:
            m = _BIT.match(line)
            if not m:
                continue
            d = int(m.group(1)) - int(m.group(3))
            if d % FRAME_BITS:
                raise AssertionError(f"{ll_path}: non-frame-aligned .ll line")
            n = _NET.search(m.group(4))
            if n and tro_re.search(n.group(1)):
                fr.add(d // FRAME_BITS)
    return sorted(fr)


def windows(payload):
    wb = WINDOW_FRAMES * FRAME_BYTES
    n = len(payload) // wb
    return payload[:n * wb].reshape(n, wb)


def ranks_of(scores, idx):
    order = np.argsort(-scores, kind="stable")
    r = np.empty(len(scores), dtype=float)
    r[order] = np.arange(1, len(scores) + 1)
    uniq, inv = np.unique(-scores, return_inverse=True)
    for g in range(len(uniq)):
        m = inv == g
        if m.sum() > 1:
            r[m] = r[m].mean()
    return {int(i): float(r[i]) for i in idx}


def main():
    p = argparse.ArgumentParser(description="L2 density-controlled evaluation")
    p.add_argument("--design", default="AES-T1000", choices=list(DESIGNS))
    args = p.parse_args()
    cfg = DESIGNS[args.design]

    ref = windows(fdri_payload(cfg["benign_ref"], ZYNQ7020_V4))
    ref_bits = np.unpackbits(ref, axis=1)
    # MEASURED local density: set-bit count of each window in this design's
    # own benign build. Using the density where the trojan actually landed
    # (rather than a nominal region figure) makes the covariate comparable
    # across designs of very different size.
    ref_density = ref_bits.sum(axis=1).astype(float)

    builds = []
    for bit in sorted(glob.glob(os.path.join(cfg["l2_dir"], "*.bit"))):
        tag = os.path.basename(bit)[:-4]
        ll = bit[:-4] + ".ll"
        if not os.path.exists(ll):
            continue
        tf = trojan_frames(ll, cfg["tro_re"])
        tw = sorted({f // WINDOW_FRAMES for f in tf})
        builds.append({
            "tag": tag, "bit": bit,
            "trojan_frames": tf, "trojan_windows": tw,
            # local host density at the trojan's landing windows
            "local_density": float(np.mean([ref_density[w] for w in tw]))
            if tw else None,
        })

    print(f"=== L2 density-controlled localization evaluation: {args.design} ===")
    print(f"{len(builds)} builds | ground truth = measured .ll trojan frames "
          f"per build")
    print(f"density covariate = measured host density at the trojan's "
          f"landing window(s)\n")

    n_win = ref.shape[0]
    rows, per_build = [], {}
    for b in builds:
        W = windows(fdri_payload(b["bit"], ZYNQ7020_V4))
        Wb = np.unpackbits(W, axis=1)
        t = b["trojan_windows"]
        pc = Wb.sum(axis=1).astype(float)
        s = {
            "popcount": pc,
            "pair_hamming": np.abs(Wb - ref_bits).sum(axis=1).astype(float),
            "pair_l1": np.abs(W.astype(np.int32)
                              - ref.astype(np.int32)).sum(axis=1).astype(float),
        }
        s["pair_l1_per_bit"] = s["pair_l1"] / (pc + 1.0)
        per_build[b["tag"]] = {"trojan_windows": t,
                               "local_density": b["local_density"],
                               "scorers": {}}
        d = b["local_density"]
        dtxt = f"{d:>8.1f}" if d is not None else "   (n/a)"
        print(f"--- {b['tag']:<10} density {dtxt} | trojan windows {t}")
        for name, sc in s.items():
            r = ranks_of(sc, t)
            best = min(r.values())
            med = float(np.median(list(r.values())))
            per_build[b["tag"]]["scorers"][name] = {
                "ranks": r, "best_rank": best, "median_rank": med}
            rows.append({"build": b["tag"], "local_density": d,
                         "scorer": name,
                         "best_rank": best, "median_rank": med,
                         "n_trojan_windows": len(t), "n_windows": n_win})
            print(f"      {name:<16} best {best:>7.1f}/{n_win} | median "
                  f"{med:>7.1f}")
        print()

    # ---- the discriminator: does performance track region density? ---------
    print("=== DISCRIMINATOR: correlation of rank with region density ===")
    print("(a scorer reading OCCUPANCY improves in dense regions -> strong")
    print(" negative corr of rank with density; a scorer that LOCALIZES is")
    print(" insensitive to density -> corr near zero)\n")
    corr = {}
    for name in ("popcount", "pair_hamming", "pair_l1", "pair_l1_per_bit"):
        pts = [(r["local_density"], r["median_rank"]) for r in rows
               if r["scorer"] == name and r["local_density"] is not None]
        if len(pts) < 3:
            continue
        x = np.array([p[0] for p in pts])
        y = np.array([p[1] for p in pts])
        med = float(np.median(y))
        if x.std() == 0:
            # No density variation to correlate against. This is itself
            # informative: the trojan landed in an equally-dense (here empty)
            # neighbourhood in every build, so this design supplies a
            # single-density condition rather than a density gradient.
            c = None
            verdict = (f"NO DENSITY VARIANCE (all landings at density "
                       f"{x[0]:.0f}) -- single-condition, not a gradient")
        else:
            c = float(np.corrcoef(x, y)[0, 1])
            verdict = ("tracks density (occupancy-driven)" if c < -0.5
                       else "insensitive to density" if abs(c) < 0.5
                       else "inverse (worse when dense)")
        corr[name] = {"pearson_r_rank_vs_density": (round(c, 3)
                                                    if c is not None else None),
                      "density_variance": float(x.std()),
                      "median_rank_over_regions": med,
                      "worst_rank": float(y.max()),
                      "best_rank": float(y.min()),
                      "n_regions": len(pts)}
        rtxt = f"r = {c:+.3f}" if c is not None else "r =    n/a"
        print(f"  {name:<16} {rtxt} | median rank over regions "
              f"{med:>7.1f} | worst {y.max():>7.1f} | {verdict}")

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "design": args.design,
        "n_builds": len(builds),
        "n_windows": n_win,
        "random_expected_rank": (n_win + 1) / 2,
        "ground_truth": "measured .ll trojan frames per build (not the "
                        "pblock: some trojan LUTs are fused into MUXF8 "
                        "macros with host logic and escaped containment)",
        "benign_reference": cfg["benign_ref"],
        "per_build": per_build,
        "density_correlation": corr,
    }
    os.makedirs("localization_corpus", exist_ok=True)
    with open(os.path.join("localization_corpus",
                           f"{cfg['out_prefix']}_eval_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    with open(os.path.join("localization_corpus",
                           f"{cfg['out_prefix']}_eval_ranks.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nresults -> localization_corpus/{cfg['out_prefix']}_eval_results.json")
    print(f"ranks   -> localization_corpus/{cfg['out_prefix']}_eval_ranks.csv")


if __name__ == "__main__":
    main()
