# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L3r -- ROUTING-INVARIANT localization.
#
#              PROBLEM. L3 measured that a purely additive implant is localized
#              to 6 windows of 1,251 (0.5%), but a FUNCTIONAL implant that taps
#              a host net perturbs 254-383 windows (20-31%). L3s then showed
#              the attacker cannot escape that by choosing a quiet tap: every
#              tap costs 20-31%, a spread of only 1.5x against a 60x
#              tapped/untapped gap. The expansion is the ROUTER's global
#              response to an added load, not the implant's own configuration
#              bits.
#
#              IDEA. If the expansion is routing, then suppressing
#              routing-volatile parts of the configuration should recover the
#              additive case's precision. Doing that properly would need a
#              frame-type map (which frames hold interconnect vs logic), i.e.
#              the FAR work this project has deliberately deferred.
#
#              It can instead be obtained EMPIRICALLY and for free. Two benign
#              builds from the SAME placed checkpoint differ only in routing --
#              same netlist, same placement, only the route directive changed.
#              Whatever they disagree about is therefore routing-volatile by
#              construction. That difference set is a ROUTING MASK, derived
#              with no device database and no FAR mapping.
#
#              The mask is built ONLY from benign builds, so it uses nothing an
#              attacker touches and nothing from the article under test.
#
# Usage:
#   python3 l3_routing_invariant.py

import csv
import glob
import json
import os
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from l2_localization_eval import WINDOW_FRAMES, ranks_of, windows

SCHEMA = "l3_routing_invariant_v1"
L3_DIR = "rebuild_pilot/pilot_artifacts/l3"
TRUTH_DIR = "rebuild_pilot/pilot_evidence/l3_reports"


def declared_windows(tag, m2f):
    """Implant windows from the sites this campaign chose pre-build."""
    import re
    p = os.path.join(TRUTH_DIR, f"{tag}_implant_truth.txt")
    if not os.path.exists(p):
        return []
    fr = set()
    for line in open(p):
        if not line.startswith("IMPLANT "):
            continue
        m = re.search(r"SLICE_X(\d+)Y(\d+)", line)
        if not m:
            continue
        key = (int(m.group(1)), int(m.group(2)) // 50)
        fr |= m2f.get(key, set())
    return sorted({f // WINDOW_FRAMES for f in fr})


def main():
    from l3_forensic_eval import slice_frame_map
    m2f = slice_frame_map(os.path.join(L3_DIR, "B_Default.ll"))

    ben = {os.path.basename(p)[:-4]: windows(fdri_payload(p, ZYNQ7020_V4))
           for p in sorted(glob.glob(os.path.join(L3_DIR, "B_*.bit")))}
    ref = ben["B_Default"]

    # ---- routing mask, from benign builds only -----------------------------
    mask = np.zeros(ref.shape[0], dtype=bool)
    pairs = 0
    for a in ben:
        for b in ben:
            if a >= b:
                continue
            mask |= (ben[a] != ben[b]).any(axis=1)
            pairs += 1
    n_vol = int(mask.sum())
    print("=== L3r routing-invariant localization ===")
    print(f"routing mask from {len(ben)} benign builds ({pairs} pairs), "
          f"same placed checkpoint, route directive varied")
    print(f"routing-volatile windows: {n_vol}/{len(mask)} "
          f"({100 * n_vol / len(mask):.1f}% of device)\n")

    tests = sorted(glob.glob(os.path.join(L3_DIR, "T_R*.bit"))
                   + glob.glob(os.path.join(L3_DIR, "F_*.bit"))
                   + glob.glob(os.path.join(L3_DIR, "P_*.bit")))
    rows = []
    print(f"{'build':<22}{'style':<9}{'raw':>7}{'masked':>8}{'reduction':>11}"
          f"{'implant kept':>14}")
    for p in tests:
        tag = os.path.basename(p)[:-4]
        style = ("tied" if tag.startswith("T_R")
                 else "tapped" if tag.startswith(("F_", "P_")) else "?")
        W = windows(fdri_payload(p, ZYNQ7020_V4))
        diff = (W != ref).any(axis=1)
        raw = int(diff.sum())
        kept = diff & ~mask                    # suppress routing-volatile
        n_kept = int(kept.sum())
        tw = declared_windows(tag, m2f)
        # how many of the implant's own windows survive the mask
        surv = sum(1 for w in tw if kept[w]) if tw else None
        red = f"{raw / max(1, n_kept):.1f}x" if n_kept else "all removed"
        it = f"{surv}/{len(tw)}" if tw else "n/a"
        rows.append({"build": tag, "style": style, "raw_windows": raw,
                     "masked_windows": n_kept, "reduction": red,
                     "implant_windows": len(tw) if tw else 0,
                     "implant_windows_surviving": surv if surv is not None else "",
                     "pct_device_raw": round(100 * raw / len(mask), 2),
                     "pct_device_masked": round(100 * n_kept / len(mask), 2)})
        print(f"{tag:<22}{style:<9}{raw:>7}{n_kept:>8}{red:>11}{it:>14}")

    tap = [r for r in rows if r["style"] == "tapped"]
    tie = [r for r in rows if r["style"] == "tied"]
    print()
    if tap:
        rr = np.array([r["raw_windows"] for r in tap], float)
        mm = np.array([r["masked_windows"] for r in tap], float)
        print(f"TAPPED  raw median {np.median(rr):.0f} "
              f"({100*np.median(rr)/len(mask):.1f}% of device) -> masked "
              f"{np.median(mm):.0f} ({100*np.median(mm)/len(mask):.1f}%)")
    if tie:
        rr = np.array([r["raw_windows"] for r in tie], float)
        mm = np.array([r["masked_windows"] for r in tie], float)
        print(f"TIED    raw median {np.median(rr):.0f} "
              f"({100*np.median(rr)/len(mask):.1f}%) -> masked "
              f"{np.median(mm):.0f} ({100*np.median(mm)/len(mask):.1f}%)")
    kept_all = [r["implant_windows_surviving"] for r in rows
                if isinstance(r["implant_windows_surviving"], int)]
    tot = sum(r["implant_windows"] for r in rows
              if isinstance(r["implant_windows_surviving"], int))
    if tot:
        print(f"\nimplant windows surviving the mask overall: "
              f"{sum(kept_all)}/{tot}")
        print("(a mask that removed the implant along with the routing would "
              "be useless -- this is the check that it does not)")

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "method": "routing mask = windows on which benign builds from the "
                     "SAME placed checkpoint disagree; they share netlist and "
                     "placement, so their disagreements are routing-volatile "
                     "by construction. No FAR map, no device database, and "
                     "nothing from the article under test.",
           "n_benign_builds": len(ben), "n_mask_pairs": pairs,
           "n_windows": int(len(mask)),
           "routing_volatile_windows": n_vol,
           "per_build": rows}
    with open(os.path.join("localization_corpus",
                           "l3_routing_invariant.json"), "w") as f:
        json.dump(out, f, indent=2)
    with open(os.path.join("localization_corpus",
                           "l3_routing_invariant.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\nresults -> localization_corpus/l3_routing_invariant.json")


if __name__ == "__main__":
    main()
