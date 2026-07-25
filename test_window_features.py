# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for window_features -- asserts the histogram invariant
#              (summed per-window histograms exactly equal the global histogram),
#              full byte coverage with frame-aligned starts, and the tail-byte
#              policy (partial final window with true byte count, never padded,
#              never dropped).
#
# Usage:
#   python test_window_features.py     (or: pytest test_window_features.py -q)

import glob
import os

import numpy as np

from split_utils import FRAME_BYTES
from window_features import (DEFAULT_WINDOW_FRAMES, N_FEATURES, N_HIST,
                             frame_windows, payload_region,
                             window_feature_matrix)

WIN = DEFAULT_WINDOW_FRAMES * FRAME_BYTES

# Region lengths covering: exact multiple of the window, single full window,
# non-multiple with a partial tail, whole frames short of a window, and
# shorter than one frame.
LENGTHS = [5 * WIN, WIN, 5 * WIN + 1234, 3 * FRAME_BYTES, 100]


def make_config_bytes(n_bytes, seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=n_bytes, dtype=np.uint8)


def test_histogram_invariant():
    """Summed per-window raw-count histograms == global histogram, exactly."""
    for n in LENGTHS:
        arr = make_config_bytes(n, seed=n)
        X, _ = window_feature_matrix(arr)
        summed = X[:, :N_HIST].sum(axis=0)
        global_hist = np.bincount(arr, minlength=N_HIST)
        assert np.array_equal(summed, global_hist), f"histogram mismatch at n={n}"
        assert summed.sum() == n


def test_window_coverage_and_alignment():
    for n in LENGTHS:
        arr = make_config_bytes(n, seed=n)
        X, meta = window_feature_matrix(arr)
        assert X.shape == (len(meta), N_FEATURES)
        assert sum(m["n_bytes"] for m in meta) == n
        for i, m in enumerate(meta):
            assert m["window_index"] == i
            assert m["start_byte"] == i * WIN  # frame-aligned window starts
        # All windows full-length except possibly the last.
        for m in meta[:-1]:
            assert m["n_bytes"] == WIN and not m["is_partial"]
        remainder = n % WIN
        last = meta[-1]
        if remainder:
            assert last["is_partial"] and last["n_bytes"] == remainder
        else:
            assert not last["is_partial"] and last["n_bytes"] == WIN


def test_edge_cases():
    # Empty region: no windows, correctly shaped empty matrix.
    X, meta = window_feature_matrix(np.array([], dtype=np.uint8))
    assert X.shape == (0, N_FEATURES) and meta == []

    # Shorter than one window: a single partial window with its true length.
    arr = make_config_bytes(100)
    X, meta = window_feature_matrix(arr)
    assert len(meta) == 1
    assert meta[0] == {"window_index": 0, "start_byte": 0, "n_bytes": 100,
                      "is_partial": True}

    # Non-default window size stays frame-aligned.
    arr = make_config_bytes(10 * FRAME_BYTES + 7)
    _, meta = window_feature_matrix(arr, window_frames=4)
    assert [m["start_byte"] for m in meta] == [0, 4 * FRAME_BYTES, 8 * FRAME_BYTES]
    assert [m["n_bytes"] for m in meta] == [4 * FRAME_BYTES, 4 * FRAME_BYTES,
                                            2 * FRAME_BYTES + 7]
    assert [m["is_partial"] for m in meta] == [False, False, True]


def test_feature_sanity():
    # Constant bytes: zero entropy, zero std, zero transitions.
    arr = np.full(WIN, 0xAB, dtype=np.uint8)
    X, _ = window_feature_matrix(arr)
    hist, stats = X[0, :N_HIST], X[0, N_HIST:]
    assert hist[0xAB] == WIN and hist.sum() == WIN
    ent, mean, std, mn, mx, med, zr, fr, trate, tmag = stats
    assert abs(ent) < 1e-6 and std == 0.0 and trate == 0.0 and tmag == 0.0
    assert mean == mx == mn == med == 0xAB and zr == 0.0 and fr == 0.0

    # frame_windows never pads: concatenated windows reproduce the region.
    arr = make_config_bytes(2 * WIN + 555)
    rebuilt = np.concatenate([w for _, w in frame_windows(arr)])
    assert np.array_equal(rebuilt, arr)


def _find_real_bitstream():
    for d in [os.environ.get("BLADEI_DATA_DIR", ""),
              os.path.expanduser("~/Desktop/Karakchi-Research/trusthub_bitstreams_v4")]:
        hits = sorted(glob.glob(os.path.join(d, "Benign", "*.bit"))) if d else []
        if hits:
            return hits[0]
    return None


def test_real_bitstream_frame_alignment():
    """Alignment invariants on a real canonical V4 file.

    The old cross-check tied windows to the whole-file histogram and asserted
    only that the region followed a sync word -- which is exactly how the
    184-byte phase error stayed invisible (LEAKAGE_AUDIT.md finding 1). The
    corrected invariants are physical:
      - the payload is exactly 10,008 frames (no remainder);
      - window 0 starts at payload byte 0 == the first configuration frame,
        whose file offset is the parsed FDRI payload offset (region+184);
      - the default 8-frame grid yields exactly 1,251 FULL windows, zero
        partial (n_frames % window_frames reported explicitly);
      - summed per-window histograms equal the payload histogram exactly.
    """
    fp = _find_real_bitstream()
    if fp is None:
        print("(alignment check skipped: no real bitstream found)")
        return
    from bitstream_io import ZYNQ7020_V4, fdri_payload_and_meta

    arr, meta = fdri_payload_and_meta(fp, profile=ZYNQ7020_V4)
    block = meta.fdri_blocks[0]
    n_frames = len(arr) // FRAME_BYTES
    assert len(arr) % FRAME_BYTES == 0 and n_frames == 10008
    assert block.payload_offset_in_region == 184

    # Window 0 must begin at the first frame's first byte.
    with open(fp, "rb") as f:
        raw = f.read()
    first = next(frame_windows(arr))
    assert first[0] == 0
    assert raw[block.payload_offset_in_file:
               block.payload_offset_in_file + 16] == first[1][:16].tobytes()

    X, meta_w = window_feature_matrix(arr)
    remainder = n_frames % DEFAULT_WINDOW_FRAMES
    assert remainder == 0, f"unexpected remainder {remainder} on this device"
    assert len(meta_w) == 1251
    assert not any(m["is_partial"] for m in meta_w)
    assert all(m["n_bytes"] == DEFAULT_WINDOW_FRAMES * FRAME_BYTES
               for m in meta_w)
    assert np.array_equal(X[:, :N_HIST].sum(axis=0),
                          np.bincount(arr, minlength=N_HIST))


if __name__ == "__main__":
    test_histogram_invariant()
    test_window_coverage_and_alignment()
    test_edge_cases()
    test_feature_sanity()
    test_real_bitstream_frame_alignment()
    print("All window feature tests passed.")
