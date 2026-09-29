# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Frame index <-> frame address (FAR) map for full Zynq-7020
#              bitstreams, derived from the pinned prjxray-db part.yaml.
#
#              A full bitstream writes the FAR once (0x00000000) and then
#              streams every frame through FDRI, letting the device
#              auto-increment the address. Frame i of the FDRI payload
#              therefore has an IMPLIED FAR, fixed by the device's column
#              layout and nothing else. The increment order, most- to
#              least-significant, is:
#
#                  block type (0=CLB_IO_CLK, 1=BLOCK_RAM)
#                  -> half (top=0, bottom=1) -> row -> column -> minor
#
#              and each row of each block type ends with 2 PAD frames that
#              carry no address. The FAR packing is UG470's:
#
#                  FAR = block<<23 | half<<22 | row<<17 | column<<7 | minor
#
#              part.yaml supplies the one device-specific input: the minor
#              frame count of every (half, row, bus, column). Other buses in
#              part.yaml (e.g. CFG_CLB) are not in the FDRI payload of our
#              bitstreams and are ignored, but listed in `ignored_buses`.
#
#              The parser here reads only the frame_count leaves of
#              global_clock_regions by indentation, after stripping custom
#              YAML tags (!<xilinx/xc7series/...>), so no YAML dependency is
#              added. verify_far_map.py re-derives the same order separately
#              and checks it against Vivado's .ll files.
#
# Usage:
#   from far_map import FarMap
#   m = FarMap.load()            # default: ~/.cache/bladei/prjxray-db/CURRENT
#   m.far(2043) == 0x00001d1f

import collections
import json
import os
import re
from dataclasses import dataclass

CACHE_ROOT = os.path.expanduser("~/.cache/bladei/prjxray-db")
PART_YAML = "zynq7/xc7z020clg400-1/part.yaml"

BLOCK_TYPES = (("CLB_IO_CLK", 0), ("BLOCK_RAM", 1))
HALVES = (("top", 0), ("bottom", 1))
PAD_FRAMES_PER_ROW = 2

_TAG = re.compile(r"!<[^>]*>")


def default_db_dir(cache_root=CACHE_ROOT):
    """The database folder named by <cache_root>/CURRENT."""
    current = os.path.join(cache_root, "CURRENT")
    if not os.path.exists(current):
        raise FileNotFoundError("%s missing -- run fetch_prjxray_db.py first"
                                % current)
    with open(current) as fh:
        return os.path.join(cache_root, fh.read().strip())


# ---------------------------------------------------------------------------
# FAR packing.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FarFields:
    block_type: int
    half: int          # 0 = top, 1 = bottom
    row: int
    column: int
    minor: int


def encode_far(block_type, half, row, column, minor):
    for name, v, width in (("block_type", block_type, 3), ("half", half, 1),
                           ("row", row, 5), ("column", column, 10),
                           ("minor", minor, 7)):
        if not 0 <= v < (1 << width):
            raise ValueError("%s=%d does not fit in %d bits" % (name, v, width))
    return (block_type << 23) | (half << 22) | (row << 17) | (column << 7) \
        | minor


def decode_far(far):
    if not 0 <= far < (1 << 26):
        raise ValueError("FAR 0x%08x has reserved bits [31:26] set" % far)
    return FarFields(block_type=(far >> 23) & 0x7, half=(far >> 22) & 0x1,
                     row=(far >> 17) & 0x1F, column=(far >> 7) & 0x3FF,
                     minor=far & 0x7F)


# ---------------------------------------------------------------------------
# part.yaml -> frame order.
# ---------------------------------------------------------------------------
def parse_part_yaml(path):
    """{(half_name, row, bus, column): frame_count} from a prjxray part.yaml.

    Tracks the chain of enclosing keys by indentation and keeps only leaves
    at global_clock_regions/<half>/rows/<row>/configuration_buses/<bus>/
    configuration_columns/<column>/frame_count.
    """
    stack, out = [], {}
    with open(path) as fh:
        for lineno, raw in enumerate(fh, 1):
            line = _TAG.sub("", raw).rstrip()
            body = line.lstrip(" ")
            if not body or body.startswith("#") or body.startswith("-"):
                continue
            key, sep, val = body.partition(":")
            if not sep:
                continue
            indent = len(line) - len(body)
            key, val = key.strip().strip("'\""), val.strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            path_keys = tuple(k for _, k in stack)
            if not val:
                stack.append((indent, key))
                continue
            if path_keys[:1] == ("global_clock_regions",) and val[0] in "{[":
                raise ValueError("%s:%d: flow-style YAML is not supported"
                                 % (path, lineno))
            if (key == "frame_count" and len(path_keys) == 8
                    and path_keys[0] == "global_clock_regions"
                    and path_keys[2] == "rows"
                    and path_keys[4] == "configuration_buses"
                    and path_keys[6] == "configuration_columns"):
                k = (path_keys[1], int(path_keys[3]), path_keys[5],
                     int(path_keys[7]))
                if k in out:
                    raise ValueError("%s:%d: duplicate column %s"
                                     % (path, lineno, k))
                out[k] = int(val, 0)
    if not out:
        raise ValueError("%s: no frame_count entries found" % path)
    return out


def frame_order(columns):
    """FDRI frame order as a list: FAR per frame, None for a pad frame.
    Returns (order, ignored_bus_names)."""
    half_ids = dict(HALVES)
    unknown = {h for (h, _, _, _) in columns} - set(half_ids)
    if unknown:
        raise ValueError("unknown clock-region halves: %s" % sorted(unknown))
    known_buses = {b for b, _ in BLOCK_TYPES}
    ignored = sorted({b for (_, _, b, _) in columns} - known_buses)

    order = []
    for bus, block in BLOCK_TYPES:
        for half_name, half in HALVES:
            rows = sorted({r for (h, r, b, _) in columns
                           if h == half_name and b == bus})
            for row in rows:
                cols = sorted(c for (h, r, b, c) in columns
                              if (h, r, b) == (half_name, row, bus))
                for col in cols:
                    for minor in range(columns[(half_name, row, bus, col)]):
                        order.append(encode_far(block, half, row, col, minor))
                order.extend([None] * PAD_FRAMES_PER_ROW)
    return order, ignored


# ---------------------------------------------------------------------------
# The map.
# ---------------------------------------------------------------------------
class FarMap:
    def __init__(self, order, db_sha=None, ignored_buses=()):
        self._fars = list(order)
        self._frame_of = {}
        for i, far in enumerate(self._fars):
            if far is None:
                continue
            if far in self._frame_of:
                raise ValueError("FAR 0x%08x assigned to frames %d and %d"
                                 % (far, self._frame_of[far], i))
            self._frame_of[far] = i
        self.db_sha = db_sha
        self.ignored_buses = tuple(ignored_buses)

    @classmethod
    def load(cls, db_dir=None):
        db_dir = db_dir or default_db_dir()
        path = os.path.join(db_dir, PART_YAML)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        order, ignored = frame_order(parse_part_yaml(path))
        sha = None
        manifest = os.path.join(db_dir, "manifest.json")
        if os.path.exists(manifest):
            with open(manifest) as fh:
                sha = json.load(fh).get("sha")
        return cls(order, db_sha=sha, ignored_buses=ignored)

    @property
    def n_frames(self):
        return len(self._fars)

    def _check_index(self, frame_index):
        if not 0 <= frame_index < len(self._fars):
            raise IndexError("frame %d outside 0..%d"
                             % (frame_index, len(self._fars) - 1))

    def is_pad(self, frame_index):
        self._check_index(frame_index)
        return self._fars[frame_index] is None

    def far(self, frame_index):
        self._check_index(frame_index)
        far = self._fars[frame_index]
        if far is None:
            raise ValueError("frame %d is a pad frame (no FAR)" % frame_index)
        return far

    def frame(self, far):
        try:
            return self._frame_of[far]
        except KeyError:
            raise ValueError("FAR 0x%08x is not a frame of this device"
                             % far) from None

    def decode(self, far):
        return decode_far(far)

    def row_counts(self):
        """{(block_type, half, row): number of non-pad frames}."""
        counts = collections.Counter()
        for far in self._fars:
            if far is not None:
                f = decode_far(far)
                counts[(f.block_type, f.half, f.row)] += 1
        return dict(counts)
