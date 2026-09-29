# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Decode CLB tile features (LUT INITs, flip-flop and mux
#              settings) from a full Zynq-7020 bitstream using the pinned
#              prjxray-db, and compare two builds tile by tile.
#
#              Bit addressing. A tile's tilegrid entry gives
#              bits.CLB_IO_CLK.baseaddr and .offset. The tile owns words
#              offset and offset+1 of every frame in its column. A segbits
#              bit "MM_BB" is
#
#                  frame = far_map.frame(baseaddr + MM)
#                  word  = offset + BB // 32
#                  bit   = BB % 32 of that big-endian 32-bit word
#
#              so each minor gives the tile one 64-bit row
#              (word offset+1 << 32 | word offset), and BB indexes that row.
#              Word 50 of every frame is HCLK + ECC; no CLB tile owns it.
#
#              A feature is active iff all of its listed bits match ("!" =
#              must be 0). The 64 single-bit INIT[00..63] entries of each
#              LUT form its truth table (8 LUTs per tile: 2 slices x A-D).
#              Only real CLB tiles (CLBLL_L/R, CLBLM_L/R) are decoded, each
#              with its own segbits file.
#
#              `compare` decodes only tiles with a differing bit in the
#              site-owned minors (0-1, 26-35), classifies every LUT with
#              lut_canon.classify, diffs the other features, and flags a
#              tile when a LUT is new / removed / function_changed or any
#              FF.ZINI / FF.ZRST feature changed.
#
# Usage:
#   python3 tile_decode.py --ref A.bit --test B.bit [--db DIR]

import argparse
import collections
import json
import os
import re
from dataclasses import dataclass, field

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload_and_meta
from far_map import FarMap, default_db_dir
from frame_types import SEGBITS_DIR, TILEGRID_JSON
from lut_canon import CLASSES as LUT_CLASSES, classify

CLB_TILE_TYPES = ("CLBLL_L", "CLBLL_R", "CLBLM_L", "CLBLM_R")
WORDS_PER_TILE = 2
TILE_ROW_BITS = 32 * WORDS_PER_TILE
HCLK_WORD = 50
LOGIC_MINORS = (0, 1) + tuple(range(26, 36))
LUTS_PER_TILE = 8
LUT_BITS = 64

FLAG_LUT_CLASSES = ("new", "removed", "function_changed")
FLAG_FEATURE_KEYS = ("FF.ZINI", "FF.ZRST")

_LUT_INIT = re.compile(r"^(.+\.[A-D]LUT)\.INIT\[(\d+)\]$")


# ---------------------------------------------------------------------------
# prjxray-db readers.
# ---------------------------------------------------------------------------
@dataclass
class Segbits:
    tile_type: str
    luts: dict = field(default_factory=dict)      # {lut: {init idx: (m, b)}}
    features: dict = field(default_factory=dict)  # {name: ((m, b, want), ...)}

    def max_minor(self):
        minors = [m for bits in self.luts.values() for m, _ in bits.values()]
        minors += [m for bits in self.features.values() for m, _, _ in bits]
        return max(minors, default=-1)

    def check(self):
        """Problems (empty = OK): 8 LUTs, each with INIT[00..63]."""
        problems = []
        if len(self.luts) != LUTS_PER_TILE:
            problems.append("%d LUTs (expected %d): %s"
                            % (len(self.luts), LUTS_PER_TILE,
                               ", ".join(sorted(self.luts))))
        for name, bits in sorted(self.luts.items()):
            if sorted(bits) != list(range(LUT_BITS)):
                problems.append("%s has INIT bits %d..%d (%d of %d)"
                                % (name, min(bits), max(bits), len(bits),
                                   LUT_BITS))
        return problems


def parse_segbits(path, tile_type):
    """Segbits for one tile type; feature names lose the "<type>." prefix."""
    prefix = tile_type + "."
    seg = Segbits(tile_type)
    luts = collections.defaultdict(dict)
    with open(path) as fh:
        for lineno, line in enumerate(fh, 1):
            toks = line.split()
            if not toks:
                continue
            if not toks[0].startswith(prefix):
                raise ValueError("%s:%d: %r is not a %s feature"
                                 % (path, lineno, toks[0], tile_type))
            name = toks[0][len(prefix):]
            bits = []
            for tok in toks[1:]:
                m, sep, b = tok.lstrip("!").partition("_")
                if not (sep and m.isdigit() and b.isdigit()):
                    raise ValueError("%s:%d: malformed bit %r"
                                     % (path, lineno, tok))
                if int(b) >= TILE_ROW_BITS:
                    raise ValueError("%s:%d: bit %s is outside the tile's %d "
                                     "words" % (path, lineno, tok,
                                                WORDS_PER_TILE))
                bits.append((int(m), int(b), 0 if tok.startswith("!") else 1))
            lut = _LUT_INIT.match(name)
            if lut:
                idx = int(lut.group(2))
                if len(bits) != 1 or bits[0][2] != 1:
                    raise ValueError("%s:%d: %s is not one set bit"
                                     % (path, lineno, name))
                if idx in luts[lut.group(1)]:
                    raise ValueError("%s:%d: duplicate %s" % (path, lineno,
                                                              name))
                luts[lut.group(1)][idx] = bits[0][:2]
            else:
                if name in seg.features:
                    raise ValueError("%s:%d: duplicate %s" % (path, lineno,
                                                              name))
                seg.features[name] = tuple(bits)
    seg.luts = dict(luts)
    return seg


@dataclass(frozen=True)
class Tile:
    name: str
    tile_type: str
    baseaddr: int
    offset: int
    n_frames: int


def clb_tiles(tilegrid_path):
    """Every CLBLL_L/R, CLBLM_L/R tile in the tilegrid, sorted by name."""
    with open(tilegrid_path) as fh:
        grid = json.load(fh)
    out = []
    for name, t in grid.items():
        if t.get("type") not in CLB_TILE_TYPES:
            continue
        bits = t.get("bits", {}).get("CLB_IO_CLK")
        if not bits:
            raise ValueError("%s has no CLB_IO_CLK bits" % name)
        if int(bits.get("words", WORDS_PER_TILE)) != WORDS_PER_TILE:
            raise ValueError("%s owns %s words (expected %d)"
                             % (name, bits["words"], WORDS_PER_TILE))
        tile = Tile(name, t["type"], int(bits["baseaddr"], 16),
                    int(bits["offset"]), int(bits["frames"]))
        if tile.offset <= HCLK_WORD < tile.offset + WORDS_PER_TILE:
            raise ValueError("%s at word %d overlaps the HCLK/ECC word %d"
                             % (name, tile.offset, HCLK_WORD))
        out.append(tile)
    return sorted(out, key=lambda t: t.name)


# ---------------------------------------------------------------------------
# Decoding.
# ---------------------------------------------------------------------------
def payload_words(payload, n_frames, frame_words=ZYNQ7020_V4.frame_words):
    """FDRI payload bytes -> (n_frames, frame_words) big-endian uint32."""
    arr = np.frombuffer(np.ascontiguousarray(payload, dtype=np.uint8)
                        .tobytes(), dtype=">u4")
    if arr.size != n_frames * frame_words:
        raise ValueError("payload is %d words, expected %d frames x %d"
                         % (arr.size, n_frames, frame_words))
    return arr.reshape(n_frames, frame_words)


def tile_rows(words, frames, offset):
    """One 64-bit int per minor: bit BB = bit BB%32 of word offset+BB//32."""
    lo = words[frames, offset]
    hi = words[frames, offset + 1]
    return [int(a) | (int(b) << 32) for a, b in zip(lo, hi)]


def decode_tile(rows, seg):
    """({lut: INIT int}, frozenset of active feature names)."""
    def bit(m, b):
        return (rows[m] >> b) & 1
    luts = {name: sum(bit(m, b) << i for i, (m, b) in bits.items())
            for name, bits in seg.luts.items()}
    active = frozenset(name for name, bits in seg.features.items()
                       if all(bit(m, b) == want for m, b, want in bits))
    return luts, active


class TileDecoder:
    """Far map + CLB tiles + segbits per tile type."""

    def __init__(self, far_map, tiles, segbits):
        self.far_map = far_map
        self.tiles = list(tiles)
        self.segbits = segbits                 # {tile_type: Segbits}
        self._frames = {}
        for t in self.tiles:
            seg = segbits.get(t.tile_type)
            if seg is None:
                raise ValueError("no segbits for %s (%s)" % (t.tile_type,
                                                             t.name))
            if seg.max_minor() >= t.n_frames:
                raise ValueError("%s segbits reach minor %d but %s has %d "
                                 "frames" % (t.tile_type, seg.max_minor(),
                                             t.name, t.n_frames))
            self._frames[t.name] = [far_map.frame(t.baseaddr + m)
                                    for m in range(t.n_frames)]

    @property
    def db_sha(self):
        return self.far_map.db_sha

    @classmethod
    def load(cls, db_dir=None):
        db_dir = db_dir or default_db_dir()
        fm = FarMap.load(db_dir)
        grid = os.path.join(db_dir, TILEGRID_JSON)
        if not os.path.exists(grid):
            raise FileNotFoundError(grid)
        segbits = {}
        for t in CLB_TILE_TYPES:
            p = os.path.join(db_dir, SEGBITS_DIR, "segbits_%s.db" % t.lower())
            if not os.path.exists(p):
                raise FileNotFoundError(p)
            segbits[t] = parse_segbits(p, t)
            problems = segbits[t].check()
            if problems:
                raise ValueError("%s: %s" % (p, "; ".join(problems)))
        return cls(fm, clb_tiles(grid), segbits)

    def frames(self, tile):
        """Frame index of each minor of `tile`."""
        return self._frames[tile.name]

    def decode(self, words, tile):
        return decode_tile(tile_rows(words, self.frames(tile), tile.offset),
                           self.segbits[tile.tile_type])


# ---------------------------------------------------------------------------
# Compare two builds.
# ---------------------------------------------------------------------------
def _is_flag_feature(name):
    return any(k in name for k in FLAG_FEATURE_KEYS)


def compare_payloads(ref, test, dec, frame_words=ZYNQ7020_V4.frame_words):
    n = dec.far_map.n_frames
    a = payload_words(ref, n, frame_words)
    b = payload_words(test, n, frame_words)
    differs = a != b

    lut_counts = {c: 0 for c in LUT_CLASSES}
    changed, flagged = {}, {}
    for tile in dec.tiles:
        frames = dec.frames(tile)
        logic = [frames[m] for m in LOGIC_MINORS if m < len(frames)]
        if not differs[logic, tile.offset:tile.offset + WORDS_PER_TILE].any():
            continue
        luts_a, feat_a = dec.decode(a, tile)
        luts_b, feat_b = dec.decode(b, tile)
        classes = {lut: classify(luts_a[lut], luts_b[lut])
                   for lut in sorted(luts_a)}
        for c in classes.values():
            lut_counts[c] += 1
        gained, lost = sorted(feat_b - feat_a), sorted(feat_a - feat_b)
        changed[tile.name] = {"luts": classes, "features_gained": gained,
                              "features_lost": lost}
        reasons = ["%s %s" % (lut, c) for lut, c in classes.items()
                   if c in FLAG_LUT_CLASSES]
        reasons += ["+" + f for f in gained if _is_flag_feature(f)]
        reasons += ["-" + f for f in lost if _is_flag_feature(f)]
        if reasons:
            flagged[tile.name] = reasons
    return {
        "tiles_checked": len(dec.tiles),
        "logic_tiles_changed": len(changed),
        "lut_classes": lut_counts,
        "flagged": sorted(flagged),
        "flag_reasons": flagged,
        "changed_tiles": changed,
    }


def compare(ref_path, test_path, dec=None, profile=ZYNQ7020_V4):
    dec = dec or TileDecoder.load()
    ref, _ = fdri_payload_and_meta(ref_path, profile)
    test, _ = fdri_payload_and_meta(test_path, profile)
    return compare_payloads(ref, test, dec, frame_words=profile.frame_words)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Decode CLB tiles of two bitstreams and classify LUT "
                    "changes")
    p.add_argument("--ref", required=True)
    p.add_argument("--test", required=True)
    p.add_argument("--db", default=None,
                   help="prjxray-db folder (default: CURRENT in the cache)")
    args = p.parse_args()

    dec = TileDecoder.load(args.db)
    r = compare(args.ref, args.test, dec)
    print("=== CLB tile decode (prjxray-db %s) ===" % (dec.db_sha or "?"))
    print("ref : %s" % args.ref)
    print("test: %s" % args.test)
    print("logic tiles changed: %d / %d" % (r["logic_tiles_changed"],
                                            r["tiles_checked"]))
    print("\n=== LUT classes (changed tiles only) ===")
    for c, n in r["lut_classes"].items():
        print("  %-21s %6d" % (c, n))
    print("\n=== flagged tiles: %d ===" % len(r["flagged"]))
    for name in r["flagged"]:
        print("  %s: %s" % (name, "; ".join(r["flag_reasons"][name])))


if __name__ == "__main__":
    main()
