# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for far_map -- the frame order must follow block type,
#              half, row, column, minor with 2 pad frames per row, checked on a
#              synthetic part.yaml with known ground truth; against the pinned
#              prjxray-db it must reproduce the V4 geometry (10,008 frames =
#              9,996 config + 12 pad), the per-row frame counts, exact
#              frame <-> FAR round-trips, and the anchor observed in our .ll
#              files (frame 2043 <-> FAR 0x00001d1f). Database tests are
#              skipped with a message when the db has not been downloaded.
#
# Usage:
#   python3 test_far_map.py    (or: pytest test_far_map.py -q)

import os
import tempfile

from far_map import PART_YAML, FarMap, decode_far, encode_far

# Custom tags left in, BLOCK_RAM listed before CLB_IO_CLK, and a bus the map
# must ignore: the order must come from the rules, not from file order.
SYNTHETIC_PART_YAML = """\
!<xilinx/xc7series/part>
idcode: 0x3727093
global_clock_regions:
  top: !<xilinx/xc7series/global_clock_region>
    rows:
      0: !<xilinx/xc7series/row>
        configuration_buses:
          BLOCK_RAM: !<xilinx/xc7series/configuration_bus>
            configuration_columns:
              0: !<xilinx/xc7series/configuration_column>
                frame_count: 3
          CLB_IO_CLK: !<xilinx/xc7series/configuration_bus>
            configuration_columns:
              0: !<xilinx/xc7series/configuration_column>
                frame_count: 2
              1: !<xilinx/xc7series/configuration_column>
                frame_count: 4
          CFG_CLB: !<xilinx/xc7series/configuration_bus>
            configuration_columns:
              0: !<xilinx/xc7series/configuration_column>
                frame_count: 9
  bottom: !<xilinx/xc7series/global_clock_region>
    rows:
      0: !<xilinx/xc7series/row>
        configuration_buses:
          CLB_IO_CLK: !<xilinx/xc7series/configuration_bus>
            configuration_columns:
              0: !<xilinx/xc7series/configuration_column>
                frame_count: 1
"""


def test_synthetic_order_and_pads():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, PART_YAML)
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as fh:
            fh.write(SYNTHETIC_PART_YAML)
        m = FarMap.load(d)

    expected = (
        [encode_far(0, 0, 0, 0, k) for k in range(2)]
        + [encode_far(0, 0, 0, 1, k) for k in range(4)] + [None, None]
        + [encode_far(0, 1, 0, 0, 0)] + [None, None]
        + [encode_far(1, 0, 0, 0, k) for k in range(3)] + [None, None])
    assert m.n_frames == len(expected) == 16
    for i, far in enumerate(expected):
        assert m.is_pad(i) == (far is None)
        if far is not None:
            assert m.far(i) == far and m.frame(far) == i
    assert m.far(8) == 0x00400000 and m.far(11) == 0x00800000
    assert m.ignored_buses == ("CFG_CLB",)
    try:
        m.far(6)
        assert False, "pad frame must not have a FAR"
    except ValueError:
        pass


def test_encode_decode():
    far = encode_far(1, 1, 2, 57, 127)
    f = decode_far(far)
    assert (f.block_type, f.half, f.row, f.column, f.minor) == (1, 1, 2, 57, 127)
    for bad in ((0, 0, 0, 0, 128), (0, 2, 0, 0, 0), (0, 0, 0, 1024, 0)):
        try:
            encode_far(*bad)
            assert False, "out-of-range field must be rejected"
        except ValueError:
            pass


def _load_or_skip(name):
    try:
        return FarMap.load()
    except FileNotFoundError as e:
        print("(%s skipped: prjxray-db not downloaded -- run "
              "fetch_prjxray_db.py; %s)" % (name, e))
        return None


def test_total_frames():
    m = _load_or_skip("total frames")
    if m is None:
        return
    n_pad = sum(m.is_pad(i) for i in range(m.n_frames))
    assert m.n_frames == 10008, m.n_frames
    assert n_pad == 12, n_pad
    assert m.n_frames - n_pad == 9996


def test_per_row_counts():
    m = _load_or_skip("per-row counts")
    if m is None:
        return
    counts = m.row_counts()
    rows = sorted({(h, r) for (_, h, r) in counts})
    assert rows, "no rows"
    for h, r in rows:
        assert counts.get((0, h, r)) == 2564, ((h, r), counts.get((0, h, r)))
        assert counts.get((1, h, r)) == 768, ((h, r), counts.get((1, h, r)))
    assert set(counts) == {(b, h, r) for b in (0, 1) for (h, r) in rows}


def test_round_trip():
    m = _load_or_skip("round trip")
    if m is None:
        return
    n_config = 0
    for i in range(m.n_frames):
        if m.is_pad(i):
            continue
        far = m.far(i)
        assert m.frame(far) == i
        f = m.decode(far)
        assert encode_far(f.block_type, f.half, f.row, f.column, f.minor) == far
        n_config += 1
    assert n_config == 9996


def test_known_anchor():
    """From the .ll: 'Bit 6604003 0x00001d1f 1027 Block=SLICE_X92Y116'
    -> frame (6604003 - 1027) / 3232 = 2043."""
    m = _load_or_skip("known anchor")
    if m is None:
        return
    assert (6604003 - 1027) % 3232 == 0 and (6604003 - 1027) // 3232 == 2043
    assert m.far(2043) == 0x00001d1f
    assert m.frame(0x00001d1f) == 2043
    f = m.decode(0x00001d1f)
    assert (f.block_type, f.half, f.row, f.column, f.minor) == (0, 0, 0, 58, 31)


if __name__ == "__main__":
    test_synthetic_order_and_pads()
    test_encode_decode()
    test_total_frames()
    test_per_row_counts()
    test_round_trip()
    test_known_anchor()
    print("All far_map tests passed.")
