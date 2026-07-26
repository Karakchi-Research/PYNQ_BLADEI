# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L1b -- first localization baseline on the AES-T1000
#              corpus. Produces a per-window suspicion ranking and measures
#              whether the KNOWN trojan windows rise to the top.
#
#              WHY TRAINING-FREE, NOT SUPERVISED. The corpus labels come from
#              Vivado .ll files, which enumerate configuration MEMORY CELLS
#              only (flip-flops / LUTRAM / BRAM) -- 5 of the AES trojan's 168
#              primitive cells, ~3% of it. They are positive SEEDS with a
#              clean benign control, not the trojan's extent. Training on them
#              would teach a model that the trojan's LUT and routing frames
#              are negatives, which is worse than not training at all, and
#              recall/IoU are not computable from them. So every scorer here
#              is TRAINING-FREE and the labels are used for EVALUATION ONLY.
#              That is exactly the use the corpus was characterised to
#              support (LOCALIZATION_PILOT_REPORT.md section 4).
#
#              Scorers (all unsupervised, all on the validated 8-frame window
#              grid over the FDRI payload):
#                pair_hamming   bit differences between the malicious window
#                               and its MATCHED benign window (same config) --
#                               the differential baseline the project has
#                               always used diagnostically
#                pair_l1        byte-level L1 distance of the same pair
#                popcount       set-bit density of the malicious window; the
#                               MANDATORY occupancy control -- any method that
#                               cannot beat "the trojan is where the bits are"
#                               is not localizing
#                entropy_dev    |window byte entropy - median over windows|
#                benign_null_z  distance from the malicious build to the
#                               benign builds at window w, standardised by how
#                               much the benign builds differ from EACH OTHER
#                               at the same w. This is the only scorer that
#                               controls for place-and-route churn, which is
#                               the known confound (a matched pair differs in
#                               ~39% of frames).
#
# Usage:
#   python3 localization_baseline.py
#   python3 localization_baseline.py --window-frames 8 --outdir localization_corpus

import argparse
import csv
import json
import os
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload, payload_hash
from split_utils import FRAME_BYTES

SCHEMA = "localization_baseline_v1"
SCORERS = ["pair_hamming", "pair_l1", "popcount", "entropy_dev",
           "benign_null_z", "pair_l1_per_bit"]


def windows_of(payload, window_frames):
    wb = window_frames * FRAME_BYTES
    n = len(payload) // wb
    return payload[:n * wb].reshape(n, wb)


def popcount_rows(a):
    return np.unpackbits(a, axis=1).sum(axis=1).astype(np.int64)


def byte_entropy_rows(a):
    out = np.empty(a.shape[0])
    for i in range(a.shape[0]):
        c = np.bincount(a[i], minlength=256).astype(np.float64)
        p = c / c.sum()
        nz = p[p > 0]
        out[i] = -(nz * np.log2(nz)).sum()
    return out


def rank_of(scores, indices):
    """1-based rank of each index when sorting scores descending.
    Ties take the average rank, so a constant scorer cannot look good."""
    order = np.argsort(-scores, kind="stable")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks within tie groups
    uniq, inv = np.unique(-scores, return_inverse=True)
    for g in range(len(uniq)):
        m = inv == g
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return {int(i): float(ranks[i]) for i in indices}


def main():
    p = argparse.ArgumentParser(description="First localization baseline (AES-T1000)")
    p.add_argument("--manifest",
                   default=os.path.join("localization_corpus",
                                        "localization_manifest.json"))
    p.add_argument("--window-frames", type=int, default=8)
    p.add_argument("--outdir", default="localization_corpus")
    p.add_argument("--topk", type=int, default=10)
    args = p.parse_args()

    with open(args.manifest) as f:
        man = json.load(f)
    design = man["design"]
    builds = [b for b in man["builds"] if "TjIn" in b and "TjFree" in b]
    print(f"=== First localization baseline: {design} ===")
    print(f"{len(builds)} matched configs | window = {args.window_frames} "
          f"frames | labels used for EVALUATION ONLY (never training)\n")

    # ---- load every payload once -------------------------------------------
    mal, ben, cfgs, truth = {}, {}, [], {}
    for b in builds:
        cfg = b["config"]
        cfgs.append(cfg)
        mal[cfg] = windows_of(fdri_payload(b["TjIn"]["bit_file"],
                                           ZYNQ7020_V4), args.window_frames)
        ben[cfg] = windows_of(fdri_payload(b["TjFree"]["bit_file"],
                                           ZYNQ7020_V4), args.window_frames)
        truth[cfg] = sorted(b["TjIn"]["windows_trojan_confirmed"])
    n_win = mal[cfgs[0]].shape[0]
    print(f"windows per build: {n_win}")

    # Benign null: pairwise Hamming among benign builds, per window.
    ben_stack = np.stack([np.unpackbits(ben[c], axis=1) for c in cfgs])
    pair_d = []
    for i in range(len(cfgs)):
        for j in range(i + 1, len(cfgs)):
            pair_d.append(np.abs(ben_stack[i] - ben_stack[j]).sum(axis=1))
    pair_d = np.stack(pair_d) if pair_d else np.zeros((1, n_win))
    null_mu, null_sd = pair_d.mean(axis=0), pair_d.std(axis=0)
    print(f"benign null (pairwise Hamming across benign builds): "
          f"mean {null_mu.mean():.1f}, {int((null_mu == 0).sum())} of {n_win} "
          f"windows identical in every benign build\n")

    rows, results = [], {}
    for cfg in cfgs:
        M, B = mal[cfg], ben[cfg]
        Mb = np.unpackbits(M, axis=1)
        Bb = np.unpackbits(B, axis=1)

        s = {}
        s["pair_hamming"] = np.abs(Mb - Bb).sum(axis=1).astype(float)
        s["pair_l1"] = np.abs(M.astype(np.int32)
                              - B.astype(np.int32)).sum(axis=1).astype(float)
        s["popcount"] = popcount_rows(M).astype(float)
        e = byte_entropy_rows(M)
        s["entropy_dev"] = np.abs(e - np.median(e))
        d_to_benign = np.stack(
            [np.abs(Mb - ben_stack[k]).sum(axis=1)
             for k in range(len(cfgs))]).mean(axis=0)
        s["benign_null_z"] = (d_to_benign - null_mu) / (null_sd + 1.0)
        # DECISIVE CONTROL: differential per occupied bit. If the differential
        # carries trojan-specific signal beyond "this window holds a lot of
        # logic", normalising by density must not destroy its ranking. If it
        # does, the differential was reading occupancy all along.
        s["pair_l1_per_bit"] = s["pair_l1"] / (s["popcount"] + 1.0)

        t = truth[cfg]
        results[cfg] = {"n_windows": n_win, "trojan_windows": t,
                        "scorers": {}}
        print(f"--- {cfg}: known trojan windows {t} ---")
        for name in SCORERS:
            sc = s[name]
            r = rank_of(sc, t)
            best = min(r.values())
            topk = sum(1 for v in r.values() if v <= args.topk)
            results[cfg]["scorers"][name] = {
                "ranks": r, "best_rank": best,
                "median_rank": float(np.median(list(r.values()))),
                f"hits_in_top{args.topk}": topk,
                "n_trojan_windows": len(t),
                "score_at_trojan": {int(i): float(sc[i]) for i in t},
                "score_max": float(sc.max()), "score_median": float(
                    np.median(sc)),
            }
            for w, rk in sorted(r.items()):
                rows.append({"design": design, "config": cfg,
                             "scorer": name, "trojan_window": w,
                             "rank": rk, "n_windows": n_win,
                             "percentile": round(100 * (1 - rk / n_win), 2),
                             "score": float(sc[w]),
                             "score_median_all_windows": float(np.median(sc))})
            print(f"    {name:<14} best rank {best:>7.1f}/{n_win} | "
                  f"median {np.median(list(r.values())):>7.1f} | "
                  f"top-{args.topk} hits {topk}/{len(t)}")

        # Benign control: same scorers on a benign build must not produce
        # a confident trojan call -- there is nothing to find.
        ctrl = np.abs(np.unpackbits(B, axis=1) - Bb).sum(axis=1)
        results[cfg]["benign_control_pair_hamming_max"] = float(ctrl.max())
        print()

    # ---- write artifacts ----------------------------------------------------
    os.makedirs(args.outdir, exist_ok=True)
    csv_path = os.path.join(args.outdir, "baseline_ranks.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    random_rank = (n_win + 1) / 2
    summary = {}
    for name in SCORERS:
        allr = [r["rank"] for r in rows if r["scorer"] == name]
        summary[name] = {
            "mean_rank": float(np.mean(allr)),
            "best_rank_overall": float(np.min(allr)),
            "worst_rank_overall": float(np.max(allr)),
            f"hits_in_top{args.topk}": int(sum(1 for r in allr
                                               if r <= args.topk)),
            "n_labelled_windows": len(allr),
            "better_than_random": bool(np.mean(allr) < random_rank),
        }

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "design": design,
        "manifest": os.path.abspath(args.manifest),
        "window_frames": args.window_frames,
        "n_windows": n_win,
        "random_expected_rank": random_rank,
        "supervision": "NONE -- all scorers are training-free; the .ll labels "
                       "are used for EVALUATION ONLY. Training on them is "
                       "prohibited: they cover ~3% of the trojan (memory "
                       "cells only), so they would teach the trojan's LUT and "
                       "routing frames as negatives.",
        "metrics_note": "Only rank/precision-style statements are valid. "
                        "Recall and IoU are NOT computable: absence of a "
                        "label is not evidence of absence of trojan "
                        "configuration.",
        "per_config": results,
        "summary_by_scorer": summary,
    }
    json_path = os.path.join(args.outdir, "baseline_results.json")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)

    print("=== SUMMARY (mean rank of known trojan windows; "
          f"random = {random_rank:.1f}) ===")
    for name, v in sorted(summary.items(), key=lambda kv: kv[1]["mean_rank"]):
        flag = "better than random" if v["better_than_random"] else \
            "NOT better than random"
        print(f"  {name:<14} mean {v['mean_rank']:>7.1f} | best "
              f"{v['best_rank_overall']:>6.1f} | top-{args.topk} "
              f"{v[f'hits_in_top{args.topk}']}/{v['n_labelled_windows']} "
              f"| {flag}")
    print(f"\nranks -> {csv_path}\nresults -> {json_path}")


if __name__ == "__main__":
    main()
