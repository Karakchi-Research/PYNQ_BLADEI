# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5 summary generation with correct statistical
#              presentation (single source of truth; the experiment scripts
#              delegate here so summaries can be regenerated from the CSVs
#              without rerunning anything). Rules:
#
#              - A grouped regime with fewer than MIN_VALID_SEEDS valid seeds
#                is reported as NOT ESTIMABLE -- insufficient valid
#                payload-component folds. Raw observations and valid-run
#                counts stay in the CSV artifacts; they are not presented as
#                a model estimate.
#              - Leave-one-family-out regimes are reported PER ELIGIBLE
#                FAMILY first (mean +/- std over that family's valid seeds),
#                then as a MACRO AVERAGE across eligible family means. Valid
#                seed x family combinations are never pooled as though they
#                were independent datasets.
#
# Usage:
#   python3 phase05_summarize.py [--outdir phase05_out]

import argparse
import csv
import json
import os
from collections import defaultdict

import numpy as np

MIN_VALID_SEEDS = 3

NOT_ESTIMABLE = ("NOT ESTIMABLE -- insufficient valid payload-component "
                 "folds")


def _read(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _fmt_group(rows_rm, n_seeds):
    """Grouped-regime line: estimate only when enough valid seeds exist."""
    valid = [float(r["bal_acc"]) for r in rows_rm if r["valid"] == "True"]
    n_total = len({r["seed"] for r in rows_rm})
    if len(valid) < MIN_VALID_SEEDS:
        raw = ", ".join(f"{v:.4f}" for v in valid) or "none"
        return (f"{NOT_ESTIMABLE} ({len(valid)}/{n_total} seeds valid; raw "
                f"observations [{raw}] retained in artifacts, not an "
                f"estimate)")
    v = np.array(valid)
    return (f"bal_acc {v.mean():.4f}+/-{v.std():.4f} "
            f"({len(valid)}/{n_total} seeds valid)")


def _fmt_lofo(rows_rm):
    """LOFO lines: per eligible family, then macro average of family means."""
    by_fam = defaultdict(list)
    totals = defaultdict(set)
    for r in rows_rm:
        totals[r["family"]].add(r["seed"])
        if r["valid"] == "True":
            by_fam[r["family"]].append(float(r["bal_acc"]))
    lines, fam_means = [], []
    for fam in sorted(totals):
        vals = by_fam.get(fam, [])
        if vals:
            v = np.array(vals)
            fam_means.append(v.mean())
            lines.append(f"    {fam:<12} bal_acc {v.mean():.4f}"
                         f"+/-{v.std():.4f} "
                         f"({len(vals)}/{len(totals[fam])} seeds valid)")
        else:
            lines.append(f"    {fam:<12} no valid seeds "
                         f"(0/{len(totals[fam])})")
    if fam_means:
        m = np.array(fam_means)
        lines.append(f"    MACRO AVG    bal_acc {m.mean():.4f}"
                     f"+/-{m.std():.4f} across {len(m)} eligible family "
                     f"means (families are the unit, not seed x family runs)")
    return lines


def summarize_stat(outdir, pre_audit_csv=os.path.join("split_comparison_out",
                                                      "results.csv")):
    rows = _read(os.path.join(outdir, "stat_results.csv"))
    lines = ["=== Phase 0.5 statistical ablation (corrected presentation) ===",
             "A = pre-audit frozen; B = FDRI+naive (diagnostic, "
             "duplicate-contaminated); C = FDRI+component, aliases "
             "(secondary, file-weighted); D = FDRI+component, unique "
             "payloads (PRIMARY); E = FDRI+LOFO, unique payloads (PRIMARY "
             "generalization)"]
    pre = defaultdict(list)
    for r in _read(pre_audit_csv):
        pre[(r["regime"], r["model"])].append(float(r["bal_acc"]))
    for (regime, model), vals in sorted(pre.items()):
        v = np.array(vals)
        lines.append(f"A_preaudit_{regime:<10} {model:<20} "
                     f"bal_acc {v.mean():.4f}+/-{v.std():.4f} (n={len(v)}; "
                     f"pre-dedup, header-contaminated)")
    models = sorted({r["model"] for r in rows})
    for model in models:
        mrows = [r for r in rows if r["model"] == model]
        for regime in sorted({r["regime"] for r in mrows}):
            rrows = [r for r in mrows if r["regime"] == regime]
            if regime.startswith("E_"):
                lines.append(f"{regime:<24} {model} (per eligible family):")
                lines.extend(_fmt_lofo(rrows))
            else:
                lines.append(f"{regime:<24} {model:<20} "
                             + _fmt_group(rrows, None))
    return "\n".join(lines)


def summarize_cnn(outdir, pre_audit_csv=os.path.join("split_comparison_out",
                                                     "cnn_results.csv")):
    rows = _read(os.path.join(outdir, "cnn_results.csv"))
    lines = ["=== Phase 0.5 corrected hybrid CNN (corrected presentation) ==="]
    pre = defaultdict(list)
    for r in _read(pre_audit_csv):
        pre[r["regime"]].append(float(r["bal_acc"]))
    for regime, vals in sorted(pre.items()):
        v = np.array(vals)
        lines.append(f"A_preaudit_cnn_{regime:<10} bal_acc {v.mean():.4f}"
                     f"+/-{v.std():.4f} (n={len(v)}; pre-dedup, "
                     f"header-contaminated)")
    for regime in sorted({r["regime"] for r in rows}):
        rrows = [r for r in rows if r["regime"] == regime]
        if "lofo" in regime:
            lines.append(f"{regime} (per eligible family):")
            lines.extend(_fmt_lofo(rrows))
        else:
            lines.append(f"{regime:<28} " + _fmt_group(rrows, None))
    return "\n".join(lines)


def write_summaries(outdir="phase05_out"):
    stat = summarize_stat(outdir)
    cnn = summarize_cnn(outdir)
    with open(os.path.join(outdir, "stat_summary.txt"), "w") as f:
        f.write(stat + "\n")
    with open(os.path.join(outdir, "cnn_summary.txt"), "w") as f:
        f.write(cnn + "\n")
    return stat, cnn


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Regenerate Phase 0.5 summaries "
                                            "from the results CSVs")
    p.add_argument("--outdir", default="phase05_out")
    args = p.parse_args()
    stat, cnn = write_summaries(args.outdir)
    print(stat + "\n\n" + cnn)
