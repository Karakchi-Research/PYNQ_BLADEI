# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L2p -- BENIGN-POPULATION localization: a DEPLOYABLE
#              analogue of the L2c consensus result.
#
#              L2c showed the trojan signal is present and localizable to rank
#              1-6, but its method needs several builds of one design with the
#              trojan deliberately RELOCATED -- which nobody screening an
#              unknown bitstream has. This script asks whether the same
#              churn-cancelling effect is obtainable from something a defender
#              PLAUSIBLY HAS: a population of builds of their own golden
#              (benign) design.
#
#              Threat model. The defender owns the design and can build it as
#              many times as they like, but sees the suspect bitstream exactly
#              once. So: reference = N benign builds of this design;
#              test = ONE malicious bitstream; score each window by how far the
#              test deviates from the benign population.
#
#              Why a MEDIAN and not a z-score. L1b already tried
#              benign_null_z = (distance - benign_mean) / benign_std and it
#              scored WORSE THAN RANDOM (mean rank 771.9). The reason is that
#              benign-vs-benign churn is largest exactly in dense logic, so
#              dividing by that spread suppresses the signal along with the
#              noise. L2c's consensus succeeded using a plain MEDIAN, which
#              cancels churn as common-mode WITHOUT amplifying by variance.
#              This script therefore uses robust central tendency and reports
#              the z-score variant alongside as the documented counterexample.
#
#              Scorers:
#                pop_median_l1   |test(w) - median_j benign_j(w)|
#                pop_major_ham   bits disagreeing with the majority bit-vote
#                                of the benign population at w
#                single_ref_l1   |test(w) - benign_0(w)|   (the L1b/L2
#                                pairwise baseline, for the 1-vs-N delta)
#                pop_z           the L1b z-score form, kept as a control
#
# Usage:
#   python3 l2_population_eval.py --design AES-T1000
#   python3 l2_population_eval.py --design b15-T200

import argparse
import csv
import glob
import json
import os
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload, payload_hash
from l2_localization_eval import (DESIGNS, WINDOW_FRAMES, ranks_of,
                                  trojan_frames, windows)

SCHEMA = "l2_population_eval_v1"

BENIGN_GLOB = {
    "AES-T1000": "rebuild_pilot/pilot_artifacts/builds/AES-T1000/TjFree/*/*.bit",
    "b15-T200": "rebuild_pilot/pilot_artifacts/builds/b15-T200/TjFree/*/*.bit",
}


def main():
    p = argparse.ArgumentParser(description="Benign-population localization")
    p.add_argument("--design", default="AES-T1000", choices=list(DESIGNS))
    args = p.parse_args()
    cfg = DESIGNS[args.design]

    # ---- benign population, deduplicated by exact payload -----------------
    seen, pop, pop_tags = {}, [], []
    for b in sorted(glob.glob(BENIGN_GLOB[args.design])):
        h = payload_hash(b, ZYNQ7020_V4)
        if h in seen:
            continue
        seen[h] = b
        pop.append(windows(fdri_payload(b, ZYNQ7020_V4)))
        pop_tags.append(os.path.basename(b)[:-4])
    P = np.stack(pop)
    Pb = np.unpackbits(P, axis=2)
    n_pop = len(pop)

    print(f"=== L2p benign-population localization: {args.design} ===")
    print(f"benign population: {n_pop} DISTINCT payloads "
          f"(deduplicated by exact FDRI hash)")
    for t in pop_tags:
        print(f"    {t}")
    if n_pop < 3:
        print(f"  WARNING: {n_pop} distinct benign builds is a thin "
              f"population for a median; treat results as indicative")
    print()

    pop_med = np.median(P.astype(np.int16), axis=0)
    pop_maj = (Pb.mean(axis=0) >= 0.5).astype(np.uint8)
    d_pair = np.stack([np.abs(Pb[i] - Pb[j]).sum(axis=2 - 1)
                       for i in range(n_pop) for j in range(i + 1, n_pop)]) \
        if n_pop > 1 else None
    null_mu = d_pair.mean(axis=0) if d_pair is not None else 0.0
    null_sd = d_pair.std(axis=0) if d_pair is not None else 1.0
    ref0, ref0b = P[0], Pb[0]

    # ---- test bitstreams: the pinned malicious builds ---------------------
    rows, per_build = {}, {}
    for bit in sorted(glob.glob(os.path.join(cfg["l2_dir"], "*.bit"))):
        tag = os.path.basename(bit)[:-4]
        ll = bit[:-4] + ".ll"
        if not os.path.exists(ll):
            continue
        t = sorted({f // WINDOW_FRAMES
                    for f in trojan_frames(ll, cfg["tro_re"])})
        if not t:
            continue
        W = windows(fdri_payload(bit, ZYNQ7020_V4))
        Wb = np.unpackbits(W, axis=1)
        d_to_pop = np.stack([np.abs(Wb - Pb[i]).sum(axis=1)
                             for i in range(n_pop)]).mean(axis=0)
        s = {
            "pop_median_l1": np.abs(W.astype(np.int16)
                                    - pop_med).sum(axis=1).astype(float),
            "pop_major_ham": np.abs(Wb.astype(np.int16)
                                    - pop_maj).sum(axis=1).astype(float),
            "single_ref_l1": np.abs(W.astype(np.int32)
                                    - ref0.astype(np.int32)).sum(axis=1).astype(float),
            "pop_z": (d_to_pop - null_mu) / (null_sd + 1.0),
        }
        density = np.unpackbits(pop_med.astype(np.uint8),
                                axis=1).sum(axis=1).astype(float)
        d = float(np.mean([density[w] for w in t]))
        per_build[tag] = {"trojan_windows": t, "local_density": d,
                          "scorers": {}}
        print(f"--- {tag:<10} density {d:>8.1f} | trojan windows {t}")
        for name, sc in s.items():
            r = ranks_of(sc, t)
            best, med_r = min(r.values()), float(np.median(list(r.values())))
            per_build[tag]["scorers"][name] = {"ranks": r, "best_rank": best,
                                               "median_rank": med_r}
            rows.setdefault(name, []).append(
                {"build": tag, "local_density": d, "scorer": name,
                 "best_rank": best, "median_rank": med_r,
                 "n_benign_population": n_pop, "n_windows": W.shape[0]})
            print(f"      {name:<16} best {best:>7.1f} | median {med_r:>7.1f}")
        print()

    print("=== SUMMARY: does a POPULATION beat a SINGLE reference? ===")
    summ = {}
    for name, rr in rows.items():
        y = np.array([r["median_rank"] for r in rr])
        x = np.array([r["local_density"] for r in rr])
        c = (None if x.std() == 0
             else float(np.corrcoef(x, y)[0, 1]))
        summ[name] = {"median_rank": float(np.median(y)),
                      "best_rank": float(y.min()),
                      "worst_rank": float(y.max()),
                      "pearson_r_rank_vs_density": (round(c, 3)
                                                    if c is not None else None),
                      "n_builds": len(rr)}
        rtxt = f"r={c:+.3f}" if c is not None else "r=  n/a"
        print(f"  {name:<16} median {np.median(y):>7.1f} | best {y.min():>6.1f}"
              f" | worst {y.max():>7.1f} | {rtxt}")

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "design": args.design,
           "threat_model": "defender owns the design and may build it N times; "
                           "the suspect bitstream is seen once. Reference = N "
                           "benign builds; test = 1 malicious bitstream.",
           "benign_population": pop_tags,
           "n_distinct_benign_payloads": n_pop,
           "n_windows": int(P.shape[1]),
           "random_expected_rank": (P.shape[1] + 1) / 2,
           "per_build": per_build, "summary": summ}
    pre = cfg["out_prefix"]
    with open(os.path.join("localization_corpus",
                           f"{pre}_population_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    flat = [r for rr in rows.values() for r in rr]
    with open(os.path.join("localization_corpus",
                           f"{pre}_population_ranks.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)
    print(f"\nresults -> localization_corpus/{pre}_population_results.json")


if __name__ == "__main__":
    main()
