# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C step 1 -- static inventory of candidate HOST designs
#              for corpus expansion. Answers, without building anything:
#
#                - how many INDEPENDENT host circuits the benchmark tree
#                  actually contains (the quantity that governs grouped-split
#                  feasibility), as opposed to trojan variants of the same host;
#                - which benchmark directories are hardware-TROJAN benchmarks
#                  (TjFree/TjIn RTL pair) versus LOGIC-OBFUSCATION benchmarks
#                  (key-based locking). Trust-Hub distributes and labels both
#                  categories correctly; they were gathered together during
#                  corpus assembly, so this separates them again.
#                - each host's current corpus status: payload component, unique
#                  payload count, and how many of its malicious files are
#                  audited no-bitstream-trace quarantine cases;
#                - a heuristic wrapper tie-off risk flag: the PIC16F84-T100
#                  failure mode found by the rebuild pilot, where the harness
#                  wrapper ties off the inputs feeding the trojan trigger so
#                  synthesis deletes the trojan.
#
#              Static analysis only -- no Vivado, no builds. The tie-off flag
#              is a SCREENING HEURISTIC that nominates designs for the
#              synthesis-level retention screen; it is not evidence of
#              retention or of its absence. Only Vivado post-synthesis
#              enumeration decides that (see PHASE05C_PLAN.md).
#
# Usage:
#   python3 candidate_host_inventory.py [--bench-dir DIR] [--outdir corpus_out]

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

# Trojan-variant suffixes to strip to reach the HOST circuit name.
_VARIANT = re.compile(r"-(T|CS|CY|NC|NR|NS|RN|SL|BE|BR|BS)\d+.*$")
# Constant tie-off of a vector/scalar signal, e.g. `assign prog_dat = 14'h0000;`
_TIEOFF = re.compile(
    r"assign\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(\d+'[hbdo][0-9a-fA-FxXzZ_]+|\{[^}]*1'b[01][^}]*\}|1'b[01]|0)\s*;")

OBFUSCATION_MARKERS = ("obfuscation method", "logic locking", "key size",
                       "sat-attack")


def host_of(bench_name):
    return _VARIANT.sub("", bench_name)


def classify(bench_dir):
    """(kind, evidence) for one benchmark directory.

    'trojan'       -- ships src/TjFree and src/TjIn RTL variants
    'obfuscation'  -- readme documents a logic-locking/obfuscation taxonomy
    'unknown'      -- neither signature present
    """
    src = os.path.join(bench_dir, "src")
    has_free = os.path.isdir(os.path.join(src, "TjFree"))
    has_in = os.path.isdir(os.path.join(src, "TjIn"))
    if has_free and has_in:
        return "trojan", "src/TjFree + src/TjIn present"
    readmes = [f for f in os.listdir(bench_dir)
               if f.lower().startswith("readme")]
    for r in readmes:
        try:
            with open(os.path.join(bench_dir, r), errors="ignore") as fh:
                text = fh.read().lower()
        except OSError:
            continue
        hits = [m for m in OBFUSCATION_MARKERS if m in text]
        if hits:
            method = ""
            for line in text.splitlines():
                if "obfuscation method" in line:
                    method = line.strip()
                    break
            return "obfuscation", f"readme markers {hits}; {method}"
    if has_free or has_in:
        return "unknown", f"partial RTL (TjFree={has_free}, TjIn={has_in})"
    return "unknown", "no TjFree/TjIn, no obfuscation markers"


def tieoff_scan(bench_dir):
    """Heuristic: constant tie-offs in the harness wrapper of the TjIn build.

    The pilot's PIC16F84-T100 finding: `top.v` ties `prog_dat = 14'h0000`, the
    trojan's trigger counter can never advance, and synthesis deletes the
    trojan. Returns the tied signal names found in wrapper-looking files.
    """
    tjin = os.path.join(bench_dir, "src", "TjIn")
    if not os.path.isdir(tjin):
        return {"scanned": False, "tied_signals": [], "n_wrapper_files": 0}
    tied, n = [], 0
    for fn in os.listdir(tjin):
        if not fn.lower().endswith((".v", ".sv")):
            continue
        # Wrapper-looking files only: top-level harnesses.
        if "top" not in fn.lower() and "wrapper" not in fn.lower():
            continue
        n += 1
        try:
            with open(os.path.join(tjin, fn), errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        for m in _TIEOFF.finditer(text):
            tied.append({"file": fn, "signal": m.group(1),
                         "value": m.group(2)})
    return {"scanned": True, "tied_signals": tied, "n_wrapper_files": n}


def main():
    p = argparse.ArgumentParser(description="Phase 0.5C candidate host inventory")
    p.add_argument("--bench-dir",
                   default=os.path.expanduser(
                       "~/Desktop/Karakchi-Research/trusthub_benchmarks"))
    p.add_argument("--index", default=os.path.join("corpus_out",
                                                   "corpus_index.json"))
    p.add_argument("--outdir", default="corpus_out")
    args = p.parse_args()

    if not os.path.isdir(args.bench_dir):
        sys.exit(f"benchmark tree not found: {args.bench_dir}")
    benches = sorted(d for d in os.listdir(args.bench_dir)
                     if os.path.isdir(os.path.join(args.bench_dir, d)))
    print(f"=== Phase 0.5C candidate host inventory ===")
    print(f"{len(benches)} benchmark directories in {args.bench_dir}\n")

    per_bench, hosts = {}, defaultdict(lambda: {
        "benchmarks": [], "kinds": set(), "tieoff_flagged": []})
    for b in benches:
        bd = os.path.join(args.bench_dir, b)
        kind, evidence = classify(bd)
        tie = tieoff_scan(bd)
        h = host_of(b)
        per_bench[b] = {"host": h, "kind": kind, "evidence": evidence,
                        "tieoff": tie}
        hosts[h]["benchmarks"].append(b)
        hosts[h]["kinds"].add(kind)
        if tie["tied_signals"]:
            hosts[h]["tieoff_flagged"].append(b)

    kind_counts = Counter(v["kind"] for v in per_bench.values())
    print("benchmark directories by kind:")
    for k, c in kind_counts.most_common():
        print(f"    {k:<14} {c:>4}")

    trojan_hosts = sorted(h for h, v in hosts.items()
                          if "trojan" in v["kinds"])
    obf_hosts = sorted(h for h, v in hosts.items()
                       if v["kinds"] == {"obfuscation"})
    print(f"\nINDEPENDENT HOST CIRCUITS")
    print(f"    trojan-benchmark hosts      : {len(trojan_hosts)}  "
          f"{trojan_hosts}")
    print(f"    obfuscation-only hosts      : {len(obf_hosts)}  {obf_hosts}")
    print(f"    -> the trojan-host count is the ceiling on independent")
    print(f"       host designs obtainable from this tree.")

    # ---- cross-reference the corpus index ---------------------------------
    corpus = {}
    if os.path.exists(args.index):
        with open(args.index) as fh:
            index = json.load(fh)
        by_host = defaultdict(lambda: {"files": 0, "quarantined": 0,
                                       "payloads": set(),
                                       "components": set()})
        for r in index["files"]:
            # corpus design keys look like AES_T1000 / wb_conmax_T300
            key = r["design_key"]
            h = re.sub(r"_T\d+.*$", "", key)
            e = by_host[h]
            e["files"] += 1
            e["quarantined"] += bool(r["quarantined"])
            e["payloads"].add(r["payload_id"])
            e["components"].add(r["component_id"])
        corpus = {h: {"files": v["files"], "quarantined": v["quarantined"],
                      "unique_payloads": len(v["payloads"]),
                      "components": sorted(v["components"])}
                  for h, v in by_host.items()}
        print(f"\nCORPUS STATUS PER TROJAN HOST "
              f"(from {args.index}, manifest {index['manifest_id']})")
        print(f"    {'host':<18}{'files':>6}{'uniq':>6}{'comps':>7}"
              f"{'quarantined':>13}  tie-off flagged benchmarks")
        for h in trojan_hosts:
            c = corpus.get(h, {"files": 0, "unique_payloads": 0,
                               "components": [], "quarantined": 0})
            flags = hosts[h]["tieoff_flagged"]
            note = f"{len(flags)}/{len(hosts[h]['benchmarks'])}" if flags \
                else "-"
            print(f"    {h:<18}{c['files']:>6}{c['unique_payloads']:>6}"
                  f"{len(c['components']):>7}{c['quarantined']:>13}  {note}")

    flagged = {h: v["tieoff_flagged"] for h, v in hosts.items()
               if v["tieoff_flagged"]}
    print(f"\nWRAPPER TIE-OFF SCREENING HEURISTIC")
    print(f"    hosts with >=1 tie-off-flagged benchmark: {len(flagged)}")
    for h, bs in sorted(flagged.items()):
        sig = per_bench[bs[0]]["tieoff"]["tied_signals"][:2]
        print(f"      {h:<18} {len(bs):>3} benchmark(s), e.g. "
              f"{[s['signal'] + '=' + s['value'] for s in sig]}")
    print(f"    NOTE: heuristic only -- nominates designs for the Vivado")
    print(f"    post-synthesis retention screen; proves nothing on its own.")

    out = {
        "schema": "candidate_host_inventory_v1",
        "generated": datetime.now(timezone.utc).isoformat(),
        "bench_dir": args.bench_dir,
        "n_benchmark_dirs": len(benches),
        "benchmark_kind_counts": dict(kind_counts),
        "independent_hosts": {
            "trojan_benchmark_hosts": trojan_hosts,
            "n_trojan_benchmark_hosts": len(trojan_hosts),
            "obfuscation_only_hosts": obf_hosts,
            "n_obfuscation_only_hosts": len(obf_hosts),
            "interpretation": (
                "n_trojan_benchmark_hosts is the CEILING on independent host "
                "designs obtainable from this benchmark tree. Grouped-split "
                "feasibility is governed by this number, not by the file "
                "count and not by the number of trojan variants."),
        },
        "corpus_status_per_host": corpus,
        "tieoff_heuristic": {
            "flagged_hosts": {h: bs for h, bs in sorted(flagged.items())},
            "method": ("constant tie-off assignments in TjIn wrapper files "
                       "(top*/wrapper*); mirrors the pilot's PIC16F84-T100 "
                       "failure where top.v ties prog_dat=14'h0000 and "
                       "synthesis deletes the trojan"),
            "limitation": ("SCREENING HEURISTIC ONLY -- nominates candidates "
                           "for the Vivado post-synthesis retention screen. "
                           "It cannot confirm retention (a non-tied design "
                           "may still lose its trojan) nor confirm deletion "
                           "(a tied signal may not feed the trigger)."),
        },
        "per_benchmark": per_bench,
    }
    os.makedirs(args.outdir, exist_ok=True)
    path = os.path.join(args.outdir, "candidate_host_inventory.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2, default=list)
    print(f"\ninventory -> {path}")


if __name__ == "__main__":
    main()
