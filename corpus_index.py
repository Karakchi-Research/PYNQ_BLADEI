# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Versioned corpus index for the leakage-controlled dataset
#              (Phase 0.5). Makes ONE DISTINCT CONFIGURATION PAYLOAD the
#              primary sample unit:
#
#              - validates every .bit against the strict V4 profile
#                (bitstream_io.ZYNQ7020_V4) and REJECTS the build on any
#                deviation -- this doubles as the all-corpus audit command;
#              - clusters files by payload digest, then CONFIRMS every
#                proposed match by exact byte comparison before merging
#                (no conclusion rests on a hash being collision-free);
#              - stores all duplicate filenames as aliases of one payload
#                class, and elects one canonical sample per unique payload;
#              - quarantines malicious aliases whose payload is byte-identical
#                to a benign build ("no bitstream trace" positives), retains
#                one benign representative of that physical configuration, and
#                preserves the full history in
#                leakage_audit_out/quarantine_contradictory.json;
#              - computes payload COMPONENTS: connected components of
#                (shared design key) OR (shared exact payload), the grouping
#                unit for corrected splits (split_utils);
#              - logs physical file counts AND effective unique-payload
#                counts, plus payload-cluster size distributions;
#              - cross-checks the totals against the independently verified
#                audit numbers (LEAKAGE_AUDIT.md) when indexing the full V4
#                corpus, and refuses to write an index that contradicts them.
#
#              Primary post-audit metrics are computed over unique payload
#              samples (canonical_files); alias/file-weighted numbers are
#              secondary by decree (RESEARCH_PLAN.md Phase 0.5).
#
# Usage:
#   python3 corpus_index.py [--data-dir DIR] [--outdir corpus_out]

import argparse
import glob
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

from bitstream_io import (PARSER_VERSION, ZYNQ7020_V4, fdri_payload_and_meta,
                          parse_fdri, payload_hash, validate_profile)
from split_utils import design_name

INDEX_VERSION = "corpus_index_v1"
DEDUP_POLICY = "one_canonical_sample_per_exact_payload_v1"
QUARANTINE_REASON = "no_bitstream_trace: payload byte-identical to a benign build"

# Mirrors the frozen train_model.FAMILY_MAPPING (train_model.py is the frozen
# pre-audit reference; importing it here would pull in torch for a pure
# indexing step). phase05 scripts that do import train_model cross-check the
# two mappings at runtime.
FAMILY_MAPPING = {
    "CRYPTO": ["AES", "BasicRSA"],
    "COMMS": ["RS232", "EthernetMAC10GE"],
    "MCU/CPU": ["PIC16F84"],
    "BUS/DISPLAY": ["wb_conmax", "vga_lcd"],
    "ITC99": ["b15", "b19"],
    "ISCAS89": ["s15850", "s35932", "s38417", "s38584"],
    "ISCAS85": ["c1355", "c1908", "c2670", "c3540", "c432", "c499", "c5315",
                "c6288", "c7552", "c880"],
}

# Independently verified totals for the full V4 corpus (LEAKAGE_AUDIT.md).
# The index build cross-checks against these when it sees exactly this corpus
# and ABORTS on disagreement (that would mean the audit itself was wrong).
EXPECTED_V4 = {"n_files": 1383, "n_benign": 545, "n_malicious": 838,
               "unique_payloads": 431, "contradictory_classes": 11,
               "quarantined_malicious": 169,
               "files_in_contradictory_classes": 367}


def family_of(path):
    base = os.path.basename(path)
    for fam, prefixes in FAMILY_MAPPING.items():
        if base.startswith(tuple(prefixes)):
            return fam
    return "UNKNOWN"


class _UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, a):
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _confirm_exact(files, spans, members, rep):
    """Byte-compare each member's payload against the representative's.
    Returns the list of members CONFIRMED identical to rep (must be all)."""
    rs, rn = spans[rep]
    with open(files[rep], "rb") as f:
        f.seek(rs)
        ref = f.read(rn)
    for m in members:
        if m == rep:
            continue
        ms, mn = spans[m]
        if mn != rn:
            raise AssertionError(f"digest collision with differing length: "
                                 f"{files[m]} vs {files[rep]}")
        with open(files[m], "rb") as f:
            f.seek(ms)
            if f.read(mn) != ref:
                raise AssertionError(f"digest collision: {files[m]} != "
                                     f"{files[rep]} despite equal digest")
    return members


def build_index(data_dir, outdir="corpus_out",
                quarantine_path=os.path.join("leakage_audit_out",
                                             "quarantine_contradictory.json"),
                profile=ZYNQ7020_V4, expected=None):
    benign = sorted(glob.glob(os.path.join(data_dir, "Benign", "*.bit")))
    malicious = sorted(glob.glob(os.path.join(data_dir, "Malicious", "*.bit")))
    files = benign + malicious
    labels = [0] * len(benign) + [1] * len(malicious)
    if not files:
        sys.exit(f"no bitstreams under {data_dir}")
    if expected is None and len(files) == EXPECTED_V4["n_files"]:
        expected = EXPECTED_V4

    # ---- 1. Profile audit + digests (the all-corpus audit) -----------------
    print(f"=== Corpus index build: {len(files)} files "
          f"({len(benign)} benign, {len(malicious)} malicious) ===")
    print(f"profile: {profile.name} | parser: {PARSER_VERSION}")
    digests, spans, rejects = [], [], []
    for i, f in enumerate(files, 1):
        try:
            arr, meta = fdri_payload_and_meta(f, profile=profile)
            b = meta.fdri_blocks[0]
            spans.append((b.payload_offset_in_file, b.n_bytes))
            digests.append(hashlib.blake2b(arr.tobytes(),
                                           digest_size=32).hexdigest())
        except Exception as e:
            rejects.append((f, str(e)))
            spans.append(None)
            digests.append(None)
        if i % 200 == 0 or i == len(files):
            print(f"    audited {i}/{len(files)}")
    if rejects:
        for f, msg in rejects[:10]:
            print(f"  REJECT {f}: {msg}")
        sys.exit(f"corpus audit FAILED: {len(rejects)} file(s) violate "
                 f"profile '{profile.name}' -- refusing to build an index")
    print(f"    profile audit: all {len(files)} files conform")

    # ---- 2. Exact payload classes (digest proposes, bytes confirm) ---------
    by_digest = defaultdict(list)
    for i, d in enumerate(digests):
        by_digest[d].append(i)
    n_confirmed = 0
    for d, members in by_digest.items():
        if len(members) > 1:
            _confirm_exact(files, spans, members, members[0])
            n_confirmed += len(members) - 1
    print(f"    exact confirmation: {n_confirmed} byte-for-byte comparisons, "
          f"all matched their digest cluster")

    # Stable class ids ordered by first alias path.
    classes = sorted(by_digest.items(),
                     key=lambda kv: min(os.path.basename(files[i])
                                        for i in kv[1]))
    payload_id_of = {}
    for cid, (d, members) in enumerate(classes):
        for i in members:
            payload_id_of[i] = f"p{cid:04d}"

    # ---- 3. Components: design-key edges OR payload edges ------------------
    keys = [design_name(f) for f in files]
    uf = _UnionFind(len(files))
    first_of = {}
    for i, k in enumerate(keys):
        if k in first_of:
            uf.union(i, first_of[k])
        else:
            first_of[k] = i
    for d, members in by_digest.items():
        for m in members[1:]:
            uf.union(members[0], m)
    roots = sorted({uf.find(i) for i in range(len(files))})
    comp_of = {r: f"c{n:04d}" for n, r in enumerate(roots)}
    component_id = [comp_of[uf.find(i)] for i in range(len(files))]

    # ---- 4. Canonical samples + quarantine ---------------------------------
    payload_classes, quarantined_idx = [], set()
    for cid, (digest, members) in enumerate(classes):
        pid = f"p{cid:04d}"
        b_alias = sorted(os.path.relpath(files[i], data_dir)
                         for i in members if labels[i] == 0)
        m_alias = sorted(os.path.relpath(files[i], data_dir)
                         for i in members if labels[i] == 1)
        contradictory = bool(b_alias) and bool(m_alias)
        # Canonical label: benign wins a contradiction -- the payload IS
        # producible by a benign build; the malicious aliases carry no trace.
        canon_label = 0 if b_alias else 1
        canon_pool = b_alias if b_alias else m_alias
        canonical = canon_pool[0]
        if contradictory:
            for i in members:
                if labels[i] == 1:
                    quarantined_idx.add(i)
        payload_classes.append({
            "payload_id": pid, "digest": digest,
            "n_aliases": len(members),
            "benign_aliases": b_alias, "malicious_aliases": m_alias,
            "contradictory": contradictory,
            "canonical_label": canon_label,
            "canonical_alias": canonical,
            "component_id": component_id[members[0]],
            "design_keys": sorted({keys[i] for i in members}),
            "family": family_of(files[members[0]]),
        })

    files_rec = [{"relpath": os.path.relpath(files[i], data_dir),
                  "label": labels[i], "family": family_of(files[i]),
                  "design_key": keys[i], "payload_id": payload_id_of[i],
                  "component_id": component_id[i],
                  "quarantined": i in quarantined_idx}
                 for i in range(len(files))]

    # ---- 5. Accounting + cross-check against the verified audit ------------
    contra = [c for c in payload_classes if c["contradictory"]]
    canon_b = sum(1 for c in payload_classes if c["canonical_label"] == 0)
    canon_m = len(payload_classes) - canon_b
    cluster_dist = Counter(c["n_aliases"] for c in payload_classes)
    per_family = {}
    for fam in FAMILY_MAPPING:
        fam_classes = [c for c in payload_classes if c["family"] == fam]
        fam_files = [r for r in files_rec if r["family"] == fam]
        if not fam_files:
            continue
        per_family[fam] = {
            "physical_files": len(fam_files),
            "unique_payloads": len(fam_classes),
            "canonical_benign": sum(1 for c in fam_classes
                                    if c["canonical_label"] == 0),
            "canonical_malicious": sum(1 for c in fam_classes
                                       if c["canonical_label"] == 1),
            "quarantined": sum(1 for r in fam_files if r["quarantined"]),
        }

    got = {"n_files": len(files), "n_benign": len(benign),
           "n_malicious": len(malicious),
           "unique_payloads": len(payload_classes),
           "contradictory_classes": len(contra),
           "quarantined_malicious": len(quarantined_idx),
           "files_in_contradictory_classes": sum(c["n_aliases"]
                                                 for c in contra)}
    if expected:
        bad = {k: (got[k], v) for k, v in expected.items() if got[k] != v}
        if bad:
            sys.exit("cross-check against the independently verified audit "
                     f"FAILED: {bad} -- refusing to write the index; "
                     "investigate before proceeding (this would mean "
                     "LEAKAGE_AUDIT.md is wrong)")
        print(f"    cross-check vs verified audit counts: all "
              f"{len(expected)} totals match")

    manifest_id = hashlib.sha256("\n".join(
        f"{r['relpath']}:{payload_classes[int(r['payload_id'][1:])]['digest']}"
        f":{r['label']}" for r in files_rec).encode()).hexdigest()[:16]

    index = {
        "version": INDEX_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(),
        "data_dir": os.path.abspath(data_dir),
        "profile": profile.name,
        "parser_version": PARSER_VERSION,
        "dedup_policy": DEDUP_POLICY,
        "manifest_id": manifest_id,
        "counts": {**got, "canonical_benign": canon_b,
                   "canonical_malicious": canon_m,
                   "n_components": len(roots),
                   "post_quarantine_files": len(files) - len(quarantined_idx)},
        "cluster_size_distribution": {str(k): v for k, v
                                      in sorted(cluster_dist.items())},
        "per_family": per_family,
        "payload_classes": payload_classes,
        "files": files_rec,
    }

    os.makedirs(outdir, exist_ok=True)
    index_path = os.path.join(outdir, "corpus_index.json")
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    index["index_sha256"] = file_hash = _sha256(index_path)

    # ---- 6. Quarantine artifact (full history, nothing silently deleted) ---
    os.makedirs(os.path.dirname(quarantine_path), exist_ok=True)
    quarantine = {
        "version": INDEX_VERSION,
        "generated": index["generated"],
        "manifest_id": manifest_id,
        "reason": QUARANTINE_REASON,
        "totals": {"contradictory_classes": len(contra),
                   "files_in_contradictory_classes": got[
                       "files_in_contradictory_classes"],
                   "quarantined_malicious_aliases": len(quarantined_idx)},
        "finding": ("These malicious builds produced configuration payloads "
                    "byte-identical to a benign build (synthesis plausibly "
                    "stripped dormant/unconnected trojan logic). They are "
                    "reported as a dataset finding; their labels cannot be "
                    "recovered from the bitstream bytes by any model."),
        "classes": [{"payload_id": c["payload_id"], "digest": c["digest"],
                     "component_id": c["component_id"],
                     "benign_aliases": c["benign_aliases"],
                     "quarantined_malicious_aliases": c["malicious_aliases"],
                     "retained_benign_representative": c["canonical_alias"],
                     "reason": QUARANTINE_REASON}
                    for c in contra],
    }
    with open(quarantine_path, "w") as f:
        json.dump(quarantine, f, indent=2)

    print(f"\n--- INDEX SUMMARY ---")
    print(f"  physical files            : {got['n_files']} "
          f"({got['n_benign']} B / {got['n_malicious']} M)")
    print(f"  unique payloads (canonical): {got['unique_payloads']} "
          f"({canon_b} B / {canon_m} M)")
    print(f"  payload components        : {len(roots)}")
    print(f"  contradictory classes     : {len(contra)} "
          f"({got['files_in_contradictory_classes']} files)")
    print(f"  quarantined malicious     : {len(quarantined_idx)}")
    print(f"  cluster sizes             : "
          f"{dict(sorted(cluster_dist.items()))}")
    for fam, c in per_family.items():
        print(f"    {fam:<12} files {c['physical_files']:>4} | unique "
              f"{c['unique_payloads']:>3} (B {c['canonical_benign']:>2} / "
              f"M {c['canonical_malicious']:>3}) | quarantined "
              f"{c['quarantined']:>3}")
    print(f"  manifest_id: {manifest_id}")
    print(f"  index -> {index_path} (sha256 {file_hash[:16]}...)")
    print(f"  quarantine -> {quarantine_path}")
    return index, index_path, quarantine_path


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load_index(path=os.path.join("corpus_out", "corpus_index.json"),
               expect_version=INDEX_VERSION):
    with open(path) as f:
        index = json.load(f)
    if index.get("version") != expect_version:
        raise RuntimeError(f"{path}: index version "
                           f"{index.get('version')!r} != {expect_version!r}")
    index["index_sha256"] = _sha256(path)
    return index


def main():
    p = argparse.ArgumentParser(description="Build the leakage-controlled "
                                            "corpus index (doubles as the "
                                            "all-corpus profile audit)")
    p.add_argument("--data-dir",
                   default=os.path.expanduser(
                       "~/Desktop/Karakchi-Research/trusthub_bitstreams_v4"))
    p.add_argument("--outdir", default="corpus_out")
    p.add_argument("--quarantine",
                   default=os.path.join("leakage_audit_out",
                                        "quarantine_contradictory.json"))
    args = p.parse_args()
    build_index(args.data_dir, args.outdir, args.quarantine)


if __name__ == "__main__":
    main()
