# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for tile_decode -- a feature bit poked into a synthetic
#              frame buffer (byte position computed here by hand, big-endian
#              words) must decode back as that feature / LUT INIT bit, with
#              "!" bits, the HCLK word and a neighbour tile's words respected;
#              the pinned segbits for every CLB tile type must hold 8 LUTs of
#              64 INIT bits; and a bitstream compared with itself must flag
#              nothing.
#
#              The read-back test needs no prjxray-db; the others skip with
#              a message when the cache is absent.
#
# Usage:
#   python3 test_tile_decode.py    (or: pytest test_tile_decode.py -q)

import os
import tempfile

import numpy as np

from far_map import FarMap, encode_far
from test_bitstream_io import make_synthetic_bit
from test_frame_types import SYNTH_V4
from tile_decode import (CLB_TILE_TYPES, HCLK_WORD, Segbits, Tile,
                         TileDecoder, compare, decode_tile, payload_words,
                         tile_rows)

FRAME_WORDS = 101
FRAME_BYTES = FRAME_WORDS * 4

_DEC = []


def _decoder():
    if not _DEC:
        try:
            _DEC.append(TileDecoder.load())
        except FileNotFoundError as e:
            print("(tile_decode db tests skipped: %s)" % e)
            _DEC.append(None)
    return _DEC[0]


def _poke(buf, frame, word, bit):
    """Set bit `bit` (0 = LSB) of big-endian word `word` in frame `frame`."""
    buf[frame * FRAME_BYTES + word * 4 + 3 - bit // 8] |= 1 << (bit % 8)


def test_feature_bit_reads_back():
    base = encode_far(0, 0, 3, 7, 0)
    fm = FarMap([None, None] + [base + m for m in range(36)])  # 2 pads first
    tile = Tile("CLBLM_L_TEST", "CLBLM_L", base, offset=48, n_frames=36)
    seg = Segbits("CLBLM_L",
                  luts={"SLICEM_X0.ALUT": {i: (26 + i % 2, 63 - i)
                                           for i in range(64)}},
                  features={"SLICEM_X0.AFF.ZINI": ((31, 3, 1),),
                            "SLICEM_X0.AFF.ZRST": ((30, 12, 1), (30, 45, 0))})
    frames = [fm.frame(base + m) for m in range(36)]
    assert frames[0] == 2 and frames[35] == 37

    buf = np.zeros(fm.n_frames * FRAME_BYTES, dtype=np.uint8)
    _poke(buf, frames[31], 48, 3)              # AFF.ZINI  31_03
    _poke(buf, frames[30], 48, 12)             # AFF.ZRST  30_12 (needs !30_45)
    _poke(buf, frames[27], 48 + 1, 40 % 32)    # INIT[23] -> 27_40: word+1
    # Noise the tile must not see: HCLK word, the neighbour tile, other frames.
    _poke(buf, frames[30], HCLK_WORD, 13)
    _poke(buf, frames[31], 46, 3)
    _poke(buf, 0, 48, 3)

    words = payload_words(buf, fm.n_frames, FRAME_WORDS)
    luts, active = decode_tile(tile_rows(words, frames, tile.offset), seg)
    assert luts == {"SLICEM_X0.ALUT": 1 << 23}
    assert active == {"SLICEM_X0.AFF.ZINI", "SLICEM_X0.AFF.ZRST"}

    _poke(buf, frames[30], 48 + 1, 45 % 32)    # 30_45 set: ZRST now off
    words = payload_words(buf, fm.n_frames, FRAME_WORDS)
    _, active = decode_tile(tile_rows(words, frames, tile.offset), seg)
    assert active == {"SLICEM_X0.AFF.ZINI"}


def test_segbits_have_eight_full_luts():
    dec = _decoder()
    if dec is None:
        return
    assert set(dec.segbits) == set(CLB_TILE_TYPES)
    for t, seg in dec.segbits.items():
        assert seg.check() == [], (t, seg.check())
    assert dec.tiles and {t.tile_type for t in dec.tiles} == \
        set(CLB_TILE_TYPES)


def test_self_compare_flags_nothing():
    dec = _decoder()
    if dec is None:
        return
    blob, _ = make_synthetic_bit(SYNTH_V4.payload_words)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "a.bit")
        with open(path, "wb") as fh:
            fh.write(blob)
        r = compare(path, path, dec, profile=SYNTH_V4)
    assert r["tiles_checked"] == len(dec.tiles) > 0
    assert r["logic_tiles_changed"] == 0
    assert r["flagged"] == [] and r["changed_tiles"] == {}
    assert all(n == 0 for n in r["lut_classes"].values())


if __name__ == "__main__":
    test_feature_bit_reads_back()
    test_segbits_have_eight_full_luts()
    test_self_compare_flags_nothing()
    print("All tile_decode tests passed.")
