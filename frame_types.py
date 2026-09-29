# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Classify every configuration frame of a full Zynq-7020
#              bitstream as routing / logic / mixed / BRAM content, and diff
#              two bitstreams by class.
#
#              far_map gives every FDRI frame its (column, minor). What that
#              minor CONFIGURES is read off the pinned prjxray-db, not
#              assumed:
#
#                - tilegrid.json lists the tiles attached to each
#                  configuration column (same CLB_IO_CLK baseaddr).
#                - each tile type's segbits_<type>.db lists every bit it owns
#                  as "<feature> [!]<minor>_<bit> ...", so the set of minors
#                  a tile type touches is read straight from the file.
#
#              Per column, a minor touched only by routing tiles (INT_L,
#              INT_R, HCLK_*) is ROUTING, only by site tiles (CLB, BRAM,
#              DSP, ...) is LOGIC, by both is MIXED. Every BLOCK_RAM-bus
#              frame (block type 1) is BRAM CONTENT; pad frames are PAD.
#
#              A tile type with no segbits file contributes NO evidence (it
#              is listed in `missing_segbits`). Fallback (reported, never
#              silent): only a minor that gets no segbits evidence from any
#              tile in its column is labelled by threshold, <= 25 routing and
#              >= 26 logic; every such column is listed in `fallback`.
#
#              Expected on this part (asserted by `check_expected`):
#                CLB columns (36):      0-1 mixed, 2-25 routing, 26-35 logic
#                BRAM/DSP columns (28): 0-25 routing, 26-27 logic
#
#              `typed_diff` counts differing frames per class and differing
#              8-frame windows twice: over all frames, and over LOGIC-ONLY
#              frames (CLB minors 26-35 + BRAM/DSP minors 26-27; the mixed
#              minors 0-1 are excluded).
#
# Usage:
#   python3 frame_types.py --ref A.bit --test B.bit [--db DIR]

import argparse
import collections
import json
import os
import sys
from dataclasses import dataclass, field

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload_and_meta
from far_map import FarMap, decode_far, default_db_dir
from l2_localization_eval import WINDOW_FRAMES

TILEGRID_JSON = "zynq7/xc7z020/tilegrid.json"
SEGBITS_DIR = "zynq7"

ROUTING, LOGIC, MIXED, BRAM_CONTENT, PAD = range(5)
CLASSES = ("routing", "logic", "mixed", "bram_content", "pad")

ROUTING_TILE_TYPES = ("INT_L", "INT_R")
ROUTING_TILE_PREFIXES = ("HCLK_",)
FALLBACK_LAST_ROUTING_MINOR = 25

# Column kinds whose LOGIC frames enter the logic-only window count.
LOGIC_WINDOW_KINDS = ("CLB", "BRAM", "DSP")

# Reporting groups for per-kind diff counts. BLOCK_RAM-bus content columns
# report under BRAM/DSP; pad frames (no column) under other.
GROUPS = ("CLB", "BRAM/DSP", "IO", "other")
_GROUP_OF_KIND = {"CLB": 0, "BRAM": 1, "DSP": 1, "BRAM_CONTENT": 1, "IO": 2}
OTHER_GROUP = 3

EXPECTED = {
    "CLB": [MIXED] * 2 + [ROUTING] * 24 + [LOGIC] * 10,
    "BRAM": [ROUTING] * 26 + [LOGIC] * 2,
    "DSP": [ROUTING] * 26 + [LOGIC] * 2,
}


# ---------------------------------------------------------------------------
# prjxray-db readers.
# ---------------------------------------------------------------------------
def segbits_minors(path):
    """Set of minors used by a segbits file. "!" (bit must be 0) still
    counts as use: the bit lives in that minor either way."""
    minors = set()
    with open(path) as fh:
        for lineno, line in enumerate(fh, 1):
            for tok in line.split()[1:]:
                m, sep, b = tok.lstrip("!").partition("_")
                if not (sep and m.isdigit() and b.isdigit()):
                    raise ValueError("%s:%d: malformed bit %r"
                                     % (path, lineno, tok))
                minors.add(int(m))
    return minors


def column_tiles(tilegrid_path):
    """{baseaddr: {(tile_type, frames)}} over CLB_IO_CLK bits."""
    with open(tilegrid_path) as fh:
        grid = json.load(fh)
    out = collections.defaultdict(set)
    for tile in grid.values():
        bits = tile.get("bits", {}).get("CLB_IO_CLK")
        if bits:
            out[int(bits["baseaddr"], 16)].add((tile["type"],
                                                int(bits["frames"])))
    return dict(out)


def column_kind(tile_types):
    if any(t.startswith("CLBL") for t in tile_types):
        return "CLB"
    if any(t in ("BRAM_L", "BRAM_R") for t in tile_types):
        return "BRAM"
    if any(t in ("DSP_L", "DSP_R") for t in tile_types):
        return "DSP"
    if any("IOB" in t or "IOI" in t for t in tile_types):
        return "IO"
    return "OTHER"


def is_routing_tile(tile_type):
    return (tile_type in ROUTING_TILE_TYPES
            or tile_type.startswith(ROUTING_TILE_PREFIXES))


def _threshold(minor):
    return ROUTING if minor <= FALLBACK_LAST_ROUTING_MINOR else LOGIC


# ---------------------------------------------------------------------------
# The classification.
# ---------------------------------------------------------------------------
@dataclass
class Column:
    block_type: int
    half: int
    row: int
    column: int
    first_frame: int
    n_minors: int
    kind: str = "OTHER"
    tile_types: tuple = ()
    classes: list = field(default_factory=list)   # one code per minor

    @property
    def key(self):
        return (self.block_type, self.half, self.row, self.column)

    def name(self):
        return "blk%d %s row%d col%d" % (self.block_type,
                                         ("top", "bottom")[self.half],
                                         self.row, self.column)


def _columns_from_map(fm):
    """Columns in FDRI order; each column's minors are contiguous frames."""
    cols = {}
    for i in range(fm.n_frames):
        if fm.is_pad(i):
            continue
        f = decode_far(fm.far(i))
        key = (f.block_type, f.half, f.row, f.column)
        if key not in cols:
            if f.minor != 0:
                raise ValueError("column %s does not start at minor 0" % (key,))
            cols[key] = Column(*key, first_frame=i, n_minors=0)
        c = cols[key]
        if i != c.first_frame + f.minor:
            raise ValueError("column %s is not contiguous at frame %d"
                             % (key, i))
        c.n_minors = f.minor + 1
    return cols


class FrameTypes:
    """Per-frame class codes plus the evidence behind them."""

    def __init__(self, far_map, columns, fallback, orphan_baseaddrs,
                 missing_segbits=None, db_dir=None):
        self.far_map = far_map
        self.columns = columns                 # {key: Column}
        self.fallback = fallback               # {key: [reason, ...]}
        self.orphan_baseaddrs = orphan_baseaddrs
        self.missing_segbits = missing_segbits or {}   # {tile_type: n_cols}
        self.db_dir = db_dir
        n = far_map.n_frames
        self.codes = np.full(n, PAD, dtype=np.uint8)
        self.groups = np.full(n, OTHER_GROUP, dtype=np.uint8)
        self.logic_mask = np.zeros(n, dtype=bool)
        for c in columns.values():
            span = slice(c.first_frame, c.first_frame + c.n_minors)
            self.codes[span] = c.classes
            self.groups[span] = _GROUP_OF_KIND.get(c.kind, OTHER_GROUP)
            if c.kind in LOGIC_WINDOW_KINDS:
                self.logic_mask[span] = np.asarray(c.classes) == LOGIC

    @property
    def n_frames(self):
        return self.far_map.n_frames

    @property
    def db_sha(self):
        return self.far_map.db_sha

    @classmethod
    def load(cls, db_dir=None):
        db_dir = db_dir or default_db_dir()
        fm = FarMap.load(db_dir)
        path = os.path.join(db_dir, TILEGRID_JSON)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        return cls.derive(fm, column_tiles(path),
                          os.path.join(db_dir, SEGBITS_DIR), db_dir=db_dir)

    @classmethod
    def derive(cls, fm, tiles_by_baseaddr, segbits_dir, db_dir=None):
        columns = _columns_from_map(fm)
        segbits = {}

        def minors_of(tile_type):
            if tile_type not in segbits:
                p = os.path.join(segbits_dir,
                                 "segbits_%s.db" % tile_type.lower())
                segbits[tile_type] = segbits_minors(p) \
                    if os.path.exists(p) else None
            return segbits[tile_type]

        # Attach tiles to columns.
        attached = collections.defaultdict(set)
        orphans = []
        for base, tiles in tiles_by_baseaddr.items():
            f = decode_far(base)
            key = (f.block_type, f.half, f.row, f.column)
            if key not in columns or f.block_type != 0:
                orphans.append(base)
                continue
            attached[key] |= {(t, f.minor, n) for t, n in tiles}

        fallback = {}
        missing_segbits = collections.Counter()
        for key, c in columns.items():
            if c.block_type == 1:
                c.kind = "BRAM_CONTENT"
                c.classes = [BRAM_CONTENT] * c.n_minors
                continue
            routing_ev, site_ev, reasons = set(), set(), []
            c.tile_types = tuple(sorted({t for t, _, _ in
                                         attached.get(key, ())}))
            c.kind = column_kind(c.tile_types)
            missing_segbits.update(t for t in c.tile_types
                                   if minors_of(t) is None)
            for t, base_minor, _ in sorted(attached.get(key, ())):
                used = minors_of(t)
                if used is None:
                    continue                   # no file: no evidence
                is_routing = is_routing_tile(t)
                for m in used:
                    m += base_minor
                    if m >= c.n_minors:
                        raise ValueError("%s minor %d outside %s (%d minors)"
                                         % (t, m, c.name(), c.n_minors))
                    (routing_ev if is_routing else site_ev).add(m)
            uncovered = []
            for m in range(c.n_minors):
                r, s = m in routing_ev, m in site_ev
                if r and s:
                    c.classes.append(MIXED)
                elif r:
                    c.classes.append(ROUTING)
                elif s:
                    c.classes.append(LOGIC)
                else:
                    c.classes.append(_threshold(m))
                    uncovered.append(m)
            if not c.tile_types:
                reasons.append("no tiles in tilegrid")
            elif uncovered:
                reasons.append("no evidence for minors %s"
                               % _ranges(uncovered))
            if reasons:
                fallback[key] = reasons
        return cls(fm, columns, fallback, sorted(orphans),
                   missing_segbits=dict(missing_segbits), db_dir=db_dir)

    def frame_counts(self):
        """{class name: number of frames}."""
        n = np.bincount(self.codes, minlength=len(CLASSES))
        return {name: int(n[i]) for i, name in enumerate(CLASSES)}

    def kind_counts(self):
        return dict(collections.Counter(c.kind for c in self.columns.values()))


def _ranges(xs):
    xs, out = sorted(xs), []
    for x in xs:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return ",".join("%d" % a if a == b else "%d-%d" % (a, b) for a, b in out)


def check_expected(ft):
    """Problems (empty list = pass) against the expected CLB/BRAM/DSP class
    patterns, plus any tilegrid baseaddr that is not a column of the map."""
    problems = []
    seen = collections.Counter()
    for c in ft.columns.values():
        want = EXPECTED.get(c.kind)
        if want is None:
            continue
        seen[c.kind] += 1
        if c.classes != want:
            problems.append("%s (%s): %s" % (c.name(), c.kind,
                                             describe(c.classes)))
    for kind in EXPECTED:
        if not seen[kind]:
            problems.append("no %s columns found" % kind)
    if ft.orphan_baseaddrs:
        problems.append("%d tilegrid baseaddrs are not columns of the map: %s"
                        % (len(ft.orphan_baseaddrs),
                           ", ".join("0x%08x" % b
                                     for b in ft.orphan_baseaddrs[:5])))
    return problems


def describe(classes):
    """'0-1 mixed, 2-25 routing, 26-35 logic' for a per-minor class list."""
    runs = []
    for m, code in enumerate(classes):
        if runs and runs[-1][2] == code:
            runs[-1][1] = m
        else:
            runs.append([m, m, code])
    return ", ".join(("%d" % a if a == b else "%d-%d" % (a, b))
                     + " " + CLASSES[code] for a, b, code in runs)


# ---------------------------------------------------------------------------
# Typed diff.
# ---------------------------------------------------------------------------
def diff_payloads(ref, test, ft, frame_bytes=ZYNQ7020_V4.frame_bytes):
    """Differing frames per class and differing 8-frame windows (all frames /
    logic-only) between two FDRI payloads."""
    n = ft.n_frames
    for name, arr in (("ref", ref), ("test", test)):
        if len(arr) != n * frame_bytes:
            raise ValueError("%s payload is %d bytes, expected %d frames x %d"
                             % (name, len(arr), n, frame_bytes))
    if n % WINDOW_FRAMES:
        raise ValueError("%d frames is not whole %d-frame windows"
                         % (n, WINDOW_FRAMES))
    differs = np.any(np.asarray(ref).reshape(n, frame_bytes)
                     != np.asarray(test).reshape(n, frame_bytes), axis=1)
    per_class = np.bincount(ft.codes[differs], minlength=len(CLASSES))
    cells = np.bincount(ft.groups[differs].astype(np.int64) * len(CLASSES)
                        + ft.codes[differs],
                        minlength=len(GROUPS) * len(CLASSES)
                        ).reshape(len(GROUPS), len(CLASSES))

    n_win = n // WINDOW_FRAMES
    win_all = differs.reshape(n_win, WINDOW_FRAMES).any(axis=1)
    win_logic = (differs & ft.logic_mask).reshape(n_win,
                                                  WINDOW_FRAMES).any(axis=1)
    return {
        "n_frames": n,
        "n_windows": n_win,
        "frames_differing": int(differs.sum()),
        "frames_differing_by_class": {name: int(per_class[i])
                                      for i, name in enumerate(CLASSES)},
        "frames_differing_by_kind_class": {
            g: {name: int(cells[gi, ci]) for ci, name in enumerate(CLASSES)}
            for gi, g in enumerate(GROUPS)},
        "windows_differing_all": int(win_all.sum()),
        "windows_differing_logic_only": int(win_logic.sum()),
        "differing_windows_all": np.flatnonzero(win_all).tolist(),
        "differing_windows_logic_only": np.flatnonzero(win_logic).tolist(),
    }


def typed_diff(ref_path, test_path, ft=None, profile=ZYNQ7020_V4):
    ft = ft or FrameTypes.load()
    ref, _ = fdri_payload_and_meta(ref_path, profile)
    test, _ = fdri_payload_and_meta(test_path, profile)
    return diff_payloads(ref, test, ft, frame_bytes=profile.frame_bytes)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Classify configuration frames and diff two bitstreams "
                    "by class")
    p.add_argument("--ref", required=True)
    p.add_argument("--test", required=True)
    p.add_argument("--db", default=None,
                   help="prjxray-db folder (default: CURRENT in the cache)")
    args = p.parse_args()

    ft = FrameTypes.load(args.db)
    print("=== frame classes (prjxray-db %s) ===" % (ft.db_sha or "?"))
    for name, n in ft.frame_counts().items():
        print("  %-13s %5d frames" % (name, n))
    print("  logic-only    %5d frames (window mask)" % int(ft.logic_mask.sum()))
    print("  columns by kind: %s" % ", ".join(
        "%s=%d" % kv for kv in sorted(ft.kind_counts().items())))

    by_reason = collections.defaultdict(list)
    for key, reasons in ft.fallback.items():
        by_reason["; ".join(reasons)].append(ft.columns[key].name())
    print("\n=== tile types without segbits (no evidence) ===")
    for t, n in sorted(ft.missing_segbits.items()):
        print("  %-24s in %3d columns" % (t, n))
    print("\n=== fallback: %d columns ===" % len(ft.fallback))
    for reason, names in sorted(by_reason.items()):
        print("  %3d x %s" % (len(names), reason))
        for nm in sorted(names):
            print("        %s" % nm)

    problems = check_expected(ft)
    print("\n=== expected CLB/BRAM/DSP patterns: %s ==="
          % ("OK" if not problems else "%d PROBLEMS" % len(problems)))
    for pr in problems:
        print("  " + pr)

    r = typed_diff(args.ref, args.test, ft)
    print("\n=== typed diff ===")
    print("ref : %s" % args.ref)
    print("test: %s" % args.test)
    print("frames differing: %d / %d" % (r["frames_differing"],
                                         r["n_frames"]))
    print("  %-9s" % "kind" + "".join("%13s" % c for c in CLASSES)
          + "%9s" % "total")
    for g, row in r["frames_differing_by_kind_class"].items():
        print("  %-9s" % g + "".join("%13d" % row[c] for c in CLASSES)
              + "%9d" % sum(row.values()))
    print("  %-9s" % "total" + "".join(
        "%13d" % r["frames_differing_by_class"][c] for c in CLASSES)
        + "%9d" % r["frames_differing"])
    print("%d-frame windows differing: all %d / %d | logic-only %d / %d"
          % (WINDOW_FRAMES, r["windows_differing_all"], r["n_windows"],
             r["windows_differing_logic_only"], r["n_windows"]))
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
