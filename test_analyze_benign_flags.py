# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for analyze_benign_flags on synthetic data only -- the
#              l3_slack folder -> (design, period) timing join, the
#              route-thru shape test (64-row and 32-row-half wires), the
#              why-not-route_thru reasons, reason parsing, and the
#              meets_timing filter that defines the evasion set.
#
# Usage:
#   python3 test_analyze_benign_flags.py
#   (or: pytest test_analyze_benign_flags.py -q)

from analyze_benign_flags import (benign_row, folder_period,
                                  is_route_thru_shaped, join_timing,
                                  lut_record, lut_shape, met_and_flagged,
                                  parse_reasons, timing_table,
                                  timing_unknown_and_flagged,
                                  why_not_route_thru, wire_input)

I0 = 0xAAAAAAAAAAAAAAAA
I3 = 0xFF00FF00FF00FF00
I5 = 0xFFFFFFFF00000000
MASK = (1 << 64) - 1
AND2 = 0x8888888888888888          # I0 & I1

DOCS = [
    {"design": "b15-T200", "per_period": [
        {"period_ns": 8.0, "wns_ns": -1.047, "meets_timing": False},
        {"period_ns": 20.0, "wns_ns": 6.524, "meets_timing": True}]},
    {"design": "AES-T1000", "per_period": [
        {"period_ns": 8.0, "wns_ns": 0.9, "meets_timing": True}]},
]


def _raises(fn, *args, exc=ValueError):
    try:
        fn(*args)
    except exc as e:
        return str(e)
    raise AssertionError("%s%r did not raise %s" % (fn.__name__, args,
                                                    exc.__name__))


def test_folder_period_join():
    assert folder_period("l3_slack/b15-T200/p20") == ("b15-T200", 20.0)
    assert folder_period("l3_slack/AES-T1000/p8") == ("AES-T1000", 8.0)
    for f in ("l3_width", "l3_funct_b15", "l3_slack/b15-T200",
              "l3_slack/b15-T200/p20/x", "l3_slack/b15-T200/q20"):
        assert folder_period(f) is None, f

    t = timing_table(DOCS)
    # Same period in two designs stays separate.
    assert join_timing("l3_slack/b15-T200/p8", t) == \
        {"wns_ns": -1.047, "meets_timing": False}
    assert join_timing("l3_slack/AES-T1000/p8", t) == \
        {"wns_ns": 0.9, "meets_timing": True}
    assert join_timing("l3_width", t) == {"wns_ns": None,
                                          "meets_timing": None}
    # An l3_slack build with no timing entry fails closed.
    _raises(join_timing, "l3_slack/b15-T200/p12", t, exc=KeyError)
    _raises(timing_table, DOCS + [DOCS[1]])


def test_route_thru_shape():
    assert wire_input(I0) == "I0"
    assert wire_input(I3) == "I3"
    assert wire_input(I5) == "I5"
    assert wire_input(I3 ^ MASK) == "~I3"
    for t in (0, MASK, AND2, I0 ^ I3):
        assert wire_input(t) is None, hex(t)
        assert not is_route_thru_shaped(t)
    assert is_route_thru_shaped(I0) and is_route_thru_shaped(I5 ^ MASK)

    # A wire on I0..I4 is also a wire in each half; one on I5 is not.
    assert lut_shape(I0) == {"o6": "I0", "lo32": "I0", "hi32": "I0"}
    assert lut_shape(I5) == {"o6": "I5", "lo32": None, "hi32": None}
    # Fractured LUT: O5 (low half) passes I2, O6 half is an AND.
    frac = (0x88888888 << 32) | 0xF0F0F0F0
    assert lut_shape(frac) == {"o6": None, "lo32": "I2", "hi32": None}


def test_why_not_route_thru():
    assert why_not_route_thru("new", 0, AND2).startswith("new table")
    assert why_not_route_thru("removed", AND2, 0).startswith("old table")
    assert why_not_route_thru("function_changed", I0, AND2) == \
        "old is a wire, new is a function"
    assert why_not_route_thru("function_changed", AND2, I3 ^ MASK) == \
        "old is a function, new is a wire"
    assert why_not_route_thru("function_changed", AND2, I0 ^ I3) == \
        "neither side is a wire"
    _raises(why_not_route_thru, "function_changed", I0, I3)
    _raises(why_not_route_thru, "pin_permutation", I0, I3)

    # A zero side is ignored when judging shape.
    frac = (0x88888888 << 32) | 0xF0F0F0F0
    r = lut_record({"tile": "T", "lut": "SLICEL_X0.ALUT", "class": "new"},
                   0, frac)
    assert r["route_thru_shaped"] is False and r["half_wire_shaped"] is True
    assert r["old_init"] == "0x0000000000000000"
    r = lut_record({"tile": "T", "lut": "SLICEL_X0.ALUT",
                    "class": "function_changed"}, I3, AND2)
    assert r["route_thru_shaped"] is True


def test_parse_reasons():
    luts, ff = parse_reasons("CLBLL_L_X68Y61", [
        "SLICEL_X1.ALUT function_changed", "SLICEL_X0.DLUT new",
        "+SLICEL_X1.AFF.ZINI", "+SLICEL_X1.AFF.ZRST",
        "-SLICEL_X1.CFF.ZINI"])
    assert [(l["lut"], l["class"]) for l in luts] == [
        ("SLICEL_X1.ALUT", "function_changed"), ("SLICEL_X0.DLUT", "new")]
    assert ff == {"ff_zini": 2, "ff_zrst": 1}
    _raises(parse_reasons, "T", ["SLICEL_X0.ALUT pin_permutation"])
    _raises(parse_reasons, "T", ["+SLICEL_X0.AFF.SRUSEDMUX"])


def test_meets_timing_filter():
    t = timing_table(DOCS)

    def rec(folder, reasons):
        return {"bit": folder + "/B_Explore.bit",
                "reference": folder + "/B_Default.bit",
                "flagged": sorted(reasons), "flag_reasons": reasons,
                "lut_classes": {"route_thru": 0}}

    one = {"CLBLL_L_X1Y1": ["SLICEL_X0.ALUT new"]}
    rows = [
        benign_row("l3_slack/b15-T200/p8", "B_Explore",
                   rec("l3_slack/b15-T200/p8", one), t),      # FAIL, flagged
        benign_row("l3_slack/b15-T200/p20", "B_Explore",
                   rec("l3_slack/b15-T200/p20", {}), t),      # MET, clean
        benign_row("l3_slack/AES-T1000/p8", "B_Explore",
                   rec("l3_slack/AES-T1000/p8", one), t),     # MET, flagged
        benign_row("l3_width", "B_Explore",
                   rec("l3_width", one), t),                  # unknown
    ]
    assert rows[0]["new"] == 1 and rows[0]["flagged"] == 1
    assert met_and_flagged(rows) == ["l3_slack/AES-T1000/p8/B_Explore"]
    assert timing_unknown_and_flagged(rows) == ["l3_width/B_Explore"]
    assert met_and_flagged(rows[:2]) == []


if __name__ == "__main__":
    test_folder_period_join()
    test_route_thru_shape()
    test_why_not_route_thru()
    test_parse_reasons()
    test_meets_timing_filter()
    print("All analyze_benign_flags tests passed.")
