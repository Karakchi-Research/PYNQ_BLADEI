# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Independent re-check of l3_format_aware_results.json.
#
#              Deliberately imports NONE of bitstream_io, far_map,
#              frame_types, tile_decode or lut_canon: the FDRI payload, the
#              frame order and the tile addressing are re-derived here from
#              the raw .bit, part.yaml and tilegrid.json, so a bug shared by
#              those modules cannot make both sides agree.
#
#                payload  packet walk in which a type-2 header continues the
#                         register of the type-1 header before it (UG470);
#                         exactly one FDRI write, after FAR = 0
#                frames   part.yaml frame_count per (half, row, bus, column),
#                         ordered bus -> half -> row -> column -> minor, with
#                         2 pad frames closing each row
#                tiles    minor m of a tile is the frame whose FAR is
#                         baseaddr + m; the tile owns words offset, offset+1
#
#              For every l3 build in the results file, against B_Default:
#                1) both .bit files hash to the SHA-256 recorded there
#                2) the 8-frame windows with any differing byte equal the
#                   recorded differing_windows_all
#                3) the GT tile set, re-mapped from declared_sites through
#                   tilegrid "sites", equals the recorded one
#                4) every GT tile and every flagged tile has a differing word
#                   in its CLB logic minors (0-1, 26-35)
#                5) the recorded survival flag agrees with 4) for GT tiles
#              A GT tile failing 4) is a real survival failure, not a bug;
#              5) is what says whether the results file reported it honestly.
#              PASS/FAIL per build; exit status is nonzero on any FAIL.
#
# Usage:
#   python3 verify_format_aware.py [--results PATH] [--artifacts DIR]
#                                  [--gt PATH] [--db DIR]

import argparse
import hashlib
import json
import os
import re
import sys

import numpy as np

CACHE_ROOT = os.path.expanduser("~/.cache/bladei/prjxray-db")
PART_YAML = "zynq7/xc7z020clg400-1/part.yaml"
TILEGRID = "zynq7/xc7z020/tilegrid.json"
RESULTS = os.path.join("localization_corpus", "format_aware",
                       "l3_format_aware_results.json")
FOLDER = "l3"
REF = "B_Default"

SYNC = b"\xaa\x99\x55\x66"
REG_FAR, REG_FDRI = 1, 2
OP_WRITE = 2
FRAME_WORDS = 101
WINDOW = 8
PADS_PER_ROW = 2
TILE_WORDS = 2
CLB_TYPES = ("CLBLL_L", "CLBLL_R", "CLBLM_L", "CLBLM_R")
LOGIC_MINORS = (0, 1) + tuple(range(26, 36))

_KEY = re.compile(r"^( *)([^\s:#-][^:]*):\s*(.*)$")


def default_db():
    current = os.path.join(CACHE_ROOT, "CURRENT")
    if not os.path.exists(current):
        return None
    with open(current) as fh:
        return os.path.join(CACHE_ROOT, fh.read().strip())


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Payload.
# ---------------------------------------------------------------------------
def read_fdri(path):
    """(FDRI payload as big-endian uint32 array, FAR written before it)."""
    with open(path, "rb") as fh:
        data = fh.read()
    start = data.find(SYNC)
    if start < 0:
        raise ValueError("%s: no sync word" % path)
    start += len(SYNC)
    n = (len(data) - start) // 4
    w = np.frombuffer(data, dtype=">u4", count=n, offset=start)
    i, reg, far, blocks = 0, None, None, []
    while i < n:
        hdr = int(w[i])
        i += 1
        kind = hdr >> 29
        if kind == 1:
            reg, count = (hdr >> 13) & 0x3FFF, hdr & 0x7FF
        elif kind == 2:
            if reg is None:
                raise ValueError("%s: type-2 packet before any type-1" % path)
            count = hdr & 0x7FFFFFF
        else:
            continue
        if (hdr >> 27) & 0x3 == OP_WRITE and count:
            if i + count > n:
                raise ValueError("%s: packet runs past end of file" % path)
            if reg == REG_FAR:
                far = int(w[i])
            elif reg == REG_FDRI:
                blocks.append((far, w[i:i + count]))
        i += count
    if len(blocks) != 1:
        raise ValueError("%s: %d FDRI writes (expected 1)"
                         % (path, len(blocks)))
    far, payload = blocks[0]
    return payload, far


# ---------------------------------------------------------------------------
# Frame order.
# ---------------------------------------------------------------------------
def frame_counts(part_yaml):
    """{(half, row, bus, column): frame_count}, row/column kept as strings."""
    out, path = {}, []
    with open(part_yaml) as fh:
        for raw in fh:
            m = _KEY.match(re.sub(r"!<[^>]*>", "", raw).rstrip())
            if not m:
                continue
            depth = len(m.group(1))
            key = m.group(2).strip().strip("'\"")
            value = m.group(3).strip()
            path = [(d, k) for d, k in path if d < depth]
            if not value:
                path.append((depth, key))
                continue
            keys = [k for _, k in path]
            if (key == "frame_count" and len(keys) == 8
                    and keys[0] == "global_clock_regions"
                    and keys[2] == "rows"
                    and keys[4] == "configuration_buses"
                    and keys[6] == "configuration_columns"):
                out[(keys[1], keys[3], keys[5], keys[7])] = int(value, 0)
    if not out:
        raise ValueError("%s: no frame_count entries" % part_yaml)
    return out


def frame_of_far(counts):
    """({FAR: frame index}, total frames including pads)."""
    out, frame = {}, 0
    for block, bus in ((0, "CLB_IO_CLK"), (1, "BLOCK_RAM")):
        for half, hname in ((0, "top"), (1, "bottom")):
            rows = sorted({r for (h, r, b, _) in counts
                           if h == hname and b == bus}, key=int)
            for row in rows:
                cols = sorted((c for (h, r, b, c) in counts
                               if (h, r, b) == (hname, row, bus)), key=int)
                for col in cols:
                    for minor in range(counts[(hname, row, bus, col)]):
                        far = ((block << 23) | (half << 22) | (int(row) << 17)
                               | (int(col) << 7) | minor)
                        if far in out:
                            raise ValueError("FAR 0x%08x derived twice" % far)
                        out[far] = frame
                        frame += 1
                frame += PADS_PER_ROW
    return out, frame


# ---------------------------------------------------------------------------
# Tiles.
# ---------------------------------------------------------------------------
def load_tilegrid(path):
    """({CLB tile: (baseaddr, offset, n_frames)}, {SLICE site: (tile, type)})."""
    with open(path) as fh:
        grid = json.load(fh)
    tiles, sites = {}, {}
    for name, t in grid.items():
        for s in t.get("sites", {}):
            if s.startswith("SLICE_"):
                sites[s] = (name, t.get("type"))
        if t.get("type") in CLB_TYPES:
            b = t["bits"]["CLB_IO_CLK"]
            tiles[name] = (int(b["baseaddr"], 16), int(b["offset"]),
                           int(b["frames"]))
    return tiles, sites


def logic_differs(differs, far_frame, tile):
    """True iff the tile has a differing word in any of its logic minors."""
    base, offset, n = tile
    frames = [far_frame[base + m] for m in LOGIC_MINORS if m < n]
    return bool(differs[frames, offset:offset + TILE_WORDS].any())


# ---------------------------------------------------------------------------
# Per-build check.
# ---------------------------------------------------------------------------
def check_build(build, rec, ref, test, far_frame, tiles, sites, gt_sites):
    """(list of problems, one-line summary)."""
    problems = []
    differs = ref != test
    win = np.flatnonzero(differs.any(axis=1).reshape(-1, WINDOW).any(axis=1))
    if win.tolist() != rec["differing_windows_all"]:
        problems.append("differing windows: %d recomputed vs %d recorded"
                        % (len(win), len(rec["differing_windows_all"])))

    def tile_ok(name):
        if name not in tiles:
            problems.append("%s is not a CLB tile in tilegrid" % name)
            return False
        try:
            return logic_differs(differs, far_frame, tiles[name])
        except KeyError as e:
            problems.append("%s: FAR 0x%08x has no frame" % (name, e.args[0]))
            return False

    fl_ok = [n for n in rec["flagged"] if tile_ok(n)]
    for n in sorted(set(rec["flagged"]) - set(fl_ok)):
        problems.append("flagged tile %s has no differing logic word" % n)
    line = "windows %d  flagged %d/%d" % (len(win), len(fl_ok),
                                          len(rec["flagged"]))

    g = rec.get("gt")
    if build in gt_sites:
        mapped, unmapped = set(), []
        for s in gt_sites[build]:
            hit = sites.get(s)
            if hit is None or hit[1] not in CLB_TYPES:
                unmapped.append(s)
            else:
                mapped.add(hit[0])
        if g is None:
            problems.append("GT exists but the results file has none")
            return problems, line
        if sorted(mapped) != g["tiles"]:
            problems.append("GT tiles differ: recomputed %s vs recorded %s"
                            % (sorted(mapped), g["tiles"]))
        if unmapped != g["sites_unmapped"]:
            problems.append("unmapped GT sites differ: %s vs %s"
                            % (unmapped, g["sites_unmapped"]))
        gt_ok = [n for n in sorted(mapped) if tile_ok(n)]
        lost = sorted(mapped - set(gt_ok))
        for n in lost:
            problems.append("GT tile %s has no differing logic word" % n)
        if (not lost) != g["survived"]:
            problems.append("recorded survived=%s but recomputed %s"
                            % (g["survived"], not lost))
        line += "  gt %d/%d" % (len(gt_ok), len(mapped))
    elif g is not None:
        problems.append("results file has GT but %s has no declared_sites"
                        % build)
    return problems, line


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Independently verify l3_format_aware_results.json")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--artifacts", default=None,
                   help="default: artifacts_root recorded in the results")
    p.add_argument("--gt", default=None,
                   help="default: gt_path recorded in the results")
    p.add_argument("--db", default=default_db(),
                   help="prjxray-db folder (default: %s/CURRENT)" % CACHE_ROOT)
    args = p.parse_args()

    with open(args.results) as fh:
        res = json.load(fh)
    artifacts = args.artifacts or res["artifacts_root"]
    gt_path = args.gt or res["gt_path"]
    if not args.db:
        sys.exit("no --db and no %s/CURRENT" % CACHE_ROOT)
    inputs = res["inputs"]

    fatal = []
    for rel in (PART_YAML, TILEGRID):
        want = inputs.get("prjxray-db/" + rel)
        if want != sha256_of(os.path.join(args.db, rel)):
            fatal.append("%s does not match the recorded SHA-256" % rel)
    if inputs.get("gt/" + os.path.basename(gt_path)) != sha256_of(gt_path):
        fatal.append("%s does not match the recorded SHA-256" % gt_path)
    if fatal:
        sys.exit("FAIL\n  " + "\n  ".join(fatal))

    far_frame, n_frames = frame_of_far(
        frame_counts(os.path.join(args.db, PART_YAML)))
    if n_frames % WINDOW:
        sys.exit("%d frames is not whole %d-frame windows" % (n_frames, WINDOW))
    tiles, sites = load_tilegrid(os.path.join(args.db, TILEGRID))
    with open(gt_path) as fh:
        gt_sites = {b: r["declared_sites"] for b, r in
                    json.load(fh)["per_build"].items() if "declared_sites" in r}

    def load(build):
        path = os.path.join(artifacts, FOLDER, build + ".bit")
        payload, far = read_fdri(path)
        errs = []
        if inputs.get("artifacts/%s/%s.bit" % (FOLDER, build)) \
                != sha256_of(path):
            errs.append("%s.bit does not match the recorded SHA-256" % build)
        if far != 0:
            errs.append("%s.bit: FDRI starts at FAR %s, not 0"
                        % (build, "none" if far is None else "0x%08x" % far))
        if payload.size != n_frames * FRAME_WORDS:
            errs.append("%s.bit: %d payload words, expected %d x %d"
                        % (build, payload.size, n_frames, FRAME_WORDS))
            return None, errs
        return payload.reshape(n_frames, FRAME_WORDS), errs

    ref, ref_errs = load(REF)
    print("=== independent check: %s builds vs %s (prjxray-db %s) ==="
          % (FOLDER, REF, res.get("prjxray_db_sha")))
    print("%d frames = %d config + %d pad | %d CLB tiles"
          % (n_frames, len(far_frame), n_frames - len(far_frame), len(tiles)))
    if ref is None:
        sys.exit("FAIL\n  " + "\n  ".join(ref_errs))

    builds = res["builds"].get(FOLDER, {})
    if not builds:
        sys.exit("FAIL: no %s builds in %s" % (FOLDER, args.results))
    n_pass = 0
    for build, rec in sorted(builds.items()):
        test, problems = load(build)
        problems = ref_errs + problems
        line = ""
        if test is not None:
            more, line = check_build(build, rec, ref, test, far_frame, tiles,
                                     sites, gt_sites)
            problems += more
        ok = not problems
        n_pass += ok
        print("  %-20s %s  %s" % (build, "PASS" if ok else "FAIL", line))
        for pr in problems:
            print("      %s" % pr)
    print("%d/%d builds PASS" % (n_pass, len(builds)))
    if n_pass != len(builds):
        sys.exit(1)


if __name__ == "__main__":
    main()
