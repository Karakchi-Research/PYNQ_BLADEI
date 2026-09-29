# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for l3f_format_aware_eval on synthetic data only -- truth
#              parsing (header, empty values, Tcl-list taps, IMPLANT lines,
#              rejection of unknown lines), the n_taps rules, roles from cell
#              prefixes, the kill rule at its edges, implant / benign /
#              truth-without-bit detection, and the reference guard.
#
# Usage:
#   python3 test_l3f_format_aware_eval.py
#   (or: pytest test_l3f_format_aware_eval.py -q)

import os
import struct
import tempfile

from l3_format_aware_eval import score
from l3f_format_aware_eval import (KILL_MAX_FP_PER_GT, ReferenceMismatch,
                                   check_reference, discover, kill_reasons,
                                   n_taps, parse_truth, role_of, tcl_list,
                                   tile_roles)

TRUTH = """tag: W3
region: SLICE_X72Y11:SLICE_X83Y49
style: trigonly
n_cells: 3
clock_net: clk_IBUF_BUFG
tap_net:
trigger_taps: clk_IBUF {out_OBUF[10]} {out_OBUF[11]}
IMPLANT bladei_ftrig_W3 SLICE_X73Y49
IMPLANT bladei_farm_W3_0 SLICE_X72Y49
IMPLANT bladei_fpay_W3 SLICE_X74Y49
"""


def _raises(fn, *args, exc=ValueError):
    try:
        fn(*args)
    except exc as e:
        return str(e)
    raise AssertionError("%s%r did not raise %s" % (fn.__name__, args,
                                                    exc.__name__))


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def make_bit(design, pad_to=256):
    """Minimal .bit header with design field 'a', padded to `pad_to` bytes."""
    a = ("%s;UserID=0XFFFFFFFF;Version=2023.2" % design).encode() + b"\x00"
    blob = (struct.pack(">H", 9) + b"\x0f\xf0" * 4 + b"\x00"
            + struct.pack(">H", 1) + b"a" + struct.pack(">H", len(a)) + a
            + b"b" + struct.pack(">H", 13) + b"7z020clg400\x00\x00")
    return blob + b"\xff" * (pad_to - len(blob))


def test_truth_parsing():
    header, implants = parse_truth(TRUTH)
    assert header["tag"] == "W3"
    assert header["region"] == "SLICE_X72Y11:SLICE_X83Y49"
    assert header["tap_net"] == ""
    assert header["trigger_taps"] == "clk_IBUF {out_OBUF[10]} {out_OBUF[11]}"
    assert list(header) == ["tag", "region", "style", "n_cells", "clock_net",
                            "tap_net", "trigger_taps"]
    assert implants == [
        {"cell": "bladei_ftrig_W3", "site": "SLICE_X73Y49", "role": "trigger"},
        {"cell": "bladei_farm_W3_0", "site": "SLICE_X72Y49", "role": "arming"},
        {"cell": "bladei_fpay_W3", "site": "SLICE_X74Y49", "role": "payload"},
    ]
    assert tcl_list(header["trigger_taps"]) == ["clk_IBUF", "out_OBUF[10]",
                                                "out_OBUF[11]"]
    assert tcl_list("") == []
    _raises(tcl_list, "{out_OBUF[10]")
    _raises(tcl_list, "{a {b}}")
    _raises(tcl_list, "{a}b")


def test_truth_rejects_unknown_lines():
    _raises(parse_truth, TRUTH + "seed: 7\n")
    _raises(parse_truth, TRUTH + "just some text\n")
    _raises(parse_truth, TRUTH + "IMPLANTS bladei_farm_W3_1 SLICE_X75Y49\n")
    _raises(parse_truth, TRUTH + "IMPLANT bladei_farm_W3_1\n")
    _raises(parse_truth, TRUTH + "IMPLANT bladei_farm_W3_1 RAMB18_X1Y2\n")
    _raises(parse_truth, TRUTH + "tag: W3\n")                  # duplicate


def test_n_taps_rules():
    assert n_taps({"trigger_taps": "a1_n_0 a1_n_100 a1_n_101"}) == 3
    assert n_taps({"trigger_taps": "clk_IBUF {out_OBUF[10]}"}) == 2
    assert n_taps({"trigger_taps": "a b", "tap_net": "x"}) == 2
    assert n_taps({"tap_net": "some_net"}) == 1
    assert n_taps({"tap_net": ""}) == 0
    assert n_taps({}) == 0


def test_roles_from_prefixes():
    assert role_of("bladei_ftrig_T_full") == "trigger"
    assert role_of("bladei_farm_T_full_3") == "arming"
    assert role_of("bladei_fpay_T_full") == "payload"
    assert role_of("bladei_implant_S1_0") == "tied"
    _raises(role_of, "bladei_farmer_0")
    _raises(role_of, "host_reg_0")
    _raises(parse_truth, TRUTH + "IMPLANT bladei_mystery_0 SLICE_X75Y49\n")

    by_site = {"SLICE_X72Y49": ("CLBLL_L_X46Y49", "CLBLL_L"),
               "SLICE_X73Y49": ("CLBLL_L_X46Y49", "CLBLL_L"),
               "SLICE_X74Y49": ("CLBLM_R_X47Y49", "CLBLM_R")}
    _, implants = parse_truth(TRUTH)
    assert tile_roles(implants, by_site) == {
        "CLBLL_L_X46Y49": ["arming", "trigger"],
        "CLBLM_R_X47Y49": ["payload"]}


def _gt(flagged, gt):
    g = {"tiles": sorted(gt), **score(flagged, gt, flagged)}
    return kill_reasons(g)


def test_kill_rule_edges():
    gt = ["T0", "T1"]
    limit = KILL_MAX_FP_PER_GT * len(gt)
    extra = ["X%d" % i for i in range(limit + 1)]
    assert _gt(gt + extra[:limit], gt) == []                   # FP = 2 x GT
    r = _gt(gt + extra, gt)                                    # FP = 2 x GT + 1
    assert len(r) == 1 and r[0].startswith("FP")
    r = _gt(["T0"], gt)                                        # recall 0.5
    assert len(r) == 1 and r[0].startswith("recall")
    assert len(_gt(["T0"] + extra, gt)) == 2
    assert _gt([], gt) and _gt([], [])                         # no GT fails


def test_build_classes():
    with tempfile.TemporaryDirectory() as root:
        for rel in ("exp/B_Default.bit", "exp/B_Explore.bit", "exp/W1.bit"):
            _write(os.path.join(root, rel), make_bit("top"))
        for rel in ("exp/reports/W1_implant_truth.txt",
                    "exp/reports/T_full_implant_truth.txt"):
            _write(os.path.join(root, rel), TRUTH.encode())
        found = discover(root, "exp", "exp/B_Default.bit")
        assert found["implant"] == [
            ("W1", "exp/W1.bit", "exp/reports/W1_implant_truth.txt")]
        assert found["benign"] == [("B_Explore", "exp/B_Explore.bit")]
        assert found["truth_without_bit"] == [
            ("T_full", "exp/reports/T_full_implant_truth.txt")]

        # A reference in another folder is not excluded from this one.
        found = discover(root, "exp", "other/B_Default.bit")
        assert [b for b, _ in found["benign"]] == ["B_Default", "B_Explore"]


def test_reference_guard():
    with tempfile.TemporaryDirectory() as root:
        paths = {name: os.path.join(root, name + ".bit")
                 for name in ("ref", "same", "longer", "aes")}
        _write(paths["ref"], make_bit("top"))
        _write(paths["same"], make_bit("top"))
        _write(paths["longer"], make_bit("top", pad_to=260))
        _write(paths["aes"], make_bit("aes_128"))
        assert check_reference(paths["same"], paths["ref"]) == "top"
        for bad in ("longer", "aes"):
            msg = _raises(check_reference, paths[bad], paths["ref"],
                          exc=ReferenceMismatch)
            assert paths[bad] in msg and paths["ref"] in msg


if __name__ == "__main__":
    test_truth_parsing()
    test_truth_rejects_unknown_lines()
    test_n_taps_rules()
    test_roles_from_prefixes()
    test_kill_rule_edges()
    test_build_classes()
    test_reference_guard()
    print("All l3f_format_aware_eval tests passed.")
