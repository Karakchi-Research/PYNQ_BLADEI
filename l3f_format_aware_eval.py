# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Format-aware localization on the meson L3 builds -- the
#              l3_format_aware_eval.py method, scored against the implant
#              truth files written at build time.
#
#              EXPERIMENTS maps each build folder under --artifacts to the
#              B_Default.bit it is compared with. The l3_slack folders carry
#              their own reference; the functional, width and size sweeps
#              were built from the b15-T200/p20 or AES-T1000/p8 checkpoint and
#              use that folder's reference. REFERENCE GUARD: a build and its
#              reference must match in file size and in the design name of the
#              .bit header ("top" for b15, "aes_128" for AES), or the run
#              stops naming both files. builds/ holds older pilot rebuilds,
#              not implants, and is not listed.
#
#              Build classes, from <folder>/reports/<build>_implant_truth.txt:
#                implant            truth file + .bit; GT = its IMPLANT sites
#                benign             .bit, no truth file (B_Explore); every
#                                   flag is a false positive
#                truth without bit  truth file only (l3_funct T_full did not
#                                   route); listed, not an error
#
#              Truth file: "key: value" header lines (keys in TRUTH_KEYS; a
#              value may be empty) and "IMPLANT <cell> <SLICE site>" lines;
#              any other line raises, as does a tag that is not the build
#              name. The header is kept as written (values whitespace-
#              stripped). trigger_taps is a Tcl list, so "{out_OBUF[10]}" is
#              one tap. n_taps = number of trigger_taps, else 1 if tap_net is
#              set, else 0. A cell's name prefix gives its role (ROLES), and a
#              GT tile collects the roles of every cell placed in it; an
#              unknown prefix raises.
#
#              Scoring reuses l3_format_aware_eval (SLICE -> tile, TP/FP/FN,
#              precision, recall, IoU, survival). KILL CRITERION: an implant
#              build FAILS if recall < KILL_MIN_RECALL or if its flagged tiles
#              outside GT exceed KILL_MAX_FP_PER_GT x its GT tiles.
#
#              Results, with the SHA-256 of every bitstream and truth file
#              (keyed by path relative to --artifacts) and of the prjxray-db
#              files, go to
#              localization_corpus/format_aware/l3f_format_aware_results.json.
#              verify_l3f_format_aware.py re-checks them independently.
#
# Usage:
#   python3 l3f_format_aware_eval.py --artifacts DIR [--db DIR] [--out PATH]

import argparse
import collections
import glob
import json
import os
import re
import struct
import sys
from datetime import datetime, timezone

from bitstream_io import ZYNQ7020_V4, fdri_payload_and_meta, file_sha256
from far_map import PART_YAML, default_db_dir
from frame_types import (SEGBITS_DIR, TILEGRID_JSON, FrameTypes,
                         check_expected, diff_payloads)
from l2_localization_eval import WINDOW_FRAMES
from l3_format_aware_eval import gt_tiles, score, site_tiles
from tile_decode import (CLB_TILE_TYPES, LOGIC_MINORS, TileDecoder,
                         compare_payloads)

SCHEMA = "l3f_format_aware_eval_v1"
OUT = os.path.join("localization_corpus", "format_aware",
                   "l3f_format_aware_results.json")

# Experiment folder -> reference bitstream, both relative to --artifacts.
B15_P20 = "l3_slack/b15-T200/p20/B_Default.bit"
AES_P8 = "l3_slack/AES-T1000/p8/B_Default.bit"
EXPERIMENTS = {
    "l3_slack/b15-T200/p8": "l3_slack/b15-T200/p8/B_Default.bit",
    "l3_slack/b15-T200/p10": "l3_slack/b15-T200/p10/B_Default.bit",
    "l3_slack/b15-T200/p12": "l3_slack/b15-T200/p12/B_Default.bit",
    "l3_slack/b15-T200/p14": "l3_slack/b15-T200/p14/B_Default.bit",
    "l3_slack/b15-T200/p16": "l3_slack/b15-T200/p16/B_Default.bit",
    "l3_slack/b15-T200/p20": B15_P20,
    "l3_slack/AES-T1000/p3": "l3_slack/AES-T1000/p3/B_Default.bit",
    "l3_slack/AES-T1000/p4": "l3_slack/AES-T1000/p4/B_Default.bit",
    "l3_slack/AES-T1000/p5": "l3_slack/AES-T1000/p5/B_Default.bit",
    "l3_slack/AES-T1000/p6": "l3_slack/AES-T1000/p6/B_Default.bit",
    "l3_slack/AES-T1000/p8": AES_P8,
    "l3_funct_b15": B15_P20,
    "l3_width": B15_P20,
    "l3_size_b15": B15_P20,
    "l3_funct": AES_P8,
    "l3_width_aes": AES_P8,
}

# Kill criterion for implant builds.
KILL_MIN_RECALL = 1.0
KILL_MAX_FP_PER_GT = 2

TRUTH_DIR = "reports"
TRUTH_SUFFIX = "_implant_truth.txt"
TRUTH_KEYS = ("tag", "region", "style", "n_cells", "clock_net", "tap_net",
              "trigger_taps", "payload_victim")
ROLES = (("bladei_ftrig_", "trigger"), ("bladei_farm_", "arming"),
         ("bladei_fpay_", "payload"), ("bladei_implant_", "tied"))
HEADER_PROBE_BYTES = 4096

_SITE = re.compile(r"^SLICE_X\d+Y\d+$")


class ReferenceMismatch(ValueError):
    """A build and its reference are not the same design / file layout."""


# ---------------------------------------------------------------------------
# Truth files.
# ---------------------------------------------------------------------------
def role_of(cell):
    for prefix, role in ROLES:
        if cell.startswith(prefix):
            return role
    raise ValueError("unknown implant cell prefix: %r" % cell)


def tcl_list(s):
    """Flat Tcl list -> items; "{a[1]}" is one item. Nesting raises."""
    out, i = [], 0
    while i < len(s):
        if s[i].isspace():
            i += 1
        elif s[i] == "{":
            j = s.find("}", i)
            if j < 0 or "{" in s[i + 1:j]:
                raise ValueError("unbalanced or nested braces in %r" % s)
            if j + 1 < len(s) and not s[j + 1].isspace():
                raise ValueError("text right after '}' in %r" % s)
            out.append(s[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < len(s) and not s[j].isspace():
                j += 1
            if "{" in s[i:j] or "}" in s[i:j]:
                raise ValueError("stray brace in %r" % s)
            out.append(s[i:j])
            i = j
    return out


def parse_truth(text, source="<truth>"):
    """(header {key: value}, [{"cell", "site", "role"}]). Raises on any
    unknown or duplicate key, malformed IMPLANT line or unknown prefix."""
    header, implants = {}, []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if line.startswith("IMPLANT"):
            toks = line.split()
            if toks[0] != "IMPLANT" or len(toks) != 3 \
                    or not _SITE.match(toks[2]):
                raise ValueError("%s:%d: malformed IMPLANT line %r"
                                 % (source, lineno, line))
            implants.append({"cell": toks[1], "site": toks[2],
                             "role": role_of(toks[1])})
            continue
        key, sep, value = line.partition(":")
        if not sep or key not in TRUTH_KEYS:
            raise ValueError("%s:%d: unknown line %r" % (source, lineno, line))
        if key in header:
            raise ValueError("%s:%d: duplicate key %s" % (source, lineno, key))
        header[key] = value.strip()
    return header, implants


def read_truth(path, build):
    with open(path) as fh:
        header, implants = parse_truth(fh.read(), path)
    if header.get("tag", build) != build:
        raise ValueError("%s: tag %r is not the build name %r"
                         % (path, header["tag"], build))
    return header, implants


def n_taps(header):
    taps = tcl_list(header.get("trigger_taps", ""))
    if taps:
        return len(taps)
    return 1 if header.get("tap_net") else 0


def tile_roles(implants, by_site):
    """{GT tile: sorted roles of the cells placed in it}."""
    roles = collections.defaultdict(set)
    for imp in implants:
        hit = by_site.get(imp["site"])
        if hit is not None and hit[1] in CLB_TILE_TYPES:
            roles[hit[0]].add(imp["role"])
    return {t: sorted(r) for t, r in sorted(roles.items())}


# ---------------------------------------------------------------------------
# Builds and the reference guard.
# ---------------------------------------------------------------------------
def discover(root, folder, ref_rel):
    """Classify a folder's builds; the reference itself is excluded.
    {"implant": [(build, bit, truth)], "benign": [(build, bit)],
     "truth_without_bit": [(build, truth)]}, paths relative to root."""
    d = os.path.join(root, folder)
    ref_real = os.path.realpath(os.path.join(root, ref_rel))
    bits = {os.path.basename(p)[:-4]: os.path.relpath(p, root)
            for p in glob.glob(os.path.join(d, "*.bit"))
            if os.path.realpath(p) != ref_real}
    truths = {os.path.basename(p)[:-len(TRUTH_SUFFIX)]:
              os.path.relpath(p, root)
              for p in glob.glob(os.path.join(d, TRUTH_DIR,
                                              "*" + TRUTH_SUFFIX))}
    return {
        "implant": [(b, bits[b], truths[b]) for b in sorted(bits)
                    if b in truths],
        "benign": [(b, bits[b]) for b in sorted(bits) if b not in truths],
        "truth_without_bit": [(b, truths[b]) for b in sorted(truths)
                              if b not in bits],
    }


def bit_design_name(path):
    """Design name: the .bit header's 'a' field up to the first ';'."""
    with open(path, "rb") as fh:
        head = fh.read(HEADER_PROBE_BYTES)
    try:
        off = 2 + struct.unpack_from(">H", head, 0)[0] + 2
        if head[off:off + 1] != b"a":
            raise ValueError
        n = struct.unpack_from(">H", head, off + 1)[0]
        field = head[off + 3:off + 3 + n]
        if len(field) != n:
            raise ValueError
    except (struct.error, ValueError):
        raise ValueError("%s: no design field in the .bit header"
                         % path) from None
    return field.rstrip(b"\x00").decode("latin1").split(";")[0]


def check_reference(build_path, ref_path):
    """Design name shared by build and reference; raises ReferenceMismatch
    naming both files on a size or design-name difference."""
    sb, sr = os.path.getsize(build_path), os.path.getsize(ref_path)
    if sb != sr:
        raise ReferenceMismatch("%s is %d bytes but its reference %s is %d"
                                % (build_path, sb, ref_path, sr))
    db, dr = bit_design_name(build_path), bit_design_name(ref_path)
    if db != dr:
        raise ReferenceMismatch("%s is design %r but its reference %s is %r"
                                % (build_path, db, ref_path, dr))
    return db


# ---------------------------------------------------------------------------
# Scoring.
# ---------------------------------------------------------------------------
def kill_reasons(g):
    """Why an implant build fails the kill criterion (empty list = PASS)."""
    out = []
    n_gt = len(g["tiles"])
    if g["recall"] is None or g["recall"] < KILL_MIN_RECALL:
        out.append("recall %s < %s" % (
            "-" if g["recall"] is None else "%.3f" % g["recall"],
            KILL_MIN_RECALL))
    if g["fp"] > KILL_MAX_FP_PER_GT * n_gt:
        out.append("FP %d > %d x %d GT tiles"
                   % (g["fp"], KILL_MAX_FP_PER_GT, n_gt))
    return out


def compare_build(ref, test, ft, dec):
    w = diff_payloads(ref, test, ft, frame_bytes=ZYNQ7020_V4.frame_bytes)
    t = compare_payloads(ref, test, dec, frame_words=ZYNQ7020_V4.frame_words)
    return {
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
    }


def gt_record(implants, flagged, changed, by_site):
    tiles, unmapped = gt_tiles([i["site"] for i in implants], by_site)
    g = {"n_sites": len(implants), "implants": implants,
         "sites_unmapped": unmapped, "tiles": tiles,
         "tile_roles": tile_roles(implants, by_site),
         **score(flagged, tiles, changed)}
    g["kill_reasons"] = kill_reasons(g)
    g["kill_passed"] = not g["kill_reasons"]
    return g


def _ratio(num, den):
    return num / den if den else None


def summarize(builds):
    imp = [(f, b, r["gt"]) for f, recs in builds.items()
           for b, r in recs.items() if r["class"] == "implant"]
    ben = [r for recs in builds.values() for r in recs.values()
           if r["class"] == "benign"]
    tp = sum(g["tp"] for _, _, g in imp)
    fp = sum(g["fp"] for _, _, g in imp)
    fn = sum(g["fn"] for _, _, g in imp)
    failed = ["%s/%s" % (f, b) for f, b, g in imp if not g["kill_passed"]]
    return {"n_implant_builds": len(imp), "tp": tp, "fp": fp, "fn": fn,
            "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
            "iou": _ratio(tp, tp + fp + fn),
            "n_survived": sum(1 for _, _, g in imp if g["survived"]),
            "kill_failed": failed, "kill_passed": not failed,
            "n_benign_builds": len(ben),
            "benign_flags_total": sum(len(r["flagged"]) for r in ben)}


# ---------------------------------------------------------------------------
# Report.
# ---------------------------------------------------------------------------
def _num(x):
    return "-" if x is None else "%.3f" % x


def print_report(builds, truth_only, summ):
    print("=== implant builds (kill: recall >= %s and FP <= %d x GT) ==="
          % (KILL_MIN_RECALL, KILL_MAX_FP_PER_GT))
    print("%-24s %-12s %6s %5s %4s %4s %4s %4s  %s"
          % ("experiment", "build", "win", "flag", "GT", "TP", "FP", "FN",
             "kill"))
    for folder, recs in builds.items():
        for build, r in recs.items():
            if r["class"] != "implant":
                continue
            g = r["gt"]
            print("%-24s %-12s %6d %5d %4d %4d %4d %4d  %s"
                  % (folder, build, r["windows_differing_all"],
                     len(r["flagged"]), len(g["tiles"]), g["tp"], g["fp"],
                     g["fn"], "PASS" if g["kill_passed"]
                     else "FAIL (%s)" % "; ".join(g["kill_reasons"])))

    print("\n=== benign builds (every flag is a false positive) ===")
    print("%-24s %-12s %6s %5s" % ("experiment", "build", "win", "flag"))
    for folder, recs in builds.items():
        for build, r in recs.items():
            if r["class"] == "benign":
                print("%-24s %-12s %6d %5d"
                      % (folder, build, r["windows_differing_all"],
                         len(r["flagged"])))

    if truth_only:
        print("\ntruth files without a bitstream: %s"
              % ", ".join("%s/%s" % (t["experiment"], t["build"])
                          for t in truth_only))

    print("\nimplant builds %d | TP %d FP %d FN %d | precision %s recall %s "
          "IoU %s | kill criterion: %s"
          % (summ["n_implant_builds"], summ["tp"], summ["fp"], summ["fn"],
             _num(summ["precision"]), _num(summ["recall"]),
             _num(summ["iou"]),
             "PASS" if summ["kill_passed"]
             else "FAIL: " + ", ".join(summ["kill_failed"])))


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Format-aware localization on the meson L3 builds, "
                    "scored against the build-time implant truth")
    p.add_argument("--artifacts", required=True,
                   help="the meson folder holding l3_slack, l3_width, ...")
    p.add_argument("--db", default=None,
                   help="prjxray-db folder (default: CURRENT in the cache)")
    p.add_argument("--out", default=OUT)
    args = p.parse_args()
    root = os.path.abspath(os.path.expanduser(args.artifacts))

    db_dir = os.path.abspath(args.db or default_db_dir())
    ft = FrameTypes.load(db_dir)
    problems = check_expected(ft)
    if problems:
        sys.exit("frame classes deviate from the expected pattern:\n  "
                 + "\n  ".join(problems))
    dec = TileDecoder.load(db_dir)
    by_site = site_tiles(os.path.join(db_dir, TILEGRID_JSON))

    db_inputs = {}
    for rel in [PART_YAML, TILEGRID_JSON] + sorted(
            os.path.relpath(q, db_dir) for q in
            glob.glob(os.path.join(db_dir, SEGBITS_DIR, "segbits_*.db"))):
        db_inputs[rel] = file_sha256(os.path.join(db_dir, rel))

    inputs, refs = {}, {}

    def ref_payload(rel):
        if rel not in refs:
            path = os.path.join(root, rel)
            if not os.path.exists(path):
                sys.exit("missing reference %s" % path)
            inputs[rel] = file_sha256(path)
            refs[rel] = fdri_payload_and_meta(path, ZYNQ7020_V4)[0]
        return refs[rel]

    builds, truth_only = {}, []
    for folder, ref_rel in EXPERIMENTS.items():
        if not os.path.isdir(os.path.join(root, folder)):
            sys.exit("missing experiment folder %s"
                     % os.path.join(root, folder))
        found = discover(root, folder, ref_rel)
        todo = found["implant"] + [(b, r, None) for b, r in found["benign"]]
        recs = {}
        for build, rel, truth_rel in todo:
            path = os.path.join(root, rel)
            try:
                design = check_reference(path, os.path.join(root, ref_rel))
            except ReferenceMismatch as e:
                sys.exit("reference guard: %s" % e)
            inputs[rel] = file_sha256(path)
            test = fdri_payload_and_meta(path, ZYNQ7020_V4)[0]
            rec = {"class": "implant" if truth_rel else "benign",
                   "bit": rel, "reference": ref_rel, "design": design,
                   "truth": truth_rel,
                   **compare_build(ref_payload(ref_rel), test, ft, dec),
                   "n_taps": None, "truth_header": None, "gt": None}
            if truth_rel:
                inputs[truth_rel] = file_sha256(os.path.join(root, truth_rel))
                header, implants = read_truth(os.path.join(root, truth_rel),
                                              build)
                rec.update(n_taps=n_taps(header), truth_header=header,
                           gt=gt_record(implants, rec["flagged"],
                                        rec["changed_tiles"], by_site))
            recs[build] = rec
            print("  %s/%s done" % (folder, build), file=sys.stderr)
        builds[folder] = recs
        for build, truth_rel in found["truth_without_bit"]:
            inputs[truth_rel] = file_sha256(os.path.join(root, truth_rel))
            header, implants = read_truth(os.path.join(root, truth_rel), build)
            truth_only.append({"experiment": folder, "build": build,
                               "truth": truth_rel, "n_taps": n_taps(header),
                               "truth_header": header,
                               "n_implants": len(implants)})

    summ = summarize(builds)
    print_report(builds, truth_only, summ)

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "part": "xc7z020clg400-1",
        "prjxray_db_sha": ft.db_sha,
        "prjxray_db_dir": db_dir,
        "artifacts_root": root,
        "experiments": EXPERIMENTS,
        "kill_criterion": {"min_recall": KILL_MIN_RECALL,
                           "max_fp_per_gt_tile": KILL_MAX_FP_PER_GT},
        "window_frames": WINDOW_FRAMES,
        "n_windows": ft.n_frames // WINDOW_FRAMES,
        "logic_minors": list(LOGIC_MINORS),
        "inputs": dict(sorted(inputs.items())),
        "prjxray_db_inputs": db_inputs,
        "builds": builds,
        "truth_without_bitstream": truth_only,
        "summary": summ,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print("-> %s" % args.out)


if __name__ == "__main__":
    main()
