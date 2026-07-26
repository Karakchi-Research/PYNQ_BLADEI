# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5B diagnostic -- diff the matched benign/malicious
#              post-synthesis leaf-cell inventories produced by dump_cells.tcl.
#
#              This exists because "the named trojan cells survived" and "the
#              matched pair differs in the bitstream" are DIFFERENT claims, and
#              the pilot found a design where the first is false and the second
#              is true (PIC16F84-T100). Reporting only the name-pattern result
#              would have mislabelled that case.
#
#              Input : pilot_artifacts/diag/<design>_<label>.cells[.summary]
#              Output: rebuild_pilot/netlist_diff.json

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DIAG = os.path.join(HERE, "pilot_artifacts", "diag")
DESIGNS = ["PIC16F84-T100", "b15-T200", "AES-T1000"]

# On the larger designs the name-level difference is dominated by synthesis
# renaming (Vivado derives instance names from the logic it packs, so a small
# RTL change renames thousands of unrelated LUTs). The counts and the primitive
# TYPE deltas carry the signal; the full name lists would be megabytes of noise.
# Lists are truncated, and the truncation is recorded in the artifact.
MAX_NAMES = 200


def load_cells(design, label):
    path = os.path.join(DIAG, f"{design}_{label}.cells")
    if not os.path.exists(path):
        return None
    cells = {}
    with open(path) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 2:
                ref, name = parts
                cells[name] = ref
    return cells


def main():
    out = {
        "schema": "netlist_diff_v1",
        "stage": "post_synthesis",
        "method": (
            "leaf primitives (IS_PRIMITIVE) enumerated by Vivado from each "
            "label's single post-synthesis checkpoint, then compared by "
            "instance name and by primitive type. Answers 'what physically "
            "differs between the matched pair', independently of whether the "
            "design's trojan NAME patterns survived synthesis."),
        "designs": {},
    }

    for d in DESIGNS:
        free = load_cells(d, "TjFree")
        mal = load_cells(d, "TjIn")
        if free is None or mal is None:
            out["designs"][d] = {"available": False}
            continue

        only_mal = sorted(set(mal) - set(free))
        only_free = sorted(set(free) - set(mal))
        type_free = Counter(free.values())
        type_mal = Counter(mal.values())
        type_delta = {
            t: {"benign": type_free.get(t, 0), "malicious": type_mal.get(t, 0),
                "delta": type_mal.get(t, 0) - type_free.get(t, 0)}
            for t in sorted(set(type_free) | set(type_mal))
            if type_mal.get(t, 0) != type_free.get(t, 0)
        }

        out["designs"][d] = {
            "available": True,
            "primitives_benign": len(free),
            "primitives_malicious": len(mal),
            "n_cells_only_in_malicious": len(only_mal),
            "n_cells_only_in_benign": len(only_free),
            "name_lists_truncated_to": MAX_NAMES,
            "name_diff_caveat": (
                "instance names are assigned by synthesis, so on large designs "
                "most name-level differences are renaming rather than added or "
                "removed logic; read primitive_type_deltas for the structural "
                "signal"),
            "cells_only_in_malicious": [
                {"name": n, "ref": mal[n]} for n in only_mal[:MAX_NAMES]],
            "cells_only_in_benign": [
                {"name": n, "ref": free[n]} for n in only_free[:MAX_NAMES]],
            "primitive_type_deltas": type_delta,
            "netlists_identical": (not only_mal and not only_free
                                   and not type_delta),
        }

    with open(os.path.join(HERE, "netlist_diff.json"), "w") as f:
        json.dump(out, f, indent=2)

    for d, rec in out["designs"].items():
        if not rec.get("available"):
            print(f"{d}: no dump available")
            continue
        print(f"{d}: benign={rec['primitives_benign']} "
              f"malicious={rec['primitives_malicious']} "
              f"only_mal={rec['n_cells_only_in_malicious']} "
              f"only_benign={rec['n_cells_only_in_benign']} "
              f"identical={rec['netlists_identical']}")
        for t, v in rec["primitive_type_deltas"].items():
            print(f"    {t}: {v['benign']} -> {v['malicious']} "
                  f"({v['delta']:+d})")


if __name__ == "__main__":
    main()
