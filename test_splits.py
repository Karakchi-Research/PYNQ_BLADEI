# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for split_utils -- asserts no design name ever appears on
#              both sides of a split, and that window sizing stays frame-aligned.
#
# Usage:
#   python test_splits.py          (or: pytest test_splits.py -q)

import numpy as np

from split_utils import (FRAME_BYTES, design_name, grouped_split_indices,
                         payload_aware_grouped_split_indices,
                         payload_component_labels)


def make_fake_dataset(n_designs=40, variants=10):
    """Synthetic Trust-Hub-style file list: each design has `variants` P&R
    builds, and every design ships a benign AND a malicious build so the
    splitter must keep the pair together."""
    files, y = [], []
    for d in range(n_designs):
        name = f"DES{d:03d}-T{100 + d}"
        for label, is_mal in (("benign", 0), ("malicious", 1)):
            for v in range(variants):
                files.append(f"trusthub_bitstreams/X/{name}_{label}_2026040{v % 10}_12{v:04d}.bit")
                y.append(is_mal)
    return files, np.array(y)


def test_design_name():
    # Real Trust-Hub filenames: benign build, trojaned build, and P&R variants
    # of one benchmark all map to the same design key.
    assert design_name("trusthub_bitstreams/Benign/AES_T100.bit") == "AES_T100"
    assert design_name("trusthub_bitstreams/Benign/AES_T100_v3.bit") == "AES_T100"
    assert design_name("trusthub_bitstreams/Malicious/AES_T100_Trojan.bit") == "AES_T100"
    assert design_name("trusthub_bitstreams/Malicious/AES_T100_Trojan_v2.bit") == "AES_T100"
    # Multi-underscore design names must not collapse to the first token.
    assert design_name("wb_conmax_T300_Trojan_v5.bit") == "wb_conmax_T300"
    assert design_name("vga_lcd_T100.bit") == "vga_lcd_T100"
    # Ethernet suffix grammar: `_Trojan` before OR after the variant token, and
    # `_d2` builds of the same benchmark stay in the same group.
    assert design_name("EthernetMAC10GE_T700_Trojan_v2.bit") == "EthernetMAC10GE_T700"
    assert design_name("EthernetMAC10GE_T700_d2_v2_Trojan.bit") == "EthernetMAC10GE_T700"
    assert design_name("EthernetMAC10GE_T700_d2.bit") == "EthernetMAC10GE_T700"
    # Distinct trojan benchmarks on the same base design stay distinct groups.
    assert design_name("AES_T1000_v2.bit") != design_name("AES_T100_v2.bit")
    # Legacy timestamped layout.
    assert design_name("AES-T200_benign_20260404_223130.bit") == "AES-T200"
    assert design_name("s15850-T100_malicious_20260404_170450.bit") == "s15850-T100"
    assert design_name("trusthub_bitstreams/Benign/RS232-T901_benign_20260101_000000.bit") == "RS232-T901"


def test_no_design_on_both_sides():
    files, y = make_fake_dataset()
    names = [design_name(f) for f in files]
    for seed in range(5):
        idx_t, idx_v, idx_te = grouped_split_indices(files, y, seed)
        assert len(idx_t) + len(idx_v) + len(idx_te) == len(files)
        train_designs = {names[i] for i in np.concatenate([idx_t, idx_v])}
        test_designs = {names[i] for i in idx_te}
        assert not (train_designs & test_designs)
        assert {names[i] for i in idx_t}.isdisjoint({names[i] for i in idx_v})


def test_frame_constant():
    assert FRAME_BYTES == 101 * 4
    assert 8 * FRAME_BYTES == 3232  # default window: 8 frames


# ---------------------------------------------------------------------------
# Phase 0.5 corrected split path.
# ---------------------------------------------------------------------------
def make_payload_dataset():
    """Synthetic corpus where DIFFERENT design keys share an exact payload
    (the real failure mode: trojan-free builds of different benchmarks are
    the same circuit). Design keys A/B share payload pDUP; C..H are clean.
    Each design has a benign and a malicious build with distinct payloads
    otherwise."""
    files, y, pids = [], [], []
    shared = [("AAA_T100", "pDUP"), ("BBB_T200", "pDUP")]
    solo = [(f"DES{c}_T{300 + i}", None) for i, c in enumerate("CDEFGH")]
    for name, dup in shared + solo:
        for label, is_mal in (("", 0), ("_Trojan", 1)):
            for v in range(3):
                files.append(f"data/X/{name}{label}_v{v + 2}.bit")
                y.append(is_mal)
                if dup and not is_mal:
                    pids.append(dup)               # shared benign payload
                else:
                    pids.append(f"p_{name}_{is_mal}_{v}")
    return files, np.array(y), np.array(pids)


def test_payload_components_merge_design_keys():
    files, y, pids = make_payload_dataset()
    comps = payload_component_labels(files, pids)
    names = np.array([design_name(f) for f in files])
    # Shared payload bridges AAA_T100 and BBB_T200 into one component...
    assert len(set(comps[names == "AAA_T100"])
               | set(comps[names == "BBB_T200"])) == 1
    # ...while unlinked designs stay separate.
    assert len(set(comps[names == "DESC_T300"])
               & set(comps[names == "AAA_T100"])) == 0


def test_payload_sharing_designs_never_split():
    """Files of different design keys sharing an exact payload must always
    land on the same side -- the case the legacy split provably gets wrong."""
    files, y, pids = make_payload_dataset()
    names = np.array([design_name(f) for f in files])
    for seed in range(5):
        idx_t, idx_v, idx_te = payload_aware_grouped_split_indices(
            files, y, seed, payload_ids=pids)
        assert len(idx_t) + len(idx_v) + len(idx_te) == len(files)
        for side_a, side_b in ((idx_t, idx_te), (idx_v, idx_te),
                               (idx_t, idx_v)):
            assert not ({pids[i] for i in side_a} & {pids[i] for i in side_b})
            assert not ({names[i] for i in side_a} & {names[i] for i in side_b})
        # The two payload-linked designs travel together.
        sides = [set(np.where(np.isin(np.arange(len(files)), idx))[0])
                 for idx in (idx_t, idx_v, idx_te)]
        linked = set(np.flatnonzero((names == "AAA_T100")
                                    | (names == "BBB_T200")))
        assert any(linked <= s for s in sides)


def test_subset_split_honors_full_corpus_components():
    """Deduplication removes the alias files whose shared payload bridges two
    design keys. Splitting the canonical SUBSET must therefore use components
    computed over the FULL corpus, or the bridge is silently lost and the two
    designs can land on opposite sides (the exact leakage the component rule
    exists to prevent)."""
    files, y, pids = make_payload_dataset()
    names = np.array([design_name(f) for f in files])
    comps_full = payload_component_labels(files, pids)
    # Canonical subset: one file per payload id (first occurrence).
    seen, canon = set(), []
    for i, p in enumerate(pids):
        if p not in seen:
            seen.add(p)
            canon.append(i)
    canon = np.array(canon)
    sub_files = [files[i] for i in canon]
    # The shared benign payload 'pDUP' now has ONE canonical file, so on the
    # subset the AAA_T100 <-> BBB_T200 design bridge exists only through the
    # full-corpus components.
    linked = {"AAA_T100", "BBB_T200"}
    for seed in range(5):
        idx_t, idx_v, idx_te = payload_aware_grouped_split_indices(
            sub_files, y[canon], seed, payload_ids=pids[canon],
            components=comps_full[canon])
        sides = [{names[canon[j]] for j in idx} for idx in (idx_t, idx_v,
                                                            idx_te)]
        # Both linked designs must sit entirely on one side.
        for side in sides:
            assert side & linked in (set(), linked), \
                f"alias-bridged designs split apart: {side & linked}"


def test_quarantined_files_are_refused():
    files, y, pids = make_payload_dataset()
    quarantined = np.zeros(len(files), dtype=bool)
    quarantined[3] = True
    try:
        payload_aware_grouped_split_indices(files, y, 0, payload_ids=pids,
                                            quarantined=quarantined)
        assert False, "should have refused quarantined input"
    except AssertionError as e:
        assert "quarantined" in str(e)


if __name__ == "__main__":
    test_design_name()
    test_no_design_on_both_sides()
    test_frame_constant()
    test_payload_components_merge_design_keys()
    test_payload_sharing_designs_never_split()
    test_subset_split_honors_full_corpus_components()
    test_quarantined_files_are_refused()
    print("All split tests passed.")
