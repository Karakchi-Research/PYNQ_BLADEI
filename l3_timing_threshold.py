# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L3 -- locate the timing-closure threshold for the
#              placed-checkpoint localizer.
#
#              L3b flipped one design's outcome by changing only its clock
#              (125 -> 50 MHz) and named the open question every write-up
#              carries: where does the threshold sit, and is it sharp or
#              gradual? l3_slack_sweep.sh builds the same design/implant/region
#              across several clock periods; this script reduces the resulting
#              bitstreams to the two curves that answer it:
#
#                floor(period)  = windows differing between two LEGITIMATE
#                                 benign rebuilds (B_Default vs B_Explore) from
#                                 the same placed checkpoint -- the routing
#                                 nondeterminism the implant must exceed;
#                signal(period) = windows by which the tied implant differs
#                                 from B_Default at the same period.
#
#              VERDICT per period: VISIBLE when floor == 0 (or signal clears
#              floor by the L3 margin) so the implant stands out, else BURIED.
#              The threshold is the period where the verdict flips, reported
#              together with the measured WNS at each period so the flip is
#              anchored to slack, not just to the constraint.
#
#              Consumes only bitstreams + timing reports; no Vivado, no bit of
#              this depends on the site->frame map (it is a pure window-count
#              argument, the same one L3b used).
#
# Usage:
#   python3 l3_timing_threshold.py --sweep-dir <dir from l3_slack_sweep.sh>

import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from l2_localization_eval import windows

SCHEMA = "l3_timing_threshold_v2"
# Visibility is decided by TWO quantities, not one. The floor (benign routing
# nondeterminism) must be low so the implant stands out, AND the implant's own
# footprint must be compact -- near the additive band L3 measured (6-11
# windows) -- so what stands out is actually localized. The 2026-07-26 b15
# sweep showed these come apart near the timing edge: at WNS ~+0.5 the floor is
# 0 but the implant perturbs ~90 windows, so a floor-only rule (the v1 logic)
# would wrongly call that a clean localization. Hence three states.
#
#   VISIBLE   floor <= FLOOR_OK and signal <= SIGNAL_OK   -- stands out AND compact
#   MARGINAL  floor <= FLOOR_OK but signal > SIGNAL_OK    -- timing met, no margin:
#                                                            floor gone but the
#                                                            implant itself
#                                                            re-routes broadly
#   BURIED    floor > FLOOR_OK                             -- implant lost in
#                                                            routing churn
FLOOR_OK = 5          # windows; effectively "the benign pair converges"
SIGNAL_OK = 20        # windows; ~2x the additive band (6-11) L3 measured
_WNS = re.compile(r"WNS\(ns\)|Slack.*\(VIOLATED\)|Slack.*\(MET\)")


def verdict_of(floor, signal):
    if floor > FLOOR_OK:
        return "BURIED"
    return "VISIBLE" if signal <= SIGNAL_OK else "MARGINAL"


def diff_windows(a, b):
    return int(np.count_nonzero(
        np.abs(a.astype(np.int32) - b.astype(np.int32)).sum(axis=1)))


def read_wns(report):
    """Worst negative slack (ns) from a report_timing_summary file."""
    if not report or not os.path.exists(report):
        return None
    txt = open(report, errors="ignore").read()
    m = re.search(r"WNS\(ns\)\s*\n?[^\n]*?(-?\d+\.\d+)", txt)
    if m:
        return float(m.group(1))
    m = re.search(r"Slack\s*\(.*?\)\s*:\s*(-?\d+\.\d+)ns", txt)
    return float(m.group(1)) if m else None


def period_dirs(sweep_dir):
    out = []
    for d in sorted(glob.glob(os.path.join(sweep_dir, "p*"))):
        m = re.match(r"p(\d+)(?:_(\d+))?$", os.path.basename(d))
        if not m:
            continue
        p = float("%s.%s" % (m.group(1), m.group(2) or "0"))
        out.append((p, d))
    return sorted(out)


def load(d, name):
    p = os.path.join(d, "%s.bit" % name)
    return windows(fdri_payload(p, ZYNQ7020_V4)) if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser(description="L3 timing-closure threshold")
    ap.add_argument("--sweep-dir", required=True,
                    help="output of l3_slack_sweep.sh for one design")
    ap.add_argument("--implant", default=None,
                    help="implant build name (default: first T_* found)")
    ap.add_argument("--outdir", default="localization_corpus")
    args = ap.parse_args()

    periods = period_dirs(args.sweep_dir)
    if not periods:
        sys.exit("no p<period> subdirectories under %s" % args.sweep_dir)

    print("=== L3 timing-closure threshold: %s ==="
          % os.path.basename(args.sweep_dir.rstrip("/")))
    print("%-8s %8s %8s %9s  %s"
          % ("period", "WNS", "floor", "signal", "verdict"))

    rows, prev = [], None
    threshold = None
    for p, d in periods:
        bd, be = load(d, "B_Default"), load(d, "B_Explore")
        tname = args.implant
        if tname is None:
            cands = sorted(glob.glob(os.path.join(d, "T_*.bit")))
            tname = os.path.basename(cands[0])[:-4] if cands else None
        ti = load(d, tname) if tname else None
        if bd is None or be is None or ti is None:
            print("  %-6.1f  incomplete build set -- skipped" % p)
            continue
        floor = diff_windows(bd, be)
        signal = diff_windows(ti, bd)
        wns = read_wns(os.path.join(d, "reports", "golden_timing.rpt")) \
            or read_wns(os.path.join(d, "reports", "%s_timing.rpt" % tname))
        verdict = verdict_of(floor, signal)
        rows.append({"period_ns": p, "wns_ns": wns, "floor_windows": floor,
                     "signal_windows": signal,
                     "meets_timing": None if wns is None else wns >= 0,
                     "verdict": verdict})
        print("%-8.1f %8s %8d %9d  %s"
              % (p, "n/a" if wns is None else "%+.3f" % wns, floor, signal,
                 verdict))
        if prev is not None and prev["verdict"] != verdict and threshold is None:
            threshold = {"between_periods_ns": [prev["period_ns"], p],
                         "between_wns_ns": [prev["wns_ns"], wns],
                         "flip": "%s -> %s" % (prev["verdict"], verdict)}
        prev = rows[-1]

    print()
    if threshold:
        lo, hi = threshold["between_periods_ns"]
        print("THRESHOLD between %.1f and %.1f ns" % (lo, hi), end="")
        if all(v is not None for v in threshold["between_wns_ns"]):
            print(" (WNS %+.3f -> %+.3f)" % tuple(threshold["between_wns_ns"]))
        else:
            print()
        # Sharp vs gradual: one flip between adjacent periods is sharp; a
        # window where margins slide across several periods is gradual.
        flips = sum(1 for i in range(1, len(rows))
                    if rows[i]["verdict"] != rows[i - 1]["verdict"])
        print("flips across the sweep: %d (%s)"
              % (flips, "single, consistent with a sharp threshold" if flips == 1
                 else "multiple -- gradual or non-monotone, report the curve"))
    else:
        v = {r["verdict"] for r in rows}
        print("no verdict flip across the swept range (%s throughout) -- widen "
              "the periods" % (v.pop() if len(v) == 1 else "mixed"))

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "design": os.path.basename(args.sweep_dir.rstrip("/")),
           "floor_ok_windows": FLOOR_OK, "signal_ok_windows": SIGNAL_OK,
           "per_period": rows, "threshold": threshold,
           "method": ("floor = B_Default vs B_Explore window diff (routing "
                      "nondeterminism); signal = tied implant vs B_Default. "
                      "VISIBLE = floor<=%d AND signal<=%d (stands out AND "
                      "compact); MARGINAL = floor<=%d but signal>%d (timing "
                      "met, no margin); BURIED = floor>%d"
                      % (FLOOR_OK, SIGNAL_OK, FLOOR_OK, SIGNAL_OK, FLOOR_OK)),
           "limit": ("one host, one implant, one region; the threshold is "
                     "located between swept periods, not to the nanosecond, "
                     "and generalisation across designs is untested")}
    os.makedirs(args.outdir, exist_ok=True)
    stem = os.path.join(args.outdir,
                        "l3_timing_threshold_%s" % out["design"])
    with open(stem + ".json", "w") as fh:
        json.dump(out, fh, indent=2)
    if rows:
        with open(stem + ".csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print("\nresults -> %s.json" % stem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
