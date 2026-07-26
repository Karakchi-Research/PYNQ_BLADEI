# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L2f -- quantify the PLACEMENT-PROVENANCE CHURN FLOOR.
#
#              L2p concluded that consensus localization works because its
#              builds share a routed-checkpoint ancestor, not because it
#              averages more references. That was an inference from ranking
#              behaviour. This script measures the underlying quantity
#              directly, with no new builds:
#
#                How many frames differ between two bitstreams, as a function
#                of how much build provenance they share?
#
#              Three provenance classes, all on the same host design:
#                SHARED-LINEAGE   pinned builds descending from one routed
#                                 reference (only the trojan was ripped and
#                                 re-placed)
#                INDEPENDENT-PNR  builds implemented separately from the same
#                                 post-synthesis checkpoint under different
#                                 directives
#                CROSS-LABEL      benign vs malicious, independently placed
#
#              If shared lineage collapses the churn floor, the supply-chain
#              threat model (defender ships a PLACED checkpoint, verifies the
#              returned bitstream against builds from it) is worth pursuing,
#              and the size of the collapse bounds how much signal a deployable
#              detector could recover.
#
# Usage:
#   python3 l2_churn_floor.py --design AES-T1000
#   python3 l2_churn_floor.py --design b15-T200

import argparse
import csv
import glob
import itertools
import json
import os
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload, payload_hash
from l2_localization_eval import DESIGNS
from split_utils import FRAME_BYTES

SCHEMA = "l2_churn_floor_v1"

BENIGN_GLOB = {
    "AES-T1000": "rebuild_pilot/pilot_artifacts/builds/AES-T1000/TjFree/*/*.bit",
    "b15-T200": "rebuild_pilot/pilot_artifacts/builds/b15-T200/TjFree/*/*.bit",
}
MALICIOUS_GLOB = {
    "AES-T1000": "rebuild_pilot/pilot_artifacts/builds/AES-T1000/TjIn/*/*.bit",
    "b15-T200": "rebuild_pilot/pilot_artifacts/builds/b15-T200/TjIn/*/*.bit",
}


def frames(path):
    a = fdri_payload(path, ZYNQ7020_V4)
    n = len(a) // FRAME_BYTES
    return a[:n * FRAME_BYTES].reshape(n, FRAME_BYTES)


def diff_frames(A, B):
    return int(np.count_nonzero((A != B).any(axis=1)))


def dedup(paths):
    seen, out = set(), []
    for p in sorted(paths):
        h = payload_hash(p, ZYNQ7020_V4)
        if h in seen:
            continue
        seen.add(h)
        out.append(p)
    return out


def summarise(name, pairs, n_frames):
    if not pairs:
        return None
    v = np.array([d for _, _, d in pairs], dtype=float)
    rec = {"class": name, "n_pairs": len(pairs),
           "median_frames_differing": float(np.median(v)),
           "min": float(v.min()), "max": float(v.max()),
           "median_pct_of_device": round(100 * float(np.median(v)) / n_frames, 2)}
    print(f"  {name:<18} pairs {len(pairs):>3} | median {np.median(v):>7.0f} "
          f"frames ({100*np.median(v)/n_frames:>5.1f}% of device) | "
          f"range {v.min():.0f}-{v.max():.0f}")
    return rec


def main():
    p = argparse.ArgumentParser(description="Placement-provenance churn floor")
    p.add_argument("--design", default="AES-T1000", choices=list(DESIGNS))
    args = p.parse_args()
    cfg = DESIGNS[args.design]

    print(f"=== L2f placement-provenance churn floor: {args.design} ===\n")

    pinned = sorted(glob.glob(os.path.join(cfg["l2_dir"], "*.bit")))
    benign = dedup(glob.glob(BENIGN_GLOB[args.design]))
    malic = dedup(glob.glob(MALICIOUS_GLOB[args.design]))
    print(f"shared-lineage pinned builds : {len(pinned)}")
    print(f"independent benign payloads  : {len(benign)}")
    print(f"independent malicious payloads: {len(malic)}\n")

    F = {p: frames(p) for p in pinned + benign + malic}
    n_frames = next(iter(F.values())).shape[0]

    def pairs_within(paths):
        return [(a, b, diff_frames(F[a], F[b]))
                for a, b in itertools.combinations(paths, 2)]

    print("frame differences by provenance class:")
    results = []
    results.append(summarise("SHARED-LINEAGE", pairs_within(pinned), n_frames))
    results.append(summarise("INDEPENDENT-PNR", pairs_within(benign), n_frames))
    results.append(summarise("INDEP-MALICIOUS", pairs_within(malic), n_frames))
    cross = [(a, b, diff_frames(F[a], F[b])) for a in benign for b in malic]
    results.append(summarise("CROSS-LABEL", cross, n_frames))
    results = [r for r in results if r]

    shared = next((r for r in results if r["class"] == "SHARED-LINEAGE"), None)
    indep = next((r for r in results if r["class"] == "INDEPENDENT-PNR"), None)
    ratio = None
    if shared and indep and shared["median_frames_differing"] > 0:
        ratio = indep["median_frames_differing"] / shared["median_frames_differing"]
    elif shared and indep:
        ratio = float("inf")

    print()
    if ratio is not None:
        print(f"=== CHURN FLOOR COLLAPSE ===")
        print(f"  independent P&R churn is {ratio:.1f}x the shared-lineage "
              f"floor")
        print(f"  ({indep['median_frames_differing']:.0f} vs "
              f"{shared['median_frames_differing']:.0f} frames, median)")
        print(f"\n  A trojan occupying a handful of frames is invisible against")
        print(f"  a {indep['median_frames_differing']:.0f}-frame noise floor "
              f"but stands out against a")
        print(f"  {shared['median_frames_differing']:.0f}-frame one. This is "
              f"the mechanism behind L2c, measured")
        print(f"  directly rather than inferred from rankings.")

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "design": args.design, "n_frames": n_frames,
           "n_shared_lineage_builds": len(pinned),
           "n_independent_benign_payloads": len(benign),
           "n_independent_malicious_payloads": len(malic),
           "classes": results,
           "independent_over_shared_ratio": ratio,
           "interpretation": (
               "SHARED-LINEAGE builds descend from one routed checkpoint and "
               "differ only where the trojan moved; INDEPENDENT-PNR builds "
               "were implemented separately and differ across the whole "
               "device. The ratio bounds how much noise a placement-provenance-"
               "sharing verification flow removes, and therefore how much "
               "trojan signal a deployable detector could recover.")}
    pre = cfg["out_prefix"]
    with open(os.path.join("localization_corpus",
                           f"{pre}_churn_floor.json"), "w") as f:
        json.dump(out, f, indent=2)
    with open(os.path.join("localization_corpus",
                           f"{pre}_churn_floor.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(f"\nresults -> localization_corpus/{pre}_churn_floor.json")


if __name__ == "__main__":
    main()
