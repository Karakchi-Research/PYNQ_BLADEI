# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5B controlled rebuild pilot -- analysis of the built
#              artifacts. Reads ONLY what the pilot produced; runs no model,
#              no classifier, no training.
#
#              Every equality decision about configuration data is made by
#              EXACT BYTE COMPARISON. Digests are used only to propose
#              candidate duplicate groups, which are then confirmed member by
#              member against the group representative (the same discipline
#              LEAKAGE_AUDIT.md Finding 2 used). A pair whose digests agree but
#              whose bytes differ would be reported as a digest collision, not
#              silently accepted.
#
#              Whole-file hashes are deliberately NOT used to decide
#              distinctness: the .bit ASCII header carries a build timestamp,
#              so two byte-identical configurations always differ as files.
#
# Outputs (all under rebuild_pilot/):
#   pilot_manifest.json         per-build provenance
#   pilot_results.csv           one row per attempted build
#   payload_distinctness.json   unique payloads / duplicate classes per design+label
#   matched_pair_frame_diffs.csv matched benign-vs-malicious frame diffs
#   trojan_retention.json       post-synth + post-route trojan evidence

import csv
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from bitstream_io import (
    ZYNQ7020_V4,
    fdri_payload_and_meta,
    payload_hash,
    file_sha256,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(HERE, "pilot_artifacts")

DESIGNS = ["PIC16F84-T100", "b15-T200", "AES-T1000"]
LABELS = ["TjFree", "TjIn"]
CONFIGS = ["C1", "C2", "C3", "C4"]

CONFIG_SETTINGS = {
    "C1": {"place": "Default", "route": "Default", "phys_opt": None},
    "C2": {"place": "Explore", "route": "Explore", "phys_opt": "Explore"},
    "C3": {"place": "ExtraNetDelay_high", "route": "AggressiveExplore",
           "phys_opt": None},
    "C4": {"place": "AltSpreadLogic_high", "route": "NoTimingRelaxation",
           "phys_opt": "AggressiveExplore"},
}

FRAME_BYTES = ZYNQ7020_V4.frame_bytes      # 404
N_FRAMES = ZYNQ7020_V4.n_frames            # 10,008


def bit_path(design, label, cfg):
    return os.path.join(ARTIFACTS, "builds", design, label, cfg,
                        f"{design}_{label}_{cfg}.bit")


def report_path(design, label, cfg, name):
    return os.path.join(ARTIFACTS, "builds", design, label, cfg, "reports", name)


# ---------------------------------------------------------------------------
# Report scraping.
# ---------------------------------------------------------------------------
def parse_trojan_report(path):
    """-> {'total_cells': int, 'total_nets': int,
           'patterns': {pat: {'cells': n, 'nets': n, 'cell_names': [...]}}}"""
    if not os.path.exists(path):
        return None
    out = {"total_cells": None, "total_nets": None, "patterns": {}}
    current = None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"total_cells=(\d+)", line)
            if m:
                out["total_cells"] = int(m.group(1))
                continue
            m = re.match(r"total_nets=(\d+)", line)
            if m:
                out["total_nets"] = int(m.group(1))
                continue
            m = re.match(r"PATTERN (\S+) cells=(\d+) nets=(\d+)", line)
            if m:
                current = m.group(1)
                out["patterns"][current] = {
                    "cells": int(m.group(2)),
                    "nets": int(m.group(3)),
                    "cell_names": [],
                    "net_names": [],
                }
                continue
            m = re.match(r"\s+CELL (\S+) (\S+)(?: LOC=(\S*))?", line)
            if m and current:
                out["patterns"][current]["cell_names"].append(
                    {"name": m.group(1), "ref": m.group(2),
                     "loc": m.group(3) or ""})
                continue
            m = re.match(r"\s+NET  (\S+)", line)
            if m and current:
                out["patterns"][current]["net_names"].append(m.group(1))
    return out


def parse_timing(path):
    """Worst negative slack and whether all constraints are met."""
    if not os.path.exists(path):
        return {}
    wns = tns = whs = None
    with open(path) as f:
        text = f.read()
    m = re.search(r"WNS\(ns\)\s+TNS\(ns\).*?\n\s*-+.*?\n\s*(-?[\d.]+)\s+(-?[\d.]+)",
                  text, re.S)
    if m:
        wns, tns = float(m.group(1)), float(m.group(2))
    m = re.search(r"WHS\(ns\)", text)
    if m:
        m2 = re.search(r"WHS\(ns\)\s+THS\(ns\).*?\n\s*-+.*?\n\s*(-?[\d.]+)",
                       text, re.S)
        if m2:
            whs = float(m2.group(1))
    return {"wns_ns": wns, "tns_ns": tns, "whs_ns": whs,
            "timing_met": (wns is not None and wns >= 0
                           and (whs is None or whs >= 0))}


def parse_utilization(path):
    """LUT / FF / BRAM / DSP / IO counts from a report_utilization file."""
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path) as f:
        for line in f:
            for key, label in (("luts", "Slice LUTs"),
                               ("ffs", "Slice Registers"),
                               ("bram", "Block RAM Tile"),
                               ("dsp", "DSPs"),
                               ("io", "Bonded IOB")):
                if line.strip().startswith("| " + label):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) > 2:
                        try:
                            out[key] = float(parts[2])
                        except ValueError:
                            pass
    return out


def parse_route_status(path):
    """report_route_status tabulates routable vs fully-routed nets and counts
    nets with routing errors; 'fully routed' means every routable net is routed
    and no net has a routing error."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        text = f.read()

    def count(label):
        m = re.search(r"#\s+of\s+" + label + r"[.\s]*:\s*(\d+)\s*:", text)
        return int(m.group(1)) if m else None

    routable = count("routable nets")
    routed = count("fully routed nets")
    errors = count("nets with routing errors")
    return {
        "routable_nets": routable,
        "fully_routed_nets": routed,
        "nets_with_routing_errors": errors,
        "fully_routed": (routable is not None and routed == routable
                         and (errors == 0 or errors is None)),
    }


# ---------------------------------------------------------------------------
# Payload handling.
# ---------------------------------------------------------------------------
def load_payloads():
    """{(design,label,cfg): payload ndarray}. Only successful builds."""
    payloads = {}
    meta = {}
    for d in DESIGNS:
        for lab in LABELS:
            for cfg in CONFIGS:
                p = bit_path(d, lab, cfg)
                if not os.path.exists(p):
                    continue
                arr, m = fdri_payload_and_meta(p, profile=ZYNQ7020_V4)
                payloads[(d, lab, cfg)] = arr
                meta[(d, lab, cfg)] = m
    return payloads, meta


def exact_equal(a, b):
    """Exact byte equality. No hashing."""
    return a.shape == b.shape and bool(np.array_equal(a, b))


def duplicate_classes(keys, payloads):
    """Group keys by exact payload equality. Digests propose the grouping;
    every proposal is then confirmed byte-for-byte against the representative.
    Returns (classes, confirmations, collisions)."""
    by_digest = defaultdict(list)
    for k in keys:
        by_digest[payload_hash(payloads[k])].append(k)

    classes = []
    confirmations = 0
    collisions = []
    for digest, members in by_digest.items():
        rep = members[0]
        confirmed = [rep]
        for other in members[1:]:
            confirmations += 1
            if exact_equal(payloads[rep], payloads[other]):
                confirmed.append(other)
            else:
                # Digests agreed but bytes differ: report, never absorb.
                collisions.append({"digest": digest,
                                   "a": list(rep), "b": list(other)})
        classes.append({"digest": digest, "members": confirmed})

    # Cross-check: distinct digests must have distinct bytes too. Confirm every
    # cross-class pair explicitly rather than trusting the digest.
    reps = [c["members"][0] for c in classes]
    for i in range(len(reps)):
        for j in range(i + 1, len(reps)):
            confirmations += 1
            if exact_equal(payloads[reps[i]], payloads[reps[j]]):
                collisions.append({"digest": "cross-class-equal",
                                   "a": list(reps[i]), "b": list(reps[j])})
    return classes, confirmations, collisions


def frame_diff_count(a, b):
    """Number of 404-byte configuration frames that differ."""
    fa = a.reshape(N_FRAMES, FRAME_BYTES)
    fb = b.reshape(N_FRAMES, FRAME_BYTES)
    return int(np.count_nonzero((fa != fb).any(axis=1)))


# ---------------------------------------------------------------------------
def main():
    if not os.path.isdir(ARTIFACTS):
        sys.exit(f"missing {ARTIFACTS} -- retrieve pilot artifacts first")

    env = {}
    envfile = os.path.join(HERE, "vivado_env_capture", "version.txt")
    if os.path.exists(envfile):
        with open(envfile) as f:
            env["vivado_version_raw"] = f.read().strip()

    payloads, metas = load_payloads()

    # ---------------------------------------------------- manifest + results
    manifest = {
        "schema": "rebuild_pilot_v1",
        "phase": "0.5B",
        "generated_by": os.path.basename(__file__),
        "vivado": {
            "version": "2023.2",
            "sw_build": "4029153",
            "build_date": "Fri Oct 13 20:13:54 MDT 2023",
            "install": "/share/reconfig/xilinx2/Vivado/2023.2",
            "host": "meson.cse.sc.edu",
            "raw_version_capture": env.get("vivado_version_raw"),
        },
        "part": "xc7z020clg400-1",
        "constraints": "deployment_pipeline/Constraints/PYNQ-Z1_AES.xdc",
        "profile": ZYNQ7020_V4.name,
        "implementation_configs": CONFIG_SETTINGS,
        "option_provenance": (
            "every place/route/phys_opt directive used appears verbatim in the "
            "installed 2023.2 help captured in vivado_env_capture/; "
            "place_design -seed is NOT documented by this release and was not used"),
        "grouping_rule": (
            "all implementation variants of one host design belong to ONE split "
            "group; variants add P&R diversity, not independent host designs"),
        "artifact_locations": {
            "bitstreams_and_local_copies": "rebuild_pilot/pilot_artifacts/ (gitignored)",
            "tracked_text_evidence": "rebuild_pilot/pilot_evidence/ (logs, reports, small .ll, indices)",
            "checkpoints": ("post_synth.dcp and post_route.dcp remain on the build "
                            "host under meson:~/blade_pilot_phase05b/builds/; each is "
                            "indexed with size + SHA-256 in pilot_evidence/dcp_index.tsv"),
            "logic_location_files": ("all 24 .ll files are indexed with size + SHA-256 in "
                                     "pilot_evidence/ll_index.tsv; the 8 AES ones are ~160 MB "
                                     "each and are kept on disk only, not in Git"),
        },
        "builds": [],
    }

    rows = []
    for d in DESIGNS:
        for lab in LABELS:
            # Synthesis success is judged from the post-synthesis reports, not
            # from the .dcp: the checkpoints are large and deliberately left on
            # the build host (indexed by hash in pilot_evidence/dcp_index.tsv),
            # so a local .dcp existence test would report every build as failed.
            synth_ok = all(os.path.exists(
                os.path.join(ARTIFACTS, "builds", d, lab, "reports", n))
                for n in ("trojan_post_synth.txt", "post_synth_utilization.rpt"))
            for cfg in CONFIGS:
                key = (d, lab, cfg)
                p = bit_path(d, lab, cfg)
                built = key in payloads
                entry = {
                    "design": d,
                    "label": lab,
                    "config": cfg,
                    "place_directive": CONFIG_SETTINGS[cfg]["place"],
                    "route_directive": CONFIG_SETTINGS[cfg]["route"],
                    "phys_opt_directive": CONFIG_SETTINGS[cfg]["phys_opt"],
                    "synthesis_succeeded": synth_ok,
                    "bitstream_built": built,
                    "bit_path": os.path.relpath(p, HERE) if built else None,
                }
                if built:
                    entry["file_sha256"] = file_sha256(p)
                    entry["fdri_payload_digest"] = payload_hash(payloads[key])
                    entry["fdri_payload_bytes"] = int(payloads[key].size)
                    entry["n_frames"] = N_FRAMES
                    entry["ll_file"] = os.path.exists(p.replace(".bit", ".ll"))
                    entry["timing"] = parse_timing(
                        report_path(d, lab, cfg, "post_route_timing.rpt"))
                    entry["utilization"] = parse_utilization(
                        report_path(d, lab, cfg, "post_route_utilization.rpt"))
                    entry["route_status"] = parse_route_status(
                        report_path(d, lab, cfg, "post_route_status.rpt"))
                manifest["builds"].append(entry)

                util = entry.get("utilization", {})
                tim = entry.get("timing", {})
                rows.append({
                    "design": d,
                    "label": lab,
                    "config": cfg,
                    "place_directive": CONFIG_SETTINGS[cfg]["place"],
                    "route_directive": CONFIG_SETTINGS[cfg]["route"],
                    "phys_opt_directive": CONFIG_SETTINGS[cfg]["phys_opt"] or "",
                    "synthesis_succeeded": synth_ok,
                    "bitstream_built": built,
                    "fdri_payload_digest": entry.get("fdri_payload_digest", ""),
                    "luts": util.get("luts", ""),
                    "ffs": util.get("ffs", ""),
                    "bram": util.get("bram", ""),
                    "wns_ns": tim.get("wns_ns", ""),
                    "timing_met": tim.get("timing_met", ""),
                    "fully_routed": entry.get("route_status", {}).get(
                        "fully_routed", ""),
                })

    # ------------------------------------------------ trojan retention
    retention = {
        "schema": "trojan_retention_v1",
        "method": (
            "cells/nets matching the design's documented trojan name patterns "
            "are enumerated post-synthesis and post-route by Vivado itself; the "
            "matched benign build is the control and must report zero matches. "
            "No DONT_TOUCH/KEEP was applied -- if synthesis removed the trojan, "
            "that is recorded as the result."),
        "designs": {},
    }
    for d in DESIGNS:
        rec = {"post_synth": {}, "post_route": {}}
        for lab in LABELS:
            rec["post_synth"][lab] = parse_trojan_report(
                os.path.join(ARTIFACTS, "builds", d, lab, "reports",
                             "trojan_post_synth.txt"))
            for cfg in CONFIGS:
                r = parse_trojan_report(
                    report_path(d, lab, cfg, "trojan_post_route.txt"))
                if r is not None:
                    rec["post_route"].setdefault(lab, {})[cfg] = r
        # Verdict, per pattern against its own benign control. A pattern that
        # also matches in the benign build is NOT trojan evidence -- e.g.
        # *prog_adr_o* matches the PIC16F84 program-address port, which exists
        # in both variants. Only patterns with a zero benign count discriminate,
        # and only those are allowed to establish retention.
        ps_free = rec["post_synth"].get("TjFree") or {}
        ps_in = rec["post_synth"].get("TjIn") or {}
        pf = ps_free.get("patterns") or {}
        pi = ps_in.get("patterns") or {}
        per_pattern = {}
        for pat in sorted(set(pf) | set(pi)):
            bf = pf.get(pat, {"cells": 0, "nets": 0})
            bi = pi.get(pat, {"cells": 0, "nets": 0})
            discriminative = (bf["cells"] == 0 and bf["nets"] == 0
                              and (bi["cells"] > 0 or bi["nets"] > 0))
            per_pattern[pat] = {
                "benign_cells": bf["cells"], "benign_nets": bf["nets"],
                "malicious_cells": bi["cells"], "malicious_nets": bi["nets"],
                "discriminative": discriminative,
                "note": ("" if discriminative else
                         "matches in the benign build too (or not at all): "
                         "not trojan evidence on its own"),
            }
        rec["per_pattern_post_synth"] = per_pattern
        disc = {p: v for p, v in per_pattern.items() if v["discriminative"]}
        rec["discriminative_patterns"] = sorted(disc)
        rec["post_synth_trojan_cells_benign"] = sum(
            v["benign_cells"] for v in disc.values())
        rec["post_synth_trojan_cells_malicious"] = sum(
            v["malicious_cells"] for v in disc.values())
        rec["post_synth_trojan_nets_malicious"] = sum(
            v["malicious_nets"] for v in disc.values())
        rec["trojan_survives_synthesis"] = bool(disc)

        # Post-route: the discriminative patterns must still match.
        pr = {}
        for lab in LABELS:
            for cfg, r in (rec["post_route"].get(lab) or {}).items():
                pats = r.get("patterns") or {}
                pr[f"{lab}/{cfg}"] = {
                    p: {"cells": pats.get(p, {}).get("cells", 0),
                        "nets": pats.get(p, {}).get("nets", 0)}
                    for p in rec["discriminative_patterns"]}
        rec["post_route_discriminative_counts"] = pr
        rec["trojan_survives_all_implementations"] = bool(
            rec["discriminative_patterns"]
            and all(any(v["cells"] > 0 or v["nets"] > 0 for v in counts.values())
                    for k, counts in pr.items() if k.startswith("TjIn/"))
            and all(all(v["cells"] == 0 and v["nets"] == 0
                        for v in counts.values())
                    for k, counts in pr.items() if k.startswith("TjFree/")))
        retention["designs"][d] = rec

    # ------------------------------------------------ payload distinctness
    distinct = {
        "schema": "payload_distinctness_v1",
        "method": (
            "FDRI configuration payloads only (whole-file hashes are unusable: "
            "the .bit ASCII header carries a per-build timestamp). Digests "
            "propose duplicate groups; EVERY proposal is confirmed by exact "
            "byte comparison against the group representative, and every "
            "cross-group representative pair is also compared exactly."),
        "per_design_label": {},
        "per_design_all_configs": {},
        "exact_byte_comparisons": 0,
        "digest_collisions": [],
    }
    total_cmp = 0
    for d in DESIGNS:
        for lab in LABELS:
            keys = [k for k in payloads if k[0] == d and k[1] == lab]
            if not keys:
                continue
            classes, ncmp, coll = duplicate_classes(keys, payloads)
            total_cmp += ncmp
            distinct["digest_collisions"].extend(coll)
            distinct["per_design_label"][f"{d}/{lab}"] = {
                "builds": len(keys),
                "unique_payloads": len(classes),
                "duplicate_classes": [
                    {"digest": c["digest"],
                     "size": len(c["members"]),
                     "configs": sorted(m[2] for m in c["members"])}
                    for c in classes],
                "configs_that_produced_a_unique_payload": sorted(
                    c["members"][0][2] for c in classes if len(c["members"]) == 1),
            }
        keys = [k for k in payloads if k[0] == d]
        if keys:
            classes, ncmp, coll = duplicate_classes(keys, payloads)
            total_cmp += ncmp
            distinct["digest_collisions"].extend(coll)
            distinct["per_design_all_configs"][d] = {
                "builds": len(keys),
                "unique_payloads": len(classes),
                "classes": [
                    {"digest": c["digest"], "size": len(c["members"]),
                     "members": [f"{m[1]}/{m[2]}" for m in c["members"]]}
                    for c in classes],
            }
    distinct["exact_byte_comparisons"] = total_cmp

    # -------------------------------- matched pair diffs + validity verdict
    pair_rows = []
    invalid = []
    for d in DESIGNS:
        for cfg in CONFIGS:
            kf, ki = (d, "TjFree", cfg), (d, "TjIn", cfg)
            if kf not in payloads or ki not in payloads:
                continue
            identical = exact_equal(payloads[kf], payloads[ki])
            nfr = frame_diff_count(payloads[kf], payloads[ki])
            nby = int(np.count_nonzero(payloads[kf] != payloads[ki]))
            pair_rows.append({
                "design": d,
                "config": cfg,
                "place_directive": CONFIG_SETTINGS[cfg]["place"],
                "route_directive": CONFIG_SETTINGS[cfg]["route"],
                "phys_opt_directive": CONFIG_SETTINGS[cfg]["phys_opt"] or "",
                "frames_total": N_FRAMES,
                "frames_differing": nfr,
                "frames_differing_pct": round(100.0 * nfr / N_FRAMES, 3),
                "bytes_differing": nby,
                "payloads_identical": identical,
                "malicious_build_valid": not identical,
            })
            if identical:
                invalid.append({"design": d, "config": cfg,
                                "reason": "malicious FDRI payload byte-identical "
                                          "to matched benign build (no trace)"})

    for b in manifest["builds"]:
        if b["label"] == "TjIn" and b.get("bitstream_built"):
            bad = any(i["design"] == b["design"] and i["config"] == b["config"]
                      for i in invalid)
            b["invalidated_no_trace"] = bad
    manifest["invalidated_builds"] = invalid

    # ------------------------------------------------------------- write out
    with open(os.path.join(HERE, "pilot_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    with open(os.path.join(HERE, "pilot_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(HERE, "payload_distinctness.json"), "w") as f:
        json.dump(distinct, f, indent=2)

    with open(os.path.join(HERE, "trojan_retention.json"), "w") as f:
        json.dump(retention, f, indent=2)

    if pair_rows:
        with open(os.path.join(HERE, "matched_pair_frame_diffs.csv"),
                  "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(pair_rows[0].keys()))
            w.writeheader()
            w.writerows(pair_rows)

    # ------------------------------------------------------------- summary
    print(f"builds with a bitstream: {len(payloads)} / "
          f"{len(DESIGNS) * len(LABELS) * len(CONFIGS)}")
    print(f"exact byte comparisons performed: {total_cmp}")
    print(f"digest collisions: {len(distinct['digest_collisions'])}")
    for k, v in distinct["per_design_label"].items():
        print(f"  {k}: {v['unique_payloads']} unique / {v['builds']} builds")
    for d, rec in retention["designs"].items():
        print(f"  trojan {d}: benign={rec['post_synth_trojan_cells_benign']} "
              f"malicious={rec['post_synth_trojan_cells_malicious']} "
              f"survives={rec['trojan_survives_synthesis']}")
    for r in pair_rows:
        print(f"  diff {r['design']}/{r['config']}: "
              f"{r['frames_differing']}/{N_FRAMES} frames "
              f"{'INVALID(no trace)' if r['payloads_identical'] else ''}")


if __name__ == "__main__":
    main()
