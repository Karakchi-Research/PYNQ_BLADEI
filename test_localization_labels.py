# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Validation for the Phase 0.5C-L1 localization labels. Checks
#              the frame-index derivation on synthetic .ll input, the window
#              aggregation rule, and -- on the real AES-T1000 corpus -- the
#              three properties that make the dataset usable:
#                (1) BENIGN SPECIFICITY: zero trojan-confirmed frames in every
#                    matched benign build (the discriminative-pattern control);
#                (2) CONTAINMENT: every confirmed-trojan frame lies inside the
#                    matched-pair frame difference;
#                (3) PLACEMENT VARIATION: at least two configurations place
#                    the trojan in disjoint frame sets, so the corpus is not a
#                    single fixed location a model could memorize.
#
# Usage:
#   python3 test_localization_labels.py  (or: pytest test_localization_labels.py -q)

import csv
import json
import os
import tempfile

from localization_labels import (HOST_OCCUPIED, NO_LL_COVERAGE,
                                 TROJAN_CONFIRMED, _pat_to_re, label_frames,
                                 parse_ll, windows_from_frames)

CORPUS = os.path.join("localization_corpus", "localization_manifest.json")


def _write_ll(path, lines):
    with open(path, "w") as f:
        f.write("Revision 3\n; synthetic\n")
        for ln in lines:
            f.write(ln + "\n")


def test_frame_index_derivation():
    """frame_index = (bit - frame_bit) / 3232, and non-divisible input is a
    hard error rather than a silently wrong label."""
    res = [_pat_to_re("*Trojan*")]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.ll")
        # frame 5 -> bit 5*3232 + 100 = 16260 ; frame 9 -> 29088 + 7 = 29095
        _write_ll(p, [
            "Bit 16260 0x00000001  100 Block=SLICE_X0Y0 Latch=AQ Net=Trojan/x",
            "Bit 29095 0x00000002    7 Block=SLICE_X1Y1 Latch=BQ Net=host/y",
        ])
        frames, tbits, n = parse_ll(p, res)
        assert n == 2
        assert frames[5]["trojan"] == 1 and frames[9]["host"] == 1
        assert tbits[0]["frame"] == 5 and tbits[0]["net"] == "Trojan/x"

        bad = os.path.join(d, "b.ll")
        _write_ll(bad, ["Bit 1001 0x1 3 Block=SLICE_X0Y0 Net=host/z"])
        try:
            parse_ll(bad, res)
            assert False, "must reject non-frame-aligned .ll"
        except AssertionError as e:
            assert "not frame-grid aligned" in str(e)


def test_pattern_matching_is_anchored_glob():
    r = _pat_to_re("*Tj_Trig*")
    assert r.match("Tj_Trigger/Tj_Trig") and r.match("a/Tj_Trig/b")
    assert not r.match("TjTrig")
    assert _pat_to_re("*lfsr*").match("Trojan/lfsr_reg[3]")


def test_labels_and_window_aggregation():
    frames = {0: {"trojan": 0, "host": 4},      # window 0
              9: {"trojan": 2, "host": 1},      # window 1 -> trojan
              20: {"trojan": 0, "host": 3}}     # window 2
    labels = label_frames(frames, 24)
    assert labels[0] == HOST_OCCUPIED
    assert labels[9] == TROJAN_CONFIRMED
    assert labels[1] == NO_LL_COVERAGE
    wins = windows_from_frames(labels, window_frames=8)
    assert len(wins) == 3
    assert wins[0]["label"] == HOST_OCCUPIED
    assert wins[1]["label"] == TROJAN_CONFIRMED and wins[1]["n_trojan_frames"] == 1
    assert wins[2]["label"] == HOST_OCCUPIED
    # A window is trojan if ANY constituent frame is.
    assert wins[1]["first_frame"] == 8


def _load_corpus():
    if not os.path.exists(CORPUS):
        return None
    with open(CORPUS) as f:
        return json.load(f)


def test_real_corpus_benign_specificity():
    """The control that makes the labels trustworthy: the trojan patterns
    must never fire in a matched benign build."""
    m = _load_corpus()
    if m is None:
        print("(skipped: no localization corpus built)")
        return
    n_checked = 0
    for b in m["builds"]:
        benign = b.get("TjFree")
        if not benign:
            continue
        n_checked += 1
        assert benign["n_frames_trojan_confirmed"] == 0, (
            f"{b['config']}: benign build reports "
            f"{benign['n_frames_trojan_confirmed']} trojan frames -- the "
            f"patterns are not discriminative")
    assert n_checked >= 3


def test_real_corpus_containment_and_variation():
    m = _load_corpus()
    if m is None:
        print("(skipped: no localization corpus built)")
        return
    placements = set()
    for b in m["builds"]:
        mal = b.get("TjIn")
        if not mal:
            continue
        tro = mal["frames_trojan_confirmed"]
        assert tro, f"{b['config']}: malicious build has no trojan frames"
        # every confirmed frame is inside the matched-pair difference
        diag = b.get("matched_pair_diff_diagnostic")
        if diag:
            assert not diag["trojan_confirmed_frames_outside_diff"], (
                f"{b['config']}: confirmed-trojan frames outside the "
                f"matched-pair diff: "
                f"{diag['trojan_confirmed_frames_outside_diff']}")
        # frames are inside the device grid
        assert all(0 <= f < m["frame_grid"]["n_frames"] for f in tro)
        placements.add(tuple(tro))
    assert len(placements) >= 2, (
        "all configurations place the trojan identically -- the corpus "
        "offers a single memorizable location")


def test_label_files_match_manifest():
    m = _load_corpus()
    if m is None:
        print("(skipped: no localization corpus built)")
        return
    lab_dir = os.path.join("localization_corpus", "labels")
    for b in m["builds"]:
        for side in ("TjIn", "TjFree"):
            if side not in b:
                continue
            tag = f"{m['design']}_{side}_{b['config']}"
            fpath = os.path.join(lab_dir, f"{tag}_frames.csv")
            wpath = os.path.join(lab_dir, f"{tag}_windows.csv")
            assert os.path.exists(fpath) and os.path.exists(wpath)
            with open(fpath) as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == m["frame_grid"]["n_frames"]
            tro = [int(r["frame_index"]) for r in rows
                   if r["label"] == TROJAN_CONFIRMED]
            assert tro == b[side]["frames_trojan_confirmed"]
            with open(wpath) as f:
                wrows = list(csv.DictReader(f))
            assert len(wrows) == m["frame_grid"]["n_windows"]
            twin = [int(r["window_index"]) for r in wrows
                    if r["label"] == TROJAN_CONFIRMED]
            assert twin == b[side]["windows_trojan_confirmed"]


if __name__ == "__main__":
    test_frame_index_derivation()
    test_pattern_matching_is_anchored_glob()
    test_labels_and_window_aggregation()
    test_real_corpus_benign_specificity()
    test_real_corpus_containment_and_variation()
    test_label_files_match_manifest()
    print("All localization label tests passed.")
