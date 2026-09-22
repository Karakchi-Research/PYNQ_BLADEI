# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L3 -- device-wide SLICE -> configuration-frame map,
#              and the complete L3 forensic rank evaluation it unlocks.
#
#              THE GAP THIS CLOSES. `l3_forensic_eval.py` ranks the implant
#              windows of the attacked builds, but it derived its site ->
#              frame map from ONE build's logic-location file, and an implant
#              is deliberately placed in FREE space, so the implant's own
#              slices never appear in any .ll. Frames had to come from host
#              cells sharing the implant's column and clock region -- and
#              where the design happens to place nothing in that column, the
#              site could not be mapped at all. Result: 3 of 6 region builds
#              were skipped, T_R0 mapped 3 of its 8 sites, and the rank
#              statistics rested on 10 implant windows out of ~150 recorded
#              implant sites across the campaign.
#
#              THE OBSERVATION THAT FIXES IT. Which frames configure a given
#              SLICE is a property of the DEVICE, not of the design: it
#              follows from the 7-series configuration column layout. So every
#              .ll produced for this part -- any design, any build, any
#              directive -- is a sample of the same map, and their union
#              covers far more of the device than any single build.
#
#              That is a claim, so it is TESTED rather than assumed. Every
#              slice observed in more than one file must report a CONSISTENT
#              frame set, where consistent means nested (one file's set is a
#              subset of another's): a single .ll only lists the frames whose
#              bits that build actually uses, so partial coverage of a
#              multi-frame SLICEM is expected, while two files disagreeing on
#              a frame INDEX for the same slice would falsify the claim and
#              the run aborts.
#
#              WHAT THE MAP CAN AND CANNOT SAY. It resolves a site to the
#              frames observed for its (column, clock-region row), which is
#              coarser than the site's own bits: the target window set is an
#              OVER-APPROXIMATION, 1-6 windows of 1,251 per build. That is
#              honest for a localization claim -- a larger target set makes
#              good ranks harder to achieve, not easier -- but it is not a
#              bit-exact ground truth and no recall/IoU number should be built
#              on it. The full 36-frames-per-CLB-column range still needs the
#              device column layout (Phase 2, unsourced).
#
#              Artifacts are written alongside the originals, never over them:
#              l3_forensic_results.json stays as the 3-build record.
#
# Usage:
#   python3 l3_site_frame_map.py [--ll-root DIR] [--l3-dir DIR]
#                                [--truth-dir DIR] [--outdir DIR]

import argparse
import collections
import csv
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from l2_localization_eval import WINDOW_FRAMES, ranks_of, windows
from split_utils import FRAME_BYTES

SCHEMA = "l3_site_frame_map_v1"
FRAME_BITS = FRAME_BYTES * 8

# 7-series clock regions are 50 CLB rows tall; a configuration frame covers one
# column within one clock-region row, so slices sharing (column, region row)
# are configured by the same frames.
CLOCK_REGION_ROWS = 50

_SITE = re.compile(r"SLICE_X(\d+)Y(\d+)")


# --------------------------------------------------------------------------
# the map
# --------------------------------------------------------------------------
def parse_ll(path):
    """(slice_x, slice_y) -> {frame indices}, from one Vivado .ll."""
    out = collections.defaultdict(set)
    n_lines = 0
    with open(path, errors="ignore") as fh:
        for line in fh:
            if not line.startswith("Bit "):
                continue
            t = line.split(None, 5)
            if len(t) < 5 or not t[4].startswith("Block=SLICE_X"):
                continue
            delta = int(t[1]) - int(t[3])
            if delta % FRAME_BITS:
                # Non-frame-aligned line: the geometry assumption is wrong.
                raise AssertionError("%s: .ll line not frame-aligned: %s"
                                     % (path, line.strip()))
            xs, _, ys = t[4][len("Block=SLICE_X"):].partition("Y")
            out[(int(xs), int(ys))].add(delta // FRAME_BITS)
            n_lines += 1
    return dict(out), n_lines


def build_device_map(ll_paths):
    """Union the per-slice frame sets, asserting consistency across files.

    Consistent = nested. Two files may list different NUMBERS of frames for
    one slice (each lists only the frames its own build uses), but a frame
    index reported for a slice by one file and contradicted by another would
    mean the map is not a device property. That aborts the run.
    """
    union, per_file, checks, nested = {}, {}, 0, 0
    for p in ll_paths:
        m, n_lines = parse_ll(p)
        per_file[p] = {"n_slice_lines": n_lines, "n_slices": len(m)}
        for key, frames in m.items():
            if key in union:
                checks += 1
                if union[key] != frames:
                    if frames <= union[key] or union[key] <= frames:
                        nested += 1
                        union[key] |= frames
                    else:
                        raise AssertionError(
                            "SLICE_X%dY%d: contradictory frame sets %s vs %s "
                            "(%s) -- the map is not a device property"
                            % (key[0], key[1], sorted(union[key]),
                               sorted(frames), p))
            else:
                union[key] = set(frames)
    by_column = collections.defaultdict(set)
    for (x, y), frames in union.items():
        by_column[(x, y // CLOCK_REGION_ROWS)] |= frames
    return union, dict(by_column), per_file, checks, nested


def site_frames(sites, by_column):
    """Frames for declared implant sites, via (column, clock-region row)."""
    frames, unmapped = set(), []
    for s in sites:
        m = _SITE.match(s)
        if not m:
            continue
        key = (int(m.group(1)), int(m.group(2)) // CLOCK_REGION_ROWS)
        if key in by_column:
            frames |= by_column[key]
        else:
            unmapped.append(s)
    return sorted(frames), unmapped


def declared_sites(truth_dir, tag):
    """Sites this campaign CHOSE for the implant, recorded before the build."""
    path = os.path.join(truth_dir, "%s_implant_truth.txt" % tag)
    sites, region = [], None
    if not os.path.exists(path):
        return sites, region
    for line in open(path):
        if line.startswith("region:"):
            region = line.split(":", 1)[1].strip()
        elif line.startswith("IMPLANT "):
            sites.append(line.split()[-1])
    return sites, region


# Build families in the L3 campaign, each with its own question.
FAMILIES = {"T": "region sweep (8 cells, 6 placements)",
            "S": "size sweep (1-32 cells, one region)",
            "F": "functional implant (taps a host net)",
            "P": "tap survey (5 host nets, size and region fixed)"}


def main():
    p = argparse.ArgumentParser(
        description="Device-wide SLICE->frame map + full L3 rank evaluation")
    p.add_argument("--ll-root", default="rebuild_pilot",
                   help="searched recursively for *.ll (any design, same part)")
    p.add_argument("--l3-dir", default="rebuild_pilot/pilot_artifacts/l3")
    p.add_argument("--truth-dir",
                   default="rebuild_pilot/pilot_evidence/l3_reports")
    p.add_argument("--outdir", default="localization_corpus")
    args = p.parse_args()

    ll_paths = sorted(glob.glob(os.path.join(args.ll_root, "**", "*.ll"),
                                recursive=True))
    if not ll_paths:
        sys.exit("no .ll files under %s" % args.ll_root)

    print("=== device-wide SLICE -> frame map ===")
    print("%d logic-location files under %s" % (len(ll_paths), args.ll_root))
    union, by_column, per_file, checks, nested = build_device_map(ll_paths)
    print("  slices mapped                : %d" % len(union))
    print("  (column, clock-region) keys  : %d" % len(by_column))
    print("  cross-file slice comparisons : %d" % checks)
    print("  nested (partial-coverage)    : %d" % nested)
    print("  CONTRADICTIONS               : 0  <- asserted, run aborts if not")

    ref_path = os.path.join(args.l3_dir, "B_Default.bit")
    if not os.path.exists(ref_path):
        sys.exit("missing the like-for-like benign reference %s" % ref_path)
    ben = {os.path.basename(q)[:-4]: windows(fdri_payload(q, ZYNQ7020_V4))
           for q in sorted(glob.glob(os.path.join(args.l3_dir, "B_*.bit")))}
    ref = ben["B_Default"]
    refb = np.unpackbits(ref, axis=1)
    pop_med = np.median(np.stack(list(ben.values())).astype(np.int16), axis=0)
    n_win = ref.shape[0]

    attacked = sorted(q for q in glob.glob(os.path.join(args.l3_dir, "*.bit"))
                      if not os.path.basename(q).startswith("B_"))
    print("\n=== L3 forensic rank evaluation, ALL attacked builds ===")
    print("reference: B_Default (like-for-like route directive) | "
          "%d windows | random rank %.0f\n" % (n_win, (n_win + 1) / 2))

    rows, per_build = [], {}
    for path in attacked:
        tag = os.path.basename(path)[:-4]
        sites, region = declared_sites(args.truth_dir, tag)
        if not sites:
            print("  %-20s no recorded implant truth -- skipped" % tag)
            continue
        frames, unmapped = site_frames(sites, by_column)
        targets = sorted({f // WINDOW_FRAMES for f in frames})
        if not targets:
            print("  %-20s %d sites, none mappable -- skipped"
                  % (tag, len(sites)))
            continue
        W = windows(fdri_payload(path, ZYNQ7020_V4))
        Wb = np.unpackbits(W, axis=1)
        scores = {
            "like_for_like_l1": np.abs(W.astype(np.int32)
                                       - ref.astype(np.int32)
                                       ).sum(axis=1).astype(float),
            "like_for_like_ham": np.abs(Wb - refb).sum(axis=1).astype(float),
            "pop_median_l1": np.abs(W.astype(np.int16)
                                    - pop_med).sum(axis=1).astype(float),
        }
        differing = set(np.flatnonzero(scores["like_for_like_l1"] > 0).tolist())
        n_diff = len(differing)
        hit_diff = len(differing & set(targets))
        rec = {"family": FAMILIES.get(tag[0], "other"), "region": region,
               "n_declared_sites": len(sites), "declared_sites": sites,
               "n_sites_unmapped": len(unmapped),
               "implant_frames": frames, "implant_windows": targets,
               "n_windows_differing_like_for_like": n_diff,
               "target_windows_in_differing_set": hit_diff,
               "scorers": {}}
        print("--- %-20s %-28s sites %d (unmapped %d)"
              % (tag, region or "-", len(sites), len(unmapped)))
        print("      target windows %s | differing %d/%d | targets inside "
              "differing set %d/%d"
              % (targets, n_diff, n_win, hit_diff, len(targets)))
        for name, sc in scores.items():
            r = ranks_of(sc, targets)
            best, med = min(r.values()), float(np.median(list(r.values())))
            topn = sum(1 for v in r.values() if v <= len(targets))
            rec["scorers"][name] = {"ranks": r, "best_rank": best,
                                    "median_rank": med,
                                    "n_target_windows": len(targets),
                                    "target_windows_in_topN": topn}
            rows.append({"build": tag, "family": rec["family"],
                         "region": region, "scorer": name, "best_rank": best,
                         "median_rank": med, "n_target_windows": len(targets),
                         "target_windows_in_topN": topn,
                         "n_windows_differing": n_diff, "n_windows": n_win})
            print("      %-20s best %6.1f | median %7.1f | in top-%d: %d/%d"
                  % (name, best, med, len(targets), topn, len(targets)))
        per_build[tag] = rec
        print()

    print("=== SUMMARY by scorer (median over builds of the per-build "
          "median rank) ===")
    summ = {}
    for name in ("like_for_like_l1", "like_for_like_ham", "pop_median_l1"):
        rr = [r for r in rows if r["scorer"] == name]
        if not rr:
            continue
        y = np.array([r["median_rank"] for r in rr])
        summ[name] = {"median_rank": float(np.median(y)),
                      "best_rank": float(y.min()),
                      "worst_rank": float(y.max()),
                      "target_windows_recovered_in_topN":
                          sum(r["target_windows_in_topN"] for r in rr),
                      "target_windows_total":
                          sum(r["n_target_windows"] for r in rr),
                      "n_builds": len(rr)}
        s = summ[name]
        print("  %-20s median %7.1f | best %6.1f | worst %7.1f | in top-N "
              "%d/%d over %d builds"
              % (name, s["median_rank"], s["best_rank"], s["worst_rank"],
                 s["target_windows_recovered_in_topN"],
                 s["target_windows_total"], s["n_builds"]))

    by_family = collections.defaultdict(list)
    for r in rows:
        if r["scorer"] == "like_for_like_ham":
            by_family[r["family"]].append(r)
    print("\n=== by build family (like_for_like_ham) ===")
    fam_summary = {}
    for fam, rr in sorted(by_family.items()):
        y = [r["median_rank"] for r in rr]
        fam_summary[fam] = {"n_builds": len(rr),
                            "median_of_median_rank": float(np.median(y)),
                            "worst_median_rank": float(max(y))}
        print("  %-42s %d builds | median %6.1f | worst %6.1f"
              % (fam, len(rr), float(np.median(y)), max(y)))

    os.makedirs(args.outdir, exist_ok=True)
    map_out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "part": "xc7z020clg400-1",
        "granularity": ("(SLICE column, clock-region row); the target window "
                        "set is an over-approximation of the site's own "
                        "frames, so ranks are conservative and no recall/IoU "
                        "number may be derived"),
        "clock_region_rows": CLOCK_REGION_ROWS,
        "n_ll_files": len(ll_paths),
        "n_slices": len(union),
        "n_column_keys": len(by_column),
        "cross_file_comparisons": checks,
        "nested_partial_coverage": nested,
        "contradictions": 0,
        "per_file": {os.path.relpath(k): v for k, v in per_file.items()},
        "column_map": {"%d,%d" % k: sorted(v) for k, v in by_column.items()},
    }
    with open(os.path.join(args.outdir, "l3_site_frame_map.json"), "w") as fh:
        json.dump(map_out, fh, indent=2)

    eval_out = {
        "schema": "l3_forensic_eval_v2",
        "generated": datetime.now(timezone.utc).isoformat(),
        "supersedes": ("l3_forensic_results.json (3 of 6 region builds; that "
                       "record is retained unchanged)"),
        "design": "AES-T1000 (benign host) + ECO implant",
        "threat_model": ("attacker edits a shipped PLACED checkpoint; host "
                         "placement is fixed, only routing varies. Task is "
                         "forensic localization of the added logic."),
        "ground_truth": ("implant sites chosen and recorded by "
                         "l3_eco_implant.tcl before the bitstream existed; "
                         "sites mapped to frames through the device-wide "
                         "SLICE->frame map (l3_site_frame_map.json)"),
        "reference_build": "B_Default (like-for-like route directive)",
        "benign_population": list(ben),
        "n_windows": n_win, "random_expected_rank": (n_win + 1) / 2,
        "families": FAMILIES,
        "per_build": per_build, "summary": summ, "by_family": fam_summary,
    }
    with open(os.path.join(args.outdir,
                           "l3_forensic_results_v2.json"), "w") as fh:
        json.dump(eval_out, fh, indent=2)
    if rows:
        with open(os.path.join(args.outdir, "l3_forensic_ranks_v2.csv"), "w",
                  newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print("\nmap  -> %s" % os.path.join(args.outdir, "l3_site_frame_map.json"))
    print("eval -> %s"
          % os.path.join(args.outdir, "l3_forensic_results_v2.json"))
    print("builds evaluated: %d (was 3)" % len(per_build))


if __name__ == "__main__":
    main()
