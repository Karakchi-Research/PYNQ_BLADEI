# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Characterize the format-aware detector's false positives on
#              the benign builds of l3f_format_aware_results.json (B_Explore:
#              the same netlist as B_Default, routed with another directive).
#              No bitstream is built.
#
#              Timing join. A build under l3_slack/<design>/pN takes the
#              per_period entry with period_ns == N from
#              l3_timing_threshold_<design>.json; a build outside l3_slack
#              gets wns_ns = meets_timing = None. An l3_slack build with no
#              matching entry raises. The WNS is the one recorded for that
#              (design, period), not a measurement of the B_Explore build.
#
#              Per build, from the saved flag reasons: flagged tiles, flagged
#              LUTs by class (new / function_changed / removed) and FF.ZINI /
#              FF.ZRST flags. EVASION CHECK: a benign build that meets timing
#              and still has flags shows that a route-directive change alone
#              trips the detector. That set is printed and must be empty; if
#              not, the report is written and the run exits 1.
#
#              Route-thru shape. The results keep no LUT INITs, so each
#              flagged LUT is re-decoded from the same bitstreams (SHA-256
#              checked against the results' inputs, prjxray-db SHA against
#              theirs, and the re-derived class must equal the saved one). A
#              table is wire-shaped when its output is one input or that
#              input's complement: over all 64 rows (o6), or over one 32-row
#              half (lo32 = O5 of a fractured LUT, hi32 = O6 when A6 = 1).
#              lut_canon is not changed; each LUT records why its route_thru
#              rule did not apply.
#
#              This file is stdlib only. The re-decode imports tile_decode
#              (numpy) lazily; --no-inits skips it.
#
# Usage:
#   python3 analyze_benign_flags.py [--results PATH] [--timing-dir DIR]
#                                   [--artifacts DIR] [--db DIR]
#                                   [--no-inits] [--out PATH]

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

SCHEMA = "benign_flag_analysis_v1"
RESULTS_SCHEMA = "l3f_format_aware_eval_v1"
RESULTS = os.path.join("localization_corpus", "format_aware",
                       "l3f_format_aware_results.json")
OUT = os.path.join("localization_corpus", "format_aware",
                   "benign_flag_analysis.json")
TIMING_DIR = os.path.expanduser(
    "~/Desktop/BLADEI_research_archive/outputs/localization_corpus")
TIMING_FILE = "l3_timing_threshold_%s.json"

# Mirrors tile_decode.FLAG_LUT_CLASSES / FLAG_FEATURE_KEYS; checked against
# them whenever tile_decode is imported.
FLAG_LUT_CLASSES = ("new", "removed", "function_changed")
FF_KEYS = (("FF.ZINI", "ff_zini"), ("FF.ZRST", "ff_zrst"))

N_INPUTS = 6
HALF = 32

# lut_canon.classify's route_thru rules, for the report.
ROUTE_THRU_RULE = ("classify returns route_thru only when old == 0 and new "
                   "is a 64-row wire, new == 0 and old is a 64-row wire, or "
                   "both are 64-row wires; a flagged class therefore means "
                   "the non-zero side(s) failed that test")

_SLACK = re.compile(r"^l3_slack/([^/]+)/p(\d+)$")
_LUT_REASON = re.compile(r"^(\S+\.[A-D]LUT) (\w+)$")


# ---------------------------------------------------------------------------
# Timing join.
# ---------------------------------------------------------------------------
def folder_period(folder):
    """(design, period_ns) for l3_slack/<design>/pN, else None."""
    m = _SLACK.match(folder)
    return (m.group(1), float(m.group(2))) if m else None


def timing_table(docs):
    """{(design, period_ns): {"wns_ns", "meets_timing"}} from timing docs.
    A duplicate (design, period) raises."""
    table = {}
    for doc in docs:
        for e in doc["per_period"]:
            key = (doc["design"], float(e["period_ns"]))
            if key in table:
                raise ValueError("duplicate timing entry %s period %g" % key)
            table[key] = {"wns_ns": e["wns_ns"],
                          "meets_timing": e["meets_timing"]}
    return table


def join_timing(folder, table):
    fp = folder_period(folder)
    if fp is None:
        return {"wns_ns": None, "meets_timing": None}
    if fp not in table:
        raise KeyError("no timing entry for %s period %g ns (%s)"
                       % (fp[0], fp[1], folder))
    return dict(table[fp])


def met_and_flagged(rows):
    """Builds that meet timing yet carry flags: the evasion set."""
    return ["%s/%s" % (r["experiment"], r["build"]) for r in rows
            if r["meets_timing"] is True and r["flagged"] > 0]


def timing_unknown_and_flagged(rows):
    return ["%s/%s" % (r["experiment"], r["build"]) for r in rows
            if r["meets_timing"] is None and r["flagged"] > 0]


# ---------------------------------------------------------------------------
# Flag reasons.
# ---------------------------------------------------------------------------
def parse_reasons(tile, reasons):
    """([{"tile", "lut", "class"}], {"ff_zini": n, "ff_zrst": n}).
    A reason that is neither a flagged LUT class nor an FF flag raises."""
    luts, ff = [], {k: 0 for _, k in FF_KEYS}
    for r in reasons:
        if r[:1] in "+-":
            keys = [k for pat, k in FF_KEYS if pat in r]
            if len(keys) != 1:
                raise ValueError("%s: unknown feature reason %r" % (tile, r))
            ff[keys[0]] += 1
            continue
        m = _LUT_REASON.match(r)
        if not m or m.group(2) not in FLAG_LUT_CLASSES:
            raise ValueError("%s: unknown LUT reason %r" % (tile, r))
        luts.append({"tile": tile, "lut": m.group(1), "class": m.group(2)})
    return luts, ff


def benign_row(folder, build, rec, table):
    luts, ff = [], {k: 0 for _, k in FF_KEYS}
    for tile in rec["flagged"]:
        l, f = parse_reasons(tile, rec["flag_reasons"][tile])
        luts += l
        for k, n in f.items():
            ff[k] += n
    by_class = collections.Counter(l["class"] for l in luts)
    return {"experiment": folder, "build": build, "bit": rec["bit"],
            "reference": rec["reference"],
            **join_timing(folder, table),
            "flagged": len(rec["flagged"]),
            **{c: by_class[c] for c in FLAG_LUT_CLASSES},
            **ff,
            "route_thru_absorbed": rec["lut_classes"]["route_thru"],
            "lut_flags": luts}


# ---------------------------------------------------------------------------
# Route-thru shape.
# ---------------------------------------------------------------------------
def input_table(k, n=N_INPUTS):
    """Truth table of the identity on input k over n inputs (I0 = LSB)."""
    return sum(1 << i for i in range(1 << n) if (i >> k) & 1)


def wire_input(table, n=N_INPUTS):
    """"I<k>" / "~I<k>" if the n-input table passes input k through, else
    None."""
    mask = (1 << (1 << n)) - 1
    for k in range(n):
        t = input_table(k, n)
        if table == t:
            return "I%d" % k
        if table == t ^ mask:
            return "~I%d" % k
    return None


def lut_shape(init):
    """Wire test over the whole table and over each 32-row half."""
    return {"o6": wire_input(init),
            "lo32": wire_input(init & ((1 << HALF) - 1), N_INPUTS - 1),
            "hi32": wire_input(init >> HALF, N_INPUTS - 1)}


def is_route_thru_shaped(init):
    """Output equals one input or its complement over all 64 rows."""
    return wire_input(init) is not None


def why_not_route_thru(cls, old, new):
    """Why lut_canon.classify gave `cls` and not route_thru."""
    if cls == "new":
        return "new table is not a 64-row wire"
    if cls == "removed":
        return "old table is not a 64-row wire"
    if cls != "function_changed":
        raise ValueError("not a flagged class: %r" % cls)
    ow, nw = is_route_thru_shaped(old), is_route_thru_shaped(new)
    if ow and nw:
        raise ValueError("both sides are wires; classify says route_thru")
    if ow:
        return "old is a wire, new is a function"
    if nw:
        return "old is a function, new is a wire"
    return "neither side is a wire"


def lut_record(flag, old, new):
    sides = [(s, v) for s, v in (("old", old), ("new", new)) if v]
    shapes = {s: lut_shape(v) for s, v in sides}
    return {**flag,
            "old_init": "0x%016x" % old, "new_init": "0x%016x" % new,
            "old_shape": lut_shape(old), "new_shape": lut_shape(new),
            "route_thru_shaped": any(sh["o6"] for sh in shapes.values()),
            "half_wire_shaped": any(sh["lo32"] or sh["hi32"]
                                    for sh in shapes.values()),
            "why_not_route_thru": why_not_route_thru(flag["class"], old, new)}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def decode_flagged(results, rows, artifacts, db_dir):
    """[lut_record] for every flagged LUT of `rows`, re-decoded from the
    bitstreams the results were computed on."""
    from bitstream_io import ZYNQ7020_V4, fdri_payload_and_meta
    from lut_canon import classify
    from tile_decode import (FLAG_FEATURE_KEYS, FLAG_LUT_CLASSES as TD_LUT,
                             TileDecoder, payload_words)
    if tuple(TD_LUT) != FLAG_LUT_CLASSES \
            or tuple(FLAG_FEATURE_KEYS) != tuple(p for p, _ in FF_KEYS):
        raise ValueError("flag classes drifted from tile_decode")

    dec = TileDecoder.load(db_dir)
    if dec.db_sha != results["prjxray_db_sha"]:
        raise ValueError("prjxray-db %s is not the results' %s"
                         % (dec.db_sha, results["prjxray_db_sha"]))
    tiles = {t.name: t for t in dec.tiles}
    n = dec.far_map.n_frames

    def words(rel):
        path = os.path.join(artifacts, rel)
        got, want = sha256_file(path), results["inputs"].get(rel)
        if got != want:
            raise ValueError("%s: SHA-256 %s, results recorded %s"
                             % (path, got, want))
        payload = fdri_payload_and_meta(path, ZYNQ7020_V4)[0]
        return payload_words(payload, n, ZYNQ7020_V4.frame_words)

    out = []
    for row in rows:
        if not row["lut_flags"]:
            continue
        a, b = words(row["reference"]), words(row["bit"])
        by_tile = collections.defaultdict(list)
        for f in row["lut_flags"]:
            by_tile[f["tile"]].append(f)
        for tile, flags in sorted(by_tile.items()):
            luts_a = dec.decode(a, tiles[tile])[0]
            luts_b = dec.decode(b, tiles[tile])[0]
            for f in flags:
                old, new = luts_a[f["lut"]], luts_b[f["lut"]]
                got = classify(old, new)
                if got != f["class"]:
                    raise ValueError("%s/%s %s %s: re-decoded class %s, "
                                     "results say %s"
                                     % (row["experiment"], row["build"], tile,
                                        f["lut"], got, f["class"]))
                out.append({"experiment": row["experiment"],
                            "build": row["build"],
                            **lut_record(f, old, new)})
        print("  %s/%s decoded" % (row["experiment"], row["build"]),
              file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Summary and report.
# ---------------------------------------------------------------------------
def summarize(rows, luts):
    s = {"n_benign_builds": len(rows),
         "n_flagged_builds": sum(1 for r in rows if r["flagged"]),
         "flagged_tiles": sum(r["flagged"] for r in rows),
         "flagged_luts_by_class": {c: sum(r[c] for r in rows)
                                   for c in FLAG_LUT_CLASSES},
         **{k: sum(r[k] for r in rows) for _, k in FF_KEYS},
         "route_thru_absorbed": sum(r["route_thru_absorbed"] for r in rows),
         "met_and_flagged": met_and_flagged(rows),
         "timing_unknown_and_flagged": timing_unknown_and_flagged(rows)}
    if luts is None:
        s["route_thru"] = None
        return s
    s["route_thru"] = {
        "n_flagged_luts": len(luts),
        "route_thru_shaped": sum(l["route_thru_shaped"] for l in luts),
        "half_wire_shaped": sum(l["half_wire_shaped"] for l in luts),
        "route_thru_shaped_by_class": {
            c: sum(1 for l in luts if l["class"] == c and l["route_thru_shaped"])
            for c in FLAG_LUT_CLASSES},
        "half_wire_shaped_by_class": {
            c: sum(1 for l in luts if l["class"] == c and l["half_wire_shaped"])
            for c in FLAG_LUT_CLASSES},
        "why_not_route_thru": dict(sorted(collections.Counter(
            l["why_not_route_thru"] for l in luts).items())),
        "classify_rule": ROUTE_THRU_RULE,
    }
    return s


def _wns(x):
    return "-" if x is None else "%.3f" % x


def _met(x):
    return "-" if x is None else ("MET" if x else "FAIL")


def print_report(rows, summ):
    print("=== benign builds (every flag is a false positive) ===")
    print("%-24s %-10s %7s %5s %5s %4s %5s %4s %5s %5s %4s"
          % ("experiment", "build", "wns_ns", "time", "flag", "new", "fchg",
             "rem", "ZINI", "ZRST", "rt"))
    for r in rows:
        print("%-24s %-10s %7s %5s %5d %4d %5d %4d %5d %5d %4d"
              % (r["experiment"], r["build"], _wns(r["wns_ns"]),
                 _met(r["meets_timing"]), r["flagged"], r["new"],
                 r["function_changed"], r["removed"], r["ff_zini"],
                 r["ff_zrst"], r["route_thru_absorbed"]))
    print("(flag = flagged tiles; new/fchg/rem = flagged LUTs; rt = LUTs "
          "lut_canon absorbed as route_thru)")

    met = summ["met_and_flagged"]
    print("\ntiming-MET benign builds with flags: %s"
          % ("none" if not met else ", ".join(met)))
    if summ["timing_unknown_and_flagged"]:
        print("timing-unknown benign builds with flags: %s"
              % ", ".join(summ["timing_unknown_and_flagged"]))

    rt = summ["route_thru"]
    if rt is None:
        print("\nroute-thru shape: skipped (--no-inits)")
        return
    print("\n=== route-thru shape of %d flagged benign LUTs ==="
          % rt["n_flagged_luts"])
    print("%-18s %6s %7s %6s" % ("class", "luts", "wire64", "half"))
    for c in FLAG_LUT_CLASSES:
        print("%-18s %6d %7d %6d"
              % (c, summ["flagged_luts_by_class"][c],
                 rt["route_thru_shaped_by_class"][c],
                 rt["half_wire_shaped_by_class"][c]))
    print("route-thru-shaped (64-row wire, either non-zero side): %d / %d"
          % (rt["route_thru_shaped"], rt["n_flagged_luts"]))
    print("half-wire-shaped (O5 or A6=1 half is a wire): %d / %d"
          % (rt["half_wire_shaped"], rt["n_flagged_luts"]))
    print("why lut_canon's route_thru did not apply:")
    for why, k in rt["why_not_route_thru"].items():
        print("  %4d  %s" % (k, why))


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Characterize the format-aware detector's benign false "
                    "positives against timing and route-thru shape")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--timing-dir", default=TIMING_DIR)
    p.add_argument("--artifacts", default=None,
                   help="meson folder (default: the results' artifacts_root)")
    p.add_argument("--db", default=None,
                   help="prjxray-db folder (default: the results' db dir)")
    p.add_argument("--no-inits", action="store_true",
                   help="skip the re-decode (no numpy needed)")
    p.add_argument("--out", default=OUT)
    args = p.parse_args()

    with open(args.results) as fh:
        results = json.load(fh)
    if results.get("schema") != RESULTS_SCHEMA:
        sys.exit("%s: schema %r, expected %r"
                 % (args.results, results.get("schema"), RESULTS_SCHEMA))

    benign = [(f, b, r) for f, recs in results["builds"].items()
              for b, r in recs.items() if r["class"] == "benign"]
    designs = sorted({folder_period(f)[0] for f, _, _ in benign
                      if folder_period(f)})
    timing_inputs, docs = {}, []
    for d in designs:
        path = os.path.join(args.timing_dir, TIMING_FILE % d)
        with open(path) as fh:
            doc = json.load(fh)
        if doc.get("design") != d:
            sys.exit("%s: design %r, expected %r"
                     % (path, doc.get("design"), d))
        docs.append(doc)
        timing_inputs[path] = sha256_file(path)
    table = timing_table(docs)

    rows = [benign_row(f, b, r, table) for f, b, r in benign]

    luts = None
    artifacts = db_dir = None
    if not args.no_inits:
        artifacts = os.path.abspath(os.path.expanduser(
            args.artifacts or results["artifacts_root"]))
        db_dir = os.path.abspath(args.db or results["prjxray_db_dir"])
        luts = decode_flagged(results, rows, artifacts, db_dir)

    summ = summarize(rows, luts)
    print_report(rows, summ)

    out = {
        "schema": SCHEMA,
        "generated": datetime.now(timezone.utc).isoformat(),
        "results": args.results,
        "results_sha256": sha256_file(args.results),
        "timing_inputs": timing_inputs,
        "wns_note": "per (design, period) from the timing sweep, not "
                    "measured on the B_Explore build",
        "artifacts_root": artifacts,
        "prjxray_db_dir": db_dir,
        "builds": [{k: v for k, v in r.items() if k != "lut_flags"}
                   for r in rows],
        "flagged_luts": luts,
        "summary": summ,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print("-> %s" % args.out)

    if summ["met_and_flagged"]:
        sys.exit("EVASION PATH: timing-met benign builds with flags: %s"
                 % ", ".join(summ["met_and_flagged"]))


if __name__ == "__main__":
    main()
