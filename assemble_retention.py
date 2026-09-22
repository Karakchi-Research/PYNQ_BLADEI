# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C -- assemble the retention screen's synthesis evidence
#              into the trojan_retention.json schema retention_screen.py
#              consumes, and classify each design.
#
#              Consumes the `trojan_post_synth.txt` files emitted by
#              screen_trojan_retention.sh (via pilot_synth.tcl) -- one per
#              (design, label) -- parses the per-pattern cell/net counts, and
#              runs the same pure `classify_design` the pilot used, so the
#              measured verdict is directly comparable to the tie-off audit's
#              static nomination.
#
#              SYNTHESIS-ONLY input. With no post_route evidence, a design
#              whose trojan survives synthesis classifies as INDETERMINATE
#              (retention through routing unproven) -- never silently ADMIT.
#              The verdict this screen is built to establish is the strict
#              NO_TRACE_AFTER_SYNTHESIS, decided from post-synthesis alone;
#              that is the tie-off audit's prediction for the nominated
#              designs and the point of the run.
#
# Usage:
#   python3 assemble_retention.py --screen-dir <retention_screen dir>
#                                 [--tieoff corpus_out/wrapper_tieoff_audit.json]
#                                 [--out corpus_out/retention_screen_synth.json]

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

from retention_screen import (NO_TRACE_AFTER_SYNTHESIS, REJECT_NO_TRACE,
                              classify_design)

_PAT = re.compile(r"PATTERN (\S+) cells=(\d+) nets=(\d+)")
_TOT = re.compile(r"total_(cells|nets)=(\d+)")


def parse_report(path):
    """One trojan_post_synth.txt -> {'patterns': {pat: {cells, nets}}, ...}."""
    patterns, totals = {}, {}
    with open(path) as fh:
        for line in fh:
            m = _PAT.match(line.strip())
            if m:
                patterns[m.group(1)] = {"cells": int(m.group(2)),
                                        "nets": int(m.group(3))}
                continue
            t = _TOT.search(line)
            if t:
                totals["total_" + t.group(1)] = int(t.group(2))
    rec = {"patterns": patterns}
    rec.update(totals)
    return rec


def tieoff_verdicts(path):
    if not path or not os.path.exists(path):
        return {}
    d = json.load(open(path))
    return {r["benchmark"]: r["verdict"] for r in d.get("per_benchmark", [])}


def main():
    p = argparse.ArgumentParser(description="Assemble + classify retention "
                                            "screen synthesis evidence")
    p.add_argument("--screen-dir", required=True,
                   help="dir with <design>/<label>/reports/trojan_post_synth.txt")
    p.add_argument("--tieoff",
                   default="corpus_out/wrapper_tieoff_audit.json")
    p.add_argument("--out",
                   default="corpus_out/retention_screen_synth.json")
    args = p.parse_args()

    designs = sorted(d for d in os.listdir(args.screen_dir)
                     if os.path.isdir(os.path.join(args.screen_dir, d)))
    if not designs:
        sys.exit("no design dirs under %s" % args.screen_dir)

    tie = tieoff_verdicts(args.tieoff)
    retention = {}
    for d in designs:
        post_synth = {}
        for lab in ("TjFree", "TjIn"):
            rp = os.path.join(args.screen_dir, d, lab, "reports",
                              "trojan_post_synth.txt")
            if os.path.exists(rp):
                post_synth[lab] = parse_report(rp)
        if post_synth:
            retention[d] = {"post_synth": post_synth, "post_route": {}}

    print("=== retention screen (synthesis-only) — assemble + classify ===")
    print("evidence: %s | %d design(s)\n" % (args.screen_dir, len(retention)))

    results, agree = {}, []
    for d in sorted(retention):
        v = classify_design(retention[d])
        results[d] = v
        disc = v["discriminative_patterns"]
        ps = retention[d]["post_synth"]
        mal_cells = sum(x["cells"] for x in ps.get("TjIn", {})
                        .get("patterns", {}).values())
        ben_cells = sum(x["cells"] for x in ps.get("TjFree", {})
                        .get("patterns", {}).values())
        t_verdict = tie.get(d, "-")
        # The tie-off audit's FROZEN prediction ⇔ this screen's NO_TRACE.
        predicted_no_trace = t_verdict in ("TROJAN_STATE_FROZEN",
                                           "TROJAN_INPUTS_ALL_TIED")
        measured_no_trace = v["trace"] == NO_TRACE_AFTER_SYNTHESIS
        match = (predicted_no_trace == measured_no_trace)
        agree.append(match)
        print("  %s" % d)
        print("    trojan cells post-synth : benign=%d malicious=%d"
              % (ben_cells, mal_cells))
        print("    trace                   : %s" % v["trace"])
        print("    discriminative patterns : %s"
              % (", ".join("%s(%dc,%dn)" % (k, x["cells"], x["nets"])
                           for k, x in disc.items()) or "(none)"))
        print("    tie-off audit predicted : %s%s"
              % (t_verdict, "  [NO-TRACE]" if predicted_no_trace else ""))
        print("    prediction vs measured  : %s"
              % ("AGREE" if match else "DISAGREE"))
        print()

    n_no_trace = sum(1 for v in results.values()
                     if v["trace"] == NO_TRACE_AFTER_SYNTHESIS)
    print("NO_TRACE_AFTER_SYNTHESIS: %d/%d" % (n_no_trace, len(results)))
    print("tie-off audit agreement : %d/%d"
          % (sum(agree), len(agree)))

    out = {
        "schema": "retention_screen_synth_v1",
        "generated": datetime.now(timezone.utc).isoformat(),
        "screen_dir": os.path.abspath(args.screen_dir),
        "stage": "synthesis-only (post_route not measured)",
        "n_designs": len(results),
        "n_no_trace_after_synthesis": n_no_trace,
        "tieoff_agreement": {"n_agree": sum(agree), "n_total": len(agree)},
        "designs": {d: {"trace": v["trace"], "admission": v["admission"],
                        "discriminative_patterns": v["discriminative_patterns"],
                        "tieoff_verdict": tie.get(d)}
                    for d, v in results.items()},
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=2)
    print("\nresults -> %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
