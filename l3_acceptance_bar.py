# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5C-L3 -- does the placed-checkpoint method pass the
#              acceptance bar that every earlier localization scorer failed?
#
#              THE BAR, set by L2 (localization_corpus/L2_RESULT.md) after the
#              density confound was measured. A localization method must:
#                (1) rank the implant well in SPARSE regions, not only dense
#                    ones;
#                (2) show near-zero rank-vs-density correlation -- L2's
#                    scorers reached r = -0.88 to -0.90, i.e. they were
#                    reading logic density and not trojan position;
#                (3) beat the `popcount` occupancy control AT EVERY DENSITY
#                    LEVEL, not on average.
#              L2c's consensus method passed it (r = +0.65) but needs several
#              builds with the trojan deliberately relocated, so it is
#              forensic-only. The placed-checkpoint difference (L3) is the
#              deployable form -- one suspect bitstream against the operator's
#              own builds -- and it has never been tested against this bar.
#
#              WHAT MAKES THE TEST POSSIBLE. The six L3 region builds put the
#              SAME implant, same size, same route directive, into the six
#              regions of `device_density_map.json`, whose mean window density
#              spans 86 to 3,174 -- a 37x range measured on the host itself.
#              Rank comes from l3_forensic_results_v2.json's device-wide
#              site->frame map, so all six builds are evaluable (the earlier
#              3-build coverage could not support a correlation at all).
#
#              ALSO REPORTED: the operator-facing precision of the flagged
#              set. The analyst examines the windows that differ from the
#              reference; of those, what fraction lands on the implant's
#              column-level target set? That is the number that decides
#              whether a screening pipeline is worth running, and it separates
#              the additive case from the functional one far more sharply than
#              rank does.
#
#              LIMITS. The target set is a COLUMN-LEVEL PROXY (column x
#              clock-region granularity, see l3_site_frame_map.py). It can
#              include windows holding no implant bits -- over-coverage across
#              the column's frames -- and can miss the exact frame holding
#              them, since the map only lists frames some build's host cells
#              actually sampled. So the reported precision is an ESTIMATE with
#              no guaranteed bias direction, not a bound, and no recall or IoU
#              follows from it. Ranks are affected in the conservative
#              direction by over-coverage (a target window with no implant
#              bits ranks badly and worsens the median). Six density points on
#              one host, one implant size, one part. Correlation on n=6 is
#              descriptive: the sign and the worst-case rank carry the
#              argument, not the coefficient.
#
# Usage:
#   python3 l3_acceptance_bar.py [--l3-dir DIR] [--eval JSON] [--density JSON]
#                                [--outdir DIR]

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

from bitstream_io import ZYNQ7020_V4, fdri_payload
from l2_localization_eval import ranks_of, windows

SCHEMA = "l3_acceptance_bar_v1"

# The bar's own thresholds, stated up front so the verdict is not chosen after
# seeing the numbers.
BAR = {
    "max_abs_density_correlation": 0.30,
    "max_worst_median_rank": 20.0,
    "must_beat_popcount_at_every_density": True,
}


def spearman(x, y):
    """Rank correlation, ties averaged. No scipy dependency in this repo."""
    def rk(v):
        v = np.asarray(v, dtype=float)
        order = np.argsort(v, kind="stable")
        r = np.empty(len(v))
        r[order] = np.arange(1, len(v) + 1)
        for u in np.unique(v):
            m = v == u
            if m.sum() > 1:
                r[m] = r[m].mean()
        return r
    return pearson(rk(x), rk(y))


def pearson(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(((x - x.mean()) * (y - y.mean())).mean() / (x.std() * y.std()))


def main():
    p = argparse.ArgumentParser(
        description="Acceptance-bar test for the placed-checkpoint method")
    p.add_argument("--l3-dir", default="rebuild_pilot/pilot_artifacts/l3")
    p.add_argument("--eval",
                   default="localization_corpus/l3_forensic_results_v2.json")
    p.add_argument("--density",
                   default="localization_corpus/device_density_map.json")
    p.add_argument("--outdir", default="localization_corpus")
    args = p.parse_args()

    with open(args.eval) as fh:
        ev = json.load(fh)
    with open(args.density) as fh:
        dm = json.load(fh)
    density_by_range = {r["slice_range"]: r["mean_window_density"]
                        for r in dm["proposed_regions"]}

    ref = windows(fdri_payload(os.path.join(args.l3_dir, "B_Default.bit"),
                               ZYNQ7020_V4))
    refb = np.unpackbits(ref, axis=1)
    n_win = ref.shape[0]

    print("=== acceptance-bar test: the deployable placed-checkpoint method ===")
    print("bar: |r(rank, density)| <= %.2f, worst median rank <= %.0f, and it "
          "must beat popcount at every density level\n"
          % (BAR["max_abs_density_correlation"], BAR["max_worst_median_rank"]))

    rows, per_build = [], {}
    for tag, rec in sorted(ev["per_build"].items()):
        region = rec.get("region")
        targets = rec["implant_windows"]
        path = os.path.join(args.l3_dir, "%s.bit" % tag)
        if not os.path.exists(path) or not targets:
            continue
        W = windows(fdri_payload(path, ZYNQ7020_V4))
        Wb = np.unpackbits(W, axis=1)
        diff = np.abs(W.astype(np.int32) - ref.astype(np.int32)).sum(axis=1)
        scores = {
            # the method under test
            "placed_checkpoint_l1": diff.astype(float),
            "placed_checkpoint_ham": np.abs(Wb - refb).sum(axis=1).astype(float),
            # controls, exactly the ones L1b/L2 made mandatory
            "popcount": Wb.sum(axis=1).astype(float),
            "diff_per_setbit": (diff / np.maximum(Wb.sum(axis=1), 1)
                                ).astype(float),
        }
        differing = set(np.flatnonzero(diff > 0).tolist())
        inter = differing & set(targets)
        precision = len(inter) / len(differing) if differing else float("nan")
        entry = {"family": rec["family"], "region": region,
                 "region_mean_density": density_by_range.get(region),
                 "n_target_windows": len(targets),
                 "n_windows_flagged": len(differing),
                 "targets_inside_flagged": len(inter),
                 "flagged_precision_column_proxy": precision,
                 "device_fraction_flagged": len(differing) / n_win,
                 "scorers": {}}
        for name, sc in scores.items():
            r = ranks_of(sc, targets)
            entry["scorers"][name] = {
                "median_rank": float(np.median(list(r.values()))),
                "best_rank": float(min(r.values())),
                "worst_rank": float(max(r.values()))}
        per_build[tag] = entry
        rows.append({"build": tag, "family": rec["family"], "region": region,
                     "density": entry["region_mean_density"],
                     "n_targets": len(targets),
                     "n_flagged": len(differing),
                     "precision_column_proxy": round(precision, 4),
                     **{"%s_median" % k: v["median_rank"]
                        for k, v in entry["scorers"].items()}})

    # --- the bar, evaluated on the six region builds -----------------------
    reg = [(t, e) for t, e in per_build.items()
           if e["family"].startswith("region sweep")
           and e["region_mean_density"] is not None]
    reg.sort(key=lambda kv: kv[1]["region_mean_density"])
    print("--- region sweep: same implant, six densities (sorted sparse -> "
          "dense)")
    print("%-8s %9s %8s %10s %10s %9s" % ("build", "density", "targets",
                                          "placed_l1", "placed_ham",
                                          "popcount"))
    for tag, e in reg:
        print("%-8s %9.1f %8d %10.1f %10.1f %9.1f"
              % (tag, e["region_mean_density"], e["n_target_windows"],
                 e["scorers"]["placed_checkpoint_l1"]["median_rank"],
                 e["scorers"]["placed_checkpoint_ham"]["median_rank"],
                 e["scorers"]["popcount"]["median_rank"]))

    dens = [e["region_mean_density"] for _, e in reg]
    corr, beats, verdict = {}, {}, {}
    for name in ("placed_checkpoint_l1", "placed_checkpoint_ham", "popcount",
                 "diff_per_setbit"):
        y = [e["scorers"][name]["median_rank"] for _, e in reg]
        corr[name] = {"pearson_r": pearson(dens, y),
                      "spearman_r": spearman(dens, y),
                      "median_rank": float(np.median(y)),
                      "worst_median_rank": float(max(y)),
                      "n_builds": len(y)}
    for name in ("placed_checkpoint_l1", "placed_checkpoint_ham"):
        wins = [e["scorers"][name]["median_rank"]
                < e["scorers"]["popcount"]["median_rank"] for _, e in reg]
        beats[name] = {"beats_popcount_at_every_density": bool(all(wins)),
                       "n_levels_won": int(sum(wins)), "n_levels": len(wins)}
        c = corr[name]
        verdict[name] = {
            "criterion_1_sparse_regions_ok":
                bool(reg[0][1]["scorers"][name]["median_rank"]
                     <= BAR["max_worst_median_rank"]),
            "criterion_2_density_independent":
                bool(abs(c["spearman_r"]) <= BAR["max_abs_density_correlation"]),
            "criterion_3_beats_popcount_everywhere":
                beats[name]["beats_popcount_at_every_density"],
            "worst_median_rank_ok":
                bool(c["worst_median_rank"] <= BAR["max_worst_median_rank"]),
        }
        verdict[name]["PASSES_BAR"] = all(verdict[name].values())

    print("\n--- rank vs region density (n = %d densities, %.0fx range)"
          % (len(dens), max(dens) / min(dens)))
    for name, c in corr.items():
        print("  %-22s pearson %+6.3f | spearman %+6.3f | median %6.1f | "
              "worst %6.1f" % (name, c["pearson_r"], c["spearman_r"],
                               c["median_rank"], c["worst_median_rank"]))
    print("\n--- verdict")
    for name, v in verdict.items():
        print("  %-22s %s" % (name, "PASSES the L2 acceptance bar"
                              if v["PASSES_BAR"] else "FAILS"))
        for k in ("criterion_1_sparse_regions_ok",
                  "criterion_2_density_independent",
                  "criterion_3_beats_popcount_everywhere",
                  "worst_median_rank_ok"):
            print("      %-42s %s" % (k, v[k]))

    print("\n--- operator-facing precision of the flagged set (column-level "
          "proxy target, an estimate not a bound)")
    print("%-20s %-14s %8s %8s %10s" % ("build", "family", "flagged",
                                        "targets", "precision"))
    for tag, e in sorted(per_build.items(),
                         key=lambda kv: kv[1]["n_windows_flagged"]):
        print("%-20s %-14s %8d %8d %9.1f%%"
              % (tag, e["family"].split()[0], e["n_windows_flagged"],
                 e["n_target_windows"],
                 100 * e["flagged_precision_column_proxy"]))

    fams = {}
    for tag, e in per_build.items():
        fams.setdefault(e["family"], []).append(e)
    fam_summary = {f: {
        "n_builds": len(v),
        "median_windows_flagged": float(np.median([e["n_windows_flagged"]
                                                   for e in v])),
        "median_precision_column_proxy":
            float(np.median([e["flagged_precision_column_proxy"] for e in v])),
    } for f, v in fams.items()}
    print("\n--- by family")
    for f, s in sorted(fam_summary.items()):
        print("  %-46s %d builds | flagged %6.1f | precision %5.1f%%"
              % (f, s["n_builds"], s["median_windows_flagged"],
                 100 * s["median_precision_column_proxy"]))

    out = {"schema": SCHEMA,
           "generated": datetime.now(timezone.utc).isoformat(),
           "bar": BAR,
           "bar_source": "localization_corpus/L2_RESULT.md",
           "rank_source": args.eval,
           "density_source": args.density,
           "n_windows": n_win,
           "region_density_range": {"min": min(dens), "max": max(dens),
                                    "ratio": max(dens) / min(dens)},
           "density_correlation": corr,
           "popcount_comparison": beats,
           "verdict": verdict,
           "per_build": per_build,
           "by_family": fam_summary,
           "limits": ("the target set is a column-level proxy (column x "
                      "clock-region granularity): it can include windows with "
                      "no implant bits and can miss the exact frame holding "
                      "them, so precision is an estimate with no guaranteed "
                      "bias direction and no recall/IoU follows. Ranks are "
                      "affected conservatively by over-coverage. Six density "
                      "points on one host, one implant size, one part; n=6 "
                      "correlation is descriptive -- the sign and the "
                      "worst-case rank carry the argument")}
    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, "l3_acceptance_bar.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(args.outdir, "l3_acceptance_bar.csv"), "w",
              newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\nresults -> %s"
          % os.path.join(args.outdir, "l3_acceptance_bar.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
