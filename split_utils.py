# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Group-wise train/val/test splitting for Trust-Hub bitstreams.
#              All place-and-route variants of a design (and its benign/malicious
#              builds) share one design key and always land on the same side of a
#              split, so a model can never be tested on a design it trained on.
#              Also home of the 7-series frame constant used for frame-aligned
#              windowing (101 words x 32 bits = 404 bytes per config frame).

import json
import os
import re

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

# 7-series configuration frame: 101 words x 32 bits.
FRAME_BYTES = 404

_LABEL_TOKEN = re.compile(r"_(benign|malicious)_", re.IGNORECASE)
# Design key = everything up to and including the Trust-Hub benchmark token
# `_T<nnn>`. Whatever build/variant suffixes follow (`_v3`, `_Trojan`, `_d2`,
# in any order) describe rebuilds of the SAME design and stay in its group.
_BENCHMARK_KEY = re.compile(r"^(.+?_T\d+)(?=_|$)")
_VARIANT_SUFFIX = re.compile(r"_v\d+$", re.IGNORECASE)
_TROJAN_SUFFIX = re.compile(r"_trojan$", re.IGNORECASE)


def design_name(path):
    """Design key from a bitstream filename.

    Real Trust-Hub layout -- the trojan-free build, the trojaned build, and all
    P&R/build variants of one benchmark share a key:
      'AES_T100.bit'                          -> 'AES_T100'
      'AES_T100_Trojan_v2.bit'                -> 'AES_T100'
      'wb_conmax_T300_Trojan_v5.bit'          -> 'wb_conmax_T300'
      'EthernetMAC10GE_T700_d2_v2_Trojan.bit' -> 'EthernetMAC10GE_T700'
    Legacy timestamped layout:
      'AES-T200_benign_20260404_223130.bit' -> 'AES-T200'
    """
    base = os.path.basename(path)
    m = _LABEL_TOKEN.search(base)
    if m:
        return base[:m.start()]
    stem = os.path.splitext(base)[0]
    m = _BENCHMARK_KEY.match(stem)
    if m:
        return m.group(1)
    stem = _VARIANT_SUFFIX.sub("", stem)
    return _TROJAN_SUFFIX.sub("", stem)


def assert_disjoint(groups, idx_a, idx_b, name_a, name_b):
    overlap = {groups[i] for i in idx_a} & {groups[i] for i in idx_b}
    assert not overlap, (
        f"{len(overlap)} design(s) on both {name_a} and {name_b} sides, "
        f"e.g. {sorted(overlap)[:5]}")


def grouped_split_indices(files, y, seed):
    """60/20/20 train/val/test indices, grouped by design name.

    Approximately label-stratified via StratifiedGroupKFold; never splits by
    file. Raises if any design ends up on two sides.
    """
    groups = np.array([design_name(f) for f in files])
    y = np.asarray(y)

    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    idx_tr, idx_te = next(outer.split(np.zeros(len(y)), y, groups))
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    rel_t, rel_v = next(inner.split(np.zeros(len(idx_tr)), y[idx_tr], groups[idx_tr]))
    idx_t, idx_v = idx_tr[rel_t], idx_tr[rel_v]

    assert_disjoint(groups, idx_t, idx_te, "train", "test")
    assert_disjoint(groups, idx_v, idx_te, "val", "test")
    assert_disjoint(groups, idx_t, idx_v, "train", "val")
    return idx_t, idx_v, idx_te


def log_split(path, seed, files, y, idx_t, idx_v, idx_te, config):
    """Write the split composition + experiment config to a JSON file."""
    groups = [design_name(f) for f in files]
    y = np.asarray(y)

    def side(idx):
        return {"n_files": int(len(idx)),
                "n_malicious": int(np.sum(y[idx] == 1)),
                "designs": sorted({groups[i] for i in idx})}

    with open(path, "w") as f:
        json.dump({"seed": seed, "config": config, "train": side(idx_t),
                   "val": side(idx_v), "test": side(idx_te)}, f, indent=2)


# ---------------------------------------------------------------------------
# Phase 0.5 corrected split path (payload-aware). The legacy functions above
# are kept UNCHANGED so pre-audit results stay reproducible; corrected
# experiments must call these explicitly. See RESEARCH_PLAN.md Phase 0.5 and
# LEAKAGE_AUDIT.md finding 3 (design-key grouping is correctly implemented
# but byte-identical payloads span design keys, so the design key is the
# wrong equivalence class).
# ---------------------------------------------------------------------------
SPLIT_SCHEMA_PAYLOAD_COMPONENT = "payload_component_v1"


def payload_component_labels(files, payload_ids):
    """Connected-component label per file, from the corpus index's payload
    ids: two files share a component iff linked by shared design identity OR
    shared exact configuration payload. `payload_ids` come precomputed from
    corpus_index (no hashing happens here)."""
    files = list(files)
    payload_ids = list(payload_ids)
    assert len(files) == len(payload_ids)
    parent = list(range(len(files)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    first = {}
    for i, key in enumerate(design_name(f) for f in files):
        union(i, first.setdefault(("d", key), i))
    for i, pid in enumerate(payload_ids):
        union(i, first.setdefault(("p", pid), i))
    return np.array([f"comp{find(i):05d}" for i in range(len(files))])


def _assert_side_disjoint(tag_arrays, idx_a, idx_b, name_a, name_b):
    for tag, arr in tag_arrays.items():
        overlap = {arr[i] for i in idx_a} & {arr[i] for i in idx_b}
        assert not overlap, (
            f"{len(overlap)} {tag}(s) on both {name_a} and {name_b} sides, "
            f"e.g. {sorted(overlap)[:5]}")


def payload_aware_grouped_split_indices(files, y, seed, payload_ids,
                                        components=None, quarantined=None,
                                        split_schema=SPLIT_SCHEMA_PAYLOAD_COMPONENT):
    """60/20/20 train/val/test indices, grouped by payload COMPONENT.

    Requires `payload_ids` (one per file) precomputed by the corpus index.
    When splitting a SUBSET of the corpus (canonical samples, post-quarantine
    files), pass `components` computed over the FULL corpus: deduplication
    removes alias files whose shared payloads bridge design keys, so
    recomputing components on the subset loses those edges and silently
    re-splits what the full graph joins (e.g. a test design's benign twin
    reaching train through an aliased-away payload). Only when `files` IS the
    whole corpus may `components` be omitted and derived here.

    Refuses quarantined inputs and asserts, per side pair: no shared design
    identity, no shared exact payload class, no shared source-file alias
    (implied by payload disjointness, asserted independently anyway), and no
    shared component.
    """
    assert split_schema == SPLIT_SCHEMA_PAYLOAD_COMPONENT, split_schema
    files = list(files)
    y = np.asarray(y)
    payload_ids = np.asarray(payload_ids)
    if quarantined is not None:
        bad = [files[i] for i in range(len(files)) if quarantined[i]]
        assert not bad, (f"{len(bad)} quarantined file(s) passed to the "
                         f"corrected split, e.g. {bad[:3]} -- filter them "
                         f"out before splitting")

    if components is None:
        comps = payload_component_labels(files, payload_ids)
    else:
        comps = np.asarray(components)
        assert len(comps) == len(files)
    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    idx_tr, idx_te = next(outer.split(np.zeros(len(y)), y, comps))
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    rel_t, rel_v = next(inner.split(np.zeros(len(idx_tr)), y[idx_tr],
                                    comps[idx_tr]))
    idx_t, idx_v = idx_tr[rel_t], idx_tr[rel_v]

    tags = {"design": np.array([design_name(f) for f in files]),
            "payload_class": payload_ids,
            "alias": np.array([os.path.basename(f) for f in files]),
            "component": comps}
    _assert_side_disjoint(tags, idx_t, idx_te, "train", "test")
    _assert_side_disjoint(tags, idx_v, idx_te, "val", "test")
    _assert_side_disjoint(tags, idx_t, idx_v, "train", "val")
    return idx_t, idx_v, idx_te


def log_split_v2(path, *, split_schema, seed, files, y, idx_t, idx_v, idx_te,
                 payload_ids, families, manifest_id, quarantined_excluded,
                 config, components=None):
    """Corrected-split log: schema, seed, physical/unique counts, component
    counts, class counts, families and design identities per side, exclusions,
    payload overlap (asserted empty), and the corpus-manifest id. Pass the
    same full-corpus `components` the split used (see
    payload_aware_grouped_split_indices)."""
    y = np.asarray(y)
    payload_ids = np.asarray(payload_ids)
    comps = (payload_component_labels(files, payload_ids)
             if components is None else np.asarray(components))
    designs = np.array([design_name(f) for f in files])
    families = np.asarray(families)

    def side(idx):
        return {"n_files": int(len(idx)),
                "n_unique_payloads": int(len({payload_ids[i] for i in idx})),
                "n_components": int(len({comps[i] for i in idx})),
                "n_benign": int(np.sum(y[idx] == 0)),
                "n_malicious": int(np.sum(y[idx] == 1)),
                "families": sorted({str(families[i]) for i in idx}),
                "designs": sorted({str(designs[i]) for i in idx})}

    overlap = sorted(({payload_ids[i] for i in idx_t}
                      | {payload_ids[i] for i in idx_v})
                     & {payload_ids[i] for i in idx_te})
    record = {"split_schema": split_schema, "seed": seed,
              "manifest_id": manifest_id,
              "n_files_total": int(len(files)),
              "n_unique_payloads_total": int(len(set(payload_ids))),
              "n_components_total": int(len(set(comps))),
              "quarantined_excluded": quarantined_excluded,
              "payload_overlap_train_test": overlap,   # asserted empty
              "config": config,
              "train": side(idx_t), "val": side(idx_v), "test": side(idx_te)}
    assert not overlap
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return record
