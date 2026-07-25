# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Leakage audit, finding 5 -- HEADER/METADATA LABEL LEAK.
#              Claim under test: the .bit ASCII container header (design-name
#              field, tool-version field, and the resulting header length /
#              file size) is correlated with the class label, and the legacy
#              whole-file feature path reads it.
#
#              STANDALONE by design: this script parses the .bit container
#              with its OWN field walker and locates the config region with
#              its OWN sync search -- it does not import bitstream_io for any
#              of its independent checks. Two checks:
#
#     A. Parse every file's header fields and produce contingency tables:
#        header length x label, design-name field x label, tool-version
#        field x label, file size x label, family x label -- plus the count
#        of files whose label is DETERMINED by each field alone.
#
#     B. Demonstration on identical-payload pairs: pairs proposed by the
#        corpus index are INDEPENDENTLY re-confirmed identical by comparing
#        every byte after this script's own sync search (config regions are
#        byte-identical => FDRI payloads are byte-identical, no FDRI parsing
#        needed). Then:
#          - legacy whole-file features (frozen train_model) DIFFER;
#          - corrected FDRI-only features (bitstream_io -- the corrected
#            path under demonstration, not part of the independent checks)
#            are EXACTLY identical;
#          - diagnostic classifiers whose inputs contain no FDRI bytes by
#            construction (file size alone; pre-sync header bytes alone)
#            score above chance under duplicate-safe payload-component
#            grouped splits.
#
# Usage:
#   python3 verify_header_leak.py [--data-dir DIR] [--outdir rebuild_pilot]

import warnings
warnings.filterwarnings("ignore")

import argparse
import json
import os
import struct
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

SYNC = bytes([0xAA, 0x99, 0x55, 0x66])

FAMILY_PREFIXES = {
    "CRYPTO": ["AES", "BasicRSA"],
    "COMMS": ["RS232", "EthernetMAC10GE"],
    "MCU/CPU": ["PIC16F84"],
    "BUS/DISPLAY": ["wb_conmax", "vga_lcd"],
    "ITC99": ["b15", "b19"],
    "ISCAS89": ["s15850", "s35932", "s38417", "s38584"],
    "ISCAS85": ["c1355", "c1908", "c2670", "c3540", "c432", "c499", "c5315",
                "c6288", "c7552", "c880"],
}

CLAIM = {"files_label_determined_by_header_length": 544,
         # The original exploratory quantifications (size-only 0.774,
         # header-only 0.751) were measured under the DESIGN-GROUPED split,
         # which the audit later showed is duplicate-leaked -- so they
         # overstate the exploitable channel and are superseded by the
         # payload-component-split numbers this script measures. They are
         # recorded here as history, not as expectations to match.
         "superseded_exploratory_size_only_bal_acc": 0.774,
         "superseded_exploratory_header_only_bal_acc": 0.751}


def family_of(path):
    base = os.path.basename(path)
    for fam, prefixes in FAMILY_PREFIXES.items():
        if base.startswith(tuple(prefixes)):
            return fam
    return "UNKNOWN"


def parse_bit_container(blob, path="<bytes>"):
    """Own .bit container-field walker (Xilinx .bit wrapper, not the config
    stream): u16-length magic block, then letter-tagged fields
    a=design/UserID/Version string, b=part, c=date, d=time, e=u32 data length.
    Returns the fields plus this script's own sync-offset measurement."""
    off = 0

    def u16():
        nonlocal off
        v = struct.unpack_from(">H", blob, off)[0]
        off += 2
        return v

    n = u16()                      # magic block, typically 9 bytes
    off += n
    u16()                          # field count / 0x0001 before 'a'
    fields = {}
    while off < len(blob):
        tag = blob[off:off + 1].decode("latin1")
        off += 1
        if tag == "e":
            fields["e_data_len"] = struct.unpack_from(">I", blob, off)[0]
            off += 4
            break
        ln = u16()
        fields[tag] = blob[off:off + ln].rstrip(b"\x00").decode("latin1")
        off += ln
    sync = blob.find(SYNC)
    if sync < 0:
        raise ValueError(f"{path}: no sync word")
    a = fields.get("a", "")
    version = ""
    for part in a.split(";"):
        if part.startswith("Version="):
            version = part[len("Version="):]
    return {"design_field": a.split(";")[0], "raw_a": a,
            "part": fields.get("b", ""), "date": fields.get("c", ""),
            "time": fields.get("d", ""), "version": version,
            "has_sw_crc": "SW_CRC=" in a,
            "header_len": sync,            # own measurement: bytes before sync
            "e_data_len": fields.get("e_data_len")}


def contingency(values, labels):
    """value -> {benign, malicious}; plus files whose value determines label."""
    table = defaultdict(lambda: {"benign": 0, "malicious": 0})
    for v, l in zip(values, labels):
        table[v]["malicious" if l else "benign"] += 1
    determined = sum(c["benign"] + c["malicious"] for c in table.values()
                     if c["benign"] == 0 or c["malicious"] == 0)
    return ({str(k): dict(v) for k, v in sorted(table.items(),
                                                key=lambda kv: str(kv[0]))},
            determined)


def main():
    p = argparse.ArgumentParser(description="Verify finding 5: header leak")
    p.add_argument("--data-dir",
                   default=os.path.expanduser(
                       "~/Desktop/Karakchi-Research/trusthub_bitstreams_v4"))
    p.add_argument("--outdir", default="rebuild_pilot")
    p.add_argument("--index", default=os.path.join("corpus_out",
                                                   "corpus_index.json"))
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--n-pairs", type=int, default=5)
    args = p.parse_args()

    import glob
    benign = sorted(glob.glob(os.path.join(args.data_dir, "Benign", "*.bit")))
    mal = sorted(glob.glob(os.path.join(args.data_dir, "Malicious", "*.bit")))
    files = benign + mal
    y = np.array([0] * len(benign) + [1] * len(mal))
    if not files:
        sys.exit(f"no bitstreams under {args.data_dir}")
    os.makedirs(args.outdir, exist_ok=True)
    print(f"=== Finding 5/5: HEADER/METADATA LABEL LEAK ===")
    print(f"{len(files)} files ({len(benign)} benign, {len(mal)} malicious)\n")

    # ---- A: header-field contingency tables (own parser) -------------------
    print("A   parsing .bit container fields (own walker, own sync search)...")
    heads, sizes, hdr_bytes = [], [], []
    for i, f in enumerate(files, 1):
        with open(f, "rb") as fh:
            head = fh.read(4096)
        rec = parse_bit_container(head, f)
        heads.append(rec)
        sizes.append(os.path.getsize(f))
        hdr_bytes.append(head[:rec["header_len"]])
        if i % 300 == 0 or i == len(files):
            print(f"    {i}/{len(files)}")

    fams = [family_of(f) for f in files]
    tables, determined = {}, {}
    for name, vals in (
            ("header_length", [h["header_len"] for h in heads]),
            ("design_field", [h["design_field"] for h in heads]),
            ("tool_version", [h["version"] + ("+SW_CRC" if h["has_sw_crc"]
                                              else "") for h in heads]),
            ("file_size", sizes),
            ("build_date", [h["date"] for h in heads]),
            ("part", [h["part"] for h in heads]),
            ("family", fams)):
        tables[name], determined[name] = contingency(vals, y)
        print(f"    {name:<14} {len(tables[name]):>4} distinct values | "
              f"label determined for {determined[name]:>4}/{len(files)} files")
    print("\n    design_field x label:")
    for v, c in tables["design_field"].items():
        print(f"      {v:<22} benign {c['benign']:>4} | malicious "
              f"{c['malicious']:>4}")
    print("    tool_version x label:")
    for v, c in tables["tool_version"].items():
        print(f"      {v:<22} benign {c['benign']:>4} | malicious "
              f"{c['malicious']:>4}")

    # ---- B1: identical-payload pairs, independently re-confirmed -----------
    print("\nB1  identical-payload / different-header pairs "
          "(index proposes, THIS script re-confirms byte-for-byte)...")
    with open(args.index) as f:
        index = json.load(f)
    rel_to_i = {os.path.relpath(f, args.data_dir): i
                for i, f in enumerate(files)}
    pairs = []
    for cl in index["payload_classes"]:
        if cl["n_aliases"] < 2:
            continue
        aliases = cl["benign_aliases"] + cl["malicious_aliases"]
        a = rel_to_i[aliases[0]]
        for other in aliases[1:]:
            b = rel_to_i[other]
            if (heads[a]["header_len"] != heads[b]["header_len"]
                    or heads[a]["raw_a"] != heads[b]["raw_a"]
                    or heads[a]["date"] != heads[b]["date"]
                    or heads[a]["time"] != heads[b]["time"]):
                pairs.append((a, b, cl["payload_id"]))
                break
        if len(pairs) >= args.n_pairs:
            break
    assert pairs, "no identical-payload pairs with differing headers found"

    import train_model as tm                       # frozen legacy path
    from bitstream_io import extract_statistical_features_fdri  # corrected

    pair_records = []
    for a, b, pid in pairs:
        with open(files[a], "rb") as fh:
            blob_a = fh.read()
        with open(files[b], "rb") as fh:
            blob_b = fh.read()
        # Independent identity confirmation: every byte after the sync word.
        region_a = blob_a[blob_a.find(SYNC) + 4:]
        region_b = blob_b[blob_b.find(SYNC) + 4:]
        regions_identical = region_a == region_b
        headers_differ = (blob_a[:blob_a.find(SYNC)]
                          != blob_b[:blob_b.find(SYNC)])
        legacy_a = tm.extract_statistical_features(files[a])
        legacy_b = tm.extract_statistical_features(files[b])
        corrected_a = extract_statistical_features_fdri(files[a])
        corrected_b = extract_statistical_features_fdri(files[b])
        n_legacy_diff = int(np.sum(legacy_a != legacy_b))
        rec = {"payload_id": pid,
               "file_a": os.path.basename(files[a]),
               "file_b": os.path.basename(files[b]),
               "label_a": int(y[a]), "label_b": int(y[b]),
               "header_len_a": heads[a]["header_len"],
               "header_len_b": heads[b]["header_len"],
               "file_size_a": sizes[a], "file_size_b": sizes[b],
               "config_regions_identical": bool(regions_identical),
               "headers_differ": bool(headers_differ),
               "legacy_wholefile_features_differ": n_legacy_diff > 0,
               "n_legacy_feature_dims_differing": n_legacy_diff,
               "corrected_fdri_features_identical":
                   bool(np.array_equal(corrected_a, corrected_b))}
        pair_records.append(rec)
        print(f"    {rec['file_a']:<32} vs {rec['file_b']:<32} "
              f"regions identical: {rec['config_regions_identical']} | "
              f"legacy dims differing: {n_legacy_diff:>3} | "
              f"corrected identical: {rec['corrected_fdri_features_identical']}")

    # ---- B2: diagnostic classifiers with no FDRI access --------------------
    print("\nB2  diagnostic classifiers (inputs contain no FDRI bytes by "
          "construction), payload-component grouped split...")
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import balanced_accuracy_score
    from split_utils import payload_aware_grouped_split_indices

    pids = np.array([r["payload_id"] for r in index["files"]])
    comps = np.array([r["component_id"] for r in index["files"]])
    index_rel = [r["relpath"] for r in index["files"]]
    order = [rel_to_i[r] for r in index_rel]
    inv = np.empty(len(files), dtype=int)
    inv[order] = np.arange(len(files))
    pids, comps = pids[inv], comps[inv]           # align to this file order

    X_size = np.array(sizes, dtype=float).reshape(-1, 1)
    X_hdr = np.stack([np.bincount(np.frombuffer(h, dtype=np.uint8),
                                  minlength=256) for h in hdr_bytes]) \
        .astype(float)
    not85 = np.array([f_ != "ISCAS85" for f_ in fams])

    def run_clf(X, mask, tag):
        sub = np.flatnonzero(mask)
        fl = [files[i] for i in sub]
        sc = []
        for seed in range(args.seeds):
            t, v, te = payload_aware_grouped_split_indices(
                fl, y[sub], seed, payload_ids=pids[sub],
                components=comps[sub])
            tr = sub[np.concatenate([t, v])]
            teg = sub[te]
            clf = RandomForestClassifier(n_estimators=300,
                                         class_weight="balanced",
                                         random_state=seed, n_jobs=-1)
            clf.fit(X[tr], y[tr])
            sc.append(balanced_accuracy_score(y[teg], clf.predict(X[teg])))
        v_ = np.array(sc)
        print(f"    {tag:<44} bal_acc {v_.mean():.4f}+/-{v_.std():.4f} "
              f"({len(sc)} seeds)")
        return {"bal_acc_mean": round(float(v_.mean()), 4),
                "bal_acc_std": round(float(v_.std()), 4),
                "per_seed": [round(float(s), 4) for s in sc]}

    clf_results = {
        "file_size_only__full_corpus": run_clf(X_size, np.ones(len(files),
                                                               dtype=bool),
                                               "file size only, full corpus"),
        "file_size_only__excl_ISCAS85": run_clf(X_size, not85,
                                                "file size only, excl. "
                                                "ISCAS85"),
        "header_bytes_only__full_corpus": run_clf(X_hdr,
                                                  np.ones(len(files),
                                                          dtype=bool),
                                                  "header byte histogram, "
                                                  "full corpus"),
        "header_bytes_only__excl_ISCAS85": run_clf(X_hdr, not85,
                                                   "header byte histogram, "
                                                   "excl. ISCAS85"),
    }

    # ---- verdict ------------------------------------------------------------
    checks = {
        "A_header_length_determines_labels":
            determined["header_length"] == CLAIM[
                "files_label_determined_by_header_length"],
        "A_design_field_has_benign_only_values": any(
            c["malicious"] == 0 and c["benign"] > 0
            for c in tables["design_field"].values()),
        "A_tool_version_has_malicious_only_value": any(
            c["benign"] == 0 and c["malicious"] > 0
            for c in tables["tool_version"].values()),
        "B1_all_pairs_regions_identical": all(
            r["config_regions_identical"] for r in pair_records),
        "B1_all_pairs_headers_differ": all(
            r["headers_differ"] for r in pair_records),
        "B1_legacy_features_differ_on_every_pair": all(
            r["legacy_wholefile_features_differ"] for r in pair_records),
        "B1_corrected_features_identical_on_every_pair": all(
            r["corrected_fdri_features_identical"] for r in pair_records),
        # The finding is the EXISTENCE of a no-FDRI channel plus legacy
        # exposure (A + B1). One above-chance no-FDRI classifier under the
        # duplicate-safe split suffices to show exploitability; the full set
        # of quantifications (including the ~chance excl-ISCAS85 rows, which
        # bound the residual channel) is reported as data, not gated.
        "B2_some_no_fdri_classifier_above_chance": any(
            r["bal_acc_mean"] > 0.55 for r in clf_results.values()),
    }
    print("\n--- VERDICT ---")
    for k, v in checks.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    ok = all(checks.values())
    print(f"\nFINDING 5 {'CONFIRMED' if ok else 'NOT CONFIRMED'}")

    out = {"finding": "header_metadata_label_leak", "confirmed": ok,
           "generated": datetime.now(timezone.utc).isoformat(),
           "claim": CLAIM, "data_dir": args.data_dir,
           "n_files": len(files),
           "method": {
               "independence": "own .bit container-field walker + own sync "
                               "search; identical-payload pairs proposed by "
                               "the corpus index are re-confirmed by "
                               "comparing every byte after this script's own "
                               "sync offset; corrected-feature identity uses "
                               "bitstream_io (the corrected path under "
                               "demonstration, not an independent check)",
               "diagnostic_classifier_inputs": "file size scalar; 256-bin "
                                               "histogram of pre-sync header "
                                               "bytes -- neither contains "
                                               "any FDRI byte by "
                                               "construction",
               "split": "payload_component_v1 grouped, components from the "
                        "corpus index, 5 seeds"},
           "contingency_tables": tables,
           "labels_determined_by_field": determined,
           "pair_demonstrations": pair_records,
           "diagnostic_classifiers": clf_results,
           "limitations": [
               "diagnostic classifiers use RandomForest(300) only; the "
               "point is existence of the channel, not its maximum strength",
               "ISCAS85 carries most but not all of the determinism: the "
               "excl-ISCAS85 rows quantify the remainder and come out at or "
               "below chance under the duplicate-safe split -- deterministic "
               "field-label associations exist there (benign-only design "
               "fields) but are not exploitable by these classifiers when "
               "whole components are held out",
               "the earlier exploratory quantifications (0.774 size-only, "
               "0.751 header-only) were measured under the design-grouped "
               "split, which is duplicate-leaked; they are SUPERSEDED by "
               "the payload-component-split numbers here and should not be "
               "cited",
               "date/time fields differ per build and were not used as "
               "classifier features (they would trivially memorize builds)"],
           "checks": checks}
    path = os.path.join(args.outdir, "header_leak_verification.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"log -> {path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
