# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Corrected bitstream I/O for the leakage-controlled corpus
#              (Phase 0.5). Two layers, deliberately separated:
#
#              1) A GENERAL packet-derived parser (`parse_bitstream`) that
#                 DERIVES -- never assumes -- the FDRI geometry of a 7-series
#                 .bit file: sync offset, FDRI block offsets/word counts,
#                 frame divisibility, FAR writes, packet count, trailer size.
#                 It makes no claim that any of these take particular values.
#
#              2) A STRICT canonical-profile validator for the Trust-Hub V4
#                 Zynq-7020 corpus (`ZYNQ7020_V4` + `validate_profile`). The
#                 controlled dataset path calls this and FAILS on deviation.
#                 The verified V4 geometry (offset 184, 1,010,808 words,
#                 10,008 frames, one uncompressed FDRI block, one initial FAR
#                 write; see LEAKAGE_AUDIT.md) lives ONLY in the profile, not
#                 in the parser, so partial bitstreams and other devices stay
#                 supportable later.
#
#              Also home of the corrected feature extractors. They consume the
#              FDRI payload ONLY -- never the .bit ASCII header, never the
#              config preamble, never the trailer -- which removes the
#              header/file-size label channel documented in LEAKAGE_AUDIT.md.
#              The statistical vector keeps the legacy 278-dim layout for
#              schema stability (`STAT_SCHEMA`), but this is shape
#              compatibility ONLY: legacy scalers/models must never be loaded
#              with these features, which is why every cache written through
#              this module embeds a provenance record and every load fails
#              closed on mismatch (`save_versioned_npz`/`load_versioned_npz`).
#
#              train_model.py and deploy_model.py are FROZEN pre-audit
#              reference implementations; this module replaces nothing there.
#              No torch import here.

import hashlib
import json
import os
import struct
from dataclasses import dataclass, field, asdict

import numpy as np
from scipy.stats import entropy, kurtosis, skew

PARSER_VERSION = "bitstream_io_v1"
STAT_SCHEMA = "fdri_stat_278_v1"          # 256 hist + 10 stats + 12 structural
SEQ_SCHEMA = "fdri_seq4096_v1"            # 4096-byte linspace subsample
PAYLOAD_DIGEST_ALGO = "blake2b-256"

N_STAT_FEATURES = 278
SEQUENCE_LENGTH = 4096

SYNC_WORD = bytes([0xAA, 0x99, 0x55, 0x66])

# 7-series type-1 packet register addresses (UG470 table 5-23).
REG_CRC, REG_FAR, REG_FDRI, REG_FDRO, REG_CMD = 0, 1, 2, 3, 4


class BitstreamFormatError(ValueError):
    """The file does not parse as a 7-series configuration stream."""


class ProfileError(ValueError):
    """The file parses, but violates the requested canonical profile."""


class CacheSchemaError(RuntimeError):
    """A cache/artifact exists but its provenance does not match expectations."""


# ---------------------------------------------------------------------------
# General parser: derives geometry, assumes nothing about its values.
# ---------------------------------------------------------------------------
@dataclass
class FdriBlock:
    payload_word_index: int        # word index within the config region
    payload_offset_in_region: int  # bytes from region start (sync word end)
    payload_offset_in_file: int    # bytes from file start
    n_words: int
    n_bytes: int


@dataclass
class BitstreamMeta:
    filepath: str
    file_size: int
    sync_offset: int               # byte offset of the sync word
    region_offset: int             # byte offset of the config region (sync end)
    region_words: int
    n_packets: int
    fdri_blocks: list = field(default_factory=list)
    far_writes: list = field(default_factory=list)   # (word_index, value)
    trailer_bytes: int = 0         # bytes after the last FDRI payload

    @property
    def n_fdri_blocks(self):
        return len(self.fdri_blocks)

    def initial_far(self):
        """Value of the last FAR write before the first FDRI block, or None."""
        if not self.fdri_blocks:
            return None
        first = self.fdri_blocks[0].payload_word_index
        before = [v for (i, v) in self.far_writes if i < first]
        return before[-1] if before else None

    def whole_frames(self, frame_words):
        """True iff every FDRI block is an exact number of `frame_words`-word
        frames."""
        return all(b.n_words % frame_words == 0 for b in self.fdri_blocks)

    def n_frames(self, frame_words):
        return sum(b.n_words // frame_words for b in self.fdri_blocks)


def parse_bitstream(data, filepath="<bytes>"):
    """Walk the type-1/type-2 packet stream and derive the FDRI geometry.

    7-series packet encoding (UG470): a type-1 header word carries
    [31:29]=001, [28:27]=opcode, [26:13]=register, [10:0]=word count; a word
    count of 0 followed by a type-2 header ([31:29]=010) takes its 27-bit
    count from that header. Payload words are skipped as data, so register
    values occurring inside FDRI payloads are never misread as packets.
    """
    sync = data.find(SYNC_WORD)
    if sync < 0:
        raise BitstreamFormatError(f"{filepath}: no sync word")
    region_offset = sync + len(SYNC_WORD)
    region_words = (len(data) - region_offset) // 4
    words = struct.unpack_from(">%dI" % region_words, data, region_offset)

    meta = BitstreamMeta(filepath=filepath, file_size=len(data),
                         sync_offset=sync, region_offset=region_offset,
                         region_words=region_words, n_packets=0)
    i = 0
    while i < region_words:
        w = words[i]
        if (w >> 29) != 1:             # NOP, pad, or orphan type-2: not a packet start
            i += 1
            continue
        opcode = (w >> 27) & 0x3
        reg = (w >> 13) & 0x3FFF
        count = w & 0x7FF
        payload_i = i + 1
        if count == 0 and payload_i < region_words and (words[payload_i] >> 29) == 2:
            count = words[payload_i] & 0x07FFFFFF
            payload_i += 1
        meta.n_packets += 1
        if opcode == 2:                # write
            if reg == REG_FAR and count >= 1:
                meta.far_writes.append((i, words[payload_i]))
            elif reg == REG_FDRI:
                meta.fdri_blocks.append(FdriBlock(
                    payload_word_index=payload_i,
                    payload_offset_in_region=payload_i * 4,
                    payload_offset_in_file=region_offset + payload_i * 4,
                    n_words=count,
                    n_bytes=count * 4))
        i = payload_i + count

    if meta.fdri_blocks:
        last = meta.fdri_blocks[-1]
        meta.trailer_bytes = len(data) - (last.payload_offset_in_file + last.n_bytes)
    return meta


def parse_fdri(filepath):
    """Parse a .bit file from disk; returns BitstreamMeta."""
    with open(filepath, "rb") as f:
        return parse_bitstream(f.read(), filepath=filepath)


# ---------------------------------------------------------------------------
# Strict canonical profile for the Trust-Hub V4 / Zynq-7020 corpus.
# Values here were independently verified (LEAKAGE_AUDIT.md, finding 1) and
# are properties of THIS corpus, not of 7-series bitstreams in general.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CanonicalProfile:
    name: str
    fdri_offset_in_region: int
    payload_words: int
    frame_words: int
    n_fdri_blocks: int
    initial_far: int

    @property
    def frame_bytes(self):
        return self.frame_words * 4

    @property
    def payload_bytes(self):
        return self.payload_words * 4

    @property
    def n_frames(self):
        return self.payload_words // self.frame_words


ZYNQ7020_V4 = CanonicalProfile(
    name="zynq7020_trusthub_v4",
    fdri_offset_in_region=184,
    payload_words=1010808,        # = 101 words x 10,008 frames = 4,043,232 B
    frame_words=101,              # 404 bytes per frame
    n_fdri_blocks=1,              # single uncompressed block
    initial_far=0x00000000,       # one FAR write before the data, auto-increment
)
assert ZYNQ7020_V4.payload_bytes == 4043232 and ZYNQ7020_V4.n_frames == 10008


def validate_profile(meta, profile=ZYNQ7020_V4):
    """Assert `meta` matches the canonical profile; raise ProfileError listing
    every deviation. The controlled dataset path must go through this."""
    problems = []
    if meta.n_fdri_blocks != profile.n_fdri_blocks:
        problems.append(f"{meta.n_fdri_blocks} FDRI blocks "
                        f"(expected {profile.n_fdri_blocks})")
    if meta.fdri_blocks:
        b = meta.fdri_blocks[0]
        if b.payload_offset_in_region != profile.fdri_offset_in_region:
            problems.append(f"FDRI payload at region offset "
                            f"{b.payload_offset_in_region} "
                            f"(expected {profile.fdri_offset_in_region})")
        if b.n_words != profile.payload_words:
            problems.append(f"{b.n_words} payload words "
                            f"(expected {profile.payload_words})")
        if b.n_words % profile.frame_words != 0:
            problems.append(f"payload is not whole {profile.frame_words}-word "
                            f"frames")
        first = b.payload_word_index
        n_far_before = sum(1 for (i, _) in meta.far_writes if i < first)
        if n_far_before != 1:
            problems.append(f"{n_far_before} FAR writes before the FDRI block "
                            f"(expected 1, auto-increment)")
        elif meta.initial_far() != profile.initial_far:
            problems.append(f"initial FAR 0x{meta.initial_far():08x} "
                            f"(expected 0x{profile.initial_far:08x})")
    if problems:
        raise ProfileError(f"{meta.filepath}: violates profile "
                           f"'{profile.name}': " + "; ".join(problems))
    return meta


# ---------------------------------------------------------------------------
# Payload access + digest.
# ---------------------------------------------------------------------------
def fdri_payload_and_meta(filepath, profile=ZYNQ7020_V4):
    """(payload uint8 array, BitstreamMeta). Validates against `profile`
    unless profile is None (general-parser mode)."""
    with open(filepath, "rb") as f:
        data = f.read()
    meta = parse_bitstream(data, filepath=filepath)
    if profile is not None:
        validate_profile(meta, profile)
    if not meta.fdri_blocks:
        raise BitstreamFormatError(f"{filepath}: no FDRI write found")
    b = meta.fdri_blocks[0]
    arr = np.frombuffer(data, dtype=np.uint8,
                        count=b.n_bytes, offset=b.payload_offset_in_file)
    return arr, meta


def fdri_payload(filepath, profile=ZYNQ7020_V4):
    """FDRI configuration payload as a uint8 array. Offset 0 of this array is
    the first byte of the first configuration frame."""
    return fdri_payload_and_meta(filepath, profile)[0]


def payload_hash(filepath_or_array, profile=ZYNQ7020_V4):
    """BLAKE2b-256 digest of the FDRI payload (config data only; the .bit
    ASCII header and packet preamble/trailer never enter the digest)."""
    if isinstance(filepath_or_array, np.ndarray):
        arr = filepath_or_array
    else:
        arr = fdri_payload(filepath_or_array, profile)
    return hashlib.blake2b(arr.tobytes(), digest_size=32).hexdigest()


# ---------------------------------------------------------------------------
# Corrected feature extractors: FDRI payload only.
# ---------------------------------------------------------------------------
def statistical_features_from_bytes(arr):
    """The legacy 278-dim statistical vector computed over `arr`.

    Mirrors the frozen train_model.extract_statistical_features layout
    byte-for-byte in SEMANTICS (histogram share, 10 stats, 12 structural),
    but over whatever array it is given -- the caller passes the FDRI payload,
    never whole-file bytes. Under a fixed-length profile `log_size` becomes a
    constant; it is retained for schema stability (a train-fit scaler zeroes
    it) rather than dropped, keeping the 278 layout intact.
    """
    size = len(arr)
    if size == 0:
        return np.zeros(N_STAT_FEATURES)

    counts = np.bincount(arr, minlength=256)
    byte_hist = counts / size

    byte_entropy = entropy(byte_hist + 1e-10)
    stats = np.array([
        byte_entropy, np.mean(arr), np.std(arr),
        skew(arr) if size > 2 else 0.0,
        kurtosis(arr) if size > 3 else 0.0,
        np.min(arr), np.max(arr), np.median(arr),
        np.sum(arr == 0) / size, np.sum(arr == 255) / size,
    ])

    log_size = np.log1p(size)
    chunk_size = max(1, size // 4)
    chunks = [arr[i * chunk_size:(i + 1) * chunk_size] for i in range(4)]
    chunk_means = [np.mean(c) if len(c) > 0 else 0.0 for c in chunks]
    chunk_stds = [np.std(c) if len(c) > 0 else 0.0 for c in chunks]

    diff = np.diff(arr.astype(np.int16))
    transition_rate = np.sum(diff != 0) / max(1, len(diff))
    avg_transition_mag = np.mean(np.abs(diff)) if len(diff) > 0 else 0.0

    nibble_balance = np.mean((arr >> 4) & 0x0F) - np.mean(arr & 0x0F)

    structural = np.array([log_size, transition_rate, avg_transition_mag,
                           nibble_balance] + chunk_means + chunk_stds)
    return np.concatenate([byte_hist, stats, structural])


def extract_statistical_features_fdri(filepath, profile=ZYNQ7020_V4):
    """278-dim statistical features over the FDRI payload only (STAT_SCHEMA)."""
    return statistical_features_from_bytes(fdri_payload(filepath, profile))


def byte_sequence_from_bytes(arr, seq_length=SEQUENCE_LENGTH):
    """Legacy fixed-length subsample (linspace stride / zero-pad), over `arr`."""
    if len(arr) == 0:
        return np.zeros(seq_length, dtype=np.int64)
    if len(arr) > seq_length:
        idx = np.linspace(0, len(arr) - 1, seq_length, dtype=int)
        seq = arr[idx]
    else:
        seq = np.zeros(seq_length, dtype=np.uint8)
        seq[:len(arr)] = arr
    return seq.astype(np.int64)


def extract_byte_sequence_fdri(filepath, seq_length=SEQUENCE_LENGTH,
                               profile=ZYNQ7020_V4):
    """Fixed-length byte sequence over the FDRI payload only (SEQ_SCHEMA)."""
    return byte_sequence_from_bytes(fdri_payload(filepath, profile), seq_length)


# ---------------------------------------------------------------------------
# Fail-closed cache provenance.
# ---------------------------------------------------------------------------
_PROVENANCE_KEY = "__provenance_json__"


def save_versioned_npz(path, provenance, **arrays):
    """Write arrays plus a provenance record. `provenance` is a flat dict of
    strings/numbers (extractor schema, parser version, manifest id, ...)."""
    payload = dict(provenance)
    payload.setdefault("parser_version", PARSER_VERSION)
    np.savez_compressed(path, **arrays,
                        **{_PROVENANCE_KEY: np.array(json.dumps(payload,
                                                                sort_keys=True))})


def load_versioned_npz(path, expected):
    """Load a versioned cache; FAIL CLOSED unless every key in `expected`
    is present in the stored provenance with an identical value."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as z:
        if _PROVENANCE_KEY not in z:
            raise CacheSchemaError(f"{path}: no provenance record -- refusing "
                                   f"to load (legacy/unversioned cache)")
        stored = json.loads(str(z[_PROVENANCE_KEY]))
        mismatches = [f"{k}: stored={stored.get(k)!r} expected={v!r}"
                      for k, v in expected.items() if stored.get(k) != v]
        if mismatches:
            raise CacheSchemaError(f"{path}: provenance mismatch -- "
                                   + "; ".join(mismatches))
        return {k: z[k] for k in z.files if k != _PROVENANCE_KEY}, stored


def file_sha256(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(bufsize):
            h.update(chunk)
    return h.hexdigest()
