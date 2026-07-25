# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5 / Phase 1 full-corpus windowed-extraction audit.
#              Runs the corrected frame-aligned extractor (window_features on
#              the FDRI payload) over EVERY file in the corpus index and
#              asserts, per file:
#                - payload passes the strict V4 profile (parsed, not assumed);
#                - exactly 10,008 frames, zero remainder;
#                - exactly 1,251 full 8-frame windows, none partial;
#                - byte coverage: window n_bytes sum to 4,043,232;
#                - summed per-window raw-count histograms == payload histogram.
#              Logs the extraction config + per-family window accounting.
#              Any violation aborts with a non-zero exit.
#
# Usage:
#   python3 audit_window_extraction.py [--index corpus_out/corpus_index.json]

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

from bitstream_io import PARSER_VERSION, ZYNQ7020_V4, fdri_payload
from corpus_index import load_index
from split_utils import FRAME_BYTES
from window_features import (DEFAULT_WINDOW_FRAMES, N_HIST,
                             window_feature_matrix)

EXPECT_FRAMES = ZYNQ7020_V4.n_frames                      # 10,008
EXPECT_WINDOWS = EXPECT_FRAMES // DEFAULT_WINDOW_FRAMES   # 1,251
EXPECT_BYTES = ZYNQ7020_V4.payload_bytes                  # 4,043,232


def audit_file(path):
    arr = fdri_payload(path, profile=ZYNQ7020_V4)   # profile-validated read
    n_frames, rem = divmod(len(arr), FRAME_BYTES)
    assert rem == 0 and n_frames == EXPECT_FRAMES, \
        f"{path}: {n_frames} frames, remainder {rem}"
    X, meta = window_feature_matrix(arr)
    assert len(meta) == EXPECT_WINDOWS, f"{path}: {len(meta)} windows"
    assert not any(m["is_partial"] for m in meta), f"{path}: partial window"
    assert sum(m["n_bytes"] for m in meta) == EXPECT_BYTES, \
        f"{path}: byte coverage broken"
    assert meta[0]["start_byte"] == 0
    assert np.array_equal(X[:, :N_HIST].sum(axis=0),
                          np.bincount(arr, minlength=N_HIST)), \
        f"{path}: histogram invariant broken"
    return len(meta)


def main():
    p = argparse.ArgumentParser(description="Full-corpus windowed-extraction audit")
    p.add_argument("--index", default=os.path.join("corpus_out",
                                                   "corpus_index.json"))
    p.add_argument("--out", default=os.path.join("phase05_out",
                                                 "window_extraction_audit.json"))
    args = p.parse_args()

    index = load_index(args.index)
    data_dir = index["data_dir"]
    recs = index["files"]
    print(f"=== Windowed-extraction audit: {len(recs)} files | "
          f"window = {DEFAULT_WINDOW_FRAMES} frames x {FRAME_BYTES} B | "
          f"expecting {EXPECT_WINDOWS} windows/file ===")

    per_family = {}
    for i, r in enumerate(recs, 1):
        n = audit_file(os.path.join(data_dir, r["relpath"]))
        f = per_family.setdefault(r["family"], {"files": 0, "windows": 0})
        f["files"] += 1
        f["windows"] += n
        if i % 100 == 0 or i == len(recs):
            print(f"    {i}/{len(recs)}")

    total_windows = sum(f["windows"] for f in per_family.values())
    print(f"\n  all {len(recs)} files passed every invariant")
    print(f"  total windows: {total_windows} "
          f"(= {len(recs)} x {EXPECT_WINDOWS})")
    assert total_windows == len(recs) * EXPECT_WINDOWS

    report = {"generated": datetime.now(timezone.utc).isoformat(),
              "manifest_id": index["manifest_id"],
              "parser_version": PARSER_VERSION,
              "profile": ZYNQ7020_V4.name,
              "extraction_config": {
                  "window_frames": DEFAULT_WINDOW_FRAMES,
                  "frame_bytes": FRAME_BYTES,
                  "window_bytes": DEFAULT_WINDOW_FRAMES * FRAME_BYTES,
                  "expected_frames_per_file": EXPECT_FRAMES,
                  "expected_windows_per_file": EXPECT_WINDOWS,
                  "partial_windows_expected": 0},
              "n_files": len(recs), "total_windows": total_windows,
              "per_family": per_family,
              "invariants": ["profile_validated_payload",
                             "whole_frame_count_10008",
                             "full_windows_1251_no_partial",
                             "byte_coverage_4043232",
                             "window_histograms_sum_to_payload_histogram"],
              "all_passed": True}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  report -> {args.out}")


if __name__ == "__main__":
    main()
