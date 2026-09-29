# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for frame_types -- classes derived from the pinned
#              prjxray-db must reproduce the expected per-column patterns
#              (CLB: 0-1 mixed, 2-25 routing, 26-35 logic; BRAM/DSP: 0-25
#              routing, 26-27 logic); a bitstream diffed with itself must
#              report nothing; and a single flipped bit in minor 30 of a CLB
#              column must land in exactly one LOGIC frame and one window,
#              counted by both the all-frames and logic-only window counts.
#
#              Bitstreams are synthetic (full V4 geometry, random payload)
#              so no corpus file is needed; the prjxray-db cache is, and the
#              tests skip with a message when it is absent.
#
# Usage:
#   python3 test_frame_types.py    (or: pytest test_frame_types.py -q)

import os
import tempfile

from bitstream_io import CanonicalProfile, ZYNQ7020_V4
from frame_types import (CLASSES, EXPECTED, LOGIC, MIXED, ROUTING,
                         FrameTypes, check_expected, describe, typed_diff)
from test_bitstream_io import make_synthetic_bit

# V4 frame geometry behind the synthetic packet preamble (payload at region
# offset 40 instead of 184).
SYNTH_V4 = CanonicalProfile(name="synthetic_v4_geometry",
                            fdri_offset_in_region=40,
                            payload_words=ZYNQ7020_V4.payload_words,
                            frame_words=ZYNQ7020_V4.frame_words,
                            n_fdri_blocks=1, initial_far=0x0)

_FT = []


def _frame_types():
    if not _FT:
        try:
            _FT.append(FrameTypes.load())
        except FileNotFoundError as e:
            print("(frame_types tests skipped: %s)" % e)
            _FT.append(None)
    return _FT[0]


def _write(d, name, blob):
    path = os.path.join(d, name)
    with open(path, "wb") as fh:
        fh.write(blob)
    return path


def test_clb_column_class_counts():
    ft = _frame_types()
    if ft is None:
        return
    clb = [c for c in ft.columns.values() if c.kind == "CLB"]
    assert clb, "no CLB columns found"
    for c in clb:
        assert c.n_minors == 36, "%s has %d minors" % (c.name(), c.n_minors)
        counts = {name: c.classes.count(i) for i, name in enumerate(CLASSES)}
        assert counts == {"routing": 24, "logic": 10, "mixed": 2,
                          "bram_content": 0, "pad": 0}, \
            "%s: %s" % (c.name(), describe(c.classes))
        assert c.classes == EXPECTED["CLB"]
    # Same check device-wide, BRAM/DSP included.
    assert check_expected(ft) == [], check_expected(ft)
    assert ft.frame_counts()["pad"] + sum(
        c.n_minors for c in ft.columns.values()) == ft.n_frames == 10008


def test_clb_minor_ranges():
    """Minors 2-25 routing, 0-1 mixed, 26-35 logic in every CLB column, in
    both the column record and the per-frame code array. Guards against
    evidence-less tiles (e.g. HCLK without segbits) turning routing into
    mixed."""
    ft = _frame_types()
    if ft is None:
        return
    for c in (c for c in ft.columns.values() if c.kind == "CLB"):
        codes = ft.codes[c.first_frame:c.first_frame + c.n_minors].tolist()
        for classes in (c.classes, codes):
            assert all(x == ROUTING for x in classes[2:26]), \
                "%s: %s" % (c.name(), describe(classes))
            assert classes[0:2] == [MIXED, MIXED], c.name()
            assert all(x == LOGIC for x in classes[26:36]), c.name()
    assert ft.frame_counts()["routing"] > 0


def test_self_diff_is_zero():
    ft = _frame_types()
    if ft is None:
        return
    blob, _ = make_synthetic_bit(SYNTH_V4.payload_words)
    with tempfile.TemporaryDirectory() as d:
        path = _write(d, "a.bit", blob)
        r = typed_diff(path, path, ft, profile=SYNTH_V4)
    assert r["n_frames"] == 10008 and r["n_windows"] == 1251
    assert r["frames_differing"] == 0
    assert all(v == 0 for v in r["frames_differing_by_class"].values())
    assert r["windows_differing_all"] == 0
    assert r["windows_differing_logic_only"] == 0


def test_one_bit_flip_in_clb_minor_30_is_logic():
    ft = _frame_types()
    if ft is None:
        return
    col = next(c for c in ft.columns.values() if c.kind == "CLB")
    frame = col.first_frame + 30
    assert ft.codes[frame] == LOGIC and ft.logic_mask[frame]
    assert ft.far_map.decode(ft.far_map.far(frame)).minor == 30

    blob, truth = make_synthetic_bit(SYNTH_V4.payload_words)
    flipped = bytearray(blob)
    off = (truth["region_offset"] + truth["fdri_offset_in_region"]
           + frame * SYNTH_V4.frame_bytes + 17)
    flipped[off] ^= 0x04
    with tempfile.TemporaryDirectory() as d:
        ref = _write(d, "ref.bit", blob)
        test = _write(d, "test.bit", bytes(flipped))
        r = typed_diff(ref, test, ft, profile=SYNTH_V4)
    assert r["frames_differing"] == 1
    assert r["frames_differing_by_class"] == {"routing": 0, "logic": 1,
                                              "mixed": 0, "bram_content": 0,
                                              "pad": 0}
    assert r["windows_differing_all"] == 1
    assert r["windows_differing_logic_only"] == 1
    assert r["differing_windows_all"] == [frame // 8]
    assert r["differing_windows_logic_only"] == [frame // 8]


if __name__ == "__main__":
    test_clb_column_class_counts()
    test_clb_minor_ranges()
    test_self_diff_is_zero()
    test_one_bit_flip_in_clb_minor_30_is_logic()
    print("All frame_types tests passed.")
