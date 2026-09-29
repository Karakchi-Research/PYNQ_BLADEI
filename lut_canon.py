# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Classify how a 6-input LUT truth table changed between two
#              builds of the same design.
#
#              A LUT INIT is a 64-bit int: bit i is the output when the
#              inputs read i, input k being bit k of i (I0 = LSB). Two
#              builds of one netlist routinely differ by which physical pin
#              carries which signal, so a changed INIT is only suspicious
#              when no relabeling of the inputs explains it. `classify`
#              checks, in this order:
#
#                old == new                              -> unchanged
#                old == 0: new is a wire (I_k or ~I_k)   -> route_thru
#                          otherwise                     -> new
#                new == 0: old is a wire                 -> route_thru
#                          otherwise                     -> removed
#                new = old with its 6 inputs relabeled   -> pin_permutation
#                both are wires                          -> route_thru
#                equal after dropping unused inputs,
#                  up to relabeling                      -> support_reduced_perm
#                otherwise                               -> function_changed
#
#              Relabeling tries all 720 input orders at once with a
#              precomputed (720, 64) source-row table.
#
# Usage:
#   from lut_canon import classify
#   classify(0b0010, 0b0100) == "pin_permutation"

import functools
import itertools

import numpy as np

N_INPUTS = 6
N_ROWS = 1 << N_INPUTS
MASK = (1 << N_ROWS) - 1

CLASSES = ("unchanged", "new", "removed", "route_thru", "pin_permutation",
           "support_reduced_perm", "function_changed")

_SHIFTS = np.arange(N_ROWS, dtype=np.uint64)


def input_table(k, n=N_INPUTS):
    """Truth table of the identity on input k (I0 = 0xAAAA...)."""
    return sum(1 << i for i in range(1 << n) if (i >> k) & 1)


INPUT_TABLES = tuple(input_table(k) for k in range(N_INPUTS))
_WIRES = frozenset(INPUT_TABLES) | frozenset(t ^ MASK for t in INPUT_TABLES)


def is_wire(init):
    """True iff the LUT passes one input through, plain or inverted."""
    return init in _WIRES


@functools.lru_cache(maxsize=None)
def _perm_sources(n):
    """(n!, 2^n) array: row p, column x is the source row read by x under
    input order p (input k of x feeds input perm[k] of the original)."""
    rows = np.arange(1 << n)
    perms = list(itertools.permutations(range(n)))
    src = np.zeros((len(perms), 1 << n), dtype=np.intp)
    for p, perm in enumerate(perms):
        for k, to in enumerate(perm):
            src[p] |= ((rows >> k) & 1) << to
    return src


def relabelings(init, n=N_INPUTS):
    """Every truth table reachable from `init` by reordering its n inputs."""
    bits = (np.uint64(init) >> _SHIFTS[:1 << n]) & np.uint64(1)
    tables = bits[_perm_sources(n)]
    packed = (tables << _SHIFTS[:1 << n]).sum(axis=1, dtype=np.uint64)
    return {int(v) for v in packed}


def same_up_to_relabeling(a, b, n=N_INPUTS):
    return b in relabelings(a, n)


def support(init):
    """Inputs the function depends on, ascending."""
    out = []
    for k in range(N_INPUTS):
        low = INPUT_TABLES[k] ^ MASK            # rows with input k = 0
        if (init & low) != ((init >> (1 << k)) & low):
            out.append(k)
    return out


def compact(init):
    """(table over the support inputs only, number of support inputs)."""
    s = support(init)
    table = 0
    for r in range(1 << len(s)):
        x = sum(((r >> j) & 1) << k for j, k in enumerate(s))
        table |= ((init >> x) & 1) << r
    return table, len(s)


def classify(old, new):
    old, new = int(old), int(new)
    for name, v in (("old", old), ("new", new)):
        if not 0 <= v <= MASK:
            raise ValueError("%s INIT 0x%x is not a 64-bit table" % (name, v))
    if old == new:
        return "unchanged"
    if old == 0:
        return "route_thru" if is_wire(new) else "new"
    if new == 0:
        return "route_thru" if is_wire(old) else "removed"
    if same_up_to_relabeling(old, new):
        return "pin_permutation"
    if is_wire(old) and is_wire(new):
        return "route_thru"
    (a, ka), (b, kb) = compact(old), compact(new)
    if ka == kb and same_up_to_relabeling(a, b, ka):
        return "support_reduced_perm"
    return "function_changed"
