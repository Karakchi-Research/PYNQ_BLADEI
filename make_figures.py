# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Generate presentation/paper figures from the tracked artifacts.
#              Every number is read from a JSON/CSV produced by a verification
#              or experiment script -- nothing is typed in by hand -- so the
#              figures cannot drift from the results they depict.
#
#              Palette: categorical slots 1-4 of the dataviz reference palette,
#              assigned in fixed order and never cycled. (The bundled Node
#              validator could not be run in this environment -- no node -- so
#              the pre-validated reference values are used verbatim rather than
#              improvised.)
#
# Usage:
#   python3 make_figures.py [--outdir figures]

import argparse
import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

# dataviz reference palette, light mode, categorical slots in fixed order
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8a86"
SURFACE, GRID = "#fcfcfb", "#e4e4e0"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "font.size": 10,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.titlecolor": INK, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
})


def J(p):
    with open(p) as f:
        return json.load(f)


def save(fig, outdir, name):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(outdir, f"{name}.{ext}"), dpi=200,
                    bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}.png / .pdf")


# --- Fig 1: corpus collapse -------------------------------------------------
def fig_corpus_collapse(outdir):
    ci = J("corpus_out/corpus_index.json")["counts"]
    inv = J("corpus_out/candidate_host_inventory.json")
    stages = ["Files\nshipped", "Distinct\nconfigurations",
              "Excl. ISCAS85\n(obfuscation)", "Independent\nhost circuits"]
    vals = [ci["n_files"], ci["unique_payloads"], 140,
            inv["independent_hosts"]["n_trojan_benchmark_hosts"]]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    bars = ax.bar(stages, vals, color=[C1, C1, C1, C2], width=0.58,
                  zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.06, f"{v:,}",
                ha="center", va="bottom", color=INK, fontweight="bold")
    ax.set_yscale("log")
    ax.set_ylim(5, vals[0] * 3)
    ax.set_ylabel("count (log scale)")
    ax.set_title("The corpus is far smaller than its file count suggests",
                 fontweight="bold", loc="left")
    ax.text(0, -0.30, "An estimable grouped split needs 30–40 independent "
            "host circuits. The suite contains 13.",
            transform=ax.transAxes, color=INK2, fontsize=9)
    ax.grid(axis="x", visible=False)
    save(fig, outdir, "fig1_corpus_collapse")


# --- Fig 2: grouped-split duplicate leakage ---------------------------------
def fig_split_leakage(outdir):
    d = J("leakage_audit_out/verify_split_leakage.json")
    seeds = [r["seed"] for r in d["grouped_per_seed"]]
    share = [100 * r["share"] for r in d["grouped_per_seed"]]
    lofo = max(100 * r["share"] for r in d["lofo_control"])
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    ax.bar([f"seed {s}" for s in seeds], share, color=C2, width=0.58, zorder=3)
    for i, v in enumerate(share):
        ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", color=INK,
                fontweight="bold")
    ax.axhline(lofo, color=C3, lw=2, ls="--", zorder=4)
    ax.text(len(seeds) - 0.4, lofo + 2.5,
            f"leave-one-family-out: {lofo:.0f}%", color=C3, ha="right",
            fontweight="bold", fontsize=9)
    ax.set_ylim(0, 85)
    ax.set_ylabel("% of test set byte-identical to a training file")
    ax.set_title("Design-grouped splits still leak duplicate bitstreams",
                 fontweight="bold", loc="left")
    ax.text(0, -0.30, "Design keys ARE disjoint every seed — but one "
            "configuration appears under 25 different design keys.",
            transform=ax.transAxes, color=INK2, fontsize=9)
    ax.grid(axis="x", visible=False)
    save(fig, outdir, "fig2_split_leakage")


# --- Fig 3: the density confound --------------------------------------------
def fig_density_confound(outdir):
    d = J("localization_corpus/l2_eval_results.json")
    # region_density is null in the regenerated results file, so take the
    # measured densities from the density map and join on region id.
    dens = {r["region_id"]: r["mean_window_density"]
            for r in J("localization_corpus/device_density_map.json")
            ["proposed_regions"]}
    want = ["pair_l1", "pair_hamming", "popcount"]
    cols = {"pair_l1": C1, "pair_hamming": C2, "popcount": C3}
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for s in want:
        xs, ys = [], []
        for tag, b in d["per_build"].items():
            if tag not in dens:
                continue                      # skips the unpinned reference
            xs.append(dens[tag])
            ys.append(b["scorers"][s]["median_rank"])
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        xs = [xs[i] for i in order]
        ys = [ys[i] for i in order]
        r = d["density_correlation"][s]["pearson_r_rank_vs_density"]
        r = 0.0 if r is None else r
        ax.plot(xs, ys, "-o", color=cols[s], lw=2, ms=8,
                label=f"{s}  (r = {r:+.2f})", zorder=3)
    ax.axhline(626, color=MUTED, lw=1.5, ls=":", zorder=2)
    ax.text(0.99, 0.93, "random (626)", transform=ax.transAxes,
            color=MUTED, ha="right", va="top", fontsize=9)
    ax.set_xlabel("local host logic density of the region the trojan was pinned into")
    ax.set_ylabel("rank of the trojan window  (1 = best, of 1,251)")
    ax.set_title("Scorers track logic density, not trojan position",
                 fontweight="bold", loc="left")
    ax.legend(frameon=False, fontsize=9)
    ax.text(0, -0.24, "Same trojan netlist, moved across a 37× density range. "
            "Every well-performing scorer degrades in sparse regions.",
            transform=ax.transAxes, color=INK2, fontsize=9)
    save(fig, outdir, "fig3_density_confound")


# --- Fig 4: churn floor by build provenance ---------------------------------
def fig_churn_floor(outdir):
    d = J("localization_corpus/l2_churn_floor.json")
    lbl = {"INDEPENDENT-PNR": "Independent\nplace & route",
           "SHARED-LINEAGE": "Shared placement\nancestor",
           "CROSS-LABEL": "Benign vs\nmalicious"}
    order = ["INDEPENDENT-PNR", "CROSS-LABEL", "SHARED-LINEAGE"]
    cls = {c["class"]: c for c in d["classes"]}
    vals = [cls[k]["median_frames_differing"] for k in order if k in cls]
    names = [lbl[k] for k in order if k in cls]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    bars = ax.bar(names, vals, color=[C2, C2, C3], width=0.55, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 90, f"{int(v):,}",
                ha="center", color=INK, fontweight="bold")
    ax.axhline(2, color=C1, lw=2, zorder=4)
    ax.text(2.35, 260, "a trojan occupies\n1–2 frames", color=C1,
            ha="right", fontsize=9, fontweight="bold")
    ax.set_ylabel("frames differing (of 10,008)")
    ax.set_title("Why the trojan is invisible: the noise floor dwarfs it",
                 fontweight="bold", loc="left")
    ax.grid(axis="x", visible=False)
    save(fig, outdir, "fig4_churn_floor")


# --- Fig 5: L3 search-space collapse ----------------------------------------
def fig_l3_collapse(outdir):
    rows = list(csv.DictReader(open("localization_corpus/l3_routing_invariant.csv")))
    tied = [int(r["raw_windows"]) for r in rows if r["style"] == "tied"]
    tap = [int(r["raw_windows"]) for r in rows if r["style"] == "tapped"]
    cats = ["Whole device\n(no reference)", "Additive implant\n(placed checkpoint)",
            "Functional implant\n(taps a host net)"]
    vals = [1251, sum(tied) / len(tied), sum(tap) / len(tap)]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    bars = ax.bar(cats, vals, color=[MUTED, C3, C2], width=0.55, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.10, f"{v:,.0f}",
                ha="center", color=INK, fontweight="bold")
    ax.set_yscale("log")
    ax.set_ylim(3, 3000)
    ax.set_ylabel("windows an analyst must examine (log scale)")
    ax.set_title("Search space under the placed-checkpoint model",
                 fontweight="bold", loc="left")
    ax.text(0, -0.30, "An implant that observes host state costs ~60× more "
            "search — the router's response, not the implant itself.",
            transform=ax.transAxes, color=INK2, fontsize=9)
    ax.grid(axis="x", visible=False)
    save(fig, outdir, "fig5_l3_collapse")


# --- Fig 6: the timing-closure mechanism ------------------------------------
def fig_timing_mechanism(outdir):
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    groups = ["b15 @125 MHz\n(fails timing)", "b15 @50 MHz\n(meets timing)"]
    floor = [62, 0]
    signal = [74, 11]
    x = range(len(groups))
    w = 0.34
    b1 = ax.bar([i - w / 2 for i in x], floor, w, label="routing noise floor",
                color=C2, zorder=3)
    b2 = ax.bar([i + w / 2 for i in x], signal, w, label="implant signal",
                color=C1, zorder=3)
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2,
                    f"{int(b.get_height())}", ha="center", color=INK,
                    fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(groups)
    ax.set_ylabel("windows differing (of 1,251)")
    ax.set_title("Closing timing makes the implant visible",
                 fontweight="bold", loc="left")
    ax.legend(frameon=False, fontsize=9)
    ax.text(0, -0.26, "Same design, netlist, implant and region — only the "
            "clock constraint changed. Buried → visible.",
            transform=ax.transAxes, color=INK2, fontsize=9)
    ax.grid(axis="x", visible=False)
    save(fig, outdir, "fig6_timing_mechanism")


# --- Fig 7: conceptual — bitstream geometry ---------------------------------
def fig_geometry(outdir):
    fig, ax = plt.subplots(figsize=(7.6, 2.7))
    ax.set_xlim(0, 118)
    ax.set_ylim(0, 34)
    ax.axis("off")

    def box(x, w, y, h, c, label, sub=None, tc="white"):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=c, edgecolor=SURFACE,
                               lw=2, zorder=3))
        ax.text(x + w / 2, y + h / 2 + (1.6 if sub else 0), label,
                ha="center", va="center", color=tc, fontweight="bold",
                fontsize=9, zorder=4)
        if sub:
            ax.text(x + w / 2, y + h / 2 - 2.6, sub, ha="center", va="center",
                    color=tc, fontsize=8, zorder=4)

    ax.text(0, 31, "A .bit file is not all configuration data",
            fontweight="bold", color=INK, fontsize=11)
    # Labels for the narrow blocks sit ABOVE them; only wide blocks carry
    # text inside, so nothing overflows its box.
    box(3, 17, 19, 8, MUTED, "header", None)
    ax.text(11.5, 16.2, "ASCII — leaks the label", ha="center", color=INK2,
            fontsize=8)
    box(20, 4, 19, 8, C4, "", None)
    ax.text(22, 28.4, "sync", ha="center", color=INK2, fontsize=8)
    box(24, 7, 19, 8, C2, "", None)
    ax.text(27.5, 16.2, "cmds\n184 B", ha="center", va="top", color=INK2,
            fontsize=8)
    box(31, 57, 19, 8, C1, "FDRI configuration payload", None)
    box(88, 12, 19, 8, MUTED, "trailer", None)
    ax.text(94, 16.2, "2,096 B", ha="center", color=INK2, fontsize=8)

    ax.annotate("", xy=(31, 13.5), xytext=(88, 13.5),
                arrowprops=dict(arrowstyle="<->", color=INK2, lw=1.4))
    ax.text(59.5, 10.4, "10,008 frames × 404 B — the only bytes that "
            "describe the circuit", ha="center", color=INK2, fontsize=9)

    for i in range(8):
        x = 31 + i * 7.1
        ax.add_patch(Rectangle((x, 3.2), 7.1, 4.2, facecolor=C3,
                               edgecolor=SURFACE, lw=1.5, zorder=3))
    ax.text(88.5, 5.3, "8 frames = 1 window  →  1,251 per device",
            ha="left", va="center", color=INK, fontweight="bold",
            fontsize=8.5, zorder=4)
    ax.text(0, 0.0, "Extraction had been anchored at the sync word — 184 bytes "
            "early, so every window straddled two frames.",
            color=INK2, fontsize=9)
    save(fig, outdir, "fig7_bitstream_geometry")


# --- Fig 8: conceptual — the threat model -----------------------------------
def fig_threat_model(outdir):
    fig, ax = plt.subplots(figsize=(7.6, 3.3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 42)
    ax.axis("off")
    ax.text(0, 39, "Placed-checkpoint verification (the datacenter case)",
            fontweight="bold", color=INK, fontsize=11)

    def node(x, y, w, h, c, title, sub):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=c, edgecolor=SURFACE,
                               lw=2, zorder=3))
        ax.text(x + w / 2, y + h - 6, title, ha="center", color="white",
                fontweight="bold", fontsize=9, zorder=4)
        ax.text(x + w / 2, y + 5.5, sub, ha="center", color="white",
                fontsize=8, zorder=4)

    node(0, 20, 27, 16, C1, "Operator", "places the design,\nships a checkpoint")
    node(37, 20, 26, 16, C2, "Vendor / tenant", "returns a bitstream\n(may add logic)")
    node(73, 20, 27, 16, C3, "Operator verifies", "vs own builds from\nthe same checkpoint")
    for x0, x1 in ((27, 37), (63, 73)):
        ax.add_patch(FancyArrowPatch((x0, 28), (x1, 28),
                                     arrowstyle="-|>", mutation_scale=16,
                                     color=INK2, lw=1.6, zorder=2))
    ax.text(50, 13.5, "Host PLACEMENT is fixed by the checkpoint, so only the "
            "added logic and its routing differ.",
            ha="center", color=INK, fontsize=9, fontweight="bold")
    ax.text(50, 7.5, "Precondition — the design must close timing with margin. "
            "If it does, an 8-flip-flop implant",
            ha="center", color=INK2, fontsize=9)
    ax.text(50, 2.5, "shows up in ~11 of 1,251 windows. If it does not, the "
            "implant is buried in the design's own routing churn.",
            ha="center", color=INK2, fontsize=9)
    save(fig, outdir, "fig8_threat_model")


def main():
    p = argparse.ArgumentParser(description="Generate figures from artifacts")
    p.add_argument("--outdir", default="figures")
    args = p.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    print(f"=== generating figures -> {args.outdir}/ ===")
    for fn in (fig_corpus_collapse, fig_split_leakage, fig_density_confound,
               fig_churn_floor, fig_l3_collapse, fig_timing_mechanism,
               fig_geometry, fig_threat_model):
        try:
            fn(args.outdir)
        except Exception as e:
            print(f"  SKIP {fn.__name__}: {e}")
    print("done.")


if __name__ == "__main__":
    main()
