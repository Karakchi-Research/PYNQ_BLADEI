# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C -- per-design admissibility overlay.
#
#              Merges every admissibility signal produced so far into one
#              per-design table that a split can consult to exclude
#              non-admitted hosts by construction:
#
#                1. Vivado retention (STRONGEST): the 0.5B pilot
#                   (corpus_out/retention_screen.json) and the synthesis-only
#                   screen (corpus_out/retention_screen_synth.json). A measured
#                   NO_TRACE / REJECT is authoritative.
#                2. Static tie-off audit (SCREENING HEURISTIC):
#                   corpus_out/wrapper_tieoff_audit.json -- used only where no
#                   Vivado verdict exists, and always labelled as a heuristic.
#
#              WHY AN OVERLAY, NOT A CORPUS-INDEX EDIT. The corpus index is
#              manifest-locked and its schema is frozen (see the Phase 0.5
#              decisions); mutating it would break provenance. This overlay is
#              a separate artifact keyed by design, joined on design_key, that
#              the split path can read alongside the index. It NEVER changes
#              the index or the manifest.
#
#              PRECEDENCE, applied per design:
#                MEASURED_REJECT   -- Vivado screen says NO_TRACE_* (the
#                                     trojan is not in the built hardware).
#                                     Exclude from the localization corpus.
#                MEASURED_ADMIT    -- Vivado screen ADMIT (retained + valid
#                                     matched pair).
#                MEASURED_HOLD     -- Vivado ADMIT-blocked on provenance.
#                HEURISTIC_REVIEW  -- no Vivado verdict; tie-off audit nominated
#                                     it (FROZEN / ALL_TIED). Needs the screen.
#                UNSCREENED        -- no Vivado verdict, tie-off says LIVE or
#                                     INDETERMINATE. Status unknown; not a pass.
#
#              This does not decide anything the underlying artifacts did not;
#              it only composes them with an explicit precedence and records
#              which signal governed each design.
#
# Usage:
#   python3 admissibility_overlay.py
#     [--pilot corpus_out/retention_screen.json]
#     [--synth corpus_out/retention_screen_synth.json]
#     [--tieoff corpus_out/wrapper_tieoff_audit.json]
#     [--index corpus_out/corpus_index.json]
#     [--out corpus_out/admissibility_overlay.json]

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

SCHEMA = "admissibility_overlay_v1"

MEASURED_REJECT = "MEASURED_REJECT"
MEASURED_ADMIT = "MEASURED_ADMIT"
MEASURED_HOLD = "MEASURED_HOLD"
HEURISTIC_REVIEW = "HEURISTIC_REVIEW"
UNSCREENED = "UNSCREENED"

# Vivado trace/admission -> overlay status.
_NO_TRACE = ("NO_TRACE_AFTER_SYNTHESIS", "NO_TRACE_AFTER_IMPLEMENTATION")
_TIEOFF_NOMINATED = ("TROJAN_STATE_FROZEN", "TROJAN_INPUTS_ALL_TIED")


def load(path):
    return json.load(open(path)) if path and os.path.exists(path) else None


def host_of(design_or_bench):
    """Normalise a corpus design_key or benchmark dir to a design tag.

    Corpus keys are AES_T1000; benchmark dirs / screen tags are AES-T1000.
    Join on the hyphenated tag.
    """
    return design_or_bench.replace("_", "-")


def vivado_status(rec):
    """Overlay status from a Vivado retention verdict record."""
    trace = rec.get("trace")
    adm = rec.get("admission")
    if trace in _NO_TRACE or adm in ("REJECT_NO_TRACE",):
        return MEASURED_REJECT
    if adm == "ADMIT_LOCALIZATION" or adm == "ADMIT":
        return MEASURED_ADMIT
    if adm == "HOLD":
        return MEASURED_HOLD
    return None  # INDETERMINATE / incomplete -> defer to heuristic


def main():
    p = argparse.ArgumentParser(description="Phase 0.5C admissibility overlay")
    p.add_argument("--pilot", default="corpus_out/retention_screen.json")
    p.add_argument("--synth", default="corpus_out/retention_screen_synth.json")
    p.add_argument("--tieoff", default="corpus_out/wrapper_tieoff_audit.json")
    p.add_argument("--index", default="corpus_out/corpus_index.json")
    p.add_argument("--out", default="corpus_out/admissibility_overlay.json")
    args = p.parse_args()

    pilot = load(args.pilot)
    synth = load(args.synth)
    tie = load(args.tieoff)
    index = load(args.index)

    # --- collect Vivado verdicts (pilot first, synth overrides/extends) ------
    vivado = {}   # design-tag -> (status, source, detail)
    if pilot:
        # The pilot screen keys per-design verdicts under "results".
        for d, rec in pilot.get("results", {}).items():
            if not isinstance(rec, dict) or "trace" not in rec:
                continue
            s = vivado_status(rec)
            if s:
                vivado[host_of(d)] = (s, "pilot_retention_screen",
                                      rec.get("trace") or rec.get("admission"))
    if synth:
        for d, rec in synth.get("designs", {}).items():
            s = vivado_status(rec)
            if s:
                vivado[host_of(d)] = (s, "synthesis_screen", rec.get("trace"))

    # --- tie-off heuristic verdicts -----------------------------------------
    tieoff = {}
    if tie:
        for r in tie.get("per_benchmark", []):
            tieoff[host_of(r["benchmark"])] = r["verdict"]

    # --- corpus footprint per design (files / payloads) ----------------------
    corpus = defaultdict(lambda: {"malicious_files": 0, "benign_files": 0,
                                  "malicious_payloads": set()})
    if index:
        for r in index["files"]:
            e = corpus[host_of(r["design_key"])]
            if r["label"] == 1:
                e["malicious_files"] += 1
                e["malicious_payloads"].add(r["payload_id"])
            else:
                e["benign_files"] += 1

    # --- compose -------------------------------------------------------------
    designs = sorted(set(vivado) | set(tieoff) | set(corpus))
    overlay, totals = {}, Counter()
    excl_files = excl_payloads = 0
    for d in designs:
        if d in vivado:
            status, source, detail = vivado[d]
        elif tieoff.get(d) in _TIEOFF_NOMINATED:
            status, source, detail = (HEURISTIC_REVIEW, "tieoff_audit",
                                      tieoff[d])
        else:
            status, source, detail = (UNSCREENED, "tieoff_audit",
                                      tieoff.get(d))
        c = corpus.get(d, {})
        row = {"status": status, "governed_by": source, "detail": detail,
               "tieoff_verdict": tieoff.get(d),
               "malicious_files": c.get("malicious_files", 0),
               "benign_files": c.get("benign_files", 0),
               "malicious_payloads": len(c.get("malicious_payloads", set()))}
        overlay[d] = row
        totals[status] += 1
        if status == MEASURED_REJECT:
            excl_files += row["malicious_files"]
            excl_payloads += row["malicious_payloads"]

    print("=== Phase 0.5C admissibility overlay ===")
    print("designs: %d | Vivado-measured: %d | tie-off only: %d\n"
          % (len(designs), len(vivado), len(designs) - len(vivado)))
    for status in (MEASURED_REJECT, MEASURED_ADMIT, MEASURED_HOLD,
                   HEURISTIC_REVIEW, UNSCREENED):
        if totals[status]:
            ds = sorted(d for d, r in overlay.items()
                        if r["status"] == status)
            print("  %-18s %3d  %s" % (status, totals[status],
                                       ", ".join(ds[:12])
                                       + (" ..." if len(ds) > 12 else "")))
    print("\nMEASURED_REJECT removes %d malicious files / %d unique payloads "
          "from the corpus by construction." % (excl_files, excl_payloads))
    print("(These are Vivado-confirmed malicious-label / no-live-trojan.)")

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "precedence": ["Vivado retention (pilot, then synthesis screen)",
                          "tie-off audit (heuristic, only where unmeasured)"],
           "sources": {"pilot": args.pilot, "synth": args.synth,
                       "tieoff": args.tieoff, "index": args.index},
           "status_counts": dict(totals),
           "measured_reject_removes": {"malicious_files": excl_files,
                                       "unique_payloads": excl_payloads},
           "note": ("overlay only; the corpus index and manifest are "
                    "unchanged. Join on the hyphenated design tag. A split "
                    "should exclude MEASURED_REJECT hosts; HEURISTIC_REVIEW "
                    "hosts await the Vivado screen and are NOT a pass."),
           "designs": overlay}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=2, default=list)
    print("\noverlay -> %s" % args.out)


if __name__ == "__main__":
    main()
