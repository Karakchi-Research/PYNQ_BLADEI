# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Frame-aligned windowed feature extraction for trojan LOCALIZATION.
#              Splits the FDRI configuration payload into windows of N 7-series
#              config frames (N x 404 bytes, default 8) and computes per-window
#              features that mirror the global statistical pipeline. Histograms
#              are RAW COUNTS so summed window histograms exactly reproduce the
#              payload histogram (the invariant checked by
#              test_window_features.py). Tail bytes form a partial final window
#              flagged with its true byte count in the window metadata -- never
#              zero-padded, never dropped (required for other window sizes and
#              device profiles; the canonical V4 payload divides exactly).
#
#              OFFSET 0 == FIRST FDRI PAYLOAD BYTE == first byte of frame 0.
#              Corrected 2026-07-25: the previous version windowed everything
#              after the sync word, whose frames actually start 184 bytes in,
#              so every window straddled two frames (LEAKAGE_AUDIT.md,
#              finding 1). Extraction now goes through bitstream_io's parsed,
#              profile-validated FDRI payload.
#              Lives alongside the frozen global pipeline; replaces nothing.

import numpy as np
from scipy.stats import entropy

from bitstream_io import ZYNQ7020_V4, fdri_payload
from split_utils import FRAME_BYTES

DEFAULT_WINDOW_FRAMES = 8

N_HIST = 256
N_STATS = 10
N_FEATURES = N_HIST + N_STATS


def payload_region(filepath, profile=ZYNQ7020_V4):
    """FDRI configuration payload as a uint8 array; byte 0 is frame 0, byte 0.

    Parsed and validated against the canonical profile (fails on deviation);
    the .bit ASCII header, packet preamble, and trailer never enter the array.
    """
    return fdri_payload(filepath, profile=profile)


def frame_windows(arr, window_frames=DEFAULT_WINDOW_FRAMES):
    """Yield (start_byte, window) slices of `arr`, frame-aligned.

    Every window starts at a multiple of window_frames * FRAME_BYTES. The final
    window keeps its true (shorter) length when `arr` is not a whole number of
    windows.
    """
    assert window_frames >= 1, "window_frames must be a positive integer"
    win = window_frames * FRAME_BYTES
    for start in range(0, len(arr), win):
        yield start, arr[start:start + win]


def _window_features(w):
    n = len(w)
    hist = np.bincount(w, minlength=N_HIST).astype(np.float64)
    diff = np.diff(w.astype(np.int16))
    transition_rate = np.sum(diff != 0) / max(1, len(diff))
    avg_transition_mag = np.mean(np.abs(diff)) if len(diff) > 0 else 0.0
    stats = np.array([
        entropy(hist / n + 1e-10),
        np.mean(w), np.std(w), np.min(w), np.max(w), np.median(w),
        np.sum(w == 0) / n, np.sum(w == 255) / n,
        transition_rate, avg_transition_mag,
    ])
    return np.concatenate([hist, stats])


def window_feature_matrix(arr, window_frames=DEFAULT_WINDOW_FRAMES):
    """Per-window features + metadata for one config-region byte array.

    Returns (X, meta): X is (n_windows, N_FEATURES) float64 -- 256 raw-count
    histogram bins followed by 10 statistical features (entropy, mean, std, min,
    max, median, zero-ratio, 0xFF-ratio, transition rate, mean |transition|).
    meta[i] records window_index, start_byte, n_bytes (true byte count, partial
    final window included) and is_partial.
    """
    win = window_frames * FRAME_BYTES
    rows, meta = [], []
    for i, (start, w) in enumerate(frame_windows(arr, window_frames)):
        rows.append(_window_features(w))
        meta.append({"window_index": i, "start_byte": int(start),
                     "n_bytes": int(len(w)), "is_partial": len(w) < win})
    X = np.array(rows) if rows else np.empty((0, N_FEATURES))
    return X, meta
