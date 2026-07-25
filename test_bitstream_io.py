# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for bitstream_io -- the parser must DERIVE geometry from
#              synthetic packet streams with known ground truth; the strict V4
#              profile must accept the canonical corpus and reject deviations;
#              corrected features must depend on the FDRI payload ONLY (same
#              payload + different header/trailer => identical features); and
#              versioned caches must fail closed on any provenance mismatch.
#
# Usage:
#   python3 test_bitstream_io.py    (or: pytest test_bitstream_io.py -q)

import glob
import os
import struct
import tempfile

import numpy as np

from bitstream_io import (CacheSchemaError, CanonicalProfile, ProfileError,
                          SYNC_WORD, ZYNQ7020_V4, byte_sequence_from_bytes,
                          extract_byte_sequence_fdri,
                          extract_statistical_features_fdri, fdri_payload,
                          fdri_payload_and_meta, load_versioned_npz,
                          parse_bitstream, payload_hash, save_versioned_npz,
                          statistical_features_from_bytes, validate_profile)

NOP = 0x20000000
TYPE1_WRITE = lambda reg, count: (1 << 29) | (2 << 27) | (reg << 13) | count
TYPE2 = lambda count: (2 << 29) | count

# Small synthetic profile: same 101-word frame as 7-series, 4 frames. FDRI
# payload offset = (4 NOPs + 2 FAR + 2 CMD + 2 FDRI headers) * 4 = 40 bytes.
TEST_PROFILE = CanonicalProfile(name="synthetic_test", fdri_offset_in_region=40,
                                payload_words=404, frame_words=101,
                                n_fdri_blocks=1, initial_far=0x0)


def make_synthetic_bit(payload_words, header=b"HDR-JUNK-\x00\x01",
                       far_value=0x0, trailer_words=(NOP, NOP),
                       trailer_tail=b"", extra_block_words=0,
                       preamble_nops=4):
    """Build a minimal .bit-like blob with a known packet structure.

    Layout after the sync word: `preamble_nops` NOPs, one FAR write, one CMD
    write, then FDRI as type-1(count=0) + type-2(count) + payload, then
    trailer words and raw tail bytes. With preamble_nops=4 the FDRI payload
    starts at region offset (4+2+2+2)*4 = 40 -- but the parser must DERIVE
    that; ground truth is returned alongside the blob for comparison.
    """
    rng = np.random.default_rng(payload_words)
    payload = rng.integers(0, 2 ** 32, size=payload_words, dtype=np.uint64)
    payload = payload.astype(np.uint32)

    words = [NOP] * preamble_nops
    words += [TYPE1_WRITE(1, 1), far_value]            # FAR write
    words += [TYPE1_WRITE(4, 1), 0x1]                  # CMD WCFG
    words += [TYPE1_WRITE(2, 0), TYPE2(payload_words)] # FDRI via type-2
    fdri_word_index = len(words)
    words += list(payload)
    if extra_block_words:
        extra = rng.integers(0, 2 ** 32, size=extra_block_words,
                             dtype=np.uint64).astype(np.uint32)
        words += [TYPE1_WRITE(2, extra_block_words)] + list(extra)
    words += list(trailer_words)

    blob = header + SYNC_WORD + struct.pack(">%dI" % len(words), *words) \
        + trailer_tail
    truth = {"sync_offset": len(header),
             "region_offset": len(header) + 4,
             "fdri_offset_in_region": fdri_word_index * 4,
             "payload_words": payload_words,
             "payload_bytes": payload_words * 4,
             "payload": payload,
             "far_value": far_value}
    return blob, truth


def test_parser_derives_geometry():
    blob, truth = make_synthetic_bit(404)
    m = parse_bitstream(blob)
    assert m.sync_offset == truth["sync_offset"]
    assert m.region_offset == truth["region_offset"]
    assert m.n_fdri_blocks == 1
    b = m.fdri_blocks[0]
    assert b.payload_offset_in_region == truth["fdri_offset_in_region"]
    assert b.n_words == truth["payload_words"]
    assert b.n_bytes == truth["payload_bytes"]
    assert m.initial_far() == truth["far_value"]
    assert m.whole_frames(101) and m.n_frames(101) == 4
    # Payload bytes recovered exactly.
    got = blob[b.payload_offset_in_file:b.payload_offset_in_file + b.n_bytes]
    assert got == truth["payload"].byteswap().tobytes() or \
        got == struct.pack(">404I", *truth["payload"])


def test_parser_is_not_fooled_by_payload_contents():
    """A word that LOOKS like an FDRI header inside the payload must be
    skipped as data (the packet walk consumes payload words)."""
    blob, truth = make_synthetic_bit(404)
    m0 = parse_bitstream(blob)
    b = m0.fdri_blocks[0]
    # Overwrite a payload word with the FDRI type-1 header pattern.
    poison = bytearray(blob)
    off = b.payload_offset_in_file + 40 * 4
    poison[off:off + 4] = struct.pack(">I", (1 << 29) | (2 << 27) | (2 << 13))
    m1 = parse_bitstream(bytes(poison))
    assert m1.n_fdri_blocks == 1
    assert m1.fdri_blocks[0].n_words == truth["payload_words"]


def test_parser_counts_multiple_blocks():
    blob, _ = make_synthetic_bit(404, extra_block_words=202)
    m = parse_bitstream(blob)
    assert m.n_fdri_blocks == 2
    assert [b.n_words for b in m.fdri_blocks] == [404, 202]
    assert m.whole_frames(101) and m.n_frames(101) == 6


def test_profile_accepts_and_rejects():
    blob, _ = make_synthetic_bit(404)
    validate_profile(parse_bitstream(blob), TEST_PROFILE)  # accepts

    # Wrong payload size.
    blob2, _ = make_synthetic_bit(303)
    try:
        validate_profile(parse_bitstream(blob2), TEST_PROFILE)
        assert False, "should have rejected wrong word count"
    except ProfileError as e:
        assert "payload words" in str(e)

    # Second FDRI block.
    blob3, _ = make_synthetic_bit(404, extra_block_words=101)
    try:
        validate_profile(parse_bitstream(blob3), TEST_PROFILE)
        assert False, "should have rejected multi-block"
    except ProfileError as e:
        assert "FDRI blocks" in str(e)

    # Wrong initial FAR.
    blob4, _ = make_synthetic_bit(404, far_value=0x1234)
    try:
        validate_profile(parse_bitstream(blob4), TEST_PROFILE)
        assert False, "should have rejected wrong FAR"
    except ProfileError as e:
        assert "FAR" in str(e)


def test_features_consume_payload_only():
    """Same payload behind different headers/trailers => identical digest,
    statistical features, and byte sequence. Different payload => different."""
    blob_a, _ = make_synthetic_bit(404, header=b"A" * 50)
    blob_b, _ = make_synthetic_bit(404, header=b"BBBB" * 40,
                                   trailer_tail=b"\xff" * 999)
    blob_c, _ = make_synthetic_bit(505, header=b"A" * 50)  # different payload

    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for name, blob in (("a", blob_a), ("b", blob_b), ("c", blob_c)):
            paths[name] = os.path.join(d, name + ".bit")
            with open(paths[name], "wb") as f:
                f.write(blob)
        pa = fdri_payload(paths["a"], profile=TEST_PROFILE)
        pb = fdri_payload(paths["b"], profile=TEST_PROFILE)
        assert np.array_equal(pa, pb)
        assert payload_hash(paths["a"], TEST_PROFILE) == \
            payload_hash(paths["b"], TEST_PROFILE)
        fa = extract_statistical_features_fdri(paths["a"], TEST_PROFILE)
        fb = extract_statistical_features_fdri(paths["b"], TEST_PROFILE)
        assert fa.shape == (278,) and np.array_equal(fa, fb)
        sa = extract_byte_sequence_fdri(paths["a"], profile=TEST_PROFILE)
        sb = extract_byte_sequence_fdri(paths["b"], profile=TEST_PROFILE)
        assert np.array_equal(sa, sb)

        pc = fdri_payload(paths["c"], profile=None)
        assert payload_hash(pc) != payload_hash(pa)


def test_stat_features_match_frozen_semantics():
    """statistical_features_from_bytes must reproduce the FROZEN
    train_model.extract_statistical_features transform exactly when both see
    the same bytes (train_model reads a whole file; we hand it a file that IS
    the payload). Skipped when torch isn't importable."""
    try:
        import train_model as tm
    except Exception:
        print("(frozen-semantics cross-check skipped: torch unavailable)")
        return
    rng = np.random.default_rng(7)
    arr = rng.integers(0, 256, size=101 * 4 * 6 + 13, dtype=np.uint8)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(arr.tobytes())
        tmp = f.name
    try:
        legacy = tm.extract_statistical_features(tmp)
        new = statistical_features_from_bytes(arr)
        assert np.allclose(legacy, new, rtol=0, atol=1e-12)
    finally:
        os.unlink(tmp)


def test_sequence_matches_frozen_semantics():
    rng = np.random.default_rng(11)
    arr = rng.integers(0, 256, size=9999, dtype=np.uint8)
    seq = byte_sequence_from_bytes(arr, seq_length=4096)
    idx = np.linspace(0, len(arr) - 1, 4096, dtype=int)
    assert np.array_equal(seq, arr[idx].astype(np.int64))
    short = byte_sequence_from_bytes(arr[:10], seq_length=64)
    assert short.shape == (64,) and (short[10:] == 0).all()


def test_cache_fails_closed():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "cache.npz")
        prov = {"extractor_schema": "fdri_stat_278_v1", "manifest_id": "m123"}
        save_versioned_npz(path, prov, X=np.arange(6).reshape(2, 3))

        arrays, stored = load_versioned_npz(path, expected=prov)
        assert np.array_equal(arrays["X"], np.arange(6).reshape(2, 3))
        assert stored["parser_version"]

        # Mismatched schema id -> reject.
        try:
            load_versioned_npz(path, expected={"extractor_schema": "legacy_278"})
            assert False, "should have rejected schema mismatch"
        except CacheSchemaError as e:
            assert "extractor_schema" in str(e)
        # Extra expectation the cache lacks -> reject.
        try:
            load_versioned_npz(path, expected={**prov, "split_schema": "x"})
            assert False, "should have rejected missing key"
        except CacheSchemaError:
            pass
        # Unversioned legacy cache -> reject.
        legacy = os.path.join(d, "legacy.npz")
        np.savez_compressed(legacy, X=np.zeros(3))
        try:
            load_versioned_npz(legacy, expected={})
            assert False, "should have rejected unversioned cache"
        except CacheSchemaError:
            pass


def _find_real_bitstream():
    for d in [os.environ.get("BLADEI_DATA_DIR", ""),
              os.path.expanduser("~/Desktop/Karakchi-Research/trusthub_bitstreams_v4")]:
        hits = sorted(glob.glob(os.path.join(d, "Benign", "*.bit"))) if d else []
        if hits:
            return hits[0]
    return None


def test_real_v4_bitstream_integration():
    """Canonical V4 integration: a real corpus file must pass the strict
    profile with the independently verified geometry (LEAKAGE_AUDIT.md)."""
    fp = _find_real_bitstream()
    if fp is None:
        print("(V4 integration test skipped: no real bitstream found)")
        return
    arr, meta = fdri_payload_and_meta(fp, profile=ZYNQ7020_V4)
    b = meta.fdri_blocks[0]
    assert b.payload_offset_in_region == 184
    assert b.n_words == 1010808 and b.n_bytes == 4043232
    assert len(arr) == 4043232
    assert meta.whole_frames(101) and meta.n_frames(101) == 10008
    assert meta.n_fdri_blocks == 1 and meta.initial_far() == 0
    # Frame 0 begins at payload byte 0 == file offset region+184.
    with open(fp, "rb") as f:
        raw = f.read()
    assert raw[b.payload_offset_in_file:b.payload_offset_in_file + 16] == \
        arr[:16].tobytes()


if __name__ == "__main__":
    test_parser_derives_geometry()
    test_parser_is_not_fooled_by_payload_contents()
    test_parser_counts_multiple_blocks()
    test_profile_accepts_and_rejects()
    test_features_consume_payload_only()
    test_stat_features_match_frozen_semantics()
    test_sequence_matches_frozen_semantics()
    test_cache_fails_closed()
    test_real_v4_bitstream_integration()
    print("All bitstream_io tests passed.")
