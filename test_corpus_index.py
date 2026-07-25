# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for corpus_index on a synthetic mini-corpus with known
#              ground truth: exact-payload classes with alias tracking, one
#              canonical sample per unique payload (no duplicate weighting),
#              contradictory-label quarantine with full history, and
#              design/payload component merging.
#
# Usage:
#   python3 test_corpus_index.py    (or: pytest test_corpus_index.py -q)

import json
import os
import tempfile

from corpus_index import build_index
from test_bitstream_io import TEST_PROFILE, make_synthetic_bit


def _write(root, cls, name, blob):
    d = os.path.join(root, cls)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "wb") as f:
        f.write(blob)
    return path


def make_mini_corpus_valid(root):
    """Synthetic corpus with known structure. Every file must pass
    TEST_PROFILE (404 payload words), so distinct payloads of equal length
    are made by flipping one payload byte deterministically (`tag`); equal
    tags mean byte-identical payloads behind different headers.

      tag 0  : DESA_T100 benign + DESB_T200 benign + DESA_T100 malicious
               -> contradictory class, spans 2 design keys (component
               merge), 1 malicious alias quarantined
      tag 5  : DESB_T200 malicious x2 (P&R aliases) -> one canonical
               malicious sample from two files
      tag 9  : DESC_T300 benign (singleton)
      tag 13 : DESC_T300 malicious (singleton)
    """
    import struct
    from bitstream_io import SYNC_WORD, parse_bitstream

    def variant(tag, hdr):
        blob, _ = make_synthetic_bit(404, header=hdr)
        if tag == 0:
            return blob
        m = parse_bitstream(blob)
        b = m.fdri_blocks[0]
        edit = bytearray(blob)
        off = b.payload_offset_in_file + 100 + tag  # unique byte per tag
        edit[off] = (edit[off] + tag) % 256
        return bytes(edit)

    _write(root, "Benign", "DESA_T100.bit", variant(0, b"h1"))
    _write(root, "Benign", "DESB_T200.bit", variant(0, b"h2-different"))
    _write(root, "Malicious", "DESA_T100_Trojan.bit", variant(0, b"h3xx"))
    _write(root, "Malicious", "DESB_T200_Trojan.bit", variant(5, b"h4"))
    _write(root, "Malicious", "DESB_T200_Trojan_v2.bit", variant(5, b"h5abc"))
    _write(root, "Benign", "DESC_T300.bit", variant(9, b"h6"))
    _write(root, "Malicious", "DESC_T300_Trojan.bit", variant(13, b"h7"))


def test_index_on_mini_corpus():
    with tempfile.TemporaryDirectory() as root:
        data = os.path.join(root, "data")
        os.makedirs(data)
        make_mini_corpus_valid(data)
        out = os.path.join(root, "out")
        qpath = os.path.join(root, "quarantine.json")
        index, index_path, _ = build_index(data, out, qpath,
                                           profile=TEST_PROFILE, expected={})

        c = index["counts"]
        # 7 physical files, 4 unique payloads.
        assert c["n_files"] == 7 and c["unique_payloads"] == 4
        # Exactly one contradictory class; its malicious alias quarantined.
        assert c["contradictory_classes"] == 1
        assert c["quarantined_malicious"] == 1
        assert c["files_in_contradictory_classes"] == 3
        # Canonical labels: contradiction resolves to benign.
        assert c["canonical_benign"] == 2 and c["canonical_malicious"] == 2

        classes = {tuple(sorted(cl["benign_aliases"]
                                + cl["malicious_aliases"])): cl
                   for cl in index["payload_classes"]}
        contra = next(cl for cl in index["payload_classes"]
                      if cl["contradictory"])
        # Alias tracking: all three same-payload files in one class,
        # spanning both design keys.
        assert contra["n_aliases"] == 3
        assert contra["design_keys"] == ["DESA_T100", "DESB_T200"]
        assert contra["canonical_label"] == 0
        assert contra["canonical_alias"].startswith("Benign/")
        # No-duplicate-weighting: canonical alias appears exactly once per
        # class, and the two v-aliases of payload 505 collapse to one sample.
        five = next(cl for cl in index["payload_classes"]
                    if cl["n_aliases"] == 2)
        assert five["canonical_label"] == 1 and len(
            five["malicious_aliases"]) == 2

        # Component merging: the shared payload bridges DESA_T100 and
        # DESB_T200 into ONE component; DESC_T300 stays separate.
        comp_by_key = {}
        for r in index["files"]:
            comp_by_key.setdefault(r["design_key"], set()).add(
                r["component_id"])
        assert comp_by_key["DESA_T100"] == comp_by_key["DESB_T200"]
        assert comp_by_key["DESC_T300"] != comp_by_key["DESA_T100"]
        assert c["n_components"] == 2

        # Quarantine artifact: full history preserved.
        with open(qpath) as f:
            q = json.load(f)
        assert q["totals"]["quarantined_malicious_aliases"] == 1
        qc = q["classes"][0]
        assert qc["quarantined_malicious_aliases"] == \
            ["Malicious/DESA_T100_Trojan.bit"]
        assert set(qc["benign_aliases"]) == {"Benign/DESA_T100.bit",
                                             "Benign/DESB_T200.bit"}
        assert qc["retained_benign_representative"] in qc["benign_aliases"]
        assert "no_bitstream_trace" in qc["reason"]

        # Quarantined file is flagged in the file records.
        rec = next(r for r in index["files"]
                   if r["relpath"] == "Malicious/DESA_T100_Trojan.bit")
        assert rec["quarantined"]
        benign_rec = next(r for r in index["files"]
                          if r["relpath"] == "Benign/DESA_T100.bit")
        assert not benign_rec["quarantined"]


def test_index_rejects_profile_violation():
    with tempfile.TemporaryDirectory() as root:
        data = os.path.join(root, "data")
        os.makedirs(data)
        make_mini_corpus_valid(data)
        # Add one file with the wrong payload size -> the audit must fail
        # the whole build, not skip the file.
        blob, _ = make_synthetic_bit(303, header=b"bad")
        _write(data, "Malicious", "DESD_T400_Trojan.bit", blob)
        try:
            build_index(data, os.path.join(root, "out"),
                        os.path.join(root, "q.json"),
                        profile=TEST_PROFILE, expected={})
            assert False, "build should have failed the profile audit"
        except SystemExit as e:
            assert "audit FAILED" in str(e)


if __name__ == "__main__":
    test_index_on_mini_corpus()
    test_index_rejects_profile_violation()
    print("All corpus_index tests passed.")
