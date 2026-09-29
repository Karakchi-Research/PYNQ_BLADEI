# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Independent re-check of l3f_format_aware_results.json.
#
#              Imports NONE of far_map, frame_types, tile_decode, lut_canon,
#              bitstream_io, l3_format_aware_eval or l3f_format_aware_eval.
#              The payload walk, part.yaml frame order and tile-word test
#              come from verify_format_aware.py, which has no import-time
#              side effects and is itself independent of those modules.
#              Everything else is re-derived here:
#
#                truth files   own regex parser (header keys, IMPLANT lines,
#                              roles from the cell prefix, Tcl-list taps)
#                site -> tile  tilegrid.json "sites", read directly
#                logic frames  tilegrid tile types: column minors 26-35 of
#                              CLB columns, 26-27 of BRAM/DSP columns
#                changed tiles every CLB tile with a differing word in its
#                              logic minors 0-1, 26-35, from the raw frames
#
#              Checks, all paths read from the results file:
#                - every recorded SHA-256 (bitstreams, truth files, db files)
#                - build classes re-discovered from the folders
#                - reference guard (file size, .bit header design name)
#                - raw differing windows, all and logic-only
#                - changed-tile set
#                - flag spot-checks: every flagged tile is a CLB tile with a
#                  differing logic word
#                - truth header, implants, n_taps, GT tiles and roles
#                - TP/FP/FN, precision, recall, IoU, survival, kill verdict
#                - the summary line
#              PASS/FAIL per build; exit status is nonzero on any FAIL.
#
# Usage:
#   python3 verify_l3f_format_aware.py [--results PATH]

import argparse
import glob
import json
import os
import re
import struct
import sys

import numpy as np

from verify_format_aware import (CLB_TYPES, FRAME_WORDS, PART_YAML, TILEGRID,
                                 WINDOW, frame_counts, frame_of_far,
                                 logic_differs, read_fdri, sha256_of)

RESULTS = os.path.join("localization_corpus", "format_aware",
                       "l3f_format_aware_results.json")

KILL_MIN_RECALL = 1.0
KILL_MAX_FP_PER_GT = 2

LOGIC_BY_TYPE = {**{t: range(26, 36) for t in CLB_TYPES},
                 **{t: range(26, 28) for t in ("BRAM_L", "BRAM_R",
                                                "DSP_L", "DSP_R")}}
TRUTH_GLOB = os.path.join("reports", "*_implant_truth.txt")
KEYS = {"tag", "region", "style", "n_cells", "clock_net", "tap_net",
        "trigger_taps", "payload_victim"}
ROLE_OF = {"ftrig": "trigger", "farm": "arming", "fpay": "payload",
           "implant": "tied"}

_HEADER = re.compile(r"^(\w+):(.*)$")
_IMPLANT = re.compile(r"^IMPLANT (bladei_(ftrig|farm|fpay|implant)_\S+) "
                      r"(SLICE_X\d+Y\d+)$")
_TCL_ITEM = re.compile(r"\{([^{}]*)\}(?=\s|$)|([^\s{}]+)")


# ---------------------------------------------------------------------------
# Truth files.
# ---------------------------------------------------------------------------
def read_truth(path):
    """(header, [(cell, site, role)])."""
    header, implants = {}, []
    with open(path) as fh:
        lines = fh.read().splitlines()
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        m = _IMPLANT.match(line.strip())
        if m:
            implants.append((m.group(1), m.group(3), ROLE_OF[m.group(2)]))
            continue
        h = _HEADER.match(line)
        if h and h.group(1) in KEYS and h.group(1) not in header:
            header[h.group(1)] = h.group(2).strip()
            continue
        raise ValueError("%s:%d: unrecognised line %r" % (path, n, line))
    return header, implants


def count_taps(header):
    s = header.get("trigger_taps", "")
    if _TCL_ITEM.sub("", s).strip():
        raise ValueError("trigger_taps is not a flat Tcl list: %r" % s)
    k = len(_TCL_ITEM.findall(s))
    if k:
        return k
    return 1 if header.get("tap_net", "") else 0


# ---------------------------------------------------------------------------
# Device data.
# ---------------------------------------------------------------------------
def load_grid(path):
    """({CLB tile: (base, offset, frames)}, {SLICE: (tile, type)},
    {FAR of every logic frame})."""
    with open(path) as fh:
        grid = json.load(fh)
    tiles, sites, logic_fars = {}, {}, set()
    for name, t in grid.items():
        ttype = t.get("type")
        for s in t.get("sites", {}):
            if s.startswith("SLICE_"):
                sites[s] = (name, ttype)
        bits = t.get("bits", {}).get("CLB_IO_CLK")
        if not bits:
            continue
        base, frames = int(bits["baseaddr"], 16), int(bits["frames"])
        if ttype in CLB_TYPES:
            tiles[name] = (base, int(bits["offset"]), frames)
        if ttype in LOGIC_BY_TYPE:
            # Logic minors count from the column's minor 0, not the tile's.
            column = base & ~0x7F
            logic_fars.update(column | m for m in LOGIC_BY_TYPE[ttype]
                              if m < (base & 0x7F) + frames)
    return tiles, sites, logic_fars


def design_name(path):
    """.bit header field 'a' up to ';' (walks the tagged fields)."""
    with open(path, "rb") as fh:
        head = fh.read(4096)
    off = 2 + struct.unpack_from(">H", head, 0)[0] + 2
    while off < len(head):
        tag = head[off:off + 1]
        n = struct.unpack_from(">H", head, off + 1)[0]
        if tag == b"a":
            return head[off + 3:off + 3 + n].split(b"\x00")[0] \
                .decode("latin1").split(";")[0]
        off += 3 + n
    raise ValueError("%s: no design field" % path)


def _ratio(num, den):
    return num / den if den else None


def _same(a, b):
    if a is None or b is None:
        return a is b
    return abs(a - b) < 1e-12


# ---------------------------------------------------------------------------
# Per-build check.
# ---------------------------------------------------------------------------
class Checker:
    def __init__(self, root, far_frame, n_frames, tiles, sites, logic_mask):
        self.root = root
        self.far_frame = far_frame
        self.n_frames = n_frames
        self.tiles = tiles
        self.sites = sites
        self.logic_mask = logic_mask
        self._frames = {}

    def frames(self, rel):
        """(n_frames, 101) words of a bitstream, with any load problems."""
        if rel not in self._frames:
            payload, far = read_fdri(os.path.join(self.root, rel))
            errs = []
            if far != 0:
                errs.append("%s: FDRI starts at FAR %r, not 0" % (rel, far))
            if payload.size != self.n_frames * FRAME_WORDS:
                errs.append("%s: %d payload words" % (rel, payload.size))
                self._frames[rel] = (None, errs)
            else:
                self._frames[rel] = (payload.reshape(self.n_frames,
                                                     FRAME_WORDS), errs)
        return self._frames[rel]

    def check(self, rec):
        """(problems, summary line, recomputed (tp, fp, fn) or None,
        recomputed kill verdict or None)."""
        root, bad = self.root, []
        ref, errs = self.frames(rec["reference"])
        bad += errs
        test, errs = self.frames(rec["bit"])
        bad += errs
        if ref is None or test is None:
            return bad, "", None, None

        bp, rp = os.path.join(root, rec["bit"]), os.path.join(root,
                                                              rec["reference"])
        if os.path.getsize(bp) != os.path.getsize(rp):
            bad.append("guard: size differs from %s" % rec["reference"])
        if design_name(bp) != design_name(rp):
            bad.append("guard: design name differs from %s"
                       % rec["reference"])
        elif design_name(bp) != rec["design"]:
            bad.append("design %r recorded as %r" % (design_name(bp),
                                                     rec["design"]))

        differs = ref != test
        frame_diff = differs.any(axis=1)
        w_all = np.flatnonzero(frame_diff.reshape(-1, WINDOW).any(axis=1))
        w_log = np.flatnonzero((frame_diff & self.logic_mask)
                               .reshape(-1, WINDOW).any(axis=1))
        if w_all.tolist() != rec["differing_windows_all"] \
                or len(w_all) != rec["windows_differing_all"]:
            bad.append("windows (all): %d recomputed vs %d recorded"
                       % (len(w_all), rec["windows_differing_all"]))
        if w_log.tolist() != rec["differing_windows_logic_only"] \
                or len(w_log) != rec["windows_differing_logic_only"]:
            bad.append("windows (logic): %d recomputed vs %d recorded"
                       % (len(w_log), rec["windows_differing_logic_only"]))

        changed = {name for name, t in self.tiles.items()
                   if logic_differs(differs, self.far_frame, t)}
        if sorted(changed) != rec["changed_tiles"]:
            bad.append("changed tiles: %d recomputed vs %d recorded "
                       "(only here: %s; only recorded: %s)"
                       % (len(changed), len(rec["changed_tiles"]),
                          sorted(changed - set(rec["changed_tiles"]))[:5],
                          sorted(set(rec["changed_tiles"]) - changed)[:5]))
        flagged = rec["flagged"]
        for name in flagged:
            if name not in self.tiles:
                bad.append("flagged %s is not a CLB tile" % name)
            elif name not in changed:
                bad.append("flagged %s has no differing logic word" % name)
        line = "win %d/%d  changed %d  flagged %d" % (
            len(w_all), len(w_log), len(changed), len(flagged))

        if rec["class"] == "benign":
            return bad, line, (0, len(flagged), 0), None
        return self.check_gt(rec, flagged, changed, bad, line)

    def check_gt(self, rec, flagged, changed, bad, line):
        header, implants = read_truth(os.path.join(self.root, rec["truth"]))
        if header != rec["truth_header"]:
            bad.append("truth header differs from recorded")
        if count_taps(header) != rec["n_taps"]:
            bad.append("n_taps %d recomputed vs %s recorded"
                       % (count_taps(header), rec["n_taps"]))
        g = rec["gt"]
        if implants != [(i["cell"], i["site"], i["role"])
                        for i in g["implants"]]:
            bad.append("implant lines differ from recorded")

        gt, roles, unmapped = set(), {}, []
        for cell, site, role in implants:
            hit = self.sites.get(site)
            if hit is None or hit[1] not in CLB_TYPES:
                unmapped.append(site)
                continue
            gt.add(hit[0])
            roles.setdefault(hit[0], set()).add(role)
        roles = {t: sorted(r) for t, r in roles.items()}
        if sorted(gt) != g["tiles"]:
            bad.append("GT tiles %s recomputed vs %s recorded"
                       % (sorted(gt), g["tiles"]))
        if roles != g["tile_roles"]:
            bad.append("GT tile roles differ from recorded")
        if unmapped != g["sites_unmapped"]:
            bad.append("unmapped sites %s vs %s" % (unmapped,
                                                    g["sites_unmapped"]))

        f = set(flagged)
        tp, fp, fn = len(f & gt), len(f - gt), len(gt - f)
        mine = {"tp": tp, "fp": fp, "fn": fn,
                "precision": _ratio(tp, len(f)), "recall": _ratio(tp, len(gt)),
                "iou": _ratio(tp, len(f | gt)), "survived": gt <= changed}
        for k in ("tp", "fp", "fn", "survived"):
            if mine[k] != g[k]:
                bad.append("%s %s recomputed vs %s recorded"
                           % (k, mine[k], g[k]))
        for k in ("precision", "recall", "iou"):
            if not _same(mine[k], g[k]):
                bad.append("%s %s recomputed vs %s recorded"
                           % (k, mine[k], g[k]))
        kill = (mine["recall"] is not None
                and mine["recall"] >= KILL_MIN_RECALL
                and fp <= KILL_MAX_FP_PER_GT * len(gt))
        if kill != g["kill_passed"]:
            bad.append("kill %s recomputed vs %s recorded"
                       % ("PASS" if kill else "FAIL",
                          "PASS" if g["kill_passed"] else "FAIL"))
        line += "  gt %d  TP %d FP %d FN %d  kill %s" % (
            len(gt), tp, fp, fn, "PASS" if kill else "FAIL")
        return bad, line, (tp, fp, fn), kill


# ---------------------------------------------------------------------------
# Discovery.
# ---------------------------------------------------------------------------
def classes_on_disk(root, folder, ref_rel):
    """{build: "implant" | "benign" | "truth_without_bit"}."""
    d = os.path.join(root, folder)
    ref = os.path.normpath(ref_rel)
    bits = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(d, "*.bit"))
            if os.path.normpath(os.path.relpath(p, root)) != ref}
    truths = {os.path.basename(p)[:-len("_implant_truth.txt")]
              for p in glob.glob(os.path.join(d, TRUTH_GLOB))}
    out = {b: "implant" if b in truths else "benign" for b in bits}
    out.update({b: "truth_without_bit" for b in truths - bits})
    return out


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Independently verify l3f_format_aware_results.json")
    p.add_argument("--results", default=RESULTS)
    args = p.parse_args()
    with open(args.results) as fh:
        res = json.load(fh)
    root, db = res["artifacts_root"], res["prjxray_db_dir"]

    fatal = []
    kc = res["kill_criterion"]
    if (kc["min_recall"], kc["max_fp_per_gt_tile"]) != (KILL_MIN_RECALL,
                                                        KILL_MAX_FP_PER_GT):
        fatal.append("kill criterion %s differs from %s / %s"
                     % (kc, KILL_MIN_RECALL, KILL_MAX_FP_PER_GT))
    for rel, want in res["prjxray_db_inputs"].items():
        if sha256_of(os.path.join(db, rel)) != want:
            fatal.append("prjxray-db %s: SHA-256 mismatch" % rel)
    for rel, want in res["inputs"].items():
        if sha256_of(os.path.join(root, rel)) != want:
            fatal.append("%s: SHA-256 mismatch" % rel)
    print("=== independent check of %s ===" % args.results)
    print("SHA-256: %d artifact inputs, %d prjxray-db files"
          % (len(res["inputs"]), len(res["prjxray_db_inputs"])))

    far_frame, n_frames = frame_of_far(
        frame_counts(os.path.join(db, PART_YAML)))
    if n_frames % WINDOW:
        sys.exit("FAIL: %d frames is not whole %d-frame windows"
                 % (n_frames, WINDOW))
    tiles, sites, logic_fars = load_grid(os.path.join(db, TILEGRID))
    logic_mask = np.zeros(n_frames, dtype=bool)
    for far in logic_fars:
        if far not in far_frame:
            fatal.append("logic FAR 0x%08x has no frame" % far)
        else:
            logic_mask[far_frame[far]] = True
    print("%d frames | %d CLB tiles | %d logic frames"
          % (n_frames, len(tiles), int(logic_mask.sum())))

    truth_only = {(t["experiment"], t["build"])
                  for t in res["truth_without_bitstream"]}
    for folder, ref_rel in res["experiments"].items():
        disk = classes_on_disk(root, folder, ref_rel)
        recorded = {b: r["class"] for b, r in
                    res["builds"].get(folder, {}).items()}
        recorded.update({b: "truth_without_bit" for f, b in truth_only
                         if f == folder})
        if disk != recorded:
            fatal.append("%s: build classes on disk %s vs recorded %s"
                         % (folder, disk, recorded))
    for t in res["truth_without_bitstream"]:
        header, implants = read_truth(os.path.join(root, t["truth"]))
        if header != t["truth_header"] or len(implants) != t["n_implants"] \
                or count_taps(header) != t["n_taps"]:
            fatal.append("truth-only %s/%s differs from recorded"
                         % (t["experiment"], t["build"]))

    chk = Checker(root, far_frame, n_frames, tiles, sites, logic_mask)
    n_pass = n_total = 0
    tot = [0, 0, 0]
    kill_failed, n_implant = [], 0
    for folder, recs in res["builds"].items():
        for build, rec in recs.items():
            n_total += 1
            try:
                bad, line, counts, kill = chk.check(rec)
            except (ValueError, KeyError, OSError) as e:
                bad, line, counts, kill = ["error: %s" % e], "", None, None
            if rec["class"] == "implant":
                n_implant += 1
                if counts:
                    tot = [a + b for a, b in zip(tot, counts)]
                if kill is not True:
                    kill_failed.append("%s/%s" % (folder, build))
            ok = not bad
            n_pass += ok
            print("  %-24s %-12s %s  %s" % (folder, build,
                                           "PASS" if ok else "FAIL", line))
            for pr in bad:
                print("      %s" % pr)

    s = res["summary"]
    tp, fp, fn = tot
    mine = {"n_implant_builds": n_implant, "tp": tp, "fp": fp, "fn": fn,
            "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
            "iou": _ratio(tp, tp + fp + fn), "kill_failed": kill_failed,
            "kill_passed": not kill_failed}
    for k, v in mine.items():
        same = _same(v, s[k]) if k in ("precision", "recall", "iou") \
            else v == s[k]
        if not same:
            fatal.append("summary %s: %s recomputed vs %s recorded"
                         % (k, v, s[k]))

    for pr in fatal:
        print("  FAIL %s" % pr)
    print("%d/%d builds PASS | summary %s | kill criterion recomputed: %s"
          % (n_pass, n_total, "OK" if not fatal else "FAIL",
             "PASS" if not kill_failed else "FAIL: " + ", ".join(kill_failed)))
    if fatal or n_pass != n_total:
        sys.exit(1)


if __name__ == "__main__":
    main()
