# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Format-aware L3 localization -- frame typing + CLB tile
#              decode on every archived L3 build, scored against the
#              constructive implant ground truth.
#
#              For each build folder (l3, l3b, l3d, l3c/PIC16F84, l3c/RS232)
#              every .bit is compared to that folder's B_Default.bit, which
#              descends from the same placed checkpoint. Per build:
#
#                raw windows    8-frame windows with any differing byte, over
#                               all frames and over logic-only frames
#                               (frame_types.diff_payloads)
#                tiles changed  CLB tiles with a differing word in their
#                               site-owned minors 0-1, 26-35
#                LUT classes    lut_canon.classify over every LUT of those
#                               tiles
#                flagged        tiles with a new / removed / function_changed
#                               LUT or an FF.ZINI / FF.ZRST change
#                               (tile_decode.compare_payloads)
#
#              GROUND TRUTH (l3 only) is the implant sites recorded before
#              the build (l3_forensic_results_v2.json,
#              per_build.<build>.declared_sites). Each SLICE sits in exactly
#              one tile per tilegrid.json "sites", so the truth becomes a tile
#              set at the same granularity as the flags. Unlike the (column,
#              clock-region) window set of l3_site_frame_map.py, this supports
#              recall and IoU:
#
#                TP = flagged & GT    FP = flagged - GT    FN = GT - flagged
#                precision = TP / |flagged|    recall = TP / |GT|
#                IoU = TP / |flagged | GT|
#                survival = every GT tile is among the changed tiles
#
#              Survival separates two ways to miss: a GT tile absent from the
#              changed set never reached the logic-minor diff at all; one that
#              changed but was not flagged was seen and then passed by the
#              flag rules. A site whose tile is not a CLB tile is reported as
#              unmapped and does not enter GT.
#
#              Results, with the prjxray-db commit and the SHA-256 of every
#              input (bitstreams, GT file, database files), go to
#              localization_corpus/format_aware/l3_format_aware_results.json.
#              verify_format_aware.py re-checks them without these modules.
#
# Usage:
#   python3 l3_format_aware_eval.py [--artifacts DIR] [--gt PATH]
#                                   [--db DIR] [--out PATH]

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

from bitstream_io import ZYNQ7020_V4, fdri_payload_and_meta, file_sha256
from far_map import PART_YAML, default_db_dir
from frame_types import (SEGBITS_DIR, TILEGRID_JSON, FrameTypes,
                         check_expected, diff_payloads)
from l2_localization_eval import WINDOW_FRAMES
from lut_canon import CLASSES as LUT_CLASSES
from tile_decode import (CLB_TILE_TYPES, LOGIC_MINORS, TileDecoder,
                         compare_payloads)

SCHEMA = "l3_format_aware_eval_v1"
FOLDERS = ("l3", "l3b", "l3d", "l3c/PIC16F84", "l3c/RS232")
GT_FOLDER = "l3"
REF_BUILD = "B_Default"
OUT = os.path.join("localization_corpus", "format_aware",
                   "l3_format_aware_results.json")

LUT_ABBREV = {"unchanged": "unch", "new": "new", "removed": "rem",
              "route_thru": "rthru", "pin_permutation": "perm",
              "support_reduced_perm": "srp", "function_changed": "fchg"}


# ---------------------------------------------------------------------------
# Ground truth: SLICE sites -> CLB tiles.
# ---------------------------------------------------------------------------
def site_tiles(tilegrid_path):
    """{SLICE site: (tile name, tile type)} from tilegrid.json "sites"."""
    with open(tilegrid_path) as fh:
        grid = json.load(fh)
    out = {}
    for name, t in grid.items():
        for site in t.get("sites", {}):
            if not site.startswith("SLICE_"):
                continue
            if site in out:
                raise ValueError("%s is in both %s and %s"
                                 % (site, out[site][0], name))
            out[site] = (name, t.get("type"))
    return out


def load_gt(path):
    """{build: [declared SLICE sites]}."""
    with open(path) as fh:
        per_build = json.load(fh)["per_build"]
    return {b: r["declared_sites"] for b, r in per_build.items()
            if "declared_sites" in r}


def gt_tiles(sites, by_site):
    """(sorted CLB tile names, [sites with no CLB tile])."""
    tiles, unmapped = set(), []
    for s in sites:
        hit = by_site.get(s)
        if hit is None or hit[1] not in CLB_TILE_TYPES:
            unmapped.append(s)
        else:
            tiles.add(hit[0])
    return sorted(tiles), unmapped


def _ratio(num, den):
    return num / den if den else None


def score(flagged, gt, changed):
    f, g = set(flagged), set(gt)
    tp = len(f & g)
    missing = sorted(g - set(changed))
    return {"tp": tp, "fp": len(f - g), "fn": len(g - f),
            "precision": _ratio(tp, len(f)),
            "recall": _ratio(tp, len(g)),
            "iou": _ratio(tp, len(f | g)),
            "survived": not missing,
            "gt_tiles_not_in_diff": missing}


# ---------------------------------------------------------------------------
# Per-folder evaluation.
# ---------------------------------------------------------------------------
def evaluate_folder(root, folder, ft, dec, gt_sites, by_site, inputs):
    d = os.path.join(root, folder)
    ref_path = os.path.join(d, REF_BUILD + ".bit")
    if not os.path.exists(ref_path):
        sys.exit("missing reference %s" % ref_path)
    inputs["artifacts/%s/%s.bit" % (folder, REF_BUILD)] = file_sha256(ref_path)
    ref, _ = fdri_payload_and_meta(ref_path, ZYNQ7020_V4)

    out = {}
    for path in sorted(glob.glob(os.path.join(d, "*.bit"))):
        build = os.path.basename(path)[:-4]
        if build == REF_BUILD:
            continue
        inputs["artifacts/%s/%s.bit" % (folder, build)] = file_sha256(path)
        test, _ = fdri_payload_and_meta(path, ZYNQ7020_V4)
        w = diff_payloads(ref, test, ft, frame_bytes=ZYNQ7020_V4.frame_bytes)
        t = compare_payloads(ref, test, dec,
                             frame_words=ZYNQ7020_V4.frame_words)
        rec = {
            "frames_differing": w["frames_differing"],
            "windows_differing_all": w["windows_differing_all"],
            "windows_differing_logic_only": w["windows_differing_logic_only"],
            "differing_windows_all": w["differing_windows_all"],
            "differing_windows_logic_only": w["differing_windows_logic_only"],
            "tiles_checked": t["tiles_checked"],
            "logic_tiles_changed": t["logic_tiles_changed"],
            "lut_classes": t["lut_classes"],
            "flagged": t["flagged"],
            "flag_reasons": t["flag_reasons"],
            "changed_tiles": sorted(t["changed_tiles"]),
            "gt": None,
        }
        sites = gt_sites.get(build) if gt_sites is not None else None
        if sites is not None:
            tiles, unmapped = gt_tiles(sites, by_site)
            rec["gt"] = {"n_sites": len(sites), "sites_unmapped": unmapped,
                         "tiles": tiles,
                         **score(t["flagged"], tiles, rec["changed_tiles"])}
        out[build] = rec
        print("  %s/%s done" % (folder, build), file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Report.
# ---------------------------------------------------------------------------
def _num(x, width=6):
    return "%*s" % (width, "-") if x is None else "%*.3f" % (width, x)


def print_table(builds, n_windows):
    print("=== format-aware L3 comparison vs %s (windows of %d; LUT counts "
          "over changed tiles) ===" % (REF_BUILD, n_windows))
    print("%-13s %-20s %5s %5s %5s " % ("folder", "build", "win", "logic",
                                         "tiles")
          + " ".join("%5s" % LUT_ABBREV.get(c, c[:5]) for c in LUT_CLASSES)
          + " %4s %3s %3s %3s %6s %6s %6s %4s"
          % ("flag", "TP", "FP", "FN", "prec", "recall", "IoU", "surv"))
    for folder, recs in builds.items():
        for build, r in recs.items():
            g = r["gt"]
            tail = (" %3s %3s %3s %6s %6s %6s %4s" % (("-",) * 7) if g is None
                    else " %3d %3d %3d %s %s %s %4s"
                    % (g["tp"], g["fp"], g["fn"], _num(g["precision"]),
                       _num(g["recall"]), _num(g["iou"]),
                       "yes" if g["survived"] else "NO"))
            print("%-13s %-20s %5d %5d %5d " % (folder, build,
                                                 r["windows_differing_all"],
                                                 r["windows_differing_logic_only"],
                                                 r["logic_tiles_changed"])
                  + " ".join("%5d" % r["lut_classes"][c] for c in LUT_CLASSES)
                  + " %4d" % len(r["flagged"]) + tail)

    print("\nflagged tiles (* = GT tile):")
    for folder, recs in builds.items():
        for build, r in recs.items():
            gt = set(r["gt"]["tiles"]) if r["gt"] else set()
            names = ["%s%s" % (n, "*" if n in gt else "") for n in r["flagged"]]
            print("  %s/%s: %s" % (folder, build,
                                   ", ".join(names) if names else "(none)"))
            if r["gt"] and r["gt"]["gt_tiles_not_in_diff"]:
                print("      GT tiles not in diff: %s"
                      % ", ".join(r["gt"]["gt_tiles_not_in_diff"]))
            if r["gt"] and r["gt"]["sites_unmapped"]:
                print("      GT sites with no CLB tile: %s"
                      % ", ".join(r["gt"]["sites_unmapped"]))


def summarize(builds):
    """Micro-averaged scores over every build with ground truth."""
    gts = [r["gt"] for recs in builds.values() for r in recs.values()
           if r["gt"] is not None]
    tp = sum(g["tp"] for g in gts)
    fp = sum(g["fp"] for g in gts)
    fn = sum(g["fn"] for g in gts)
    return {"n_builds": len(gts), "tp": tp, "fp": fp, "fn": fn,
            "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
            "iou": _ratio(tp, tp + fp + fn),
            "n_survived": sum(1 for g in gts if g["survived"])}


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Frame-type + CLB tile comparison on every L3 build, "
                    "scored against the implant ground truth")
    p.add_argument("--artifacts", default="rebuild_pilot/pilot_artifacts",
                   help="folder holding l3, l3b, l3d, l3c/...")
    p.add_argument("--gt", default=os.path.join(
        "localization_corpus", "l3_forensic_results_v2.json"))
    p.add_argument("--db", default=None,
                   help="prjxray-db folder (default: CURRENT in the cache)")
    p.add_argument("--out", default=OUT)
    args = p.parse_args()

    db_dir = args.db or default_db_dir()
    ft = FrameTypes.load(db_dir)
    problems = check_expected(ft)
    if problems:
        sys.exit("frame classes deviate from the expected pattern:\n  "
                 + "\n  ".join(problems))
    dec = TileDecoder.load(db_dir)
    tilegrid_path = os.path.join(db_dir, TILEGRID_JSON)
    by_site = site_tiles(tilegrid_path)
    if not os.path.exists(args.gt):
        sys.exit("missing ground truth %s" % args.gt)
    gt_sites = load_gt(args.gt)

    inputs = {"gt/" + os.path.basename(args.gt): file_sha256(args.gt)}
    db_files = [PART_YAML, TILEGRID_JSON] + sorted(
        os.path.relpath(q, db_dir) for q in
        glob.glob(os.path.join(db_dir, SEGBITS_DIR, "segbits_*.db")))
    for rel in db_files:
        inputs["prjxray-db/" + rel] = file_sha256(os.path.join(db_dir, rel))

    builds = {}
    for folder in FOLDERS:
        builds[folder] = evaluate_folder(
            args.artifacts, folder, ft, dec,
            gt_sites if folder == GT_FOLDER else None, by_site, inputs)
    n_windows = ft.n_frames // WINDOW_FRAMES

    print_table(builds, n_windows)
    summ = summarize(builds)
    print("\n%s GT builds %d | TP %d FP %d FN %d | precision %s recall %s "
          "IoU %s | survived %d/%d"
          % (GT_FOLDER, summ["n_builds"], summ["tp"], summ["fp"], summ["fn"],
             _num(summ["precision"], 0), _num(summ["recall"], 0),
             _num(summ["iou"], 0), summ["n_survived"], summ["n_builds"]))
    unused = sorted(set(gt_sites) - set(builds[GT_FOLDER]))
    if unused:
        print("GT builds with no bitstream in %s: %s"
              % (GT_FOLDER, ", ".join(unused)))

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "part": "xc7z020clg400-1",
        "prjxray_db_sha": ft.db_sha,
        "artifacts_root": args.artifacts,
        "gt_path": args.gt,
        "gt_folder": GT_FOLDER,
        "reference_build": REF_BUILD,
        "window_frames": WINDOW_FRAMES,
        "n_windows": n_windows,
        "logic_minors": list(LOGIC_MINORS),
        "gt_mapping": ("declared SLICE -> its tile via tilegrid.json "
                       "\"sites\"; non-CLB tiles are reported as unmapped"),
        "survival": ("every GT tile has a differing word in its logic "
                     "minors, i.e. is among changed_tiles"),
        "inputs": inputs,
        "builds": builds,
        "summary": summ,
        "gt_builds_without_bitstream": unused,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print("-> %s" % args.out)


if __name__ == "__main__":
    main()
