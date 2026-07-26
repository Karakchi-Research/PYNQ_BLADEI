# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C retention screen -- the admissibility protocol as
#              executable code. Classifies each candidate host design from
#              build evidence, so "is this design usable as a localization
#              target?" is a reproducible verdict rather than a judgement call.
#
#              Four-state TRACE taxonomy (a strict pipeline: synthesis ->
#              implementation -> bitstream; a design is classified at the
#              EARLIEST stage where its trojan disappears):
#
#                TROJAN_RETAINED
#                    >=1 discriminative trojan cell/net post-synthesis AND
#                    still present post-route in EVERY implementation
#                    configuration built.
#                NO_TRACE_AFTER_SYNTHESIS
#                    zero discriminative matches in the post-synthesis
#                    netlist -- the trojan never entered the hardware.
#                    (Pilot counterexample: PIC16F84-T100, whose harness ties
#                    off the trigger inputs.) This is the PRIMARY test and it
#                    is strictly stronger than any bitstream-level check: a
#                    design can fail here while still producing a differing
#                    bitstream from dead-logic synthesis residue.
#                NO_TRACE_AFTER_IMPLEMENTATION
#                    present post-synthesis but gone post-route in >=1
#                    configuration, OR the malicious FDRI payload is
#                    byte-identical to its matched benign build (the audit's
#                    original 169-file criterion).
#                INDETERMINATE
#                    required evidence missing; never silently treated as a
#                    pass.
#
#              A pattern only counts if it is DISCRIMINATIVE: it fires in the
#              malicious build and reports ZERO in the matched benign control.
#              Patterns firing in both are host structure, not trojan
#              evidence, and are dropped per-pattern (never pooled).
#
#              Then VALID_MATCHED_PAIR per implementation configuration, and
#              a host-level ADMISSION verdict for the localization corpus.
#
#              Consumes build evidence only -- no Vivado, no bitstream
#              parsing, no model training. `classify_design()` is pure so the
#              tests can drive every state with synthetic evidence.
#
# Usage:
#   python3 retention_screen.py [--pilot-dir rebuild_pilot] [--out ...]

import argparse
import csv
import json
import os
from collections import OrderedDict
from datetime import datetime, timezone

SCHEMA = "retention_screen_v1"

# --- trace states -----------------------------------------------------------
TROJAN_RETAINED = "TROJAN_RETAINED"
NO_TRACE_AFTER_SYNTHESIS = "NO_TRACE_AFTER_SYNTHESIS"
NO_TRACE_AFTER_IMPLEMENTATION = "NO_TRACE_AFTER_IMPLEMENTATION"
INDETERMINATE = "INDETERMINATE"

# --- host admission verdicts ------------------------------------------------
ADMIT = "ADMIT_LOCALIZATION"
REJECT_NO_TRACE = "REJECT_NO_TRACE"
HOLD = "HOLD"
REJECT_INCOMPLETE = "REJECT_INCOMPLETE_EVIDENCE"

BENIGN, MALICIOUS = "TjFree", "TjIn"


def discriminative_patterns(post_synth):
    """Patterns that fire in the malicious build and are ZERO in the benign
    control. Returns {pattern: {"cells": n, "nets": n}} for malicious."""
    benign = post_synth.get(BENIGN, {}).get("patterns", {})
    mal = post_synth.get(MALICIOUS, {}).get("patterns", {})
    out = {}
    for pat, m in mal.items():
        b = benign.get(pat, {"cells": 0, "nets": 0})
        if (b.get("cells", 0) or b.get("nets", 0)):
            continue                      # non-discriminative: host structure
        if (m.get("cells", 0) or m.get("nets", 0)):
            out[pat] = {"cells": m.get("cells", 0), "nets": m.get("nets", 0)}
    return out


def _route_matches(post_route, label, cfg, patterns):
    """Total discriminative cell+net matches for one config."""
    cfgs = post_route.get(label, {})
    if cfg not in cfgs:
        return None
    pats = cfgs[cfg].get("patterns", {})
    total = 0
    for pat in patterns:
        p = pats.get(pat, {})
        total += p.get("cells", 0) + p.get("nets", 0)
    return total


def classify_design(retention, payload_identical_by_cfg=None,
                    reproduced=None):
    """Pure classifier. Returns an ordered verdict dict.

    retention: {"post_synth": {label: {"patterns": {...}}},
                "post_route": {label: {cfg: {"patterns": {...}}}}}
    payload_identical_by_cfg: {cfg: bool} -- malicious payload byte-identical
                              to matched benign (bitstream-level no-trace)
    reproduced: bool|None -- does a rebuild reproduce the shipped corpus
                             payload byte-exactly (provenance evidence)
    """
    post_synth = retention.get("post_synth", {})
    post_route = retention.get("post_route", {})
    payload_identical_by_cfg = payload_identical_by_cfg or {}

    if BENIGN not in post_synth or MALICIOUS not in post_synth:
        return OrderedDict(trace=INDETERMINATE,
                           reason="post-synthesis evidence missing for one or "
                                  "both labels (benign control is mandatory)",
                           discriminative_patterns={},
                           post_route_configs={}, valid_pairs=[],
                           invalid_pairs=[], admission=REJECT_INCOMPLETE)

    disc = discriminative_patterns(post_synth)

    # --- stage 1: synthesis --------------------------------------------------
    if not disc:
        return OrderedDict(
            trace=NO_TRACE_AFTER_SYNTHESIS,
            reason="zero discriminative trojan cells/nets in the "
                   "post-synthesis netlist; the trojan is not in the "
                   "hardware. A differing bitstream, if any, is dead-logic "
                   "synthesis residue and is NOT trojan evidence.",
            discriminative_patterns={}, post_route_configs={},
            valid_pairs=[], invalid_pairs=[], admission=REJECT_NO_TRACE)

    # --- stage 2: implementation --------------------------------------------
    cfgs = sorted(post_route.get(MALICIOUS, {}))
    if not cfgs:
        return OrderedDict(
            trace=INDETERMINATE,
            reason="post-synthesis trojan present but no post-route evidence; "
                   "retention through implementation is unproven",
            discriminative_patterns=disc, post_route_configs={},
            valid_pairs=[], invalid_pairs=[], admission=REJECT_INCOMPLETE)

    route_counts, lost_at_route = {}, []
    for cfg in cfgs:
        n = _route_matches(post_route, MALICIOUS, cfg, disc)
        route_counts[cfg] = n
        if not n:
            lost_at_route.append(cfg)

    # --- stage 3: bitstream --------------------------------------------------
    identical = sorted(c for c, v in payload_identical_by_cfg.items() if v)

    if lost_at_route or identical:
        bits = []
        if lost_at_route:
            bits.append(f"discriminative matches vanish post-route in "
                        f"{lost_at_route}")
        if identical:
            bits.append(f"malicious FDRI payload byte-identical to matched "
                        f"benign in {identical}")
        return OrderedDict(
            trace=NO_TRACE_AFTER_IMPLEMENTATION, reason="; ".join(bits),
            discriminative_patterns=disc, post_route_configs=route_counts,
            valid_pairs=[], invalid_pairs=sorted(set(lost_at_route) | set(identical)),
            admission=REJECT_NO_TRACE)

    # --- retained ------------------------------------------------------------
    verdict = OrderedDict(
        trace=TROJAN_RETAINED,
        reason=f"{len(disc)} discriminative pattern(s) present post-synthesis "
               f"and post-route in all {len(cfgs)} configuration(s); benign "
               f"control clean; no payload collapsed to its benign twin",
        discriminative_patterns=disc, post_route_configs=route_counts,
        valid_pairs=cfgs, invalid_pairs=[])

    if reproduced is False:
        verdict["admission"] = HOLD
        verdict["admission_reason"] = (
            "trojan retention verified, but rebuilds do not reproduce the "
            "shipped corpus payload byte-exactly, so this host's corpus "
            "provenance is unestablished. Admit only after provenance is "
            "resolved or the corpus files are replaced by these rebuilds.")
    else:
        verdict["admission"] = ADMIT
        verdict["admission_reason"] = (
            "retention verified through routing with a clean benign control, "
            "and >=1 valid matched benign/malicious pair differing at the "
            "FDRI-payload level"
            + ("; rebuild reproduces the corpus payload byte-exactly"
               if reproduced else ""))
    return verdict


# --- evidence loading -------------------------------------------------------
def load_pilot_evidence(pilot_dir):
    """Assemble per-design evidence from the Phase 0.5B pilot artifacts."""
    with open(os.path.join(pilot_dir, "trojan_retention.json")) as f:
        retention = json.load(f)["designs"]

    identical = {}
    diffs_path = os.path.join(pilot_dir, "matched_pair_frame_diffs.csv")
    if os.path.exists(diffs_path):
        with open(diffs_path) as f:
            for row in csv.DictReader(f):
                identical.setdefault(row["design"], {})[row["config"]] = (
                    row["payloads_identical"].strip().lower() == "true")

    reproduced = {}
    repro_path = os.path.join(pilot_dir, "corpus_reproduction.json")
    if os.path.exists(repro_path):
        with open(repro_path) as f:
            for r in json.load(f)["results"]:
                d = r["design"]
                reproduced[d] = reproduced.get(d, True) and bool(
                    r.get("reproduced"))
    return retention, identical, reproduced


def main():
    p = argparse.ArgumentParser(description="Phase 0.5C retention screen")
    p.add_argument("--pilot-dir", default="rebuild_pilot")
    p.add_argument("--out", default=os.path.join("corpus_out",
                                                 "retention_screen.json"))
    args = p.parse_args()

    retention, identical, reproduced = load_pilot_evidence(args.pilot_dir)
    print("=== Phase 0.5C retention screen ===")
    print(f"evidence: {args.pilot_dir} | {len(retention)} design(s)\n")

    results = {}
    for design in sorted(retention):
        v = classify_design(retention[design],
                            payload_identical_by_cfg=identical.get(design),
                            reproduced=reproduced.get(design))
        results[design] = v
        pats = ", ".join(f"{k}({d['cells']}c,{d['nets']}n)"
                         for k, d in v["discriminative_patterns"].items())
        print(f"  {design}")
        print(f"    trace      : {v['trace']}")
        print(f"    admission  : {v['admission']}")
        print(f"    patterns   : {pats or '(none discriminative)'}")
        print(f"    post-route : {v['post_route_configs'] or '-'}")
        print(f"    reason     : {v['reason']}")
        print()

    counts = {}
    for v in results.values():
        counts[v["admission"]] = counts.get(v["admission"], 0) + 1
    admitted = sorted(d for d, v in results.items()
                      if v["admission"] == ADMIT)
    print(f"admission summary: {counts}")
    print(f"ADMITTED for localization corpus: {admitted or 'none'}")

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "evidence_dir": os.path.abspath(args.pilot_dir),
        "taxonomy": {
            TROJAN_RETAINED:
                "discriminative trojan cells/nets post-synthesis AND "
                "post-route in every configuration; benign control clean",
            NO_TRACE_AFTER_SYNTHESIS:
                "zero discriminative matches post-synthesis; trojan absent "
                "from the hardware. Primary and strictest test -- a design "
                "can fail here while still producing a differing bitstream",
            NO_TRACE_AFTER_IMPLEMENTATION:
                "present post-synthesis but lost post-route in >=1 config, "
                "or malicious FDRI payload byte-identical to matched benign",
            INDETERMINATE: "required evidence missing; never a pass",
        },
        "admission_verdicts": {
            ADMIT: "retention verified + valid matched pair(s) + provenance",
            REJECT_NO_TRACE: "no live trojan in the built hardware",
            HOLD: "retention verified but corpus provenance unestablished",
            REJECT_INCOMPLETE: "evidence insufficient to decide",
        },
        "rules": [
            "a pattern counts only if DISCRIMINATIVE: nonzero in malicious "
            "AND zero in the matched benign control",
            "patterns are evaluated per pattern, never pooled",
            "no DONT_TOUCH/KEEP may be applied; if synthesis removes the "
            "trojan that is the result",
            "bitstream difference is NOT evidence of a trojan (PIC16F84-T100 "
            "differs by 199 frames with no live trojan)",
            "payload identity is confirmed by exact byte comparison; digests "
            "may only propose",
        ],
        "results": results,
        "admitted_hosts": admitted,
        "admission_counts": counts,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nscreen -> {args.out}")


if __name__ == "__main__":
    main()
