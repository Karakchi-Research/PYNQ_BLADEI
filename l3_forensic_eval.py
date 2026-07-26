# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L3 -- forensic localization under the
#              attack-on-placed-checkpoint threat model.
#
#              SETTING. The defender implements their design to a PLACED
#              checkpoint and ships it; bitstreams built from that checkpoint
#              are verified against the defender's own builds from the same
#              checkpoint. An attacker editing the placed design cannot move
#              the host, because placement is already fixed. The task is
#              FORENSIC: something is suspected, and the question is WHERE the
#              added logic sits.
#
#              GROUND TRUTH IS CONSTRUCTIVE, not inferred. l3_eco_implant.tcl
#              chose the implant sites and recorded them before the bitstream
#              existed (reports/<tag>_implant_truth.txt), and the .ll gives an
#              independent confirmation of the frames the implanted flip-flops
#              configure. This is the strongest ground truth in the project:
#              earlier stages had to infer trojan extent from name patterns
#              (~3% coverage) or from pblocks that only partially contained it.
#
#              WHY THIS SHOULD WORK WHERE EARLIER STAGES FAILED. L2f measured
#              the churn floor: independently placed builds differ in ~4,588 of
#              10,008 frames, which buries a small implant. Here every build
#              descends from one placed checkpoint, so host placement is
#              identical and only routing varies.
#
# Usage:
#   python3 l3_forensic_eval.py

import csv
import glob
import json
import os
import re
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from l2_localization_eval import WINDOW_FRAMES, ranks_of, windows
from split_utils import FRAME_BYTES

SCHEMA = "l3_forensic_eval_v1"
L3_DIR = "rebuild_pilot/pilot_artifacts/l3"
TRUTH_DIR = "rebuild_pilot/pilot_evidence/l3_reports"
FRAME_BITS = FRAME_BYTES * 8

_BIT = re.compile(r"^Bit\s+(\d+)\s+0x([0-9a-fA-F]+)\s+(\d+)\s+(.*)$")
_BLOCK = re.compile(r"Block=SLICE_X(\d+)Y(\d+)")

# 7-series clock region height in CLB rows. A configuration frame covers one
# column within one clock-region row, so every SLICE sharing (column,
# clock-region row) is configured by the same frame set.
CLOCK_REGION_ROWS = 50


def slice_frame_map(ll_path):
    """(column, clock_region_row) -> {frame indices}, from Vivado's own .ll.

    Needed because the implanted flip-flops have UNCONNECTED Q pins, and a
    .ll line only names a latch when a net is attached to it -- so the implant
    cells appear nowhere in the file. Their frames are recovered instead from
    other cells sharing the same column and clock region, which by the 7-series
    frame geometry are configured by the same frames.
    """
    m2f = {}
    with open(ll_path) as f:
        for line in f:
            m = _BIT.match(line)
            if not m:
                continue
            d = int(m.group(1)) - int(m.group(3))
            if d % FRAME_BITS:
                raise AssertionError(f"{ll_path}: non-frame-aligned .ll line")
            b = _BLOCK.search(m.group(4))
            if not b:
                continue
            key = (int(b.group(1)), int(b.group(2)) // CLOCK_REGION_ROWS)
            m2f.setdefault(key, set()).add(d // FRAME_BITS)
    return m2f


def implant_frames(sites, m2f):
    """Frames of the declared implant sites, via the column/clock-region map."""
    fr, unmapped = set(), []
    for s in sites:
        b = re.match(r"SLICE_X(\d+)Y(\d+)", s)
        if not b:
            continue
        key = (int(b.group(1)), int(b.group(2)) // CLOCK_REGION_ROWS)
        if key in m2f:
            fr |= m2f[key]
        else:
            unmapped.append(s)
    return sorted(fr), unmapped


def declared_sites(tag):
    """The sites this campaign CHOSE for the implant, recorded pre-build."""
    p = os.path.join(TRUTH_DIR, f"{tag}_implant_truth.txt")
    sites, region = [], None
    if not os.path.exists(p):
        return sites, region
    for line in open(p):
        if line.startswith("region:"):
            region = line.split(":", 1)[1].strip()
        elif line.startswith("IMPLANT "):
            sites.append(line.split()[-1])
    return sites, region


def main():
    ben = {os.path.basename(p)[:-4]: windows(fdri_payload(p, ZYNQ7020_V4))
           for p in sorted(glob.glob(os.path.join(L3_DIR, "B_*.bit")))}
    tro = {os.path.basename(p)[:-4]: p
           for p in sorted(glob.glob(os.path.join(L3_DIR, "T_*.bit")))}
    if "B_Default" not in ben:
        raise SystemExit("missing the like-for-like benign build B_Default")

    ref = ben["B_Default"]                       # same route directive
    refb = np.unpackbits(ref, axis=1)
    # Column/clock-region frame map, built once from a benign build's .ll.
    ref_ll = os.path.join(L3_DIR, "B_Default.ll")
    m2f = slice_frame_map(ref_ll)
    pop = np.stack(list(ben.values()))
    pop_med = np.median(pop.astype(np.int16), axis=0)
    n_win = ref.shape[0]

    print("=== L3 forensic localization (attack on a placed checkpoint) ===")
    print(f"benign population: {list(ben)}")
    print(f"attacked builds  : {list(tro)}")
    print(f"{n_win} windows | ground truth = constructively chosen implant "
          f"sites, confirmed by .ll\n")

    rows, per_build = [], {}
    for tag, path in tro.items():
        sites, region = declared_sites(tag)
        fr, unmapped = implant_frames(sites, m2f)
        t = sorted({f // WINDOW_FRAMES for f in fr})
        if not t:
            print(f"  {tag}: implant sites not mappable to frames "
                  f"({len(unmapped)} unmapped) -- skipped")
            continue
        W = windows(fdri_payload(path, ZYNQ7020_V4))
        Wb = np.unpackbits(W, axis=1)
        s = {
            "like_for_like_l1": np.abs(W.astype(np.int32)
                                       - ref.astype(np.int32)).sum(axis=1).astype(float),
            "like_for_like_ham": np.abs(Wb - refb).sum(axis=1).astype(float),
            "pop_median_l1": np.abs(W.astype(np.int16)
                                    - pop_med).sum(axis=1).astype(float),
        }
        n_diff = int(np.count_nonzero(s["like_for_like_l1"] > 0))
        per_build[tag] = {"region": region, "n_declared_sites": len(sites),
                          "declared_sites": sites,
                          "n_sites_unmapped": len(unmapped),
                          "implant_frames": fr, "implant_windows": t,
                          "n_windows_differing_like_for_like": n_diff,
                          "scorers": {}}
        print(f"--- {tag:<8} region {region}")
        print(f"      implant windows {t} | windows differing from "
              f"B_Default: {n_diff}/{n_win}")
        for name, sc in s.items():
            r = ranks_of(sc, t)
            best = min(r.values())
            med = float(np.median(list(r.values())))
            hit1 = sum(1 for v in r.values() if v <= len(t))
            per_build[tag]["scorers"][name] = {
                "ranks": r, "best_rank": best, "median_rank": med,
                "n_implant_windows": len(t),
                "implant_windows_in_topN": hit1}
            rows.append({"build": tag, "region": region, "scorer": name,
                         "best_rank": best, "median_rank": med,
                         "n_implant_windows": len(t),
                         "implant_windows_in_topN": hit1,
                         "n_windows_differing": n_diff, "n_windows": n_win})
            print(f"      {name:<20} best {best:>6.1f} | median {med:>7.1f} "
                  f"| implant windows in top-{len(t)}: {hit1}/{len(t)}")
        print()

    print("=== SUMMARY (rank of implant windows, of "
          f"{n_win}; random = {(n_win + 1) / 2:.0f}) ===")
    summ = {}
    for name in ("like_for_like_l1", "like_for_like_ham", "pop_median_l1"):
        rr = [r for r in rows if r["scorer"] == name]
        y = np.array([r["median_rank"] for r in rr])
        tot_hits = sum(r["implant_windows_in_topN"] for r in rr)
        tot_win = sum(r["n_implant_windows"] for r in rr)
        summ[name] = {"median_rank": float(np.median(y)),
                      "best_rank": float(y.min()),
                      "worst_rank": float(y.max()),
                      "implant_windows_recovered_in_topN": tot_hits,
                      "implant_windows_total": tot_win,
                      "n_builds": len(rr)}
        print(f"  {name:<20} median {np.median(y):>7.1f} | best "
              f"{y.min():>6.1f} | worst {y.max():>7.1f} | recovered in top-N: "
              f"{tot_hits}/{tot_win}")

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "design": "AES-T1000 (benign host) + ECO implant",
           "threat_model": "attacker edits a shipped PLACED checkpoint; host "
                           "placement is fixed, only routing varies. Task is "
                           "forensic localization of the added logic.",
           "ground_truth": "implant sites chosen and recorded by "
                           "l3_eco_implant.tcl BEFORE the bitstream existed, "
                           "independently confirmed by the .ll",
           "benign_population": list(ben), "n_windows": n_win,
           "random_expected_rank": (n_win + 1) / 2,
           "per_build": per_build, "summary": summ}
    with open(os.path.join("localization_corpus",
                           "l3_forensic_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    with open(os.path.join("localization_corpus",
                           "l3_forensic_ranks.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\nresults -> localization_corpus/l3_forensic_results.json")


if __name__ == "__main__":
    main()
