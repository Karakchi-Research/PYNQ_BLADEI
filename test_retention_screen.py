# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for the Phase 0.5C retention screen. Every state of the
#              trace taxonomy is exercised with synthetic evidence, and the
#              classifier is checked against the three REAL Phase 0.5B pilot
#              outcomes (AES-T1000 retained, b15-T200 retained-but-HOLD,
#              PIC16F84-T100 no-trace-after-synthesis) so the protocol is
#              validated on measured data, not only on constructed cases.
#
# Usage:
#   python3 test_retention_screen.py   (or: pytest test_retention_screen.py -q)

import os

from retention_screen import (ADMIT, HOLD, INDETERMINATE,
                              NO_TRACE_AFTER_IMPLEMENTATION,
                              NO_TRACE_AFTER_SYNTHESIS, REJECT_INCOMPLETE,
                              REJECT_NO_TRACE, TROJAN_RETAINED,
                              classify_design, discriminative_patterns,
                              load_pilot_evidence)

PILOT_DIR = "rebuild_pilot"


def _ev(benign_pats, mal_pats, route=None):
    """Build a retention-evidence dict. route: {cfg: {pattern: (cells, nets)}}"""
    def pats(d):
        return {"patterns": {k: {"cells": c, "nets": n}
                             for k, (c, n) in d.items()}}
    ev = {"post_synth": {"TjFree": pats(benign_pats),
                         "TjIn": pats(mal_pats)}}
    if route is not None:
        ev["post_route"] = {"TjIn": {cfg: pats(p) for cfg, p in route.items()}}
    return ev


# --- discriminative-pattern rule -------------------------------------------
def test_benign_control_drops_nondiscriminative_patterns():
    # `*bus*` fires in BOTH builds -> host structure, must be dropped.
    # `*Trojan*` fires only in malicious -> discriminative.
    ev = _ev({"*bus*": (9, 12), "*Trojan*": (0, 0)},
             {"*bus*": (9, 12), "*Trojan*": (5, 7)})
    disc = discriminative_patterns(ev["post_synth"])
    assert set(disc) == {"*Trojan*"}
    assert disc["*Trojan*"] == {"cells": 5, "nets": 7}


def test_net_only_match_is_discriminative():
    # A trojan may survive as nets only (b15's muxed clock); cells==0 must
    # still count.
    disc = discriminative_patterns(
        _ev({"*MUXed*": (0, 0)}, {"*MUXed*": (0, 74)})["post_synth"])
    assert disc["*MUXed*"] == {"cells": 0, "nets": 74}


# --- the four trace states --------------------------------------------------
def test_state_trojan_retained():
    v = classify_design(
        _ev({"*Tj*": (0, 0)}, {"*Tj*": (5, 5)},
            route={"C1": {"*Tj*": (5, 5)}, "C4": {"*Tj*": (4, 6)}}),
        payload_identical_by_cfg={"C1": False, "C4": False}, reproduced=True)
    assert v["trace"] == TROJAN_RETAINED
    assert v["admission"] == ADMIT
    assert v["valid_pairs"] == ["C1", "C4"] and not v["invalid_pairs"]


def test_state_no_trace_after_synthesis():
    """The PIC16F84 shape: zero discriminative matches post-synthesis.
    Must classify at SYNTHESIS even though the bitstream differs."""
    v = classify_design(
        _ev({"*Counter*": (0, 0)}, {"*Counter*": (0, 0)},
            route={"C1": {"*Counter*": (0, 0)}}),
        payload_identical_by_cfg={"C1": False},  # bitstream DOES differ
        reproduced=True)
    assert v["trace"] == NO_TRACE_AFTER_SYNTHESIS
    assert v["admission"] == REJECT_NO_TRACE
    assert "not trojan evidence" in v["reason"].lower() or \
        "residue" in v["reason"].lower()


def test_state_no_trace_after_implementation_lost_at_route():
    v = classify_design(
        _ev({"*Tj*": (0, 0)}, {"*Tj*": (5, 5)},
            route={"C1": {"*Tj*": (5, 5)}, "C3": {"*Tj*": (0, 0)}}),
        payload_identical_by_cfg={"C1": False, "C3": False})
    assert v["trace"] == NO_TRACE_AFTER_IMPLEMENTATION
    assert "C3" in v["invalid_pairs"] and v["admission"] == REJECT_NO_TRACE


def test_state_no_trace_after_implementation_identical_payload():
    """The audit's original 169-file criterion: trojan survives the netlist
    but the built payload equals its benign twin."""
    v = classify_design(
        _ev({"*Tj*": (0, 0)}, {"*Tj*": (5, 5)},
            route={"C1": {"*Tj*": (5, 5)}}),
        payload_identical_by_cfg={"C1": True})
    assert v["trace"] == NO_TRACE_AFTER_IMPLEMENTATION
    assert "byte-identical" in v["reason"]
    assert v["admission"] == REJECT_NO_TRACE


def test_state_indeterminate_missing_control_and_missing_route():
    no_control = {"post_synth": {"TjIn": {"patterns": {"*Tj*": {"cells": 5,
                                                                "nets": 5}}}}}
    v = classify_design(no_control)
    assert v["trace"] == INDETERMINATE and v["admission"] == REJECT_INCOMPLETE

    v2 = classify_design(_ev({"*Tj*": (0, 0)}, {"*Tj*": (5, 5)}))
    assert v2["trace"] == INDETERMINATE
    assert v2["admission"] == REJECT_INCOMPLETE


def test_hold_when_provenance_unreproduced():
    """Retention verified but the rebuild does not reproduce the corpus
    payload -> HOLD, not ADMIT (the b15-T200 shape)."""
    v = classify_design(
        _ev({"*Tj*": (0, 0)}, {"*Tj*": (5, 5)},
            route={"C1": {"*Tj*": (5, 5)}}),
        payload_identical_by_cfg={"C1": False}, reproduced=False)
    assert v["trace"] == TROJAN_RETAINED
    assert v["admission"] == HOLD
    assert "provenance" in v["admission_reason"]


# --- validation against the real pilot measurements -------------------------
def test_matches_real_pilot_outcomes():
    if not os.path.exists(os.path.join(PILOT_DIR, "trojan_retention.json")):
        print("(pilot validation skipped: no pilot artifacts)")
        return
    retention, identical, reproduced = load_pilot_evidence(PILOT_DIR)
    got = {d: classify_design(retention[d], identical.get(d),
                              reproduced.get(d))
           for d in retention}

    # AES-T1000: 107 Trojan + 61 Tj_Trig cells, survives all 4 configs,
    # reproduces the corpus byte-exactly.
    aes = got["AES-T1000"]
    assert aes["trace"] == TROJAN_RETAINED, aes
    assert aes["admission"] == ADMIT
    assert set(aes["discriminative_patterns"]) == {"*Trojan*", "*Tj_Trig*"}
    assert len(aes["valid_pairs"]) == 4

    # b15-T200: retained (UTj cells + 74 muxed-clock nets) but the rebuild
    # does not reproduce the shipped corpus payload -> HOLD.
    b15 = got["b15-T200"]
    assert b15["trace"] == TROJAN_RETAINED, b15
    assert b15["admission"] == HOLD
    assert "*UTj*" in b15["discriminative_patterns"]
    assert "*MUXed*" in b15["discriminative_patterns"]

    # PIC16F84-T100: trojan deleted at synthesis, despite a 199-frame
    # bitstream difference in every configuration.
    pic = got["PIC16F84-T100"]
    assert pic["trace"] == NO_TRACE_AFTER_SYNTHESIS, pic
    assert pic["admission"] == REJECT_NO_TRACE
    assert pic["discriminative_patterns"] == {}
    # And confirm the trap this protocol exists to avoid: its payloads are
    # NOT identical to benign, so a bitstream-only screen would pass it.
    assert not any(identical["PIC16F84-T100"].values())


if __name__ == "__main__":
    test_benign_control_drops_nondiscriminative_patterns()
    test_net_only_match_is_discriminative()
    test_state_trojan_retained()
    test_state_no_trace_after_synthesis()
    test_state_no_trace_after_implementation_lost_at_route()
    test_state_no_trace_after_implementation_identical_payload()
    test_state_indeterminate_missing_control_and_missing_route()
    test_hold_when_provenance_unreproduced()
    test_matches_real_pilot_outcomes()
    print("All retention screen tests passed.")
