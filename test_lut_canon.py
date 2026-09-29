# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Tests for lut_canon -- a 2-input function with its pins
#              swapped must be a pin_permutation (as a bare 4-bit INIT and
#              replicated over the unused inputs); input tables and support
#              compaction must match hand-computed values; and each class is
#              reached in the documented check order.
#
# Usage:
#   python3 test_lut_canon.py    (or: pytest test_lut_canon.py -q)

from lut_canon import (INPUT_TABLES, MASK, classify, compact, is_wire,
                       relabelings, support)

I0, I1, I2, I3 = INPUT_TABLES[:4]


def test_two_input_pin_swap_is_permutation():
    # 0b0010: out=1 only at I0=1,I1=0.  0b0100: only at I0=0,I1=1.
    assert classify(0b0010, 0b0100) == "pin_permutation"
    # Same pair written as a true 2-input LUT (pattern repeated over I2..I5).
    assert classify(0x2222222222222222, 0x4444444444444444) \
        == "pin_permutation"


def test_input_tables_and_support():
    assert INPUT_TABLES == (0xAAAAAAAAAAAAAAAA, 0xCCCCCCCCCCCCCCCC,
                            0xF0F0F0F0F0F0F0F0, 0xFF00FF00FF00FF00,
                            0xFFFF0000FFFF0000, 0xFFFFFFFF00000000)
    assert support(0x2222222222222222) == [0, 1]
    assert compact(0x2222222222222222) == (0b0010, 2)
    assert support(I3) == [3] and compact(I3) == (0b10, 1)
    assert compact(0) == (0, 0) and compact(MASK) == (1, 0)
    assert len(relabelings(1 << 63)) == 1               # 6-input AND
    assert len(relabelings(I0 & I1 & I2)) == 20         # C(6, 3) placements
    assert len(relabelings(I0)) == 6


def test_class_order():
    and01, xor01 = I0 & I1, I0 ^ I1
    assert classify(and01, and01) == "unchanged"
    assert classify(0, and01) == "new"
    assert classify(and01, 0) == "removed"
    assert classify(0, I2) == "route_thru"
    assert classify(I2 ^ MASK, 0) == "route_thru"
    assert is_wire(I0) and is_wire(I3 ^ MASK) and not is_wire(and01)
    # A wire moving to another pin is a relabeling, caught before route_thru.
    assert classify(I0, I3) == "pin_permutation"
    # Wire to inverted wire is not a relabeling.
    assert classify(I0, I3 ^ MASK) == "route_thru"
    assert classify(and01, I2 & I3) == "pin_permutation"
    assert classify(and01, xor01) == "function_changed"
    assert classify(and01, and01 & I2) == "function_changed"


if __name__ == "__main__":
    test_two_input_pin_swap_is_permutation()
    test_input_tables_and_support()
    test_class_order()
    print("All lut_canon tests passed.")
