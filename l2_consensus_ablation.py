# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L2a -- how many shared-lineage builds does consensus
#              localization actually need?
#
#              Two factors could explain why L2c consensus (median rank 1-6)
#              beat L2p benign-population (21.5-132):
#                (i)  PROVENANCE -- consensus builds share a routed-checkpoint
#                     ancestor, so their pairwise churn floor is lower
#                     (measured in L2f: 1100 vs 4588 frames on AES, 4.2x); and
#                (ii) POPULATION SIZE -- consensus had 6 peers to vote with,
#                     L2p had 3.
#
#              This ablation separates them: re-run consensus using every
#              subset size k = 2..N-1 of the SHARED-LINEAGE builds. If small-k
#              consensus still localizes well, provenance is the dominant
#              factor and the practical requirement is modest. If performance
#              degrades toward L2p levels as k shrinks, both factors matter and
#              the requirement includes a minimum build count.
#
#              The answer is a concrete design parameter for the supply-chain
#              verification flow: how many builds from the golden checkpoint a
#              defender must make.
#
# Usage:
#   python3 l2_consensus_ablation.py --design AES-T1000

import argparse
import csv
import glob
import itertools
import json
import os
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from l2_localization_eval import (DESIGNS, WINDOW_FRAMES, ranks_of,
                                  trojan_frames, windows)

SCHEMA = "l2_consensus_ablation_v1"
MAX_SUBSETS = 20          # cap combinations per k for runtime


def main():
    p = argparse.ArgumentParser(description="Consensus population-size ablation")
    p.add_argument("--design", default="AES-T1000", choices=list(DESIGNS))
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    cfg = DESIGNS[args.design]
    rng = np.random.default_rng(args.seed)

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
    X = np.stack(mats)
    n, n_win = len(tags), X.shape[1]

    print(f"=== L2a consensus population-size ablation: {args.design} ===")
    print(f"{n} shared-lineage builds | seed {args.seed}\n")
    print(f"{'peers k':>8}  {'median rank':>12}  {'best':>7}  {'worst':>7}"
          f"  {'subsets':>8}")

    rows = []
    for k in range(2, n):
        med_ranks = []
        for target_i, tag in enumerate(tags):
            others = [j for j in range(n) if j != target_i]
            combos = list(itertools.combinations(others, k))
            if len(combos) > MAX_SUBSETS:
                pick = rng.choice(len(combos), MAX_SUBSETS, replace=False)
                combos = [combos[i] for i in pick]
            for cb in combos:
                med = np.median(X[list(cb)].astype(np.int16), axis=0)
                sc = np.abs(X[target_i].astype(np.int16)
                            - med).sum(axis=1).astype(float)
                r = ranks_of(sc, truth[tag])
                med_ranks.append(float(np.median(list(r.values()))))
        v = np.array(med_ranks)
        rows.append({"design": args.design, "n_peers": k,
                     "median_rank": float(np.median(v)),
                     "mean_rank": float(v.mean()),
                     "best_rank": float(v.min()), "worst_rank": float(v.max()),
                     "n_evaluations": len(v), "n_windows": n_win})
        print(f"{k:>8}  {np.median(v):>12.1f}  {v.min():>7.1f}  "
              f"{v.max():>7.1f}  {len(v):>8}")

    best_k = min(rows, key=lambda r: r["median_rank"])["n_peers"]
    k2 = next(r for r in rows if r["n_peers"] == 2)
    kmax = rows[-1]
    print(f"\n=== READING ===")
    print(f"  k=2 peers  : median rank {k2['median_rank']:.1f}")
    print(f"  k={kmax['n_peers']} peers  : median rank "
          f"{kmax['median_rank']:.1f}")
    if k2["median_rank"] <= 3 * kmax["median_rank"]:
        print(f"  -> PROVENANCE dominates: even 2 shared-lineage peers")
        print(f"     localize well. A defender needs only a handful of builds")
        print(f"     from the golden checkpoint.")
    else:
        print(f"  -> POPULATION SIZE also matters: performance degrades")
        print(f"     substantially below k={best_k}; the flow needs at least")
        print(f"     that many builds from the golden checkpoint.")

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "design": args.design, "n_builds": n, "n_windows": n_win,
           "random_expected_rank": (n_win + 1) / 2,
           "max_subsets_per_k": MAX_SUBSETS, "seed": args.seed,
           "by_population_size": rows,
           "reference_points": {
               "L2c_consensus_full_population": "median 6.0 (AES), 1.0 (b15)",
               "L2p_benign_population_n3": "median 21.5 (AES), 132.0 (b15)",
               "L2_single_reference": "median 32.0 (AES), 137.0 (b15)"}}
    pre = cfg["out_prefix"]
    with open(os.path.join("localization_corpus",
                           f"{pre}_consensus_ablation.json"), "w") as f:
        json.dump(out, f, indent=2)
    with open(os.path.join("localization_corpus",
                           f"{pre}_consensus_ablation.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nresults -> localization_corpus/{pre}_consensus_ablation.json")


if __name__ == "__main__":
    main()
