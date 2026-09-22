# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: BLADEI-VERIFY -- the deployable placed-checkpoint localizer as a
#              command-line screen. This is the L3 result packaged as a tool:
#              given a bitstream the operator built from their own placed
#              checkpoint (the REFERENCE) and a SUSPECT bitstream returned by a
#              third party, it reports the configuration windows in which the
#              suspect differs -- the candidate locations of any added logic --
#              and gates that report on the routing-determinism PRECONDITION
#              the operator can check from two of their own benign builds.
#
#              THREAT MODEL (see localization_corpus/L3_FORENSIC_RESULT.md).
#              The operator implements a design to a PLACED checkpoint and ships
#              it; a returned bitstream must be built from that checkpoint, so
#              host placement is fixed and only routing/added-logic can differ.
#              The tool never needs the netlist, a FAR map, or a model.
#
#              WHAT IT DOES, exactly:
#                * payload = the profile-validated FDRI region (bitstream_io),
#                  reshaped into 1,251 eight-frame windows;
#                * DIFF = windows where suspect != reference (byte-exact);
#                * FLOOR = if a second benign build under the same route
#                  directive is given (--floor-ref), the windows by which two
#                  legitimate builds differ -- the routing nondeterminism the
#                  implant must exceed. The precondition (L3B/L3-timing): if the
#                  floor is ~0 the flagged set is trustworthy; if it is large
#                  the design does not route deterministically (typically
#                  because it does not close timing with margin) and the flag
#                  is unreliable.
#
#              HONEST OUTPUT. The tool localizes; it does not detect. It answers
#              "where does this bitstream differ from mine", given the operator
#              already holds the matching checkpoint. It reports flagged windows
#              and the floor verdict, and never claims a window "is a trojan".
#              Window granularity only; no recall/IoU.
#
# Usage:
#   python3 bladei_verify.py --reference ref.bit --suspect suspect.bit
#                            [--floor-ref ref2.bit] [--json out.json]

import argparse
import json
import sys
import time

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from l2_localization_eval import WINDOW_FRAMES, windows
from split_utils import FRAME_BYTES

FLOOR_OK = 5   # windows; "the design routes deterministically" (L3-timing)


def load_windows(path):
    return windows(fdri_payload(path, ZYNQ7020_V4))


def diff_windows(a, b):
    """Indices where the two window matrices differ, byte-exact."""
    d = np.abs(a.astype(np.int32) - b.astype(np.int32)).sum(axis=1)
    return np.flatnonzero(d > 0), d


def contiguous_runs(idx):
    """Compress a sorted index list into [start,end] runs for readability."""
    runs, idx = [], list(idx)
    for i in idx:
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    return [(a, b) for a, b in runs]


def main():
    p = argparse.ArgumentParser(
        description="BLADEI-VERIFY: placed-checkpoint bitstream localizer")
    p.add_argument("--reference", required=True,
                   help="operator's own build from the placed checkpoint")
    p.add_argument("--suspect", required=True,
                   help="bitstream under test (same placed checkpoint)")
    p.add_argument("--floor-ref", default=None,
                   help="a second legitimate benign build (same route "
                        "directive) to measure the routing floor / precondition")
    p.add_argument("--json", default=None)
    args = p.parse_args()

    t_start = time.perf_counter()
    ref = load_windows(args.reference)
    sus = load_windows(args.suspect)
    if ref.shape != sus.shape:
        sys.exit("reference and suspect have different geometry (%s vs %s)"
                 % (ref.shape, sus.shape))
    n_win = ref.shape[0]

    flagged, dmag = diff_windows(sus, ref)
    flagged = flagged.tolist()

    floor_n, floor_windows, precondition = None, [], "not measured"
    if args.floor_ref:
        fref = load_windows(args.floor_ref)
        fw, _ = diff_windows(fref, ref)
        floor_windows = fw.tolist()
        floor_n = len(floor_windows)
        precondition = ("PASS (routes deterministically; flagged set is "
                        "trustworthy)" if floor_n <= FLOOR_OK else
                        "FAIL (routing nondeterministic -- %d benign-vs-benign "
                        "windows; the design likely does not close timing with "
                        "margin, so the flag is unreliable)" % floor_n)
        # Flagged windows not explained by the benign routing floor.
        residual = sorted(set(flagged) - set(floor_windows))
    else:
        residual = flagged

    elapsed_ms = 1000.0 * (time.perf_counter() - t_start)
    print("=== BLADEI-VERIFY ===")
    print("reference : %s" % args.reference)
    print("suspect   : %s" % args.suspect)
    print("windows   : %d (8 frames each)" % n_win)
    print()
    print("flagged windows (suspect != reference): %d / %d  (%.2f%% of device)"
          % (len(flagged), n_win, 100.0 * len(flagged) / n_win))
    if args.floor_ref:
        print("routing floor (benign vs benign)     : %d windows" % floor_n)
        print("precondition                         : %s" % precondition)
        print("flagged beyond the routing floor     : %d windows" % len(residual))
    top = sorted(range(n_win), key=lambda i: -dmag[i])[:min(10, len(flagged))]
    top = [i for i in top if dmag[i] > 0]
    print("\ncandidate windows (by change magnitude), most-changed first:")
    print("  " + ", ".join(str(i) for i in top))
    print("contiguous flagged runs: %s"
          % (contiguous_runs(sorted(residual))[:20] or "-"))
    print("elapsed         : %.0f ms  (host; parse + window + compare)"
          % elapsed_ms)
    print("\nNOTE: localization, not detection. Reports WHERE the suspect "
          "differs from your\nown build; it does not assert a window is "
          "malicious. Window granularity only.")

    if args.json:
        out = {"tool": "bladei_verify_v1", "n_windows": n_win,
               "reference": args.reference, "suspect": args.suspect,
               "floor_ref": args.floor_ref,
               "n_flagged": len(flagged), "flagged_windows": flagged,
               "floor_windows": floor_windows, "floor_n": floor_n,
               "precondition": precondition,
               "residual_windows": residual,
               "top_by_magnitude": top,
               "elapsed_ms_host": round(elapsed_ms, 1)}
        json.dump(out, open(args.json, "w"), indent=2)
        print("\njson -> %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
