# Copyright (c) 2025, Rye Stahle-Smith; All rights reserved.
# PYNQ BLADEI: Bitstream-Level Abnormality Detection for Embedded Inference
# Description: Phase 0.5 corrected hybrid-CNN comparison. Runs the FROZEN
#              train_model.train_cnn_trojan_detector (architecture, epochs,
#              early stopping, pos_weight all unmodified; runtime compat shims
#              only, as in cnn_split_comparison.py) on CORRECTED inputs:
#              FDRI-payload byte sequences + FDRI-payload statistical
#              features, unique-payload samples, payload-component splits.
#              Regimes (per RESEARCH_PLAN.md Phase 0.5):
#                D  unique payloads + payload-component grouped split
#                   -- PRIMARY corrected grouped result
#                E  unique payloads + leave-one-family-out, eligible families
#                   -- PRIMARY generalization result
#              Pre-audit CNN numbers are read from
#              split_comparison_out/cnn_results.csv for comparison, never
#              recomputed. All models and scalers are fit fresh; no legacy
#              checkpoint or scaler is ever loaded (Decision B). Contaminated
#              diagnostics (B/C) are deliberately NOT reproduced with the CNN.
#
# Usage:
#   python3 phase05_cnn_comparison.py [--seeds 5] [--device auto]

import warnings
warnings.filterwarnings("ignore")

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from sklearn.metrics import (confusion_matrix, f1_score, precision_score,
                             recall_score)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

from bitstream_io import (PARSER_VERSION, SEQ_SCHEMA, STAT_SCHEMA,
                          ZYNQ7020_V4, CacheSchemaError,
                          extract_byte_sequence_fdri, load_versioned_npz,
                          save_versioned_npz)
from corpus_index import DEDUP_POLICY, INDEX_VERSION, load_index
import corpus_index as ci
from phase05_stat_comparison import (ISCAS85_EXCLUSION, content_hash,
                                     corpus_arrays, side_counts)
from split_utils import (SPLIT_SCHEMA_PAYLOAD_COMPONENT,
                         payload_aware_grouped_split_indices,
                         payload_component_labels, log_split_v2)


def install_shims_and_device(device_arg):
    """Frozen train_model + current torch need two runtime shims (identical
    to cnn_split_comparison.py); the device override is process-local."""
    import torch
    import train_model as tm

    assert ci.FAMILY_MAPPING == tm.FAMILY_MAPPING, \
        "corpus_index.FAMILY_MAPPING drifted from frozen train_model"

    if device_arg == "auto":
        device_arg = ("cuda" if torch.cuda.is_available() else
                      "mps" if torch.backends.mps.is_available() else "cpu")
    tm.DEVICE = torch.device(device_arg)

    class _ReduceLROnPlateauCompat(tm.ReduceLROnPlateau):
        def __init__(self, *a, verbose=False, **kw):
            super().__init__(*a, **kw)
    tm.ReduceLROnPlateau = _ReduceLROnPlateauCompat

    _orig_bce = torch.nn.BCEWithLogitsLoss

    class _BCEWithLogitsLossCompat(_orig_bce):
        def __init__(self, *a, pos_weight=None, **kw):
            if pos_weight is not None:
                pos_weight = pos_weight.to(tm.DEVICE)
            super().__init__(*a, pos_weight=pos_weight, **kw)
    torch.nn.BCEWithLogitsLoss = _BCEWithLogitsLossCompat
    return tm, torch


def load_or_extract_sequences(paths, relpaths, provenance, cache_path):
    try:
        arrays, _ = load_versioned_npz(cache_path, expected=provenance)
        if list(arrays["relpaths"]) == list(relpaths):
            print(f"(sequences loaded from versioned cache: {cache_path})")
            return arrays["X"]
        raise CacheSchemaError(f"{cache_path}: file list changed")
    except FileNotFoundError:
        pass
    print(f"=== Extracting {SEQ_SCHEMA} sequences for {len(paths)} files ===")
    X = np.empty((len(paths), 4096), dtype=np.int64)
    for i, p in enumerate(paths):
        X[i] = extract_byte_sequence_fdri(p, profile=ZYNQ7020_V4)
        if (i + 1) % 50 == 0 or i + 1 == len(paths):
            print(f"    {i + 1}/{len(paths)}")
    save_versioned_npz(cache_path, provenance, X=X,
                       relpaths=np.array(relpaths))
    return X


def run_cnn_once(tm, torch, tag, X_seq, X_stat, y, idx_t, idx_v, idx_te,
                 seed):
    """One fresh training run through the frozen harness; returns metrics."""
    scaler = StandardScaler().fit(X_stat[np.concatenate([idx_t, idx_v])])
    Xs = {k: scaler.transform(X_stat[i])
          for k, i in (("t", idx_t), ("v", idx_v), ("te", idx_te))}
    tm.set_seed(seed)
    print(f"\n##### RUN {tag}: train {len(idx_t)} / val {len(idx_v)} / "
          f"test {len(idx_te)} #####")
    model, test_bal_acc = tm.train_cnn_trojan_detector(
        X_seq[idx_t], Xs["t"], y[idx_t],
        X_seq[idx_v], Xs["v"], y[idx_v],
        X_seq[idx_te], Xs["te"], y[idx_te])

    test_loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.LongTensor(X_seq[idx_te]), torch.FloatTensor(Xs["te"]),
            torch.FloatTensor(y[idx_te])),
        batch_size=tm.BATCH_SIZE)
    criterion = torch.nn.BCEWithLogitsLoss()
    _, _, bal_check, y_pred, y_true = tm.evaluate_hybrid(model, test_loader,
                                                         criterion)
    assert abs(bal_check - test_bal_acc) < 1e-6
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    return {"bal_acc": float(test_bal_acc),
            "precision": precision_score(y_true, y_pred, pos_label=1,
                                         zero_division=0),
            "recall": recall_score(y_true, y_pred, pos_label=1,
                                   zero_division=0),
            "f1": f1_score(y_true, y_pred, pos_label=1, zero_division=0),
            "tn": int(cm[0, 0]), "fp": int(cm[0, 1]),
            "fn": int(cm[1, 0]), "tp": int(cm[1, 1])}


def main():
    p = argparse.ArgumentParser(description="Phase 0.5 corrected hybrid CNN")
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--device", default="auto",
                   choices=["auto", "cpu", "mps", "cuda"])
    p.add_argument("--index", default=os.path.join("corpus_out",
                                                   "corpus_index.json"))
    p.add_argument("--quarantine",
                   default=os.path.join("leakage_audit_out",
                                        "quarantine_contradictory.json"))
    p.add_argument("--outdir", default="phase05_out")
    p.add_argument("--pre-audit-csv",
                   default=os.path.join("split_comparison_out",
                                        "cnn_results.csv"))
    args = p.parse_args()

    tm, torch = install_shims_and_device(args.device)
    print(f"Device: {tm.DEVICE} (runtime override; train_model.py frozen)")

    index = load_index(args.index)
    with open(args.quarantine) as f:
        quarantine_doc = json.load(f)
    manifest_id = index["manifest_id"]
    index_hash = content_hash(index)
    quarantine_hash = content_hash(quarantine_doc)

    paths, y, pids, fams, quarantined, canonical = corpus_arrays(index)
    relpaths = [r["relpath"] for r in index["files"]]

    # Corrected CNN regimes use ONLY the canonical unique-payload samples,
    # ISCAS85 excluded by policy (same as the statistical table).
    keep = np.flatnonzero((fams != "ISCAS85") & canonical)
    assert not quarantined[keep].any()
    k_paths = [paths[i] for i in keep]
    k_rel = [relpaths[i] for i in keep]
    k_y, k_pids, k_fams = y[keep], pids[keep], fams[keep]
    # Components over the FULL corpus, then subset: dedup collapses the alias
    # files whose shared payloads bridge design keys, so components computed
    # on the canonical subset alone would drop those edges (see test_splits).
    comps = payload_component_labels(paths, pids)[keep]
    print(f"canonical corpus for CNN: {len(keep)} unique payloads "
          f"({int((k_y == 0).sum())} B / {int((k_y == 1).sum())} M), "
          f"{len(set(comps))} components\n{ISCAS85_EXCLUSION}")

    base_prov = {"parser_version": PARSER_VERSION,
                 "profile": ZYNQ7020_V4.name, "manifest_id": manifest_id,
                 "corpus_index_version": INDEX_VERSION,
                 "corpus_index_hash": index_hash,
                 "quarantine_hash": quarantine_hash,
                 "dedup_policy": DEDUP_POLICY,
                 "population": "canonical_unique_payloads_excl_ISCAS85"}
    X_seq = load_or_extract_sequences(
        k_paths, k_rel, {**base_prov, "extractor_schema": SEQ_SCHEMA},
        os.path.join(args.outdir, "sequences_fdri_seq4096_v1.npz"))

    # Stat branch: reuse the phase05 stat cache (full corpus), subset to keep.
    stat_cache = os.path.join(args.outdir, "features_fdri_stat_278_v1.npz")
    arrays, _ = load_versioned_npz(stat_cache, expected={
        "extractor_schema": STAT_SCHEMA, "manifest_id": manifest_id,
        "corpus_index_hash": index_hash, "quarantine_hash": quarantine_hash})
    assert list(arrays["relpaths"]) == relpaths
    X_stat = arrays["X"][keep]

    os.makedirs(os.path.join(args.outdir, "runs"), exist_ok=True)
    csv_path = os.path.join(args.outdir, "cnn_results.csv")
    csv_file = open(csv_path, "w", newline="")
    fields = ["regime", "weighting", "seed", "family", "n_train", "n_val",
              "n_test", "n_test_benign", "n_test_malicious", "bal_acc",
              "precision", "recall", "f1", "tn", "fp", "fn", "tp", "valid",
              "invalid_reason", "extractor_schema", "split_schema",
              "manifest_id", "device"]
    writer = csv.DictWriter(csv_file, fieldnames=fields)
    writer.writeheader()
    scores = defaultdict(list)

    def record(regime, seed, family, sides, m, split_schema, valid=True,
               reason=""):
        row = {"regime": regime, "weighting": "PRIMARY_unique_payload",
               "seed": seed, "family": family or "",
               "n_train": sides[0], "n_val": sides[1], "n_test": sides[2],
               "n_test_benign": sides[3], "n_test_malicious": sides[4],
               "valid": valid, "invalid_reason": reason,
               "extractor_schema": f"{SEQ_SCHEMA}+{STAT_SCHEMA}",
               "split_schema": split_schema, "manifest_id": manifest_id,
               "device": str(tm.DEVICE)}
        if m:
            row.update({k: (f"{v:.4f}" if isinstance(v, float) else v)
                        for k, v in m.items()})
            scores[regime].append(m["bal_acc"])
        writer.writerow(row)
        csv_file.flush()

    def three_way_valid(idx_t, idx_v, idx_te):
        for name, idx in (("train", idx_t), ("val", idx_v), ("test", idx_te)):
            if len(set(k_y[idx])) < 2:
                return (f"{name} side is single-class "
                        f"({int((k_y[idx] == 0).sum())} B / "
                        f"{int((k_y[idx] == 1).sum())} M)")
        return None

    cnn_cfg = {"model": "HybridCNN (train_model.py, frozen)",
               "sequence_length": tm.SEQUENCE_LENGTH,
               "embedding_dim": tm.EMBEDDING_DIM, "dropout": tm.DROPOUT,
               "batch_size": tm.BATCH_SIZE, "epochs_max": tm.EPOCHS,
               "patience": tm.PATIENCE, "learning_rate": tm.LEARNING_RATE,
               "pos_weight": 0.75, "fresh_weights_and_scaler": True,
               "compat_shims": ["ReduceLROnPlateau: drop removed verbose "
                                "kwarg", "BCEWithLogitsLoss: pos_weight to "
                                "active device"],
               "exclusions": {"ISCAS85": ISCAS85_EXCLUSION}}

    # ---- D: unique payloads, payload-component grouped split ---------------
    for seed in range(args.seeds):
        idx_t, idx_v, idx_te = payload_aware_grouped_split_indices(
            k_paths, k_y, seed, payload_ids=k_pids, components=comps)
        reason = three_way_valid(idx_t, idx_v, idx_te)
        sides = (len(idx_t), len(idx_v), len(idx_te),
                 int((k_y[idx_te] == 0).sum()), int((k_y[idx_te] == 1).sum()))
        log_split_v2(os.path.join(args.outdir, "runs",
                                  f"split_cnnD_seed{seed}.json"),
                     split_schema=SPLIT_SCHEMA_PAYLOAD_COMPONENT, seed=seed,
                     files=k_paths, y=k_y, idx_t=idx_t, idx_v=idx_v,
                     idx_te=idx_te, payload_ids=k_pids, families=k_fams,
                     components=comps, manifest_id=manifest_id,
                     quarantined_excluded={"n": int(quarantined.sum()),
                                           "reason": "no_bitstream_trace"},
                     config={**cnn_cfg, "regime": "cnn_D",
                             "invalid_reason": reason})
        if reason:
            print(f"[cnn_D seed {seed}] INVALID: {reason}")
            record("cnn_D_fdri_component_unique", seed, None, sides, None,
                   SPLIT_SCHEMA_PAYLOAD_COMPONENT, valid=False, reason=reason)
            continue
        m = run_cnn_once(tm, torch, f"cnn_D_seed{seed}", X_seq, X_stat, k_y,
                         idx_t, idx_v, idx_te, seed)
        record("cnn_D_fdri_component_unique", seed, None, sides, m,
               SPLIT_SCHEMA_PAYLOAD_COMPONENT)

    # ---- E: unique payloads, LOFO over eligible families -------------------
    eligible, exclusions = [], {"ISCAS85": ISCAS85_EXCLUSION}
    for fam in sorted(set(k_fams)):
        fy = k_y[k_fams == fam]
        if len(set(fy)) < 2:
            exclusions[fam] = (f"single-class after quarantine "
                               f"({int((fy == 0).sum())} B / "
                               f"{int((fy == 1).sum())} M unique payloads)")
            print(f"[cnn_E {fam}] EXCLUDED: {exclusions[fam]}")
        else:
            eligible.append(fam)
    all_idx = np.arange(len(keep))
    for seed in range(args.seeds):
        for fam in eligible:
            idx_te = all_idx[k_fams == fam]
            idx_rest = all_idx[k_fams != fam]
            sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True,
                                        random_state=seed)
            rel_t, rel_v = next(sgkf.split(np.zeros(len(idx_rest)),
                                           k_y[idx_rest], comps[idx_rest]))
            idx_t, idx_v = idx_rest[rel_t], idx_rest[rel_v]
            reason = three_way_valid(idx_t, idx_v, idx_te)
            sides = (len(idx_t), len(idx_v), len(idx_te),
                     int((k_y[idx_te] == 0).sum()),
                     int((k_y[idx_te] == 1).sum()))
            tag = f"cnn_E_seed{seed}_{fam.replace('/', '-')}"
            log_split_v2(os.path.join(args.outdir, "runs",
                                      f"split_{tag}.json"),
                         split_schema="lofo_unique_payload_v1", seed=seed,
                         files=k_paths, y=k_y, idx_t=idx_t, idx_v=idx_v,
                         idx_te=idx_te, payload_ids=k_pids, families=k_fams,
                         components=comps, manifest_id=manifest_id,
                         quarantined_excluded={"n": int(quarantined.sum()),
                                               "reason": "no_bitstream_trace"},
                         config={**cnn_cfg, "regime": "cnn_E", "family": fam,
                                 "invalid_reason": reason})
            if reason:
                print(f"[{tag}] INVALID: {reason}")
                record("cnn_E_fdri_lofo_unique", seed, fam, sides, None,
                       "lofo_unique_payload_v1", valid=False, reason=reason)
                continue
            m = run_cnn_once(tm, torch, tag, X_seq, X_stat, k_y,
                             idx_t, idx_v, idx_te, seed)
            record("cnn_E_fdri_lofo_unique", seed, fam, sides, m,
                   "lofo_unique_payload_v1")

    csv_file.close()

    # ---- summary (delegated: NOT-ESTIMABLE / per-family+macro rules) -------
    from phase05_summarize import summarize_cnn
    summary = (summarize_cnn(args.outdir, pre_audit_csv=args.pre_audit_csv)
               + f"\nmanifest {manifest_id}, {args.seeds} seeds, "
               f"device {tm.DEVICE}"
               + f"\nexclusions: {json.dumps(exclusions, indent=2)}")
    print("\n" + summary)
    with open(os.path.join(args.outdir, "cnn_summary.txt"), "w") as f:
        f.write(summary + "\n")
    with open(os.path.join(args.outdir, "cnn_run_meta.json"), "w") as f:
        json.dump({"generated": datetime.now(timezone.utc).isoformat(),
                   "manifest_id": manifest_id,
                   "corpus_index_hash": index_hash,
                   "quarantine_hash": quarantine_hash,
                   "config": cnn_cfg, "exclusions": exclusions,
                   "seeds": args.seeds, "device": str(tm.DEVICE)}, f,
                  indent=2)
    print(f"results -> {csv_path}")


if __name__ == "__main__":
    main()
