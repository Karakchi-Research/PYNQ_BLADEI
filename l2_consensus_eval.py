# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L2c -- leave-one-out CONSENSUS localization, the
#              method the pinned corpus uniquely enables.
#
#              MOTIVATION. Every scorer tested so far compares a malicious
#              build to a benign reference, and all of them turned out to be
#              reading logic occupancy rather than trojan position (L2_RESULT).
#              The pinned corpus supports a fundamentally different comparison:
#              N builds of the SAME netlist, same synthesis, differing ONLY in
#              where the trojan was placed. So for build k, the other N-1
#              builds act as a control population that contains the same host
#              and the same trojan SOMEWHERE ELSE.
#
#              Score(k, w) = how far build k deviates from the consensus of
#              the other builds at window w. Where build k has its trojan and
#              the others do not, k should stand out. Crucially this needs NO
#              benign reference and NO labels -- it is unsupervised, and the
#              .ll labels remain evaluation-only.
#
#              Two variants:
#                consensus_l1   |build_k(w) - median_{j!=k} build_j(w)|
#                consensus_ham  bitwise disagreement with the majority bit
#                               vote of the other builds at w
#
#              The same density discriminator from l2_localization_eval is
#              applied: a method that genuinely localizes should not have its
#              performance track local host density.
#
# Usage:
#   python3 l2_consensus_eval.py --design AES-T1000
#   python3 l2_consensus_eval.py --design b15-T200

import argparse
import csv
import glob
import json
import os
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from l2_localization_eval import (DESIGNS, WINDOW_FRAMES, ranks_of,
                                  trojan_frames, windows)

SCHEMA = "l2_consensus_eval_v1"


def main():
    p = argparse.ArgumentParser(description="Leave-one-out consensus localization")
    p.add_argument("--design", default="AES-T1000", choices=list(DESIGNS))
    args = p.parse_args()
    cfg = DESIGNS[args.design]

    ref = windows(fdri_payload(cfg["benign_ref"], ZYNQ7020_V4))
    ref_density = np.unpackbits(ref, axis=1).sum(axis=1).astype(float)

    tags, mats, truth = [], [], {}
    for bit in sorted(glob.glob(os.path.join(cfg["l2_dir"], "*.bit"))):
        tag = os.path.basename(bit)[:-4]
        ll = bit[:-4] + ".ll"
        if not os.path.exists(ll):
            continue
        tw = sorted({f // WINDOW_FRAMES
                     for f in trojan_frames(ll, cfg["tro_re"])})
        if not tw:
            continue
        tags.append(tag)
        mats.append(windows(fdri_payload(bit, ZYNQ7020_V4)))
        truth[tag] = tw

    n = len(tags)
    if n < 3:
        raise SystemExit(f"need >=3 builds for a leave-one-out consensus, "
                         f"have {n}")
    X = np.stack(mats)                      # (n_builds, n_win, win_bytes)
    Xb = np.unpackbits(X, axis=2)
    n_win = X.shape[1]

    print(f"=== L2 leave-one-out consensus localization: {args.design} ===")
    print(f"{n} builds of one netlist, differing only in trojan placement")
    print(f"no benign reference used; labels are evaluation-only\n")

    rows, per_build = {}, {}
    for k, tag in enumerate(tags):
        others = [j for j in range(n) if j != k]
        med = np.median(X[others].astype(np.int16), axis=0)
        maj = (Xb[others].mean(axis=0) >= 0.5).astype(np.uint8)
        s = {
            "consensus_l1": np.abs(X[k].astype(np.int16)
                                   - med).sum(axis=1).astype(float),
            "consensus_ham": np.abs(Xb[k].astype(np.int16)
                                    - maj).sum(axis=1).astype(float),
        }
        t = truth[tag]
        d = float(np.mean([ref_density[w] for w in t]))
        per_build[tag] = {"trojan_windows": t, "local_density": d,
                          "scorers": {}}
        print(f"--- {tag:<10} density {d:>8.1f} | trojan windows {t}")
        for name, sc in s.items():
            r = ranks_of(sc, t)
            best, med_r = min(r.values()), float(np.median(list(r.values())))
            per_build[tag]["scorers"][name] = {
                "ranks": r, "best_rank": best, "median_rank": med_r,
                "score_at_trojan": {int(i): float(sc[i]) for i in t},
                "score_median_all": float(np.median(sc))}
            rows.setdefault(name, []).append(
                {"build": tag, "local_density": d, "scorer": name,
                 "best_rank": best, "median_rank": med_r,
                 "n_trojan_windows": len(t), "n_windows": n_win})
            print(f"      {name:<16} best {best:>7.1f}/{n_win} | median "
                  f"{med_r:>7.1f}")
        print()

    print("=== DISCRIMINATOR: rank vs local host density ===")
    corr = {}
    for name, rr in rows.items():
        x = np.array([r["local_density"] for r in rr])
        y = np.array([r["median_rank"] for r in rr])
        if x.std() == 0:
            c, verdict = None, (f"NO DENSITY VARIANCE (all at {x[0]:.0f}) -- "
                                f"single-condition")
        else:
            c = float(np.corrcoef(x, y)[0, 1])
            verdict = ("tracks density (occupancy-driven)" if c < -0.5
                       else "insensitive to density" if abs(c) < 0.5
                       else "inverse")
        corr[name] = {"pearson_r_rank_vs_density": (round(c, 3) if c is not None
                                                    else None),
                      "median_rank": float(np.median(y)),
                      "best_rank": float(y.min()),
                      "worst_rank": float(y.max()),
                      "n_builds": len(rr)}
        rtxt = f"r = {c:+.3f}" if c is not None else "r =    n/a"
        print(f"  {name:<16} {rtxt} | median rank {np.median(y):>7.1f} | "
              f"best {y.min():>6.1f} | worst {y.max():>7.1f} | {verdict}")

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "design": args.design, "n_builds": n, "builds": tags,
           "n_windows": n_win, "random_expected_rank": (n_win + 1) / 2,
           "method": "leave-one-out consensus across pinned builds of one "
                     "netlist; no benign reference; unsupervised",
           "per_build": per_build, "density_correlation": corr}
    pre = cfg["out_prefix"]
    with open(os.path.join("localization_corpus",
                           f"{pre}_consensus_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    flat = [r for rr in rows.values() for r in rr]
    with open(os.path.join("localization_corpus",
                           f"{pre}_consensus_ranks.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)
    print(f"\nresults -> localization_corpus/{pre}_consensus_results.json")


if __name__ == "__main__":
    main()
