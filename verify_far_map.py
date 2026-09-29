# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Independent check of the frame index <-> FAR map against
#              Vivado's own logic-location (.ll) files.
#
#              Deliberately imports NEITHER far_map NOR bitstream_io: the
#              frame order is re-derived here from part.yaml by a different
#              route (a generic indentation tree, then a walk over it), so a
#              shared bug cannot make both agree.
#
#              Every .ll 'Bit' line states a bit offset, a FAR and the bit's
#              offset within its frame, e.g.
#                  Bit  6604003 0x00001d1f   1027 Block=SLICE_X92Y116 ...
#              so frame = (6604003 - 1027) / 3232 = 2043 -- which must be an
#              exact integer. The checks, over every line of every file:
#                1) alignment   : 0 <= frame_offset < 3232 and the division
#                                 is exact
#                2) agreement   : the FAR Vivado states for that frame equals
#                                 the FAR derived from part.yaml (a pad or
#                                 out-of-range frame is a mismatch)
#                3) uniqueness  : no FAR is observed at two different frames
#              Counts are printed and written, with the db SHA, to
#              localization_corpus/format_aware/far_map_verification.json.
#              Exit status is nonzero if any check fails.
#
# Usage:
#   python3 verify_far_map.py [--db DIR] [--ll-root DIR] [--out PATH]

import argparse
import collections
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

SCHEMA = "far_map_verification_v1"
CACHE_ROOT = os.path.expanduser("~/.cache/bladei/prjxray-db")
PART_YAML = "zynq7/xc7z020clg400-1/part.yaml"
FRAME_BITS = 101 * 32                 # 3232
PADS_PER_ROW = 2
N_EXAMPLES = 20


def default_db():
    current = os.path.join(CACHE_ROOT, "CURRENT")
    if not os.path.exists(current):
        return None
    with open(current) as fh:
        return os.path.join(CACHE_ROOT, fh.read().strip())


def yaml_tree(path):
    """Block-style YAML mappings -> nested dicts (scalars kept as strings).
    Custom tags are stripped; list items are ignored."""
    root = {}
    stack = [(-1, root)]
    with open(path) as fh:
        for raw in fh:
            line = re.sub(r"!<[^>]*>", "", raw).rstrip()
            text = line.lstrip(" ")
            if not text or text[0] in "#-" or ":" not in text:
                continue
            indent = len(line) - len(text)
            key, value = text.split(":", 1)
            key, value = key.strip().strip("'\""), value.strip()
            while stack[-1][0] >= indent:
                stack.pop()
            if value:
                stack[-1][1][key] = value
            else:
                child = {}
                stack[-1][1][key] = child
                stack.append((indent, child))
    return root


def derive_fars(part_yaml):
    """({frame_index: FAR} over configuration frames, total frame count)."""
    regions = yaml_tree(part_yaml)["global_clock_regions"]
    fars, frame = {}, 0
    for block, bus in ((0, "CLB_IO_CLK"), (1, "BLOCK_RAM")):
        for half, name in ((0, "top"), (1, "bottom")):
            rows = regions.get(name, {}).get("rows", {})
            for row in sorted(rows, key=int):
                cols = (rows[row].get("configuration_buses", {})
                        .get(bus, {}).get("configuration_columns", {}))
                if not cols:
                    continue
                for col in sorted(cols, key=int):
                    for minor in range(int(cols[col]["frame_count"], 0)):
                        fars[frame] = ((block << 23) | (half << 22)
                                       | (int(row) << 17) | (int(col) << 7)
                                       | minor)
                        frame += 1
                frame += PADS_PER_ROW
    return fars, frame


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(
        description="Verify the part.yaml frame->FAR map against .ll files")
    p.add_argument("--db", default=default_db(),
                   help="prjxray-db folder (default: %s/CURRENT)" % CACHE_ROOT)
    p.add_argument("--ll-root", default="rebuild_pilot",
                   help="searched recursively for *.ll")
    p.add_argument("--out", default=os.path.join(
        "localization_corpus", "format_aware", "far_map_verification.json"))
    args = p.parse_args()

    if not args.db:
        sys.exit("no --db and no %s/CURRENT -- run fetch_prjxray_db.py first"
                 % CACHE_ROOT)
    part_yaml = os.path.join(args.db, PART_YAML)
    if not os.path.exists(part_yaml):
        sys.exit("missing %s" % part_yaml)
    part_sha256 = sha256_of(part_yaml)
    db_sha = os.path.basename(os.path.normpath(args.db))
    manifest_path = os.path.join(args.db, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as fh:
            manifest = json.load(fh)
        db_sha = manifest.get("sha", db_sha)
        listed = manifest.get("files", {}).get(PART_YAML, {}).get("sha256")
        if listed and listed != part_sha256:
            sys.exit("%s does not match its manifest SHA-256" % part_yaml)

    derived, n_frames = derive_fars(part_yaml)
    print("prjxray-db %s: %d frames = %d config + %d pad"
          % (db_sha, n_frames, len(derived), n_frames - len(derived)))

    ll_paths = sorted(glob.glob(os.path.join(args.ll_root, "**", "*.ll"),
                                recursive=True))
    if not ll_paths:
        sys.exit("no .ll files under %s" % args.ll_root)

    pairs = set()
    frames_of_far = collections.defaultdict(set)
    per_file = {}
    n_lines = n_malformed = n_misaligned = 0
    lines_by_block = collections.Counter()
    misaligned_examples = []
    for path in ll_paths:
        n_file = 0
        with open(path, errors="ignore") as fh:
            for line in fh:
                if not line.startswith("Bit "):
                    continue
                n_lines += 1
                n_file += 1
                t = line.split(None, 4)
                try:
                    bit, far, offset = int(t[1]), int(t[2], 16), int(t[3])
                except (IndexError, ValueError):
                    n_malformed += 1
                    continue
                if not 0 <= offset < FRAME_BITS or (bit - offset) % FRAME_BITS:
                    n_misaligned += 1
                    if len(misaligned_examples) < N_EXAMPLES:
                        misaligned_examples.append(
                            "%s: %s" % (os.path.relpath(path), line.strip()))
                    continue
                frame = (bit - offset) // FRAME_BITS
                lines_by_block[(far >> 23) & 0x7] += 1
                pairs.add((frame, far))
                frames_of_far[far].add(frame)
        per_file[os.path.relpath(path)] = n_file

    mismatches = sorted((f, far) for (f, far) in pairs
                        if derived.get(f) != far)
    collisions = {far: sorted(fs) for far, fs in frames_of_far.items()
                  if len(fs) > 1}
    observed_frames = {f for f, _ in pairs}
    covered = observed_frames & set(derived)
    passed = not (n_malformed or n_misaligned or mismatches or collisions)

    counts = {
        "n_ll_files": len(ll_paths),
        "n_bit_lines": n_lines,
        "n_malformed_lines": n_malformed,
        "n_misaligned_lines": n_misaligned,
        "n_bit_lines_by_block_type": {str(k): v for k, v in
                                      sorted(lines_by_block.items())},
        "n_distinct_frame_far_pairs": len(pairs),
        "n_distinct_fars": len(frames_of_far),
        "n_mismatched_pairs": len(mismatches),
        "n_fars_at_multiple_frames": len(collisions),
        "n_config_frames_observed": len(covered),
        "n_config_frames_derived": len(derived),
        "n_frames_derived": n_frames,
    }

    print("%d .ll files under %s" % (len(ll_paths), args.ll_root))
    for k, v in counts.items():
        print("  %-28s: %s" % (k, v))
    for f, far in mismatches[:N_EXAMPLES]:
        want = derived.get(f)
        print("  MISMATCH frame %d: .ll 0x%08x, part.yaml %s"
              % (f, far, "0x%08x" % want if want is not None
                 else "pad/out of range"))
    for far, fs in list(collisions.items())[:N_EXAMPLES]:
        print("  COLLISION FAR 0x%08x at frames %s" % (far, fs))
    for ex in misaligned_examples:
        print("  MISALIGNED %s" % ex)
    print("PASS" if passed else "FAIL")

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "part": "xc7z020clg400-1",
        "prjxray_db_sha": db_sha,
        "part_yaml_sha256": part_sha256,
        "ll_root": args.ll_root,
        "frame_bits": FRAME_BITS,
        "passed": passed,
        "counts": counts,
        "examples": {
            "mismatches": [{"frame": f, "ll_far": "0x%08x" % far,
                            "derived_far": (None if derived.get(f) is None
                                            else "0x%08x" % derived[f])}
                           for f, far in mismatches[:N_EXAMPLES]],
            "collisions": {"0x%08x" % far: fs for far, fs in
                           list(collisions.items())[:N_EXAMPLES]},
            "misaligned": misaligned_examples,
        },
        "per_file_bit_lines": per_file,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print("-> %s" % args.out)
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
